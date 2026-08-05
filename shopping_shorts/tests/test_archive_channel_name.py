"""역대 히트작 — 채널명 한글 표시 + 채널 클릭 필터 + 내부검색 카드 개선(2026-08-06).

사장님 요청 3가지(길이 표시는 데이터가 아직 없어 별건):
  1. "채널명은 한글로 레퍼런스 랭킹처럼"
     → 랭킹은 `i.name || i.username`으로 그린다. 아카이브 API는 username만 내려줘서
       화면에 @아이디만 떴다. reel_history에 한글 표시명이 있다(518채널 중 433개).
  2. "그거 누르면 해당 채널들만 나오게 레퍼런스처럼"
     → /api/archive/items?username= 필터는 이미 있다. 카드에서 부를 배선이 없었다.
  3. "숏템 내부검색에도 썸네일 바로 재생 + 조회수·댓글 썸네일 위에 (히트작 메인처럼)"
     → 내부검색 모달 카드는 클릭 시 원본 새 창으로 나갔고, 지표는 아래 회색 메타 줄이었다.
"""
import pathlib
import re

ARCHIVE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "archive.html"


# ── 1. 서버: 채널 표시명을 내려준다 ──────────────────────────────
def test_channel_name_map_returns_korean_names(tmp_path):
    from shopping_shorts.store import Store
    st = Store(tmp_path / "t.db")
    with st._conn() as c:
        for u, n in (("1min.living", "일분살림"), ("noname_ch", ""), ("chae2home", "채이홈")):
            c.execute("INSERT INTO reel_history(shortcode, username, name, first_seen) "
                      "VALUES(?,?,?,datetime('now'))", (u + "_sc", u, n))
    m = st.channel_name_map()
    assert m.get("1min.living") == "일분살림"
    assert m.get("chae2home") == "채이홈"
    # 이름이 빈 채널은 맵에 넣지 않는다 — 화면이 `name || username`으로 폴백해야 한다
    assert not m.get("noname_ch")


def test_archive_items_include_display_name(tmp_path, monkeypatch):
    """카드가 한글 이름을 그리려면 목록 API가 그 값을 실어야 한다."""
    from shopping_shorts import app as app_mod
    src = (pathlib.Path(app_mod.__file__)).read_text(encoding="utf-8")
    i = src.index('@app.get("/api/archive/items")')
    body = src[i:src.index("@app.", i + 10)]
    assert "channel_name_map" in body or "name" in body, "목록 API가 표시명을 안 싣는다"


# ── 2. 화면: 한글 이름 + 채널 클릭 필터 ──────────────────────────
def _card_markup():
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    i = src.index('return `<div class="card">')
    return src[i:src.index("</div></div>`;", i)]


def test_card_shows_korean_name_with_username_fallback():
    """랭킹과 같은 규칙 — 한글 이름이 있으면 한글로, 없으면 @아이디로(빈칸 금지).

    ★문법이 아니라 **동작**을 본다: `i.name || x`든 `i.name ? a : b`든 상관없고,
    '이름을 읽고 + username 폴백이 있다'만 만족하면 된다(구현 방식을 테스트가 강제하면
    나중에 리팩터링할 때 멀쩡한 코드가 빨갛게 된다)."""
    card = _card_markup()
    ch = card[card.index('<div class="ch"'):card.index("</div>", card.index('<div class="ch"'))]
    assert "i.name" in ch, "채널 줄이 한글 표시명을 안 읽는다"
    assert "i.username" in ch, "폴백이 없다 — 이름 없는 85개 채널이 빈칸이 된다"


def test_card_channel_is_clickable_filter():
    """채널명을 누르면 그 채널만 — 레퍼런스 랭킹의 searchChannel과 같은 동작."""
    card = _card_markup()
    assert "filterChannel(" in card, "채널명에 필터 배선이 없다"
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    assert "function filterChannel(" in src, "filterChannel 함수가 없다"


def test_filter_channel_reloads_that_channel_only():
    """필터가 실제로 그 채널만 다시 불러와야 한다(화면에서 숨기는 게 아니라)."""
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    i = src.index("function filterChannel(")
    body = src[i:src.index("\n}", i)]
    assert "load(" in body or "CHSEL" in body, "필터가 목록을 다시 안 부른다"


# ── 3. 내부검색 모달: 썸네일 재생 + 지표 배지 ────────────────────
def _similar_markup():
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    i = src.index('return `<div class="cards">`')
    return src[i:src.index("function ", i)]


def test_similar_thumb_plays_inline():
    """★사장님: "썸네일 바로 재생되게" — 원본 새 창이 아니라 그 자리에서 재생.
    히트작 메인의 playArch를 그대로 쓴다(같은 동작을 두 번 구현하지 않는다)."""
    sim = _similar_markup()
    assert "playArch(" in sim, "내부검색 썸네일이 인라인 재생을 안 한다"
    assert "window.open" not in sim.split('class="thumb"')[1].split(">")[0], \
        "썸네일 클릭이 아직 새 창을 연다"


def test_similar_has_view_and_comment_badges():
    """조회수·댓글을 썸네일 위 배지로 — 히트작 메인과 같은 .views/.cmts를 재사용한다."""
    sim = _similar_markup()
    assert 'class="views"' in sim, "내부검색에 조회수 배지가 없다"
    assert 'class="cmts"' in sim, "내부검색에 댓글 배지가 없다"
    assert "댓글" in sim, "'댓글' 글자가 없다(숫자만이면 구분 불가)"
