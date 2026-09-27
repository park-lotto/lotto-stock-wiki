# -*- coding: utf-8 -*-
"""완성본 렌더 vs 캡컷 초안 vs 내보내기(ZIP) — 같은 job 의 **컷 목록**을 컷 단위로 대조한다(2026-09-27, 읽기 전용).

왜: 완성본 컷은 편집 화면 코드(screen_clips)·청소본 정본(clean_base)을 한 곳에서 판단해 렌더하는데,
  캡컷 초안(capcut_draft)·내보내기(export_bundle)가 같은 판단을 타는지는 아무도 안 쟀다
  (tools/gate_video.json 의 not_measured). 길이 셋이다 — 한쪽에만 들어간 판단은 다른 쪽에서 빠진다.

세 목록을 만드는 법(★전부 라이브 코드를 그대로 부른다 — 도구가 따로 계산하는 건 ①의 인자 조립뿐):
  ① 완성본 렌더 = mix_pipeline.render_inputs_for(allow_clean=False) → video_assemble._render_mix 의 컷 결정부
     (plan_beat_clips_for · cut_frame_list · 시작 당기기 · _speed_and_freeze) — run_render 의 청소 분기(소스별 청소본
     덮기 / 완성본 1편 청소)도 따라 한다. ★_render_mix 는 컷 계획만 따로 떼어 부를 입구가 없어 인자 조립을 여기 옮겼다
     → `_RENDER_MIRROR` 줄들이 video_assemble 원문에 그대로 있는지 매번 확인하고, 없으면 도구가 멈춘다(말없이 어긋나지 않게).
  ② 캡컷 초안 = app.api_mix_capcut **원문을 그대로 실행**하되 쓰기 자리만 임시 폴더(CC_OUT/<job>)로 바꾼다
     (out_root·완성본 조각 자르기·배속 역변환·머리카피·장면꾸미기 폴더). 나온 draft_content.json 의 영상 트랙을 읽는다.
  ③ 내보내기 = app.api_mix_export(part=sources) 원문을 그대로 실행(zip 경로만 임시 폴더) — export_bundle._cut_clip 을
     가로채 **자르려던 구간**(소스·시작·끝)을 기록한다(ffmpeg 는 안 돌린다 — ZIP 조각 = 그 인자 그대로).

비교(컷 단위, 칸 안 순서로 짝):
  src(어느 파일 — 청소본이냐 원본이냐) · start(소스 시작) · read(읽는 길이) · t0/out(타임라인 자리·길이, 캡컷만) ·
  speed(캡컷 배속 vs 완성본 움직임 배속) · freeze(완성본이 느리게+정지로 채운 컷을 캡컷은 일정 배속으로 늘림) ·
  count(칸의 컷 개수) · clean(청소 종류: base 정본 / src 소스별 청소본 / final 완성본 청소 / final_clip 완성본 조각 / orig 원본).

★도구는 고객 파일·DB를 바꾸지 않는다:
  - DB 는 sqlite mode=ro 로만 연다(Store._conn 교체 — 스키마 초기화도 건너뛴다). 쓰려고 하면 예외가 난다.
  - clean_base._write(정본 보정 저장)를 막는다 — render_inputs_for 안 calibrate 가 고객 clean_base.json 을 고쳐 쓴다.
  - 캡컷 라우트에 넘기는 job 에서 deco·headcopy·caption_style 을 뺀다(컷과 무관, 꾸미기 그림 캐시·댓글카드 PNG 를
    고객 폴더에 굽는 경로를 안 타게).
  - job 하나 끝나면 CC_OUT/<job>/ 를 통째로 지운다. 실행 전후 고객 job 폴더 파일 목록(크기·수정시각)을 대조해 보고서에 적는다.

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      CC_OUT=/tmp/capcut_audit python3 /tmp/capcut_audit/capcut_export_audit.py [N최근done=10] [job_id ...]
결과: $CC_OUT/report.txt (job별 한 줄 + == 요약) · $CC_OUT/cuts.jsonl (불일치 컷 상세)
"""
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, ".")

