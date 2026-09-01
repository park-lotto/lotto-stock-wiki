"""작업봇을 돌린다.

사장님 PC에서 실행한다 — 서버 상주가 아니라서 **구독으로 동작(API 비용 0원)**.
시작: 봇켜기.bat 더블클릭 / 멈춤: 창에서 Ctrl+C
"""
import os
import sys
import traceback

from tg_bot.context import extract
from tg_bot.poller import Telegram
from tg_bot.probe import ProbeError, Prober
from tg_bot.reply import build, table_loaded

BASE = os.environ.get("SHORTS_BASE", "https://shoppingshorts.duckdns.org")

_HELP = ("주소에서 작업 번호를 찾지 못했습니다.\n"
         "고객이 보낸 주소를 그대로 붙여넣어 주세요 "
         "(…/produce?job_id=… 형태).")


def load_env(path=".env"):
    """.env 를 읽어 환경변수로 올린다(python-dotenv 없이도 되게).

    ★이미 설정된 값은 덮지 않는다 — 셸에서 준 값이 우선이다.
    """
    for name in (path, os.path.join("..", path)):
        if not os.path.exists(name):
            continue
        with open(name, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        return name
    return None


def handle(text, prober):
    """메시지 하나 → 사장님께 보낼 답변 문자열."""
    info = extract(text)
    if not info["job_id"]:
        return _HELP
    try:
        job = prober.job(info["job_id"])
    except ProbeError as e:
        return f"조사하지 못했습니다.\n{e}"
    return build(info["job_id"], job, question=info["text"])


def main():
    load_env()
    tg = Telegram()
    if not tg.ok():
        # ★무엇이 없는지 이름으로 말한다 — "설정 오류"로 뭉개면 못 고친다.
        print("중단: .env 에 " + " / ".join(tg.missing()) + " 가 없다.",
              file=sys.stderr)
        return 1

    user = os.environ.get("DASH_USER", "")
    password = os.environ.get("DASH_PASS", "")
    if not user or not password:
        miss = [n for n, v in (("DASH_USER", user), ("DASH_PASS", password)) if not v]
        print("중단: .env 에 " + " / ".join(miss) + " 가 없다(서버 조회에 필요).",
              file=sys.stderr)
        return 1

    if not table_loaded():
        # 죽이지는 않는다. 다만 조용히 나빠지지 않게 알린다.
        print("경고: app.py 의 고객문구 변환표를 못 읽었다 — 일반 문구로만 답한다.",
              file=sys.stderr)

    prober = Prober(BASE, user, password)
    tg.send("🤖 작업봇을 켰습니다. 고객 질문을 넘겨주세요.")
    print(f"작업봇 실행 중 ({BASE}). 멈추려면 Ctrl+C.")

    try:
        while True:
            for text in tg.poll():
                try:
                    tg.send(handle(text, prober))
                except Exception:   # noqa: BLE001 — 한 건 실패가 봇을 죽이면 안 된다
                    traceback.print_exc()
                    tg.send("처리 중 오류가 났습니다. 창의 기록을 확인해 주세요.")
    except KeyboardInterrupt:
        tg.send("🤖 작업봇을 껐습니다.")
        print("종료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
