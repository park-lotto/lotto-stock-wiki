from scripts.goal_loop import pending

def test_write_read_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(pending, "PENDING_PATH", tmp_path / "pending.json")
    assert pending.read() is None
    pending.write({"date": "2026-07-02", "png": "x.png", "reasons": ["폭락"], "created_at": "t"})
    got = pending.read()
    assert got["date"] == "2026-07-02" and got["reasons"] == ["폭락"]
    pending.clear()
    assert pending.read() is None
