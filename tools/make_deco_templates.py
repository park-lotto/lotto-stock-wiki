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
    # ★PIL의 rectangle([x0,y0,x1,y1])은 양끝 좌표를 **포함**해서 칠한다(끝점 inclusive).
    # 그래서 bar=190이면 [0,190]은 191px가 칠해진다 — 먼 쪽 좌표에서 1을 빼야
    # 선언한 px 수와 실제로 칠해진 px 수가 정확히 같아진다.
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = _rgba(t["color"])
    if t["shape"] == "top":
        b = t["geom"]["bar"]
        d.rectangle([0, 0, W, b - 1], fill=col)
    elif t["shape"] == "topbottom":
        b = t["geom"]["bar"]
        d.rectangle([0, 0, W, b - 1], fill=col)
        d.rectangle([0, H - b, W, H - 1], fill=col)
    else:  # frame
        b = t["geom"]["border"]
        d.rectangle([0, 0, W, b - 1], fill=col)
        d.rectangle([0, H - b, W, H - 1], fill=col)
        d.rectangle([0, 0, b - 1, H], fill=col)
        d.rectangle([W - b, 0, W - 1, H], fill=col)
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for t in dt.TEMPLATES:
        draw(t).save(OUT / t["file"], "PNG")
        print("wrote", t["file"], t["name"])
    print(f"총 {len(dt.TEMPLATES)}장 →", OUT)


if __name__ == "__main__":
    main()
