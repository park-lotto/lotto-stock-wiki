import time
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_unapproved_signup_sets_24h_trial_window(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("evt", "pw12", approved=False)
    cust = s.get_customer(cid)
    now = int(time.time())
    # 대기중이지만 체험창은 열렸다: now+24h 근처(오차 5분)
    assert cust["approved_at"] is None
    assert cust["trial_ends_at"] is not None
    assert abs(cust["trial_ends_at"] - (now + 24 * 3600)) < 300


def test_approved_signup_has_no_trial_window(tmp_path):
    s = _store(tmp_path)
    cid = s.create_customer("appr", "pw12")  # 기본 approved=True
    assert s.get_customer(cid)["trial_ends_at"] is None
