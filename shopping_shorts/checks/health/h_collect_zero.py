"""'오류 없이 0건'인 수집(B-42). 네이버클립(dict 튜플 언패킹→0건)·쓰레드 사고와 같은 모양.
last_run::<platform>의 items가 0이면 빨강. 기록 자체가 없으면 h_ranking_fresh가 잡으므로 여기선 회색."""
import json
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample
from shopping_shorts.checks.health.h_ranking_fresh import PLATFORMS

META = {"name": "오류 없이 0건인 수집", "every": "1h", "source": "reference.db settings last_run::*"}


def measure(ctx):
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_collect_zero", META["name"], None, None, detail=repr(e))]
    out = []
    try:
        for p in PLATFORMS:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (f"last_run::{p}",)).fetchone()
            if not row or not row["value"]:
                out.append(Sample(f"h_collect_zero::{p}", f"{META['name']} — {p}", None, None, detail="기록 없음"))
                continue
            n = len(json.loads(row["value"]).get("items") or [])
            out.append(Sample(f"h_collect_zero::{p}", f"{META['name']} — {p}", n, n > 0, detail=f"{n}건"))
    finally:
        conn.close()
    return out
