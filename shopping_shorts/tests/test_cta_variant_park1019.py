# -*- coding: utf-8 -*-
"""Park님 10-19: 스티커·클릭 CTA 미인식 → 판 못 만듦 / 비수창 기본 문구 화살표 / 화살표는 TTS가 안 읽음."""
from shopping_shorts import cta_variants as cv
from shopping_shorts.edit_plan import _looks_cta_text
from shopping_shorts.narration_naturalize import naturalize, strip_arrows


def test_click_sticker_link_is_cta():
    assert _looks_cta_text("이국적인 샌드 커피 위치 구매는 화면 속 스티커를 클릭해주세요.")
    assert _looks_cta_text("궁금하시면 구매링크 확인해주세요")


def test_marked_plan_finds_cta_without_marks():
    lines = ["첫 줄 이야기", "둘째 줄 이야기", "구매는 화면 속 스티커를 클릭해주세요."]
    plan = {"beats": [{"role": "hook", "narration": lines[0]}, {"role": "feature", "narration": lines[1]},
                      {"role": "closing", "narration": lines[2]}]}
    job = {"given_script": "\n".join(lines), "script_structure": {}}
    assert cv.cta_beat_indexes(plan) == []
    assert cv.cta_beat_indexes(cv.marked_plan(plan, job)) == [2]
    assert "cta_mark" not in plan["beats"][2]          # 원본은 그대로


def test_yt_long_default_has_arrow_and_old_default_upgrades():
    d = {p["key"]: p["text"] for p in cv.PLATFORMS}
    assert "▶" in d["yt_long"]
    cfg = cv.normalize({"items": [{"key": "yt_long", "text": "아래 관련 영상을 눌러 구매링크를 확인하세요."}]})
    assert cfg["items"][2]["text"] == d["yt_long"]


def test_arrows_not_spoken():
    assert "▶" not in naturalize("아래 ▶관련 영상을 눌러 구매링크를 확인하세요.", {})
    assert "👇" not in strip_arrows("👇 아래 영상")
    assert strip_arrows("  공백 그대로  ") == "  공백 그대로  "
