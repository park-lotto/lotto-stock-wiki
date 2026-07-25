"""틱톡 키워드검색 수집의 남용/비용 가드 + 관리자 노브 설정 엔드포인트.

노브 3개: tiktok_search_count(검색당 개수, 기본 60) / tiktok_daily_limit(하루 수집횟수,
기본 10) / tiktok_month_budget(월 예산 상한 $, 기본 5.0). 하루 상한 초과 시 거부.

⚠️ 2026-07-24: 키워드검색(Apify 유료)이 옵트인으로 빠져(app._collect_tiktok는
항상 include_paid_keywords=False) 실제 지출이 없다 → api_collect의 월예산
킬스위치·지출누적은 건너뛴다(무료 수집이 유령 지출로 막히는 걸 방지, Fix 2).
아래 예산 관련 테스트는 그 새 계약(체크·누적 skip)에 맞춰졌다. daily_limit
가드는 비용과 무관하게 계속 유지된다."""
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    # 실제 Apify/수집을 타지 않게 collect를 스텁 — 가드/누적만 검증
    monkeypatch.setattr(appmod, "collect", lambda platform="instagram", categories=None, limit_channels=None: [])
    return TestClient(appmod.app), db


def test_settings_get_defaults(tmp_path, monkeypatch):
    c, _ = _client(tmp_path, monkeypatch)
    r = c.get("/api/tiktok/settings").json()
    assert r["ok"]
    assert r["search_count"] == 50   # 언어당 기본 50개(요청 변경 60→50)
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


def test_collect_not_blocked_by_month_budget_gate_skip(tmp_path, monkeypatch):
    """Fix 2(2026-07-24): 유료 검색이 꺼져 있어 지출 게이트를 건너뛴다 — 월예산이
    이미 소진된 상태를 흉내내도(add_tiktok_spend) 무료 틱톡 수집은 막히지 않는다."""
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    s.set_setting("tiktok_month_budget", "5.0")
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    s.add_tiktok_spend(month, 5.0)   # 유령 지출(옛 로직 잔재) — 새 계약에선 무시돼야 함

    r = c.post("/api/collect?platform=tiktok")
    assert r.status_code == 200
    assert r.json()["ok"]


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


def test_successful_tiktok_collect_bumps_count_but_not_spend(tmp_path, monkeypatch):
    """Fix 2: 성공 수집은 하루카운트(남용 가드)는 여전히 늘리지만, 유료 검색이
    꺼져 있으므로 월지출은 더 이상 누적되지 않는다(0.0 유지)."""
    c, db = _client(tmp_path, monkeypatch)
    s = Store(db)
    # 언어 시드가 있어도 무료경로(_collect_tiktok 기본값)는 검색을 타지 않는다.
    s.add_seed("tiktok", "ko", "청소")
    s.add_seed("tiktok", "en", "cleaning")
    r = c.post("/api/collect?platform=tiktok")
    assert r.status_code == 200 and r.json()["ok"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert s.tiktok_daily_count(0, now.strftime("%Y-%m-%d")) == 1
    assert s.tiktok_month_spend(now.strftime("%Y-%m")) == 0.0


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
