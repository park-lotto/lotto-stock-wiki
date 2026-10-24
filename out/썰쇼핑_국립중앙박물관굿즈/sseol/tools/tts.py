"""내레이션 생성 + 자막 타이밍 정렬.

사용법: python tts.py <프로젝트폴더> [--reuse]   (--reuse: 이미 받은 raw TTS 재사용)

1) script.json 의 제목 + 카드 문장을 타입캐스트로 한 번에 읽힘 (config.json 의 voice)
2) 문장 사이 긴 쉼을 줄이고, 원본 속도(초당 약 8.2음절)에 맞춰 템포 보정
3) Speechmatics 로 받아쓰기 → 대본 글자와 정렬해 줄마다 등장 시각 계산
출력: narration.wav, timing.json
"""
import difflib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# API 키: 패키지의 keys/ 폴더 우선, 없으면 ~/.volcano/keys (파일명 = 키 이름, 내용 = 키 값)
KEY_DIRS = [os.path.join(ROOT, "keys"), os.path.join(os.path.expanduser("~"), ".volcano", "keys")]
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))


def key(name):
    env = os.environ.get(name.upper() + "_API_KEY")  # 환경변수가 있으면 그 키 (예: TYPECAST_API_KEY)
    if env:
        return env.strip()
    for d in KEY_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return open(p, encoding="utf-8-sig").read().strip()
    raise SystemExit(f"API 키가 없습니다: keys/{name} 파일에 키 값만 넣어주세요")


def spoken(text):
    return text.replace("“", "").replace("”", "").replace('"', "")


def norm_chars(text):
    """정렬용: 한글·영문·숫자만."""
    return [c for c in text if c.isalnum()]


def syllables(text):
    return sum(1 for c in text if "가" <= c <= "힣" or c.isdigit())


def wav_dur(p):
    with wave.open(p) as w:
        return w.getnframes() / w.getframerate()


def typecast(text, out):
    v = CFG["voice"]
    body = {"voice_id": v["voice_id"], "text": text, "model": v.get("model", "ssfm-v30"), "language": "kor",
            "prompt": {"emotion_type": "preset", "emotion_preset": v.get("emotion", "normal"),
                       "emotion_intensity": v.get("intensity", 1.0)},
            "output": {"volume": 100, "audio_pitch": v.get("pitch", 0), "audio_tempo": v.get("tempo", 1.0),
                       "audio_format": "wav"}}
    req = urllib.request.Request("https://api.typecast.ai/v1/text-to-speech", data=json.dumps(body).encode(),
                                 headers={"X-API-KEY": key("typecast"), "Content-Type": "application/json"})
    open(out, "wb").write(urllib.request.urlopen(req, timeout=300).read())


def speechmatics(path):
    k = key("speechmatics")
    b = "----" + uuid.uuid4().hex
    cfg = json.dumps({"type": "transcription",
                      "transcription_config": {"language": "ko", "operating_point": "enhanced"}})
    body = (f'--{b}\r\nContent-Disposition: form-data; name="config"\r\n\r\n{cfg}\r\n--{b}\r\n'
            f'Content-Disposition: form-data; name="data_file"; filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'
            ).encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    base = "https://asr.api.speechmatics.com/v2/jobs"
    jid = json.load(urllib.request.urlopen(urllib.request.Request(
        base, data=body, headers={"Authorization": "Bearer " + k, "Content-Type": "multipart/form-data; boundary=" + b})))["id"]
    for _ in range(200):
        st = json.load(urllib.request.urlopen(urllib.request.Request(
            f"{base}/{jid}", headers={"Authorization": "Bearer " + k})))["job"]["status"]
        if st == "done":
            break
        if st in ("rejected", "deleted"):
            raise SystemExit("speechmatics 실패: " + st)
        time.sleep(2)
    t = json.load(urllib.request.urlopen(urllib.request.Request(
        f"{base}/{jid}/transcript?format=json-v2", headers={"Authorization": "Bearer " + k})))
    return [(r["alternatives"][0]["content"], r["start_time"], r["end_time"])
            for r in t["results"] if r["type"] == "word"]


PAUSE_END, PAUSE_MID = 0.11, 0.06   # 원본 5편 실측(목소리 최고치 −14dB 아래 연속 구간): 문장 끝 0.11초 · 그 밖 0.06초


