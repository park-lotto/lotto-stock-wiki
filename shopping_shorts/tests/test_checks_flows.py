from shopping_shorts.checks import discover
from shopping_shorts.checks.flows import base


def test_flows_discovered_have_contract():
    mods = discover.discover("flows")
    assert mods, "flow_*.py가 하나도 없다"
    for m in mods:
        assert {"name", "needs_worker", "timeout_s"} <= set(m.META) and callable(m.run)


def test_current_work_id_parses_query():
    class P:
        url = "http://x/produce?work=abc123&t=1"
    assert base.current_work_id(P()) == "abc123"
    P.url = "http://x/produce"
    assert base.current_work_id(P()) is None


def test_roundtrip_reports_which_stage_diverged():
    calls = {"local": ["A", "A", "B"], "server": ["A"]}

    class FakePage:
        url = "http://x/produce?work=w1"
        def reload(self, **kw): pass
        def wait_for_timeout(self, ms): pass
    class FakeSession:
        page = FakePage(); base_url = "http://x"
    r = base.roundtrip(FakeSession(), name="대본 왕복", signature="L2:script",
                       edit=lambda p: "A", read_local=lambda p: calls["local"].pop(0),
                       read_server=lambda s, w: calls["server"].pop(0),
                       go_away=lambda p: None, go_back=lambda p: None)
    assert r.verdict == "red" and "새로고침" in r.reason
