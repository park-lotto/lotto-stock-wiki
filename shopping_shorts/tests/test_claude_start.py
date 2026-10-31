# -*- coding: utf-8 -*-
"""회원별 시작 한 줄·시작.md(관제 294) — 파일에는 키 원문이 없고, 인증값으로 지금 키를 받되 옛 키를 끊지 않는다."""
import io
import zipfile

import pytest

from shopping_shorts import app as app_module
from shopping_shorts import claude_portal as cp
from shopping_shorts.store import Store


@pytest.fixture
def st(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("CLAUDE_LICENSE_SECRET", "test-secret")
    store = Store(tmp_path / "t.db")
    store.set_setting("claude_portal_enabled", "1")
    return store


def test_인증값으로_지금_키를_받고_옛_키를_끊지_않는다(st):
    key = cp.issue_license(7, st)["key"]
    assert cp.start_redeem(cp.start_token(7), st)["key"] == key
    assert cp.verify_license(key, st)["cid"] == 7


def test_키가_없는_회원은_새로_발급(st):
    got = cp.start_redeem(cp.start_token(8), st)["key"]
    assert cp.verify_license(got, st)["cid"] == 8


def test_회수된_키는_되살리지_않고_새_키(st):
    key = cp.issue_license(9, st)["key"]
    new = cp.issue_license(9, st)["key"]
    assert cp.start_redeem(cp.start_token(9), st)["key"] == new != key


def test_파일에_키_원문이_없다(st):
    key = cp.issue_license(7, st)["key"]
    md = cp.start_md(7, "https://x.test")
    assert key not in md and "SHORTEM_START" in md
    with zipfile.ZipFile(io.BytesIO(cp.start_zip(7, "https://x.test"))) as z:
        body = z.read("시작.md").decode("utf-8")
    assert key not in body and "SHORTEM_START" in body


@pytest.mark.parametrize("bad", ["", "x", "7.9999999999.abc", "a.b.c"])
def test_위조는_거절(st, bad):
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(bad, st)
    assert e.value.code == "bad_key"


def test_다른_회원_번호로_바꾸면_거절(st):
    cid, exp, sig = cp.start_token(7).split(".")
    with pytest.raises(cp.PortalError):
        cp.start_redeem(f"8.{exp}.{sig}", st)


def test_기한_지나면_거절(st, monkeypatch):
    token = cp.start_token(7)
    monkeypatch.setattr(cp, "_now", lambda: int(token.split(".")[1]) + 1)
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(token, st)
    assert e.value.code == "expired"


def test_스위치가_꺼지면_거절(st):
    st.set_setting("claude_portal_enabled", "")
    with pytest.raises(cp.PortalError) as e:
        cp.start_redeem(cp.start_token(7), st)
    assert e.value.code == "disabled"


def test_설치_스크립트에_주소가_채워지고_비밀이_없다():
    from fastapi.testclient import TestClient
    r = TestClient(app_module.app).get("/api/claude/start.ps1", headers={"host": "stmaker.kr"})
    assert r.status_code == 200 and "https://stmaker.kr" in r.text and "__BASE__" not in r.text and "SHORTEM-L1." not in r.text


def test_승인하면_열리고_해제하면_닫힌다(st, monkeypatch):
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    st.set_setting("claude_portal_enabled", "admin")
    assert not app_module._setting_gate(st, "claude_portal_enabled", 7)
    cp.set_member(7, True, st)
    cp.set_member(11, True, st)
    assert app_module._setting_gate(st, "claude_portal_enabled", 7)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 8)
    cp.set_member(7, False, st)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 7)
    cp.set_member(11, False, st)
    assert st.get_setting("claude_portal_enabled", "") == "admin"


def test_전체_공개면_승인_목록을_덮지_않는다(st):
    with pytest.raises(cp.PortalError):
        cp.set_member(7, True, st)
    assert st.get_setting("claude_portal_enabled", "") == "1"


def test_회원_1번_승인이_전체_공개가_되지_않는다(st, monkeypatch):
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    st.set_setting("claude_portal_enabled", "admin")
    cp.set_member(1, True, st)
    assert app_module._setting_gate(st, "claude_portal_enabled", 1)
    assert not app_module._setting_gate(st, "claude_portal_enabled", 2)
    cp.set_member(1, False, st)
    assert st.get_setting("claude_portal_enabled", "") == "admin"


def test_더블클릭_파일에_키_원문이_없다(st):
    key = cp.issue_license(7, st)["key"]
    body = cp.start_cmd(7, "https://x.test")
    assert key not in body and "SHORTEM_START" in body and body.startswith("@echo off")


def test_메뉴_스크립트에_비밀이_없다():
    from fastapi.testclient import TestClient
    r = TestClient(app_module.app).get("/api/claude/start_menu.ps1")
    assert r.status_code == 200 and "숏클 시작" in r.text and "SHORTEM-L1." not in r.text
