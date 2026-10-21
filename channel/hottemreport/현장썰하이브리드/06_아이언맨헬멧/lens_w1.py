# -*- coding: utf-8 -*-
"""06 아이언맨헬멧 — 렌즈를 워커1 전용 프로필(.lens_profile_w1)로 돌린다(공용 lens.py 는 안 고친다, 실행 중에만 PROFILE 바꿈).
    py lens_w1.py shop <이름> <사진…>   → 렌즈쿠팡.main (결과 현장썰하이브리드/렌즈_<이름>.json)
    py lens_w1.py video <out.json> <사진…> → lens_rows(SKIP_VIDEO, hl=en) — 틱톡·인스타·유튜브 링크 남김
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.calcopy import lens  # noqa: E402

lens.PROFILE = str(ROOT / ".lens_profile_w1")

if sys.argv[1] == "shop":
    import importlib.util
    spec = importlib.util.spec_from_file_location("lens_cp", HERE.parent / "렌즈쿠팡.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.lens_page = lens.lens_page
    m.main(sys.argv[2], sys.argv[3:])
else:
    out, imgs = sys.argv[2], sys.argv[3:]
    per = {}
    with lens.lens_page() as pg:
        for img in imgs:
            try:
                per[img] = lens.lens_rows(pg, img, skip=lens.SKIP_VIDEO, hl="en")
            except Exception as e:  # noqa: BLE001 — 한 장 실패는 결과에 남기고 계속
                per[img] = [{"error": f"{type(e).__name__} {str(e)[:80]}"}]
            print(img, len(per[img]))
    Path(out).write_text(json.dumps(per, ensure_ascii=False, indent=1), encoding="utf-8")
    for img, rows in per.items():
        for r in rows:
            if any(s in r.get("href", "") for s in ("tiktok", "instagram", "youtube", "youtu.be")):
                print(" ", r["shop"][:20], r["text"][:60], r["href"])
