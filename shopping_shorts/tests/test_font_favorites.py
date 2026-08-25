# -*- coding: utf-8 -*-
"""폰트 즐겨찾기(2026-08-26) — 계정마다 별을 눌러 자주 쓰는 폰트를 맨 위로.

기본값은 사장님이 fonts.json의 star로 정해두고, 사용자가 바꾸면 그 계정 것으로
서버(customer_prefs)에 남는다.

★여기서 지키는 것
  ① '한 번도 안 고침'과 '별을 다 끔'은 다르다 — 후자를 기본값으로 되돌리면
     사용자가 일부러 비운 걸 무시하는 셈이다.
  ② 계정끼리 섞이지 않는다.
  ③ 정렬 판단은 화면에서 fontList() **하나**만 한다(0순위-B). 폰트 목록을
     그리는 곳이 5군데라 각자 정렬하면 화면마다 순서가 달라진다.
"""
import json
import pathlib
import re
import tempfile

import pytest

from shopping_shorts.store import Store
from shopping_shorts.tests.js_harness import run_js, requires_node

BASE = pathlib.Path(__file__).resolve().parent.parent.parent
PRODUCE = BASE / "shopping_shorts" / "static" / "produce.html"
FONTS_JSON = BASE / "shopping_shorts" / "static" / "fonts.json"
KEY = "font_favorites"


# ── 저장 계층 ────────────────────────────────────────────────
def _store():
    return Store(pathlib.Path(tempfile.mkdtemp()) / "t.db")


def test_저장한적_없으면_기본값을_준다():
    s = _store()
    assert s.get_pref(KEY, 1, default=["A.ttf"]) == ["A.ttf"]


def test_저장하면_그_값이_나온다():
    s = _store()
    s.set_pref(KEY, ["X.ttf", "Y.ttf"], 1)
    assert s.get_pref(KEY, 1, default=["A.ttf"]) == ["X.ttf", "Y.ttf"]


def test_계정끼리_섞이지_않는다():
    s = _store()
    s.set_pref(KEY, ["X.ttf"], 1)
    assert s.get_pref(KEY, 2, default=["A.ttf"]) == ["A.ttf"]


def test_별을_전부_꺼도_기본값으로_안_돌아간다():
    """★핵심: 빈 리스트는 '비움'이지 '없음'이 아니다."""
    s = _store()
    s.set_pref(KEY, [], 1)
    assert s.get_pref(KEY, 1, default=["A.ttf"]) == []


def test_되돌리면_기본값으로_간다():
    s = _store()
    s.set_pref(KEY, ["X.ttf"], 1)
    s.clear_pref(KEY, 1)
    assert s.get_pref(KEY, 1, default=["A.ttf"]) == ["A.ttf"]


def test_손상된_값이_화면을_막지_않는다():
    """JSON이 깨져도 기본값으로 넘어가야 한다(fail-open)."""
    s = _store()
    with s._conn() as c:
        c.execute("INSERT INTO customer_prefs(customer_id,key,value) VALUES(?,?,?)",
                  (1, KEY, "{망가진"))
    assert s.get_pref(KEY, 1, default=["A.ttf"]) == ["A.ttf"]


# ── 기본값의 출처 ────────────────────────────────────────────
def test_기본값은_fonts_json의_star에서_온다():
    """파일명을 코드에 또 적지 않는다 — 정본은 fonts.json 하나(0순위-B)."""
    from shopping_shorts import app as app_module
    want = [f["file"] for f in json.loads(FONTS_JSON.read_text(encoding="utf-8"))
            if f.get("star")]
    assert app_module._font_fav_default() == want
    assert want, "star가 하나도 없다 — 기본 즐겨찾기가 빈다"


# ── 화면 정렬 ────────────────────────────────────────────────
pytestmark_node = requires_node


def _extract(fn_names):
    """produce.html에서 함수 몇 개만 떼어 온다(브라우저 없이 돌리려고)."""
    src = PRODUCE.read_text(encoding="utf-8")
    out = []
    for name in fn_names:
        m = re.search(r"^function %s\(.*?^}" % re.escape(name), src, re.S | re.M)
        assert m, f"{name} 을 못 찾았다"
        out.append(m.group(0))
    return "\n".join(out)


@requires_node
def test_즐겨찾기가_맨_위로_가고_그_안에서는_원래_순서를_지킨다():
    js = """
    const HC_FONTS=[{file:'a'},{file:'b'},{file:'c'},{file:'d'}];
    let FONT_FAV=['c','a'];
    """ + _extract(["isFav", "fontList"]) + """
    console.log(fontList().map(f=>f.file).join(','));
    """
    # 즐겨찾기 a,c가 앞으로 — 단 HC_FONTS 순서(a 먼저)를 지킨다
    assert run_js(js) == "a,c,b,d"


@requires_node
def test_즐겨찾기가_비면_원래_순서_그대로다():
    js = """
    const HC_FONTS=[{file:'a'},{file:'b'}];
    let FONT_FAV=[];
    """ + _extract(["isFav", "fontList"]) + """
    console.log(fontList().map(f=>f.file).join(','));
    """
    assert run_js(js) == "a,b"


@requires_node
def test_서버응답_전에는_원래_순서로_그린다():
    """FONT_FAV=null(아직 못 받음)이어도 목록이 비거나 죽으면 안 된다."""
    js = """
    const HC_FONTS=[{file:'a'},{file:'b'}];
    let FONT_FAV=null;
    """ + _extract(["isFav", "fontList"]) + """
    console.log(fontList().map(f=>f.file).join(','));
    """
    assert run_js(js) == "a,b"


# ── 회귀 방어 ────────────────────────────────────────────────
def test_폰트_목록을_그리는_곳이_전부_fontList를_쓴다():
    """★한 곳이라도 HC_FONTS를 직접 map하면 그 화면만 별 순서가 안 먹는다.
    (설명·주석용 언급은 제외하고, 실제로 목록을 그리는 .map 호출만 본다)"""
    src = PRODUCE.read_text(encoding="utf-8")
    bad = re.findall(r"HC_FONTS\.map\(", src)
    assert not bad, (
        f"HC_FONTS.map( 이 {len(bad)}곳 남아 있다 — fontList()로 바꿔라.\n"
        f"  안 바꾸면 그 화면만 즐겨찾기 순서가 안 먹는다(0순위-B).")


def test_별_클릭이_폰트_선택으로_새지_않는다():
    """별은 항목 안에 있다 — stopPropagation이 없으면 누를 때 폰트까지 바뀐다."""
    src = PRODUCE.read_text(encoding="utf-8")
    m = re.search(r"async function toggleFav\(.*?^}", src, re.S | re.M)
    assert m, "toggleFav 를 못 찾았다"
    assert "stopPropagation" in m.group(0)
    assert "preventDefault" in m.group(0)
