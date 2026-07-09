"""
remote_daily_ingest.py — Lightsail 원격 서버 전용 일일 캐치업

로컬 atom_pipeline.py의 원격판. 차이점:
  - crawling_bot_data(윈도우 전용) 대신 같은 서버의 kmong/crawling_bot/output/md/{date}/
    를 raw/{카테고리}로 직접 복사 (sync_crawling.py의 TYPE_MAP과 동일 매핑)
  - win32com 의존 오실레이터(STEP4)는 리눅스에서 못 돌리므로 제외
  - 로컬과 Gemini 키 풀을 공유하므로, 카테고리를 동시에 여러 개 띄우면
    같은 sqlite 파일에 여러 프로세스가 동시에 insert_atom()을 호출하다가
    쓰기가 유실되는 사고가 있었다(2026-07-03 실측) — 그래서 전부 순차 실행.

사용법:
    python scripts/remote_daily_ingest.py              # 오늘 날짜
    python scripts/remote_daily_ingest.py --date 2026-07-03
"""
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable
CRAWL_OUTPUT_ROOT = Path("/home/ubuntu/kmong/crawling_bot/output/md")

# kmong 크롤봇 유형 → raw/ 폴더 매핑 (sync_crawling.py TYPE_MAP과 동일)
TYPE_MAP = {
    "blog": "blog",
    "news": "news",
    "market": "market",
    "reports": "report",
    "telegram": "telegram",
    "youtube": "yt",
}


def _copy_normalized(src: Path, dst: Path) -> None:
    """.gitattributes(eol=lf)와 어긋나는 CRLF가 섞이면 체크아웃마다 phantom
    modified가 떠서 git pull이 막힌다(2026-07-09 사고) — LF로 정규화해 복사."""
    try:
        text = src.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        shutil.copy2(src, dst)
        return
    dst.write_text(text, encoding="utf-8", newline="\n")


def sync_from_crawler(date_str: str) -> None:
    src_root = CRAWL_OUTPUT_ROOT / date_str
    if not src_root.exists():
        print(f"[SYNC] {src_root} 없음 — 크롤 결과 없음")
        return
    total = 0
    for kmong_type, raw_type in TYPE_MAP.items():
        src_dir = src_root / kmong_type
        if not src_dir.exists():
            continue
        dst_dir = ROOT / "raw" / raw_type
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.glob("*.md"):
            dst = dst_dir / f.name
            if dst.exists():
                continue
            _copy_normalized(f, dst)
            total += 1
    print(f"[SYNC] {total}개 파일 복사 완료")


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*50}\n[{label}] {' '.join(str(c) for c in cmd)}\n{'='*50}")
    r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"[{label}] 완료 (exit={r.returncode})")
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    today = args.date or datetime.now().strftime("%Y-%m-%d")

    print(f"\n[remote_daily_ingest] 시작: {today}")
    sync_from_crawler(today)

    # 순차 실행 필수 — 동시 실행 시 sqlite 쓰기 유실 사고 있었음(2026-07-03)
    run([PYTHON, "-m", "pipeline.atoms.telegram_ingest", "--all", "--date", today, "--limit", "30"],
        "telegram")
    run([PYTHON, "-m", "pipeline.atoms.report_ingest", "--all", "--date", today, "--limit", "30"],
        "report")
    run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "blog", "--all", "--date", today, "--limit", "20"],
        "blog")
    run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "youtube", "--all", "--date", today, "--limit", "10"],
        "youtube")
    run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "news", "--all", "--date", today, "--limit", "40"],
        "news")

    print(f"\n[remote_daily_ingest] 완료: {today}")


if __name__ == "__main__":
    main()
