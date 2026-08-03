"""채널 아카이브 크롤러(2026-08-03) — run 오케스트레이션 계약(크롤은 모킹).

잠그는 것: ①대상 선정=(엑셀∪발굴)−차단−done, 팔로워 내림차순 ②성공 시 upsert+done
③로그인벽 2연속이면 회차 중단 ④렌더 진행 중이면 대기 후 재개(사용하면서 수집).
"""
import os
import tempfile
from unittest.mock import patch
import pytest
from shopping_shorts import channel_archive as ca
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _targets_env(store, excel, disc, removed=()):
    for u in removed:
        pass
    p1 = patch.object(ca, "load_channels", return_value=excel)
    p2 = patch.object(store.__class__, "discovered_channels", lambda self: disc)
    p3 = patch.object(store.__class__, "removed_usernames",
                      lambda self: set(removed))
    return p1, p2, p3


def test_pick_targets_orders_by_followers_and_excludes(store):
    excel = [{"username": "big", "followers": 100000},
             {"username": "mid", "followers": 500},
             {"username": "blocked", "followers": 999999}]
    disc = [{"username": "newbie", "followers": 0}]
    store.archive_mark("mid", "done", reels=3)
    p1, p2, p3 = _targets_env(store, excel, disc, removed=("blocked",))
    with p1, p2, p3:
        out = ca.pick_targets(store)
    assert out == ["big", "newbie"]    # done·차단 제외, 팔로워 내림차순


def test_run_saves_and_marks_done(store):
    excel = [{"username": "ch1", "followers": 10}]
    items = [{"shortcode": "AAA", "url": "u", "thumbnail": "t",
              "views": 5, "likes": 1, "comments": 2, "posted_at": "2026-01-01T00:00:00Z"}]
    p1, p2, p3 = _targets_env(store, excel, [])
    with p1, p2, p3, \
         patch.object(ca, "crawl_channel", return_value=(items, "https://x/reels/", None)), \
         patch.object(store.__class__, "heavy_job_running", lambda self: False), \
         patch.object(ca, "Store", return_value=store):
        ok = ca.run(sleep=lambda s: None, log=lambda *a: None)
    assert ok == 1
    assert store.archive_done_usernames() == {"ch1"}
    with store._conn() as c:
        row = c.execute("SELECT views FROM channel_archive WHERE shortcode='AAA'").fetchone()
    assert row[0] == 5


def test_run_stops_after_two_login_walls(store):
    excel = [{"username": f"c{i}", "followers": 10 - i} for i in range(4)]
    p1, p2, p3 = _targets_env(store, excel, [])
    calls = []
    with p1, p2, p3, \
         patch.object(ca, "crawl_channel",
                      side_effect=lambda u, **k: (calls.append(u) or
                                                  ([], "https://www.instagram.com/accounts/login", None))), \
         patch.object(store.__class__, "heavy_job_running", lambda self: False), \
         patch.object(ca, "Store", return_value=store):
        ok = ca.run(sleep=lambda s: None, log=lambda *a: None)
    assert ok == 0
    assert len(calls) == 2             # 2연속 로그인벽에서 중단


def test_run_yields_while_render_busy(store):
    excel = [{"username": "ch1", "followers": 10}]
    busy = {"n": 2}
    def _busy(self):
        busy["n"] -= 1
        return busy["n"] >= 0          # 두 번 바쁨 → 세 번째에 진행
    p1, p2, p3 = _targets_env(store, excel, [])
    slept = []
    with p1, p2, p3, \
         patch.object(ca, "crawl_channel", return_value=([{"shortcode": "A", "url": "", "thumbnail": "",
                                                            "views": 0, "likes": 0, "comments": 0,
                                                            "posted_at": ""}], "u", None)), \
         patch.object(store.__class__, "heavy_job_running", _busy), \
         patch.object(ca, "Store", return_value=store):
        ca.run(sleep=lambda s: slept.append(s), log=lambda *a: None)
    assert ca._BUSY_POLL_S in slept    # 양보 대기가 실제로 일어남
