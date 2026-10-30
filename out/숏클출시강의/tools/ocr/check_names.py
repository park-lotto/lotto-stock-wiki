"""완성 조각에 채널 이름이 읽히는 채로 남았나 — 1초 간격 OCR 전수(sweep.py 결과 json)에서 채널 이름 꼴만 골라 찍는다.
쓰기: py check_names.py <sweep.json> [...]   → 남은 곳이 있으면 rc=1
흐린 글자는 OCR 점수가 낮거나 엉뚱하게 읽힌다 — 점수 0.6 이상으로 또렷이 읽힌 것만 '남음'으로 본다.
"""
import json, re, sys

NAME = re.compile(r"(템리포|템리폿|홈샷|lily ?lily|앤샷템|얜샷템|shortem|에이아이온|AI:ON|마음한컷|Heart_shot|썰반장|돌곰이집|프롬렌즈|제이팝시선)", re.I)
bad = 0
for f in sys.argv[1:]:
    for t, txt, sc, box in json.load(open(f, encoding="utf-8")):
        if sc >= 0.6 and NAME.search(txt) and "출처" not in txt:
            print(f"{f} {t:6.1f}s  {txt}  {box[0]}")
            bad += 1
print("남은 채널 이름", bad)
sys.exit(1 if bad else 0)
