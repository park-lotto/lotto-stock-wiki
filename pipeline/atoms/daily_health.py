"""파이프라인 매일 건강검진 (MVP) — 기존 신호만 모아 정상=1줄/이상=상세 텔레카드."""

_DROP_RATIO = 0.5  # 어제 대비 -50%↓ 경보


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
