# -*- coding: utf-8 -*-
"""벤치 판(renderer=bench) 렌더 뒤 자동 검사 — 판 설정의 길이·음량·창 + 배치 대조 + 0초 얼굴 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/bench_check.py <판> <doc_dir> <work_dir>

잰다: ① 길이 = 판 설정 length 안 · 완성본 화면 = 시간표 끝 ±1프레임 ② 음량 = loudness.lufs ±0.5, 최고점 ≤ tp+0.5
③ 0초·첫 줄 구간 연예인 얼굴(thumb.face_check, 창 = frame.window) ④ 배치 = placement.check_place(본보기 벤치 편과 칸별 등장·강조 비율)
결과 = <doc>/자동검사.json. 벤치와 나란히 보는 시트는 compare_sheet.py(눈 확인용).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FPS, jload, jsave, lufs, run  # noqa: E402


def vdur(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", p]).stdout.strip() or 0)


def check(style_name: str, doc: Path, work: Path, log=print) -> dict:
    from tools.calcopy.hybrid import styles as ST, thumb
    st = ST.load(style_name)
    R = Path(work) / "render"
    final = R / "final.mp4"
    T = jload(R / "timeline.json")
    tab = jload(R / "자막표.json")
    d = vdur(final)
    I, tp = lufs(final)
    L, LD = st["loudness"], st["length"]
    x, y, w, h = st["frame"]["window"]
    first = T["lines"][next(iter(T["lines"]))]
    face = thumb.face_check(final, (x, y, w, h), tuple(first), log=log)
    rows = [("길이", LD["min"] - 0.5 <= d <= LD["max"] + 0.5, f"{d:.2f}초 (판 {LD['min']}~{LD['max']})"),
            ("화면=시간표", abs(d - T["end"]) <= 1 / FPS + 0.01, f"{d:.3f} vs {T['end']}"),
            ("음량", abs(I - L["lufs"]) <= 0.5, f"{I} LUFS (목표 {L['lufs']})"),
            ("최고점", tp <= L["tp"] + 0.5, f"{tp} dBFS (≤ {L['tp']}+0.5)"),
            ("0초·첫 줄 얼굴", face["ok"], " ".join(f"{f['t']}s:{'○' if f['ok'] else f['why']}" for f in face["frames"])),
            ("배치(본보기 벤치 편 대조)", tab["check"]["ok"], f"본보기 {tab['check']['reference']} · 칸 최대 차 {tab['check']['worst_slot_diff']}")]
    ok = all(r[1] for r in rows)
    rep = {"style": style_name, "ok": ok, "rows": [{"what": a, "ok": b, "value": c} for a, b, c in rows], "placement": tab["check"], "log": tab.get("log")}
    jsave(Path(doc) / "자동검사.json", rep)
    for a, b, c in rows:
        log(f"  {'○' if b else '×'} {a}: {c}")
    return {"ok": ok, "report": str(Path(doc) / "자동검사.json")}


if __name__ == "__main__":
    r = check(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
    sys.exit(0 if r["ok"] else 1)
