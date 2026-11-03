# -*- coding: utf-8 -*-
"""여러 편 묶음 글꼴 판별 — 같은 하위 스타일(같은 채널·같은 역할)의 제목(또는 브랜드) 줄을 전부 모아 글꼴 하나로 정한다.

    PYTHONUTF8=1 py tools/calcopy/engine/font_pool.py <뜯기 폴더> [<뜯기 폴더> …] [--role title|brand] [--grid out.png] [--write]

  <뜯기 폴더>  analyze.py 결과 폴더(뜯기.json + captions/<role><k>.png). 같은 하위 스타일 편만 넣는다(묶음은 부르는 쪽이 고른다)
  --write      각 뜯기.json 의 fonts.<role>_pooled 에 묶음 결과를 적는다(편 단위 fonts.<role> 는 참고로 남긴다)
  --grid       묶음 1위~3위로 첫 줄을 그린 대조 그림(맨 위 원본)

판단은 fontmatch.pooled_rank 한 곳 — 여기는 줄 크롭·글자를 모으고 결과를 적기만 한다.
(2026-10-16 썰풀다 ho5·7DY·1_V 제목: 편 단위로 Cafe24Ohsquare / yg-jalnan 으로 갈렸다)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from tools.calcopy.engine import fontmatch  # noqa: E402


def collect(dirs: list[Path], role: str) -> tuple[list, list[dict]]:
    """[(줄 마스크, 글자)], [{dir, band, n_lines, skipped?}]"""
    samples, log = [], []
    for d in dirs:
        R = json.loads((d / "뜯기.json").read_text(encoding="utf-8"))
        for b in ((R.get("fonts") or {}).get("title_bands") or {}).get("bands", []):
            if b.get("role") != role:
                continue
            png = d / "captions" / f"{role}{b['k']}.png"
            lines = [str(x) for x in (b.get("text") or []) if str(x).strip()]
            if not png.exists() or not lines:
                log.append({"dir": d.name, "band": b["band"], "skipped": "크롭 또는 글자 없음"})
                continue
            masks = fontmatch.line_masks(np.array(Image.open(png).convert("RGB")), b["ink"])
            if len(masks) != len(lines):
                log.append({"dir": d.name, "band": b["band"], "skipped": f"글자 줄 {len(lines)} ≠ 잉크 줄 {len(masks)}"})
                continue
            samples += list(zip(masks, lines))
            log.append({"dir": d.name, "band": b["band"], "n_lines": len(lines)})
    return samples, log


def main() -> None:
    ap = argparse.ArgumentParser(description="여러 편 묶음 글꼴 판별")
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--role", default="title", choices=["title", "brand"])
    ap.add_argument("--grid")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dirs = [Path(x) for x in a.dirs]
    samples, log = collect(dirs, a.role)
    res = fontmatch.pooled_rank(samples) if samples else {"failed": "모을 줄 없음", "top": [], "n": 0}
    res["group"] = [d.name for d in dirs]
    res["lines"] = log
    print(json.dumps({k: v for k, v in res.items() if k != "lines"}, ensure_ascii=False, indent=1))
    for x in log:
        print(" ", x)
    if a.grid and samples and res.get("top"):
        m, t = samples[0]
        fontmatch.grid(m, t, res["top"][:3], a.grid)
        print("그림:", a.grid)
    if a.write:
        for d in dirs:
            jf = d / "뜯기.json"
            R = json.loads(jf.read_text(encoding="utf-8"))
            R.setdefault("fonts", {})[f"{a.role}_pooled"] = res
            jf.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
        print("적음:", len(dirs), "편")


if __name__ == "__main__":
    main()
