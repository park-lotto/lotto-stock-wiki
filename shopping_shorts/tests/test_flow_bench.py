# -*- coding: utf-8 -*-
import json

from tools.calcopy.hybrid import flow, flow_bench as FB, jev_gate
from tools.calcopy.hybrid import runner_ops as R


def _go(st, m=None, rp=None):
    return flow.step(st, m or {}, rp or {}, {})


def _vid(i):
    return {"id": i, "mp4": f"src/{i}.mp4", "v360": f"src/{i}_360.mp4", "title": i, "views": 1}


def _st(phase, **bm):
    return {"fmt": "벤치마킹", "phase": phase, "log": [], "tries": {}, "bm": {"slug": "s", "style": "틀", "name": "n", **bm}}


def _fr(n=1, tag="a"):
    """실행기 bm_eye_frames 가 돌려주는 한 편 그림 묶음 꼴."""
    return {"dur": 3.0, "fps": 30.0, "n_cuts_all": n, "frame0": f"eye/{tag}/frame0.jpg", "cuts": [{"t": 1.0 + i, "img": f"eye/{tag}/cut_{i:02d}.jpg"} for i in range(n)]}


def _eye_ans(n=1, kind="cut", f0="scene", text=""):
    return {"frame0": {"kind": f0, "text": text}, "cuts": [{"i": i, "kind": kind} for i in range(n)]}


def _done_eye(n=1):
    return {"cuts": [{"t": 1.0 + i, "kind": "cut"} for i in range(n)], "frame0": {"kind": "scene", "text": ""}}


def test_start_goes_to_env_check():
    st = flow.start_bench("https://www.youtube.com/@abc", [], "내프리셋", "a" * 12)
    r = _go(st)
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_env"
    assert r["stage"]["total"] == 9 and "칼카피" not in r["message"]


def test_agy_logout_stops_with_two_lines():
    st = flow.start_bench("https://www.youtube.com/@abc", [], "n", "b" * 12)
    _go(st)
    r = _go(st, {"bm_env": {"agy": True, "agy_login": False, "disk_gb": 50}})
    assert r["status"] == "stop" and r["why"] == "agy 로그인이 끊겼어요" and "제미나이" in r["fix"]
    assert r["retry_ok"] is True and "_task" not in r["state"]      # 회원 과제로 안 바뀌고, 오푸스로 넘어가지도 않는다


def test_agy_missing_stops():
    st = flow.start_bench("https://www.youtube.com/@abc", [], "n", "b" * 12)
    _go(st)
    assert _go(st, {"bm_env": {"agy": False, "agy_login": False}})["status"] == "stop"


def test_fable_only_two_places():
    assert sorted(q["id"] for q in FB.ASKS.values() if q["model"] == "fable") == ["bm_confirm", "bm_verdict"]


def test_no_sonnet_or_haiku():
    assert all(q["model"] in ("opus", "fable") for q in FB.ASKS.values())


def test_review_requests_use_asks_models():
    st = _st("bm_read_got", videos=[_vid("a")], eye={"a": _done_eye()})
    r = _go(st, {"read_a": {"answer": {"voice": "여"}}})
    assert r["status"] == "review" and r["review"][0]["model"] == "opus"
    assert _go(_st("bm_confirm", side="side/x.mp4", rules={}))["review"][0]["model"] == "fable"
    assert _go(_st("bm_verdict", side="side/x.mp4"))["review"][0]["model"] == "fable"


def test_read_schema_has_no_cut_count():
    assert not [k for k in FB.READ_SCHEMA["properties"] if "cut" in k and k != "cut_feel"]


def test_panbokki_stops_after_three():
    st = {"fmt": "벤치마킹", "phase": "bm_panbokki", "pan_n": 3, "log": [], "tries": {}, "bm": {"fails": ["caption.y"]}}
    r = _go(st, {"pan": {"match_ok": False, "fails": ["caption.y"]}})
    assert r["status"] == "stop" and "여기까지 맞췄어요" in r["why"] and "caption.y" in r["fix"]
    assert not r.get("retry_ok")


def test_jev_down_stops_without_task(monkeypatch):
    def boom(*a, **k):
        raise jev_gate.JevDown("no_key")
    monkeypatch.setattr(jev_gate, "decide", boom)
    st = {"fmt": "벤치마킹", "phase": "bm_panbokki", "pan_n": 0, "log": [], "tries": {}, "bm": {}}
    r = _go(st, {"pan": {"match_ok": False, "fails": ["caption.y"], "cands": [{"path": "a"}, {"path": "b"}]}})
    assert r["status"] == "stop" and r["why"] == "잠시 판단 서버가 쉬고 있어요" and r["fix"] == "잠시 뒤 다시 해 주세요"
    assert r["retry_ok"] is True and "_task" not in r["state"] and r["state"]["alarm"]["kind"] == "jev_down"
    assert st["pan_n"] == 0 and any("경보" in x for x in st["log"])
    # 다시 시도: Jev 가 살아나면 직전 대조표로 이어 간다
    monkeypatch.setattr(jev_gate, "decide", lambda *a, **k: {"pick": 1, "conf": 0.9, "fixroot": [0.1, 0.9], "ok": True})
    st["phase"] = "bm_panbokki"
    st["bm"].update({"slug": "s", "style": "틀", "trial": "t.mp4", "videos": [_vid("a")]})
    r2 = _go(st)
    assert r2["status"] == "execute" and r2["do"][0]["fix"] == {"path": "b"}


def test_panbokki_picks_by_jev_and_remeasures(monkeypatch):
    seen = {}

    def dec(problem, facts, fixes):
        seen["fixes"] = fixes
        return {"pick": 0, "conf": 0.8, "fixroot": [0.8, 0.2], "ok": True}
    monkeypatch.setattr(jev_gate, "decide", dec)
    st = _st("bm_panbokki", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, {"pan": {"match_ok": False, "fails": ["x"], "cands": [{"path": "p1", "value": 1}, {"path": "p2", "value": 2}]}, "side": {"side": "side/a.mp4"}})
    assert [d["cmd"] for d in r["do"]] == ["bm_fix"] and r["do"][0]["fix"]["path"] == "p1" and st["phase"] == "bm_trial"   # 한 칸 고친 뒤 시험 편 다시(Ruling 10)
    assert st["pan_n"] == 1 and st["bm"]["side"] == "side/a.mp4" and len(seen["fixes"]) == 2


def test_panbokki_low_confidence_stops_no_deeper(monkeypatch):
    monkeypatch.setattr(jev_gate, "decide", lambda *a, **k: {"pick": 0, "conf": 0.5, "fixroot": [0.5, 0.5], "ok": False})
    st = _st("bm_panbokki", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, {"pan": {"match_ok": False, "fails": ["x"], "cands": [{"path": "p1"}, {"path": "p2"}]}})
    assert r["status"] == "stop" and "여기까지 맞췄어요" in r["why"] and "x" in r["fix"] and not r.get("retry_ok")