OUT = Path(os.getenv("CC_OUT", "/tmp/capcut_audit"))
DB = "shopping_shorts/data/reference.db"
TOL = 0.05          # 초 — 완성본은 30fps 프레임 경계(±1/60초), 캡컷은 마이크로초라 1프레임+여유
SPEED_TOL = 0.01
MIN_FREE_GB = 20

# ①이 옮겨 적은 _render_mix 의 컷 결정 줄 — 원문에 없으면 렌더 코드가 바뀐 것(도구를 고쳐야 한다).
_RENDER_MIRROR = (
    "tts_dur = _beat_effective_dur(beat, tts)",
    "runout = _LAST_RUNOUT if idx == _runout_idx else 0.0",
    "plan = plan_beat_clips_for(beat, tts_dur, _srcd, runout=runout)",
    "_cfr = cut_frame_list([float(c[\"out_dur\"]) for c in plan], _nfr)",
    "_ofr = int(round(_trans_sec() * 30)) if _n > 1 else 0",
    "start = max(0.0, min(start, sdur - min(_c_src, sdur)))",
    "_c_src, _c_out, preferred_speed=_beat_speed)",
    "for s in _beat_material(beat)",
)


# ───────────────────────── 읽기 전용 장치 ─────────────────────────
def ro_store():
    """Store 를 mode=ro 로 바꾼다(프로세스 전체). 스키마 초기화(CREATE/ALTER)도 건너뛴다."""
    from shopping_shorts import store as _st
    S = _st.Store
    if getattr(S, "_audit_ro", False):
        return S

    def _init(self, db_path):
        self.db_path = Path(db_path)

    def _conn(self):
        return sqlite3.connect("file:%s?mode=ro" % Path(self.db_path).resolve().as_posix(), uri=True, timeout=15.0)

    S.__init__ = _init
    S._conn = _conn
    S._audit_ro = True
    return S


def snapshot(d):
    """폴더 파일 목록 {상대경로: (크기, 수정시각ns)} — 실행 전후 대조용."""
    out = {}
    d = Path(d)
    if not d.exists():
        return out
    for p in d.rglob("*"):
        try:
            if p.is_file() or p.is_symlink():
                st = p.lstat()
                out[str(p.relative_to(d))] = (st.st_size, st.st_mtime_ns)
        except OSError:
            pass
    return out


def snap_diff(a, b):
    """바뀐/생긴/사라진 파일 목록."""
    return sorted([("+" + k) for k in b if k not in a] + [("-" + k) for k in a if k not in b]
                  + [("~" + k) for k in a if k in b and a[k] != b[k]])


# ───────────────────────── 청소 종류 ─────────────────────────
def _norm(p):
    """경로 비교용 — 상대/절대·심볼릭 차이로 같은 파일을 '다른 파일'로 보지 않게(2026-09-27 서버 첫 실행에서 25건 오탐)."""
    return os.path.realpath(str(p)) if p else ""


def clean_kind(path, base_paths=(), clean_src_paths=()):
    p = _norm(path)
    if not p:
        return "none"
    if p in {_norm(x) for x in base_paths}:
        return "base"
    if p in {_norm(x) for x in clean_src_paths}:
        return "src"
    if "capcut_clean_" in Path(p).name or "capcut_speed_" in Path(p).name:
        return "final_clip"
    return "orig"


# ───────────────────────── ① 완성본 렌더 컷 ─────────────────────────
def check_render_mirror(src_text):
    miss = [s for s in _RENDER_MIRROR if s not in src_text]
    if miss:
        raise RuntimeError("video_assemble._render_mix 가 바뀌었다 — 도구 ①을 고쳐라: %s" % miss)


