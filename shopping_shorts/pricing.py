"""작업별 포인트 단가 — 내부는 100배 정수, 화면에서만 나눈다.

왜 100배인가: points_ledger.delta가 INTEGER라 0.1P를 못 담는다(store.py:752).
소수를 쓰면 반올림 오차가 잔액에 쌓이므로 정수로만 계산한다.

단가는 admin 설정(point_cost_{op})이 있으면 그걸 쓴다 — 실측 후 배포 없이 고치려고.
기본값은 자막제거만 실비용 근거가 있고(500원/편) 나머지는 임시값이다.
"""

# 1P = 100원 (마진 0, 원가대로). 값은 '포인트×100'.
_DEFAULTS = {
    "vmake":  500,   # 5P   — VMake 실비용 500원/편 (사장님 확인 2026-08-17)
    "mix":    300,   # 3P   — ⚠️임시값. 영상 1편 Gemini+TTS 미실측
    "tts":    100,   # 1P   — ⚠️임시값. 문자수 과금 미실측
    "lens":    10,   # 0.1P — SerpApi 키당 월 100회 무료, 남용 방지용
    "script":  10,   # 0.1P — Gemini 태깅 1건 0.679원 실측 기준(최소단위)
}


def cost(store, op):
    """이 작업 1회에 깎을 포인트(×100). 모르는 작업은 0(무료)."""
    if op not in _DEFAULTS:
        return 0
    try:
        raw = store.get_setting(f"point_cost_{op}")
        if raw is not None:
            v = int(raw)
            if v >= 0:              # 음수는 충전이 돼버린다
                return v
    except (TypeError, ValueError):
        pass                        # 깨진 설정값 — 기본값으로 간다
    return _DEFAULTS[op]


def to_display(internal):
    """내부값 → 화면용. 500 → 5, 10 → 0.1. 정수면 정수로 준다(5.0P 방지)."""
    v = internal / 100
    return int(v) if v == int(v) else round(v, 2)
