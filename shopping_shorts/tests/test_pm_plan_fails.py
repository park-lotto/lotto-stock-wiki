# -*- coding: utf-8 -*-
"""회원 실행기 c_pm 계획: PC 제작기 계획 표 미달 행(fails)을 problems 로 넘긴다 — 11-03 베이글 편 A12 A-B-A 가 계획 표엔 × 였는데
ok None·problems None 으로 넘어가 렌더 뒤 B표에서야 걸려 다시 렌더했다(Jev 뿌리 0.83·해결 0.77)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402

PRESET = "channel/humorshowshow/preset/썰템쇼_화자썰"


def _w(tmp_path):
    d = tmp_path / "doc" / "pm"
    d.mkdir(parents=True)
    (d / "대본.json").write_text("{}", encoding="utf-8")
    (d / "재료.json").write_text(json.dumps({"shots": []}), encoding="utf-8")
    return tmp_path


def test_plan_table_fails_become_problems(tmp_path, monkeypatch):
    monkeypatch.setattr(PM, "make_one", lambda *a, **k: {"ok": None, "fails": ["A12 A-B-A 끼움 ['#3~#5 x→meme→(3.0)']"], "note": "계획 시트 · A12"})
    r = R.c_pm(_w(tmp_path), {"mode": "plan", "preset": PRESET})
    assert r["ok"] is False and r["problems"] == ["A12 A-B-A 끼움 ['#3~#5 x→meme→(3.0)']"]


def test_plan_clean_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(PM, "make_one", lambda *a, **k: {"ok": None, "fails": [], "note": "계획 검사 통과"})
    r = R.c_pm(_w(tmp_path), {"mode": "plan", "preset": PRESET})
    assert r["ok"] is None and "problems" not in r
