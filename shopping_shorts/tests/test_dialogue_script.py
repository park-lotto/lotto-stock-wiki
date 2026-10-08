# -*- coding: utf-8 -*-
import pytest

from shopping_shorts import dialogue_script as ds

SRC = ["이제 충전 케이블 보호기 이걸로 끝났음",
       "밋밋한 케이블 쓰던 사람들 사이에서 난리라는데",
       "이건 바로 강아지 케이블 커버.",
       "툭하면 꺾여서 단선되던 단자를 파란 강아지가 꽉 물어 지켜 버림"]


def _good():
    return {"lines": [
        {"speaker": "나레이션", "text": "이제 충전 케이블 보호기 이걸로 끝났음.", "tag": "", "src": [0]},
        {"speaker": "나레이션", "text": "밋밋한 케이블 쓰던 사람들 사이에서 난리라는데, 이건 바로 강아지 케이블 커버.", "tag": "", "src": [1, 2]},
        {"speaker": "동생", "text": "근데 단자 맨날 꺾이잖아?", "tag": "[Doubtful]", "src": [3]},
        {"speaker": "언니", "text": "파란 강아지가 꽉 물고 있어서 지켜 줘.", "tag": "excited", "src": [3]},
    ]}


def test_convert_ok_and_tag_normalized():
    out = ds.convert(SRC, "narr_then_talk", call=lambda p, s: _good())
    assert [o["speaker"] for o in out] == ["나레이션", "나레이션", "동생", "언니"]
    assert out[2]["tag"] == "doubtful"          # 대괄호·대문자 정리
    assert ds.script_text(out).count("\n") == 3
    assert "[" not in ds.script_text(out)


def test_new_number_rejected():
    bad = _good(); bad["lines"][3]["text"] = "2만 원대인데 꽉 물고 있어."
    with pytest.raises(ValueError, match="숫자"):
        ds.convert(SRC, "narr_then_talk", call=lambda p, s: bad)


def test_dropped_line_rejected():
    bad = _good(); bad["lines"][3]["src"] = [2]; bad["lines"][2]["src"] = [2]
    with pytest.raises(ValueError, match="빠짐"):
        ds.convert(SRC, "narr_then_talk", call=lambda p, s: bad)


def test_wrong_speaker_and_bracket_rejected():
    bad = _good(); bad["lines"][2]["speaker"] = "아빠"; bad["lines"][3]["text"] = "[laughs] 지켜 줘"
    errs = ds.check(SRC, [{**l, "tag": ""} for l in bad["lines"]], "narr_then_talk")
    assert any("틀 밖" in e for e in errs) and any("대괄호" in e for e in errs)


def test_remap_and_meta():
    out = ds.convert(SRC, "narr_then_talk", call=lambda p, s: _good())
    srcs = ["s0", "s1", "s2", "s3"]
    assert ds.remap_beat_sources(srcs, out) == ["s0", "s1", "s3", "s3"]
    m = ds.meta("narr_then_talk", out, {"언니": "kr-hanna-natural", "모르는": "x"})
    assert m["cast"]["언니"] == "kr-hanna-natural" and "모르는" not in m["cast"]
    assert len(m["lines"]) == len(out) and "text" not in m["lines"][0]


def test_every_form_has_cast_for_each_role():
    for k, f in ds.FORMS.items():
        assert set(f["cast"]) == set(f["roles"]), k


def test_cut_and_punct_rejected():
    out = [{"speaker": "나레이션", "text": "이제 끝났음", "tag": "", "src": [0, 1, 2]},
           {"speaker": "동생", "text": "볼 때마다 답답했던 그 스트레스를", "tag": "", "src": [3]},
           {"speaker": "언니", "text": "지켜 줘.", "tag": "", "src": [3]}]
    errs = ds.check(SRC, out, "narr_then_talk")
    assert any("조사로 끊김" in e for e in errs) and any("문장 부호" in e for e in errs)


