# -*- coding: utf-8 -*-
"""숏클 썰템쇼 = PC 제작 라인(preset_make)과 같게(사장님 11-03, handoff/숏클_썰템쇼_PC라인_설계.md).
  · script_audit.as_lines 가 PC 작품 대본 꼴(frame_vars·speaker)을 읽는다 — PC 10편이 화자 0줄·제목 0줄로 전부 미달이던 것
  · preset_make.crop_box = 계획 검사와 회원 자를 칸 시트가 같이 쓰는 칸(예전 계산 그대로)
  · runner_ops.pm_member_patch = 회원 목소리(대본 voice 칸)·회원 빠르기·짤 폴더만 덮는다"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.hybrid import runner_ops as RO  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402

PC = ROOT / "channel" / "humorshowshow"


def test_pc_script_format_read():
    d = SA.as_lines({"frame_vars": {"frames[hook].layers[text:title].text": "한국 코스트코만\n대놓고 차별한 디저트"},
                     "lines": [{"text": "a/b", "tts": "a b."}, {"text": "c", "speaker": "제조사", "tts": "c."}]})
    assert d["title_lines"] == [[["한국 코스트코만", None]], [["대놓고 차별한 디저트", None]]]
    assert [l["kind"] for l in d["lines"]] == ["tts", "tts"] and d["lines"][1]["who"] == "제조사" and d["lines"][0]["id"] == "줄1"
    hy = {"lines": [{"id": "N1", "kind": "tts", "tts": "x"}]}
    assert SA.as_lines(hy) is hy                                    # 회원 hybrid 대본은 그대로


def test_pc_ten_pass_speaker_and_title():
    works = sorted(PC.glob("작품*_*"))
    assert len(works) >= 10
    for w in works:
        r = SA.audit(w / "대본.json", version="썰템쇼판")
        bad = {x["kind"] for x in r["rules"] if not x["ok"]}
        assert not bad & {"speaker_lines", "title_lines"}, (w.name, bad)


def test_crop_box_same_as_before():
    assert PM.crop_box(None, None, 1920, 1080, 1080, 878) == [296, 0, 1328, 1080]      # 높이 전체·가운데(0.81배)
    assert PM.crop_box(None, 100, 1920, 1080, 1080, 878) == [100, 0, 1328, 1080]
    assert PM.crop_box([350, 200, 1082, 880], None, 1920, 1080, 1080, 878) == [350, 200, 1082, 880]


def test_member_patch(tmp_path, monkeypatch):
    doc = tmp_path / "doc" / "pm"
    doc.mkdir(parents=True)
    (doc / "대본.json").write_text(json.dumps({"lines": []}), encoding="utf-8")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"member": {"tts": {"voice_id": "kr-mina-expressive", "provider": "elevenlabs", "tempo": 1.05}}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(pack))
    p = RO.pm_member_patch(tmp_path, doc)
    assert p == {"meme_dir": str(tmp_path / "memes"), "tts_tempo": 1.05}
    assert json.loads((doc / "대본.json").read_text(encoding="utf-8"))["voice"] == {"voice_id": "kr-mina-expressive", "provider": "elevenlabs"}
    monkeypatch.delenv("SHORTEM_MEMBER_PACK")
    assert RO.pm_member_patch(tmp_path, doc) == {"meme_dir": str(tmp_path / "memes")}


def test_c_pm_needs_docs(tmp_path):
    r = RO.c_pm(tmp_path, {"mode": "plan", "preset": "channel/humorshowshow/preset/썰템쇼_화자썰"})
    assert r["ok"] is False and "대본.json" in r["error"]
