"""텔레 알림 — 러너의 unsure/실패 호출용(스펙 트랙4). 무키 폴백·예외삼킴."""
import shopping_shorts.notify as notify


class _FakeReq:
    def __init__(self, exc=None):
        self.calls = []
        self._exc = exc

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json})
        if self._exc:
            raise self._exc

        class R:  # noqa
            status_code = 200
        return R()


def test_no_keys_is_noop(monkeypatch):
    monkeypatch.delenv("SHORTS_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("SHORTS_TELEGRAM_CHAT_ID", raising=False)
    fr = _FakeReq()
    assert notify.send_telegram("hi", _requests=fr) is False
    assert fr.calls == []                       # 호출 자체 안 함


def test_sends_when_keys_present():
    fr = _FakeReq()
    ok = notify.send_telegram("작업 확인 필요", token="TOK", chat_id="42", _requests=fr)
    assert ok is True
    assert len(fr.calls) == 1
    assert "TOK" in fr.calls[0]["url"] and fr.calls[0]["url"].endswith("/sendMessage")
    assert fr.calls[0]["json"]["chat_id"] == "42"
    assert fr.calls[0]["json"]["text"] == "작업 확인 필요"


def test_network_error_swallowed():
    fr = _FakeReq(exc=RuntimeError("down"))
    assert notify.send_telegram("x", token="T", chat_id="1", _requests=fr) is False


def test_reads_env(monkeypatch):
    monkeypatch.setenv("SHORTS_TELEGRAM_TOKEN", "ENVTOK")
    monkeypatch.setenv("SHORTS_TELEGRAM_CHAT_ID", "99")
    fr = _FakeReq()
    assert notify.send_telegram("y", _requests=fr) is True
    assert "ENVTOK" in fr.calls[0]["url"] and fr.calls[0]["json"]["chat_id"] == "99"