def render_cuts(plan, tts_paths, source_video_paths, probe=None):
    """_render_mix 의 컷 결정부 그대로 → [{beat,ci,vid,src,start,read,t0,out,speed,freeze}] (영상은 안 만든다)."""
    from shopping_shorts import video_assemble as va
    probe = probe or va._probe_duration
    _cache = {}

    def _src_dur(vid):
        if vid not in _cache:
            try:
                _cache[vid] = probe(source_video_paths[vid])
            except Exception:      # noqa: BLE001 — 렌더와 같다(못 재면 0)
                _cache[vid] = 0.0
        return _cache[vid]

    out = []
    _cum_t = 0.0
    _runout_idx = max((b["beat_idx"] for b in plan["beats"] if tts_paths.get(b["beat_idx"])), default=None)
    for beat in plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        tts_dur = va._beat_effective_dur(beat, tts)
        _srcd = {s.get("video_id"): _src_dur(s.get("video_id"))
                 for s in va._beat_material(beat) if s and s.get("video_id") in source_video_paths}
        runout = va._LAST_RUNOUT if idx == _runout_idx else 0.0
        _f0 = int(round(_cum_t * 30))
        _cum_t += tts_dur + runout
        _nfr = max(1, int(round(_cum_t * 30)) - _f0)
        cp = va.plan_beat_clips_for(beat, tts_dur, _srcd, runout=runout)
        if not cp:
            continue
        segs = [s for s in va._beat_material(beat) if s and _srcd.get(s.get("video_id"), 0.0) > 0.05]
        _n = len(cp)
        _cfr = va.cut_frame_list([float(c["out_dur"]) for c in cp], _nfr)
        _ofr = int(round(va._trans_sec() * 30)) if _n > 1 else 0
        if _ofr > 0 and any((nf + (_ofr if j < _n - 1 else 0)) / 30.0 <= _ofr / 30.0 + 0.05
                            for j, nf in enumerate(_cfr)):
            _ofr = 0
        _pad = _ofr / 30.0
        fr = _f0
        for j, c in enumerate(cp):
            _nf = _cfr[j] + (_ofr if j < _n - 1 else 0)
            _c_pad = _pad if j < _n - 1 else 0.0
            _c_src, _c_out = c["src_dur"], c["out_dur"]
            if _c_pad > 1e-3:
                _sd = _src_dur(c["video_id"])
                _lim = va._piece_end_limit(c, segs, _sd)
                _room = max(0.0, _lim - (c["start"] + _c_src)) if _lim > 0 else 0.0
                _c_src = _c_src + min(_c_pad, _room)
                _c_out = _c_out + _c_pad
            try:
                _bs = float(c.get("playback_speed"))
            except (TypeError, ValueError):
                _bs = 1.0
            if not math.isfinite(_bs) or abs(_bs - 1.0) <= 1e-6:
                _bs = None
            play_out, freeze = va._speed_and_freeze(_c_src, _c_out, preferred_speed=_bs)
            sdur = _src_dur(c["video_id"])
            start = c["start"]
            if sdur > 0:
                start = max(0.0, min(start, sdur - min(_c_src, sdur)))
            out.append({"beat": int(idx), "ci": j, "vid": c["video_id"],
                        "src": source_video_paths.get(c["video_id"]),
                        "start": round(float(start), 4), "read": round(float(c["src_dur"]), 4),
                        "t0": round(fr / 30.0, 4), "out": round(_cfr[j] / 30.0, 4),
                        "speed": round(float(_c_src) / play_out, 4) if play_out > 1e-6 else 1.0,
                        "freeze": round(float(freeze), 4), "screen": bool(c.get("screen"))})
            fr += _cfr[j]
    return out


