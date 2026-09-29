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
import argparse
import json
import os
import subprocess
import sys
import tempfile
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

#: 계정 번호 → CLAUDE_CONFIG_DIR. 1번(본계정)은 변수를 **지운다** — 걸면 ~\.claude\.claude.json 을
#: 찾아 빈 설정을 새로 만든다(프로필 주석, 2026-09-21 실측).
ACCOUNT_DIRS = {"1": None, "2": ".claude-sub", "3": ".claude-sub3"}


def build_launch(cwd, *, account="1", agent="claude", model="", prompt="", pc="", tag="",
                 card=None, resume=True, home=None):
    """새 창에서 돌릴 명령·환경·이름을 조립한다(실행 없음 — 테스트 가능한 한 곳, 카드 046).

    이름 = "PC·계정·용도[·카드N]" — Claude 앱 Code 목록에서 두 PC 창을 가른다.
    Claude 창은 텔레그램 플러그인을 끈 설정으로 띄운다: 봇 수신자는 관제창 하나뿐이어야 한다(409).
    """
    account = str(account)
    if account not in ACCOUNT_DIRS:
        raise ValueError(f"없는 계정: {account} (1/2/3)")
    home = Path(home or Path.home())
    name = "·".join([pc, account, tag] + ([f"카드{card}"] if card else []))
    env, unset = {}, []
    if ACCOUNT_DIRS[account]:
        env["CLAUDE_CONFIG_DIR"] = str(home / ACCOUNT_DIRS[account])
    else:
        unset.append("CLAUDE_CONFIG_DIR")
    if agent == "codex":
        argv = list(AGENTS["codex"])
    else:
        argv = ["claude", "--remote-control", name,
                "--settings", str(home / "claude-remote-settings.json")]
        if resume:
            argv.append("--continue")
        if model:
            argv += ["--model", model]
    if prompt:
        argv.append(prompt)
    return {"argv": argv, "env": env, "env_unset": unset, "name": name, "cwd": str(cwd)}


SESSION_FILE = ".session.json"


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def launch_script(L):
    """새 PowerShell 창이 -File 로 돌릴 스크립트. 인라인 -Command 는 Start-Process 가 안쪽
    큰따옴표를 벗겨 ParserError 가 난다(2026-09-30 실측) — 그래서 파일로 넘긴다."""
    lines = [r'$env:PATH = "$env:LOCALAPPDATA\Microsoft\WinGet\Links;$env:PATH"']
    lines += [f"Remove-Item Env:\\{k} -ErrorAction SilentlyContinue" for k in L["env_unset"]]
    lines += [f"$env:{k} = {_ps_quote(v)}" for k, v in L["env"].items()]
    lines.append(f"Set-Location -LiteralPath {_ps_quote(L['cwd'])}")
    lines.append(f"$Host.UI.RawUI.WindowTitle = {_ps_quote(L['name'])}")
    lines.append("& " + " ".join(_ps_quote(a) for a in L["argv"]))
    return "\r\n".join(lines) + "\r\n"


def launch_window(L):
    """보이는 새 PowerShell 창에서 L 을 실행하고, 트랙 폴더에 창 pid 를 적는다."""
    fd, path = tempfile.mkstemp(suffix=".ps1", prefix="track_open_")
    with os.fdopen(fd, "w", encoding="utf-8-sig") as f:       # PS 5.1 은 BOM 없으면 한글이 깨진다
        f.write(launch_script(L))
    p = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", path],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    Path(L["cwd"], SESSION_FILE).write_text(
        json.dumps({"pid": p.pid, "name": L["name"]}, ensure_ascii=False), encoding="utf-8")
    return p.pid


def _image_name(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout.strip()
    return out.split(",")[0].strip('"').lower() if out.startswith('"') else ""


def session_alive(cwd):
    """트랙 폴더에 기록된 창이 아직 떠 있으면 그 기록, 아니면 None(낡은 기록 포함)."""
    try:
        rec = json.loads(Path(cwd, SESSION_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if _image_name(rec.get("pid", 0)) == "powershell.exe" else None


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
    if argv and argv[0] == "--window":        # claude-remote.ps1 이 넘긴다(트랙 없는 창, 카드 046)
        ap = argparse.ArgumentParser()
        ap.add_argument("--window", action="store_true")
        ap.add_argument("--tag", required=True)
        ap.add_argument("--account", default="1")
        ap.add_argument("--model", default="")
        ap.add_argument("--cwd", required=True)
        a = ap.parse_args(argv)
        import pc_label
        L = build_launch(a.cwd, account=a.account, model=a.model, pc=pc_label.label(),
                         tag=a.tag, resume=False)
        print(f"열림: {L['name']} (pid {launch_window(L)})")
        return 0
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
