"""레퍼런스 랭킹 플랫폼 토글 — 지금 계약은 "안 보인다" (사장님 2026-08-17).

계약 이력(지우지 마라 — 왜 몇 번이나 뒤집혔는지가 중요하다):
- 2026-07-21: 안 쓴다 → display:none으로 숨김(삭제 아님, 로직 보존).
- 2026-07-24: 사장님이 뒤집음 — "토글로 인스타 유튜브 틱톡 샤오훙슈 도우인을 다
  설계하고싶다". 틱톡 무료 자동수집이 실증되며 숨길 이유가 사라졌다 → 노출이 계약.
- 2026-08-17(1차): "접어놔줘 나중에 뭐할지 모르니 안보이게" → <details>로 접음.
- 2026-08-17(2차): "이거 두개 아예안보이게 하줘 필요없음" → 접기 버튼조차 뗐다.
  지금 계약 = platformFold(details)가 display:none.

보존 계약(모든 시기 공통, 한 번도 안 바뀌었다):
PLATFORM 기본값 instagram + switchPlatform 로직은 살아 있어야 한다.
보이든 접히든 숨기든 랭킹 첫 화면은 인스타로 뜨고, 되살리기는 CSS 한 줄이어야 한다.
"""
import pathlib

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def test_platform_tabs_hidden():
    """평소 화면에 안 나와야 한다 — 지금 계약(2026-08-17 2차)."""
    html = INDEX.read_text(encoding="utf-8")
    i = html.find('id="platformFold"')
    assert i != -1, "platformFold를 못 찾음(구조 변경?)"
    tag = html[html.rfind("<details", 0, i): html.find(">", i) + 1]
    assert "display:none" in tag,         "플랫폼 줄이 다시 화면에 나온다 — 사장님은 '아예 안 보이게'를 요구했다"


def test_platform_still_defaults_instagram():
    """토글을 보여도 랭킹 첫 화면은 인스타 기본이어야 한다 — 로직은 보존."""
    html = INDEX.read_text(encoding="utf-8")
    assert "PLATFORM='instagram'" in html or 'PLATFORM = "instagram"' in html, \
        "PLATFORM 기본값 instagram이 사라졌다"
    assert "function switchPlatform" in html, "switchPlatform 로직은 보존해야 한다"


