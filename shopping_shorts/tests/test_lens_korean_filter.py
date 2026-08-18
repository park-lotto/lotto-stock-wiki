"""🇰🇷 한국만 필터(2026-08-18 사장님 "여기서 한국만도 만들어줄 수 있어?").

렌즈 결과에 '🌍 해외만'(제목에 한글 없음)은 있었지만 그 반대가 없었다.
국내 레퍼런스만 보려면 눈으로 골라야 했다.

여기서 못박는 것:
  ① 판정은 '해외만'과 **같은 자**(_HANGUL_RE)를 쓴다 — 따로 만들면 한쪽만 고쳐져 어긋난다.
  ② 둘은 **서로 배타**다. 함께 켜면 '한글 있고 없고'를 동시에 요구해 결과가 늘 0이 된다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _fn(src, name):
    i = src.find("function %s(" % name)
    assert i != -1, "%s 를 못 찾음" % name
    start = src.index("{", i)
    depth = 0
    for j in range(start, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    pytest.fail("%s 끝을 못 찾음" % name)


def _run(setup, expr):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    src = INDEX.read_text(encoding="utf-8")
    hangul = src[src.index("_HANGUL_RE"):]
    hangul = hangul[:hangul.index("\n")]
    script = ("var " + hangul.split("var ", 1)[-1] if hangul.startswith("var ") else "var " + hangul)
    script = script if script.startswith("var") else "var " + hangul
    body = ("const LENS_STATE={sc:{}};\nfunction renderLens(){}\n" + script + "\n"
            + _fn(src, "toggleLensForeign") + "\n" + _fn(src, "toggleLensKorean") + "\n"
            + setup + "\nconsole.log(JSON.stringify(" + expr + "));")
    r = subprocess.run(["node", "-e", body], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_한국만과_해외만은_동시에_안_켜진다():
    out = _run("toggleLensForeign('sc'); toggleLensKorean('sc');",
               "[LENS_STATE.sc.koreanOnly, LENS_STATE.sc.foreignOnly]")
    assert out == [True, False], "한국만을 켜면 해외만은 꺼져야 한다(둘 다면 결과 0)"
    out2 = _run("toggleLensKorean('sc'); toggleLensForeign('sc');",
                "[LENS_STATE.sc.koreanOnly, LENS_STATE.sc.foreignOnly]")
    assert out2 == [False, True]


def test_같은_한글판정자를_쓴다():
    """따로 정규식을 만들면 '해외만'과 '한국만'이 서로 다른 답을 낼 수 있다."""
    src = INDEX.read_text(encoding="utf-8")
    assert src.count("if(st.koreanOnly) shown=shown.filter(i=>_HANGUL_RE.test(i.title||''));") == 1
    assert "if(st.foreignOnly) shown=shown.filter(i=>!_HANGUL_RE.test(i.title||''));" in src


def test_화면에_체크박스가_있다():
    src = INDEX.read_text(encoding="utf-8")
    assert "🇰🇷 한국만" in src and "toggleLensKorean('${shortcode}')" in src
