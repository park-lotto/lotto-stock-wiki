# -*- coding: utf-8 -*-
"""Vertex 미등록 안내(10-07 사장님) — 판정 vertex_route.needs_notice 한 곳 · 하루 1회 · 3단계 시작 안내(막지 않음) · 효과음 ⭐ API."""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import vertex_route
from shopping_shorts.store import Store


def test_판정_관리자_제외_등록회원_제외(monkeypatch):
    monkeypatch.setattr(vertex_route, "_is_admin", lambda c: int(c) == 0)
    monkeypatch.setattr(vertex_route, "member_info", lambda c: {"project_id": "p"} if int(c) == 7 else None)
    assert vertex_route.needs_notice(0) is False
    assert vertex_route.needs_notice(7) is False
    assert vertex_route.needs_notice(5) is True


@pytest.fixture
def c(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(vertex_route, "needs_notice", lambda cid: True)
    return TestClient(app_mod.app)


def test_하루1회_닫으면_그날은_안뜸(c, monkeypatch):
    d = c.get("/api/settings/vertex_notice").json()
    assert d["show"] is True and d["url"] == "/settings#vertexCard" and "Vertex" in d["text"]
    assert c.post("/api/settings/vertex_notice/seen").json()["ok"]
    assert c.get("/api/settings/vertex_notice").json()["show"] is False
    monkeypatch.setattr(app_mod, "_vertex_notice_day", lambda: "2099-01-01")       # 다음 날
    assert c.get("/api/settings/vertex_notice").json()["show"] is True


def test_등록하면_안뜸(c, monkeypatch):
    monkeypatch.setattr(vertex_route, "needs_notice", lambda cid: False)
    assert c.get("/api/settings/vertex_notice").json()["show"] is False
    assert app_mod._vertex_notice(5) is None


def test_3단계_시작_응답에_안내가_실린다():
    import inspect
    src = inspect.getsource(app_mod.api_produce_mix_start)
    assert '"vertex_notice": _vn' in src and "_vertex_notice(" in src
