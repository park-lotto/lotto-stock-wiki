# -*- coding: utf-8 -*-
"""나레이션형 쇼츠 대본 구조 자 — 스피치매틱스 asr/*.json + yt-dlp info 폴더에서.
사용: PYTHONUTF8=1 py script_structure.py <asr 폴더> [info 폴더]
잰 것: ①전환 표지(하지만·사실·바로·심지어…)가 편 길이의 몇 %에 오는가 ②말 속도·쉼(단어 사이 0.25초↑) ③제목 낱말별 조회 중앙(info 폴더를 주면).
★표지는 받아쓰기 낱말 그대로 센다 — 받아쓰기가 틀린 낱말은 빠진다(문장 전문은 화면 자막으로 따로 확인할 것).
"""
import json, glob, os, sys, re, statistics as st

MARK = ["하지만", "그러나", "그런데", "사실", "바로", "문제는", "심지어", "무엇보다", "하물며", "특히", "그럼에도", "아니", "아", "이제부터", "진짜", "결과", "이후", "막상", "요즘은", "그러다"]
asr = sys.argv[1]
per = {}
for f in sorted(glob.glob(os.path.join(asr, "*.json"))):
    r = json.load(open(f, encoding="utf-8"))
    w = [(x["alternatives"][0]["content"], x["start_time"], x["end_time"]) for x in r["results"] if x["type"] == "word"]
    if len(w) < 20:
        continue
    end = w[-1][2]; vid = os.path.basename(f)[:11]
    gaps = [b[1] - a[2] for a, b in zip(w, w[1:])]
    chars = sum(len(c) for c, _, _ in w)
    hits = [(c, round(s, 1), round(s / end * 100)) for c, s, _ in w if c in MARK]
    per[vid] = hits
    print(f"{vid} 끝 {end:.1f}s 낱말 {len(w)} 글자 {chars} 글자/초 {chars / end:.1f} 쉼0.25↑ {sum(1 for g in gaps if g >= .25)} 최장쉼 {max(gaps):.2f} | " + " ".join(f"{c}@{p}%" for c, _, p in hits))
print("\n표지별 위치(편 길이 %) — 편수 / 중앙 / 범위")
for m in MARK:
    ps = [p for h in per.values() for c, _, p in h if c == m]
    vs = sum(1 for h in per.values() if any(c == m for c, _, _ in h))
    if ps:
        print(f"  {m}: {vs}/{len(per)}편 · {len(ps)}회 · 중앙 {st.median(ps):.0f}% ({min(ps)}~{max(ps)})")
if len(sys.argv) > 2:
    rows = []
    for f in glob.glob(os.path.join(sys.argv[2], "*.info.json")):
        j = json.load(open(f, encoding="utf-8"))
        rows.append((j["upload_date"], j["view_count"] or 0, j["duration"], j["title"]))
    rows.sort()
    cut = sys.argv[3] if len(sys.argv) > 3 else "00000000"
    cur = [r for r in rows if r[0] >= cut]
    print(f"\n제목 낱말 — {cut} 이후 {len(cur)}편, 전체 조회 중앙 {st.median([r[1] for r in cur]):.0f}")
    for k in ["근황", "이유", "정체", "비밀", "계의", "버린", "1등", "한국", "일본", "ㄷㄷ", "사람들", "필수", "미친", "충격", "천재", "?"]:
        a = [r[1] for r in cur if k in r[3]]
        if a:
            print(f"  '{k}': {len(a)}편 · 조회 중앙 {st.median(a):.0f} · 100만↑ {sum(1 for x in a if x >= 1e6)}")
    for lab, lo, hi in [("06-12~07-15", "20250612", "20250715"), ("07-30~08-02", "20250730", "20250802"), ("08-12~09-18", "20250812", "20250918"), ("09-19~10-31", "20250919", "20251031")]:
        a = [r for r in rows if lo <= r[0] <= hi]
        if a:
            print(f"  시기 {lab}: {len(a)}편 · 조회 중앙 {st.median([r[1] for r in a]):.0f} · 길이 중앙 {st.median([r[2] for r in a])}s · 제목 글자 중앙 {st.median([len(r[3]) for r in a])} · 100만↑ {sum(1 for r in a if r[1] >= 1e6)} · 해시태그 있는 편 {sum(1 for r in a if '#' in r[3])}")
