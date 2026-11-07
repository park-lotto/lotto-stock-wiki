# 연출 점검: 같은 모션이 얼마나 가깝게 다시 나오는지, 전환이 얼마나 긴지 잰다.
# 사용: 작업 폴더에서 python -X utf8 <경로>/motion_audit.py  → 어기면 종료코드 1
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio.settings import BUILD, CFG
from studio.direction import direct, STAGES
tl = direct(json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8")))
seq = {}
def add(kind, t, v): seq.setdefault(kind, []).append((t, v))
for s in tl["shots"]:
    add("컷", s["t0"], s["cut"])
    for a, st, mv, c in s.get("beats", []):
        add("무대", s["t0"] + a, st); add("무대+카메라", s["t0"] + a, st + "/" + mv)
        if c: add("컷", s["t0"] + a, c)
    if s["type"] == "bignum": add("숫자", s["t0"], s["look"])
    if s["type"] == "bar":
        add("그래프", s["t0"], s["look"])
        for a, lk, c in s.get("swaps", []): add("그래프", s["t0"] + a, lk); add("컷", s["t0"] + a, c)
    if s["type"] == "labels": add("항목", s["t0"], s["look"])
    if s["type"] == "vs":
        add("VS", s["t0"], s["look"])
        for a, lk, c in s.get("swaps", []): add("VS", s["t0"] + a, lk); add("컷", s["t0"] + a, c)
    if s["type"] == "typo":
        for m in s["modes"]: add("문장", s["t0"], m)
bad = 0
for k, v in seq.items():
    names = [x[1] for x in v]; c = collections.Counter(names); same = sum(a == b for a, b in zip(names, names[1:]))
    last, gaps = {}, []
    for i, n in enumerate(names):
        if n in last: gaps.append(i - last[n])
        last[n] = i
    need = min(len(c) - 1, 3); low = min(gaps) if gaps else 0; ok = same == 0 and (not gaps or low >= need); bad += not ok
    print(f"{'통과' if ok else '실패'} {k}: {len(names)}회 {len(c)}종 · 연속 {same} · 재등장 최소 간격 {low} · 최다 {c.most_common(1)[0]}")
holds = []
for s in tl["shots"]:
    b = sorted([x[0] for x in s.get("beats", [])] + [x[0] for x in s.get("swaps", [])]) or [0]; b = b if b[0] == 0 else [0] + b; e = b[1:] + [s["t1"] - s["t0"]]; holds += [q - p for p, q in zip(b, e)]
print(f"한 화면 최장 {max(holds):.1f}초 · 전환: 범퍼 {CFG['bumper_main_sec']}초/{CFG['bumper_short_sec']}초 · 챕터 {CFG['chapter_gap']}초")
sys.exit(1 if bad else 0)
