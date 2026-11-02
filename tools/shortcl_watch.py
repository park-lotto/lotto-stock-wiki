# -*- coding: utf-8 -*-
"""숏클 대기실 감시(관제 304) — 사장님 PC 대기실 Claude 창이 Monitor 도구로 띄운다. 새 긴급 사건을 **한 줄씩** stdout 으로 낸다.

    py tools/shortcl_watch.py          # 이어서 돈다(Ctrl+C = 일부러 끔 — 서버가 '끊김' 알림을 안 보낸다)

한 줄 꼴: [11-02 14:03:21] #123 stuck 홍길동(12) 제품 확인 sid=abcd…: 글
그 밖의 줄: [대기실] … (시작·끊김·복구)
- 15초마다 새 사건, 60초마다 생존 신호(ping). 무엇이 긴급인지는 서버 claude_live.is_urgent 한 곳(urgent=1).
- 인증 = tools/live_admin.admin_cookie(2시간짜리 관리자 쿠키). 403·401·리다이렉트면 새로 받는다.
- 어디까지 읽었는지 ~/.shortcl_watch_last 에 남긴다 — 창을 껐다 켜도 그동안의 사건을 놓치지 않는다. 처음이면 옛 사건은 쏟지 않는다.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLL_SEC = 15
PING_SEC = 60
TEXT_MAX = 400
BACKOFF_MAX = 60
STATE_FILE = Path.home() / ".shortcl_watch_last"


def line(e: dict) -> str:
    """사건 → 한 줄(Monitor 는 줄마다 알림 하나)."""
    t = time.strftime("%m-%d %H:%M:%S", time.localtime(e.get("ts") or 0))
    who = f"{e.get('member') or '회원'}({e.get('cid')})"
    stage = " ".join(str(e.get("stage") or "").split())
    sid = f" sid={e['sid']}" if e.get("sid") else ""
    text = " ".join(str(e.get("text") or "").split())[:TEXT_MAX]
    return f"[{t}] #{e.get('id')} {e.get('kind')} {who}" + (f" {stage}" if stage else "") + f"{sid}: {text}"


class Watcher:
    def __init__(self, session, mint, emit, state_file=STATE_FILE, base=None):
        self.s, self.mint, self.emit, self.state_file = session, mint, emit, Path(state_file)
        self.base = (base or "").rstrip("/")
        self.cookie = None
        self.down = False
        self.last = None
        try:
            self.last = int(self.state_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pass

    def _head(self):
        if not self.cookie:
            self.cookie = self.mint()
        return {"Cookie": f"dash_auth={self.cookie}", "Accept": "application/json"}

    def _broke(self, why):
        if not self.down:
            self.down = True
            self.emit(f"[대기실] 서버 연결이 끊겼습니다 — 다시 시도 중({why})")

    def _ok(self):
        if self.down:
            self.down = False
            self.emit("[대기실] 서버 연결이 돌아왔습니다")

    def tick(self) -> bool:
        """한 번 살핀다. 성공하면 True. 끊겨도 죽지 않는다(다음 tick 이 다시)."""
        try:
            r = self.s.get(f"{self.base}/api/admin/claude/live/events", params={"urgent": 1, "since_id": self.last or 0, "limit": 200},
                           headers=self._head(), timeout=20, allow_redirects=False)
        except Exception as e:      # noqa: BLE001 — 네트워크·쿠키 발급 실패 모두 다음 번에
            self._broke(type(e).__name__)
            return False
        if r.status_code in (301, 302, 303, 307, 401, 403):       # 쿠키 만료
            self.cookie = None
            try:
                self.cookie = self.mint()
            except Exception as e:  # noqa: BLE001
                self._broke(type(e).__name__)
            return False
        if r.status_code != 200:
            self._broke(f"HTTP {r.status_code}")
            return False
        d = r.json()
        self._ok()
        if self.last is None:                                      # 첫 시작 — 옛 사건은 쏟지 않는다
            self._save(d.get("last_id") or 0)
            return True
        for e in d.get("events") or []:
            self.emit(line(e))
        self._save(d.get("last_id") or self.last)
        return True

    def _save(self, v):
        self.last = int(v)
        try:
            self.state_file.write_text(str(self.last), encoding="utf-8")
        except OSError as e:
            self.emit(f"[대기실] 읽은 자리를 저장하지 못했습니다: {e}")

    def ping(self, stop=False):
        try:
            self.s.post(f"{self.base}/api/admin/claude/live/ping", json={"stop": bool(stop)}, headers=self._head(), timeout=20, allow_redirects=False)
        except Exception as e:      # noqa: BLE001 — 생존 신호 실패는 tick 이 끊김으로 알린다
            self._broke(type(e).__name__)


def _setup():
    import requests
    from tools.live_admin import BASE, admin_cookie
    ck = os.environ.get("SHORTCL_COOKIE")
    return requests.Session(), (lambda: ck) if ck else admin_cookie, os.environ.get("SHORTCL_BASE") or BASE


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    s, mint, base = _setup()

    def emit(x):
        print(x, flush=True)

    w = Watcher(s, mint, emit, base=base)
    emit(f"[대기실] 감시 시작 — {base} · 읽은 자리 {w.last if w.last is not None else '처음'}")
    next_ping, fails = 0.0, 0
    try:
        while True:
            now = time.time()
            if now >= next_ping:
                w.ping()
                next_ping = now + PING_SEC
            fails = 0 if w.tick() else fails + 1
            time.sleep(min(BACKOFF_MAX, POLL_SEC * (2 ** min(fails, 2))))
    except KeyboardInterrupt:
        w.ping(stop=True)
        emit("[대기실] 감시를 끕니다")


if __name__ == "__main__":
    main()
