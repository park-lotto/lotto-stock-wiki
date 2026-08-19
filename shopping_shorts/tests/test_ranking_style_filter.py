"""랭킹 필터 버튼이 **모든 카테고리를 덮는가** — 조용히 사라지는 영상 차단.

실사고 구조(2026-08-19):
`index.html`의 필터는 `TOPIC_CTYPE[i.category] === STATE.ctype`으로 거른다.
그래서 **TOPIC_CTYPE에 없는 카테고리는 undefined가 되어 어느 버튼에도 안 뜬다**
— '전체'에서만 보이고 나머지 버튼에선 통째로 사라진다. 오류도 안 난다.

실측: 백엔드에 제품정체형 203건·오용형 75건이 있는데 TOPIC_CTYPE에 없어
**278건이 버튼으로는 못 찾는 상태**였다. 같은 사고가 2026-07-16 홈템 병합 때도 났다
(index.html 주석에 "매핑을 지우면 undefined가 되어 어느 버튼에도 안 뜬다"고 적혀 있다).

→ 백엔드가 낼 수 있는 카테고리 전부가 TOPIC_CTYPE에 있어야 하고,
  그 값들이 전부 CTYPES 버튼 key와 1:1이어야 한다. 이걸 코드로 못박는다.
"""
import pathlib
import re

import pytest

from shopping_shorts.categorize import KEYWORDS, TOPIC_CTYPE as BACKEND_CTYPE

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _js_obj(name):
    """index.html에서 `const NAME = {...}` 또는 `[...]`를 뽑아 문자열로."""
    html = INDEX.read_text(encoding="utf-8")
    i = html.find("const %s" % name)
    assert i != -1, "%s를 못 찾음(구조 변경?)" % name
    start = html.index("=", i) + 1
    while html[start] in " \n":
        start += 1
    open_ch = html[start]
    close_ch = {"{": "}", "[": "]"}[open_ch]
    depth = 0
    for j in range(start, len(html)):
        if html[j] == open_ch:
            depth += 1
        elif html[j] == close_ch:
            depth -= 1
            if depth == 0:
                return html[start:j + 1]
    pytest.fail("%s 끝을 못 찾음" % name)


def _topic_ctype_map():
    """TOPIC_CTYPE = {홈템:"홈템", ...} → dict"""
    src = _js_obj("TOPIC_CTYPE")
    out = {}
    for m in re.finditer(r'([\w가-힣]+)\s*:\s*"([^"]+)"', src):
        out[m.group(1)] = m.group(2)
    assert out, "TOPIC_CTYPE 파싱 실패"
    return out


def _ctype_keys():
    """CTYPES = [{key:"전체",...}, ...] → key 목록"""
    src = _js_obj("CTYPES")
    return re.findall(r'key\s*:\s*"([^"]+)"', src)


def test_백엔드_카테고리가_전부_버튼에_매핑돼있다():
    """★이게 깨지면 그 카테고리 영상은 '전체' 말고는 어디서도 안 보인다.

    백엔드가 낼 수 있는 값 = categorize.KEYWORDS의 topic들 + '기타'."""
    backend = set(KEYWORDS) | {"기타"}
    mapped = set(_topic_ctype_map())
    missing = sorted(backend - mapped)
    assert not missing, (
        "TOPIC_CTYPE에 없는 백엔드 카테고리 %s — 이 영상들은 버튼으로 못 찾는다"
        % missing)


def test_매핑값이_전부_실재하는_버튼이다():
    """오타나 옛 이름을 가리키면 그 카테고리는 영원히 0건이 된다."""
    keys = set(_ctype_keys())
    bad = {k: v for k, v in _topic_ctype_map().items() if v not in keys}
    assert not bad, "CTYPES에 없는 버튼을 가리키는 매핑: %s (버튼: %s)" % (bad, sorted(keys))


def test_전체버튼이_있다():
    assert "전체" in _ctype_keys()


def test_썰쇼핑_두갈래가_한_버튼으로_모인다():
    """사장님 지시: "지금 있는 썰쇼핑 채널종류들을 모으고".

    제품정체형(은폐형)·오용형은 대본 스파인은 따로지만 **화면에선 한 덩어리**여야 한다."""
    m = _topic_ctype_map()
    assert m.get("제품정체형") == m.get("오용형") is not None, (
        "제품정체형·오용형이 같은 버튼으로 안 모인다: %s / %s"
        % (m.get("제품정체형"), m.get("오용형")))


def test_백엔드_ctype표와_어긋나지_않는다():
    """categorize.TOPIC_CTYPE(백엔드)에 있는 topic은 화면 매핑에도 있어야 한다."""
    missing = sorted(set(BACKEND_CTYPE) - set(_topic_ctype_map()))
    assert not missing, "백엔드 ctype표에만 있고 화면에 없는 topic: %s" % missing
