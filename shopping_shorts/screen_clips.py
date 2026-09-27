# -*- coding: utf-8 -*-
"""완성본 컷 = 편집 화면 컷 (2026-09-26 사장님 "근본해결").

왜: 컷 계산이 두 벌이었다 — 화면(static/scene_play.js planClips, 브라우저)과 서버(video_assemble.plan_beat_clips_for).
규칙을 하나씩 맞춰도 계속 어긋났다(하루에 네 군데: 손 컷 정리·컷 리듬 칸·조각 끝 이어 읽기·구절 맞춤 기본값).
7일 522 job 중 97 job·502칸이 화면≠완성본이었다(tools 점검). 그래서 서버가 **화면 코드를 그대로 node로 돌려**
그 컷을 쓴다. 계산은 화면 한 벌만 남는다 — 화면을 고치면 완성본이 자동으로 따라간다.

흐름: warm(job) — 작업 입구(렌더 입력·소스 길이 조회)가 부른다. 화면 데이터(api_mix_scene_lab_data와 같은 것)로
      runner.js 를 돌려 칸마다 컷을 받아 **칸 내용 키**로 캐시한다.
      lookup(beat, tts_dur, src_durs) — video_assemble.plan_beat_clips_for 맨 앞에서 부른다. 없으면 None(종전 계산).
★실패는 종전 계산으로 떨어진다(렌더를 막지 않는다) — 대신 **조용히가 아니라** 경보를 남긴다(2026-09-27):
  화면 데이터가 있는 job인데 예비 계산으로 떨어진 칸 → stderr `[screen_clips] FALLBACK job=… beat=… why=…`
  + 프로세스 내 기록 FALLBACKS. 화면 데이터가 아예 없는 job(옛 job, 404)은 예비 계산이 정상이라 info 한 줄만.
  렌더가 warm 뒤에 칸을 고쳐 쓰면(키가 달라져 lookup이 빗나간다) → `BEAT_MUTATED`로 같은 기록에 남긴다.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
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

# ── 경보(조용한 되돌아가기 금지, 2026-09-27) ─────────────────────────────────────────────
# FALLBACKS: [{"job","beat","why","ts","kind"}] — kind = "FALLBACK"(화면 컷 대신 예비 계산) | "BEAT_MUTATED"
FALLBACKS = []
_FALLBACKS_MAX = 5000
_JOB_STATE = {}      # job_id → {"screen": "ok"|"none"|"failed", "why": 사유} — "none"(옛 job)만 조용하다
_OWNER = {}          # 칸 음성 파일(tts_path) → job_id — 칸 키가 달라져도 음성 파일은 그대로라 어느 job 칸인지 안다
_SEEN = set()        # (kind, job, beat, why) — 같은 렌더 안에서 같은 경보를 여러 번 찍지 않게(begin이 비운다)


def _record(job_id, beat_idx, why, kind="FALLBACK"):
    """경보 한 건 — stderr 한 줄 + FALLBACKS. 같은 (kind, job, beat, why)는 begin() 전까지 한 번만."""
    sig = (kind, job_id, beat_idx, why)
    with _LOCK:
        if sig in _SEEN:
            return
        _SEEN.add(sig)
        FALLBACKS.append({"job": job_id, "beat": beat_idx, "why": why, "ts": time.time(), "kind": kind})
        if len(FALLBACKS) > _FALLBACKS_MAX:
            del FALLBACKS[: len(FALLBACKS) - _FALLBACKS_MAX]
    if kind == "BEAT_MUTATED":
        print("[screen_clips] BEAT_MUTATED job=%s beat=%s keys=%s" % (job_id, beat_idx, why), file=sys.stderr)
    else:
        print("[screen_clips] FALLBACK job=%s beat=%s why=%s" % (job_id, beat_idx, why), file=sys.stderr)


def begin(job_id):
    """렌더·미리보기 시작 — 이 job의 중복 억제를 비우고 시작 시각을 돌려준다(fallbacks_for·summarize의 since)."""
    with _LOCK:
        for sig in [x for x in _SEEN if x[1] == job_id]:
            _SEEN.discard(sig)
    return time.time()


def fallbacks_for(job_id, since=0.0):
    with _LOCK:
        return [dict(e) for e in FALLBACKS if e["job"] == job_id and e["ts"] >= since]


ALERT_KIND_PREFIX = "screen_clips_fallback"
_ALERT_RESOLVE_IN_PYTEST = False     # 테스트가 닫기 경로를 시험할 때만 켠다(monkeypatch)


def alert_kind(job_id):
    """관리자 쪽지 종류 — **job마다 따로**. ops_alert는 쿨다운·서명·resolve_kind가 전부 kind 단위라,
    한 종류로 묶으면 ① 30분 안의 다른 job 경보가 쿨다운에 먹히고 ② 한 job이 멀쩡해지면 남의 배너까지 닫힌다."""
    return "%s:%s" % (ALERT_KIND_PREFIX, job_id)


def _alert(job_id, got):
    """렌더 끝 경보를 관리자 쪽지함(ops_alert, 대시보드 배너)으로. 경보 0이면 이 job의 열린 배너를 닫는다.
    ★알림 실패가 렌더를 막지 않는다(ops_alert 설계 원칙과 같다)."""
    try:
        from shopping_shorts import ops_alert as _oa
        kind = alert_kind(job_id)
        if got:
            beats = sorted({e["beat"] for e in got if e["beat"] is not None})
            whys = {}
            for e in got:
                w = e["why"] if e["kind"] == "FALLBACK" else "BEAT_MUTATED:%s" % e["why"]
                w = str(w).split(" ", 1)[0] if w.startswith(("node_fail", "scene_data_error", "warm_exception",
                                                             "src_unreadable")) else w
                whys[w] = whys.get(w, 0) + 1
            why_txt = ", ".join("%s×%d" % (k, v) if v > 1 else k for k, v in sorted(whys.items()))
            title = "완성본 컷이 편집 화면과 다를 수 있음 — job %s 칸 %s (%s)" % (job_id, beats or "-", why_txt)
            detail = "\n".join("[%s] beat=%s why=%s" % (e["kind"], e["beat"], e["why"]) for e in got)
            _oa.raise_alert(kind, title, detail, grade=_oa.GRADE_CUSTOMER,
                            signature=why_txt + "|" + ",".join(str(b) for b in beats),
                            auto="렌더는 서버 예비 계산으로 계속 진행했다",
                            todo="tools/editor_vs_final_video.py로 이 job의 편집 화면과 완성본을 대조")
        elif os.environ.get("PYTEST_CURRENT_TEST") and not _ALERT_RESOLVE_IN_PYTEST:
            return      # ★resolve_kind엔 pytest 가드가 없다 — 서버 크론 pytest가 라이브 쪽지함을 건드리지 않게(raise_alert와 같은 이유)
        elif any(a.get("kind") == kind and not a.get("resolved") for a in (_oa.list_alerts(limit=100) or [])):
            _oa.resolve_kind(kind)          # 같은 job이 이번엔 경보 0 — 그 job 배너만 닫는다
            # (열린 쪽지가 없으면 안 부른다 — resolve_kind는 부를 때마다 서명 칸을 settings에 써서 job마다 행이 쌓인다)
    except Exception as e:      # noqa: BLE001
        print("[screen_clips] 관리자 경보 전달 실패(렌더 계속): %s" % e, file=sys.stderr)


def summarize(job_id, since=0.0):
    """렌더 끝 요약 — 경보가 있었으면 stderr 한 줄 + 관리자 쪽지(job당 1건), 없으면 그 job의 열린 쪽지를 닫는다.
    반환: 그 기간의 경보 목록. (mix_jobs에는 남기지 않는다 — 경고용 칼럼이 없고 스키마 변경은 범위 밖.)
    화면 데이터가 없는 옛 job은 FALLBACKS에 안 들어가므로 경보 대상이 아니다."""
    got = fallbacks_for(job_id, since)
    if got:
        nf = sum(1 for e in got if e["kind"] == "FALLBACK")
        beats = sorted({e["beat"] for e in got if e["beat"] is not None})
        print("[screen_clips] SUMMARY job=%s fallback=%d mutated=%d beats=%s — 완성본 컷이 편집 화면과 다를 수 있다"
              % (job_id, nf, len(got) - nf, beats), file=sys.stderr)
    _alert(job_id, got)
    return got


def _set_state(jid, screen, why=None):
    with _LOCK:
        prev = _JOB_STATE.get(jid)
        if len(_JOB_STATE) > _CACHE_MAX:
            _JOB_STATE.clear()
        _JOB_STATE[jid] = {"screen": screen, "why": why}
    return prev


def _register_owner(jid, plan_beats):
    with _LOCK:
        if len(_OWNER) > _CACHE_MAX:
            _OWNER.clear()
        for b in plan_beats:
            tp = (b or {}).get("tts_path")
            if tp:
                _OWNER[str(tp)] = jid


def _miss(beat, why):
    """lookup이 None을 돌려주는 자리 — 화면 데이터가 있는 job의 칸이면 경보. 옛 job(화면 데이터 없음)·주인 모를 칸은 조용.
    항상 None(호출부가 `return _miss(...)`로 쓴다)."""
    tp = (beat or {}).get("tts_path")
    with _LOCK:
        jid = _OWNER.get(str(tp)) if tp else None
        st = _JOB_STATE.get(jid) if jid else None
    if not st or st["screen"] == "none":
        return None
    if st["screen"] == "failed":
        why = "warm_failed(%s)" % st["why"]
    _record(jid, (beat or {}).get("beat_idx"), why)
    return None


def snapshot(plan):
    """warm 직후 편성표 칸 사본 — check_mutation이 assemble 직전과 대조한다."""
    import copy
    return copy.deepcopy(list((plan or {}).get("beats") or []))


def check_mutation(job_id, before, plan):
    """렌더는 편성표를 고쳐 쓰지 않는다 — warm 직후와 assemble 직전의 칸 키가 다르면 BEAT_MUTATED. 막지는 않는다.
    반환: [(beat_idx, [바뀐 키])]."""
    after = list((plan or {}).get("beats") or [])
    before = list(before or [])
    out = []
    if len(before) != len(after):
        _record(job_id, None, "beat_count %d->%d" % (len(before), len(after)), kind="BEAT_MUTATED")
        out.append((None, ["beat_count"]))
    for a, b in zip(before, after):
        if beat_key(a) != beat_key(b):
            a = a or {}; b = b or {}
            keys = sorted(str(k) for k in set(a) | set(b)
                          if k not in _VOLATILE and not str(k).startswith("_") and a.get(k) != b.get(k))
            _record(job_id, b.get("beat_idx"), ",".join(keys) or "?", kind="BEAT_MUTATED")
            out.append((b.get("beat_idx"), keys))
    return out


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
    """작업 하나의 화면 컷을 계산해 캐시에 넣는다. 성공한 칸 수(실패 0).
    ★화면 데이터가 있는데 실패하면 경보(FALLBACK), 데이터가 아예 없으면(옛 job) info 한 줄 — 둘 다 렌더는 막지 않는다."""
    if not _enabled() or not job or not job.get("job_id"):
        return 0
    jid = job["job_id"]
    plan_beats = (job.get("edit_plan") or {}).get("beats") or []
    _register_owner(jid, plan_beats)
    try:
        data = _scene_data(jid)
    except Exception as e:      # noqa: BLE001 — 데이터가 있는지조차 모른다 → 조용히 넘기지 않는다
        _set_state(jid, "failed", "scene_data %s" % type(e).__name__)
        _record(jid, None, "scene_data_error %s: %s" % (type(e).__name__, str(e)[:200]))
        return 0
    if not data or not data.get("beats"):
        prev = _set_state(jid, "none", "no_screen_data")
        if not prev or prev.get("screen") != "none":
            print("[screen_clips] info job=%s 화면 데이터 없음 — 예비 계산 사용(옛 job 정상)" % jid, file=sys.stderr)
        return 0
    try:
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        h = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        with _LOCK:
            if _DATA_SEEN.get(jid) == h:
                _JOB_STATE[jid] = {"screen": "ok", "why": None}
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
            _set_state(jid, "failed", "node rc=%s" % out.returncode)
            _record(jid, None, "node_fail rc=%s %s" % (out.returncode, (out.stderr or "").strip()[-300:]))
            return 0
        res = json.loads(out.stdout)
        n = 0
        bad = []
        with _LOCK:
            if len(_CACHE) > _CACHE_MAX:
                _CACHE.clear()
            # 화면 데이터의 칸 = 편성표의 칸(같은 순서). 키는 **편성표 칸**으로 만든다 — 렌더가 보는 그 dict다.
            for b, r in zip(plan_beats, res):
                k = beat_key(b)
                if k and r and r.get("c") is not None:
                    _CACHE[k] = r
                    n += 1
                else:
                    bad.append(((b or {}).get("beat_idx"), "beat_key_fail" if not k else "screen_no_result"))
            _DATA_SEEN[jid] = h
            _JOB_STATE[jid] = {"screen": "ok", "why": None}
        if len(res) != len(plan_beats):
            _record(jid, None, "beat_count screen=%d plan=%d" % (len(res), len(plan_beats)))
        for bi, why in bad:
            _record(jid, bi, why)
        return n
    except Exception as e:      # noqa: BLE001 — 화면 계산 실패가 렌더를 막으면 안 된다(대신 경보)
        _set_state(jid, "failed", type(e).__name__)
        _record(jid, None, "warm_exception %s: %s" % (type(e).__name__, str(e)[:200]))
        return 0


def has(beat):
    """이 칸의 화면 컷이 준비돼 있나."""
    if not _enabled():
        return False
    k = (beat or {}).get("_screen_key") or beat_key(beat)
    with _LOCK:
        r = _CACHE.get(k) if k else None
    return bool(r and r.get("c"))


def plays_at_speed(fit, sync, sd, out):
    """이 컷을 **읽는 길이 전부를 화면 길이에 맞춰 일정 배속으로** 트나(True) — 아니면 느리게(1.15배 상한)+정지(False).
    완성본(lookup → playback_speed)과 편집 화면 합본(app._pvproxy_build _cut_motion)이 **이 함수 하나**로 정한다(2026-09-27).
    ★왜: 합본은 [속도 맞추기]만 배속으로 틀고 칸 통합 속도(sync_speed)·읽는 길이가 긴 컷은 읽는 길이를 화면 길이로 잘라 1배속으로 틀었다
      — 1.4배 칸에서 완성본은 원본 1.358초를, 미리보기는 0.97초만 보여 컷 끝 장면이 7프레임 갈렸다(68b48b12c7f5 칸5, 서버 실측)."""
    try:
        return bool(fit) or abs(float(sync or 1.0) - 1.0) > 1e-6 or float(sd) > float(out) + 1e-3
    except (TypeError, ValueError):
        return bool(fit)


def lookup(beat, tts_dur, src_durs):
    """화면 컷 → 렌더 조각 계획 [{video_id,start,src_dur,out_dur[,playback_speed]}]. 없거나 못 쓰면 None."""
    if not _enabled():
        return None
    # 캡컷·ZIP 이 원본 재료 이름을 `<vid>_raw` 로 바꾼 사본은 바꾸기 전 키(_screen_key)·이름 대응(_screen_vid)을 단다(mix_pipeline._plan_on_source_files)
    k = (beat or {}).get("_screen_key") or beat_key(beat)
    vmap = (beat or {}).get("_screen_vid") or {}
    with _LOCK:
        r = _CACHE.get(k) if k else None
    if not k:
        return _miss(beat, "beat_key_fail")
    if not r:
        return _miss(beat, "no_screen_cut")          # 키 불일치(렌더가 칸을 고쳐 썼거나 warm 실패)
    if not r.get("c"):
        return _miss(beat, "screen_empty")
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
        vid = vmap.get(c.get("v"), c.get("v"))
        total = float((src_durs or {}).get(vid, 0.0) or 0.0)
        if total <= 0.05:
            return _miss(beat, "src_unreadable %s" % vid)   # 소스를 못 읽는다 — 종전 계산이 손상 소스를 거른다
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
        if plays_at_speed(c.get("fit"), sync, sd, out):
            p["playback_speed"] = sd / out
        plan.append(p)
    return plan or _miss(beat, "screen_zero_len")
