from tools.calcopy.hybrid import runner_ops as R


def test_cmds_registered():
    for c in ("bm_env", "bm_fetch", "bm_tear", "agy_read", "bm_side", "bm_brief"):
        assert c in R.CMDS and c in R.CMD_LABEL


def test_agy_read_passes_through(monkeypatch, tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"x")
    from tools.calcopy.engine import agy
    monkeypatch.setattr(agy, "ask_video", lambda v, ask, schema, **k: {"answer": {"ok": 1}, "sec": 1.0})
    out = R.run_do(tmp_path, [{"id": "a1", "cmd": "agy_read", "video": "v.mp4", "ask": "q", "schema": {"type": "object"}}])
    assert out["a1"]["answer"] == {"ok": 1}


def test_agy_read_refuses_path_outside_work(tmp_path):
    out = R.run_do(tmp_path, [{"id": "a1", "cmd": "agy_read", "video": "../x.mp4", "ask": "q", "schema": {}}])
    assert "error" in out["a1"]


def test_bm_brief_writes_zip(monkeypatch, tmp_path):
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    (p / "frame.json").write_text("{}", encoding="utf-8")
    (p / "manifest.json").write_text("{}", encoding="utf-8")
    from tools.calcopy.engine import preset_brief
    monkeypatch.setattr(preset_brief, "render", lambda pd, od, name: {"md": "프리셋.md", "claude_md": "CLAUDE.md", "sha": "x"})
    out = R.run_do(tmp_path, [{"id": "b", "cmd": "bm_brief", "slug": "s", "style": "틀", "name": "n"}])
    assert (tmp_path / out["b"]["zip"]).exists()


def test_bm_env_shape(monkeypatch, tmp_path):
    from tools.calcopy.engine import agy
    monkeypatch.setattr(agy, "find", lambda: "agy.exe")
    monkeypatch.setattr(agy, "logged_in", lambda run=None: True)
    out = R.run_do(tmp_path, [{"id": "e", "cmd": "bm_env"}])["e"]
    assert out["agy"] is True and out["agy_login"] is True and out["disk_gb"] > 0


def test_slug_cannot_escape_work_folder(tmp_path):
    out = R.run_do(tmp_path, [{"id": "t", "cmd": "bm_tear", "slug": "../../x", "videos": []},
                              {"id": "b", "cmd": "bm_brief", "slug": "../../x", "style": "틀", "name": "n"}])
    assert "error" in out["t"] and "error" in out["b"]


def test_bm_side_refuses_outside_path(tmp_path):
    out = R.run_do(tmp_path, [{"id": "s", "cmd": "bm_side", "bench": "../a.mp4", "ours": "b.mp4"}])
    assert "error" in out["s"]
