"""랭킹 축 노출 규칙 — 발굴 축 숨김 + 플랫폼별 카테고리 (2026-08-26 사장님 지시).

사장님: *"발굴축은 헷갈리니까 숨겨놔 카테고리만하고 / 인스타쪽 썰쇼핑과 장비공구는 없애"*

## 두 가지 축이 헷갈렸다

같은 화면에 줄이 둘이었다:
  · 카테고리 = **무엇을** 파는가(제품)  — 홈템·뷰티·장비템…
  · 발굴 축   = **어떻게** 말하는가(화법) — 썰쇼핑·연예인·레시피
'썰쇼핑'이 **양쪽에 다 있어서** 특히 헷갈렸다(카테고리의 썰쇼핑 = 제품정체형+오용형,
발굴 축의 썰쇼핑 = 채널 화법). → 발굴 축 줄을 통째로 숨긴다.

## 인스타에는 안 맞는 카테고리가 있다

썰쇼핑(제품정체형·오용형)·장비템은 **유튜브 발굴에서 나온 축**이다. 인스타 탭에
띄워봐야 사장님이 쓰지 않는 버튼이라 화면만 복잡해진다.

★그런데 **버튼만 숨기면 그 카테고리 항목이 '전체'에서만 보이게 된다**(index.html
주석의 그 사고). 그래서 숨김은 **플랫폼별**로 하고, 유튜브에선 그대로 둔다.
"""
import pathlib
import re

import pytest

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"
HTML = INDEX.read_text(encoding="utf-8")


def _fn(name):
    """function NAME(...){...} 본문을 중괄호 균형으로 잘라낸다."""
    i = HTML.find("function %s(" % name)
    assert i != -1, "%s를 못 찾음(구조 변경?)" % name
    start = HTML.index("{", i)
    depth = 0
    for j in range(start, len(HTML)):
        if HTML[j] == "{":
            depth += 1
        elif HTML[j] == "}":
            depth -= 1
            if depth == 0:
                return HTML[start:j + 1]
    pytest.fail("%s 끝을 못 찾음" % name)


# ── ① 발굴 축 줄은 화면에 안 뜬다 ────────────────────────────────────
def test_발굴축_줄은_그려지지_않는다():
    """★사장님 지시 — 카테고리 하나만 남긴다."""
    body = _fn("renderStyles")
    assert "발굴 축" not in body, "발굴 축 줄을 아직 그린다"


def test_발굴축_판정코드는_지우지_않는다():
    """지우면 나중에 왜 없는지 아무도 모른다(platformTabs 선례).
    되살릴 수 있게 라벨 표는 남겨둔다."""
    assert "STYLE_LABELS" in HTML, "라벨 표까지 지웠다 — 되살릴 길이 없어진다"


def test_스타일_상태가_목록을_거르지_않는다():
    """숨긴 축이 STATE.style에 남아 있으면 **목록이 조용히 비어** 보인다.
    (예전에 눌러둔 값이 localStorage 등으로 살아남는 경우)"""
    body = _fn("renderStyles")
    assert "STATE.style" not in body or 'STATE.style=""' in HTML.replace(" ", ""), \
        "숨기면서 STATE.style을 비우지 않았다"


# ── ② 인스타에선 썰쇼핑·장비템 버튼을 안 보여준다 ──────────────────
def _hidden_map():
    """CTYPE_HIDDEN = {instagram:[...], ...} → dict"""
    i = HTML.find("const CTYPE_HIDDEN")
    assert i != -1, "CTYPE_HIDDEN 표가 없다"
    start = HTML.index("{", i)
    depth = 0
    for j in range(start, len(HTML)):
        if HTML[j] == "{":
            depth += 1
        elif HTML[j] == "}":
            depth -= 1
            if depth == 0:
                src = HTML[start:j + 1]
                break
    out = {}
    for m in re.finditer(r'(\w+)\s*:\s*\[([^\]]*)\]', src):
        out[m.group(1)] = re.findall(r'"([^"]+)"', m.group(2))
    return out


def test_인스타는_썰쇼핑과_장비템을_숨긴다():
    """★사장님 지시 — 인스타 탭에서 이 두 버튼은 안 보인다."""
    hidden = _hidden_map()
    assert set(hidden.get("instagram", [])) >= {"썰쇼핑", "장비템"}, \
        f"인스타 숨김 목록이 부족하다: {hidden.get('instagram')}"


def test_유튜브는_그대로_다_보인다():
    """유튜브는 이 축들이 실제로 쓰인다 — 같이 지우면 안 된다.
    (실측 2026-08-26: 유튜브 8,000건에 장비템 99·제품정체형 170·오용형 83)"""
    hidden = _hidden_map()
    assert not hidden.get("youtube"), f"유튜브에서도 숨긴다: {hidden.get('youtube')}"


def test_숨김은_버튼만이고_항목을_버리지_않는다():
    """★버튼을 숨겨도 그 카테고리 항목은 '전체'에서 계속 보여야 한다.
    거르는 코드(render)에 숨김 목록이 끼어들면 항목이 통째로 사라진다."""
    body = _fn("render")
    assert "CTYPE_HIDDEN" not in body, \
        "render()가 숨김 목록으로 항목을 거른다 — 버튼만 숨겨야 한다"


def test_숨긴_버튼이_눌려있으면_전체로_되돌린다():
    """인스타로 갈아탔는데 STATE.ctype이 숨긴 값이면 목록이 빈 채로 남는다."""
    body = _fn("renderCtypes")
    assert "STATE.ctype" in body and ("전체" in body), \
        "숨긴 버튼이 활성일 때 되돌리는 처리가 없다"


def test_렌더는_숨김표를_실제로_읽는다():
    """표만 있고 안 쓰면 화면은 그대로다."""
    body = _fn("renderCtypes")
    assert "CTYPE_HIDDEN" in body, "renderCtypes가 숨김 표를 안 읽는다"


def test_플랫폼_갈아탈때_카테고리줄을_다시_그린다():
    """★안 부르면 유튜브에서 인스타로 가도 썰쇼핑·장비템 버튼이 그대로 남는다.
    (2026-08-26 실측: switchPlatform이 renderCtypes를 안 불렀다)"""
    body = _fn("switchPlatform")
    assert "renderCtypes()" in body, "플랫폼 전환 시 카테고리 줄을 안 그린다"
