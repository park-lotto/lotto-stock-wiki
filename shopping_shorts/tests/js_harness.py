"""JS 하네스 공용 실행기 — `node -e` 대신 **임시파일**로 돌린다(2026-08-19).

## 왜 이 파일이 생겼나

`node -e "<코드>"`는 JS 전체가 **명령줄 인자**가 된다. 윈도우 CreateProcess의
명령줄 상한은 **32,767자**라, 하네스가 붙는 원본(.js/.html)이 몇 줄만 커져도
`WinError 206`으로 죽는다. 리눅스 서버는 ARG_MAX가 커서 안 터지므로 **게이트가
갈린다**(로컬만 빨감).

이 함정을 **세 번** 밟았다 — 그때마다 "터진 그 파일만" 임시파일로 바꿨고,
공용화를 안 해서 다음 파일에서 또 터졌다:

    6d7add362 (2026-07-25)  sidebar 하네스
    d784d7e67 (2026-07-29)  슬라이스 JS
    e2b462c40 (2026-08-18)  슬라이스 하네스 2개   ← 같은 함정, 세 번째

그래서 판단처를 **여기 한 곳**으로 모은다(CLAUDE.md 0순위-B). 새 JS 테스트는
`node -e`를 직접 부르지 말고 이 모듈을 써라 — `test_no_node_dash_e.py`가 강제한다.

## 쓰는 법

    from shopping_shorts.tests.js_harness import NODE, run_js, requires_node

    pytestmark = requires_node          # node 없으면 파일 통째 skip

    def test_something():
        out = run_js("console.log(1+1);")
        assert out == "2"

★확장자는 반드시 `.js`다. `.mjs`로 쓰면 ESM으로 해석돼 기존 하네스(`const`·
`require` 혼용, 최상위 `await` 없음)가 통째로 깨진다 — 실측으로 확인된 함정이라
`suffix`를 인자로 열어두지 않았다.
"""
import os
import shutil
import subprocess
import tempfile

import pytest

#: node 실행파일 경로(없으면 None) — 각 테스트가 skip 판단에 쓴다.
NODE = shutil.which("node")

#: 테스트 파일 맨 위에 `pytestmark = requires_node` 로 달면 node 없을 때 통째 skip.
requires_node = pytest.mark.skipif(NODE is None, reason="node 없음")


def run_js(code, timeout=30, check=True):
    """JS 소스를 임시 .js 파일로 써서 `node <파일>`로 실행한다.

    code    : 실행할 JS 전문(하네스 + 원본 + 단언까지 이미 합쳐진 것)
    timeout : 초. 외부 도구 호출엔 반드시 상한을 둔다(무한대기 사고 전례).
    check   : True면 rc!=0에서 stderr를 붙여 assert 실패. False면 (rc, out, err) 반환.

    반환: check=True → stdout(.strip()) / check=False → (returncode, stdout, stderr)

    ★`node -e`를 쓰지 않는 이유는 모듈 docstring 참조(명령줄 32,767자 상한).
    """
    if NODE is None:                      # 호출 전에 requires_node로 걸러지는 게 정상
        raise RuntimeError("node 없음 — pytestmark = requires_node 를 달아라")
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run([NODE, path], capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace")
    finally:
        try:
            os.unlink(path)
        except OSError:                   # 윈도우에서 드물게 잠김 — 임시파일이라 무해
            pass
    if not check:
        return r.returncode, r.stdout, r.stderr
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def run_js_proc(code, **kw):
    """`subprocess.run([node, "-e", code], **kw)` 자리를 그대로 대신한다.

    반환이 **CompletedProcess**라 기존 호출부의 `r.returncode` / `r.stdout` /
    `r.stderr` 처리를 한 줄도 안 고치고 바꿔 끼울 수 있다(회귀 최소화가 목적).

    새 코드는 되도록 `run_js()`를 써라 — 이건 기존 테스트 이관용 어댑터다.
    `capture_output`·`text`·`encoding` 등은 호출부가 넘긴 값을 그대로 존중하되,
    안 넘겼으면 안전한 기본값(캡처·텍스트·utf-8·30초)을 채운다.
    """
    if NODE is None:
        raise RuntimeError("node 없음 — pytestmark = requires_node 를 달아라")
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    kw.setdefault("timeout", 30)
    kw.setdefault("stdin", subprocess.DEVNULL)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        return subprocess.run([NODE, path], **kw)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
