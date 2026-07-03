"""대기 브리핑 수동 발행 — 이상징후로 에스컬레이션된 브리핑을 사장님 확인 후 채널로 발행."""
from scripts.goal_loop import pending, morning_brief as mb


def publish_pending() -> dict:
    """대기 중인 브리핑이 있으면 채널로 발행하고 대기 해제. 없으면 ok=False."""
    p = pending.read()
    if not p:
        return {"ok": False, "error": "대기 없음"}
    caption = f"📊 {p['date']} 아침 브리핑"
    sent = mb.viz_card.send_telegram_photo(p["png"], caption)
    if sent:
        pending.clear()
    return {"ok": True, "sent": bool(sent)}
