"""플랫폼마다 지표 이름이 달라야 한다(2026-08-23).

사장님: "유튜브는 시간당 조회수가 메인이어야 한다. 댓글이 없어서"
→ 실측하니 **값은 이미 조회수 기반**이었다(build_youtube_items: speed=조회수/경과h,
   중앙값 22.5/h·최대 42,417/h). 화면 라벨만 인스타 기준 '시간당댓글'로 고정돼 있어
   "댓글로 매기고 있다"고 읽힐 수밖에 없었다.
"""
import pathlib
import re

_SRC = (pathlib.Path(__file__).resolve().parents[1]
        / "static" / "index.html").read_text(encoding="utf-8")


def test_유튜브_라벨은_조회수_기준이다():
    m = re.search(r"const TAB_LABEL = \{(.*?)\n\};", _SRC, re.S)
    assert m, "TAB_LABEL이 없다"
    yt = re.search(r"youtube:\s*\{([^}]*)\}", m.group(1))
    assert yt, "youtube 라벨이 없다"
    assert "시간당 조회수" in yt.group(1)
    assert "조회수당 반응" in yt.group(1)


def test_유튜브는_팔로워당댓글_탭을_숨긴다():
    """실측 유튜브 8,776건 전부 followers 없음 — 눌러도 전부 0이라 있는 척하면 고장으로 보인다."""
    m = re.search(r"youtube:\s*\{[^}]*hide:\s*\[([^\]]*)\]", _SRC)
    assert m and "fan_density" in m.group(1)


def test_유튜브_기본정렬은_시간당_조회수다():
    m = re.search(r"const DEFAULT_TAB = \{([^}]*)\}", _SRC)
    assert m and re.search(r"youtube:\s*'speed'", m.group(1))


def test_카드_지표이름은_탭_이름을_그대로_쓴다():
    """두 벌로 적으면 탭은 '시간당 조회수'인데 카드는 '시간당댓글'이 된다(0순위-B)."""
    assert "function _statLabel" in _SRC
    assert "_statLabel('speed')" in _SRC and "_statLabel('density')" in _SRC
    # 카드에 옛 고정 문자열이 남아 있으면 안 된다
    assert "<span>시간당댓글</span>" not in _SRC
    assert "<span>조회수당댓글</span>" not in _SRC


def test_인스타는_종전_이름을_지킨다():
    """인스타는 댓글이 실제 지표다 — 바뀌면 안 된다."""
    m = re.search(r"const TAB_LABEL = \{(.*?)\n\};", _SRC, re.S)
    assert "instagram:" not in m.group(1), "인스타는 기본값(시간당댓글)을 쓴다"
