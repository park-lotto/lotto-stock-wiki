from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_no_vmake_anywhere_in_produce_html():
    # 사용자 노출 UI 파일 전체에서 벤더명 완전 제거(주석 포함)
    assert "VMake" not in HTML and "vmake" not in HTML


def test_new_brand_and_card_markup_present():
    assert "숏템 고품질 자막제거기" in HTML       # 브랜드 히어로 타이틀
    assert 'class="hero' in HTML                  # 히어로 카드
    assert 'id="cleanShowcase"' in HTML           # 항상 보이는 데모 쇼케이스
    assert 'class="chips"' in HTML                # 기능 칩
    assert 'class="sw-track"' in HTML             # 프리미엄 스위치 트랙


def test_state_render_strings_present():
    # 로딩 스캔 연출·완료 C비교·실패 친절문구가 JS innerHTML에 존재
    assert "AI가 자막 영역을 자연스럽게 복원하는 중" in HTML
    assert "길면 수십 분" in HTML
    assert 'class="cp-compare"' in HTML
    assert "cp-arrow" in HTML and "AI 제거" in HTML
    assert "자막 제거에 실패했어요" in HTML


def test_motion_keyframes_present():
    for kf in ["@keyframes rise", "@keyframes scan", "@keyframes drawArrow",
               "@keyframes checkPop", "@keyframes flow"]:
        assert kf in HTML, kf
    # 접근성: 모션 축소 존중
    assert "prefers-reduced-motion" in HTML


def test_legacy_ids_and_handlers_preserved():
    # JS가 참조하는 계약이 안 깨졌는지
    for tok in ['id="subToggle"', 'id="subState"', 'id="cleanPreviewWrap"',
                'id="btnCleanPreview"', 'id="cleanPreview"',
                'onchange="onSubToggle()"', 'onclick="startCleanPreview()"']:
        assert tok in HTML, tok
