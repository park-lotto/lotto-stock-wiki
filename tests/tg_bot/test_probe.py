import pytest

from tg_bot.probe import Prober, ProbeError


class FakeResp:
    def __init__(self, code=200, data=None, cookies=None):
        self.status_code = code
        self._data = data if data is not None else {}
        self.cookies = cookies or {}

    def json(self):
        return self._data


class FakeSession:
    """requests.Session 흉내 — 호출 기록을 남긴다."""

    def __init__(self, responses):
        self.responses = responses      # {(method, url): FakeResp}
        self.calls = []
        self.cookies = {}

    def post(self, url, data=None, timeout=None, allow_redirects=None):
        self.calls.append(("POST", url))
        return self.responses.get(("POST", url), FakeResp(404))

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return self.responses.get(("GET", url), FakeResp(404))


BASE = "https://x.test"


def test_로그인에_성공하면_상태를_조회한다():
    s = FakeSession({
        ("POST", BASE + "/api/login"): FakeResp(303),
        ("GET", BASE + "/api/mix/status/j1"): FakeResp(
            200, {"status": "failed", "error": "gemini 키 소진"}),
    })
    p = Prober(BASE, "u", "p", session=s)
    out = p.job("j1")
    assert out["status"] == "failed"
    assert out["error"] == "gemini 키 소진"


def test_로그인은_한_번만_한다():
    s = FakeSession({
        ("POST", BASE + "/api/login"): FakeResp(303),
        ("GET", BASE + "/api/mix/status/j1"): FakeResp(200, {"status": "done"}),
        ("GET", BASE + "/api/mix/status/j2"): FakeResp(200, {"status": "done"}),
    })
    p = Prober(BASE, "u", "p", session=s)
    p.job("j1")
    p.job("j2")
    assert [c for c in s.calls if c[0] == "POST"] == [("POST", BASE + "/api/login")]


def test_없는_job은_사유를_분명히_말한다():
    s = FakeSession({
        ("POST", BASE + "/api/login"): FakeResp(303),
        ("GET", BASE + "/api/mix/status/nope"): FakeResp(404, {"error": "job 없음"}),
    })
    p = Prober(BASE, "u", "p", session=s)
    with pytest.raises(ProbeError) as e:
        p.job("nope")
    assert "찾을 수 없" in str(e.value)


def test_401이면_로그인_실패라고_말한다():
    """★사유를 뭉개지 않는다 — '조회 실패'로 뭉개면 원인을 못 찾는다."""
    s = FakeSession({
        ("POST", BASE + "/api/login"): FakeResp(303),
        ("GET", BASE + "/api/mix/status/j1"): FakeResp(401, {"error": "unauthorized"}),
    })
    p = Prober(BASE, "u", "p", session=s)
    with pytest.raises(ProbeError) as e:
        p.job("j1")
    assert "로그인" in str(e.value)


def test_로그인_자체가_실패하면_그렇게_말한다():
    s = FakeSession({("POST", BASE + "/api/login"): FakeResp(500)})
    p = Prober(BASE, "u", "p", session=s)
    with pytest.raises(ProbeError) as e:
        p.job("j1")
    assert "로그인에 실패" in str(e.value)
