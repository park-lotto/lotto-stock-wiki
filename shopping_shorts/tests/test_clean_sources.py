from shopping_shorts.store import Store


def test_clean_fields_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    s = Store(db)
    s.create_mix_job("j1", ["u"], 30, "template")
    job = s.get_mix_job("j1")
    assert job["clean_status"] is None
    assert job["clean_sources"] is None
    assert job["clean_error"] is None
    s.update_mix_job("j1", clean_status="ready", clean_error=None,
                     clean_sources={"s0": "/tmp/clean_src_s0.mp4"})
    job = s.get_mix_job("j1")
    assert job["clean_status"] == "ready"
    assert job["clean_sources"] == {"s0": "/tmp/clean_src_s0.mp4"}


def test_clean_status_failed_persists(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_mix_job("j2", ["u"], 30, "template")
    s.update_mix_job("j2", clean_status="failed", clean_error="키 없음")
    job = s.get_mix_job("j2")
    assert job["clean_status"] == "failed"
    assert job["clean_error"] == "키 없음"
