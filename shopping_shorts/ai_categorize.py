"""수집 항목을 캡션 기반으로 AI(Gemini)가 카테고리 재분류.

키워드 분류(categorize.py)는 빠르지만 캡션에 섞인 stray 단어에 오판한다
(실측 2026-07-13: 잡곡밥 요리영상 캡션의 '살림' 한 단어 → 생활용품으로 오판).
그래서 수집 직후 이 모듈이 캡션 의미를 읽어 category를 덮어쓴다 — AI가 주(主),
키워드는 폴백:
- 전용 Gemini 키풀(SHORTS_GEMINI_KEYS)로 배치 분류. 정상 카테고리면 덮어씀.
- 키 미설정/쿼터소진/오류면 조용히 건너뜀 → 키워드 결과 그대로 유지(폴백).
방침: 맛집(식당 방문 추천)은 '집에서 만드는 레시피'가 아니므로 기타로 둔다.

키풀 로테이션·클라이언트 캐시·소진판정은 comment_gen의 것을 재사용한다.
"""
import json

from google.genai import types

from shopping_shorts import comment_gen
from shopping_shorts.config import CATEGORIES

_MODEL = comment_gen._MODEL
_BATCH = 25
_CATS = set(CATEGORIES)

_PROMPT = """너는 한국 인스타 릴스(살림·요리·인테리어·쇼핑 숏폼) 분류기다.
각 항목의 [channel]은 참고만, 반드시 [caption] 내용으로 카테고리 하나를 정하라.
채널명엔 장르가 도배돼 있으니 캡션이 절대 우선이다.

카테고리(정확히 이 중 하나):
- 홈템: 집꾸미기·셀프인테리어·수납·공간연출 등 방법/노하우 + 살 수 있는 생활/주방 물건·가전 소개·추천
        (옛 '인테리어'+'생활용품'을 합쳤고, 2026-07-31에 '가전'까지 흡수 —
         에어프라이어·믹서기는 주방살림이자 가전이라 경계가 실무에 없다)
- 레시피: 집에서 만드는 요리·음료·베이킹·밥, 음식 비법·꿀팁 (예: "잡곡밥 지을 때 이거 넣으세요")
- 뷰티: 화장품·메이크업·스킨케어
- 기타: 캡션이 무의미하거나 위 주제 밖 (식당 방문 추천 '맛집'도 여기 — 집에서 만드는 게 아님)

출력은 반드시 JSON 객체 하나로만: {"0":"레시피","1":"홈템",...}
키는 입력의 i 값(문자열), 값은 카테고리명. 배열 등 다른 형식 금지.
입력:
"""


def _parse(raw, idxs):
    """Gemini 응답 → {int_index: category}. dict/list 둘 다 견딤. 실패 시 {}."""
    out = {}
    if not raw:
        return out
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return out
    if isinstance(data, dict):
        for k, v in data.items():
            cat = v.get("category") if isinstance(v, dict) else v
            try:
                out[int(k)] = cat
            except (TypeError, ValueError):
                pass
    elif isinstance(data, list):
        for pos, el in enumerate(data):
            if isinstance(el, dict):
                idx = el.get("i", el.get("id", el.get("index")))
                cat = el.get("category") or el.get("cat") or el.get("label")
                if idx is None and pos < len(idxs):
                    idx = idxs[pos]
                try:
                    if cat:
                        out[int(idx)] = cat
                except (TypeError, ValueError):
                    pass
            elif isinstance(el, str) and pos < len(idxs):
                out[idxs[pos]] = el
    return out


def _classify_batch(batch, max_key_tries=3):
    """batch: [(idx, item), ...] → {idx: category}. 실패·무키면 {}(폴백)."""
    payload = [{"i": idx,
                "channel": (it.get("name") or "")[:40],
                "caption": (it.get("caption") or "")[:300]}
               for idx, it in batch]
    idxs = [b[0] for b in batch]
    for _ in range(max_key_tries):
        key, ki = comment_gen._current_key_and_idx()
        if key is None:
            return {}  # 전용 풀 소진 → 폴백
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=_MODEL,
                contents=_PROMPT + json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return _parse(resp.text, idxs)
        except Exception as e:  # noqa: BLE001 — 분류 실패는 치명적이지 않다(키워드 폴백)
            if (comment_gen.key_vault.is_daily_exhausted_error(e)
                    or comment_gen.key_vault.is_account_disabled_error(e)):
                comment_gen._mark_key_exhausted(ki)  # 소진 키 제외 후 다음 키로
                continue
            return {}  # 그 외 오류는 이 배치만 포기(키워드 유지)
    return {}


def reclassify(items, batch_size=_BATCH):
    """items의 'category'를 AI(캡션)로 덮어쓴다(in-place). 변경 건수 반환.
    키 미설정이면 0(키워드 결과 유지). 배치 단위 실패는 해당 배치만 폴백.

    ★캡션 없는 항목은 아예 AI에 보내지 않는다(2026-07-30). 429 회피로 수집이 캡션을
    안 담게 되자, 근거가 채널명뿐인 항목까지 AI에 물어보고 그 '기타' 판정이 상류의
    폴백(발굴 태그·과거 이력 카테고리)을 덮어써서 랭킹이 다시 기타로 뒤덮였다
    (실측: 289건 중 277건 → 폴백 적용 후에도 248건). 판단 근거가 없으면 묻지 않는 게 맞고,
    Gemini 호출도 그만큼 준다.
    ★AI가 '기타'를 줘도 기존 값이 '기타'가 아니면 덮지 않는다 — 폴백으로 얻은 정보를
    '모르겠다'가 지우는 일을 막는다."""
    if not comment_gen.SHORTS_GEMINI_KEYS or not items:
        return 0
    enum = [(i, it) for i, it in enumerate(items) if (it.get("caption") or "").strip()]
    changed = 0
    for start in range(0, len(enum), batch_size):
        out = _classify_batch(enum[start:start + batch_size])
        for idx, cat in out.items():
            if cat not in _CATS or not (0 <= idx < len(items)):
                continue
            cur = items[idx].get("category")
            if cat == cur or (cat == "기타" and cur and cur != "기타"):
                continue
            items[idx]["category"] = cat
            changed += 1
    return changed
