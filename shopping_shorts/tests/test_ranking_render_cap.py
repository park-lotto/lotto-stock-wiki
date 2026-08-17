"""랭킹 카드 렌더 상한 — 2026-08-18 사장님 "인스타에서 유튜브 넘어가면 버퍼가 엄청심해".

원인(실측): 카드 수가 플랫폼마다 35배 차이다.
    인스타 161장 / 유튜브 5,681장
서버는 멀쩡했다 — /api/reference 프로파일 0.14초
    (load 0.06 · vision_tags 0.01 · durations 0.01 · json.dumps 0.06, 3.1MB)
느린 쪽은 브라우저다. `items.map(...)`이 상한 없이 5,681장을 innerHTML 한 방에 만들면서
이미지 5,681개가 동시에 걸려 탭 전환이 몇 초씩 멈춘다.

처방: 데이터를 자르는 게 아니라 **그리기만 나눠 한다**(상한 + [더 보기]).
"""
import pathlib
import re

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _html():
    return INDEX.read_text(encoding="utf-8")


def test_render_cap_exists():
    """상한 상수가 있어야 한다."""
    html = _html()
    assert "RENDER_STEP" in html, "렌더 상한 상수가 사라졌다"
    assert re.search(r"let RENDER_CAP\s*=", html), "RENDER_CAP 선언이 없다"


def test_render_slices_items():
    """실제로 잘라서 그려야 한다 — 상수만 있고 안 쓰면 의미가 없다."""
    html = _html()
    assert re.search(r"items\s*=\s*items\.slice\(0,\s*RENDER_CAP\)", html), \
        "RENDER_CAP으로 items를 자르는 코드가 없다"


def test_show_more_button_exists():
    """잘린 나머지에 도달할 길이 있어야 한다(데이터 손실처럼 보이면 안 된다)."""
    html = _html()
    assert "function showMoreCards" in html, "[더 보기] 핸들러가 없다"
    assert "showMoreCards()" in html, "[더 보기] 버튼이 렌더에 안 붙었다"
    assert "RENDER_CAP += RENDER_STEP" in html, "더 보기가 상한을 안 늘린다"


def test_cap_resets_unless_keepcap():
    """★탭·검색·필터가 바뀌면 상한이 리셋돼야 한다.

    안 하면 유튜브에서 5,000장까지 늘린 상태가 인스타 탭까지 따라가 같은 증상이 난다."""
    html = _html()
    assert re.search(r"if\(!\(opts && opts\.keepCap\)\)\s*RENDER_CAP\s*=\s*RENDER_STEP", html), \
        "render()가 상한을 리셋하지 않는다"
    assert "render({keepCap:true})" in html, "더 보기가 상한을 리셋시켜 버린다"


def test_total_count_shown():
    """몇 장 중 몇 장인지 보여야 한다 — 안 보이면 '검색이 안 된다'로 오해한다."""
    html = _html()
    assert "_total" in html, "전체 건수를 안 세고 있다"
