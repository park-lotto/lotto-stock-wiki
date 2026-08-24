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
