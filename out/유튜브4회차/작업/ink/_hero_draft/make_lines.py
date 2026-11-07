# 원본 선화 → 화면에 보일 선 PNG(l_<이름>.png): 잉크색 #1F1D1A + 알파 = 원본 진하기(바탕 215↑ 투명). 펜 마스크로 드러낸다.
# 쓰기: py make_lines.py g_m_hope g_f_hope ...
import sys, os, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
for n in sys.argv[1:]:
    g = np.array(Image.open(os.path.join(HERE, n + ".png")).convert("L")).astype(np.float32)
    g[g >= 215] = 255
    a = np.clip((255 - g) * (255 / 200), 0, 255).astype(np.uint8)       # 55 이하 = 완전 불투명
    rgba = np.dstack([np.full_like(a, 0x1F), np.full_like(a, 0x1D), np.full_like(a, 0x1A), a])
    Image.fromarray(rgba, "RGBA").save(os.path.join(HERE, "l_" + n[2:] + ".png"), optimize=True)
    print("l_" + n[2:])
