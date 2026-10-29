"""관제 265 → 10-29 사장님 '하나의 MCP': 칼카피 판 → 회원 MCP 발행 (tools/claude_portal/member_publish.py).
발행해도 되나 = ready(): MCP 길 완주 기록(channel/<slug>/_kal/회원실측.json ok) + 사장님 확인(owner_ok). 서류 단계(L2)는 참고만.
card_levels(엔진 preset_card)는 가짜로 바꾸고, 회원실측 기록과 대기열·스위치·점검 단계 동작을 잰다."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import member_publish as MP  # noqa: E402

ENGINE = ROOT

FAKE = {
    "lowpan": {"level": "L1", "missing": ["품질관문 ○"], "preset_dir": "channel/lowpan/preset/a"},
    "okpan": {"level": "L1", "missing": ["눈검수 E9"], "preset_dir": "channel/okpan/preset/b"},
    "holdpan": {"level": "보류(벤치 소멸)", "missing": ["줄판독≥6"], "preset_dir": None},
}


@pytest.fixture
def eng(tmp_path, monkeypatch):
    monkeypatch.setattr(MP, "card_levels", lambda engine: FAKE)
    return tmp_path


def _queue(eng):
    p = eng / MP.QUEUE_REL
    return json.loads(p.read_text(encoding="utf-8"))["queue"] if p.exists() else []


def _episode(eng, ok=True):
    """flow_episode.js 결과 파일 꼴(마지막 JSON) + 실제 완성본 파일."""
    v = eng / "final.mp4"
    v.write_bytes(b"x")
    out = eng / "ep.out"
    out.write_text("진행 줄…\n" + json.dumps({"ok": ok, "videos": [str(v)], "final": {"sec": 29.2, "audio": True, "w": 1080, "h": 1920}}),
                   encoding="utf-8")
    return out


def test_queue_rejects_without_mcp_run(eng, capsys):
    assert MP.main(["--engine", str(eng), "queue", "lowpan"]) == 2
    assert "MCP 길 완주 기록 없음" in capsys.readouterr().out
    assert _queue(eng) == []


def test_queue_rejects_hold(eng):
    assert MP.main(["--engine", str(eng), "queue", "holdpan"]) == 2
    assert _queue(eng) == []


def test_live_then_owner_approve_then_queue(eng, capsys):
    assert MP.main(["--engine", str(eng), "live", "okpan", "--out", str(_episode(eng))]) == 0
    assert MP.main(["--engine", str(eng), "queue", "okpan"]) == 2          # 사장님 확인 전엔 못 오른다
    assert "사장님 확인 전" in capsys.readouterr().out
    assert MP.main(["--engine", str(eng), "approve", "okpan"]) == 0
    assert MP.main(["--engine", str(eng), "queue", "okpan"]) == 0
    assert [e["slug"] for e in _queue(eng)] == ["okpan"]
    assert MP.main(["--engine", str(eng), "queue", "okpan"]) == 0          # 두 번 넣어도 한 줄
    assert len(_queue(eng)) == 1


def test_failed_run_is_not_ok(eng):
    assert MP.main(["--engine", str(eng), "live", "okpan", "--out", str(_episode(eng, ok=False))]) == 1
    assert MP.main(["--engine", str(eng), "approve", "okpan"]) == 2        # 완주 못 한 편은 확인할 것도 없다


def _ready_okpan(eng):
    MP.main(["--engine", str(eng), "live", "okpan", "--out", str(_episode(eng))])
    MP.main(["--engine", str(eng), "approve", "okpan"])
    MP.main(["--engine", str(eng), "queue", "okpan"])


def test_open_refuses_without_owner_ok(eng, monkeypatch, capsys):
    _ready_okpan(eng)
    called = []
    monkeypatch.setattr(MP.subprocess, "run", lambda *a, **k: called.append(a))
    assert MP.main(["--engine", str(eng), "open", "--version", "9.9.9"]) == 2
    assert "--owner-ok" in capsys.readouterr().out
    assert called == []


def test_open_dry_plan_starts_with_member_check(eng, monkeypatch, capsys):
    _ready_okpan(eng)
    called = []
    monkeypatch.setattr(MP.subprocess, "run", lambda *a, **k: called.append(a))
    assert MP.main(["--engine", str(eng), "open", "--dry", "--version", "9.9.9", "--out", str(eng / "build")]) == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l[:2] in ("1.", "2.", "3.", "4.")]
    assert "member_check.py" in lines[0] and "channel/okpan/preset/b" in lines[0]
    assert "preset_pack.py build" in lines[1] and "build_win.py" in lines[2] and "upload_release.py" in lines[3]
    assert called == []


def test_open_drops_unapproved_after_queue(eng, monkeypatch, capsys):
    _ready_okpan(eng)
    rec = MP.live_record(eng, "okpan")
    rec["owner_ok"] = False
    MP.live_path(eng, "okpan").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    assert MP.main(["--engine", str(eng), "open", "--dry", "--version", "9.9.9"]) == 0
    out = capsys.readouterr().out
    assert "[제외] okpan" in out and "preset_pack.py" not in out


@pytest.mark.skipif(not (ENGINE / "tools" / "calcopy" / "preset_card.py").is_file(), reason="엔진 없음")
def test_real_engine_levels_come_from_preset_card():
    L = MP.card_levels(ENGINE)
    assert L and all("level" in d and "missing" in d for d in L.values())