def test_no_candidates_stops_at_first_pan_without_side_rerender():
    st = _st("bm_panbokki", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, {"pan": {"match_ok": False, "fails": ["chunk.sec"], "cands": []}, "side": {"side": "side/a.mp4"}})
    assert r["status"] == "stop" and "여기까지 맞췄어요" in r["why"] and "chunk.sec" in r["fix"]
    assert "do" not in r and st.get("pan_n", 0) == 0
    assert "deeper" not in json.dumps(r, ensure_ascii=False)


def test_alarm_shape_is_fixed(monkeypatch):
    def boom(*a, **k):
        raise jev_gate.JevDown("no_key")
    monkeypatch.setattr(jev_gate, "decide", boom)
    st = _st("bm_panbokki")
    _go(st, {"pan": {"match_ok": False, "fails": ["x"], "cands": [{"path": "a"}, {"path": "b"}]}})
    assert set(st["alarm"]) == set(FB.ALARM_KEYS) and st["alarm"] == {"kind": "jev_down", "why": "no_key", "at": "bm_panbokki"}


def test_fable_never_called_a_third_time():
    # 확정(1) → 최종 불합격 → 되돌림 → 잡도리가 맞았다고 해도 세 번째 페이블 요청은 나가지 않는다
    st = _st("bm_confirm", rules={"rules": {}}, side="side/a.mp4")
    r = _go(st)
    assert r["status"] == "review" and r["review"][0]["id"] == "bm_confirm" and st["bm"]["fable_n"] == 1
    r = _go(st, rp={"bm_confirm": {"ok": True, "wrong": []}})
    assert r["review"][0]["id"] == "bm_verdict" and st["bm"]["fable_n"] == 2
    r = _go(st, rp={"bm_verdict": {"ok": False, "wrong": ["caption.y"]}})
    assert r["status"] == "stop" and "caption.y" in r["fix"]       # 후보가 없어 잡도리에서 멈춤
    st["phase"] = "bm_panbokki"                                      # 후보가 있어 맞췄다고 나와도
    r = _go(st, {"pan": {"match_ok": True}})
    assert r["status"] == "stop" and "여기까지 맞췄어요" in r["why"] and "caption.y" in r["fix"] and "review" not in r
    assert st["bm"]["fable_n"] == 2
    st["phase"] = "bm_verdict"
    assert _go(st)["status"] == "stop" and st["bm"]["fable_n"] == 2


def test_match_ok_goes_to_confirm_review():
    st = _st("bm_panbokki", rules={"rules": {}})
    r = _go(st, {"pan": {"match_ok": True}, "side": {"side": "side/a.mp4"}})
    assert r["status"] == "review" and r["review"][0]["id"] == "bm_confirm" and r["review"][0]["show"] == [{"file": "side/a.mp4"}]


def test_confirm_fail_goes_back_then_stops():
    st = _st("bm_confirm_got", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, rp={"bm_confirm": {"ok": False, "wrong": ["caption.y"]}})      # 되돌림 → 고칠 후보 없음 → 바로 멈춤(재기 되풀이 없음)
    assert r["status"] == "stop" and "caption.y" in r["fix"] and st["bm"]["confirm_n"] == 1
    st["bm"]["confirm_n"] = 5                  # 되돌림 횟수 상한(CONFIRM_MAX)은 없어졌다 — 멈춤은 잡도리 규칙(후보 0) 하나
    st["phase"] = "bm_verdict_got"
    r = _go(st, rp={"bm_verdict": {"ok": False, "wrong": ["caption.y"]}})
    assert r["status"] == "stop" and "caption.y" in r["fix"]


def test_verdict_ok_makes_brief_and_finishes():
    st = _st("bm_verdict_got", other_styles=["틀2"])
    r = _go(st, rp={"bm_verdict": {"ok": True, "wrong": []}})
    assert r["do"][0]["cmd"] == "bm_brief"
    r = _go(st, {"brief": {"zip": "out/s_틀.zip"}})
    assert r["status"] == "done" and r["preset"]["zip"] == "out/s_틀.zip" and r["preset"]["other_styles"] == ["틀2"]


def test_two_frames_keeps_biggest():
    st = {"fmt": "벤치마킹", "phase": "bm_tear_got", "log": [], "tries": {}, "bm": {"slug": "s", "videos": [_vid("a"), _vid("b"), _vid("c")]}}
    r = _go(st, {"bm_tear": {"presets": [{"style": "틀", "sources": ["a", "b"]}, {"style": "틀2", "sources": ["c"]}], "failed": []}})
    assert st["bm"]["style"] == "틀" and st["bm"]["other_styles"] == ["틀2"]
    assert [d["cmd"] for d in r["do"]] == ["bm_skel"] and r["do"][0]["ids"] == ["a", "b"]       # 줄판독 뼈대 먼저(관리자 Ruling 8) — 판독은 그 줄로


def test_fix_command_registered_and_missing_slot_errors(tmp_path):
    assert "bm_fix" in R.CMDS and "bm_fix" in R.CMD_LABEL
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    (p / "frame.json").write_text(json.dumps({"caption": {"y": 1}}), encoding="utf-8")
    (p / "manifest.json").write_text("{}", encoding="utf-8")
    out = R.run_do(tmp_path, [{"id": "f", "cmd": "bm_fix", "slug": "s", "style": "틀", "fix": {"path": "nope", "value": 1, "why": "t"}}])
    assert "error" in out["f"]       # 없는 자리는 조용히 넘기지 않고 오류


# ── 줄판독(bm_measure — 관리자 Ruling 8: 뼈대 = kal_analyze.skeleton, 눈 칸 = bm_read 결과, check_doc 통과만 대조에) ──
def _skel(n=2):
    return {"lines": [{"i": i, "t0": i * 1.0, "t1": i * 1.0 + 0.9, "text": f"줄{i}"} for i in range(n)], "dur": 3.0}


def _eye(n=2, speaker="나레"):
    return [{"i": i, "speaker": speaker, "layer": "채널", "enter": "instant", "sfx": None, "scene": "제품", "t0": 99, "text": "바꿈"} for i in range(n)]


def test_skel_then_reads_carry_lines():
    st = _st("bm_skel_got", videos=[_vid("a"), _vid("b")], keep=["a", "b"])
    r = _go(st, {"skel": {"docs": {"a": _skel(), "b": _skel()}, "failed": []}})
    assert [d["id"] for d in r["do"]] == ["read_a", "read_b", "eye_b"] and r["do"][0]["video"] == "src/a_360.mp4"
    e = r["do"][2]
    assert e["cmd"] == "bm_eye_frames" and [v["mp4"] for v in e["videos"]] == ["src/a.mp4", "src/b.mp4"]      # 원본(360 아님 — 2프레임 번쩍임)
    assert e["videos"][0]["win_doc"] == "channel/s/줄판독_뼈대/a.json"
    assert "줄1" in r["do"][0]["ask"] and "lines" in r["do"][0]["schema"]["properties"]


