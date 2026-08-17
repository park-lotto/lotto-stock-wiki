"""레퍼런스 랭킹 플랫폼 토글 — 지금 계약은 "안 보인다" (사장님 2026-08-17).

계약 이력(지우지 마라 — 왜 몇 번이나 뒤집혔는지가 중요하다):
- 2026-07-21: 안 쓴다 → display:none으로 숨김(삭제 아님, 로직 보존).
- 2026-07-24: 사장님이 뒤집음 — "토글로 인스타 유튜브 틱톡 샤오훙슈 도우인을 다
  설계하고싶다". 틱톡 무료 자동수집이 실증되며 숨길 이유가 사라졌다 → 노출이 계약.
- 2026-08-17(1차): "접어놔줘 나중에 뭐할지 모르니 안보이게" → <details>로 접음.
- 2026-08-17(2차): "이거 두개 아예안보이게 하줘 필요없음" → 접기 버튼조차 뗐다.
- 2026-08-17(3차): "인스타랑 유튜브 쓰레드탭 3개를만들어 ... 릴스랑 결이 달라서
  카테고리를 다양하게하려고 유튜브쪽을 모으는거야" → **3개만 노출**이 지금 계약.
  인스타·유튜브는 수집 결(48h·댓글 vs 14일·조회수)이 달라 탭으로 가른다.
  쓰레드는 다른 세션이 기초작업 중이라 자리만 잡아두고 비활성.
  틱톡·샤오홍슈·도우인은 요소 보존 + display:none(로직이 잡으므로 삭제 금지).

보존 계약(모든 시기 공통, 한 번도 안 바뀌었다):
PLATFORM 기본값 instagram + switchPlatform 로직은 살아 있어야 한다.
보이든 접히든 숨기든 랭킹 첫 화면은 인스타로 뜨고, 되살리기는 CSS 한 줄이어야 한다.
"""
import pathlib

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def test_platform_tabs_visible():
    """인스타·유튜브·쓰레드 3개는 화면에 나와야 한다 — 지금 계약(2026-08-17 3차)."""
    html = INDEX.read_text(encoding="utf-8")
    i = html.find('id="platformFold"')
    assert i != -1, "platformFold를 못 찾음(구조 변경?)"
    tag = html[html.rfind("<details", 0, i): html.find(">", i) + 1]
    assert "display:none" not in tag, \
        "플랫폼 줄이 숨겨졌다 — 사장님은 '탭 3개를 만들어'를 요구했다(3차)"


def _tab_tag(html, platform):
    i = html.find(f'data-platform="{platform}"')
    assert i != -1, f"{platform} 탭을 못 찾음"
    return html[html.rfind("<div", 0, i): html.find(">", i) + 1]


def test_three_tabs_shown_rest_hidden():
    """노출은 인스타·유튜브·쓰레드 3개. 나머지는 요소를 남긴 채 숨긴다(로직 보존)."""
    html = INDEX.read_text(encoding="utf-8")
    for p in ("instagram", "youtube", "threads"):
        assert "display:none" not in _tab_tag(html, p), f"{p} 탭이 숨겨졌다"
    for p in ("tiktok", "xiaohongshu", "douyin"):
        tag = _tab_tag(html, p)
        assert "display:none" in tag, \
            f"{p} 탭이 다시 노출됐다 — 3개만 보여야 한다"


def test_threads_tab_is_placeholder():
    """쓰레드는 다른 세션이 작업 중 — 자리만 잡고 눌리면 안 된다."""
    html = INDEX.read_text(encoding="utf-8")
    tag = _tab_tag(html, "threads")
    assert "switchPlatform" not in tag, \
        "쓰레드 탭에 switchPlatform이 붙었다 — 백엔드가 아직 없어 누르면 깨진다"


def test_platform_still_defaults_instagram():
    """토글을 보여도 랭킹 첫 화면은 인스타 기본이어야 한다 — 로직은 보존."""
    html = INDEX.read_text(encoding="utf-8")
    assert "PLATFORM='instagram'" in html or 'PLATFORM = "instagram"' in html, \
        "PLATFORM 기본값 instagram이 사라졌다"
    assert "function switchPlatform" in html, "switchPlatform 로직은 보존해야 한다"