# ── API: 스위치 · 새 작업 만들기 ─────────────────────────────────────────────
import importlib
import time

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import keycrypt
from shopping_shorts.store import Store


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", "x" * 44)
    importlib.reload(keycrypt)
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    st = Store(db)
    st.create_mix_job("J1", ["https://x/1"], 20, "free", given_script="\n".join(SRC),
                      script_structure={"beat_sources": ["s0", "s1", "s2", "s3"]}, customer_id=0)
    st.update_mix_job("J1", voice={"voice_id": "v", "speed": 1.25})
    wid = st.upsert_produce_work(None, {"script": "\n".join(SRC)}, job_id="J1", step=3, customer_id=0)
    monkeypatch.setattr(ds.script_generate, "_call_json", lambda p, s: _good())
    c = TestClient(appmod.app, cookies={"dash_auth": appmod._sign_session(0, int(time.time()) + 3600)})
    return c, st, wid


def test_api_off_by_default(api):
    c, st, wid = api
    assert c.post("/api/produce/dialogue/convert", json={"script": "\n".join(SRC), "form": "narr_then_talk"}).status_code == 403
    assert c.post(f"/api/produce/dialogue/from_work/{wid}", json={"form": "narr_then_talk"}).status_code == 403


def test_api_from_work_makes_new_job(api):
    c, st, wid = api
    st.set_setting("dialogue_enabled", "admin")
    r = c.post(f"/api/produce/dialogue/from_work/{wid}", json={"form": "narr_then_talk"})
    assert r.status_code == 200, r.text
    j = st.get_mix_job(r.json()["job_id"])
    assert j["given_script"].count("\n") == 3 and "[" not in j["given_script"]
    ss = j["script_structure"]
    assert ss["beat_sources"] == ["s0", "s1", "s3", "s3"]           # 줄 수에 맞춰 재배치
    assert [l["speaker"] for l in ss["dialogue"]["lines"]] == ["나레이션", "나레이션", "동생", "언니"]
    assert set(ss["dialogue"]["voices"]) == {"나레이션", "동생", "언니"}
    assert j["voice"]["speed"] == 1.25
    assert ds.of_job(j) is not None
    assert st.get_mix_job("J1")["given_script"] == "\n".join(SRC)   # 원본은 그대로
    w2 = st.get_produce_work(r.json()["work_id"], 0)
    assert w2["job_id"] == j["job_id"] and w2["title"].startswith("[대화형")


def test_api_forms_and_preview_by_work(api):
    c, st, wid = api
    st.set_setting("dialogue_enabled", "admin")
    f = c.get("/api/produce/dialogue/forms").json()
    assert [x["id"] for x in f["forms"]] == list(ds.FORMS) and all(x["desc"] for x in f["forms"])
    r = c.post("/api/produce/dialogue/convert", json={"work_id": wid, "form": "narr_then_talk"}).json()
    assert r["ok"] and r["source"] == SRC and len(r["lines"]) == 4
    me = c.get("/api/me").json()
    assert me["dialogue"] is True


def test_api_make_uses_previewed_lines_as_is(api, monkeypatch):
    c, st, wid = api
    st.set_setting("dialogue_enabled", "admin")
    lines = ds.convert(SRC, "narr_then_talk", call=lambda p, s: _good())
    lines[3]["text"] = "파란 강아지가 꽉 물어 줘."                 # 사람이 본 그대로 — 다시 변환하지 않는다
    monkeypatch.setattr(ds.script_generate, "_call_json", lambda p, s: (_ for _ in ()).throw(AssertionError("재변환 금지")))
    r = c.post(f"/api/produce/dialogue/from_work/{wid}", json={"form": "narr_then_talk", "lines": lines,
                                                              "cast": {"언니": "kr-hanna-natural"}})
    assert r.status_code == 200, r.text
    j = st.get_mix_job(r.json()["job_id"])
    assert j["given_script"].split("\n")[3] == "파란 강아지가 꽉 물어 줘."
    assert j["script_structure"]["dialogue"]["cast"]["언니"] == "kr-hanna-natural"
    bad = [dict(l) for l in lines]; bad[3]["text"] = "2만 원인데 꽉 물어 줘."
    r2 = c.post(f"/api/produce/dialogue/from_work/{wid}", json={"form": "narr_then_talk", "lines": bad})
    assert r2.status_code == 422 and "숫자" in r2.json()["error"]