def test_skel_none_stops():
    st = _st("bm_skel_got", videos=[_vid("a")], keep=["a"])
    f = {"skel": {"docs": {}, "failed": [{"video": "a", "why": "뜯기 없음"}]}}
    r = _go(st, f)                       # 스스로 한 번 다시 — 뼈대만(옛 retry=bm_tear_got 은 빈 뜯기 결과로 '프리셋 없음' 오판)
    assert r["status"] == "execute" and [d["cmd"] for d in r["do"]] == ["bm_skel"]
    r = _go(st, f)                       # 또 실패 = 넘어가지 않는다
    assert r["status"] in ("stop", "review") and any("자막 줄을 나누지" in x for x in st["log"])


def test_read_then_fill_takes_only_eye_slots():
    st = _st("bm_read_got", videos=[_vid("a")], keep=["a"], skel={"a": 2})
    r = _go(st, {"read_a": {"answer": {"voice": "여", "lines": _eye()}}, "eye_b": {"frames": {"a": _fr(1)}, "failed": []}})
    assert r["review"][0]["id"] == "bm_read" and "lines" in r["review"][0]["need"] and r["review"][0]["model"] == "opus"
    assert [q["id"] for q in r["review"]] == ["bm_read", "bm_eye_a"]
    r = _go(st, rp={"bm_read": {"rules": {"자막": "노랑"}, "per_video": {"a": {"story_order": ["훅", "공개"]}}, "lines": {"a": _eye()}}, "bm_eye_a": _eye_ans(1, "flash")})
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_fill"
    f = r["do"][0]["fills"]["a"]
    assert all("t0" not in l and "text" not in l for l in f["lines"])       # 기계값(시각·글)은 뼈대 그대로 — 눈 칸만 채운다
    assert f["doc"]["narr_share"] == 1.0 and f["doc"]["beats"] == ["훅", "공개"]
    assert f["eye"] == {"cuts": [{"t": 1.0, "kind": "flash"}], "frame0": {"kind": "scene", "text": ""}}      # 시각 = 그림 뽑을 때 잰 값
    assert st["bm"]["rules"]["rules"] == {"자막": "노랑"}


def test_failed_check_doc_not_used_and_rereads_then_stops():
    st = _st("bm_measure_got", videos=[_vid("a"), _vid("b")], keep=["a", "b"], skel={"a": 2, "b": 2}, skel_lines={"a": _skel()["lines"], "b": _skel()["lines"]})
    r = _go(st, {"fill": {"ok": [], "bad": {"a": ["줄0 speaker 미기입"], "b": ["줄1 enter 미기입"]}, "dir": "channel/s/줄판독"}})
    assert r["status"] == "execute" and sorted(d["id"] for d in r["do"]) == ["read_a", "read_b"]      # 한 번 다시 읽기
    assert "speaker 미기입" in r["do"][0]["ask"] and not st["bm"].get("line_reads")
    st["phase"] = "bm_measure_got"
    r = _go(st, {"fill": {"ok": [], "bad": {"a": ["줄0 speaker 미기입"], "b": ["줄1 enter 미기입"]}, "dir": "channel/s/줄판독"}})
    assert r["status"] == "stop" and r["why"] and r["fix"] and not st["bm"].get("line_reads")


def test_partial_pass_keeps_only_passed_docs():
    st = _st("bm_measure_got", videos=[_vid("a"), _vid("b")], keep=["a", "b"], skel={"a": 2, "b": 2}, reread=1)
    r = _go(st, {"fill": {"ok": ["a"], "bad": {"b": ["줄1 enter 미기입"]}, "dir": "channel/s/줄판독"}})
    assert st["bm"]["line_reads"] == ["channel/s/줄판독/a.json"] and any("b" in x for x in st["log"])
    assert r["status"] == "review" and r["review"][0]["id"] == "bm_trial" and st["bm"]["line_reads"] == ["channel/s/줄판독/a.json"]


def test_flow_read_measure_trial_order():
    st = _st("bm_tear_got", videos=[_vid("a")])
    _go(st, {"bm_tear": {"presets": [{"style": "틀", "sources": ["a"]}], "failed": []}})
    assert st["phase"] == "bm_skel_got"
    _go(st, {"skel": {"docs": {"a": _skel()}, "failed": []}})
    assert st["phase"] == "bm_read_got"
    _go(st, {"read_a": {"answer": {"lines": _eye()}}, "eye_b": {"frames": {"a": _fr(1)}, "failed": []}})
    assert st["phase"] == "bm_measure"
    _go(st, rp={"bm_read": {"rules": {}, "per_video": {}, "lines": {"a": _eye()}}, "bm_eye_a": _eye_ans(1)})
    assert st["phase"] == "bm_measure_got"
    r = _go(st, {"fill": {"ok": ["a"], "bad": {}, "dir": "channel/s/줄판독"}})
    assert st["phase"] == "bm_trial_got" and r["status"] == "review" and r["review"][0]["id"] == "bm_trial"


# ── 실행기: 뼈대·채우기(판단 없음 — 뼈대 = kal_analyze.skeleton, 검사 = kal_analyze.check_doc) ──
def _tear_file(W, vid="a"):
    d = W / "channel" / "s" / "뜯기" / vid
    d.mkdir(parents=True)
    J = {"probe": {"duration": 3.0, "fps": 30, "w": 1080, "h": 1920}, "layout": {"window": [0, 0, 1080, 1920], "caption_band": [1200, 1400]},
         "captions": {"items": [{"t0": 0.0, "t1": 0.9, "text": ["첫", "줄"], "top_y": 1250}, {"t0": 1.0, "t1": 1.9, "text": "둘째 줄", "top_y": 1250}]},
         "cuts": {"times": [1.0]}}
    (d / "뜯기.json").write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")


