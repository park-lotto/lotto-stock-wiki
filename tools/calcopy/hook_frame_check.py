# -*- coding: utf-8 -*-
"""훅 틀 시험(음성·돈 없음): 판마다 짧은/긴 첫 줄로 frame_segments·틀 그림을 만들어 모음 그림으로. py -m tools.calcopy.hook_frame_check <출력폴더>"""
import glob, json, sys
from pathlib import Path
from PIL import Image
from tools.calcopy.hybrid import render_bench as R
LONG = "요즘 사람들이 왜 다들 이 물건을 사서 쓰는지 직접 써 보고 나서야 드디어 알게 되었습니다"
SHORT = "이거 진짜예요"
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); fail = []; shots = []
for p in sorted(glob.glob("tools/calcopy/hybrid/styles/*.json")):
    n = Path(p).stem
    st = json.load(open(p, encoding="utf8"))
    if n.startswith("_") or not (st.get("frame") or {}).get("segments"):
        continue
    for tag, txt in (("short", SHORT), ("long", LONG)):
        S = {"title_lines": [[["제목 시험", None]]], "source_label": "", "post": {}, "lines": [{"id": "L1", "kind": "tts", "tts": txt, "caps": [txt]}, {"id": "L2", "kind": "tts", "tts": "다음", "caps": ["다음"]}]}
        T = {"end": 20.0, "lines": {"L1": [0.0, 3.0], "L2": [3.0, 20.0]}, "cuts": []}
        try:
            g = R.frame_segments(S, T, st)[0]
            f = R.seg_frame_png(S, st, g, out / f"{n}_{tag}.png")
            shots.append(f); print(n, tag, g["captions"], "띠글" if g["body_text"] else "-")
            has = st["frame"]["segments"][0].get("long")
            if tag == "long" and has and g["captions"] != "show": fail.append(n)
            if tag == "long" and has:   # 자막 세로 범위가 띠 안에 드는가
                c = st.get("caption") or {}; k = c.get("stack"); bb = g["frame"]["post"]["body_box"]["box"]
                y0, y1 = (k["y"] - k["pitch"] / 2, k["y"] + (k["lines"] - .5) * k["pitch"]) if k else tuple(c["band"])
                print("  자막", round(y0), round(y1), "띠", bb[1], bb[3])
                if y0 < bb[1] or y1 > bb[3]: fail.append(n + " 자막이 띠 밖")
            if tag == "short" and has and g["captions"] != "hide": fail.append(n)
        except Exception as e:
            fail.append(n); print(n, tag, "오류", repr(e)[:160])
W = 270; H = 480
sheet = Image.new("RGB", (W * max(len(shots), 1), H), "#333")
for i, f in enumerate(shots):
    im = Image.open(f).convert("RGBA"); bg = Image.new("RGBA", im.size, "#555"); bg.alpha_composite(im); sheet.paste(bg.convert("RGB").resize((W, H)), (i * W, 0))
sheet.save(out / "sheet.jpg", quality=85)
print("실패", fail); sys.exit(1 if fail else 0)
