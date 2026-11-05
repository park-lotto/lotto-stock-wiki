# -*- coding: utf-8 -*-
"""merge_preset_pack — 편마다 값($per_video) 처리(관제 234, 10-20 라이브 시험 'layers[2].y = $per_video' 로 틀 검사 멈춤).
전 프리셋: 합친 틀이 틀 검사를 통과하고, 제목 밖 글 칸에 '$per_video' 가 남지 않는다. 제목 글은 대본 몫이라 남는다. 채널명 칸은 고객 채널명."""
import glob
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import calcopy_make as MK  # noqa: E402
from shopping_shorts.calcopy_frame import schema  # noqa: E402

PRESETS = sorted(os.path.dirname(f).replace(os.sep, "/").split(str(ROOT).replace(os.sep, "/") + "/")[-1]
                 for f in glob.glob(str(ROOT / "channel" / "*" / "preset" / "**" / "frame.json"), recursive=True))
PACK = {"brand": {"channel_name": "내 채널"}}


@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_merges_to_a_valid_frame_without_leftover_vars(preset):
    cfg = MK.merge_preset_pack(preset, PACK)
    spec = schema.validate(cfg["frame"])
    left = [(L["role"], L.get("text")) for L in schema.all_layers(spec)
            if L["kind"] == "text" and L.get("role") != "title" and "$per_video" in str(L.get("text") or "")]
    assert left == []
    nums = [k for L in schema.all_layers(spec) for k, v in L.items() if v == "$per_video" and k != "text"]
    assert nums == []


def test_measured_defaults_fill_numbers_and_title_text_stays_for_script():
    cfg = MK.merge_preset_pack("channel/annapick/preset/검정띠2줄_출처", PACK)
    t = next(L for L in MK._frames(cfg["frame"])[0]["layers"] if L.get("kind") == "text" and L.get("role") == "title")
    assert isinstance(t["y"], (int, float)) and isinstance(t["size"], (int, float))
    assert t["text"] == "$per_video"
    assert any("편마다 값" in a for a in cfg["applied"])


def test_brand_slot_gets_channel_name_before_leftovers_are_dropped():
    cfg = MK.merge_preset_pack("channel/homedesignnote/preset/전체화면_가운데자막", PACK)
    brands = [L["text"] for L in MK._frames(cfg["frame"])[0]["layers"] if L.get("kind") == "text" and L.get("role") == "brand"]
    assert brands == ["내 채널"]
