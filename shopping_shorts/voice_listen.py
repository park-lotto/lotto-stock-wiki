"""음성 듣기 엔진 — TTS 결과물을 '귀'로 검수한다(관제 254, 2026-10-23 사장님 "들을 수 있는 엔진이 필요하고, 우리 tts도 어짜피 검수를 해야하니").

글자(대본)와 비교하는 게 아니라 **나온 소리**를 잰다. 세 겹:
  ① 읽기   — 위스퍼로 받아쓴 것을 대본과 **읽는 소리(히라가나/한글)** 로 맞춘다. 漢字↔かな 표기 차이는 오류가 아니고,
             소리가 다르면(ダイソー→アイス, かかく→かく) 오류다.
  ② 운율   — 말 빠르기(초당 음절)·끊김(0.5초+ 쉼)·앞뒤 무음·음높이 폭(단조로움)·소리 크기·찢어짐.
             원어민 기준 범위(native_band)와 비교해 벗어나면 짚는다.
  ③ 귀 판정 — (선택) 제미나이에게 원어민 음성과 **나란히** 들려 A/B로 묻는다. 혼자 점수 매기게 하면 거의 다 만점이라(실측 15개 중 14개 5점) 쓸모없다.

  from shopping_shorts.voice_listen import listen
  r = listen("x.mp3", "台本テキスト", lang="ja")   # → {"ok", "reading":{...}, "prosody":{...}, "issues":[...]}
  py -m shopping_shorts.voice_listen <mp3> "<대본>" [ja|ko]
"""
import difflib
import json
import re
import sys

_MODEL = None
_MODEL_NAME = "deepdml/faster-whisper-large-v3-turbo-ct2"
_PUNCT = re.compile(r"[\s、。，,．.！!？?「」『』（）()・…〜~ー\-—:;：；\"'“”‘’]")

# 원어민 기준 범위 — 일본 쇼핑 쇼츠 9편 실측 10~90%(tools/ja_caption/native_band.py, 2026-10-23):
#   말 빠르기 7.22~9.41 모라/초(중앙 8.39) · 음높이 폭 11.1~20.7반음(중앙 14.5) · 0.5초+ 쉼 10초당 0~0.16.
#   배경음 걷어낸 목소리(demucs) 4편으로 다시 재도 11.0~17.3반음 — 배경음 탓에 부푼 게 아니다.
NATIVE_BAND = {
    "ja": {"syl_per_sec": (7.0, 9.6), "pitch_semitones": (11.0, 22.0), "long_pause_per_10s": (0.0, 1.0)},
}


def _model(cpu=False):
    global _MODEL
    if _MODEL is None or cpu:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(_MODEL_NAME, device="cpu" if cpu else "cuda",
                              compute_type="int8" if cpu else "float16")
    return _MODEL


def transcribe(path, lang="ja"):
    import librosa   # 이 PC의 av 판본이 faster_whisper 파일 열기와 안 맞아(metadata_errors) 소리를 직접 풀어 넘긴다
    audio, _sr = librosa.load(str(path), sr=16000, mono=True)
    def run(m):
        segs, _info = m.transcribe(audio, language=lang, word_timestamps=True, vad_filter=False, beam_size=5)
        return [{"w": w.word, "start": w.start, "end": w.end, "p": w.probability} for s in segs for w in (s.words or [])]
    try:
        words = run(_model())
    except Exception as e:  # GPU 부품(cublas 등)이 없으면 첫 계산에서 터진다 → CPU 로 바꿔 다시. 조용히 넘기지 않는다
        print("voice_listen: GPU 못 씀 → CPU(%s)" % (str(e)[:80],), file=sys.stderr)
        words = run(_model(cpu=True))
    return "".join(x["w"] for x in words).strip(), words


def reading(text, lang="ja"):
    """표기를 걷어낸 '읽는 소리'. 일본어=히라가나, 그 밖=문장부호만 뺀 글자."""
    t = _PUNCT.sub("", text or "")
    if lang != "ja":
        return t
    import pykakasi
    kk = pykakasi.kakasi()
    return "".join(x["hira"] for x in kk.convert(t))


