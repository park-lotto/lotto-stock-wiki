#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""썰쇼핑 입구 — 맥·윈도우 같은 명령 하나.

  python preset.py status                                   도구·글꼴·열쇠 점검(열쇠 값은 안 보임) — JSON
  python preset.py tts     <프로젝트> [--reuse]              내레이션 + 자막 시각 (타입캐스트 · Speechmatics)
  python preset.py media   yt|img|clip|pick <프로젝트> ...   소재 받기 (tools/media.py 와 같은 인자)
  python preset.py scenes  <프로젝트>                        소재 고르기 scenes.json (후보 영상마다 작은 사본을 agy 가 한 번 봄 · 고르기는 코드)
  python preset.py aiimg   <프로젝트> <이름> "<장면 설명>" [참고그림]   실사풍 재연 그림 (agy 구독)
  python preset.py review  <프로젝트>                        굽기 전 판정 review.json (작은 미리보기를 agy 가 한 번 봄 · 판정은 코드)
  python preset.py render  <프로젝트> [--still 초]           out.mp4 + render_receipt.json (review 통과여야 굽는다)
  python preset.py check   <프로젝트>                        sseol_check.json (규격·길이·굽기 전 판정·영수증)
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(ROOT, "tools")
CMDS = {"tts": "tts.py", "media": "media.py", "scenes": "scenes.py", "aiimg": "aiimg.py", "review": "review.py", "render": "render.py", "check": "check.py", "status": "check.py"}

for _s in (sys.stdout, sys.stderr):        # 윈도우 콘솔(cp949)에 없는 글자를 찍다 죽지 않게
    if _s is not None and hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    sys.path.insert(0, TOOLS)
    sys.argv = [os.path.join(TOOLS, CMDS[cmd])] + (["--status"] if cmd == "status" else []) + sys.argv[2:]
    runpy.run_path(sys.argv[0], run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
