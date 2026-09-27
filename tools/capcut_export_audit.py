# -*- coding: utf-8 -*-
"""완성본 렌더 vs 캡컷 초안 vs 내보내기(ZIP) — 같은 job 의 **컷 목록**을 컷 단위로 대조한다(2026-09-27, 읽기 전용).

왜: 완성본 컷은 편집 화면 코드(screen_clips)·청소본 정본(clean_base)을 한 곳에서 판단해 렌더한다. 캡컷 초안(capcut_draft)·
  내보내기(export_bundle)가 **같은 소스·같은 청소·같은 컷**을 싣는지를 결과물(초안 파일·ZIP 조각 구간)로 잰다.
  2026-09-27 첫 실측: ZIP 이 정본 없는 자막제거 job 의 원본(자막 박힌) 소스를 담음(4 job 104컷) · 캡컷이 정지 컷을
  한 배속으로 늘림(9컷) → 수리: 청소 종류 = mix_pipeline.clean_route / 재료 = export_sources_for /
  컷 계획 = video_assemble.render_cut_plan 한 곳. 이 도구는 영상 관문(tools/video_gate.py)·매일 점검이 돌린다.

세 목록:
  ① 완성본 렌더 = render_inputs_for(allow_clean=False) + run_render 의 청소 분기(clean_route) → render_cut_plan(렌더가 굽는 바로 그 계획)
  ② 캡컷 초안 = app.api_mix_capcut **원문을 그대로 실행**하되 쓰기 자리만 임시 폴더(CC_OUT/<job>)로 바꾼다
     (out_root·머리카피·장면꾸미기 폴더, 완성본 조각은 export_sources_for(clip_dir=임시)). 나온 draft_content.json 의 본 영상 트랙
     (영상 조각 + 정지 사진 조각)을 읽는다.
  ③ 내보내기 = app.api_mix_export(part=sources) 원문을 그대로 실행(zip 경로만 임시 폴더) — export_bundle._cut_clip 을
     가로채 **자르려던 구간**(소스·시작·끝)을 기록한다(ffmpeg 는 안 돌린다 — ZIP 조각 = 그 인자 그대로).

비교(컷 단위, 칸 안 순서로 짝):
  src(어느 파일) · clean(청소 종류: base 정본 / src 소스별 청소본 / final 완성본 청소 / final_clip 완성본 조각 / orig 원본) ·
  start·read(소스 구간) · t0·out(타임라인 자리·길이, 캡컷만) · speed(움직이는 배속) · freeze(정지 몫 길이) · count(칸의 컷 개수).

★도구는 고객 파일·DB를 바꾸지 않는다:
  - DB 는 sqlite mode=ro 로만 연다(Store._conn 교체 — 스키마 초기화도 건너뛴다). 쓰려고 하면 예외가 난다.
  - clean_base._write(정본 보정 저장)를 막는다 — render_inputs_for 안 calibrate 가 고객 clean_base.json 을 고쳐 쓴다.
  - 캡컷 라우트에 넘기는 job 에서 deco·headcopy·caption_style 을 뺀다(컷과 무관, 꾸미기 그림을 고객 폴더에 굽는 경로를 안 타게).
  - 완성본 조각(청소 완성본 자르기·배속 역변환)은 임시 폴더에 자른다(export_sources_for clip_dir).
  - job 하나 끝나면 CC_OUT/<job>/ 를 통째로 지운다. 실행 전후 고객 job 폴더 파일 목록(크기·수정시각)을 대조해 보고서에 적는다.
★PATCH_DIR: 병합 관문이 병합본 모듈을 /tmp/gate_<sha>/ 에 올려 이 도구로 잰다(editor_vs_final_video 와 같은 방식).

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
      CC_OUT=/tmp/capcut_audit [PATCH_DIR=/tmp/x] python3 tools/capcut_export_audit.py [N최근done=10] [job_id ...]
결과: $CC_OUT/report.txt (job별 한 줄 + `== 컷 N · 캡컷 불일치 X · 내보내기 불일치 Y`) · $CC_OUT/cuts.jsonl ·
      $CC_OUT/done.txt(`CEA_DONE rc=N`) · 예외면 $CC_OUT/crash.txt
"""
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import traceback
import types
from pathlib import Path

sys.path.insert(0, ".")