def test_skel_and_fill_commands(tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    assert {"bm_skel", "bm_fill"} <= set(R.CMDS) and {"bm_skel", "bm_fill"} <= set(R.CMD_LABEL)
    _tear_file(tmp_path)
    out = R.run_do(tmp_path, [{"id": "skel", "cmd": "bm_skel", "slug": "s", "ids": ["a", "zz"]}])["skel"]
    assert [l["text"] for l in out["docs"]["a"]["lines"]] == ["첫 줄", "둘째 줄"] and out["failed"][0]["video"] == "zz"
    good = {"lines": [{"i": i, "speaker": "나레", "layer": "채널", "enter": "instant", "sfx": None, "scene": "제품"} for i in range(2)],
            "doc": {"beats": ["훅"], "narr_share": 1.0}}
    bad = {"lines": [{"i": 0, "speaker": "나레", "layer": "채널", "enter": "instant"}], "doc": {"beats": ["훅"], "narr_share": 1.0}}   # 줄1 눈 칸 비움
    res = R.run_do(tmp_path, [{"id": "fill", "cmd": "bm_fill", "slug": "s", "fills": {"a": good}}])["fill"]
    p = tmp_path / "channel" / "s" / "줄판독" / "a.json"
    assert res["ok"] == ["a"] and p.is_file() and not K.check_doc(json.loads(p.read_text(encoding="utf-8")))["errors"]
    res = R.run_do(tmp_path, [{"id": "fill", "cmd": "bm_fill", "slug": "s", "fills": {"a": bad}}])["fill"]
    assert res["ok"] == [] and res["bad"]["a"] and not p.exists()           # 못 넘은 판독은 남기지 않는다(대조에 안 쓰임)


# ── 시험 편 = 회원 과제(관리자 Ruling 10) · 대조 = bm_match(kal_analyze.bench_match) ──
def _trial_st(**kw):
    return _st("bm_measure_got", url="https://www.youtube.com/@abc", videos=[_vid("a")], keep=["a"], skel={"a": 2}, reread=1, **kw)


def test_trial_is_member_task_not_stop():
    st = _trial_st()
    r = _go(st, {"fill": {"ok": ["a"], "bad": {}, "dir": "channel/s/줄판독"}})
    q = r["review"][0]
    assert r["status"] == "review" and q["id"] == "bm_trial" and q["model"] == "opus" and "work_dir" in q["need"]
    assert q["meta"]["kind"] == "member_task" and q["meta"]["tool"] == "shortem_make"
    assert q["meta"]["preset"] == {"slug": "s", "style": "틀", "dir": "channel/s/preset/틀"} and q["meta"]["source"] == {"channel": "https://www.youtube.com/@abc"}
    assert "_task" not in st and r["stage"]["text"] == "시험 영상 만들기" and r["message"].endswith("시험 영상 만들기 중")
    assert "칼카피" not in r["message"] and "칼카피" not in q["ask"]


def test_trial_ask_has_preset_id_slot_for_member_pc():
    """회원 PC(flow_driver.memberTask)가 임시 내 프리셋 id 를 이 자리에 채운다 — 문구는 서버 한 곳(관제 319 과제 8)."""
    st = _trial_st()
    q = _go(st, {"fill": {"ok": ["a"], "bad": {}, "dir": "channel/s/줄판독"}})["review"][0]
    assert 'shortem_make(step="start", preset="{preset_id}")' in q["ask"]
    assert "sid" in q["ask"].split("답:")[1]


def test_trial_task_has_no_bench_mp4():
    st = _trial_st()
    r = _go(st, {"fill": {"ok": ["a"], "bad": {}, "dir": "channel/s/줄판독"}})
    blob = json.dumps(r["review"], ensure_ascii=False)
    assert "src/a.mp4" not in blob and "src/a_360.mp4" not in blob and ".mp4" not in json.dumps(r["review"][0]["meta"], ensure_ascii=False)


def test_trial_videos_only_source_has_no_channel():
    st = _st("bm_trial", videos_in=["https://youtube.com/shorts/aaa"], videos=[_vid("a")], line_reads=["channel/s/줄판독/a.json"])
    q = _go(st)["review"][0]
    assert q["meta"]["source"] == {"channel": None} and "youtube.com/shorts/aaa" not in q["ask"]


def test_trial_got_missing_or_failed_stops_two_lines():
    for rp in ({}, {"bm_trial": {"work_dir": "", "ok": False, "why": "렌더 실패"}}, {"bm_trial": {"ok": True}}):
        st = _st("bm_trial_got", videos=[_vid("a")], line_reads=["channel/s/줄판독/a.json"])
        r = _go(st, rp=rp)
        assert r["status"] == "stop" and r["why"] == "시험 영상을 만들지 못했어요" and r["fix"] and r["retry_ok"] is True
        assert "_task" not in r["state"]


def _trial_eye(st, n=1):
    """시험 편 눈 판정 두 걸음(그림 뽑기 → 같은 질문 review)을 지나 대조(bm_side·bm_match)까지."""
    r = _go(st, {"eye_t": {"frames": {"trial": _fr(n, "trial")}, "failed": []}})
    assert r["status"] == "review" and [q["id"] for q in r["review"]] == ["bm_eye_trial"]
    return _go(st, rp={"bm_eye_trial": _eye_ans(n)})


def test_trial_got_runs_side_and_match():
    st = _st("bm_trial_got", videos=[_vid("a")], keep=["a"], line_reads=["channel/s/줄판독/a.json"])
    r = _go(st, rp={"bm_trial": {"work_dir": "make/t1", "ok": True}})
    assert [d["cmd"] for d in r["do"]] == ["bm_eye_frames"] and st["phase"] == "bm_trial_eye"
    assert r["do"][0]["videos"] == [{"id": "trial", "mp4": "make/t1/final.mp4", "win_doc": "channel/s/줄판독/a.json"}]
    assert "화면 전환 확인" in R.CMD_LABEL["bm_eye_frames"] and "칼카피" not in R.CMD_LABEL["bm_eye_frames"]
    r = _trial_eye(st)
    assert [d["cmd"] for d in r["do"]] == ["bm_side", "bm_match"] and st["phase"] == "bm_panbokki"
    side, pan = r["do"]
    assert side["ours"] == "make/t1/final.mp4" and pan["work"] == "make/t1" and pan["line_reads"] == ["channel/s/줄판독/a.json"]
    assert pan["eye"] == {"cuts": [{"t": 1.0, "kind": "cut"}], "frame0": {"kind": "scene", "text": ""}}


def test_flow_trial_to_match_to_fix_and_back(monkeypatch):
    monkeypatch.setattr(jev_gate, "decide", lambda *a, **k: {"pick": 1, "conf": 0.9, "fixroot": [0.2, 0.8], "ok": True})
    st = _trial_st()
    _go(st, {"fill": {"ok": ["a"], "bad": {}, "dir": "channel/s/줄판독"}})
    assert st["phase"] == "bm_trial_got"
    _go(st, rp={"bm_trial": {"work_dir": "make/t1", "ok": True}})
    _trial_eye(st)
    assert st["phase"] == "bm_panbokki"
    cands = [{"path": "p1", "value": 1, "why": "a"}, {"path": "p2", "value": 2, "why": "b"}]
    r = _go(st, {"pan": {"match_ok": False, "fails": ["enter.mode.나레", "chunk.sec"], "cands": cands, "gate_ok": True}, "side": {"side": "side/x.mp4"}})
    assert [d["cmd"] for d in r["do"]] == ["bm_fix"] and r["do"][0]["fix"] == cands[1] and st["phase"] == "bm_trial"
    r = _go(st, {"fix": {"fixed": "p2"}})
    assert r["status"] == "review" and r["review"][0]["id"] == "bm_trial" and st["pan_n"] == 1


def test_fix_error_stops():
    st = _st("bm_trial", videos=[_vid("a")], line_reads=["x"])
    r = _go(st, {"fix": {"error": "ValueError: 자리 없음"}})
    assert r["status"] == "stop" and r["why"] and r["fix"]


def test_match_error_stops():
    st = _st("bm_panbokki", trial="make/t1/final.mp4", videos=[_vid("a")])
    r = _go(st, {"pan": {"error": "ValueError: timeline.json 에 줄 시각이 없다"}})
    assert r["status"] == "stop" and r["why"] and r["fix"]


# ── bm_match 실행기 + 진짜 match_table(가짜 함수 아님) ──
def _bench_doc(vid):
    return {"id": vid, "dur": 4.0, "lines": [{"t0": 0.0, "t1": 1.0, "text": "첫째 줄이다", "speaker": "나레", "layer": "채널", "enter": "pop"},
                                           {"t0": 1.0, "t1": 2.0, "text": "둘째 줄이다", "speaker": "나레", "layer": "채널", "enter": "pop"},
                                           {"t0": 2.0, "t1": 4.0, "text": "셋째 줄", "speaker": "나레", "layer": "채널", "enter": "pop"}]}


def _remake_out(W, verdict="통과", seams=True, kind="tts"):
    out = W / "make" / "t1"
    (out / "대조").mkdir(parents=True)
    steps = [{"text": "첫째 줄이다", "t0": 0.0, "t1": 1.0, "new_cut": True, "sent": 0, "line": 0},
             {"text": "첫째 줄이다\n둘째 줄이다", "t0": 1.0, "t1": 2.0, "new_cut": False, "sent": 0, "line": 0},
             {"text": "셋째 줄", "t0": 2.0, "t1": 4.0, "new_cut": True, "sent": 1, "line": 1}]
    (out / "timeline.json").write_text(json.dumps({"steps": steps, "dur": 4.0}, ensure_ascii=False), encoding="utf-8")
    bad = [] if verdict == "통과" else ["자막 y"]
    (out / "remake_log.json").write_text(json.dumps({"kind": kind, "steps": {"compare": {"verdict": verdict, "out": bad, "failed": []},
                                                                            "seams": {"ok": seams, "rewinds": [] if seams else [3.2]}}}, ensure_ascii=False), encoding="utf-8")
    (out / "대조" / "verdict.json").write_text(json.dumps({"verdict": verdict, "n_in": 3, "n_criteria": 3, "out": bad, "failed": []}, ensure_ascii=False), encoding="utf-8")
    (out / "audio.json").write_text(json.dumps({"sfx": []}), encoding="utf-8")
    return out


def _preset(W, enter=None):
    p = W / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    frame = {"canvas": [1080, 1920], "layers": [{"kind": "video", "x": 0, "y": 0, "w": 1080, "h": 1920},
                                                {"kind": "text", "role": "caption", "x": 540, "y": 1300, "w": 980, "align": "center", "lines": 2,
                                                 "font": "CcPretendard-Bold", "size": 60, "line_h": 70, "rgb": [255, 255, 255], "enter": enter}]}
    (p / "frame.json").write_text(json.dumps(frame, ensure_ascii=False), encoding="utf-8")
    (p / "manifest.json").write_text("{}", encoding="utf-8")
    lr = W / "channel" / "s" / "줄판독"
    lr.mkdir(parents=True)
    for v in ("a", "b"):
        (lr / f"{v}.json").write_text(json.dumps(_bench_doc(v), ensure_ascii=False), encoding="utf-8")


def test_bm_match_real_table_on_remake_folder(tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    assert "bm_match" in R.CMDS and "bm_match" in R.CMD_LABEL
    _remake_out(tmp_path)
    _preset(tmp_path)
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1",
                               "line_reads": ["channel/s/줄판독/a.json", "channel/s/줄판독/b.json"]}])["pan"]
    assert "error" not in out, out
    assert set(out) >= {"match_ok", "fails", "cands", "gate_ok"} and out["gate_ok"] is True and out["match_ok"] is False
    rows = {r["key"]: r for r in out["table"]["rows"]}
    assert rows["enter.mode.나레"]["judge"] == "out" and rows["enter.mode.나레"]["ours"] == "instant"     # 프리셋 자막 enter 없음 = instant
    assert rows["cut.median"]["judge"] == "failed" and "cut.median" in out["fails"]                     # 완성본 mp4 없음 = 못 잼(통과 아님)
    solo = {r["key"]: r for r in K.match_table([_bench_doc("a")], K.ours_from_remake(tmp_path / "make" / "t1"), None, None)["rows"]}
    assert rows["chunk.chars"]["ours"] == solo["chunk.chars"]["ours"]
    assert len(out["cands"]) == 1 and out["cands"][0]["path"] == "layers[text:caption].enter"
    assert out["cands"][0]["value"] == {"kind": "pop", "ms": K.ENTER_MS} and "enter.mode.나레" in out["cands"][0]["why"]


