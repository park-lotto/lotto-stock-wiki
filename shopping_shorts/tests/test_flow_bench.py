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
    st = _st("bm_read_got", videos=[_vid("a")])
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
    assert [d["cmd"] for d in r["do"]] == ["bm_fix", "render_trial"] and r["do"][0]["fix"]["path"] == "p1"
    assert st["pan_n"] == 1 and st["bm"]["side"] == "side/a.mp4" and len(seen["fixes"]) == 2


def test_panbokki_low_confidence_remeasures_deeper(monkeypatch):
    monkeypatch.setattr(jev_gate, "decide", lambda *a, **k: {"pick": 0, "conf": 0.5, "fixroot": [0.5, 0.5], "ok": False})
    st = _st("bm_panbokki", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, {"pan": {"match_ok": False, "fails": ["x"], "cands": [{"path": "p1"}, {"path": "p2"}]}})
    assert r["do"][1]["cmd"] == "bm_match" and r["do"][1]["deeper"] is True and st["pan_n"] == 1


def test_match_ok_goes_to_confirm_review():
    st = _st("bm_panbokki", rules={"rules": {}})
    r = _go(st, {"pan": {"match_ok": True}, "side": {"side": "side/a.mp4"}})
    assert r["status"] == "review" and r["review"][0]["id"] == "bm_confirm" and r["review"][0]["show"] == [{"file": "side/a.mp4"}]


def test_confirm_fail_goes_back_then_stops():
    st = _st("bm_confirm_got", trial="t.mp4", videos=[_vid("a")])
    r = _go(st, rp={"bm_confirm": {"ok": False, "wrong": ["caption.y"]}})
    assert r["status"] == "execute" and r["do"][1]["deeper"] is True and st["pan_n"] == 1
    st["bm"]["confirm_n"] = FB.CONFIRM_MAX
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
    assert [d["id"] for d in r["do"]] == ["read_a", "read_b"] and r["do"][0]["video"] == "src/a_360.mp4"


def test_fix_command_registered_and_missing_slot_errors(tmp_path):
    assert "bm_fix" in R.CMDS and "bm_fix" in R.CMD_LABEL
    p = tmp_path / "channel" / "s" / "preset" / "틀"
    p.mkdir(parents=True)
    (p / "frame.json").write_text(json.dumps({"caption": {"y": 1}}), encoding="utf-8")
    (p / "manifest.json").write_text("{}", encoding="utf-8")
    out = R.run_do(tmp_path, [{"id": "f", "cmd": "bm_fix", "slug": "s", "style": "틀", "fix": {"path": "nope", "value": 1, "why": "t"}}])
    assert "error" in out["f"]       # 없는 자리는 조용히 넘기지 않고 오류
