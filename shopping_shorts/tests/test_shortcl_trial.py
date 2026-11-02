# -*- coding: utf-8 -*-
"""숏클 무료 업그레이드 1주(관제 300) — 승인·만료·재신청·관리자 승인 우선."""
import pytest
from shopping_shorts import claude_portal as cp
from shopping_shorts.store import Store


@pytest.fixture
def st(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("claude_portal_enabled", "admin")
    return s


def test_신청하면_열리고_7일뒤_닫히고_재신청불가(st, monkeypatch):
    assert cp.trial_state(st, 5, True)["available"]
    cp.claim_trial(5, True, st)
    assert cp.portal_open(st, 5)
    assert cp.trial_state(st, 5, True) == {"available": False, "active": True, "days_left": 7}
    real = cp._now()
    monkeypatch.setattr(cp, "_now", lambda: real + 7 * 86400 + 1)
    assert not cp.portal_open(st, 5)
    assert not cp.trial_state(st, 5, True)["available"]
    with pytest.raises(cp.PortalError):
        cp.claim_trial(5, True, st)


def test_자격없으면_거절(st):
    with pytest.raises(cp.PortalError):
        cp.claim_trial(5, False, st)
    assert not cp.portal_open(st, 5)


def test_관리자_승인은_기한없음(st, monkeypatch):
    cp.claim_trial(5, True, st)
    cp.set_member(5, True, st)
    real = cp._now()
    monkeypatch.setattr(cp, "_now", lambda: real + 30 * 86400)
    assert cp.portal_open(st, 5)


def test_기존_승인회원은_버튼없음(st):
    cp.set_member(9, True, st)
    assert not cp.trial_state(st, 9, True)["available"]


def test_신청주소는_로그인세션_경로():
    """/api/claude/ 는 공개 접두사라 세션이 안 붙는다 — 반드시 me/ 아래(라이브 사고 11-01)."""
    from pathlib import Path
    root = Path(cp.__file__).parent
    assert '@app.post("/api/claude/me/trial")' in (root / "app.py").read_text(encoding="utf-8")
    assert '"/api/claude/me/trial"' in (root / "static/settings.html").read_text(encoding="utf-8")
