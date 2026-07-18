from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_only_clean_reference_presets():
    # 레퍼런스(HOMEDIRECTOR)와 동일한 깔끔한 흰색 프리셋 3개만 — 위치만 다름
    assert "name:'심플 화이트'" in HTML
    assert "name:'심플 화이트(하단)'" in HTML
    assert "name:'심플 화이트(크게)'" in HTML
    assert "const FEATURED = ['심플 화이트','심플 화이트(하단)','심플 화이트(크게)']" in HTML
    # 기본값 = 심플 화이트(가운데)
    assert "const DEFAULT_STYLE_NAME='심플 화이트'" in HTML
    # 요란한 옛 프리셋은 전부 제거됨
    for gone in ("name:'임팩트 옐로'", "name:'네온 글로우", "name:'화이트+민트 투톤'",
                 "name:'레드 강조'", "name:'큐트 핑크'", "name:'옐로 2톤"):
        assert gone not in HTML, f"제거됐어야 할 프리셋 잔존: {gone}"


def test_default_badge_and_use_map():
    # ⭐기본 배지 + 용도 태그 맵 유지
    assert "⭐기본" in HTML
    assert "const use = STYLE_USE[p.name]" in HTML
    assert "p.name===DEFAULT_STYLE_NAME" in HTML
    assert "'심플 화이트':'자막 가운데·깔끔'" in HTML


def test_captions_are_white_no_box():
    # 3개 모두 흰색 자막 + 박스 없음(레퍼런스 정합)
    assert "color:'#FFFFFF',size:50,y:37,outline:true,outline_color:'#000000',outline_w:3,box:false" in HTML
    assert "color:'#FFFFFF',size:50,y:82" in HTML  # 하단 변형


def test_no_fabricated_stats_on_cards():
    # 허위 지표(조회/참여 숫자)를 카드에 박지 않는다 — 정직성 잠금
    assert "조회 21만" not in HTML
    assert "참여 5.6%" not in HTML
