# -*- coding: utf-8 -*-
"""소재창고 워커 시험 (관제 097, 2026-10-16) — 서버 규격 docs/superpowers/specs/2026-10-16-소재창고-api.md.

**진짜 앱 라우트**(`/api/admin/calcopy/topics*` → calcopy_topics)를 TestClient 로 띄우고 워커를 그 위에서 돌린다
(관리자 확인만 test_calcopy_topics 처럼 통과시킨다 · CALCOPY_DATA_DIR = tmp · 시계 = CT._now 바꿔치기).
단계는 가짜(MockSteps) — 엔진·무료 제미나이·유료 API 를 부르지 않는다. 엔진 없음 시험만 진짜 worker_steps.

재는 것: 한 바퀴(find → … → plan_review → 사람 통과 → produce → check → final_review → 사람 통과 → passed) ·
잠금 충돌 · heartbeat 끊김(11분) 뒤 다른 워커 인수·옛 워커 거절 · heartbeat 스레드 · 검수 자리 거절 ·
엔진 없음 = release(이유) · 단계 예외 = release · 서버 필수 자료 거절(score 5기준) = release · 비용 상한 = 다른 행.
"""
from __future__ import annotations

import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest

from shopping_shorts import calcopy_topics as CT
from tools.calcopy.engine import worker as W
from tools.calcopy.engine import worker_steps as WS

CRIT = {k: {"score": 4, "why": f"{k} 근거 문장"} for k in ("아는 대상", "몰랐던", "재미", "이야기", "얻는 것")}


