"""쓰레드 카드 포맷 — 문구가 주인공, 빈 지표는 안 그린다.

사장님 2026-08-18: "이건 포멧이 좀 달라야할것같은게 문구가 핵심이자나. 영상이랑
문구도 가져와야할것같은데" / "이미지만 올려온것도 여기는 써도 될것같애 + 텍스트랑"

★왜 인스타 카드를 그대로 쓰면 안 되나(실측 234건):
    followers 0% · views 0% · duration 0%   ← 쓰레드는 이 셋을 아예 안 준다
    caption  100%                            ← 그런데 정작 핵심인 캡션은 안 그렸다
  즉 빈 지표 줄만 늘어놓고 본문은 안 보이는 카드였다.

★미디어 종류가 셋이다(실측 939건): 영상 446(47%) · 이미지 299(32%) · 글만 194(21%).
  글만 있는 게시물이 좋아요 최대 17,595로 **제일 높다**(댓글 3,998). 썸네일이 없다고
  버리면 안 된다 — 카드가 세 종류를 다 소화해야 한다.
"""
import pathlib
import re

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _card_block():
    """카드 마크업 템플릿(el.innerHTML = ... 부분)을 통째로 뽑는다."""
    html = INDEX.read_text(encoding="utf-8")
    i = html.find('el.innerHTML = _notice + items.map(')
    assert i != -1, "카드 렌더 블록을 못 찾음(구조 변경?)"
    j = html.index('.join("")', i)
    return html[i:j]


def test_캡션이_카드에_그려진다():
    """쓰레드는 문구가 본체다 — caption을 쓰는 코드가 있어야 한다."""
    block = _card_block()
    assert "caption" in block, (
        "카드가 caption을 아예 안 그린다 — 쓰레드는 문구가 핵심인데 안 보인다")


def test_캡션은_이스케이프한다():
    """캡션은 사용자 입력이다. 그대로 끼우면 따옴표·꺾쇠가 마크업을 깬다."""
    block = _card_block()
    m = re.search(r"esc\(\s*i\.caption", block)
    assert m, "caption을 esc() 없이 넣고 있다 — 따옴표·꺾쇠가 카드를 깬다"


def test_썸네일_없는_글도_카드가_나온다():
    """글만 있는 게시물(썸네일 0%)에서 <img>를 빈 src로 그리면 깨진 이미지가 뜬다.

    실측 194건(21%)이 여기 해당하고, 좋아요 최대 17,595로 가장 반응이 크다.
    """
    block = _card_block()
    assert "i.thumbnail" in block, "썸네일 유무를 보는 분기가 없다"
    # 썸네일이 없을 때 <img>를 건너뛰는 삼항/조건이 있어야 한다
    assert re.search(r"i\.thumbnail\s*\?", block), (
        "썸네일이 없을 때를 안 가른다 — 글만 있는 게시물에서 깨진 이미지가 뜬다")


def test_값이_없는_지표는_그리지_않는다():
    """팔로워·조회수·영상길이는 쓰레드에서 전부 0% — 빈 줄을 그리면 안 된다."""
    block = _card_block()
    for field, label in (("i.followers", "팔로워"), ("i.views", "조회수"),
                         ("i.duration", "영상길이")):
        # 해당 필드를 쓰는 곳은 반드시 조건부여야 한다(무조건 출력 금지)
        for m in re.finditer(re.escape(field), block):
            seg = block[max(0, m.start() - 120):m.start()]
            assert ("?" in seg or "${" in seg), (
                f"{label}({field})을 조건 없이 그린다 — 쓰레드에선 빈 줄이 된다")


def test_조회수당댓글은_조회수가_있을때만():
    """density = 댓글÷조회수. 조회수가 0%인 쓰레드에선 항상 0%로 뜬다 → 감춰야 한다."""
    block = _card_block()
    i = block.find("조회수당댓글")
    assert i != -1, "조회수당댓글 줄을 못 찾음"
    seg = block[max(0, i - 200):i]
    assert "?" in seg, (
        "조회수당댓글을 조건 없이 그린다 — 조회수 없는 플랫폼(쓰레드)에서 늘 0%가 뜬다")
