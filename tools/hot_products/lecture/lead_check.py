"""시점 맞춘 검증 — 터진 쇼츠가 올라오기 '전'에 네이버 검색이 오르고 있었나.
각 터진 상품: 올라온 주 기준 [-4,0)주 평균 vs [-12,-4)주 평균 → 사전 상승률.
비교 기준(base): 같은 키워드의 아무 4주 구간 상승률 분포. 사전 상승이 base 보다 잦으면 '앞선 신호'다.
입력 work/hits_products.json + work/hits_dump.json(올라온 시각) · 출력 work/lead_check.json"""
import datetime, json, os, re, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "..", "work")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
env = gkeys.env()
dump = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
ts = {x.get("shortcode"): (x.get("upload_ts") or x.get("first_seen")) for v in dump.values() for x in v}
hits = [r for r in json.load(open(os.path.join(WORK, "hits_products.json"), encoding="utf-8")) if r.get("is_product") and r.get("kw")]
def to_date(t):
    if not t: return None
    try: return datetime.date.fromtimestamp(float(t)) if str(t).replace(".", "").isdigit() else datetime.date.fromisoformat(str(t)[:10])
    except Exception: return None
rows = []
for r in hits:
    d = to_date(ts.get(r["shortcode"]))
    if d and d > datetime.date(2023, 6, 1): rows.append((r["kw"].split(",")[0].strip(), d, r))
kws = sorted({k for k, _, _ in rows})
print("날짜 있는 터진 상품", len(rows), "키워드", len(kws))
end = datetime.date.today() - datetime.timedelta(days=1); start = end - datetime.timedelta(days=365 * 3)
series = {}
for i in range(0, len(kws), 5):
    b = kws[i:i + 5]
    body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week", "keywordGroups": [{"groupName": k, "keywords": [k]} for k in b]}
    for _ in range(3):
        try:
            res = gkeys.datalab(body)
            for g in res: series[g["title"]] = [(datetime.date.fromisoformat(x["period"]), x["ratio"]) for x in g["data"]]
            break
        except Exception as e:
            err = str(e)[:60]
def rise(s, at):
    a = [v for d, v in s if -4 <= (d - at).days // 7 < 0]; b = [v for d, v in s if -12 <= (d - at).days // 7 < -4]
    if len(a) < 3 or len(b) < 6 or sum(b) == 0: return None
    return (sum(a) / len(a)) / (sum(b) / len(b)) - 1
pre, base = [], []
for k, d, r in rows:
    s = series.get(k)
    if not s or len(s) < 60: continue
    x = rise(s, d)
    if x is not None: pre.append((x, k, d, r.get("views")))
    for w in range(12, len(s) - 1, 4):                       # 같은 키워드의 아무 시점
        y = rise(s, s[w][0])
        if y is not None: base.append(y)
def share(v, t): return round(100 * sum(1 for x in v if x > t) / len(v)) if v else None
out = {"n_hits": len(pre), "n_base": len(base),
       "pre_rise_gt20": share([x for x, *_ in pre], 0.2), "base_rise_gt20": share(base, 0.2),
       "pre_rise_gt50": share([x for x, *_ in pre], 0.5), "base_rise_gt50": share(base, 0.5),
       "top": [{"kw": k, "date": str(d), "views": v, "pre_rise_pct": round(x * 100)} for x, k, d, v in sorted(pre, reverse=True)[:20]]}
json.dump(out, open(os.path.join(WORK, "lead_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"터진 상품 {out['n_hits']}개: 올라오기 전 4주 검색 +20%↑ {out['pre_rise_gt20']}% (아무 시점 {out['base_rise_gt20']}%) / +50%↑ {out['pre_rise_gt50']}% (아무 시점 {out['base_rise_gt50']}%)")
for t in out["top"][:10]: print("  ", t)