# ───────────────────────── ② 캡컷 초안 컷 ─────────────────────────
def capcut_cuts(draft, timeline, source_video_paths):
    """draft_content.json 의 본 영상 트랙(첫 video 트랙) → [{beat,ci,vid,src,start,read,t0,out,speed}]."""
    mats = {m["id"]: m for m in (draft.get("materials") or {}).get("videos") or []}
    speeds = {m["id"]: m for m in (draft.get("materials") or {}).get("speeds") or []}
    vt = next((t for t in draft.get("tracks") or [] if t.get("type") == "video"
               and any((mats.get(s.get("material_id")) or {}).get("type") == "video" for s in t.get("segments") or [])),
              None)
    wins = [(int(r["beat_idx"]), float(r.get("t0") or 0.0), float(r.get("t0") or 0.0) + float(r.get("dur") or 0.0))
            for r in timeline or []]
    out, per = [], {}
    for s in (vt or {}).get("segments") or []:
        m = mats.get(s.get("material_id")) or {}
        tr, sr = s.get("target_timerange") or {}, s.get("source_timerange") or {}
        t0 = float(tr.get("start") or 0) / 1e6
        d = float(tr.get("duration") or 0) / 1e6
        mid = t0 + d / 2
        bi = next((b for b, a, e in wins if a - 1e-6 <= mid < e + 1e-6), None)
        sp = next((speeds[r]["speed"] for r in s.get("extra_material_refs") or [] if r in speeds), 1.0)
        vid = m.get("material_name")
        ci = per.get(bi, 0)
        per[bi] = ci + 1
        out.append({"beat": bi, "ci": ci, "vid": vid, "src": (source_video_paths or {}).get(vid),
                    "start": round(float(sr.get("start") or 0) / 1e6, 4),
                    "read": round(float(sr.get("duration") or 0) / 1e6, 4),
                    "t0": round(t0, 4), "out": round(d, 4), "speed": round(float(sp), 4)})
    return out


# ───────────────────────── ③ 내보내기 컷 ─────────────────────────
_ZIP_NAME = re.compile(r"^beat_(\d+)_(\d+)_")


def export_cuts(records, source_video_paths):
    """가로챈 _cut_clip 인자 [(src, start, end, out_name)] → [{beat,ci,vid,src,start,read}]."""
    inv = {}
    for v, p in (source_video_paths or {}).items():
        inv.setdefault(_norm(p), v)
    out = []
    for src, st, en, name in records:
        m = _ZIP_NAME.match(name or "")
        if not m:
            continue
        out.append({"beat": int(m.group(1)), "ci": int(m.group(2)), "vid": inv.get(_norm(src)), "src": str(src),
                    "start": round(float(st), 4), "read": round(float(en) - float(st), 4)})
    return out


# ───────────────────────── 대조 ─────────────────────────
def compare(R, X, kind, base_paths=(), clean_src_paths=(), render_clean=None):
    """R(완성본)과 X(캡컷|내보내기)를 칸 안 순서로 짝지어 → (불일치 컷 [{beat,ci,why,r,x}], 비교한 컷 수).
    kind='capcut' 이면 타임라인 자리(t0·out)·배속까지, 'export' 면 소스·시작·읽는 길이만 본다.
    render_clean: 완성본의 청소 종류를 강제(완성본 1편 청소 경로 = 'final' — 조립은 원본으로 하고 뒤에 통째 청소)."""
    def _by(rows):
        d = {}
        for r in rows:
            d.setdefault(r["beat"], []).append(r)
        return d

    rb, xb = _by(R), _by(X)
    bad, n = [], 0
    for b in sorted(set(rb) | set(xb), key=lambda v: (v is None, v if v is not None else 0)):
        rs, xs = rb.get(b, []), xb.get(b, [])
        for k in range(max(len(rs), len(xs))):
            n += 1
            r = rs[k] if k < len(rs) else None
            x = xs[k] if k < len(xs) else None
            if r is None or x is None:
                bad.append({"beat": b, "ci": k, "why": ["count"], "r": r, "x": x})
                continue
            why = []
            rk = render_clean or clean_kind(r["src"], base_paths, clean_src_paths)
            xk = clean_kind(x["src"], base_paths, clean_src_paths)
            final_clip = xk == "final_clip"
            if final_clip:
                if rk != "final":
                    why.append("clean")
            else:
                if rk != xk:
                    why.append("clean")       # 예: 완성본은 청소(final/src/base)인데 이쪽은 원본(orig) = 원본 자막이 살아 나간다
                if _norm(r["src"]) != _norm(x["src"]) and "clean" not in why:
                    why.append("src")
                if abs(r["start"] - x["start"]) > TOL:
                    why.append("start")
                if abs(r["read"] - x["read"]) > TOL:
                    why.append("read")
            if kind == "capcut":
                if abs(r["t0"] - x["t0"]) > TOL:
                    why.append("t0")
                if abs(r["out"] - x["out"]) > TOL:
                    why.append("out")
                if r.get("freeze", 0.0) > TOL and not final_clip:   # 완성본 조각은 정지까지 구워져 있다 — 같은 화면
                    why.append("freeze")          # 완성본 = 느리게(≤1.15배)+정지 / 캡컷 = 한 배속으로 늘림 → 화면이 다르다
                elif not final_clip and abs(r["speed"] - x["speed"]) > SPEED_TOL:
                    why.append("speed")
            if why:
                bad.append({"beat": b, "ci": k, "why": why, "r": r, "x": x})
    return bad, n


