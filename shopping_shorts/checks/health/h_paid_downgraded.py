"""결제 고객이 랭킹만으로 떨어지지 않았나(B-51). reference_체험과_유료가_같은_필드를_쓴다 —
payments>0인데 plan이 pro가 아니고 full_access_until도 지난 계정.

★관리자(cid=0)는 제외 — payments가 있어도 강등 개념이 없다.
★결제 시각 이후 승인 기간(full_access_until)이 갱신 중일 수 있으니, '가장 최근 결제'
  기준으로만 본다(옛 결제 하나 때문에 최신 재결제 뒤 정상 상태를 빨강으로 잘못 켜지 않게)."""
import time
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "결제했는데 랭킹만 보이는 회원", "every": "1h", "source": "customers × payments"}


def measure(ctx):
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_paid_downgraded", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT c.id FROM customers c WHERE c.id!=0 AND c.plan!='pro' AND c.full_access_until<? "
            "AND EXISTS(SELECT 1 FROM payments p WHERE p.customer_id=c.id AND p.amount>0)",
            (int(time.time()),)).fetchall()
    finally:
        conn.close()
    ids = [str(r["id"]) for r in rows]
    return [Sample("h_paid_downgraded", META["name"], len(ids), len(ids) == 0,
                   detail=("회원 " + ",".join(ids[:20])) if ids else "없음", evidence_url="/admin")]