def fit_pauses(path, bounds):
    """줄 경계마다 목소리가 잦아든 구간을 원본과 같은 잣대로 재서, 목표보다 길면 가운데를 잘라낸다.
    bounds: [(경계 시각, 목표 초)]. 잘라낸 [(시작, 길이)] 를 돌려준다(뒤 시각 보정용)."""
    import numpy as np
    with wave.open(path) as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), np.int16).astype(np.float64)
    hop = sr // 100
    e = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(sr // 40) / (sr // 40), "same")[::hop]) / 32768 + 1e-9)
    cuts = []
    for tb, target in bounds:
        c = int(tb * 100)
        lo, hi = max(0, c - 30), min(len(e), c + 30)
        peak = np.percentile(e[max(0, c - 100):c + 100], 90)
        low = e[lo:hi] < peak - 14
        best, cur, end = 0, 0, lo
        for i, v in enumerate(low):
            cur = cur + 1 if v else 0
            if cur > best:
                best, end = cur, lo + i + 1
        excess = best * 0.01 - target
        if excess > 0.005:
            mid = (end - best / 2) * 0.01
            cuts.append((mid - excess / 2, excess))
    keep, pos = [], 0
    for st, ln in sorted(cuts):
        a, b = int(st * sr), int((st + ln) * sr)
        keep.append(x[pos:a]); pos = b
    keep.append(x[pos:])
    y = np.concatenate(keep).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y.tobytes())
    return sorted(cuts)


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main():
    proj = os.path.abspath(sys.argv[1])
    s = json.load(open(os.path.join(proj, "script.json"), encoding="utf-8"))
    # 줄 단위 세그먼트: (카드번호 또는 -1=제목, 줄번호, 읽을 문장)
    segs = [(-1, 0, s["title"] + ".")]
    for ci, c in enumerate(s["cards"]):
        say = c.get("say")
        if say:  # 카드 통째로 읽을 문장을 따로 준 경우: 줄 경계는 글자 수 비율로
            segs.append((ci, "say", say))
        else:
            for li, line in enumerate(c["lines"]):
                segs.append((ci, li, line))
    # 문장 끝(음슴체 ~함·~음 등)은 대본 줄 끝에 마침표를 직접 찍는다 — 받침만으로는 «여름» 같은 명사와 구별이 안 된다.
    # 마침표가 있어야 억양이 떨어지고 쉼(원본 실측 0.11초)이 생긴다. 화면 자막에서는 마침표가 지워진다.
    text = " ".join(spoken(t) for _, _, t in segs)

    raw = os.path.join(proj, "tts_raw.wav")
    if not ("--reuse" in sys.argv and os.path.exists(raw)):
        print("타입캐스트 생성 중…", flush=True)
        typecast(text, raw)
    # 말 속도 재기용: 긴 쉼을 0.11초로 줄인 길이로 음절/초를 잰다
    SIL = "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.12:stop_threshold=-35dB:stop_silence={},areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
    tight = os.path.join(proj, "tts_tight.wav")
    ff("-i", raw, "-af", SIL.format(0.11), "-ar", "48000", "-ac", "1", tight)
    rate = syllables(text) / wav_dur(tight)
    factor = max(0.8, min(1.6, CFG.get("target_syllables_per_sec", 8.2) / rate))
    # 빠르기 보정을 먼저 하고 쉼을 줄여야 최종 문장 끝 쉼이 원본 실측 0.11초가 된다(반대 순서면 0.11/배율로 짧아짐)
    out = os.path.join(proj, "narration.wav")
    ff("-i", raw, "-af", f"atempo={factor:.4f}," + SIL.format(0.11) + ",loudnorm=I=-13:TP=-1:LRA=7", "-ar", "48000", "-ac", "1", out)
    dur = wav_dur(out)
    print(f"속도 {rate:.2f}음절/초 → x{factor:.3f} 보정, 길이 {dur:.2f}초")

    print("받아쓰기 정렬 중…", flush=True)
    words = speechmatics(out)
    a_chars, a_times = [], []
    for w, st, en in words:
        cs = norm_chars(w)
        for i, c in enumerate(cs):
            a_chars.append(c)
            a_times.append(st + (en - st) * i / max(len(cs), 1))
    s_chars, s_owner = [], []
    for si, (_, _, t) in enumerate(segs):
        for c in norm_chars(t):
            s_chars.append(c)
            s_owner.append(si)
    sm = difflib.SequenceMatcher(None, s_chars, a_chars, autojunk=False)
    s2t = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            s2t[blk.a + k] = a_times[blk.b + k]
    known = sorted(s2t)

    def time_of(idx):
        if idx in s2t:
            return s2t[idx]
        after = [k for k in known if k > idx]
        before = [k for k in known if k < idx]
        if before and after:
            k0, k1 = before[-1], after[0]
            return s2t[k0] + (s2t[k1] - s2t[k0]) * (idx - k0) / (k1 - k0)
        return s2t[after[0]] if after else (s2t[before[-1]] if before else 0.0)

    seg_start = []
    pos = 0
    for _, _, t in segs:
        seg_start.append(max(0.0, time_of(pos) - 0.05))
        pos += len(norm_chars(t))
    matched = len(s2t) / max(len(s_chars), 1)

    # 줄 경계 쉼을 원본 실측값으로 (문장 끝 = 줄이 마침표로 끝남)
    bounds = [(seg_start[si + 1] + 0.05, PAUSE_END if t.rstrip().endswith(".") else PAUSE_MID)
              for si, (_, _, t) in enumerate(segs[:-1])]
    cuts = fit_pauses(out, bounds)
    shift = lambda tt: tt - sum(ln for st, ln in cuts if st < tt)
    seg_start = [max(0.0, shift(v)) for v in seg_start]
    words = [(w, shift(a), shift(b)) for w, a, b in words]
    dur = wav_dur(out)
    print(f"쉼 맞춤: {len(cuts)}곳 {sum(ln for _, ln in cuts):.2f}초 줄임")

    cards = [{"start": None, "line_starts": []} for _ in s["cards"]]
    for si, (ci, li, t) in enumerate(segs):
        if ci < 0:
            continue
        if li == "say":  # 줄 경계를 글자 수 비율로
            nxt = seg_start[si + 1] if si + 1 < len(segs) else dur
            lines = s["cards"][ci]["lines"]
            tot = sum(len(norm_chars(x)) for x in lines)
            acc = 0
            for x in lines:
                cards[ci]["line_starts"].append(seg_start[si] + (nxt - seg_start[si]) * acc / max(tot, 1))
                acc += len(norm_chars(x))
        else:
            cards[ci]["line_starts"].append(seg_start[si])
    for c in cards:
        c["start"] = c["line_starts"][0]
    timing = {"intro_end": cards[0]["start"], "cards": cards, "end": round(dur + 0.4, 3),
              "match_ratio": round(matched, 3), "words": words}
    json.dump(timing, open(os.path.join(proj, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"정렬 일치율 {matched:.0%}, 인트로 {timing['intro_end']:.2f}초, 카드 {len(cards)}개")


if __name__ == "__main__":
    main()
