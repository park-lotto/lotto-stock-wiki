"""관제 → 트랙 분배 (카드 046). 관제창(텔레그램)이 부르는 한 줄.

    py tools/dispatch.py <트랙> "<지시>" [--account 2] [--agent codex] [--model fable] [--card N]

exit 0 = 새 창 열림 · 3 = 그 트랙 창이 이미 작업 중(두 번째 창 금지 — 같은 대화를 두 창이 잡으면 꼬인다)
· 1 = 오류. 새 창은 새 대화로 열려 그 트랙 핸드오프를 먼저 읽고, 끝나면 tg_notify 로 보고한다.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import merge_gate
import pc_label
import track
import track_open

#: --continue 를 쓰지 않는다: Claude 는 대화 폴더 이름에서 한글을 전부 '-' 로 바꿔, 이름 길이가 같은
#: 트랙끼리 폴더를 공유한다(2026-09-30 실측: 트랙 33개 → 대화 폴더 6개). 이어받기가 **남의 트랙 대화**를
#: 잡을 수 있다. 대신 매번 새 대화로 열고 그 트랙 핸드오프를 먼저 읽게 한다.
HANDOFF_RULE = "(먼저 handoff/{track}.md 가 있으면 읽고 이어서 하라.)\n\n"
REPORT_RULE = ("\n\n(관제 분배 작업이다. 끝나면 결과를 한 단락으로 "
               "`py tools/tg_notify.py \"<결과>\"` 로 보고하라. 막히면 막힌 이유를 같은 방법으로 보고하라.)")


def _link_card(number, track_name):
    subprocess.run([sys.executable, str(Path(__file__).with_name("control.py")),
                    "link", str(number), track_name], check=False)


def main(argv=None):
    merge_gate.make_output_safe()
    ap = argparse.ArgumentParser(description="관제 → 트랙 분배")
    ap.add_argument("track")
    ap.add_argument("order")
    ap.add_argument("--account", default="1")
    ap.add_argument("--agent", default="claude", choices=["claude", "codex"])
    ap.add_argument("--model", default="")
    ap.add_argument("--card", type=int)
    a = ap.parse_args(argv)

    wt = track.worktree_path(a.track)
    if not wt.exists():
        print(f"없는 트랙: {a.track} — 만들려면 카드 등록 뒤 py tools/track.py start {a.track} --card <번호>")
        return 1
    busy = track_open.session_alive(wt)
    if busy:
        print(f"작업 중: {busy['name']} — 앱에서 이어 지시하거나 끝난 뒤 다시 분배")
        return 3
    if a.card:
        _link_card(a.card, a.track)
    L = track_open.build_launch(wt, account=a.account, agent=a.agent, model=a.model,
                                prompt=HANDOFF_RULE.format(track=a.track) + a.order + REPORT_RULE,
                                resume=False, pc=pc_label.label(),
                                tag=a.track, card=a.card)
    pid = track_open.launch_window(L)
    print(f"열림: {L['name']} (pid {pid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
