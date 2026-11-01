# 실사 영상 받기 — shots.py 의 stock 샷(q)과 배경(bg_q)을 assets/stock/sNNN.mp4 로 저장
# 순서: Pixabay(키 ~/.volcano/keys/pixabay 또는 PIXABAY_API_KEY) → Wikimedia Commons(키 불필요, CC BY 류는 설명란 표기 필수)
# Pexels 는 2026-11 새 키 발급이 중단돼 뺐다. 출처는 assets/stock/credits.md 에 쌓인다.
# 사용: 작업 폴더에서 python -X utf8 <경로>/stock.py [--force]   (LONGFORM_WORK 로 작업 폴더 지정 가능)
import importlib.util, json, os, re, subprocess, sys, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
WORK = os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd())
OUT = os.path.join(WORK, "assets", "stock"); os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (longform-preset; contact parklotto12@gmail.com)"
keyfile = os.path.expanduser("~/.volcano/keys/pixabay")
PIXABAY = os.environ.get("PIXABAY_API_KEY") or (open(keyfile, encoding="utf-8").read().strip() if os.path.exists(keyfile) else "")
MIN_W, MIN_SEC, MAX_MB = 1280, 5, 250
BAD_LICENSE = re.compile(r"\bNC\b|\bND\b|fair use", re.I)
used = set()


def get_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read())


def pixabay(q):
    if not PIXABAY: return None
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": PIXABAY, "q": q, "per_page": 15, "safesearch": "true"})
    for h in get_json(url)["hits"]:
        vid = f"pixabay:{h['id']}"
        if vid in used or h["duration"] < MIN_SEC: continue
        for size in ("large", "medium"):
            f = h["videos"].get(size) or {}
            if f.get("url") and f.get("width", 0) >= MIN_W:
                return dict(id=vid, url=f["url"], width=f["width"], page=h["pageURL"], author=h.get("user", ""), license="Pixabay Content License")
    return None


def commons(q):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:video {q}", "gsrnamespace": 6, "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist"})
    pages = (get_json(url).get("query") or {}).get("pages") or {}
    for p in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        i = (p.get("imageinfo") or [{}])[0]; m = i.get("extmetadata") or {}
        lic = (m.get("LicenseShortName") or {}).get("value", "")
        vid = f"commons:{p['pageid']}"
        if vid in used or not lic or BAD_LICENSE.search(lic): continue
        if i.get("width", 0) < MIN_W or (i.get("duration") or 0) < MIN_SEC or i.get("size", 1e12) > MAX_MB * 1e6: continue
        author = re.sub(r"<[^>]+>", "", (m.get("Artist") or {}).get("value", "")).strip()
        return dict(id=vid, url=i["url"], width=i["width"], page=i.get("descriptionurl", ""), author=author, license=lic)
    return None


def fetch(v, path):
    tmp = path + ".dl"
    req = urllib.request.Request(v["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
        f.write(r.read())
    # 소리는 버리고 1920 폭·앞 20초만(컷은 3~11초) — webm 도 mp4 로 맞춘다
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-t", "20", "-an", "-vf", "scale=1920:-2",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", path], check=True)
    os.remove(tmp)


def main():
    spec = importlib.util.spec_from_file_location("shots", os.path.join(WORK, "shots.py"))
    sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
    if not PIXABAY: print("[경고] Pixabay 키 없음 — Wikimedia 만 찾는다", flush=True)
    miss = []
    with open(os.path.join(OUT, "credits.md"), "a", encoding="utf-8") as cred:
        for s in sh.S:
            q = s.get("q") or s.get("bg_q")
            if not q: continue
            name = f"s{s['s'][0]:03d}.mp4"; path = os.path.join(OUT, name)
            if os.path.exists(path) and "--force" not in sys.argv: continue
            v = None
            for find in (pixabay, commons):
                try:
                    v = find(q)
                except Exception as e:
                    print(name, find.__name__, "실패", q, e, flush=True)
                if v: break
            if not v: miss.append((name, q)); print(name, "못 찾음:", q, flush=True); continue
            used.add(v["id"]); fetch(v, path)
            cred.write(f"- {name} · {q} · {v['license']} · {v['author']} · {v['page']}\n"); cred.flush()
            print(name, "ok", v["id"], v["license"], v["width"], flush=True)
    print(f"못 찾은 샷 {len(miss)}개 — 검색어를 바꾸거나 AI 그림으로 대신한다" if miss else "전부 받음")


if __name__ == "__main__":
    main()
