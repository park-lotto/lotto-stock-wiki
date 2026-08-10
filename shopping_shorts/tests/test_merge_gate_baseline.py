# -*- coding: utf-8 -*-
"""병합 게이트 — 기준선이 비정상일 때의 판정 (2026-08-06).

★실사고: test_channel_name_backfill.py가 미구현 모듈을 모듈 수준에서 import해
pytest가 수집 단계에서 중단(rc=2)됐다. 그러면 before["failed"]가 **빈 리스트**가 되고,
compare()가 단순 빼기를 하는 바람에 **원래 있던 실패 22건이 전부 '새로 깨진 것'으로**
잡혔다 — 하필 그 수집 오류를 고치는 커밋이 게이트에 막혔다.

반대 방향 사고도 같은 뿌리에서 났다: 기준선이 rc=2라 "실패 0건"으로 보이니
"게이트 통과"가 찍히고 **검증 없이 병합 1건이 그대로 나갔다.**
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import merge_gate as mg  # noqa: E402


def _snap(rc, failed=(), compile_ok=True, import_ok=True):
    return {"pytest_rc": rc, "failed": list(failed),
            "compile_ok": compile_ok, "import_ok": import_ok}


def test_기준선_정상_새실패는_막는다():
    """게이트 본연의 기능 — 약해지면 안 된다."""
    assert mg.compare(_snap(1, ["a"]), _snap(1, ["a", "b"]))


def test_기준선_정상_실패동일하면_통과():
    assert not mg.compare(_snap(1, ["a"]), _snap(1, ["a"]))


def test_기준선_비정상인데_병합후_정상이면_통과():
    """★이 사고 자체 — 기준선이 깨진 건 이 병합의 잘못이 아니다.
    빼기를 하면 기존 실패 전부가 신규로 오탐돼 '고치는 커밋'이 막힌다."""
    assert not mg.compare(_snap(2, []), _snap(1, ["a"] * 22))


def test_둘다_비정상이면_막는다():
    """★실패 목록이 양쪽 다 비어 '통과'로 보이지만, 실제로는 한 건도 안 돈 것이다.
    통과시키면 검증 없이 병합된다(실제로 그렇게 1건이 나갔다)."""
    assert mg.compare(_snap(2, []), _snap(2, []))


def test_기준선_정상인데_병합후_비정상이면_막는다():
    assert mg.compare(_snap(1, []), _snap(2, []))


def test_수집오류_rc는_비정상으로_친다():
    """rc 2(수집오류)·3(내부오류)·5(수집0)는 '테스트가 돌았다'가 아니다."""
    assert 0 in mg._PYTEST_SANE_RC and 1 in mg._PYTEST_SANE_RC
    for bad in (2, 3, 4, 5):
        assert bad not in mg._PYTEST_SANE_RC


def test_기준선_경고를_조용히_넘기지_않는다():
    """무력화된 사실을 안 알리면 게이트가 눈뜬장님인 걸 아무도 모른다."""
    warns = mg.baseline_warnings(_snap(2, []))
    assert any("무력" in w for w in warns)