def reasons(bad):
    c = {}
    for x in bad:
        for w in x["why"]:
            c[w] = c.get(w, 0) + 1
    return c


# ───────────────────────── 라우트 원문 실행 ─────────────────────────
def route_fn(app_mod, name, subs, extra):
    """app.py 의 라우트 함수 원문을 떼어, 쓰기 자리만 바꿔(subs) 새 이름공간에서 실행한 함수.
    subs = [(원문, 바꿀 글, 필수여부)] — 필수 원문이 없으면 라우트가 바뀐 것이라 멈춘다."""
    src = Path(app_mod.__file__).read_text(encoding="utf-8")
    i = src.index("def %s(" % name)
    j = src.index("\n@app.", i)
    body = src[i:j]
    for old, new, req in subs:
        if old not in body:
            if req:
                raise RuntimeError("%s 원문이 바뀌었다 — 도구의 쓰기 자리 바꾸기를 고쳐라: %r" % (name, old))
            continue
        body = body.replace(old, new)
    ns = dict(app_mod.__dict__)
    ns.update(extra)
    exec(compile(body, "%s<%s>" % (app_mod.__file__, name), "exec"), ns)
    return ns[name]


_CAPCUT_SUBS = [
    ('out_root = work / "capcut"', 'out_root = _AUDIT_OUT / "capcut"', True),
    ("split_final_into_beat_clips(_cf, timeline, work)", "split_final_into_beat_clips(_cf, timeline, _AUDIT_OUT)", True),
    ("_clips, timeline, work)", "_clips, timeline, _AUDIT_OUT)", True),
    ('_hc_dir = work / "capcut_hc"', '_hc_dir = _AUDIT_OUT / "capcut_hc"', False),
    ('_ss_dir = work / "capcut_scene_style"', '_ss_dir = _AUDIT_OUT / "capcut_scene_style"', False),
]
_EXPORT_SUBS = [
    ("out = work / f\"export_{part or 'all'}.zip\"", "out = _AUDIT_OUT / f\"export_{part or 'all'}.zip\"", True),
    ("work.mkdir(parents=True, exist_ok=True)", "pass  # 감사 도구: 고객 폴더에 안 만든다", False),
]


