import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate

TOOLS = str(Path(__file__).resolve().parent)


# ── Windows 콘솔 인코딩 (실측으로 발견된 크래시) ──────────────────

def _run_under_cp949(code):
    env = dict(os.environ, PYTHONIOENCODING="cp949")
    return subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)


def test_cp949_console_really_crashes_on_emoji():
    """짝 테스트 — 이게 없으면 아래 테스트가 죽은 테스트인지 알 수 없다.
    (통과하는데 결함 못 잡는 테스트가 이 저장소에서 반복됐다)"""
    p = _run_under_cp949("print('\\u2139')")
    assert p.returncode != 0
    assert b"UnicodeEncodeError" in p.stderr


def test_make_output_safe_survives_cp949_console():
    """2026-07-16 드라이런 실측: 게이트가 'ℹ️'를 찍다 터져 한 번도 완주 못 했다."""
    p = _run_under_cp949(
        f"import sys; sys.path.insert(0, r'{TOOLS}');"
        "import merge_gate; merge_gate.make_output_safe();"
        "print('\\u2139 \\uae30\\uc900\\uc120 \\u26a0\\ufe0f \\u2705 \\U0001f9f9')"
    )
    assert p.returncode == 0, p.stderr.decode("cp949", "replace")
    assert "기준선".encode("cp949") in p.stdout, "한글까지 깨지면 안 된다"


def test_track_cli_survives_cp949_console():
    """track.py도 ✅·⚠️·🧹를 찍는다 — 3단계 실전에서 똑같이 터질 자리였다."""
    p = _run_under_cp949(
        f"import sys; sys.path.insert(0, r'{TOOLS}');"
        "import track; sys.exit(track.main(['list']))"
    )
    assert p.returncode == 0, p.stderr.decode("cp949", "replace")


# ── 실패 목록 파싱 ────────────────────────────────────────────────

def test_parse_failed_picks_up_failed_and_error_lines():
    out = (
        "FAILED shopping_shorts/tests/test_app.py::test_x - AssertionError: boom\n"
        "ERROR shopping_shorts/tests/test_y.py::test_z\n"
        "2 failed, 3 passed in 1.2s\n"
    )
    assert merge_gate.parse_failed(out) == {
        "shopping_shorts/tests/test_app.py::test_x",
        "shopping_shorts/tests/test_y.py::test_z",
    }


def test_parse_failed_keeps_parametrized_ids_with_spaces():
    # id 안에 공백이 있어도 ' - ' 앞까지가 id다. \S+로 자르면 여기서 깨진다.
    out = "FAILED tests/test_a.py::test_p[a b c] - ValueError\n"
    assert merge_gate.parse_failed(out) == {"tests/test_a.py::test_p[a b c]"}


def test_parse_failed_ignores_unrelated_lines():
    out = "collected 10 items\nPASSED tests/test_a.py::test_ok\n= 10 passed =\n"
    assert merge_gate.parse_failed(out) == set()


def test_parse_failed_handles_collection_error_without_test_id():
    out = "ERROR shopping_shorts/tests/test_broken.py - ImportError: no module\n"
    assert merge_gate.parse_failed(out) == {"shopping_shorts/tests/test_broken.py"}


# ── 기준선 비교 (게이트의 심장) ───────────────────────────────────

def _snap(**kw):
    base = {
        "compile_ok": True,
        "import_ok": True,
        "pytest_rc": 0,
        "failed": [],
    }
    base.update(kw)
    return base


def test_compare_passes_when_nothing_changed():
    assert merge_gate.compare(_snap(), _snap()) == []


def test_compare_flags_newly_broken_test():
    before = _snap(pytest_rc=1, failed=["tests/test_a.py::test_old"])
    after = _snap(pytest_rc=1, failed=["tests/test_a.py::test_old",
                                       "tests/test_b.py::test_new"])
    problems = merge_gate.compare(before, after)
    assert len(problems) == 1
    assert "tests/test_b.py::test_new" in problems[0]
    # 기존 실패는 문제로 세지 않는다
    assert "test_old" not in problems[0]


def test_compare_tolerates_preexisting_failures():
    # 현재 main의 25 failed. 이걸 문제로 세면 모든 병합이 막힌다.
    fails = [f"tests/test_x.py::test_{i}" for i in range(25)]
    before = _snap(pytest_rc=1, failed=fails)
    after = _snap(pytest_rc=1, failed=fails)
    assert merge_gate.compare(before, after) == []


def test_compare_ignores_tests_that_got_fixed():
    before = _snap(pytest_rc=1, failed=["tests/test_a.py::test_x"])
    after = _snap(pytest_rc=0, failed=[])
    assert merge_gate.compare(before, after) == []


def test_compare_flags_import_regression():
    # 의미적 충돌의 주 검출기 — 텍스트 충돌 없이 병합됐지만 main이 ImportError
    problems = merge_gate.compare(_snap(), _snap(import_ok=False))
    assert len(problems) == 1
    assert "import" in problems[0].lower()


def test_compare_flags_compile_regression():
    problems = merge_gate.compare(_snap(), _snap(compile_ok=False))
    assert len(problems) == 1
    assert "문법" in problems[0]


def test_compare_flags_pytest_crash_even_with_empty_failed_list():
    # rc=2는 수집 자체가 터진 것. failed=[]라고 통과시키면 게이트가 눈뜬장님이 된다.
    problems = merge_gate.compare(_snap(), _snap(pytest_rc=2, failed=[]))
    assert len(problems) == 1
    assert "pytest" in problems[0].lower()


def test_compare_does_not_flag_pytest_rc_1_when_baseline_already_rc_1():
    before = _snap(pytest_rc=1, failed=["tests/test_a.py::test_x"])
    after = _snap(pytest_rc=1, failed=["tests/test_a.py::test_x"])
    assert merge_gate.compare(before, after) == []


def test_compare_tolerates_broken_baseline_but_says_so():
    # main이 이미 import 깨진 채면 게이트는 통과시키되(기준선 방식) 침묵하지 않는다
    before = _snap(import_ok=False)
    after = _snap(import_ok=False)
    problems = merge_gate.compare(before, after)
    assert problems == []
    assert merge_gate.baseline_warnings(before)  # 경고는 남는다


def test_baseline_warnings_silent_on_healthy_baseline():
    assert merge_gate.baseline_warnings(_snap()) == []


def test_compare_reports_every_new_failure_not_just_first():
    before = _snap(pytest_rc=1, failed=[])
    after = _snap(pytest_rc=1, failed=["tests/t.py::a", "tests/t.py::b"])
    problems = merge_gate.compare(before, after)
    joined = " ".join(problems)
    assert "tests/t.py::a" in joined and "tests/t.py::b" in joined
