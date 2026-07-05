"""텔레그램 채널별 raw 최신성 판정.
atoms.db의 created_at은 인제스트 처리 시각이라 옛 파일을 오늘 재처리해도 오늘 날짜로
찍혀 착시를 일으킨다(2026-07-05 실전 발견: 실시간주식뉴스 채널이 07-03 raw를 오늘
재처리해서 마치 신선한 것처럼 보였음) — 그래서 raw 파일명에 박힌 날짜만 신뢰한다."""
import glob
import os
import re
from datetime import datetime

FNAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$")
DEFAULT_FRESHNESS_DAYS = 2


def latest_dates_by_channel(raw_telegram_dir, resolve_channel_key_fn):
    """raw/telegram/*.md 파일명에서 채널별 최신 날짜 추출.
    resolve_channel_key_fn: telegram_registry.resolve_channel_key 같은
    (표시명 -> 등록키|None) 함수. 반환: {등록키: "YYYY-MM-DD"}(채널별 최신 날짜 하나씩)."""
    latest = {}
    for path in glob.glob(os.path.join(raw_telegram_dir, "*.md")):
        m = FNAME_RE.match(os.path.basename(path))
        if not m:
            continue
        date_str, display_name = m.group(1), m.group(2)
        key = resolve_channel_key_fn(display_name)
        if key is None:
            continue
        if key not in latest or date_str > latest[key]:
            latest[key] = date_str
    return latest


def classify_channel(channel, latest_date, today_str, freshness_days=DEFAULT_FRESHNESS_DAYS):
    """단일 채널 판정. status: never_synced|stale|ok.
    gap이 freshness_days 이상이면(경계값 포함) stale — 기본 임계치는 2일이므로
    2일치 공백이 나면 그 시점에 바로 알람이 떠야 하고, 3일째까지 미뤄지면 안 된다."""
    if latest_date is None:
        return {"channel": channel, "status": "never_synced", "days_stale": None,
                "latest_date": None}
    today = datetime.strptime(today_str, "%Y-%m-%d")
    last = datetime.strptime(latest_date, "%Y-%m-%d")
    gap = (today - last).days
    status = "stale" if gap >= freshness_days else "ok"
    return {"channel": channel, "status": status, "days_stale": gap, "latest_date": latest_date}


def check_all_channels(raw_telegram_dir, channels_config, resolve_channel_key_fn,
                        today_str, excluded=frozenset()):
    """channels_config: telegram_channels.json 로드 결과(dict). excluded는
    텔레그램 레지스트리의 _EXCLUDED처럼 신선도 체크 자체에서 빼야 하는 채널 키 집합."""
    latest = latest_dates_by_channel(raw_telegram_dir, resolve_channel_key_fn)
    results = []
    for key, cfg in channels_config.items():
        if key in excluded:
            continue
        freshness_days = cfg.get("freshness_days", DEFAULT_FRESHNESS_DAYS)
        results.append(classify_channel(key, latest.get(key), today_str, freshness_days))
    return results


def anomalies_only(results):
    return [r for r in results if r["status"] != "ok"]
