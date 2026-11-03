"""이미지·영상 소재 찾기.

  python media.py img  <프로젝트> <이름> "<검색어>" [개수=12]
      네이버 이미지 검색(키 불필요) → 실패분은 빙 이미지로 보충 → cands/<이름>/ 에 저장 (고르기는 agy 가 사진을 직접 봄)
  python media.py yt   <프로젝트> <이름> "<검색어>" [개수=4]
      유튜브 검색 → 720p 이하로 통째로 받기 → cands/<이름>/ 에 저장
      (어느 구간을 쓸지는 agy 가 영상을 직접 보고 고른다 — 장면 모아보기 그림은 만들지 않음)
  python media.py clip <프로젝트> <원본경로> <시작초> <길이초> <저장이름>
      후보 영상에서 구간 잘라 media/<저장이름>.mp4 (30fps, 소리 포함)
  python media.py pick <프로젝트> <후보경로> <저장이름>
      후보 이미지를 media/ 로 복사
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from io_utils import imread, imwrite, probe, run_enc, x264

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# yt-dlp 는 가상환경에 깐 파이썬 모듈로 부른다 — 윈도우·맥 모두 PATH 와 상관없이 같은 길
YTDLP = [sys.executable, "-m", "yt_dlp"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
LABEL_FONT = os.path.join(ROOT, "assets", "fonts", "Pretendard-Regular.otf")


def get(url, headers=None, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout).read()


def naver_images(q):
    t = get("https://search.naver.com/search.naver?" + urllib.parse.urlencode({"where": "image", "query": q})
            ).decode("utf-8", "ignore")
    urls = [u.encode().decode("unicode_escape") if "\\u" in u else u for u in re.findall(r'"originalUrl":"(.*?)"', t)]
    return [u.replace("\\/", "/") for u in urls]


def bing_images(q):
    t = get("https://www.bing.com/images/async?" + urllib.parse.urlencode(
        {"q": q, "first": 0, "count": 40, "qft": "+filterui:imagesize-large", "mmasync": 1})).decode("utf-8", "ignore")
    out = []
    for m in re.findall(r'm="(\{.*?\})"', t):
        try:
            out.append(json.loads(html.unescape(m))["murl"])
        except Exception:
            pass
    return out


def fetch_image(url, path):
    for ref in ("https://search.naver.com/", None):
        try:
            data = get(url, {"Referer": ref} if ref else None, timeout=15)
            arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if arr is None:  # webp/gif 등
                import io
                arr = np.array(Image.open(io.BytesIO(data)).convert("RGB"))[:, :, ::-1]
            h, w = arr.shape[:2]
            if w < 400 or h < 300:
                return None
            imwrite(path, arr)
            return w, h
        except Exception:
            continue
    return None


def sheet(items, out, cols=4, cell=360):
    """items: [(라벨, BGR 이미지)] → 번호 붙은 모아보기."""
    f = ImageFont.truetype(LABEL_FONT, 26)
    rows = (len(items) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell, rows * (cell + 34)), (40, 40, 40))
    d = ImageDraw.Draw(canvas)
    for i, (lab, img) in enumerate(items):
        h, w = img.shape[:2]
        s = min(cell / w, cell / h)
        th = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))))
        x, y = (i % cols) * cell, (i // cols) * (cell + 34)
        canvas.paste(Image.fromarray(th[:, :, ::-1]), (x + (cell - th.shape[1]) // 2, y + 34 + (cell - th.shape[0]) // 2))
        d.text((x + 6, y + 3), lab, font=f, fill=(255, 230, 0))
    canvas.save(out, quality=88)
    return out


def cmd_img(proj, name, q, n=12):
    d = os.path.join(proj, "cands", name)
    os.makedirs(d, exist_ok=True)
    urls = []
    for fn in (naver_images, bing_images):
        try:
            urls += [u for u in fn(q) if u not in urls]
        except Exception as e:
            print(f"  {fn.__name__} 실패: {e}")
    got = []
    for u in urls:
        if len(got) >= n:
            break
        p = os.path.join(d, f"{len(got) + 1:02d}.jpg")
        wh = fetch_image(u, p)
        if wh:
            got.append({"file": p, "url": u, "w": wh[0], "h": wh[1]})
    json.dump(got, open(os.path.join(d, "_list.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(got)}장 저장: {d}")


def cmd_yt(proj, name, q, n=4):
    d = os.path.join(proj, "cands", name)
    os.makedirs(d, exist_ok=True)
    r = subprocess.run([*YTDLP, "--flat-playlist", "-J", f"ytsearch{n * 3}:{q}"], capture_output=True, text=True,
                       encoding="utf-8")
    entries = [e for e in json.loads(r.stdout)["entries"] if e.get("duration") and e["duration"] <= 600][:n]
    res = []
    for i, e in enumerate(entries, 1):
        base = os.path.join(d, f"v{i:02d}")
        # 유튜브가 간헐적으로 403 을 내서(구간 다운로드는 항상 막힘) 형식을 바꿔가며 통째로 받는다
        for fmt in ("bv*[protocol*=m3u8][height<=720]/b[protocol*=m3u8][height<=720]",
                    "bv*[height<=720][ext=mp4]", "bv*[height<=1080]", "18", "b"):
            for f in os.listdir(d):
                if f.startswith(f"v{i:02d}.") and f.endswith(".part"):
                    os.remove(os.path.join(d, f))
            subprocess.run([*YTDLP, "-q", "--no-warnings", "-f", fmt, "-o", base + ".%(ext)s", e["url"]],
                           capture_output=True)
            if any(f.startswith(f"v{i:02d}.") and not f.endswith((".part", ".jpg")) for f in os.listdir(d)):
                break
        vids = [f for f in os.listdir(d) if f.startswith(f"v{i:02d}.") and not f.endswith((".part", ".jpg"))]
        if not vids:
            print(f"v{i:02d} 다운로드 실패: {e.get('title')}")
            continue
        path = os.path.join(d, vids[0])
        res.append({"file": path, "title": e.get("title"), "channel": e.get("channel"), "url": e["url"],
                    "duration": e["duration"]})
        print(f"v{i:02d} [{e['duration']}s] {e.get('title')} — {e.get('channel')}")
    json.dump(res, open(os.path.join(d, "_list.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(res)}개 저장: {d}")


def cmd_clip(proj, src, start, dur, name):
    os.makedirs(os.path.join(proj, "media"), exist_ok=True)
    out = os.path.join(proj, "media", name + ".mp4")
    # 소리도 남긴다 — 원본은 영상 클립 자체 소리(깨는 소리·씹는 소리)를 살려 쓴다. script 에서 "audio": true 로 켬
    w, h = probe(src)[:2]                                # 같은 용량 비트레이트의 크기
    run_enc(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", str(dur),
             "-vf", "fps=30", *x264("fast", 16, w, h, 30), "-c:a", "aac", "-b:a", "160k", out], check=True)
    print(out)


def cmd_pick(proj, src, name):
    os.makedirs(os.path.join(proj, "media"), exist_ok=True)
    out = os.path.join(proj, "media", name + os.path.splitext(src)[1])
    shutil.copy(src, out)
    print(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    proj = os.path.abspath(a[1])
    if a[0] == "img":
        cmd_img(proj, a[2], a[3], int(a[4]) if len(a) > 4 else 12)
    elif a[0] == "yt":
        cmd_yt(proj, a[2], a[3], int(a[4]) if len(a) > 4 else 4)
    elif a[0] == "clip":
        cmd_clip(proj, a[2], float(a[3]), float(a[4]), a[5])
    elif a[0] == "pick":
        cmd_pick(proj, a[2], a[3])
