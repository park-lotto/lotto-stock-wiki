# -*- coding: utf-8 -*-
"""숏클 회원 Claude 에게 메시지 보내기(관제 304) — 대기실 창이 답장할 때 쓴다.

    py tools/shortcl_send.py <cid> "메시지"            # 회원 프로그램이 1분 안에 받아 다음 도구 응답·다음 회원 말에 싣는다
    py tools/shortcl_send.py <cid> "메시지" --sid <sid>

서버 판단은 claude_live.send 한 곳(1~1000자·라이선스 있는 회원만). 실패하면 이유를 내고 종료 코드 1.
"""
from __future__ import annotations

import sys

from shortcl_watch import _setup


def main(argv):
    args, sid = list(argv), ""
    if "--sid" in args:
        i = args.index("--sid")
        sid = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s, mint, base = _setup()
    r = s.post(f"{base}/api/admin/claude/live/send", json={"cid": args[0], "text": args[1], "sid": sid},
               headers={"Cookie": f"dash_auth={mint()}", "Accept": "application/json"}, timeout=20, allow_redirects=False)
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code != 200 or not d.get("ok"):
        print(f"못 보냈습니다: HTTP {r.status_code} {d.get('msg') or d.get('error') or ''}")
        return 1
    print(f"보냈습니다 — 메시지 #{d['id']} · 회원 {args[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
