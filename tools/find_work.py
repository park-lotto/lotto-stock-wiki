"""작업 기록 찾기 — 뭔가 시작하기 전에 "이거 전에 한 적 있나?"를 1초에 답한다.

## 왜 필요한가 (2026-08-09)

핸드오프가 **68개**인데 목록은 셋 다 썩어 있었다:
    NEXT_SESSION.md   15개만 등재, 7/25에 멈춤
    handoff/README.md 12개만 등재
    실제 파일          68개
→ 53개는 파일은 있는데 **찾을 방법이 없었다.**

실제 사고: 이 도구를 만든 세션조차 `handoff/히트작크롤.md`가 있는 줄 모르고
처음부터 조사를 다시 했다. `.tracks/키소진오탐`이 이미 있다는 것도 우연히 알았다.

**손으로 관리하는 목록은 반드시 썩는다**(이미 3번 썩었다). 그래서 이 도구는
목록을 만들지 않는다 — **매번 파일을 직접 읽어 검색**한다. 갱신이 필요 없다.

## 사용

    py tools/find_work.py 카테고리        # 카테고리 관련 기록 전부
    py tools/find_work.py 썸네일 만료      # 여러 낱말(모두 포함하는 것 우선)
    py tools/find_work.py --list          # 최근 갱신순 전체 목록

찾는 곳: handoff/*.md · wiki/log.d/*.md · CLAUDE.md · 메모리 인덱스
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 한국어 윈도우 콘솔은 기본 cp949라 '—' 하나에 UnicodeEncodeError로 죽는다(실측).
# 출력만 UTF-8로 바꾼다 — 못 바꾸는 환경이면 대체문자로 넘어가게 둔다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

BASE = Path(__file__).resolve().parent.parent
SEARCH_DIRS = [BASE / "handoff", BASE / "wiki" / "log.d"]
EXTRA_FILES = [BASE / "CLAUDE.md", BASE / "NEXT_SESSION.md"]

# 메모리는 프로젝트 밖에 있다(사용자별 경로). 있으면 같이 본다.
_MEM = Path(os.environ.get("CLAUDE_MEMORY_DIR", "")) if os.environ.get(
    "CLAUDE_MEMORY_DIR") else None


def _read(path):
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def collect_files():
    files = []
    for d in SEARCH_DIRS:
        if d.is_dir():
            files.extend(sorted(d.glob("*.md")))
    files.extend(f for f in EXTRA_FILES if f.is_file())
    if _MEM and _MEM.is_dir():
        files.extend(sorted(_MEM.glob("*.md")))
    return files


def _mtime(path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return datetime.fromtimestamp(0)


def search(terms):
    """모든 낱말을 포함하는 파일 우선, 그다음 일부 포함. 최근 갱신순."""
    lowered = [t.lower() for t in terms]
    hits = []
    for path in collect_files():
        text = _read(path)
        if not text:
            continue
        low = text.lower()
        matched = [t for t in lowered if t in low]
        if not matched:
            continue
        # 정렬 기준은 두 단계다(2026-08-09 테스트가 잡아낸 것):
        #   ① 낱말을 몇 개 포함하나 — "둘 다 다룬 문서"가 언제나 우선이다
        #   ② 같은 개수면 파일명에 있는 쪽 — 트랙 이름이 곧 주제인 경우가 많다
        # 파일명 가산을 ①에 더하면, 한 낱말만 맞는데 파일명이라는 이유로
        # 두 낱말 다 맞는 문서를 제친다(실측 실패).
        name_bonus = sum(1 for t in lowered if t in path.name.lower())
        hits.append((len(matched), name_bonus, _mtime(path), path, text, matched))
    hits.sort(key=lambda h: (-h[0], -h[1], -h[2].timestamp()))
    return hits


def _snippet(text, terms, width=95):
    """낱말이 처음 나오는 줄을 보여준다 — 제목보다 문맥이 도움이 된다."""
    for line in text.splitlines():
        low = line.lower()
        if any(t in low for t in terms) and len(line.strip()) > 12:
            s = line.strip().lstrip("#>-* ")
            return s[:width] + ("…" if len(s) > width else "")
    for line in text.splitlines():
        if line.strip():
            return line.strip().lstrip("#>-* ")[:width]
    return ""


def cmd_list():
    files = [f for f in collect_files() if f.parent.name == "handoff"]
    files.sort(key=lambda p: -_mtime(p).timestamp())
    print(f"핸드오프 {len(files)}개 (최근 갱신순)\n")
    for p in files:
        print(f"  {_mtime(p):%Y-%m-%d}  {p.stem}")
    print("\n특정 주제를 찾으려면: py tools/find_work.py <낱말>")


def main():
    ap = argparse.ArgumentParser(
        description="작업 기록 찾기 — 시작 전에 과거 기록부터 읽어라")
    ap.add_argument("terms", nargs="*", help="찾을 낱말(여러 개 가능)")
    ap.add_argument("--list", action="store_true", help="핸드오프 전체 목록")
    ap.add_argument("-n", type=int, default=8, help="최대 몇 건 (기본 8)")
    a = ap.parse_args()

    if a.list or not a.terms:
        cmd_list()
        return 0

    hits = search(a.terms)
    if not hits:
        print(f"'{' '.join(a.terms)}' 관련 기록 없음 — 새 작업이다.")
        print("작업 후 handoff/<트랙>.md 에 남겨라(다음 세션이 이 도구로 찾는다).")
        return 0

    print(f"'{' '.join(a.terms)}' 관련 기록 {len(hits)}건 — 위에서부터 읽어라\n")
    for _n, _bonus, mt, path, text, matched in hits[:a.n]:
        rel = path.relative_to(BASE) if BASE in path.parents else path.name
        age = (datetime.now() - mt).days
        stale = "  ⚠️오래됨" if age > 30 else ""
        print(f"  [{mt:%m-%d}] {rel}{stale}")
        print(f"      {_snippet(text, matched)}")
    if len(hits) > a.n:
        print(f"\n  … 외 {len(hits) - a.n}건")
    print("\n⚠️ 기록은 쓸 당시의 사실이다 — 코드·서버가 아직 그런지 확인하고 답하라.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
