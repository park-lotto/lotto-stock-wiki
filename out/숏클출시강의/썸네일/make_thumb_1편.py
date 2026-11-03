import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

D = sys.argv[1]
FD = "C:/Users/TheRose/Desktop/로또의 주식/.tracks/유튜브제작/shopping_shorts/static/fonts/"
W, H = 1280, 720
YEL, WHT, RED, BLK = (255, 222, 0), (255, 255, 255), (232, 22, 38), (0, 0, 0)

def F(name, s): return ImageFont.truetype(FD + name, s)

def heavy(im, xy, s, font, fill, stroke=12, shadow=10, rot=0):
    """두꺼운 검정 외곽 + 아래로 떨어진 그림자 — 유료 썸네일 톤."""
    l, t, r, b = ImageDraw.Draw(im).textbbox((0, 0), s, font=font, stroke_width=stroke)
    pad = 40
    lay = Image.new("RGBA", (r - l + pad * 2 + shadow, b - t + pad * 2 + shadow), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    o = (pad - l, pad - t)
    d.text((o[0] + shadow, o[1] + shadow), s, font=font, fill=(0, 0, 0, 200), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
    d.text(o, s, font=font, fill=fill, stroke_width=stroke, stroke_fill=BLK)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(lay, (xy[0] - pad, xy[1] - pad))

def band(im, xy, s, font, bg, fg, rot=0):
    d0 = ImageDraw.Draw(im)
    l, t, r, b = d0.textbbox((0, 0), s, font=font)
    lay = Image.new("RGBA", (r - l + 44, b - t + 30), bg)
    ImageDraw.Draw(lay).text((22 - l, 15 - t), s, font=font, fill=fg)
    if rot: lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(lay, xy)

def make(out, title_font, sub_font):
    bg = Image.open(f"{D}/real3.png").convert("RGB")
    # 배경 전체 = 폰 50대 거치대 통째로, 흑백
    full = bg.resize((W, H)).convert("L")
    full = ImageEnhance.Contrast(full).enhance(1.35)
    full = ImageEnhance.Brightness(full).enhance(0.95).convert("RGBA")
    im = full.copy()
    # 오른쪽 반: 같은 흑백 사진 위에 어두운 빨강을 덮는다(폰이 비쳐 보이게)
    right = Image.alpha_composite(full, Image.new("RGBA", (W, H), (90, 0, 8, 110)))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(770, 0), (W, 0), (W, H), (530, H)], fill=255)
    im.paste(right, (0, 0), mask)
    d = ImageDraw.Draw(im)
    d.line([(770, 0), (530, H)], fill=YEL, width=14)
    # 왼쪽 아래 어둡게(제목 받침)
    sh = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(sh)
    for y in range(H):
        sd.line((0, y, W, y), fill=int(max(0, min(150, (y - 470) * 0.8))))
    im = Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)), im, sh)

    band(im, (26, 24), "클로드 1타 개발자의 노하우", sub_font(44), RED + (255,), WHT)
    heavy(im, (30, 395), "개발하다 답답해서", sub_font(62), WHT, stroke=9, shadow=6)
    heavy(im, (22, 488), "직접 시작", title_font(128), YEL, stroke=12, shadow=10)
    heavy(im, (735, 22), "쇼츠공장", title_font(124), WHT, stroke=14, shadow=12)
    # 가린 조회수 카드: 실제 값(19,164회)을 흐리고 '공개 금지' 띠로 덮는다
    card = Image.new("RGBA", (560, 250), (255, 255, 255, 255))
    cd = ImageDraw.Draw(card)
    cd.text((28, 20), "채널 개설 일주일 조회수", font=sub_font(42), fill=(70, 70, 70))
    cd.text((28, 86), "19,164회", font=title_font(132), fill=(220, 20, 30))
    card.paste(card.crop((14, 80, 546, 240)).filter(ImageFilter.GaussianBlur(16)), (14, 80))
    cd = ImageDraw.Draw(card)
    cd.rectangle((14, 128, 546, 196), fill=(20, 20, 20))
    f2 = sub_font(52); tw = cd.textbbox((0, 0), "공개 금지", font=f2)[2]
    cd.text(((560 - tw) // 2, 132), "공개 금지", font=f2, fill=WHT)
    card = card.rotate(3, expand=True, resample=Image.BICUBIC)
    card = card.resize((int(card.width * 0.85), int(card.height * 0.85)), Image.LANCZOS); im.alpha_composite(card, (715, 225))
    heavy(im, (1010, 440), "?", title_font(230), RED, stroke=14, shadow=12, rot=-12)
    im.convert("RGB").save(out)

make(f"{D}/v3_jalnan.png", lambda s: F("Jalnan2.ttf", s), lambda s: F("BlackHanSans.ttf", s))
make(f"{D}/v3_gmarket.png", lambda s: F("GmarketSansBold.otf", s), lambda s: F("TmonMonsori.ttf", s))
sheet = Image.new("RGB", (1280, 360))
for i, n in enumerate(["v3_jalnan", "v3_gmarket"]):
    sheet.paste(Image.open(f"{D}/{n}.png").resize((640, 360)), (i * 640, 0))
sheet.save(f"{D}/v3_sheet.png")
print("ok")
