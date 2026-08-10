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


# ── 메타 줄 정리(2026-08-06 사장님) ────────────────────────────────
# "채널명 아래 댓글수는 중복이니 지우고, 좋아요 갯수가 짤린다. 하트를 컬러로 바꿔"
#   - 댓글수는 이미 썸네일 위 배지(.cmts)에 크게 있다 → 아래 줄의 💬는 같은 값 두 번.
#   - 그 중복이 자리를 먹어 좋아요(❤)가 잘렸다 → 빼면 자리가 난다.
#   - ❤가 흑백 문자라 안 보였다 → 컬러로.

def test_meta_line_has_no_duplicate_comment_count():
    """썸네일 배지에 이미 있는 댓글수를 아래 줄에서 또 보여주지 않는다."""
    card = _card_markup()
    meta = card[card.index('<div class="meta">'):card.index("</div>", card.index('<div class="meta">'))]
    assert "i.comments" not in meta, f"메타 줄에 댓글수가 아직 있다(중복): {meta}"


def test_meta_line_still_shows_likes_and_date():
    """좋아요와 날짜는 남는다 — 지우는 건 '중복'인 댓글수뿐이다."""
    card = _card_markup()
    meta = card[card.index('<div class="meta">'):card.index("</div>", card.index('<div class="meta">'))]
    assert "i.likes" in meta, "좋아요가 사라졌다"
    assert "posted_at" in meta, "날짜가 사라졌다"


def test_heart_is_colored():
    """❤(흑백 문자)는 회색 메타 줄에서 안 보인다 — 색이 있는 하트로."""
    card = _card_markup()
    meta = card[card.index('<div class="meta">'):card.index("</div>", card.index('<div class="meta">'))]
    assert "❤️" in meta or "♥" in meta or "heart" in meta.lower(), \
        f"하트가 아직 흑백이다: {meta}"
