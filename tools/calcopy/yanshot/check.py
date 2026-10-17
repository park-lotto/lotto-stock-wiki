# -*- coding: utf-8 -*-
"""⑥ 검수 — 판단 주인: check(B, T, S, P, R, W, slug) (관제 097, 2026-10-17).

검수 매뉴얼(tools/calcopy/검수_매뉴얼.md) B표를 같은 자로 잰다 — 벤치와 우리를 bench_one.measure 하나로(길이·LUFS·컷 중앙),
이음매는 check_seams.check(틀 frame.json 창·자막 띠), 원음은 완성본 원음 창만 잘라 받아쓰기 1회(B17).
통과 → C:/Users/CH/Desktop/칼카피영상/얜샷템/칼카피_얜샷템_<소재>.mp4 (MD5 같게). 실패 → B표.md 에 이유 남기고 StageError(조용한 실패 금지).
"""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from tools.calcopy.yanshot.common import GEM_MODELS, StageError, dur_of, jload, jsave, lufs_of, md5, run

OUT_DIR = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템")     # 10-17 지휘: 바탕화면 바로 아래 금지, 채널 폴더로
CPS, CPS_TOL = 8.4, 0.05
LEN_TOL, LUFS_TOL, PEAK_MAX = 0.15, 1.5, -0.5
CUT_FAST, CUT_SLOW = 0.90, 1.30          # B4: 벤치 컷 중앙 대비(빠르면 반려 쪽)
Y_MIN = 60
ASR_COVER = 0.55


def _ymean(mp4, t: float, win) -> float:
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf",
                        f"crop={win[2]}:{win[3]}:{win[0]}:{win[1]},scale=270:-2,format=gray", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True).stdout
    return float(np.asarray(Image.open(io.BytesIO(b))).mean()) if b else 0.0


def orig_asr(final, win: list, ask=None) -> dict:
    """완성본 원음 창만 잘라 받아쓰기 1회(B17·B8) — 창마다 클립, 한 요청."""
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    parts = []
    tmp = Path(final).parent / "asr_check"
    tmp.mkdir(exist_ok=True)
    for k, (a, b) in enumerate(win):
        mp3 = tmp / f"win{k}.mp3"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(final), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(mp3)])
        parts += [f"클립 {k}:", (mp3.read_bytes(), "audio/mp3")]
    d, why = ask(parts, '클립마다 한국어 말소리를 들리는 그대로 받아써라(배경음악 빼고). JSON만: {"clips":[{"i":0,"text":""}]}',
                 tag="yanshot_check_asr", models=GEM_MODELS)
    if d is None:
        raise StageError(f"완성본 원음 받아쓰기 실패: {why}")
    return {"texts": [c.get("text", "") for c in (d.get("clips") or d.get("items") or [])], "model": d.get("_model")}


