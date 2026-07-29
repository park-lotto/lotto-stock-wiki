"""추출 안정화(2026-07-29): 제미니 파일 PROCESSING 대기가 60초로 조급해 '조금 느린' 영상이
빈 추출로 실패→대본이 짧아졌다(5a8e089d 10초 실사고). 대기 상한을 넉넉히 올려 실제로 준비될
때까지 기다리게 한다. 실패는 진짜 처리불가일 때만.
"""
import types as _t
from shopping_shorts import video_analysis as va


class _FakeState:
    def __init__(self, name):
        self.name = name


class _FakeFile:
    def __init__(self, states):
        # states: 순차로 반환할 상태 이름들(마지막이 최종)
        self._states = list(states)
        self.name = "files/fake"
        self.state = _FakeState(self._states[0])


class _FakeClient:
    """files.get를 부를 때마다 다음 상태로 전이하는 스텁."""
    def __init__(self, file_obj):
        self._f = file_obj
        self.files = _t.SimpleNamespace(get=self._get)

    def _get(self, name=None):
        if len(self._f._states) > 1:
            self._f._states.pop(0)
        self._f.state = _FakeState(self._f._states[0])
        return self._f


def test_wait_cap_is_generous():
    """조급한 60초가 아니라 넉넉한(>=180초) 상한이어야 '조금 느린' 영상이 성공한다."""
    import inspect
    sig = inspect.signature(va._wait_until_active)
    assert sig.parameters["max_wait_s"].default >= 180


def test_wait_returns_when_active(monkeypatch):
    """PROCESSING 몇 번 뒤 ACTIVE가 되면 그 파일을 반환(폴링 지속)."""
    monkeypatch.setattr(va.time, "sleep", lambda s: None)   # 테스트 빠르게
    f = _FakeFile(["PROCESSING", "PROCESSING", "ACTIVE"])
    client = _FakeClient(f)
    out = va._wait_until_active(client, f, max_wait_s=180, poll_interval=2)
    assert out.state.name == "ACTIVE"


def test_wait_raises_only_after_cap(monkeypatch):
    """상한까지 계속 PROCESSING이면 그때만 실패(진짜 처리불가)."""
    monkeypatch.setattr(va.time, "sleep", lambda s: None)
    f = _FakeFile(["PROCESSING"])   # 영원히 PROCESSING
    client = _FakeClient(f)
    try:
        va._wait_until_active(client, f, max_wait_s=6, poll_interval=2)
        assert False, "실패를 던져야 한다"
    except RuntimeError as e:
        assert "PROCESSING" in str(e)
