# -*- coding: utf-8 -*-
"""품질 관문 한 벌 — 공용 렌더러(render_bench) 완성본을 한 함수로 판정한다 (관제 263 지시서 04, 2026-10-24 · 표준 §5-1).

    PYTHONUTF8=1 py tools/calcopy/hybrid/quality_gate.py gate <판> <doc_dir> <work_dir> [--no-fit] [--no-asr] [--no-media] [--no-eye]

왜: 관문이 두 벌이었다 — bench_check(10항목: 규격·화면·썸네일·배치)와 checks/preset_make B표(B13 중복·B16 ABA·B18 쉼·되감김) —
    어느 경로로 만들었느냐에 따라 검사가 달랐고, 1차 자(kal_analyze.match_table)는 관문 어디서도 안 돌았다(표준 §0).
판단 주인: 항목마다 **기존 주인 함수를 import** 해서 부른다(복사 금지) — 이 파일이 새로 정하는 것은 '묶음·○×·미측정=×' 뿐.
  규격·화면·썸네일 측정 = 이 파일(옛 bench_check 본문을 옮김 — bench_check.py 는 호출만 남김)
  재료 B13·B16 = checks.reuse_violations·aba_violations · 되감김 = engine/check_seams.check
  쉼 B18 = checks.pauses_between(문턱 checks.PAUSE_LO/HI) · 받아쓰기 = engine/check_line_sync(asr_segments·line_starts_from_asr·LIMIT)
  대본 = script_audit.audit · 배치 = placement.check_place(렌더 때 자막표.check 에 기록) · 1차 자 = kal_analyze.match_from_render
  장면↔대사 = 완성본 컷 ↔ 계획이 고른 원본 프레임 동일성(창 픽셀 대조 ≥0.97, 표준 §11-4 ㉔) + 계획 점수(material_fit 의 루브릭 rubric:v1)를 그대로 보고
    — 완성본을 다시 채점하지 않는다(같은 자를 두 번 돌리면 잡음만 잰다) · 자 = 루브릭 하나(㉕, 상위편_목표.json), 버전 불일치면 ×
  썸네일 규칙 = thumb_rule.check · 광고 = engine/ad_mark 표식
판정: 항목 ok = True(○) / False(×) / None(미측정 — ×로 센다, 표준 §4-1 "미측정 칸은 ✓가 아니다"). 하나라도 ○가 아니면 ok:false.
출력: <doc>/품질관문.json · <doc>/자동검사.json(같은 내용, 옛 꼴 호환) · <doc>/재현일치도.json·.md · <doc>/장면대사.json · <work>/eye/(눈 검수 묶음)
모드(표준 §11 ⑥): --fast = 렌더 직후(규격·화면·재료·자막·효과·표식) · --full = 납품 전(전부: 소리·대본·썸네일·1차 자·장면↔대사 포함).
  항목마다 걸린 초 = <work>/gate_stage_log.json(engine/stage_log) · 무거운 측정은 <work>/render/gate_cache.json(완성본·목소리 md5, match 입력 sha)로 재사용.
"""
from __future__ import annotations

import argparse
import hashlib


import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FPS, ROOT, jload, jsave, lufs, probe, run  # noqa: E402

GATE_VERSION = "quality_gate:v2(2026-10-25 표준 §11)"
FAST_GROUPS = ("규격", "화면", "재료", "자막·효과", "표식")
GAP_TOL = 1 / 30 + 0.02    # 줄 사이 간격 = 판 timing(시간표) ±1프레임+0.02 (표준 §11 ①ⓐ)
OLD_PAUSE_RENDERERS = ("make", "itssum", "jaemi")   # 고정 PAUSE_LO/HI 는 옛 렌더러 판에서만(표준 §11 ①ⓒ)
B13_GAP_MAX, B13_GAP_FRAC = 3.0, 0.25            # 거리 문턱 = min(3.0, 0.25 × 소스 길이) (표준 §11 ②)
TD_TOL = 0.30                                     # 전환 세기 = 우리 drop 중앙값이 벤치 drop 중앙값 ±30% (표준 ⑯, 측정 주인 render_bench.transition_drop)
TD_KINDS = ("zoomblur",)
FREEZE_SEC = 0.3      # 창 안 같은 그림이 이만큼 이어지면 멈춤(벤치 컷 중앙 약 1초 · 실제 촬영 영상은 프레임마다 잡음이 있어 0이 안 나온다)
SIZE = (1080, 1920)
FRAME_SAME_MIN = 0.97     # 완성본 컷 = 계획 프레임: 창 영역 회색 1−평균절대차/255 ≥ 0.97 (표준 §11-4 ㉔ⓐ)
LEGACY10 = ("길이", "화면=시간표", "음량", "최고점", "0초·첫 줄 얼굴", "컷 조각 프레임 = 계획", "화면 멈춤 없음",
            "컷 끝 번쩍임 없음(0.2초 안 장면 경계)", "썸네일 맨 앞 2프레임", "배치(본보기 벤치 편 대조)")
GROUPS = ("규격", "화면", "재료", "자막·효과", "소리", "대본", "1차 자", "장면↔대사", "썸네일", "표식")


# ---------------------------------------------------------------- 측정 조각(옛 bench_check 본문 — 주인 이 파일)
def vdur(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", p]).stdout.strip().split(",")[0] or 0)   # 98 #73


def part_frames(R: Path, T: dict) -> list:
    """컷 조각마다 (번호, 줄, 원본@초, 계획, 실제) — 계획과 다른 것만."""
    from tools.calcopy.hybrid.render_bench import count_frames
    bad = []
    for k, c in enumerate(T["cuts"]):
        p = R / "parts" / f"c{k:02d}.mp4"
        got = count_frames(p) if p.exists() else 0
        if got != c.get("frames"):
            bad.append((k, c["line"], f"{c['src']}@{c.get('ss')}", c.get("frames"), got))
    return bad


def part_slivers(R: Path, T: dict, src_dir: Path | None = None) -> list:
    """컷 처음·끝 0.2초 안에 원본 장면 경계가 있는 것(이웃 샷이 몇 프레임 끼어 번쩍임) — (번호, 줄, 원본@초, 경계 초(컷 기준)).
    경계 판정 = render_bench.shot_starts(원본) 한 곳(나레 컷 snap_ss 와 같은 판정 — 조각을 따로 재면 문턱이 달라 어긋났다, 10-24)."""
    from tools.calcopy.hybrid.render_bench import IMG_EXT, SLIVER_SEC, shot_starts, slivers
    bad = []
    for k, c in enumerate(T["cuts"]):
        src = Path(src_dir) / c["src"] if src_dir else None
        if not src or not src.exists() or src.suffix.lower() in IMG_EXT:
            continue
        a = float(c.get("ss") or 0.0)
        sv = slivers(shot_starts(src), a, a + (c.get("frames") or 0) / FPS, SLIVER_SEC)
        if sv:
            bad.append((k, c["line"], f"{c['src']}@{a}", [round(x - a, 3) for x in sv]))
    return bad


def thumb_stamped(video: Path, doc: Path) -> tuple[bool | None, str]:
    """썸네일.json 이 있으면 완성본 0·1프레임 = 고른 카드 그림인가(회색 평균 차 < 12 — 광고 표시·압축 차 허용), 2프레임은 카드가 아닌가."""
    import numpy as np
    from PIL import Image
    sp = Path(doc) / "썸네일.json"
    if not sp.exists():
        return None, "썸네일.json 없음(검사 안 함)"
    pk = jload(sp).get("pick")
    jpg = Path(doc) / "thumb" / f"{pk}.jpg"
    ref = np.asarray(Image.open(jpg).convert("L").resize((108, 192)), dtype=np.int16)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", r"select=lt(n\,3),scale=108:192,format=gray", "-vsync", "0",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108).astype(np.int16)
    d = [round(float(np.abs(f - ref).mean()), 1) for f in fr]
    ok = len(d) == 3 and d[0] < 12 and d[1] < 12 and d[2] >= 12
    return ok, f"안 {pk} · 프레임 0·1·2 차 {d}"


def freezes(video: Path, win, min_sec: float = FREEZE_SEC) -> list:
    """창 안(win = x,y,w,h) 그림이 그대로인 구간 [(시작초, 끝초)] — 프레임 차(108폭 회색 평균) < 0.05 가 min_sec 이상."""
    import numpy as np
    x, y, w, h = win
    sw, sh = 108, max(8, round(108 * h / w))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"crop={w}:{h}:{x}:{y},scale={sw}:{sh},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, sh, sw).astype(np.int16)
    same = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)) < 0.05
    out, i, need = [], 0, round(min_sec * FPS)
    while i < len(same):
        if same[i]:
            j = i
            while j < len(same) and same[j]:
                j += 1
            if j - i + 1 >= need:
                out.append((round(i / FPS, 2), round((j + 1) / FPS, 2)))
            i = j
        else:
            i += 1
    return out


