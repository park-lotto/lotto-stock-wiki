"""4회차 세로 쇼츠 썸네일 4장(11-04) — 롱폼 확정 시안5(make_thumb.py)와 같은 결: 어두운 완성 쇼츠 배경 + 주황 픽셀 캐릭터 + 노란 꼬리표 + 흰/노랑/민트 큰 글씨
1080x1920 기준 좌표를 K배(2160x3840)로 그려 png 원본 + 1080x1920 jpg.
usage: py thumb/make_thumb_v.py <출력폴더>"""
import os, sys, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

S = os.path.dirname(os.path.abspath(__file__)); WK = os.path.dirname(S)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S, "short")
os.makedirs(OUT, exist_ok=True)
K = 2; W, H = 1080 * K, 1920 * K
FONT = os.path.join(WK, "fonts", "Pretendard-Black.otf")
COL = {"W": (255, 255, 255), "M": (35, 240, 200), "Y": (255, 214, 0), "R": (255, 45, 45)}
ORANGE = (217, 119, 87)
GRID = ["   ############  ", "   ##E######E##  ", " ################", "   ############  ", "    # #    # #   "]   # make_thumb.py 와 같은 캐릭터
SETS = {   # 편: (배경 쇼츠 순서 — 첫째가 그 편 완성본, 꼬리표, 글줄 3)
    "1_타투": (["tattoo", "sun", "ottogi", "tint", "lego", "choco"], "캡컷 노가다 전혀없음!!",
              [[["클로드가 ", "W"], ["진짜", "Y"]], [["일냈다!", "W"]], [["\"한 줄\"", "Y"], [" 쳤더니 쇼츠 완성", "M"]]]),
    "2_선크림": (["sun", "tattoo", "tint", "spat", "ottogi", "lego"], "이메일만 보내던 쉰 살",
               [[["손편집 강의 ", "W"], ["2개", "Y"]], [["다 안 되던 게", "W"]], [["키보드 ", "M"], ["한 줄", "Y"], ["로 끝", "M"]]]),
    "3_오뚜기": (["ottogi", "choco", "chal", "lego", "sun", "tattoo"], "베끼기 아닙니다!!",
               [[["잘된 채널", "Y"], ["을", "W"]], [["통째로 뜯는다", "W"]], [["클로드 ", "M"], ["벤치마킹", "Y"]]]),
    "4_레고": (["lego", "ottogi", "tattoo", "choco", "sun", "tint"], "매주 새 스타일 +2",
             [[["채널 ", "W"], ["하나만?", "Y"]], [["할 이유 없다", "W"]], [["\"만들어줘\" ", "Y"], ["한 줄이면 끝", "M"]]]),
}


def frame(name, t=2.5):
    p = os.path.join(OUT, f"_f_{name}.png")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", os.path.join(WK, "src", f"{name}.mp4"), "-frames:v", "1", p], check=True)
    return Image.open(p).convert("RGB")


def draw_char(img, x0, y0, PX, PY, body, eye):
    d = ImageDraw.Draw(img)
    for r, row in enumerate(GRID):
        for c, ch in enumerate(row):
            if ch != " ":
                x, y = x0 + c * PX, y0 + r * PY
                d.rectangle((x, y, x + PX - 1, y + PY - 1), fill=eye if ch == "E" else body)


