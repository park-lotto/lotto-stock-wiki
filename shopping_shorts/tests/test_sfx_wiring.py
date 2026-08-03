"""seam 테스트 — match_sfx가 쓴 beat["sfx"]["asset_id"]를 run_render·run_preview가
그대로 읽어 asset_id→media_path로 해석해 assemble에 sfx_paths로 넘기는지(저장위치=읽기위치).
컷어웨이(test_mix_cutaway_wiring)와 같은 구조.
"""
from pathlib import Path

from shopping_shorts import mix_pipeline


def _plan_with_sfx():
    return {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "x", "target_seconds": 2.0, "role": "hook",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0,
         "sfx": {"asset_id": 8, "match_type": "role", "position": "first"}}]}


class _FakeStore:
    def __init__(self, *a, **k):
        pass

    def get_mix_job(self, jid):
        return {"edit_plan": _plan_with_sfx(), "status": "ready_for_review", "urls": [],
                "subtitle_removal": False, "deco": None, "headcopy": None,
                "caption_style": None}

    def get_scene_asset(self, asset_id, customer_id=0):
        return {"id": asset_id, "media_path": f"/lib/{asset_id}.mp3"}

    def update_mix_job(self, *a, **k):
        pass


def _wire(monkeypatch, captured):
    def fake_assemble(edit_plan, tts_paths, source_video_paths, out_path, **kw):
        captured["sfx_paths"] = kw.get("sfx_paths")
        Path(out_path).write_bytes(b"x")
        return out_path
    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)
    monkeypatch.setattr(mix_pipeline, "Store", _FakeStore)
    monkeypatch.setattr(mix_pipeline, "_resolve_sources", lambda job, work: {})


def test_run_render_resolves_sfx_asset_paths(monkeypatch, tmp_path):
    captured = {}
    _wire(monkeypatch, captured)
    mix_pipeline.run_render("job1", str(tmp_path / "db"), str(tmp_path))
    assert captured["sfx_paths"] == {0: "/lib/8.mp3"}


def test_run_preview_resolves_sfx_asset_paths(monkeypatch, tmp_path):
    captured = {}
    _wire(monkeypatch, captured)
    mix_pipeline.run_preview("job1", str(tmp_path / "db"), str(tmp_path))
    assert captured["sfx_paths"] == {0: "/lib/8.mp3"}


def test_plan_and_tts_calls_match_sfx(monkeypatch, tmp_path):
    """_plan_and_tts가 match_scene_assets 직후 match_sfx를 부르는지.

    ★2026-08-01: 자동 배치는 설정(scene_library_auto_enabled)으로 게이트된다 —
    자산이 있어도 기본은 안 붙는다. 감자 자산이 아이스크림 영상을 덮은 실사고 때문이다.
    이 테스트는 '켰을 때 순서가 clip→sfx인가'를 본다.
    """
    calls = []
    monkeypatch.setattr(mix_pipeline, "match_scene_assets",
                        lambda plan, assets: (calls.append("clip"), plan)[1])
    monkeypatch.setattr(mix_pipeline, "match_sfx",
                        lambda plan, assets: (calls.append("sfx"), plan)[1])
    monkeypatch.setattr(mix_pipeline, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mix_pipeline, "_refill_beats_to_tts", lambda *a, **k: None)
    monkeypatch.setattr(mix_pipeline, "_conform_beats", lambda *a, **k: None)

    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "x", "target_seconds": 2.0, "role": "hook",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0}]}
    monkeypatch.setattr(mix_pipeline, "build_edit_plan", lambda *a, **k: plan)

    class S:
        def update_mix_job(self, *a, **k):
            pass

        def list_scene_assets(self, customer_id=0, asset_type=None):
            # clip·sfx 둘 다 자산이 있는 상황
            return [{"id": 1, "asset_type": asset_type}]

        def get_setting(self, key, default=""):
            return "1" if key == "scene_library_auto_enabled" else default

    mix_pipeline._plan_and_tts(S(), "job1", {0: "s"}, 2.0, "t", "레시피",
                               tmp_path, customer_id=0)
    assert calls == ["clip", "sfx"]   # clip 매칭 직후 sfx 매칭


def test_scene_library_off_by_default(monkeypatch, tmp_path):
    """설정을 안 켜면 자산이 있어도 아무것도 안 붙는다(2026-08-01 실사고)."""
    calls = []
    monkeypatch.setattr(mix_pipeline, "match_scene_assets",
                        lambda plan, assets: (calls.append("clip"), plan)[1])
    monkeypatch.setattr(mix_pipeline, "match_sfx",
                        lambda plan, assets: (calls.append("sfx"), plan)[1])
    monkeypatch.setattr(mix_pipeline, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mix_pipeline, "_refill_beats_to_tts", lambda *a, **k: None)
    monkeypatch.setattr(mix_pipeline, "_conform_beats", lambda *a, **k: None)
    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "x", "target_seconds": 2.0, "role": "hook",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0}]}
    monkeypatch.setattr(mix_pipeline, "build_edit_plan", lambda *a, **k: plan)

    class S:
        def update_mix_job(self, *a, **k):
            pass

        def list_scene_assets(self, customer_id=0, asset_type=None):
            return [{"id": 1, "asset_type": asset_type}]

        def get_setting(self, key, default=""):
            return default          # 설정 없음 = 기본 OFF

    mix_pipeline._plan_and_tts(S(), "job1", {0: "s"}, 2.0, "t", "레시피",
                               tmp_path, customer_id=0)
    assert calls == []
