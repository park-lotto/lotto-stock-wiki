"""샤오홍슈 계정 발굴 오케스트레이션(service) — 담기·삭제(블랙리스트)·자동등록·is_registered.
설계: docs/superpowers/specs/2026-07-29-샤오홍슈-계정발굴-design.md"""
from shopping_shorts import service, config
from shopping_shorts.store import Store


def _note(uid, nick, likes=0):
    return {"channel_id": uid, "channel_title": nick, "likes": likes,
            "comments": 0, "collects": 0, "shares": 0, "url": "u", "thumbnail": "t"}


def _wire(monkeypatch, tmp_path, notes):
    db = str(tmp_path / "t.db")
    Store(db)  # 초기화
    monkeypatch.setattr(service, "DB_PATH", db)
    monkeypatch.setattr(service.xiaohongshu_search, "search_full", lambda kw: notes)
    monkeypatch.setattr(service.overseas_seeds, "load_seeds", lambda: {"주방": {"cn": ["kw1"]}})
    return db


def test_discovery_accumulation_counts_observations(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    def acc(e): return [{"userid": "u1", "engagement_sum": e, "note_count": 3, "nickname": "A"}]
    s.xhs_discovery_record("2026-07-29T10:00:00", acc(100))
    s.xhs_discovery_record("2026-07-29T10:00:00", acc(100))  # 같은 타임스탬프(=같은 발굴) → 1관측(멱등)
    s.xhs_discovery_record("2026-07-29T14:00:00", acc(50))   # 같은 날 다른 발굴 → 별개 관측
    s.xhs_discovery_record("2026-07-30T09:00:00", acc(30))   # 다음 날
    stats = s.xhs_discovery_stats()
    assert stats["u1"]["appear_count"] == 3         # 관측 3회(자주 돌수록↑)
    assert stats["u1"]["appear_days"] == 2          # 달력상 이틀
    assert stats["u1"]["cum_engagement"] == 180     # 100+50+30
    assert stats["u1"]["last_seen"] == "2026-07-30T09:00:00"


def test_discover_attaches_accumulation(monkeypatch, tmp_path):
    notes = [_note("u1", "A", 5), _note("u1", "A", 5)]
    _wire(monkeypatch, tmp_path, notes)
    out = service.discover_xiaohongshu_accounts()
    assert out[0]["appear_count"] == 1              # 첫 발굴 = 1관측
    assert out[0]["cum_engagement"] == out[0]["engagement_sum"]


def test_discover_endpoint_guards_when_overseas_running(monkeypatch):
    import json
    from shopping_shorts import app, overseas_hot_jobs
    monkeypatch.setattr(overseas_hot_jobs, "status", lambda: {"status": "running"})
    resp = app.api_xhs_discover()          # 해외HOT 수집중이면 발굴 건너뜀
    body = json.loads(resp.body)
    assert body["ok"] is False and "해외HOT" in body["error"]


def test_search_fn_follows_xhs_scraper_config(monkeypatch):
    # 기본(apify)이면 유료 검색, playwright면 무료 크롤 검색을 고른다.
    from shopping_shorts import xiaohongshu_search, playwright_crawl
    monkeypatch.setattr(config, "XHS_SCRAPER", "apify")
    assert service._xhs_search_fn() is xiaohongshu_search.search_full
    monkeypatch.setattr(config, "XHS_SCRAPER", "playwright")
    assert service._xhs_search_fn() is playwright_crawl.search_full


def test_discover_then_adopt_marks_registered(monkeypatch, tmp_path):
    notes = [_note("u1", "A", 5), _note("u1", "A", 5), _note("u2", "B", 3), _note("u2", "B", 3)]
    _wire(monkeypatch, tmp_path, notes)

    out = service.discover_xiaohongshu_accounts()
    assert {a["userid"] for a in out} == {"u1", "u2"}
    assert all(not a["is_registered"] for a in out)

    top = out[0]
    r = service.adopt_xiaohongshu_account(top["profile_url"], userid=top["userid"])
    assert r["ok"]
    # 담은 뒤 다시 발굴하면 is_registered=True
    out2 = {a["userid"]: a for a in service.discover_xiaohongshu_accounts()}
    assert out2[top["userid"]]["is_registered"]


def test_blacklist_excludes_from_discovery_and_blocks_adopt(monkeypatch, tmp_path):
    notes = [_note("u1", "A", 5), _note("u1", "A", 5), _note("bad", "쓰레기", 9), _note("bad", "쓰레기", 9)]
    _wire(monkeypatch, tmp_path, notes)

    service.blacklist_xiaohongshu_account("bad", profile_url="https://www.rednote.com/user/profile/bad")
    out = service.discover_xiaohongshu_accounts()
    assert [a["userid"] for a in out] == ["u1"]   # bad 영구 제외

    # 블랙리스트 계정은 담기도 거부
    r = service.adopt_xiaohongshu_account("https://www.rednote.com/user/profile/bad", userid="bad")
    assert not r["ok"] and r["reason"] == "blacklisted"


def test_auto_register_adds_top_n_excluding_blacklist(monkeypatch, tmp_path):
    notes = [_note("hi", "H", 50), _note("hi", "H", 50),
             _note("mid", "M", 10), _note("mid", "M", 10),
             _note("bad", "X", 99), _note("bad", "X", 99)]
    db = _wire(monkeypatch, tmp_path, notes)
    service.blacklist_xiaohongshu_account("bad")

    added = service.auto_register_xiaohongshu(top_n=10)
    accounts = {s["value"] for s in Store(db).list_seeds("xiaohongshu") if s["kind"] == "account"}
    assert "https://www.rednote.com/user/profile/hi" in accounts
    assert "https://www.rednote.com/user/profile/mid" in accounts
    assert "https://www.rednote.com/user/profile/bad" not in accounts   # 블랙리스트 제외
    assert len(added) == 2

    # 재실행하면 이미 등록돼 추가 0(멱등)
    assert service.auto_register_xiaohongshu(top_n=10) == []
