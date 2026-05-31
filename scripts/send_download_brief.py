"""
send_download_brief.py — 엑셀 다운로드 결과 → 텔레그램 발송

사용법:
  python scripts/send_download_brief.py
  python scripts/send_download_brief.py --dry
"""
import sys, json, urllib.request, urllib.parse, argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT     = Path(__file__).parent.parent
SAVE_DIR = ROOT / "raw" / "매일 엑셀넣을것"


def load_env() -> dict:
    env_path = ROOT / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def send_telegram(text: str) -> bool:
    cfg = load_env()
    token   = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  .env 에 BOT_TOKEN / CHAT_ID 없음")
        return False

    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for idx, chunk in enumerate(chunks, 1):
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as resp:
                result = json.loads(resp.read())
                if not result.get("ok"):
                    print(f"❌ {result}")
                    return False
        except Exception as e:
            print(f"❌ 발송 실패: {e}")
            return False
    print(f"✅ 텔레그램 발송 완료 ({len(chunks)}건)")
    return True


def build_message() -> str:
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    files = sorted(SAVE_DIR.iterdir()) if SAVE_DIR.exists() else []
    excel = [f for f in files if f.suffix in (".xlsx", ".xlsm") and f.is_file()]

    lines = [f"📥 <b>태린이아빠 엑셀 다운로드</b> — {now}"]
    lines.append("")

    if excel:
        for f in excel:
            kb   = f.stat().st_size // 1024
            name = f.stem  # 확장자 제외
            lines.append(f"✅ {name}  ({kb:,}KB)")
        lines.append("")
        lines.append(f"총 {len(excel)}개 파일")
    else:
        lines.append("⚠️ 다운로드된 파일 없음 — 수동 확인 필요")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    msg = build_message()
    print(msg)

    if not args.dry:
        send_telegram(msg)


if __name__ == "__main__":
    main()
