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
import shutil
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
    # ★빈 묘사는 판정 대상에서 빠진다(_usable) — 대신 여기서 따로 세어 결과에 남긴다(맞음으로 세지 않는다)
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
    # ★판정 커버리지(2026-09-05 리뷰 M2): 판정이 절반만 돌아오면 그 점수는 '판정된 것만'의 평균이다.
    #   80% 미만이면 점수를 믿지 않는다(None) — 숫자가 있는데 틀린 것보다 없는 게 낫다.
    judged = len(detail or [])
    counts["_judged"] = judged
    counts["_kept"] = len(kept)
    if kept and judged < 0.8 * len(kept):
        return None, len(kept), counts
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
    # ★평균은 **둘 다 판정된 영상**에서만(2026-09-05 리뷰 M2) — 한쪽만 빠진 집합끼리 비교하면 편향된다
    both = [r for r in results if r.get("classic_score") is not None and r.get("b1_score") is not None]
    cs = [r["classic_score"] for r in both]
    bs = [r["b1_score"] for r in both]
    return {
        "videos": len(results),
        "compared": len(both),
        "classic_avg": round(sum(cs) / len(cs), 3) if cs else None,
        "b1_avg": round(sum(bs) / len(bs), 3) if bs else None,
        "unjudged": sum(1 for r in results if r.get("classic_score") is None or r.get("b1_score") is None),
        # 전사 사유별 편수(2026-09-05: 서버 30편 전사 0/30인데 키·오디오·API 중 무엇인지 몰랐다)
        "transcript_status": dict(__import__("collections").Counter(
            str(r.get("b1_transcript_status") or "?") for r in results if r.get("b1_transcript_status") is not None)),
        "b1_better": sum(1 for r in both if r["b1_score"] > r["classic_score"]),
        "classic_better": sum(1 for r in both if r["b1_score"] < r["classic_score"]),
        "tie": sum(1 for r in both if r["b1_score"] == r["classic_score"]),
        "b1_secs_avg": round(sum(r.get("b1_secs") or 0 for r in results) / max(1, len(results)), 1),
        "b1_fail": sum(1 for r in results if r.get("b1_error")),
        # ★빈 묘사는 점수에 안 들어간다 — 그래서 따로 센다. 이 수가 0이 아니면 위 평균은 '판정된 것만'의 평균이다.
        "b1_empty_segs": sum(int(r.get("b1_empty") or 0) for r in results),
        "b1_segs_total": sum(int(r.get("b1_segs") or 0) for r in results),
        "classic_empty_segs": sum(int(r.get("classic_empty") or 0) for r in results),
        # 라벨(결·쓰임) 일치율 — 목표표 3번(2026-09-05 서버 측정). 텍스트 판정(관대)이라 상대 비교만.
        "classic_role_pct": _pct(results, "classic_role_ok", "classic_label_n"),
        "classic_label_pct": _pct(results, "classic_label_ok", "classic_label_n"),
        "b1_role_pct": _pct(results, "b1_role_ok", "b1_label_n"),
        "b1_label_pct": _pct(results, "b1_label_ok", "b1_label_n"),
    }


def _pct(results, ok_key, n_key):
    """라벨 판정된 구간 합계 기준 백분율(정수). 판정이 하나도 없으면 None."""
    n = sum(int(r.get(n_key) or 0) for r in results)
    if not n:
        return None
    return int(100 * sum(int(r.get(ok_key) or 0) for r in results) / n)


_LABEL_MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash")


