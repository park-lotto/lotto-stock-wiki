"""틱톡 로그인이 없어도 틱톡 소재가 아니면 제작을 막지 않는다(11-02 사장님 '틱톡 안 되면 회원들한테 안내를 해')."""
from tools.calcopy.hybrid import runner_ops as R


def _setup(monkeypatch):
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    monkeypatch.setattr(R, "CACHE", False, raising=False)
    monkeypatch.setattr(R, "_cookie_ok", lambda pf: pf != "tiktok")
    monkeypatch.setattr(R, "browser_ok", lambda **k: True, raising=False)
    monkeypatch.setattr(R, "yt_probe", lambda u: "", raising=False)
    import tools.calcopy.origin_find as OF
    monkeypatch.setattr(OF, "yt_auth", lambda u: ["--cookies-from-browser", "x"])


def _ids(version, url):
    return [x["id"] for x in R.need_list(version, url, "")]


def test_not_blocked_for_other_sources(monkeypatch):
    _setup(monkeypatch)
    assert "login:tiktok" not in _ids("썰템쇼판", "https://www.youtube.com/shorts/abc")


def test_blocked_for_tiktok_source(monkeypatch):
    _setup(monkeypatch)
    assert "login:tiktok" in _ids("썰템쇼판", "https://www.tiktok.com/@a/video/1")
