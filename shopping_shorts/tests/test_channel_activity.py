"""활동성 선별(2026-07-22) — channel_activity store + select_tracked + census."""
from datetime import datetime, timezone, timedelta

import pytest
from openpyxl import Workbook

from shopping_shorts.store import Store
from shopping_shorts import channels as ch_mod
from shopping_shorts import service as svc
from shopping_shorts.channels import select_tracked, load_channels
from shopping_shorts.config import MAX_TRACKED, DEAD_AFTER_DAYS


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def _ch(u, name=None):
    return {"username": u, "name": name or u, "followers": 0, "inpock": ""}


# ── store: channel_activity 왕복 ──
def test_upsert_alive_roundtrip(store):
    store.upsert_activity("Alive1", alive=True, last_post_at="2026-07-22T00:00:00+00:00",
                          engagement_density=0.5, activity_score=0.9)
    m = store.activity_map()
    assert m["alive1"]["alive"] is True
    assert m["alive1"]["engagement_density"] == 0.5
    assert store.alive_usernames() == {"alive1"}
    assert store.dead_usernames() == set()


def test_upsert_dead_only_flips_alive(store):
    store.upsert_activity("Dead1", alive=False)
    assert store.dead_usernames() == {"dead1"}
    assert store.alive_usernames() == set()


def test_revival(store):
    store.upsert_activity("ch", alive=False)
    assert store.dead_usernames() == {"ch"}
    store.upsert_activity("ch", alive=True, last_post_at="2026-07-22T00:00:00+00:00",
                          engagement_density=0.1, activity_score=0.2)
    assert store.dead_usernames() == set()
    assert store.alive_usernames() == {"ch"}


def test_dead_preserves_prior_last_post(store):
    store.upsert_activity("ch", alive=True, last_post_at="2026-07-20T00:00:00+00:00",
                          engagement_density=0.3, activity_score=0.4)
    store.upsert_activity("ch", alive=False)   # 사망은 last_post_at 안 건드림
    assert store.activity_map()["ch"]["last_post_at"] == "2026-07-20T00:00:00+00:00"


# ── select_tracked: 활동성 필터 ──
def test_select_includes_alive_and_pending():
    excel = [_ch("alive1"), _ch("pending1"), _ch("dead1")]
    out = select_tracked(excel, [], removed=set(), dead={"dead1"})
    users = {c["username"] for c in out}
    assert users == {"alive1", "pending1"}   # dead 제외, pending 포함


def test_select_excludes_removed_and_dead():
    excel = [_ch("a"), _ch("b"), _ch("c")]
    out = select_tracked(excel, [], removed={"a"}, dead={"b"})
    assert {c["username"] for c in out} == {"c"}


def test_select_all_pending_when_no_activity():
    # 센서스 전(dead 비어있음) → 전원 포함(초기 안전동작)
    excel = [_ch(f"c{i}") for i in range(10)]
    out = select_tracked(excel, [], removed=set(), dead=set())
    assert len(out) == 10


def test_select_discovered_in_front_and_dedup():
    excel = [_ch("e1"), _ch("e2")]
    out = select_tracked(excel, [_ch("mypick"), _ch("E1")], removed=set(), dead=set())
    users = [c["username"] for c in out]
    assert users[0] == "mypick"          # 등록채널 앞
    assert users.count("e1") + [u.lower() for u in users].count("e1") >= 1
    assert "E1" not in users             # 엑셀 중복 dedupe


def test_select_max_tracked_safety_cap():
    excel = [_ch(f"c{i}") for i in range(MAX_TRACKED + 50)]
    out = select_tracked(excel, [], removed=set(), dead=set())
    assert len(out) == MAX_TRACKED


# ── load_channels: 팔로워 컷 제거(무캡) ──
def test_load_channels_no_follower_cap(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["채널명", "주소", "팔로워", "인포크"])
    for i in range(250):                 # 옛 코드면 200에서 잘렸다
        ws.append([f"ch{i}", f"https://instagram.com/ch{i}", 250 - i, ""])
    path = tmp_path / "bench.xlsx"
    wb.save(path)
    got = load_channels(path)
    assert len(got) == 250               # 무캡 — 전체 반환


# ── census(): 전수 스캔 → 생존/사망 분류 ──
def _reel(user, comments=10, views=100, hours_ago=5):
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"ownerUsername": user, "username": user, "timestamp": ts,
            "shortcode": f"{user}_sc", "commentsCount": comments,
            "videoViewCount": views, "url": f"https://instagram.com/reel/{user}"}


def test_census_classifies_alive_and_dead(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "DB_PATH", tmp_path / "c.db")
    monkeypatch.setattr(svc, "load_channels", lambda: [_ch("alive1"), _ch("dead1")])
    # alive1만 최근 릴스 반환, dead1은 없음
    monkeypatch.setattr(svc, "fetch_reels",
                        lambda users, **k: [_reel("alive1")])
    res = svc.census()
    assert res["alive_n"] == 1
    assert res["dead_n"] == 1
    assert {c["username"] for c in res["dead"]} == {"dead1"}
    recs = {r["username"]: r for r in res["activity_records"]}
    assert recs["alive1"]["alive"] is True
    assert recs["dead1"]["alive"] is False


def test_census_counts_revival(tmp_path, monkeypatch):
    db = tmp_path / "c.db"
    Store(db).upsert_activity("comeback", alive=False)   # 전에 죽었던 채널
    monkeypatch.setattr(svc, "DB_PATH", db)
    monkeypatch.setattr(svc, "load_channels", lambda: [_ch("comeback")])
    monkeypatch.setattr(svc, "fetch_reels", lambda users, **k: [_reel("comeback")])
    res = svc.census()
    assert res["revived_n"] == 1


def test_record_activity_keeps_best_score():
    seen = {}
    # 낮은 참여밀도 먼저
    svc._record_activity(seen, "ch", {"comments": 1, "views": 100, "age_hours": 40},
                         {"timestamp": "2026-07-20T00:00:00+00:00"})
    low = seen["ch"]["activity_score"]
    # 높은 참여밀도 + 더 최근
    svc._record_activity(seen, "ch", {"comments": 50, "views": 100, "age_hours": 1},
                         {"timestamp": "2026-07-22T00:00:00+00:00"})
    assert seen["ch"]["activity_score"] > low
    assert seen["ch"]["last_post_at"] == "2026-07-22T00:00:00+00:00"
