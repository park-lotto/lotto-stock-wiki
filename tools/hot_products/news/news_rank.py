"""뉴스 화제상품 거르기 — news_hot.json 의 각 상품이 '수요가 실제로 움직인 근거'가 있는지 다시 판정한다.
남김: 품절·완판·판매/검색 N배·예약 마감·유행 확산·품귀  /  뺌: 할인 행사·증정품·출시·팝업·매장 홍보·단순 '인기'
연령 갈래는 여기서 정하지 않는다(검색어 갈래는 틀린다 — 펭수 굿즈가 5060 으로 감). age_trend.py 쏠림으로 붙인다.
실행(서버 공용풀): HOT_SERVER_POOL=1 python3 news_rank.py  → news_rank.json"""
import json, os, sys, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
from google import genai
from google.genai import types, errors

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = gkeys.gemini_keys()
items = [a for a in json.load(open(os.path.join(HERE, "news_hot.json"), encoding="utf-8"))["items"] if a["shortsable"]]
PROMPT = """아래는 뉴스·유튜브 제목에서 뽑은 상품과 '화제 근거' 문구, 원문 제목이다. 각 줄을 판정하라.
- demand: 수요가 실제로 움직였다는 근거가 있나. true = 품절·완판·매진·품귀·판매량/검색량 N배·예약 마감·재입고 대기·또래 사이 유행 확산.
  false = 할인 행사·증정품·출시 소식·팝업스토어·매장 홍보·막연한 '인기'·브랜드 광고성 기사.
- evidence: demand=true 면 근거 문구를 원문에서 짧게(없으면 "")
- kw: 쇼핑 검색창에 칠 일반 상품명 2~4단어(브랜드·캐릭터명 빼고. 캐릭터 굿즈 자체가 상품이면 '캐릭터명 굿즈' 허용)
- shorts: 15~30초 쇼츠로 보여줄 장면이 있나(true/false). 스마트폰·노트북·가구 대형 브랜드 신제품은 false
JSON 배열만: [{"i":번호,"demand":true,"evidence":"","kw":"","shorts":true}]"""
ki, out = 0, []
for s in range(0, len(items), 60):
    b = items[s:s + 60]
    text = "\n".join(f"{i}. 상품:{a['products'][:2]} | 근거:{a['buzz'][:2]} | 제목:{[l['t'] for l in a['links'][:2]]}" for i, a in enumerate(b))
    res, err = None, ""
    for _ in range(len(KEYS) * 2):
        try:
            client = genai.Client(api_key=KEYS[ki % len(KEYS)])   # 변수에 잡아둔다 — 한 줄로 쓰면 호출 전에 닫힌다
            r = client.models.generate_content(
                model="gemini-2.5-flash", contents=PROMPT + "\n" + text,
                config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
            res = json.loads(r.text); break
        except (errors.ClientError, errors.ServerError) as e:
            err = str(e)[:90]; ki += 1; time.sleep(5 if "429" in str(e) else 2)
    if res is None:
        sys.exit(f"★판정 실패 묶음 {s} — 결과를 쓰지 않는다: {err}")
    for o in res:
        i = o.get("i")
        if isinstance(i, int) and 0 <= i < len(b):
            out.append({**b[i], "demand": bool(o.get("demand")), "evidence": o.get("evidence") or "",
                        "kw_clean": o.get("kw") or b[i]["kw"], "shorts": bool(o.get("shorts"))})
    print(f"{min(s + 60, len(items))}/{len(items)}", flush=True)
keep = [a for a in out if a["demand"] and a["shorts"]]
json.dump({"n_in": len(items), "n_judged": len(out), "items": out}, open(os.path.join(HERE, "news_rank.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("판정", len(out), "/ 수요근거+쇼츠", len(keep))
for a in keep[:40]: print(f"  {a['kw_clean']:<16} | {a['evidence'][:40]} | {a['grps']}")
