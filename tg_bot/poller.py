"""텔레그램 수신·발송.

★조사 로직을 모른다 — 메시지를 나르기만 한다(폰 스크립트가 '배달만 한다'는 관례와 같다).
★사장님 chat_id 외에는 무시한다 — 봇 이름을 알아낸 남이 말을 걸 수 있다.
★발송 방식은 notify.send_telegram 과 같다(sendMessage 직접 호출, 라이브러리 없음).
"""
import os

_API = "https://api.telegram.org/bot{token}/{method}"


class Telegram:
    def __init__(self, token=None, chat_id=None, *, requests_mod=None):
        self.token = token or os.environ.get("SHORTS_TELEGRAM_TOKEN", "")
        self.chat_id = str(chat_id or os.environ.get("SHORTS_TELEGRAM_CHAT_ID", ""))
        if requests_mod is None:
            import requests as requests_mod
        self.r = requests_mod
        self._offset = None

    def ok(self):
        return bool(self.token and self.chat_id)

    def missing(self):
        """무엇이 없는지 이름으로 알려준다 — '설정 오류'로 뭉개지 않는다."""
        out = []
        if not self.token:
            out.append("SHORTS_TELEGRAM_TOKEN")
        if not self.chat_id:
            out.append("SHORTS_TELEGRAM_CHAT_ID")
        return out

    def send(self, text):
        if not self.ok():
            return False
        try:
            resp = self.r.post(
                _API.format(token=self.token, method="sendMessage"),
                json={"chat_id": self.chat_id, "text": text},
                timeout=20,
            )
            return getattr(resp, "status_code", 0) == 200
        except Exception:       # noqa: BLE001 — 알림 실패가 봇을 죽이면 안 된다(notify.py 관례)
            return False

    def poll(self, wait=25):
        """새 메시지 목록. ★사장님 것만 돌려준다."""
        if not self.ok():
            return []
        params = {"timeout": wait}
        if self._offset is not None:
            params["offset"] = self._offset
        try:
            resp = self.r.get(
                _API.format(token=self.token, method="getUpdates"),
                params=params, timeout=wait + 10,
            )
            data = resp.json()
        except Exception:       # noqa: BLE001 — 네트워크가 끊겨도 다음 바퀴에 다시 시도한다
            return []
        out = []
        for up in data.get("result", []):
            self._offset = up.get("update_id", 0) + 1
            msg = up.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != self.chat_id:
                continue            # ★남이 건 말은 무시한다
            text = msg.get("text")
            if text:
                out.append(text)
        return out
