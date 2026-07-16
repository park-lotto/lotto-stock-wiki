"""탭 제목 = 지금 이 창이 무슨 작업 중인지. 창 6개를 눈으로 구분하려고.

왜 필요한가: Claude Code는 탭 제목을 **세션 이름**에서 가져오는데(설치본의
`terminalTitleFromRename`, 기본 켜짐) 그 이름은 **대화 내용 자동요약**이다.
그래서 퍼미션 얘기로 시작한 창은 탭에 "권한 없이 작업 진행하기"가 뜬다.

## 어떻게 도나

Claude가 탭을 직접 못 박는다 — **Bash 출력은 터미널에 안 닿는다**(실측: OSC를
내보내면 그냥 문자로 캡처된다). 훅만이 `terminalSequence`로 터미널에 쓸 수 있다.
그래서 두 조각으로 나눈다:

    Claude:  py tools/session_title.py set "보이스 T6 회수"   ← 상태파일에 쓴다
    훅:      py tools/session_title.py                        ← 읽어서 탭에 박는다

상태는 **세션마다 따로**다(`CLAUDE_CODE_SESSION_ID`, Bash에 노출됨 — 실측).
창 6개가 같은 폴더를 봐도 서로 제목을 안 밟는다.

제목 우선순위:
    1. Claude가 `set`으로 박은 것       ← "지금 뭘 하는지"가 제일 정확하다
    2. 트랙 폴더명(`.tracks/<트랙명>`)  ← 안 박았으면 폴더가 곧 트랙
    3. "main · 위키/조사"

## 계약 (설치본 스키마 실측 — 추측 아님)

`terminalSequence`는 **최상위 필드**다. `hookSpecificOutput` 안에 넣으면 무시된다.
설치본 describe: "Only notification/title OSCs (0, 1, 2, 9, 99, 777) and BEL are
permitted; anything else is dropped." → OSC 2(창/탭 제목)를 쓴다.
`sessionTitle`은 `UserPromptSubmit`의 `hookSpecificOutput`에 있다("Set the session title").
"""
import json
import os
import sys
import tempfile
from pathlib import Path

TRACKS_DIR = ".tracks"
MAIN_TITLE = "main · 위키/조사"
# 탭은 좁다. 터미널이 알아서 자르기 전에 우리가 줄여야 이름이 온전히 보인다.
MAX_LEN = 40
STATE_DIR = Path(tempfile.gettempdir()) / "claude_session_title"
# 세션 이름을 덮는 건 이 이벤트뿐이다(설치본 스키마).
SESSION_TITLE_EVENTS = {"UserPromptSubmit"}


def state_file(session_id):
    if not session_id:
        return None
    # 세션 id는 uuid다. 경로가 될 만한 글자만 남겨 디렉터리 탈출을 막는다.
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
    return STATE_DIR / f"{safe}.txt" if safe else None


def read_label(session_id):
    """Claude가 `set`으로 박아둔 '지금 하는 일'. 없으면 None."""
    f = state_file(session_id)
    if not f or not f.exists():
        return None
    try:
        label = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return label or None


def write_label(session_id, label):
    f = state_file(session_id)
    if not f:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text((label or "").strip(), encoding="utf-8")
    return True


def track_of(cwd):
    """작업 폴더에서 트랙명을 뽑는다. 트랙 폴더가 아니면 None.

    `.tracks/<트랙명>` 바로 아래든 더 깊은 곳이든 같은 트랙이다.
    """
    if not cwd:
        return None
    parts = [p for p in str(cwd).replace("\\", "/").split("/") if p]
    try:
        i = parts.index(TRACKS_DIR)
    except ValueError:
        return None
    if i + 1 >= len(parts):
        return None
    return parts[i + 1]


def title_for(cwd, session_id=None):
    """탭에 띄울 제목. Claude가 박은 게 있으면 그게 이긴다."""
    title = read_label(session_id) or track_of(cwd) or MAIN_TITLE
    return title[:MAX_LEN]


def osc_title(title):
    """OSC 2 = 창/탭 제목. 설치본 allowlist가 OSC 0/1/2/9/99/777만 허용한다."""
    return f"\033]2;{title}\007"


def build_output(event, cwd, session_id=None):
    """훅이 돌려줄 JSON.

    ★terminalSequence는 최상위다 — hookSpecificOutput 안에 넣으면 조용히 무시된다.
    """
    title = title_for(cwd, session_id)
    out = {"terminalSequence": osc_title(title)}
    if event in SESSION_TITLE_EVENTS:
        # 세션 이름 자체를 덮어야 자동요약이 나중에 탭을 되찾아가지 못한다.
        out["hookSpecificOutput"] = {"hookEventName": event, "sessionTitle": title}
    return out


def run_hook(stdin, stdout):
    try:
        payload = json.load(stdin)
    except Exception:
        payload = {}
    event = payload.get("hook_event_name") or ""
    cwd = payload.get("cwd") or os.getcwd()
    session_id = payload.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    json.dump(build_output(event, cwd, session_id), stdout)
    return 0


def run_set(label, stdout, env=None):
    env = os.environ if env is None else env
    session_id = env.get("CLAUDE_CODE_SESSION_ID")
    if not write_label(session_id, label):
        # 세션 id가 없으면 조용히 실패하지 마라 — 제목이 안 바뀐 걸 모르게 된다.
        print("no CLAUDE_CODE_SESSION_ID - title not set", file=sys.stderr)
        return 1
    # ASCII로만 찍는다. 이 저장소가 cp949로 오늘만 네 번 죽었다.
    stdout.write("session title set\n")
    return 0


def main(argv=None, stdin=None, stdout=None):
    argv = sys.argv[1:] if argv is None else argv
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if argv and argv[0] == "set":
        return run_set(" ".join(argv[1:]), stdout)
    return run_hook(stdin, stdout)


if __name__ == "__main__":
    sys.exit(main())
