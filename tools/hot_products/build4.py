"""v4 시안 데이터 — 키워드(상품) 한 줄에 우리가 잰 신호를 모두 붙인다. 판정 기준은 lecture/catalog_tx.md 에서 검증된 것만.
입력: work/v3_data.json(사이트 베스트+쇼츠 분류) · work/enrich.json·hits/enrich.json(월검색·4주추세) · work/season.json·hits/season.json(곧 뜰 시즌)
      work/novelty_check.json(전년비) · work/hits_products.json+hits_dump.json(터진 쇼츠) · news/news_rank.json(뉴스 수요근거) · news/age_trend.json(연령 쏠림)
      work/series.json(데이터랩 52주, 없으면 받아서 저장)
출력: work/v4_data.json  →  build_html4.py 가 out/인기상품랭킹_시안_v4.html 로 굽는다"""
import datetime, json, os, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "work"); N = os.path.join(HERE, "news")
sys.path.insert(0, HERE)
import gkeys

def load(p, d=None):
    p = os.path.join(HERE, p)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

v3 = load("work/day_data.json") or load("work/v3_data.json", [])   # 하루 비교(build_day)가 있으면 그것, 없으면 10-19 시안 데이터
enr = {**load("work/enrich.json", {}), **load("work/hits/enrich.json", {}), **load("work/news/enrich.json", {})}   # news = 뉴스·기타 행(검색수 없던 것)
season = {**load("work/season.json", {}), **load("work/hits/season.json", {}), **load("work/news/season.json", {})}
nov = load("work/novelty_check.json", {"hits": {}, "cands": {}}); yoy = {**nov["cands"], **nov["hits"]}
age = load("news/age_trend.json", {})
nr = load("news/news_rank.json", {"items": []})["items"]
dump = load("work/hits_dump.json", {}); meta = {x.get("shortcode"): x for v in dump.values() for x in v}

def day(t):
    try: return datetime.date.fromtimestamp(float(t)) if str(t).replace(".", "").isdigit() else datetime.date.fromisoformat(str(t)[:10])
    except Exception: return None

rows = {}
def row(kw):
    return rows.setdefault(kw, {"kw": kw, "sites": [], "img": "", "price": "", "url": "", "cat": "", "wow": None,
                                "hits": [], "news": [], "src": set()})
# 1) 사이트 베스트(쇼츠 가능만)
for r in v3:
    if not r.get("kw") or r.get("cat") == "제외": continue
    x = row(r["kw"]); x["src"].add("best")
    x["sites"].append({"site": r["site"], "list": r.get("list"), "rank": r.get("rank"), "title": r.get("title"), "url": r.get("url"),
                       "tags": r.get("tags") or [], "speed": (r.get("sc") or {}).get("speed"), "new": r.get("new"), "rank_up": r.get("rank_up")})   # speed = 같은 사이트 안 판매 속도 백분위(build3)
    if not x["img"]: x.update(img=r.get("img") or "", price=r.get("price") or "", url=r.get("url") or "", cat=r.get("cat") or "", wow=r.get("wow"))
# 블라인드 평가(work/blind_scores.json): 터진 상품 키워드의 분류·막연함·신박함 — 식품·막연한 키워드는 화면에서 뺀다
_items = dict(l.split("	", 1) for l in open(os.path.join(W, "blind_items.tsv"), encoding="utf-8").read().splitlines()) if os.path.exists(os.path.join(W, "blind_items.tsv")) else {}
_sc = load("work/blind_scores.json", {})
blind = {_items[i]: v for i, v in _sc.items() if i in _items}
CAT = {"홈": "홈템", "주방": "홈템", "뷰티": "뷰티", "디지털": "디지털템", "차량": "차량템", "반려": "반려템", "육아": "육아템", "취미": "장비템", "건강": "홈템", "패션": "패션", "기타": "기타"}
# 2) 터진 쇼츠
for h in load("work/hits_products.json", []):
    if not (h.get("is_product") and h.get("kw")): continue
    m = meta.get(h["shortcode"], {}); d = day(m.get("upload_ts") or m.get("first_seen"))
    k = h["kw"].split(",")[0].strip(); bl = blind.get(k, {})
    if bl.get("generic") or bl.get("cat") in ("식품", "패션"): continue      # 막연한 키워드·식품·옷은 쇼츠 상품이 아니다(사장님 기준)
    x = row(k); x["src"].add("hit")
    if not x["cat"] and bl: x["cat"] = CAT.get(bl.get("cat"), ""); x["wow"] = bl.get("wow")
    x["hits"].append({"date": str(d) if d else "", "views": m.get("views") or h.get("views") or 0, "comments": m.get("comments") or 0,
                      "url": m.get("url") or "", "user": m.get("username") or "", "platform": h.get("platform")})
