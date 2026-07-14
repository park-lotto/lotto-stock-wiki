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


from shopping_shorts.video_assemble import _motion_layer_filters


def test_motion_layer_filters_builds_overlay_chain():
    layers = [
        {"_abspath": "/a/swipe.mov", "start": 1.5, "dur": 0.6, "x": 50, "y": 50, "width": 720, "alpha": 1},
        {"_abspath": "/a/spark.mov", "start": 0, "dur": None, "x": 50, "y": 40, "width": 300, "alpha": 0.8},
    ]
    inputs, fc, vcur, nxt = _motion_layer_filters(layers, next_input_idx=1, vcur="v0")
    # 입력 2개가 인덱스 1,2로 추가된다
    assert inputs == ["-i", "/a/swipe.mov", "-i", "/a/spark.mov"]
    assert nxt == 3
    assert vcur == "mlv1"                       # 마지막 레이어 출력 라벨
    joined = ";".join(fc)
    # 첫 레이어: width 스케일 + enable(구간)
    assert "scale=720:-1" in joined
    assert "between(t,1.500,2.100)" in joined
    # 둘째 레이어: dur=None → enable 없음, alpha 0.8
    assert "colorchannelmixer=aa=0.80" in joined
    assert joined.count("enable=") == 1        # 전체재생 레이어는 enable 없음


def test_motion_layer_filters_empty_is_noop():
    inputs, fc, vcur, nxt = _motion_layer_filters([], next_input_idx=1, vcur="v0")
    assert inputs == [] and fc == [] and vcur == "v0" and nxt == 1


import shopping_shorts.video_assemble as va


def test_burn_captions_composites_motion_layers(tmp_path, monkeypatch):
    # 모션 자산 실물(빈 파일이어도 경로 존재하면 빌더가 포함)
    asset = tmp_path / "swipe.mov"
    asset.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"
    base.write_bytes(b"\x00")

    captured = {}
    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: captured.setdefault("cmd", cmd))
    # ⚠️ _burn_captions는 폰트 미해결 시 조기 복사 후 return(538~540행) → 모션 코드에 도달 못 함.
    #    테스트를 실폰트에 의존시키지 않도록 폰트 해석을 강제하고 실제 복사는 no-op.
    monkeypatch.setattr(va, "_resolve_font", lambda: str(asset))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)
    # 폰트/자막 경로를 타지 않도록 자막 없는 최소 edit_plan
    edit_plan = {"beats": []}
    deco = {
        "motion": {
            "color_filter": "eq=saturation=1.2",
            "layers": [{"_abspath": str(asset), "start": 0.5, "dur": 0.6,
                        "x": 50, "y": 50, "width": 720, "alpha": 1}],
        }
    }
    out = tmp_path / "out.mp4"
    va._burn_captions(str(base), edit_plan, {}, str(out), tmp_path, None, None, deco)
    cmd = captured["cmd"]
    assert "-filter_complex" in cmd            # 모션 있으면 복합 경로
    fcx = cmd[cmd.index("-filter_complex") + 1]
    assert "eq=saturation=1.2" in fcx          # base vf에 색감필터 부착
    assert "overlay=" in fcx                   # 레이어 합성
    assert str(asset) in cmd                   # 자산이 입력으로 추가됨


