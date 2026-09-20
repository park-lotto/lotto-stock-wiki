"""run.handle 의 갈림길 테스트.

★여기서 진짜 클로드를 부르면 안 된다 — 느리고(1건 60초+) 결과가 흔들린다.
  대화 경로는 반드시 `_ask` 스텁을 넣어 부른다.
"""
import pytest

from tg_bot.probe import ProbeError
from tg_bot.run import Session, handle


class FakeProber:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.asked = []

    def job(self, job_id):
        self.asked.append(job_id)
        if self.error:
            raise ProbeError(self.error)
        return self.result


class FakeAsk:
    """ask() 흉내 — 부른 인자를 기록한다."""

    def __init__(self, answer="클로드 답", sid="S1", raises=None):
        self.answer = answer
        self.sid = sid
        self.raises = raises
        self.calls = []

    def __call__(self, prompt, *, session_id=None, cwd=None, **kw):
        self.calls.append({"prompt": prompt, "session_id": session_id})
        if self.raises:
            raise self.raises
        return self.answer, self.sid


URL = "https://shoppingshorts.duckdns.org/produce?job_id=j9"


# ── ① 주소가 있으면 조사한다 ──────────────────────────────────────

def test_주소가_있으면_그_job을_조사한다():
    p = FakeProber({"status": "done"})
    handle("안 돼요 " + URL, p, _ask=FakeAsk())
    assert p.asked == ["j9"]


def test_주소가_있으면_클로드를_안_부른다():
    """★정확한 조회가 대화보다 낫다 — 추측이 안 섞인다."""
    a = FakeAsk()
    handle("안 돼요 " + URL, FakeProber({"status": "done"}), _ask=a)
    assert a.calls == []


def test_실패한_작업은_원인과_고객문구를_준다():
    p = FakeProber({"status": "failed", "error": "gemini 키 소진"})
    out = handle("안 돼요 " + URL, p, _ask=FakeAsk())
    assert "【원인】" in out
    assert "【고객께 보낼 문구】" in out


def test_조사에_실패하면_사유를_그대로_전한다():
    p = FakeProber(error="작업 j9 을(를) 찾을 수 없습니다.")
    out = handle("안 돼요 " + URL, p, _ask=FakeAsk())
    assert "찾을 수 없" in out


def test_환불_문의는_경고가_붙는다():
    p = FakeProber({"status": "failed", "error": "x"})
    out = handle("환불해주세요 " + URL, p, _ask=FakeAsk())
    assert "직접 확인" in out


# ── ② 주소가 없으면 대화한다 ──────────────────────────────────────

def test_주소가_없으면_클로드와_대화한다():
    a = FakeAsk(answer="그건 이렇습니다")
    out = handle("이 오류 왜 나?", FakeProber(), _ask=a)
    assert out == "그건 이렇습니다"
    assert a.calls[0]["prompt"] == "이 오류 왜 나?"


def test_첫_대화엔_세션이_없다():
    a = FakeAsk()
    handle("안녕", FakeProber(), Session(), _ask=a)
    assert a.calls[0]["session_id"] is None


def test_두_번째부터는_세션을_이어준다():
    """★이게 '대화가 이어진다'의 전부다."""
    a = FakeAsk(sid="S7")
    s = Session()
    handle("내 이름은 홍길동", FakeProber(), s, _ask=a)
    handle("내 이름 뭐지?", FakeProber(), s, _ask=a)
    assert a.calls[1]["session_id"] == "S7"


def test_새로_치면_맥락을_버린다():
    a = FakeAsk(sid="S7")
    s = Session()
    handle("안녕", FakeProber(), s, _ask=a)
    out = handle("/새로", FakeProber(), s, _ask=a)
    assert "새 대화" in out
    handle("또 안녕", FakeProber(), s, _ask=a)
    assert a.calls[-1]["session_id"] is None


def test_대화가_실패하면_사유를_보여준다():
    from tg_bot.ask import AskError
    a = FakeAsk(raises=AskError("claude 명령을 찾지 못했습니다."))
    out = handle("뭐 좀", FakeProber(), _ask=a)
    assert "찾지 못했" in out


def test_빈_메시지는_되묻는다():
    a = FakeAsk()
    out = handle("   ", FakeProber(), _ask=a)
    assert "무엇을" in out
    assert a.calls == []


@pytest.mark.parametrize("cmd", ["/새로", "/new", "/reset"])
def test_새로시작_명령_세_가지(cmd):
    s = Session()
    s.claude_id = "S9"
    handle(cmd, FakeProber(), s, _ask=FakeAsk())
    assert s.claude_id is None
