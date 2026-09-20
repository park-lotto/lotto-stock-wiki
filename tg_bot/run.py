"""작업봇을 돌린다.

사장님 PC에서 실행한다 — 서버 상주가 아니라서 **구독으로 동작(API 비용 0원)**.
시작: 봇켜기.bat 더블클릭 / 멈춤: 창에서 Ctrl+C
"""
import os
import sys
import traceback

from tg_bot.ask import AskError, ask
from tg_bot.context import extract
from tg_bot.poller import Telegram
from tg_bot.probe import ProbeError, Prober
from tg_bot.reply import build, table_loaded

BASE = os.environ.get("SHORTS_BASE", "https://shoppingshorts.duckdns.org")

# 작업 폴더 — 여기서 클로드가 파일을 읽고 고친다. 기본은 이 프로젝트.
WORK_DIR = os.environ.get("BOT_WORK_DIR") or os.getcwd()

_NEW = ("🆕 새 대화를 시작합니다. 앞의 맥락은 잊습니다.")
_INTRO = ("🤖 작업봇을 켰습니다.\n\n"
          "• 고객 주소를 붙여넣으면 → 그 작업을 조사합니다\n"
          "• 그냥 물어보시면 → 대화합니다 (터미널과 같습니다)\n"
          "• /새로 → 대화를 처음부터")


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


class Session:
    """대화 하나를 기억한다. session_id 가 있으면 클로드가 맥락을 이어간다."""

    def __init__(self):
        self.claude_id = None

    def reset(self):
        self.claude_id = None


def handle(text, prober, session=None, *, _ask=None):
    """메시지 하나 → 사장님께 보낼 답변 문자열.

    ★갈림길은 하나뿐이다(0순위-B): 작업 주소가 있으면 **조사**, 없으면 **대화**.
    """
    session = session if session is not None else Session()
    body = (text or "").strip()

    if body in ("/새로", "/new", "/reset"):
        session.reset()
        return _NEW

    info = extract(body)

    # ① 작업 주소가 있으면 — 정확한 조회가 대화보다 낫다(추측이 안 섞인다).
    if info["job_id"]:
        try:
            job = prober.job(info["job_id"])
        except ProbeError as e:
            return f"조사하지 못했습니다.\n{e}"
        return build(info["job_id"], job, question=info["text"])

    # ② 그 외에는 클로드와 대화한다 — 터미널에서 하던 그대로.
    if not body:
        return "무엇을 도와드릴까요?"
    caller = _ask or ask
    try:
        answer, sid = caller(body, session_id=session.claude_id, cwd=WORK_DIR)
    except AskError as e:
        return f"{e}"
    if sid:
        session.claude_id = sid
    return answer or "(답이 비어 있습니다)"


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
    session = Session()
    tg.send(_INTRO)
    print(f"작업봇 실행 중 ({BASE}, 작업폴더 {WORK_DIR}). 멈추려면 Ctrl+C.")

    try:
        while True:
            for text in tg.poll():
                try:
                    # 대화는 몇 분 걸릴 수 있다 — 잠잠하면 사장님이 죽은 줄 안다.
                    if not extract(text)["job_id"] and not text.startswith("/"):
                        tg.send("⏳ 생각 중입니다…")
                    tg.send(handle(text, prober, session))
                except Exception:   # noqa: BLE001 — 한 건 실패가 봇을 죽이면 안 된다
                    traceback.print_exc()
                    tg.send("처리 중 오류가 났습니다. 창의 기록을 확인해 주세요.")
    except KeyboardInterrupt:
        tg.send("🤖 작업봇을 껐습니다.")
        print("종료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
