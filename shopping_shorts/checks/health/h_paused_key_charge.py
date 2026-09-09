"""꺼둔 고객 키가 본사 포인트를 깎나(B-50). reference_vmake_paused_편법행이_과금을_계속한다 —
customer_keys.service가 정식 이름(keyroute.SVC_*) 밖이면 '키 없음'으로 읽혀 본사 키 과금.

★status는 안 본다 — 이 사고의 본질은 '끈 방법'(service 필드에 옛 이름을 붙여 사실상
  끈 것) 그 자체가 이미 라우팅을 깨뜨린다는 것. status가 뭐든 service 철자가 정식이
  아니면 그 즉시 라우팅 실패 후보다."""
from shopping_shorts import keyroute
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "꺼둔 회원 키가 본사 포인트를 깎나", "every": "1h", "source": "customer_keys.service"}
VALID = {v for k, v in vars(keyroute).items() if k.startswith("SVC_") and isinstance(v, str)}


def measure(ctx):
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_paused_key_charge", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute("SELECT customer_id, service FROM customer_keys").fetchall()
    finally:
        conn.close()
    bad = [f"{r['customer_id']}:{r['service']}" for r in rows if r["service"] not in VALID]
    return [Sample("h_paused_key_charge", META["name"], len(bad), len(bad) == 0,
                   detail=("정식 아닌 service " + ", ".join(bad[:20])) if bad else "전부 정식 이름")]
