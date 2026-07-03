"""일일 검증 에이전트 — pipeline/atoms/daily_health.py 패턴 확장.
크롤링 신선도(요일별 평균)+pytest 회귀+stockbrain 서비스 상태를 점검하고
텔레그램으로 통합 보고. 서버 외부 도달성 체크는 범위 밖(온서버 체커로는
원리적으로 감지 불가 — 2026-07-03 원격서버 네트워크 장애로 실증됨)."""
import glob
import os
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
