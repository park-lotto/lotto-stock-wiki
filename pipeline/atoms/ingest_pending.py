"""
ingest_pending.py — 미처리 파일만 우선순위 순으로 ingest.

우선순위: 최신 날짜 → 신뢰도 높은 유형 순
토큰 절약: --limit로 한 번에 처리할 파일 수 제한

사용법:
    python -m pipeline.atoms.ingest_pending              # 기본 30개
    python -m pipeline.atoms.ingest_pending --limit 10   # 10개만
    python -m pipeline.atoms.ingest_pending --type telegram  # 특정 유형만
    python -m pipeline.atoms.ingest_pending --date 2026-06-07  # 특정 날짜만
    python -m pipeline.atoms.ingest_pending --dry-run    # 목록만 출력
"""
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime

from .db import get_conn, init_db
from .ingest import ingest_file

RAW_ROOT = Path(__file__).parent.parent.parent / "raw"

# 전용 파이프라인 STEP이 이미 담당하는 유형 — 여기서는 절대 건드리지 않는다.
#   report    → report_ingest.py (PDF 질문지 경로)
#   telegram  → telegram_ingest.py (텔레 질문지 경로)
#   blog/news → post_ingest.py --source blog|news (질문지+레지스트리 경로)
#   yt        → post_ingest.py --source youtube
# 이 제네릭 경로(ingest.ingest_file)로 처리하면 신뢰도가 D로 뭉개지고
# 얕은 추출이 되므로, 전용 STEP이 처리하도록 스캔 대상에서 제외한다.
# raw/ 하위 폴더명 기준. (youtube 원본 폴더명은 raw/yt)
EXCLUDED_TYPES = {"report", "telegram", "blog", "news", "yt"}

# 유형별 우선순위 (낮을수록 먼저) — 전용 STEP 없는 유형만 남김
TYPE_PRIORITY = {
    "wisereport": 3,
    "market":     6,
    "L5_섹터":    8,
    "L2_미국시장": 9,
    "L1_글로벌유동성": 10,
    "L3_한국시장": 11,
    "L4_국제정세": 12,
    "L6_수급":    13,
}

# 인제스트 대상 확장자
TARGET_EXTS = {".md", ".json"}

# 건너뛸 파일 패턴
SKIP_PATTERNS = [
    r"ingest_report",
    r"oscillator_scan",
    r"다운로드규칙",
    r"영상\.md",
    r"strategy/",
    r"supply/",
    r"yt_trend/",
    r"\.obsidian",
    # 질문지 OUTPUT 산출물 폴더 — 전용 파이프라인이 이미 만든 결과물이므로
    # fresh input으로 재스캔하면 안 됨 (Gemini 호출 낭비 + 중복)
    r"/telegram_q/",
    r"/report_q/",
    r"/post_q/",
    r"/blog_q/",
]


def _should_skip(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(re.search(p, s) for p in SKIP_PATTERNS)


def _extract_date(path: Path) -> str:
    """파일명 또는 경로에서 날짜 추출. 없으면 '0000-00-00'."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(path))
    return m.group(1) if m else "0000-00-00"


def get_done_files() -> set[str]:
    """atoms.db에서 이미 처리된 raw_file — 파일명(stem) 집합으로 반환.
    절대경로/상대경로 혼재 문제를 파일명 기준으로 해결."""
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT raw_file FROM atoms").fetchall()
    conn.close()
    result = set()
    for (path,) in rows:
        norm = path.replace("\\", "/")
        result.add(norm)
        # 파일명만으로도 매칭
        result.add(norm.split("/")[-1])
    return result


def get_pending_files(
    type_filter: str = None,
    date_filter: str = None,
) -> list[Path]:
    """미처리 파일 목록 — 우선순위 순 정렬."""
    done = get_done_files()

    pending = []
    for f in RAW_ROOT.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in TARGET_EXTS:
            continue
        if _should_skip(f):
            continue
        rel = str(f.relative_to(RAW_ROOT.parent)).replace("\\", "/")
        fname = f.name
        if rel in done or fname in done:
            continue

        # 유형 = raw/ 바로 아래 폴더명
        parts = f.relative_to(RAW_ROOT).parts
        file_type = parts[0] if parts else "기타"

        # 전용 STEP이 담당하는 유형은 여기서 건드리지 않는다.
        # 단, --type으로 명시적으로 지정하면 수동 처리 허용.
        if file_type in EXCLUDED_TYPES and file_type != type_filter:
            continue

        if type_filter and file_type != type_filter:
            continue
        if date_filter and date_filter not in str(f):
            continue

        pending.append(f)

    def sort_key(f: Path):
        parts = f.relative_to(RAW_ROOT).parts
        file_type = parts[0] if parts else "기타"
        date = _extract_date(f)
        priority = TYPE_PRIORITY.get(file_type, 99)
        return (date, priority)  # 날짜 내림차순을 위해 뒤에서 reverse

    return sorted(pending, key=sort_key, reverse=True)


def main():
    parser = argparse.ArgumentParser(description="미처리 파일 우선순위 ingest")
    parser.add_argument("--limit", type=int, default=30, help="처리할 파일 수 (기본 30)")
    parser.add_argument("--type", default=None, dest="type_filter", help="유형 필터 (telegram/blog/news/report 등)")
    parser.add_argument("--date", default=None, dest="date_filter", help="날짜 필터 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="목록만 출력, 실제 처리 없음")
    args = parser.parse_args()

    init_db()
    pending = get_pending_files(args.type_filter, args.date_filter)
    targets = pending[:args.limit]

    print(f"미처리 전체: {len(pending)}개 | 이번 처리: {len(targets)}개 (limit={args.limit})")
    if args.type_filter:
        print(f"유형 필터: {args.type_filter}")
    if args.date_filter:
        print(f"날짜 필터: {args.date_filter}")
    print()

    if args.dry_run:
        for f in targets:
            parts = f.relative_to(RAW_ROOT).parts
            file_type = parts[0] if parts else "기타"
            print(f"  [{file_type}] {f.name}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    total_atoms = 0
    for i, f in enumerate(targets, 1):
        date = _extract_date(f) or today
        parts = f.relative_to(RAW_ROOT).parts
        file_type = parts[0] if parts else "기타"
        print(f"[{i}/{len(targets)}] [{file_type}] {f.name}")
        try:
            count = ingest_file(str(f), date)
            total_atoms += count
            print(f"  → {count}개 원자")
        except Exception as e:
            print(f"  → 실패: {e}")

    print(f"\n완료: {len(targets)}개 파일, {total_atoms}개 원자 생성")
    print(f"남은 미처리: {len(pending) - len(targets)}개")


if __name__ == "__main__":
    main()
