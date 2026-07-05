"""장중 시황 브리핑 — 세션 페이즈 판정. 시각(+요일)으로 프레이밍을 결정한다."""
import datetime as _dt


def session_phase(now: _dt.datetime) -> str:
    """반환: premarket|intraday|closed|weekend. 한국 장 기준(평일 09:00~15:30).
    premarket 08:00~08:50, intraday 08:50~15:30, 그 외 평일은 closed, 주말은 weekend."""
    if now.weekday() >= 5:          # 5=토, 6=일
        return "weekend"
    hm = now.hour * 60 + now.minute
    if 8 * 60 <= hm < 8 * 60 + 50:
        return "premarket"
    if 8 * 60 + 50 <= hm < 15 * 60 + 30:
        return "intraday"
    return "closed"
