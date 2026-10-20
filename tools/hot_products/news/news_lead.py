"""검증 — 뉴스가 앞선 신호인가. 터진 상품: 올라오기 전 30일 기사 수 / 베스트셀러 후보: 오늘 기준 전 30일 기사 수.
네이버 뉴스 API 최신순으로 최대 300건까지 거슬러 세고, 300건으로도 창 시작에 못 닿으면 '300+'로 본다.
출력 work/news_lead.json"""
import datetime, email.utils, json, os, statistics, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "..", "work")
env = {}
for line in open(os.path.join(HERE, "..", "..", "..", ".env"), encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
H = {"X-Naver-Client-Id": env["NAVER_CLIENT_ID"], "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"]}
cache = {}
def dates(kw):
    if kw in cache: return cache[kw]
    out = []
    for start in (1, 101, 201):
        u = "https://openapi.naver.com/v1/search/news.json?" + urllib.parse.urlencode({"query": f'"{kw}"', "display": 100, "start": start, "sort": "date"})
        try: items = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20))["items"]
        except Exception: time.sleep(1); continue
        out += [email.utils.parsedate_to_datetime(i["pubDate"]).date() for i in items]
        if len(items) < 100: break
    cache[kw] = out; return out
def count(kw, at):
    d = dates(kw); lo = at - datetime.timedelta(days=30)
    n = sum(1 for x in d if lo <= x < at)
    if len(d) >= 300 and min(d) >= lo: n = 300             # 300건으로 창 시작까지 못 내려감 = 300+
    return n
dump = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
meta = {x.get("shortcode"): x for v in dump.values() for x in v}
def day(t):
    try: return datetime.date.fromtimestamp(float(t)) if str(t).replace(".", "").isdigit() else datetime.date.fromisoformat(str(t)[:10])
    except Exception: return None
hits = {}
for r in json.load(open(os.path.join(WORK, "hits_products.json"), encoding="utf-8")):
    if not (r.get("is_product") and r.get("kw")): continue
    m = meta.get(r["shortcode"], {}); d = day(m.get("upload_ts") or m.get("first_seen"))
    k = r["kw"].split(",")[0].strip()
    if d and (k not in hits or d < hits[k]): hits[k] = d            # 키워드별 첫 히트 날짜
today = datetime.date.today()
cands = json.load(open(os.path.join(WORK, "kws.json"), encoding="utf-8"))
res = {"hits": {}, "cands": {}}
for i, (k, d) in enumerate(hits.items()):
    res["hits"][k] = count(k, d)
    if i % 50 == 0: print("터진", i, len(hits), flush=True)
for i, k in enumerate(cands):
    res["cands"][k] = count(k, today)
    if i % 50 == 0: print("후보", i, len(cands), flush=True)
json.dump(res, open(os.path.join(WORK, "news_lead.json"), "w", encoding="utf-8"), ensure_ascii=False)
for name, v in (("터진 상품(올라오기 전 30일)", list(res["hits"].values())), ("베스트셀러 후보(최근 30일)", list(res["cands"].values()))):
    n = len(v); f = lambda t: round(100 * sum(1 for x in v if x >= t) / n)
    print(f"{name} {n}개: 기사 0건 {100 - f(1)}% / 1건+ {f(1)}% / 5건+ {f(5)}% / 20건+ {f(20)}% / 중앙값 {statistics.median(v)}")
