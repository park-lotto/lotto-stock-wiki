"""역대 히트작 카드 — 댓글수를 썸네일 위에 조회수와 나란히 보여준다(2026-08-06).

사장님: "댓글수를 썸네일 조회수 옆에 댓글이라고 눈에 띄게 표시해줘 / 결국 댓글수가 제일 중요함."

이 화면은 기본 정렬이 이미 댓글순인데(SORT='comments'), 정작 카드에서 댓글수는
아래 메타 줄에 `❤ 3 · 💬 8.4만 · 2025-12-30`처럼 회색 작은 글씨로 묻혀 있었다.
썸네일 위엔 조회수(👁)만 금색 배지로 떠 있어서, **정렬 기준인 값이 화면에서 제일 안 보였다.**

여기서 못 박는 것:
1. 썸네일 위에 댓글 배지가 있다(조회수 배지와 같은 줄).
2. '댓글'이라는 말이 붙는다 — 숫자만 두 개 나란히 있으면 뭐가 뭔지 모른다(60대 어포던스).
3. 조회수 배지는 그대로 남는다(맞바꾸는 게 아니라 나란히).
"""
import pathlib
import re

ARCHIVE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "archive.html"


def _card_markup():
    """카드 렌더 템플릿(썸네일 블록)만 잘라온다 — 비슷한 배지가 다른 곳(내부검색 모달)에도
    있어서 파일 전체를 훑으면 엉뚱한 곳을 보고 통과할 수 있다."""
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    i = src.index('return `<div class="card">')
    return src[i:src.index("</div></div>`;", i)]


def test_comment_badge_is_on_the_thumbnail():
    """★핵심. 댓글수가 썸네일 위 배지로 뜬다 — 정렬 기준이 제일 잘 보여야 한다."""
    card = _card_markup()
    assert "cmts" in card, "썸네일 댓글 배지(.cmts)가 없다"
    assert "i.comments" in card, "댓글 배지가 실제 댓글수를 안 읽는다"
    # 배지가 썸네일(.thumb) 안에 있어야 한다 — body로 내려가면 그냥 메타 줄과 같아진다
    thumb = card[card.index('<div class="thumb">'):card.index('<div class="body">')]
    assert "cmts" in thumb, "댓글 배지가 썸네일 밖에 있다"


def test_comment_badge_is_labeled():
    """숫자만 두 개 나란히 두면 뭐가 조회수고 뭐가 댓글인지 모른다 — 글자로 붙인다."""
    card = _card_markup()
    thumb = card[card.index('<div class="thumb">'):card.index('<div class="body">')]
    m = re.search(r'class="cmts"[^>]*>([^<]*)\$\{', thumb)
    assert m, "댓글 배지 템플릿을 못 찾았다: " + thumb
    assert "댓글" in m.group(1), f"'댓글' 글자가 없다(숫자만 있으면 구분 불가): {m.group(1)!r}"


def test_views_badge_survives():
    """조회수를 밀어내면 안 된다 — 나란히 보여야 비교가 된다."""
    card = _card_markup()
    thumb = card[card.index('<div class="thumb">'):card.index('<div class="body">')]
    assert 'class="views"' in thumb and "i.views" in thumb, "조회수 배지가 사라졌다"


def test_badge_has_its_own_style():
    """조회수(금색)와 색이 같으면 나란히 놔도 안 구분된다 — .cmts 규칙이 따로 있어야 한다."""
    src = ARCHIVE_HTML.read_text(encoding="utf-8")
    assert re.search(r"^\.cmts\{", src, re.M), ".cmts CSS 규칙이 없다"
