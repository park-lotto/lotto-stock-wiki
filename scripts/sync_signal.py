"""신호 스냅샷을 서버로 업로드. build_signal_snapshot 직후 실행."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
KEY = "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.39.179.148"
REMOTE_DIR = "/home/ubuntu/kmong/crawling_bot/output/signal"
LOCAL = ROOT / "output" / "signal" / "signal_snapshot.json"


def main():
    if not LOCAL.exists():
        print("스냅샷 없음 — build_signal_snapshot 먼저 실행"); return False
    subprocess.run(
        ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", HOST,
         f"mkdir -p {REMOTE_DIR}"], check=True)
    subprocess.run(
        ["scp", "-i", KEY, "-o", "StrictHostKeyChecking=no",
         str(LOCAL), f"{HOST}:{REMOTE_DIR}/signal_snapshot.json"], check=True)
    print("스냅샷 서버 동기화 완료")
    return True


if __name__ == "__main__":
    main()
