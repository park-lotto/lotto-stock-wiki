# 구간 전환 화면과 끝 화면
from .settings import *
from .marks import *
from .motion import *
def bridge_screen(lt, T, short=False):
    """속도선 속에서 채널명이 빛나며 멈춘다."""
    img = night().convert("RGBA"); speed_lines(img, lt * 0.9); n = CFG["channel_name"]; p = smooth(lt / (0.4 if short else 0.7))
    img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(150 * p))))
    f = fit_face("HAN", 150 if short else 190, n, W - 300); y = H / 2
    glow_text(img, n, W / 2, y + (1 - p) * 40, f, INK, 26, p)
    d = ImageDraw.Draw(img); w = d.textlength(n, font=f) * p; d.rectangle([W / 2 - w / 2, y + 130, W / 2 + w / 2, y + 137], fill=GOLD)
    return img

def closing_screen(lt, T):
    img = night().convert("RGBA"); d = ImageDraw.Draw(img); p = smooth(lt / 0.8)
    orbit(img, W / 2, H / 2, 620, lt, GOLD, 0.5, 2); glow_text(img, CFG["channel_name"], 110, 130, face("HAN", 76), INK, 16, p, "l"); d.rectangle([110, 190, 110 + 300 * p, 197], fill=GOLD)
    for lab, x, y, w, h in [(CFG["outro_left"], 110, 320, 900, 506), (CFG["outro_right"], 1100, 320, 710, 400)]:
        spaced(img, lab, x, y - 54, 34, INK, 3); corner_ticks(d, (x, y, x + w, y + h), GOLD + (int(255 * p),), 54, 6)
    img.alpha_composite(mark_icon(96), (1100, 756))
    return img
