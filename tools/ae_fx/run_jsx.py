"""실행 중인 After Effects 에 jsx 를 보내고 끝날 때까지 기다린다 (관제 112).

왜 따로 있나(2026-10-04 실측):
  - AfterFX.exe -r 에 한글이 든 경로를 주면 스크립트가 조용히 안 돈다 → 영문 작업 폴더로 복사해 보낸다.
  - ExtendScript 는 BOM 없는 UTF-8 의 한글을 깨뜨린다 → utf-8-sig 로 다시 쓴다.
  - -r 은 바로 돌아오므로, 스크립트가 끝에 쓰는 '완료 파일'을 기다린다.

사용: py tools/ae_fx/run_jsx.py <jsx> <완료파일> [제한초]
"""
import subprocess
import sys
import time
from pathlib import Path

AFTERFX = Path(r"D:\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe")
WORK = Path(r"D:\ae_fx_work")


def main():
    jsx, done = Path(sys.argv[1]), Path(sys.argv[2])
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    run_dir = WORK / "_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    staged = run_dir / jsx.name
    staged.write_text(jsx.read_text(encoding="utf-8"), encoding="utf-8-sig")
    if done.exists():
        done.unlink()
    subprocess.Popen([str(AFTERFX), "-r", str(staged)])
    began = time.time()
    while not done.exists():
        if time.time() - began > limit:
            print(f"[시간 초과] {limit}초 안에 완료 파일이 안 생겼다: {done}")
            return 2
        time.sleep(2)
    time.sleep(1)
    print(f"[완료] {time.time() - began:.0f}초")
    print(done.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
