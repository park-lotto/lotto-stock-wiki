"""관리페이지 사용량 리셋 (2026-08-27).

★왜 생겼나: 김데릭님(cid 241)이 렌즈 10/10을 쓴 뒤 입금하셨는데, 사용량을 되돌릴
  경로가 UI에도 API에도 없어서 사장님이 서버에 SSH로 붙어 sqlite를 직접 고쳤다.
  등급(set_plan)·포인트(admin/points)는 버튼이 있는데 **일일 사용횟수만 없었다**.
"""
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _s(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def test_usage_reset_zeroes_one_op(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.usage_incr(1, "lens", "2026-08-26")
    s.usage_incr(1, "lens", "2026-08-26")
    s.usage_incr(1, "render", "2026-08-26")
    assert s.usage_reset(1, "lens", "2026-08-26") == 2      # 지워진 값을 돌려준다
    assert s.usage_get(1, "lens", "2026-08-26") == 0
    assert s.usage_get(1, "render", "2026-08-26") == 1      # 다른 op는 그대로


def test_usage_reset_scoped_by_customer_and_day(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.usage_incr(1, "lens", "2026-08-26")
    s.usage_incr(2, "lens", "2026-08-26")
    s.usage_incr(1, "lens", "2026-08-25")
    s.usage_reset(1, "lens", "2026-08-26")
    assert s.usage_get(2, "lens", "2026-08-26") == 1        # 남의 것 안 건드림
    assert s.usage_get(1, "lens", "2026-08-25") == 1        # 다른 날 안 건드림


def test_usage_reset_missing_row_is_zero(tmp_path):
    """없는 행을 리셋해도 조용히 0. 버튼 연타가 500이 되면 안 된다."""
    s = Store(str(tmp_path / "t.db"))
    assert s.usage_reset(9, "lens", "2026-08-26") == 0


def test_reset_lets_blocked_customer_run_again(tmp_path, monkeypatch):
    """리셋의 진짜 목적 — 막힌 고객이 다시 돌아야 한다(김데릭 사례 재현)."""
    s = _s(tmp_path, monkeypatch)
    s.set_setting("limit_lens", 2)
    cid = s.create_customer("f", "pw12")
    s.set_plan(cid, "free", full_access_until=0)
    assert appmod.check_and_count(cid, "lens") is True
    assert appmod.check_and_count(cid, "lens") is True
    assert appmod.check_and_count(cid, "lens") is False     # 막힘
    s.usage_reset(cid, "lens", appmod._today_utc())
    assert appmod.check_and_count(cid, "lens") is True      # 다시 됨


def test_effective_limits_reports_source(tmp_path, monkeypatch):
    """화면이 '이 사람에게 실제로 걸린 한도'를 보여줄 수 있어야 한다.

    ★김데릭 사고의 원인은 limit_lens_pro가 빈 문자열이라 int('')가 터져
      조용히 기본 10으로 떨어진 것이었다. 화면에 근거를 같이 띄워 재발을 막는다.
    """
    s = _s(tmp_path, monkeypatch)
    cid = s.create_customer("p", "pw12")
    s.set_plan(cid, "pro", full_access_until=0)
    s.set_setting("limit_lens_pro", "")                     # ← 사고 당시 서버 상태
    eff = appmod._effective_limits(s, cid)
    assert eff["lens"]["limit"] == 10
    assert eff["lens"]["fallback"] is True                  # 기본값으로 떨어졌음을 알린다


# ── API 엔드포인트 ──────────────────────────────────────────────────────
from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch, admin=True):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_is_admin", lambda cid: admin)
    s = Store(db)
    s.ensure_paywall_schema()
    return TestClient(appmod.app), s


def test_api_reset_one_op(tmp_path, monkeypatch):
    c, s = _client(tmp_path, monkeypatch)
    day = appmod._today_utc()
    for _ in range(10):
        s.usage_incr(241, "lens", day)
    s.usage_incr(241, "script", day)
    r = c.post("/api/admin/usage/reset", json={"customer_id": 241, "op": "lens"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d["cleared"]["lens"] == 10
    assert d["usage"]["lens"] == 0
    assert d["usage"]["script"] == 1            # 안 건드림
    assert s.usage_get(241, "lens", day) == 0


def test_api_reset_all_ops_when_op_omitted(tmp_path, monkeypatch):
    c, s = _client(tmp_path, monkeypatch)
    day = appmod._today_utc()
    s.usage_incr(7, "lens", day); s.usage_incr(7, "render", day)
    r = c.post("/api/admin/usage/reset", json={"customer_id": 7})
    assert r.status_code == 200
    assert r.json()["usage"] == {"lens": 0, "render": 0, "script": 0}


def test_api_reset_rejects_bad_input(tmp_path, monkeypatch):
    c, _ = _client(tmp_path, monkeypatch)
    assert c.post("/api/admin/usage/reset", json={}).status_code == 422
    assert c.post("/api/admin/usage/reset",
                  json={"customer_id": 1, "op": "hack"}).status_code == 422


def test_api_reset_requires_admin(tmp_path, monkeypatch):
    """★관리자 전용이어야 한다 — 회원이 자기 사용량을 리셋하면 한도가 무의미해진다."""
    c, _ = _client(tmp_path, monkeypatch, admin=False)
    assert c.post("/api/admin/usage/reset",
                  json={"customer_id": 1, "op": "lens"}).status_code == 403
