"""텔레그램 알림 — 러너(auto_run)가 unsure/실패 시 사장님을 부른다(스펙 트랙4).

★부가 채널이라 러너를 절대 죽이지 않는다: 키 없으면 no-op, 네트워크 예외는 삼킨다(tts.py 무키 폴백 관례).
봇 토큰/챗ID는 env(SHORTS_TELEGRAM_TOKEN/SHORTS_TELEGRAM_CHAT_ID). 프로젝트에 기존 텔레 인프라가
없어 여기서 새로 배선한다.
"""
import os


def send_telegram(text, *, token=None, chat_id=None, _requests=None):
    token = token or os.environ.get("SHORTS_TELEGRAM_TOKEN")
    chat_id = chat_id or os.environ.get("SHORTS_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False                     # 무키 폴백 — 조용히 넘어간다
    if _requests is None:
        import requests as _requests      # 실행시에만 임포트(테스트는 주입)
    try:
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        return getattr(r, "status_code", 0) == 200
    except Exception:
        return False                     # 알림 실패가 러너를 죽이면 안 된다
