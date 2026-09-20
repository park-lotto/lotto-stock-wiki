from tg_bot.setup_helper import fetch_chat_ids, upsert_env


class FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeRequests:
    def __init__(self, data):
        self.data = data

    def get(self, url, timeout=None):
        return FakeResp(self.data)


def _up(uid, cid):
    return {"update_id": uid, "message": {"chat": {"id": cid}, "text": "안녕"}}


def test_chat_id를_뽑는다():
    r = FakeRequests({"result": [_up(1, 777)]})
    ids, err = fetch_chat_ids("tok", requests_mod=r)
    assert ids == ["777"] and err is None


def test_같은_id는_한_번만():
    r = FakeRequests({"result": [_up(1, 777), _up(2, 777)]})
    ids, _ = fetch_chat_ids("tok", requests_mod=r)
    assert ids == ["777"]


def test_토큰이_거부되면_사유를_말한다():
    r = FakeRequests({"ok": False, "description": "Unauthorized"})
    ids, err = fetch_chat_ids("나쁜토큰", requests_mod=r)
    assert ids is None and "Unauthorized" in err


def test_말을_안_걸었으면_빈_목록():
    r = FakeRequests({"result": []})
    ids, err = fetch_chat_ids("tok", requests_mod=r)
    assert ids == [] and err is None


def test_env에_새로_넣는다(tmp_path):
    p = tmp_path / ".env"
    upsert_env({"A": "1"}, path=str(p))
    assert "A=1" in p.read_text(encoding="utf-8")


def test_기존_키를_날리지_않는다(tmp_path):
    """★.env 에는 API 키가 들어 있다. 덮어쓰면 다른 기능이 통째로 죽는다."""
    p = tmp_path / ".env"
    p.write_text("GEMINI_KEY=소중한값\nDASH_PASS=비번\n", encoding="utf-8")
    upsert_env({"SHORTS_TELEGRAM_TOKEN": "tok"}, path=str(p))
    body = p.read_text(encoding="utf-8")
    assert "GEMINI_KEY=소중한값" in body
    assert "DASH_PASS=비번" in body
    assert "SHORTS_TELEGRAM_TOKEN=tok" in body


def test_같은_키는_갱신한다(tmp_path):
    p = tmp_path / ".env"
    p.write_text("SHORTS_TELEGRAM_TOKEN=옛날\n", encoding="utf-8")
    upsert_env({"SHORTS_TELEGRAM_TOKEN": "새것"}, path=str(p))
    body = p.read_text(encoding="utf-8")
    assert "새것" in body and "옛날" not in body
    assert body.count("SHORTS_TELEGRAM_TOKEN") == 1
