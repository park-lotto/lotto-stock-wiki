# 대본 줄 → 시간표·자막 조각
from .settings import *
def break_points(lines):
    """짧은 범퍼를 넣을 챕터. config 에 적었으면 그대로, 비었으면 본편 챕터의 1/3·2/3 지점"""
    if CFG.get("bumper_short_before"): return CFG["bumper_short_before"]
    ch = []
    for l in lines:
        c = l.get("chapter")
        if l["type"] == "line" and c and c not in ch and c not in CFG.get("no_capsule", []) and c != "마무리": ch.append(c)
    return [ch[len(ch) // 3], ch[2 * len(ch) // 3]] if len(ch) >= 3 else []

def make_schedule():
    lines = json.load(open(os.path.join(NARR, "lines.json"), encoding="utf-8"))
    skip = set(getattr(SH, "SKIP", [])); para = set(getattr(SH, "PARA", []))
    t, out, events, prev_ch = 0.0, [], [], None
    short_before = set(break_points(lines))
    for l in lines:
        if l["type"] == "bumper":
            events.append(dict(kind="bumper", t=t, dur=CFG["bumper_main_sec"])); t += CFG["bumper_main_sec"]; continue
        if l["type"] == "skip" or l["i"] in skip: continue
        just_bumped = bool(events) and events[-1]["kind"] == "bumper" and abs(events[-1]["t"] + events[-1]["dur"] - t) < 1e-6
        if prev_ch is not None and l["chapter"] != prev_ch and not just_bumped:
            if l["chapter"] in short_before:
                events.append(dict(kind="bumper_short", t=t, dur=CFG["bumper_short_sec"])); t += CFG["bumper_short_sec"]
            else:  # 종이 대각선 와이프(0.45초) + 휙
                events.append(dict(kind="wipe", t=t, dur=CFG["chapter_gap"])); t += CFG["chapter_gap"]
        if l["i"] in para and prev_ch == l["chapter"] and not just_bumped: t += CFG.get("para_gap", 0.5)
        prev_ch = l["chapter"]
        out.append(dict(i=l["i"], chapter=l["chapter"], text=l["text"], t0=round(t, 3), t1=round(t + l["dur"], 3)))
        t += l["dur"] + CFG["line_gap"]
    end_narr = t
    events.append(dict(kind="outro", t=end_narr + 0.4, dur=CFG["outro_sec"]))
    total = end_narr + 0.4 + CFG["outro_sec"]
    L = {x["i"]: x for x in out}
    # 샷 시간: 첫 문장 시작 ~ 다음 샷 첫 문장 시작(범퍼는 따로)
    shots = []
    for k, s in enumerate(SH.S):
        a = s["s"][0]
        while a not in L:
            a += 1
            if a > max(L): raise SystemExit(f"shots.py 샷 {s['s']}: 대본에 없는 문장 번호입니다(마지막 문장 {max(L)})")
        shots.append(dict(k=k, **s, t0=L[a]["t0"], chapter=L[a]["chapter"]))
    for j, s in enumerate(shots):
        nxt = shots[j + 1]["t0"] if j + 1 < len(shots) else end_narr + 0.4
        # 사이에 범퍼가 있으면 범퍼 시작에서 끊는다
        for e in events:
            if s["t0"] < e["t"] < nxt: nxt = min(nxt, e["t"])
        s["t1"] = round(nxt, 3)
    # 0초 시작 보정
    shots[0]["t0"] = 0.0
    # (r4) 같은 그림을 다른 구도로 다시 끊던 것은 '초점이 왔다갔다'로 보여서 없앴다 → 한 컷 안에서 천천히 이동
    # 자막 조각
    subs = []
    for x in out:
        for (a, b, txt) in cut_caption(x["text"], x["t0"], x["t1"]): subs.append(dict(t0=a, t1=b, text=txt))
    tl = dict(total=round(total, 3), end_narr=round(end_narr, 3), lines=out, shots=shots, events=events, subs=subs)
    json.dump(tl, open(os.path.join(BUILD, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"총 {total/60:.2f}분 · 샷 {len(shots)} · 자막 {len(subs)} · 범퍼 {sum(e['kind'].startswith('bumper') for e in events)}")
    durs = [s["t1"] - s["t0"] for s in shots]
    print(f"샷 길이 평균 {np.mean(durs):.2f}초 · 최소 {min(durs):.2f} · 최대 {max(durs):.2f}")
    return tl

NOBREAK_AFTER = {"이", "그", "저", "안", "못", "좀", "더", "잘", "다", "또", "제일", "딱", "꼭", "한", "두", "세", "그냥", "아주", "진짜", "엄청", "확"}
NOBREAK_BEFORE = {"게", "건", "거", "것", "거죠", "거예요", "수", "데", "줄", "때", "적", "뿐", "만큼", "중", "있다는", "없다는"}
GOOD_END = re.compile(r"(,|고|서|면|데|니까|는데|은데|지만|면서|어서|아서|해서|라서|다가|든|요\?|요|죠|다)$")
def cut_caption(text, t0, t1, mx=None):
    mx = mx or 24
    words = text.replace("'", "").split()
    L = len(" ".join(words))
    n = max(1, math.ceil(L / mx))
    if n == 1: return [(round(t0, 3), round(t1, 3), text.replace("'", "").rstrip(".,"))]
    # 경계 j(=words[:j] | words[j:])마다 벌점
    def pen(j):
        a, b = words[j - 1], words[j]
        p = 0.0
        if a in NOBREAK_AFTER: p += 40
        if b in NOBREAK_BEFORE or b.split(",")[0] in NOBREAK_BEFORE: p += 40
        if re.match(r"^\d", b) and re.search(r"\d,$", a): p += 60          # 1, 2위
        if GOOD_END.search(a): p -= 8
        if re.search(r"[.?!]$", a): p -= 30                                   # 문장 끝은 꼭 끊기
        if re.search(r"\d(억|만|조|천)?$", a) and re.match(r"^(유로|달러|원|명|표|퍼센트|%|년|월|개월|배)", b): p += 50  # 300억 / 유로
        if a.endswith(",") and len(a) <= 4 and len(b.rstrip(",")) <= 3: p += 35  # 짧은 나열(좌파, 중도, 극우)
        if re.search(r"(러|어|아|여)$", a) and re.match(r"^(가|오|주|보|있|놓|두|버리)", b): p += 25  # 놀러 가는, 보여 주고
        return p
    import functools
    lens = [len(w) for w in words]
    def seg_len(i, j): return sum(lens[i:j]) + (j - i - 1)
    target = L / n
    @functools.lru_cache(None)
    def best(i, k):  # words[i:]를 k조각으로
        if k == 1:
            sl = seg_len(i, len(words)); return ((sl - target) ** 2 * 0.05 + (1e6 if sl > (mx + 5 if re.search(r"[.?!]$", words[-1]) else mx + 2) else 0), (len(words),))
        res = (1e18, ())
        for j in range(i + 1, len(words) - k + 2):
            sl = seg_len(i, j)
            lim = mx + 5 if re.search(r"[.?!]$", words[j - 1]) else mx + 2
            if sl > lim: continue
            c = (sl - target) ** 2 * 0.05 + pen(j) + (30 if sl < 6 else 0)
            sub = best(j, k - 1)
            if not sub[1] or sub[1][-1] != len(words): continue
            if c + sub[0] < res[0]: res = (c + sub[0], (j,) + sub[1])
        return res
    cuts = best(0, n)[1]
    if not cuts or cuts[-1] != len(words): return cut_caption(text, t0, t1, mx + 4) if mx < 40 else [(round(t0, 3), round(t1, 3), text.replace("'", "").rstrip(".,"))]
    chunks, i = [], 0
    for j in cuts: chunks.append(" ".join(words[i:j])); i = j
    w8 = [max(1, len(re.findall(r"[가-힣0-9A-Za-z]", c))) for c in chunks]; tot = sum(w8)
    res, a = [], t0
    for c, ww in zip(chunks, w8):
        b = a + (t1 - t0) * ww / tot; res.append((round(a, 3), round(b, 3), c.rstrip(".,"))); a = b
    return res
def word_time(tl, i, needle):
    """문장 i 안에서 needle(숫자 등)을 말하는 대략의 순간(글자 위치 비례)"""
    x = next((l for l in tl["lines"] if l["i"] >= i), None)
    if x is None: return tl["end_narr"]
    txt = x["text"]; pos = txt.find(needle) if needle else -1
    if pos < 0:
        m = re.search(r"\d", txt); pos = m.start() if m else 0
    return x["t0"] + (x["t1"] - x["t0"]) * pos / max(1, len(txt))
def first_num(s):
    m = re.search(r"[\d][\d,.]*", s or ""); return m.group(0) if m else ""
def find_said(tl, s, needle):
    """샷의 문장들 가운데 needle(또는 정수 부분)을 말하는 순간. 없으면 None"""
    if not needle: return None
    cands = [needle]
    if "." in needle: cands.append(needle.split(".")[0])
    for nd in cands:
        for li in range(s["s"][0], s["s"][1] + 1):
            x = next((l for l in tl["lines"] if l["i"] == li), None)
            if x and nd in x["text"]: return word_time(tl, li, nd)
    return None
def reveal_time(tl, s):
    """블러 해제·딩 시점: 강조 항목 숫자를 말하는 순간"""
    if not s.get("reveal"): return None
    needle = ""
    if s["type"] == "bar" and s.get("hl", -1) >= 0: needle = first_num(s["items"][s["hl"]][2]).rstrip(".,")
    if s["type"] == "table" and s.get("hl_rows"): needle = first_num(" ".join(s["rows"][s["hl_rows"][0]]))
    if s.get("reveal_word"): return word_time(tl, s["reveal"], s["reveal_word"])
    t = find_said(tl, s, needle)
    return t if t is not None else word_time(tl, s["reveal"], needle)
def bubble_time(tl, s):
    if len(s["bubble"]) > 2: return word_time(tl, s["bubble"][0], s["bubble"][2])
    li, txt = s["bubble"][:2]; key = re.sub(r"[^가-힣A-Za-z0-9 ]", "", txt).strip()
    x = next((l for l in tl["lines"] if l["i"] >= li), None)
    for n in (6, 4):
        if x and key[:n] and key[:n] in x["text"]: return word_time(tl, li, key[:n])
    for wd in reversed([w for w in key.split() if len(w) >= 2]):
        if x and wd in x["text"]: return word_time(tl, li, wd)
    return line_time(tl, li)
def at_time(tl, a):
    """(문장, 단어) → 그 단어를 말하는 순간. 단어가 비면 문장 시작"""
    li, wd = a[0], (a[1] if len(a) > 1 else "")
    return word_time(tl, li, wd) if wd else line_time(tl, li)
def line_time(tl, i):
    for x in tl["lines"]:
        if x["i"] >= i: return x["t0"]
    return tl["end_narr"]

