# -*- coding: utf-8 -*-
"""소재 후보 판정(Jev) — 지침/소재.md 조건를 점수로 재서 종합 점수순 표를 낸다.
    python -X utf8 jev_screen.py <후보폴더|파일...> [--channel "이름"]
후보 = 소재 하나당 txt 한 파일. 60점 이상 통과, 40~59 보류(사람 판단), 그 아래 탈락.
"""
import glob
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys
os.environ.setdefault("TYPESAFE_API_KEY", keys.get("typesafe"))

from typesafe_sdk import Noul, Score, TypeSafeClient

N_LEVELS = 4
WEIGHTS = {  # 합 1.0
    "myth": 0.25, "chapters": 0.20, "sources": 0.20, "relevance": 0.20, "fresh": 0.15,
}
CONF_MIN = 0.35   # 이보다 낮은 항목이 있으면 점수가 높아도 사람 판단으로 넘긴다(Jev 확신도)
# 단계 문구가 판정의 전부다(Jev 는 각 단계를 설명만 보고 따로 판단). 지시문은 영어, candidate 만 한국어(공식: 영어가 주력).
QUESTIONS = {
    "fresh": Score(instructions="How recently was `candidate` reported, relative to `today`?",
                   criteria=["No date is given, or the latest reported date is more than 3 months before `today`",
                             "The latest reported date is 1 to 3 months before `today`",
                             "The latest reported date is 8 to 30 days before `today`",
                             "The latest reported date is within 7 days of `today`"]),
    "myth": Score(instructions="Does `candidate` give a reason to overturn what people commonly believe?",
                  criteria=["No concrete number appears",
                            "Numbers appear but only describe the situation",
                            "A number is surprising, but no specific common belief is challenged",
                            "A specific common belief or official claim is contradicted by a specific number"]),
    "chapters": Score(instructions="How many distinct causes does `candidate` state for what happened?",
                      criteria=["No cause is stated", "One cause is stated", "Two distinct causes are stated",
                                "Three or more distinct causes are stated"]),
    "sources": Score(instructions="How many separate named sources does `candidate` cite?",
                     criteria=["No source is named", "One source is named", "Two sources are named",
                               "Three or more official statistics, institutions or news outlets are named"]),
    "relevance": Score(instructions="How directly does `candidate` touch the daily life of Korean viewers of `channel`?",
                       criteria=["No link to Korea at all",
                                 "A foreign story with only a distant link to Korea",
                                 "Affects Korean industries or the Korean economy in general",
                                 "Directly affects Korean households' money, jobs, housing or prices"]),
    "defame": Noul(instructions="Can `candidate` only be told by accusing a named individual?",
                   criteria={"true": "The story depends on claiming that a specific named person committed wrongdoing",
                             "false": "The story is about institutions, markets, policies or statistics; companies and officials appear only as facts"}),
}


def judge(client, name, text, channel, today):
    r = client.system_one(state={"candidate": text, "channel": channel, "today": today}, questions=QUESTIONS)
    parts = {k: r.scores[k].score / (N_LEVELS - 1) for k in WEIGHTS}
    conf = min(r.scores[k].confidence for k in WEIGHTS)
    total = round(sum(parts[k] * w for k, w in WEIGHTS.items()) * 100)
    defame = r.nouls["defame"].noul
    verdict = "보류" if defame >= 0.5 or (total >= 40 and conf < CONF_MIN) else "통과" if total >= 60 else "보류" if total >= 40 else "탈락"
    return dict(name=name, total=total, verdict=verdict, defame=round(defame, 2), conf=round(conf, 2), **{k: round(v, 2) for k, v in parts.items()})


def main():
    args = sys.argv[1:]
    channel = "시사·경제 해설 롱폼"
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
        print(f"| {x['name']} | {x['total']} | {x['verdict']} | {x['myth']} | {x['chapters']} | {x['sources']} | {x['relevance']} | {x['fresh']} | {x['defame']} | {x['conf']} |")


if __name__ == "__main__":
    main()