OUT = Path(os.getenv("CC_OUT", "/tmp/capcut_audit"))
# 장면 전환 캐시(seg_snap — 화면 데이터가 부른다)는 결과 폴더 아래 — 도구는 소재 옆(고객 폴더)에 쓰지 않는다(2026-09-27 9차 관문 실측)
os.environ.setdefault("SEG_SNAP_CACHE_DIR", str(OUT / "snapcache"))
DB = "shopping_shorts/data/reference.db"
TOL = 0.05          # 초 — 완성본은 30fps 프레임 경계(±1/60초), 캡컷은 마이크로초라 1프레임+여유
SPEED_TOL = 0.01
MIN_FREE_GB = 20
SUMMARY_RE = re.compile(r"^== 컷 (\d+) · 캡컷 불일치 (\d+) · 내보내기 불일치 (\d+)(?: · 청소 미생성 (\d+) job)?\s*$")
# PATCH_DIR 에서 얹는 모듈(순서 = import 의존 순서). 관문(video_gate.PATCH_RELS)이 이 목록을 올려야 한다 — 테스트가 대조한다.
PATCH_MODULES = ("frame_match", "screen_clips", "video_assemble", "clean_base", "mix_pipeline",
                 "export_bundle", "capcut_draft")


def load_patches():
    """PATCH_DIR 의 병합본 모듈을 먼저 얹는다(app 을 import 하기 전에). app.py 는 라우트 원문만 거기서 읽는다(route_fn)."""
    pd = os.getenv("PATCH_DIR")
    if not pd:
        return None
    import shopping_shorts
    for n in PATCH_MODULES:
        f = Path(pd) / ("%s.py" % n)
        if f.exists():
            sp = importlib.util.spec_from_file_location("shopping_shorts." + n, str(f))
            m = importlib.util.module_from_spec(sp)
            sys.modules["shopping_shorts." + n] = m
            sp.loader.exec_module(m)
            setattr(shopping_shorts, n, m)
    return Path(pd)


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
    if Path(p).name.startswith("capcut_src_"):
        return "src_file"           # 소스 영상별 청소 파일(export_sources_for — 정본·청소 완성본 모두)
    if "capcut_clean_" in Path(p).name or "capcut_speed_" in Path(p).name:
        return "final_clip"
    return "orig"


# ───────────────────────── ① 완성본 렌더 컷 ─────────────────────────
def render_cuts(plan, tts_paths, source_video_paths, probe=None):
    """렌더가 굽는 컷 계획(video_assemble.render_cut_plan) → [{beat,ci,vid,src,start,read,cread,t0,out,speed,freeze,screen}].
    read = 계획 조각의 읽는 길이(ZIP 이 자르는 구간) · cread = 화면에 보이는 움직임이 읽는 길이(정지 컷이면 움직이는 몫만) ·
    freeze = 화면 안 정지 몫(초)."""
    from shopping_shorts import video_assemble as va
    out = []
    for bp in va.render_cut_plan(plan, tts_paths, source_video_paths, probe=probe):
        for cp in bp["clips"]:
            c = cp["clip"]
            hold = cp["hold_fr"] / 30.0 if cp["freeze"] > 1e-3 else 0.0
            move = cp["cfr"] / 30.0 - hold
            read = float(c["src_dur"])
            out.append({"beat": int(bp["idx"]), "ci": cp["j"], "vid": c["video_id"], "seg": c.get("seg_id"),
                        "pstart": round(float(c["start"]), 4),
                        "src": source_video_paths.get(c["video_id"]),
                        "start": round(float(cp["start"]), 4), "read": round(read, 4),
                        "cread": round(move * cp["speed"], 4),
                        "t0": round(cp["f_start"] / 30.0, 4), "out": round(cp["cfr"] / 30.0, 4),
                        "speed": round(cp["speed"], 4),
                        "freeze": round(hold, 4), "screen": bool(c.get("screen"))})
    return out


