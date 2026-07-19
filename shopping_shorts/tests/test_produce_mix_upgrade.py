"""조합 초안 카드에 요소 버튼·업그레이드 배선이 실렸는지(문자열 앵커 — 이 파일의 다른 mix 테스트와 동일 방식)."""
import pathlib

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def test_mix_upgrade_wiring_present():
    t = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "const MIX_ELEMS=" in t
    assert "function mixUpgrade(" in t
    assert "function mixToggleElem(" in t
    assert "/api/wiki/draft/upgrade" in t
    assert "function useDraft(i){" in t  # 이름 유지(기존 테스트 3개가 의존)
    # 요소 8개 키가 버튼 목록에 다 있는지
    for k in ["hook", "development", "twist", "characters", "appeal", "tone", "devices", "cta"]:
        assert "'%s'" % k in t or '"%s"' % k in t
