"""카톡 답변봇 저장소·라우트 테스트."""
import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_add_and_list_qa(store):
    qid = store.bot_qa_add(room="공통", question="포인트?", answer="충전하세요",
                           tags="포인트", source="handoff/x.md")
    rows = store.bot_qa_list()
    assert len(rows) == 1 and rows[0]["id"] == qid
    assert rows[0]["status"] == "draft", "새 항목은 초안으로 시작해야 한다"


def test_only_approved_are_served(store):
    store.bot_qa_add(room="공통", question="A?", answer="a", tags="", source="")
    ok = store.bot_qa_add(room="공통", question="B?", answer="b", tags="", source="")
    store.bot_qa_set_status(ok, "approved")
    served = store.bot_qa_list(status="approved")
    assert [r["id"] for r in served] == [ok], "미승인 초안이 새어나가면 안 된다"


def test_update_answer_keeps_id(store):
    qid = store.bot_qa_add(room="공통", question="A?", answer="a", tags="", source="")
    store.bot_qa_update(qid, question="A?", answer="고친 답", tags="t")
    assert store.bot_qa_list()[0]["answer"] == "고친 답"


def test_unanswered_same_question_is_counted_not_duplicated(store):
    """같은 질문이 반복되면 묶어서 센다 — 뭐가 자주 나오는지 보여야 한다."""
    store.bot_unanswered_add("문의", "이거 어떻게 써요")
    store.bot_unanswered_add("문의", "이거 어떻게 써요")
    rows = store.bot_unanswered_list()
    assert len(rows) == 1 and rows[0]["count"] == 2


# ── 라우트 ──────────────────────────────────────────────────────────
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """★/api/kakao/ask는 로그인 쿠키가 아니라 **자체 비밀키 헤더**로 막는다.
    그래서 여기선 DASH_PASS를 안 켠다(폰은 로그인을 못 한다 — 그게 설계다)."""
    monkeypatch.setenv("KAKAO_BOT_SECRET", "s3cret")
    from shopping_shorts import app as app_module
    monkeypatch.setattr(app_module, "DB_PATH", str(tmp_path / "t.db"))
    # ★_BOT_ASKED는 모듈 전역(프로세스 수명)이라 테스트끼리 하루상한 카운트가 새어든다
    # (실측: 순서상 우연히 통과했지만 상한 테스트가 진짜 0에서 시작 안 함) — 매 테스트 격리.
    app_module._BOT_ASKED.clear()
    return TestClient(app_module.app)


def _ask(client, text, room="문의", secret="s3cret"):
    return client.post("/api/kakao/ask",
                       headers={"X-Bot-Secret": secret},
                       json={"room": room, "sender": "홍길동", "text": text})


def test_wrong_secret_is_rejected(client):
    """★열어두면 아무나 우리 제미니 한도를 태운다."""
    assert _ask(client, "!질문 포인트", secret="nope").status_code == 401


def test_non_command_gets_no_reply(client):
    r = _ask(client, "그냥 잡담")
    assert r.status_code == 200 and r.json()["reply"] == ""


def test_unknown_question_is_recorded_not_invented(client):
    """★모르면 지어내지 말고 '확인해서 알려드릴게요' + 목록에 쌓는다."""
    r = _ask(client, "!질문 화성 갈 수 있나요")
    assert "확인" in r.json()["reply"]
    from shopping_shorts.store import Store
    from shopping_shorts import app as app_module
    rows = Store(app_module.DB_PATH).bot_unanswered_list()
    assert rows and rows[0]["question"] == "화성 갈 수 있나요"


def test_sensitive_question_skips_ai(client, monkeypatch):
    """돈 얘기는 AI를 안 거치고 사람 연결로 간다."""
    from shopping_shorts import bot_answer
    monkeypatch.setattr(bot_answer, "_call",
                        lambda p: pytest.fail("민감 질문에 AI를 불렀다"))
    r = _ask(client, "!질문 환불 해주세요")
    assert r.status_code == 200 and r.json()["reply"]


def test_kill_switch_stops_everything(client):
    """긴급 정지 — 폰을 안 만지고 서버 설정 한 줄로 멈춘다."""
    from shopping_shorts.store import Store
    from shopping_shorts import app as app_module
    Store(app_module.DB_PATH).set_setting("kakao_bot_enabled", "0")
    assert _ask(client, "!질문 아무거나").json()["reply"] == ""


def test_daily_limit_per_sender(client, monkeypatch):
    """사람당 하루 상한 — 장난·도배 방지."""
    from shopping_shorts.store import Store
    from shopping_shorts import app as app_module
    Store(app_module.DB_PATH).set_setting("kakao_bot_daily_limit", "2")
    for _ in range(2):
        _ask(client, "!질문 화성 갈 수 있나요")
    assert _ask(client, "!질문 화성 갈 수 있나요").json()["reply"] == ""


def test_missing_server_secret_locks_the_route(tmp_path, monkeypatch):
    """★비밀키를 서버에 안 넣은 상태에서 **아무나 부를 수 있으면 안 된다**.

    2026-08-25 실측: 종전 비교식은 미설정("")과 헤더없음("")이 같아져 200을 줬다.
    사장님이 키를 나중에 넣는 게 정상 경로라, 그 사이에 열려 있으면 안 된다."""
    monkeypatch.delenv("KAKAO_BOT_SECRET", raising=False)
    from fastapi.testclient import TestClient
    from shopping_shorts import app as app_module
    monkeypatch.setattr(app_module, "DB_PATH", str(tmp_path / "t.db"))
    app_module._BOT_ASKED.clear()
    c = TestClient(app_module.app)
    r = c.post("/api/kakao/ask", json={"room": "문의", "sender": "x", "text": "!질문 테스트"})
    assert r.status_code == 401, "비밀키 미설정인데 라우트가 열려 있다"
    # 헤더를 아무렇게나 붙여도 마찬가지
    r2 = c.post("/api/kakao/ask", headers={"X-Bot-Secret": ""},
                json={"room": "문의", "sender": "x", "text": "!질문 테스트"})
    assert r2.status_code == 401
