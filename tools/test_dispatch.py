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
