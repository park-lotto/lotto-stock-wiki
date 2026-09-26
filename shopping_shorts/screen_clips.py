# -*- coding: utf-8 -*-
"""완성본 컷 = 편집 화면 컷 (2026-09-26 사장님 "근본해결").

왜: 컷 계산이 두 벌이었다 — 화면(static/scene_play.js planClips, 브라우저)과 서버(video_assemble.plan_beat_clips_for).
규칙을 하나씩 맞춰도 계속 어긋났다(하루에 네 군데: 손 컷 정리·컷 리듬 칸·조각 끝 이어 읽기·구절 맞춤 기본값).
7일 522 job 중 97 job·502칸이 화면≠완성본이었다(tools 점검). 그래서 서버가 **화면 코드를 그대로 node로 돌려**
그 컷을 쓴다. 계산은 화면 한 벌만 남는다 — 화면을 고치면 완성본이 자동으로 따라간다.

흐름: warm(job) — 작업 입구(렌더 입력·소스 길이 조회)가 부른다. 화면 데이터(api_mix_scene_lab_data와 같은 것)로
      runner.js 를 돌려 칸마다 컷을 받아 **칸 내용 키**로 캐시한다.
      lookup(beat, tts_dur, src_durs) — video_assemble.plan_beat_clips_for 맨 앞에서 부른다. 없으면 None(종전 계산).
★실패는 조용히 종전 계산으로 떨어진다(렌더를 막지 않는다) — 대신 stderr에 남긴다.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RUNNER = _HERE / "screen_clips_runner.js"
_SCENE_PLAY = _HERE / "static" / "scene_play.js"
_CACHE = {}          # 칸 키 → {"t": 화면 칸 길이, "c": [컷]}
_DATA_SEEN = {}      # job_id → 화면 데이터 해시(같으면 다시 안 돌린다)
_LOCK = threading.Lock()
_CACHE_MAX = 20000
# 컷 계산에 쓰이지 않는 칸 필드 — 키에서 뺀다(그림에 무관한데 자주 바뀌는 것)
_VOLATILE = {"screen_clips", "fit", "fit_evidence", "effect", "alternates_meta", "scene_desc", "gate"}


def _enabled():
    return os.getenv("SCREEN_CLIPS", "1") not in ("0", "false", "off")


def beat_key(beat):
    """칸 내용 키 — 화면 컷을 가르는 입력 전부(재료·손 컷·구절 맞춤·리듬·자막·음성 파일)."""
    b = {k: v for k, v in (beat or {}).items() if k not in _VOLATILE and not str(k).startswith("_")}
    try:
        raw = json.dumps(b, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:      # noqa: BLE001
        return None
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _scene_data(job_id):
    from shopping_shorts import app as _app       # 함수 안에서 — 최상위면 순환 import
    r = _app.api_mix_scene_lab_data(job_id)
    d = r if isinstance(r, dict) else json.loads(r.body)
    return (d or {}).get("data")


def warm(job):
    """작업 하나의 화면 컷을 계산해 캐시에 넣는다. 성공한 칸 수(실패 0)."""
    if not _enabled() or not job or not job.get("job_id"):
        return 0
    jid = job["job_id"]
    try:
        data = _scene_data(jid)
        if not data or not data.get("beats"):
            return 0
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        h = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        with _LOCK:
            if _DATA_SEEN.get(jid) == h:
                return len(data["beats"])
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(raw)
            tmp = f.name
        try:
            out = subprocess.run(["node", str(_RUNNER), str(_SCENE_PLAY), tmp],
                                 capture_output=True, text=True, timeout=60)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        if out.returncode != 0:
            print("[screen_clips] %s 화면 계산 실패(종전 계산 사용): %s" % (jid, out.stderr.strip()[-300:]),
                  file=sys.stderr)
            return 0
        res = json.loads(out.stdout)
        plan_beats = (job.get("edit_plan") or {}).get("beats") or []
        n = 0
        with _LOCK:
            if len(_CACHE) > _CACHE_MAX:
                _CACHE.clear()
            # 화면 데이터의 칸 = 편성표의 칸(같은 순서). 키는 **편성표 칸**으로 만든다 — 렌더가 보는 그 dict다.
            for b, r in zip(plan_beats, res):
                k = beat_key(b)
                if k and r and r.get("c") is not None:
                    _CACHE[k] = r
                    n += 1
            _DATA_SEEN[jid] = h
        return n
    except Exception as e:      # noqa: BLE001 — 화면 계산 실패가 렌더를 막으면 안 된다
        print("[screen_clips] %s 화면 계산 예외(종전 계산 사용): %s: %s" % (jid, type(e).__name__, e),
              file=sys.stderr)
        return 0


def has(beat):
    """이 칸의 화면 컷이 준비돼 있나."""
    if not _enabled():
        return False
    k = beat_key(beat)
    with _LOCK:
        r = _CACHE.get(k) if k else None
    return bool(r and r.get("c"))


def lookup(beat, tts_dur, src_durs):
    """화면 컷 → 렌더 조각 계획 [{video_id,start,src_dur,out_dur[,playback_speed]}]. 없거나 못 쓰면 None."""
    if not _enabled():
        return None
    k = beat_key(beat)
    with _LOCK:
        r = _CACHE.get(k) if k else None
    if not r or not r.get("c"):
        return None
    cuts = r["c"]
    try:
        t_screen = float(r.get("t") or 0) or sum(float(c["d"]) for c in cuts)
        scale = (float(tts_dur) / t_screen) if (tts_dur and t_screen > 1e-3) else 1.0
    except (TypeError, ValueError):
        scale = 1.0
    try:
        sync = float((beat or {}).get("sync_speed") or 1.0)
    except (TypeError, ValueError):
        sync = 1.0
    plan = []
    for c in cuts:
        vid = c.get("v")
        total = float((src_durs or {}).get(vid, 0.0) or 0.0)
        if total <= 0.05:
            return None                         # 소스를 못 읽는다 — 종전 계산이 손상 소스를 거른다
        start = float(c.get("s") or 0.0)
        out = float(c.get("d") or 0.0) * scale
        sd = c.get("sd")
        sd = float(sd) if sd is not None else out
        if out <= 1e-3:
            continue
        start = max(0.0, min(start, total - 0.05))
        sd = max(1e-3, min(sd, total - start))
        p = {"video_id": vid, "start": start, "src_dur": sd, "out_dur": out, "screen": True}
        # 배속: 화면이 속도 맞추기(fit)로 끝까지 움직였거나 통합 속도를 줬거나 읽는 길이가 더 길면 — 그 비율 그대로.
        #   그 밖(읽는 길이 < 화면 길이)은 느리게(1.15배 상한)+정지 — 화면 미리보기 합본(pvproxy)과 같은 기계.
        if c.get("fit") or abs(sync - 1.0) > 1e-6 or sd > out + 1e-3:
            p["playback_speed"] = sd / out
        plan.append(p)
    return plan or None
