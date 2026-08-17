"""설정 화면 — 참고 화면을 베끼지 않았는지, 우리 색을 쓰는지."""
from pathlib import Path

_HTML = Path(__file__).parent.parent / "static" / "settings.html"


def test_page_exists():
    assert _HTML.exists()


def test_uses_our_mint_not_reference_green():
    """★사장님 지시 '똑같이 하면안되' — 참고 화면의 연두색을 쓰면 안 된다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert "--accent" in txt or "37e0bd" in txt
    assert "a3e635" not in txt.lower()      # 참고 화면 연두색
    assert "쇼핑팩토리" not in txt           # 참고 화면 브랜드


def test_has_two_tabs():
    txt = _HTML.read_text(encoding="utf-8")
    assert "포인트" in txt and "내 키 등록" in txt


def test_no_coupang_or_buffer_tab():
    """연동이 없는 서비스의 빈 탭을 만들지 않는다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert "쿠팡 파트너스" not in txt
    assert "Buffer" not in txt


def test_key_input_is_password_type():
    """키 입력칸이 평문으로 보이면 어깨너머로 샌다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert 'type="password"' in txt


def test_says_optional():
    """★60대 배려 — 등록을 안 해도 된다는 걸 알려야 한다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert "안 하셔도" in txt or "않으셔도" in txt


def test_route_registered():
    """클린 URL 루프에 settings가 들어갔는지."""
    app_py = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    assert '"settings"' in app_py


def test_sidebar_has_settings():
    js = (Path(__file__).parent.parent / "static" / "sidebar.js").read_text(encoding="utf-8")
    assert "/settings" in js


# ── 아래는 추가 방어 (약화 금지, 보강만) ──────────────────────────────

def test_route_is_in_clean_url_loop_not_manual():
    """★수동 라우트를 만들면 _NOCACHE 방어가 빠진다(2026-07-14 실사고).
    클린 URL 루프의 튜플 안에 settings가 들어있는지 본다."""
    app_py = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    i = app_py.index("for _pg in (")
    loop_head = app_py[i:app_py.index("):", i)]
    assert '"settings"' in loop_head, "settings가 클린 URL 루프 튜플에 없다"


def test_sidebar_settings_is_free():
    """포인트를 충전하려면 무료 등급도 설정에 들어올 수 있어야 한다."""
    js = (Path(__file__).parent.parent / "static" / "sidebar.js").read_text(encoding="utf-8")
    line = [ln for ln in js.splitlines() if "/settings" in ln]
    assert line, "sidebar.js에 /settings 항목이 없다"
    assert "free: true" in line[0], "설정 메뉴에 free:true가 없다(무료 등급이 못 들어온다)"


def test_calls_real_backend_endpoints():
    """Task 8 백엔드를 실제로 부르는지 — 목업으로 끝내지 않았는지."""
    txt = _HTML.read_text(encoding="utf-8")
    for ep in ("/api/settings/points", "/api/settings/keys",
               "/api/settings/keys/delete", "/api/settings/keys/verify"):
        assert ep in txt, f"{ep} 호출이 없다"


def test_handles_master_key_disabled():
    """enabled=false(마스터키 없음)면 등록란을 감추고 안내해야 한다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert "enabled" in txt


def test_no_framework_cdn():
    """빌드 도구가 없는 프로젝트 — 외부 CDN·프레임워크 금지."""
    txt = _HTML.read_text(encoding="utf-8").lower()
    for bad in ("cdn.jsdelivr", "unpkg.com", "cdnjs.cloudflare", "react", "vue.js"):
        assert bad not in txt, f"외부 의존 {bad} 발견"


def test_watch_link_is_constant_not_hash_href():
    """'받는 방법 영상'은 아직 URL이 없다 — href='#' 금지, 상수로 빼둔다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert 'href="#"' not in txt
    assert "GUIDE_VIDEO" in txt, "가이드 영상 URL 상수가 없다"


def test_has_refund_notice():
    """하단 고지 — 환불 원칙이 적혀 있어야 한다."""
    txt = _HTML.read_text(encoding="utf-8")
    assert "환불" in txt


def test_includes_sidebar():
    txt = _HTML.read_text(encoding="utf-8")
    assert "/sidebar.js" in txt
