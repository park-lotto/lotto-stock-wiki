# -*- coding: utf-8 -*-
"""대사 → 장면 시간표 — 판단 주인 plan_from_lines (관제 244).
입력: 대사 줄(list[str]) + 상품 정보 + 프리셋 → 출력: 장면표 {scenes:[{i,type,t0,dur,text,vars}], total}.
글자→초 환산은 edit_plan.speech_cps 한 곳(말속도 상수 두 벌 금지 — memory reference_말속도_상수_4벌).
TTS 가 붙으면 줄 타이밍(t0·dur)을 TTS 실측으로 바꿔 넣는다 — 장면 종류·부품 배정 규칙은 그대로.
가격·할인율 규칙(iart ecommerce promo-video): 할인가는 **계산으로만**(같은 숫자를 두 번 적지 않는다), 가짜 타이머 금지."""
from shopping_shorts.mograph import ledger

# 장면 종류 순서(쇼핑 상품 소개 10~15초): 훅 → 상품 → 가격 → 특징 → 엔드카드. 줄이 더 많으면 특징으로, 적으면 뒤부터 뺀다.
SCENE_ORDER = ["hook", "product", "price", "features", "cta"]
MIN_SCENE_S = 1.6       # 한 장면 최소 길이 — 등장 모션(0.6초)+읽기. 3단계 컷 하한(1.5초)보다 조금 길게
# 장면 종류별 최소 길이 — 그 장면의 모션이 다 보이는 시간(템플릿 시간표 실측: 가격 = 정가 0.45 → 취소선 0.5 → 배지 0.75 → 숫자 1.0 → 카운트다운 ≤1.1)
MIN_BY_TYPE = {"hook": 2.0, "product": 2.4, "price": 3.0, "features": 2.6, "cta": 2.2}
PAD_S = 0.35            # 줄 사이 숨(대사 끝 → 다음 장면)
DEFAULT_PRESET = "shop-basic"


def line_seconds(text, typ=None):
    from shopping_shorts.edit_plan import speech_cps
    n = len([c for c in (text or "") if not c.isspace()])
    return max(MIN_BY_TYPE.get(typ, MIN_SCENE_S), MIN_SCENE_S, round(n / speech_cps(text) + PAD_S, 2))


def _preset(preset_id):
    for p in ledger.load_presets():
        if p.get("preset_id") == preset_id:
            return p
    return {"preset_id": preset_id, "design_ref": {}, "motion_character": {}}


def plan_from_lines(lines, product=None, preset_id=DEFAULT_PRESET, timings=None):
    """lines: 대사 줄 / product: {name, price, discount_pct, features[], brand, cta} / timings: [{t0,dur}] TTS 실측(있으면 우선)."""
    lines = [str(x).strip() for x in (lines or []) if str(x).strip()]
    if not lines:
        raise ValueError("대사가 없습니다")
    product = dict(product or {})
    price = int(product.get("price") or 0)
    pct = max(0, min(90, int(product.get("discount_pct") or 0)))
    sale = int(round(price * (100 - pct) / 100 / 10) * 10) if price else 0    # 할인가 = 계산만(10원 단위)
    product.update({"price": price, "discount_pct": pct, "sale_price": sale})
    preset = _preset(preset_id)
    n = len(lines)
    types = list(SCENE_ORDER)
    if n < len(types):
        # 줄이 적으면 뒤쪽부터 빼되 훅·엔드카드는 남긴다(1줄이면 훅만)
        keep = ["hook"] + ([] if n == 1 else (["cta"] if n == 2 else SCENE_ORDER[1:n - 1] + ["cta"]))
        types = keep
    else:
        types = SCENE_ORDER[:-1] + ["features"] * (n - len(SCENE_ORDER)) + ["cta"]
    scenes, t = [], 0.0
    for i, (text, typ) in enumerate(zip(lines, types)):
        if timings and i < len(timings) and timings[i].get("dur"):
            t0, dur = float(timings[i].get("t0", t)), max(MIN_BY_TYPE.get(typ, MIN_SCENE_S), float(timings[i]["dur"]))
        else:
            t0, dur = t, line_seconds(text, typ)
        scenes.append({"i": i, "type": typ, "t0": round(t0, 2), "dur": round(dur, 2), "text": text})
        t = t0 + dur
    return {"preset": preset.get("preset_id"), "design_ref": preset.get("design_ref") or {},
            "motion_character": preset.get("motion_character") or {}, "product": product,
            "scenes": scenes, "total": round(t, 2), "width": 1080, "height": 1920, "fps": 30,
            "safe": {"w": 900, "h": 1400, "note": "iart tiktok short-form 후보값 — 우리 자막 위치 실측으로 확정 전"}}
