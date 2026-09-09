"""결제 고객이 랭킹만으로 떨어지지 않았나(B-51).

★0순위-B: SQL로 권한을 재구현하지 않는다 — `access_level()`(app.py:12164)만이 유일한
  판정 함수다. SQL은 결제 이력이 있는 계정으로 **후보만 좁히고**, 최종 판정은
  `access_level(id, now=epoch, cust=행)`으로 라이브와 같은 함수를 호출해 확인한다.

★관리자(cid=0)는 후보에서 제외 — payments가 있어도 강등 개념이 없다.
★후보가 너무 많으면(CANDIDATE_CAP) 판단 불가로 회색 처리하고 detail에 남긴다."""
import time
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "결제했는데 랭킹만 보이는 회원", "every": "1h", "source": "customers × payments × access_level"}
CANDIDATE_CAP = 200


def measure(ctx):
    now = int(time.time())
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_paid_downgraded", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT c.* FROM customers c WHERE c.id!=0 "
            "AND EXISTS(SELECT 1 FROM payments p WHERE p.customer_id=c.id AND p.amount>0)").fetchall()
    finally:
        conn.close()

    if len(rows) > CANDIDATE_CAP:
        return [Sample("h_paid_downgraded", META["name"], None, None,
                       detail=f"후보 {len(rows)}건 > 상한 {CANDIDATE_CAP} — 판단 보류")]

    try:
        from shopping_shorts.app import access_level
    except Exception as e:  # noqa: BLE001
        return [Sample("h_paid_downgraded", META["name"], None, None, detail=f"access_level import 실패: {e!r}")]

    ids = []
    for r in rows:
        cust = dict(r)
        try:
            level = access_level(cust["id"], now=now, cust=cust)
        except Exception as e:  # noqa: BLE001
            return [Sample("h_paid_downgraded", META["name"], None, None,
                           detail=f"access_level 호출 실패(id={cust['id']}): {e!r}")]
        if level != "full":
            ids.append(str(cust["id"]))
    return [Sample("h_paid_downgraded", META["name"], len(ids), len(ids) == 0,
                   detail=("회원 " + ",".join(ids[:20])) if ids else "없음", evidence_url="/admin")]
