"""aerender 로 렌더 대기열을 뽑고, 그 사이 생긴 에펙 디스크 캐시를 지운다 (관제 112).

왜(2026-10-04 실사고): 4초짜리 34개를 뽑는 동안 에펙 디스크 캐시(.aecache)가
C:\\Users\\<나>\\AppData\\Local\\Temp\\Adobe 에 19.27GB 쌓여 C 여유가 0GB 가 됐다 — 다른 세션의 쓰기까지 실패했다.
그래서 ①시작 전 C 여유를 보고 ②끝나면(실패해도) 이번 렌더가 만든 캐시만 지운다.

사용: py tools/ae_fx/render.py <프로젝트.aep>
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

AERENDER = Path(r"D:\Adobe\Adobe After Effects 2026\Support Files\aerender.exe")
CACHE_ROOT = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "Adobe" / "After Effects"
MIN_FREE_GB = 12


def free_gb():
    return shutil.disk_usage("C:\\").free / 1024 ** 3


def purge_since(began):
    n = size = 0
    for f in CACHE_ROOT.rglob("*.aecache"):
        try:
            st = f.stat()
            if st.st_mtime >= began:
                f.unlink()
                n += 1
                size += st.st_size
        except OSError:
            pass
    return n, size / 1024 ** 3


def main():
    project = sys.argv[1]
    before = free_gb()
    if before < MIN_FREE_GB:
        print(f"[거절] C 여유 {before:.1f}GB < {MIN_FREE_GB}GB — 렌더 캐시가 디스크를 채운다. 먼저 비워라.")
        return 3
    began = time.time()
    try:
        run = subprocess.run([str(AERENDER), "-project", project], capture_output=True)
        text = run.stdout.decode("cp949", errors="replace")
        lines = [ln for ln in text.splitlines() if ln.strip() and "PROGRESS:  0:" not in ln]
        print("\n".join(lines[-12:]))
        rc = run.returncode
    finally:
        n, gb = purge_since(began)
        print(f"[캐시] {n}개 {gb:.2f}GB 지움 · C 여유 {before:.1f} → {free_gb():.1f}GB · {time.time() - began:.0f}초")
    return rc


if __name__ == "__main__":
    sys.exit(main())
