"""`node -e` 재발 차단 가드 — 2026-08-19.

## 왜 이 테스트가 있나

`node -e "<코드>"`는 JS 전체가 명령줄 인자가 돼 윈도우 상한 **32,767자**에 걸린다
(`WinError 206`). 원본 파일이 몇 줄만 커져도 터지는 **시한폭탄**이다.

이 함정을 세 번 밟았고 세 번 다 "터진 그 파일만" 고쳤다:

    6d7add362 (07-25) → d784d7e67 (07-29) → e2b462c40 (08-18)

**고치기만 하고 가드를 안 둬서** 매번 다른 파일에서 되살아났다. 이 테스트가
네 번째를 막는다 — 새 JS 테스트는 `shopping_shorts/tests/js_harness.run_js`를 써라.

    from shopping_shorts.tests.js_harness import run_js, requires_node
    pytestmark = requires_node
    out = run_js(js_code)

★이 파일 자신은 검사에서 제외한다(위 설명에 패턴 문자열이 들어 있다).
"""
import pathlib
import re

TESTS_DIR = pathlib.Path(__file__).resolve().parent

#: 자기 자신만 제외 — "예외 목록"을 늘리기 시작하면 가드가 무력해진다.
_EXEMPT = {"test_no_node_dash_e.py"}

#: `subprocess.run([NODE, "-e", js])` / `["node", "-e", ...]` 등 인라인 호출 형태.
#: 리스트 원소로 "-e"가 오는 경우만 잡는다 — 주석 속 산문은 걸리지 않게.
_PATTERN = re.compile(r"""["'](?:node|NODE)["']\s*,\s*["']-e["']"""
                      r"""|NODE\s*,\s*["']-e["']""")


def test_node_dash_e_를_직접_쓰지_않는다():
    """tests/ 안에서 `node -e` 인라인 실행을 금지한다(임시파일 실행으로 대체).

    걸리면 파일명을 전부 나열한다 — "어디를 고쳐야 하나"를 바로 알 수 있게.
    """
    offenders = []
    for p in sorted(TESTS_DIR.glob("test_*.py")):
        if p.name in _EXEMPT:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(src.splitlines(), start=1):
            if _PATTERN.search(line):
                offenders.append(f"{p.name}:{i}")
    assert not offenders, (
        "`node -e` 인라인 실행이 남아 있습니다(윈도우 명령줄 32,767자 상한 → WinError 206).\n"
        "shopping_shorts/tests/js_harness.py 의 run_js() 로 바꾸세요.\n"
        "위반: " + ", ".join(offenders))


def test_공용_하네스가_임시파일을_쓴다():
    """가드가 가리키는 대체재가 실제로 임시파일 방식인지 고정한다.

    js_harness가 언젠가 `node -e`로 되돌아가면 이 가드 전체가 무의미해진다.
    """
    src = (TESTS_DIR / "js_harness.py").read_text(encoding="utf-8")
    assert "mkstemp" in src, "js_harness가 임시파일을 안 쓴다"
    assert not _PATTERN.search(src), "js_harness 자신이 node -e를 쓴다"
    assert 'suffix=".js"' in src, "확장자는 .js여야 한다(.mjs면 ESM으로 해석돼 깨진다)"
