"""관제 315 — VMake 진행 정체 조기 종료·1회 재제출 / 릴레이 없을 때 틱톡 서버 경로 생략."""
import itertools

from shopping_shorts.vmake_sdk.core import api as vapi
from shopping_shorts import kw_backends


class _Clock:
    def __init__(self):
        self.t = 0.0

    def mono(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _api_with(monkeypatch, progress_seq, predict_ms=787017):
    clk = _Clock()
    monkeypatch.setattr(vapi.time, "monotonic", clk.mono)
    monkeypatch.setattr(vapi.time, "sleep", clk.sleep)
    a = vapi.AiApi.__new__(vapi.AiApi)
    it = iter(progress_seq)

    def q(uri, policy):
        pg = next(it, progress_seq[-1])
        return {"is_finished": False,
                "result": {"data": {"status": 0, "progress": pg, "predict_elapsed": predict_ms}}}
    a.queryStatus = q
    policy = {"url": "https://x", "status_query": {"path": "s", "durations": ",".join(["10000"] * 400)}}
    return a, policy, clk


def test_stuck_99_percent_stops_long_before_an_hour(monkeypatch):
    # 11-03 실측 모양: 예상 787초, 99%에서 그대로
    a, pol, clk = _api_with(monkeypatch, [0.5, 0.9, 0.99])
    r = a.status("t1", pol)
    assert r["error"] == "poll_stalled"
    assert r["progress"] == 0.99
    assert 1574 <= r["elapsed_seconds"] <= 1574 + 320      # 예상×2 직후, 1시간(3600) 훨씬 전


def test_slow_but_moving_task_is_not_cut(monkeypatch):
    # 진행률이 계속 오르면 예상의 2배를 넘겨도 기다린다
    seq = [round(0.001 * i, 3) for i in range(1, 400)]
    a, pol, clk = _api_with(monkeypatch, seq, predict_ms=60000)
    r = a.status("t2", pol)
    assert r["error"] == "poll_timeout"                     # 정체가 아니라 예산 소진


def test_stall_off_switch(monkeypatch):
    monkeypatch.setenv("MT_AI_POLL_STALL_MIN_S", "0")
    a, pol, clk = _api_with(monkeypatch, [0.99])
    assert a.status("t3", pol)["error"] == "poll_timeout"


def test_stall_resubmits_once_then_fails(monkeypatch, tmp_path):
    from shopping_shorts import vmake_client as vc
    calls = itertools.count()

    class C:
        def run_task(self, **kw):
            next(calls)
            return {"error": "poll_stalled", "skill_status": "failed", "task_id": "t", "detail": "멈춤"}
    monkeypatch.setattr(vc, "_new_api_client", lambda ak, sk: C())
    monkeypatch.setattr(vc, "_split_key", lambda k: ("a", "b"))
    src = tmp_path / "in.mp4"; src.write_bytes(b"x")
    try:
        vc.remove_subtitles(str(src), "a:b", str(tmp_path / "out.mp4"), tier=vc.TIER_PRO)
    except RuntimeError as e:
        assert "멈춤" in str(e)
    else:
        raise AssertionError("두 번 멈추면 실패로 올라가야 한다")
    assert next(calls) == 2                                 # 최초 1 + 재제출 1, 그 이상 없음


def test_tiktok_skips_server_browser_when_relay_missing(monkeypatch):
    monkeypatch.setattr(kw_backends, "_tiktok_via_relay", lambda k, n: None)
    monkeypatch.delenv("KW_TIKTOK_SERVER_PW", raising=False)
    import playwright.sync_api as ps
    launched = []
    monkeypatch.setattr(ps, "sync_playwright", lambda: launched.append(1) or (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(kw_backends.config, "TIKTOK_SESSION_PATH", __file__, raising=False)
    assert kw_backends.pw_tiktok("dog carrier", 8) == []
    assert launched == []          # 늘 0건인 서버 브라우저(60초+9초)를 띄우지 않는다


def test_relay_gives_waited_search_before_background_detail():
    from shopping_shorts.coupang_relay import RelayQueue
    q = RelayQueue()
    for n in range(19):
        q.submit_async("detail", {"product": "p%d" % n})
    import threading
    got = {}
    t = threading.Thread(target=lambda: got.setdefault("r", q.submit("dog carrier", 8, 3, kind="tiktok",
                                                                    payload={"keyword": "dog carrier"})))
    t.start()
    import time as _t
    for _ in range(40):
        if q.status()["waiting"] == 20:
            break
        _t.sleep(0.05)
    job = q.take(1)
    assert job.kind == "tiktok"                     # 상품재료 19건을 건너뛰고 먼저
    q.complete(job.id, {"items": [{"url": "u"}]})
    t.join(5)
    assert got["r"]["items"][0]["url"] == "u"


def test_coupang_access_denied_200_is_block_and_cools_down(monkeypatch):
    from shopping_shorts import coupang_search as cs
    import playwright.sync_api as ps
    launches = []

    class Resp:
        status = 200

    class Page:
        def goto(self, *a, **k): return Resp()
        def wait_for_timeout(self, *a): pass
        def wait_for_selector(self, *a, **k): raise TimeoutError()
        def evaluate(self, *a): return []
        def inner_text(self, *a): return "Access Denied | You don't have permission to access"

    class Ctx:
        pages = [Page()]
        def close(self): pass

    class P:
        class chromium:
            @staticmethod
            def launch_persistent_context(*a, **k):
                launches.append(1); return Ctx()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(ps, "sync_playwright", lambda: P())
    monkeypatch.setattr(cs.config, "COUPANG_SEARCH_ENABLED", True, raising=False)
    monkeypatch.setattr(cs, "_MIN_INTERVAL_SEC", 0)
    monkeypatch.setattr(cs, "_blocked_until", [0.0])
    r = cs.search("강아지 캐리어 315시험", limit=3)
    assert r.get("blocked") and "Access Denied" in r["notice"]   # '결과 없음'으로 오판하지 않는다
    r2 = cs.search("다른 검색어 315시험", limit=3)
    assert r2.get("blocked") and len(launches) == 1                 # 쉬는 동안 브라우저를 다시 안 띄운다
