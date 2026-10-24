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
  장면↔대사 = oneshot/scene_fit.measure_render(material_auto.fit_judge, Claude 소넷) · 썸네일 규칙 = thumb_rule.check · 광고 = engine/ad_mark 표식
판정: 항목 ok = True(○) / False(×) / None(미측정 — ×로 센다, 표준 §4-1 "미측정 칸은 ✓가 아니다"). 하나라도 ○가 아니면 ok:false.
출력: <doc>/품질관문.json · <doc>/자동검사.json(같은 내용, 옛 꼴 호환) · <doc>/재현일치도.json·.md · <doc>/장면대사.json · <work>/eye/(눈 검수 묶음)
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
from tools.calcopy.hybrid.common import FPS, ROOT, jload, jsave, lufs, nchar, probe, run  # noqa: E402

GATE_VERSION = "quality_gate:v1(2026-10-24)"
FREEZE_SEC = 0.3      # 창 안 같은 그림이 이만큼 이어지면 멈춤(벤치 컷 중앙 약 1초 · 실제 촬영 영상은 프레임마다 잡음이 있어 0이 안 나온다)
SIZE = (1080, 1920)
FIT_MEAN_TOL, FIT_BELOW_TOL = 1.0, 0.10   # 장면↔대사 = 평균 ≥ 벤치−1 · 7 미만 비율 ≤ 벤치+10%p(표준 §3-3 A5 · 지침서 §3-4)
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


def bench_fit(bench_docs: list[dict]) -> dict | None:
    """벤치 줄판독 fit 칸(0~10) → 편별 평균·FIT_MIN 미만 비율의 중앙값."""
    from tools.calcopy.engine import material_auto as MA
    per = []
    for d in bench_docs:
        sc = [l["fit"] for l in d.get("lines") or [] if isinstance(l.get("fit"), (int, float))]
        if sc:
            per.append((sum(sc) / len(sc), sum(1 for s in sc if s < MA.FIT_MIN) / len(sc)))
    if not per:
        return None
    return {"mean": round(statistics.median(m for m, _ in per), 2), "below_rate": round(statistics.median(b for _, b in per), 3), "n_docs": len(per)}


def fit_verdict(ours: dict, bench: dict | None) -> tuple[bool | None, str]:
    if not bench:
        return None, "벤치 줄판독 fit 칸 없음(미측정)"
    if ours.get("mean") is None:
        return None, f"우리 판정 0칸(미측정) — 벤치 평균 {bench['mean']}"
    ok = ours["mean"] >= bench["mean"] - FIT_MEAN_TOL and ours["below_rate"] <= bench["below_rate"] + FIT_BELOW_TOL
    return ok, (f"우리 평균 {ours['mean']}·7 미만 {ours['below_min']}/{ours['judged']}({ours['below_rate']}) vs 벤치 평균 {bench['mean']}·"
                f"7 미만 {bench['below_rate']} (기준 평균 ≥ 벤치−{FIT_MEAN_TOL}, 미만 비율 ≤ 벤치+{FIT_BELOW_TOL})")


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


def line_cps_verdict(chars: dict, durs: dict) -> tuple[bool | None, str]:
    """줄별 말속도 ±35%(2693d5856 render_itssum.make_sentences 의 align 경계 장치와 같은 폭 — 그쪽은 렌더를 멈추고, 여기는 완성본 소리 조각으로 다시 잰다)."""
    ids = [k for k in chars if durs.get(k)]
    if not ids:
        return None, "줄 소리 조각(s_<줄>.wav) 없음(미측정)"
    mean = sum(chars[k] for k in ids) / sum(durs[k] for k in ids)
    rates = {k: round(chars[k] / durs[k], 2) for k in ids}
    bad = {k: r for k, r in rates.items() if not (0.65 * mean <= r <= 1.35 * mean)}
    return (not bad), f"평균 {mean:.2f}자/초 · " + " ".join(f"{k}:{r}" for k, r in rates.items()) + (f" · 밖 {bad}" if bad else "")


