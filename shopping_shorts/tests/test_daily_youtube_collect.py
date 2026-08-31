import pytest

import shopping_shorts.store as store_mod
from scripts import daily_youtube_collect as dyc


class _FakeStore:
    """main()이 쓰는 Store 표면만 흉내낸다.

    ★실 DB를 쓰면 안 된다(2026-08-31): main()이 성공 시 settings에 '오늘 수집 완료'
    표식을 남기도록 바뀌었는데, 테스트가 그걸 라이브 DB에 쓰면 그날 진짜 수집이
    "이미 완료"로 건너뛰어진다 — 테스트가 운영을 망가뜨린다.
    (표식을 안 지우면 테스트끼리도 오염된다: 실제로 첫 테스트가 남긴 표식 때문에
     두 번째 테스트가 조기 종료해 실패했다.)"""

    saved = {}

    def __init__(self, *_a, **_k):
        pass

    def get_setting(self, key, default=None):
        return self.saved.get(key, default)

    def set_setting(self, key, value):
        self.saved[key] = value

    def heavy_job_active(self):
        return False


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch):
    _FakeStore.saved = {}
    monkeypatch.setattr(store_mod, "Store", _FakeStore)


def test_main_collects_youtube_free_path(monkeypatch):
    calls = {}
    def fake_collect(platform, seed_only=False):
        calls["platform"] = platform
        calls["seed_only"] = seed_only
        return [{"shortcode": "a"}]

    monkeypatch.setattr(dyc.service, "collect", fake_collect)
    rc = dyc.main()
    assert rc == 0
    assert calls["platform"] == "youtube"   # 인스타(유료) 아님
    # 2026-07-29: seed_only는 구현돼 있으나 아직 켜지 않는다.
    # 미등록 우량 채널을 시드에 먼저 넣기 전에 켜면 수집량이 급감한다(설계 §T3 → §T4 순서).
    # register_good_youtube_channels.py 실행 후 True로 바꾸고 이 단언도 True로 뒤집는다.
    assert calls["seed_only"] is False


def test_main_survives_exception(monkeypatch):
    def boom(platform, seed_only=False):
        raise RuntimeError("api down")
    monkeypatch.setattr(dyc.service, "collect", boom)
    assert dyc.main() == 1                   # 예외 삼키고 비정상 종료코드만


def test_skips_when_already_collected_today(monkeypatch):
    """같은 날 두 번째 회차는 수집하지 않는다 — 타이머를 여러 번 돌려도 중복이 없다."""
    calls = []
    monkeypatch.setattr(dyc.service, "collect",
                        lambda platform, seed_only=False: calls.append(platform) or [{"shortcode": "a"}])
    assert dyc.main() == 0
    assert calls == ["youtube"]              # 1회차: 실제 수집
    assert dyc.main() == 0
    assert calls == ["youtube"]              # 2회차: 표식 보고 건너뜀


def test_render_busy_leaves_no_done_mark(monkeypatch):
    """렌더 중 양보는 '오늘 완료'가 아니다 — 표식이 남으면 그날 재시도가 통째로 죽는다."""
    monkeypatch.setattr(_FakeStore, "heavy_job_active", lambda self: True)
    called = []
    monkeypatch.setattr(dyc.service, "collect",
                        lambda platform, seed_only=False: called.append(1) or [])
    assert dyc.main() == 0
    assert called == []                      # 수집 안 함
    assert _FakeStore.saved == {}            # ★표식도 안 남김 → 다음 회차가 다시 시도한다
