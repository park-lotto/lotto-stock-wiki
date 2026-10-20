"""강의 영상 → 제미나이가 직접 보고 '상품 발굴 방법 카드'로 뽑는다(유튜브 URL을 그대로 넘김, 다운로드 없음).
실행: py -I analyze.py [최대편수]   입력 videos.json → 출력 cards/<id>.json (이미 있으면 건너뜀)
키: 저장소 .env 의 GEMINI_API_KEY* 를 돌려 쓴다(무료 AI Studio 키. 버텍스 금지)."""
import json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types, errors

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "..")
env = {}
for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
KEYS = [v for k, v in env.items() if re.match(r"^GEMINI_(API|INGEST|BRIEFING)_KEY(_\d+)?$", k) and v]   # 임베딩 키는 뺀다
MODEL = os.environ.get("LECTURE_MODEL", "gemini-2.5-flash")
os.makedirs(os.path.join(HERE, "cards"), exist_ok=True)

PROMPT = """너는 한국 이커머스 상품 발굴 전문가다. 이 유튜브 강의 영상을 끝까지 보고(화면에 나오는 사이트·메뉴·필터·숫자까지),
강사가 "잘 팔릴 상품 / 뜨는 키워드 / 시즌 상품 / 바이럴 상품"을 찾는 **방법**을 빠짐없이 뽑아라.
우리 목적: 쇼핑쇼츠(신박한 상품을 소개하는 쇼츠·릴스, 쿠팡파트너스 수수료) 제작자가 '정말 될 만한 상품'을 핀셋으로 고르는 것.

규칙:
- 영상에서 실제로 말하거나 화면에 보인 것만 적는다. 추측은 "guess": true 로 표시.
- 숫자 기준(검색량·상품수·리뷰수·판매량·비율·기간 등)은 강사가 말한 값 그대로.
- 각 방법마다 그 방법으로 찾은 **실제 상품·키워드 예시**를 영상에 나온 그대로 적는다.
- 광고·홍보 영상(강의 판매만 하고 방법이 없음)이면 is_lecture=false 로 하고 나머지는 비워도 된다.

JSON만 출력:
{
 "is_lecture": true,
 "platforms": ["네이버","쿠팡",...],
 "methods": [
  {"name": "방법 이름(짧게)",
   "goal": "시즌|바이럴·급상승|꾸준히 팔림|경쟁 틈새|기타",
   "data_source": "사이트·도구·메뉴 경로(예: 네이버 데이터랩 > 쇼핑인사이트 > 분야 통계)",
   "steps": ["화면에서 하는 순서"],
   "filters_and_thresholds": ["예: 월 검색량 1만 이상", "상품수/검색수 0.5 이하"],
   "signal": "이 방법이 '될 상품'이라고 보는 근거",
   "examples": [{"item": "상품·키워드", "why": "왜 골랐나", "result": "실제 결과(매출 등, 말했으면)"}],
   "timestamp": "mm:ss",
   "guess": false}
 ],
 "viral_or_season_keywords": ["영상에 나온 뜨는 키워드·시즌 키워드"],
 "pitfalls": ["강사가 경고한 함정"],
 "unique_insight": "이 영상에만 있는 독특한 관점 1~2문장",
 "evidence_level": "실제 매출·화면 증거 있음|사례만|주장만"
}"""

vids = json.load(open(os.path.join(HERE, "videos.json"), encoding="utf-8"))
cand = [v for v in vids.values() if 240 <= v["duration"] <= 5400 and v["views"] >= 3000]
cand.sort(key=lambda v: (-len(v["queries"]), -v["views"]))          # 여러 검색어에 걸린 것·조회수 높은 것 먼저
limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != "all" else len(cand)
# 나눠 돌리기: py -I analyze.py all 2/5 → 5명 중 2번 일꾼(후보를 5로 나눠 맡고, 키도 다른 데서 시작)
if len(sys.argv) > 2:
    k, n = map(int, sys.argv[2].split("/"))
    cand = cand[k::n]
    ki = k * max(1, len(KEYS) // n)
else:
    ki = 0
done = 0
for v in cand:
    if done >= limit: break
    path = os.path.join(HERE, "cards", f"{v['id']}.json")
    if os.path.exists(path): continue
    url = f"https://www.youtube.com/watch?v={v['id']}"
    res, err = None, ""
    for attempt in range(len(KEYS) * 3):
        client = genai.Client(api_key=KEYS[ki % len(KEYS)])
        try:
            r = client.models.generate_content(model=MODEL, contents=types.Content(parts=[
                    types.Part(file_data=types.FileData(file_uri=url, mime_type="video/*")), types.Part(text=PROMPT)]),
                config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json",
                                                   media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW))
            res = json.loads(r.text); break
        except errors.ClientError as e:                       # 429 한도·400 등 → 다음 키
            err = str(e)[:160]; ki += 1
            if "429" not in err and "RESOURCE_EXHAUSTED" not in err: break
            time.sleep(20)          # 분당 한도(지역) — 키를 바꿔도 같이 막히니 잠깐 쉰다
        except errors.ServerError as e:
            err = str(e)[:160]; time.sleep(15)
        except Exception as e:
            err = str(e)[:160]; break
    if res is None:
        print("실패", v["id"], v["title"][:30], err, flush=True); continue
    res["_video"] = v; res["_model"] = MODEL
    json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    done += 1
    print(f"[{done}] {v['title'][:40]} | 방법 {len(res.get('methods', []))}개 | 강의={res.get('is_lecture')}", flush=True)
print("끝: 새로 분석", done, "/ 카드 총", len(os.listdir(os.path.join(HERE, "cards"))))
