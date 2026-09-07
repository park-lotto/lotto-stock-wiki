"""결제 0원인데 전기능인 계정(B-52). 체험(trial_ends_at) 중인 계정은 의도된 것이라 제외.

★admin=1 · cid=0 은 원래부터 전기능이라 제외(오탐 방지).
★approved_at이 있고 payments가 없는 경우도 있을 수 있다(사장님이 admin 화면에서
  손으로 pro/기간을 준 경우) — 이건 '결제 없이 열림'이 사실이므로 그대로 빨강이다.
  단, trial_ends_at 창 안의 정상 무료체험만 걸러낸다."""
import time
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "결제 없이 전기능이 열린 회원", "every": "1h", "source": "customers × payments"}


def measure(ctx):
    now = int(time.time())
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_free_full_access", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT id FROM customers c WHERE id!=0 AND admin=0 AND (plan='pro' OR full_access_until>?) "
            "AND COALESCE(trial_ends_at,0) < ? "
            "AND NOT EXISTS(SELECT 1 FROM payments p WHERE p.customer_id=c.id AND p.amount>0)",
            (now, now)).fetchall()
    finally:
        conn.close()
    ids = [str(r["id"]) for r in rows]
    return [Sample("h_free_full_access", META["name"], len(ids), len(ids) == 0,
                   detail=("회원 " + ",".join(ids[:20])) if ids else "없음", evidence_url="/admin")]
