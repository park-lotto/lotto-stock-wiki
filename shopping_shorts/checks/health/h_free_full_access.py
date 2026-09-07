"""결제 0원인데 전기능인 계정(B-52).

★0순위-B: 권한 판정을 SQL로 재구현하지 않는다. `access_level()`(app.py:12164)가 유일한
  판정 함수이고, 규칙이 여러 번 바뀌었다(2026-08-21 plan='trial'→ranking_only 확정 등).
  SQL로 베끼면 다음 규칙 변경 때 또 어긋난다(리뷰에서 실측: plan='trial' 정상 체험 계정을
  옛 SQL이 거짓 빨강으로 잡았다).

방식: SQL은 **의심 후보를 좁히는 데만** 쓴다(결제 0원인 계정, 전체 스캔 회피).
후보 각각을 `access_level(id, now=epoch, cust=행)`으로 실제 판정해 "full"이 나오는
것만 최종 빨강으로 센다 — 라이브와 같은 함수라 어긋날 수 없다.

★admin=1 · cid=0 은 원래부터 전기능이라 후보에서 제외.
★후보가 너무 많으면(CANDIDATE_CAP) 판단 불가로 회색 처리하고 detail에 남긴다."""
import time
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "결제 없이 전기능이 열린 회원", "every": "1h", "source": "customers × payments × access_level"}
CANDIDATE_CAP = 200


def measure(ctx):
    now = int(time.time())
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_free_full_access", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT c.* FROM customers c WHERE id!=0 AND admin=0 "
            "AND NOT EXISTS(SELECT 1 FROM payments p WHERE p.customer_id=c.id AND p.amount>0)").fetchall()
    finally:
        conn.close()

    if len(rows) > CANDIDATE_CAP:
        return [Sample("h_free_full_access", META["name"], None, None,
                       detail=f"후보 {len(rows)}건 > 상한 {CANDIDATE_CAP} — 판단 보류")]

    try:
        from shopping_shorts.app import access_level
    except Exception as e:  # noqa: BLE001
        return [Sample("h_free_full_access", META["name"], None, None, detail=f"access_level import 실패: {e!r}")]

    ids = []
    for r in rows:
        cust = dict(r)
        try:
            level = access_level(cust["id"], now=now, cust=cust)
        except Exception as e:  # noqa: BLE001
            return [Sample("h_free_full_access", META["name"], None, None,
                           detail=f"access_level 호출 실패(id={cust['id']}): {e!r}")]
        if level == "full":
            ids.append(str(cust["id"]))
    return [Sample("h_free_full_access", META["name"], len(ids), len(ids) == 0,
                   detail=("회원 " + ",".join(ids[:20])) if ids else "없음", evidence_url="/admin")]
