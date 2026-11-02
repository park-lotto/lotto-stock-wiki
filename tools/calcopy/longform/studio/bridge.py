# 구간 전환 화면과 끝 화면
from .settings import *
from .marks import *
from .motion import *
def bridge_screen(lt, T, short=False, look="lines"):
    """챕터 사이 짧은 숨. 세 가지가 번갈아 나온다."""
    img = dark("base", lt); n = CFG["channel_name"]; p = smooth(lt / 0.22); f = fit_face("HAN", 150 if short else 190, n, W - 300); y = H / 2
    if look == "lines": speed_lines(img, lt * 2.2); img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(150 * p))))
    elif look == "rings":
        for i in range(5): ping(img, W / 2, y, ((lt * 2.4 + i * 0.2) % 1.0), GOLD, 120, 760)
    else:
        d = ImageDraw.Draw(img); c = 1 - smooth(lt / 0.3)
        for i in range(9): x = i * W // 9; d.rectangle([x, 0, x + int(W / 9 * c), H], fill=GOLD)
    z = 1 + (1 - p) * 0.3; glow_text(img, n, W / 2, y, fit_face("HAN", int((150 if short else 190) * z), n, W - 200), INK, 26, p)
    d = ImageDraw.Draw(img); w = d.textlength(n, font=f) * p; d.rectangle([W / 2 - w / 2, y + 130, W / 2 + w / 2, y + 137], fill=GOLD)
    return img

def closing_screen(lt, T):
    img = night().convert("RGBA"); d = ImageDraw.Draw(img); p = smooth(lt / 0.8)
    orbit(img, W / 2, H / 2, 620, lt, GOLD, 0.5, 2); glow_text(img, CFG["channel_name"], 110, 130, face("HAN", 76), INK, 16, p, "l"); d.rectangle([110, 190, 110 + 300 * p, 197], fill=GOLD)
    for lab, x, y, w, h in [(CFG["outro_left"], 110, 320, 900, 506), (CFG["outro_right"], 1100, 320, 710, 400)]:
        spaced(img, lab, x, y - 54, 34, INK, 3); corner_ticks(d, (x, y, x + w, y + h), GOLD + (int(255 * p),), 54, 6)
    img.alpha_composite(mark_icon(96), (1100, 756))
    return img
