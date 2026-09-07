"""죽은 키를 다시 부르나(B-45). api_events에서 같은 key_tail이 auth_dead를 두 번 이상 —
첫 사망 이후 재호출 건수. 0이어야 한다(handoff/키사망차단.md:34 '사흘째 재호출')."""
from datetime import timedelta
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample
from shopping_shorts.api_health import _DB_PATH as EVENTS_DB

META = {"name": "죽은 API 키를 다시 부르나", "every": "1h", "source": "api_events outcome=auth_dead"}


def measure(ctx):
    since = (ctx["now"] - timedelta(hours=24)).isoformat()
    try:
        conn = ro_connect(ctx.get("events_db") or ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_dead_key_recall", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT service, key_tail, COUNT(*) AS n, MIN(ts) AS first_ts FROM api_events "
            "WHERE outcome='auth_dead' AND ts>=? AND key_tail IS NOT NULL "
            "GROUP BY service, key_tail HAVING n>1", (since,)).fetchall()
    finally:
        conn.close()
    recalls = sum(r["n"] - 1 for r in rows)
    detail = "; ".join(f"{r['service']} …{r['key_tail']} {r['n']-1}회 재호출" for r in rows) or "재호출 없음"
    return [Sample("h_dead_key_recall", META["name"], recalls, recalls == 0, detail=detail, evidence_url="/apiwatch")]
