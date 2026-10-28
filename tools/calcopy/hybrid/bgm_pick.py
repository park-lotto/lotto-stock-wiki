# -*- coding: utf-8 -*-
"""배경음 곡 **추천만** — 벤치 소리의 템포·밝기 ↔ 우리 곡 창고(shopping_shorts/assets/bgm_lib) 거리 상위 N (관제 263 지시서 02, 표준 §3-3 A4).

    PYTHONUTF8=1 py tools/calcopy/hybrid/bgm_pick.py recommend <판 이름 | 벤치 영상·소리 폴더 | 파일> [--top 3] [--json 출력]

신호 = engine/sound/bgm_fp(같은 자): tempo(스펙트럴 플럭스 자기상관 BPM, 'all' 대역) · bright(스펙트럼 무게중심 Hz) · 크로마 코사인(best_match).
벤치 소리에는 나레·원음이 섞여 있다 — 템포·밝기·화성은 '분위기 가까움'일 뿐 곡 식별이 아니다(벤치 곡 식별 불가, 표준 §3-3 A4).
★판 `bgm.id` 는 사람이 적는다. 이 도구는 후보만 낸다(판 칸 `bgm.candidates` 에 옮겨 적는 것은 판 담당 — 지시서 07).

거리 = |log2(템포 비)| / 0.5 + |log2(밝기 비)| / 1.0 + (1 − 크로마 코사인)   — 템포 반 옥타브(×1.41)·밝기 한 옥타브(×2)·화성 반대가 같은 무게.
템포는 반·두 배 혼동(자기상관 배수)을 갚는다: 비를 [0.5, 2] 배 셋 중 가장 가까운 것으로.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/calcopy/engine/sound"))

BGM_DIR = ROOT / "shopping_shorts/assets/bgm_lib"
MEDIA = (".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".wav")
W_TEMPO, W_BRIGHT = 0.5, 1.0


def _fp():
    import bgm_fp      # engine/sound/bgm_fp.py — 신호 주인
    return bgm_fp


def signal(path: Path) -> dict:
    """한 소리(영상이면 소리만)의 템포·밝기·크로마 평균."""
    fp = _fp()
    p = Path(path)
    if p.suffix.lower() not in (".wav", ".mp3"):
        with tempfile.TemporaryDirectory() as td:
            w = Path(td) / "a.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", str(fp.SR), str(w)], check=True,
                           stdin=subprocess.DEVNULL)
            x = fp.F.load(str(w))
    else:
        x = fp.F.load(str(p))
    t = fp.tempo(x)
    return {"tempo": t["all"], "tempo_ac": t["all_ac"], "bright": fp.bright(x), "chroma": fp.chroma_seq(x)}


def _tempo_dist(a: float, b: float) -> float:
    return min(abs(math.log2(a * k / b)) for k in (0.5, 1.0, 2.0))


def library() -> dict:
    return {p.stem: p for p in sorted(BGM_DIR.glob("*.mp3"))}


def bench_files(target: str) -> list[Path]:
    p = Path(target)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.suffix.lower() in MEDIA)
    from tools.calcopy.hybrid import styles as ST          # 판 이름 → 판 칸 bench.src_dir
    st = ST.load(target)
    src = (st.get("bench") or {}).get("src_dir")
    if not src or not Path(src).is_dir():
        raise SystemExit(f"판 {target} 의 bench.src_dir 가 없다({src}) — 벤치 영상 폴더를 직접 줘라")
    return sorted(f for f in Path(src).iterdir() if f.suffix.lower() in (".mp4", ".webm", ".mkv"))


def recommend(target: str, top: int = 3, log=print) -> dict:
    import numpy as np
    fp = _fp()
    files = bench_files(target)
    if not files:
        raise SystemExit(f"벤치 소리가 없다: {target}")
    B = [signal(f) for f in files]
    tempo = float(np.median([b["tempo"] for b in B]))
    bright = float(np.median([b["bright"] for b in B]))
    log(f"벤치 {len(files)}편 템포 중앙 {tempo:.1f} BPM · 밝기 중앙 {bright:.0f} Hz")
    rows = []
    for name, p in library().items():
        L = signal(p)
        chroma = float(np.mean([dict(fp.best_match(b["chroma"], {name: L["chroma"]}))[name] for b in B]))
        d = _tempo_dist(L["tempo"], tempo) / W_TEMPO + abs(math.log2(L["bright"] / bright)) / W_BRIGHT + (1 - chroma)
        rows.append({"id": name, "dist": round(d, 3), "tempo": L["tempo"], "bright": L["bright"], "chroma": round(chroma, 3)})
    rows.sort(key=lambda r: r["dist"])
    return {"made_by": "tools/calcopy/hybrid/bgm_pick.py recommend", "target": target, "n_bench": len(files),
            "bench": {"tempo_med": round(tempo, 1), "bright_med": round(bright), "files": [f.name for f in files]},
            "candidates": rows[:top], "all": rows,
            "note": "추천만 — 판 bgm.id 는 사람이 고른다(나레·원음 섞인 벤치 소리라 곡 식별 아님)"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recommend"); r.add_argument("target"); r.add_argument("--top", type=int, default=3); r.add_argument("--json")
    a = ap.parse_args()
    out = recommend(a.target, a.top)
    for c in out["candidates"]:
        print(f"  {c['id']:24s} 거리 {c['dist']:.3f} · 템포 {c['tempo']} · 밝기 {c['bright']:.0f} · 화성 {c['chroma']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
