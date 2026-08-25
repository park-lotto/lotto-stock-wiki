"""카톡 답변봇 순수 로직 — DB·HTTP를 모른다(테스트가 DB 없이 돈다)."""
import pytest

from shopping_shorts import bot_qa


# ── 호출어 ──────────────────────────────────────────────────────────
def test_bang_question_is_parsed():
    assert bot_qa.parse_command("!질문 포인트 어떻게 사요") == "포인트 어떻게 사요"


def test_bang_alone_without_text_is_ignored():
    assert bot_qa.parse_command("!질문") is None
    assert bot_qa.parse_command("!질문   ") is None


def test_plain_message_is_ignored():
    """★호출 안 된 말에 답하면 방이 시끄럽고 정지 위험이 커진다."""
    assert bot_qa.parse_command("안녕하세요") is None
    assert bot_qa.parse_command("포인트 어떻게 사요?") is None


def test_bang_without_keyword_also_works():
    """'!' 뒤에 바로 물어도 받는다 — 사장님이 외우기 쉬운 쪽이 이긴다."""
    assert bot_qa.parse_command("!포인트 어떻게 사요") == "포인트 어떻게 사요"


# ── 민감어 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("q", [
    "환불 해주세요", "결제가 안 돼요", "계좌 알려주세요",
    "입금했는데요", "카드 등록 어떻게",
])
def test_money_questions_are_sensitive(q):
    """★돈 얘기를 봇이 잘못 답하면 분쟁이 된다 — AI를 아예 안 거친다."""
    assert bot_qa.is_sensitive(q) is True


def test_normal_question_is_not_sensitive():
    assert bot_qa.is_sensitive("영상 몇 개까지 만들 수 있어요") is False


# ── 길이 ────────────────────────────────────────────────────────────
def test_long_answer_is_trimmed():
    """카톡에서 잘리면 안 보인다 — 우리가 먼저 자른다."""
    out = bot_qa.trim("가" * 5000)
    assert len(out) <= bot_qa.MAX_REPLY
    assert out.endswith("…")


def test_short_answer_is_untouched():
    assert bot_qa.trim("짧은 답") == "짧은 답"


# ── 검색 ────────────────────────────────────────────────────────────
QA = [
    {"id": 1, "room": "공통", "question": "포인트는 어떻게 사나요",
     "answer": "설정 화면에서 충전합니다.", "tags": "포인트 충전 결제"},
    {"id": 2, "room": "공통", "question": "영상은 몇 개까지 만들 수 있나요",
     "answer": "포인트가 있는 만큼 만듭니다.", "tags": "영상 제작 개수"},
    {"id": 3, "room": "체험단", "question": "챌린지는 하루 몇 개 올리나요",
     "answer": "하루 2개입니다.", "tags": "챌린지 제출 하루"},
]


def test_search_finds_relevant_item():
    hits = bot_qa.search("포인트 충전하고 싶어요", QA, room="문의")
    assert hits and hits[0]["id"] == 1


def test_search_returns_empty_for_unrelated_question():
    """★자료에 없으면 빈 손으로 온다 → 호출부가 AI를 안 부른다(지어내기 차단)."""
    assert bot_qa.search("오늘 날씨 어때요", QA, room="문의") == []


def test_search_limits_to_top_n():
    """수백 개로 늘어도 3~5개만 먹인다 — 느려지지도 비싸지지도 않는다."""
    many = [dict(QA[0], id=i) for i in range(100)]
    assert len(bot_qa.search("포인트", many, room="문의")) <= bot_qa.TOP_N


def test_challenge_room_prefers_challenge_material():
    """체험단방에선 챌린지 자료를 먼저 본다."""
    hits = bot_qa.search("하루 몇 개", QA, room="체험단")
    assert hits[0]["id"] == 3


def test_challenge_only_material_hidden_in_other_room():
    """체험단 전용 자료가 문의방으로 새면 안 된다."""
    hits = bot_qa.search("챌린지 하루 몇 개", QA, room="문의")
    assert all(h["room"] != "체험단" for h in hits)
