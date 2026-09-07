"""관리자 API는 앱 라우트를 TestClient로 실제 호출한다(호출부 형태 그대로). 인증은 앱의 _sign_session."""
import time
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.checks import db
from shopping_shorts.checks.verdict import Result, RED, GREEN


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DEFAULT_PATH", tmp_path / "checks.db")
    c = TestClient(appmod.app)
    if appmod._AUTH_ON:
        c.cookies.set("dash_auth", appmod._sign_session(0, int(time.time()) + 3600))
    return c


def test_summary_marks_newly_red(monkeypatch, tmp_path):
    conn = db.open_db(tmp_path / "checks.db")
    r1 = db.start_run(conn, "s", "deploy", "a"); db.add_result(conn, r1, Result("L1", "버튼", GREEN, signature="b")); db.finish_run(conn, r1, GREEN)
    r2 = db.start_run(conn, "s", "deploy", "b"); db.add_result(conn, r2, Result("L1", "버튼", RED, signature="b", reason="pageerror")); db.finish_run(conn, r2, RED)
    c = _client(monkeypatch, tmp_path)
    j = c.get("/api/admin/checks/summary").json()
    assert j["ok"] and j["run"]["run_id"] == r2
    assert [x["signature"] for x in j["newly_red"]] == ["b"]
    assert "버튼" in j["headline"]


def test_admin_page_requires_admin(monkeypatch, tmp_path):
    c = TestClient(appmod.app)
    r = c.get("/admin/checks")
    assert r.status_code in (303, 401, 403) if appmod._AUTH_ON else r.status_code == 200
