"""숏템프리셋 한 번에 반영 — 칼카피 트랙들이 쌓은 장부를 모아 main 병합 → 라이브 (관제 224, 2026-10-18 사장님).

사장님: "커밋하면 트랙에 모두 각자 기록을 다 하고, 내가 요청하거나 아니면 새벽 2시에 저장된 모든 거 한 번에 병합 후 라이브 간다."
그래서 세션은 장부 바꿀 때마다 병합하지 않는다 — 자기 트랙에 커밋만 한다. 반영은 이 도구 하나가 한다:
  ① track.py use 숏템프리셋 (D 에 가 있거나 치워졌으면 되살림)
  ② 숏템프리셋 트랙의 sync_preset_ledgers.py — 칼카피숏템엔진 마지막 커밋의 장부·근거 문서 중 main 과 다른 것만 옮겨 커밋
  ③ 옮긴 게 있을 때만 track.py finish 숏템프리셋 (관문 통과 시 main → 서버 배포창 2~6시에 라이브)

  py tools/calcopy/preset_publish.py            # 사장님이 "반영해" 할 때(지금 바로)
  py tools/calcopy/preset_publish.py --install  # 매일 02:00 작업 스케줄러 등록(숏템_숏템프리셋_반영)
로그: .tracks/_finish_logs/preset_publish.log (스케줄러 실행분)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TRACK = "숏템프리셋"
TASK = "숏템_숏템프리셋_반영"


def _python() -> str:
    exe = Path(sys.executable)
    p = exe.with_name("python.exe")               # 스케줄러는 pythonw 로 띄운다 — 자식은 콘솔 파이썬으로
    return str(p if p.exists() else exe)


def main_repo() -> Path:
    here = Path(__file__).resolve().parent
    out = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=here,
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    return Path(out).parent


def _run(args, cwd) -> int:
    print("$", " ".join(str(a) for a in args), flush=True)
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    print((r.stdout + r.stderr).strip()[-3000:], flush=True)
    return r.returncode


def publish() -> int:
    repo = main_repo()
    track_py = repo / ".tracks" / "_tools_latest" / "tools" / "track.py"
    track_py = track_py if track_py.exists() else repo / "tools" / "track.py"
    wt = repo / ".tracks" / TRACK
    if _run([_python(), track_py, "use", TRACK], repo) != 0 and not wt.exists():
        print(f"❌ 트랙 폴더 {wt} 를 못 살렸다", flush=True)
        return 2
    _run(["git", "fetch", "-q", "origin"], wt)
    _run(["git", "merge", "-q", "--ff-only", "origin/main"], wt)      # 트랙이 main 보다 뒤면 따라붙는다(앞선 커밋은 그대로)
    rc = _run([_python(), "tools/calcopy/sync_preset_ledgers.py"], wt)    # 다른 것만 옮겨 커밋(없으면 그냥 0)
    if rc != 0:
        print(f"❌ 장부 옮기기 실패(rc={rc})", flush=True)
        return rc
    ahead = subprocess.run(["git", "rev-list", "--count", "origin/main..HEAD"], cwd=wt,
                           capture_output=True, text=True).stdout.strip()
    if ahead in ("", "0"):
        print("✅ 반영할 것 없음 — 페이지 장부 = 엔진 마지막 커밋", flush=True)
        return 0
    return _run([_python(), track_py, "finish", TRACK], repo)


def install() -> bool:
    repo = main_repo()
    base = repo / ".tracks" / "_tools_latest"           # 최신 main 도구 폴더(main 폴더가 옛 판이어도 최신으로 돈다)
    base = base if (base / "tools" / "calcopy" / "preset_publish.py").exists() else repo
    sys.path.insert(0, str(base / "tools"))
    import win_schedule
    return win_schedule.register(TASK, ["/SC", "DAILY", "/ST", "02:00"], base,
                                 [r"tools\calcopy\preset_publish.py"],
                                 repo / ".tracks" / "_finish_logs" / "preset_publish.log")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit((0 if install() else 1) if "--install" in sys.argv else publish())
