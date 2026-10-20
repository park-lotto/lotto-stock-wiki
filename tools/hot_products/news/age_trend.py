"""연령별 검색 — 데이터랩 검색어트렌드 연령 필터로 키워드가 '아이·10대' 또는 '50대+' 쪽에서 뜨는지 잰다.
같은 요청에 기준어(선물)를 넣어 연령 간 비교가 되게 한다: 쏠림 = (키워드/기준어)_연령 ÷ (키워드/기준어)_전체.
상승 = 최근 4주 평균 ÷ 그 전 8주 평균 - 1 (연령별).
실행: py -I age_trend.py [키워드 ...]  (없으면 news_hot.json 의 쇼츠 가능 키워드) → age_trend.json"""
import datetime, json, os, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
env = gkeys.env()
H = {"X-Naver-Client-Id": env["NAVER_CLIENT_ID"], "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"], "Content-Type": "application/json"}
ANCHOR = "선물"
AGES = {"전체": None, "아이10대": ["1", "2"], "5060": ["9", "10", "11"]}   # 데이터랩 하루 1,000회 한도 — 화면에 쓰는 갈래만   # 1=0~12 2=13~18 … 9=50~54 10=55~59 11=60+
kws = (json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) == 2 and sys.argv[1].endswith(".json") else sys.argv[1:]) \
      or [a["kw"] for a in json.load(open(os.path.join(HERE, "news_hot.json"), encoding="utf-8"))["items"] if a["shortsable"]]   # 목록 파일(.json)도 받는다(띄어쓴 키워드가 안 갈라지게)
kws = list(dict.fromkeys(k for k in kws if k and k != ANCHOR))
end = datetime.date.today() - datetime.timedelta(days=1); start = end - datetime.timedelta(weeks=20)
def call(group, ages):
    body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week",
            "keywordGroups": [{"groupName": ANCHOR, "keywords": [ANCHOR]}] + [{"groupName": k, "keywords": [k]} for k in group]}
    if ages: body["ages"] = ages
    for _ in range(3):
        try:
            res = gkeys.datalab(body)          # 데이터랩은 gkeys 한 곳에서(앱 키 순환)
            return {g["title"]: [x["ratio"] for x in g["data"]] for g in res}
        except Exception as e:
            err = str(e); time.sleep(2)
    print("ERR", group[:2], err[:80]); return {}
def avg(v): return sum(v) / len(v) if v else 0
out = {}
for i in range(0, len(kws), 4):
    g = kws[i:i + 4]; per = {name: call(g, ages) for name, ages in AGES.items()}
    for k in g:
        row = {}
        for name, s in per.items():
            v, a = s.get(k) or [], s.get(ANCHOR) or []
            if len(v) < 12: continue
            rec, prev = avg(v[-4:]), avg(v[-12:-4])
            row[name] = {"level": round(avg(v[-4:]) / max(avg(a[-4:]), 1e-6), 4),           # 기준어 대비 최근 크기
                         "rise": round(rec / prev - 1, 2) if prev > 0 else (9.99 if rec > 0 else None)}
        base = (row.get("전체") or {}).get("level")
        for name in ("아이10대", "5060"):
            if name in row and base: row[name]["skew"] = round(row[name]["level"] / base, 2)
        out[k] = row
    print(f"{min(i + 4, len(kws))}/{len(kws)}", flush=True)
json.dump(out, open(os.path.join(HERE, "age_trend.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def show(name):
    rows = [(k, r[name]) for k, r in out.items() if name in r and r[name].get("skew")]
    rows.sort(key=lambda x: -x[1]["skew"])
    print(f"\n== {name} 쪽으로 쏠린 키워드(쏠림 = 전체 대비 배수, 상승 = 최근4주/전8주)")
    for k, x in rows[:15]: print(f"  {k:<18} 쏠림 {x['skew']:>5}  상승 {x['rise']}")
for n in ("아이10대", "5060"): show(n)
