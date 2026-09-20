"""유료 게이트가 새지 않나(B-53). ranking_only 회원 세션으로 유료 API를 불러 402/403이 아닌 응답을 센다.
쿠키는 앱의 _sign_session을 그대로 쓴다(형태를 발명하지 않는다). 대상 API는 _ranking_only_blocked가
막는 경로 중 GET 3개 — 실제 변경은 일으키지 않는다.

★base_url 없음 = 회색(전역 제약). ★ranking_only 회원이 라이브DB에 하나도 없으면(전부 pro/체험 등)
  판단 불가로 회색 — 없는 사람을 상대로 "안 샜다"고 초록을 우기지 않는다."""
import time
import requests
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample

META = {"name": "유료 기능이 무료 회원에게 새나", "every": "6h", "source": "미리보기 HTTP"}
PROBES = ("/api/produce/works", "/api/produce/tts/credits", "/api/mix/status/nonexistent")


def measure(ctx):
    base = ctx.get("base_url")
    if not base:
        return [Sample("h_paid_gate", META["name"], None, None, detail="base_url 없음")]
    try:
        conn = ro_connect(ctx["live_db"])
        row = conn.execute("SELECT id FROM customers WHERE id!=0 AND admin=0 AND plan!='pro' "
                           "AND full_access_until<? AND approved_at IS NOT NULL LIMIT 1",
                           (int(time.time()),)).fetchone()
        conn.close()
    except Exception as e:  # noqa: BLE001
        return [Sample("h_paid_gate", META["name"], None, None, detail=repr(e))]
    if not row:
        return [Sample("h_paid_gate", META["name"], None, None, detail="ranking_only 회원 없음")]
    from shopping_shorts.app import _sign_session, _COOKIE_MAX_AGE
    cookie = _sign_session(int(row["id"]), int(time.time()) + _COOKIE_MAX_AGE)
    leaks = []
    for path in PROBES:
        try:
            r = requests.get(base + path, cookies={"dash_auth": cookie}, timeout=10)
        except Exception as e:  # noqa: BLE001 — 접속 실패는 새는 게 아니라 판단 불가
            return [Sample("h_paid_gate", META["name"], None, None, detail=repr(e))]
        if r.status_code not in (401, 402, 403):
            leaks.append(f"{path}={r.status_code}")
    return [Sample("h_paid_gate", META["name"], len(leaks), len(leaks) == 0,
                   detail=("통과됨: " + "; ".join(leaks)) if leaks else f"회원 {row['id']}로 3경로 전부 차단")]
