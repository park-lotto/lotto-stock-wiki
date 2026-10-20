"""검증 — '1년 전엔 없던 키워드(신규)'가 터진 상품을 가르나. (강의: 아이템스카우트 '1년 전 같은 기간에 없던' 필터)
지금 = 기준일 직전 4주 평균, 작년 = 같은 4주의 52주 전 평균(데이터랩 주간). 신규 = 작년이 지금의 15% 미만, 전년비 2배+.
터진 상품은 첫 히트 날짜 기준, 베스트셀러 후보는 오늘 기준. 출력 work/novelty_check.json"""
import datetime, json, os, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "..", "work")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
env = gkeys.env()
end = datetime.date.today() - datetime.timedelta(days=1); start = end - datetime.timedelta(days=365 * 2 + 60)
def series(kws):
    out = {}
    for i in range(0, len(kws), 5):
        body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week", "keywordGroups": [{"groupName": k, "keywords": [k]} for k in kws[i:i + 5]]}
        for _ in range(3):
            try:
                res = gkeys.datalab(body)
                for g in res: out[g["title"]] = [(datetime.date.fromisoformat(x["period"]), x["ratio"]) for x in g["data"]]
                break
            except Exception: time.sleep(2)
    return out
def yoy(s, at):
    now = [v for d, v in s if -4 <= (d - at).days // 7 < 0]
    ly = [v for d, v in s if -56 <= (d - at).days // 7 < -52]
    if len(now) < 3 or len(ly) < 3: return None
    n, l = sum(now) / len(now), sum(ly) / len(ly)
    return None if n == 0 else l / n          # 작년/지금 (작을수록 새것)
dump = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
meta = {x.get("shortcode"): x for v in dump.values() for x in v}
def day(t):
    try: return datetime.date.fromtimestamp(float(t)) if str(t).replace(".", "").isdigit() else datetime.date.fromisoformat(str(t)[:10])
    except Exception: return None
hits = {}
for r in json.load(open(os.path.join(WORK, "hits_products.json"), encoding="utf-8")):
    if not (r.get("is_product") and r.get("kw")): continue
    m = meta.get(r["shortcode"], {}); d = day(m.get("upload_ts") or m.get("first_seen")); k = r["kw"].split(",")[0].strip()
    if d and (k not in hits or d < hits[k]): hits[k] = d
cands = json.load(open(os.path.join(WORK, "kws.json"), encoding="utf-8"))
sh, sc = series(list(hits)), series(cands)
today = datetime.date.today()
R = {"hits": {k: yoy(sh[k], d) for k, d in hits.items() if k in sh}, "cands": {k: yoy(sc[k], today) for k in cands if k in sc}}
json.dump(R, open(os.path.join(WORK, "novelty_check.json"), "w", encoding="utf-8"), ensure_ascii=False)
for name, v in (("터진 상품", R["hits"]), ("베스트셀러 후보", R["cands"])):
    x = [r for r in v.values() if r is not None]; n = len(x)
    print(f"{name} {n}개: 신규(작년<지금의15%) {round(100*sum(1 for r in x if r < 0.15)/n)}% / 전년비 2배+ {round(100*sum(1 for r in x if r < 0.5)/n)}% / 작년보다 줄어듦 {round(100*sum(1 for r in x if r > 1)/n)}%")
new = sorted([(r, k) for k, r in R["hits"].items() if r is not None and r < 0.15])
print("터진 신규 키워드 예:", [k for _, k in new[:25]])
