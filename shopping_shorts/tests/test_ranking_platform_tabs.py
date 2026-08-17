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
- 2026-08-17(4차): 쓰레드 배선 완료 — service._collect_threads()가 생겨 "비활성"
  전제가 사라졌다. 지표·창은 인스타와 동일(댓글 기준·48h, 사장님 결정).

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


def test_threads_tab_is_wired():
    """쓰레드 탭은 배선 완료 — 눌러서 들어가진다(2026-08-17 4차, 계약 뒤집힘).

    이 검사는 원래 정반대였다("switchPlatform이 붙으면 안 된다"). 그때는 백엔드가
    없어 누르면 깨졌기 때문이고, 지금은 service._collect_threads()가 생겨 그 전제가
    사라졌다 → 뒤집는다. 되돌릴 일이 생기면 이 줄이 아니라 백엔드 유무를 먼저 봐라.
    """
    html = INDEX.read_text(encoding="utf-8")
    tag = _tab_tag(html, "threads")
    assert "switchPlatform('threads'" in tag, \
        "쓰레드 탭이 다시 비활성이 됐다 — 백엔드가 있는데 못 들어간다"


def test_threads_seed_saves_as_account_kind():
    """쓰레드 시드는 kind='account'로 저장돼야 한다 — 조용한 0건을 막는 검사.

    ★addSeed의 기본 경로는 kind를 **언어코드**('ko')로 저장한다. 쓰레드가 거기로
      흘러가면 service._collect_threads의 `kind == "account"` 필터에 안 걸려
      "등록은 됐는데 수집이 0건"이 된다 — 화면엔 아무 오류도 안 뜬다. 그래서
      전용 분기가 살아있는지 못박는다(2026-08-17).
    """
    html = INDEX.read_text(encoding="utf-8")
    i = html.find("async function addSeed()")
    assert i != -1, "addSeed를 못 찾음(구조 변경?)"
    body = html[i:html.find("async function removeSeed", i)]
    assert "PLATFORM==='threads'" in body, \
        "addSeed에 쓰레드 분기가 사라졌다 — 시드가 kind='ko'로 저장돼 수집이 조용히 0건이 된다"
    j = body.find("PLATFORM==='threads'")
    assert "kind:'account'" in body[j:], "쓰레드 시드가 account로 저장되지 않는다"


def test_platform_still_defaults_instagram():
    """토글을 보여도 랭킹 첫 화면은 인스타 기본이어야 한다 — 로직은 보존."""
    html = INDEX.read_text(encoding="utf-8")
    assert "PLATFORM='instagram'" in html or 'PLATFORM = "instagram"' in html, \
        "PLATFORM 기본값 instagram이 사라졌다"
    assert "function switchPlatform" in html, "switchPlatform 로직은 보존해야 한다"


