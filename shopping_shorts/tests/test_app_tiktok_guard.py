"""틱톡 키워드검색 수집의 남용/비용 가드 + 관리자 노브 설정 엔드포인트.

노브 3개: tiktok_search_count(검색당 개수, 기본 60) / tiktok_daily_limit(하루 수집횟수,
기본 10) / tiktok_month_budget(월 예산 상한 $, 기본 5.0). 예산 초과 시 킬스위치,
하루 상한 초과 시 거부. 성공 수집은 하루카운트 증가 + 월지출 누적."""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    # 실제 Apify/수집을 타지 않게 collect를 스텁 — 가드/누적만 검증
    monkeypatch.setattr(appmod, "collect", lambda platform="instagram", limit_channels=None: [])
    return TestClient(appmod.app), db


def test_settings_get_defaults(tmp_path, monkeypatch):
    c, _ = _client(tmp_path, monkeypatch)
    r = c.get("/api/tiktok/settings").json()
    assert r["ok"]
    assert r["search_count"] == 60
    assert r["daily_limit"] == 10
    assert r["month_budget"] == 5.0


def test_settings_get_exposes_today_usage(tmp_path, monkeypatch):
    """설정 GET은 오늘 남은 횟수(remaining_today)와 이번달 지출(month_spend)도 함께 준다
    — 프론트가 '오늘 남은 N회'를 실제 카운트로 보여주기 위함."""
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.set_setting("tiktok_daily_limit", "10")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    s.bump_tiktok_daily(0, now.strftime("%Y-%m-%d"))   # LEGACY(0) 1회 사용
    s.bump_tiktok_daily(0, now.strftime("%Y-%m-%d"))   # 2회
    s.add_tiktok_spend(now.strftime("%Y-%m"), 0.34)

    r = c.get("/api/tiktok/settings").json()
    assert r["used_today"] == 2
    assert r["remaining_today"] == 8
    assert round(r["month_spend"], 2) == 0.34


def test_settings_post_roundtrip(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch)
    r = c.post("/api/tiktok/settings",
               json={"search_count": 30, "daily_limit": 5, "month_budget": 2.5}).json()
    assert r["ok"]
    g = c.get("/api/tiktok/settings").json()
    assert (g["search_count"], g["daily_limit"], g["month_budget"]) == (30, 5, 2.5)


def test_collect_blocked_when_month_budget_exceeded(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.set_setting("tiktok_month_budget", "5.0")
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    s.add_tiktok_spend(month, 5.0)   # 이미 예산 소진

    r = c.post("/api/collect?platform=tiktok")
    assert r.status_code == 429
    assert r.json()["error_code"] == "budget_exceeded"


def test_collect_blocked_when_daily_limit_reached(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.set_setting("tiktok_daily_limit", "2")
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    s.bump_tiktok_daily(0, day)
    s.bump_tiktok_daily(0, day)   # LEGACY_CUSTOMER_ID(0) 하루 2회 소진

    r = c.post("/api/collect?platform=tiktok")
    assert r.status_code == 429
    assert r.json()["error_code"] == "daily_limit"


def test_successful_tiktok_collect_bumps_count_and_spend(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.add_seed("tiktok", "keyword", "청소")
    r = c.post("/api/collect?platform=tiktok")
    assert r.status_code == 200 and r.json()["ok"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert s.tiktok_daily_count(0, now.strftime("%Y-%m-%d")) == 1
    # 지출이 누적됐다(키워드 있으면 0보다 큼)
    assert s.tiktok_month_spend(now.strftime("%Y-%m")) > 0


def test_non_tiktok_collect_not_guarded(tmp_path, monkeypatch):
    """인스타/유튜브 수집은 틱톡 가드에 영향받지 않는다."""
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.set_setting("tiktok_month_budget", "5.0")
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    s.add_tiktok_spend(month, 99.0)   # 틱톡 예산 초과 상태여도

    r = c.post("/api/collect?platform=youtube")
    assert r.status_code == 200   # 유튜브는 통과
