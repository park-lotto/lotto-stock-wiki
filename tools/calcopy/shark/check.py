# -*- coding: utf-8 -*-
"""샥탬스토리 렌더 결과물 검사 → B표 초안 (관제 097, 2026-10-18). 숫자는 render.py 가 남긴 render_info.json 만 읽는다(다시 계산 안 함).

    PYTHONUTF8=1 py tools/calcopy/shark/check.py <편 doc 폴더> <작업 폴더> [--stage plan|preview|render]

재는 것(검수_매뉴얼.md B 항목):
  B1 길이 벤치 ±15% · B2 LUFS 목표(−9.0)±0.5·최고점 ≤ −0.5 dBFS(ebur128 true peak) · B4 컷 중앙 벤치 ±30%(빠르면 반려 쪽)·컷 ≥1.2·끝 컷 ≥1.5
  B13 같은 소스 겹침·±3초 재사용(hybrid.checks.reuse_violations 그대로) · B16' 되감김·점프줌(engine/check_seams) · A9 자막 ≤13자
  화면↔소리 시각(원음 컷의 화면초 − 소리초, |>0.04|) · 원음 창 나레 없음(나레 파일이 원음 창 안에서 무음인지) · 1초 시트(engine/remake.sheet_1s)
plan 단계는 영상 없이 B1(추정)·B4·B13·A9·시각 어긋남만.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid.common import dur_of, jload, jsave, lufs, md5, nchar, silences  # noqa: E402
from tools.calcopy.hybrid.checks import reuse_violations  # noqa: E402
from tools.calcopy.shark.caption_style import rules  # noqa: E402

LEN_TOL, CUT_TOL = 0.15, 0.30
LOUD = rules()["loudness"]   # B2 목표·트루피크 = rules.json loudness 한 곳(R5 −14 LUFS·≤ −1.5 dBTP) — 렌더·하이브리드와 같은 값
LUFS_TOL, PEAK_MAX = LOUD["check_tol"], LOUD["true_peak_max"]
CUT_MIN, END_MIN, CAP_MAX, SYNC_TOL = 1.2, 1.5, 13, 0.04


EN_ASR_PROMPT = ('Transcribe the spoken English exactly as heard. Write the English words — do NOT translate or transliterate into '
                 'Korean. Skip music and sound effects. Count the speakers. Empty text if there is no speech.\n'
                 'JSON only: {"text":"","speakers":1}')
EN_MATCH_MIN = 0.5   # 대본 원문 낱말 중 받아쓰기(두 모델 중 나은 쪽)에 나온 비율 — 6편 영어 재받아쓰기 6줄 실측으로 정함


def _words(t: str) -> list[str]:
    import re
    t = re.sub(r"(?<=\d),(?=\d)", "", (t or "").lower()).replace("%", " percent")
    return [w for w in re.findall(r"[a-z0-9']+", t) if w not in ("the", "a", "an", "uh", "um")]


def orig_match(ow: list[dict], res: dict) -> list[dict]:
    """(판단 주인: 원음 들림) 원음 줄마다 대본 영어(en) 낱말 중 받아쓰기에 나온 비율(모델별 최고) · 한국어 섞임."""
    import re
    out = []
    for i, x in enumerate(ow):
        want = _words(x.get("en"))
        heard = [c.get("text", "") for r in res.get("runs") or [] for c in r.get("clips") or [] if c.get("i") == i]
        best = max((sum(1 for w in want if w in set(_words(h))) / max(1, len(want)) for h in heard), default=0.0)
        ko = any(re.search(r"[가-힣]", h) for h in heard)
        out.append({"id": x["id"], "recall": round(best, 2), "ko": ko, "heard": heard, "ok": best >= EN_MATCH_MIN and not ko})
    return out


SCENE_TH = 0.3   # 벤치 QMJ 를 이 자로 재면 컷 중앙 1.27(프리셋 cut_sec_median_ref 와 같음) — th 0.4 면 1.47 로 벤치 값이 안 나온다(10-18 실측)


def scene_cuts(mp4: Path, win) -> list[float]:
    """완성본 창만(1/4) ffmpeg scene 점수 > SCENE_TH 인 프레임 시각 = 장면 바뀜(B4 의 자 — 벤치 1.27 과 같은 방법)."""
    import re
    import subprocess
    x, y, w, h = win
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-vf", f"crop={w}:{h}:{x}:{y},scale={w // 4}:{h // 4},select='gt(scene,{SCENE_TH})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [float(t) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def forward_runs(cuts: list[dict], gap_max: float = 3.0) -> list[dict]:
    """B13 앞처리: 화면에서 바로 이어지는(t1≈다음 t0) 같은 소스 컷이 원본에서 앞으로만 가면(겹침 0·틈 ≤ gap_max초) 한 컷으로 묶는다.
    방송 편집을 그대로 따라 이어 읽은 원음 줄들(2편 L1~L2·L6~L9)을 '±3초 재사용'으로 잡던 오탐 수리 — 되돌아가거나 겹치면 묶지 않아 여전히 잡힌다."""
    out = []
    for c in sorted(cuts, key=lambda c: c["t0"]):
        c = {**c, "ss": float(c["ss"]), "dur": float(c["dur"])}
        p = out[-1] if out else None
        if p and p["src"] == c["src"] and abs(float(p["t1"]) - float(c["t0"])) < 0.06:
            end = p["ss"] + p["dur"]
            if end - 0.05 <= c["ss"] <= end + gap_max:
                p["dur"] = round(c["ss"] + c["dur"] - p["ss"], 3); p["t1"] = c["t1"]
                p["line"] = f"{str(p['line']).split('~')[0]}~{c['line']}"
                continue
        out.append(c)
    return out


def check(doc: Path, work: Path, stage: str = "render", asr: bool = False) -> dict:
    R = work / stage
    info = jload(R / "render_info.json")
    S = jload(doc / "대본.json")
    target = (S.get("render") or {}).get("target_lufs", LOUD["target_lufs"])
    cuts = [c for c in info["cuts"] if not c.get("dropped")]
    ds = sorted(c["dur"] for c in cuts)
    med = ds[len(ds) // 2]
    rows = []

    def row(k, name, value, ok, why=""):
        rows.append({"k": k, "name": name, "value": value, "ok": bool(ok), "why": why})
    final = R / "final.mp4"
    has_video = stage != "plan" and final.exists()
    dur = dur_of(final) if has_video else info["dur"]
    bd = info.get("bench_dur")
    row("B1", "길이" + ("" if has_video else "(추정)"), f"{dur:.2f}초 vs 벤치 {bd}", (not bd) or abs(dur / bd - 1) <= LEN_TOL,
        f"{(dur / bd - 1) * 100:+.1f}%" if bd else "벤치 길이 없음")
    if has_video:
        I, pk = lufs(final)
        row("B2", "LUFS·최고점", f"{I} LUFS · {pk} dBFS (목표 {target})", abs(I - target) <= LUFS_TOL and pk <= PEAK_MAX)
    bm = info.get("bench_cut_median")
    seams = None
    if has_video:   # B4 는 벤치 컷 중앙(1.27, 완성본 장면 검출로 잰 값)과 같은 자 = 완성본 장면 검출(check_seams 컷)로 잰다 — 원음 컷 안 방송 편집 경계까지 센다(5편 25컷 1.73 vs 장면 31조각 1.30)
        from tools.calcopy.engine import check_seams
        fr = jload(R / "frame.json")
        v = next(l for l in fr["layers"] if l["kind"] == "video")
        seams = check_seams.check(str(final), (v["x"], v["y"], v["w"], v["h"]), None)
        jsave(R / "seams.json", seams)
        b = [0.0] + scene_cuts(final, (v["x"], v["y"], v["w"], v["h"])) + [dur]
        sd = sorted(y - x for x, y in zip(b, b[1:]) if y - x > 0.05)
        med = sd[len(sd) // 2]
    last = [c for c in cuts if c["line"] == cuts[-1]["line"]]   # 마지막 묶음(끝 줄) — 매뉴얼 B4: 컷 ≥1.2·끝 컷 ≥1.5
    row("B4", "컷 중앙(벤치 ±30%)·끝 묶음 ≥1.2·끝 컷 ≥1.5",
        f"중앙 {med:.2f}({f'완성본 장면 검출 scene>{SCENE_TH} {len(sd)}조각' if seams else '컷표'}·벤치 {bm}) · 끝 묶음 {[c['dur'] for c in last]} · 전체 최단 {ds[0]:.2f} · 1.2초 미만 {[(c['i'], c['dur']) for c in cuts if c['dur'] < CUT_MIN]}",
        all(c["dur"] >= CUT_MIN - 1e-6 for c in last) and cuts[-1]["dur"] >= END_MIN and (not bm or 1 - CUT_TOL <= med / bm <= 1 + CUT_TOL),
        (f"×{med / bm:.2f}" if bm else "") + " · 원음 컷은 재료 시각 그대로라 짧을 수 있음 — 컷표 참고")
    from tools.calcopy.shark.caption_style import rules as _rules
    tmax = _rules()["title"]["line_chars_max"]
    _T = S.get("titles") or {}
    tl = [x for x in (_T.get("hook") or "\n".join(x for x in (_T.get("line1"), _T.get("line2")) if x)).split("\n") if x]
    row("TITLE", f"제목 줄당 글자 ≤{tmax}(공백 포함 — 넘으면 글자가 벤치 100~135px 보다 작아짐)", [(t, len(t)) for t in tl], all(len(t) <= tmax for t in tl),
        "규칙 shark/rules.json title.line_chars_max(벤치 8편 긴 줄 12자=100.5px)")
    b13 = reuse_violations(forward_runs(cuts))
    row("B13", "같은 장면 ±3초 재사용", b13 or "0", not b13)
    capmax = max(nchar(c["text"]) for c in info["captions"])
    row("A9", f"자막 조각 ≤{CAP_MAX}자", capmax, capmax <= CAP_MAX)
    off = [(c["i"], c["line"], c["sync"]) for c in cuts if abs(c.get("sync", 0)) > SYNC_TOL]
    row("SYNC", "원음 컷 화면↔소리 시각(화면초−소리초)", off or "0", not off, "재료 시각 그대로 — 어긋남은 재료(편 담당) 쪽")
    if has_video:
        from tools.calcopy.engine.remake import sheet_1s
        row("B16'", "되감김·점프줌(check_seams)", f"컷 {len(seams['컷'])} · 되감김 {len(seams['되감김'])} · 점프줌 {len(seams['점프줌'])}({seams['점프줌_판정'] or '드묾'})",
            seams["ok"])
        nar = Path(info["narr_placed"])
        sil = silences(nar, "-45dB", 0.05)
        bad = []
        for x in info["lines"]:
            if x["kind"] != "O":
                continue
            a, b = x["speak"][0] + 0.05, x["speak"][1] - 0.05
            covered = sum(max(0.0, min(e, b) - max(s, a)) for s, e in sil)
            if covered < (b - a) - 0.05:
                bad.append(f"{x['id']} 무음 {covered:.2f}/{b - a:.2f}초")
        row("O-NARR", "원음 창 안 나레 없음", bad or "0", not bad)
        if asr:   # 완성본 원음 창만 잘라 서버 제미나이 2모델 단독 받아쓰기(영어 요청문) — 대본 영어 원문과 낱말 일치율
            from tools.calcopy.hybrid import server_ai
            ow = [x for x in info["lines"] if x["kind"] == "O"]
            spans = [list(x["speak"]) for x in ow]
            cache = R / "asr_orig_en.json"
            res = jload(cache) if cache.exists() and jload(cache).get("spans") == spans else None
            if res is None:
                res = server_ai.asr_clips(final, [tuple(s_) for s_ in spans], prompt=EN_ASR_PROMPT)
                res["spans"] = spans
                jsave(cache, res)
            m = orig_match(ow, res)
            bad = [f"{x['id']} {x['recall']:.0%}" + (" 한국어" if x["ko"] else "") for x in m if not x["ok"]]
            row("ASR", f"원음 창 영어 받아쓰기(2모델) ↔ 대본 영어 원문 낱말 일치 ≥{EN_MATCH_MIN:.0%}",
                f"모델 {res.get('ok_models')} · " + " · ".join(f"{x['id']} {x['recall']:.0%}" for x in m),
                len(res.get("ok_models") or []) >= 2 and not bad, f"{cache}" + (f" · 미달 {bad}" if bad else ""))
        sheet = R / "final_sheet_1s.jpg"
        sheet_1s(final, sheet)
    L = [f"# 샥탬스토리 B표 초안 — {doc.name} · {stage} (tools/calcopy/shark/check.py)", "",
         (f"완성본 `{final}` · MD5 `{md5(final)}` · " if has_video else "영상 없음(계획) · ") + f"{dur:.2f}초 · 컷표 `{R / '컷표.md'}`", "",
         "| # | 항목 | 값 | ○/× | 비고 |", "|---|---|---|---|---|",
         *[f"| {r['k']} | {r['name']} | {r['value']} | {'○' if r['ok'] else '×'} | {r['why']} |" for r in rows], "",
         "사람이 볼 것: 1초 시트로 줄↔장면 · 남의 글자(크롭) · 자막 잔존 · 꾸밈(못 그림 목록: render_info.fx_not_drawn)", ""]
    (R / "B표_draft.md").write_text("\n".join(L), encoding="utf-8")
    res = {"stage": stage, "ok_auto": all(r["ok"] for r in rows), "rows": rows, "dur": dur, "cut_median": med}
    jsave(R / "checks.json", res)
    print(f"[check {stage}] " + " ".join(f"{r['k']}{'○' if r['ok'] else '×'}" for r in rows) + f" → {R / 'B표_draft.md'}")
    for r in rows:
        if not r["ok"]:
            print(f"   × {r['k']} {r['value']}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--stage", default="render", choices=["plan", "preview", "render"])
    ap.add_argument("--asr", action="store_true")
    a = ap.parse_args()
    check(Path(a.doc).resolve(), Path(a.work).resolve(), a.stage, a.asr)


if __name__ == "__main__":
    main()
