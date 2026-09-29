"""트랙 창 → 텔레그램 보고 (카드 046).  py tools/tg_notify.py "<결과>"

보내기(sendMessage)만 한다 — 받기(getUpdates)는 관제창 하나만 해야 하므로(409) 절대 부르지 않는다.
토큰은 이 PC 의 ~/.claude/channels/telegram/.env, 받는 사람은 access.json allowFrom[0].
토큰을 출력·로그에 남기지 않는다.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate
import pc_label

STATE = Path.home() / ".claude" / "channels" / "telegram"


def _token(state_dir):
    try:
        for line in (state_dir / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(url, body, timeout=15) as r:
        return r.status == 200


def main(argv=None, state_dir=STATE, pc=None, cwd_name=None):
    merge_gate.make_output_safe()
    text = " ".join(argv if argv is not None else sys.argv[1:]).strip()
    token = _token(state_dir)
    try:
        chat = str(json.loads((state_dir / "access.json").read_text(encoding="utf-8"))["allowFrom"][0])
    except (OSError, ValueError, KeyError, IndexError):
        chat = ""
    if not (token and chat and text):
        print("보고 실패: 토큰·받는 사람·내용 중 하나가 없다 (이 화면에 결과를 남겨라)")
        return 1
    head = f"[{pc or pc_label.label()}·{cwd_name or Path.cwd().name}] "
    try:
        ok = _post(f"https://api.telegram.org/bot{token}/sendMessage",
                   {"chat_id": chat, "text": head + text})
    except OSError as e:          # 예외 문자열엔 URL(토큰)이 섞일 수 있어 이름만 남긴다
        print(f"보고 실패: {type(e).__name__}")
        return 1
    print("보고 완료" if ok else "보고 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
