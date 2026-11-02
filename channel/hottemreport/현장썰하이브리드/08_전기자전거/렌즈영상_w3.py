# -*- coding: utf-8 -*-
"""08 워커3 — 사진 → 렌즈 결과 중 영상 사이트(틱톡·유튜브·인스타)만(lens.lens_rows SKIP_VIDEO, 프로필 .lens_profile_w3).
    PYTHONUTF8=1 py 렌즈영상_w3.py <out.json> <hl> <사진…>"""
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import tools.calcopy.lens as L  # noqa: E402
L.PROFILE = str(ROOT / ".lens_profile_w3")
out, hl, imgs = sys.argv[1], sys.argv[2], sys.argv[3:]
res = {}
with L.lens_page() as pg:
    for img in imgs:
        rows = L.lens_rows(pg, img, skip=L.SKIP_VIDEO, hl=hl)
        res[img] = rows
        for r in rows:
            if re.search(r"tiktok|youtube|instagram|facebook|douyin", r["shop"]):
                print(Path(img).name, r["href"][:100], "|", r["text"][:70])
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
