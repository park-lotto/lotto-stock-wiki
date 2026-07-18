"""6단계 SEO — 태그 칩 추가·삭제(2026-07-18, 사장님 요청).

계획서가 YAGNI로 뺐다가 T8에서 사장님이 "넣어"라고 하셔서 붙였다.
지금까지 태그 20개는 읽기 전용이었다.

produce.html의 **실제 소스**를 앵커로 잘라 Node로 실행한다(재구현이 아니다).
seoTagDel/seoTagAdd가 SEO.tags를 고치고 seoSave()로 서버에 저장하는지 본다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

# 태그 편집 함수 두 개만 잘라낸다.
_START = "function seoTagDel(i){"
_END = "function seoCopyYoutube(){"

_HARNESS = r"""
'use strict';
const _inputs = {};
global.document = {
  getElementById(id){ return (_inputs[id] = _inputs[id] || { value:'', focus(){} }); },
};
global.renderSeo = () => {};
global.seoSave = async () => { global.__saved = JSON.parse(JSON.stringify(global.SEO.tags)); };
"""

_DRIVER_TEMPLATE = r"""
(async () => {
  global.SEO = { tags: ['가', '나', '다'] };
  const inp = document.getElementById('seoTagNew');
  __ACTIONS__
  console.log(JSON.stringify({ tags: global.SEO.tags, saved: global.__saved }));
})();
"""


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


def _run(tmp_path, actions):
    driver = _DRIVER_TEMPLATE.replace("__ACTIONS__", actions)
    js = tmp_path / "t.js"
    js.write_text(_HARNESS + _slice() + driver, encoding="utf-8")
    # ★encoding="utf-8" 필수 — text=True만 주면 윈도우 cp949로 디코딩하다 한글 출력에서
    # 리더 스레드가 죽는데 예외가 삼켜져 returncode=0인데 stdout만 None이 온다(실측).
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_tag_delete_removes_and_saves(tmp_path):
    got = _run(tmp_path, "seoTagDel(1);")     # '나' 삭제
    assert got["tags"] == ["가", "다"]
    assert got["saved"] == ["가", "다"]        # 서버에도 반영


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_tag_add_appends_and_saves(tmp_path):
    got = _run(tmp_path, "inp.value = '라'; seoTagAdd();")
    assert got["tags"] == ["가", "나", "다", "라"]
    assert got["saved"] == ["가", "나", "다", "라"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_tag_add_strips_leading_hash(tmp_path):
    """사장님이 '#직장인'을 넣어도 태그엔 '직장인'만 — 유튜브 태그는 # 없이 쓴다."""
    got = _run(tmp_path, "inp.value = '#직장인'; seoTagAdd();")
    assert got["tags"][-1] == "직장인"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_tag_add_ignores_duplicate(tmp_path):
    """이미 있는 태그는 안 늘린다 — 20개 한도에 중복을 채우면 손해다."""
    got = _run(tmp_path, "inp.value = '나'; seoTagAdd();")
    assert got["tags"] == ["가", "나", "다"]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_tag_add_ignores_blank(tmp_path):
    """빈 값·공백만은 무시한다."""
    got = _run(tmp_path, "inp.value = '   '; seoTagAdd();")
    assert got["tags"] == ["가", "나", "다"]
    assert got.get("saved") is None            # 저장도 안 부른다
