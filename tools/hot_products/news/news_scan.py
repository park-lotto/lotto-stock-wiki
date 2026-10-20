"""뉴스·유튜브에서 '지금 화제인 상품'을 줍는다 — 세 갈래: 화제(품절·완판·역주행) / 아이(초등·잘파 인싸템) / 5060(효도템·시니어).
1) 네이버 뉴스 검색 API(최근 N일, 최신순) + 유튜브 최신순 검색(yt-dlp) 제목을 모은다
2) 제미나이가 제목·요약에서 실제 살 수 있는 상품만 뽑아 쇼츠 가능 여부를 단다(식품·소모품·옷 제외)
3) 키워드별로 기사 수·언론사 수·첫 등장일을 합친다
실행: py -I news_scan.py [일수=14]  → news_raw.json, news_hot.json"""
import collections, datetime, email.utils, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types, errors

HERE = os.path.dirname(os.path.abspath(__file__))
env = {}
for line in open(os.path.join(HERE, "..", "..", "..", ".env"), encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
H = {"X-Naver-Client-Id": env["NAVER_CLIENT_ID"], "X-Naver-Client-Secret": env["NAVER_CLIENT_SECRET"]}
KEYS = [v for k, v in env.items() if re.match(r"^GEMINI_(API|INGEST|BRIEFING)_KEY(_\d+)?$", k) and v]
EXTRACT_ONLY = "--extract-only" in sys.argv                       # 모은 제목(news_raw.json)으로 상품 고르기만 다시
args = [a for a in sys.argv[1:] if not a.startswith("--")]
DAYS = int(args[0]) if args else 14
SINCE = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DAYS)

NEWS = {
    "화제": ["품절대란", "품절 대란 제품", "완판 행진", "없어서 못 판다", "오픈런 제품", "역주행 인기", "입소문 타고 판매", "판매량 급증",
             "매출 급증 제품", "SNS 화제 제품", "틱톡 유행 제품", "인스타 유행템", "다이소 품절", "올리브영 품절", "대란템", "MZ 인기템",
             "신박한 아이템", "주문 폭주", "재입고 알림", "1위 상품 인기"],
    "아이": ["초등학생 사이 유행", "초등학생 인기 장난감", "초딩 인싸템", "잘파세대 인기", "알파세대 유행", "어린이 인기 장난감 품절",
             "10대 인기템", "학생들 사이 열풍", "아이들 사이 유행 장난감", "키즈 인기 제품", "문구 유행 학생", "중학생 유행"],
    "5060": ["효도템", "시니어 인기 상품", "5060 인기", "중장년 인기 제품", "액티브 시니어 상품", "부모님 선물 인기", "홈쇼핑 완판",
             "실버 용품 인기", "50대 인기", "60대 인기 제품", "어르신 인기 제품", "파크골프 인기"],
}
YT = {"화제": ["요즘 난리난 꿀템", "품절대란 아이템", "다이소 신상 꿀템", "쿠팡 꿀템 추천"],
      "아이": ["초등학생 인싸템", "요즘 초등학생 유행", "초딩 유행템", "잼민이 유행"],
      "5060": ["효도템 추천", "부모님 선물 추천 효도", "50대 꿀템", "시니어 꿀템"]}

def clean(s): return re.sub(r"<[^>]+>", "", s).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
raw = []
for grp, qs in ({} if EXTRACT_ONLY else NEWS).items():
    for q in qs:
        for start in (1, 101):
            u = "https://openapi.naver.com/v1/search/news.json?" + urllib.parse.urlencode({"query": q, "display": 100, "start": start, "sort": "date"})
            try: items = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20))["items"]
            except Exception as e: print("ERR", q, str(e)[:60]); break
            old = False
            for it in items:
                d = email.utils.parsedate_to_datetime(it["pubDate"])
                if d < SINCE: old = True; continue
                raw.append({"src": "news", "grp": grp, "q": q, "date": d.date().isoformat(), "title": clean(it["title"]),
                            "desc": clean(it["description"])[:160], "link": it.get("originallink") or it["link"]})
            if old or len(items) < 100: break
            time.sleep(0.2)
