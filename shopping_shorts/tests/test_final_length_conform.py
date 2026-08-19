"""믹스 최종 총량 재측정(2026-08-11 사장님 '25~35초') — 리라이트 팽창이 재측정 없이
나가던 구멍의 배선 잠금 + _conform_overflow_beats 계약."""
from pathlib import Path

from shopping_shorts import edit_plan as ep


def test_wiring_two_conform_calls():
    src = Path(ep.__file__).read_text(encoding="utf-8")
    # 리라이트 전 1회(채점용) + 리라이트·서명보장 뒤 최종 1회 = 2곳
    assert src.count('_conform_overflow_beats(plan["beats"], target_seconds)') >= 2
    # 최종 호출이 restyle 뒤에 있다
    assert src.rindex('_conform_overflow_beats(plan["beats"]') > src.rindex("apply_restyle(plan")


def test_within_budget_untouched():
    beats = [{"narration": "짧은 문장."}, {"narration": "또 짧은 문장."}]
    out = ep._conform_overflow_beats([dict(b) for b in beats], 30)
    assert [b["narration"] for b in out] == [b["narration"] for b in beats]


def test_overflow_shrinks_with_injected_conform():
    long = "가" * 200
    beats = [{"narration": long}, {"narration": long}]
    out = ep._conform_overflow_beats(beats, 10, conform=lambda t, s: t[: int(s * 10)])
    assert sum(len(b["narration"]) for b in out) < 400