def compare_reading(script, heard, lang="ja"):
    a, b = reading(script, lang), reading(heard, lang)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    # 앞뒤 3글자를 붙여 어느 낱말인지 보이게 한다(「だ」→「が」만으론 못 찾는다)
    diffs = [{"script": a[i1:i2], "heard": b[j1:j2], "kind": t,
              "where": a[max(0, i1 - 3):i2 + 3], "heard_where": b[max(0, j1 - 3):j2 + 3]}
             for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]
    return {"match": round(sm.ratio(), 3), "script_read": a, "heard_read": b, "diffs": diffs}


def _syllables(text_read, lang):
    if lang == "ja":   # 모라: 작은 ゃゅょ 는 앞 글자에 붙는다
        return sum(1 for ch in text_read if ch not in "ゃゅょぁぃぅぇぉゎ")
    return len(text_read)


def prosody(path, words, script_read, lang="ja"):
    import numpy as np
    import librosa
    y, sr = librosa.load(str(path), sr=16000, mono=True)
    dur = len(y) / sr
    if not words:
        return {"duration": round(dur, 2), "error": "말소리를 못 찾았어요"}
    t0, t1 = words[0]["start"], words[-1]["end"]
    speech = max(0.01, t1 - t0)
    gaps = [round(b["start"] - a["end"], 2) for a, b in zip(words, words[1:]) if b["start"] - a["end"] >= 0.5]
    f0, voiced, _ = librosa.pyin(y, fmin=70, fmax=500, sr=sr, frame_length=1024)
    f0 = f0[voiced & ~np.isnan(f0)] if f0 is not None else np.array([])
    semis = float(12 * np.log2(np.percentile(f0, 95) / np.percentile(f0, 5))) if len(f0) > 20 else 0.0
    rms = librosa.feature.rms(y=y)[0]
    return {
        "duration": round(dur, 2),
        "lead_silence": round(t0, 2), "tail_silence": round(dur - t1, 2),
        "syl_per_sec": round(_syllables(script_read, lang) / speech, 2),
        "long_pauses": gaps, "long_pause_per_10s": round(len(gaps) * 10 / speech, 2),
        "pitch_semitones": round(semis, 1),
        "loudness_db": round(float(20 * np.log10(np.mean(rms) + 1e-9)), 1),
        "clipping": int(np.sum(np.abs(y) > 0.99)),
        "low_conf_words": [x["w"].strip() for x in words if x["p"] < 0.5],
    }


def listen(path, script, lang="ja"):
    heard, words = transcribe(path, lang)
    rd = compare_reading(script, heard, lang)
    pr = prosody(path, words, rd["script_read"], lang)
    issues = []
    for d in rd["diffs"]:
        if len(d["script"]) + len(d["heard"]) >= 1:
            issues.append(f"읽기: 「{d['where']}」를 「{d['heard_where']}」로 읽음")
    band = NATIVE_BAND.get(lang, {})
    for k, (lo, hi) in band.items():
        v = pr.get(k)
        if isinstance(v, (int, float)) and not (lo <= v <= hi):
            issues.append(f"운율: {k}={v} (원어민 {lo}~{hi})")
    if pr.get("clipping", 0) > 50:
        issues.append(f"소리 찢어짐 {pr['clipping']}샘플")
    if pr.get("lead_silence", 0) > 0.6 or pr.get("tail_silence", 0) > 0.8:
        issues.append(f"앞뒤 무음 {pr.get('lead_silence')}초/{pr.get('tail_silence')}초")
    return {"ok": not issues, "heard": heard, "reading": rd, "prosody": pr, "issues": issues}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    r = listen(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "ja")
    r["reading"].pop("script_read"); r["reading"].pop("heard_read")
    print(json.dumps(r, ensure_ascii=False, indent=1))
