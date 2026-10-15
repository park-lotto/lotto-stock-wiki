# -*- coding: utf-8 -*-
"""관리자 화면 관제 보드(2026-09-30, 관제 카드 004 — 사장님 "1 2 다 하고").

못 박는 것:
1. /api/admin/control/board 가 저장소 관제/cards 를 tools/control.py 로 읽어 준다(파싱 두 벌 없음).
2. [승인] 은 서버 파일(data/control_approvals.json)에 적히고 보드에 곧바로 보인다 — 카드 파일(git)은 서버가 안 고친다.
3. 비관리자는 403.
4. admin.html 에 보드 상자·승인 버튼·load() 호출이 있다.
"""
import json
import pathlib

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module

ADMIN_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "admin.html"

CARD = """# 004 · 관리자 보드

- 상태: 등록
- 등록: 2026-09-30 01:00
- 제보: 설계
- 판단 주인: app.py:_admin_control_board
- 분배: 관제
- 됐다의 기준: 화면에 보인다
- 승인 필요: 예
- 승인:
- 병합:
- 서버 반영:
- 라이브 실측:
- 재발:

## 요청

보드

## 이력

- 2026-09-30 01:00 등록
"""


def _setup(monkeypatch, tmp_path, admin=True):
    root = tmp_path / "repo"
    (root / "관제" / "cards").mkdir(parents=True)
    (root / "관제" / "cards" / "004-보드.md").write_text(CARD, encoding="utf-8")
    (root / "tools").mkdir()
    real = pathlib.Path(__file__).resolve().parents[2] / "tools" / "control.py"
    (root / "tools" / "control.py").write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(app_module, "_control_root", lambda: root)
    monkeypatch.setattr(app_module, "_control_approvals_path", lambda: tmp_path / "data" / "control_approvals.json")
    if admin:
        monkeypatch.setattr(app_module, "_require_admin", lambda request: None)
    else:
        # ★세션 없는 요청은 customer_id None → _as_cid(None)==0 → **사장님으로 통과**한다(_is_admin). 그래서 비관리자는
        #   로그인한 일반 회원으로 흉내 내야 한다 — 여기선 판정 함수가 거절을 돌려주는 것으로 대신한다.
        from fastapi.responses import JSONResponse
        monkeypatch.setattr(app_module, "_require_admin", lambda request: JSONResponse({"error": "관리자 전용"}, status_code=403))
    return TestClient(app_module.app)


def test_보드는_카드를_저장소에서_읽는다(monkeypatch, tmp_path):
    c = _setup(monkeypatch, tmp_path)
    d = c.get("/api/admin/control/board").json()
    assert d["ok"] and len(d["cards"]) == 1
    card = d["cards"][0]
    assert card["no"] == 4 and card["title"] == "관리자 보드" and card["state"] == "등록"
    assert card["needs_approval"].startswith("예") and card["approval"] == "" and card["server_approval"] is None
    assert "등록" in d["states"] and "회귀" in d["states"]


def test_승인_버튼은_서버_파일에_적히고_보드에_보인다(monkeypatch, tmp_path):
    c = _setup(monkeypatch, tmp_path)
    r = c.post("/api/admin/control/approve", json={"no": 4, "note": "사장님 화면 승인"})
    assert r.status_code == 200 and r.json()["ok"]
    saved = json.loads((tmp_path / "data" / "control_approvals.json").read_text(encoding="utf-8"))
    assert saved["004"]["note"] == "사장님 화면 승인" and saved["004"]["at"]
    card = c.get("/api/admin/control/board").json()["cards"][0]
    assert card["server_approval"]["note"] == "사장님 화면 승인"
    assert card["approval"] == "", "카드 파일(git)은 서버가 고치지 않는다 — 로컬 finish 가 옮긴다"
    # 카드 md 원본 그대로
    assert (tmp_path / "repo" / "관제" / "cards" / "004-보드.md").read_text(encoding="utf-8") == CARD


def test_근거_없는_승인은_거절(monkeypatch, tmp_path):
    c = _setup(monkeypatch, tmp_path)
    assert c.post("/api/admin/control/approve", json={"no": 4, "note": ""}).status_code == 400
    assert c.post("/api/admin/control/approve", json={"no": 0, "note": "x"}).status_code == 400


def test_비관리자는_403(monkeypatch, tmp_path):
    c = _setup(monkeypatch, tmp_path, admin=False)
    assert c.get("/api/admin/control/board").status_code == 403
    assert c.post("/api/admin/control/approve", json={"no": 4, "note": "x"}).status_code == 403


def test_화면에_보드와_승인_버튼이_있다():
    html = ADMIN_HTML.read_text(encoding="utf-8")
    assert 'id=controlBoard' in html and "renderControlBoard()" in html
    assert "/api/admin/control/board" in html and "/api/admin/control/approve" in html
    assert "function approveCard" in html
    assert "결정할 것" in html and "잘못된 것" in html and "ctlTech" in html, "사장님용 두 줄 + 기술 보기 토글"
