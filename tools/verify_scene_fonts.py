"""장면꾸미기 로컬 폰트 파일의 무결성과 한글 글리프를 검사한다."""
from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1] / "shopping_shorts" / "static" / "fonts"
TARGETS = [
    "BagelFatOne-Regular.ttf", "Dongle-Bold.ttf", "GothicA1-Black.ttf",
    "Hahmlet-Variable.ttf", "Orbit-Regular.ttf", "SongMyung-Regular.ttf",
    "YeonSung-Regular.ttf", "GowunDodum-Regular.ttf", "NanumGothicCoding-Bold.ttf",
    "NanumMyeongjo-ExtraBold.ttf", "GrandifloraOne-Regular.ttf", "MoiraiOne-Regular.ttf",
]


for filename in TARGETS:
    font = TTFont(ROOT / filename)
    family = next(
        (entry.toUnicode() for entry in font["name"].names if entry.nameID == 1 and entry.platformID == 3),
        filename,
    )
    cmap = font.getBestCmap() or {}
    korean_ok = all(ord(char) in cmap for char in "한글폰트")
    print(f"{filename}|{family}|korean={korean_ok}|glyphs={len(cmap)}")
    if not korean_ok:
        raise SystemExit(f"Korean glyph check failed: {filename}")
