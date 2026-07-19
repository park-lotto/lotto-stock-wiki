"""썸네일 제목 추천 — 확정 대본으로 화면에 큼직하게 얹을 짧은 제목 후보를 뽑는다(2026-07-19).

SEO 제목(seo_generate, 검색 최적화·100자)과는 목적이 다르다. 썸네일 제목은 **이미지 위에
얹는 것**이라 2~3어절·한두 줄·호기심/충격 위주여야 한다(길면 자동 줄바꿈으로 작아진다).
목적: 제목을 못 떠올리는 사장님이 **원본 영상만 보고 클릭 한 번으로** 얹게 하는 것.

플럼빙(모델·키풀 캐스케이드·소진 마킹)은 seo_generate와 똑같다 — 대화형이라 소진에 취약해
comment_gen 전용키가 아니라 key_vault 공유풀(general→…)을 캐스케이드로 쓴다.
"""
import json

from google.genai import types

from shopping_shorts import comment_gen
from pipeline.atoms import key_vault

_MODEL = comment_gen._MODEL
_GEN_GROUP = "general"

_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["text", "why"],
            },
            "minItems": 4,
            "maxItems": 6,
        },
    },
    "required": ["titles"],
}

_PROMPT = """너는 한국 쇼츠 채널의 썸네일 카피라이터다. 아래 영상 대본을 보고, 영상 위에 큼직하게 얹을 **썸네일 제목** 후보 5개를 만든다.

[썸네일 제목 규격 — SEO 제목과 다르다. 어기면 못 쓴다]
- 짧고 강하게: 한 줄 2~7글자, 최대 두 줄(줄바꿈이 필요하면 \\n을 넣어라). 검색용 긴 문장 금지.
- 스크롤을 멈추게: 호기심·충격·반전·숫자·의외성 중 하나를 건다.
- 대본에 실제로 있는 사실만. 없는 효능·과장·허위 금지.
- 말투는 대본을 따른다(대본이 반말이면 제목도 반말).
- 이모지·특수기호 금지(글자만 — 꾸밈은 화면에서 따로 얹는다).
- 5개는 서로 다른 각도로: 질문형 / 감탄형 / 숫자형 / 반전형 / 정보형 등 겹치지 않게.
- why: 왜 이 제목이 스크롤을 멈추게 하는지 한 줄로.
- 전부 한국어.

[대본]
{script}

[구조 분석]
{structure}

[화면 헤드카피(참고)]
{headcopy}
"""


def _build_prompt(job):
    struct = job.get("script_structure") or {}
    head = (job.get("headcopy") or {}).get("text") or ""
    return _PROMPT.format(
        script=job.get("given_script") or "",
        structure=json.dumps(struct, ensure_ascii=False, indent=1),
        headcopy=head,
    )


def generate(job):
    """key_vault 캐스케이드로 썸네일 제목 후보 리스트를 생성. 소진키는 마킹하고 다음 키로.
    무키·전부실패면 None(호출부가 502로 돌려준다)."""
    keys = key_vault.get_live_keys_cascade(_GEN_GROUP)
    if not keys:
        return None
    prompt = _build_prompt(job)
    for key in keys:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            data = json.loads(resp.text)
            return data.get("titles") or []
        except Exception as e:  # noqa: BLE001 — 생성 실패는 치명적 아님
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or _GEN_GROUP, key)
                continue
            if key_vault.is_quota_error(e):
                continue  # 순간 rate limit — 다음 키로
            return None
    return None
