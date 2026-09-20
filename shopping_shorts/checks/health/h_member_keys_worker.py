"""회원 키가 워커에서도 쓰이나(B-46). reference_회원키가_제작에_안쓰였다 — 합류가 웹 startup에만.
api_heartbeats(proc='worker')의 detail(keypool.resync_pools가 남김)이 24h 안에 있어야 한다."""
from datetime import timedelta
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "회원 키가 워커에서도 쓰이나", "every": "1h", "source": "api_heartbeats proc=worker"}


def measure(ctx):
    since = (ctx["now"] - timedelta(hours=24)).isoformat()
    try:
        conn = ro_connect(ctx.get("events_db") or ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_member_keys_worker", META["name"], None, None, detail=repr(e))]
    try:
        row = conn.execute("SELECT COUNT(*) AS n, MAX(ts) AS last FROM api_heartbeats "
                           "WHERE proc='worker' AND ts>=? AND detail IS NOT NULL", (since,)).fetchone()
    finally:
        conn.close()
    n = row["n"] if row else 0
    return [Sample("h_member_keys_worker", META["name"], n, n > 0,
                   detail=f"워커 키풀 하트비트 {n}건, 마지막 {row['last'] if row else '-'}")]
