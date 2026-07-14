import json
from pathlib import Path

from shopping_shorts.motion_assets import load_manifest, resolve_layers


def _make_assets(tmp_path):
    d = tmp_path / "motion"
    d.mkdir(parents=True)
    (d / "swipe_left.mov").write_bytes(b"\x00")   # 실물 있는 자산
    (d / "manifest.json").write_text(json.dumps({"assets": [
        {"id": "swipe_left", "type": "transition", "file": "swipe_left.mov",
         "default": {"width": 1080, "x": 50, "y": 50}},
        {"id": "sparkle", "type": "sticker", "file": "sparkle.mov",  # 파일 실물 없음
         "default": {"width": 300, "x": 50, "y": 40}},
    ]}, ensure_ascii=False), encoding="utf-8")
    return d


def test_load_manifest_indexes_by_id(tmp_path):
    d = _make_assets(tmp_path)
    m = load_manifest(str(d))
    assert m["swipe_left"]["type"] == "transition"
    assert m["swipe_left"]["default"]["width"] == 1080


def test_resolve_merges_default_and_abspath(tmp_path):
    d = _make_assets(tmp_path)
    # 사용자가 준 레이어: width만 재정의, 나머지는 default로 채워져야 함
    layers = [{"asset_id": "swipe_left", "start": 1.5, "dur": 0.6, "width": 720}]
    out = resolve_layers(layers, str(d))
    assert len(out) == 1
    L = out[0]
    assert L["_abspath"] == str(d / "swipe_left.mov")
    assert L["width"] == 720          # 레이어 값이 default를 이긴다
    assert L["x"] == 50 and L["y"] == 50   # default 채움
    assert L["start"] == 1.5 and L["dur"] == 0.6


def test_resolve_skips_unknown_and_missing_file(tmp_path):
    d = _make_assets(tmp_path)
    layers = [
        {"asset_id": "does_not_exist"},          # 매니페스트에 없음 → skip
        {"asset_id": "sparkle"},                 # 매니페스트엔 있으나 파일 실물 없음 → skip
    ]
    assert resolve_layers(layers, str(d)) == []


def test_resolve_handles_none_and_empty(tmp_path):
    d = _make_assets(tmp_path)
    assert resolve_layers(None, str(d)) == []
    assert resolve_layers([], str(d)) == []


def test_resolve_skips_entry_without_file(tmp_path):
    d = tmp_path / "motion"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"assets": [
        {"id": "nofile", "type": "sticker", "default": {}},  # file 키 없음 → skip
    ]}, ensure_ascii=False), encoding="utf-8")
    assert resolve_layers([{"asset_id": "nofile"}], str(d)) == []