def test_bm_match_gate_fail_blocks_match_ok(tmp_path):
    _remake_out(tmp_path, verdict="미달", seams=True)
    _preset(tmp_path, enter={"kind": "pop", "ms": 170})
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1",
                               "line_reads": ["channel/s/줄판독/a.json"]}])["pan"]
    assert out["gate_ok"] is False and out["match_ok"] is False and any(x.startswith("관문:") for x in out["fails"])
    assert {r["key"]: r for r in out["table"]["rows"]}["enter.mode.나레"]["judge"] == "in" and out["cands"] == []


def test_ours_from_remake_reads_new_chunk_only_and_narr_speaker(tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    o = K.ours_from_remake(_remake_out(tmp_path))
    assert [l["text"] for l in o["lines"]] == ["첫째 줄이다", "둘째 줄이다", "셋째 줄"] and o["dur"] == 4.0
    assert all(l["speaker"] == "나레" for l in o["lines"])


def test_ours_from_remake_beats_shape_and_missing(tmp_path):
    import pytest
    from tools.calcopy.engine import kal_analyze as K
    out = tmp_path / "w"
    out.mkdir()
    (out / "timeline.json").write_text(json.dumps({"beats": [{"t0": 0.0, "dur": 1.5, "caption_lines": ["가나다"]}, {"t0": 1.5, "dur": 0.5, "caption_lines": []}]}, ensure_ascii=False), encoding="utf-8")
    (out / "remake_log.json").write_text(json.dumps({"kind": "none"}), encoding="utf-8")
    o = K.ours_from_remake(out)
    assert o["lines"] == [{"t0": 0.0, "t1": 1.5, "text": "가나다", "speaker": None, "enter": None, "layer": "채널", "sfx": None}] and o["dur"] == 2.0
    (out / "timeline.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        K.ours_from_remake(out)


def test_gate_from_remake_folder(tmp_path):
    from tools.calcopy.engine import remake
    g = remake.gate_of(_remake_out(tmp_path, verdict="미달", seams=False))
    assert g["ok"] is False and "자막 y" in g["fails"] and any("이음매" in x for x in g["fails"])
    assert remake.passed("원본 없음 — 대조 생략", True) is True and remake.passed("미달", True) is False


# ── 최종 검토 고침(관제 319) — 다시 시도 길이 막다른 길·재제작으로 새지 않게 ──
def _retry(st):
    return flow.step(st, {}, {}, {"retry": True})


def test_env_command_error_is_retry_stop_not_agy_missing():
    st = flow.start_bench("https://www.youtube.com/@abc", [], "n", "c" * 12)
    _go(st)
    r = _go(st, {"bm_env": {"error": "실행기를 띄우지 못했다: spawn ENOENT"}})
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_env"          # 잠깐의 문제 — 스스로 한 번 다시
    r = _go(st, {"bm_env": {"error": "실행기를 띄우지 못했다: spawn ENOENT"}})
    assert r["status"] == "stop" and r["retry_ok"] is True and "agy" not in r["why"]
    r = _retry(st)
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_env"


def test_measure_zero_pass_retry_rereads_not_dead_end():
    lines = _skel()["lines"]
    st = _st("bm_measure_got", videos=[_vid("a"), _vid("b")], keep=["a", "b"], skel={"a": 2, "b": 2}, skel_lines={"a": lines, "b": lines}, reread=1,
             eye={"a": _done_eye(), "b": _done_eye()})        # 눈 판정은 이미 받았다 — 다시 시도는 판독만(그림을 다시 뽑지 않는다)
    r = _go(st, {"fill": {"ok": [], "bad": {"a": ["줄0 speaker 미기입"]}, "dir": "channel/s/줄판독"}})
    assert r["status"] == "stop" and r["retry_ok"] is True
    for _ in range(2):                    # 다시 시도할 때마다 같은 막다른 길이 아니라 판독을 새로
        r = _retry(st)
        assert r["status"] == "execute" and sorted(d["id"] for d in r["do"]) == ["read_a", "read_b"], r
        assert all(d["cmd"] == "agy_read" for d in r["do"]) and st["bm"]["reread"] == 0
        st["phase"] = "bm_measure_got"
        st["bm"]["reread"] = 1
        r = _go(st, {"fill": {"ok": [], "bad": {"a": ["줄0 speaker 미기입"]}, "dir": "channel/s/줄판독"}})
        assert r["status"] == "stop" and r["retry_ok"] is True


def test_match_error_retry_reruns_compare_with_same_trial():
    st = _st("bm_trial_got", videos=[_vid("a")], line_reads=["channel/s/줄판독/a.json"])
    _go(st, rp={"bm_trial": {"work_dir": "trial/t0_abcdefabcdef", "ok": True}})
    r = _trial_eye(st)
    assert [d["cmd"] for d in r["do"]] == ["bm_side", "bm_match"]
    st["_asker_in"] = None                # 받은 입력을 못 둔 경우(ASKER_IN_MAX 넘음)에도 같은 시험 편으로
    r = _go(st, {"side": {"side": "side/a.mp4"}, "pan": {"error": "ValueError: remake 관문 기록 없음"}})
    assert r["status"] == "stop" and r["retry_ok"] is True
    r = _retry(st)
    assert r["status"] == "execute" and [d["cmd"] for d in r["do"]] == ["bm_side", "bm_match"], r      # 시험 편을 다시 만들지 않는다
    assert r["do"][1]["work"] == "trial/t0_abcdefabcdef" and r["do"][0]["ours"] == "trial/t0_abcdefabcdef/final.mp4"
    assert not any(q.get("id") == "bm_trial" for q in r.get("review") or [])


def _multi_frame(enter=None):
    """훅 카드가 있는 채널의 틀(to_frame_multi 꼴 — 실측: 방구 게시글형 frames[hook·body], 자막은 body 에만)."""
    vid = {"kind": "video", "x": 0, "y": 300, "w": 1080, "h": 1200}
    cap = {"kind": "text", "role": "caption", "x": 540, "y": 1300, "w": 980, "align": "center", "lines": 2,
           "font": "CcPretendard-Bold", "size": 60, "line_h": 70, "rgb": [255, 255, 255], "enter": enter}
    return {"canvas": [1080, 1920], "frames": [
        {"id": "hook", "span": [0, 2.0], "layers": [dict(vid), {"kind": "text", "role": "title", "x": 540, "y": 200, "w": 980, "align": "center", "lines": 2,
                                                                "font": "CcPretendard-Bold", "size": 80, "line_h": 90, "rgb": [255, 255, 255], "enter": None, "text": "제목"}]},
        {"id": "body", "span": [2.0, None], "layers": [dict(vid), cap]}]}


def test_bm_match_multi_frame_preset_reads_body_caption_and_offers_fix(tmp_path):
    """실측(방구 3편 remake + 게시글형 틀)에서 드러남: 틀이 여러 장이면 자막 층을 못 찾아 우리 등장을 instant 로 잡고 고칠 후보가 0개였다."""
    from tools.calcopy.engine import kal_analyze as K, preset_save as P
    _remake_out(tmp_path)
    _preset(tmp_path)
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    (p / "frame.json").write_text(json.dumps(_multi_frame(), ensure_ascii=False), encoding="utf-8")
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1",
                               "line_reads": ["channel/s/줄판독/a.json"]}])["pan"]
    assert "error" not in out, out
    assert len(out["cands"]) == 1 and out["cands"][0]["path"] == "frames[body].layers[text:caption].enter", out["cands"]
    assert out["cands"][0]["path"] in P.flat(_multi_frame())                  # bm_fix(preset_save.fix_value) 가 실제로 고칠 수 있는 자리
    (p / "frame.json").write_text(json.dumps(_multi_frame({"kind": "pop", "ms": 170}), ensure_ascii=False), encoding="utf-8")
    o = K.ours_from_remake(tmp_path / "make" / "t1", _multi_frame({"kind": "pop", "ms": 170}))
    assert {l["enter"] for l in o["lines"]} == {"pop"}                         # 본편 틀 자막 등장을 읽는다
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1",
                               "line_reads": ["channel/s/줄판독/a.json"]}])["pan"]
    assert {r["key"]: r for r in out["table"]["rows"]}["enter.mode.나레"]["judge"] == "in" and out["cands"] == []


