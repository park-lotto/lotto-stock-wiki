# -*- coding: utf-8 -*-
"""줄마다 장면 후보 모으기 — 동영상(1순위)·사진 검색(2순위) 후보를 받아 후보 시트를 만든다 (관제 097, 2026-10-15).
판단(무엇을 찾을지·무엇을 고를지)은 오푸스가 scene_plan.json·picks.json 으로 한다. 이 스크립트는 받고 보여주기만(단순 작업).

    PYTHONUTF8=1 py tools/calcopy/scene_pack.py <작업폴더>      # <작업폴더>/scene_plan.json 필요
출력: cand/<줄>/v*.mp4 · p*.jpg  + cand_sheet/<줄>.jpg(동영상 3프레임씩 + 사진들, 번호 표시)
"""
import json, subprocess, sys
from pathlib import Path
import requests
from PIL import Image, ImageDraw

base = Path(sys.argv[1]); plan = json.loads((base / "scene_plan.json").read_text(encoding="utf-8"))
UA = {"User-Agent": "Mozilla/5.0"}


def _wh(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    try:
        w, h = map(int, o.split(",")[:2]); return w, h
    except ValueError:
        return 0, 0


def videos(q, out, n=2):
    subprocess.run(["yt-dlp", "--encoding", "utf-8", "-q", "--match-filter", "duration<90", "--max-downloads", str(n + 2),
                    "-f", "bv*[height<=1920][ext=mp4]+ba/b[ext=mp4]/b", "--merge-output-format", "mp4",
                    "-o", str(out / "v_%(id)s.%(ext)s"), f"ytsearch15:{q} #shorts"], capture_output=True)
    for f in out.glob("v_*.mp4"):          # 세로만 남긴다(엔진이 가로를 거절, 크롭하면 확대됨)
        w, h = _wh(f)
        if not h or w >= h:
            f.unlink()


def photos(q, out, n=4):
    from ddgs import DDGS
    k = 0
    for r in DDGS().images(q, max_results=12):
        if k >= n:
            break
        try:
            b = requests.get(r["image"], headers=UA, timeout=15).content
            p = out / f"p{k}.jpg"; p.write_bytes(b)
            Image.open(p).convert("RGB").save(p); k += 1
        except Exception:      # noqa: BLE001 — 깨진 이미지는 버리고 다음 후보
            continue


def sheet(i, out, dst):
    tiles = []
    for v in sorted(out.glob("v_*.mp4")):
        for t in (1, 3, 6):
            f = out / f"_{v.stem}_{t}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(v), "-frames:v", "1", "-vf", "scale=160:-2", str(f)])
            if f.exists():
                tiles.append((f"{v.stem}@{t}s", Image.open(f).copy())); f.unlink()
    for p in sorted(out.glob("p*.jpg")):
        im = Image.open(p); im.thumbnail((160, 285)); tiles.append((p.stem, im))
    if not tiles:
        return
    sh = Image.new("RGB", (len(tiles) * 165, 305), "white"); d = ImageDraw.Draw(sh)
    for k, (lab, im) in enumerate(tiles):
        sh.paste(im, (k * 165, 18)); d.text((k * 165 + 2, 2), lab[:22], fill=(220, 0, 0))
    sh.save(dst / f"{i:02d}.jpg", quality=80)


cs = base / "cand_sheet"; cs.mkdir(exist_ok=True)
for L in plan["lines"]:
    out = base / "cand" / f"{L['i']:02d}"; out.mkdir(parents=True, exist_ok=True)
    if not list(out.glob("v_*.mp4")) and L.get("video"):
        videos(L["video"], out)
    if not list(out.glob("p*.jpg")) and L.get("photo"):
        photos(L["photo"], out)
    sheet(L["i"], out, cs)
    print(L["i"], "영상", len(list(out.glob("v_*.mp4"))), "사진", len(list(out.glob("p*.jpg"))))
