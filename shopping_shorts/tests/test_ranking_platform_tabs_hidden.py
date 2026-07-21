"""레퍼런스 랭킹 인스타/유튜브/틱톡 플랫폼 토글 숨김 (사장님 2026-07-21).

사장님이 플랫폼 전환을 안 쓴다 → 탭만 숨긴다(삭제 아님, 되돌리기 쉽게). switchPlatform·
PLATFORM 로직은 그대로 두고 PLATFORM 기본값 instagram으로 랭킹·수집·채널등록이 계속
정상 동작한다(렌즈검색과는 목적이 다른 별개 기능이라 로직 자체는 보존).
"""
import pathlib

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def test_platform_tabs_hidden():
    html = INDEX.read_text(encoding="utf-8")
    i = html.find('id="platformTabs"')
    assert i != -1, "platformTabs 요소를 못 찾음(구조 변경?)"
    tag = html[html.rfind("<div", 0, i): html.find(">", i) + 1]
    assert "display:none" in tag, "플랫폼 토글이 아직 숨겨지지 않았다"


def test_platform_still_defaults_instagram():
    """숨겨도 랭킹은 인스타 기본으로 계속 떠야 한다 — 로직은 보존."""
    html = INDEX.read_text(encoding="utf-8")
    assert "PLATFORM='instagram'" in html or 'PLATFORM = "instagram"' in html, \
        "PLATFORM 기본값 instagram이 사라졌다 — 숨김이 랭킹을 깨면 안 된다"
    assert "function switchPlatform" in html, "switchPlatform 로직은 보존해야 한다(되돌리기용)"
