"""매칭 결과 '취소하고 다시 매칭' 버튼(2026-07-20 사장님) 회귀 가드.

장면이 대사와 안 맞거나 이상하게 나오면 매칭을 취소하고 처음부터 다시 할 수 있어야 한다.
+ produce.html 인라인 JS 구문 검증 — 제작소가 통째로 안 열리던 SyntaxError 사고(핸드오프) 방지.
"""
import pathlib
import re
import shutil
import subprocess

import pytest

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")


def test_cancel_button_and_fn_present():
    html = PRODUCE.read_text(encoding="utf-8")
    assert 'onclick="cancelMixReview()"' in html      # 버튼이 함수를 부른다
    assert "function cancelMixReview(" in html         # 함수 정의 존재
    assert "취소하고 다시 매칭" in html                 # 사장님이 볼 라벨


def test_cancel_resets_matching_state():
    # 취소는 새 매칭(startProduceMix)이 초기화하는 것과 같은 상태를 되돌려야 한다.
    html = PRODUCE.read_text(encoding="utf-8")
    body = html.split("function cancelMixReview(")[1].split("async function _restoreMixContext")[0]
    for token in ("MIX_JOB=null", "PREVIEW_STATUS=null", "clearInterval(MIX_POLL)",
                  "refreshNextBtn()", "mixReview"):
        assert token in body, token


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_produce_inline_js_syntax_ok(tmp_path):
    html = PRODUCE.read_text(encoding="utf-8")
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    js = tmp_path / "inline.js"
    js.write_text("\n;\n".join(blocks), encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
