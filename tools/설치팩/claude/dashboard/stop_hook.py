"""Stop hook: prompts a per-session dashboard log entry for known project paths."""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
STATE_DIR = BASE / ".stop_state"
# 같은 세션에 이 간격이 지나면 다시 한 번만 알린다(긴 세션 대비). 초 단위.
REMIND_AFTER = 3600


def already_prompted(session_id):
    """이 세션에 최근 알렸으면 True — 매 턴 막는 것을 끊는다(2026-08-18).

    session_id가 없으면(테스트·구버전) 표시를 남기지 않고 항상 알린다.
    파일이 깨졌거나 못 써도 훅이 죽으면 안 되므로 조용히 '안 알림'으로 본다.
    """
    if not session_id:
        return False
    mark = STATE_DIR / f"{session_id}.txt"
    try:
        if mark.is_file() and (time.time() - mark.stat().st_mtime) < REMIND_AFTER:
            return True
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        mark.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        return False
    return False


def match_category(cwd, config):
    cwd_norm = str(Path(cwd).resolve()).lower()
    for cat in config["categories"]:
        for hint in cat.get("path_hints", []):
            hint_norm = str(Path(hint).resolve()).lower()
            if cwd_norm == hint_norm or cwd_norm.startswith(hint_norm + "\\"):
                return cat["name"]
    return None


def active_tracks(cwd):
    """<cwd>/.sessions/*.json 에서 트랙명을 모은다.

    .sessions/ 는 페이즈2에서 생긴다. 없으면 빈 목록(페이즈1에서도 정상 동작).
    손상된 파일은 조용히 건너뛴다 — 훅이 죽으면 세션 종료가 막힌다.
    """
    d = Path(cwd) / ".sessions"
    if not d.is_dir():
        return []
    tracks = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        name = data.get("track")
        if name:
            tracks.append(name)
    return tracks


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    category = match_category(payload.get("cwd", ""), config)
    if category is None:
        return
    # ★한 세션에 한 번만 막는다(2026-08-18 사장님 "매 턴 재발행 안 되게").
    #   Stop 훅은 답을 마칠 때마다 걸리는데 매번 block하면, 시킨 걸 이미 다 해도
    #   다음 턴에 또 막혀 같은 명령을 10번 넘게 반복하게 된다(실측). 세션 id로
    #   표시를 남겨 두 번째부터는 조용히 통과시킨다(1시간 지나면 한 번 더 알림).
    if already_prompted(payload.get("session_id")):
        return
    # ★재발행 요구는 뺐다(2026-08-18 사장님 B안). 이 훅은 답을 마칠 때마다 걸리는데
    # 그때마다 Artifact 재발행까지 시키니 세션 6~7개가 하루 수십 번을 올려
    # `deploy 429: frame_daily_push_cap_reached`(하루 발행 한도)에 걸렸다. 게다가
    # 다른 세션이 올릴 때마다 오는 '바뀌었다' 알림에 답하는 것 자체가 또 한 턴이 돼
    # 재발행→알림→재발행 쳇바퀴가 됐다. 기록(dashboard_cli add)은 HTML을 매번 다시
    # 만들어 두므로, 발행은 필요할 때 사람이 한 번만 하면 된다.
    cli_path = BASE / "dashboard_cli.py"
    tracks = active_tracks(payload.get("cwd", ""))
    if tracks:
        hint = "활성 트랙: " + ", ".join(tracks) + " 중 본인 것"
    else:
        hint = "본인 작업 트랙명(예: 꾸미기, 보이스, 장면라이브러리)"
    reason = (
        f"이 세션은 '{category}' 프로젝트 작업입니다. 종료 전에 다음을 하세요: "
        f'1) `py "{cli_path}" add --category "{category}" --track "<{hint}>" '
        f'--summary "<오늘 한 일 1~3줄>" --next "<다음 할 일>"` 실행. '
        f"(대시보드 재발행은 하지 마세요 — 사장님이 요청할 때만 합니다.)"
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    main()
