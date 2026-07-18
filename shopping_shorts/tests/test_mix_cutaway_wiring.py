"""Task 3 seam 테스트 — 매칭(scene_match)이 쓴 beat["cutaway"]를 run_render가 그대로
읽어 asset_id→media_path로 해석해 assemble에 cutaway_paths로 넘기는지(저장위치=읽기위치).

브리프의 `_prepare_render_inputs` 스텁은 실제 코드에 없다(run_render는 tts_paths를 plan에서
직접 만들고, source_video_paths는 _resolve_sources(job, work)로 만든다) — 그래서 그 두 지점을
그대로 monkeypatch로 잘라내 핵심 단언만 남긴다.
"""
from pathlib import Path

from shopping_shorts import mix_pipeline


def test_run_render_resolves_cutaway_asset_paths(monkeypatch, tmp_path):
    # plan의 beat["cutaway"]["asset_id"]가 assemble에 media_path로 넘어가는지(seam).
    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "x", "target_seconds": 2.0, "role": "본문",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0,
         "cutaway": {"asset_id": 5, "score": 0.9}}]}

    captured = {}

    def fake_assemble(edit_plan, tts_paths, source_video_paths, out_path, **kw):
        captured["cutaway_paths"] = kw.get("cutaway_paths")
        Path(out_path).write_bytes(b"x")
        return out_path
    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)

    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, jid):
            # 실제 mix_jobs 스키마엔 customer_id 컬럼이 없다(get_mix_job이 반환하는 dict에도
            # 없음) — run_render은 job.get("customer_id", 0) 관용구로 안전 기본값을 쓴다.
            return {"edit_plan": plan, "status": "ready_for_review", "urls": [],
                    "subtitle_removal": False, "deco": None, "headcopy": None,
                    "caption_style": None}

        def get_scene_asset(self, asset_id, customer_id=0):
            return {"id": asset_id, "media_path": f"/lib/{asset_id}.mp4"}

        def update_mix_job(self, *a, **k):
            pass
    monkeypatch.setattr(mix_pipeline, "Store", FakeStore)

    # _resolve_sources: 실제로는 work 디렉터리를 glob해서 소스 mp4를 찾는다. 이 seam
    # 테스트는 그 경로를 안 쓰므로(다운로드 소스 없음) 빈 dict로 잘라낸다.
    monkeypatch.setattr(mix_pipeline, "_resolve_sources", lambda job, work: {})

    mix_pipeline.run_render("job1", str(tmp_path / "db"), str(tmp_path))

    assert captured["cutaway_paths"] == {0: "/lib/5.mp4"}


def test_run_preview_resolves_cutaway_asset_paths(monkeypatch, tmp_path):
    # 리뷰 발견사항: run_render는 cutaway_paths를 assemble에 넘기지만 run_preview는
    # 안 넘겨서, 사장님이 유료 VMake 렌더 전에 무료로 확인하는 미리보기에 방금 붙인
    # 컷어웨이가 안 보였다. run_preview도 동일하게 해석해서 넘기는지 검증(seam).
    plan = {"structure": "t", "beats": [
        {"beat_idx": 0, "narration": "x", "target_seconds": 2.0, "role": "본문",
         "primary": {"video_id": 0, "seg_id": "s0", "start": 0, "end": 2},
         "alternates": [], "effect": "cut", "fit": 0,
         "cutaway": {"asset_id": 5, "score": 0.9}}]}

    captured = {}

    def fake_assemble(edit_plan, tts_paths, source_video_paths, out_path, **kw):
        captured["cutaway_paths"] = kw.get("cutaway_paths")
        Path(out_path).write_bytes(b"x")
        return out_path
    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)

    class FakeStore:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, jid):
            # run_preview는 status를 안 건드리지만 get_mix_job은 여전히 전체 job을
            # 반환해야 한다 — customer_id는 스키마에 없으므로 job.get(..., 0) 관용구.
            return {"edit_plan": plan, "status": "ready_for_review", "urls": [],
                    "subtitle_removal": False, "deco": None, "headcopy": None,
                    "caption_style": None}

        def get_scene_asset(self, asset_id, customer_id=0):
            return {"id": asset_id, "media_path": f"/lib/{asset_id}.mp4"}

        def update_mix_job(self, *a, **k):
            pass
    monkeypatch.setattr(mix_pipeline, "Store", FakeStore)

    # _resolve_sources: 실제로는 work 디렉터리를 glob해서 소스 mp4를 찾는다. 이 seam
    # 테스트는 그 경로를 안 쓰므로(다운로드 소스 없음) 빈 dict로 잘라낸다.
    monkeypatch.setattr(mix_pipeline, "_resolve_sources", lambda job, work: {})

    mix_pipeline.run_preview("job1", str(tmp_path / "db"), str(tmp_path))

    assert captured["cutaway_paths"] == {0: "/lib/5.mp4"}
