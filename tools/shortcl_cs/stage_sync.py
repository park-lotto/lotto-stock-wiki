# -*- coding: utf-8 -*-
"""숏클 게시 무대 맞추기 — 엔진 트랙 파일과 무대(설치본 폴더)를 대조하고, sync 면 다른 파일을 무대로 복사한다.

  py -X utf8 tools/shortcl_cs/stage_sync.py            # 대조만(엔진·앱·회원 지침)
  py -X utf8 tools/shortcl_cs/stage_sync.py sync       # 복사

엔진 트랙 폴더(.tracks/칼카피숏템엔진)에서 실행한다.
★server/index.js 는 복사하지 않는다 — 무대 index.js = 트랙 index.js 에서 보류 코드(quitWhenClaudeCloses 블록·호출)를 뺀 것(11-03 진단 틀림, 게시 보류).
   index.js 가 다르면 'index.js(손으로)' 로 알려 준다 → strip_index 를 부른다.
★트랙에 다른 창이 아직 커밋하지 않은 파일이 있으면 그 파일까지 무대로 간다 — sync 전에 git status 로 남의 미커밋 파일을 먼저 본다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

STAGE = os.environ.get("SHORTCL_STAGE", "C:/t/build134/win-x64/Shortem")
PAIRS = [("", "engine"), ("shortem_client/server/", "server")]
GUIDE = ("installer/common/MEMBER_GUIDE.md", ["server/guide/MEMBER_GUIDE.md", "claude-plugin/shortem/guide/MEMBER_GUIDE.md"])
HOLD = "// Claude 창이 닫히면(입력 끝)"


def norm(p: str) -> bytes:
    return open(p, "rb").read().replace(b"\r\n", b"\n")


def strip_index(src: str = "shortem_client/server/index.js", dst: str | None = None) -> None:
    """트랙 index.js 에서 보류 블록·호출을 뺀 것을 무대에 쓴다."""
    dst = dst or os.path.join(STAGE, "server", "index.js")
    s = open(src, encoding="utf-8").read()
    if HOLD in s:
        a = s.index(HOLD)
        b = s.index("  return bye;\n}\n", a) + len("  return bye;\n}\n")
        s = s[:a] + s[b:]
        s = s.replace("  quitWhenClaudeCloses();\n", "")
    assert "quitWhenClaudeCloses" not in s
    open(dst, "w", encoding="utf-8", newline="").write(s)


def main() -> None:
    sync = len(sys.argv) > 1 and sys.argv[1] == "sync"
    tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True, encoding="utf-8").stdout.split("\n"))
    diff, same = [], 0
    eng = os.path.join(STAGE, "engine")
    for root, _, fs in os.walk(eng):
        for f in fs:
            sp = os.path.join(root, f)
            rel = os.path.relpath(sp, eng).replace(os.sep, "/")
            if rel in tracked:
                if norm(sp) == norm(rel):
                    same += 1
                else:
                    diff.append((rel, sp))
    srv = "shortem_client/server/"
    for rel in [t for t in tracked if t.startswith(srv)]:
        sp = os.path.join(STAGE, "server", rel[len(srv):])
        if rel.endswith("/index.js") and rel == srv + "index.js":
            continue
        if not os.path.exists(sp) or norm(sp) != norm(rel):
            diff.append((rel, sp))
    for g in GUIDE[1]:
        sp = os.path.join(STAGE, g)
        if not os.path.exists(sp) or norm(sp) != norm(GUIDE[0]):
            diff.append((GUIDE[0], sp))
    print("엔진 같음", same, "다름", len(diff))
    for rel, sp in diff:
        print(" ", rel, "→", sp)
    print("index.js(손으로): strip_index 로 맞춘다 — 보류 블록 빼고")
    if sync:
        for rel, sp in diff:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            shutil.copyfile(rel, sp)
        strip_index()
        print("복사", len(diff), "+ index.js")


if __name__ == "__main__":
    main()
