from tg_bot.probe import ProbeError
from tg_bot.run import handle


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


URL = "https://shoppingshorts.duckdns.org/produce?job_id=j9"


def test_주소가_있으면_그_job을_조사한다():
    p = FakeProber({"status": "done"})
    handle("안 돼요 " + URL, p)
    assert p.asked == ["j9"]


def test_실패한_작업은_원인과_고객문구를_준다():
    p = FakeProber({"status": "failed", "error": "gemini 키 소진"})
    out = handle("안 돼요 " + URL, p)
    assert "【원인】" in out
    assert "【고객께 보낼 문구】" in out


def test_주소가_없으면_주소를_달라고_한다():
    p = FakeProber({"status": "done"})
    out = handle("그냥 안 돼요", p)
    assert "주소" in out
    assert p.asked == []          # 조사하지 않는다


def test_조사에_실패하면_사유를_그대로_전한다():
    """★'조사 실패'로 뭉개지 않는다 — 무엇이 문제인지 보여야 고친다."""
    p = FakeProber(error="작업 j9 을(를) 찾을 수 없습니다. 주소가 맞는지 확인해 주세요.")
    out = handle("안 돼요 " + URL, p)
    assert "찾을 수 없" in out


def test_환불_문의는_경고가_붙는다():
    p = FakeProber({"status": "failed", "error": "x"})
    out = handle("환불해주세요 " + URL, p)
    assert "직접 확인" in out
