import sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
sys.path.insert(0, sys.argv[2])
from thumb_v3 import heavy, band, F, YEL, WHT, RED, BLK  # 롱폼 썸네일과 같은 글자 부품

D = sys.argv[1]
W, H = 1080, 1920
T = lambda s: F("Jalnan2.ttf", s)
S = lambda s: F("BlackHanSans.ttf", s)

bg = Image.open(f"{D}/real3.png").convert("RGB")       # 1920x1080 폰 공장
from PIL import ImageFilter
# 뒤: 같은 사진을 세로로 꽉 채워 흐리게 / 앞: 거치대 전체(폰 50대)가 다 보이게 가로 맞춤
back = bg.crop((980 - 304, 0, 980 + 304, 1080)).resize((W, H)).filter(ImageFilter.GaussianBlur(18))
rack = bg.crop((260, 0, 1660, 1080))                    # 거치대 전체
rack = rack.resize((W, int(1080 * W / 1400)), Image.LANCZOS)
back.paste(rack, (0, 830))
im = back.convert("L")
im = ImageEnhance.Brightness(ImageEnhance.Contrast(im).enhance(1.35)).enhance(0.9).convert("RGBA")
# 위·아래 어둡게(글자 받침), 가운데 폰은 살린다
m = Image.new("L", (W, H)); md = ImageDraw.Draw(m)
for y in range(H):
    v = 230 - y * 0.2 if y < 850 else (max(0, (y - 1560) * 0.6) if y > 1560 else 0)
    md.line((0, y, W, y), fill=int(max(0, min(220, v))))
im = Image.composite(Image.new("RGBA", (W, H), (0, 0, 0, 255)), im, m)

band(im, (60, 130), "클로드 1타 개발자", S(56), RED + (255,), WHT)
heavy(im, (60, 240), "하도 답답해서 직접", S(96), WHT, stroke=11, shadow=8)
heavy(im, (40, 360), "쇼츠공장", T(250), YEL, stroke=18, shadow=16)
heavy(im, (60, 640), "차렸습니다", S(110), WHT, stroke=12, shadow=9)
heavy(im, (60, 1640), "채널 50개 공개", S(120), WHT, stroke=12, shadow=10)
heavy(im, (850, 1560), "?", T(260), RED, stroke=16, shadow=12, rot=-10)
im.convert("RGB").save(f"{D}/short_A.png")
im.convert("RGB").resize((360, 640)).save(f"{D}/short_A_s.png")
print("ok")
