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
    """호출마다 다른 키를 준다 — 한 키만 때리던 버그(성공률 7%)의 회귀 방지.

    ⚠️ 4번째 호출까지 `[0,1,2,0]`을 기대하지 않는다(2026-08-09 수정).
    페이서가 키당 최소 간격(_MIN_GAP_S = 60/5 = 12초)을 지키므로, 키 3개를 한
    바퀴 돈 뒤엔 **가장 먼저 풀리는 키가 풀릴 때까지 잔다**. 옛 기대값은
    _RPM_PER_KEY=15(간격 4초)를 전제로 쓴 것인데 그 값 자체가 실측과 달라
    429를 자초하던 원인이었다(실측 한도는 분당 5). 여기서 검증할 것은
    '한 바퀴 안에서 키가 겹치지 않는다'이지 커서의 산술이 아니다.
    """
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k0", "k1", "k2"])
    monkeypatch.setattr(comment_gen, "_load_state", _no_exhausted)
    comment_gen._rr_cursor["i"] = 0
    comment_gen._key_last_used.clear()   # 다른 테스트가 남긴 사용시각을 지운다
    got = [comment_gen._next_live_key_and_idx()[1] for _ in range(3)]
    assert sorted(got) == [0, 1, 2], "한 바퀴 안에서는 3개 키를 겹치지 않고 다 쓴다"


def _setup(monkeypatch, clients_by_key, marks):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k0", "k1", "k2"])
    monkeypatch.setattr(comment_gen, "_load_state", _no_exhausted)
    monkeypatch.setattr(comment_gen, "_client_for_key",
                        lambda key: _FakeClient(clients_by_key[key]))
    monkeypatch.setattr(comment_gen, "_mark_key_exhausted", lambda idx: marks.append(idx))
    comment_gen._rr_cursor["i"] = 0
    # 앞선 테스트가 남긴 키 사용시각을 지운다(2026-08-09). 안 지우면 페이서가
    # 쿨다운으로 12초를 자며 다른 키를 골라 이 테스트가 단독으론 통과하고
    # 전체 실행에선 실패한다 — 순서 의존 테스트가 된다.
    comment_gen._key_last_used.clear()


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
