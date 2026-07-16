"""탭 제목을 "지금 무슨 작업 중인지"로 만든다 — 창 6개를 눈으로 구분하려고.

왜 필요한가: Claude Code는 터미널 탭 제목을 **세션 이름**에서 가져오는데(설치본의
`terminalTitleFromRename` 설정, 기본 켜짐), 그 이름은 대화 내용 자동요약이다.
그래서 퍼미션 얘기로 시작한 창은 탭에 "권한 없이 작업 진행하기"가 뜬다.
트랙 6개를 동시에 돌리면 어느 창이 어느 작업인지 알 수 없다.

해법: 세션 이름을 **트랙명**으로 덮는다. 트랙명은 추측할 필요가 없다 —
작업 폴더가 곧 트랙이다(`.tracks/<트랙명>`). CLAUDE.md가 "코드는 트랙 폴더에서"를
강제하므로 cwd만 보면 정확히 알 수 있다.

- `SessionStart`  → `sessionTitle`로 세션 이름 자체를 박는다.
- `UserPromptSubmit` → 매 턴 `terminalSequence`(OSC 2)로 탭을 다시 박는다.
  자동요약이 나중에 세션 이름을 갈아치워도 탭은 트랙명을 지킨다.

허용되는 이스케이프는 설치본에 박혀 있다: OSC 0/1/2/9/99/777 + BEL만 통과.
그래서 OSC 2(`ESC ] 2 ; 제목 BEL`)를 쓴다.
"""
import json
import os
import sys

TRACKS_DIR = ".tracks"
MAIN_TITLE = "main · 위키/조사"
# 탭은 좁다. 길면 터미널이 알아서 자르지만, 자르기 전에 우리가 줄여야
# "장면라이브..." 같은 게 아니라 트랙명이 온전히 보인다.
MAX_LEN = 40


def track_of(cwd):
    """작업 폴더에서 트랙명을 뽑는다. 트랙 폴더가 아니면 None.

    `.tracks/<트랙명>` 바로 아래든 더 깊은 곳이든 같은 트랙이다
    (`.tracks/보이스/shopping_shorts` 에서 열어도 '보이스').
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


def title_for(cwd):
    """탭에 띄울 제목."""
    name = track_of(cwd)
    title = name if name else MAIN_TITLE
    return title[:MAX_LEN]


def osc_title(title):
    """OSC 2 = 창/탭 제목. 설치본 allowlist가 OSC 0/1/2/9/99/777만 허용한다."""
    return f"\033]2;{title}\007"


def build_output(event, cwd):
    """훅이 돌려줄 JSON. 이벤트마다 먹히는 필드가 다르다."""
    title = title_for(cwd)
    out = {"hookEventName": event, "terminalSequence": osc_title(title)}
    if event == "SessionStart":
        # 세션 이름 자체를 덮어야 자동요약이 처음부터 안 뜬다.
        out["sessionTitle"] = title
    return {"hookSpecificOutput": out}


def main(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        payload = json.load(stdin)
    except Exception:
        payload = {}
    event = payload.get("hook_event_name") or "SessionStart"
    cwd = payload.get("cwd") or os.getcwd()
    json.dump(build_output(event, cwd), stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
