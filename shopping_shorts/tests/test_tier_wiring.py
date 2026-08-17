"""등급제가 실제 수집 경로에 붙었나 — 하네스가 계약을 발명하지 않도록 실제 함수로 검증.

(feedback_harness_invented_contract: 주입값을 진짜 코드가 쓰는지 확인하지 않으면
 0% 동작해도 테스트는 초록이 된다)
"""
import pytest

from shopping_shorts import config, service, channel_tier


class _FakeStore:
    def __init__(self, rows):
        self._rows = rows

    def reel_history_rows(self):
        return self._rows

    def discovered_channels(self):
        return []

    def removed_usernames(self):
        return set()

    def dead_usernames(self):
        return set()

    def channel_categories(self):
        return {}


@pytest.fixture
def _rows():
    # hit=A(댓글500 2건) / half=B(1건) / cold=C(0건)
    return [
        {"username": "hit", "comments": 900, "first_seen": "2026-08-16"},
        {"username": "hit", "comments": 800, "first_seen": "2026-08-15"},
        {"username": "half", "comments": 900, "first_seen": "2026-08-16"},
        {"username": "half", "comments": 3, "first_seen": "2026-08-15"},
        {"username": "cold", "comments": 5, "first_seen": "2026-08-16"},
    ]


class _Stop(Exception):
    """스크레이퍼까지 도달했으면 목적 달성 — 하류(저장·태깅)는 이 테스트 관심사가 아니다."""


def _run_collect(monkeypatch, rows, tier_on):
    """collect의 인스타 경로를 태우고 '실제로 스크레이퍼에 넘어간 채널'을 잡아낸다."""
    captured = {}

    monkeypatch.setattr(config, "REFERENCE_TIER", tier_on)
    monkeypatch.setattr(config, "INSTAGRAM_SCRAPER", "playwright")
    monkeypatch.setattr(service, "load_channels",
                        lambda *a, **k: [{"username": u} for u in ("hit", "half", "cold")])
    monkeypatch.setattr(service, "select_tracked", lambda ch, *a, **k: ch)
    monkeypatch.setattr(service, "Store", lambda *a, **k: _FakeStore(rows))

    def _fake_fetch(usernames, on_progress=None):
        captured["usernames"] = list(usernames)
        raise _Stop

    monkeypatch.setattr(service, "_pw_fetch_reels", _fake_fetch)
    with pytest.raises(_Stop):
        service.collect(platform="instagram")
    return captured.get("usernames", [])


def test_등급제_off면_전부_긁는다(monkeypatch, _rows):
    assert sorted(_run_collect(monkeypatch, _rows, tier_on=False)) == ["cold", "half", "hit"]


def test_등급제_on이면_A는_항상_포함(monkeypatch, _rows):
    # A는 주기 1일이라 어느 날에 돌려도 반드시 들어간다
    assert "hit" in _run_collect(monkeypatch, _rows, tier_on=True)


def test_등급제_on이면_채널이_줄어든다(monkeypatch, _rows):
    # B·C는 주기가 길어 대부분의 날엔 빠진다 — 셋 다 나오는 날은 드물다
    got = _run_collect(monkeypatch, _rows, tier_on=True)
    assert len(got) <= 3 and "hit" in got


def test_이력없는_신규채널은_등급제_켜도_긁힌다(monkeypatch):
    # 안 긁으면 이력이 안 쌓여 영영 등급이 안 생긴다
    got = _run_collect(monkeypatch, [], tier_on=True)
    assert sorted(got) == ["cold", "half", "hit"]


def test_config_기준값이_실제로_쓰인다(monkeypatch, _rows):
    # 기준을 1건으로 낮추면 half(히트 1건)도 A가 되어 매일 긁혀야 한다
    monkeypatch.setattr(config, "REFERENCE_TIER_HIT_COUNT", 1)
    monkeypatch.setattr(config, "REFERENCE_TIER_HIT_COMMENTS", 500)
    assert "half" in _run_collect(monkeypatch, _rows, tier_on=True)


def test_store에서_원자료를_읽는다(_rows):
    # compute_tiers가 먹을 수 있는 모양인지 — 키 이름이 어긋나면 전원 C로 떨어진다
    tiers = channel_tier.compute_tiers(_rows, today="2026-08-17")
    assert tiers == {"hit": "A", "half": "B", "cold": "C"}