def audit_job(jid, app, mp, va, cb, eb, cd, S):
    """job 하나 → dict(요약) 또는 (None, 사유)."""
    st = S(DB)
    job = st.get_mix_job(jid)
    if not job or not job.get("edit_plan"):
        return None, "편집안 없음"
    work = Path(app._MIX_WORK_DIR) / jid          # ★라우트와 같은 폴더 표기(상대경로로 주면 경로 문자열이 갈린다)
    wd = OUT / jid
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    before = snapshot(work)
    rec = {"phase": None, "cuts": []}

    def _cut_rec(src, start, end, out_path):
        rec["cuts"].append((rec["phase"], str(src), float(start), float(end), Path(str(out_path)).name))
        return False        # 자르지 않는다 — 인자가 곧 ZIP·보관함 조각의 구간이다

    _orig_cut = eb._cut_clip
    eb._cut_clip = _cut_rec
    try:
        # ① 완성본 — render_inputs_for + run_render 청소 분기
        plan_r, paths_r, base = mp.render_inputs_for(st, job, jid, work, [], job.get("customer_id") or 0, allow_clean=False)
        base_paths = set(cb.source_paths(base).values()) if base else set()
        clean_src = {v: p for v, p in (job.get("clean_sources") or {}).items() if p and Path(p).exists()}
        render_clean = None
        miss_clean = []
        if job.get("subtitle_removal") and base is None:
            if mp._clean_strategy(job) == "final":
                render_clean = "final"
            else:
                miss_clean = sorted(v for v in paths_r if v not in clean_src)
                paths_r = {v: clean_src.get(v, p) for v, p in paths_r.items()}
        tts = mp.tts_paths_of(plan_r)
        R = render_cuts(plan_r, tts, paths_r)

        # ② 캡컷 — 라우트 원문 그대로(쓰기 자리만 임시 폴더)
        cap = {}

        class _JobStore(S):
            def get_mix_job(self, j):
                d = super().get_mix_job(j)
                return dict(d, deco=None, headcopy=None, caption_style=None) if d else d

        def _adf(out_root, base_abs, **kw):
            cap.update(kw)
            return cd.assemble_draft_folder(out_root, base_abs, **kw)

        cd_proxy = types.SimpleNamespace(**{k: getattr(cd, k) for k in dir(cd) if not k.startswith("__")})
        cd_proxy.assemble_draft_folder = _adf
        ext = {"_AUDIT_OUT": wd, "Store": _JobStore, "capcut_draft": cd_proxy}
        rec["phase"] = "capcut"
        f_cc = route_fn(app, "api_mix_capcut", _CAPCUT_SUBS, ext)
        resp = f_cc(jid, base="C:/capcut_audit")
        C, cc_err = [], None
        if isinstance(resp, dict) and resp.get("ok"):
            draft = json.loads(resp["texts"]["draft_content.json"])
            C = capcut_cuts(draft, cap.get("timeline") or [], cap.get("source_video_paths") or {})
        else:
            try:
                cc_err = json.loads(resp.body).get("error")
            except Exception:      # noqa: BLE001
                cc_err = repr(resp)[:120]

        # ③ 내보내기 — 라우트 원문 그대로(zip 만 임시 폴더), 조각 구간은 가로채 기록
        rec["phase"] = "export"
        exp_paths = {}

        def _rif(*a, **k):
            r = mp.render_inputs_for(*a, **k)
            exp_paths.update(r[1])
            return r

        mp_proxy = types.SimpleNamespace(**{k: getattr(mp, k) for k in dir(mp) if not k.startswith("__")})
        mp_proxy.render_inputs_for = _rif
        f_ex = route_fn(app, "api_mix_export", _EXPORT_SUBS, {"_AUDIT_OUT": wd, "Store": _JobStore,
                                                             "mix_pipeline": mp_proxy})
        f_ex(jid, part="sources")
        E = export_cuts([(s, a, e, n) for ph, s, a, e, n in rec["cuts"] if ph == "export"], exp_paths)
    finally:
        eb._cut_clip = _orig_cut
        if not os.getenv("CC_KEEP"):
            shutil.rmtree(wd, ignore_errors=True)
    after = snapshot(work)
    bc, nc = compare(R, C, "capcut", base_paths, set(clean_src.values()), render_clean) if C else ([], 0)
    be, ne = compare(R, E, "export", base_paths, set(clean_src.values()), render_clean)
    kinds = lambda rows, force=None: sorted({force or clean_kind(r["src"], base_paths, set(clean_src.values())) for r in rows})
    return {"job": jid, "beats": len({r["beat"] for r in R}), "R": len(R), "C": len(C), "E": len(E),
            "cc_bad": bc, "ex_bad": be, "cc_err": cc_err, "screen": sum(1 for r in R if r["screen"]),
            "clean": (kinds(R, render_clean), kinds(C), kinds(E)), "miss_clean": miss_clean,
            "diff": snap_diff(before, after)}, ""