def make(key, srcs, tag, lines):
    bg = Image.new("RGB", (W, H), (8, 8, 10))
    cw = 400 * K   # 3열 2줄, 시안5처럼 들쭉날쭉
    pos = [(-40, 40), (330, -30), (700, 60), (-60, 760), (320, 690), (690, 790)]
    for k, (nm, (x, y)) in enumerate(zip(srcs, pos)):
        im = frame(nm).resize((cw, int(1920 * cw / 1080)), Image.LANCZOS)
        im = ImageEnhance.Brightness(im).enhance(0.62 if k == 0 else 0.5)
        mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 18 * K, fill=255)
        bg.paste(im, (x * K, y * K), mask)
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(max(0, min(255, (y / K - 1000) * 255 / 260))))
    bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, grad.resize((W, H))).convert("RGBA")
    # 그 편 완성본 한 칸을 밝고 크게(Jev 썸네일 B안 0.47·0.64) — 오른쪽 위, 흰 테두리
    fw = 560 * K; im = frame(srcs[0]).resize((fw, int(1920 * fw / 1080)), Image.LANCZOS)
    fx, fy, bd = 470 * K, 90 * K, 10 * K
    fsh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(fsh).rounded_rectangle((fx - bd + 20 * K, fy - bd + 26 * K, fx + fw + bd + 20 * K, fy + im.height + bd + 26 * K), 30 * K, fill=(0, 0, 0, 200))
    bg = Image.alpha_composite(bg, fsh.filter(ImageFilter.GaussianBlur(18 * K)))
    ImageDraw.Draw(bg).rounded_rectangle((fx - bd, fy - bd, fx + fw + bd, fy + im.height + bd), 30 * K, fill=(255, 255, 255, 255))
    mask = Image.new("L", im.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 22 * K, fill=255)
    bg.paste(im, (fx, fy), mask)
    # 캐릭터 + 주황 빛 — 완성본 왼쪽 아래에 걸치게
    PX = 26 * K; PY = 2 * PX
    gw, gh = len(GRID[0]) * PX, len(GRID) * PY
    cx, cy = 300 * K, 900 * K; ox, oy = cx - gw // 2, cy - gh // 2
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - gw * 0.75, cy - gh * 0.75, cx + gw * 0.75, cy + gh * 0.75), fill=(255, 120, 50, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(80 * K)); bg = Image.alpha_composite(Image.alpha_composite(bg, glow), glow)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); draw_char(sh, ox + 14 * K, oy + 20 * K, PX, PY, (0, 0, 0, 170), (0, 0, 0, 170))
    bg = Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(10 * K)))
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            draw_char(ol, ox + dx * 9 * K, oy + dy * 9 * K, PX, PY, (0, 0, 0, 255), (0, 0, 0, 255))
    bg = Image.alpha_composite(bg, ol); draw_char(bg, ox, oy, PX, PY, ORANGE + (255,), (20, 20, 20, 255))
    d = ImageDraw.Draw(bg)
    # 꼬리표(검은 상자 + 노란 글)
    f = ImageFont.truetype(FONT, 66 * K); tw = d.textlength(tag, font=f); tx, ty = 50 * K, 1140 * K   # 완성본 아래(위에 두면 제목 띠를 가린다)
    d.rounded_rectangle((tx - 22 * K, ty - 16 * K, tx + tw + 22 * K, ty + 92 * K), 12 * K, fill=(0, 0, 0))
    d.text((tx, ty), tag, font=f, fill=COL["Y"])
    # 글줄 3 — 가운데 정렬, 폭 넘치면 줄인다
    for parts, base, size, stroke in zip(lines, (1400, 1590, 1770), (170, 170, 112), (13, 13, 10)):
        size *= K
        while True:
            fo = ImageFont.truetype(FONT, size); tot = sum(d.textlength(p[0], font=fo) for p in parts)
            if tot <= W - 80 * K: break
            size -= 4
        x = (W - tot) / 2
        for p in parts:
            d.text((x, base * K), p[0], font=fo, fill=COL[p[1]], stroke_width=stroke * K, stroke_fill=(0, 0, 0), anchor="ls")
            x += d.textlength(p[0], font=fo)
    png = os.path.join(OUT, f"쇼츠{key}_썸네일_2160x3840.png"); bg.convert("RGB").save(png)
    bg.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(os.path.join(OUT, f"쇼츠{key}_썸네일_1080x1920.jpg"), quality=92)
    print(png)


for k, (srcs, tag, lines) in SETS.items():
    make(k, srcs, tag, lines)
