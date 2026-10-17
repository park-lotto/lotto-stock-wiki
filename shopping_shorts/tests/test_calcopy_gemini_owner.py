# -*- coding: utf-8 -*-
"""칼카피 공용 뿌리(10-18) — 제미나이 창구 한 곳(서버 대체·묶음 동시·모델 교차), 이름 발음 사전 주인, 단계 시간 장부.
네트워크 없이 돈다(로컬·서버 호출은 가짜로 바꿔 끼운다)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.calcopy.engine import gemini_free as g, gemini_keys as gk, name_dict as ND, stage_log  # noqa: E402


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    monkeypatch.setattr(gk, "QUOTA_FILE", tmp_path / "q.json")
    monkeypatch.setattr(gk, "_pairs", lambda env_file=None: [("K1", "v1"), ("K2", "v2")])
    g.CALLS.clear()
    g._DEAD.clear()
    yield


def test_auto_backend_falls_to_server_only_when_local_quota(monkeypatch, quiet):
    """로컬 풀이 오늘 다 막혔으면(quota) 서버 풀로 같은 프롬프트를 보내고 _via=server 표식. 로컬이 답하면 서버를 안 부른다."""
    monkeypatch.setattr(g, "BACKEND", "auto")
    called = []
    monkeypatch.setattr(g, "_ask_server", lambda parts, prompt, tag="", models=None: (called.append(prompt) or {"ok": 1, "_model": "m", "_via": "server"}, None))
    monkeypatch.setattr(g, "_ask_local", lambda *a, **k: ({"ok": 1, "_model": "gemini-3.5-flash"}, None))
    d, err = g.ask(["x"], "p1", "t")
    assert d["_model"] == "gemini-3.5-flash" and not called
    monkeypatch.setattr(g, "_ask_local", lambda *a, **k: (None, "quota"))
    d, err = g.ask(["x"], "p2", "t")
    assert err is None and d["_via"] == "server" and d["_local_err"] == "quota" and called == ["p2"]
    monkeypatch.setattr(g, "_ask_local", lambda *a, **k: (None, "503"))   # 한도 아닌 실패는 서버로 안 넘긴다(원인을 가리지 않게)
    assert g.ask(["x"], "p3", "t") == (None, "503") and called == ["p2"]


def test_local_backend_never_calls_server(monkeypatch, quiet):
    monkeypatch.setattr(g, "BACKEND", "local")
    monkeypatch.setattr(g, "_ask_server", lambda *a, **k: pytest.fail("서버를 부르면 안 된다"))
    for nm in ("K1", "K2"):
        for m in g.MODELS:
            gk.mark(nm, m, "429")
    t0 = time.time()
    assert g.ask(["x"], "y", "t") == (None, "quota") and time.time() - t0 < 2


def test_server_parts_and_answer_shape(monkeypatch, quiet):
    """서버 대체 경로: 파트 변환(그림 bytes·(bytes,mime)·글) + 모델 순서대로 첫 성공 모델의 답, 전부 실패면 모델별 이유."""
    from tools.calcopy.engine import gemini_server as GS
    sent = {}

    def fake_raw(jobs, models=GS.MODELS, max_tries=8, workers=12):
        sent["jobs"] = jobs; sent["models"] = list(models)
        return {"runs": [[{"model": models[0], "why": "model_404"}, {"model": models[1], "json": [{"label": "a"}], "tries": 1, "sec": 1.0}]], "sec": 1.0}
    monkeypatch.setattr(GS, "ask_raw", fake_raw)
    d, err = g._ask_server([b"\xff\xd8", (b"\x00", "audio/mp3"), "글"], "프롬프트", "t", ("m1", "m2"))
    parts = sent["jobs"][0]["parts"]
    assert [p.get("mime", "text") for p in parts] == ["image/jpeg", "audio/mp3", "text"] and parts[2]["text"] == "글"
    assert err is None and d["_model"] == "m2" and d["_via"] == "server" and d["items"] == [{"label": "a"}]   # 목록 답은 {"items": …} 로(로컬과 같은 꼴)
    monkeypatch.setattr(GS, "ask_raw", lambda *a, **k: {"runs": [[{"model": "m1", "why": "x"}, {"model": "m2", "why": "y"}]], "sec": 1})
    d, err = g._ask_server(["글"], "p", "t", ("m1", "m2"))
    assert d is None and "m1: x" in err and "m2: y" in err


def test_ask_many_keeps_order_and_runs_concurrently(monkeypatch, quiet):
    monkeypatch.setattr(g, "ask", lambda parts, prompt, tag="", models=None: (time.sleep(0.3), ({"p": prompt}, None))[1])
    t0 = time.time()
    res = g.ask_many([(["x"], f"p{i}", f"t{i}") for i in range(8)])
    assert [d["p"] for d, _ in res] == [f"p{i}" for i in range(8)]
    assert time.time() - t0 < 1.5          # 순차면 2.4초


def test_ask_cross_keeps_each_model(monkeypatch, quiet):
    monkeypatch.setattr(g, "ask", lambda parts, prompt, tag="", models=None: ({"m": models[0]}, None) if models[0] == "a" else (None, "429"))
    r = g.ask_cross(["x"], "p", ("a", "b"))
    assert r == [{"model": "a", "json": {"m": "a"}}, {"model": "b", "why": "429"}]


def test_name_dict_owner_is_engine_and_apply_all(monkeypatch, tmp_path):
    from tools.calcopy.hybrid import name_check
    assert name_check.DICT == ND.DICT and ND.DICT.name == "name_dict.json" and ND.DICT.parent.name == "engine"
    monkeypatch.setattr(ND, "DICT", tmp_path / "nd.json")
    ND.save({"names": {"최은경": {"tts": "최, 은경", "voices": {"v1": "방송인, 최, 은경 씨"}}, "장윤정": {"tts": "장윤정"}}})
    assert ND.apply_all("최은경 씨가 장윤정 씨와", None) == "최, 은경 씨가 장윤정 씨와"
    assert ND.apply_all("최은경 씨가", "v1") == "방송인, 최, 은경 씨 씨가"
    assert ND.apply_all("박세리 씨가 산 거예요", "v1") == "박세리 씨가 산 거예요"      # 사전에 없으면 그대로(결과 동일)
    assert ND.names_in("최은경·장윤정") == ["최은경", "장윤정"] and ND.apply_all("", "v1") == ""


def test_preset_make_tts_applies_name_dict_without_changing_other_text(monkeypatch, tmp_path):
    """preset_make.tts 가 덩어리마다 사전을 적용 — 사전 이름이 없는 작품은 합성 글이 전과 완전히 같다(캐시 키도 같다)."""
    from tools.calcopy.engine import preset_make as PM
    monkeypatch.setattr(ND, "DICT", tmp_path / "nd.json")
    ND.save({"names": {"최은경": {"tts": "최, 은경"}}})
    got = []

    def synth(text, out):
        got.append(text); Path(out).write_bytes(b"ID3")
    monkeypatch.setattr(PM, "run", lambda cmd: Path(cmd[-1]).write_bytes(b"RIFF"))
    w = {"voice": "v", "lines": [{"tts": "오늘은 좋은 날."}, {"tts": "최은경 씨가 산 거예요."}]}
    log = {}
    PM.tts(w, {"tts_split": None}, tmp_path / "c", None, True, log, synth=synth)
    assert got == ["오늘은 좋은 날.", "최, 은경 씨가 산 거예요."] and log["tts_name_dict"] == {"최은경": "최, 은경"}
    got.clear(); log = {}
    PM.tts({"voice": "v", "lines": [{"tts": "박세리 씨가 산 거예요."}]}, {"tts_split": None}, tmp_path / "c2", None, True, log, synth=synth)
    assert got == ["박세리 씨가 산 거예요."] and "tts_name_dict" not in log


def test_stage_log_owner_shared_by_hybrid(tmp_path):
    from tools.calcopy.hybrid import common
    assert common.Timer is stage_log.Timer and common.timed is stage_log.timed
    tm = stage_log.Timer(tmp_path / "stage_log.json")
    with stage_log.timed(tm, "a"):
        pass
    with pytest.raises(ValueError):
        with stage_log.timed(tm, "b"):
            raise ValueError("x")
    rows = stage_log.Timer(tmp_path / "stage_log.json").cur["stages"]
    assert [r["stage"] for r in rows] == ["a", "b"] and rows[1]["note"].startswith("실패: x")
    agg = stage_log.collect([tmp_path])
    assert agg["files"] == 1 and set(agg["stages"]) == {"a", "b"}


def test_analyze_batched_uses_ask_many_for_real_gate_only(monkeypatch):
    from tools.calcopy.engine import analyze
    seen = []
    monkeypatch.setattr(g, "ask_many", lambda jobs, workers=None: (seen.append(len(jobs)) or [({"items": [{"label": lab} for lab in j[0][0::2]]}, None) for j in jobs]))
    items = [(f"컷 {i}", b"j") for i in range(25)]
    got, errs = analyze._batched(g.ask, items, "p", "t")
    assert seen == [3] and len(got) == 25 and not errs                        # 묶음 3개를 한 번에 ask_many 로
    fake = lambda part, prompt, tag: ({"items": [{"label": part[0]}]}, None)  # noqa: E731 — 시험 주입은 순차 그대로
    got, errs = analyze._batched(fake, items, "p", "t")
    assert seen == [3] and len(got) == 3