def test_skel_fill_match_on_real_remake_shape(tmp_path):
    """고정 자료 = 실제 remake 결과(방구 3편 render, 10-16)·실제 뜯기(48PbLQ5az6k)·실제 틀(게시글형, 훅+본편)을 줄인 것.
    이 편은 이음매 검사(10-17) 전이라 remake_log 에 steps.seams 가 없어 {ok:true} 만 덧붙였다(지금 remake 가 남기는 꼴). 큰 영상은 없다 → 컷·소리 칸은 못 잼."""
    import shutil
    from pathlib import Path
    X = Path(__file__).parent / "fixtures" / "bm_real_remake"
    shutil.copytree(X / "make", tmp_path / "make")
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    shutil.copy2(X / "frame.json", p / "frame.json")
    t = tmp_path / "channel" / "s" / "뜯기" / "v1"
    t.mkdir(parents=True)
    shutil.copy2(X / "48PbLQ5az6k_뜯기.json", t / "뜯기.json")
    sk = R.run_do(tmp_path, [{"id": "skel", "cmd": "bm_skel", "slug": "s", "ids": ["v1"]}])["skel"]
    assert not sk["failed"] and len(sk["docs"]["v1"]["lines"]) == 12
    L = sk["docs"]["v1"]["lines"]
    beye = {"cuts": [{"t": L[2]["t0"], "kind": "cut"}, {"t": L[5]["t0"], "kind": "flash"}], "frame0": {"kind": "card", "text": "표지 글"}}
    fills = {"v1": {"lines": [{"i": l["i"], "speaker": "나레", "layer": "채널", "enter": "pop", "sfx": None, "scene": "장면"} for l in L],
                    "doc": {"beats": ["훅", "본론"], "narr_share": 1.0}, "eye": beye}}
    f = R.run_do(tmp_path, [{"id": "fill", "cmd": "bm_fill", "slug": "s", "fills": fills}])["fill"]
    assert f["ok"] == ["v1"] and not f["bad"]
    doc = json.loads((tmp_path / f["dir"] / "v1.json").read_text(encoding="utf-8"))
    assert doc["frame0"]["kind"] == "card" and [l["transition"] for l in doc["lines"]][:6] == ["none", "none", "cut", "none", "none", "flash"]
    oeye = {"cuts": [{"t": 3.0, "kind": "cut"}], "frame0": {"kind": "scene", "text": ""}}
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1", "line_reads": [f"{f['dir']}/v1.json"], "eye": oeye}])["pan"]
    assert "error" not in out, out
    rows = {r["key"]: r for r in out["table"]["rows"]}
    assert {k for k, r in rows.items() if r["judge"] == "failed"} == {"cut.median", "mix.lufs"}   # 영상 없이 못 재는 칸(전환·0초 화면은 눈 판정으로 잰다 — Ruling 17)
    assert rows["thumb.frame0"]["bench"] == "card" and rows["thumb.frame0"]["ours"] == "scene" and rows["thumb.frame0"]["judge"] == "out"
    assert rows["transition.rate"]["ours"] == {"cut": 1.0} and rows["transition.rate"]["judge"] in ("in", "out")
    assert rows["enter.mode.나레"]["ours"] == "instant" and rows["enter.mode.나레"]["judge"] == "out"
    assert [c["path"] for c in out["cands"]] == ["frames[body].layers[text:caption].enter"]
    assert out["gate_ok"] is False and any(x.startswith("관문:") for x in out["fails"]) and out["match_ok"] is False


