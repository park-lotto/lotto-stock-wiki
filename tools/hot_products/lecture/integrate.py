"""통합 — 강의 카드(cards/*.json)의 방법들을 제미나이가 같은 방법끼리 묶어 '방법 목록'으로 만든다.
출력 catalog.json + catalog.md. 몇 번이고 다시 돌려도 된다(카드가 늘면 목록도 갱신)."""
import glob, json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from google import genai
from google.genai import types, errors

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # gkeys = 키·환경값의 유일한 곳
import gkeys
env = gkeys.env()
KEYS = gkeys.gemini_keys()

cards = [json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(HERE, "cards", "*.json"))]
cards = [c for c in cards if c.get("is_lecture")]
lines = []
for c in cards:
    v = c["_video"]
    for m in c.get("methods", []):
        ex = "; ".join(f"{e.get('item')}" for e in (m.get("examples") or [])[:4])
        lines.append(f"[{v['id']}|조회{v['views']}|{c.get('evidence_level','')}] {m.get('name')} / 목적:{m.get('goal')} / 출처:{m.get('data_source')} "
                     f"/ 기준:{' , '.join(m.get('filters_and_thresholds') or [])} / 신호:{m.get('signal')} / 예:{ex}")
print("강의", len(cards), "방법 줄", len(lines))

PROMPT = """아래는 상품 발굴 강의 여러 편에서 뽑은 '방법' 목록이다(줄마다 [영상id|조회수|증거수준]).
같은 방법끼리 묶어 표준 방법 목록을 만들어라. 우리 목적: 쇼핑쇼츠 제작자가 '정말 될 만한 상품'을 핀셋으로 고르는 것.

각 표준 방법마다:
- name, goal(시즌|바이럴·급상승|꾸준히 팔림|경쟁 틈새|마진·소싱|기타)
- videos: 이 방법을 쓴 영상 id 목록(빠짐없이), n_videos
- data_source: 쓰는 사이트·도구(여러 개면 모두)
- thresholds: 강사들이 쓴 숫자 기준을 모아 범위로(예: "월 검색량 1천~1만 이상(5명)") — 강사마다 다르면 다르다고 적어라
- signal: 왜 될 상품이라고 보나
- examples: 그 방법으로 나온 실제 상품·키워드(중복 제거, 최대 10)
- automatable: 우리가 무료로 자동 수집 가능한가 — "가능(근거)" | "부분(무엇이 막힘)" | "불가(이유)".
  우리가 이미 가진 데이터: 네이버 쇼핑 베스트 API(구매·클릭순, 리뷰수), 네이버 검색광고 키워드도구(월검색·경쟁), 데이터랩 검색어트렌드(3년 주간),
  쿠팡 파트너스 API(카테고리 베스트·골드박스, 순위만), 1688 순위(월판매·전월성장), 테무 베스트(누적판매·시간당), 아마존 베스트(리뷰·순위), 유튜브 검색(yt-dlp), 틱톡 크리에이티브센터 해시태그(한국 7일)
- credibility: 증거수준과 영상 수를 보고 상/중/하

그리고 맨 끝에 'gaps': 강의들이 말하지만 우리가 아직 못 재는 것, 더 찾아봐야 할 검색어 5개.
JSON만: {"methods":[...], "gaps":{"cannot_measure":[...], "next_queries":[...]}}"""
res, ki = None, 0
for _ in range(len(KEYS) * 2):
    try:
        client = genai.Client(api_key=KEYS[ki % len(KEYS)])
        r = client.models.generate_content(model=os.environ.get("INTEGRATE_MODEL", "gemini-2.5-pro"),
                                           contents=PROMPT + "\n\n" + "\n".join(lines),
                                           config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
        res = json.loads(r.text); break
    except (errors.ClientError, errors.ServerError) as e:
        print("재시도", str(e)[:100]); ki += 1; time.sleep(5)
if not res: sys.exit("통합 실패")
res["_n_lectures"] = len(cards); res["_n_lines"] = len(lines)
json.dump(res, open(os.path.join(HERE, "catalog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ms = sorted(res["methods"], key=lambda m: -m.get("n_videos", 0))
md = [f"# 상품 발굴 방법 목록 (강의 {len(cards)}편 · 방법 {len(lines)}줄 통합)\n",
      "| # | 방법 | 목적 | 강의 수 | 기준 | 자동수집 | 신뢰 |", "|---|---|---|---|---|---|---|"]
for i, m in enumerate(ms, 1):
    md.append(f"| {i} | {m['name']} | {m.get('goal')} | {m.get('n_videos')} | {'; '.join(m.get('thresholds') or [])[:120]} | {m.get('automatable')} | {m.get('credibility')} |")
md.append("\n## 못 재는 것\n" + "\n".join(f"- {g}" for g in res["gaps"].get("cannot_measure", [])))
md.append("\n## 다음 검색어\n" + "\n".join(f"- {g}" for g in res["gaps"].get("next_queries", [])))
open(os.path.join(HERE, "catalog.md"), "w", encoding="utf-8").write("\n".join(md))
print("방법", len(ms), "→ catalog.md")
