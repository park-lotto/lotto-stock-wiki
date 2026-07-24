"""레퍼런스 랭킹 플랫폼 토글 — **노출**이 계약이다 (사장님 2026-07-24).

계약 이력(지우지 마라 — 왜 뒤집혔는지가 중요하다):
- 2026-07-21: 사장님이 플랫폼 전환을 안 쓴다 → 탭을 `display:none`으로 숨겼다.
  삭제가 아니라 숨김이었다 — 되돌리기 쉽게 switchPlatform·PLATFORM 로직을 보존했다.
- 2026-07-24: 사장님이 직접 뒤집었다 — "토글로 인스타 유튜브 틱톡 샤오훙슈 도우인을
  다 설계하고싶다". 틱톡 무료 자동수집(yt-dlp 계정시드)이 실증되며 숨길 이유가 사라졌다.
  → 이제 **탭이 보이는 것**이 지켜야 할 계약이다. 다시 숨기려면 이 파일부터 고쳐라.

보존 계약(양쪽 시기 공통): PLATFORM 기본값 instagram + switchPlatform 로직.
탭을 보이든 숨기든 랭킹 첫 화면은 인스타로 떠야 한다.
"""
import pathlib

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def test_platform_tabs_visible():
    html = INDEX.read_text(encoding="utf-8")
    i = html.find('id="platformTabs"')
    assert i != -1, "platformTabs 요소를 못 찾음(구조 변경?)"
    tag = html[html.rfind("<div", 0, i): html.find(">", i) + 1]
    assert "display:none" not in tag, \
        "플랫폼 토글이 다시 숨겨졌다 — 2026-07-24 계약 위반(사장님이 5플랫폼 토글을 요구)"


def test_platform_still_defaults_instagram():
    """토글을 보여도 랭킹 첫 화면은 인스타 기본이어야 한다 — 로직은 보존."""
    html = INDEX.read_text(encoding="utf-8")
    assert "PLATFORM='instagram'" in html or 'PLATFORM = "instagram"' in html, \
        "PLATFORM 기본값 instagram이 사라졌다"
    assert "function switchPlatform" in html, "switchPlatform 로직은 보존해야 한다"
