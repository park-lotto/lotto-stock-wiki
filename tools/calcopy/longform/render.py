# 숏클 지식롱폼 렌더러 (PIL 프레임 → ffmpeg)
# 사용: python -I render.py timeline        # 타임라인·자막·오디오 만들기
#       python -I render.py video [시작초 끝초]  # 영상 렌더(부분 렌더 가능)
#       python -I render.py mux               # 영상+오디오 합치기
import os, sys, re, json, math, wave, subprocess, importlib.util, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)                     # 공용 재료(글꼴·효과음·배경음)
WORK = os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd())   # 편마다 다른 것(대본·샷·녹음·그림·결과)
E = lambda *a: os.path.join(WORK, *a)
CFG = json.load(open(P("config.json"), encoding="utf-8"))
if os.path.exists(E("config.json")) and E("config.json") != P("config.json"):
    CFG.update(json.load(open(E("config.json"), encoding="utf-8")))
W, H = CFG["width"], CFG["height"]; FPS = CFG["fps_num"] / CFG["fps_den"]
C = {k: tuple(v) for k, v in CFG["colors"].items()}
spec = importlib.util.spec_from_file_location("shots", E("shots.py")); SH = importlib.util.module_from_spec(spec); spec.loader.exec_module(SH)
for _s in SH.S:  # 기사 캡처가 있으면 글자 카드 대신 실제 기사 화면, 없으면 알린다(글자 나열은 12건 잡도리 3번)
    if _s.get("article"):
        if os.path.exists(E("assets", "article", _s["article"] + ".png")) and os.path.exists(E("assets", "article", _s["article"] + ".json")):
            _s["type"] = "article"; _s.pop("src", None)
        else: print(f"[경고] 기사 캡처 없음 {_s['article']} — 글자 카드로 대신함", flush=True)
NARR = E("narr"); BUILD = E("build"); os.makedirs(BUILD, exist_ok=True)

# ───────────────────────── 글꼴 ─────────────────────────
_fc = {}
def F(name, size):
    k = (name, size)
    if k not in _fc:
        path = {"B": "Pretendard-Bold.otf", "XB": "Pretendard-ExtraBold.otf", "K": "Pretendard-Black.otf", "M": "Pretendard-Medium.otf",
                "R": "Pretendard-Regular.otf", "SB": "Pretendard-SemiBold.otf", "SERIF": "HANBatangB.ttf",
                "HAN": "BlackHanSans-Regular.ttf", "PEN": "NanumPenScript-Regular.ttf", "GM": CFG.get("font_main", "GmarketSansBold.otf")}[name]
        _fc[k] = ImageFont.truetype(P("fonts", path), size)
    return _fc[k]


