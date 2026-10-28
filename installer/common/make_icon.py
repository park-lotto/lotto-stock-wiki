"""숏템 아이콘 생성기 — mcpb/icon.png(512) · win/shortem.ico(16~256) 를 같은 그림에서 만든다.
실행: py installer/common/make_icon.py   (Pillow 필요)
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S = 1024  # 크게 그린 뒤 줄여 계단 현상을 없앤다


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 세로 그라데이션 배경(#FF5A36 → #C2185B)
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    top, bot = (255, 90, 54), (194, 24, 91)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # 세로 화면(숏폼) 모양 흰 테두리
    fw, fh = int(S * 0.44), int(S * 0.66)
    fx, fy = (S - fw) // 2, (S - fh) // 2
    d.rounded_rectangle([fx, fy, fx + fw, fy + fh], radius=int(S * 0.06), outline=(255, 255, 255, 255), width=int(S * 0.045))
    # 가운데 재생 삼각형
    cx, cy, r = S // 2 + int(S * 0.02), S // 2, int(S * 0.13)
    d.polygon([(cx - r * 0.8, cy - r), (cx - r * 0.8, cy + r), (cx + r, cy)], fill=(255, 255, 255, 255))
    return img


def main() -> None:
    big = draw()
    png = ROOT / "mcpb" / "icon.png"
    big.resize((512, 512), Image.LANCZOS).save(png)
    ico = ROOT / "win" / "shortem.ico"
    big.resize((256, 256), Image.LANCZOS).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(png, png.stat().st_size)
    print(ico, ico.stat().st_size)


if __name__ == "__main__":
    main()
