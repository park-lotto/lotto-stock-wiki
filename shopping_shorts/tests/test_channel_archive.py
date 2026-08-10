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


# ── 계정 풀 분리(2026-08-09) ──
# 왜 잠그나: 아카이브와 레퍼런스랭킹이 같은 계정을 공유해, 아침 아카이브가 한도를
# 태우면 저녁 수집이 첫 채널부터 0건이 됐다(199채널 전부 not_found 실사고).
# 폴더가 없을 땐 동작이 안 바뀌어야 하고(폴백), 생기면 계정·출구가 모두 갈려야 한다.

def _mk(d, *names):
    os.makedirs(d, exist_ok=True)
    for n in names:
        with open(os.path.join(d, n), "w") as f:
            f.write("{}")


def test_session_slots_falls_back_when_pool_dir_absent(tmp_path):
    """하위 폴더가 없으면 기존처럼 상위 폴더 전체 — 분리 전에도 동작 불변."""
    d = str(tmp_path / "sess")
    _mk(d, "a.json", "b.json")
    with patch.dict(os.environ, {"INSTAGRAM_SESSION_DIR": d}):
        arch = ca.session_slots(ca.POOL_ARCHIVE)
        ref = ca.session_slots(ca.POOL_REFERENCE)
    assert [os.path.basename(x) for x in arch] == ["a.json", "b.json"]
    assert [os.path.basename(x) for x in ref] == ["a.json", "b.json"]


def test_session_slots_splits_by_pool(tmp_path):
    """하위 폴더가 있으면 자기 풀만 본다 — 서로의 한도를 잠식하지 않는다."""
    d = str(tmp_path / "sess")
    _mk(d)
    _mk(os.path.join(d, "archive"), "a1.json", "a2.json")
    _mk(os.path.join(d, "reference"), "r1.json")
    with patch.dict(os.environ, {"INSTAGRAM_SESSION_DIR": d}):
        arch = [os.path.basename(x) for x in ca.session_slots(ca.POOL_ARCHIVE)]
        ref = [os.path.basename(x) for x in ca.session_slots(ca.POOL_REFERENCE)]
    assert arch == ["a1.json", "a2.json"]
    assert ref == ["r1.json"]
    assert not set(arch) & set(ref)


def test_slot_proxy_exits_do_not_collide_across_pools():
    """풀이 갈려도 출구 IP가 겹치면 계정↔IP 1:1이 깨져 한 기계로 묶인다."""
    env = {"WEBSHARE_USER": "u", "WEBSHARE_PASS": "p"}
    with patch.dict(os.environ, env):
        arch = {ca.slot_proxy(i, ca.POOL_ARCHIVE) for i in range(3)}
        ref = {ca.slot_proxy(i, ca.POOL_REFERENCE) for i in range(3)}
    assert not arch & ref
    # 풀 미지정(기존 호출부)은 아카이브와 같은 번호대 — 하위호환.
    with patch.dict(os.environ, env):
        assert ca.slot_proxy(0) == ca.slot_proxy(0, ca.POOL_ARCHIVE)
