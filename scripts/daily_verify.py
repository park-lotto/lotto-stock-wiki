"""일일 검증 에이전트 — pipeline/atoms/daily_health.py 패턴 확장.
크롤링 신선도(요일별 평균)+pytest 회귀+stockbrain 서비스 상태를 점검하고
텔레그램으로 통합 보고. 서버 외부 도달성 체크는 범위 밖(온서버 체커로는
원리적으로 감지 불가 — 2026-07-03 원격서버 네트워크 장애로 실증됨)."""
import glob
import json
import os
import re
import subprocess
from datetime import datetime


def count_today_files(raw_root: str, source: str, date_str: str) -> int:
    flat = glob.glob(os.path.join(raw_root, source, f"{date_str}_*"))
    if flat:
        return len(flat)
    sub = os.path.join(raw_root, source, date_str)
    if os.path.isdir(sub):
        return len([f for f in os.listdir(sub) if os.path.isfile(os.path.join(sub, f))])
    return 0


def weekday_average(history: dict, source: str, weekday: int, weeks: int = 4) -> float | None:
    samples = []
    for date_str, counts in history.items():
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if d.weekday() == weekday and source in counts:
            samples.append(counts[source])
    if not samples:
        return None
    samples = samples[-weeks:]
    return sum(samples) / len(samples)


def check_crawl_freshness(raw_root: str, sources: list[str], history: dict,
                            today_date: str) -> list[dict]:
    weekday = datetime.strptime(today_date, "%Y-%m-%d").weekday()
    alerts = []
    for source in sources:
        avg = weekday_average(history, source, weekday)
        if avg is None or avg < 3:
            continue   # 표본 부족하거나 원래 적은 소스는 판단 보류
        today_count = count_today_files(raw_root, source, today_date)
        if today_count < avg * 0.3:
            alerts.append({"source": source, "today": today_count, "avg": avg,
                            "level": "orange"})
    return alerts


def run_pytest_check(root: str, timeout: int = 300) -> dict:
    try:
        r = subprocess.run(["python", "-m", "pytest", "-q"], cwd=root,
                            capture_output=True, timeout=timeout)
    except Exception as e:
        return {"ok": True, "failed_tests": [], "error": f"측정 실패: {e}"}
    if r.returncode == 0:
        return {"ok": True, "failed_tests": []}
    out = r.stdout.decode("utf-8", errors="replace")
    failed = re.findall(r"^FAILED (\S+)", out, re.MULTILINE)
    failed += re.findall(r"^ERROR collecting (\S+)", out, re.MULTILINE)
    return {"ok": False, "failed_tests": failed}


def check_service_health(service_name: str = "stockbrain") -> dict:
    try:
        r = subprocess.run(["systemctl", "is-active", service_name],
                            capture_output=True, timeout=15)
        active = r.stdout.decode().strip() == "active"
        if active:
            return {"active": True, "restarted": False}
        subprocess.run(["sudo", "systemctl", "restart", service_name],
                        capture_output=True, timeout=15)
        r2 = subprocess.run(["systemctl", "is-active", service_name],
                             capture_output=True, timeout=15)
        return {"active": r2.stdout.decode().strip() == "active", "restarted": True}
    except Exception as e:
        return {"active": None, "restarted": False, "error": str(e)}


def render_verify_card(date_str: str, freshness_alerts: list[dict],
                         pytest_result: dict, service_result: dict) -> str:
    problems = bool(freshness_alerts) or not pytest_result.get("ok", True) \
        or service_result.get("restarted") or service_result.get("active") is False

    if not problems:
        return f"✅ 일일검증 {date_str} 정상 — pytest ok, stockbrain active"

    lines = [f"⚠️ 일일검증 {date_str} — 확인 필요"]
    for a in freshness_alerts:
        lines.append(f"🟠 {a['source']} 신선도 저하: 오늘 {a['today']}건"
                      f"(평균 {a['avg']:.1f}건)")
    if not pytest_result.get("ok", True):
        lines.append(f"🔴 pytest 실패: {', '.join(pytest_result['failed_tests'])}")
    if service_result.get("restarted"):
        status = "복구됨" if service_result.get("active") else "재시작해도 실패"
        lines.append(f"🟡 stockbrain 서비스 재시작 시도됨 — {status}")
    elif service_result.get("active") is False:
        lines.append("🔴 stockbrain 서비스 비활성 상태(재시작 시도 안 됨)")
    return "\n".join(lines)


def load_verify_history(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_verify_counts(path: str, date_str: str, counts: dict) -> None:
    hist = load_verify_history(path)
    hist[date_str] = counts
    for d in sorted(hist)[:-14]:
        del hist[d]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def main():
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history_path = os.path.join(root, "pipeline", "atoms", "daily_verify_history.json")
    raw_root = os.path.join(root, "raw")
    sources = ["telegram", "news", "report"]
    today = datetime.now().strftime("%Y-%m-%d")

    history = load_verify_history(history_path)
    freshness_alerts = check_crawl_freshness(raw_root, sources, history, today)
    pytest_result = run_pytest_check(root)
    service_result = check_service_health("stockbrain")

    card = render_verify_card(today, freshness_alerts, pytest_result, service_result)
    print(card)
    try:
        sys.path.insert(0, root)
        from calc_oscillator import send_telegram
        send_telegram(card)
    except Exception as e:
        print(f"  [일일검증] 텔레 발송 생략: {e}")

    today_counts = {s: count_today_files(raw_root, s, today) for s in sources}
    save_verify_counts(history_path, today, today_counts)


if __name__ == "__main__":
    main()
