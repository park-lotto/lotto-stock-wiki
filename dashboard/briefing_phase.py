"""장중 시황 브리핑 — 세션 페이즈 판정. 시각(+요일)으로 프레이밍을 결정한다."""
import datetime as _dt


def session_phase(now: _dt.datetime) -> str:
    """반환: premarket|premarket_nxt|intraday|afterhours|afterhours_night|closed|weekend.
    한국 장 기준(09:00~15:30). premarket 07:30~08:00(미국장 마감~국내장 개장 전),
    premarket_nxt 08:00~09:00(NXT 프리마켓), intraday 09:00~15:30,
    afterhours 15:30~18:00(마감 후 저녁 브리핑), afterhours_night 18:00~20:00
    (코스피 야간선물+나스닥 프리장), 그 외 평일은 closed, 주말은 weekend.
    08:00·18:00도 실제 phase 경계로 둬서 phase_changed가 그 즉시 재합성을 강제한다
    (그렇지 않으면 다음 30분 heartbeat까지 최대 30분 지연될 수 있음)."""
    if now.weekday() >= 5:          # 5=토, 6=일
        return "weekend"
    hm = now.hour * 60 + now.minute
    if 7 * 60 + 30 <= hm < 8 * 60:
        return "premarket"
    if 8 * 60 <= hm < 9 * 60:
        return "premarket_nxt"
    if 9 * 60 <= hm < 15 * 60 + 30:
        return "intraday"
    if 15 * 60 + 30 <= hm < 18 * 60:
        return "afterhours"
    if 18 * 60 <= hm < 20 * 60:
        return "afterhours_night"
    return "closed"


def phase_focus(phase: str) -> str:
    """phase별로 브리핑이 다뤄야 할 초점을 지시문으로 반환."""
    if phase == "premarket":
        return ("미국장(나스닥·다우) 마감 결과를 반영하고, 오늘 국내 시장이 어떻게 흘러갈지"
                " 예상 시나리오와 시장 분위기를 서술하라.")
    if phase == "premarket_nxt":
        return ("미국장 마감 결과를 반영한 오늘 국내 시장 예상 시나리오·분위기에 더해, 지금은"
                " NXT(넥스트트레이딩) 시간대다 — rank_popular/rank_amt 상위 종목 중 NXT 상승"
                " 종목을 강한 섹터로 분류하고, 왜 그 섹터가 강한지 뉴스·원자(news) 근거로"
                " 분명한 이유를 제시하라.")
    if phase == "afterhours":
        return "정규장 마감 후 하루 흐름을 정리하는 평소와 같은 시황 브리핑을 이어가라."
    if phase == "afterhours_night":
        return ("지금은 18시 이후다 — 코스피 야간선물(코스피야간선물) 동향과 나스닥 프리마켓"
                "(프리장) 움직임으로 초점을 전환하고, 나스닥 주요 종목·이슈를 중심으로 서술하라.")
    return ""
