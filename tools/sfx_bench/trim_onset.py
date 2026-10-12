# -*- coding: utf-8 -*-
"""팩 파일 앞 무음 자르기 — 소리가 '들리는'(최고점-6dB) 시점이 LEAD_MS에 오게 맞춘다.

왜(2026-09-22 실렌더): 팩07 휙은 -6dB 도달 47ms·최고점 87ms, 딸깍딸깍은 앞 99ms가 무음이라
자막이 바뀐 뒤 0.07~0.1초 늦게 들렸다(이븐쇼핑 휙 차오름 중앙 28ms). 오프너는 두 번 치는
구조 자체가 소리라 건드리지 않는다. 여러 번 돌려도 결과가 같다(이미 맞으면 그대로).
사용: py tools/sfx_bench/trim_onset.py shopping_shorts/assets/sfx_packs
"""
import glob, os, sys
import numpy as np, soundfile as sf
LEAD_MS = 5
SKIP = {"opener"}
root = sys.argv[1]
n = 0
for f in sorted(glob.glob(os.path.join(root, "*", "*.wav"))):
    if os.path.basename(f)[:-4] in SKIP:
        continue
    x, sr = sf.read(f)
    k = int(0.005 * sr)
    r = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(k) / k, "same")) + 1e-9)
    on = int(np.argmax(r > r.max() - 6)) - k // 2
    cut = max(0, on - int(LEAD_MS / 1000 * sr))
    if cut > int(0.003 * sr):
        y = x[cut:].copy()
        f_in = min(len(y), int(0.002 * sr)); y[:f_in] *= np.linspace(0, 1, f_in)   # 자른 자리 딸깍 방지
        sf.write(f, y, sr, subtype="PCM_16"); n += 1
        print(f"{os.path.relpath(f, root)}: 앞 {cut / sr * 1000:.0f}ms 자름")
print("자른 파일", n)
