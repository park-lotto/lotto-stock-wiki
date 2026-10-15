# -*- coding: utf-8 -*-
"""대본 전문(scripts_*.json — 화면 자막을 옮긴 것) 문체 자. 사용: PYTHONUTF8=1 py script_text_stats.py <scripts.json>
잰 것: 편별 문장 수·구절 수·글자 수, 구절 글자수 분포, 문장 끝 꼴, 전해 듣는 말투(~다는·~라는데·~다고) 수,
       숫자·ㅋㅋ/ㄷㄷ, 2인칭·1인칭, 박자(tag) 순서."""
import json, re, sys, statistics as st, collections as co

d = json.load(open(sys.argv[1], encoding="utf-8"))["videos"]
END = [("~다고 함", r"다고 함(ㅋㅋ|ㄷㄷ)?$"), ("~다고/라고/냐고(전언으로 끝)", r"(다고|라고|냐고)\s?(ㅋㅋ|ㄷㄷ)?$"),
       ("~는데(다음 문장으로 넘김)", r"(는데|은데|인데|건데)(ㄷㄷ)?$"), ("~는 거", r"(는|던) 거(ㄷㄷ|\.\.\?)?$"),
       ("~음/됨(음슴체)", r"(음|됨|임)$")]
endc = co.Counter(); ph_all = []; hear = 0; sent = 0
for v in d:
    L = v["lines"]; body = [t for g, t in L if g != "T"]
    ph = [p for t in body for p in t.split("/")]
    chars = sum(len(re.sub(r"\s", "", p)) for p in ph)
    ph_all += [len(p) for p in ph]
    txt = " ".join(t.replace("/", " ") for t in body)
    h = len(re.findall(r"다는|라는|다고|라고|냐는|다며|라며", txt)); hear += h; sent += len(body)
    for g, t in L:
        if g in ("T", "C"):
            continue
        s = t.replace("/", " ")
        for name, pat in END:
            if re.search(pat, s):
                endc[name] += 1; break
        else:
            endc["그 밖(명사·이어짐): …" + s[-5:]] += 1
    print(f"{v['id']} {v['ch']} {v['views']:>10,} [{v['type']}] 문장 {len(body)} 구절 {len(ph)} 글자 {chars} 전언 {h} "
          f"숫자 {len(re.findall(r'[0-9]+', txt))} ㅋㅋ {txt.count('ㅋㅋ')} ㄷㄷ {txt.count('ㄷㄷ')} "
          f"2인칭 {len(re.findall(r'여러분|당신|님들', txt))} 1인칭 {len(re.findall(r'나는|내가|저는|제가|우리 ', txt))} "
          f"제목 {len(L[0][1])}자 | {''.join(g for g, _ in L)}")
s = sorted(ph_all)
print(f"\n구절 글자수(공백 포함) 중앙 {st.median(ph_all)} p10 {s[len(s) // 10]} p90 {s[len(s) * 9 // 10]} 최대 {max(ph_all)} n={len(ph_all)}")
print(f"문장 {sent}개 / 전해 듣는 말투 표지 {hear}회")
print("문장 끝 꼴(제목·댓글 한 줄 제외):")
for k, n in endc.most_common():
    print(f"  {k}: {n}")
