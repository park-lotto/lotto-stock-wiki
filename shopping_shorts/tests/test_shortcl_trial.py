# -*- coding: utf-8 -*-
"""숏클 Pro 전환(관제 306)과 승인 — 전환·동시 클릭·해제·관리자 승인 우선."""
import pytest
from shopping_shorts import claude_portal as cp
from shopping_shorts.store import Store


@pytest.fixture
def st(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.set_setting("claude_portal_enabled", "admin")
    return s


def test_Pro_회원은_버튼으로_전환되고_기한이_없다(st, monkeypatch):
    assert cp.trial_state(st, 5, True)["available"]
    assert cp.claim_trial(5, True, st) == {"ok": True, "moved": True}
    assert cp.portal_open(st, 5) and not cp.trial_state(st, 5, True)["available"]
    real = cp._now()
    monkeypatch.setattr(cp, "_now", lambda: real + 400 * 86400)
    assert cp.portal_open(st, 5)


def test_전환하면_관리자표에_숏클_무료이동으로_남는다(st):
    st.save_program_member(5, 1, 0, "", "", "조교A")
    cp.claim_trial(5, True, st)
    m = st.program_members()[5]
    assert m["shortcl"] and m["shortem"] and m["move"] == "free" and m["tutor"] == "조교A"


def test_여러_명이_동시에_눌러도_빠지지_않는다(st):
    import concurrent.futures as cf
    ids = list(range(100, 140))
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: cp.claim_trial(i, True, st), ids))
    assert all(cp.portal_open(st, i) for i in ids)
    assert set(ids) <= set(st.program_members())


def test_다시_눌러도_그대로(st):
    cp.claim_trial(5, True, st)
    assert cp.claim_trial(5, True, st) == {"ok": True, "already": True}


def test_관리자가_해제하면_닫히고_다시_못_누른다(st):
    cp.claim_trial(5, True, st)
    cp.set_member(5, False, st)
    assert not cp.portal_open(st, 5) and not cp.trial_state(st, 5, True)["available"]
    with pytest.raises(cp.PortalError):
        cp.claim_trial(5, True, st)


def test_Pro_아니면_버튼없음(st):
    assert not cp.trial_state(st, 5, False)["available"]


def test_자격없으면_거절(st):
    with pytest.raises(cp.PortalError):
        cp.claim_trial(5, False, st)
    assert not cp.portal_open(st, 5)


def test_관리자_승인은_기한없음(st, monkeypatch):
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
