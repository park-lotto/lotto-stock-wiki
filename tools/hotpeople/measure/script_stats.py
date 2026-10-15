# -*- coding: utf-8 -*-
"""대본 언어(W)·후킹 구조(K) 통계 — subs.json(read_subs.py) + cuts.json(cuts.py)에서.
표본 폴더에서: PYTHONUTF8=1 py ../measure/script_stats.py → subs_flat.json + 콘솔.
잰 것: 글자수·어절·종결어미 분포·숫자/따옴표/쉼표/마침표/물음표 비율·형광펜·빨강 위치·
       글자수↔노출초 회귀·글자/초·첫 자막 유형 재료·이름 공개 위치·전환("하지만") 위치·단어 빈도.
"""
import json, re, statistics as st, collections as C

subs = json.load(open("subs.json", encoding="utf-8"))
cuts = json.load(open("cuts.json", encoding="utf-8"))
allS, per = [], {}
for vid, d in subs.items():
    ss = [s for s in d["subs"] if s.get("text")]
    c = cuts[vid + ".mp4"]
    ts = [0] + c["sub_times"]; ends = c["sub_times"] + [c["dur"]]
    for i, s in enumerate(ss):
        s["vid"], s["i"], s["N"] = vid, i + 1, len(ss)
        s["dur"] = (ends[i] - ts[i]) if i < len(ts) else None
        t = s["text"].replace(" / ", " ")
        s["chars"] = len(re.sub(r"\s", "", t)); s["words"] = len(t.split())
        s["num"] = bool(re.search(r"\d", t)); s["quote"] = bool(re.search(r'["“”\'‘’]', t))
        s["comma"] = "," in t; s["period"] = t.rstrip().endswith("."); s["ellip"] = "…" in t or "..." in t
        s["q"] = "?" in t; s["excl"] = "!" in t
        last = re.sub(r'[\s"“”\'‘’.…?!,]+$', "", t)
        s["end"] = ("습니다/니다" if re.search(r"(습니다|니다)$", last)
                    else "음/임/함/됨/짐(명사형)" if re.search(r"(음|임|함|됨|짐|됐음|였음|았음|었음)$", last)
                    else "다(평서)" if last.endswith("다")
                    else "까지/에서(이어짐)" if re.search(r"(까지|에서|는데|지만|으로|로)$", last) else "명사/기타")
        allS.append(s)
    per[vid] = ss
n = len(allS)
print("자막 총", n, "편", len(per))
srt = sorted(s["chars"] for s in allS)
print("글자수(공백제외) 중앙", st.median(srt), "p10", srt[n // 10], "p90", srt[n * 9 // 10], "최대", srt[-1])
print("어절 중앙", st.median([s["words"] for s in allS]), "최대", max(s["words"] for s in allS))
print("종결어미 분포:", dict(C.Counter(s["end"] for s in allS).most_common()))
for k, l in [("num", "숫자 포함"), ("quote", "따옴표 인용"), ("comma", "쉼표"), ("period", "마침표로 끝"),
             ("ellip", "말줄임"), ("q", "물음표"), ("excl", "느낌표"), ("mark", "형광펜")]:
    c = sum(1 for s in allS if s.get(k)); print(f"{l}: {c}/{n} = {100 * c / n:.0f}%")
print("빨간 단어 자막:", sum(1 for s in allS if s.get("red")), "/", n, "편당", [sum(1 for s in per[v] if s.get("red")) for v in per])
xs = [s["chars"] for s in allS if s["dur"]]; ys = [s["dur"] for s in allS if s["dur"]]
mx, my = st.mean(xs), st.mean(ys)
b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs); a = my - b * mx
r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** .5
ys_s = sorted(ys)
print(f"노출초 = {a:.2f} + {b:.3f}×글자수, r={r:.2f}, N={len(xs)}; 노출 중앙 {st.median(ys):.2f} p10 {ys_s[len(ys) // 10]:.2f} p90 {ys_s[len(ys) * 9 // 10]:.2f}")
print("글자/초 중앙", round(st.median([s["chars"] / s["dur"] for s in allS if s["dur"]]), 2))
print("\n첫 자막 글자수 중앙", st.median([per[v][0]["chars"] for v in per]),
      "| 첫 자막 숫자", sum(1 for v in per if per[v][0]["num"]), "| 첫 자막 따옴표", sum(1 for v in per if per[v][0]["quote"]), f"/ {len(per)}")
for v in per:
    ss = per[v]
    piv = [s["i"] for s in ss if "하지만" in s["text"] or "그러나" in s["text"]]
    names = [(s["i"], m.group(0)) for s in ss for m in [re.search(r'["“\'‘][가-힣A-Za-z ]{2,10}["”\'’]', s["text"])] if m]
    print(f"\n[{v}] N={len(ss)} 따옴표어구 {names[:3]} 전환 {piv} 형광펜 {[s['i'] for s in ss if s.get('mark')]} "
          f"빨강 {[s['i'] for s in ss if s.get('red')]} 숫자 {[s['i'] for s in ss if s['num']]}")
    for s in ss[:3] + ss[-2:]:
        print(f"   #{s['i']:>2} {s['text']}")
tok, first = C.Counter(), C.Counter()
for s in allS:
    ws = re.findall(r"[가-힣]{2,}", s["text"]); tok.update(ws)
    if s["i"] <= 3: first.update(ws)
print("\n단어 상위 40:", tok.most_common(40)); print("첫3자막 단어 상위 15:", first.most_common(15))
json.dump(allS, open("subs_flat.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
