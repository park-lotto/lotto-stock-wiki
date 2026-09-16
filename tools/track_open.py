"""트랙 폴더에서 AI 코딩 도구(Claude Code·Codex)를 연다 — 경로를 손으로 칠 필요 없게.

    트랙.bat            → 열린 트랙 목록에서 번호로 고르기 (더블클릭 가능)
    트랙.bat 보이스      → 바로 그 트랙으로
    코덱스.bat           → 같은 목록에서 고르되 Codex로 연다(2026-09-09)

★도구가 늘어도 여는 절차는 여기 한 곳이다(0순위-B) — 목록·번호 고르기·트랙 검증을
  도구마다 베껴 쓰면 언젠가 한쪽만 고쳐져 어긋난다.

왜 필요한가: 트랙 폴더는 `<프로젝트>/.tracks/<트랙명>`이라 매번
`cd .tracks\\보이스`를 치게 하면 아무도 안 지킨다. 규칙은 지키기 쉬워야 지켜진다
(이 프로젝트가 '규칙으로는 못 막는다'를 이미 두 번 배웠다).
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate
import track


#: 도구별 실행 명령. Codex는 그 폴더에만 쓰기를 허용해 띄운다(read-only면 파일도 못 읽는다 —
#: 실측 2026-09-09: `--sandbox read-only`에서 Get-Content가 "blocked by policy"로 막혔다).
AGENTS = {
    "claude": ["claude"],
    "codex": ["codex", "--sandbox", "workspace-write"],
}


def open_track(name, repo=track.BASE, agent="claude", extra=()):
    wt = track.worktree_path(name, repo)
    if not wt.exists():
        raise track.TrackError(
            f"없는 트랙: {name}\n"
            f"만들려면: py tools/track.py start {name}"
        )
    print(f"\n▶ {name} 트랙에서 엽니다\n  {wt}\n")
    # cwd만 바꿔 claude를 띄운다. 출력을 캡처하지 않으므로 TUI가 콘솔을 그대로 쓴다.
    return subprocess.call(["claude", *sys.argv[2:]], cwd=str(wt))


def choose(repo=track.BASE):
    names = [b[len(track.BRANCH_PREFIX):] for b in track.track_branches(repo)]
    names = [n for n in names if track.worktree_path(n, repo).exists()]
    if not names:
        print("열린 트랙이 없다.\n  새로 만들기: py tools/track.py start <이름>")
        return None
    print("\n열린 트랙:\n")
    for i, n in enumerate(names, 1):
        ahead = track.ahead_count(repo, track.branch_name(n))
        tail = f"  (main보다 {ahead}커밋 앞섬)" if ahead else ""
        print(f"  {i}. {n}{tail}")
    print()
    try:
        pick = input("번호 (엔터=취소): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not pick:
        return None
    if not pick.isdigit() or not (1 <= int(pick) <= len(names)):
        print(f"잘못된 번호: {pick}")
        return None
    return names[int(pick) - 1]


def main(argv=None):
    merge_gate.make_output_safe()
    argv = list(sys.argv[1:] if argv is None else argv)
    agent = "claude"
    if argv and argv[0] == "--agent":        # 코덱스.bat이 넘긴다
        argv.pop(0)
        agent = (argv.pop(0) if argv else "claude").lower()
    name = argv[0] if argv else choose()
    if not name:
        return 1
    try:
        return open_track(name, agent=agent, extra=argv[1:])
    except track.TrackError as e:
        print(f"\n중단: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("\n중단: 'claude' 명령을 못 찾았다. PATH를 확인해라.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