class Clock:
    def __init__(self):
        self.t = CT.datetime(2026, 10, 16, 9, 0, 0, tzinfo=CT.KST)

    def __call__(self):
        return self.t

    def tick(self, **kw):
        self.t = self.t + timedelta(**kw)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from shopping_shorts import app as A
    clk = Clock()
    monkeypatch.setattr(CT, "_now", clk)
    monkeypatch.setenv("CALCOPY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(A, "_require_admin", lambda request: None)
    return TestClient(A.app), clk, tmp_path


class MockSteps:
    """가짜 단계 — 서버가 단계마다 요구하는 자료(규격 §1 표)를 규격대로 만들어 준다."""

    def __init__(self, tmp: Path, fail: dict | None = None, slow: float = 0, override: dict | None = None):
        self.tmp, self.fail, self.slow, self.override, self.calls = tmp, fail or {}, slow, override or {}, []

    def _f(self, name, text="x"):
        p = self.tmp / "mock" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return str(p)

    def run_step(self, step, topic, ctx):
        self.calls.append((step, (topic or {}).get("id")))
        if self.slow:
            time.sleep(self.slow)
        if step in self.fail:
            raise self.fail[step]
        if step in self.override:
            return self.override[step]
        if step == "find":
            return {"rows": [{"name": "신라면 구미 공장 비하인드", "source": {"via": "youtube", "query": "신라면 공장"}},
                             {"name": "코스트코 핫도그 가격 비밀", "source": {"via": "youtube", "query": "코스트코 핫도그"}}]}
        return {
            "bench": {"artifacts": {"벤치.md": self._f("벤치.md", "# 벤치")}, "outputs": {"bench": "벤치.md"}, "cost": {"gemini": 1},
                      "data": {"bench": {"n_videos": 6, "points": [{"kind": "twist", "text": "반전"}]}}},
            "score": {"cost": {"gemini": 1}, "data": {"score": {"criteria": CRIT, "total": 20}}},
            "assign": {"data": {"assign": {"channel": ctx.channel, "preset": ctx.channel}}},
            "script": {"artifacts": {"대본.json": self._f("대본.json", "{}")}, "outputs": {"script": "대본.json"}, "cost": {"gemini": 2}},
            "source": {"artifacts": {"재료_뼈대.json": self._f("재료_뼈대.json", "{}")}, "data": {"rights": {"v_a.mp4": "유튜브 쇼츠(재료 후보)"}}},
            "plan": {"artifacts": {"계획.md": self._f("계획.md", "# 계획\n- 컷 5")}, "outputs": {"plan": "계획.md"}},
            "produce": {"artifacts": {"final.mp4": self._f("final.mp4", "mp4")}, "outputs": {"final": "final.mp4"}, "cost": {"typecast": 1}},
            "check": {"artifacts": {"verdict.json": self._f("verdict.json", '{"verdict":"통과"}'), "final_sheet_1s.jpg": self._f("s.jpg")},
                      "outputs": {"verdict": "verdict.json", "sheet_1s": "final_sheet_1s.jpg"}},
        }[step]


def _worker(cl, tmp, steps=None, name="pc-식품-bench", **kw):
    logs = []
    w = W.Worker(W.Api("", session=cl), "식품", "bench", "yummyknow", name=name, out_root=tmp / "out",
                 steps=steps or MockSteps(tmp), log=logs.append, **kw)
    w.logs = logs
    return w


def _add(cl, name="A", category="식품"):
    r = cl.post("/api/admin/calcopy/topics", json={"name": name, "category": category, "track": "bench"})
    assert r.status_code == 200, r.text
    return r.json()["topic"]["id"]


def _review(cl, tid, stage, verdict="pass", **kw):
    r = cl.post(f"/api/admin/calcopy/topics/{tid}/review", json={"stage": stage, "verdict": verdict, "by": "시험", **kw})
    assert r.status_code == 200, r.text
    return r.json()["topic"]


def _topic(cl, tid):
    return cl.get(f"/api/admin/calcopy/topics/{tid}").json()


# ── 한 바퀴 ────────────────────────────────────────────────────────────────
def test_한바퀴_find부터_passed까지_검수는_사람(env):
    cl, clk, tmp = env
    w = _worker(cl, tmp)
    r = w.tick()                                  # 할 일 없음 → 소재 찾기
    assert r["result"] == "found" and len(r["ids"]) == 2
    t1 = r["ids"][0]
    seq = [w.tick()["result"] for _ in range(12)]    # 2행 × 6단계 → 둘 다 plan_review 에서 멈춤
    assert seq == ["advanced"] * 12, w.logs
    board = cl.get("/api/admin/calcopy/topics").json()
    assert board["totals"] == {"plan_review": 2} and len(board["decide"]) == 2
    r = w.tick()
    assert r["result"] == "idle"                  # 검수 자리는 워커가 못 넘는다(find 는 한 시간 간격이라 안 돈다)
    _review(cl, t1, "plan_review")
    assert w.tick()["topic"]["state"] == "produced"
    assert w.tick()["topic"]["state"] == "final_review"
    assert w.tick()["result"] == "idle"
    t = _review(cl, t1, "final_review")
    assert t["state"] == "passed"
    d = _topic(cl, t1)
    assert [h["to"] for h in d["history"] if h["kind"] == "advance"] == [
        "benched", "scored", "assigned", "scripted", "sourced", "plan_review", "produced", "final_review"]
    assert d["topic"]["outputs"]["plan"] == "계획.md" and d["topic"]["outputs"]["final"] == "final.mp4"
    cost = d["topic"]["cost"]
    assert {k: v for k, v in cost.items() if k != "seconds"} == {"gemini": 4, "typecast": 1}
    assert isinstance(cost["seconds"], int) and 0 <= cost["seconds"] <= 10      # 가짜 단계라 거의 0초(벽시계라 정확일치는 흔들린다)
    names = {f["name"] for f in d["files"]}
    assert {"계획.md", "final.mp4", "verdict.json", "대본.json", "벤치.md"} <= names
    assert cl.get(next(f["url"] for f in d["files"] if f["name"] == "계획.md")).text.startswith("# 계획")
    kpi = cl.get("/api/admin/calcopy/topics").json()["kpi"]
    assert kpi["plan_review"]["pass"] == 1 and kpi["final_review"]["pass"] == 1


# ── 잠금 ──────────────────────────────────────────────────────────────────
def test_잠금충돌_다른워커는_같은행을_못받고_남의것은_못넘긴다(env):
    cl, clk, tmp = env
    t1, t2 = _add(cl, "A"), _add(cl, "B")
    a, b = W.Api("", session=cl), W.Api("", session=cl)
    assert a.claim_next("w1", ["bench"])["topic"]["id"] == t1
    assert b.claim_next("w2", ["bench"])["topic"]["id"] == t2
    c = a.claim_next("w3", ["bench"])
    assert c["topic"] is None and any("잠김" in x for x in c["reasons"])
    with pytest.raises(W.ApiError) as e:
        b.advance(t1, "w2", data={"bench": {"x": 1}})
    assert e.value.status == 409 and "잠근 워커가 아님" in e.value.msg


def test_heartbeat_끊기면_11분뒤_다른워커가_집어가고_옛워커는_거절(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    api = W.Api("", session=cl)
    assert api.claim_next("wa", ["bench"])["topic"]["id"] == tid    # wa 가 받고 죽음
    wb = _worker(cl, tmp, name="wb", find_every=0)
    clk.tick(minutes=10)
    assert wb.tick()["result"] == "idle"                            # 10분: 아직 wa 잠금
    clk.tick(minutes=2)
    r = wb.tick()                                                     # 12분: 끊김 → wb 인수
    assert r["result"] == "advanced" and r["topic"]["state"] == "benched"
    assert any(h["kind"] == "expire" for h in _topic(cl, tid)["history"])
    with pytest.raises(W.ApiError) as e:
        api.advance(tid, "wa", data={"bench": {"x": 1}})
    assert e.value.status == 409


def test_heartbeat_스레드가_긴단계동안_잠금을_살린다(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    w = _worker(cl, tmp, steps=MockSteps(tmp, slow=0.6), hb_interval=0.05, find_every=0)
    seen = []
    real = w.api.heartbeat

    def spy(t, worker, doing=None):
        seen.append((t, doing))
        clk.tick(minutes=5)                 # 맥박 한 번에 5분씩 흐른다고 치자 → 맥박이 없으면 잠금이 풀린다
        return real(t, worker, doing)
    w.api.heartbeat = spy
    w.start_heartbeat()
    try:
        r = w.tick()
    finally:
        w.stop_heartbeat()
    assert r["result"] == "advanced", w.logs          # 수십 분이 흘렀어도 맥박 덕에 잠금 유지
    assert len([s for s in seen if s == (tid, "bench 중")]) >= 3


# ── 검수 자리 ──────────────────────────────────────────────────────────────
def test_검수자리는_claim도_advance도_서버가_거절(env):
    cl, clk, tmp = env
    w = _worker(cl, tmp, find_every=0)
    tid = _add(cl, "A")
    for _ in range(6):
        assert w.tick()["result"] == "advanced"
    assert _topic(cl, tid)["topic"]["state"] == "plan_review"
    assert w.tick()["result"] == "idle"
    r = cl.post(f"/api/admin/calcopy/topics/{tid}/claim", json={"worker": "w", "step": "produce"})
    assert r.status_code == 409
    with pytest.raises(W.ApiError) as e:
        w.api.advance(tid, w.name, outputs={"final": "x.mp4"})
    assert e.value.status == 409 and "사람 검수 자리" in e.value.msg


# ── 실패는 이유와 함께 멈춤 ─────────────────────────────────────────────────
def _to(cl, w, tid, n):
    for _ in range(n):
        assert w.tick()["result"] == "advanced", w.logs


def test_엔진없음은_NotImplemented_이유로_release_진짜_worker_steps(env, monkeypatch):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    _to(cl, _worker(cl, tmp, find_every=0), tid, 3)              # assigned 까지 가짜로
    real_import = WS.importlib.import_module

    def no_script_engine(name, *a, **k):
        if name.endswith("script_engine"):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name, *a, **k)
    monkeypatch.setattr(WS.importlib, "import_module", no_script_engine)
    w = _worker(cl, tmp, steps=WS, find_every=0)
    r = w.tick()
    assert r["result"] == "error"
    t = _topic(cl, tid)["topic"]
    assert t["state"] == "assigned" and t["lock"]["owner"] is None          # 조용히 넘어가지 않았고 잠금은 풀렸다
    assert "NotImplementedError" in t["last_error"] and "script_engine" in t["last_error"]
    errs = cl.get("/api/admin/calcopy/topics").json()["errors"]
    assert errs and errs[0]["id"] == tid                                     # 보드 '멈춘 이유'에 뜬다


def test_단계예외는_release_원문과함께(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    w = _worker(cl, tmp, steps=MockSteps(tmp, fail={"bench": RuntimeError("유튜브 검색 0건")}), find_every=0)
    assert w.tick()["result"] == "error"
    t = _topic(cl, tid)["topic"]
    assert t["state"] == "found" and "RuntimeError: 유튜브 검색 0건" in t["last_error"]


def test_StepError는_산출물을_올리고_이유로_멈춘다(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    p = tmp / "대본_검사.md"
    p.write_text("미통과", encoding="utf-8")
    w = _worker(cl, tmp, steps=MockSteps(tmp, fail={"bench": WS.StepError("벤치 포인트 0", {"벤치_실패.md": str(p)})}), find_every=0)
    w.tick()
    d = _topic(cl, tid)
    assert "벤치 포인트 0" in d["topic"]["last_error"] and "벤치_실패.md" in {f["name"] for f in d["files"]}


def test_서버가_필수자료를_거절하면_release로_이유가_남는다(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    bad = {"score": {"cost": {"gemini": 1}, "data": {"score": {"criteria": dict(list(CRIT.items())[:3])}}}}
    w = _worker(cl, tmp, steps=MockSteps(tmp, override=bad), find_every=0)
    _to(cl, w, tid, 1)
    r = w.tick()
    assert r["result"] == "refused" and r["status"] == 400
    t = _topic(cl, tid)["topic"]
    assert t["state"] == "benched" and "5기준" in t["last_error"]


def test_find_실패는_로그로(env):
    cl, clk, tmp = env
    w = _worker(cl, tmp, steps=MockSteps(tmp, fail={"find": WS.StepError("후보 0 — yt_search 결과 0")}))
    r = w.tick()
    assert r["result"] == "error" and any("후보 0" in x for x in w.logs)


def test_모르는단계는_이유로_멈춘다(tmp_path):
    with pytest.raises(WS.StepError) as e:
        WS.run_step("review", {"id": 1}, WS.Ctx(out_root=tmp_path, channel="x", category="식품", track="bench"))
    assert "할 수 없는 단계" in e.value.reason


# ── 비용 상한 ──────────────────────────────────────────────────────────────
def test_비용상한이면_그단계는_건너뛰고_다른행(env):
    cl, clk, tmp = env
    w = _worker(cl, tmp, find_every=0)
    t_prod = _add(cl, "만들 차례")
    _to(cl, w, t_prod, 6)
    _review(cl, t_prod, "plan_review")                               # → producing
    assert cl.post("/api/admin/calcopy/topics/caps", json={"typecast": 0}).status_code == 200
    t_bench = _add(cl, "벤치 차례")
    r = w.tick()
    assert r["result"] == "advanced" and r["topic"]["id"] == t_bench
    assert _topic(cl, t_prod)["topic"]["state"] == "producing"        # 상한 단계는 안 돌았다
    w.allowed = ["produce"]
    r = w.tick()
    assert r["result"] == "idle" and any("typecast" in x for x in r["reasons"])


# ── 실물 세션(requests) 모양 ─────────────────────────────────────────────────
def test_Api는_requests가_받는_인자만_쓴다(tmp_path):
    """TestClient(httpx)는 content= 를 받지만 requests 는 TypeError — 시험만 통과하고 실물에서 올리기가 전부 죽었다(10-16 로컬 HTTP 실측)."""
    import inspect

    import requests
    sig = inspect.signature(requests.Session.request)
    calls = []

    class R:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True}

    class S:
        cookies = requests.Session().cookies

        def post(self, url, **kw):
            sig.bind(None, "POST", url, **kw)        # requests 가 못 받는 인자면 TypeError
            calls.append(kw)
            return R()

        get = post
    a = W.Api("http://127.0.0.1:1", session=S())
    p = tmp_path / "계획.md"
    p.write_text("# 계획", encoding="utf-8")
    a.upload(1, "계획.md", p)
    a.claim_next("w", ["bench"])
    a.advance(1, "w", data={"bench": {"x": 1}})
    a.release(1, "w", "이유")
    a.heartbeat(1, "w", "1/3")
    assert calls[0]["data"] == "# 계획".encode("utf-8")



# ── 규격 §6 보완 ───────────────────────────────────────────────────────────
def test_단계소요초가_cost_seconds로_쌓인다(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    w = _worker(cl, tmp, steps=MockSteps(tmp, slow=1.2), find_every=0)
    assert w.tick()["result"] == "advanced"
    sec = _topic(cl, tid)["topic"]["cost"]["seconds"]
    assert 1 <= sec <= 3, sec


def test_카테고리_트랙_채널로_거른다(env):
    cl, clk, tmp = env
    t_home = _add(cl, "홈템 소재", category="홈템")
    w = _worker(cl, tmp, find_every=0)                       # 식품·bench·yummyknow
    assert w.tick()["result"] == "idle"                        # 홈템은 안 집는다
    t_food = _add(cl, "식품 소재")
    _to(cl, w, t_food, 3)                                      # assign 까지는 채널 없이 → 내 채널로 배정
    other = _worker(cl, tmp, name="sseol-식품", find_every=0)
    other.channel = "sseolpulda"
    r = other.tick()                                           # 다른 채널 워커는 내 채널에 배정된 script 를 못 집는다
    assert r["result"] == "idle", r
    assert _topic(cl, t_food)["topic"]["state"] == "assigned"
    assert _topic(cl, t_home)["topic"]["state"] == "found"
    assert w.tick()["topic"]["state"] == "scripted"


def test_쉬는워커도_보드_워커패널에_이유와함께(env):
    cl, clk, tmp = env
    w = _worker(cl, tmp, steps=MockSteps(tmp, fail={"find": WS.StepError("후보 0 — 도우인 로그인벽")}))
    assert w.tick()["result"] == "error"
    ws = cl.get("/api/admin/calcopy/topics").json()["workers"]
    me = next(x for x in ws if x["worker"] == w.name)
    assert me["status"] == "idle" and "도우인 로그인벽" in (me["idle_reason"] or "") and me["category"] == "식품"


def test_세번_실패하면_stalled_사람이_unstall(env):
    cl, clk, tmp = env
    tid = _add(cl, "A")
    w = _worker(cl, tmp, steps=MockSteps(tmp, fail={"bench": RuntimeError("검색 차단")}), find_every=0)
    for i in range(3):
        assert w.tick()["result"] == "error"
        clk.tick(minutes=31)                                   # 실패 뒤 대기(30분) 지남
    b = cl.get("/api/admin/calcopy/topics").json()
    assert [x["id"] for x in b["stalled"]] == [tid]
    assert w.tick()["result"] == "idle"                        # 멈춘 소재는 안 준다
    r = cl.post(f"/api/admin/calcopy/topics/{tid}/unstall", json={"by": "시험", "note": "쿠키 갈았음"})
    assert r.status_code == 200 and r.json()["topic"]["stalled"] is False
    assert _worker(cl, tmp, find_every=0).tick()["result"] == "advanced"
