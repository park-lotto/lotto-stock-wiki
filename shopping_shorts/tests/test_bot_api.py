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
