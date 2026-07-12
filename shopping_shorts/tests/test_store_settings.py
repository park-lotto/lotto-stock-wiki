from shopping_shorts.store import Store


def test_set_and_get_setting(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.get_setting("vmake_api_key") is None      # 기본 None
    s.set_setting("vmake_api_key", "abc123")
    assert s.get_setting("vmake_api_key") == "abc123"


def test_set_setting_overwrites(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("vmake_api_key", "first")
    s.set_setting("vmake_api_key", "second")
    assert s.get_setting("vmake_api_key") == "second"


def test_get_setting_default(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.get_setting("missing", default="fallback") == "fallback"


def test_mix_job_subtitle_removal_default(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_mix_job("j1", ["u"], 30, "template")
    job = s.get_mix_job("j1")
    assert job["subtitle_removal"] is False       # 기본 꺼짐
    assert job["clean_video_path"] is None


def test_mix_job_subtitle_removal_true(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_mix_job("j2", ["u"], 30, "template", subtitle_removal=True)
    assert s.get_mix_job("j2")["subtitle_removal"] is True


def test_update_mix_job_clean_path(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.create_mix_job("j3", ["u"], 30, "template")
    s.update_mix_job("j3", clean_video_path="/x/clean.mp4")
    assert s.get_mix_job("j3")["clean_video_path"] == "/x/clean.mp4"
