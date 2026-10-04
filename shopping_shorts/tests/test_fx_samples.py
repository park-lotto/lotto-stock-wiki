# -*- coding: utf-8 -*-
"""효과 견본(2026-10-04, 관제 118) — 관리자 전용 화면.

못 박는 것:
1. /fx_samples · /fx_samples.html · 목록 · 영상 네 주소 모두 비관리자는 403(정적 마운트로 뚫리지 않는다).
2. 관리자는 data/fx_samples 의 manifest.json 과 <번호>.mp4 를 받는다. 폴더는 _fx_samples_dir 한 곳.
3. 견본 번호 꼴이 아니면 404(경로 조작 차단).
4. 사이드바 항목은 admin:true 다.
"""
import json
import pathlib

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _client(monkeypatch, tmp_path, admin=True):
    d = tmp_path / "fx_samples"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps(
        {"updated": "2026-10-04", "groups": [{"key": "A", "name": "자막 등장", "desc": "", "items": [
            {"id": "A1", "title": "글자 블러 올라오기", "tag": "text", "note": ""}]}]}, ensure_ascii=False), encoding="utf-8")
    (d / "A1.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(app_module, "_fx_samples_dir", lambda: d)
    if admin:
        monkeypatch.setattr(app_module, "_require_admin", lambda request: None)
    else:
        # 세션 없는 요청은 사장님으로 통과하므로(_is_admin), 비관리자는 판정 함수가 거절하는 것으로 흉내 낸다.
        from fastapi.responses import JSONResponse
        monkeypatch.setattr(app_module, "_require_admin",
                            lambda request: JSONResponse({"error": "관리자 전용"}, status_code=403))
    return TestClient(app_module.app)


def test_비관리자는_네_주소_모두_403(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, admin=False)
    for url in ("/fx_samples", "/fx_samples.html", "/api/admin/fx_samples", "/api/admin/fx_samples/video/A1.mp4"):
        assert c.get(url).status_code == 403, url


def test_관리자는_목록과_영상을_받는다(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    page = c.get("/fx_samples")
    assert page.status_code == 200 and "효과 견본" in page.text
    d = c.get("/api/admin/fx_samples").json()
    assert d["ok"] and d["groups"][0]["items"][0]["id"] == "A1"
    v = c.get("/api/admin/fx_samples/video/A1.mp4")
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4" and v.content.startswith(b"\x00\x00\x00\x18ftyp")


def test_없는_견본과_번호_아닌_주소는_404(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    assert c.get("/api/admin/fx_samples/video/Z9.mp4").status_code == 404
    assert c.get("/api/admin/fx_samples/video/..%2Fsecret.mp4").status_code == 404
    assert c.get("/api/admin/fx_samples/video/a1.mp4").status_code == 404


def test_올린_견본이_없으면_빈_목록(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    (tmp_path / "fx_samples" / "manifest.json").unlink()
    d = c.get("/api/admin/fx_samples").json()
    assert d["ok"] and d["groups"] == []


def test_사이드바_항목은_관리자_전용(monkeypatch):
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    line = next(ln for ln in js.splitlines() if 'href: "/fx_samples"' in ln)
    assert "admin: true" in line
