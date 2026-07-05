"""텔레그램 리포트 조립 — 슬럿 알림(이상 있을 때만) + 21:45 일일요약(미해결 항목 강제 포함)."""


def render_slot_alert(slot_label, channel, outcome, root_cause=None, summary=None):
    """outcome: 'auto_fixed' | 'escalated'. 신규 감지/상태변화 시에만 호출된다(오케스트레이터가 판단)."""
    if outcome == "auto_fixed":
        lines = [f"🟢 [{slot_label}] {channel} — 자동수정 완료"]
        if root_cause:
            lines.append(f"→ 원인: {root_cause}")
        if summary:
            lines.append(f"→ {summary}")
        return "\n".join(lines)
    lines = [f"🔴 [{slot_label}] {channel} — 사람 판단 필요"]
    if root_cause:
        lines.append(f"→ 진단: {root_cause}")
    lines.append("→ 코드로 해결 불가 또는 실패 → 자동 skip(당일 재시도 안 함)")
    return "\n".join(lines)


def render_healed_alert(slot_label, channel, days_open):
    return f"✅ [{slot_label}] {channel} — 해결됨({days_open}일만에)"


def render_daily_summary(date_str, slot_stats, pytest_result, service_results, open_escalations):
    """slot_stats: {"checked", "detected", "auto_fixed", "escalated"}.
    service_results: {서비스명: {"active": bool}}.
    open_escalations: {채널명: {"first_detected", "days_open"}}."""
    lines = [f"📋 일일 인제스트 요약 {date_str}"]
    lines.append(
        f"슬럿 {slot_stats['checked']}회 체크 / {slot_stats['detected']}건 발견 / "
        f"{slot_stats['auto_fixed']}건 자동수정 / {slot_stats['escalated']}건 에스컬레이션"
    )
    if pytest_result.get("ok", True):
        lines.append("✅ pytest 정상")
    else:
        lines.append(f"🔴 pytest 실패: {', '.join(pytest_result['failed_tests'])}")
    for name, result in service_results.items():
        badge = "✅" if result.get("active") else "🔴"
        lines.append(f"{badge} {name} 서비스: {'정상' if result.get('active') else '비정상'}")
    if open_escalations:
        lines.append("⚠️ 미해결 에스컬레이션:")
        for channel, info in open_escalations.items():
            lines.append(f"  - {channel} — {info['days_open']}일째 미해결(최초 {info['first_detected']})")
    else:
        lines.append("미해결 에스컬레이션 없음")
    return "\n".join(lines)
