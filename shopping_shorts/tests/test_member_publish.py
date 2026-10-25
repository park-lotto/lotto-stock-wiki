"""관제 265: 칼카피 판 → 회원 MCP '발행 대기 → 사장님 스위치' (tools/claude_portal/member_publish.py).
판정 주인은 엔진 preset_card — 여기서는 그 결과(card_levels)를 가짜로 바꿔 대기열·스위치 동작만 잰다."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import member_publish as MP  # noqa: E402

ENGINE = ROOT.parent / "칼카피숏템엔진"

FAKE = {
    "lowpan": {"level": "L1", "missing": ["품질관문 ○", "재현일치도 ○", "눈검수 E1~E8"], "preset_dir": "channel/lowpan/preset/a"},
    "okpan": {"level": "L2", "missing": ["눈검수 E9"], "preset_dir": "channel/okpan/preset/b"},
    "holdpan": {"level": "보류(벤치 소멸)", "missing": ["줄판독≥6"], "preset_dir": None},
}


@pytest.fixture
def eng(tmp_path, monkeypatch):
    monkeypatch.setattr(MP, "card_levels", lambda engine: FAKE)
    return tmp_path


def _queue(eng):
    p = eng / MP.QUEUE_REL
    return json.loads(p.read_text(encoding="utf-8"))["queue"] if p.exists() else []


def test_queue_rejects_l1(eng, capsys):
    assert MP.main(["--engine", str(eng), "queue", "lowpan"]) == 2
    out = capsys.readouterr().out
    assert "[거절]" in out and "품질관문 ○" in out
    assert _queue(eng) == []


def test_queue_rejects_hold(eng):
    assert MP.main(["--engine", str(eng), "queue", "holdpan"]) == 2
    assert _queue(eng) == []


def test_queue_accepts_l2(eng):
    assert MP.main(["--engine", str(eng), "queue", "okpan"]) == 0
    q = _queue(eng)
    assert [e["slug"] for e in q] == ["okpan"] and q[0]["level"] == "L2"
    assert MP.main(["--engine", str(eng), "queue", "okpan"]) == 0      # 두 번 넣어도 한 줄
    assert len(_queue(eng)) == 1


def test_open_refuses_without_owner_ok(eng, monkeypatch, capsys):
    MP.main(["--engine", str(eng), "queue", "okpan"])
    called = []
    monkeypatch.setattr(MP.subprocess, "run", lambda *a, **k: called.append(a))
    assert MP.main(["--engine", str(eng), "open", "--version", "9.9.9"]) == 2
    assert "--owner-ok" in capsys.readouterr().out
    assert called == []


def test_open_dry_prints_plan_and_runs_nothing(eng, monkeypatch, capsys):
    MP.main(["--engine", str(eng), "queue", "okpan"])
    called = []
    monkeypatch.setattr(MP.subprocess, "run", lambda *a, **k: called.append(a))
    assert MP.main(["--engine", str(eng), "open", "--dry", "--version", "9.9.9", "--out", str(eng / "build")]) == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l[:2] in ("1.", "2.", "3.")]
    assert "preset_pack.py build" in lines[0] and "channel/okpan/preset/b" in lines[0]
    assert "build_win.py" in lines[1] and "upload_release.py" in lines[2]
    assert called == []


def test_open_drops_regressed_pan(eng, monkeypatch, capsys):
    # 대기열에 오른 뒤 단계가 떨어지면 열 때 뺀다
    MP.main(["--engine", str(eng), "queue", "okpan"])
    monkeypatch.setattr(MP, "card_levels", lambda engine: {**FAKE, "okpan": {**FAKE["okpan"], "level": "L1"}})
    assert MP.main(["--engine", str(eng), "open", "--dry", "--version", "9.9.9"]) == 0
    out = capsys.readouterr().out
    assert "[제외] okpan" in out and "preset_pack.py" not in out


@pytest.mark.skipif(not (ENGINE / "tools" / "calcopy" / "preset_card.py").is_file(), reason="엔진 트랙 폴더 없음")
def test_real_engine_levels_come_from_preset_card():
    L = MP.card_levels(ENGINE)
    assert L and all("level" in d and "missing" in d for d in L.values())
