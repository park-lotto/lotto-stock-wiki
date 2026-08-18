"""옛 로직이 새 로직을 조용히 밀어내던 회귀 차단(2026-08-18 실사고).

무슨 일이 있었나: 사장님 PC에 옛 확장(1.0.0)이 남아 있었다. 로직 첫 줄이
`if (window.__ssGrabLoaded) return;` 였던 탓에 **먼저 뜬 옛 코드가 이겨서**,
새로 배포한 채널수집 버튼이 유튜브·쓰레드에서 아예 안 떴다. 오류 한 줄 없이
조용히 죽는 형태라 원인 찾는 데 오래 걸렸다.

처방: 버전 숫자를 박아 **큰 쪽이 이어받는다**. 여기서는 node로 실제 실행해
① 옛 로직(버전 없음)이 먼저 돌아도 새 로직이 이어받는지
② 같은/더 새 버전이 이미 돌면 두 번 안 도는지
를 확인한다(문법검사로는 못 잡는 층).
"""
import pathlib
import shutil
import subprocess

import pytest

LOGIC = pathlib.Path(__file__).resolve().parents[1] / "userscript" / "grab_logic.js"


def _guard_src():
    """파일 첫머리의 가드 블록만 뽑는다(BASE 정의 직전까지)."""
    src = LOGIC.read_text(encoding="utf-8")
    i = src.index("var LOGIC_VER")
    j = src.index("var BASE =")
    return src[i:j]


def _run(setup):
    if not shutil.which("node"):
        pytest.skip("node 없음")
    script = (
        "var removed = [];\n"
        "var window = { document: null };\n"
        "var document = { querySelectorAll: function () { "
        "  return [{ remove: function () { removed.push(1); } }]; } };\n"
        "var cleared = [];\n"
        "function clearInterval(id) { cleared.push(id); }\n"
        + setup +
        "var tookOver = true;\n"
        "(function () {\n" + _guard_src() +
        "  tookOver = true; return;\n"
        "})();\n"
        "console.log(JSON.stringify({ver: window.__ssGrabVer, removed: removed.length,"
        " cleared: cleared.length}));\n"
    )
    # return 문이 함수 안에 있어야 하므로 가드를 즉시실행 함수로 감쌌다.
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    import json
    return json.loads(r.stdout)


def test_옛_로직이_먼저_돌아도_새_로직이_이어받는다():
    out = _run("window.__ssGrabLoaded = true;\n")   # 옛 코드: 버전 표시가 없다
    assert out["ver"] == 20260818, "새 로직이 버전을 남기며 이어받아야 한다"
    assert out["removed"] >= 1, "옛 버튼을 걷어내고 다시 그려야 한다"


def test_같은_버전이_이미_돌면_두_번_돌지_않는다():
    out = _run("window.__ssGrabLoaded = true; window.__ssGrabVer = 20260818;\n")
    assert out["removed"] == 0, "같은 버전이면 손대지 않고 그대로 둔다"


def test_더_새_버전이_돌면_옛_로직은_물러난다():
    out = _run("window.__ssGrabLoaded = true; window.__ssGrabVer = 20990101;\n")
    assert out["ver"] == 20990101, "더 새것이 이미 돌면 덮어쓰지 않는다"
    assert out["removed"] == 0


def test_타이머_핸들을_남긴다():
    """핸들이 없으면 다음 버전이 옛 인터벌을 끌 수 없다 — 이 줄이 빠지면 회귀."""
    assert "window.__ssGrabTimer = setInterval(tick, 2000)" in \
        LOGIC.read_text(encoding="utf-8")
