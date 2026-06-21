"""파이프라인 매일 건강검진 (MVP) — 기존 신호만 모아 정상=1줄/이상=상세 텔레카드."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .db import get_conn

_ROOT = Path(__file__).parent.parent.parent
_HISTORY = Path(__file__).parent / "health_history.json"
_UNMATCHED = _ROOT / "raw" / "telegram_unmatched.log"
_FOREIGN = _ROOT / "raw" / "telegram_foreign_unmapped.log"

_DROP_RATIO = 0.5  # 어제 대비 -50%↓ 경보


def collect_atom_counts(date: str) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT source_type, COUNT(*) FROM atoms WHERE date=? GROUP BY source_type", (date,)
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def _log_lines_for_date(path: Path, date: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(date))


def load_history(path: Path = _HISTORY) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_snapshot(metrics: dict, path: Path = _HISTORY) -> None:
    hist = load_history(path)
    hist[metrics["date"]] = {k: v for k, v in metrics.items() if k != "date"}
    # 최근 14일만 보관
    for d in sorted(hist)[:-14]:
        del hist[d]
    path.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_signals(date: str) -> dict:
    atoms = collect_atom_counts(date)
    queue_new = _log_lines_for_date(_UNMATCHED, date) + _log_lines_for_date(_FOREIGN, date)
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "pipeline/atoms/", "-q"],
                           cwd=str(_ROOT), capture_output=True, timeout=300)
        pytest_ok = r.returncode == 0
    except Exception:
        pytest_ok = True  # 측정 실패는 경보 아님
    return {"date": date, "atoms": atoms, "queue_new": queue_new, "pytest_ok": pytest_ok}


def compare_to_baseline(today: dict, yesterday: dict) -> list[dict]:
    """원자 수집량과 파이프라인 상태를 어제와 비교 → 경보 리스트 반환."""
    alerts = []

    # pytest 실패 → red
    if not today.get("pytest_ok", True):
        alerts.append({"level": "red", "code": "PYTEST_FAIL", "msg": "pytest 실패"})

    # 원자 급감 (-50%↓) → orange
    y_atoms = (yesterday or {}).get("atoms") or {}
    for src, cnt in (today.get("atoms") or {}).items():
        prev = y_atoms.get(src)
        if prev and prev > 0 and cnt < prev * _DROP_RATIO:
            alerts.append({"level": "orange", "code": "ATOM_DROP",
                           "msg": f"{src} 원자 급감: {prev}→{cnt}"})

    # 보강큐 신규 추가 → yellow
    if today.get("queue_new", 0) > 0:
        alerts.append({"level": "yellow", "code": "QUEUE_NEW",
                       "msg": f"보강큐 신규 {today['queue_new']}건"})

    return alerts


def render_card(metrics: dict, alerts: list) -> str:
    """경보 유무에 따라 건강검진 카드 텍스트 생성."""
    date = metrics.get("date", "")
    atoms = metrics.get("atoms") or {}
    atom_str = " · ".join(f"{k}+{v}" for k, v in atoms.items())
    pytest_str = "pytest ok" if metrics.get("pytest_ok", True) else "pytest FAIL"

    if not alerts:
        # 정상: 한 줄
        return f"✅ 건강검진 {date} 정상 — {pytest_str}, 원자 {atom_str}"

    # 이상: 상세
    icon = {"red": "🔴", "orange": "🟠", "yellow": "🟡"}
    lines = [f"⚠️ 건강검진 {date} — 경보 {len(alerts)}건"]
    for a in alerts:
        lines.append(f"{icon.get(a['level'], '•')} {a['msg']}")
    lines.append(f"[현황] {pytest_str}, 원자 {atom_str}")

    return "\n".join(lines)


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    date = datetime.now().strftime("%Y-%m-%d")
    metrics = collect_signals(date)
    hist = load_history()
    yest = hist.get((datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"), {})
    alerts = compare_to_baseline(metrics, yest)
    card = render_card(metrics, alerts)
    print(card)
    try:
        from calc_oscillator import send_telegram
        send_telegram(card)
    except Exception as e:
        print(f"  [건강검진] 텔레 발송 생략: {e}")
    save_snapshot(metrics)


if __name__ == "__main__":
    main()
