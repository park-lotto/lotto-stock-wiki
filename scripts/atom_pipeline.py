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
    python scripts/atom_pipeline.py --resume     # 중간에 죽었을 때 이어서 (완료된 STEP 건너뜀)
"""
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable


def _state_path(date: str) -> Path:
    return ROOT / "out" / f"atom_pipeline_{date}" / "state.json"


def load_state(date: str) -> dict:
    p = _state_path(date)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"date": date, "steps": {}}


def save_state(date: str, state: dict) -> None:
    p = _state_path(date)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd: list[str], label: str, state: dict = None, date: str = None, resume: bool = False) -> int:
    """state·date가 주어지면 STEP 단위 체크포인트를 남긴다.
    resume=True면 이미 완료된 STEP은 건너뛴다 — 파이프라인 도중 죽었을 때 처음부터 재실행하며
    이미 끝난 Gemini 호출(크롤·인제스트)을 낭비하는 것을 막는다."""
    if resume and state is not None and state["steps"].get(label, {}).get("status") == "done":
        print(f"[{label}] 이미 완료됨 — 건너뜀 (--resume)")
        return 0
    print(f"\n{'='*50}")
    print(f"[{label}] {' '.join(str(c) for c in cmd)}")
    print('='*50)
    r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"[{label}] 완료 (exit={r.returncode})")
    if state is not None and date is not None:
        state["steps"][label] = {"status": "done", "exit": r.returncode,
                                  "at": datetime.now().isoformat()}
        save_state(date, state)
    return r.returncode


def main():
    parser = argparse.ArgumentParser(description="크롤링봇 → 원자 DB 자동 파이프라인")
    parser.add_argument("--date", default=None, help="날짜 (YYYY-MM-DD), 기본=오늘")
    parser.add_argument("--skip-pdf", action="store_true", help="PDF ingest 건너뜀")
    parser.add_argument("--pdf-limit", type=int, default=20, help="PDF 처리 최대 수 (기본 20)")
    parser.add_argument("--pending-limit", type=int, default=30, help="미처리 파일 최대 수 (기본 30)")
    parser.add_argument("--dry-run", action="store_true", help="상태만 출력, 실행 없음")
    parser.add_argument("--resume", action="store_true",
                        help="이전 실행이 중간에 죽었을 때 이어서 — 완료된 STEP은 건너뜀")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    print(f"\n[atom_pipeline] 시작: {today}")
    print(f"{'='*50}")

    state = load_state(today)
    if args.resume and state["steps"]:
        done = [k for k, v in state["steps"].items() if v.get("status") == "done"]
        print(f"[atom_pipeline] --resume: {len(done)}개 STEP 이미 완료됨 → 건너뜀: {', '.join(done)}")

    def r(cmd, label):
        return run(cmd, label, state=state, date=today, resume=args.resume)

    if args.dry_run:
        # 상태만 출력
        subprocess.run([PYTHON, "scripts/sync_crawling.py", "--date", today], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.ingest_pending", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        if not args.skip_pdf:
            subprocess.run([PYTHON, "-m", "pipeline.atoms.report_ingest", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.telegram_ingest", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "blog", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "youtube", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        subprocess.run([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "news", "--all", "--dry-run", "--limit", "5"], cwd=str(ROOT))
        return

    # 1단계: 동기화 + 새 파일 원자화
    r([PYTHON, "scripts/sync_crawling.py", "--date", today, "--ingest"],
        "STEP1 sync+ingest")

    # 2단계: 미처리 잔여 파일 처리 (어제 이전 누락분 포함)
    r([PYTHON, "-m", "pipeline.atoms.ingest_pending",
         "--limit", str(args.pending_limit)],
        "STEP2 pending")

    # 3단계: 리포트 PDF 원자화 (질문지 방식)
    if not args.skip_pdf:
        r([PYTHON, "-m", "pipeline.atoms.report_ingest",
             "--all", "--limit", str(args.pdf_limit)],
            "STEP3 report_ingest")

    # 3.5단계: 텔레그램 인제스트 (질문지 방식)
    r([PYTHON, "-m", "pipeline.atoms.telegram_ingest",
         "--all", "--limit", "30"],
        "STEP3.5 telegram")

    # 3.6단계: 블로그 인제스트 (겸용 post_ingest)
    r([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "blog",
         "--all", "--limit", "30"],
        "STEP3.6 blog")

    # 3.7단계: 유튜브 인제스트 (겸용 post_ingest)
    r([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "youtube",
         "--all", "--limit", "30"],
        "STEP3.7 youtube")

    # 3.8단계: 뉴스 인제스트 (겸용 post_ingest)
    r([PYTHON, "-m", "pipeline.atoms.post_ingest", "--source", "news",
         "--all", "--limit", "40"],
        "STEP3.8 news")

    # 3.9단계: 채널간 이벤트 병합 (비파괴 — mention_count 표시)
    r([PYTHON, "-m", "pipeline.atoms.event_merge", "--date", today],
        "STEP3.9 event_merge")

    # 4단계: 수급 오실레이터 (xlsm 파일 있을 때만)
    osc_xlsm = list(ROOT.glob("raw/매일 엑셀넣을것/외국인기관수급오실레이터*.xlsm"))
    if osc_xlsm and args.resume and state["steps"].get("STEP4 oscillator", {}).get("status") == "done":
        print("[STEP4 oscillator] 이미 완료됨 — 건너뜀 (--resume)")
    elif osc_xlsm:
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
        state["steps"]["STEP4 oscillator"] = {"status": "done", "at": datetime.now().isoformat()}
        save_state(today, state)

    # 4.5단계: 종목→섹터 맵 갱신 + '기타' 원자 재분류 (wiki stock 폴더 반영)
    r([PYTHON, "-m", "pipeline.atoms.build_stock_sector_map"],
        "STEP4.5 sector_map")
    r([PYTHON, "-m", "pipeline.atoms.backfill_sector"],
        "STEP4.6 backfill_sector")

    # 5단계: wiki 자동 반영
    r([PYTHON, "-m", "pipeline.atoms.wiki_update"], "STEP5 wiki_update")

    # 6단계: 매일 건강검진 (정상=1줄/이상=상세 텔레카드)
    r([PYTHON, "-m", "pipeline.atoms.daily_health"], "STEP6 health")

    # 7단계: 사람 브레인 적중률 스냅샷 (퍼널 vs 실제픽 → 이력 누적 → 자동수렴)
    r([PYTHON, "-m", "pipeline.people.track", "태린이아빠"], "STEP7 brain_snapshot")

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
