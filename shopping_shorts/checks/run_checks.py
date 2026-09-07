"""점검 진입점 하나. health: 라이브 DB 읽기만(미리보기 불필요, 5분 타이머가 매번 부른다).
deploy/daily: Task 12에서 채운다."""
import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from shopping_shorts.checks import db, discover
from shopping_shorts.checks.ro import LIVE_DB
from shopping_shorts.checks.verdict import GRAY, Result, Sample

SERVICE = "shopping-shorts"
REPO = Path(__file__).resolve().parents[2]


def head_sha(repo=REPO):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _record_discover_errors(conn, run_id):
    """discover.py 계약: LAST_ERRORS에 담긴 import 실패 항목마다 GRAY Result를 남긴다.
    항목 파일이 문법 오류로 깨지면 그 점검은 영영 안 돌면서 화면은 초록으로 보이는
    사고를 막는다 — 깨진 모듈도 화면에 '판정 불가'로 보여야 한다."""
    for full_name, exc_repr in discover.LAST_ERRORS:
        mod_name = full_name.rsplit(".", 1)[-1]
        r = Result(
            layer="L3",
            name=f"점검 항목 로드 실패 — {mod_name}",
            verdict=GRAY,
            reason=f"import 실패: {exc_repr}",
            signature=f"L3:import:{mod_name}",
        )
        if run_id is not None:
            db.add_result(conn, run_id, r)


def run_health(conn, ctx, force=False, run_id=None):
    out = []
    mods = discover.discover("health")
    _record_discover_errors(conn, run_id)
    for m in mods:
        item = m.__name__.rsplit(".", 1)[-1]
        if not force and not discover.is_due(m.META["every"], db.last_sample_ts(conn, item)):
            continue
        try:
            samples = m.measure(ctx)
        except Exception as e:  # noqa: BLE001 — 항목 하나의 예외가 나머지를 막지 않는다
            samples = [Sample(item, m.META["name"], None, None, detail=f"measure 예외: {e!r}")]
        for s in samples:
            db.add_sample(conn, s)
            out.append(s)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", choices=["health", "deploy", "daily"], required=True)
    ap.add_argument("--force", action="store_true", help="주기 무시하고 전부")
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    conn = db.open_db(a.db)
    ctx = {"live_db": LIVE_DB, "base_url": None, "now": datetime.now(timezone.utc)}
    if a.trigger == "health":
        run_id = db.start_run(conn, SERVICE, "health", head_sha())
        samples = run_health(conn, ctx, force=a.force, run_id=run_id)
        rows = db.latest_results(conn, run_id)
        overall = GRAY if any(r["verdict"] == GRAY for r in rows) else "green"
        db.finish_run(conn, run_id, overall)
        for s in samples:
            print(f"[{s.verdict:6}] {s.name} — {s.detail}")
        for r in rows:
            print(f"[{r['verdict']:6}] {r['name']} — {r['reason']}")
        return 0
    print("deploy/daily는 Task 12에서 구현", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
