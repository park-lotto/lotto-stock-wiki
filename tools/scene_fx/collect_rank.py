# -*- coding: utf-8 -*-
"""레퍼런스랭킹(서버 store.hits_since — 화면 /api/reference?days=N&min_views=M 과 같은 함수)에서
잘되는 썰 쇼핑 채널 영상을 뽑아 장면 효과 실측 목록에 계속 쌓는다 (관제 124).

기간·조회수: 7일 10만+ / 14일 10만+ / 30일 100만+ (사장님 2026-10-05 "주간 10만·100만, 2주·한 달 잘되는 채널 위주로 계속 수집").
채널은 CHANNELS(썰 쇼핑 채널 이름)로 거른다 — 레시피·연예인·메이크업·애니는 효과 패턴이 달라 뺀다.
이미 받은 영상은 건너뛴다(목록 bench_rank.json 에 누적).

사용: py tools/scene_fx/collect_rank.py --dl <영상폴더> [--per 4]
"""
import argparse, json, os, re, subprocess, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
LIST = os.path.join(HERE, "bench_rank.json")
KEY = os.path.expanduser(r"~\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem")
HOST = "ubuntu@shoppingshorts.duckdns.org"

# 썰 쇼핑 채널(랭킹 상위에서 사람이 고른 것 — 2026-10-05). 새 채널은 여기 더한다.
CHANNELS = ["만물상점", "5초쇼핑", "눌러", "고수의살림", "행님쇼핑", "재미쏙", "짤컷", "찐템요약", "이븐쇼핑",
            "공가미", "잇템집사(ittemZipsa)", "쇼핑스토리", "살림빨", "쓸모있어", "집꾸", "살림아리",
            "살림킹왕짱", "인생갓템", "긍정템", "살림장착"]

REMOTE = r'''
import sys,json,re,sqlite3
sys.path.insert(0,'/home/ubuntu/lotto-stock-wiki')
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH
s=Store(DB_PATH)
c=sqlite3.connect('/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db')
def vid(u):
    m=re.search(r'(?:shorts/|v=)([\w-]{11})',u or ''); return m.group(1) if m else None
names={}
for u,n in c.execute("select url,channel_name from source_enrichment where platform='youtube'"):
    v=vid(u)
    if v: names[v]=n
out=[]
for days,mv in ((7,100000),(14,100000),(30,1000000)):
    for i in s.hits_since(days,min_comments=0,platform='youtube',min_views=mv):
        v=vid(i.get('url'))
        if v: out.append({"id":v,"channel":names.get(v) or i.get('name') or i.get('username'),
                          "views":int(i.get('views') or 0),"window":f"{days}d_{mv}","caption":(i.get('caption') or '')[:80]})
print(json.dumps(out,ensure_ascii=False))
'''


def fetch():
    r = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-i", KEY, HOST,
                        "cd /home/ubuntu/lotto-stock-wiki && python3 -"],
                       input=REMOTE, capture_output=True, text=True, encoding="utf-8", timeout=300)
    line = [l for l in r.stdout.splitlines() if l.startswith("[")]
    if not line:
        raise SystemExit("랭킹 조회 실패: " + r.stderr[-500:])
    return json.loads(line[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dl", required=True)
    ap.add_argument("--per", type=int, default=4, help="채널당 최대 편수(조회수 순)")
    a = ap.parse_args()
    have = json.load(open(LIST, encoding="utf-8")) if os.path.exists(LIST) else []
    known = {x["id"] for x in have}
    rows = fetch()
    best = {}
    for r in rows:
        if r["channel"] not in CHANNELS:
            continue
        if r["id"] not in best or r["views"] > best[r["id"]]["views"]:
            best[r["id"]] = r
    by_ch = {}
    for r in sorted(best.values(), key=lambda x: -x["views"]):
        by_ch.setdefault(r["channel"], []).append(r)
    added = 0
    for ch, rs in by_ch.items():
        cnt = sum(1 for x in have if x["channel"] == ch)
        for r in rs:
            if cnt >= a.per:
                break
            if r["id"] in known:
                continue
            p = os.path.join(a.dl, r["id"] + ".mp4")
            if not os.path.exists(p):
                subprocess.run(["yt-dlp", "-q", "--no-warnings", "--extractor-args", "youtube:player_client=android",
                                "-f", "bv*[height<=1920][ext=mp4]+ba/b[ext=mp4]/b", "--merge-output-format", "mp4",
                                "-o", p, "https://www.youtube.com/shorts/" + r["id"]], timeout=300)
            if os.path.exists(p):
                have.append(r); known.add(r["id"]); cnt += 1; added += 1
                print("받음", ch, r["id"], r["views"], r["window"])
    json.dump(have, open(LIST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"새로 {added}편 · 누적 {len(have)}편 · 채널 {len({x['channel'] for x in have})}개")


if __name__ == "__main__":
    main()
