# -*- coding: utf-8 -*-
"""채널 벤치마킹 2판 서버 창구(관제 319 과제 7) — bench_start 반 관문 + 지시서 경보(state.alarm) → claude_alerts.
반 판단 주인 = claude_portal.member_tier. 경보 꼴 = flow_bench.ALARM_KEYS."""
import types
from pathlib import Path

from shopping_shorts import claude_flow as cf
from shopping_shorts.tests.test_claude_portal import _h, _key, env  # noqa: F401 — pytest 픽스처

ENGINE = str(Path(__file__).resolve().parents[2])
BODY = {"step": "bench_start", "source": {"url": "https://www.youtube.com/@abc"}, "name": "n"}


def _member(env, monkeypatch, plan):
    monkeypatch.setenv("CLAUDE_FLOW_ENGINE", ENGINE)
    env["store"].save_program_member(0, "", "", plan, "", "")
    key = _key(env)
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(key)).status_code == 200
    return c, key


def _alerts(env):
    with cf.CP._tx(env["store"]) as con:
        return cf.CP._rows(con, "SELECT * FROM claude_alerts WHERE rule='jev_down'")


def test_bench_start_기본반_거절(env, monkeypatch):
    c, key = _member(env, monkeypatch, "기본반")
    r = c.post("/api/claude/step", headers=_h(key), json=BODY)
    assert r.status_code == 403 and r.json()["code"] == "tier_locked"


def test_bench_start_고급반_환경점검_do(env, monkeypatch):
    c, key = _member(env, monkeypatch, "고급반")
    r = c.post("/api/claude/step", headers=_h(key), json=BODY)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["do"][0]["cmd"] == "bm_env" and b["next_payload"] and "TYPESAFE" not in r.text


def test_bench_start_주소_없으면_거절(env, monkeypatch):
    c, key = _member(env, monkeypatch, "고급반")
    r = c.post("/api/claude/step", headers=_h(key), json={"step": "bench_start", "source": {}, "name": "n"})
    assert r.status_code == 400


def test_흐름_경보가_관리자_경보로_한_번만(env, monkeypatch):
    monkeypatch.setenv("CLAUDE_FLOW_ENGINE", ENGINE)
    calls = []

    def start(url, version, sid):
        return {"sid": sid, "ref": url, "phase": "a", "n": 0}

    def step(state, measure, replies, user):
        state["n"] += 1
        if state["n"] == 1:      # 첫 걸음에만 지시서가 경보를 남긴다
            state["alarm"] = {"kind": "jev_down", "why": "Jev 꺼짐", "at": "bm_panbokki"}
        calls.append(dict(state))
        return {"status": "execute", "message": "m", "state": state}
    monkeypatch.setattr(cf, "_flow", lambda: types.SimpleNamespace(start=start, step=step))
    pdir = [p for p in cf.CP.presets(env["store"]) if p["id"] == env["preset"]][0]["dir"]
    import json
    (pdir / "line.json").write_text(json.dumps({"line": "hybrid", "version": "키치잇판"}), encoding="utf-8")
    key = _key(env)
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(key)).status_code == 200
    r = c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"],
                                                           "source": {"url": "https://www.youtube.com/shorts/cNo91ddBwB8"}})
    assert r.status_code == 200, r.text
    a = _alerts(env)
    assert len(a) == 1 and "Jev 꺼짐" in a[0]["detail"] and "TYPESAFE" not in a[0]["detail"]
    r2 = c.post("/api/claude/step", headers=_h(key), json={"step": "go", "payload": r.json()["next_payload"]})
    assert r2.status_code == 200 and len(calls) == 2
    assert len(_alerts(env)) == 1      # 다음 걸음에 중복 행 없음
