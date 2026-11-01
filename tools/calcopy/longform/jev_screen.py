# -*- coding: utf-8 -*-
"""소재 후보 판정(Jev) — 소재발굴가이드.md 5절 점검표를 점수로 재서 종합 점수순 표를 낸다.
    C:\\Users\\CH\\jev-lab\\.venv\\Scripts\\python.exe tools/calcopy/longform/jev_screen.py <후보폴더|파일...> [--channel "이름"]
후보 = 소재 하나당 txt 한 파일. 60점 이상 통과, 40~59 보류(사람 판단), 그 아래 탈락.
원본 프리셋의 jev-screen.ps1 은 받지 못해 가이드의 조건으로 다시 만든 것이다(질문 문구는 원본과 다를 수 있다).
"""
import glob
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for line in Path(r"C:\Users\CH\jev-lab\.env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from typesafe_sdk import Noul, Score, TypeSafeClient

LEVELS = ["Clearly no", "Weakly", "Somewhat", "Clearly yes"]
WEIGHTS = {  # 가이드 5절 항목. 합 1.0
    "myth": 0.25, "chapters": 0.20, "sources": 0.20, "relevance": 0.20, "fresh": 0.15,
}
QUESTIONS = {
    "fresh": Score(instructions="`candidate` is a story reported within the past week of the given `today`",
                   criteria=LEVELS),
    "myth": Score(instructions="`candidate` has a common belief about the cause, and a concrete number that overturns it",
                  criteria=LEVELS),
    "chapters": Score(instructions="The cause in `candidate` can be split into three or more separate explanatory chapters",
                      criteria=LEVELS),
    "sources": Score(instructions="`candidate` names three or more official statistics, institutions or news sources",
                     criteria=LEVELS),
    "relevance": Score(instructions="Korean viewers of `channel` would feel `candidate` matters to their own life",
                       criteria=LEVELS),
    "defame": Noul(instructions="`candidate` can only be told by accusing a named individual rather than explaining systems"),
}


def judge(client, name, text, channel, today):
    r = client.system_one(state={"candidate": text, "channel": channel, "today": today}, questions=QUESTIONS)
    parts = {k: r.scores[k].score / (len(LEVELS) - 1) for k in WEIGHTS}
    total = round(sum(parts[k] * w for k, w in WEIGHTS.items()) * 100)
    defame = r.nouls["defame"].noul
    verdict = "통과" if total >= 60 and defame < 0.5 else "보류" if total >= 40 else "탈락"
    return dict(name=name, total=total, verdict=verdict, defame=round(defame, 2), **{k: round(v, 2) for k, v in parts.items()})


def main():
    args = sys.argv[1:]
    channel = "지식한입 롱폼(시사·경제 해설)"
    if "--channel" in args:
        i = args.index("--channel"); channel = args[i + 1]; del args[i:i + 2]
    files = []
    for a in args:
        files += sorted(glob.glob(os.path.join(a, "*.txt"))) if os.path.isdir(a) else [a]
    if not files:
        sys.exit("후보 파일이 없습니다")
    today = __import__("datetime").date.today().isoformat()
    with TypeSafeClient(model="jev-latest") as client:
        rows = [judge(client, Path(f).stem, Path(f).read_text(encoding="utf-8"), channel, today) for f in files]
    rows.sort(key=lambda x: -x["total"])
    print("| 소재 | 종합 | 판정 | 뒤집기 | 챕터 | 출처 | 공감 | 이번주 | 명예훼손 |\n|---|---|---|---|---|---|---|---|---|")
    for x in rows:
        print(f"| {x['name']} | {x['total']} | {x['verdict']} | {x['myth']} | {x['chapters']} | {x['sources']} | {x['relevance']} | {x['fresh']} | {x['defame']} |")


if __name__ == "__main__":
    main()
