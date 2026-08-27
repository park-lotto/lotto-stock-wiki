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
    # 캐시는 **키 조합별**로 나뉜다(2026-08-27) — 공용(0회)으로 채워진 값이 개인 키
    # 판정을 오염시키면 자기 키가 멀쩡한 회원이 계속 막힌다. 그래서 통째로 비운다.
    lens_discover._quota_cache.clear()
    yield
    lens_discover._quota_cache.clear()


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
    for _e in lens_discover._quota_cache.values():
        _e["at"] -= (lens_discover._QUOTA_TTL_S + 1)
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


# ── 회원은 자기 키 잔량으로 판정한다 — 2026-08-27 실사고 ────────────────────────

def test_keys_arg_overrides_owner_pool(monkeypatch):
    """★공용이 0이어도 자기 키가 남았으면 그 값을 봐야 한다.

    실사고: 공용 env 키 5개가 전부 소진되자, 자기 키에 200회씩 남은 회원 24명이
    통째로 429로 막혔다("렌즈 끝났다" 문의가 몰린 진짜 원인). 게이트가 누가
    요청했는지를 안 보고 공용 키만 조회한 탓이다.
    """
    _patch(monkeypatch, ["공용1"], {"공용1": _Resp({"total_searches_left": 0}),
                                    "내키": _Resp({"total_searches_left": 201})})
    assert lens_discover.account_searches_left() == 0            # 공용 기준
    assert lens_discover.account_searches_left(keys=["내키"]) == 201   # 내 키 기준


def test_cache_is_per_key_set(monkeypatch):
    """★캐시를 한 통에 담으면 공용(0)이 개인 판정을 오염시켜 고친 게 도로 막힌다."""
    fake = _patch(monkeypatch, ["공용1"], {"공용1": _Resp({"total_searches_left": 0}),
                                           "내키": _Resp({"total_searches_left": 201})})
    assert lens_discover.account_searches_left() == 0
    assert lens_discover.account_searches_left(keys=["내키"]) == 201
    # 각자 캐시를 타므로 재조회 없이도 값이 유지된다
    assert lens_discover.account_searches_left() == 0
    assert lens_discover.account_searches_left(keys=["내키"]) == 201
    assert len(fake.calls) == 2, "키 조합별로 한 번씩만 왕복해야 한다"