# ── 전환·0초 첫 화면(Ruling 17) — 시각은 프로그램, 종류는 같은 눈. 넣기 규칙 = kal_analyze.apply_eye 한 곳 ──
def test_apply_eye_puts_cut_on_line_starting_at_it_and_frame0():
    from tools.calcopy.engine import kal_analyze as K
    lines = [{"t0": 0.0, "t1": 1.0}, {"t0": 1.0, "t1": 2.0}, {"t0": 2.0, "t1": 3.0}, {"t0": 5.0, "t1": 6.0}]
    f0 = K.apply_eye(lines, {"cuts": [{"t": 1.0, "kind": "cut"}, {"t": 2.02, "kind": "cut"}, {"t": 2.5, "kind": "흰 번쩍임"}, {"t": 4.2, "kind": "black"}],
                             "frame0": {"kind": "card", "text": " 표지 "}})
    assert [l["transition"] for l in lines] == ["none", "cut", "flash", "black"]       # 경계 컷 = 그 컷에서 시작하는 줄 · 한 줄 여럿 = cut 아닌 것 · 창 밖 = 가까운 줄
    assert f0["text"] == "표지" and K.frame0_kind({"frame0": f0}) == "card"
    assert K.frame0_kind({"frame0": K.apply_eye([], {"cuts": [], "frame0": {"kind": "scene", "text": "무시"}})}) == "scene"
    assert all(K.cut_in_line(c, 1.0, 2.0) == (0.9 <= c < 2.1) for c in (0.89, 0.9, 1.5, 2.09, 2.1))


def test_eye_check_rejects_bad_shapes():
    import pytest
    from tools.calcopy.engine import kal_analyze as K
    ok = {"cuts": [{"t": 1.0, "kind": "zoom blur"}], "frame0": {"kind": "scene", "text": ""}}
    assert K.eye_check(ok, 1) == []
    assert K.eye_check(ok, 2)                                                        # 컷 빠짐
    assert K.eye_check({"cuts": [{"t": 1.0, "kind": "none"}], "frame0": {"kind": "scene"}}, 1)    # 전환 없음은 컷 판정이 아니다
    assert K.eye_check({"cuts": [], "frame0": {"kind": "card", "text": ""}}, 0)       # card 인데 글 없음
    assert K.eye_check({"cuts": [], "frame0": {"kind": "표지"}}, 0) and K.eye_check(None)
    with pytest.raises(ValueError):
        K.apply_eye([{"t0": 0, "t1": 1}], {"cuts": [], "frame0": None})


def test_ours_from_remake_with_eye_same_rule(tmp_path):
    from tools.calcopy.engine import kal_analyze as K
    out = _remake_out(tmp_path)
    o = K.ours_from_remake(out)
    assert o["frame0_kind"] is None and all("transition" not in l for l in o["lines"])        # 눈 판정 없으면 그대로 미측정
    o = K.ours_from_remake(out, eye={"cuts": [{"t": 2.0, "kind": "flash"}], "frame0": {"kind": "scene", "text": ""}})
    assert [l["transition"] for l in o["lines"]] == ["none", "none", "flash"] and o["frame0_kind"] == "scene"
    T = K.match_table([_bench_doc("a")], o, None, None)
    rows = {r["key"]: r for r in T["rows"]}
    assert rows["thumb.frame0"]["judge"] == "failed"          # 벤치 쪽 frame0 이 없으면 여전히 못 잰 칸(원칙 그대로)
    assert rows["transition.rate"]["judge"] == "failed"


def test_eye_frames_command_on_real_video(tmp_path):
    """실제 ffmpeg 로 빨강 1초 → 흰 2프레임 → 파랑 1초 영상을 만들어 그림 뽑기(0초 한 장 + 컷마다 띠)."""
    import subprocess
    from tools.calcopy.engine import kal_analyze as K
    src = tmp_path / "src"
    src.mkdir()
    mp4 = src / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:s=180x320:r=30:d=1", "-f", "lavfi", "-i", "color=white:s=180x320:r=30:d=0.0667",
                    "-f", "lavfi", "-i", "color=blue:s=180x320:r=30:d=1", "-filter_complex", "[0][1][2]concat=n=3:v=1[v]", "-map", "[v]",
                    "-pix_fmt", "yuv420p", str(mp4)], check=True)
    out = R.run_do(tmp_path, [{"id": "e", "cmd": "bm_eye_frames", "videos": [{"id": "v", "mp4": "src/v.mp4"}]}])["e"]
    assert not out["failed"], out
    fr = out["frames"]["v"]
    assert fr["frame0"] == "eye/v/frame0.jpg" and (tmp_path / fr["frame0"]).is_file()
    assert fr["cuts"] and abs(fr["cuts"][0]["t"] - 1.0) < 0.1 and all((tmp_path / c["img"]).is_file() for c in fr["cuts"])
    assert len(fr["cuts"]) <= K.EYE_CUTS_MAX
    bad = R.run_do(tmp_path, [{"id": "e", "cmd": "bm_eye_frames", "videos": [{"id": "x", "mp4": "src/없음.mp4"}]}])["e"]
    assert bad["failed"] and not bad["frames"]


