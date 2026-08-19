"""다른 PC에서 종목검색 화면을 로컬로 띄울 때 필요한 것들을 점검·준비한다.

    py scripts/stock_setup.py

## 왜 필요한가

코드는 git으로 따라오지만 **데이터는 안 따라온다**(전부 gitignore):

    pipeline/atoms/atoms.db   발언 — 없으면 검색·판단·쟁점 칸이 통째로 빈다
    data/flow.db              수급 — 없으면 외국인·기관 표와 차트 마커가 빈다
    .env                      KIS 키 — 없으면 차트·수급 조회 자체가 안 된다

그래서 다른 PC에서 `git pull`만 하면 화면이 **조용히 반쪽**이 된다. 에러가 안 나고
그냥 비어 보이기 때문에 "고장났다"로 오해하기 쉽다. 이 스크립트가 무엇이 없는지
먼저 말해주고, 자동으로 채울 수 있는 것은 채운다.

⚠️ 라이브(stockbrain1.duckdns.org)는 서버가 자기 데이터를 갖고 있으므로 **이것과 무관하다.**
   로컬에서 직접 띄워 확인할 때만 필요하다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)


def _p(*parts):
    return os.path.join(BASE, *parts)


def _mb(path):
    try:
        return os.path.getsize(path) / 1024 / 1024
    except OSError:
        return 0


def _find_main_folder() -> str | None:
    """트랙 폴더(.tracks/<이름>)에서 돌고 있다면 main 폴더를 찾아 준다."""
    parent = os.path.dirname(BASE)
    if os.path.basename(parent) == ".tracks":
        return os.path.dirname(parent)
    return None


def check_env() -> bool:
    path = _p(".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="ignore") as f:
            has_kis = any(l.startswith("KIS_APP_KEY") for l in f)
        if has_kis:
            print("  [OK] .env — KIS 키 있음")
            return True
        print("  [!!] .env는 있는데 KIS_APP_KEY가 없다 → 차트·수급 조회가 안 된다")
        return False
    print("  [!!] .env 없음 → 차트·수급 조회가 안 된다")
    print("       py tools/track.py start <트랙명> 으로 트랙을 만들면 자동 복사된다.")
    return False


def check_atoms() -> bool:
    path = _p("pipeline", "atoms", "atoms.db")
    if os.path.exists(path) and _mb(path) > 1:
        print(f"  [OK] atoms.db {_mb(path):.0f}MB — 발언 자료 있음")
        return True

    main = _find_main_folder()
    src = os.path.join(main, "pipeline", "atoms", "atoms.db") if main else ""
    if src and os.path.exists(src) and _mb(src) > 1:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(src, path)
        print(f"  [채움] atoms.db {_mb(path):.0f}MB — main 폴더에서 복사했다")
        return True

    print("  [!!] atoms.db 없음 → 발언·판단·쟁점 칸이 통째로 빈다")
    print("       서버에서 받아라(용량 약 32MB):")
    print("       scp -i <키> ubuntu@43.200.48.69:"
          "/home/ubuntu/lotto-stock-wiki/pipeline/atoms/atoms.db pipeline/atoms/")
    return False


def check_flow(auto: bool) -> bool:
    path = _p("data", "flow.db")
    if os.path.exists(path) and _mb(path) > 0.05:
        import sqlite3
        conn = sqlite3.connect(path)
        n, days = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT date) FROM stock_flow_daily").fetchone()
        conn.close()
        print(f"  [OK] flow.db {n:,}행 · {days}일 — 수급 자료 있음")
        return True

    print("  [--] flow.db 없음 → 외국인·기관 표와 차트 수급 마커가 빈다")
    if not auto:
        print("       채우려면: py scripts/flow_daily.py   (398종목 약 6분)")
        return False

    print("       지금 채운다 — 398종목, 약 6분 걸린다…")
    r = subprocess.run([sys.executable, os.path.join(HERE, "flow_daily.py")],
                       cwd=BASE)
    return r.returncode == 0


def main(argv):
    auto = "--fill" in argv
    print("종목검색 화면 로컬 준비 상태\n")
    ok_env = check_env()
    ok_atoms = check_atoms()
    ok_flow = check_flow(auto and ok_env)

    print("\n" + "-" * 52)
    if ok_env and ok_atoms and ok_flow:
        print("전부 준비됐다. 아래로 띄우면 된다:")
    else:
        print("빠진 게 있다. 위 안내대로 채운 뒤 띄워라:")
        if ok_env and not ok_flow:
            print("  (수급만 없으면) py scripts/stock_setup.py --fill")
    print("  cd dashboard && py -m uvicorn server:app --port 8099")
    print("  → http://127.0.0.1:8099/stock?q=현대차")
    print("\n※ 라이브(stockbrain1.duckdns.org)는 서버가 자기 데이터를 갖고 있어 이것과 무관하다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
