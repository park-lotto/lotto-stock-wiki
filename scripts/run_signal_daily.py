"""시그널 일일 파이프라인: 스냅샷 생성 → 백테스트 갱신 → 서버 동기화.

07:50 ingest_excel 직후(엑셀이 받아진 뒤) 실행한다.
실행: python scripts/run_signal_daily.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _run(label, args):
    print(f"\n▶ {label}")
    r = subprocess.run([sys.executable, *args], cwd=str(ROOT))
    if r.returncode != 0:
        print(f"  ⚠️ {label} 실패(code {r.returncode}) — 계속 진행")
    return r.returncode == 0


def main():
    _run("스냅샷 생성", ["-m", "pipeline.build_signal_snapshot"])
    _run("백테스트 갱신", ["-m", "pipeline.backtest_signal"])
    _run("서버 동기화", ["scripts/sync_signal.py"])
    print("\n✅ 시그널 일일 파이프라인 완료")


if __name__ == "__main__":
    main()
