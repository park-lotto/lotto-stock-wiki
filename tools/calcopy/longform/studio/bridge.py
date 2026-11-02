# 구간 전환 화면과 끝 화면
from .settings import *
from .marks import *
def channel_title(d, x, y, size, fill):
    d.text((x, y), CFG["channel_name"], font=face("GM", size), fill=fill)

def bridge_screen(lt, T, short=False):
    img = Image.new("RGBA", (W, H), (12, 24, 28, 255)); d = ImageDraw.Draw(img); ac = C["sub_bar"]; n = CFG["channel_name"]
    dur = 0.5 if short else 0.9; p = smooth(lt / dur); size = 150 if short else 190; f = face("GM", size); w = width_of(d, n, f); x = (W - w) / 2; y = H / 2 - size * 0.62
    d.rectangle([0, H / 2 + size * 0.62, W * p, H / 2 + size * 0.62 + 10], fill=ac)
    for i, ch in enumerate(n):
        g = smooth((lt - i * 0.06) / 0.3)
        if g > 0: d.text((x + d.textlength(n[:i], font=f), y + (1 - g) * size * 0.5), ch, font=f, fill=(255, 255, 255, int(255 * g)))
    return img

def closing_screen(lt, T):
    img = Image.new("RGBA", (W, H), (12, 24, 28, 255)); d = ImageDraw.Draw(img); ac = C["sub_bar"]; p = smooth(lt / 0.8)
    channel_title(d, 110, 90, 72, (255, 255, 255, 255)); d.rectangle([110, 190, 110 + 300 * p, 198], fill=ac)
    for lab, x, y, w, h in [(CFG["outro_left"], 110, 320, 900, 506), (CFG["outro_right"], 1100, 320, 710, 400)]:
        d.text((x, y - 62), lab, font=face("GM", 40), fill=(255, 255, 255, 255))
        d.rectangle([x, y, x + w * p, y + h], outline=ac, width=6)
    img.alpha_composite(mark_icon(96), (1100, 756))
    return img

