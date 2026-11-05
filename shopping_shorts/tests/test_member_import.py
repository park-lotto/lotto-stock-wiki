# -*- coding: utf-8 -*-
"""member_import(회원 프리셋 → 우리 프리셋) — 옮긴 칸 수·필수 칸·회원 값 그대로·모르는 칸 멈춤 (관제 319, 2026-11-06)."""
import json

import pytest

from tools.calcopy.engine import member_import as MI

SPEC = {
    "name": "시험형", "version": "1.0.0", "measured_from": "x",
    "canvas": {"w": 1080, "h": 1920},
    "layout": {"background": "0x090D26", "video_y": 420, "video_size": 1080},
    "title": {"font": "GmarketSansBold.otf", "size": 92, "band_h": 420, "line_centers_y": [195, 316], "base": "#FFFFFF",
              "highlight": "#F8DF0A", "max_lines": 2, "max_chars_per_line": 11, "max_width": 980, "font_note": "", "space_em": 0.28},
    "subtitle": {"font": "Pretendard-Light.otf", "size": 51, "color": "#FFFFFF", "box_alpha": 0.5, "pad_x": 10, "pad_top": 10, "glyph_h": 44,
                 "last_line_center_y": 1401, "line_pitch": 75, "box_bottom_y": 1432, "max_chars_per_line": 16, "max_lines": 2,
                 "min_card_s": 0.6, "split_pause_s": 0.35},
    "burned_subtitle_probe": {"y0": 945},
    "logo": {"center_y": 1660, "box": [600, 114]},
    "ending_card": {"seconds": 1.0, "background": "black", "optional": True},
    "crop": {"mode": "center", "scene_threshold": 0.3, "snap_to_center_px": 40, "face_k": 0.5, "face_max_shift_px": 140, "note": "",
             "burned_text": {"enabled": True}},
    "segment": {"min_s": 30, "max_s": 75},
    "audio": {"keep_if_lufs_between": [-18, -10], "target_lufs": -14, "true_peak": -1.0, "tail_fade_s": 0.12},
    "encode": {"crf": 18},
    "tts_voice": {"provider": "typecast", "voice_id": "tc_x", "name": "Jihoon", "tempo": 1.0},
    "enhance": {},
}
JOB = {"source": "a.mp4", "start": 0, "end": 45, "title": ["윗줄", "아랫줄"], "highlight": None, "subtitles": "auto", "logo": "l.png",
       "delogo": [], "ending_seconds": 1.0, "ending_jingle": None, "enhance": None, "out": "o.mp4", "play": False, "upload": {}}


def _member(tmp_path, spec=SPEC):
    d = tmp_path / "member"
    (d / "fonts").mkdir(parents=True)
    (d / "prompts").mkdir()
    (d / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (d / "job.template.json").write_text(json.dumps(JOB, ensure_ascii=False), encoding="utf-8")
    (d / "prompts" / "pick.txt").write_text("고르기", encoding="utf-8")
    return d


def test_counts_and_required_files(tmp_path):
    out = tmp_path / "channel" / "m" / "preset" / "s"
    M = MI.convert(_member(tmp_path), out, "9")
    for n in ("frame.json", "defaults.json", "r7.json", "manifest.json", "job.template.json"):
        assert (out / n).exists(), n
    c = M["import_counts"]
    assert sum(c.values()) == len(M["import_table"]) == 66   # 실제 2226 묶음은 job._메모 하나 더 = 67
    assert c[MI.MOVED] == 22 and c[MI.SCRIPT_ONLY] == 13
    assert {m["status"] for m in M["motion"]} <= {MI.MOVED, MI.NO_SLOT, MI.SCRIPT_ONLY}


def test_member_values_unchanged(tmp_path):
    out = tmp_path / "p" / "preset" / "s"
    MI.convert(_member(tmp_path), out)
    F = json.loads((out / "frame.json").read_text(encoding="utf-8"))
    L = {l.get("role", l["kind"]): l for l in F["layers"]}
    assert L["bg"]["rgb"] == [9, 13, 38]
    assert (L["video"]["y"], L["video"]["w"], L["video"]["h"]) == (420, 1080, 1080)
    t = L["title"]
    assert t["size"] == 92 and t["w"] == 980 and t["font"] == "GmarketSansBold"
    assert t["y"] + t["line_h"] / 2 == 195 and t["y"] + 1.5 * t["line_h"] == 316
    assert t["line_rgb"] == [[255, 255, 255], [248, 223, 10]] and t["enter"] is None
    assert "caption" not in L            # Pretendard-Light 는 우리 등록 글꼴에 없음 → 대체 없이 층 안 만듦
    assert L["image"]["y"] + L["image"]["h"] / 2 == 1660
    D = json.loads((out / "defaults.json").read_text(encoding="utf-8"))
    assert D["tts"]["voice_id"] == "tc_x" and D["audio"]["keep_if_lufs_between"] == [-18, -10]
    R = json.loads((out / "r7.json").read_text(encoding="utf-8"))["summary"]
    assert R["crop"]["mode"] == "center" and R["end"]["sec"] == 1.0 and R["orig_caption"]["mode"] == "burned"


def test_unknown_key_stops(tmp_path):
    bad = {**SPEC, "new_motion": {"kind": "bounce"}}
    with pytest.raises(ValueError, match="모르는 칸"):
        MI.convert(_member(tmp_path, bad), tmp_path / "x" / "preset" / "s")
    M = MI.convert(_member(tmp_path / "b", bad), tmp_path / "y" / "preset" / "s", accept_unknown=True)
    assert [u["path"] for u in M["accepted_unknown"]] == ["spec.new_motion.kind"]
