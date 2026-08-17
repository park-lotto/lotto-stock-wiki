"""SerpApi 실잔량 가드 (2026-08-17).

왜 있나 — 우리 `lens_count`는 클릭당 1인데 실제로는 로케일 3벌 × 재시도로 최대
3회가 나간다. 서버 실측: 우리 카운터 196/500인데 실제 SerpApi는 369/500 소진
(남은 131). 카운터만 믿으면 키가 다 죽는 순간 렌즈가 조용히 빈손이 된다.

네트워크는 안 탄다(requests를 통째로 가짜로 바꾼다).
"""
import pytest

from shopping_shorts import lens_discover


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        if self._p is _BAD_JSON:
            raise ValueError("not json")
        return self._p


_BAD_JSON = object()


class _FakeRequests:
    """키별 응답을 미리 정해두고 호출 횟수를 센다."""

    RequestException = Exception

    def __init__(self, by_key):
        self.by_key = by_key
        self.calls = []

    def get(self, url, params=None, timeout=None):
        key = (params or {}).get("api_key")
        self.calls.append(key)
        v = self.by_key[key]
        if isinstance(v, Exception):
            raise v
        return v


@pytest.fixture(autouse=True)
def _clear_cache():
    lens_discover._quota_cache["at"] = 0.0
    lens_discover._quota_cache["left"] = None
    yield
    lens_discover._quota_cache["at"] = 0.0
    lens_discover._quota_cache["left"] = None


def _patch(monkeypatch, keys, by_key):
    monkeypatch.setattr(lens_discover, "SERPAPI_KEYS", keys)
    monkeypatch.setattr(lens_discover, "SERPAPI_KEY", keys[0] if keys else "")
    fake = _FakeRequests(by_key)
    monkeypatch.setattr(lens_discover, "requests", fake)
    return fake


def test_sums_left_across_keys(monkeypatch):
    """실측 그대로: 키1 소진(0) + 키2 131 = 131."""
    _patch(monkeypatch, ["k1", "k2"], {
        "k1": _Resp({"total_searches_left": 0, "searches_per_month": 250}),
        "k2": _Resp({"total_searches_left": 131, "searches_per_month": 250}),
    })
    assert lens_discover.account_searches_left() == 131


def test_unreadable_returns_none_not_zero(monkeypatch):
    """한 키도 못 읽으면 '모른다'(None). 0으로 뭉개면 멀쩡한데 렌즈를 막는다."""
    _patch(monkeypatch, ["k1", "k2"], {
        "k1": _FakeRequests.RequestException("boom"),
        "k2": _Resp({"error": "Invalid API key"}, status=401),
    })
    assert lens_discover.account_searches_left() is None


def test_partial_read_counts_only_what_was_read(monkeypatch):
    """일부만 읽혀도 읽힌 값은 쓴다(전부 실패일 때만 None)."""
    _patch(monkeypatch, ["k1", "k2"], {
        "k1": _Resp(_BAD_JSON),
        "k2": _Resp({"total_searches_left": 40}),
    })
    assert lens_discover.account_searches_left() == 40


def test_non_numeric_left_is_ignored(monkeypatch):
    """문자열·None을 int로 뭉개 0을 만들지 않는다."""
    _patch(monkeypatch, ["k1"], {"k1": _Resp({"total_searches_left": "many"})})
    assert lens_discover.account_searches_left() is None


def test_cached_within_ttl_then_refetched(monkeypatch):
    """렌즈 호출마다 왕복하지 않는다 — TTL 안에서는 캐시."""
    fake = _patch(monkeypatch, ["k1"], {"k1": _Resp({"total_searches_left": 7})})
    assert lens_discover.account_searches_left() == 7
    assert lens_discover.account_searches_left() == 7
    assert len(fake.calls) == 1, "TTL 안인데 두 번 왕복했다"
    lens_discover._quota_cache["at"] -= (lens_discover._QUOTA_TTL_S + 1)
    assert lens_discover.account_searches_left() == 7
    assert len(fake.calls) == 2, "TTL이 지났는데 갱신하지 않았다"


def test_force_bypasses_cache(monkeypatch):
    fake = _patch(monkeypatch, ["k1"], {"k1": _Resp({"total_searches_left": 7})})
    lens_discover.account_searches_left()
    lens_discover.account_searches_left(force=True)
    assert len(fake.calls) == 2


def test_no_keys_returns_none(monkeypatch):
    _patch(monkeypatch, [], {})
    assert lens_discover.account_searches_left() is None


# ── 가드(app) 쪽 ─────────────────────────────────────────────────────────

class _Store:
    def __init__(self, count=0, override=""):
        self._c = count
        self._o = override

    def lens_month_count(self, month):
        return self._c

    def get_setting(self, k, d=""):
        return self._o if k == "lens_month_limit" else d


def _guard(monkeypatch, left, store):
    from shopping_shorts import app as appmod
    monkeypatch.setattr(lens_discover, "account_searches_left",
                        lambda *a, **kw: left)
    return appmod._lens_quota_guard(store, "2026-08")


def test_guard_blocks_when_real_quota_zero_even_if_counter_low(monkeypatch):
    """★핵심 회귀 — 우리 카운터는 여유(196)인데 실잔량 0이면 막아야 한다."""
    r = _guard(monkeypatch, 0, _Store(count=196))
    assert r is not None and r.status_code == 429


def test_guard_passes_when_real_quota_left(monkeypatch):
    assert _guard(monkeypatch, 131, _Store(count=196)) is None


def test_guard_falls_back_to_counter_when_quota_unknown(monkeypatch):
    """실잔량을 못 읽어도 기존 카운터 가드는 살아 있어야 한다."""
    assert _guard(monkeypatch, None, _Store(count=999999)) is not None
    assert _guard(monkeypatch, None, _Store(count=0)) is None
