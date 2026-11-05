"""kal.py 선정·수집·공통 — 개정안 kal v2 채택 항목(관제 319, 11-06).
select-04 선정표·선정 밖 편 금지 · select-07 하루당 조회 · select-12 다른 ref 거절 · outside-01 형식 칸 · common-23 영상 목록 입구
collect-01 멈춤·형식 없음 대안 · collect-04 댓글 따로 · collect-m01 sha256 중복 · common-10 write_guard · common-17 지침서 바뀜
"""
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.calcopy.engine import kal


def _S(tmp_path, monkeypatch, ref="@ch", fmt=None):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "DATA", tmp_path / "data")
    S = kal.State("s1", ref, "우리", 2, "아니오", "v", fmt)
    S.save()
    return S


def _cp(out="", rc=0):
    return SimpleNamespace(returncode=rc, stdout=out, stderr="")


def test_select12_other_ref_refused(tmp_path, monkeypatch):
    _S(tmp_path, monkeypatch, "@ch")
    kal.State("s1", "https://www.youtube.com/@ch/shorts", None, 2, None)          # 같은 채널 다른 꼴은 통과
    with pytest.raises(ValueError, match="다른 벤치"):
        kal.State("s1", "@other", None, 2, None)


def test_select07_04_rank_per_day_and_table(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch)
    now = time.time()
    day = lambda n: time.strftime("%Y%m%d", time.localtime(now - n * 86400))  # noqa: E731
    flat = {"channel": "채널", "channel_follower_count": 1000, "entries": [
        {"id": "old", "view_count": 1000000}, {"id": "new", "view_count": 300000}, {"id": "mid", "view_count": 500000}]}
    det = {"old": day(1000), "new": day(3), "mid": day(100)}
    seen = []

    def fake_run(cmd, timeout=0):
        seen.append(cmd)
        if "--flat-playlist" in cmd:
            assert cmd[-1].endswith("/shorts")
            return _cp(json.dumps(flat))
        vid = cmd[-1].split("v=")[-1]
        return _cp(json.dumps({"upload_date": det[vid], "duration": 30, "title": vid}))
    monkeypatch.setattr(kal, "_run", fake_run)
    st, out, note = kal.step_select(S)
    assert st == "done"
    assert S.d["channel"]["top_ids"] == ["new", "mid"]                   # 누적 1위(old)가 아니라 하루당 조회순
    tab = Path(out["pick_table"]).read_text(encoding="utf-8")
    assert "| 1 | new | https://www.youtube.com/shorts/new |" in tab and "하루당 조회" in tab
    assert S.d["channel"]["measured_at"]


def test_outside01_long_format_uses_videos_tab_and_min_len(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch, fmt="long")
    flat = {"entries": [{"id": "a", "view_count": 10, "duration": 600, "upload_date": "20250101"}, {"id": "b", "view_count": 20, "duration": 60, "upload_date": "20250101"}]}
    monkeypatch.setattr(kal, "_run", lambda cmd, timeout=0: _cp(json.dumps(flat)) if cmd[-1].endswith("/videos") else _cp("", 1))
    st, out, note = kal.step_select(S)
    assert st == "done" and S.d["channel"]["top_ids"] == ["a"] and S.d["format"] == "long"


def test_select04_tteutgi_refuses_ids_outside_pick(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch)
    S.d["channel"] = {"top_ids": ["a"]}
    S.step("collect").update({"state": "done", "outputs": {"ids": ["a", "x"]}})
    st, out, note = kal.step_tteutgi(S)
    assert st == "failed" and "선정 밖" in note


def test_common23_given_files_skip_channel(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch, ref=[str(tmp_path / "v1.mp4")])
    (tmp_path / "v1.mp4").write_bytes(b"one")
    from tools.calcopy.engine.bench_member import given_videos
    S.d["given"] = given_videos([str(tmp_path / "v1.mp4")])
    monkeypatch.setattr(kal, "_run", lambda *a, **k: pytest.fail("채널 목록을 읽으면 안 된다"))
    st, out, note = kal.step_select(S)
    assert st == "done" and S.d["channel"]["top_ids"] == ["v1"]
    monkeypatch.setattr(kal, "disk_gate", lambda w: None)
    st, out, note = kal.step_collect(S)
    assert st == "done" and (tmp_path / "data/s1/src/v1.mp4").read_bytes() == b"one"


