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

LUFS_TOL, PEAK_MAX, LEN_TOL, CUT_TOL = 0.5, -0.5, 0.15, 0.30
CUT_MIN, END_MIN, CAP_MAX, SYNC_TOL = 1.2, 1.5, 13, 0.04


def check(doc: Path, work: Path, stage: str = "render") -> dict:
    R = work / stage
    info = jload(R / "render_info.json")
    S = jload(doc / "대본.json")
    target = (S.get("render") or {}).get("target_lufs", -9.0)
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
    last = [c for c in cuts if c["line"] == cuts[-1]["line"]]   # 마지막 묶음(끝 줄) — 매뉴얼 B4: 컷 ≥1.2·끝 컷 ≥1.5
    row("B4", "컷 중앙(벤치 ±30%)·끝 묶음 ≥1.2·끝 컷 ≥1.5",
        f"중앙 {med:.2f}(벤치 {bm}) · 끝 묶음 {[c['dur'] for c in last]} · 전체 최단 {ds[0]:.2f} · 1.2초 미만 {[(c['i'], c['dur']) for c in cuts if c['dur'] < CUT_MIN]}",
        all(c["dur"] >= CUT_MIN - 1e-6 for c in last) and cuts[-1]["dur"] >= END_MIN and (not bm or 1 - CUT_TOL <= med / bm <= 1 + CUT_TOL),
        (f"×{med / bm:.2f}" if bm else "") + " · 원음 컷은 재료 시각 그대로라 짧을 수 있음 — 컷표 참고")
    b13 = reuse_violations([{**c, "src": c["src"]} for c in cuts])
    row("B13", "같은 장면 ±3초 재사용", b13 or "0", not b13)
    capmax = max(nchar(c["text"]) for c in info["captions"])
    row("A9", f"자막 조각 ≤{CAP_MAX}자", capmax, capmax <= CAP_MAX)
    off = [(c["i"], c["line"], c["sync"]) for c in cuts if abs(c.get("sync", 0)) > SYNC_TOL]
    row("SYNC", "원음 컷 화면↔소리 시각(화면초−소리초)", off or "0", not off, "재료 시각 그대로 — 어긋남은 재료(편 담당) 쪽")
    if has_video:
        from tools.calcopy.engine import check_seams
        from tools.calcopy.engine.remake import sheet_1s
        fr = jload(R / "frame.json")
        v = next(l for l in fr["layers"] if l["kind"] == "video")
        seams = check_seams.check(str(final), (v["x"], v["y"], v["w"], v["h"]), None)
        jsave(R / "seams.json", seams)
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
    a = ap.parse_args()
    check(Path(a.doc).resolve(), Path(a.work).resolve(), a.stage)


if __name__ == "__main__":
    main()