# ── 2단계(대본 생성 전 틀 고르기) ─────────────────────────────────────────
def test_apply_to_lines_converts_and_keeps_sources():
    lines = [{"text": t, "role": r, "group": g} for t, r, g in zip(SRC, ["hook", "problem", "reveal", "feature"], [0, 0, 1, 2])]
    bs = [{"seg": "s0"}, {"seg": "s1"}, {"seg": "s2"}, {"seg": "s3"}]
    nl, nbs, m, err = ds.apply_to_lines(lines, bs, "narr_then_talk", call=lambda p, s: _good())
    assert err == "" and [l["text"] for l in nl][2] == "근데 단자 맨날 꺾이잖아?"
    assert nbs == [{"seg": "s0"}, {"seg": "s1"}, {"seg": "s3"}, {"seg": "s3"}]
    assert nl[2]["group"] == 2 and m["form"] == "narr_then_talk" and len(m["lines"]) == 4


def test_apply_to_lines_failure_keeps_ssul():
    lines = [{"text": t} for t in SRC]
    nl, nbs, m, err = ds.apply_to_lines(lines, ["a"] * 4, "narr_then_talk", call=lambda p, s: {})
    assert nl is lines and m is None and "실패" in err


def _mix_client(monkeypatch, tmp_path):
    db = tmp_path / "m.db"
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "run_mix_job", lambda *a, **k: None)
    return TestClient(appmod.app), Store(db)


_DLG = {"form": "narr_then_talk", "lines": [{"speaker": "나레이션", "tag": "", "src": [0]}, {"speaker": "나레이션", "tag": "", "src": [1, 2]},
                                            {"speaker": "동생", "tag": "doubtful", "src": [3]}, {"speaker": "언니", "tag": "", "src": [3]}]}
_SCRIPT = "이제 끝났음.\n이건 바로 커버.\n근데 꺾이잖아?\n꽉 물어 줘."


def test_mix_start_attaches_voices_when_on(monkeypatch, tmp_path):
    c, st = _mix_client(monkeypatch, tmp_path)
    st.set_setting("dialogue_enabled", "1")
    r = c.post("/api/produce/mix/start", json={"script": _SCRIPT, "urls": ["https://www.instagram.com/reel/AAA111/"],
                                               "script_structure": {"dialogue": _DLG}})
    assert r.status_code == 200, r.text
    d = st.get_mix_job(r.json()["job_id"])["script_structure"]["dialogue"]
    assert set(d["voices"]) == {"나레이션", "동생", "언니"} and ds.of_structure({"dialogue": d}) is not None


def test_mix_start_drops_dialogue_when_off_and_blocks_line_mismatch(monkeypatch, tmp_path):
    c, st = _mix_client(monkeypatch, tmp_path)
    r = c.post("/api/produce/mix/start", json={"script": _SCRIPT, "urls": ["https://www.instagram.com/reel/AAA111/"],
                                               "script_structure": {"dialogue": _DLG}})
    assert r.status_code == 200 and "dialogue" not in (st.get_mix_job(r.json()["job_id"])["script_structure"] or {})
    st.set_setting("dialogue_enabled", "1")
    r2 = c.post("/api/produce/mix/start", json={"script": _SCRIPT + "\n한 줄 더.", "urls": ["https://www.instagram.com/reel/BBB222/"],
                                                "script_structure": {"dialogue": _DLG}})
    assert r2.status_code == 422 and "줄 수" in r2.json()["error"]
