"""관제 265: 회원 설치본 엔진 묶음 — HAND(실행기·렌더)가 부르는 파일이 묶음 규칙에 막혀 빠지면 build 가 멈춰야 한다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import engine_bundle as EB  # noqa: E402

ENGINE = ROOT.parent / "칼카피숏템엔진"


@pytest.mark.skipif(not (ENGINE / "tools" / "calcopy" / "hybrid" / "render_bench.py").is_file(), reason="엔진 트랙 폴더 없음")
def test_hand_deps_all_resolved():
    assert EB.hand_unresolved(ENGINE) == []


@pytest.mark.skipif(not (ENGINE / "tools" / "calcopy" / "hybrid" / "render_bench.py").is_file(), reason="엔진 트랙 폴더 없음")
def test_hand_missing_module_is_caught(monkeypatch):
    # 사보타주: render_bench 가 부르는 thumb_rule 을 HAND 에서 빼면 빨강이어야 한다
    monkeypatch.setattr(EB, "HAND", tuple(h for h in EB.HAND if not h.endswith("thumb_rule.py")))
    bad = EB.hand_unresolved(ENGINE)
    assert any("thumb_rule.py" in b for b in bad)
