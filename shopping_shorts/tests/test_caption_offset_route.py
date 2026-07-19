def test_caption_offset_saved_on_beat(monkeypatch):
    from shopping_shorts import app as appmod
    saved = {}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, job_id):
            return {"edit_plan": {"beats": [
                {"beat_idx": 0, "narration": "가"}, {"beat_idx": 1, "narration": "나"}]}}
        def update_mix_job(self, job_id, **fields):
            saved.update(fields)
    monkeypatch.setattr(appmod, "Store", FakeStore)

    res = appmod.api_mix_caption_offset("job1", 1, {"offset": 0.3})
    assert res["ok"] is True and abs(res["offset"] - 0.3) < 1e-9
    beat1 = saved["edit_plan"]["beats"][1]
    assert abs(beat1["cap_offset"] - 0.3) < 1e-9


def test_caption_offset_clamped_and_404(monkeypatch):
    from shopping_shorts import app as appmod
    from starlette.responses import JSONResponse

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, job_id):
            return {"edit_plan": {"beats": [{"beat_idx": 0, "narration": "가"}]}}
        def update_mix_job(self, job_id, **fields): pass
    monkeypatch.setattr(appmod, "Store", FakeStore)

    clamped = appmod.api_mix_caption_offset("job1", 0, {"offset": 99})
    assert clamped["offset"] == 2.0                      # 상한 클램프
    missing = appmod.api_mix_caption_offset("job1", 5, {"offset": 0.1})
    assert isinstance(missing, JSONResponse) and missing.status_code == 404
