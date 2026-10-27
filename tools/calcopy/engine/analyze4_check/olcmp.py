# -*- coding: utf-8 -*-
"""외곽선 두께 전/후: engine_뜯기3 의 띠·자막 구간(가운데 프레임 6장)을 같은 크롭으로 옛/새 captions.glyph_style 에 넣어 비교.

    git show <옛 커밋>:shopping_shorts/channelkit/bench/captions.py > captions_old.py
    PYTHONUTF8=1 py tools/calcopy/engine/analyze4_check/olcmp.py captions_old.py > olcmp.txt
(출력: 편마다 old/new 외곽선 px 목록과 중앙값. 원본 mp4 = C:/숏템_칼카피/<slug>/mp4)
"""
import sys, json, importlib.util, numpy as np
from pathlib import Path
OLD_FILE = sys.argv[1]
R0 = str(Path(__file__).resolve().parents[4])
sys.path.insert(0, R0)
from shopping_shorts.channelkit.bench import probe, captions as NEW
spec = importlib.util.spec_from_file_location("shopping_shorts.channelkit.bench.captions_old", OLD_FILE)
OLD = importlib.util.module_from_spec(spec); spec.loader.exec_module(OLD)
out = {}
for slug in ["sseolpulda","banggu","hottemreport","yummyknow"]:
    for d in sorted(Path(f"C:/숏템_칼카피/{slug}/engine_뜯기3").glob("*/뜯기.json")):
        R = json.loads(d.read_text(encoding="utf-8")); L = R["layout"]; C = R.get("captions") or {}
        band, ink = L.get("caption_band"), L.get("ink_polarity")
        spans = C.get("spans") or []
        if not band or not spans: continue
        y0, y1 = max(0, band[0]-40), min(1920, band[1]+40)
        mp4 = f"C:/숏템_칼카피/{slug}/mp4/{d.parent.name}.mp4"
        idx = sorted(set(np.linspace(0, len(spans)-1, min(6, len(spans))).astype(int).tolist()))
        o, n = [], []
        for i in idx:
            a, b = spans[i]
            img = probe.grab(mp4, (a+b)/2, f"crop=1080:{y1-y0}:0:{y0}", 1080, y1-y0)
            if img is None: continue
            go = OLD.glyph_style(img, ink, R["layout"].get("bg_rgb") or [255,255,255]); gn = NEW.glyph_style(img, ink, R["layout"].get("bg_rgb") or [255,255,255])
            if go: o.append(go["outline_px"])
            if gn: n.append(gn["outline_px"])
        rec = {"ink": ink, "old": o, "new": n, "old_med": int(np.median(o)) if o else None, "new_med": int(np.median(n)) if n else None}
        print(slug[:5], d.parent.name, json.dumps(rec), flush=True)
