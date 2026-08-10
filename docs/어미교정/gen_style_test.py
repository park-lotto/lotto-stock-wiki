# -*- coding: utf-8 -*-
"""메종홈디노 스타일 테스트 생성 (2026-08-05) — 라이브 배선 전 오프라인 데모.

우리 실제 소재(원본 대본) 3개에 스타일 프로파일+실제 히트작 few-shot 3개를 입혀
어떻게 나오는지 본다. 사장님 육안 판정용 — 좋으면 프롬프트 배선 착수.
"""
import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"), override=False)
from google import genai
from google.genai import types

MODELS = ["gemini-3.5-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite",
          "gemini-3.1-flash-lite", "gemini-3.1-flash-lite"]

# few-shot: 스타일 프로파일이 지정한 조회수 검증 대표 3개 (전문 주입 — 요약 금지)
FEWSHOT_IDS = ["DX0exd4xDfq", "DZn7GxUTPtM", "DbKzl_TxvAG"]

PROMPT_TMPL = """너는 국내 최정상 쇼핑 숏폼 대본 작가다. 아래 [스타일 예시]는 한 히트
채널(조회수 52만~158만 검증)의 실제 대본이다. 이 채널의 결을 몸에 입혀라:

[이 스타일의 뼈대 — 예시에서 그대로 보인다]
- 훅: 사건/발견 선언("와, 저 이거 보고 소리 질렀어요" / "~가 만들어서 난리 났다는 ~가 있어요")
- 반드시 인물을 통과한다(와이프·친구·엄마·개발자) — "내가 좋다"가 아니라 "그 사람이 이렇게 쓰더라"
- 제품 소개 전에 기존 방식의 짜증을 내 경험으로 1~2문장
- "근데 이건" 반전 + 구체 스펙 딱 하나
- 장점 2~3개를 한 문장에 몰고("~는데 ~니까 ~더라고요") 끝에 어미 하나로 닫는다
- "심지어/더 대박인 건" 보너스 → "없어서 못 산다고 하더라고요" 사회적 증거

[스타일 예시 — 실제 히트 대본 3개]
{fewshot}

[지켜야 할 우리 규칙 — 스타일보다 우선]
- 사실은 [원본 대본]에 있는 것만. 없는 성능·가격·출처 인물 창작 금지
  (원본에 인물이 없으면 '친구/와이프가 쓰더라' 같은 관계 프레임만 빌리고 구체 신상은 만들지 마라).
- 마지막은 보상형 댓글 CTA: 댓글에 '키워드' 남기면 **뭘 받는지** 명시.
- 같은 어미 연속 2회 금지, "~더라고요" 계열은 전체 최대 2번.
- 길이는 원본과 비슷하게(±20%).

[원본 대본 {idx}]
{source}

[출력] JSON만: {{"styled": "스타일 적용 대본 전문"}}
"""


def main():
    scripts = json.load(open(os.path.join(HERE, "maison_scripts.json"), encoding="utf-8"))
    by_id = {s["shortcode"]: s for s in scripts}
    fewshot = "\n\n".join(
        f"예시{i+1} ({by_id[fid]['views']:,}회):\n{by_id[fid]['text']}"
        for i, fid in enumerate(FEWSHOT_IDS))

    pairs = json.load(open(os.path.join(HERE, "script_pairs4.json"), encoding="utf-8"))
    # 소재 다양하게 3개: 김밥(레시피)·스팀기(청소)·+1
    picks = []
    for kw in ("김밥", "스팀", ""):
        for p in pairs:
            if p["job_id"] in [x["job_id"] for x in picks]:
                continue
            if kw in p["before"] or kw == "":
                picks.append(p)
                break
        if len(picks) == 3:
            break

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""),
                          http_options=types.HttpOptions(timeout=180_000))
    out = []
    for i, p in enumerate(picks):
        src = p["before"].replace(" / ", " ")
        prompt = PROMPT_TMPL.format(fewshot=fewshot, idx=i + 1, source=src)
        styled = None
        for attempt, model in enumerate(MODELS):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema={"type": "object",
                                         "properties": {"styled": {"type": "string"}},
                                         "required": ["styled"]},
                        temperature=1.0))
                styled = json.loads(resp.text)["styled"].replace("*", "")
                print(f"[{i+1}] OK ({model})", flush=True)
                break
            except Exception as e:
                print(f"  [재시도 {attempt+1} {model}] {str(e)[:80]}", flush=True)
                time.sleep(5 * (attempt + 1))
        out.append({"job_id": p["job_id"], "before": src, "styled": styled or "(실패)"})

    dst = os.path.join(HERE, "style_test_maison.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for x in out:
        print("=" * 60)
        print(f"[{x['job_id'][:8]}]")
        print("--- 원본 ---")
        print(x["before"])
        print("--- 메종홈디노 스타일 ---")
        print(x["styled"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
