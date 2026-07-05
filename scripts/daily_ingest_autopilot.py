"""크롤링 인제스트 자동점검·자동수정 오케스트레이터.
서버(/home/ubuntu/lotto-stock-wiki)에서 실행 — 원격 crontab:
  50 8,12,15,18,21 * * *  daily_ingest_autopilot.py --slot
  45 21 * * *              daily_ingest_autopilot.py --daily-summary
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.atoms.telegram_registry import resolve_channel_key, is_excluded, _CHANNELS
from daily_verify import run_pytest_check, check_service_health
from calc_oscillator import send_telegram

import autopilot_freshness as freshness
import autopilot_state as state_mod
import autopilot_diagnose as diagnose_mod
import autopilot_fix as fix_mod
import autopilot_deploy as deploy_mod
import autopilot_report as report_mod

RAW_TELEGRAM_DIR = str(ROOT / "raw" / "telegram")
STATE_PATH = str(ROOT / "pipeline" / "atoms" / "autopilot_state.json")
CRAWLER_ROOT = "/home/ubuntu/kmong/crawling_bot"
CRAWLER_LOG = f"{CRAWLER_ROOT}/logs/service.log"
BACKUP_ROOT = str(ROOT / "scratchpad" / "autopilot_backups")
FILE_CAP = 3


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _excluded_channels():
    return {k for k in _CHANNELS if is_excluded(k)}


def process_channel(channel, anomaly, state, slot_label, today_str):
    """이상 채널 하나를 진단→(필요시)수정→배포까지 처리. 슬럿 알림 텍스트 리스트 반환."""
    alerts = []
    if not state_mod.should_diagnose(state, channel, today_str):
        state_mod.touch_anomaly(state, channel, today_str)
        return alerts  # 오늘 이미 진단함 — 재시도 안 함, 알림도 없음(일일요약에서만 리마인드)

    state_mod.touch_anomaly(state, channel, today_str)
    log_tail = diagnose_mod.read_log_tail(CRAWLER_LOG)
    diagnosis = diagnose_mod.diagnose(channel, anomaly, log_tail, cwd=str(ROOT))

    if diagnosis is None:
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated",
            root_cause="진단 호출 실패(타임아웃/토큰 문제)"))
        return alerts

    if diagnosis["target"] == "unfixable" or diagnosis["requires_destructive_action"]:
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated", root_cause=diagnosis["root_cause"]))
        return alerts

    fix_cwd = str(ROOT) if diagnosis["target"] == "local" else CRAWLER_ROOT
    backups = {}
    if diagnosis["target"] == "remote_crawler":
        backups = deploy_mod.backup_remote_files(
            CRAWLER_ROOT, diagnosis["target_files"], BACKUP_ROOT)

    fix_result = fix_mod.apply_fix(channel, diagnosis, cwd=fix_cwd)

    if fix_result is None or not fix_result.get("done"):
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated", root_cause=diagnosis["root_cause"],
            summary="수정 시도 실패"))
        return alerts

    if diagnosis["target"] == "local":
        changed = fix_mod.changed_files(str(ROOT))
    else:
        changed = diagnosis["target_files"]

    if not fix_mod.within_file_cap(changed, cap=FILE_CAP):
        if diagnosis["target"] == "remote_crawler":
            deploy_mod.rollback_remote_crawler(CRAWLER_ROOT, backups)
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated", root_cause=diagnosis["root_cause"],
            summary=f"수정 범위 {len(changed)}개 파일 — 캡({FILE_CAP}) 초과로 자동커밋 취소"))
        return alerts

    pytest_result = run_pytest_check(str(ROOT))
    if not pytest_result["ok"]:
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated", root_cause=diagnosis["root_cause"],
            summary="수정 후 pytest 실패 — 커밋 안 함"))
        return alerts

    if diagnosis["target"] == "local":
        commit_hash = deploy_mod.deploy_local(
            str(ROOT), f"[autopilot-auto-fix] {channel}: {fix_result['summary']}", changed)
        deployed = commit_hash is not None
        service_name = "stockbrain"
    else:
        commit_hash = None
        deployed = deploy_mod.deploy_remote_crawler(CRAWLER_ROOT)
        service_name = "crawlingbot"

    healthy = deploy_mod.health_check(service_name) if deployed else False

    if not deployed or not healthy:
        if diagnosis["target"] == "local" and commit_hash:
            deploy_mod.rollback_local(str(ROOT), commit_hash, changed)
        elif diagnosis["target"] == "remote_crawler":
            deploy_mod.rollback_remote_crawler(CRAWLER_ROOT, backups)
        state_mod.mark_diagnosed(state, channel, today_str, "escalated")
        alerts.append(report_mod.render_slot_alert(
            slot_label, channel, "escalated", root_cause=diagnosis["root_cause"],
            summary="배포 후 헬스체크 실패 — 자동 롤백함"))
        return alerts

    deploy_mod.append_wiki_log(
        str(ROOT),
        f"- {today_str} — [autopilot] {channel} 자동수정: {fix_result['summary']} "
        f"(원인: {diagnosis['root_cause']})")
    state_mod.mark_diagnosed(state, channel, today_str, "auto_fixed")
    alerts.append(report_mod.render_slot_alert(
        slot_label, channel, "auto_fixed", root_cause=diagnosis["root_cause"],
        summary=fix_result["summary"]))
    return alerts


def run_slot(slot_label=None):
    today_str = _today()
    slot_label = slot_label or datetime.now().strftime("%H:%M")
    state = state_mod.load_state(STATE_PATH)
    excluded = _excluded_channels()
    results = freshness.check_all_channels(
        RAW_TELEGRAM_DIR, _CHANNELS, resolve_channel_key, today_str, excluded=excluded)

    anomalies = freshness.anomalies_only(results)
    anomaly_channels = {r["channel"] for r in anomalies}

    alerts = []
    for r in anomalies:
        alerts.extend(process_channel(r["channel"], r, state, slot_label, today_str))

    for channel in list(state.keys()):
        if channel == "_daily_stats" or channel in anomaly_channels:
            continue
        healed = state_mod.resolve_if_healed(state, channel, today_str)
        if healed:
            alerts.append(report_mod.render_healed_alert(
                slot_label, channel, healed["days_open"]))

    state_mod.save_state(STATE_PATH, state)
    for text in alerts:
        send_telegram(text)
    return alerts


def run_daily_summary():
    today_str = _today()
    state = state_mod.load_state(STATE_PATH)
    pytest_result = run_pytest_check(str(ROOT))
    service_results = {
        "stockbrain": check_service_health("stockbrain"),
        "crawlingbot": check_service_health("crawlingbot"),
    }
    open_esc = {
        channel: {"first_detected": entry["first_detected"],
                  "days_open": state_mod.days_open(entry, today_str)}
        for channel, entry in state_mod.open_escalations(state).items()
    }
    stats = state_mod.get_daily_stats(state, today_str)
    slot_stats = {"checked": 5, "detected": stats["detected"],
                  "auto_fixed": stats["auto_fixed"], "escalated": stats["escalated"]}
    card = report_mod.render_daily_summary(
        today_str, slot_stats, pytest_result, service_results, open_esc)
    send_telegram(card)
    return card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", action="store_true")
    parser.add_argument("--daily-summary", action="store_true")
    args = parser.parse_args()
    if args.slot:
        run_slot()
    elif args.daily_summary:
        run_daily_summary()
    else:
        parser.error("--slot 또는 --daily-summary 중 하나 필요")


if __name__ == "__main__":
    main()
