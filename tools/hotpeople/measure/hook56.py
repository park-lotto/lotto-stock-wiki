# -*- coding: utf-8 -*-
"""채널 전 편의 **첫 자막(훅)·헤드라인**을 한 장 시트로 뜯어 제미니로 읽는다 → 훅 유형 × 조회 대조 재료.
입력: 저화질(세로 720) mp4 폴더 + 메타(rows_scored.json, channel_stats.py 산출). 좌표는 1080×1920 기준을 높이 비율로 줄인다.
사용: PYTHONUTF8=1 py hook56.py <mp4폴더> <rows_scored.json> → hooks.json + hook_sheet_*.png
"""
import subprocess, json, sys, os, glob, time
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, r"C:\Users\CH\Desktop\로또의 주식\.tracks\숏템엔진")
from shopping_shorts.channelkit.providers import gemini_reader
from shopping_shorts.channelkit.prompt import parse_any

D, META = sys.argv[1], sys.argv[2]
rows = {r["id"]: r for r in json.load(open(META, encoding="utf-8"))}
ENV = r"C:\Users\CH\Desktop\로또의 주식\.tracks\숏템엔진\.env"
readers = [gemini_reader("gemini-3.1-flash-lite", env_file=ENV), gemini_reader("gemini-2.5-flash", env_file=ENV)]
T_HOOK = 1.0                      # 첫 자막은 0~2초 사이에 떠 있다(자막 1개 ≈ 2.2초)


def frame(f, t):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                       capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(r[0]), int(r[1])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t}", "-i", f, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < w * h * 3: return None
    img = Image.frombytes("RGB", (w, h), raw[:w * h * 3])
    return img.resize((1080, 1920)) if (w, h) != (1080, 1920) else img


crops = []
for f in sorted(glob.glob(os.path.join(D, "*.mp4"))):
    vid = os.path.basename(f)[:11]
    img = frame(f, T_HOOK)
    if img is None: continue
    head = img.crop((0, 200, 1080, 480)).resize((540, 140))
    sub = img.crop((0, 1272, 1080, 1470)).resize((540, 99))
    crops.append((vid, head, sub))
sheets = []
for si in range(0, len(crops), 14):
    chunk = crops[si:si + 14]
    sh = Image.new("RGB", (1120, len(chunk) * 250 + 10), "white"); d = ImageDraw.Draw(sh)
    for i, (vid, head, sub) in enumerate(chunk):
        y = i * 250 + 5
        d.rectangle([0, y, 1120, y + 245], outline="black")
        d.text((5, y + 2), f"{i + 1}  {vid}  조회 {rows.get(vid, {}).get('view_count', '?'):,}", fill=(0, 0, 255))
        sh.paste(head, (10, y + 20)); sh.paste(sub, (10, y + 145))
        d.text((560, y + 20), "헤드라인 ↑ / 첫 자막 ↓", fill="gray")
    p = f"hook_sheet_{si // 14 + 1}.png"; sh.save(p); sheets.append((p, chunk))

PROMPT = ("한국어 쇼츠 채널의 영상 {n}편 시트다. 칸마다 왼쪽 위 파란 번호, 위 그림 = 헤드라인(제목 2줄), 아래 그림 = 첫 자막(1초 시점). "
          "번호 순서대로 글자를 그대로 옮겨라(줄바꿈은 ' / '). 첫 자막 뒤에 노란 형광펜 띠가 있으면 mark=true. 자막이 없으면 \"\".\n"
          "출력 JSON: {\"items\": [{\"n\": 1, \"headline\": \"…\", \"first_sub\": \"…\", \"mark\": true}, …]}")
out = {}
for p, chunk in sheets:
    got = None
    for rd in readers:
        for wait in (0, 10, 30):
            if wait: time.sleep(wait)
            try:
                r = parse_any(rd(PROMPT.replace("{n}", str(len(chunk))), [p])) or {}   # .format은 JSON 중괄호를 필드로 읽어 KeyError(2026-09-28)
                items = r.get("items") if isinstance(r, dict) else None
                if items and len(items) == len(chunk): got = items; break
                print(f"[{p}] 개수 불일치 기대 {len(chunk)} 받음 {len(items) if items else None}")
            except Exception as e:
                print(f"[{p}] 실패: {repr(e)[:120]}")
        if got: break
    if not got: print(f"[{p}] ★실패"); continue
    for (vid, _, _), it in zip(chunk, got):
        out[vid] = {"headline": it.get("headline", ""), "first_sub": it.get("first_sub", ""), "mark": bool(it.get("mark")),
                    "views": rows.get(vid, {}).get("view_count"), "title": rows.get(vid, {}).get("title"), "date": rows.get(vid, {}).get("upload_date")}
json.dump(out, open("hooks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done", len(out), "/", len(crops))
for vid, o in sorted(out.items(), key=lambda kv: -(kv[1]["views"] or 0)):
    print(f"{o['views']:>9,} {'★' if o['mark'] else ' '} {o['first_sub'][:40]:40s} | {o['headline'][:30]}")
