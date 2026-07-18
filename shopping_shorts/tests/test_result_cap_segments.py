from shopping_shorts import video_assemble as va


def test_result_builder_adds_cap_segments(monkeypatch):
    from shopping_shorts import app as appmod

    narr = "여러분 오이 절대 냉장고에 그냥 두지 마세요"

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, job_id):
            return {"edit_plan": {"structure": "hook", "beats": [
                {"beat_idx": 0, "narration": narr, "role": "hook"}]}}
    monkeypatch.setattr(appmod, "Store", FakeStore)

    res = appmod.api_mix_result("job1")
    beat = res["beats"][0]
    assert beat["cap_segments"] == va._caption_segments(narr)
    assert len(beat["cap_segments"]) >= 1
