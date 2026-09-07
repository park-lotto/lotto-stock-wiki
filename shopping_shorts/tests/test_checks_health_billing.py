import sqlite3
import time
from datetime import datetime, timezone

from shopping_shorts.checks.health import (
    h_free_full_access,
    h_paid_downgraded,
    h_paid_gate,
    h_paused_key_charge,
)


def _db(tmp_path):
    p = tmp_path / "reference.db"
    c = sqlite3.connect(p)
    c.executescript("""
    CREATE TABLE customers(id INTEGER PRIMARY KEY, plan TEXT, full_access_until INTEGER, approved_at INTEGER,
                           admin INTEGER DEFAULT 0, pro_from INTEGER, pro_until INTEGER, trial_ends_at INTEGER);
    CREATE TABLE payments(id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER, paid_at INTEGER);
    CREATE TABLE customer_keys(id INTEGER PRIMARY KEY, customer_id INTEGER, service TEXT, status TEXT);
    """)
    c.commit()
    return p, c


# ── B-51 결제고객 강등 ─────────────────────────────────────────────
def test_paid_customer_with_free_plan_is_red(tmp_path):
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(5,'free',0,?,0,NULL,NULL,NULL)", (now - 100,))
    c.execute("INSERT INTO payments(customer_id,amount,paid_at) VALUES(5,77000,?)", (now - 10,))
    c.commit()
    s = h_paid_downgraded.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and s.value == 1 and "5" in s.detail


def test_paid_customer_still_within_full_access_is_not_red(tmp_path):
    """오탐 방지: 결제했고 아직 승인 기간(full_access_until) 안이면 강등이 아니다."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(6,'free',?,?,0,NULL,NULL,NULL)", (now + 86400 * 10, now - 100))
    c.execute("INSERT INTO payments(customer_id,amount,paid_at) VALUES(6,77000,?)", (now - 10,))
    c.commit()
    s = h_paid_downgraded.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


def test_admin_with_payments_and_free_plan_is_not_red(tmp_path):
    """오탐 방지: cid=0(사장님)은 강등 판정 대상에서 제외."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(0,'free',0,?,1,NULL,NULL,NULL)", (now - 100,))
    c.execute("INSERT INTO payments(customer_id,amount,paid_at) VALUES(0,77000,?)", (now - 10,))
    c.commit()
    s = h_paid_downgraded.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


# ── B-52 0원 전기능 ────────────────────────────────────────────────
def test_free_customer_with_future_full_access_is_red(tmp_path):
    """진짜 위반: 승인됐고(approved_at 있음) plan은 free인데 full_access_until만 미래 —
    access_level()이 'full'을 내는 실제 강등-반대 사고."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(7,'free',?,?,0,NULL,NULL,NULL)", (now + 86400 * 30, now))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and s.value == 1


def test_pro_without_expiry_and_no_payment_is_still_red(tmp_path):
    """진짜 위반 2: plan='pro'·pro_until 없음(무기한)인데 결제 0원 — access_level()이 'full'.
    access_level을 직접 부르므로 이런 위반은 여전히 잡혀야 한다(점검이 무력화되지 않았는지 확인)."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(14,'pro',0,?,0,NULL,NULL,NULL)", (now,))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and "14" in s.detail


def test_trial_plan_with_future_full_access_is_not_red(tmp_path):
    """★리뷰 Critical 재현 케이스: plan='trial'(2026-08-21 사장님 확정 방식), full_access_until
    미래, 결제 0원. access_level()은 plan='trial'이면 full_access_until과 무관하게 무조건
    'ranking_only'를 낸다(app.py:12216) — 정상 체험 계정이라 빨강이면 안 된다.
    옛 SQL(`plan='pro' OR full_access_until>now`)은 이 케이스를 놓쳐 거짓 빨강을 냈었다."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(15,'trial',?,?,0,NULL,NULL,NULL)", (now + 86400 * 30, now - 100))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0 and "15" not in s.detail


def test_customer_within_trial_window_is_not_red(tmp_path):
    """오탐 방지: 미승인(approved_at NULL) + trial_ends_at 창 안의 정상 무료체험 이벤트는
    access_level()이 'ranking_only'를 낸다 — 빨강이 아니다."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(8,'free',?,NULL,0,NULL,NULL,?)",
              (now + 86400 * 30, now + 86400 * 3))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


def test_pending_unapproved_customer_is_not_red(tmp_path):
    """오탐 방지(리뷰 지적): 승인 대기(approved_at NULL) + 체험창도 지남 → access_level()은
    'pending'(전면차단)이지 'full'이 아니다. 승인 대기 계정이 거짓 빨강을 내면 안 된다."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(16,'free',?,NULL,0,NULL,NULL,NULL)", (now + 86400 * 30,))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


def test_admin_account_with_full_access_is_not_red(tmp_path):
    """오탐 방지: admin=1(관리자) 계정은 전기능이 정상이라 제외."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(9,'free',?,?,1,NULL,NULL,NULL)", (now + 86400 * 30, now))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


def test_paid_pro_customer_is_not_red(tmp_path):
    """오탐 방지: 결제 기록이 있는 pro 회원은 정상."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(10,'pro',0,?,0,NULL,NULL,NULL)", (now,))
    c.execute("INSERT INTO payments(customer_id,amount,paid_at) VALUES(10,77000,?)", (now - 10,))
    c.commit()
    s = h_free_full_access.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


# ── B-50 꺼둔 키 과금 ──────────────────────────────────────────────
def test_unknown_service_name_in_customer_keys_is_red(tmp_path):
    p, c = _db(tmp_path)
    c.execute("INSERT INTO customer_keys(customer_id,service,status) VALUES(57,'vmake_paused','ok')")
    c.commit()
    s = h_paused_key_charge.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is False and "vmake_paused" in s.detail


def test_valid_service_names_are_not_red(tmp_path):
    """오탐 방지: keyroute.SVC_* 정식 이름은 status와 무관하게 빨강이 아니다."""
    p, c = _db(tmp_path)
    c.execute("INSERT INTO customer_keys(customer_id,service,status) VALUES(11,'vmake','off')")
    c.execute("INSERT INTO customer_keys(customer_id,service,status) VALUES(12,'gemini','ok')")
    c.commit()
    s = h_paused_key_charge.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


def test_no_customer_keys_is_not_red(tmp_path):
    """오탐 방지: 회원 키가 아예 없으면 0건으로 정상(회색이 아니라 초록)."""
    p, c = _db(tmp_path)
    s = h_paused_key_charge.measure({"live_db": p, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is True and s.value == 0


# ── B-53 유료 게이트 누수 ──────────────────────────────────────────
def test_paid_gate_without_base_url_is_gray():
    s = h_paid_gate.measure({"live_db": None, "base_url": None, "now": datetime.now(timezone.utc)})[0]
    assert s.ok is None


def test_paid_gate_without_ranking_only_customer_is_gray(tmp_path):
    """오탐 방지: 랭킹전용 회원이 라이브에 하나도 없으면 판단 불가(회색) — 함부로 초록 우기지 않는다."""
    p, c = _db(tmp_path)
    now = int(time.time())
    c.execute("INSERT INTO customers VALUES(13,'pro',0,?,0,NULL,NULL,NULL)", (now,))
    c.commit()
    s = h_paid_gate.measure({"live_db": p, "base_url": "http://127.0.0.1:1", "now": datetime.now(timezone.utc)})[0]
    assert s.ok is None
