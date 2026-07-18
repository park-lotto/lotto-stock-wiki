from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_style_use_map_and_default_badge():
    # 용도 태그 맵 존재 + 기본/대표 스타일이 매핑돼 있다
    assert "const STYLE_USE=" in HTML
    assert "'임팩트 옐로':'레시피·강한 훅'" in HTML
    # 카드에 ⭐기본 배지와 용도 라벨을 그린다
    assert "⭐기본" in HTML
    assert "const use = STYLE_USE[p.name]" in HTML
    assert "p.name===DEFAULT_STYLE_NAME" in HTML


def test_no_fabricated_stats_on_cards():
    # 허위 지표(조회/참여 숫자)를 카드에 박지 않는다 — 정직성 잠금
    assert "조회 21만" not in HTML
    assert "참여 5.6%" not in HTML
