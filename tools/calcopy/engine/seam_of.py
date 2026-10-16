# -*- coding: utf-8 -*-
"""preset_make 완성본의 이음매 걸림(B16)을 시각·그림으로 다시 본다 — preset_make 표엔 개수만 나온다 (관제 097, 10-17).
    PYTHONUTF8=1 py tools/calcopy/engine/seam_of.py <자료폴더/make>   → 걸린 시각 목록 + <make>/seams.jpg(걸린 곳 앞·뒤 프레임, 자막으로 토막을 읽는다)
판단은 check_seams·preset_make 가 한다. 여기는 옮겨 적고 보여 주기만."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import check_seams, preset_make as P  # noqa: E402

mk = Path(sys.argv[1])
win, mask = P.seam_area(mk / "work")
r = check_seams.check(str(mk / "final.mp4"), win, mask)
hits = [(k, x) for k in ("되감김", "점프줌") for x in r[k]]
for k, x in hits:
    print(k, x)
if hits:
    from PIL import Image, ImageDraw
    rows = []
    for k, x in hits:
        ims = []
        for dt in (-0.1, 0.05):
            o = mk / f"_seam_{x['t'] + dt:.2f}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, x['t'] + dt):.2f}", "-i", str(mk / "final.mp4"), "-frames:v", "1",
                            "-vf", "scale=200:-2", str(o)], stdin=subprocess.DEVNULL)
            ims.append(Image.open(o).convert("RGB"))
            o.unlink()
        row = Image.new("RGB", (420, ims[0].height), "white")
        row.paste(ims[0], (0, 0))
        row.paste(ims[1], (210, 0))
        ImageDraw.Draw(row).text((4, 4), f"{k} {x['t']}", fill="red")
        rows.append(row)
    sh = Image.new("RGB", (420, sum(x.height for x in rows)), "white")
    y = 0
    for x in rows:
        sh.paste(x, (0, y))
        y += x.height
    sh.save(mk / "seams.jpg", quality=80)
    print(mk / "seams.jpg")
