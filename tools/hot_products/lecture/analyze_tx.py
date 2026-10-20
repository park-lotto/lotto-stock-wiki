"""강의 정독 — 영상 '전체 자막'을 통째로 제미나이에게 주고 방법을 뽑게 한다. 모든 방법·기준·예시에 강사 말 인용(quote)을 달게 하고,
인용이 자막에 실제로 있는지 프로그램이 검사해 없는 항목은 버린다(지어낸 것 차단). 저해상도 영상 요약(analyze.py)을 대신한다.
실행: py -I analyze_tx.py [k/n]  입력 videos.json(강의 후보) · 자막 subs/<id>.txt(fidelity.subs 재사용) → cards_tx/<id>.json"""
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types, errors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # -I 는 스크립트 폴더를 path 에서 뺀다
from fidelity import subs, norm
from verify_tx import verify          # 인용 검사는 verify_tx 한 곳          # 자막 받기·정규화는 한 곳(fidelity.py)

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "cards_tx"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
env = gkeys.env()
KEYS = gkeys.gemini_keys()
PROMPT = """아래는 한 유튜브 강의의 **전체 자막**(자동자막이라 띄어쓰기·오타 있음)이다. 처음부터 끝까지 빠짐없이 읽고,
강사가 '잘 팔릴 상품 / 뜨는 키워드 / 시즌 상품 / 바이럴 상품'을 고르는 방법을 모두 뽑아라.
우리 목적: 쇼핑쇼츠(신박한 물건 소개 쇼츠·릴스, 쿠팡파트너스) 제작자가 될 만한 상품을 핀셋으로 고르는 것.

절대 규칙:
- 자막에 있는 말만. 모든 항목에 근거 인용 quote 를 단다 — 자막의 **연속된 원문 그대로 8~40자**(고치지 말고 복사).
- 숫자 기준은 강사가 말한 값 그대로. 인용 못 하는 것은 적지 마라.
- 상품 발굴과 무관한 부분(가입·광고 세팅·상세페이지 등)은 methods 에 넣지 말고 skipped 에 한 줄로 적어라(무엇을 건너뛰었는지 남긴다).
JSON만:
{"is_lecture":true,"platforms":[...],
 "methods":[{"name":"","goal":"시즌|바이럴·급상승|꾸준히 팔림|경쟁 틈새|기타","data_source":"","steps":[""],
   "thresholds":[{"rule":"월 검색량 1만 이상","quote":"..."}],
   "signal":"","signal_quote":"...",
   "examples":[{"item":"","why":"","quote":"..."}]}],
 "pitfalls":[{"text":"","quote":"..."}],
 "skipped":["건너뛴 부분 요약"],
 "unique_insight":"","insight_quote":"..."}"""
vids = json.load(open(os.path.join(HERE, "videos.json"), encoding="utf-8"))
cand = sorted([v for v in vids.values() if 240 <= v["duration"] <= 5400 and v["views"] >= 3000], key=lambda v: (-len(v["queries"]), -v["views"]))
ki = 0
if len(sys.argv) > 1:
    k, n = map(int, sys.argv[1].split("/")); cand = cand[k::n]; ki = k * max(1, len(KEYS) // n)
for v in cand:
    path = os.path.join(OUT, v["id"] + ".json")
    if os.path.exists(path): continue
    raw = subs(v["id"])
    if len(raw) < 300: print("자막 없음", v["id"], v["title"][:30], flush=True); continue
    res = None
    for _ in range(len(KEYS) * 2):
        try:
            client = genai.Client(api_key=KEYS[ki % len(KEYS)])
            r = client.models.generate_content(model="gemini-2.5-flash", contents=PROMPT + "\n\n[자막]\n" + raw[:180000],
                                               config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
            res = json.loads(r.text); break
        except (errors.ClientError, errors.ServerError) as e:
            ki += 1; time.sleep(10 if "429" in str(e) else 3)
        except Exception as e:
            print("ERR", v["id"], str(e)[:80]); break
    if not isinstance(res, dict): print("실패", v["id"], flush=True); continue
    res = verify(res, raw); res["_video"] = v; kept, dropped = res["_check"]["kept"], res["_check"]["dropped"]
    json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(float(os.environ.get("HOT_GAP", "0")))     # 공용풀은 고객 제작과 같이 쓴다 — 서버에선 간격을 둔다
    print(f"{v['id']} 방법 {len(res['methods'])} 인용확인 {kept} 버림 {dropped} | {v['title'][:34]}", flush=True)
