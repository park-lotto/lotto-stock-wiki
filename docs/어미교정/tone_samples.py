# -*- coding: utf-8 -*-
"""말맛(어미·문장연결) 예시 대본을 Gemini로 여러 스타일·여러 소재로 뽑아본다.
프롬프트 개선 전 '어떤 결이 정답인가'를 사장님이 눈으로 고르기 위한 탐색용 (일회성).
"""
import io
import json
import sys

sys.path.insert(0, r"C:\Users\CH\Desktop\로또의 주식")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from google import genai
from google.genai import types
from shopping_shorts.config import SHORTS_GEMINI_KEYS


def _keys():
    """쇼핑쇼츠 전용 풀 우선, 없으면(회사PC 등) 공유 풀·단일 키로 폴백. 탐색용 일회성."""
    if SHORTS_GEMINI_KEYS:
        return SHORTS_GEMINI_KEYS
    import os
    from dotenv import load_dotenv
    load_dotenv(r"C:\Users\CH\Desktop\로또의 주식\.env", override=False)
    try:
        from pipeline.atoms import key_vault
        pool = [k for k in (key_vault.all_keys() if hasattr(key_vault, "all_keys") else []) if k]
        if pool:
            return pool
    except Exception:
        pass
    return [k for k in [os.environ.get("GEMINI_API_KEY", "")] if k]

MODEL = "gemini-3.5-flash"

ROUGH = """여러분 가전 청소할 때 이거 꼭 넣으세요. 다이소에서 산 이 세정제로 싹 닦아봤어요.
오래된 가전도 새것처럼 빛나는 거 있죠? 겨울에 지문 하나 안 남게 깔끔해지는 것 같아요.
근데 이게 대박인 게 방수코팅까지 된다는 거예요. 특히 물기 관리까지 쉽다니..
청소 한 번으로 한 달간 깨끗하게, 가전제품이 새 제품처럼 변합니다.
댓글에 '청소' 남겨주시면 저렴하게 사실 수 있는 제품 정보 보내드릴게요."""

