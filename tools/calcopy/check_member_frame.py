"""회원 꾸미기 값이 판 틀 그림까지 닿나 — 전 판을 끔/켬으로 그려 픽셀 대조(렌더·캡컷이 쓰는 frame_png·styles.load 그대로).
실행: py -m tools.calcopy.check_member_frame  (rc=0 = 전 판 달라짐)"""
import json, os, sys, tempfile
from pathlib import Path
from PIL import Image, ImageChops
from tools.calcopy.hybrid import render_bench as RB, styles as STY

S = {"title": ["아무도 몰랐던", "이 제품 뒷이야기"], "title_lines": ["아무도 몰랐던", "이 제품 뒷이야기"], "source_label": "출처"}
PACK = {"member": {"brand": {"channel_name": "시험채널", "colors": {"bg": [30, 60, 120]}},
              "text": {"title_font": "BlackHanSans", "title_colors": ["#FF0000", "#00FF00"], "title_scale": 0.8}}}

def main():
    tmp = Path(tempfile.mkdtemp()); pf = tmp / "p.json"; pf.write_text(json.dumps(PACK), encoding="utf-8")
    bad = []; n = 0
    for f in sorted(STY.DIR.glob("*판*.json")):
        name = f.stem
        if not STY.load(name).get("frame"):
            continue            # 전용 렌더러 판
        a, b = tmp / "a.png", tmp / "b.png"
        try:
            os.environ.pop("SHORTEM_MEMBER_PACK", None); RB.frame_png(S, STY.load(name), a)
            os.environ["SHORTEM_MEMBER_PACK"] = str(pf); st = STY.load(name); RB.frame_png(S, st, b)
        except Exception as e:
            bad.append(f"{name}: {type(e).__name__} {str(e)[:90]}"); continue
        n += 1
        if not ImageChops.difference(Image.open(a).convert("RGB"), Image.open(b).convert("RGB")).getbbox():
            bad.append(f"{name}: 안 달라짐")
        if name.startswith(sys.argv[1] if len(sys.argv) > 1 else "잇템로그판"):
            Image.open(b).convert("RGB").resize((360, 640)).save("member_frame_sample.png")
    print("판", n, "문제", len(bad)); print("\n".join(bad))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
