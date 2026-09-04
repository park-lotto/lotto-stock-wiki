# -*- coding: utf-8 -*-
"""1단계 정확도 서버 실측 — SSH 없이 관리자 API로 돌린다(2026-09-05).

왜: 회사·집 PC에서 서버 22번 포트가 막혀 로컬 4편으로만 쟀다. 443은 열려 있으니 서버가 **스스로**
최근 작업의 소스 영상을 골라 [기존 추출 vs B1(컷별 프레임 태깅)]의 묘사↔프레임 정확도를 같은 판정기로 재고
결과를 파일로 남긴다. 사장님이 할 일은 없다(관리자 계정으로 시작 버튼/URL 한 번).

동작(백그라운드 스레드 1개, 동시 1건):
  · 최근 mix_jobs 중 extract가 있고 작업 폴더에 mp4가 남아 있는 소스 N개
  · 기존: job["extract"][vid]["segments"] 그대로 → 판정
  · B1: frame_script.extract_script_frames(mp4, vid) 실행(서버 키·Whisper 사용) → 판정
  · 판정 = tag_qa_frames(_extract_frames + _judge, 전수). 같은 잣대로 상대 비교만 믿는다(판정기는 관대하다)
결과: data/probes/frame_accuracy_<ts>.json + 모듈 상태(진행률·요약). 픽 로직엔 안 쓴다.
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

_STATE = {"status": "idle", "started": None, "done": 0, "total": 0, "results": [], "summary": {},
          "path": "", "error": ""}
_LOCK = threading.Lock()


def _judge_all(segments, video_path, tmp_dir):
    """세그 전부를 프레임 대조 → (점수 0~1 or None, 대조 건수, 맞음/부분/틀림)."""
    from shopping_shorts import tag_qa_frames as T
    picked = [(i, s) for i, s in enumerate(segments or []) if T._usable(s)]
    if not picked:
        return None, 0, {}
    paths, kept = T._extract_frames(video_path, picked, tmp_dir)
    if not paths:
        return None, 0, {}
    verdicts = T._judge(paths, kept)
    for _ in range(2):
        if verdicts:
            break
        time.sleep(6)
        verdicts = T._judge(paths, kept)
    score, detail = T.score_verdicts(verdicts, kept)
    counts = {}
    for d in detail or []:
        v = d.get("verdict") if isinstance(d, dict) else None
        if v:
            counts[v] = counts.get(v, 0) + 1
    return score, len(kept), counts


def pick_sources(store, work_dir, n=30):
    """최근 작업에서 (job_id, vid, mp4 경로, 기존 세그먼트) — 영상 파일이 아직 있는 것만."""
    out = []
    with store._conn() as c:
        rows = c.execute("SELECT job_id, extract_json FROM mix_jobs WHERE extract_json IS NOT NULL "
                         "AND extract_json != '' ORDER BY created_at DESC LIMIT 200").fetchall()
    for job_id, ex_json in rows:
        try:
            ex = json.loads(ex_json or "{}")
        except Exception:      # noqa: BLE001
            continue
        for vid, e in (ex or {}).items():
            if not isinstance(e, dict) or not e.get("segments"):
                continue
            d = Path(work_dir) / job_id / vid
            mp4 = next(d.glob("*.mp4"), None) if d.exists() else None
            if not mp4:
                continue
            out.append({"job_id": job_id, "vid": vid, "path": str(mp4), "classic": e.get("segments")})
            if len(out) >= n:
                return out
    return out


def summarize(results):
    """[{classic_score, b1_score, ...}] → 평균·우위 건수(순수 함수)."""
    cs = [r["classic_score"] for r in results if r.get("classic_score") is not None]
    bs = [r["b1_score"] for r in results if r.get("b1_score") is not None]
    both = [r for r in results if r.get("classic_score") is not None and r.get("b1_score") is not None]
    return {
        "videos": len(results),
        "classic_avg": round(sum(cs) / len(cs), 3) if cs else None,
        "b1_avg": round(sum(bs) / len(bs), 3) if bs else None,
        "b1_better": sum(1 for r in both if r["b1_score"] > r["classic_score"]),
        "classic_better": sum(1 for r in both if r["b1_score"] < r["classic_score"]),
        "tie": sum(1 for r in both if r["b1_score"] == r["classic_score"]),
        "b1_secs_avg": round(sum(r.get("b1_secs") or 0 for r in results) / max(1, len(results)), 1),
        "b1_fail": sum(1 for r in results if r.get("b1_error")),
    }


def _run(store, work_dir, n, out_dir):
    from shopping_shorts import frame_script
    try:
        # ★키가 없으면 판정이 조용히 None으로 떨어진다(로컬 실측에서 확인) — 상태에 사유를 남긴다.
        try:
            from shopping_shorts import comment_gen
            if comment_gen._current_key_and_idx()[0] is None:
                with _LOCK:
                    _STATE["error"] = "Gemini 키 없음(SHORTS 풀 0개) — 판정·B1 태깅이 빈 값으로 떨어진다"
        except Exception:      # noqa: BLE001
            pass
        srcs = pick_sources(store, work_dir, n=n)
        with _LOCK:
            _STATE.update(total=len(srcs), done=0, results=[])
        for s in srcs:
            r = {"job_id": s["job_id"], "vid": s["vid"], "classic_segs": len(s["classic"])}
            tmp = tempfile.mkdtemp(prefix="probe_fa_")
            try:
                r["classic_score"], r["classic_n"], r["classic_counts"] = _judge_all(s["classic"], s["path"], tmp)
            except Exception as e:      # noqa: BLE001
                r["classic_error"] = repr(e)[:200]
            t0 = time.time()
            try:
                b1 = frame_script.extract_script_frames(s["path"], s["vid"], caption="", _no_classic=True)
                r["b1_secs"] = round(time.time() - t0, 1)
                r["b1_segs"] = len(b1.get("segments") or [])
                r["b1_transcript_chars"] = len(b1.get("full_text") or "")
                r["b1_ko_chars"] = len(b1.get("full_text_ko") or "")
                r["b1_brief"] = (b1.get("source_brief") or {}).get("flow", "")[:120]
                r["b1_score"], r["b1_n"], r["b1_counts"] = _judge_all(b1.get("segments"), s["path"],
                                                                     tempfile.mkdtemp(prefix="probe_fb_"))
            except Exception as e:      # noqa: BLE001
                r["b1_error"] = repr(e)[:200]
            with _LOCK:
                _STATE["results"].append(r)
                _STATE["done"] += 1
                _STATE["summary"] = summarize(_STATE["results"])
        path = Path(out_dir) / ("frame_accuracy_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            payload = {"started": _STATE["started"], "summary": _STATE["summary"], "results": _STATE["results"]}
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            _STATE.update(status="done", path=str(path))
    except Exception as e:      # noqa: BLE001
        with _LOCK:
            _STATE.update(status="error", error=repr(e)[:300])
        print(f"[probe_frame_accuracy] 실패: {e!r}", file=sys.stderr)


def start(store, work_dir, out_dir, n=30):
    """백그라운드 시작. 이미 도는 중이면 False."""
    with _LOCK:
        if _STATE["status"] == "running":
            return False
        _STATE.update(status="running", started=time.strftime("%Y-%m-%dT%H:%M:%S"), done=0, total=0,
                      results=[], summary={}, path="", error="")
    th = threading.Thread(target=_run, args=(store, work_dir, max(1, min(int(n), 40)), out_dir), daemon=True)
    th.start()
    return True


def state():
    with _LOCK:
        return dict(_STATE, results=list(_STATE["results"]))
