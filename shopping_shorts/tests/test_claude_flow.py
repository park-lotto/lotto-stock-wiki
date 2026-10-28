# -*- coding: utf-8 -*-
"""볼케이노형 제작 지시 창구(관제 234, 2026-10-21) — POST /api/claude/step 의 관문·서명·옛 상태 거절.
지시서 내용(13단계)은 엔진 트랙 hybrid/flow.py 시험이 본다 — 여기는 가짜 지시서로 서버 껍데기만 못 박는다.
1. 하이브리드 프리셋이 아니면 start 거절 · 유튜브 주소 아니면 거절
2. next_payload 한 글자 바꾸면 400 · 옛 payload 다시 보내면 stale
3. approve 가 지시서에 user.approve 로 간다 · 응답에 state 본문 없음(서명 payload 로만)
"""
import json
import types

from shopping_shorts import claude_flow as cf
from shopping_shorts.tests.test_claude_portal import _h, _key, _w, env  # noqa: F401 — pytest 픽스처


def _fake_flow():
    calls = []

    def start(url, version, sid):
        return {"sid": sid, "ref": url, "version": version, "phase": "a", "n": 0}

    def step(state, measure, replies, user):
        calls.append({"phase": state["phase"], "measure": measure, "user": user})
        state["n"] += 1
        if user.get("approve"):
            return {"status": "done", "message": "완성", "video": "x.mp4", "state": state}
        return {"status": "execute", "message": f"단계 {state['n']}", "do": [{"id": "env", "cmd": "env"}], "state": state}
    return types.SimpleNamespace(start=start, step=step), calls


def _setup(env, monkeypatch, hybrid=True):
    pdir = [p for p in cf.CP.presets(env["store"]) if p["id"] == env["preset"]][0]["dir"]
    if hybrid:
        _w(pdir / "line.json", {"line": "hybrid", "version": "키치잇판"})
    fake, calls = _fake_flow()
    monkeypatch.setattr(cf, "_flow", lambda: fake)
    key = _key(env)
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(key)).status_code == 200      # 기기 등록
    return c, key, calls


URL = "https://www.youtube.com/shorts/cNo91ddBwB8"


def test_하이브리드_아니면_start_거절(env, monkeypatch):
    c, key, _ = _setup(env, monkeypatch, hybrid=False)
    r = c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"], "source": {"url": URL}})
    assert r.status_code == 400 and "단계 진행" in r.json()["msg"]


def test_주소_모양_거절(env, monkeypatch):
    c, key, _ = _setup(env, monkeypatch)
    r = c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"], "source": {"url": "https://evil.example/x"}})
    assert r.status_code == 400


def test_payload_위변조와_옛상태_거절(env, monkeypatch):
    c, key, calls = _setup(env, monkeypatch)
    r = c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"], "source": {"url": URL}})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["status"] == "execute" and "state" not in b and b["sid"] and b["next_payload"].startswith("v1.1.")
    p1 = b["next_payload"]
    # 한 글자 바꾸면 400
    bad = p1[:-1] + ("0" if p1[-1] != "0" else "1")
    assert c.post("/api/claude/step", headers=_h(key), json={"step": "go", "payload": bad}).status_code == 400
    # 정상 이어 가기 → seq 2
    r2 = c.post("/api/claude/step", headers=_h(key), json={"step": "go", "payload": p1, "measure": {"env": {"ok": 1}}})
    assert r2.status_code == 200 and r2.json()["next_payload"].startswith("v1.2.")
    assert calls[-1]["measure"] == {"env": {"ok": 1}}
    # 옛 payload(p1)를 다시 → stale
    r3 = c.post("/api/claude/step", headers=_h(key), json={"step": "go", "payload": p1})
    assert r3.status_code != 200 and r3.json()["code"] == "stale"
    # 사인 → 지시서에 approve
    r4 = c.post("/api/claude/step", headers=_h(key), json={"step": "approve", "payload": r2.json()["next_payload"]})
    assert r4.json()["status"] == "done" and calls[-1]["user"]["approve"] is True
    with cf.CP._tx(env["store"]) as con:
        row = cf.CP._row(con, "SELECT * FROM claude_flow_runs")
    assert row["seq"] == 3 and row["status"] == "done" and "ref" not in (row["summary_json"] or "")   # 요약만(주소·본문 없음)


def test_다른_고객_payload_거절(env, monkeypatch):
    c, key, _ = _setup(env, monkeypatch)
    p1 = c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"], "source": {"url": URL}}).json()["next_payload"]
    key2 = cf.CP.issue_license(5, env["store"])["key"]
    assert c.get("/api/claude/license", headers=_h(key2, fp="d" * 64)).status_code == 200
    r = c.post("/api/claude/step", headers=_h(key2, fp="d" * 64), json={"step": "go", "payload": p1})
    assert r.status_code == 400 and "찾을 수 없습니다" in r.json()["msg"]
