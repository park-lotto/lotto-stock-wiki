from scripts.goal_loop import pending, morning_brief as mb


def test_publish_reads_and_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(pending, "PENDING_PATH", tmp_path / "p.json")
    pending.write({"date": "2026-07-02", "png": "x.png", "reasons": ["폭락"], "created_at": "t"})
    calls = {}
    monkeypatch.setattr(mb.viz_card, "send_telegram_photo",
                        lambda png, caption="", chat_id=None: calls.setdefault("png", png) or True)
    from scripts.goal_loop import publish
    res = publish.publish_pending()
    assert res["ok"] is True and res["sent"] is True
    assert calls["png"] == "x.png"
    assert pending.read() is None


def test_publish_no_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(pending, "PENDING_PATH", tmp_path / "none.json")
    from scripts.goal_loop import publish
    res = publish.publish_pending()
    assert res["ok"] is False