def tw(d, s, f): b = d.textbbox((0, 0), s, font=f); return b[2] - b[0]
def ease(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

# ───────────────────────── 타임라인 ─────────────────────────
def short_bumper_chapters(lines):
    """짧은 범퍼를 넣을 챕터. config 에 적었으면 그대로, 비었으면 본편 챕터의 1/3·2/3 지점"""
    if CFG.get("bumper_short_before"): return CFG["bumper_short_before"]
    ch = []
    for l in lines:
        c = l.get("chapter")
        if l["type"] == "line" and c and c not in ch and c not in CFG.get("no_capsule", []) and c != "마무리": ch.append(c)
    return [ch[len(ch) // 3], ch[2 * len(ch) // 3]] if len(ch) >= 3 else []

def build_timeline():
    lines = json.load(open(os.path.join(NARR, "lines.json"), encoding="utf-8"))
    skip = set(getattr(SH, "SKIP", [])); para = set(getattr(SH, "PARA", []))
    t, out, events, prev_ch = 0.0, [], [], None
    short_before = set(short_bumper_chapters(lines))
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
        for (a, b, txt) in split_sub(x["text"], x["t0"], x["t1"]): subs.append(dict(t0=a, t1=b, text=txt))
    tl = dict(total=round(total, 3), end_narr=round(end_narr, 3), lines=out, shots=shots, events=events, subs=subs)
    json.dump(tl, open(os.path.join(BUILD, "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"총 {total/60:.2f}분 · 샷 {len(shots)} · 자막 {len(subs)} · 범퍼 {sum(e['kind'].startswith('bumper') for e in events)}")
    durs = [s["t1"] - s["t0"] for s in shots]
    print(f"샷 길이 평균 {np.mean(durs):.2f}초 · 최소 {min(durs):.2f} · 최대 {max(durs):.2f}")
    return tl

NOBREAK_AFTER = {"이", "그", "저", "안", "못", "좀", "더", "잘", "다", "또", "제일", "딱", "꼭", "한", "두", "세", "그냥", "아주", "진짜", "엄청", "확"}
NOBREAK_BEFORE = {"게", "건", "거", "것", "거죠", "거예요", "수", "데", "줄", "때", "적", "뿐", "만큼", "중", "있다는", "없다는"}
GOOD_END = re.compile(r"(,|고|서|면|데|니까|는데|은데|지만|면서|어서|아서|해서|라서|다가|든|요\?|요|죠|다)$")
def split_sub(text, t0, t1, mx=None):
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
    if not cuts or cuts[-1] != len(words): return split_sub(text, t0, t1, mx + 4) if mx < 40 else [(round(t0, 3), round(t1, 3), text.replace("'", "").rstrip(".,"))]
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

# ───────────────────────── 오디오 ─────────────────────────
SR = 48000
def read_wav(path):
    tmp = path
    if not path.lower().endswith(".wav") or True:
        tmp = os.path.join(BUILD, "_tmp_" + re.sub(r"[^A-Za-z0-9_.]", "_", os.path.basename(path)) + ".wav")
        if not os.path.exists(tmp) or os.path.getmtime(tmp) < os.path.getmtime(path):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", tmp], check=True)
    with wave.open(tmp) as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a
def db(x): return 10 ** (x / 20)
def place(buf, a, t, gain=1.0):
    s = int(t * SR); e = min(len(buf), s + len(a))
    if e > s: buf[s:e] += a[:e - s] * gain

SFX = {"whoosh": "media/sfx/whoosh.mp3", "pop": "media/sfx/pop.mp3", "type": "media/sfx/typing.mp3",
       "thud": "media/sfx/thud.mp3", "ding": "media/sfx/ding.mp3"}
def build_audio(tl):
    SFX.update(CFG.get("sfx") or {})
    n = int((tl["total"] + 0.5) * SR); narr = np.zeros(n, np.float32); fx = np.zeros(n, np.float32); mus = np.zeros(n, np.float32)
    for x in tl["lines"]:
        place(narr, read_wav(os.path.join(NARR, "trim", f"{x['i']:03d}.wav")), x["t0"])
    sfx = {k: read_wav(P(v)) for k, v in SFX.items() if os.path.exists(P(v))}
    if "whoosh" in sfx:  # 모아서 터지는 소리 → 가장 큰 지점 앞 0.45초 ~ 뒤 0.25초만
        a = sfx["whoosh"]; env = np.convolve(np.abs(a), np.ones(960) / 960, "same"); pk = int(np.argmax(env))
        sfx["whoosh"] = a[max(0, pk - int(0.45 * SR)): pk + int(0.25 * SR)].copy()
        sfx["whoosh"] /= max(1e-6, np.abs(sfx["whoosh"]).max()) / 0.8
    def cut(a, sec): m = int(sec * SR); a = a[:m].copy(); f = min(len(a), int(0.05 * SR)); a[-f:] *= np.linspace(1, 0, f); return a
    for s in tl["shots"]:
        ty = s["type"]
        if ty in ("bar", "table", "vs", "cycle", "rating", "ladder", "pct") and "whoosh" in sfx: place(fx, sfx["whoosh"], max(0, s["t0"] - 0.45), db(-18))
        if ty == "quote" and "type" in sfx: place(fx, cut(sfx["type"], 1.0), s["t0"] + 0.1, db(-17))
        if ty == "bignum" and "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.6), s["t0"], db(-14))
        if ty == "bignum" and "pop" in sfx: place(fx, sfx["pop"], bignum_end(tl, s), db(-10))
        if "bubble" in s and "pop" in sfx and not s.get("variant"): place(fx, sfx["pop"], bubble_time(tl, s) + 0.05, db(-7))
        if "stamp" in s and "thud" in sfx: place(fx, cut(sfx["thud"], 0.8), word_time(tl, s["stamp"][0], s["stamp"][1]), db(-6))
        if "reveal" in s and "ding" in sfx: place(fx, cut(sfx["ding"], 0.8), reveal_time(tl, s), db(-18))
        if ty == "labels" and "pop" in sfx:
            for j, it in enumerate(s["items"]): place(fx, sfx["pop"], label_time(tl, it, j), db(-8))
        if ty == "table" and s.get("row_at") and "pop" in sfx:
            for a in s["row_at"]: place(fx, sfx["pop"], max(s["t0"], at_time(tl, a)), db(-12))
    for s in tl["shots"]:
        if s["type"] == "typo":
            for c in typo_cards(s, tl):
                if c["enter"] == "stamp" and "thud" in sfx: place(fx, cut(sfx["thud"], 0.35), c["t"], db(-15))
                elif "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.3), max(0, c["t"] - 0.08), db(-17))
        if s["type"] == "article":
            if "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.45), max(0, s["t0"] - 0.1), db(-18))
            for ct in circle_times(s, tl):
                if "pop" in sfx: place(fx, sfx["pop"], s["t0"] + ct, db(-11))
    for e in tl["events"]:
        if e["kind"] == "wipe" and "whoosh" in sfx: place(fx, cut(sfx["whoosh"][int(0.25 * SR):], 0.35), max(0, e["t"] - 0.05), db(-17))
    # 음악: 본편 BGM(챕터 바뀌면 곡 교체) + 징글 + 아웃트로
    main = read_wav(P(CFG["bgm_main"])); alt = read_wav(P(CFG["bgm_alt"])); jg = read_wav(P(CFG["jingle"]))
    alt_t = next((x["t0"] for x in tl["lines"] if x["chapter"] == CFG["bgm_alt_from_chapter"]), None)
    def loop_fill(a, t0, t1, g):
        pos = t0
        while t1 - pos > 0.05:
            seg = a[: int(min(len(a), (t1 - pos) * SR))].copy()
            fl = min(len(seg) // 2, int(1.0 * SR))
            if fl > 0: seg[:fl] *= np.linspace(0, 1, fl); seg[-fl:] *= np.linspace(1, 0, fl)
            place(mus, seg, pos, g)
            step = len(seg) / SR - 1.0
            if step <= 0.5: break
            pos += step
    outro = next(e for e in tl["events"] if e["kind"] == "outro")
    segs, cur = [], 0.0
    for e in tl["events"]:
        if e["kind"].startswith("bumper"): segs.append((cur, e["t"])); cur = e["t"] + e["dur"]
    segs.append((cur, outro["t"]))
    from scipy.signal import butter, sosfilt
    hp = butter(4, CFG.get("bgm_highpass", 150), "highpass", fs=SR, output="sos")
    def prep(a):  # 저음 깎고 곡마다 음량(RMS) 맞추기
        a = sosfilt(hp, a).astype(np.float32); r = np.sqrt(np.mean(a[: SR * 90] ** 2)) + 1e-9
        return a * (db(-20) / r)
    rot = [prep(read_wav(P(x))) for x in CFG.get("bgm_rotation", [CFG["bgm_main"]])]
    for j, (a, b) in enumerate(segs):
        loop_fill(rot[j % len(rot)], a, b, db(CFG["bgm_db"]))
    for e in tl["events"]:
        if e["kind"].startswith("bumper"):
            j = jg[int(CFG["jingle_start"] * SR): int((CFG["jingle_start"] + e["dur"] + 0.3) * SR)].copy()
            f = int(0.3 * SR); j[-f:] *= np.linspace(1, 0, f); place(mus, j, e["t"], db(CFG["jingle_db"]))
            if "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.5), e["t"], db(-12))
            if "thud" in sfx: place(fx, cut(sfx["thud"], 0.5), e["t"] + (0.35 if e["kind"] == "bumper_short" else 0.6), db(-9))
    o = jg[int(CFG["outro_music_start"] * SR): int((CFG["outro_music_start"] + outro["dur"]) * SR)].copy()
    f = int(2.0 * SR); o[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR)); o[-f:] *= np.linspace(1, 0, f)
    place(mus, o, outro["t"], db(CFG["jingle_db"]))
    mix = narr * db(0) + fx + mus
    mix = np.clip(mix, -1, 1)
    out = os.path.join(BUILD, "mix_raw.wav")
    with wave.open(out, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    # 나레이션 압축 느낌 + 목표 음량
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-af",
                    f"acompressor=threshold=-20dB:ratio=3:attack=5:release=80,loudnorm=I={CFG['target_lufs']}:TP=-1.5:LRA=4",
                    "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", os.path.join(BUILD, "mix.wav")], check=True)
    print("오디오:", os.path.join(BUILD, "mix.wav"))

# ───────────────────────── 그림 재료 ─────────────────────────
random.seed(7)
def paper_bg():
    p = os.path.join(BUILD, "_paper.png")
    if os.path.exists(p): return Image.open(p).convert("RGB")
    rng = np.random.default_rng(3)
    base = np.ones((H, W, 3), np.float32) * np.array(C["paper"], np.float32)
    n = rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32)
    n = np.array(Image.fromarray(((n - n.min()) / (n.max() - n.min()) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32) / 255
    fine = rng.normal(0, 1, (H, W)).astype(np.float32) * 2.2
    img = base + ((n - 0.5) * 14)[..., None] + fine[..., None]
    # 구김 선
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA")
    for _ in range(26):
        x0, y0 = rng.integers(0, W), rng.integers(0, H); x1, y1 = x0 + rng.integers(-700, 700), y0 + rng.integers(-400, 400)
        d.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, 40), width=2); d.line([(x0 + 2, y0 + 2), (x1 + 2, y1 + 2)], fill=(0, 0, 0, 14), width=2)
    im = im.filter(ImageFilter.GaussianBlur(0.6)); im.save(p); return im

_vig = None
def vignette():
    global _vig
    if _vig is None:
        y, x = np.mgrid[0:H, 0:W]; r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        a = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 0.62
        _vig = Image.fromarray((a * 255).astype(np.uint8))
    return _vig
def photo_grade(im, dark=0.0):
    im = ImageEnhance.Color(im).enhance(0.85); im = ImageEnhance.Contrast(im).enhance(1.08)
    if dark: im = ImageEnhance.Brightness(im).enhance(1 - dark)
    black = Image.new("RGB", (W, H), (0, 0, 0)); return Image.composite(black, im, vignette())

_img = {}
def load_base(k):
    if k in _img: return _img[k]
    p = None
    for c in (E("assets", "stock", f"s{k:03d}.jpg"), E("assets", "img", f"s{k:03d}.png"), E("assets", "img", f"s{k:03d}.jpg")):
        if os.path.exists(c): p = c; break
    if p is None:
        print(f"[경고] 문장 {k} 샷 그림 없음 — 종이 배경으로 대신함", flush=True)
        im = paper_bg()
    else:
        im = Image.open(p).convert("RGB"); r = max(W / im.width, H / im.height) * 1.0
        im = im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)
        l, t = (im.width - W) // 2, (im.height - H) // 2; im = im.crop((l, t, l + W, t + H))
    _img[k] = im; return im
def stock_video_frame(k, t):
    p = E("assets", "stock", f"s{k:03d}.mp4")
    return None if not os.path.exists(p) else p

class ClipReader:
    """실사 영상(assets/stock/sNNN.mp4)을 샷 길이만큼 순서대로 읽는다(렌더는 앞에서부터 진행)."""
    cur = None
    def __init__(self, path, dur):
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={CFG['fps_num']}/{CFG['fps_den']},setpts=PTS*{1.0}"
        self.p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-i", path, "-t", f"{dur + 0.5:.3f}", "-vf", vf,
                                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.path, self.n, self.last = path, 0, None
    def frame(self, idx):
        while self.n <= idx:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3: break
            self.last = Image.frombytes("RGB", (W, H), b); self.n += 1
        return self.last
    def close(self):
        try: self.p.kill()
        except Exception: pass
def clip_frame(s, lt, T):
    path = E("assets", "stock", f"s{s.get('clip', s['s'][0]):03d}.mp4")
    if not os.path.exists(path): return None
    key = (path, s["t0"])
    if ClipReader.cur is None or ClipReader.cur[0] != key:
        if ClipReader.cur: ClipReader.cur[1].close()
        ClipReader.cur = (key, ClipReader(path, T))
    return ClipReader.cur[1].frame(int(lt * FPS))

def kenburns(im, p, z0=1.0, z1=1.07, k=None):
    p = max(0.0, min(1.0, p)); q = p * p * (3 - 2 * p) * 0.5 + p * 0.5
    if k is not None and k % 2: z0, z1 = z1, z0          # 홀수 샷은 줌아웃
    z = z0 + (z1 - z0) * q; w, h = W / z, H / z
    dirs = [(1, 0), (-1, 0), (0, 1), (1, 1), (-1, -1), (0, -1)]; dx, dy = dirs[(k or 0) % len(dirs)] if k is not None else (0, 0)
    l = (W - w) / 2 + dx * (W - w) / 2 * (q * 2 - 1); t = (H - h) / 2 + dy * (H - h) / 2 * (q * 2 - 1)
    return im.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)

# ───────────────────────── 상시 UI ─────────────────────────
def draw_symbol(size):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = size
    d.rectangle([s * .06, s * .06, s * .94, s * .94], fill=C["sub_bar"])
    d.polygon([(s * .38, s * .28), (s * .38, s * .72), (s * .74, s * .5)], fill=(255, 255, 255, 255))
    return im

_ui = {}
def ui_layer_b(chapter, bright):
    """채널 패와 챕터 태그. logo_side 로 좌우를 바꾼다(캡슐·구분선 없음)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); ac = C["sub_bar"]; right = CFG.get("logo_side", "right") == "right"
    f = F("GM", 34); n = CFG["channel_name"]; nw = tw(d, n, f); x0 = W - 48 - nw - 44 if right else 48
    d.rectangle([x0, 36, x0 + nw + 44, 96], fill=ac); d.text((x0 + 22, 46), n, font=f, fill=(255, 255, 255, 255))
    if chapter and chapter not in CFG.get("no_capsule", []):
        tag = chapter.split(" : ")[-1]; fc = F("GM", 28); cw = tw(d, tag, fc); xc = 48 if right else W - 48 - cw - 44
        d.rectangle([xc, 36, xc + cw + 44, 90], fill=(20, 24, 28, 225)); d.rectangle([xc, 84, xc + cw + 44, 90], fill=ac)
        d.text((xc + 22, 47), tag, font=fc, fill=(255, 255, 255, 255))
    return im

def ui_layer(chapter, bright):
    k = (chapter, bright)
    if k not in _ui: _ui[k] = ui_layer_b(chapter, bright)
    return _ui[k]

NUMTOK = re.compile(r"\d[\d,.]*(?:%|만|천|억|조|원|달러|배|명|개월|개|년|월|분기)*(?: \d천)?(?: ?(?:원|달러|명))?")
def draw_sub_b(frame, text, p):
    """결 b: 아래 띠 + 흰 글자 + 숫자만 노란색. 글자는 0.12초 동안 살짝 올라온다."""
    d = ImageDraw.Draw(frame, "RGBA"); f = F("GM", 44); w = tw(d, text, f)
    d.rectangle([0, H - 100, W, H], fill=C["sub_box"]); d.rectangle([0, H - 106, W, H - 100], fill=C["sub_bar"])
    x = (W - w) // 2; y = H - 76 + int((1 - ease(p / 0.12)) * 16); i = 0
    for m in list(NUMTOK.finditer(text)) + [None]:
        a = text[i: m.start() if m else len(text)]
        if a: d.text((x, y), a, font=f, fill=(255, 255, 255, 255)); x += d.textlength(a, font=f)
        if m: d.text((x, y), m[0], font=f, fill=C["yellow"] + (255,)); x += d.textlength(m[0], font=f); i = m.end()

_src = {}
def src_layer(src, bright):
    k = (src, bright)
    if k in _src: return _src[k]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if src:
        d = ImageDraw.Draw(im); f = F("SB", 26); s = src if src == "AI 생성" else f"출처 : {src}"
        w = tw(d, s, f); col = (51, 51, 51, 255) if bright else (229, 229, 229, 255)
        x_, y_ = 48, H - 148   # 자막 띠 위 왼쪽
        d.text((x_, y_), s, font=f, fill=col, stroke_width=0 if bright else 2, stroke_fill=(0, 0, 0, 200))
    _src[k] = im; return im

# ───────────────────────── 오버레이 조각 ─────────────────────────
def bubble(img, text, cx, cy, p):
    if p <= 0: return
    f = F("GM", 40); d = ImageDraw.Draw(img); w = tw(d, text, f); x = 64 - (1 - ease(p / 0.2)) * (w + 140); y = H - 262
    d.rectangle([x, y, x + w + 58, y + 78], fill=(255, 255, 255, 245)); d.rectangle([x, y, x + 12, y + 78], fill=C["sub_bar"])
    d.text((x + 34, y + 19), text, font=f, fill=(17, 24, 28, 255))

def stamp(img, text, cx, cy, p):
    if p <= 0: return
    f = F("GM", 54); d = ImageDraw.Draw(img); w = tw(d, text, f); x = W - 64 - w - 56 + (1 - ease(p / 0.16)) * (w + 120); y = 128
    d.rectangle([x, y, x + w + 56, y + 92], fill=C["wine"] + (245,)); d.text((x + 28, y + 19), text, font=f, fill=(255, 255, 255, 255))

MARK = re.compile(r"\[\[(.+?)\]\]|~~(.+?)~~")
def parse_mark(text):
    """[[강조박스]] · ~~취소선~~ → [(조각, 종류)]  종류: '' / 'box' / 'strike'"""
    out, i = [], 0
    for m in MARK.finditer(text):
        if m.start() > i: out.append((text[i:m.start()], ""))
        out.append((m[1], "box") if m[1] is not None else (m[2], "strike")); i = m.end()
    if i < len(text): out.append((text[i:], ""))
    return out
BOXC = [(200, 255, 0), (255, 30, 138), (255, 214, 0), (30, 108, 235)]
def big_label(img, text, p):
    if p <= 0: return
    a = int(255 * ease(p / 0.2)); sc = 1.0 + 0.18 * (1 - ease(p / 0.22)); f = F("K", int(80 * sc)); d = ImageDraw.Draw(img)
    segs = parse_mark(text); ws = [tw(d, t, f) for t, _ in segs]; w = sum(ws)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    y = H // 2 - 60; x = (W - w) // 2
    dl.rounded_rectangle([x - 50, H // 2 - 84, x + w + 50, H // 2 + 56], radius=20, fill=(0, 0, 0, int(a * 0.66)))
    nb = 0
    for (t, k), ww in zip(segs, ws):
        if k == "box":
            g = ease((p - 0.25) / 0.2); c = BOXC[nb % len(BOXC)]; nb += 1
            if g > 0: dl.rectangle([x - 10, H // 2 - 74, x - 10 + (ww + 20) * g, H // 2 + 46], fill=c + (a,))
            dl.text((x, y), t, font=f, fill=((17, 17, 17, a) if g > 0.5 else (255, 225, 53, a)))
        elif k == "strike":
            dl.text((x, y), t, font=f, fill=(210, 210, 210, a), stroke_width=4, stroke_fill=(0, 0, 0, a))
            g = ease((p - 0.15) / 0.2)
            if g > 0: dl.line([(x - 6, H // 2 - 8), (x - 6 + (ww + 12) * g, H // 2 - 8)], fill=(255, 40, 40, a), width=10)
        else:
            dl.text((x, y), t, font=f, fill=(255, 225, 53, a), stroke_width=5, stroke_fill=(0, 0, 0, a))
        x += ww
    img.alpha_composite(lay)

def rich_lines(d, text, hl, f, maxw):
    """줄바꿈(\n) 기준 + 강조 구간 표시: [(줄, [(조각, 강조여부)])]"""
    out = []
    for ln in text.split("\n"):
        parts, rest = [], ln
        while rest:
            pos = [(rest.find(h), h) for h in hl if h and rest.find(h) >= 0]
            if not pos: parts.append((rest, False)); break
            i, h = min(pos)
            if i > 0: parts.append((rest[:i], False))
            parts.append((h, True)); rest = rest[i + len(h):]
        out.append(parts)
    return out

# ───────────────────────── 샷 그리기 ─────────────────────────
BRIGHT = {"bar", "table", "vs", "cycle", "rating", "ladder", "pct"}
def is_bright(s): return s["type"] in BRIGHT or (s["type"] == "quote" and s.get("style") == "paper")
def is_ai_bg(s):
    n = s.get("img", s["s"][0])
    return os.path.exists(E("assets", "img", f"s{n:03d}.png")) and not os.path.exists(E("assets", "stock", f"s{n:03d}.mp4")) and not os.path.exists(E("assets", "stock", f"s{n:03d}.jpg"))
def shot_src(s):
    if s["type"] == "article":
        m = load_article(s["article"])[1]; return s.get("src") or f'{m.get("media", "")} {m.get("date", "").replace("-", ".")}'
    if "src" in s:
        return s["src"] + (", AI 생성" if (is_ai_bg(s) and s["type"] in ("quote", "bignum", "labels", "ai", "stock")) else "")
    if s["type"] == "ai": return "AI 생성"
    if is_ai_bg(s) and s["type"] in ("stock", "labels", "bignum", "quote"): return "AI 생성"
    return ""

def pan_b(im, p, k):
    """결 b: 확대 없이 일정 배율로 한 방향으로 흐른다(샷 번호로 방향이 돈다)."""
    z = 1.13; w, h = W / z, H / z; mx, my = W - w, H - h; q = max(0.0, min(1.0, p))
    l, t = [(mx * q, my / 2), (mx * (1 - q), my / 2), (mx / 2, my * q), (mx / 2, my * (1 - q))][k % 4]
    return im.transform((W, H), Image.EXTENT, (l, t, l + w, t + h), Image.BILINEAR)

def photo_frame(s, lt, T, dark=0.0):
    im = clip_frame(s, lt, T)
    if im is None:
        if s.get("variant"):
            base = load_base(s.get("img", s["s"][0])); z = 1.16 - 0.06 * max(0.0, min(1.0, lt / max(T, 0.1)))
            w, h = int(W / z), int(H / z); l, tp = int((W - w) * 0.8), int((H - h) * 0.3)
            im = base.crop((l, tp, l + w, tp + h)).resize((W, H), Image.BILINEAR)
        elif CFG.get("photo_motion", "pan") == "pan":
            im = pan_b(load_base(s.get("img", s["s"][0])), lt / max(T, 0.1), s["s"][0])
        else:
            im = kenburns(load_base(s.get("img", s["s"][0])), lt / max(T, 0.1), 1.04, 1.16, s.get("k", 0))
    return photo_grade(im, dark).convert("RGBA")

MARKER = [(255, 214, 0), (120, 205, 255), (255, 140, 190)]
def draw_quote(s, lt, T, tl):
    st = s.get("style", "dark")
    if st == "dark": img = photo_frame(s, lt, T, dark=0.62)
    elif st == "paper":
        img = photo_frame(s, lt, T, dark=0.0); ov = Image.new("RGBA", (W, H), C["paper"] + (205,)); img.alpha_composite(ov)
    else: img = photo_frame(s, lt, T, dark=0.35)
    f = F("SERIF", 50); d = ImageDraw.Draw(img)
    lines = rich_lines(d, s["text"], s.get("hl", []), f, W - 400)
    lh = 86; tot_h = lh * len(lines); maxw = max(sum(tw(d, p, F("K", 58) if h else f) + (12 if h else 0) for p, h in ln) for ln in lines)
    y = (H - tot_h) // 2 - 20; x0 = (W - maxw) // 2
    if st == "beige":
        d.rectangle([x0 - 60, y - 50, x0 + maxw + 60, y + tot_h + 40], fill=C["beige"] + (245,), outline=C["beige_border"], width=3)
        d.rectangle([x0 - 52, y - 42, x0 + maxw + 52, y + tot_h + 32], outline=C["beige_border"] + (140,), width=1)
    base_c = (255, 255, 255, 255) if st == "dark" else (34, 34, 34, 255)
    hl_c = C["yellow"] + (255,) if st == "dark" else C["wine"] + (255,)
    td = max(1.5, min(7.0, T * 0.8)); total_chars = sum(len(p) for ln in lines for p, _ in ln); shown = int(total_chars * min(1.0, lt / td))
    cnt = 0
    for ln in lines:
        x = x0
        for p, h in ln:
            vis = p[: max(0, min(len(p), shown - cnt))]; cnt += len(p)
            fi = f if not h else F("K", 58)
            if vis:
                if h:
                    hi = s.get("hl", []).index(p) if p in s.get("hl", []) else 0; mc = MARKER[hi % len(MARKER)]
                    vw = tw(d, vis, fi); d.rectangle([x - 6, y - 4, x + vw + 6, y + 66], fill=mc + (255,))
                    d.text((x, y - 4), vis, font=fi, fill=(17, 17, 17, 255))
                else:
                    d.text((x, y), vis, font=fi, fill=base_c)
            x += tw(d, p, fi) + (12 if h else 0)
        y += lh
    return img

def bignum_end(tl, s):
    return (word_time(tl, s.get("count_line", s["s"][0]), s["count_word"]) + 0.2) if s.get("count_word") else s["t0"] + 1.3
def draw_bignum(s, lt, T, tl):
    img = photo_frame(s, lt, T, dark=0.5); d = ImageDraw.Draw(img)
    end_t = bignum_end(tl, s) - s["t0"]
    st_t = max(0.15, end_t - 3.0)
    pr = ease((lt - st_t) / max(0.3, end_t - st_t)); v = s["v0"] + (s["v1"] - s["v0"]) * pr
    if s["fmt"] == "joeok":
        iv = int(round(v)); txt = (f"{iv // 10000}조 {iv % 10000:,}억 유로" if iv >= 10000 else f"{iv:,}억 유로")
    else:
        txt = s["fmt"].format(v)
    if pr >= 1 and s.get("fmt_final"): txt = s["fmt_final"]
    bump = max(0.0, 1 - (lt - end_t) / 0.28) if lt >= end_t else 0.0
    f = F("GM", int(150 * (1 + 0.16 * bump))); w = tw(d, txt, f); tb = d.textbbox((0, 0), txt, font=f)
    nx = lambda w_: 132
    d.rectangle([92, H // 2 - 190, 104, H // 2 + 130], fill=C["sub_bar"])
    cy_ = H // 2 - 35; sh = int(10 * bump * math.sin(lt * 90))
    d.text((nx(w) + sh, cy_ - (tb[1] + tb[3]) / 2), txt, font=f, fill=(255, 255, 255, 255) if bump < 0.5 else C["yellow"] + (255,), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    fl = F("B", 46); w2 = tw(d, s["label"], fl); d.text((nx(w2), H // 2 - 190), s["label"], font=fl, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    sub_t = (at_time(tl, s["sub_word"]) - s["t0"]) if s.get("sub_word") else end_t + 0.5
    if s.get("sub") and lt > sub_t:
        fs = F("XB", 54); w3 = tw(d, s["sub"], fs); d.text((nx(w3), H // 2 + 70), s["sub"], font=fs, fill=C["yellow"] + (255,), stroke_width=4, stroke_fill=(0, 0, 0, 255))
    return img

def chart_header(d, title, sub):
    f = F("XB", 60); w = tw(d, title, f); d.text(((W - w) // 2, 150), title, font=f, fill=(34, 34, 34, 255))
    if sub: fs = F("M", 30); w2 = tw(d, sub, fs); d.text(((W - w2) // 2, 228), sub, font=fs, fill=(102, 102, 102, 255))

def draw_bar(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img); chart_header(d, s["title"], s.get("sub"))
    items = s["items"]; n = len(items); hl = s.get("hl", -1); orient = s.get("orient", "v")
    vals = [v for _, v, _ in items] + ([s["ref"][0]] if s.get("ref") else [])
    vmin = min(0, min(vals)) * 1.12; vmax = max(0, max(vals)) * 1.12
    if vmax <= 0: vmax = abs(vmin) * 1.6
    rev_t = (reveal_time(tl, s) - s["t0"] - 0.3) if s.get("reveal") else 0
    g = ease((lt - 0.15) / 0.7)
    # 막대마다: 그 숫자를 말하는 순간 차오름(못 찾으면 0.4초 간격)
    starts = []
    for j, (lab, v, disp) in enumerate(items):
        ft = find_said(tl, s, first_num(disp).rstrip(".,"))
        if ft is None: ft = find_said(tl, s, lab.split()[0])
        if ft is not None: starts.append(max(0.1, ft - s["t0"] - 0.25))
        else: starts.append((starts[-1] + 0.6) if starts else 0.15)
    G = [ease((lt - st) / 0.55) for st in starts]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    if orient == "v":
        x_area0, x_area1, y_base, y_top = 360, W - 360, 800, 330
        if vmin < 0: y_base, y_top = 560, 300
        slot = (x_area1 - x_area0) / n; bw = min(220, slot * 0.55)
        for j, (lab, v, disp) in enumerate(items):
            g = G[j]; cx = x_area0 + slot * (j + 0.5); hpx = (y_base - y_top) * (abs(v) / (vmax - vmin)) * g
            col = C["blue"] if j == hl else C["gray"]
            if v >= 0: dl.rectangle([cx - bw / 2, y_base - hpx, cx + bw / 2, y_base], fill=col + (255,))
            else: dl.rectangle([cx - bw / 2, y_base, cx + bw / 2, y_base + hpx], fill=C["red"] + (255,))
            fl = F("B", 34); w = tw(dl, lab, fl); dl.text((cx - w / 2, (y_base + 14) if v >= 0 else (y_base - 52)), lab, font=fl, fill=(68, 68, 68, 255))
            if g > 0.6:
                fv = F("K", 54 if j == hl else 44); w = tw(dl, disp, fv); ty = (y_base - hpx - 70) if v > 0 else ((y_base - 120) if v == 0 else (y_base + hpx + 12))
                vl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dv = ImageDraw.Draw(vl)
                dv.text((cx - w / 2, ty), disp, font=fv, fill=((C["blue"] if j == hl else (108, 117, 125)) if v >= 0 else C["red"]) + (255,))
                if s.get("reveal") and j == hl and lt < rev_t: vl = vl.filter(ImageFilter.GaussianBlur(14))
                lay.alpha_composite(vl)
        dl.line([(x_area0 - 20, y_base), (x_area1 + 20, y_base)], fill=(150, 150, 150, 255), width=2)
        if s.get("ref") and (not s.get("ref_at") or lt >= line_time(tl, s["ref_at"]) - s["t0"]):
            rv, rl = s["ref"]; ry = y_base - (y_base - y_top) * (rv / (vmax - vmin))
            for xx in range(int(x_area0 - 20), int(x_area1 + 20), 28): d.line([(xx, ry), (xx + 16, ry)], fill=C["red"] + (150,), width=3)
            dl.text((x_area1 + 30, ry - 20), rl, font=F("B", 30), fill=C["red"] + (255,))
    else:
        x0, x1, y0 = 560, W - 300, 340; slot = min(150, 520 / n); bh = slot * 0.62
        for j, (lab, v, disp) in enumerate(items):
            g = G[j]; cy = y0 + slot * (j + 0.5) + (520 - slot * n) / 2; wpx = (x1 - x0) * (v / vmax) * g
            col = C["blue"] if j == hl else C["gray"]
            dl.rectangle([x0, cy - bh / 2, x0 + wpx, cy + bh / 2], fill=col + (255,))
            fl = F("B", 36); w = tw(dl, lab, fl); dl.text((x0 - 30 - w, cy - 22), lab, font=fl, fill=(68, 68, 68, 255))
            if g > 0.6:
                fv = F("K", 48); vl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dv = ImageDraw.Draw(vl)
                dv.text((x0 + wpx + 20, cy - 30), disp, font=fv, fill=(C["blue"] if j == hl else (108, 117, 125)) + (255,))
                if s.get("reveal") and j == hl and lt < rev_t: vl = vl.filter(ImageFilter.GaussianBlur(14))
                lay.alpha_composite(vl)
        if s.get("ref"):
            rv, rl = s["ref"]; rx = x0 + (x1 - x0) * (rv / vmax)
            for yy in range(y0 - 20, y0 + 560, 26): d.line([(rx, yy), (rx, yy + 14)], fill=C["red"] + (150,), width=3)
            dl.text((rx - 60, y0 - 70), rl, font=F("B", 32), fill=C["red"] + (255,))
    img.alpha_composite(lay)
    if s.get("badge"):
        bt = (word_time(tl, s["badge"][0], s["badge"][2]) if len(s["badge"]) > 2 else line_time(tl, s["badge"][0])) - s["t0"]
        if lt > bt:
            d = ImageDraw.Draw(img); fb = F("K", 56); t = s["badge"][1]; w = tw(d, t, fb)
            bx = W - 150 - (w + 60); q = ease((lt - bt) / 0.18); sc_ = 1.0 + 0.25 * (1 - q)
            bl = Image.new("RGBA", (w + 60, 90), (0, 0, 0, 0)); dbl = ImageDraw.Draw(bl)
            dbl.rounded_rectangle([0, 0, w + 59, 89], radius=45, fill=C["red"] + (255,)); dbl.text((30, 8), t, font=fb, fill=(255, 255, 255, 255))
            bl = bl.resize((int(bl.width * sc_), int(bl.height * sc_)), Image.BICUBIC)
            img.alpha_composite(bl, (int(bx + (w + 60) / 2 - bl.width / 2), int(295 - bl.height / 2)))
    if s.get("stamp"):
        stt = word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]; stamp(img, s["stamp"][1], W - 520, 760, lt - stt)
    return img

def draw_table(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img); chart_header(d, s["title"], None)
    cols, rows = s["cols"], s["rows"]; nc = len(cols)
    fh, fr = F("B", 36), F("SB", 36)
    widths = [max(tw(d, str(r[c]), fr) for r in rows + [cols]) + 80 for c in range(nc)]
    tot = sum(widths); sc = min(1.0, (W - 240) / tot); widths = [w * sc for w in widths]; tot = sum(widths)
    x0 = (W - tot) / 2; y = 290; rh = 88
    rev_t = (reveal_time(tl, s) - s["t0"]) if s.get("reveal") else 0
    d.rounded_rectangle([x0, y, x0 + tot, y + rh], radius=16, fill=C["table_head"] + (255,))
    xx = x0
    for c in range(nc): w = tw(d, cols[c], fh); d.text((xx + (widths[c] - w) / 2, y + 22), cols[c], font=fh, fill=(255, 255, 255, 255)); xx += widths[c]
    y += rh
    for ri, r in enumerate(rows):
        hl = ri in s.get("hl_rows", [])
        bg = C["table_hl"] if hl else (C["table_alt"] if ri % 2 else (255, 255, 255))
        rl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(rl)
        dr.rectangle([x0, y, x0 + tot, y + rh], fill=bg + (255,)); dr.line([(x0, y + rh), (x0 + tot, y + rh)], fill=(224, 224, 224, 255), width=2)
        xx = x0
        for c in range(nc):
            t = str(r[c]); fnt = F("XB" if (hl or c == 0) else "SB", 36); w = tw(dr, t, fnt)
            dr.text((xx + (widths[c] - w) / 2, y + 22), t, font=fnt, fill=((30, 58, 138, 255) if c == 0 else (34, 34, 34, 255)))
            xx += widths[c]
        if s.get("row_at") and ri < len(s["row_at"]): appear = ease((lt - max(0.2, at_time(tl, s["row_at"][ri]) - s["t0"] - 0.2)) / 0.3)
        else: appear = ease((lt - 0.2 - ri * 0.18) / 0.3)
        if appear > 0:
            if s.get("reveal") and lt < rev_t and (ri in s.get("hl_rows", []) or (not s.get("hl_rows") and ri == len(rows) - 1)): rl = rl.filter(ImageFilter.GaussianBlur(10))
            a = rl.getchannel("A").point(lambda v: int(v * appear)); rl.putalpha(a); img.alpha_composite(rl)
        y += rh
    return img

def label_time(tl, it, j):
    return word_time(tl, it[0], it[2]) if len(it) > 2 else line_time(tl, it[0]) + j * 0.35
LABELC = [((255, 214, 0), (17, 17, 17)), ((30, 108, 235), (255, 255, 255)), ((255, 30, 138), (255, 255, 255))]
def draw_labels(s, lt, T, tl):
    img = photo_frame(s, lt, T, dark=0.45); d = ImageDraw.Draw(img)
    items = s["items"]; f = F("K", 80); n = len(items)
    ws = [tw(d, it[1], f) + 100 for it in items]; gap = 40
    row = sum(ws) + gap * (n - 1) <= W - 200
    if row:
        x = (W - (sum(ws) + gap * (n - 1))) / 2; ys = [H // 2 - 50] * n; xs = []
        for w in ws: xs.append(x); x += w + gap
    else:
        xs = [(W - w) / 2 for w in ws]; ys = [H // 2 - 60 - (n - 1) * 80 + j * 160 for j in range(n)]
    for j, it in enumerate(items):
        t = it[1]; at = label_time(tl, it, j) - s["t0"]
        p = lt - at
        if p <= 0: continue
        sc = (0.55 + 0.6 * ease(p / 0.12)) if p < 0.12 else (1.15 - 0.15 * ease((p - 0.12) / 0.12))
        fw = F("K", max(20, int(80 * sc))); w = tw(d, t, fw)
        cx = xs[j] + ws[j] / 2; cy = ys[j] + 45
        plain = t.strip().lower() == "vs"
        bgc, ink = ((255, 255, 255), (17, 17, 17)) if plain else LABELC[j % len(LABELC)]
        bgc, ink = [(TYPO_BG["lime"], (12, 24, 28)), (TYPO_BG["pink"], (12, 24, 28)), (C["yellow"], (12, 24, 28))][j % 3]
        d.rectangle([cx - w / 2 - 44, cy - 58 * sc, cx + w / 2 + 44, cy + 58 * sc], fill=tuple(bgc) + (250,))
        tb = d.textbbox((0, 0), t, font=fw); d.text((cx - w / 2 - tb[0], cy - (tb[1] + tb[3]) / 2), t, font=fw, fill=ink + (255,))
    return img

def draw_vs(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title"): chart_header(d, s["title"], None)
    ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.5, 1.4]
    for j, (t, col) in enumerate([(s["left"], C["blue"]), (s["right"], C["red"])]):
        p = ease((lt - ats[j]) / 0.35)
        if p <= 0: continue
        cx = W / 2 + (-1 if j == 0 else 1) * 420; f = F("K", 66); w = tw(d, t, f)
        d.rounded_rectangle([cx - 330, 340, cx + 330, 640], radius=30, fill=col + (int(255 * p),))
        d.text((cx - w / 2, 450), t, font=f, fill=(255, 255, 255, int(255 * p)))
    if lt > ats[1]:
        f = F("HAN", 120); w = tw(d, "VS", f); d.text(((W - w) / 2, 410), "VS", font=f, fill=(34, 34, 34, 255))
    if s.get("sub") and lt > ats[2]:
        f = F("B", 42); w = tw(d, s["sub"], f); d.text(((W - w) / 2, 720), s["sub"], font=f, fill=(68, 68, 68, 255))
    return img

def draw_cycle(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title"): chart_header(d, s["title"], None)
    cx, cy, R = W / 2, H / 2 + 20, 270; n = len(s["items"])
    pts = [(cx + R * math.cos(-math.pi / 2 + j * 2 * math.pi / n), cy + R * math.sin(-math.pi / 2 + j * 2 * math.pi / n)) for j in range(n)]
    active = int((lt / 0.9)) % n if lt > 0.3 else -1
    for j in range(n):
        a, b = pts[j], pts[(j + 1) % n]; mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        p = ease((lt - 0.2 - j * 0.3) / 0.3)
        if p > 0:
            ex = a[0] + (b[0] - a[0]) * (0.25 + 0.5 * p); ey = a[1] + (b[1] - a[1]) * (0.25 + 0.5 * p)
            d.line([(a[0] + (b[0] - a[0]) * 0.25, a[1] + (b[1] - a[1]) * 0.25), (ex, ey)], fill=(120, 120, 120, 255), width=10)
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            d.polygon([(ex + 26 * math.cos(ang), ey + 26 * math.sin(ang)), (ex + 22 * math.cos(ang + 2.4), ey + 22 * math.sin(ang + 2.4)), (ex + 22 * math.cos(ang - 2.4), ey + 22 * math.sin(ang - 2.4))], fill=(120, 120, 120, 255))
    for j, t in enumerate(s["items"]):
        x, y = pts[j]; col = C["red"] if j == active else C["navy"]
        d.ellipse([x - 120, y - 70, x + 120, y + 70], fill=col + (255,)); f = F("K", 54); w = tw(d, t, f); d.text((x - w / 2, y - 36), t, font=f, fill=(255, 255, 255, 255))
    return img

def draw_rating(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img); chart_header(d, "피치 · 프랑스 국가신용등급", None)
    ats = [at_time(tl, a) - s["t0"] for a in s["at"]] if s.get("at") else [0.15, 0.8, 1.4]
    p = ease((lt - ats[0]) / 0.4)
    d.ellipse([W / 2 - 520, 330, W / 2 - 160, 690], fill=C["navy"] + (int(255 * p),))
    f = F("K", 150); w = tw(d, s["grade"], f); d.text((W / 2 - 340 - w / 2, 420), s["grade"], font=f, fill=(255, 255, 255, int(255 * p)))
    fl = F("B", 40); d.text((W / 2 - 400, 720), "등급 유지", font=fl, fill=(68, 68, 68, 255))
    if lt > ats[1]:
        d.text((W / 2 + 40, 380), "등급 전망", font=F("B", 44), fill=(68, 68, 68, 255))
        d.text((W / 2 + 40, 460), s["before"], font=F("K", 80), fill=C["gray"] + (255,))
        d.text((W / 2 + 290, 460), "→", font=F("K", 80), fill=(90, 90, 90, 255))
        if lt > ats[2]: d.text((W / 2 + 400, 460), s["after"], font=F("K", 80), fill=C["red"] + (255,))
    return img

def draw_ladder(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img); chart_header(d, "신용등급 사다리 (피치 기준)", None)
    rows = s["rows"]; y = 280; rh = 76; x0 = W / 2 - 420
    for j, r in enumerate(rows):
        p = ease((lt - 0.1 - j * 0.08) / 0.25)
        if p <= 0: continue
        hl = r == s["hl"]; junk = r.startswith("BB") and not r.startswith("BBB")
        col = C["blue"] if hl else ((200, 60, 60) if junk else (120, 130, 145))
        d.rounded_rectangle([x0, y, x0 + 220, y + rh - 12], radius=12, fill=col + (int(255 * p),))
        f = F("K", 44); w = tw(d, r, f); d.text((x0 + 110 - w / 2, y + 8), r, font=f, fill=(255, 255, 255, int(255 * p)))
        if r in s["marks"]: d.text((x0 + 260, y + 10), s["marks"][r], font=F("XB" if hl else "B", 40), fill=(col if (hl or junk) else (68, 68, 68)) + (int(255 * p),))
        y += rh
    nt = (at_time(tl, s["note_at"]) - s["t0"]) if s.get("note_at") else 1.2
    if lt > nt:
        y1 = 280 + rh * rows.index("A+") + rh / 2 - 6; y2 = 280 + rh * rows.index("BB+") + rh / 2 - 6; bx = x0 - 40
        d.line([(bx, y1), (bx - 30, y1), (bx - 30, y2), (bx, y2)], fill=C["red"] + (255,), width=5)
        f = F("XB", 40); t = "여섯 칸 차이"; w = tw(d, t, f)
        d.rounded_rectangle([bx - 60 - w - 40, (y1 + y2) / 2 - 36, bx - 50, (y1 + y2) / 2 + 36], radius=18, fill=C["red"] + (255,))
        d.text((bx - 70 - w, (y1 + y2) / 2 - 26), t, font=f, fill=(255, 255, 255, 255))
    return img

def draw_pct(s, lt, T, tl):
    img = paper_bg().convert("RGBA"); d = ImageDraw.Draw(img)
    if s.get("title_top"): chart_header(d, s["title_top"], None)
    c_end = (at_time(tl, s["count_at"]) - s["t0"] + 0.2) if s.get("count_at") else 1.2
    c_st = max(0.15, c_end - 3.0); p = ease((lt - c_st) / max(0.3, c_end - c_st)); v = s["value"] * p; cx, cy, r = W / 2 - 330, H / 2 + 40, 230
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(217, 221, 226, 255))
    d.pieslice([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * v / 100, fill=C["red"] + (255,))
    d.ellipse([cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62], fill=C["paper"] + (255,))
    t = f"{v:.0f}%"; f = F("K", 96); w = tw(d, t, f); d.text((cx - w / 2, cy - 62), t, font=f, fill=C["red"] + (255,))
    fw = F("XB", 50); d.text((W / 2 + 10, H / 2 - 150), s["who"], font=fw, fill=C["navy"] + (255,))
    y = H / 2 - 60
    for ln in s["title"].split("\n"): d.text((W / 2 + 10, y), ln, font=F("B", 46), fill=(34, 34, 34, 255)); y += 66
    return img

def draw_photo(s, lt, T, tl):
    img = photo_frame(s, lt, T, dark=0.05)
    if s.get("bubble"):
        bt = bubble_time(tl, s) - s["t0"]; bubble(img, s["bubble"][1], W / 2 + 40, H / 2 - 120, lt - bt)
    if s.get("stamp"):
        stt = word_time(tl, s["stamp"][0], s["stamp"][1]) - s["t0"]; stamp(img, s["stamp"][1], W / 2 + 330, H / 2 + 40, lt - stt)
    if s.get("big"):
        bt = line_time(tl, s["big"][0]) - s["t0"]; big_label(img, s["big"][1], lt - bt)
    return img


# ───────────────────────── 키네틱 타이포 카드 (타이포템플릿 규격) ─────────────────────────
TYPO_BG = {"black": (12, 24, 28), "ivory": (240, 244, 243), "lime": (72, 226, 196), "pink": (255, 112, 80), "blue": (18, 160, 142)}
TYPO_INK = {"black": (245, 245, 240), "ivory": (17, 17, 17), "lime": (17, 17, 17), "pink": (17, 17, 17), "blue": (255, 255, 255)}
if CFG.get("typo_colors"):   # 결 손잡이 — 편 config 로 타이포 카드 색을 바꾼다
    TYPO_BG.update({k: tuple(v) for k, v in CFG["typo_colors"].items()})
    BOXC[:] = [TYPO_BG["lime"], TYPO_BG["pink"], tuple(C["yellow"]), TYPO_BG["blue"]]
def typo_cards(s, tl):
    """items: (문장, 단어, 글자, 바탕, 위치 L/C/R, 크기 S0/S1/S2, 등장 stamp/whip, [박스색])"""
    out = []
    for j, it in enumerate(s["items"]):
        t = max(s["t0"], at_time(tl, (it[0], it[1])) - 0.05) if j else s["t0"]
        out.append(dict(t=t, text=it[2], bg=it[3], pos=it[4], size=it[5], enter=it[6], box=(it[7] if len(it) > 7 else None)))
    return out
def typo_now(s, lt, tl):
    cs = typo_cards(s, tl); T = s["t0"] + lt; cur = cs[0]
    for c in cs:
        if c["t"] <= T: cur = c
    return cur, T - cur["t"]
def draw_typo_b(c, p):
    """결 b: 글자가 차례로 아래에서 올라오고, 강조는 색 글자 + 밑줄이 그어진다."""
    bg = TYPO_BG[c["bg"]]
    img = Image.new("RGBA", (W, H), bg + (255,)); ink = TYPO_INK[c["bg"]]; d = ImageDraw.Draw(img)
    rows = [parse_mark(r) for r in c["text"].split("/")]; size = {"S0": 300, "S1": 190, "S2": 130}[c["size"]]
    while True:
        f = F("GM", size); rw = [sum(tw(d, t, f) for t, _ in r) for r in rows]
        if max(rw) <= W * 0.84 or size < 60: break
        size = int(size * 0.92)
    lh = int(size * 1.3); y = (H - lh * len(rows)) / 2; n = 0
    for r, w in zip(rows, rw):
        x = {"L": W * 0.08, "C": (W - w) / 2, "R": W * 0.92 - w}[c["pos"]]
        for t, k in r:
            col = (TYPO_BG[c["box"]] if c.get("box") else C["sub_bar"][:3]) if k == "box" else ink
            if k == "box" and c["bg"] != "black": col = C["blue"]
            base = x; tb = d.textbbox((0, 0), "가", font=f)
            for i, ch in enumerate(t):
                g = ease((p - n * 0.028) / 0.24); n += 1; cx = base + d.textlength(t[:i], font=f)
                if g > 0: d.text((cx, y + (lh - tb[3] - tb[1]) / 2 + (1 - g) * size * 0.55), ch, font=f, fill=tuple(col) + (int(255 * g),))
            ww = tw(d, t, f)
            if k:
                g = ease((p - n * 0.028 - 0.05) / 0.22); yy = y + lh * (0.93 if k == "box" else 0.52)
                if g > 0: d.rectangle([base, yy, base + ww * g, yy + max(8, size // 14)], fill=tuple(col if k == "box" else C["wine"]) + (255,))
            x += ww
        y += lh
    return img

def draw_typo(s, lt, T, tl):
    c, p = typo_now(s, lt, tl)
    return draw_typo_b(c, p)

def typo_bright(s, lt, tl):
    c, _ = typo_now(s, lt, tl); return c["bg"] != "black"

# ───────────────────────── 기사 캡처 + 빨간 동그라미 ─────────────────────────
_art = {}
def load_article(name):
    if name not in _art:
        im = Image.open(E("assets", "article", name + ".png")).convert("RGB")
        meta = json.load(open(E("assets", "article", name + ".json"), encoding="utf-8"))
        _art[name] = (im, meta)
    return _art[name]
_artbg = {}
def article_bg(s):
    k = s["s"][0]
    if k not in _artbg:
        base = load_base(s.get("img", s["s"][0]))
        _artbg[k] = photo_grade(base.filter(ImageFilter.GaussianBlur(18)), 0.55).convert("RGBA")
    return _artbg[k]
def circle_times(s, tl):
    ats = s.get("circle_at") or []
    n = len(load_article(s["article"])[1]["boxes"]); T = s["t1"] - s["t0"]; out = []
    for j in range(n):
        out.append((at_time(tl, ats[j]) - s["t0"]) if j < len(ats) and ats[j] else T * (0.32 + 0.3 * j))
    return out
def hand_ellipse(dl, box, g, seed):
    x0, y0, x1, y1 = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; rx, ry = (x1 - x0) / 2 + 34, (y1 - y0) / 2 + 26
    rnd = random.Random(seed); ph = rnd.uniform(0, 6.28); n = max(2, int(80 * g)); pts = []
    for i in range(n + 1):
        a = -2.4 + (2 * math.pi + 0.5) * (i / 80); wob = 1 + 0.035 * math.sin(a * 3 + ph) + 0.05 * (i / 80)
        pts.append((cx + rx * wob * math.cos(a), cy + ry * wob * math.sin(a) - 4 * (i / 80)))
    dl.line(pts, fill=(235, 30, 30, 255), width=8, joint="curve")
def draw_article(s, lt, T, tl):
    img = article_bg(s).copy(); art, meta = load_article(s["article"])
    boxes = meta["boxes"]; cts = circle_times(s, tl)
    allb = [b for bs in boxes for b in bs]
    def union(bs): return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
    U = union(allb); fx = (U[0] + U[2]) / 2; fy = (U[1] + U[3]) / 2
    # 보여 줄 창: 처음엔 기사 위쪽(제목)부터, 첫 동그라미 전에 구절로 내려오며 살짝 확대
    DW, DH = 1440, 780; aw, ah = art.size
    # 처음엔 기사 폭 전체 → 첫 동그라미 때 첫 구절이 화면 폭 60%쯤 되게 확대
    B0 = union(boxes[0]); pw = max(200, B0[2] - B0[0])
    z0 = DW / aw; z1 = min(max(z0, 0.6 * DW / pw), z0 * 1.45, 1.0)
    mv = ease((lt - 0.2) / max(0.6, cts[0] - 0.2)); z = z0 + (z1 - z0) * mv
    fx = (B0[0] + B0[2]) / 2; fy = (B0[1] + B0[3]) / 2
    cw, ch = DW / z, DH / z
    top_y = 0 if not meta.get("headline_box") else max(0, meta["headline_box"][1] - 40)
    cy0 = min(max(top_y + ch / 2, ch / 2), max(ch / 2, ah - ch / 2)); cy1 = min(max(fy, ch / 2), max(ch / 2, ah - ch / 2))
    cyy = cy0 + (cy1 - cy0) * mv
    cxt = min(max(fx, cw / 2), aw - cw / 2) if cw < aw else aw / 2; cxx = aw / 2 + (cxt - aw / 2) * mv
    l, t = cxx - cw / 2, cyy - ch / 2
    view = art.transform((DW, DH), Image.EXTENT, (l, t, l + cw, t + ch), Image.BICUBIC, fillcolor=(255, 255, 255)).convert("RGBA")
    # 형광 + 동그라미 (화면 좌표)
    hl = Image.new("RGBA", (DW, DH), (0, 0, 0, 0)); dh = ImageDraw.Draw(hl)
    ov = Image.new("RGBA", (DW, DH), (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
    for j, bs in enumerate(boxes):
        g = ease((lt - cts[j]) / 0.45)
        if g <= 0: continue
        sb = [[(b[0] - l) * z, (b[1] - t) * z, (b[2] - l) * z, (b[3] - t) * z] for b in bs]
        for b in sb: dh.rectangle([b[0] - 4, b[1] + 2, b[0] - 4 + (b[2] - b[0] + 8) * min(1, g * 1.4), b[3] + 2], fill=(255, 230, 0, 110))
        if len(sb) == 1 or (union(sb)[3] - union(sb)[1]) < 90: hand_ellipse(do, union(sb), g, j * 7 + s["s"][0])
        else:  # 여러 줄 구절: 줄마다 빨간 밑줄
            for i_, b in enumerate(sb):
                gi = max(0.0, min(1.0, g * len(sb) - i_))
                if gi > 0: do.line([(b[0], b[3] + 6), (b[0] + (b[2] - b[0]) * gi, b[3] + 6 - 3 * gi)], fill=(235, 30, 30, 255), width=8)
    view.alpha_composite(hl); view.alpha_composite(ov)
    # 카드(그림자) 등장: 아래에서 올라오며
    q = ease(lt / 0.35); x0 = (W - DW) // 2; y0 = 128 + int((1 - q) * 120)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle([x0 + 10, y0 + 16, x0 + DW + 10, y0 + DH + 16], fill=(0, 0, 0, int(150 * q)))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    if q < 1: view.putalpha(view.getchannel("A").point(lambda v: int(v * q)))
    img.alpha_composite(view, (x0, y0))
    return img

DRAW = {"typo": draw_typo, "article": draw_article, "quote": draw_quote, "bignum": draw_bignum, "bar": draw_bar, "table": draw_table, "labels": draw_labels, "vs": draw_vs,
        "cycle": draw_cycle, "rating": draw_rating, "ladder": draw_ladder, "pct": draw_pct, "stock": draw_photo, "ai": draw_photo}

def logo_text(d, x, y, size, fill):
    d.text((x, y), CFG["channel_name"], font=F("GM", size), fill=fill)

def draw_bumper(lt, T, short=False):
    img = Image.new("RGBA", (W, H), (12, 24, 28, 255)); d = ImageDraw.Draw(img); ac = C["sub_bar"]; n = CFG["channel_name"]
    dur = 0.5 if short else 0.9; p = ease(lt / dur); size = 150 if short else 190; f = F("GM", size); w = tw(d, n, f); x = (W - w) / 2; y = H / 2 - size * 0.62
    d.rectangle([0, H / 2 + size * 0.62, W * p, H / 2 + size * 0.62 + 10], fill=ac)
    for i, ch in enumerate(n):
        g = ease((lt - i * 0.06) / 0.3)
        if g > 0: d.text((x + d.textlength(n[:i], font=f), y + (1 - g) * size * 0.5), ch, font=f, fill=(255, 255, 255, int(255 * g)))
    return img

def draw_outro(lt, T):
    img = Image.new("RGBA", (W, H), (12, 24, 28, 255)); d = ImageDraw.Draw(img); ac = C["sub_bar"]; p = ease(lt / 0.8)
    logo_text(d, 110, 90, 72, (255, 255, 255, 255)); d.rectangle([110, 190, 110 + 300 * p, 198], fill=ac)
    for lab, x, y, w, h in [(CFG["outro_left"], 110, 320, 900, 506), (CFG["outro_right"], 1100, 320, 710, 400)]:
        d.text((x, y - 62), lab, font=F("GM", 40), fill=(255, 255, 255, 255))
        d.rectangle([x, y, x + w * p, y + h], outline=ac, width=6)
    img.alpha_composite(draw_symbol(96), (1100, 756))
    return img

# ───────────────────────── 영상 렌더 ─────────────────────────
def pick_encoder():
    """NVENC 가 실제로 돌면 GPU, 아니면 CPU."""
    ok = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True).returncode == 0
    return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"] if ok else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

def render_video(t_from=None, t_to=None, out=None, frames=None):
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    total = tl["total"]; nfr = int(total * FPS)
    f0 = int((t_from or 0) * FPS); f1 = int((t_to or total) * FPS) if t_to else nfr
    if frames: f0, f1 = frames   # 구간 동시 렌더는 프레임 번호로 끊는다(초로 끊으면 경계에서 한 장이 겹치거나 빠진다)
    out = out or os.path.join(BUILD, "video.mp4" if t_from is None else f"part_{int(t_from)}_{int(t_to or total)}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{CFG['fps_num']}/{CFG['fps_den']}",
                           "-i", "-", *pick_encoder(), "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    shots = tl["shots"]; subs = tl["subs"]; evs = tl["events"]; si = 0
    for fi in range(f0, f1):
        t = fi / FPS
        ev = next((e for e in evs if e["t"] <= t < e["t"] + e["dur"]), None)
        if ev and ev["kind"].startswith("bumper"):
            frame = draw_bumper(t - ev["t"], ev["dur"], ev["kind"] == "bumper_short")
        elif ev and ev["kind"] == "outro":
            frame = draw_outro(t - ev["t"], ev["dur"])
        elif t >= shots[-1]["t1"] and not (ev and ev["kind"] == "wipe"):
            frame = draw_outro(0, 1)
        else:
            s = next((x for x in reversed(shots) if x["t0"] <= t), shots[0])
            lt, T = t - s["t0"], s["t1"] - s["t0"]
            frame = DRAW[s["type"]](s, lt, T, tl)
            if s["type"] != "typo" and lt < 0.2:   # 컷이 바뀔 때 색 띠가 지나간다
                x_ = -420 + (W + 840) * ease(lt / 0.2); dw = ImageDraw.Draw(frame, "RGBA")
                dw.polygon([(x_ + 150, 0), (x_ + 330, 0), (x_ + 180, H), (x_, H)], fill=C["sub_bar"])
            br = typo_bright(s, lt, tl) if s["type"] == "typo" else is_bright(s)
            if ev and ev["kind"] == "wipe":  # 크림 종이가 대각선으로 지나간다
                p = (t - ev["t"]) / ev["dur"]; lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
                x = -W * 0.6 + (W * 2.2) * p
                dl.polygon([(x + 14, 0), (x + W * 0.9 + 14, 0), (x + W * 0.5 + 14, H), (x - W * 0.4 + 14, H)], fill=(0, 0, 0, 60))
                lay = lay.filter(ImageFilter.GaussianBlur(10)); dl = ImageDraw.Draw(lay)
                dl.polygon([(x, 0), (x + W * 0.9, 0), (x + W * 0.5, H), (x - W * 0.4, H)], fill=(245, 239, 224, 255))
                frame.alpha_composite(lay)
            frame.alpha_composite(ui_layer(s["chapter"], br))
            src_bright = br
            if not br:  # 사진이라도 우하단이 밝으면 어두운 글자
                reg = frame.crop((40, H - 150, 760, H - 106)).convert("L"); src_bright = np.asarray(reg).mean() > 135
            if s["type"] != "typo": frame.alpha_composite(src_layer(shot_src(s), src_bright))
            so = None if s["type"] == "typo" else next((x for x in subs if x["t0"] <= t < x["t1"] + 0.1), None)
            if so: draw_sub_b(frame, so["text"], t - so["t0"])
        ff.stdin.write(frame.convert("RGB").tobytes())
        if fi % 300 == 0: print(f"{t/60:.2f}분 / {total/60:.2f}분", flush=True)
    ff.stdin.close(); ff.wait(); print("영상:", out)

def render_parallel(n=6):
    """구간 n개를 프로세스로 나눠 그린 뒤 다시 인코딩 없이 잇는다. 프레임 수가 안 맞으면 멈춘다."""
    tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
    nfr = int(tl["total"] * FPS); cuts = [nfr * k // n for k in range(n + 1)]
    parts = [os.path.join(BUILD, f"gpu_{k}.mp4") for k in range(n)]
    def start(k):
        log = open(os.path.join(BUILD, f"gpu_{k}.log"), "w", encoding="utf-8")   # 왜 죽었는지 남긴다(11-02 2번 구간이 까닭 없이 끊겼다)
        return subprocess.Popen([sys.executable, "-X", "utf8", os.path.abspath(__file__), "video-part", str(cuts[k]), str(cuts[k + 1]), parts[k]],
                                stdout=log, stderr=subprocess.STDOUT)
    ps = [start(k) for k in range(n)]
    bad = [k for k, p in enumerate(ps) if p.wait()]
    for k in bad:   # 혼자 다시 돌리면 대개 지나간다 — 한 번만
        print(f"구간 {k} 다시", flush=True)
        if start(k).wait(): raise SystemExit(f"구간 {k} 렌더 실패 — build/gpu_{k}.log")
    lst = os.path.join(BUILD, "gpu_list.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '" + p.replace(chr(92), "/") + "'" + chr(10) for p in parts))
    out = os.path.join(BUILD, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout.strip().rstrip(","))
    if got != nfr: raise SystemExit(f"프레임 수 불일치: {got} != {nfr}")
    for p in parts: os.remove(p)
    print("영상:", out, got, "프레임")

def mux():
    out = E("_완성", CFG.get("output_name", "완성본.mp4")); os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "video.mp4"), "-i", os.path.join(BUILD, "mix.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    print("완성:", os.path.abspath(out))

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "timeline"
    if cmd == "timeline": tl = build_timeline(); build_audio(tl)
    elif cmd == "video":
        a = float(sys.argv[2]) if len(sys.argv) > 2 else None; b = float(sys.argv[3]) if len(sys.argv) > 3 else None; render_video(a, b)
    elif cmd == "video-gpu": render_parallel(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    elif cmd == "video-part": render_video(out=sys.argv[4], frames=(int(sys.argv[2]), int(sys.argv[3])))
    elif cmd == "frame":
        tl = json.load(open(os.path.join(BUILD, "timeline.json"), encoding="utf-8"))
        for ts in sys.argv[2:]:
            t = float(ts); render_video(t, t + 1 / FPS, os.path.join(BUILD, f"frame_{t:.1f}.mp4"))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, f"frame_{t:.1f}.mp4"), "-frames:v", "1", os.path.join(BUILD, f"frame_{t:.1f}.png")])
    elif cmd == "mux": mux()
