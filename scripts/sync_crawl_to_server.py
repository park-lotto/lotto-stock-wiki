"""크롤링봇 수신폴더(crawling_bot_data) → 서버 대시보드(output/md) 동기화.

사용자의 모든 크롤링(뉴스·리포트·블로그·텔레·유튜브·마켓)이 로컬
C:/Users/TheRose/crawling_bot_data 로 들어온다. 이를 서버로 올려 대시보드에 노출한다.
포맷 동일(이미 output/md 구조) → 그대로 복사. 추가(additive), 서버 파일 삭제 안 함.

실행: python scripts/sync_crawl_to_server.py            # 오늘
      python scripts/sync_crawl_to_server.py --days 2   # 오늘+어제
"""
import argparse
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path("C:/Users/TheRose/crawling_bot_data")
KEY = "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
# IP는 바뀔 수 있다 — 서버 주소는 SERVER_HOST 환경변수로 한 번에 교체한다.
HOST = os.getenv("SERVER_HOST", "ubuntu@3.39.179.148")
REMOTE_MD = "/home/ubuntu/kmong/crawling_bot/output/md"


def _ssh(cmd):
    subprocess.run(["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", HOST, cmd], check=False)


def _scp_dir(local_dir: Path, remote_dir: str):
    subprocess.run(
        ["scp", "-r", "-i", KEY, "-o", "StrictHostKeyChecking=no",
         str(local_dir), f"{HOST}:{remote_dir}/"], check=False)


def sync(days: int):
    today = datetime.now()
    total = 0
    for i in range(days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        day_dir = SRC / date
        if not day_dir.is_dir():
            continue
        cats = [d for d in day_dir.iterdir() if d.is_dir()]
        if not cats:
            continue
        _ssh(f"mkdir -p {REMOTE_MD}/{date}")
        for cat in cats:
            n = len(list(cat.glob("*.md")))
            _scp_dir(cat, f"{REMOTE_MD}/{date}")
            print(f"  {date}/{cat.name}: {n}개 동기화")
            total += n
    print(f"동기화 완료 (총 {total}개 파일)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    args = ap.parse_args()
    sync(args.days)
