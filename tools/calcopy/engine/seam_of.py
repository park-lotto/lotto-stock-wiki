# -*- coding: utf-8 -*-
"""preset_make 완성본의 이음매 걸림(B16)을 시각으로 다시 본다(preset_make 표엔 개수만 나온다) (관제 097, 10-17).
    PYTHONUTF8=1 py tools/calcopy/engine/seam_of.py <자료폴더/make>
판단은 check_seams·preset_make 가 한다. 여기는 시각을 토막으로 옮겨 적기만."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import check_seams, preset_make as P  # noqa: E402

mk = Path(sys.argv[1])
win, mask = P.seam_area(mk / "work")
r = check_seams.check(str(mk / "final.mp4"), win, mask)
for kind in ("되감김", "점프줌"):
    for x in r[kind]:
        print(kind, x)
print("컷 시작(검출):", r["컷"])