# ───────────────────────── ② 캡컷 초안 컷 ─────────────────────────
def capcut_cuts(draft, timeline, source_video_paths):
    """draft_content.json 의 본 영상 트랙(첫 video 트랙) → [{beat,ci,vid,src,start,read,t0,out,speed,freeze}].
    정지 사진 조각(photo)은 바로 앞 영상 조각의 정지 몫(freeze)으로 붙인다."""
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
        if m.get("type") == "photo":
            if out and abs(out[-1]["t0"] + out[-1]["out"] - t0) < 1e-3:
                out[-1]["freeze"] = round(out[-1]["freeze"] + d, 4)
                out[-1]["out"] = round(out[-1]["out"] + d, 4)
            continue
        mid = t0 + d / 2
        bi = next((b for b, a, e in wins if a - 1e-6 <= mid < e + 1e-6), None)
        sp = next((speeds[r]["speed"] for r in s.get("extra_material_refs") or [] if r in speeds), 1.0)
        vid = m.get("material_name")
        ci = per.get(bi, 0)
        per[bi] = ci + 1
        out.append({"beat": bi, "ci": ci, "vid": vid, "src": (source_video_paths or {}).get(vid),
                    "start": round(float(sr.get("start") or 0) / 1e6, 4),
                    "read": round(float(sr.get("duration") or 0) / 1e6, 4),
                    "t0": round(t0, 4), "out": round(d, 4), "speed": round(float(sp), 4), "freeze": 0.0})
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
def clean_made(job, work, route, base, clean_src, mp):
    """청소 산출물이 **실제로 있나** — 정본(base) / 청소 완성본 파일(route=final: 내보내기와 같은 식
    clean_final_path_for_plan or clean_video_path) / 소스별 청소본(route=sources). 자막제거 끔(none)은 해당 없음(True).
    ★없으면 렌더는 '만들면 청소'지만 내보내기는 '아직 없으니 원본' — 설계상 다른 게 맞다. 청소 차원은 비교에서 뺀다
      (관문 8차 실측: 미렌더 준비 job 2개 56컷이 {'clean'}로 잡혔다)."""
    if route == "base":
        return base is not None
    if route == "final":
        cf = mp.clean_final_path_for_plan(job, work) or (job or {}).get("clean_video_path")
        return bool(cf and Path(cf).exists())
    if route == "sources":
        return bool(clean_src)
    return True


def compare(R, X, kind, base_paths=(), clean_src_paths=(), render_clean=None, skip_clean=False):
    """R(완성본)과 X(캡컷|내보내기)를 칸 안 순서로 짝지어 → (불일치 컷 [{beat,ci,why,r,x}], 비교한 컷 수).
    kind='capcut' 이면 타임라인 자리(t0·out)·배속·정지 몫까지, 'export' 면 소스·시작·읽는 길이만 본다.
    render_clean: 완성본의 청소 종류를 강제(완성본 1편 청소 경로 = 'final' — 조립은 원본으로 하고 뒤에 통째 청소).
    skip_clean: 청소 산출물이 아직 없는 job — 청소 종류(clean) 차원은 세지 않는다(clean_made). 컷 자리·구간·배속은 그대로 잰다."""
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
            if xk == "src_file":
                # 소스별 청소 파일: 완성본이 청소(정본/완성본 청소)여야 하고, 컷이 가리키는 **원본 영상·원본 시각**이 같아야 한다
                if rk not in ("base", "final"):
                    why.append("clean")
                if r.get("o_vid") is not None or x.get("o_vid") is not None:
                    if r.get("o_vid") != x.get("o_vid") or x.get("vid") != r.get("o_vid"):
                        why.append("media")
                    elif r.get("o_start") is not None and x.get("o_start") is not None \
                            and min(abs(r["o_start"] - o) for o in [x["o_start"]] + list(x.get("o_alts") or [])) > TOL:
                        why.append("start")
                if x.get("f0") is not None and abs(int(x["f0"]) - int(round(r["t0"] * 30))) > 1:
                    why.append("start")         # 완성본 청소 파일: 그 컷이 완성본의 다른 자리를 튼다
                if rk == "final" and x.get("vid") != r.get("vid"):
                    why.append("media")
                if rk != "final":
                    rr = r.get("cread", r["read"]) if kind == "capcut" else r["read"]
                    if abs(rr - x["read"]) > TOL:
                        why.append("read")
                final_clip = rk == "final"      # 구운 조각 — 정지·배속은 조각 안에
            elif final_clip:
                if rk != "final":
                    why.append("clean")
            else:
                if rk != xk:
                    why.append("clean")       # 예: 완성본은 청소(final/src/base)인데 이쪽은 원본(orig) = 원본 자막이 살아 나간다
                if _norm(r["src"]) != _norm(x["src"]) and "clean" not in why:
                    why.append("src")
                if abs(r["start"] - x["start"]) > TOL:
                    why.append("start")
                rr = r.get("cread", r["read"]) if kind == "capcut" else r["read"]
                if abs(rr - x["read"]) > TOL:
                    why.append("read")
            if kind == "capcut":
                if abs(r["t0"] - x["t0"]) > TOL:
                    why.append("t0")
                if abs(r["out"] - x["out"]) > TOL:
                    why.append("out")
                if not final_clip:   # 완성본 조각은 정지까지 구워져 있다 — 같은 화면
                    if abs(r.get("freeze", 0.0) - x.get("freeze", 0.0)) > TOL:
                        why.append("freeze")      # 정지 몫이 다르다(종전: 완성본 = 느리게+정지 / 캡컷 = 한 배속으로 늘림)
                    elif abs(r["speed"] - x["speed"]) > SPEED_TOL:
                        why.append("speed")
            if skip_clean:
                why = [w for w in why if w != "clean"]
            if why:
                bad.append({"beat": b, "ci": k, "why": why, "r": r, "x": x})
    return bad, n