PROMPT = f"""너는 한국 쇼핑 숏폼(살림·주방·청소·생활용품) 대본 작가다.

지금 우리 대본 생성기의 문제는 **어미가 단조롭다**는 것이다.
'~하더라고요 / ~돼요 / ~되죠' 정도만 돌려써서 밋밋하고, 문장을 하나씩 뚝뚝 끊어 써서
광고 문구처럼 들린다.

우리가 원하는 결(아래는 사장님이 손으로 급하게 쓴 **러프 스케치**다. 정답이 아니라
'대충 이런 말맛' 정도의 방향 감만 잡은 것이니 그대로 베끼지 말고 결만 참고해라):

---
{ROUGH}
---

[1단계 — 구조분석 먼저 해라]
위 러프를 **문장 단위로 해부**해서 analysis에 담아라. 각 문장마다:
- role: 이 문장이 대본에서 맡은 역할 (훅 / 도입 / 시연 / 반응 / 반전 / 강화 / 마무리 / CTA)
- ending: 실제 쓰인 종결어미를 표면형 그대로 ("~세요" "~봤어요" "~는 거 있죠?" "~것 같아요"
  "~다는 거예요" "~다니.." "~합니다" "~드릴게요")
- ending_type: 그 어미의 기능 (권유 / 경험담 / 확인요구 / 완곡추측 / 발견제시 / 여운 /
  단정 / 약속 …)
- connector: 앞 문장과 잇는 말이 있으면 그것 ("근데 이게 대박인 게" "특히" 등), 없으면 ""
- note: 이 문장이 왜 이 자리에 이 어미로 있는지 한 줄

그다음 analysis 전체를 관통하는 패턴을 pattern_summary에 정리해라:
- ending_flow: 어미 기능이 흘러가는 순서 (예: 권유→경험담→확인요구→완곡추측→발견제시→여운→단정→약속)
- rules: 이 러프에서 뽑아낸 말맛 규칙 4~6개 (어미 반복 여부, 문장 연결 방식, 텐션 곡선,
  단정하는 자리와 흐리는 자리의 배치 등)

★주의: 이 러프는 사장님이 **손으로 급하게 쓴 스케치**다. 정답이 아니다. 잘된 점과 함께
어색한 점(오타·비문·어색한 어미)도 솔직히 짚어라. 베낄 대상이 아니라 **해부할 표본**이다.

[2단계 — 분석을 근거로 예시를 만들어라]
1단계에서 뽑은 ending_flow와 rules를 **실제로 적용해서**, 서로 다른 **말투 스타일 5가지**를
정의하고 각 스타일마다 **소재 3개**로 대본을 써라. 총 15개다.
소재는 아래 3개를 공통으로 써라(스타일 비교가 되게):
  1) 다이소 가전 세정제 (오래된 가전 얼룩·지문 제거, 방수코팅)
  2) 주방 기름때 세정 티슈 (후드·가스레인지 찌든 기름)
  3) 욕실 물때·곰팡이 제거 스프레이 (실리콘 줄눈 곰팡이)

스타일 5가지는 네가 직접 이름 붙이고 정의해라. 다만 서로 확실히 달라야 한다 —
어미 레퍼토리·문장 연결 방식·화자의 텐션이 구분되게. (예: 수다스러운 이웃 / 담담한
증언 / 놀란 리액션 위주 / 살림 고수의 팁 전수 / 친구한테 몰래 알려주는 톤 …
이건 예시일 뿐 네가 더 좋은 걸 잡아도 된다.)
★러프의 어미를 그대로 재탕하지 마라. 러프는 표본 하나일 뿐이고, 한국어 구어 종결어미는
훨씬 넓다 — 스타일마다 **다른 어미 레퍼토리**를 새로 발굴해서 써라.

[각 대본 규칙]
- 길이는 한국어 250~300자 (약 30초 분량)
- 1단계에서 뽑은 ending_flow를 이 대본이 실제로 따르게 써라 (기계적 복사가 아니라
  기능의 흐름을 지키라는 뜻)
- 어미가 3회 이상 반복되면 안 된다 (같은 어미 연타 금지)
- 문장을 **끊지 말고 이어라** — 연결어미·접속사로 흘러가게
- CTA는 [명분 한 줄] + "댓글에 'OO' 남겨주시면 보내드릴게요" 형식
- 상세페이지 상투어 금지 (꿀템·갓성비·완벽 해결·삶의 질 상승)
- 없는 가격·할인·한정수량 지어내기 금지

[출력]
JSON만. 스키마:
{{"analysis": [{{"sentence": "러프의 문장 그대로", "role": "...", "ending": "...",
   "ending_type": "...", "connector": "...", "note": "..."}}],
 "pattern_summary": {{"ending_flow": ["기능1", "기능2", "..."],
   "rules": ["규칙1", "..."], "weaknesses": ["러프의 어색한 점1", "..."]}},
 "styles": [{{"style_name": "...", "style_desc": "이 스타일의 어미 레퍼토리와 문장 연결 방식 한 줄 설명",
  "ending_kit": ["이 스타일이 주로 쓰는 어미 5~7개"],
  "scripts": [{{"topic": "소재명", "text": "대본 전문"}}]}}]}}
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "role": {"type": "string"},
                    "ending": {"type": "string"},
                    "ending_type": {"type": "string"},
                    "connector": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["sentence", "role", "ending", "ending_type", "connector", "note"],
            },
        },
        "pattern_summary": {
            "type": "object",
            "properties": {
                "ending_flow": {"type": "array", "items": {"type": "string"}},
                "rules": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["ending_flow", "rules", "weaknesses"],
        },
        "styles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "style_name": {"type": "string"},
                    "style_desc": {"type": "string"},
                    "ending_kit": {"type": "array", "items": {"type": "string"}},
                    "scripts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["topic", "text"],
                        },
                    },
                },
                "required": ["style_name", "style_desc", "ending_kit", "scripts"],
            },
        },
    },
    "required": ["analysis", "pattern_summary", "styles"],
}


def main():
    keys = _keys()
    print(f"[키풀] {len(keys)}개", flush=True)
    last_err = None
    for i, key in enumerate(keys):
        try:
            client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180_000))
            resp = client.models.generate_content(
                model=MODEL,
                contents=PROMPT,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SCHEMA,
                    temperature=1.0,
                ),
            )
            data = json.loads(resp.text)
            out = r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\a2d5d291-265d-4f38-a840-e1cd5f8224bc\scratchpad\tone_samples.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[성공] key#{i} → {out}", flush=True)
            print(f"\n{'#'*70}\n# 1단계 — 러프 구조분석\n{'#'*70}")
            for a in data.get("analysis", []):
                conn = f"  [연결어: {a['connector']}]" if a.get("connector") else ""
                print(f"\n· {a['sentence']}")
                print(f"    역할={a['role']} / 어미={a['ending']} ({a['ending_type']}){conn}")
                print(f"    → {a['note']}")
            ps = data.get("pattern_summary", {})
            print(f"\n{'-'*70}\n[어미 흐름] {' → '.join(ps.get('ending_flow', []))}")
            print("[말맛 규칙]")
            for r in ps.get("rules", []):
                print(f"  - {r}")
            print("[러프의 약점]")
            for w in ps.get("weaknesses", []):
                print(f"  - {w}")
            print(f"\n{'#'*70}\n# 2단계 — 스타일별 예시 대본\n{'#'*70}")
            for s in data.get("styles", []):
                print(f"\n{'='*70}\n■ {s['style_name']} — {s['style_desc']}")
                print(f"  어미킷: {' / '.join(s.get('ending_kit', []))}")
                for sc in s.get("scripts", []):
                    print(f"\n  [{sc['topic']}]\n  {sc['text']}")
            return 0
        except Exception as e:
            last_err = e
            msg = str(e)[:120]
            print(f"[키#{i} 실패] {msg}", flush=True)
            continue
    print(f"[전멸] {last_err}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
