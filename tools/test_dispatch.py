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
