"""키워드마다 수요·경쟁 지표를 붙인다.
  · 네이버 검색광고 키워드도구: 월 검색수(PC+모바일)·경쟁정도
  · 네이버 데이터랩 검색어트렌드: 최근 4주 vs 그 앞 8주 (상승률), 1년 최고 대비 지금
  · 유튜브(yt-dlp 검색, 키 불필요): "<키워드> 쇼츠" 상위 20개 조회수 합·중앙값
입력: 지금 폴더의 kws.json (["키워드", ...])  출력: 같은 폴더 enrich.json {kw: {...}}
실행: cd work && py -I ../enrich.py  /  cd work/hits && py -I ../../enrich.py  (사본 enrich_run.py 는 지웠다)"""
import base64, datetime, hashlib, hmac, json, os, statistics, subprocess, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gkeys                      # 키·환경값·데이터랩 호출의 유일한 곳
env = gkeys.env()
kws = json.load(open("kws.json", encoding="utf-8"))
out = json.load(open("enrich.json", encoding="utf-8")) if os.path.exists("enrich.json") else {}
todo = [k for k in kws if k not in out or "search_month" not in out[k] or "trend_up" not in out[k]]   # 실패해 값이 빠진 것도 다시(10-20 한도 초과 뒤 영영 안 채워지던 것)
print("할 일", len(todo), "/", len(kws))

def searchad(batch):
    ts = str(int(time.time() * 1000)); path = "/keywordstool"
    sig = base64.b64encode(hmac.new(env["NAVER_SEARCHAD_SECRET"].encode(), f"{ts}.GET.{path}".encode(), hashlib.sha256).digest()).decode()
    q = urllib.parse.urlencode({"hintKeywords": ",".join(b.replace(" ", "") for b in batch), "showDetail": 1})
    req = urllib.request.Request(f"https://api.searchad.naver.com{path}?{q}", headers={
        "X-Timestamp": ts, "X-API-KEY": env["NAVER_SEARCHAD_ACCESS_LICENSE"], "X-Customer": env["NAVER_SEARCHAD_CUSTOMER_ID"], "X-Signature": sig})
    rows = json.load(urllib.request.urlopen(req, timeout=20)).get("keywordList", [])
    by = {r["relKeyword"]: r for r in rows}
    res = {}
    for b in batch:
        r = by.get(b.replace(" ", ""))
        if not r: continue
        n = lambda v: 5 if isinstance(v, str) else int(v)   # "< 10" 은 5로
        res[b] = {"search_month": n(r["monthlyPcQcCnt"]) + n(r["monthlyMobileQcCnt"]), "comp": r.get("compIdx")}
    return res

def datalab(batch):
    end = datetime.date.today() - datetime.timedelta(days=1); start = end - datetime.timedelta(days=365)
    body = {"startDate": str(start), "endDate": str(end), "timeUnit": "week",
            "keywordGroups": [{"groupName": b, "keywords": [b]} for b in batch]}
    res = {}
    for g in gkeys.datalab(body, timeout=20):
        v = [x["ratio"] for x in g["data"]]
        if len(v) < 12: continue
        recent, before = sum(v[-4:]) / 4, sum(v[-12:-4]) / 8
        res[g["title"]] = {"trend_up": round((recent / before - 1) * 100) if before else None,
                           "vs_peak": round(recent / max(v) * 100) if max(v) else None}
    return res

def youtube(kw):
    try:
        p = subprocess.run(["py", "-m", "yt_dlp", f"ytsearch20:{kw} 쇼츠", "--flat-playlist", "--print", "%(view_count)s"],
                           capture_output=True, text=True, encoding="utf-8", timeout=90)
        v = [int(x) for x in p.stdout.split() if x.isdigit()]
        return {"yt_views_sum": sum(v), "yt_views_med": int(statistics.median(v)) if v else 0, "yt_n": len(v)}
    except Exception as e:
        return {"yt_err": str(e)[:60]}

for i in range(0, len(todo), 5):
    batch = todo[i:i + 5]
    for b in batch: out.setdefault(b, {})
    try:
        for k, v in searchad(batch).items(): out[k].update(v)
    except Exception as e: print("searchad ERR", str(e)[:80])
    try:
        for k, v in datalab(batch).items(): out[k].update(v)
    except Exception as e: print("datalab ERR", str(e)[:80])
    for b in batch: out[b].update(youtube(b))
    json.dump(out, open("enrich.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(i + len(batch), "/", len(todo), batch[0], out[batch[0]], flush=True)
    time.sleep(0.5)
print("끝", len(out))