def map_origins(R, C, ex, base):
    """캡컷 컷(소스별 파일 좌표)·완성본 컷(청소본 좌표)을 **원본 영상·원본 시각**으로 되돌려 o_vid/o_start 를 단다.
    좌표 변환은 export_sources_for 가 만든 조각 배치(source_layout)와 정본 조각 지도(clean_base._regions·mp.clean_origin)만 쓴다."""
    from shopping_shorts import mix_pipeline as mp, clean_base as cb
    layout = (ex or {}).get("source_layout") or {}
    route = (ex or {}).get("route")
    if not layout:
        return
    for x in C:
        L = layout.get(x.get("vid"))
        if not L:
            continue
        # 조각 경계에 선 시작점은 **뒤 조각**의 첫 프레임이다 — 정확히 든 조각을 먼저, 없으면 ±0.02초.
        #   ★렌더 계획의 시작 당기기(파일 끝에서 몇 프레임 앞으로)로 앞 조각 끝에 걸린 컷은 뒤 조각의 원본 좌표로도 적어 둔다
        #     (o_alts) — 완성본도 통짜 청소본에서 같은 몇 프레임을 당겨 읽는다(7bbb 9칸 1프레임).
        nxt = [p for p in L["pieces"] if p["off"] - 0.1 <= x["start"] < p["off"] - 1e-3]
        if route == "base" and nxt:
            q = nxt[0]
            x["o_alts"] = [round(q["cs"] + (x["start"] - q["off"]) / (q["k"] or 1.0), 4)]
        exact = [p for p in L["pieces"] if p["off"] - 1e-3 <= x["start"] < p["off"] + p["len"] - 1e-3]
        for p in exact or [p for p in L["pieces"] if p["off"] - 0.02 <= x["start"] < p["off"] + p["len"] + 0.02]:
                if route == "base":
                    x["o_vid"], x["o_start"] = x["vid"], round(p["cs"] + (x["start"] - p["off"]) / (p["k"] or 1.0), 4)
                else:
                    x["f0"] = p["f0"] + int(round((x["start"] - p["off"]) * 30))
                break
    if route == "base" and base is not None:
        regs = cb._regions(base)
        for r in R:
            if r.get("o_vid") is not None:
                continue
            # 조각 찾기는 **계획한 시작**(pstart)으로 — 렌더의 시작 당기기(청소본 끝)가 앞 조각 경계 밖으로 민 값으로 찾으면
            #   엉뚱한 조각이 걸린다(7bbb 9칸: 31.229 vs 계획 31.267). 원본 시각엔 당긴 만큼을 더한다.
            ps = r.get("pstart", r["start"])
            v, o, rr = mp.clean_origin(regs, r["vid"], ps, r.get("seg"))
            if v is not None:
                r["o_vid"], r["o_start"] = v, round(o + (r["start"] - ps) / (rr[6] or 1.0), 4)