def test_collect01_stall_then_alt_format(tmp_path, monkeypatch):
    base = tmp_path
    calls = []

    def fake(args, timeout=0, stall_sec=None, watch=None):
        calls.append(args[1])
        assert stall_sec == kal.STALL_SEC and watch == base / "v"
        if len(calls) == 1:
            return SimpleNamespace(returncode=1, stalled=True, timed_out=False, stderr="")
        (base / "v.mp4").write_bytes(b"x")
        return SimpleNamespace(returncode=0, stalled=False, timed_out=False, stderr="")
    rc, note = kal.fetch_one(base, "v", "u", "A/B", ytdlp=fake)
    assert rc == 0 and calls == ["A/B", "B"] and "대안" in note


def test_collect01_404_no_retry(tmp_path):
    calls = []

    def fake(args, **k):
        calls.append(1)
        return SimpleNamespace(returncode=1, stalled=False, timed_out=False, stderr="HTTP 404")
    rc, note = kal.fetch_one(tmp_path, "v", "u", "A/B", ytdlp=fake)
    assert rc == 1 and len(calls) == 1


def test_collect_m01_and_04_dedupe_and_comments(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch)
    S.d["channel"] = {"top_ids": ["a", "b", "c"]}
    src = tmp_path / "data/s1/src"
    src.mkdir(parents=True)
    monkeypatch.setattr(kal, "disk_gate", lambda w: None)

    def fake_fetch(base, vid, url, fmt):
        (base / f"{vid}.mp4").write_bytes(b"same" if vid in ("a", "b") else b"other")
        return 0, ""
    monkeypatch.setattr(kal, "fetch_one", fake_fetch)

    def fake_run(cmd, timeout=0):
        if "--write-comments" in cmd:
            vid = Path(cmd[cmd.index("-o") + 1]).name.split(".")[0]
            (src / f"{vid}.comments.info.json").write_text(json.dumps({"comments": [{"text": "ㅋㅋ", "timestamp": 1}]}), encoding="utf-8")
        return _cp()
    monkeypatch.setattr(kal, "_run", fake_run)
    st, out, note = kal.step_collect(S)
    assert st == "done" and out["ids"] == ["a", "c"] and "b=a" in note
    assert json.loads((src / "a.comments.json").read_text(encoding="utf-8"))[0]["text"] == "ㅋㅋ"


def test_common10_write_guard_frozen_preset(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch)
    pd = S.dir / "preset/p"
    pd.mkdir(parents=True)
    (pd / "manifest.json").write_text(json.dumps({"frozen_at": "2026-11-06"}), encoding="utf-8")
    (pd / "frame.json").write_text("{}", encoding="utf-8")
    for k in kal.STEPS:
        S.step(k)["state"] = "done"
    S.step("apply")["state"] = "todo"

    def bad_apply(S_):
        (pd / "frame.json").write_text('{"x":1}', encoding="utf-8")
        return "done", {}, "ok"
    monkeypatch.setitem(kal.RUN, "apply", bad_apply)
    kal.run(S, log=lambda *a: None)
    assert S.step("apply")["state"] == "failed" and "지킬 파일" in S.step("apply")["note"]


def test_common17_guide_change_resets_human_steps(tmp_path, monkeypatch):
    S = _S(tmp_path, monkeypatch)
    g = tmp_path / kal.GUIDE_FILES[0]
    g.parent.mkdir(parents=True)
    g.write_text("# 지침\n## 1 절\n", encoding="utf-8")
    assert kal.guide_check(S) == []
    S.step("rules")["state"] = "done"
    g.write_text("# 지침\n## 1 절\n## 2 새 절\n", encoding="utf-8")
    ch = kal.guide_check(S)
    assert ch and "2 새 절" in ch[0] and S.step("rules")["state"] == "todo"


def test_from_start_refuses_when_earlier_human_step_todo(tmp_path, monkeypatch):
    """감시 적발(11-06 kal_snap run_make4): '[지침 바뀜]'으로 readlines·rules·copy 가 todo 인데 --from make 가 make·verify 를 그대로 돌렸다.
    앞 단계가 done 이 아니면 --from 은 아무 단계도 돌리지 않고 멈춘다(Jev C:/t/fm_jev/q2.json fix_0)."""
    S = _S(tmp_path, monkeypatch)
    for k in kal.STEPS:
        S.step(k)["state"] = "done"
    S.step("rules")["state"] = "todo"
    called = []
    monkeypatch.setattr(kal, "RUN", {k: (lambda S, k=k: called.append(k) or ("done", {}, "")) for k in kal.STEPS})
    logs = []
    kal.run(S, "make", log=logs.append)
    assert called == []
    assert any("rules" in x and "--from rules" in x for x in logs)
    S.step("rules")["state"] = "done"
    kal.run(S, "verify", log=logs.append)
    assert called == ["verify", "apply"]