def test_bench_eye_reviews_same_question_as_trial():
    st = _st("bm_read_got", videos=[_vid("a"), _vid("b")], keep=["a", "b"], skel={"a": 2, "b": 2})
    r = _go(st, {"read_a": {"answer": {"voice": "여"}}, "eye_b": {"frames": {"a": _fr(2), "b": _fr(0, "b")}, "failed": []}})
    qs = {q["id"]: q for q in r["review"]}
    assert set(qs) == {"bm_read", "bm_eye_a", "bm_eye_b"} and qs["bm_eye_a"]["model"] == "opus"
    assert qs["bm_eye_a"]["show"] == [{"file": "eye/a/frame0.jpg"}, {"file": "eye/a/cut_00.jpg"}, {"file": "eye/a/cut_01.jpg"}]
    head = FB.EYE_ASK.split("{cuts}")[0]
    assert qs["bm_eye_a"]["ask"].startswith(head) and qs["bm_eye_b"]["ask"].startswith(head)
    t = _st("bm_trial_eye", trial="make/t1/final.mp4")
    q = _go(t, {"eye_t": {"frames": {"trial": _fr(1, "trial")}, "failed": []}})["review"][0]
    assert q["ask"].startswith(head) and q["model"] == "opus"        # 벤치·시험 편 같은 판정 기준 문구(한 곳)
    assert "칼카피" not in head and FB.ASKS["bm_eye"]["model"] == "opus"


def test_bench_eye_frames_error_or_missing_stops_two_lines():
    for m in ({"read_a": {"answer": {"voice": "여"}}, "eye_b": {"error": "RuntimeError: 프레임 뽑기 실패"}},
              {"read_a": {"answer": {"voice": "여"}}, "eye_b": {"frames": {}, "failed": [{"video": "a"}]}},
              {"read_a": {"answer": {"voice": "여"}}}):
        st = _st("bm_read_got", videos=[_vid("a")], keep=["a"], skel={"a": 2})
        r = _go(st, m)
        assert r["status"] == "stop" and r["why"] == "화면 전환을 확인하지 못했어요" and r["fix"] and r["retry_ok"] is True, r


def test_bench_eye_bad_answer_stops_then_asks_eye_only_and_keeps_read_reply():
    st = _st("bm_read_got", videos=[_vid("a")], keep=["a"], skel={"a": 2})
    _go(st, {"read_a": {"answer": {"voice": "여"}}, "eye_b": {"frames": {"a": _fr(2)}, "failed": []}})
    read = {"rules": {"x": 1}, "per_video": {}, "lines": {"a": _eye()}}
    r = _go(st, rp={"bm_read": read, "bm_eye_a": {"frame0": {"kind": "scene", "text": ""}, "cuts": [{"i": 0, "kind": "cut"}]}})   # 컷1 빠짐
    assert r["status"] == "stop" and r["why"] == "화면 전환을 확인하지 못했어요" and r["retry_ok"] is True
    r = _retry(st)
    assert r["status"] == "review" and [q["id"] for q in r["review"]] == ["bm_eye_a"]          # 판독은 다시 묻지 않는다
    r = _go(st, rp={"bm_eye_a": _eye_ans(2, "zoomblur")})
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_fill"
    assert r["do"][0]["fills"]["a"]["eye"]["cuts"] == [{"t": 1.0, "kind": "zoomblur"}, {"t": 2.0, "kind": "zoomblur"}]
    assert st["bm"]["rules"]["rules"] == {"x": 1} and "read_reply" not in st["bm"]


def test_reread_does_not_ask_eye_again():
    st = _st("bm_read_got", videos=[_vid("a")], keep=["a"], skel={"a": 2}, eye={"a": _done_eye()})
    r = _go(st, {"read_a": {"answer": {"voice": "여"}}})
    assert [q["id"] for q in r["review"]] == ["bm_read"]


def test_trial_eye_bad_answer_stops_and_retry_reasks():
    st = _st("bm_trial_got", videos=[_vid("a")], line_reads=["channel/s/줄판독/a.json"])
    _go(st, rp={"bm_trial": {"work_dir": "make/t1", "ok": True}})
    _go(st, {"eye_t": {"frames": {"trial": _fr(1, "trial")}, "failed": []}})
    r = _go(st, rp={"bm_eye_trial": {"frame0": {"kind": "card", "text": ""}, "cuts": [{"i": 0, "kind": "cut"}]}})    # card 인데 글 없음
    assert r["status"] == "stop" and r["why"] == "화면 전환을 확인하지 못했어요" and r["retry_ok"] is True
    r = _retry(st)
    assert r["status"] == "review" and [q["id"] for q in r["review"]] == ["bm_eye_trial"]
    r = _go(st, rp={"bm_eye_trial": _eye_ans(1)})
    assert [d["cmd"] for d in r["do"]] == ["bm_side", "bm_match"]


def test_trial_frames_error_stops():
    st = _st("bm_trial_eye", trial="make/t1/final.mp4")
    r = _go(st, {"eye_t": {"error": "RuntimeError: 프레임 뽑기 실패"}})
    assert r["status"] == "stop" and r["why"] == "화면 전환을 확인하지 못했어요" and r["retry_ok"] is True


def test_new_trial_rejudges_trial_eye_only():
    st = _st("bm_trial_got", videos=[_vid("a")], line_reads=["channel/s/줄판독/a.json"], eye={"a": _done_eye()}, trial_eye=_done_eye(), trial_frames=_fr(1, "trial"))
    r = _go(st, rp={"bm_trial": {"work_dir": "make/t2", "ok": True}})
    assert [d["cmd"] for d in r["do"]] == ["bm_eye_frames"] and "trial_eye" not in st["bm"] and st["bm"]["eye"] == {"a": _done_eye()}


def test_compare_retry_reuses_trial_eye():
    st = _st("bm_compare", trial_dir="make/t1", trial="make/t1/final.mp4", videos=[_vid("a")], trial_eye=_done_eye())
    r = _go(st)
    assert [d["cmd"] for d in r["do"]] == ["bm_side", "bm_match"] and r["do"][1]["eye"] == _done_eye()
    st = _st("bm_compare", trial_dir="make/t1", trial="make/t1/final.mp4", videos=[_vid("a")])
    assert [d["cmd"] for d in _go(st)["do"]] == ["bm_eye_frames"]


def test_bm_fill_bad_eye_is_bad_not_written(tmp_path):
    _tear_file(tmp_path)
    R.run_do(tmp_path, [{"id": "skel", "cmd": "bm_skel", "slug": "s", "ids": ["a"]}])
    good = {"lines": [{"i": i, "speaker": "나레", "layer": "채널", "enter": "instant", "sfx": None, "scene": "제품"} for i in range(2)],
            "doc": {"beats": ["훅"], "narr_share": 1.0}}
    res = R.run_do(tmp_path, [{"id": "fill", "cmd": "bm_fill", "slug": "s", "fills": {"a": {**good, "eye": {"cuts": [], "frame0": {"kind": "x"}}}}}])["fill"]
    assert res["ok"] == [] and "frame0" in res["bad"]["a"][0]
    res = R.run_do(tmp_path, [{"id": "fill", "cmd": "bm_fill", "slug": "s", "fills": {"a": {**good, "eye": {"cuts": [{"t": 1.0, "kind": "black"}], "frame0": {"kind": "scene", "text": ""}}}}}])["fill"]
    doc = json.loads((tmp_path / "channel" / "s" / "줄판독" / "a.json").read_text(encoding="utf-8"))
    assert res["ok"] == ["a"] and [l["transition"] for l in doc["lines"]] == ["none", "black"] and doc["frame0"]["kind"] == "scene"
