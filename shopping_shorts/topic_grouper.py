"""수집 배치를 AI(Gemini)가 "같은 제품/주제" 단위로 그룹핑 — "같은 주제 모아보기"
기능의 원자료(2026-07-13).

카테고리(ai_categorize.py)는 너무 굵어서("생활용품"만 수십 개) 진짜 같은 제품을
다루는 릴스끼리 묶지 못한다. 이 모듈은 캡션을 의미로 읽어 같은 제품/주제면 같은
로컬 그룹번호를 매기게 하고(표현이 달라도 — "자석 케이블 정리" ≈ "실리콘 자석
케이블"), 호출부가 run_date와 조합해 전역 group_id로 변환한다.

키풀 로테이션·클라이언트 캐시·소진판정은 ai_categorize.py와 동일하게
comment_gen의 것을 재사용한다. 배치(48h 창) 안에서만 그룹핑되고 지난 배치와는
안 섞인다 — 화면도 어차피 48h만 보여주므로 범위가 자연히 일치한다.
"""
import json

from google.genai import types

from shopping_shorts import comment_gen

_MODEL = comment_gen._MODEL
_BATCH = 25

_PROMPT = """너는 한국 쇼핑/생활 숏폼 릴스의 "주제 그룹핑" 담당이다.
아래 항목들의 [caption]을 읽고, 서로 같은 제품이나 같은 노하우/주제를 다루는
것끼리 같은 group 번호(정수, 1부터)를 매겨라. 표현이 달라도 실제로 같은
제품/주제면 같이 묶는다(예: "자석 케이블 정리"와 "실리콘 자석 케이블"은 같은
제품 → 같은 group). 겹치는 게 전혀 없는 항목은 자기 혼자만의 고유 번호를 준다.
채널명([channel])은 참고만 하고 반드시 caption 내용으로 판단하라.

출력은 반드시 JSON 객체 하나로만: {"0":1,"1":2,"2":1,...}
키는 입력의 i 값(문자열), 값은 group 번호(정수). 다른 형식 금지.
입력:
"""


def _parse(raw):
    """Gemini 응답 → {int_index: int_group}. 실패 시 {}."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                out[int(k)] = int(v)
            except (TypeError, ValueError):
                pass
    return out


def _group_batch(batch, max_key_tries=3):
    """batch: [(idx, item), ...] → {idx: local_group_num}. 실패·무키면 {}."""
    payload = [{"i": idx,
                "channel": (it.get("name") or "")[:40],
                "caption": (it.get("caption") or "")[:300]}
               for idx, it in batch]
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return {}
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL,
                contents=_PROMPT + json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return _parse(resp.text)
        except Exception as e:  # noqa: BLE001 — 그룹핑 실패는 치명적이지 않다(부가기능)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)
                continue
            return {}
    return {}


def group_items(items, run_tag, batch_size=_BATCH):
    """items([{shortcode, name, caption}, ...]) → {shortcode: group_id}.

    run_tag: 배치를 구분하는 문자열(예: run_date) — 전역 고유 group_id 생성용
    (배치마다 로컬 그룹번호 1,2,3...이 겹치지 않게 접두어로 붙인다).
    키 미설정/전부 실패면 빈 dict(기능 조용히 비활성 — 폴백 없음, 부가기능이라
    죽여도 수집 자체엔 영향 없음)."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not items:
        return {}
    enum = list(enumerate(items))
    mapping = {}
    for start in range(0, len(enum), batch_size):
        out = _group_batch(enum[start:start + batch_size])
        for idx, local_gid in out.items():
            if 0 <= idx < len(items):
                sc = items[idx].get("shortcode")
                if sc:
                    mapping[sc] = f"{run_tag}_{local_gid}"
    return mapping
