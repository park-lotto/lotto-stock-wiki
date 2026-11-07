# 나레이션·효과음·음악 믹스
from .settings import *
from .timing import *
from .cards import *
from .typeset import *
from .news import *
SR = 48000
def load_pcm(path):
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
def make_soundtrack(tl):
    SFX.update(CFG.get("sfx") or {})
    n = int((tl["total"] + 0.5) * SR); narr = np.zeros(n, np.float32); fx = np.zeros(n, np.float32); mus = np.zeros(n, np.float32)
    for x in tl["lines"]:
        place(narr, load_pcm(os.path.join(NARR, "trim", f"{x['i']:03d}.wav")), x["t0"])
    sfx = {k: load_pcm(P(v)) for k, v in SFX.items() if os.path.exists(P(v))}
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
        if ty == "bignum" and "pop" in sfx: place(fx, sfx["pop"], number_landing(tl, s), db(-10))
        if "bubble" in s and "pop" in sfx and not s.get("variant"): place(fx, sfx["pop"], bubble_time(tl, s) + 0.05, db(-7))
        if "stamp" in s and "thud" in sfx: place(fx, cut(sfx["thud"], 0.8), word_time(tl, s["stamp"][0], s["stamp"][1]), db(-6))
        if "reveal" in s and "ding" in sfx: place(fx, cut(sfx["ding"], 0.8), reveal_time(tl, s), db(-18))
        if ty == "labels" and "pop" in sfx:
            for j, it in enumerate(s["items"]): place(fx, sfx["pop"], label_time(tl, it, j), db(-8))
        if ty == "table" and s.get("row_at") and "pop" in sfx:
            for a in s["row_at"]: place(fx, sfx["pop"], max(s["t0"], at_time(tl, a)), db(-12))
    for s in tl["shots"]:
        if s["type"] == "typo":
            for c in type_items(s, tl):
                if c["enter"] == "stamp" and "thud" in sfx: place(fx, cut(sfx["thud"], 0.35), c["t"], db(-15))
                elif "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.3), max(0, c["t"] - 0.08), db(-17))
        if s["type"] == "article":
            if "whoosh" in sfx: place(fx, cut(sfx["whoosh"], 0.45), max(0, s["t0"] - 0.1), db(-18))
            for ct in circle_times(s, tl):
                if "pop" in sfx: place(fx, sfx["pop"], s["t0"] + ct, db(-11))
    for e in tl["events"]:
        if e["kind"] == "wipe" and "whoosh" in sfx: place(fx, cut(sfx["whoosh"][int(0.25 * SR):], 0.35), max(0, e["t"] - 0.05), db(-17))
    # 음악: 본편 BGM(챕터 바뀌면 곡 교체) + 징글 + 아웃트로
    if CFG["music"]:   # 판이 음악을 끄면 BGM·징글·아웃트로 음악을 깔지 않는다(효과음은 그대로)
        main = load_pcm(P(CFG["bgm_main"])); alt = load_pcm(P(CFG["bgm_alt"])); jg = load_pcm(P(CFG["jingle"]))
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
        rot = [prep(load_pcm(P(x))) for x in CFG.get("bgm_rotation", [CFG["bgm_main"]])]
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

