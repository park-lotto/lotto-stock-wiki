# Pexels 무료 실사 영상 받기 — shots.py 의 stock 샷(q)과 배경(bg_q)을 assets/stock/sNNN.mp4 로 저장
# 키: 환경변수 PEXELS_API_KEY 또는 ~/.volcano/keys/pexels (파일 첫 줄)
# 사용: python -I stock.py [--force]
import os, sys, json, urllib.request, urllib.parse, importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
key = os.environ.get("PEXELS_API_KEY") or (open(os.path.expanduser("~/.volcano/keys/pexels"), encoding="utf-8").read().strip()
                                          if os.path.exists(os.path.expanduser("~/.volcano/keys/pexels")) else "")
if not key: print("Pexels 키가 없습니다 (PEXELS_API_KEY 또는 ~/.volcano/keys/pexels)"); sys.exit(1)
spec = importlib.util.spec_from_file_location("shots", os.path.join(HERE, "shots.py")); sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
OUT = os.path.join(HERE, "assets", "stock"); os.makedirs(OUT, exist_ok=True)
used = set()
def search(q):
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": q, "orientation": "landscape", "size": "medium", "per_page": 15})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["videos"]
log = []
for s in sh.S:
    q = s.get("q") or s.get("bg_q")
    if not q: continue
    name = f"s{s['s'][0]:03d}.mp4"; path = os.path.join(OUT, name)
    if os.path.exists(path) and "--force" not in sys.argv: continue
    try:
        vids = [v for v in search(q) if v["id"] not in used and v["duration"] >= 5]
        if not vids: print(name, "검색 결과 없음:", q); continue
        v = vids[0]; used.add(v["id"])
        files = sorted([f for f in v["video_files"] if f.get("width") and 1280 <= f["width"] <= 1920 and f["file_type"] == "video/mp4"], key=lambda f: -f["width"])
        if not files: files = sorted(v["video_files"], key=lambda f: -(f.get("width") or 0))
        urllib.request.urlretrieve(files[0]["link"], path)
        log.append(dict(file=name, query=q, pexels_id=v["id"], url=v["url"], author=v["user"]["name"]))
        print(name, "ok", q, v["url"])
    except Exception as e:
        print(name, "실패", q, e)
json.dump(log, open(os.path.join(OUT, "pexels_credits.json"), "a", encoding="utf-8"), ensure_ascii=False, indent=1)