def test_burn_captions_motion_plus_bgm_keeps_audio_index(tmp_path, monkeypatch):
    # 모션 입력이 인덱스를 소비한 뒤에도 bgm 오디오 입력 인덱스가 맞아야 한다(idx off-by-one 가드)
    asset = tmp_path / "swipe.mov"; asset.write_bytes(b"\x00")
    bgm = tmp_path / "bgm.mp3"; bgm.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"; base.write_bytes(b"\x00")
    captured = {}
    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(va, "_resolve_font", lambda: str(asset))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)
    deco = {
        "bgm": {"_abspath": str(bgm), "volume": 15},
        "motion": {"layers": [{"_abspath": str(asset), "start": 0, "dur": 0.5,
                               "x": 50, "y": 50, "width": 720, "alpha": 1}]},
    }
    va._burn_captions(str(base), {"beats": []}, {}, str(tmp_path / "out.mp4"), tmp_path, None, None, deco)
    cmd = captured["cmd"]
    fcx = cmd[cmd.index("-filter_complex") + 1]
    # 입력 순서: 0=base, 1=motion asset, 2=bgm → bgm 오디오는 [2:a]
    assert "[2:a]" in fcx                    # bgm 오디오 인덱스가 모션 입력 뒤로 정확히 밀렸다
    assert "amix" in fcx                     # bgm 믹스 존재
    assert "overlay=" in fcx                 # 모션 합성 존재


def test_burn_captions_color_only_uses_simple_vf(tmp_path, monkeypatch):
    # 레이어 없이 색감필터만 → filter_complex 안 타고 단순 -vf에 필터가 붙는다
    asset = tmp_path / "f.ttf"; asset.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"; base.write_bytes(b"\x00")
    captured = {}
    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(va, "_resolve_font", lambda: str(asset))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)
    deco = {"motion": {"color_filter": "eq=saturation=1.3", "layers": []}}
    va._burn_captions(str(base), {"beats": []}, {}, str(tmp_path / "out.mp4"), tmp_path, None, None, deco)
    cmd = captured["cmd"]
    assert "-filter_complex" not in cmd          # 레이어 없으니 단순 경로
    assert "-vf" in cmd
    assert "eq=saturation=1.3" in cmd[cmd.index("-vf") + 1]   # 색감필터가 -vf에 부착


import json as _json
import shopping_shorts.mix_pipeline as mp
from shopping_shorts.store import Store


def test_run_render_resolves_motion_layers(tmp_path, monkeypatch):
    # 자산 폴더 + 매니페스트
    adir = tmp_path / "assets"
    adir.mkdir()
    (adir / "swipe_left.mov").write_bytes(b"\x00")
    (adir / "manifest.json").write_text(_json.dumps({"assets": [
        {"id": "swipe_left", "type": "transition", "file": "swipe_left.mov",
         "default": {"width": 1080, "x": 50, "y": 50}}]}), encoding="utf-8")
    # motion_assets가 이 폴더를 보도록 기본 경로 교체
    monkeypatch.setattr(mp, "MOTION_ASSETS_DIR", str(adir))

    db = tmp_path / "t.db"
    store = Store(db)
    store.create_mix_job("jm", ["u0"], 20, "free")
    store.update_mix_job("jm", status="ready_for_review",
        edit_plan={"structure": "free", "beats": [
            {"beat_idx": 0, "role": "훅", "narration": "n", "tts_path": str(tmp_path / "t.mp3")}]},
        deco={"motion": {"layers": [{"asset_id": "swipe_left", "start": 1.0, "dur": 0.5}]}})
    # 소스/ tts 실물 없이도 assemble 직전까지만 검증하도록 의존부 무력화
    work = tmp_path / "work" / "jm"; work.mkdir(parents=True)
    (work / "s0").mkdir(); (work / "s0" / "a.mp4").write_bytes(b"\x00")
    (tmp_path / "t.mp3").write_bytes(b"\x00")

    captured = {}
    monkeypatch.setattr(mp, "assemble", lambda *a, **k: captured.update(k) or "x")
    mp.run_render("jm", str(db), str(tmp_path / "work"))

    deco = captured["deco"]
    layer = deco["motion"]["layers"][0]
    assert layer["_abspath"].endswith("swipe_left.mov")   # 경로 해석됨
    assert layer["start"] == 1.0 and layer["dur"] == 0.5


from shopping_shorts.motion_text import render_text_overlay, TextRenderUnavailable
import pytest


def test_render_text_overlay_stub_raises(tmp_path):
    with pytest.raises(TextRenderUnavailable):
        render_text_overlay("KineticHook", {"text": "역대급세일"}, str(tmp_path))