for grp, qs in ({} if EXTRACT_ONLY else YT).items():
    for q in qs:
        url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q, "sp": "CAI="})   # 업로드 날짜순(ytsearchdate는 이 yt-dlp 에 없음)
        p = subprocess.run(["py", "-m", "yt_dlp", url, "--flat-playlist", "--playlist-end", "30", "--print", "%(id)s\t%(view_count)s\t%(title)s"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
        for line in p.stdout.splitlines():
            f = line.split("\t", 2)
            if len(f) == 3: raw.append({"src": "youtube", "grp": grp, "q": q, "date": "", "title": f[2], "desc": "", "views": f[1], "link": "https://youtu.be/" + f[0]})
seen, uniq = set(), []
for r in raw:
    key = re.sub(r"\W", "", r["title"])[:40]
    if key in seen: continue
    seen.add(key); uniq.append(r)
print("모은 제목", len(raw), "→ 중복 뺀", len(uniq))
if EXTRACT_ONLY: uniq = json.load(open(os.path.join(HERE, "news_raw.json"), encoding="utf-8"))
else: json.dump(uniq, open(os.path.join(HERE, "news_raw.json"), "w", encoding="utf-8"), ensure_ascii=False)

PROMPT = """아래는 최근 뉴스 기사·유튜브 영상 제목(+요약)이다. 각 줄에서 '지금 화제가 되는, 실제로 살 수 있는 상품'만 뽑아라.
우리 목적: 쇼핑쇼츠(신박한 물건을 영상으로 보여주는 쇼츠·릴스) 소재 찾기.
- 상품이 없거나(정책·주식·연예·행사·병원·보험·금융·부동산·서비스·여행상품) 막연한 분류뿐이면 건너뛴다.
- product: 구체적인 물건 이름(브랜드 있으면 포함), kw: 쇼핑 검색창에 칠 2~4단어(브랜드 없이 일반명)
- shortsable: 영상으로 보여줄 거리가 있는 물건(생활·주방·뷰티기기·디지털·장난감·차량·반려·육아·운동기구 등)=true,
  식품·음료·술·과자·화장품 단품 소모품·옷·신발·자동차 자체·아파트=false
- buzz: 기사가 말하는 화제 근거(품절·완판·판매 n배·SNS 유행·재출시 등) 한 구절
- who: 주 사용층(아이|10대|2030|5060|전체)
JSON 배열만: [{"i":번호,"product":"...","kw":"...","shortsable":true,"buzz":"...","who":"..."}]"""
ki, out, failed = 0, [], 0
for s in range(0, len(uniq), 80):
    b = uniq[s:s + 80]
    text = "\n".join(f"{i}. [{r['grp']}] {r['title']} | {r['desc']}" for i, r in enumerate(b))
    res, err = None, ""
    for _ in range(len(KEYS) * 2):
        try:
            client = genai.Client(api_key=KEYS[ki % len(KEYS)])
            r = client.models.generate_content(model="gemini-2.5-flash", contents=PROMPT + "\n" + text,
                                               config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
            res = json.loads(r.text); break
        except (errors.ClientError, errors.ServerError) as e:
            err = str(e)[:90]; ki += 1; time.sleep(5 if "429" in str(e) else 2)
        except Exception as e:
            print("ERR", str(e)[:80]); break
    if res is None:
        failed += 1; print(f"★실패 묶음 {s}~{s + len(b)} (제미나이 한도·오류) 마지막 오류: {err}", flush=True)
    for o in res or []:
        i = o.get("i")
        if isinstance(i, int) and 0 <= i < len(b) and o.get("kw"):
            out.append({**b[i], **{k: o.get(k) for k in ("product", "kw", "shortsable", "buzz", "who")}})
    print(f"{min(s + 80, len(uniq))}/{len(uniq)} 상품 {len(out)}", flush=True)
n_batches = (len(uniq) + 79) // 80
if failed * 2 > n_batches:
    sys.exit(f"★상품 고르기 실패 {failed}/{n_batches}묶음 — news_hot.json 을 덮어쓰지 않는다. 한도 풀린 뒤: py -I news_scan.py --extract-only")
agg = collections.OrderedDict()
for r in out:
    k = re.sub(r"\s+", " ", r["kw"].strip())
    a = agg.setdefault(k, {"kw": k, "products": [], "grps": collections.Counter(), "who": collections.Counter(), "n_news": 0, "n_yt": 0,
                           "first": "", "shortsable": 0, "buzz": [], "links": []})
    a["n_news" if r["src"] == "news" else "n_yt"] += 1
    a["grps"][r["grp"]] += 1; a["who"][r.get("who") or ""] += 1; a["shortsable"] += 1 if r.get("shortsable") else -1
    if r["product"] not in a["products"]: a["products"].append(r["product"])
    if r.get("buzz") and len(a["buzz"]) < 3: a["buzz"].append(r["buzz"])
    if len(a["links"]) < 3: a["links"].append({"t": r["title"][:60], "u": r["link"], "d": r["date"]})
    if r["date"] and (not a["first"] or r["date"] < a["first"]): a["first"] = r["date"]
hot = sorted(agg.values(), key=lambda a: -(a["n_news"] + a["n_yt"]))
for a in hot: a["grps"] = dict(a["grps"]); a["who"] = dict(a["who"]); a["shortsable"] = a["shortsable"] > 0
json.dump({"since": SINCE.date().isoformat(), "n_titles": len(uniq), "items": hot}, open(os.path.join(HERE, "news_hot.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("상품 키워드", len(hot), "/ 쇼츠 가능", sum(a["shortsable"] for a in hot))
for a in [a for a in hot if a["shortsable"]][:40]:
    print(f"  {a['kw']:<16} 뉴스{a['n_news']} 유튜브{a['n_yt']} {a['grps']} {a['who']} | {a['products'][:2]} | {a['buzz'][:1]}")
