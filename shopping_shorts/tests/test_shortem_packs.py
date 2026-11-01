# -*- coding: utf-8 -*-
"""숏템팩(관제 222) — 관리자 전용 팩 모음 화면.

못 박는 것:
1. /shortem_packs · .html · 목록 API 모두 비관리자는 403(정적 마운트로 뚫리지 않는다).
2. 목록은 팩 주인 함수를 그대로 읽는다 — 효과음팩 = sfx_pack.list_packs, 배경음 = bgm_lib.list_tracks, 글꼴 = static/fonts.
3. 사이드바 '숏템팩' 묶음은 묶음째 관리자 전용이고 세부 팩 칸으로 간다. 효과 견본은 이 묶음으로 옮겼다.
4. 화면의 장면 효과 이름은 편집기 효과 탭(out/scene-style-connect.js SCENE_FX)과 같다.
그림·소리 실측은 tools/shortem_packs/check_page.py(브라우저)가 한다.
"""
import json
import pathlib
import re

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATIC = ROOT / "shopping_shorts" / "static"


def _client(monkeypatch, admin=True):
    if admin:
        monkeypatch.setattr(app_module, "_require_admin", lambda request: None)
    else:
        monkeypatch.setattr(app_module, "_require_admin",
                            lambda request: JSONResponse({"error": "관리자 전용"}, status_code=403))
    return TestClient(app_module.app)


def test_비관리자는_세_주소_모두_403(monkeypatch):
    c = _client(monkeypatch, admin=False)
    for url in ("/shortem_packs", "/shortem_packs.html", "/api/admin/shortem_packs"):
        assert c.get(url).status_code == 403, url


def test_목록은_팩_주인을_그대로_읽는다(monkeypatch):
    from shopping_shorts import sfx_pack, bgm_lib
    c = _client(monkeypatch)
    assert "숏템팩" in c.get("/shortem_packs").text
    d = c.get("/api/admin/shortem_packs").json()
    assert d["ok"]
    assert [p["name"] for p in d["sfx_packs"]] == [n for n, _ in sfx_pack.list_packs()]
    assert all(len(p["slots"]) == len(sfx_pack.SLOTS) for p in d["sfx_packs"])
    assert [t["id"] for t in d["bgm"]] == [t["id"] for t in bgm_lib.list_tracks()]
    assert d["fonts"] == sorted(f.name for f in (STATIC / "fonts").iterdir() if f.suffix.lower() in (".ttf", ".otf"))
    assert {"count", "engines"} <= set(d["voices"]) and {"total", "emotions"} <= set(d["memes"])
    assert len(d["sfx_drawer"]) == 8


def test_사이드바_숏템팩_묶음():
    src = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    start = src.index('{ label: "숏템팩", admin: true, items: [')
    block = src[start:src.index("] },", start)]
    hrefs = re.findall(r'href: "([^"]+)"', block)
    assert hrefs[0] == "/shortem_packs" and "/fx_samples" in hrefs
    assert all('admin: true' in line for line in block.splitlines() if 'href:' in line)
    page = (STATIC / "shortem_packs.html").read_text(encoding="utf-8")
    for h in hrefs:
        if "#" in h:
            assert f"section('{h.split('#')[1]}'" in page, h   # 세부 팩 칸이 화면에 있다
    # 효과 견본은 제작 묶음에서 빠졌다(두 곳에 두지 않는다)
    assert src.count('href: "/fx_samples"') == 1


def test_장면효과_이름은_편집기와_같다():
    page = (STATIC / "shortem_packs.html").read_text(encoding="utf-8")
    mine = dict(re.findall(r"(\w+):'([^']+)'", page[page.index("const SCENE_FX_LABEL={"):].split("};")[0]))
    conn = (ROOT / "out" / "scene-style-connect.js").read_text(encoding="utf-8")
    line = conn[conn.index("const SCENE_FX=["):].split(";")[0]
    editor = {k: v for k, v in re.findall(r"\['(\w+)','([^']+)'\]", line) if k != "none"}
    assert mine == editor
