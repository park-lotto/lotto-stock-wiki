"""채널당 N개 상한 — 2026-08-18 사장님 "체널당 최신영상 2개까지만 배치하면 몇개 나오나".

왜: 한 채널이 최대 53장까지 화면을 도배했다(실측). 레퍼런스를 훑는 목적엔
'같은 채널 50장'이 아니라 '채널이 몇 개인가'가 중요하다.
    실측 5,681장 → 1,347장(-76%) · 채널 888개는 그대로 유지

★어떤 2개를 남길지는 여기서 정하지 않는다 — **지금 켠 정렬 탭**이 정한다.
사장님: "검증된 체널들은 최신순이 맞는건데. 조회수터진것도 물론 필요하고"
    🕒 최신순 탭  → 채널당 최신 2개
    👁 조회수순 탭 → 채널당 조회수 상위 2개
실측 겹침 62% = 두 탭이 실제로 다른 영상을 보여준다(38%가 다름). 그래서 하나로 못 박으면
나머지 한쪽을 잃는다. 정렬 뒤에 자르는 이 순서가 곧 계약이다(0순위-B: 기준은 한 곳에서만).
"""
import pathlib
import re

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _html():
    return INDEX.read_text(encoding="utf-8")


def test_상한_상수와_기본켜짐():
    html = _html()
    assert "PER_CHANNEL_MAX = 2" in html, "채널당 상한 상수가 없다"
    assert "PER_CHANNEL_ON" in html, "on/off 플래그가 없다"
    assert "localStorage.getItem('ss_perch') !== '0'" in html, \
        "기본이 켜짐이 아니다(끈 적 없으면 켜져 있어야 한다)"


def test_정렬_뒤에_자른다():
    """★핵심 계약 — 정렬보다 먼저 자르면 '최신순 2개'가 아니라 아무거나 2개가 남는다."""
    html = _html()
    sort_at = html.find("items.sort((a,b)=> sortKey(b)-sortKey(a))")
    cut_at = html.find("if(PER_CHANNEL_ON)")
    assert sort_at != -1, "정렬 코드를 못 찾았다"
    assert cut_at != -1, "채널당 상한 코드를 못 찾았다"
    assert sort_at < cut_at, \
        "채널당 상한이 정렬보다 먼저 돈다 — 탭이 고른 순서가 무시된다"


def test_상한은_렌더상한보다_먼저():
    """채널당 자르기 → 그다음 렌더 상한. 순서가 뒤집히면 200장 안에서만 접혀 효과가 준다."""
    html = _html()
    cut_at = html.find("if(PER_CHANNEL_ON)")
    render_cap_at = html.find("items.slice(0, RENDER_CAP)")
    assert cut_at < render_cap_at, "채널당 상한이 렌더 상한보다 뒤에 있다"


def test_접힌_건수를_보여준다():
    """숨긴 걸 숫자로 안 알리면 '영상이 사라졌다'로 읽힌다."""
    html = _html()
    assert "_perChCut" in html, "접힌 건수를 세지 않는다"
    assert "건 접힘" in html, "접힌 건수를 화면에 안 보여준다"


def test_토글이_있고_상태를_기억한다():
    html = _html()
    assert "function togglePerChannel" in html, "토글 핸들러가 없다"
    assert 'data-f="perch"' in html, "토글 버튼이 없다"
    assert "localStorage.setItem('ss_perch'" in html, "껐다 켠 상태를 기억하지 않는다"


def test_renderFilterButtons가_perch를_덮지_않는다():
    """perch는 STATE.filters가 아니라 전용 플래그다 — 덮어쓰면 새로고침 때 꺼진 것처럼 보인다."""
    html = _html()
    assert re.search(r'if\(b\.dataset\.f === "perch"\)', html), \
        "renderFilterButtons가 perch를 STATE.filters로 덮어쓴다"