# 3) 뉴스 — 수요 근거 + 쇼츠 가능만
for a in nr:
    if not (a.get("demand") and a.get("shorts") and len((a.get("evidence") or "").strip()) >= 2): continue   # 근거 문구가 실제로 있는 것만
    x = row(a["kw_clean"]); x["src"].add("news")
    x["news"] += [{"t": l["t"], "u": l["u"], "d": l["d"], "ev": a.get("evidence", "")} for l in a["links"][:2]]

# 데이터랩 52주 시리즈(행 안 추이선) — 받아 둔 것은 다시 받지 않는다
SER = os.path.join(W, "series.json"); series = load("work/series.json", {})
end = datetime.date.today() - datetime.timedelta(days=1); start = end - datetime.timedelta(weeks=52)
need = [k for k in rows if k not in series]; ser_fail = 0
for i in range(0, len(need), 5):
    body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week", "keywordGroups": [{"groupName": k, "keywords": [k]} for k in need[i:i + 5]]}
    for _ in range(3):
        try:
            res = gkeys.datalab(body)          # 데이터랩은 gkeys 한 곳에서(앱 키 순환)
            for g in res: series[g["title"]] = [round(p["ratio"], 1) for p in g["data"]]
            break
        except Exception as e:
            err = str(e)[:80]; time.sleep(2)
    else:
        print("★시리즈 실패", need[i:i + 5][:2], err); ser_fail += 1
    if i % 100 == 0: print("시리즈", i, "/", len(need), flush=True)
json.dump(series, open(SER, "w", encoding="utf-8"), ensure_ascii=False)

today = datetime.date.today(); out = []
for k, x in rows.items():
    e = enr.get(k, {}); s = season.get(k, {}); a = age.get(k, {}); y = yoy.get(k)
    hits = sorted(x["hits"], key=lambda h: h["date"], reverse=True)
    best = max(x["sites"], key=lambda q: q.get("speed") or -1, default=None)
    last = max((h["date"] for h in hits if h["date"]), default="")
    days_since = (today - datetime.date.fromisoformat(last)).days if last else None
    out.append({
        "kw": k, "img": x["img"], "price": x["price"], "url": x["url"], "cat": x["cat"], "wow": x["wow"],
        "src": sorted(x["src"]), "sites": x["sites"][:4], "site_set": sorted({q["site"] for q in x["sites"]}),
        "sell": best.get("speed") if best else None, "sell_site": best["site"] if best else "", "sell_tags": (best or {}).get("tags", [])[:2], "news": x["news"][:3],
        "search": e.get("search_month"), "comp": e.get("comp"), "trend": e.get("trend_up"), "vs_peak": e.get("vs_peak"),
        "yt_med": e.get("yt_views_med"),
        "season_up": s.get("season_up"), "peak_ly": s.get("peak_ly"),
        "yoy": round(1 / y, 1) if y else None,                       # 전년비 배수(지금/작년)
        "kids": (a.get("아이10대") or {}).get("skew"), "senior": (a.get("5060") or {}).get("skew"),
        "n_hits": len(hits), "hit_max": max((h["views"] for h in hits), default=0), "hit_last": last, "hit_days": days_since,
        "hits": hits[:6], "ser": series.get(k, []),
    })
json.dump({"built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "rows": out}, open(os.path.join(W, "v4_data.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("행", len(out), "| 베스트", sum("best" in r["src"] for r in out), "터진", sum("hit" in r["src"] for r in out), "뉴스", sum("news" in r["src"] for r in out),
      "| 시리즈 있음", sum(bool(r["ser"]) for r in out), f"| ★시리즈 실패 묶음 {ser_fail}" if ser_fail else "")