def media_check(R, C, draft, route):
    """캡컷 미디어(본 영상 트랙의 영상 소재 이름) = 완성본이 쓴 **원본 소스 영상 목록**인가 → 불일치 목록.
    청소본 경로(base/final)면 이름이 원본 id(o_vid / 원본 vid)여야 하고 'clean'·'cb*'·'cc*' 통짜·조각 이름이면 안 된다
    (2026-09-27 이윤정님 제보: 정본 job 캡컷 미디어가 src_clean 하나)."""
    mats = {m["id"]: m for m in (draft.get("materials") or {}).get("videos") or []}
    names = sorted({(mats.get(s.get("material_id")) or {}).get("material_name")
                    for t in (draft.get("tracks") or [])[:1] for s in t.get("segments") or []
                    if (mats.get(s.get("material_id")) or {}).get("type") == "video"})
    if route == "base":
        want = sorted({r.get("o_vid") or r["vid"] for r in R})
    else:
        want = sorted({r["vid"] for r in R})
    bad = []
    # 정본 뒤 원본 재료 칸(자막 남는 칸)은 `<vid>_raw` — 같은 원본 영상이다
    if sorted({n[:-4] if n and n.endswith("_raw") else n for n in names}) != want:
        bad.append({"beat": None, "ci": None, "why": ["media"], "r": want, "x": names})
    blob = [n for n in names if n and (n == "clean" or n.startswith(("cb", "cc")))]
    if route in ("base", "final") and blob:
        bad.append({"beat": None, "ci": None, "why": ["media"], "r": "소스별", "x": blob})
    return bad, names


def reasons(bad):
    c = {}
    for x in bad:
        for w in x["why"]:
            c[w] = c.get(w, 0) + 1
    return c


def parse_summary(text):
    """report.txt → {"cuts","capcut","export"} 또는 None(요약 줄 없음/형식 다름 = 판정 불가)."""
    for line in (text or "").splitlines():
        m = SUMMARY_RE.match(line)
        if m:
            a, b, c, d = m.groups()
            return {"cuts": int(a), "capcut": int(b), "export": int(c), "clean_missing": int(d or 0)}
    return None


# ───────────────────────── 라우트 원문 실행 ─────────────────────────
def route_fn(app_mod, name, subs, extra, app_file=None):
    """app.py 의 라우트 함수 원문을 떼어, 쓰기 자리만 바꿔(subs) 새 이름공간에서 실행한 함수.
    subs = [(원문, 바꿀 글, 필수여부)] — 필수 원문이 없으면 라우트가 바뀐 것이라 멈춘다.
    app_file: 원문을 읽을 파일(PATCH_DIR 의 병합본 app.py). 없으면 import 된 app 파일."""
    src = Path(app_file or app_mod.__file__).read_text(encoding="utf-8")
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
    exec(compile(body, "%s<%s>" % (app_file or app_mod.__file__, name), "exec"), ns)
    return ns[name]


_CAPCUT_SUBS = [
    ('out_root = work / "capcut"', 'out_root = _AUDIT_OUT / "capcut"', True),
    ('_hc_dir = work / "capcut_hc"', '_hc_dir = _AUDIT_OUT / "capcut_hc"', False),
    ('_ss_dir = work / "capcut_scene_style"', '_ss_dir = _AUDIT_OUT / "capcut_scene_style"', False),
]
_EXPORT_SUBS = [
    ("out = work / f\"export_{part or 'all'}.zip\"", "out = _AUDIT_OUT / f\"export_{part or 'all'}.zip\"", True),
    ("work.mkdir(parents=True, exist_ok=True)", "pass  # 감사 도구: 고객 폴더에 안 만든다", False),
]


def _proxy(mod, **over):
    p = types.SimpleNamespace(**{k: getattr(mod, k) for k in dir(mod) if not k.startswith("__")})
    for k, v in over.items():
        setattr(p, k, v)
    return p


