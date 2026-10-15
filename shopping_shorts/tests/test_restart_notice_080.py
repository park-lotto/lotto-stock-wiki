# -*- coding: utf-8 -*-
"""관제 080: 웹 재시작 자동 조치·안내 — 서버는 모든 응답에 버전 표식(X-SS-Boot), 화면 공용 fetch(sidebar.js)가 재시도·띠."""
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod


def test_every_response_carries_boot_header():
    c = TestClient(app_mod.app)
    r1 = c.get("/sidebar.js")
    r2 = c.get("/없는주소-404")
    assert r1.headers.get("x-ss-boot") == app_mod._SS_BOOT_ID
    assert r2.headers.get("x-ss-boot") == app_mod._SS_BOOT_ID       # 404 에도 붙는다(화면이 어떤 응답으로든 알아챈다)


def test_sidebar_retries_only_get_and_warns_on_post():
    js = (Path(app_mod.__file__).parent / "static" / "sidebar.js").read_text(encoding="utf-8")
    assert "X-SS-Boot" in js and "_SS_RETRY_MS" in js
    assert "같은 버튼을 한 번 더 눌러 주세요" in js and "새 버전이 적용됐어요" in js
    assert "return _ssFetch(this, arguments)" in js                     # 전 화면 공용 fetch 가 실제로 이 경로를 탄다
