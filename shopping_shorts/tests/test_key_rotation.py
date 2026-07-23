"""제미니 키풀 로테이션 — 45개 키가 있어도 1번 키만 쓰던 버그 수정(2026-07-23).

두 버그: (1) _current_key_and_idx가 항상 live[0] → 라운드로빈 없음.
(2) _default_call이 분당 429(PerMinute)를 교체 신호로 안 봐 즉시 None → 재시도·교체 없음.
결과 성공률 7%. 라운드로빈 + 분당429 재시도로 고친다."""
import json
from shopping_shorts import comment_gen, pattern_bank


def _no_exhausted(*a, **k):
    return {"date": "x", "exhausted": []}


class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, behavior):
        self._b = behavior

    def generate_content(self, model=None, contents=None, config=None):
        b = self._b
        if isinstance(b, Exception):
            raise b
        return _FakeResp(b)


class _FakeClient:
    def __init__(self, behavior):
        self.models = _FakeModels(behavior)


def test_round_robin_cycles(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k0", "k1", "k2"])
    monkeypatch.setattr(comment_gen, "_load_state", _no_exhausted)
    comment_gen._rr_cursor["i"] = 0
    got = [comment_gen._next_live_key_and_idx()[1] for _ in range(4)]
    assert got == [0, 1, 2, 0]                 # 호출마다 다음 키, 끝나면 처음으로


def _setup(monkeypatch, clients_by_key, marks):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k0", "k1", "k2"])
    monkeypatch.setattr(comment_gen, "_load_state", _no_exhausted)
    monkeypatch.setattr(comment_gen, "_client_for_key",
                        lambda key: _FakeClient(clients_by_key[key]))
    monkeypatch.setattr(comment_gen, "_mark_key_exhausted", lambda idx: marks.append(idx))
    comment_gen._rr_cursor["i"] = 0


_PER_MIN = Exception("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerMinutePerProjectPerModel-FreeTier limit: 15")
_PER_DAY = Exception("429 RESOURCE_EXHAUSTED PerDay limit: 500")
_OK = json.dumps({"hook": ["훅"]})


def test_per_minute_429_rotates_without_exhausting(monkeypatch):
    marks = []
    # k0=분당429, k1=성공 → 라운드로빈이 k0→k1로 넘어가 성공, k0은 영구제외 안 함
    _setup(monkeypatch, {"k0": _PER_MIN, "k1": _OK, "k2": _OK}, marks)
    res = pattern_bank._default_call("p", {"type": "object"})
    assert res == {"hook": ["훅"]}
    assert marks == []                         # 분당 한도는 일시적 → 소진 마킹 금지


def test_daily_429_marks_exhausted(monkeypatch):
    marks = []
    _setup(monkeypatch, {"k0": _PER_DAY, "k1": _OK, "k2": _OK}, marks)
    res = pattern_bank._default_call("p", {"type": "object"})
    assert res == {"hook": ["훅"]}
    assert marks == [0]                        # 일일 소진은 그날 제외
