"""
atom_pipeline.py — 크롤링봇 데이터 → 원자 DB 자동 파이프라인

매일 자동 실행 (Task Scheduler):
  1. crawling_bot_data → raw/ 동기화 (새 파일만)
  2. 새 파일 원자화 → atoms.db + ChromaDB
  3. 리포트 PDF 원자화 (최대 20개)
  4. 미처리 잔여 파일 ingest (최대 30개)

사용법:
    python scripts/atom_pipeline.py              # 오늘 날짜 기준
    python scripts/atom_pipeline.py --date 2026-06-07
    python scripts/atom_pipeline.py --skip-pdf   # PDF 건너뜀
    python scripts/atom_pipeline.py --dry-run    # 실행 없이 상태만 출력
"""
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*50}")
    print(f"[{label}] {' '.join(str(c) for c in cmd)}")
    print('='*50)
    r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"[{label}] 완료 (exit={r.returncode})")
    return r.returncode


def main():
    parser = argparse.ArgumentParser(description="크롤링봇 → 원자 DB 자동 파이프라인")
    parser.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD), 기본=오늘")
    parser.add_argument("--skip-pdf", action="store_true", help="PDF ingest 건너뜀")
    parser.add_argument("--pdf-limit", type=int, default=20, help="PDF 처리 최대 수 (기본 20)")
    parser.add_argument("--pending-limit", type=int, default=30, help="미처리 파일 최대 수 (기본 30)")
    parser.add_argument("--dry-run", action="store_true", help="상태만 출력, 실행 없음")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    print(f"\n[atom_pipeline] 시작: {today}")
    print(f"{'='*50}")

    if args.dry_run:
        # 상태만 출력
        subprocess.run([PYTHON, "scripts/sync_crawling.py", "--date", today], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.ingest_pending", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        if not args.skip_pdf:
            subprocess.run([PYTHON, "-m", "pipeline.atoms.report_ingest", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        return

    # 1단계: 동기화 + 새 파일 원자화
    run([PYTHON, "scripts/sync_crawling.py", "--date", today, "--ingest"],
        "STEP1 sync+ingest")

    # 2단계: 미처리 잔여 파일 처리 (어제 이전 누락분 포함)
    run([PYTHON, "-m", "pipeline.atoms.ingest_pending",
         "--limit", str(args.pending_limit)],
        "STEP2 pending")

    # 3단계: 리포트 PDF 원자화 (질문지 방식)
    if not args.skip_pdf:
        run([PYTHON, "-m", "pipeline.atoms.report_ingest",
             "--all", "--limit", str(args.pdf_limit)],
            "STEP3 report_ingest")

    # 4단계: 수급 오실레이터 (xlsm 파일 있을 때만)
    osc_xlsm = list(ROOT.glob("raw/매일 엑셀넣을것/외국인기관수급오실레이터*.xlsm"))
    if osc_xlsm:
        import subprocess as _sp
        print(f"\n{'='*50}")
        print(f"[STEP4 oscillator] {osc_xlsm[0].name}")
        osc_result = _sp.run(
            [PYTHON, "calc_oscillator.py", "--all", "--json"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8"
        )
        if osc_result.returncode == 0 and osc_result.stdout.strip():
            ingest_result = _sp.run(
                [PYTHON, "-m", "pipeline.atoms.osc_ingest", "--stdin"],
                input=osc_result.stdout, cwd=str(ROOT),
                capture_output=False, text=True, encoding="utf-8"
            )
            print(f"[STEP4 oscillator] 완료 (exit={ingest_result.returncode})")
        else:
            print(f"[STEP4 oscillator] 건너뜀 (오실레이터 실행 실패 또는 빈 결과)")

    # 5단계: wiki 자동 반영
    run([PYTHON, "-m", "pipeline.atoms.wiki_update"], "STEP5 wiki_update")

    # 최종 현황 출력
    print(f"\n{'='*50}")
    print("[atom_pipeline] 완료 — 현황:")
    subprocess.run([
        PYTHON, "-c",
        "import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace');"
        "from pipeline.atoms.db import get_conn;"
        "from pipeline.atoms.vector_db import get_collection;"
        "conn=get_conn();"
        "total=conn.execute('SELECT COUNT(*) FROM atoms').fetchone()[0];"
        "conn.close();"
        "print(f'atoms.db: {total}개 | ChromaDB: {get_collection().count()}개')"
    ], cwd=str(ROOT))


if __name__ == "__main__":
    main()
