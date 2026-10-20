"""시즌 예보(실행: 키워드 폴더에서 py -I <경로>/season.py — kws.json·enrich.json 을 읽어 season.json) — 데이터랩 검색어트렌드 3년 주간값으로 '작년 이맘때 → 8주 뒤' 상승률과 작년 피크 시점을 잰다."""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gkeys                      # 데이터랩 호출의 유일한 곳
sys.stdout.reconfigure(encoding="utf-8")
today = datetime.date.today(); end = today - datetime.timedelta(days=1); start = end - datetime.timedelta(days=365 * 3)
kws = json.load(open("kws.json", encoding="utf-8"))
out = {}
for i in range(0, len(kws), 5):
    b = kws[i:i + 5]
    body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week", "keywordGroups": [{"groupName": k, "keywords": [k]} for k in b]}
    try:
        res = gkeys.datalab(body, timeout=20)
    except Exception as e:
        print("ERR", b[0], str(e)[:80]); continue
    for g in res:
        d = {x["period"]: x["ratio"] for x in g["data"]}
        if len(d) < 100: continue
        def avg(a, z):  # 작년 같은 날 기준 a~z주 평균
            v = [r for p, r in d.items() if a <= (datetime.date.fromisoformat(p) - (today - datetime.timedelta(days=364))).days // 7 < z]
            return sum(v) / len(v) if v else None
        now_ly, ahead_ly = avg(-2, 1), avg(3, 9)            # 작년: 지금 무렵 vs 3~8주 뒤
        now = sum(list(d.values())[-3:]) / 3
        ly = {p: r for p, r in d.items() if p.startswith(str(today.year - 1)) or p.startswith(str(today.year)) and p < str(today - datetime.timedelta(days=300))}
        peak_p = max(ly, key=ly.get) if ly else None
        out[g["title"]] = {"season_up": round((ahead_ly / now_ly - 1) * 100) if (now_ly and ahead_ly is not None) else None,
                           "now_vs_ly": round((now / now_ly - 1) * 100) if (now_ly and ahead_ly is not None) else None,
                           "peak_ly": peak_p, "peak_ratio": round(max(d.values()) and (max(ly.values()) / max(d.values())) * 100) if ly else None}
json.dump(out, open("season.json", "w", encoding="utf-8"), ensure_ascii=False)
EN = json.load(open("enrich.json", encoding="utf-8"))
rows = [(v["season_up"], k, v["now_vs_ly"], v["peak_ly"], EN.get(k, {}).get("search_month")) for k, v in out.items() if v["season_up"] is not None and (EN.get(k, {}).get("search_month") or 0) >= 1000]
print("분석", len(out), "| 월검색 1천+ 중 앞으로 8주 시즌 상승 상위")
for r in sorted(rows, reverse=True)[:20]:
    print(f"  작년 기준 3~8주 뒤 +{r[0]}%  {r[1]}  (월검색 {r[4]:,}, 작년 대비 지금 {r[2]:+}%, 작년 피크 {r[3]})")
