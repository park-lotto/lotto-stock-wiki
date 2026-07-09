"""sync_telegram_only.py — 크롤봇 output/md/{날짜}/telegram/ -> raw/telegram/
경량 동기화 전용(텔레그램만). remote_daily_ingest.py는 다른 무거운 작업
(atom추출 등)까지 같이 돌아서 자주 실행하기엔 부담이라, 텔레그램 뉴스릴레이
채널의 빠른 반영("가장 빠른 주식뉴스" 채널이 하루 5번밖에 안 도니 속보가
늦게 반영된다는 지적, 2026-07-03)을 위해 크롤 주기(*/15 7-23)와 맞춰
따로 자주 돌린다.

사용법:
    python scripts/sync_telegram_only.py              # 오늘 날짜
    python scripts/sync_telegram_only.py --date 2026-07-03
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CRAWL_OUTPUT_ROOT = Path("/home/ubuntu/kmong/crawling_bot/output/md")


def _copy_normalized(src: Path, dst: Path) -> None:
    """.gitattributes(eol=lf)와 어긋나는 CRLF가 섞이면 체크아웃마다 phantom
    modified가 떠서 git pull이 막힌다(2026-07-09 사고) — LF로 정규화해 복사."""
    try:
        text = src.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        shutil.copy2(src, dst)
        return
    dst.write_text(text, encoding="utf-8", newline="\n")


def sync_telegram(date_str: str) -> int:
    src_dir = CRAWL_OUTPUT_ROOT / date_str / "telegram"
    if not src_dir.exists():
        print(f"[SYNC] {src_dir} 없음 — 크롤 결과 없음")
        return 0
    dst_dir = ROOT / "raw" / "telegram"
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in src_dir.glob("*.md"):
        dst = dst_dir / f.name
        if dst.exists() and dst.stat().st_mtime >= f.stat().st_mtime:
            continue
        _copy_normalized(f, dst)
        copied += 1
    print(f"[SYNC] 텔레그램 {copied}개 파일 복사(신규/갱신)")
    return copied


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    today = args.date or datetime.now().strftime("%Y-%m-%d")
    sync_telegram(today)


if __name__ == "__main__":
    main()
