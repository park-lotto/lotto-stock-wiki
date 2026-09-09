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


def test_summary_ignores_later_health_run(monkeypatch, tmp_path):
    """★2026-09-07 리뷰 지적 회귀 테스트: daily run이 낸 빨강이 5분마다 도는 health run(=
    check_results 없음) 때문에 화면에서 사라지면 안 된다. deploy/daily run만 요약에 쓴다."""
    conn = db.open_db(tmp_path / "checks.db")
    r_daily = db.start_run(conn, "s", "daily", "a")
    db.add_result(conn, r_daily, Result("L1", "버튼", RED, signature="b", reason="pageerror"))
    db.finish_run(conn, r_daily, RED)
    # health run이 더 나중에 끝났다 — check_results는 안 남긴다(실제 파이프라인과 동일)
    r_health = db.start_run(conn, "s", "health", "a")
    db.finish_run(conn, r_health, GREEN)
    assert r_health > r_daily  # 더 최근 run임을 확인

    c = _client(monkeypatch, tmp_path)
    j = c.get("/api/admin/checks/summary").json()
    assert j["ok"] and j["run"]["run_id"] == r_daily
    assert j["run"]["trigger"] == "daily"
    assert j["results"] and j["results"][0]["verdict"] == "red"
    assert j["counts"]["red"] == 1
    assert "전부 정상" not in j["headline"]


def test_admin_page_requires_admin(monkeypatch, tmp_path):
    c = TestClient(appmod.app)
    r = c.get("/admin/checks")
    assert r.status_code in (303, 401, 403) if appmod._AUTH_ON else r.status_code == 200


def test_evidence_serves_real_screenshot(monkeypatch, tmp_path):
    """정상 케이스: evidence_dir 아래 shot.png가 있으면 200으로 이미지가 내려간다."""
    monkeypatch.setattr(db, "DEFAULT_PATH", tmp_path / "checks.db")
    evroot = tmp_path / "checks_evidence"
    monkeypatch.setattr(appmod, "_EVIDENCE_ROOT", evroot.resolve())
    conn = db.open_db(tmp_path / "checks.db")
    r1 = db.start_run(conn, "s", "deploy", "a")
    result = Result("L1", "장면편집", RED, signature="scene", evidence_dir="run1_scene")
    db.add_result(conn, r1, result)
    db.finish_run(conn, r1, RED)
    result_id = conn.execute("SELECT id FROM check_results ORDER BY id DESC LIMIT 1").fetchone()["id"]
    shot_dir = evroot / "run1_scene"
    shot_dir.mkdir(parents=True)
    (shot_dir / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    c = _client(monkeypatch, tmp_path)

    r = c.get(f"/api/admin/checks/evidence/{result_id}/shot.png")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")

    # summary/results도 evidence_ok=True로 보고해야 화면이 링크를 그린다
    j = c.get("/api/admin/checks/summary").json()
    assert j["results"][0]["evidence_ok"] is True


def test_evidence_missing_file_returns_friendly_404(monkeypatch, tmp_path):
    """증거 폴더는 있어도 파일이 없는 정상 케이스 — 404지만 JSON으로 이유를 알린다(날 에러 화면 아님)."""
    monkeypatch.setattr(db, "DEFAULT_PATH", tmp_path / "checks.db")
    evroot = tmp_path / "checks_evidence"
    monkeypatch.setattr(appmod, "_EVIDENCE_ROOT", evroot.resolve())
    conn = db.open_db(tmp_path / "checks.db")
    r1 = db.start_run(conn, "s", "deploy", "a")
    db.add_result(conn, r1, Result("L1", "장면편집", RED, signature="scene", evidence_dir="no_such_dir"))
    db.finish_run(conn, r1, RED)
    result_id = conn.execute("SELECT id FROM check_results ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c = _client(monkeypatch, tmp_path)

    r = c.get(f"/api/admin/checks/evidence/{result_id}/shot.png")
    assert r.status_code == 404
    assert r.json()["ok"] is False

    j = c.get("/api/admin/checks/summary").json()
    assert j["results"][0]["evidence_ok"] is False


def test_evidence_path_traversal_blocked(monkeypatch, tmp_path):
    """경로 탈출 시도가 전부 차단되는지 — 증거 루트 밖 파일이 절대 내려가면 안 된다."""
    monkeypatch.setattr(db, "DEFAULT_PATH", tmp_path / "checks.db")
    evroot = tmp_path / "checks_evidence"
    evroot.mkdir()
    monkeypatch.setattr(appmod, "_EVIDENCE_ROOT", evroot.resolve())
    # 루트 밖에 진짜 파일을 하나 심어 둔다 — 이게 절대 내려가면 안 된다
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"SECRET")
    conn = db.open_db(tmp_path / "checks.db")
    r1 = db.start_run(conn, "s", "deploy", "a")
    db.add_result(conn, r1, Result("L1", "장면편집", RED, signature="scene", evidence_dir="../"))
    db.finish_run(conn, r1, RED)
    result_id = conn.execute("SELECT id FROM check_results ORDER BY id DESC LIMIT 1").fetchone()["id"]
    c = _client(monkeypatch, tmp_path)

    # ① evidence_dir 자체가 ".." — DB에 이런 값이 들어와도 정규식이 막아야 한다
    r = c.get(f"/api/admin/checks/evidence/{result_id}/shot.png")
    assert r.status_code == 404
    assert r.json()["ok"] is False

    # ② URL의 filename에 상대경로 탈출 시도 (raw ..)
    r2 = c.get(f"/api/admin/checks/evidence/{result_id}/..%2f..%2fsecret.png")
    assert r2.status_code in (404, 400)
    assert b"SECRET" not in r2.content

    # ③ 필터를 우회하려는 이중 인코딩·확장자 위장 시도
    r3 = c.get(f"/api/admin/checks/evidence/{result_id}/shot.png.exe")
    assert r3.status_code in (404, 400)
    r4 = c.get(f"/api/admin/checks/evidence/{result_id}/..secret.png")
    assert r4.status_code == 404
    assert b"SECRET" not in r4.content

    # ④ 직접 함수 레벨로도 확인: 루트 밖으로는 절대 못 나간다
    assert appmod._evidence_shot_path("../../..", "shot.png") is None
    assert appmod._evidence_shot_path("ok_dir", "../../../secret.png") is None
