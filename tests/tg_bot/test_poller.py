from tg_bot.poller import Telegram


class FakeResp:
    def __init__(self, data=None, code=200):
        self._data = data or {}
        self.status_code = code

    def json(self):
        return self._data


class FakeRequests:
    def __init__(self, updates=None):
        self.updates = updates or []
        self.posted = []

    def get(self, url, params=None, timeout=None):
        return FakeResp({"result": self.updates})

    def post(self, url, json=None, timeout=None):
        self.posted.append(json)
        return FakeResp(code=200)


def _update(uid, chat_id, text):
    return {"update_id": uid, "message": {"chat": {"id": chat_id}, "text": text}}


def test_사장님_메시지는_받는다():
    r = FakeRequests([_update(1, 777, "안녕")])
    tg = Telegram("tok", "777", requests_mod=r)
    assert tg.poll() == ["안녕"]


def test_남의_메시지는_무시한다():
    """★보안 경계. 봇 이름을 알아낸 남이 말을 걸 수 있다."""
    r = FakeRequests([_update(1, 999, "나쁜짓")])
    tg = Telegram("tok", "777", requests_mod=r)
    assert tg.poll() == []


def test_섞여_있으면_사장님_것만():
    r = FakeRequests([_update(1, 999, "남"), _update(2, 777, "나")])
    tg = Telegram("tok", "777", requests_mod=r)
    assert tg.poll() == ["나"]


def test_같은_메시지를_두_번_주지_않는다():
    """offset이 올라가야 다음 폴링에서 같은 걸 또 처리하지 않는다."""
    r = FakeRequests([_update(5, 777, "한번만")])
    tg = Telegram("tok", "777", requests_mod=r)
    tg.poll()
    r.updates = []
    assert tg.poll() == []
    assert tg._offset == 6


def test_텍스트가_없는_메시지는_건너뛴다():
    r = FakeRequests([{"update_id": 1, "message": {"chat": {"id": 777}}}])
    tg = Telegram("tok", "777", requests_mod=r)
    assert tg.poll() == []


def test_발송은_chat_id를_실어_보낸다():
    r = FakeRequests()
    tg = Telegram("tok", "777", requests_mod=r)
    assert tg.send("답변") is True
    assert r.posted == [{"chat_id": "777", "text": "답변"}]


def test_토큰이_없으면_보내지_않는다():
    r = FakeRequests()
    tg = Telegram("", "777", requests_mod=r)
    assert tg.send("x") is False
    assert r.posted == []


def test_무엇이_없는지_이름으로_말한다():
    """★'설정 오류'로 뭉개지 않는다."""
    assert Telegram("", "", requests_mod=FakeRequests()).missing() == [
        "SHORTS_TELEGRAM_TOKEN", "SHORTS_TELEGRAM_CHAT_ID"]
    assert Telegram("tok", "", requests_mod=FakeRequests()).missing() == [
        "SHORTS_TELEGRAM_CHAT_ID"]


def test_네트워크가_죽어도_봇은_안_죽는다():
    class Boom:
        def get(self, *a, **k):
            raise OSError("끊김")

        def post(self, *a, **k):
            raise OSError("끊김")

    tg = Telegram("tok", "777", requests_mod=Boom())
    assert tg.poll() == []
    assert tg.send("x") is False
