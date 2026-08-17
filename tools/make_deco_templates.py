"""꾸미기 템플릿 PNG 12종 생성 — 1080x1920 투명 RGBA.

★PNG만 커밋하면 "이게 어떻게 만들어졌는지" 아무도 모른다. 색·두께를 바꿀 땐
deco_templates.py를 고치고 이 스크립트를 다시 돌린다(손으로 그리지 않는다).

실행: py tools/make_deco_templates.py
"""
import pathlib
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from shopping_shorts import deco_templates as dt   # noqa: E402

W, H = 1080, 1920
OUT = pathlib.Path(__file__).resolve().parents[1] / "shopping_shorts" / "static" / "templates"


def _rgba(hex_color, alpha=255):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def draw(t):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = _rgba(t["color"])
    if t["shape"] == "top":
        d.rectangle([0, 0, W, t["geom"]["bar"]], fill=col)
    elif t["shape"] == "topbottom":
        b = t["geom"]["bar"]
        d.rectangle([0, 0, W, b], fill=col)
        d.rectangle([0, H - b, W, H], fill=col)
    else:  # frame
        b = t["geom"]["border"]
        d.rectangle([0, 0, W, b], fill=col)
        d.rectangle([0, H - b, W, H], fill=col)
        d.rectangle([0, 0, b, H], fill=col)
        d.rectangle([W - b, 0, W, H], fill=col)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for t in dt.TEMPLATES:
        draw(t).save(OUT / t["file"], "PNG")
        print("wrote", t["file"], t["name"])
    print(f"총 {len(dt.TEMPLATES)}장 →", OUT)


if __name__ == "__main__":
    main()