# ---------------------------------------------------------------- 관문
def _row(rows: list, group: str, what: str, fn, src: str):
    try:
        ok, value = fn()
    except Exception as e:  # noqa: BLE001 — 못 잰 항목은 ×(미측정)로 남긴다. 조용히 넘기지 않는다
        ok, value = None, f"측정 실패: {type(e).__name__}: {str(e)[:200]}"
    rows.append({"group": group, "what": what, "ok": ok, "value": value, "src": src})
    return ok


def gate(style_name: str, doc, work, bench: bool = True, eye_pack: bool = True, fit: bool = True, asr: bool = True, media: bool = True,
         only: tuple | None = None, llm=None, log=print) -> dict:
    """(판단 주인 — 품질 관문 한 벌) 표준 §5-1 묶음 그대로. only = 묶음 이름 튜플 또는 'legacy10'(옛 bench_check 10항목만 — 회원 경로 호환)."""
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
    want = (lambda g: True) if not only or legacy else (lambda g: g in only)
    rows: list = []
    cache: dict = {}

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
        _row(rows, "규격", "길이", lambda: (LD["min"] - 0.5 <= dur() <= LD["max"] + 0.5, f"{dur():.2f}초 (판 {LD['min']}~{LD['max']})"), "판 length · ffprobe")
        _row(rows, "규격", "화면=시간표", lambda: (abs(dur() - T["end"]) <= 1 / FPS + 0.01, f"{dur():.3f} vs {T['end']}"), "timeline.end")
        _row(rows, "규격", "음량", lambda: (abs(loud()[0] - L["lufs"]) <= 0.5, f"{loud()[0]} LUFS (목표 {L['lufs']})"), "ebur128")
        _row(rows, "규격", "최고점", lambda: (loud()[1] <= L["tp"] + 0.5, f"{loud()[1]} dBFS (≤ {L['tp']}+0.5)"), "ebur128 peak")
        if not legacy:
            def size():
                w, h, _ = probe(final)
                f = fps_of(final)
                return (w, h) == SIZE and abs(f - FPS) < 0.01, f"{w}×{h} · {f}fps"
            _row(rows, "규격", "1080×1920·30fps", size, "ffprobe")
    # ── 화면
    if want("화면"):
        first = T["lines"][next(iter(T["lines"]))]

        def face():
            f = thumb.face_check(final, win, tuple(first), log=log)
            return f["ok"], " ".join(f"{x['t']}s:{'○' if x['ok'] else x['why']}" for x in f["frames"])
        _row(rows, "화면", "0초·첫 줄 얼굴", face, "thumb.face_check")
        _row(rows, "화면", "컷 조각 프레임 = 계획", lambda: (lambda b: (not b, "전부 같음" if not b else str(b)))(part_frames(R, T)), "parts/c*.mp4")
        _row(rows, "화면", "화면 멈춤 없음", lambda: (lambda z: (not z, "0건" if not z else " ".join(f"{a}~{b}s" for a, b in z)))(freezes(final, win)), "창 안 프레임 차")
        _row(rows, "화면", "컷 끝 번쩍임 없음(0.2초 안 장면 경계)",
             lambda: (lambda s: (not s, "0건" if not s else str(s)))(part_slivers(R, T, Path(jload(doc / "재료.json")["cand_dir"]))), "render_bench.shot_starts")
        if not legacy:
            def y_ok():
                from tools.calcopy.hybrid.checks import Y_MIN, _ymean
                y0, y1 = _ymean(final, 0.3, win), _ymean(final, dur() - 0.3, win)
                return y0 >= Y_MIN and y1 >= Y_MIN, f"{y0:.0f} · {y1:.0f} (≥{Y_MIN})"
            _row(rows, "화면", "B9 첫·끝 컷 Y≥60", y_ok, "checks._ymean")
    # ── 재료
    cuts = [{"src": c["src"], "ss": float(c.get("ss") or 0), "dur": float(c["t1"]) - float(c["t0"]), "t0": float(c["t0"]), "t1": float(c["t1"]),
             "line": c.get("line"), "seg": "A" if c.get("kind") == "orig" else "B", "see": c.get("see")} for c in T.get("cuts") or []]
    if want("재료") and not legacy:
        from tools.calcopy.hybrid import checks as CK

        def b13():
            v = CK.reuse_violations(cuts, CK.orig_spans_of(S, "잇썸홈판"))     # 대본 lines[kind=orig, src, spans] 꼴 = 잇썸홈판 꼴과 같다
            return not v, v or "0"
        _row(rows, "재료", "B13 같은 장면 ±3초 재사용", b13, "checks.reuse_violations")
        _row(rows, "재료", "B16 A-B-A 끼움(나레 컷)", lambda: (lambda v: (not v, v or "0"))(CK.aba_violations([c for c in cuts if c["seg"] == "B"])), "checks.aba_violations")

        def seams():
            from tools.calcopy.engine import check_seams
            s = check_seams.check(str(final), win, None)
            jsave(R / "seams.json", s)
            return s["ok"], f"컷 {len(s['컷'])} · 되감김 {len(s['되감김'])} {[r.get('t') for r in s['되감김']]} · 점프줌 {len(s['점프줌'])}({s['점프줌_판정'] or '드묾'})"
        _row(rows, "재료", "B16' 되감김·점프줌", seams, "engine/check_seams.check")
    # ── 자막·효과
    lrp = (st.get("bench") or {}).get("line_reads")
    lrp = (ROOT / lrp) if lrp and not Path(lrp).is_absolute() else (Path(lrp) if lrp else None)
    bench_docs = [jload(p) for p in sorted(lrp.glob("*.json"))] if lrp and lrp.exists() else []
    if want("자막·효과"):
        _row(rows, "자막·효과", "배치(본보기 벤치 편 대조)",
             lambda: (tab["check"]["ok"], f"본보기 {tab['check']['reference']} · 칸 최대 차 {tab['check']['worst_slot_diff']}"), "자막표.check = placement.check_place")
        if not legacy:
            _row(rows, "자막·효과", "B14 효과음 과다(≤ 벤치 p90)", lambda: sfx_excess(len(tab.get("sfx") or []), float(T["end"]), bench_docs), "자막표.sfx · 줄판독 sfx")
    # ── 소리
    if want("소리") and not legacy:
        narr = [l for l in S.get("lines") or [] if l.get("kind") == "tts"]

        def cps():
            from tools.calcopy.hybrid.common import dur_of
            chars = {l["id"]: nchar(l.get("tts") or "") for l in narr}
            durs = {k: dur_of(R / f"s_{k}.wav") for k in chars if (R / f"s_{k}.wav").exists()}
            return line_cps_verdict(chars, durs)
        _row(rows, "소리", "줄별 말속도 ±35%", cps, "s_<줄>.wav · 대본 tts 글자")

        def pauses():
            from tools.calcopy.hybrid.checks import PAUSE_HI, PAUSE_LO, pauses_between
            ids = list(T["lines"])
            bounds = [(T["lines"][a][1], T["lines"][b][0]) for a, b in zip(ids[:-1], ids[1:]) if a.startswith("N") and b.startswith("N")]
            if not bounds:
                return None, "이어진 나레 줄 경계 없음(미측정)"
            pv = [p["pause"] for p in pauses_between(R / "voice.wav", bounds)]
            return all(PAUSE_LO - 0.02 <= p <= PAUSE_HI + 0.03 for p in pv), f"나레↔나레 경계 쉼 {pv} (checks {PAUSE_LO}~{PAUSE_HI} +0.03/−0.02)"
        _row(rows, "소리", "B18 쉼 0.22~0.30", pauses, "checks.pauses_between(voice.wav)")

        def asr_rows():
            if not asr:
                return None, "받아쓰기 안 함(--no-asr, 미측정)"
            from tools.calcopy.engine import check_line_sync as LS
            win_n = [tuple(T["lines"][l["id"]]) for l in narr if l["id"] in T["lines"]]
            segs = [s for s in LS.asr_segments(R / "voice.wav") if any(a - 0.3 <= s[0] <= b + 0.3 for a, b in win_n)]
            heard = LS.line_starts_from_asr([l.get("tts") or "" for l in narr], segs)
            out = []
            for l, h in zip(narr, heard):
                t0 = T["lines"].get(l["id"], [None])[0]
                d = None if h is None or t0 is None else round(float(t0) - h, 2)
                out.append({"line": l["id"], "said": l.get("tts"), "t0": t0, "heard_t0": h, "diff": d, "ok": d is not None and abs(d) <= LS.LIMIT})
            cache["asr"] = {"rows": out, "segs": segs}
            bad = [r["line"] for r in out if not r["ok"]]
            return not bad, f"나레 {len(out)}줄 중 못 찾음·{LS.LIMIT}초 넘게 어긋남 {bad or '0'} (whisper 로컬)"
        _row(rows, "소리", "나레 받아쓰기 ↔ 대본", asr_rows, "engine/check_line_sync(whisper)")
    # ── 대본
    if want("대본") and not legacy:
        def aud():
            from tools.calcopy.hybrid import script_audit
            r = script_audit.audit(doc / "대본.json", style_name)
            bad = [f"{x['kind']}: {x['why']}" for x in r["rules"] if not x["ok"]] + ([f"engine {r['engine']}"] if r.get("engine") and not r["engine"].get("ok") else [])
            return r["ok"], f"규칙 {len(r['rules'])}개 · 미달 {bad or '0'}"
        _row(rows, "대본", "script_audit", aud, "hybrid/script_audit.audit")
    # ── 썸네일(0초 측정이 1차 자 thumb.frame0 에 들어가므로 1차 자보다 먼저)
    if want("썸네일"):
        def ts():
            ok, msg = thumb_stamped(final, doc)
            cache["frame0"] = "card" if ok else ("scene" if ok is False else None)
            if legacy:              # 옛 bench_check 그대로: 썸네일.json 없으면 검사 안 함 = 통과
                return ok is not False, msg
            return ok, msg
        _row(rows, "썸네일", "썸네일 맨 앞 2프레임", ts, "썸네일.json · 완성본 0~2프레임")
        if not legacy:
            def trule():
                from tools.calcopy.hybrid import thumb_rule
                sp = doc / "썸네일.json"
                if not sp.exists():
                    return None, "썸네일.json 없음(미측정)"
                bad = thumb_rule.check(jload(sp), n_parts=len(T.get("cuts") or []))
                return not bad, bad or "통과"
            _row(rows, "썸네일", "thumb_rule.check(3안 규칙)", trule, "hybrid/thumb_rule.check")

            def adm():
                from tools.calcopy.engine import ad_mark
                _, _, comment = ad_mark._probe(final)
                return ad_mark.MARK in comment, f"완성본 comment = {comment!r}"
            _row(rows, "썸네일", "광고 표시(ad_mark)", adm, "engine/ad_mark 표식")
    # ── 1차 자
    match = None
    if want("1차 자") and not legacy and bench:
        def m():
            nonlocal match
            from tools.calcopy.engine import kal_analyze as K
            match = K.match_from_render(st, doc, work, media=media, frame0_kind_measured=cache.get("frame0"))
            jsave(doc / "재현일치도.json", match)
            (doc / "재현일치도.md").write_text(K.match_md(match, f"{style_name} {doc.name}"), encoding="utf-8")
            ok, msg, _ = match_verdict(match, bool(st.get("base")))
            if st.get("base"):
                up = getattr(K, "upgrade_table", None)
                match["upgrade"] = up(st, doc, work) if callable(up) else "kal_analyze.upgrade_table 없음(지시서 05 전)"
            return ok, msg
        _row(rows, "1차 자", "재현일치도(match_table)", m, "kal_analyze.match_from_render → 재현일치도.json")
    # ── 장면↔대사
    fit_res = None
    if want("장면↔대사") and not legacy:
        def f():
            nonlocal fit_res
            if not fit:
                return None, "장면↔대사 안 함(--no-fit, 미측정)"
            from tools.calcopy.oneshot import scene_fit
            fit_res = scene_fit.measure_render(work, llm=llm, out=doc / "장면대사.json")
            bf = bench_fit(bench_docs)
            fit_res["bench"] = bf
            jsave(doc / "장면대사.json", fit_res)
            return fit_verdict(fit_res["summary"], bf)
        _row(rows, "장면↔대사", "scene_fit(컷마다 대사↔장면)", f, "oneshot/scene_fit.measure_render → material_auto.fit_judge")
    # ── 표식
    if want("표식") and not legacy:
        def mk():
            try:
                sf = ST.path_of(style_name)
            except SystemExit:
                sf = None
            return marker_verdict(info, sf)
        _row(rows, "표식", "render_info 표식(판 sha·렌더러 sig·reference)", mk, "render_info.json")
    if legacy:                      # 옛 bench_check 줄 순서 그대로(자동검사.json 대조 호환)
        rows.sort(key=lambda r: LEGACY10.index(r["what"]))
    ok = all(r["ok"] is True for r in rows)
    rep = {"style": style_name, "ok": ok, "gate": GATE_VERSION, "mode": "legacy10" if legacy else (list(only) if only else "full"),
           "rows": [{"group": r["group"], "what": r["what"], "ok": r["ok"], "value": r["value"], "src": r["src"]} for r in rows],
           "n": len(rows), "n_ok": sum(r["ok"] is True for r in rows), "n_bad": sum(r["ok"] is False for r in rows), "n_unmeasured": sum(r["ok"] is None for r in rows),
           "placement": tab.get("check"), "log": tab.get("log"),
           "match": {"verdict": match["verdict"], "file": str(doc / "재현일치도.json")} if match else None,
           "fit": {"summary": fit_res["summary"], "bench": fit_res.get("bench"), "file": str(doc / "장면대사.json")} if fit_res else None}
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
        log(f"  {'○' if r['ok'] is True else '×' if r['ok'] is False else '미측정'} [{r['group']}] {r['what']}: {r['value']}")
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
        fit_by[(r["cut"]["t0"], r["cut"]["t1"])] = r
    C = ["# 줄↔컷 대조표 (컷마다: 시각 · 줄 · 그 순간 자막 · 화면 설명(재료) · 장면↔대사 점수)", "",
         "| # | 시각 | 줄 | 자막 | 화면(소스@초 · 설명) | fit | 판정(E3) |", "|---|---|---|---|---|---|---|"]
    rows = tab.get("rows") or []
    for k, c in enumerate(T.get("cuts") or []):
        cap = " / ".join(r.get("text") or "" for r in rows if float(r["t0"]) < float(c["t1"]) and float(r["t1"]) > float(c["t0"]))
        fr = fit_by.get((c["t0"], c["t1"]))
        C.append(f"| {k} | {c['t0']:.2f}–{c['t1']:.2f} | {c.get('line')} | {cap} | {Path(str(c['src'])).stem}@{c.get('ss')} {c.get('see', '')} | "
                 f"{fr.get('score') if fr else '-'} |  |")
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
    a = ap.parse_args(argv)
    r = gate(a.style, Path(a.doc), Path(a.work), eye_pack=not a.no_eye, fit=not a.no_fit, asr=not a.no_asr, media=not a.no_media,
             only="legacy10" if a.legacy10 else None)
    print(f"판정 {'통과' if r['ok'] else '미달'} → {r['report']}")
    if r.get("match"):
        print(f"재현일치도 {r['match']['verdict']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