def audit_job(jid, app, mp, va, cb, eb, cd, S, app_file=None):
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

    def _esf(*a, **k):
        k["clip_dir"] = wd / "clips"                 # ★완성본 조각은 임시 폴더에(고객 폴더 캐시 금지)
        (wd / "clips").mkdir(exist_ok=True)
        r = mp.export_sources_for(*a, **k)
        rec.setdefault("ex", {})[rec["phase"]] = r
        return r

    _orig_cut = eb._cut_clip
    eb._cut_clip = _cut_rec
    try:
        # ① 완성본 — render_inputs_for + run_render 의 청소 분기(clean_route — 렌더가 부르는 그 함수)
        plan_r, paths_r, base = mp.render_inputs_for(st, job, jid, work, [], job.get("customer_id") or 0, allow_clean=False)
        base_paths = set(cb.source_paths(base).values()) if base else set()
        clean_src = {v: p for v, p in (job.get("clean_sources") or {}).items() if p and Path(p).exists()}
        route_r = mp.clean_route(job, base)
        made = clean_made(job, work, route_r, base, clean_src, mp)
        render_clean = "final" if (route_r == "final" and made) else None
        miss_clean = []
        if route_r == "sources":
            miss_clean = sorted(v for v in paths_r if v not in clean_src)
            paths_r = mp.with_clean_sources(paths_r, clean_src)
        tts = mp.tts_paths_of(plan_r)
        R = render_cuts(plan_r, tts, paths_r)

        class _JobStore(S):
            def get_mix_job(self, j):
                d = super().get_mix_job(j)
                return dict(d, deco=None, headcopy=None, caption_style=None) if d else d

        mp_proxy = _proxy(mp, export_sources_for=_esf)
        # ② 캡컷 — 라우트 원문 그대로(쓰기 자리만 임시 폴더)
        cap = {}

        def _adf(out_root, base_abs, **kw):
            cap.update(kw)
            return cd.assemble_draft_folder(out_root, base_abs, **kw)

        rec["phase"] = "capcut"
        f_cc = route_fn(app, "api_mix_capcut", _CAPCUT_SUBS,
                        {"_AUDIT_OUT": wd, "Store": _JobStore, "mix_pipeline": mp_proxy,
                         "capcut_draft": _proxy(cd, assemble_draft_folder=_adf)}, app_file)
        resp = f_cc(jid, base="C:/capcut_audit")
        C, cc_err = [], None
        draft, media_bad, media_names = None, [], []
        if isinstance(resp, dict) and resp.get("ok"):
            draft = json.loads(resp["texts"]["draft_content.json"])
            C = capcut_cuts(draft, cap.get("timeline") or [], cap.get("source_video_paths") or {})
            ex_cc = (rec.get("ex") or {}).get("capcut") or {}
            map_origins(R, C, ex_cc, base)
            media_bad, media_names = media_check(R, C, draft, ex_cc.get("route"))
        else:
            try:
                cc_err = json.loads(resp.body).get("error")
            except Exception:      # noqa: BLE001
                cc_err = repr(resp)[:120]

        # ③ 내보내기 — 라우트 원문 그대로(zip 만 임시 폴더), 조각 구간은 가로채 기록
        rec["phase"] = "export"
        f_ex = route_fn(app, "api_mix_export", _EXPORT_SUBS,
                        {"_AUDIT_OUT": wd, "Store": _JobStore, "mix_pipeline": mp_proxy}, app_file)
        f_ex(jid, part="sources")
        exp_paths = ((rec.get("ex") or {}).get("export") or {}).get("source_video_paths") or {}
        E = export_cuts([(s, a, e, n) for ph, s, a, e, n in rec["cuts"] if ph == "export"], exp_paths)
        map_origins(R, E, (rec.get("ex") or {}).get("export") or {}, base)
    finally:
        eb._cut_clip = _orig_cut
        if not os.getenv("CC_KEEP"):
            shutil.rmtree(wd, ignore_errors=True)
    after = snapshot(work)
    bc, nc = compare(R, C, "capcut", base_paths, set(clean_src.values()), render_clean, skip_clean=not made) if C else ([], 0)
    bc = bc + (media_bad if C else [])
    be, ne = compare(R, E, "export", base_paths, set(clean_src.values()), render_clean, skip_clean=not made)
    if not C and R:
        bc = [{"beat": None, "ci": None, "why": ["capcut_failed"], "r": None, "x": cc_err}]
    kinds = lambda rows, force=None: sorted({force or clean_kind(r["src"], base_paths, set(clean_src.values())) for r in rows})  # noqa: E731
    return {"job": jid, "beats": len({r["beat"] for r in R}), "R": len(R), "C": len(C), "E": len(E),
            "cc_bad": bc, "ex_bad": be, "cc_err": cc_err, "screen": sum(1 for r in R if r["screen"]),
            "media": media_names,
            "freeze": sum(1 for r in R if r["freeze"] > TOL),
            "clean": (kinds(R, render_clean), kinds(C), kinds(E)), "miss_clean": miss_clean,
            "clean_missing": (not made) and route_r in ("final", "sources"), "route": route_r,
            "diff": snap_diff(before, after)}, ""


