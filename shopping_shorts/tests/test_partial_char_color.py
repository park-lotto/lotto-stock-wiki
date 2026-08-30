# -*- coding: utf-8 -*-
"""🖍 글자별 색(2026-08-30 사장님 "바꾸고 싶은 글자만 컬러 바꿀 수 있게").
헤드카피(영상 drawtext)와 썸네일(캔버스)이 **같은 규칙**으로 자르는지 지킨다."""
import pathlib

from shopping_shorts import video_assemble as va

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_build_segments_partial_inside_word():
    """단어 일부('꿀템')만 색이 바뀐다 — 예전엔 단어 전체가 일치해야만 됐다."""
    segs = va._build_segments("쿠팡꿀템", "#FFFFFF", [{"keyword": "꿀템", "color": "#FFD400"}])
    assert [(t, c) for t, c, _b, _bc in segs] == [("쿠팡", "#FFFFFF"), ("꿀템", "#FFD400")]


def test_build_segments_longer_rule_wins_on_overlap():
    """겹치면 긴 규칙이 먼저 자리를 잡는다(짧은 규칙이 긴 걸 조각내면 색이 튄다)."""
    rules = [{"keyword": "고기", "color": "#FF0000"}, {"keyword": "얼린고기", "color": "#00FF00"}]
    segs = va._build_segments("얼린고기 보관", "#FFFFFF", rules)
    assert segs[0][:2] == ("얼린고기", "#00FF00")


def test_build_segments_no_rules_single_segment():
    segs = va._build_segments("안녕하세요", "#FFFFFF", [])
    assert segs == [("안녕하세요", "#FFFFFF", False, None)]


def test_build_segments_whole_word_still_works():
    """종전 동작(단어 전체 일치)도 그대로 — 부분 매칭이 이를 포함한다."""
    segs = va._build_segments("나만 몰랐던 쿠팡", "#FFFFFF", [{"keyword": "쿠팡", "color": "#FF2D2D"}])
    assert segs[-1][:2] == ("쿠팡", "#FF2D2D")


def test_ui_has_partial_color_pickers():
    """헤드카피·썸네일 양쪽에 '고른 글자 색칠' 배선이 살아 있어야 한다."""
    assert "function hlSegments(" in HTML          # 자르는 규칙은 한 곳
    assert "function hcPaintSelection(" in HTML     # 헤드카피
    assert "function thumbPaintSelection(" in HTML  # 썸네일
    assert 'id="thumbTextArea"' in HTML             # 선택 범위를 읽는 칸
    assert "L.hl && L.hl.length" in HTML            # 썸네일 렌더가 규칙을 읽는다