def check(B: dict, T: dict, S: dict, P: dict, R: dict, W: Path, slug: str, ask=None, log=print) -> dict:
    from tools.calcopy.engine import bench_one, check_seams
    from tools.calcopy.yanshot.bench import sheet
    from tools.calcopy.yanshot.plan import visual_cuts, median
    from tools.calcopy.yanshot.trace import coverage
    W = Path(W)
    doc = W / "doc"
    final = Path(R["final"])
    P = jload(W / "plan.json")                        # make 가 TTS 실측으로 다시 맞춘 계획
    sheet(final, doc / "final_sheet_1s.jpg")
    fr = str(doc / "frame.json")
    win_v, mask = check_seams.from_frame(fr)
    seams = check_seams.check(str(final), win_v, mask)
    jsave(W / "render" / "seams.json", seams)
    mo = bench_one.measure(str(final))
    bm = B.get("measure") or {}
    lf = lufs_of(final)
    dur = dur_of(final)
    tts = R["tts"]
    rows = []

    def row(k, name, bench, ours, ok, why=""):
        rows.append({"k": k, "name": name, "bench": bench, "ours": ours, "ok": ok, "why": why})

    row("B1", "길이 ±15%", B["dur"], round(dur, 2), abs(dur / B["dur"] - 1) <= LEN_TOL, f"{(dur / B['dur'] - 1) * 100:+.1f}%")
    lb = bm.get("lufs")
    row("B2", "LUFS ±1.5 · 최고점 ≤−0.5", lb, f"{lf['I']} · 피크 {lf['peak']}", lb is not None and abs(lf["I"] - lb) <= LUFS_TOL and (lf["peak"] or 0) <= PEAK_MAX)
    cps = tts["cps"]
    row("B3", "말속도 8.4자/초 ±5%(줄별)", CPS, cps, all(abs(c / CPS - 1) <= CPS_TOL for c in cps))
    bmed, omed = bm.get("shot_median"), (mo.get("cuts") or {}).get("shot_median")
    row("B4", "컷 중앙(벤치 ×0.9~1.3, 빠르면 반려)", bmed, f"{omed} (계획 보이는 컷 {P.get('visual_cut_median')})",
        bool(bmed and omed and CUT_FAST <= omed / bmed <= CUT_SLOW), f"{omed / bmed:.2f}배" if bmed and omed else "못 잼")
    y0, y1 = _ymean(final, 0.3, win_v), _ymean(final, dur - 0.3, win_v)
    row("B9", "첫·끝 컷 Y≥60", "", f"{y0:.0f} · {y1:.0f}", y0 >= Y_MIN and y1 >= Y_MIN)
    b13 = [v for v in P["violations"] if v.startswith("B13")]
    row("B13", "같은 장면 ±3초 재사용 0", "", b13 or "0", not b13)
    aba = [v for v in P["violations"] if v.startswith("A-B-A") or v.startswith("되감김")]
    row("B16", "되감김·A-B-A·점프 줌(check_seams)", "", f"되감김 {len(seams['되감김'])} · 점프줌 {len(seams['점프줌'])}({seams['점프줌_판정'] or '드묾'}) · 계획 {aba or '0'}",
        seams["ok"] and not aba)
    win = R["windows"]
    said = [b["orig"]["said"] for b in P["blocks"] if b["kind"] == "원음"]
    heard = orig_asr(final, win, ask=ask)
    cov = round(coverage(" ".join(said), " ".join(heard["texts"])), 2)
    row("B17", "원음 단독 받아쓰기 = 본인 말", " / ".join(said), " / ".join(heard["texts"]) + f" ({heard['model']})", cov >= ASR_COVER, f"덮음 {cov}")
    tp = tts["atempo"]
    mean = sum(tp) / len(tp)
    long = [l["chars"] for l in S["lines"] if l["chars"] > 35]
    row("B17'", "TTS 35자↓ · 줄별 배속 ±10%", "", f"줄 {[l['chars'] for l in S['lines']]}자 · atempo {tp}", not long and all(abs(x / mean - 1) <= 0.1 + 1e-6 for x in tp))
    capbad = [c["text"] for c in P["captions"] if len(c["text"].replace(" ", "")) > 15]
    row("A9", "자막 조각 ≤13자(원음 낱말 하나 넘침 허용 15)", "", capbad or "0", not capbad)
    cc = P.get("crop_checks") or []
    row("A5·A13", "크롭 검사(덧씌운 글자 0 · 주인공/제품 보임)", "", f"{len(cc)}회 · 마지막 걸림 {cc[-1]['bad'] if cc else '?'}", bool(cc) and not cc[-1]["bad"])
    ok = all(r["ok"] for r in rows)
    dest = OUT_DIR / f"칼카피_얜샷템_{slug}.mp4"
    md = None
    if ok:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, dest)
        md = md5(final)
        if md5(dest) != md:
            raise StageError("완성본 복사 MD5 불일치")
    lines = [f"# B표 — 얜샷템 {B.get('person')} {B.get('product')} (벤치 {B['id']} {B.get('channel')}, 원본 {T['source']['id']})", "",
             f"완성본 `{final}` · {'복사 `' + str(dest) + '` MD5 `' + md + '`(같음)' if ok else '**통과 못 함 — 복사 안 함**'}",
             f"1초 시트 `{doc / 'final_sheet_1s.jpg'}` · TTS 미나 1회 → atempo {tp}", "",
             "| # | 항목 | 벤치 | 우리 | ○/× | 근거 |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['k']} | {r['name']} | {r['bench']} | {r['ours']} | {'○' if r['ok'] else '×'} | {r['why']} |" for r in rows]
    lines += ["", "B7(자막 잔존)·A3(줄↔장면)은 1초 시트·계획 시트를 눈으로 본다 — 도구 판정 아님."]
    (doc / "B표.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = {"ok": ok, "rows": rows, "dest": str(dest) if ok else None, "md5": md, "seams": {"ok": seams["ok"], "되감김": len(seams["되감김"]), "점프줌": len(seams["점프줌"])},
           "ours_measure": {"shot_median": omed, "lufs": lf, "dur": dur}}
    jsave(W / "check.json", res)
    log(f"[check] {'통과' if ok else '걸림'}: " + " · ".join(f"{r['k']}{'○' if r['ok'] else '×'}" for r in rows))
    if not ok:
        raise StageError("B표 걸림 — " + "; ".join(f"{r['k']} {r['ours']} {r['why']}" for r in rows if not r["ok"]) + f" (B표 {doc / 'B표.md'})")
    return res