def pick_jobs(n):
    con = sqlite3.connect("file:%s?mode=ro" % Path(DB).resolve().as_posix(), uri=True)
    try:
        return [r[0] for r in con.execute(
            "select job_id from mix_jobs where status='done' order by updated_at desc limit ?", (n,))]
    finally:
        con.close()


def run(ids_or_n):
    OUT.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(str(OUT)).free / 1e9
    if free < MIN_FREE_GB:
        raise SystemExit("중단: %s 여유 %.1fGB < %dGB" % (OUT, free, MIN_FREE_GB))
    patch = load_patches()
    S = ro_store()
    from shopping_shorts import app, mix_pipeline as mp, video_assemble as va, clean_base as cb
    from shopping_shorts import export_bundle as eb, capcut_draft as cd
    app_file = str(patch / "app.py") if patch and (patch / "app.py").exists() else None
    cb._write = lambda work, base: None      # ★고객 clean_base.json 보호
    ids = ids_or_n if isinstance(ids_or_n, list) else pick_jobs(int(ids_or_n))
    rep = open(OUT / "report.txt", "w", encoding="utf-8")
    det = open(OUT / "cuts.jsonl", "w", encoding="utf-8")
    print("판정: 시간 ±%.2fs · 배속 ±%.2f · 표기 [사유:개수] — src 다른 파일 / clean 청소 종류 다름 / start·read 소스 구간 / "
          "t0·out 타임라인 자리 / speed 배속 / freeze 정지 몫 / count 컷 개수 / capcut_failed 초안 못 만듦" % (TOL, SPEED_TOL),
          file=rep, flush=True)
    tot = cc = ex = cmiss = 0
    for jid in ids:
        t0 = time.time()
        try:
            r, why = audit_job(jid, app, mp, va, cb, eb, cd, S, app_file)
        except Exception as e:      # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            r, why = None, "%s: %s" % (type(e).__name__, str(e)[:160])
        if not r:
            print(jid, "건너뜀", why, file=rep, flush=True)
            continue
        tot += r["R"]
        cmiss += bool(r.get("clean_missing"))
        cc += len(r["cc_bad"])
        ex += len(r["ex_bad"])
        for side in ("cc_bad", "ex_bad"):
            for x in r[side]:
                det.write(json.dumps({"job": jid, "side": side[:2], **x}, ensure_ascii=False, default=str) + "\n")
        print("%s 칸%d 컷R%d(화면컷%d·정지컷%d)/C%d/E%d | 캡컷 미디어 %s | 캡컷 불일치 %d %s%s | 내보내기 불일치 %d %s | 청소 R%s C%s E%s%s | 고객폴더 변화 %s | %.0fs" % (
            jid, r["beats"], r["R"], r["screen"], r["freeze"], r["C"], r["E"], r["media"], len(r["cc_bad"]), reasons(r["cc_bad"]),
            (" (캡컷 실패: %s)" % r["cc_err"]) if r["cc_err"] else "", len(r["ex_bad"]), reasons(r["ex_bad"]),
            r["clean"][0], r["clean"][1], r["clean"][2],
            ((" 청소본없는소스%s" % r["miss_clean"]) if r["miss_clean"] else "")
            + ((" · 청소 미생성(%s — 청소 비교 제외)" % r["route"]) if r.get("clean_missing") else ""),
            r["diff"][:5] if r["diff"] else "없음", time.time() - t0), file=rep, flush=True)
    print("== 컷 %d · 캡컷 불일치 %d · 내보내기 불일치 %d · 청소 미생성 %d job" % (tot, cc, ex, cmiss), file=rep, flush=True)
    rep.close()
    det.close()


def main():
    args = sys.argv[1:]
    ids = [a for a in args if not a.isdigit()]
    target = ids if ids else (int(args[0]) if args and args[0].isdigit() else 10)
    OUT.mkdir(parents=True, exist_ok=True)
    done = OUT / "done.txt"
    for f in (done, OUT / "crash.txt"):
        if f.exists():
            f.unlink()
    rc = 1
    try:
        run(target)
        rc = 0
    except BaseException:      # noqa: BLE001 — 죽은 이유를 판정 쪽(관문·매일 점검)이 볼 수 있게 남긴다
        (OUT / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
    done.write_text("CEA_DONE rc=%d\n" % rc, encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
