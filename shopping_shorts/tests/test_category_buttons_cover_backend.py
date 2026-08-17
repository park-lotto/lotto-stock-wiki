"""카테고리 버튼이 백엔드 카테고리를 전부 덮는지 — '전체 = 버튼 합'이어야 한다.

★이 사고는 이미 두 번 났다(index.html:582 주석):
  2026-07-16 홈템 병합 때 매핑을 안 고쳐 두 덩어리가 통째로 누락됐고,
  2026-07-31 가전→홈템 때도 같은 자리였다.
TOPIC_CTYPE에 없는 카테고리는 undefined가 되어 **어느 버튼에도 안 뜬다** —
데이터는 있는데 화면에서 찾을 길이 없어진다(조용한 실패).

2026-08-18 '제품정체형'을 새로 만들면서 세 번째로 밟을 뻔했다. 그래서 못 박는다:
categorize.KEYWORDS의 모든 키 + '기타'가 TOPIC_CTYPE에 있어야 하고,
그 값은 전부 CTYPES의 key여야 한다.
"""
import pathlib
import re

from shopping_shorts.categorize import KEYWORDS, TOPIC_CTYPE as BACKEND_CTYPE

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _js_topic_ctype():
    """index.html의 TOPIC_CTYPE(프론트 매핑)을 {백엔드카테고리: 버튼key}로 읽는다."""
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const TOPIC_CTYPE = \{(.*?)\};", html, re.S)
    assert m, "index.html에서 TOPIC_CTYPE을 못 찾았다"
    return dict(re.findall(r"(\w+)\s*:\s*\"([^\"]+)\"", m.group(1)))


def _js_ctype_keys():
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const CTYPES = \[(.*?)\];", html, re.S)
    assert m, "index.html에서 CTYPES를 못 찾았다"
    return set(re.findall(r'key:"([^"]+)"', m.group(1)))


def test_모든_백엔드_카테고리가_버튼_매핑에_있다():
    """categorize가 내는 값 중 프론트가 모르는 게 있으면 그 카드는 사라진다."""
    front = _js_topic_ctype()
    expected = set(KEYWORDS) | {"기타"}
    missing = expected - set(front)
    assert not missing, (
        f"프론트 TOPIC_CTYPE에 없는 백엔드 카테고리: {sorted(missing)} "
        "— 이 카테고리 카드는 어느 버튼에도 안 뜬다(index.html:582 주석의 재발)")


def test_매핑값이_전부_실제_버튼이다():
    """매핑은 있는데 그런 버튼이 없으면 역시 안 뜬다."""
    front = _js_topic_ctype()
    keys = _js_ctype_keys()
    bad = {k: v for k, v in front.items() if v not in keys}
    assert not bad, f"버튼이 없는 매핑값: {bad} (CTYPES key: {sorted(keys)})"


def test_제품정체형_버튼이_있다():
    """2026-08-18 신설 축 — 이븐쇼핑류가 '기타'에 묻히지 않게."""
    front = _js_topic_ctype()
    assert front.get("제품정체형") == "제품형", "제품정체형 매핑이 없거나 틀렸다"
    assert "제품형" in _js_ctype_keys(), "제품정체 버튼이 CTYPES에 없다"


def test_백엔드_ctype축과_어긋나지_않는다():
    """categorize.TOPIC_CTYPE(백엔드)도 제품정체형을 알고 있어야 한다."""
    assert BACKEND_CTYPE.get("제품정체형") == "제품형"
