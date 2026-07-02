"""
sync_crawling.py — crawling_bot_data → raw/ 동기화

crawling_bot_data/{날짜}/{유형}/ 파일들을 raw/{유형}/ 로 복사.
이미 존재하는 파일은 스킵. 새 유형 폴더는 자동 생성.

사용법:
    python scripts/sync_crawling.py              # 오늘 날짜
    python scripts/sync_crawling.py --date 2026-06-07
    python scripts/sync_crawling.py --all        # 전체 날짜
    python scripts/sync_crawling.py --ingest     # 동기화 후 ingest 실행
"""
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# 경로 설정
CRAWLING_ROOT = Path(r"C:\Users\TheRose\crawling_bot_data")
RAW_ROOT = Path(__file__).parent.parent / "raw"

# crawling_bot_data 유형 → raw/ 폴더 매핑
# 새 유형이 생기면 여기에 추가하거나, 매핑 없으면 이름 그대로 사용
TYPE_MAP = {
    "blog":               "blog",
    "news":               "news",
    "market":             "market",
    "reports":            "report",
    "reports_summarized": "report",   # 요약본도 report로 통합
    "telegram":           "telegram",
    "youtube":            "yt",
}


def sync_date(date_str: str, overwrite: bool = False) -> list[Path]:
    """특정 날짜 폴더를 raw/로 복사. 복사된 파일 목록 반환.

    overwrite=True면 이미 있어도 덮어씀 (텔레그램처럼 채널당 1파일에
    당일 내내 내용이 append되는 경우, 오후 슬롯에서 갱신본을 raw/로 반영)."""
    date_dir = CRAWLING_ROOT / date_str
    if not date_dir.exists():
        print(f"[SKIP] {date_str} — 폴더 없음")
        return []

    copied = []
    for type_dir in sorted(date_dir.iterdir()):
        if not type_dir.is_dir():
            continue

        raw_type = TYPE_MAP.get(type_dir.name, type_dir.name)  # 매핑 없으면 이름 그대로
        dest_dir = RAW_ROOT / raw_type
        dest_dir.mkdir(parents=True, exist_ok=True)

        for src in sorted(type_dir.iterdir()):
            if not src.is_file():
                continue
            dest = dest_dir / src.name
            if dest.exists() and not overwrite:
                continue  # 이미 있으면 스킵 (overwrite면 갱신)
            shutil.copy2(src, dest)
            copied.append(dest)
            print(f"  [복사] {raw_type}/{src.name}")

    return copied


def get_all_dates() -> list[str]:
    """crawling_bot_data의 날짜 폴더 전체 목록 (오름차순)."""
    return sorted(
        d.name for d in CRAWLING_ROOT.iterdir()
        if d.is_dir() and d.name[:4].isdigit() and len(d.name) == 10
    )


def run_ingest(files: list[Path]) -> None:
    """복사된 파일들을 ingest.

    ⚠️ report/telegram/blog/news/yt 는 전용 파이프라인
    (report_ingest / telegram_ingest / post_ingest)이 질문지+레지스트리 경로로
    처리한다. 여기 제네릭 경로(pipeline.atoms.ingest)로 처리하면 신뢰도가 D로
    뭉개지므로 스킵한다. atom_pipeline.py의 STEP3~3.8이 뒤이어 담당한다.
    """
    if not files:
        return
    # 전용 STEP이 담당하는 유형 — ingest_pending.EXCLUDED_TYPES와 동일
    try:
        from pipeline.atoms.ingest_pending import EXCLUDED_TYPES
    except Exception:
        EXCLUDED_TYPES = {"report", "telegram", "blog", "news", "yt"}
    # MD, JSON만 ingest (이미지·Excel은 별도 처리) + 전용 STEP 유형 제외
    ingest_targets = []
    for f in files:
        if f.suffix.lower() not in {".md", ".json"}:
            continue
        try:
            ftype = f.relative_to(RAW_ROOT).parts[0]
        except Exception:
            ftype = ""
        if ftype in EXCLUDED_TYPES:
            continue
        ingest_targets.append(f)
    if not ingest_targets:
        print("[INGEST] ingest 대상 파일 없음 (전용 STEP 유형 제외 후 남은 MD/JSON 없음)")
        return

    import subprocess
    today = datetime.now().strftime("%Y-%m-%d")
    for f in ingest_targets:
        print(f"  [INGEST] {f.relative_to(RAW_ROOT.parent)}")
        subprocess.run(
            [sys.executable, "-m", "pipeline.atoms.ingest", str(f), today],
            cwd=str(RAW_ROOT.parent)
        )


def main():
    parser = argparse.ArgumentParser(description="crawling_bot_data → raw/ 동기화")
    parser.add_argument("--date", default=None, help="특정 날짜 (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="전체 날짜 동기화")
    parser.add_argument("--ingest", action="store_true", help="동기화 후 ingest 실행")
    parser.add_argument("--overwrite", action="store_true",
                        help="이미 있는 파일도 덮어씀 (텔레 당일 갱신본 반영용)")
    args = parser.parse_args()

    if args.all:
        dates = get_all_dates()
    elif args.date:
        dates = [args.date]
    else:
        dates = [datetime.now().strftime("%Y-%m-%d")]

    print(f"[SYNC] 대상 날짜: {dates}")
    print(f"  소스: {CRAWLING_ROOT}")
    print(f"  대상: {RAW_ROOT}\n")

    all_copied = []
    for date in dates:
        copied = sync_date(date, overwrite=args.overwrite)
        all_copied.extend(copied)

    print(f"\n[OK] 총 {len(all_copied)}개 파일 복사 완료")

    if args.ingest and all_copied:
        print("\n[INGEST] ingest 시작...")
        run_ingest(all_copied)


if __name__ == "__main__":
    main()
