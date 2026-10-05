"""감정짤 밈팩 — GIPHY 검색 결과에서 감정별 리액션 짤(mp4)을 가져온다.

    py tools/meme_pack/giphy.py <작업폴더> [--per 20]

GIPHY 짤은 이미 1~4초로 잘린 리액션이라 자를 게 적다(소리 없음·가로 480px 안팎 — 화질은 유튜브 원본보다 낮다).
결과: raw/gph_<id>.mp4 + sheets/thumbs/gph_<id>.jpg + extra_giphy.json (뷰어 serve.py 가 같이 싣는다)
이미 받은 것은 다시 안 받는다. 감정 목록·사이트 검색어의 주인은 search.py(EMOTIONS·SITE_QUERIES) — 여기서 다시 적지 않는다.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS, SITE_QUERIES as QUERIES  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
MIN_SEC, MIN_H = 1.0, 200


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search(query):
    """검색 페이지 → [(gif id, 제목 슬러그)] (페이지에 나온 순서대로)."""
    html = get("https://giphy.com/search/" + urllib.parse.quote(query.replace(" ", "-"))).decode("utf-8", "replace")
    slugs = {m.group(2): m.group(1) for m in re.finditer(r"/gifs/([A-Za-z0-9-]*?)-?([A-Za-z0-9]{10,})[\"\\?]", html)}
    ids = []
    for m in re.finditer(r"giphy\.com/media/[^/\"\\]+/([A-Za-z0-9]{10,})/", html):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return [(i, slugs.get(i, "").replace("-", " ")) for i in ids]


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    j = json.loads(r.stdout)
    return float(j["format"]["duration"]), int(j["streams"][0]["width"]), int(j["streams"][0]["height"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--per", type=int, default=20)
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    raw, thumbs = os.path.join(work, "raw"), os.path.join(work, "sheets", "thumbs")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(thumbs, exist_ok=True)
    out_path = os.path.join(work, "extra_giphy.json")
    rows = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else []
    have = {r["id"] for r in rows}
    skipped = {"짧음/작음": 0, "받기 실패": 0}
    for emo in EMOTIONS:
        got = sum(1 for r in rows if r["emotion"] == emo)
        for q in QUERIES.get(emo, []):
            try:
                found = search(q)
            except OSError as e:
                print(f"[검색 실패] {q}: {e}", file=sys.stderr)
                continue
            for gid, slug in found:
                cid = f"gph_{gid}"
                if got >= a.per:
                    break
                if cid in have:
                    continue
                path = os.path.join(raw, f"{cid}.mp4")
                try:
                    if not os.path.exists(path):
                        data = get(f"https://media.giphy.com/media/{gid}/giphy.mp4")
                        with open(path, "wb") as f:
                            f.write(data)
                        time.sleep(0.3)
                    dur, w, h = probe(path)
                except Exception as e:  # 받기·판독 실패는 세어 두고 넘어간다
                    skipped["받기 실패"] += 1
                    print(f"[실패] {gid}: {e!r}"[:160], file=sys.stderr)
                    if os.path.exists(path):
                        os.remove(path)
                    continue
                have.add(cid)
                if dur < MIN_SEC or h < MIN_H:
                    skipped["짧음/작음"] += 1
                    os.remove(path)
                    continue
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.3:.2f}", "-i", path, "-frames:v", "1",
                                "-vf", "scale=-2:260", os.path.join(thumbs, f"{cid}.jpg")])
                rows.append({"id": cid, "title": f"[GIPHY] {slug or q}", "emotion": emo, "duration": round(dur, 2),
                             "w": w, "h": h, "source": f"https://giphy.com/gifs/{gid}", "views": 0, "query": q})
                got += 1
        print(f"{emo}: {got}개")
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, out_path)
    print(f"합계 {len(rows)}개 · 건너뜀 {skipped}")


if __name__ == "__main__":
    main()