def judge_labels(segs, *, _call=None):
    """결(shot_role)·쓰임(label)이 묘사·변화에 맞게 붙었는지 텍스트로 판정(영상당 1회). → (결 맞음, 쓰임 맞음, 판정 구간 수).
    tools/probes/label_agreement.py의 판정을 서버 프로브에 옮긴 것(목표표 3번 — 서버에서 재야 한다).
    빈 묘사 구간은 분모에서 뺀다(둘 다 false로 세면 빈 묘사가 이중 벌점). 실패·키 없음 → (0, 0, 0)."""
    from shopping_shorts import frame_script
    items = [{"no": i + 1, "scene_desc": s.get("scene_desc", ""), "change": s.get("change", ""),
              "shot_role": s.get("shot_role", ""), "label": s.get("label", "")}
             for i, s in enumerate(segs or []) if (s.get("scene_desc") or "").strip()]
    if not items:
        return 0, 0, 0
    try:
        from shopping_shorts import shot_roles
        guide = shot_roles.guide_block()
    except Exception:      # noqa: BLE001
        guide = ""
    prompt = ("아래는 영상 구간마다 AI가 적은 [묘사(scene_desc)·변화(change)]와 거기에 붙인 [결(shot_role)·쓰임(label)]이다. "
              "묘사·변화를 사실로 보고, 결과 쓰임이 그 묘사에 **맞게 붙었는지** 항목마다 판정해라.\n결 어휘 정의:\n" + guide
              + "\n판정 규칙: role_ok = 결이 묘사와 맞으면 true(묘사에 근거가 없거나 반대면 false). "
              "label_ok = 쓰임이 '왜 이 장면이 여기 있나'를 묘사에 맞게 12자 안팎으로 잡았으면 true(빈칸·묘사 반복·무관하면 false).\n"
              + json.dumps(items, ensure_ascii=False)
              + '\n출력은 JSON {"items":[{"no":1,"role_ok":true,"label_ok":true,"why":"한 줄"}]} 만.')
    text = None
    if _call is not None:
        text = _call(prompt)
    else:
        try:
            from google import genai
            from google.genai import types
            from shopping_shorts import comment_gen
            for model in _LABEL_MODELS:
                key, _ = comment_gen._current_key_and_idx()
                if key is None:
                    return 0, 0, 0
                try:
                    cli = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=150_000))
                    text = cli.models.generate_content(model=model, contents=[prompt],
                                                       config=types.GenerateContentConfig(
                                                           response_mime_type="application/json")).text
                    break
                except Exception as e:      # noqa: BLE001 — 다음 모델·키로
                    print(f"probe.judge_labels: {model} 실패 {str(e)[:80]}", file=sys.stderr)
                    time.sleep(3)
        except Exception as e:      # noqa: BLE001
            print(f"probe.judge_labels: 건너뜀 {e!r}"[:160], file=sys.stderr)
            return 0, 0, 0
    try:
        data = frame_script.loads_lenient(text or "") or {}
    except Exception:      # noqa: BLE001 — JSON이 아니면 판정 0(분모는 남긴다)
        data = {}
    res = data.get("items") if isinstance(data, dict) else data
    by = {int(x.get("no", 0)): x for x in (res or []) if isinstance(x, dict)}
    nos = [it["no"] for it in items]
    ro = sum(1 for n in nos if by.get(n, {}).get("role_ok") is True)
    lo = sum(1 for n in nos if by.get(n, {}).get("label_ok") is True)
    return ro, lo, len(nos)


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
                r["b1_transcript_status"] = b1.get("transcript_status")
                r["b1_brief"] = (b1.get("source_brief") or {}).get("flow", "")[:120]
                r["b1_empty"] = sum(1 for x in (b1.get("segments") or []) if not (x.get("scene_desc") or "").strip())
                r["b1_empty_ratio"] = b1.get("tag_empty_ratio")
                # ★태깅 실패는 '정확도 낮음'이 아니라 '실패'다(2026-09-05 리뷰 M1) — 점수 대신 오류로 남긴다
                if (r["b1_empty_ratio"] or 0) > frame_script.EMPTY_FAIL_RATIO:
                    r["b1_error"] = "태깅 실패(묘사 빈 비율 %.0f%%)" % (100 * r["b1_empty_ratio"])
                    with _LOCK:
                        _STATE["results"].append(r)
                        _STATE["done"] += 1
                        _STATE["summary"] = summarize(_STATE["results"])
                    shutil.rmtree(tmp, ignore_errors=True)
                    continue
                r["b1_score"], r["b1_n"], r["b1_counts"] = _judge_all(b1.get("segments"), s["path"], tmp)
                r["classic_empty"] = sum(1 for x in (s["classic"] or []) if not (x.get("scene_desc") or "").strip())
                # 라벨 일치(결·쓰임) — 기존·B1 각 1회 텍스트 판정. 실패해도 점수 판정엔 영향 없다.
                for name, segs in (("classic", s["classic"]), ("b1", b1.get("segments") or [])):
                    ro, lo, n = judge_labels(segs)
                    r[name + "_role_ok"], r[name + "_label_ok"], r[name + "_label_n"] = ro, lo, n
            except Exception as e:      # noqa: BLE001
                r["b1_error"] = repr(e)[:200]
            with _LOCK:
                _STATE["results"].append(r)
                _STATE["done"] += 1
                _STATE["summary"] = summarize(_STATE["results"])
            shutil.rmtree(tmp, ignore_errors=True)          # 프레임 임시폴더 정리(리뷰 M6)
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
