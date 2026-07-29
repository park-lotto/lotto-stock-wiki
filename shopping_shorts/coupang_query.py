"""쿠팡 검색어 만들기(2026-07-29) — 편집안의 affiliate_target을 그대로 쓰면 엉뚱한 게 나온다.

실사고(사장님 캡처): 대본이 "갈라진 옷 프린팅을 살리는 꿀팁"인데 affiliate_target이
**"갈라진 프린팅 수선"**(서술형)이라, 쿠팡이 '수선'만 붙잡아 **자수 패치·고양이 캐릭터
패치**를 잔뜩 내놨다. 사람이라면 "옷 프린팅 복원제"나 "열전사 필름"을 검색했을 것이다.

그래서 대본 + 타깃을 같이 읽고 **쿠팡 검색창에 칠 법한 상품명**으로 바꾼다.
- 결과는 여러 개(최대 3). 첫 개로 자동 검색하고 나머지는 화면에 칩으로 놓아
  한 번의 클릭으로 갈아탈 수 있게 한다 — 어차피 한 방에 맞히긴 어렵다.
- ★AI가 죽거나 키가 소진돼도 기능이 멈추면 안 된다. 그럴 땐 원래 타깃을 그대로 쓴다.
"""
import json
import re

_MODEL = "gemini-2.5-flash"

_PROMPT = """너는 한국 쇼핑 검색 도우미다. 아래 쇼츠 대본과 '연결 대상'을 읽고,
이 영상을 본 사람이 **실제로 사려고 쿠팡 검색창에 칠 상품명**을 2~3개 만들어라.

규칙:
- 상품 이름이어야 한다. 행동·증상·서술("갈라진 프린팅 수선", "정리하는 법")은 금지.
- 2~4단어, 한국어. 브랜드명은 넣지 마라.
- 서로 다른 각도로 제안해라(같은 말 바꿔쓰기 금지).
- 이 영상과 무관한 상품은 넣지 마라.

출력은 JSON만: {"queries": ["...", "..."]}

"""


def _clean(q):
    q = re.sub(r"\s+", " ", (q or "")).strip().strip('"')
    return q if 2 <= len(q) <= 30 else ""


def parse_queries(raw, limit=3):
    """모델 응답 → 검색어 리스트(순수). 못 알아보면 빈 리스트."""
    try:
        data = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw or "", re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except Exception:
            return []
    out, seen = [], set()
    for q in (data.get("queries") if isinstance(data, dict) else []) or []:
        c = _clean(q if isinstance(q, str) else "")
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:limit]


def suggest(target, script="", limit=3):
    """(대본, 타깃) → 쿠팡 검색어 후보. 실패하면 [target]으로 조용히 폴백한다."""
    target = (target or "").strip()
    if not target and not script:
        return []
    fallback = [target] if target else []
    try:
        from google.genai import types

        from shopping_shorts import comment_gen
    except Exception:
        return fallback

    body = (f"연결 대상: {target}\n대본: {(script or '')[:900]}")
    for _ in range(3):
        # 라운드로빈 — _current_key_and_idx는 늘 live[0]만 줘서 1번 키만 때린다(2026-07-23 교훈).
        key, ki = comment_gen._next_live_key_and_idx()
        if key is None:
            return fallback
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL, contents=_PROMPT + body,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            qs = parse_queries(resp.text, limit=limit)
            # 타깃도 뒤에 남겨둔다 — AI가 헛다리를 짚었을 때 사장님이 되돌아갈 자리.
            if target and target not in qs:
                qs.append(target)
            return qs or fallback
        except Exception as e:  # noqa: BLE001 — 검색어 제안 실패가 기능을 죽이면 안 된다
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return fallback
    return fallback
