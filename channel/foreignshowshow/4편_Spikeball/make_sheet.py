# -*- coding: utf-8 -*-
"""4편 Spikeball 계획 시트 — 재료.json 컷마다 벤치 틀(1080x1920, 제목 띠 2줄, 창 [0,434,1080,1052]) 위에 가운데 프레임 + 시작/끝 프레임 띠.
python make_sheet.py → plan/계획_시트.jpg · plan/frames/*.jpg (관제 097). 꾸밈(빨간 원·점선 원·화살표·돈 이모지)은 자리 표시만."""
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
FONT = "C:/Windows/Fonts/malgunbd.ttf"
W, H = 1080, 1920
WIN = (0, 434, 1080, 1052)
S = 0.3  # 칸 축소 비율


def frame(src, t, crop, out):
    x, y, w, h = crop
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                    "-vf", f"crop={w}:{h}:{x}:{y},scale={WIN[2]}:{WIN[3]}", str(out)], check=True)
    return Image.open(out).convert("RGB")


def luma(im):
    g = im.convert("L").resize((64, 64))
    return sum(g.getdata()) / 4096


def main():
    M = json.loads((HERE / "재료.json").read_text(encoding="utf-8"))
    D = json.loads((HERE / "대본.json").read_text(encoding="utf-8"))
    lines = {l["id"]: l for l in D["final"]["lines"]}
    fd = HERE / "plan" / "frames"
    fd.mkdir(parents=True, exist_ok=True)
    f_title = ImageFont.truetype(FONT, 84)
    f_sub = ImageFont.truetype(FONT, 64)
    f_lab = ImageFont.truetype(FONT, 40)
    cells = []
    seen_line = {}
    for s in M["shots"]:
        a = s["ss"]
        d = s["dur"]
        ims = [frame(s["src"], a + t, s["src_crop"], fd / f"{s['i']:02d}_{k}.jpg") for k, t in (("a", 0.12), ("m", d / 2), ("b", d - 0.12))]
        c = Image.new("RGB", (W, H + 520), "black")
        dr = ImageDraw.Draw(c)
        for txt, y, col in ((D["titles"]["line1"], 211, (255, 226, 0)), (D["titles"]["line2"], 318, (255, 255, 255))):
            tw = dr.textlength(txt, font=f_title)
            dr.text(((W - tw) / 2, y), txt, font=f_title, fill=col, stroke_width=4, stroke_fill="black")
        c.paste(ims[1], (WIN[0], WIN[1]))
        ln = lines[s["line"]]
        k = seen_line.get(s["line"], 0)
        seen_line[s["line"]] = k + 1
        subs = ln["sub"]
        sub = subs[min(k * max(1, len(subs) // max(1, sum(1 for x in M["shots"] if x["line"] == s["line"]))), len(subs) - 1)]
        tw = dr.textlength(sub, font=f_sub)
        hl = any(h in sub for h in ln.get("hl", []))
        dr.text(((W - tw) / 2, 940), sub, font=f_sub, fill=(120, 255, 200) if hl else "white", stroke_width=5, stroke_fill="black")
        if s.get("fx"):
            dr.rectangle((20, WIN[1] + 20, 620, WIN[1] + 90), fill=(200, 0, 60))
            dr.text((32, WIN[1] + 26), "꾸밈: " + s["fx"], font=f_lab, fill="white")
        # 아래 띠: 시작·끝 프레임 + 라벨
        for j, im in enumerate((ims[0], ims[2])):
            c.paste(im.resize((420, 409)), (60 + j * 540, 1500))
        y0 = H + 60
        au = s["audio"]["kind"]
        lab = [f"#{s['i']} {s['line']} {s['t_final_est'][0]:.1f}~{s['t_final_est'][1]:.1f}s ({d:.2f}s) · {au}",
               f"{Path(s['src']).name.split('_')[0]} 원본 {s['src_orig_span'][0]:.2f}~{s['src_orig_span'][1]:.2f} · crop {s['src_crop']} ×{s['scale']}",
               f"Y 시작/가운데/끝 {luma(ims[0]):.0f}/{luma(ims[1]):.0f}/{luma(ims[2]):.0f}",
               s["ours"][:34]]
        for n, t in enumerate(lab):
            dr.text((20, y0 + n * 54 - 40), t, font=f_lab, fill=(255, 220, 120) if n == 0 else "white")
        cells.append(c.resize((int(W * S), int((H + 520) * S))))
    cols = 8
    cw, ch = cells[0].size
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (40, 40, 40))
    for i, c in enumerate(cells):
        sheet.paste(c, (i % cols * cw, i // cols * ch))
    out = HERE / "plan" / "계획_시트.jpg"
    sheet.save(out, quality=82)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