def main():
    args = sys.argv[1:]
    n = int(args[0]) if args and args[0].isdigit() else 10
    ids = [a for a in args if not a.isdigit()]
    OUT.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(str(OUT)).free / 1e9
    if free < MIN_FREE_GB:
        print("중단: %s 여유 %.1fGB < %dGB" % (OUT, free, MIN_FREE_GB))
        sys.exit(2)
    S = ro_store()
    from shopping_shorts import app, mix_pipeline as mp, video_assemble as va, clean_base as cb
    from shopping_shorts import export_bundle as eb, capcut_draft as cd
    check_render_mirror(Path(va.__file__).read_text(encoding="utf-8"))
    cb._write = lambda work, base: None      # ★고객 clean_base.json 보호
    if not ids:
        con = sqlite3.connect("file:%s?mode=ro" % Path(DB).resolve().as_posix(), uri=True)
        ids = [r[0] for r in con.execute(
            "select job_id from mix_jobs where status='done' order by updated_at desc limit ?", (n,))]
        con.close()
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    det = open(OUT / "cuts.jsonl", "w", encoding="utf-8")
    print("판정: 시간 ±%.2fs · 배속 ±%.2f · 표기 [사유:개수] — src 다른 파일 / clean 청소 종류 다름 / start·read 소스 구간 / "
          "t0·out 타임라인 자리 / speed 배속 / freeze 완성본만 느리게+정지 / count 컷 개수" % (TOL, SPEED_TOL),
          file=rep, flush=True)
    tot = cc = ex = 0
    for jid in ids:
        t0 = time.time()
        try:
            r, why = audit_job(jid, app, mp, va, cb, eb, cd, S)
        except Exception as e:      # noqa: BLE001
            import traceback
            traceback.print_exc(file=sys.stderr)
            r, why = None, "%s: %s" % (type(e).__name__, str(e)[:160])
        if not r:
            print(jid, "건너뜀", why, file=rep, flush=True)
            continue
        tot += r["R"]
        cc += len(r["cc_bad"])
        ex += len(r["ex_bad"])
        for side in ("cc_bad", "ex_bad"):
            for x in r[side]:
                det.write(json.dumps({"job": jid, "side": side[:2], **x}, ensure_ascii=False, default=str) + "\n")
        print("%s 칸%d 컷R%d(화면컷%d)/C%d/E%d | 캡컷 불일치 %d %s%s | 내보내기 불일치 %d %s | 청소 R%s C%s E%s%s | 고객폴더 변화 %s | %.0fs" % (
            jid, r["beats"], r["R"], r["screen"], r["C"], r["E"], len(r["cc_bad"]), reasons(r["cc_bad"]),
            (" (캡컷 실패: %s)" % r["cc_err"]) if r["cc_err"] else "", len(r["ex_bad"]), reasons(r["ex_bad"]),
            r["clean"][0], r["clean"][1], r["clean"][2],
            (" 청소본없는소스%s" % r["miss_clean"]) if r["miss_clean"] else "",
            r["diff"][:5] if r["diff"] else "없음", time.time() - t0), file=rep, flush=True)
    print("== 컷 %d · 캡컷 불일치 %d · 내보내기 불일치 %d" % (tot, cc, ex), file=rep, flush=True)
    rep.close()
    det.close()


if __name__ == "__main__":
    main()
