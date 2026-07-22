from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_no_vmake_anywhere_in_produce_html():
    # 사용자 노출 UI 파일 전체에서 벤더명 완전 제거(주석 포함)
    assert "VMake" not in HTML and "vmake" not in HTML


def test_new_brand_and_card_markup_present():
    assert "AI 자막 제거" in HTML
    assert 'class="clean-card"' in HTML or 'class="clean-card ' in HTML
    assert 'class="sw-track"' in HTML          # 프리미엄 스위치 트랙


def test_legacy_ids_and_handlers_preserved():
    # JS가 참조하는 계약이 안 깨졌는지
    for tok in ['id="subToggle"', 'id="subState"', 'id="cleanPreviewWrap"',
                'id="btnCleanPreview"', 'id="cleanPreview"',
                'onchange="onSubToggle()"', 'onclick="startCleanPreview()"']:
        assert tok in HTML, tok
