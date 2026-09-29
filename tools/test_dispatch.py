# -*- coding: utf-8 -*-
"""카드 046 — 창 여는 곳·분배·보고·PC 이름 단위 테스트."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pc_label


def test_pc_label_reads_config(tmp_path):
    (tmp_path / ".claude-pc.json").write_text(json.dumps({"label": "집"}), encoding="utf-8")
    assert pc_label.label(home=tmp_path, computer="DESKTOP-X") == "집"


def test_pc_label_falls_back_to_computer_name(tmp_path):
    assert pc_label.label(home=tmp_path, computer="DESKTOP-X") == "DESKTOP-X"


def test_pc_label_ignores_broken_json(tmp_path):
    (tmp_path / ".claude-pc.json").write_text("{", encoding="utf-8")
    assert pc_label.label(home=tmp_path, computer="DESKTOP-X") == "DESKTOP-X"


import track_open

HOME = Path("C:/Users/CH")


def test_build_launch_account1_clears_config_dir(tmp_path):
    L = track_open.build_launch(tmp_path, account="1", pc="집", tag="대본작성", card=46,
                                prompt="고쳐", home=HOME)
    assert L["env_unset"] == ["CLAUDE_CONFIG_DIR"]
    assert "CLAUDE_CONFIG_DIR" not in L["env"]
    assert L["name"] == "집·1·대본작성·카드46"
    a = L["argv"]
    assert a[0] == "claude" and "--continue" in a
    assert a[a.index("--remote-control") + 1] == "집·1·대본작성·카드46"
    assert a[a.index("--settings") + 1] == str(HOME / "claude-remote-settings.json")
    assert a[-1] == "고쳐"


def test_build_launch_account2_sets_sub_config(tmp_path):
    L = track_open.build_launch(tmp_path, account="2", pc="회사", tag="t", home=HOME)
    assert L["env"]["CLAUDE_CONFIG_DIR"] == str(HOME / ".claude-sub")
    assert L["name"] == "회사·2·t"


def test_build_launch_model_and_no_continue(tmp_path):
    L = track_open.build_launch(tmp_path, pc="집", tag="t", model="fable", resume=False, home=HOME)
    assert L["argv"][L["argv"].index("--model") + 1] == "fable"
    assert "--continue" not in L["argv"]


def test_build_launch_codex(tmp_path):
    L = track_open.build_launch(tmp_path, agent="codex", pc="집", tag="t", prompt="p", home=HOME)
    assert L["argv"][:3] == ["codex", "--sandbox", "workspace-write"]
    assert L["argv"][-1] == "p"
    assert "--remote-control" not in L["argv"]


def test_build_launch_rejects_bad_account(tmp_path):
    with pytest.raises(ValueError):
        track_open.build_launch(tmp_path, account="4", pc="집", tag="t", home=HOME)


def test_session_alive_missing_file(tmp_path):
    assert track_open.session_alive(tmp_path) is None


def test_session_alive_dead_pid(tmp_path, monkeypatch):
    (tmp_path / ".session.json").write_text(json.dumps({"pid": 99999, "name": "n"}), encoding="utf-8")
    monkeypatch.setattr(track_open, "_image_name", lambda pid: "")
    assert track_open.session_alive(tmp_path) is None


def test_session_alive_live_window(tmp_path, monkeypatch):
    (tmp_path / ".session.json").write_text(json.dumps({"pid": 123, "name": "집·1·t"}), encoding="utf-8")
    monkeypatch.setattr(track_open, "_image_name", lambda pid: "powershell.exe")
    assert track_open.session_alive(tmp_path)["name"] == "집·1·t"


def test_launch_script_text(tmp_path):
    L = track_open.build_launch(tmp_path, pc="집", tag="t", prompt="it's \"q\"", home=HOME)
    s = track_open.launch_script(L)
    assert "Remove-Item Env:\CLAUDE_CONFIG_DIR" in s
    assert "Set-Location -LiteralPath '" in s
    assert "'it''s \"q\"'" in s          # PowerShell 작은따옴표 이스케이프


import dispatch


@pytest.fixture
def fake_track(tmp_path, monkeypatch):
    (tmp_path / "대본작성").mkdir()
    monkeypatch.setattr(dispatch.track, "worktree_path", lambda name, repo=None: tmp_path / name)
    monkeypatch.setattr(dispatch.pc_label, "label", lambda: "집")
    calls = {}

    def fake_launch(L):
        calls["L"] = L
        return 777

    monkeypatch.setattr(dispatch.track_open, "launch_window", fake_launch)
    monkeypatch.setattr(dispatch, "_link_card", lambda n, t: calls.setdefault("card", (n, t)))
    return calls


def test_dispatch_opens_window(fake_track, monkeypatch):
    monkeypatch.setattr(dispatch.track_open, "session_alive", lambda cwd: None)
    assert dispatch.main(["대본작성", "자막 고쳐", "--card", "46"]) == 0
    L = fake_track["L"]
    assert L["name"] == "집·1·대본작성·카드46"
    assert L["argv"][-1].startswith("자막 고쳐")
    assert "tg_notify.py" in L["argv"][-1]
    assert fake_track["card"] == (46, "대본작성")


def test_dispatch_busy(fake_track, monkeypatch):
    monkeypatch.setattr(dispatch.track_open, "session_alive", lambda cwd: {"pid": 1, "name": "집·1·대본작성"})
    assert dispatch.main(["대본작성", "x"]) == 3
    assert "L" not in fake_track


def test_dispatch_missing_track(fake_track):
    assert dispatch.main(["없는트랙", "x"]) == 1
