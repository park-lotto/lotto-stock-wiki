"""수리 전 '같은 꼴 이력' 찾기 — 두더지 막기(사장님 11-05 "고친 걸 또 고치는 두더지 금지").

뿌리(Jev 원인 0.91·증명 0.86): 수리 전 Jev 질문을 사건 하나로만 짜서 '같은 꼴을 전에 몇 번 고쳤나'·'꼴 전체를 막는 장치' 후보가
안 들어갔다 → Jev 는 매번 '이 사건의 뿌리'로 통과시켰고 같은 꼴이 하루 4번씩 다시 났다(설정 칸↔렌더 4·진행 신호 2·3번 연속 4·맥 렌더 2).

쓰는 법(수리 착수 전, 매번):
  py -X utf8 tools/shortcl_cs/fix_history.py <증상 낱말> [<낱말> ...] [--days 14]
  예) fix_history.py 진행 신호 180초       fix_history.py 렌더에 안 닿 설정 칸
→ 엔진 트랙 커밋 제목·숏클 상태 파일 결함 표에서 낱말이 든 것을 센다.
  2건 이상이면: Jev facts 에 이 목록을 넣고, fixes 후보에 '꼴 전체를 막는 장치(전수 대조 시험·판단 한 곳으로 모으기)'를 반드시 넣는다.
  장치가 best 가 아닐 때만 사건 수리.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CS = HERE.parents[2]                                   # .tracks/숏클cs팀
ENGINE = CS.parent / "칼카피숏템엔진"
STATE = CS / "handoff" / "숏클cs팀_보고서_상태.json"


def commits(words: list[str], days: int) -> list[str]:
    if not ENGINE.is_dir():
        return []
    r = subprocess.run(["git", "-C", str(ENGINE), "log", f"--since={days} days ago", "--format=%h %ad %s", "--date=short"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [ln for ln in r.stdout.splitlines() if any(w in ln for w in words)]


def cases(words: list[str]) -> list[str]:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for c in d.get("cases") or []:
        s = json.dumps(c, ensure_ascii=False)
        if any(w in s for w in words):
            out.append(f"{c.get('member')} · {c.get('symptom')} · {c.get('root')} · {c.get('commit') or c.get('fix')}")
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("words", nargs="+")
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    cm, cs = commits(a.words, a.days), cases(a.words)
    print(f"[같은 꼴 이력] 낱말 {a.words} · 최근 {a.days}일 커밋 {len(cm)}건 · 결함 표 {len(cs)}건")
    for x in cm[:30]:
        print("  커밋", x[:160])
    for x in cs[:30]:
        print("  결함", x[:160])
    n = max(len(cm), len(cs))
    if n >= 2:
        print("★ 2건 이상 = 두더지 위험: Jev facts 에 위 목록을, fixes 에 '꼴 전체를 막는 장치' 후보를 반드시 넣어라")
    else:
        print("처음 보는 꼴 — 사건 수리 + 같은 꼴이 다른 곳에 있나 grep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