def fps_of(p) -> float:
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", p]).stdout.strip().split(",")[0]
    a, _, b = r.partition("/")
    return round(float(a) / float(b or 1), 3)


# ---------------------------------------------------------------- 판정 조각(입력 = 숫자 — 사보타주 시험이 이것을 부른다)
def sfx_excess(n_sfx: int, dur: float, bench_docs: list[dict]) -> tuple[bool | None, str]:
    """B14 효과음 과다 = 우리 발/초 ≤ 벤치 편별 발/초의 p90(표준 §3-3 A2). 벤치 줄판독이 없으면 미측정."""
    import numpy as np
    from tools.calcopy.engine.kal_analyze import _sfx_n
    dens = [sum(_sfx_n(l) for l in d.get("lines") or []) / float(d["dur"]) for d in bench_docs if d.get("dur")]
    if not dens:
        return None, "벤치 줄판독 없음(미측정)"
    p90 = float(np.percentile(dens, 90))
    ours = n_sfx / dur if dur else 0.0
    return ours <= p90 + 1e-9, f"우리 {n_sfx}발/{dur:.1f}초 = {ours:.3f}/초 · 벤치 p90 {p90:.3f}/초(편별 {[round(x, 3) for x in dens]})"


def _src_gray(src: Path, t: float, crop, size: tuple[int, int]):
    """계획 프레임 = 원본 t초를 렌더와 같은 칸(crop [x,y,w,h])으로 잘라 창 크기(size=(w,h))로 — 회색."""
    import numpy as np
    from tools.calcopy.hybrid.render_bench import IMG_EXT
    x, y, w, h = crop
    pre = ["-loop", "1"] if Path(src).suffix.lower() in IMG_EXT else ["-ss", f"{max(0.0, t):.3f}"]
    raw = subprocess.run(["ffmpeg", "-v", "error", *pre, "-i", str(src), "-frames:v", "1", "-vf",
                          f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}:flags=lanczos,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.uint8).reshape(size[1], size[0]) if len(raw) == size[0] * size[1] else None


