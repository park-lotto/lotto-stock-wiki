"""봇 토큰·chat_id 를 확인하고 .env 에 넣어주는 도우미.

사장님이 긴 명령을 붙여넣지 않게 한다 — 지키기 쉬워야 지켜진다.
실행: 봇설정.bat 더블클릭  (또는 py -m tg_bot.setup_helper)
"""
import os
import sys

_ENV = ".env"


def fetch_chat_ids(token, *, requests_mod=None):
    """봇에게 말을 건 사람들의 chat_id 목록. 실패하면 (None, 사유)."""
    if requests_mod is None:
        import requests as requests_mod
    try:
        r = requests_mod.get(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
        data = r.json()
    except Exception as e:      # noqa: BLE001
        return None, f"텔레그램에 연결하지 못했습니다: {e}"
    if not data.get("ok", True):
        return None, f"토큰이 거부됐습니다: {data.get('description', '사유 불명')}"
    ids = []
    for up in data.get("result", []):
        cid = ((up.get("message") or {}).get("chat") or {}).get("id")
        if cid is not None and str(cid) not in ids:
            ids.append(str(cid))
    return ids, None


def upsert_env(pairs, path=_ENV):
    """.env 에 key=value 를 넣거나 갱신한다. 나머지 줄은 건드리지 않는다."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    for key, value in pairs.items():
        for i, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == key:
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    print("=" * 52)
    print(" 작업봇 설정 — 텔레그램 봇 토큰과 chat_id 를 넣습니다")
    print("=" * 52)
    print()
    print("먼저 텔레그램에서 준비하세요:")
    print("  1) @BotFather 에게 /newbot 을 보내 봇을 만듭니다")
    print("  2) 받은 토큰을 복사합니다")
    print("  3) 만든 봇에게 아무 말이나 겁니다 (예: 안녕)")
    print()

    token = input("봇 토큰을 붙여넣으세요: ").strip()
    if not token:
        print("토큰이 비었습니다. 중단합니다.", file=sys.stderr)
        return 1

    ids, err = fetch_chat_ids(token)
    if err:
        print(err, file=sys.stderr)
        return 1
    if not ids:
        print("chat_id 를 찾지 못했습니다 — 봇에게 먼저 말을 걸고 다시 실행하세요.",
              file=sys.stderr)
        return 1

    if len(ids) == 1:
        chat_id = ids[0]
        print(f"chat_id 를 찾았습니다: {chat_id}")
    else:
        print("여러 개를 찾았습니다:")
        for i, cid in enumerate(ids, 1):
            print(f"  {i}) {cid}")
        pick = input(f"번호를 고르세요 (1~{len(ids)}): ").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(ids):
            print("잘못 골랐습니다. 중단합니다.", file=sys.stderr)
            return 1
        chat_id = ids[int(pick) - 1]

    path = upsert_env({"SHORTS_TELEGRAM_TOKEN": token,
                       "SHORTS_TELEGRAM_CHAT_ID": chat_id})
    print()
    print(f"{path} 에 저장했습니다.")

    if not os.environ.get("DASH_PASS") and "DASH_PASS" not in open(
            path, encoding="utf-8").read():
        print()
        print("⚠️ .env 에 DASH_USER / DASH_PASS 도 있어야 서버를 조회합니다.")
        print("   없으면 봇이 켜질 때 알려줍니다.")

    print()
    print("이제 봇켜기.bat 을 더블클릭하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
