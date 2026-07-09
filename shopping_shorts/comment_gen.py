"""Gemini로 릴스 캡션 기반 자연스러운 댓글 후보 생성. 기존 key_vault 재사용."""
import json
import time
from google.genai import types
from pipeline.atoms import key_vault

_GROUP = "general"
_MODEL = "gemini-3.1-flash-lite"

_PROMPT = """너는 인스타에서 활발히 소통하는 진짜 사람이다.
아래 릴스를 방금 본 팔로워처럼, 영상 내용에 실제로 반응하는 한국어 댓글 3개를 만들어라.

[채널] {channel}
[카테고리] {category}
[영상 캡션] {caption}

규칙:
- 먼저 캡션에 "댓글 이벤트/응모/참여" CTA가 있는지 판단하라
  (예: "댓글 남겨주시면 추첨", "OO 남겨주세요", "댓글로 참여", "이벤트 참여" 등).
- CTA가 있으면: 3개 중 2개는 그 지시를 실제로 따르는 참여 댓글로 만들어라.
  캡션이 요구하는 특정 단어·문구·이모지가 있으면, **그 단어를 댓글 맨 마지막에
  독립적으로(문장 끝에 붙여서, 앞 문장과 자연스럽게 이어지되 눈에 띄게)
  배치**하라 — 예: "이거 완전 필요했어요! 얼음" (O), "얼음 정말 유용하네요" (X, 문장
  중간에 묻힘). 문장 안에 흩어놓지 말고 항상 끝에 한 번, 명확히 노출.
  매번 조금씩 다르게·자연스럽게. 나머지 1개는 영상 내용에 반응하는 일반 댓글.
- CTA가 없으면: 3개를 톤 다르게 — 질문형, 공감형, 칭찬/저장 언급형.
- 모든 댓글: 영상 내용에 구체적으로 반응. 내용과 무관한 범용 문구 금지.
- 1~2줄, 짧고 자연스럽게. 존댓말. 이모지는 0~1개만.
- 광고·홍보·링크 금지. 봇처럼 보이는 정형 문구 금지.
- 반드시 JSON 배열로만 출력: ["댓글1", "댓글2", "댓글3"]
"""


def _get_client():
    return key_vault.get_client(_GROUP)


def build_prompt(caption, channel, category):
    return _PROMPT.format(
        caption=(caption or "(캡션 없음 — 채널·카테고리로 유추)"),
        channel=channel or "",
        category=category or "기타",
    )


def parse_response(raw):
    """Gemini 응답 텍스트 → 댓글 list[str]. 실패 시 []."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict) and isinstance(data.get("comments"), list):
        return [str(x) for x in data["comments"]]
    return []


def generate(caption, channel, category, max_retries=4):
    """캡션→댓글 3개. Gemini 쿼터 초과 시 key_vault 로테이션. 최종 실패 시 []."""
    prompt = build_prompt(caption, channel, category)
    for attempt in range(max_retries):
        try:
            resp = _get_client().models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return parse_response(resp.text)
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e):
                if key_vault.rotate(_GROUP):
                    continue
                return []
            if key_vault.is_quota_error(e):
                time.sleep(62)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            return []
    return []
