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


def _fake_tear(monkeypatch, bad=()):
    from tools.calcopy.engine import bench_member as BM
    def tear(mp4, outdir, llm):
        if mp4.stem in bad:
            raise RuntimeError("뜯기 실패")
        return {"id": mp4.stem}, {"k": mp4.stem[0]}, None
    monkeypatch.setattr(BM, "member_llm", lambda: None)
    monkeypatch.setattr(BM, "tear", tear)
    monkeypatch.setattr(BM, "shape_key", lambda frame: frame["k"])


def _fake_save(monkeypatch, fail_ids=()):
    from tools.calcopy.engine import preset_save as P
    saved = []
    def save(J, frame, dest, vid, src):
        if vid in fail_ids:
            raise OSError("저장 실패")
        saved.append((dest.name, vid))
    monkeypatch.setattr(P, "save", save)
    return saved


def _tear(tmp_path, ids):
    return R.run_do(tmp_path, [{"id": "t", "cmd": "bm_tear", "slug": "s", "videos": [{"id": i, "mp4": f"src/{i}.mp4"} for i in ids]}])["t"]


def test_tear_same_shape_one_group(monkeypatch, tmp_path):
    _fake_tear(monkeypatch)
    saved = _fake_save(monkeypatch)
    out = _tear(tmp_path, ["a1", "a2"])
    assert len(out["presets"]) == 1 and out["presets"][0]["style"] == "틀" and out["presets"][0]["sources"] == ["a1", "a2"]
    assert saved == [("틀", "a1"), ("틀", "a2")]


def test_tear_other_shape_is_tul2(monkeypatch, tmp_path):
    _fake_tear(monkeypatch)
    _fake_save(monkeypatch)
    out = _tear(tmp_path, ["a1", "b1"])
    assert sorted(p["style"] for p in out["presets"]) == ["틀", "틀2"]


def test_tear_one_failure_keeps_going(monkeypatch, tmp_path):
    _fake_tear(monkeypatch, bad=("a1",))
    _fake_save(monkeypatch)
    out = _tear(tmp_path, ["a1", "a2"])
    assert len(out["failed"]) == 1 and out["failed"][0]["video"] == "a1" and "뜯기 실패" in out["failed"][0]["why"]
    assert out["presets"][0]["sources"] == ["a2"]


def test_tear_save_failure_leaves_no_ghost_group(monkeypatch, tmp_path):
    _fake_tear(monkeypatch)
    _fake_save(monkeypatch, fail_ids=("a1",))
    out = _tear(tmp_path, ["a1", "b1"])
    assert out["failed"][0]["video"] == "a1"
    assert all(p["sources"] for p in out["presets"])                  # 빈 유령 틀 없음
    assert [p["style"] for p in out["presets"]] == ["틀"]             # 번호도 소비하지 않음


def test_bm_fetch_copies_outside_mp4_and_returns_relative(monkeypatch, tmp_path):
    from tools.calcopy.engine import bench_member as BM, agy_check
    W = tmp_path / "w"
    W.mkdir()
    ext = tmp_path / "ext" / "x.mp4"
    ext.parent.mkdir()
    ext.write_bytes(b"x")
    monkeypatch.setattr(BM, "given_videos", lambda vs: [{"id": "x1"}])
    monkeypatch.setattr(BM, "fetch", lambda v, d: str(ext))
    monkeypatch.setattr(agy_check, "to360", lambda src, dst: str(dst))
    out = R.run_do(W, [{"id": "f", "cmd": "bm_fetch", "videos": ["whatever"]}])["f"]
    v = out["videos"][0]
    assert v["mp4"] == "src/x1.mp4" and v["v360"] == "src/x1_360.mp4"
    assert (W / "src" / "x1.mp4").read_bytes() == b"x"


def test_bm_brief_sends_paths_relative_to_work(monkeypatch, tmp_path):
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    (p / "frame.json").write_text("{}", encoding="utf-8")
    from tools.calcopy.engine import preset_brief
    monkeypatch.setattr(preset_brief, "render", lambda pd, od, name: {"md": str(od / "프리셋.md"), "claude_md": str(od / "CLAUDE.md"), "sha": "x"})
    out = R.run_do(tmp_path, [{"id": "b", "cmd": "bm_brief", "slug": "s", "style": "틀", "name": "n"}])["b"]
    assert out["md"] == "channel/s/preset/틀/프리셋.md" and out["claude_md"] == "channel/s/preset/틀/CLAUDE.md"
    assert str(tmp_path) not in json_dump(out)


def json_dump(o):
    import json
    return json.dumps(o, ensure_ascii=False)


def _answer_later(q, ans, after):
    """회원 Claude 대신 — after 초 뒤 줄 폴더에 답을 쓴다(engine_bridge.answer 와 같은 꼴: tmp → 바꿔 달기)."""
    import json
    import threading
    import time

    def run():
        t0 = time.time()
        while time.time() - t0 < 30:
            for d in q.iterdir() if q.is_dir() else []:
                if (d / "request.json").is_file() and not (d / "answer.json").exists() and time.time() - t0 >= after:
                    (d / "answer.json.tmp").write_text(json.dumps(ans, ensure_ascii=False), encoding="utf-8")
                    (d / "answer.json.tmp").replace(d / "answer.json")
                    return
            time.sleep(0.1)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th


def test_tear_without_member_key_waits_for_member_claude_past_stall(monkeypatch, tmp_path):
    """회원 제미나이 키 없음 → bm_tear 의 판독은 회원 Claude(client_llm) 줄 폴더로 간다. 답을 기다리는 동안은 진행 신호 없음으로 끊지 않는다(Ruling 16)."""
    from tools.calcopy.engine import bench_member as BM, client_llm, gemini_free as GF
    q = tmp_path / "ai" / "_runner"
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(q))
    monkeypatch.delenv("SHORTEM_MEMBER_GEMINI_KEY", raising=False)
    monkeypatch.setattr(GF, "BACKEND", "client")
    monkeypatch.setattr(client_llm, "POLL_S", 0.05)
    seen = {}

    def tear(mp4, outdir, llm):
        d, err = llm(["글"], "자막을 읽어라", "bench_ocr")
        seen["d"], seen["err"] = d, err
        return {"id": mp4.stem}, {"k": "a"}, None
    monkeypatch.setattr(BM, "tear", tear)
    monkeypatch.setattr(BM, "shape_key", lambda frame: frame["k"])
    _fake_save(monkeypatch)
    W = tmp_path / "W"
    W.mkdir()
    th = _answer_later(q, {"items": ["첫 줄"]}, after=2.5)     # 진행 신호 없음 기준(stall)의 다섯 배를 넘겨 답한다
    out = R.run_do(W, [{"id": "t", "cmd": "bm_tear", "slug": "s", "videos": [{"id": "a1", "mp4": "src/a1.mp4"}]}], stall=0.5)["t"]
    th.join(5)
    assert "error" not in out, out
    assert seen["err"] is None and seen["d"]["items"] == ["첫 줄"] and seen["d"]["_via"] == "client"
    assert out["presets"][0]["sources"] == ["a1"] and not client_llm.WAITING


def test_watch_still_cuts_real_stall(tmp_path, monkeypatch):
    """회원 Claude 를 기다리지 않는 일은 예전처럼 stall 초 만에 끊는다(감시를 무디게 하지 않았다)."""
    import time
    monkeypatch.setitem(R.CMDS, "_t_sleep", lambda W, d: time.sleep(3) or {"ok": 1})
    out = R.run_do(tmp_path, [{"id": "s", "cmd": "_t_sleep"}], stall=0.5)["s"]
    assert out.get("timed_out") is True