def frame_same(a, b, mask=None) -> float:
    """두 회색 그림의 같음 = 1 − 평균절대차/255(mask True = 뺄 픽셀: 자막·스티커). 1/4 크기로 줄여 잰다(압축 잡음 완화)."""
    import cv2
    import numpy as np
    sz = (max(8, a.shape[1] // 4), max(8, a.shape[0] // 4))
    A = cv2.resize(a, sz, interpolation=cv2.INTER_AREA).astype(np.float32)
    B = cv2.resize(b, sz, interpolation=cv2.INTER_AREA).astype(np.float32)
    keep = np.ones(A.shape, bool) if mask is None else ~(cv2.resize(mask.astype(np.uint8), sz, interpolation=cv2.INTER_NEAREST) > 0)
    if keep.sum() < 50:
        return float("nan")
    return round(1 - float(np.abs(A - B)[keep].mean()) / 255, 4)


def _frames_at(video: Path, frames: list[int], crop) -> dict:
    """영상의 프레임 번호들을 한 번에(ffmpeg select 1회) 창 칸 회색으로 → {번호: 배열}. 시각→프레임은 번호로(입력 -ss 의 1프레임 밀림 없음)."""
    import numpy as np
    if not frames:
        return {}
    x, y, w, h = crop
    fs = sorted(set(int(f) for f in frames))
    sel = "+".join(f"eq(n\\,{f})" for f in fs)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"select={sel},crop={w}:{h}:{x}:{y},format=gray", "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    return dict(zip(fs, arr))


def plan_frames_check(R: Path, T: dict, cand_dir: Path, win: list, mask_of=None) -> list[dict]:
    """(판단 주인 — 완성본 컷 = 계획 프레임, ㉔) 컷마다 처음·가운데·끝 3시각에서 화면 창 ↔ 원본(ss+경과)을 렌더 칸(crop_used>crop)으로.
    화면 = render/base.mp4(완성본에서 자막만 뺀 바탕 — 틀·창·전환 그대로)가 있으면 그것, 없으면 final.mp4 + mask_of(자막 띠 빼기).
    칸이 '얼굴 자동'인데 렌더 기록(crop_used)이 없거나 밀기·움직임·그림 칸이 있는 컷은 대조 밖(sim None + 사유)."""
    video = R / "base.mp4" if (R / "base.mp4").exists() else R / "final.mp4"
    if video.name == "base.mp4":
        mask_of = None
    plan = []
    out = []
    for k, c in enumerate(T.get("cuts") or []):
        crop = c.get("crop_used") or c.get("crop")
        why = None
        if not (isinstance(crop, list) and len(crop) == 4):
            why = f"칸 '{crop}' — 렌더가 쓴 칸(crop_used) 기록 없음"
        elif c.get("push") or c.get("move") or c.get("pic"):
            why = "밀기·움직임·그림 칸 컷 — 원본 프레임과 화면이 다르게 그려짐"
        src = Path(cand_dir) / str(c.get("src"))
        if not why and not src.exists():
            why = f"원본 없음 {src.name}"
        if why:
            out.append({"k": k, "line": c.get("line"), "src": c.get("src"), "ss": c.get("ss"), "sim": None, "why": why})
            continue
        t0, t1 = float(c["t0"]), float(c["t1"])
        d = t1 - t0
        ts = [t0 + d / 2] if d < 0.4 else [t0 + d * 0.2, t0 + d / 2, t1 - d * 0.2]
        plan.append((k, c, src, crop, [round(t * FPS) for t in ts]))
        out.append(None)
    got = _frames_at(video, [f for *_, fs in plan for f in fs], win)
    for k, c, src, crop, fs in plan:
        sims = []
        for f in fs:
            fr = got.get(f)
            g = _src_gray(src, float(c.get("ss") or 0) + (f - round(float(c["t0"]) * FPS)) / FPS, crop, (win[2], win[3]))
            if fr is None or g is None:
                continue
            sims.append(frame_same(fr, g, mask_of(f / FPS, fr.shape) if mask_of else None))
        sims = [x for x in sims if x == x]
        out[k] = {"k": k, "line": c.get("line"), "src": c.get("src"), "ss": c.get("ss"), "fit": c.get("fit"), "screen": video.name,
                  "sim": round(statistics.median(sims), 4) if sims else None, "sims": sims, "why": None if sims else "프레임 못 읽음"}
    return [r for r in out if r is not None]


def plan_frames_verdict(rows: list[dict]) -> tuple[bool | None, str]:
    """컷마다 sim ≥ FRAME_SAME_MIN. 대조 밖 컷(sim None)은 사유와 함께 따로 적고 ×(미측정 ≠ 통과)."""
    if not rows:
        return None, "컷 없음(미측정)"
    bad = [r for r in rows if r["sim"] is not None and r["sim"] < FRAME_SAME_MIN]
    miss = [r for r in rows if r["sim"] is None]
    ok = not bad and not miss
    msg = f"{len(rows)}컷 중 같음 {len(rows) - len(bad) - len(miss)} · 다름 {[(r['k'], r['line'], r['sim']) for r in bad] or 0}"
    if miss:
        msg += f" · 대조 밖 {[(r['k'], r['line'], r['why']) for r in miss]}"
    return ok, msg + f" (창 1−평균차 ≥ {FRAME_SAME_MIN}, 최저 {min((r['sim'] for r in rows if r['sim'] is not None), default=None)})"


def plan_score_report(doc: Path, slug: str | None) -> tuple[bool | None, str, bool]:
    """계획 점수(material_fit 의 장면대사_계획.json) 그대로 보고 + 자 대조(㉕): 계획 rubric = scene_fit.RUBRIC_V = 상위편_목표.json rubric.
    반환 (ok, 글, ref) — 자가 맞으면 참고 행(ref=True), 어긋나면 ×(ref=False). 계획 파일 없으면 참고 행 '계획 없음'."""
    from tools.calcopy.oneshot.scene_fit import RUBRIC_V
    pp = Path(doc) / "장면대사_계획.json"
    tp = ROOT / "channel" / str(slug or "_") / "_kal" / "상위편_목표.json"
    top = (jload(tp).get("scene_fit") or {}) if tp.exists() else {}
    if not pp.exists():
        return True, f"계획 점수 없음(material_fit 계획 전 편) · 목표 {top.get('p75_mean')}/{top.get('p25_below7')} ({top.get('rubric')})", True
    P = jload(pp)
    rv = {"계획": P.get("rubric"), "scene_fit": RUBRIC_V, "상위편_목표": top.get("rubric")}
    if len({v for v in rv.values()}) != 1:
        return False, f"자 불일치 {rv} — 벤치·계획을 같은 루브릭으로 다시 재야 한다", False
    return True, (f"계획 평균 {P.get('mean')}·7 미만 {P.get('below_n')}/{P.get('below_base')}({P.get('below7')}) vs 목표 평균 {top.get('p75_mean')}·"
                  f"7 미만 {top.get('p25_below7')} · 계획 판정 {'통과' if P.get('ok') else '미달'} · {P.get('stop') or ''} ({RUBRIC_V})"), True


def match_verdict(T: dict, upgrade: bool) -> tuple[bool | None, str, list]:
    """1차 자 판정 — 1차 판 = MATCH_RULES 기준(core) 칸 전부 in · 업그레이드 판(base) = 뼈대 칸(MATCH_SKELETON)만. 미측정(failed) = ×."""
    from tools.calcopy.engine.kal_analyze import MATCH_SKELETON
    need = [r for r in T["rows"] if (r["key"] in MATCH_SKELETON if upgrade else r["core"])]
    if not need:
        return None, "필수 칸 없음(미측정)", []
    bad = [r["key"] + ("(미측정)" if r["judge"] == "failed" else "") for r in need if r["judge"] != "in"]
    n_in = sum(r["judge"] == "in" for r in T["rows"])
    n_out = sum(r["judge"] == "out" for r in T["rows"])
    n_fail = sum(r["judge"] == "failed" for r in T["rows"])
    return (not bad), (f"{'업그레이드 판 — 뼈대 칸만 필수' if upgrade else '1차 판 — 기준 칸 전부 필수'} · 전체 {len(T['rows'])}칸 ✓{n_in} ✗{n_out} 미측정{n_fail} · "
                       f"필수 {len(need)}칸 중 미달 {bad or '없음'} · 벤치 {T.get('n_bench')}편"), bad


def marker_verdict(info: dict, style_file: Path | None) -> tuple[bool, str]:
    """표식(0순위-C): render_info.json 에 판 파일 sha·렌더러 sig·placement reference — 없으면 불신. sha 가 지금 판 파일과 다르면 ×."""
    miss = [k for k in ("style_sha", "renderer_sig") if not info.get(k)]
    ref = (info.get("placement_check") or {}).get("reference") or (info.get("placement") or {}).get("reference")
    if not ref:
        miss.append("placement.reference")
    if miss:
        return False, f"불신 — render_info.json 에 {miss} 없음"
    if style_file and style_file.exists():
        cur = hashlib.sha256(style_file.read_bytes()).hexdigest()
        rec = str(info["style_sha"])
        if not (cur.startswith(rec) or rec.startswith(cur)):
            return False, f"판 파일이 렌더 뒤 바뀜(기록 {rec[:12]} ≠ 지금 {cur[:12]})"
    return True, f"style_sha {str(info['style_sha'])[:12]} · renderer_sig {info['renderer_sig']} · reference {ref}"


def cps_tol():
    """줄별 말속도 허용 폭의 주인 = render_itssum.CPS_LINE_TOL(표준 §11 ⑤). 상수가 아직 없으면 None(02 몫)."""
    try:
        from tools.calcopy.hybrid import render_itssum
    except Exception:  # noqa: BLE001
        return None
    return getattr(render_itssum, "CPS_LINE_TOL", None)


def line_cps_verdict(table: dict | None, tol: float | None) -> tuple[bool | None, str]:
    """렌더가 render_info.json 에 남긴 줄별 cps 표 {줄: 자/초} 가 평균 ±tol 안인가 — 재계산하지 않는다(주인 = render_itssum, 렌더가 막는다)."""
    if tol is None:
        return None, "render_itssum.CPS_LINE_TOL 없음(미측정 — 02 가 상수 이름을 뽑는다)"
    if not table:
        return None, "render_info.json 에 줄별 cps 표(line_cps) 없음(미측정 — 렌더가 남겨야 한다)"
    vals = [float(v) for v in table.values()]
    mean = sum(vals) / len(vals)
    bad = {k: v for k, v in table.items() if not ((1 - tol) * mean <= float(v) <= (1 + tol) * mean)}
    return (not bad), f"렌더 기록 평균 {mean:.2f}자/초 ±{tol:.0%} · " + " ".join(f"{k}:{v}" for k, v in table.items()) + (f" · 밖 {bad}" if bad else "")


def reuse_violations_bench(cuts: list[dict], src_len: dict) -> list[str]:
    """B13(공용 렌더러 판 — 표준 §11 ②): 같은 소스에서 ① 프레임을 하나라도 공유(겹침)하면 항상 × ② 겹치지 않아도 거리 < min(3.0, 0.25×소스 길이)
    이고 이어 붙인 앞으로 가기(앞 컷 끝 = 다음 컷 시작, 원본에서 앞으로)가 아니면 ×. 사진·짤은 B6 몫이라 뺀다.
    (옛 길 itssum·jaemi 는 checks.reuse_violations 그대로 — 그쪽 ±3초는 긴 원본 전제)"""
    from tools.calcopy.hybrid.render_bench import IMG_EXT
    eps = 1 / 30
    rows = sorted([(c["src"], float(c["ss"]), float(c["ss"]) + float(c["dur"]), c) for c in cuts
                   if Path(str(c["src"])).suffix.lower() not in IMG_EXT], key=lambda r: r[3]["t0"])
    bad = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            s1, a1, b1, c1 = rows[i]
            s2, a2, b2, c2 = rows[j]
            if s1 != s2:
                continue
            tag = f"{Path(s1).stem} {a1:.2f}~{b1:.2f}({c1.get('line')}) ↔ {a2:.2f}~{b2:.2f}({c2.get('line')})"
            if a1 < b2 - eps and a2 < b1 - eps:
                bad.append(f"겹침 {min(b1, b2) - max(a1, a2):.2f}초: {tag}")
                continue
            adjacent = abs(float(c1["t1"]) - float(c2["t0"])) < 0.06 and a2 >= b1 - eps
            th = min(B13_GAP_MAX, B13_GAP_FRAC * float(src_len.get(s1) or 0)) if src_len.get(s1) else B13_GAP_MAX
            gap = max(a1, a2) - min(b1, b2)
            if not adjacent and gap < th:
                bad.append(f"거리 {gap:.2f}초 < {th:.2f}: {tag}")
    return bad


def drop_verdict(ours: list, bench: list) -> tuple[bool | None, str]:
    """전환 세기(표준 ⑯): 우리 경계 drop 중앙값이 벤치 drop 중앙값의 ±TD_TOL 안. 우리 경계 0개 = ×(벤치엔 전환이 있는데 우리는 없다)."""
    o = [float(x) for x in ours if x is not None and x == x]
    b = [float(x) for x in bench if x is not None and x == x]
    if not b:
        return None, "벤치 drop 표본 없음(미측정)"
    bm = statistics.median(b)
    if not o:
        return False, f"우리 전환 경계 0개 — 벤치 drop 중앙 {bm:.3f}({len(b)}회)"
    om = statistics.median(o)
    ok = abs(om - bm) <= TD_TOL * abs(bm)
    return ok, f"우리 drop 중앙 {om:.3f}({len(o)}경계) vs 벤치 {bm:.3f}({len(b)}회 {[round(x, 3) for x in b]}) · 허용 ±{TD_TOL:.0%}"


def bench_drops(st: dict, kinds=TD_KINDS) -> dict | None:
    """벤치 줄판독에 그 전환 종류가 있는 편만 render_bench.bench_transition_drop — 채널 _kal/transition_drop.json 에 편별 캐시.
    벤치에 그 종류가 하나도 없으면 None(관문 행 생략 — 미측정 아님)."""
    from tools.calcopy.engine.kal_analyze import transition_key
    from tools.calcopy.hybrid.render_bench import bench_transition_drop
    B = st.get("bench") or {}
    lr = (ROOT / B["line_reads"]) if B.get("line_reads") and not Path(B["line_reads"]).is_absolute() else Path(B.get("line_reads") or "")
    if not B.get("line_reads") or not lr.exists():
        return None
    cpath = ROOT / "channel" / str(B.get("channel")) / "_kal" / "transition_drop.json"
    cache = jload(cpath) if cpath.exists() else {}
    out, used, n_src = {"drops": [], "ms": [], "per": {}}, False, 0
    for f in sorted(lr.glob("*.json")):
        d = jload(f)
        if not any(transition_key(l.get("transition")) in kinds for l in d.get("lines") or []):
            continue
        used = True
        v = Path(B.get("src_dir") or "") / f"{d.get('id')}.mp4"
        if not v.exists():
            out["per"][d.get("id")] = "원본 mp4 없음"
            continue
        n_src += 1
        for k in kinds:
            key = f"{d.get('id')}|{k}|{f.stat().st_size}:{int(f.stat().st_mtime)}|{v.stat().st_size}"
            if key not in cache:
                cache[key] = bench_transition_drop(f, v, kind=k)
            bs = cache[key].get("boundaries") or []
            out["per"][f"{d.get('id')}:{k}"] = [b.get("drop") for b in bs]
            out["drops"] += [b.get("drop") for b in bs]
            out["ms"] += [b.get("ms") for b in bs if b.get("ms") is not None]
    if not used:
        return None
    cpath.parent.mkdir(parents=True, exist_ok=True)
    jsave(cpath, cache)
    out["n_src"] = n_src
    return out


def gap_verdict(pairs: list[tuple[str, float, float]]) -> tuple[bool | None, str]:
    """B18 줄 사이 간격(표준 §11 ①ⓐ): [(경계, 계획 간격=시간표, 실측 무음)] — |실측−계획| ≤ 1프레임+0.02."""
    if not pairs:
        return None, "줄 경계 없음(미측정)"
    bad = [(k, p, m) for k, p, m in pairs if abs(m - p) > GAP_TOL]
    return (not bad), "경계 " + " ".join(f"{k}:{p:.2f}→{m:.2f}" for k, p, m in pairs) + f" (허용 ±{GAP_TOL:.3f})" + (f" · 밖 {[k for k, _, _ in bad]}" if bad else "")


def inline_pause_verdict(items: list[tuple[str, list[str], list[float]]], th: dict) -> tuple[bool | None, str]:
    """B18a 한 줄 안 문장부호 쉼(표준 §11 ①ⓑ): [(줄, 부호 목록(쉼표·마침표), 그 줄 안 무음 길이 목록)] — 긴 무음부터 마침표·쉼표 순으로 짝지어
    문턱 th{comma, period} −0.02/+0.03 안(checks 의 허용 폭과 같다)."""
    if not items:
        return None, "줄 안 문장부호 없음(해당 없음 — 미측정)"
    out, bad = [], []
    for lid, marks, sil in items:
        ms = sorted(marks, key=lambda m: 0 if m == "period" else 1)
        ss = sorted(sil, reverse=True)
        for k, m in enumerate(ms):
            v = ss[k] if k < len(ss) else 0.0
            ok = th[m] - 0.02 <= v <= th[m] + 0.03
            out.append(f"{lid}{'.' if m == 'period' else ','}{v:.2f}")
            if not ok:
                bad.append(f"{lid}:{m} {v:.2f}(목표 {th[m]})")
    return (not bad), " ".join(out) + f" (쉼표 {th['comma']}·마침표 {th['period']}, −0.02/+0.03)" + (f" · 밖 {bad}" if bad else "")


# ---------------------------------------------------------------- 관문
def _row(rows: list, group: str, what: str, fn, src: str, timer=None, ref: bool = False):
    import time
    t0 = time.time()
    try:
        ok, value = fn()
    except Exception as e:  # noqa: BLE001 — 못 잰 항목은 ×(미측정)로 남긴다. 조용히 넘기지 않는다
        ok, value = None, f"측정 실패: {type(e).__name__}: {str(e)[:200]}"
    sec = round(time.time() - t0, 1)
    rows.append({"group": group, "what": what, "ok": ok, "value": value, "src": src, "sec": sec, **({"ref": True} if ref else {})})
    if timer is not None:
        timer.done(f"gate:{group}:{what}", sec)
    return ok


def _cached(store: dict, key: str, fn):
    if key in store:
        return store[key]
    store[key] = fn()
    return store[key]


def gate(style_name: str, doc, work, bench: bool = True, eye_pack: bool = True, fit: bool = True, asr: bool = True, media: bool = True,
         only: tuple | None = None, llm=None, log=print, mode: str = "full") -> dict:
    """(판단 주인 — 품질 관문 한 벌) 표준 §5-1 묶음 그대로. mode = 'full'(납품 전 전부) | 'fast'(렌더 직후 FAST_GROUPS, 눈 묶음 없음).
    only = 묶음 이름 튜플 또는 'legacy10'(옛 bench_check 10항목만 — 회원 경로 호환)."""
    from tools.calcopy.engine.stage_log import Timer
    from tools.calcopy.hybrid.common import md5
    from tools.calcopy.hybrid import styles as ST
    from tools.calcopy.hybrid import thumb
    doc, work = Path(doc), Path(work)
    st = ST.load(style_name)
    R = work / "render"
    final = R / "final.mp4"
    T = jload(R / "timeline.json")
    tab = jload(R / "자막표.json")
    info = jload(R / "render_info.json") if (R / "render_info.json").exists() else {}
    S = jload(doc / "대본.json") if (doc / "대본.json").exists() else {}
    L, LD = st["loudness"], st["length"]
    win = tuple(st["frame"]["window"])
    legacy = only == "legacy10"
    if mode == "fast" and not only:
        only = FAST_GROUPS
        eye_pack = False
    want = (lambda g: True) if not only or legacy else (lambda g: g in only)
    rows: list = []
    cache: dict = {}
    timer = Timer(work / "gate_stage_log.json")
    cpath = R / "gate_cache.json"
    store = jload(cpath) if cpath.exists() else {}
    fmd5 = md5(final)

    def save_store():
        jsave(cpath, store)

    def row(group, what, fn, src, ref=False):
        return _row(rows, group, what, fn, src, timer, ref)

    def dur():
        if "d" not in cache:
            cache["d"] = vdur(final)
        return cache["d"]

    def loud():
        if "I" not in cache:
            cache["I"] = lufs(final)
        return cache["I"]

    # ── 규격
    if want("규격"):
        row("규격", "길이", lambda: (LD["min"] - 0.5 <= dur() <= LD["max"] + 0.5, f"{dur():.2f}초 (판 {LD['min']}~{LD['max']})"), "판 length · ffprobe")
        row("규격", "화면=시간표", lambda: (abs(dur() - T["end"]) <= 1 / FPS + 0.01, f"{dur():.3f} vs {T['end']}"), "timeline.end")
        row("규격", "음량", lambda: (abs(loud()[0] - L["lufs"]) <= 0.5, f"{loud()[0]} LUFS (목표 {L['lufs']})"), "ebur128")
        row("규격", "최고점", lambda: (loud()[1] <= L["tp"] + 0.5, f"{loud()[1]} dBFS (≤ {L['tp']}+0.5)"), "ebur128 peak")
        if not legacy:
            def size():
                w, h, _ = probe(final)
                f = fps_of(final)
                return (w, h) == SIZE and abs(f - FPS) < 0.01, f"{w}×{h} · {f}fps"
            row("규격", "1080×1920·30fps", size, "ffprobe")
    # ── 화면
    if want("화면"):
        first = T["lines"][next(iter(T["lines"]))]

        def face():
            f = thumb.face_check(final, win, tuple(first), log=log)
            return f["ok"], " ".join(f"{x['t']}s:{'○' if x['ok'] else x['why']}" for x in f["frames"])
        row("화면", "0초·첫 줄 얼굴", face, "thumb.face_check")
        row("화면", "컷 조각 프레임 = 계획", lambda: (lambda b: (not b, "전부 같음" if not b else str(b)))(part_frames(R, T)), "parts/c*.mp4")
        row("화면", "화면 멈춤 없음", lambda: (lambda z: (not z, "0건" if not z else " ".join(f"{a}~{b}s" for a, b in z)))(freezes(final, win)), "창 안 프레임 차")
        row("화면", "컷 끝 번쩍임 없음(0.2초 안 장면 경계)",
             lambda: (lambda s: (not s, "0건" if not s else str(s)))(part_slivers(R, T, Path(jload(doc / "재료.json")["cand_dir"]))), "render_bench.shot_starts")
        if not legacy:
            def y_ok():
                from tools.calcopy.hybrid.checks import Y_MIN, _ymean
                y0, y1 = _ymean(final, 0.3, win), _ymean(final, dur() - 0.3, win)
                return y0 >= Y_MIN and y1 >= Y_MIN, f"{y0:.0f} · {y1:.0f} (≥{Y_MIN})"
            row("화면", "B9 첫·끝 컷 Y≥60", y_ok, "checks._ymean")
            bd = None
            try:
                bd = bench_drops(st)
            except Exception as e:  # noqa: BLE001 — 벤치를 못 재면 행을 미측정으로 남긴다(생략 아님)
                row("화면", "전환 세기(zoomblur drop)", lambda e=e: (None, f"벤치 측정 실패: {type(e).__name__}: {str(e)[:160]}"), "render_bench.bench_transition_drop")
            if bd is not None:                  # 벤치에 zoomblur 가 없는 판은 행 생략(표준 ⑯)
                td = {}

                def drop_row():
                    from tools.calcopy.hybrid.render_bench import render_transition_drop
                    r = render_transition_drop(R, style_name, kinds=TD_KINDS)
                    td["ours"] = r.get("boundaries") or []
                    return drop_verdict([b.get("drop") for b in td["ours"]], bd["drops"])
                row("화면", "전환 세기(zoomblur drop 중앙 ±30%)", drop_row, "render_bench.render_transition_drop ↔ bench_transition_drop(채널 _kal 캐시)")
                row("화면", "전환 길이 ms(참고)", lambda: (True, f"우리 {[b.get('ms') for b in td.get('ours') or []]} · 벤치 {bd['ms']}"),
                    "transition_drop.ms", ref=True)
    # ── 재료
    cuts = [{"src": c["src"], "ss": float(c.get("ss") or 0), "dur": float(c["t1"]) - float(c["t0"]), "t0": float(c["t0"]), "t1": float(c["t1"]),
             "line": c.get("line"), "seg": "A" if c.get("kind") == "orig" else "B", "see": c.get("see")} for c in T.get("cuts") or []]
    if want("재료") and not legacy:
        from tools.calcopy.hybrid import checks as CK

        def b13():
            if st.get("renderer") in OLD_PAUSE_RENDERERS:
                v = CK.reuse_violations(cuts, CK.orig_spans_of(S, "잇썸홈판"))
                return not v, v or "0"
            from tools.calcopy.hybrid.common import dur_of
            cd = Path(jload(doc / "재료.json")["cand_dir"])
            lens = {c["src"]: dur_of(cd / c["src"]) for c in cuts if (cd / c["src"]).exists()}
            v = reuse_violations_bench(cuts, lens)
            return not v, (v or "0") if v else f"0 (소스 길이 {{{', '.join(f'{Path(k).stem}:{x:.1f}' for k, x in lens.items())}}})"
        row("재료", "B13 같은 장면 재사용(겹침 ×·거리 min(3, 0.25×길이))", b13, "quality_gate.reuse_violations_bench")
        row("재료", "B16 A-B-A 끼움(나레 컷)", lambda: (lambda v: (not v, v or "0"))(CK.aba_violations([c for c in cuts if c["seg"] == "B"])), "checks.aba_violations")

        def seams():
            from tools.calcopy.engine import check_seams
            s = _cached(store, f"seams|{fmd5}|{list(win)}", lambda: check_seams.check(str(final), win, None))
            save_store()
            jsave(R / "seams.json", s)
            return s["ok"], f"컷 {len(s['컷'])} · 되감김 {len(s['되감김'])} {[r.get('t') for r in s['되감김']]} · 점프줌 {len(s['점프줌'])}({s['점프줌_판정'] or '드묾'})"
        row("재료", "B16' 되감김·점프줌", seams, "engine/check_seams.check")
    # ── 자막·효과
    lrp = (st.get("bench") or {}).get("line_reads")
    lrp = (ROOT / lrp) if lrp and not Path(lrp).is_absolute() else (Path(lrp) if lrp else None)
    bench_docs = [jload(p) for p in sorted(lrp.glob("*.json"))] if lrp and lrp.exists() else []
    if want("자막·효과"):
        row("자막·효과", "배치(본보기 벤치 편 대조)",
             lambda: (tab["check"]["ok"], f"본보기 {tab['check']['reference']} · 칸 최대 차 {tab['check']['worst_slot_diff']}"), "자막표.check = placement.check_place")
        if not legacy:
            row("자막·효과", "B14 효과음 과다(≤ 벤치 p90)", lambda: sfx_excess(len(tab.get("sfx") or []), float(T["end"]), bench_docs), "자막표.sfx · 줄판독 sfx")
    # ── 소리
    if (want("소리") or mode == "fast") and not legacy:      # 줄별 cps = render_info 표 읽기라 빠르다 → --fast 에도
        row("소리", "줄별 말속도 ±35%(렌더 기록)", lambda: line_cps_verdict(info.get("line_cps"), cps_tol()), "render_info.line_cps · render_itssum.CPS_LINE_TOL")
    if want("소리") and not legacy:
        narr = [l for l in S.get("lines") or [] if l.get("kind") == "tts"]

        ids = list(T["lines"])

        def gaps():
            from tools.calcopy.hybrid.checks import PAUSE_HI, PAUSE_LO, pauses_between
            if st.get("renderer") in OLD_PAUSE_RENDERERS:      # 옛 길 상수(표준 §11 ①ⓒ)
                bounds = [(T["lines"][a][1], T["lines"][b][0]) for a, b in zip(ids[:-1], ids[1:]) if a.startswith("N") and b.startswith("N")]
                pv = [p["pause"] for p in pauses_between(R / "voice.wav", bounds)]
                return (all(PAUSE_LO - 0.02 <= p <= PAUSE_HI + 0.03 for p in pv) if pv else None), f"옛 길 쉼 {pv} ({PAUSE_LO}~{PAUSE_HI})"
            bounds = [(f"{a}→{b}", T["lines"][a][1], T["lines"][b][0]) for a, b in zip(ids[:-1], ids[1:])]
            meas = pauses_between(R / "voice.wav", [(x, y) for _, x, y in bounds])
            return gap_verdict([(k, round(y - x, 3), m["pause"]) for (k, x, y), m in zip(bounds, meas)])
        row("소리", "B18 줄 사이 간격 = 판 timing(±1프레임+0.02)", gaps, "timeline.lines(판 timing) · checks.pauses_between(voice.wav)")

        def inline():
            from tools.calcopy.hybrid.common import silences
            sp = st.get("speech") or {}
            th = {"comma": float(sp.get("pause_comma", 0.22)), "period": float(sp.get("pause_period", 0.30))}
            sil = silences(R / "voice.wav", "-35dB", 0.08)
            items = []
            for l in narr:
                txt = (l.get("tts") or "").rstrip(" .,?!~…")
                marks = ["comma" if ch == "," else "period" for ch in txt if ch in ",."]
                if not marks or l["id"] not in T["lines"]:
                    continue
                a, b = T["lines"][l["id"]]
                inside = [round(min(e, b - 0.05) - max(x, a + 0.05), 3) for x, e in sil if e > a + 0.05 and x < b - 0.05]
                items.append((l["id"], marks, [v for v in inside if v > 0]))
            return inline_pause_verdict(items, th)
        row("소리", "B18a 줄 안 문장부호 쉼", inline, "판 speech.pause_comma/period(없으면 0.22/0.30) · voice.wav 무음")

        def asr_rows():
            if not asr:
                return None, "받아쓰기 안 함(--no-asr, 미측정)"
            from tools.calcopy.engine import check_line_sync as LS
            win_n = [tuple(T["lines"][l["id"]]) for l in narr if l["id"] in T["lines"]]
            vmd5 = md5(R / "voice.wav")
            allsegs = _cached(store, f"asr|{vmd5}", lambda: [list(x) for x in LS.asr_segments(R / "voice.wav")])
            save_store()
            segs = [tuple(s) for s in allsegs if any(a - 0.3 <= s[0] <= b + 0.3 for a, b in win_n)]
            heard = LS.line_starts_from_asr([l.get("tts") or "" for l in narr], segs)
            out = []
            for l, h in zip(narr, heard):
                t0 = T["lines"].get(l["id"], [None])[0]
                d = None if h is None or t0 is None else round(float(t0) - h, 2)
                out.append({"line": l["id"], "said": l.get("tts"), "t0": t0, "heard_t0": h, "diff": d, "ok": d is not None and abs(d) <= LS.LIMIT})
            cache["asr"] = {"rows": out, "segs": segs}
            bad = [r["line"] for r in out if not r["ok"]]
            return not bad, f"나레 {len(out)}줄 중 못 찾음·{LS.LIMIT}초 넘게 어긋남 {bad or '0'} (whisper 로컬)"
        row("소리", "나레 받아쓰기 ↔ 대본", asr_rows, "engine/check_line_sync(whisper)")
    # ── 대본
    if want("대본") and not legacy:
        def aud():
            from tools.calcopy.hybrid import script_audit
            r = script_audit.audit(doc / "대본.json", style_name)
            bad = [f"{x['kind']}: {x['why']}" for x in r["rules"] if not x["ok"]] + ([f"engine {r['engine']}"] if r.get("engine") and not r["engine"].get("ok") else [])
            return r["ok"], f"규칙 {len(r['rules'])}개 · 미달 {bad or '0'}"
        row("대본", "script_audit", aud, "hybrid/script_audit.audit")
    # ── 썸네일(0초 측정이 1차 자 thumb.frame0 에 들어가므로 1차 자보다 먼저)
    if want("썸네일"):
        def ts():
            ok, msg = thumb_stamped(final, doc)
            cache["frame0"] = "card" if ok else ("scene" if ok is False else None)
            if legacy:              # 옛 bench_check 그대로: 썸네일.json 없으면 검사 안 함 = 통과
                return ok is not False, msg
            return ok, msg
        row("썸네일", "썸네일 맨 앞 2프레임", ts, "썸네일.json · 완성본 0~2프레임")
        if not legacy:
            def trule():
                from tools.calcopy.hybrid import thumb_rule
                sp = doc / "썸네일.json"
                if not sp.exists():
                    return None, "썸네일.json 없음(미측정)"
                bad = thumb_rule.check(jload(sp), n_parts=len(T.get("cuts") or []))
                return not bad, bad or "통과"
            row("썸네일", "thumb_rule.check(3안 규칙)", trule, "hybrid/thumb_rule.check")

            def adm():
                from tools.calcopy.engine import ad_mark
                _, _, comment = ad_mark._probe(final)
                return ad_mark.MARK in comment, f"완성본 comment = {comment!r}"
            row("썸네일", "광고 표시(ad_mark)", adm, "engine/ad_mark 표식")
    # ── 1차 자
    match = None
    if want("1차 자") and not legacy and bench:
        def m():
            nonlocal match
            from tools.calcopy.engine import kal_analyze as K
            lr = sorted((st.get("bench") or {}).get("line_reads") and (ROOT / st["bench"]["line_reads"]).glob("*.json") or [])
            key = "match|" + hashlib.sha256("|".join([fmd5, md5(R / "자막표.json"), md5(R / "timeline.json"), str(media), str(cache.get("frame0")), md5(Path(K.__file__)),
                                                       hashlib.sha256(ST.path_of(style_name).read_bytes()).hexdigest()]
                                                      + [f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in lr]).encode()).hexdigest()[:24]
            match = _cached(store, key, lambda: K.match_from_render(st, doc, work, media=media, frame0_kind_measured=cache.get("frame0")))
            save_store()
            match["ok"] = match.get("verdict") == "통과"       # 카드(preset_card match_ok)가 읽는 칸
            jsave(doc / "재현일치도.json", match)
            (doc / "재현일치도.md").write_text(K.match_md(match, f"{style_name} {doc.name}"), encoding="utf-8")
            ok, msg, _ = match_verdict(match, bool(st.get("base")))
            if st.get("base"):                                  # 업그레이드 판: 05 업그레이드 자 결과를 붙인다(판정은 05 의 gates.upgrade)
                up = K.upgrade_table(st, doc, work)
                cache["gates_upgrade"] = {**up["gates"]["upgrade"], "better_n": up["better_n"], "measured_n": up["measured_n"],
                                          "file": str(doc / "업그레이드_측정.json")}
                match["upgrade"] = cache["gates_upgrade"]
                msg += f" · 업그레이드 나아짐 {up['gates']['upgrade']['better']}(사람 {up['human_n']}·미측정 {up['unmeasured_n']})"
            return ok, msg
        row("1차 자", "재현일치도(match_table)", m, "kal_analyze.match_from_render → 재현일치도.json")
    # ── 장면↔대사(㉔ 프레임 동일성 + 계획 점수 보고)
    fit_res = None
    if want("장면↔대사") and not legacy:
        def same():
            nonlocal fit_res
            from tools.calcopy.hybrid.render_bench import frame_window
            wv = frame_window(st["frame"])
            wv = [wv[0], wv[1], wv[2], min(wv[3], 1920 - wv[1])]
            import numpy as np
            cb = next((d.get("layout", {}).get("caption_band") for d in bench_docs if (d.get("layout") or {}).get("caption_band")), None)

            def band(t, shape):                 # base.mp4(자막 없는 바탕)가 없을 때만 쓰인다 — 완성본에서 벤치 자막 띠(layout.caption_band ±40)를 뺀다
                m = np.zeros(shape, bool)
                if cb:
                    m[max(0, cb[0] - 40 - wv[1]):max(0, cb[1] + 40 - wv[1]), :] = True
                return m
            rows_ = plan_frames_check(R, T, Path(jload(doc / "재료.json")["cand_dir"]), wv, band)
            fit_res = {"made_by": "quality_gate.plan_frames_check", "min_sim": FRAME_SAME_MIN, "rows": rows_,
                       "screen": "base.mp4(자막 전 완성 화면)" if (R / "base.mp4").exists() else "final.mp4 − 벤치 자막 띠 ±40"}
            jsave(doc / "장면대사.json", fit_res)
            return plan_frames_verdict(rows_)
        row("장면↔대사", "완성본 컷 = 계획 프레임(창 대조 ≥0.97)", same, "quality_gate.plan_frames_check(base.mp4 또는 final−자막 띠 ↔ 원본 ss)")
        pr = plan_score_report(doc, (st.get("bench") or {}).get("channel"))
        row("장면↔대사", "계획 점수(루브릭)", lambda: pr[:2], "<doc>/장면대사_계획.json(material_fit) · channel/<slug>/_kal/상위편_목표.json", ref=pr[2])
    # ── 표식
    if want("표식") and not legacy:
        def mk():
            try:
                sf = ST.path_of(style_name)
            except SystemExit:
                sf = None
            return marker_verdict(info, sf)
        row("표식", "render_info 표식(판 sha·렌더러 sig·reference)", mk, "render_info.json")
    if legacy:                      # 옛 bench_check 줄 순서 그대로(자동검사.json 대조 호환)
        rows.sort(key=lambda r: LEGACY10.index(r["what"]))
    ok = all(r["ok"] is True for r in rows if not r.get("ref"))     # 참고 행은 판정 밖
    rep = {"style": style_name, "ok": ok, "gate": GATE_VERSION, "mode": "legacy10" if legacy else (mode if mode == "fast" else (list(only) if only else "full")),
           "sec": round(sum(r.get("sec") or 0 for r in rows), 1),
           "rows": [{"group": r["group"], "what": r["what"], "ok": r["ok"], "value": r["value"], "src": r["src"], "sec": r.get("sec"), **({"ref": True} if r.get("ref") else {})} for r in rows],
           "n": len(rows), "n_ok": sum(r["ok"] is True for r in rows), "n_bad": sum(r["ok"] is False for r in rows), "n_unmeasured": sum(r["ok"] is None for r in rows),
           "placement": tab.get("check"), "log": tab.get("log"),
           "match": {"verdict": match["verdict"], "file": str(doc / "재현일치도.json")} if match else None,
           "gates": {"upgrade": cache.get("gates_upgrade")},      # preset_card L3 가 읽는다(업그레이드 판만, 1차 판은 None)
           "fit": {"min_sim": fit_res["min_sim"], "n": len(fit_res["rows"]), "file": str(doc / "장면대사.json")} if fit_res else None}
    if eye_pack and not legacy:
        try:
            rep["eye_pack_dir"] = str(make_eye_pack(style_name, doc, work, T, tab, S, cuts, cache.get("asr"), fit_res, bool(st.get("base"))))
        except Exception as e:  # noqa: BLE001 — 눈 검수 묶음 실패는 관문 ×(묶음 없이 2단을 못 한다)
            rep["eye_pack_dir"] = None
            rep["rows"].append({"group": "표식", "what": "눈 검수 묶음", "ok": False, "value": f"만들기 실패: {e}", "src": "make_eye_pack"})
            rep["ok"] = False
    if not legacy:
        jsave(doc / "품질관문.json", rep)
    jsave(doc / "자동검사.json", rep)       # 호환(runner_ops·flow 가 이 파일을 읽는다) — 같은 내용
    for r in rep["rows"]:
        log(f"  {'참고' if r.get('ref') else '○' if r['ok'] is True else '×' if r['ok'] is False else '미측정'} [{r['group']}] {r['what']} ({r.get('sec')}초): {r['value']}")
    return {"ok": rep["ok"], "report": str(doc / ("자동검사.json" if legacy else "품질관문.json")), "rows": rep["rows"], "match": match, "fit": fit_res,
            "eye_pack_dir": rep.get("eye_pack_dir")}


# ---------------------------------------------------------------- 2단 눈 검수 묶음(표준 §5-2)
EYE_Q = [("E1", "그 채널에 올려도 되나(결·톤)", "벤치 3편 섞어 놓으면 구분이 안 간다(1차) / 더 낫다고 말할 수 있다(업그레이드)"),
         ("E2", "훅 3초", "결과·반전·얼굴/물건 — 벤치 훅 규칙(카드 rules thumb·script) 그대로"),
         ("E3", "줄↔장면", "문장에 적힌 동작·상태가 그 컷에 보인다(A3) — 전부 ○"),
         ("E4", "자막", "모양·등장·강조·꾸밈 없는 줄이 벤치 본보기 편과 같다(없는 것도 스타일)"),
         ("E5", "소리", "발음 뭉개짐 0·원음 알아들림·BGM 이 말을 안 가림·효과음이 박자에 맞음"),
         ("E6", "사실", "지어낸 사실·금액·CTA·질병 0 — 근거.md 줄마다"),
         ("E7", "금지", "다른 채널 연예인 영상 0·남의 글자 0·원본 로고/워터마크 0"),
         ("E8", "썸네일 카드", "본편에 있는 장면·행동 지점 원·'??'+꼬리표")]
EYE_Q9 = ("E9", "업그레이드(해당 판만)", "바꾼 칸마다 §4-2 측정값이 나아졌고 근거 기록이 있다")


def _strip(final: Path, t0: float, t1: float, dst: Path, step: float = 0.1, cols: int = 10, w: int = 162):
    """t0~t1 을 step 초마다 한 칸(위에 시각) — 0.1초 띠."""
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid.compare_sheet import grab
    h = round(w * 1920 / 1080)
    ts = [round(t0 + k * step, 2) for k in range(int(round((t1 - t0) / step)))]
    rows_n = (len(ts) + cols - 1) // cols
    im = Image.new("RGB", (cols * w, rows_n * (h + 18)), (16, 16, 16))
    d = ImageDraw.Draw(im)
    for k, t in enumerate(ts):
        x, y = (k % cols) * w, (k // cols) * (h + 18)
        im.paste(grab(final, t, (w, h)), (x, y + 18))
        d.text((x + 4, y + 2), f"{t:.1f}s", fill=(255, 230, 0))
    im.save(dst, quality=85)
    return dst


def make_eye_pack(style_name: str, doc: Path, work: Path, T: dict, tab: dict, S: dict, cuts: list, asr: dict | None, fit_res: dict | None,
                  upgrade: bool) -> Path:
    """<work>/eye/ = 1초 시트 · 벤치 나란히(compare_sheet) · 훅 3초·끝 2초 0.1초 띠 · 받아쓰기 대조표 · 줄↔컷 대조표 · 눈검수_질문.md."""
    from tools.calcopy.engine.remake import sheet_1s
    from tools.calcopy.hybrid import compare_sheet
    E = Path(work) / "eye"
    E.mkdir(parents=True, exist_ok=True)
    final = Path(work) / "render" / "final.mp4"
    s1 = Path(doc) / "final_sheet_1s.jpg"
    if not s1.exists():
        sheet_1s(final, s1)
    shutil.copy2(s1, E / "시트_1초.jpg")
    compare_sheet.sheet(style_name, Path(doc), Path(work))
    for n in ("벤치대조_시트.jpg", "벤치대조_등장.jpg"):
        if (Path(doc) / n).exists():
            shutil.copy2(Path(doc) / n, E / n)
    end = float(T["end"])
    _strip(final, 0.0, min(3.0, end), E / "훅3초_0.1초.jpg")
    _strip(final, max(0.0, end - 2.0), end - 0.05, E / "끝2초_0.1초.jpg")
    A = ["# 받아쓰기 대조표 (나레 줄 ↔ 완성본 voice.wav 받아쓰기, whisper 로컬)", "",
         "| 줄 | 대본(말한 글) | 자막 시작 | 들린 시작 | 차 | ○× |", "|---|---|---|---|---|---|"]
    if asr:
        A += [f"| {r['line']} | {r['said']} | {r['t0']} | {r['heard_t0']} | {r['diff']} | {'○' if r['ok'] else '×'} |" for r in asr["rows"]]
        A += ["", "받아쓰기 원문(나레 구간):", "", " ".join(w for _, _, w in asr["segs"])]
    else:
        A += ["", "(받아쓰기 안 함 — `--no-asr` 또는 측정 실패. 눈 검수 E5 는 소리를 직접 들어 판정)"]
    for o in [l for l in S.get("lines") or [] if l.get("kind") == "orig"]:
        A += [f"- 원음 {o.get('id')}: said «{o.get('said', '')}» · 자막 {[c.get('text') for c in o.get('caps') or []]}"]
    (E / "받아쓰기대조.md").write_text("\n".join(A) + "\n", encoding="utf-8")
    fit_by = {}
    for r in (fit_res or {}).get("rows") or []:
        fit_by[r["k"]] = r
    C = ["# 줄↔컷 대조표 (컷마다: 시각 · 줄 · 그 순간 자막 · 화면 설명(재료) · 계획 점수(루브릭) · 완성본=계획 프레임 같음)", "",
         "| # | 시각 | 줄 | 자막 | 화면(소스@초 · 설명) | 계획 fit · 같음 | 판정(E3) |", "|---|---|---|---|---|---|---|"]
    rows = tab.get("rows") or []
    for k, c in enumerate(T.get("cuts") or []):
        cap = " / ".join(r.get("text") or "" for r in rows if float(r["t0"]) < float(c["t1"]) and float(r["t1"]) > float(c["t0"]))
        fr = fit_by.get(k)
        C.append(f"| {k} | {c['t0']:.2f}–{c['t1']:.2f} | {c.get('line')} | {cap} | {Path(str(c['src'])).stem}@{c.get('ss')} {c.get('see', '')} | "
                 f"{c.get('fit', '-')} · 같음 {fr.get('sim') if fr else '-'} |  |")
    (E / "줄컷대조.md").write_text("\n".join(C) + "\n", encoding="utf-8")
    Q = [f"# 눈 검수 질문 — {style_name} {Path(doc).name} (표준 §5-2)", "",
         "답은 `<doc>/눈검수.json` {\"E1\": {\"v\": \"○|×|△\", \"memo\": \"…\"}, …} — ○ 전부 + △ 0 이어야 통과.", "",
         "자료: 시트_1초.jpg · 벤치대조_시트.jpg · 벤치대조_등장.jpg · 훅3초_0.1초.jpg · 끝2초_0.1초.jpg · 받아쓰기대조.md · 줄컷대조.md", "",
         "| # | 묻는 것 | 기준 |", "|---|---|---|"]
    Q += [f"| {a} | {b} | {c} |" for a, b, c in EYE_Q + ([EYE_Q9] if upgrade else [])]
    Q += ["", "×가 나면 그 항목을 1단 자동 항목으로 만들 수 있는지 먼저 본다(한 번 지적받은 건 도구 규칙으로)."]
    (E / "눈검수_질문.md").write_text("\n".join(Q) + "\n", encoding="utf-8")
    return E


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate")
    g.add_argument("style"); g.add_argument("doc"); g.add_argument("work")
    g.add_argument("--no-fit", action="store_true"); g.add_argument("--no-asr", action="store_true")
    g.add_argument("--no-media", action="store_true"); g.add_argument("--no-eye", action="store_true")
    g.add_argument("--legacy10", action="store_true", help="옛 bench_check 10항목만")
    m = g.add_mutually_exclusive_group()
    m.add_argument("--fast", action="store_true", help="렌더 직후: 규격·화면·재료·자막·효과·표식(목표 ≤2분)")
    m.add_argument("--full", action="store_true", help="납품 전: 전부(기본)")
    a = ap.parse_args(argv)
    r = gate(a.style, Path(a.doc), Path(a.work), eye_pack=not a.no_eye, fit=not a.no_fit, asr=not a.no_asr, media=not a.no_media,
             only="legacy10" if a.legacy10 else None, mode="fast" if a.fast else "full")
    print(f"판정 {'통과' if r['ok'] else '미달'} → {r['report']}")
    if r.get("match"):
        print(f"재현일치도 {r['match']['verdict']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
