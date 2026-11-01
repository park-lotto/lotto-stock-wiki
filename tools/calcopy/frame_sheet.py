# -*- coding: utf-8 -*-
"""클로드가 눈으로 읽을 장면 시트 — 편마다 0.5초 간격 프레임을 한 장에, 칸마다 시각 표시 (관제 097, 2026-10-15).
사장님: "판단·분석은 클로드로" → 영상 판독을 모델에 넘기지 않고 시트+받아쓰기를 클로드가 읽는다.

    PYTHONUTF8=1 py tools/calcopy/frame_sheet.py C:/숏템_칼카피/banggu [간격초=0.5]
출력: <폴더>/sheet/<id>.jpg (6열, 칸 180px 폭) + <id>.txt (받아쓰기 단어 시각)
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw

base = Path(sys.argv[1]); step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
out = base / "sheet"; out.mkdir(exist_ok=True)
COLS, CW = 6, 180
for mp4 in sorted((base / "mp4").glob("*.mp4")):
    vid = mp4.stem
    if (out / f"{vid}.jpg").exists():
        continue
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout or 0)
    tmp = out / f"_{vid}"; tmp.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps={1/step},scale={CW}:-2", str(tmp / "%04d.jpg")])
    fr = sorted(tmp.glob("*.jpg"))
    if not fr:
        continue
    w, h = Image.open(fr[0]).size
    rows = (len(fr) + COLS - 1) // COLS
    sh = Image.new("RGB", (COLS * w, rows * (h + 16)), "white"); d = ImageDraw.Draw(sh)
    for i, f in enumerate(fr):
        x, y = i % COLS * w, i // COLS * (h + 16)
        sh.paste(Image.open(f), (x, y + 16)); d.text((x + 3, y + 2), f"{i * step:.1f}s", fill=(220, 0, 0))
    sh.save(out / f"{vid}.jpg", quality=80)
    for f in fr: f.unlink()
    tmp.rmdir()
    a = base / "asr" / f"{vid}.json"
    if a.exists():
        W = [(x["alternatives"][0]["content"], x["start_time"]) for x in json.loads(a.read_text(encoding="utf-8")).get("results", []) if x.get("type") == "word"]
        (out / f"{vid}.txt").write_text(f"길이 {dur:.1f}s\n" + " ".join(f"[{t:.1f}]{w}" for w, t in W), encoding="utf-8")
print("시트", len(list(out.glob("*.jpg"))))
