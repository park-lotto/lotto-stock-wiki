"""죽은 키를 다시 부르나(B-45). api_events에서 같은 key_tail이 auth_dead를 두 번 이상 —
첫 사망 이후 재호출 건수. 0이어야 한다(handoff/키사망차단.md:34 '사흘째 재호출').

★회원 개인 키(customer_id 있음) 죽음은 운영 사고가 아니다 — api_health.verdict()가 이미
이 구분을 하고 있다(2026-09-04 사장님 실측: typecast 183건·elevenlabs 252건이 전부 회원
340·268 소유였는데 '죽은 키'로 danger가 울렸다. api_health.py verdict()의 dead_by_svc/
member_dead 분기 참조 — customer_id가 있으면 problems가 아니라 warns로 뺀다).
이 항목도 같은 기준을 쓴다: customer_id IS NULL(운영 키)인 재호출만 빨강, 회원 키
재호출은 ::member 서브키로 따로 기록하되 빨강을 켜지 않는다(정보성, ok=True)."""
from datetime import timedelta
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "죽은 API 키를 다시 부르나", "every": "1h", "source": "api_events outcome=auth_dead"}


def measure(ctx):
    since = (ctx["now"] - timedelta(hours=24)).isoformat()
    try:
        conn = ro_connect(ctx.get("events_db") or ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_dead_key_recall", META["name"], None, None, detail=repr(e))]
    try:
        rows = conn.execute(
            "SELECT service, key_tail, customer_id, COUNT(*) AS n, MIN(ts) AS first_ts FROM api_events "
            "WHERE outcome='auth_dead' AND ts>=? AND key_tail IS NOT NULL "
            "GROUP BY service, key_tail, customer_id HAVING n>1", (since,)).fetchall()
    finally:
        conn.close()
    ops_rows = [r for r in rows if not r["customer_id"]]
    member_rows = [r for r in rows if r["customer_id"]]

    ops_recalls = sum(r["n"] - 1 for r in ops_rows)
    ops_detail = "; ".join(f"{r['service']} …{r['key_tail']} {r['n']-1}회 재호출" for r in ops_rows) or "재호출 없음"
    out = [Sample("h_dead_key_recall", META["name"], ops_recalls, ops_recalls == 0,
                  detail=ops_detail, evidence_url="/apiwatch")]

    member_recalls = sum(r["n"] - 1 for r in member_rows)
    member_detail = "; ".join(
        f"{r['service']} 회원{r['customer_id']} …{r['key_tail']} {r['n']-1}회 재호출(회원 개인 키 — 운영 사고 아님)"
        for r in member_rows) or "재호출 없음"
    out.append(Sample("h_dead_key_recall::member", f"{META['name']} — 회원 키(참고용)",
                      member_recalls, True, detail=member_detail, evidence_url="/apiwatch"))
    return out
