# -*- coding: utf-8 -*-
"""소재창고 워커 시험 (관제 097, 2026-10-16) — 설계 docs/superpowers/specs/2026-10-16-소재창고-보드-워커-design.md §3·§4.

서버 API 는 다른 담당이 만드는 중이라, 규격 §3 대로 도는 **가짜 API**(FastAPI + TestClient) 위에서 워커를 돌린다.
가짜 API 는 판단(상태 전이·잠금 11분·검수 자리·비용 상한)을 규격 그대로 흉내 낸다 — 정식 API 가 생기면
`_client()` 만 진짜 앱으로 바꿔 같은 시험을 돌린다.

재는 것: 한 바퀴(find→…→plan_review, 사람 통과 → produce→check→final_review) · 잠금 충돌 · heartbeat 끊김 뒤 다른 워커 인수 ·
검수 자리 넘기기 거절 · 엔진 없음 = 이유와 함께 멈춤 · 단계 예외 = advance(error) · 비용 상한 = 그 단계 건너뛰고 다른 행 · heartbeat 스레드.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from tools.calcopy.engine import worker as W
from tools.calcopy.engine import worker_steps as WS

KEY = "test-key"
STATES = ["found", "benched", "scored", "assigned", "scripted", "sourced", "plan_review", "producing", "produced", "final_review",
          "passed", "rejected"]
# 규격 §1 — 단계: 받는 상태 → 끝난 상태
STEP_FROM = {"bench": "found", "score": "benched", "assign": "scored", "script": "assigned", "source": "scripted",
             "plan": "sourced", "produce": "producing", "check": "produced"}
STEP_TO = {"bench": "benched", "score": "scored", "assign": "assigned", "script": "scripted", "source": "sourced",
           "plan": "plan_review", "produce": "produced", "check": "final_review"}
REVIEW = ("plan_review", "final_review")
LEASE = 11 * 60


class FakeApi:
    """규격 §3-1 을 흉내 내는 가짜 서버(메모리). clock 을 밀어 잠금 만료를 시험한다."""

    def __init__(self, min_found: int = 0, caps: dict | None = None):
        self.now = 1_000_000.0
        self.rows: dict[str, dict] = {}
        self.heartbeats: list[dict] = []
        self.uploads: list[tuple] = []
        self.min_found = min_found
        self.caps = caps or {}                         # {"produce": "tts"} → 그 단계는 429 budget
        self.buggy_hand_review = False                 # True면 검수 대기 행을 실수로 내준다(서버 버그 흉내)
        self.app = self._build()

    def add(self, topic, state="found", **kw):
        tid = f"t_{len(self.rows) + 1:04d}"
        self.rows[tid] = {"id": tid, "topic": topic, "state": state, "category": kw.get("category", "식품"),
                          "track": kw.get("track", "bench"), "source": {}, "worker": None, "lease_until": 0, "error": None,
                          "artifacts": {}, "cost": {}, "history": [], **{k: v for k, v in kw.items() if k not in ("category", "track")}}
        return tid

    def _build(self):
        app, f = FastAPI(), self

        def auth(req: Request):
            return req.headers.get("X-Calcopy-Key") == KEY

        def deny():
            return JSONResponse({"error": "auth", "detail": "키 불일치"}, status_code=403)

        @app.post("/api/calcopy_worker/claim")
        def claim(req: Request, body: dict):
            if not auth(req):
                return deny()
            ex = set(body.get("exclude_steps") or [])
            for tid, r in f.rows.items():
                if r["category"] != body["category"] or r["state"] in ("passed", "rejected") or r.get("error"):
                    continue
                if r["worker"] and r["lease_until"] > f.now:
                    continue                                   # 잠금 중
                step = next((s for s, st in STEP_FROM.items() if st == r["state"]), None)
                if f.buggy_hand_review and r["state"] in REVIEW:
                    step = "plan"
                if step is None or step in ex:
                    continue
                if step in f.caps:
                    return JSONResponse({"error": "budget", "step": step, "which": f.caps[step], "detail": f"{f.caps[step]} 상한"},
                                        status_code=429)
                r["worker"], r["lease_until"] = body["worker"], f.now + LEASE
                return {"topic": dict(r), "step": step, "lease_until": r["lease_until"]}
            n_found = sum(1 for r in f.rows.values() if r["state"] == "found" and r["category"] == body["category"])
            if n_found < f.min_found and "find" not in ex:
                return {"topic": None, "step": "find"}
            return {"topic": None, "step": None, "reason": "할 일 없음"}

        @app.post("/api/calcopy_worker/topics")
        def topics(req: Request, body: dict):
            if not auth(req):
                return deny()
            ids = [f.add(x["topic"], "found", category=body["category"], track=body["track"], source=x.get("source") or {})
                   for x in body["rows"]]
            return {"ids": ids}

        @app.post("/api/calcopy_worker/topics/{tid}/advance")
        def advance(tid: str, req: Request, body: dict):
            if not auth(req):
                return deny()
            r = f.rows.get(tid)
            if not r:
                return JSONResponse({"error": "not_found"}, status_code=404)
            if r["worker"] != body["worker"] or r["lease_until"] <= f.now:
                return JSONResponse({"error": "lock", "detail": f"잠금 주인 {r['worker']}"}, status_code=409)
            if r["state"] in REVIEW:
                return JSONResponse({"error": "review_gate", "detail": f"{r['state']} 는 사람 자리"}, status_code=409)
            if STEP_FROM.get(body["step"]) != r["state"]:
                return JSONResponse({"error": "bad_step", "detail": f"{body['step']} ≠ {r['state']}"}, status_code=409)
            r["artifacts"].update(body.get("artifacts") or {})
            for k, v in (body.get("cost") or {}).items():
                r["cost"][k] = r["cost"].get(k, 0) + v
            r.update(body.get("data") or {})
            if body.get("error"):
                r["error"] = body["error"]
                r["history"].append({"from": r["state"], "to": r["state"], "by": body["worker"], "note": body["error"]})
            else:
                r["history"].append({"from": r["state"], "to": STEP_TO[body["step"]], "by": body["worker"]})
                r["state"] = STEP_TO[body["step"]]
            r["worker"], r["lease_until"] = None, 0
            return {"ok": True, "topic": dict(r)}

        @app.post("/api/calcopy_worker/topics/{tid}/file")
        async def upload(tid: str, req: Request, name: str = Form(...), file: UploadFile = File(...)):
            if not auth(req):
                return deny()
            data = await file.read()
            f.uploads.append((tid, name, len(data)))
            return {"url": f"/api/admin/calcopy/topics/{tid}/file/{name}"}

        @app.post("/api/calcopy_worker/heartbeat")
        def heartbeat(req: Request, body: dict):
            if not auth(req):
                return deny()
            f.heartbeats.append({**body, "at": f.now})
            r = f.rows.get(body.get("topic_id") or "")
            if r and r["worker"] == body["worker"]:
                r["lease_until"] = f.now + LEASE
            return {"ok": True}

        return app

    def review(self, tid, decision, back_to=None):
        """보드 결정 줄(사람) — 통과면 plan_review→producing, final_review→passed."""
        r = self.rows[tid]
        assert r["state"] in REVIEW
        if decision == "pass":
            r["state"] = "producing" if r["state"] == "plan_review" else "passed"
        else:
            r["state"] = back_to or "rejected"


class MockSteps:
    """가짜 단계 — 엔진을 부르지 않고 산출물 파일만 만든다(무료 제미나이 쿼터 바닥·유료 금지)."""

    def __init__(self, tmp: Path, fail: dict | None = None, slow: float = 0):
        self.tmp, self.fail, self.slow, self.calls = tmp, fail or {}, slow, []

    def run_step(self, step, topic, ctx):
        self.calls.append((step, (topic or {}).get("id")))
        if self.slow:
            time.sleep(self.slow)
        if step in self.fail:
            raise self.fail[step]
        if step == "find":
            return {"rows": [{"topic": "신라면 구미 공장 비하인드", "source": {"kind": "youtube", "query": "신라면 공장"}},
                             {"topic": "코스트코 핫도그 가격 비밀", "source": {"kind": "youtube", "query": "코스트코 핫도그"}}]}
        p = self.tmp / f"{topic['id']}_{step}.md"
        p.write_text(f"# {step}\n", encoding="utf-8")
        data = {"scores": {"total": 41.5}} if step == "score" else {}
        return {"artifacts": {f"{step}.md": str(p)}, "cost": {"llm_calls": 1 if step in ("bench", "score", "script") else 0}, "data": data}


def _client(fake: FakeApi):
    return TestClient(fake.app)


def _worker(fake, tmp, steps=None, name="pc-식품-bench", **kw):
    api = W.Api("", KEY, session=_client(fake))
    return W.Worker(api, "식품", "bench", "yummyknow", name=name, out_root=tmp / "out", steps=steps or MockSteps(tmp),
                    log=lambda *_: None, **kw)


# ── 한 바퀴 ────────────────────────────────────────────────────────────────
def test_한바퀴_find부터_final_review까지_검수는_사람(tmp_path):
    fake = FakeApi(min_found=1)
    w = _worker(fake, tmp_path)
    r = w.tick()
    assert r["result"] == "found" and len(r["ids"]) == 2
    tid = r["ids"][0]
    fake.min_found = 0                       # 후보가 찼다 — 서버가 더 찾으라고 하지 않게
    seq = []
    for _ in range(12):                      # 행 2개 × 6단계 = 12 → 둘 다 plan_review 에서 멈춘다
        r = w.tick()
        seq.append(r["result"])
    assert seq == ["advanced"] * 12
    assert {x["state"] for x in fake.rows.values()} == {"plan_review"}
    assert w.tick()["result"] == "idle"       # 검수 자리에서는 워커가 할 일이 없다(건너뛰지 않음)
    fake.review(tid, "pass")
    assert w.tick()["result"] == "advanced" and fake.rows[tid]["state"] == "produced"
    assert w.tick()["result"] == "advanced" and fake.rows[tid]["state"] == "final_review"
    assert w.tick()["result"] == "idle"
    fake.review(tid, "pass")
    assert fake.rows[tid]["state"] == "passed"
    row = fake.rows[tid]
    assert [h["to"] for h in row["history"]] == ["benched", "scored", "assigned", "scripted", "sourced", "plan_review", "produced", "final_review"]
    assert row["artifacts"]["plan.md"]["url"].endswith("/plan.md")       # 산출물은 올라가 보드 주소가 생긴다
    assert row["cost"]["llm_calls"] == 3 and row["scores"]["total"] == 41.5
    assert len(fake.uploads) == 8 + 6       # 행1 8단계 + 행2 6단계


# ── 잠금 ──────────────────────────────────────────────────────────────────
def test_잠금충돌_다른워커는_같은행을_못받는다(tmp_path):
    fake = FakeApi()
    t1 = fake.add("A")
    t2 = fake.add("B")
    a = W.Api("", KEY, session=_client(fake))
    c1 = a.claim("w1", "식품", "bench", "yummyknow")
    c2 = a.claim("w2", "식품", "bench", "yummyknow")
    assert c1["topic"]["id"] == t1 and c2["topic"]["id"] == t2
    c3 = a.claim("w3", "식품", "bench", "yummyknow")
    assert c3["step"] is None                                   # 둘 다 잠겨 있다
    with pytest.raises(W.ApiError) as e:
        a.advance(t1, "w2", "bench")                            # 남의 잠금으로 넘기기
    assert e.value.status == 409 and e.value.code == "lock"


def test_heartbeat_끊기면_11분뒤_다른워커가_집어가고_옛워커는_lock(tmp_path):
    fake = FakeApi()
    tid = fake.add("A")
    slow_a = MockSteps(tmp_path)
    wa = _worker(fake, tmp_path, steps=slow_a, name="wa")
    wb = _worker(fake, tmp_path, name="wb")
    a = wa.api
    got = a.claim("wa", "식품", "bench", "yummyknow")          # wa 가 받고 죽음(heartbeat 없음)
    assert got["topic"]["id"] == tid
    fake.now += 10 * 60
    assert wb.tick()["result"] == "idle"                        # 10분: 아직 wa 잠금
    fake.now += 2 * 60
    r = wb.tick()                                                # 12분: 끊김 → wb 인수
    assert r["result"] == "advanced" and fake.rows[tid]["state"] == "benched"
    with pytest.raises(W.ApiError) as e:                         # 되살아난 wa 의 보고는 거절
        a.advance(tid, "wa", "bench")
    assert e.value.code == "lock"


def test_heartbeat는_잠금을_늘린다(tmp_path):
    fake = FakeApi()
    tid = fake.add("A")
    w = _worker(fake, tmp_path, name="wa")
    w.api.claim("wa", "식품", "bench", "yummyknow")
    w._set(step="bench", topic_id=tid)
    fake.now += 10 * 60
    w.beat()                                                     # 10분에 맥박 → 잠금이 지금+11분
    fake.now += 5 * 60
    assert w.api.claim("wb", "식품", "bench", "yummyknow")["step"] is None   # 15분이어도 wa 것


def test_heartbeat_스레드가_긴단계동안_돈다(tmp_path):
    fake = FakeApi()
    tid = fake.add("A")
    w = _worker(fake, tmp_path, steps=MockSteps(tmp_path, slow=0.5), hb_interval=0.05)
    w.start_heartbeat()
    try:
        assert w.tick()["result"] == "advanced"
    finally:
        w.stop_heartbeat()
    during = [h for h in fake.heartbeats if h.get("topic_id") == tid and h.get("step") == "bench"]
    assert len(during) >= 3, fake.heartbeats


# ── 검수 자리 ──────────────────────────────────────────────────────────────
def test_검수자리_넘기기는_서버가_거절하고_행은_그대로(tmp_path):
    fake = FakeApi()
    tid = fake.add("A", state="plan_review")
    fake.buggy_hand_review = True                                # 서버 버그로 검수 대기 행이 나가도
    w = _worker(fake, tmp_path)
    r = w.tick()
    assert r["result"] == "review_gate"
    assert fake.rows[tid]["state"] == "plan_review"


# ── 실패는 이유와 함께 멈춤 ─────────────────────────────────────────────────
def test_엔진없음은_NotImplemented_이유로_멈춘다_진짜_worker_steps(tmp_path, monkeypatch):
    fake = FakeApi()
    tid = fake.add("A", state="assigned")
    real_import = WS.importlib.import_module

    def no_script_engine(name, *a, **k):
        if name.endswith("script_engine"):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, *a, **k)
    monkeypatch.setattr(WS.importlib, "import_module", no_script_engine)
    w = _worker(fake, tmp_path, steps=WS)
    r = w.tick()
    assert r["result"] == "error"
    row = fake.rows[tid]
    assert row["state"] == "assigned"                          # 조용히 넘어가지 않았다
    assert "NotImplementedError" in row["error"] and "script_engine" in row["error"]
    assert w.tick()["result"] == "idle"                        # 멈춘 행은 다시 안 준다(서버 규칙)


def test_단계예외는_advance_error로_원문과함께(tmp_path):
    fake = FakeApi()
    tid = fake.add("A")
    w = _worker(fake, tmp_path, steps=MockSteps(tmp_path, fail={"bench": RuntimeError("유튜브 검색 0건")}))
    r = w.tick()
    assert r["result"] == "error"
    assert fake.rows[tid]["state"] == "found" and "RuntimeError: 유튜브 검색 0건" in fake.rows[tid]["error"]


def test_StepError는_산출물도_같이_올린다(tmp_path):
    fake = FakeApi()
    tid = fake.add("A", state="assigned")
    p = tmp_path / "대본_검사.md"
    p.write_text("미통과", encoding="utf-8")
    w = _worker(fake, tmp_path, steps=MockSteps(tmp_path, fail={"script": WS.StepError("대본 검사 미통과", {"대본_검사.md": str(p)})}))
    w.tick()
    row = fake.rows[tid]
    assert "대본 검사 미통과" in row["error"] and row["artifacts"]["대본_검사.md"]["url"]


def test_find_실패는_heartbeat_last_error로_보드에(tmp_path):
    fake = FakeApi(min_found=1)
    w = _worker(fake, tmp_path, steps=MockSteps(tmp_path, fail={"find": WS.StepError("후보 0 — yt_search 결과 0")}))
    r = w.tick()
    assert r["result"] == "error"
    assert any("후보 0" in (h.get("last_error") or "") for h in fake.heartbeats)


def test_모르는단계는_이유로_멈춘다(tmp_path):
    with pytest.raises(WS.StepError) as e:
        WS.run_step("final_review", {"id": "t"}, WS.Ctx(out_root=tmp_path, channel="x", category="식품", track="bench"))
    assert "할 수 없는 단계" in e.value.reason


# ── 비용 상한 ──────────────────────────────────────────────────────────────
def test_비용상한이면_그단계는_건너뛰고_다른행(tmp_path):
    fake = FakeApi(caps={"produce": "tts"})
    t_prod = fake.add("만들 차례", state="producing")
    t_bench = fake.add("벤치 차례")
    w = _worker(fake, tmp_path)
    r = w.tick()
    assert r["result"] == "advanced" and r["topic"]["id"] == t_bench
    assert fake.rows[t_prod]["state"] == "producing"            # 상한 단계는 안 돌았다
    fake.rows.pop(t_bench)
    assert w.tick()["result"] == "idle"


def test_키가_틀리면_403(tmp_path):
    fake = FakeApi()
    a = W.Api("", "wrong", session=_client(fake))
    with pytest.raises(W.ApiError) as e:
        a.claim("w", "식품", "bench", "yummyknow")
    assert e.value.status == 403
