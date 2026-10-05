"""(로컬) 재료 소리에서 '사람 말' 구간을 Whisper로 세고 언어·내용을 남긴다 — 원음살리기 조사 1단계.

  py tools/orig_voice/speech_census.py <sample_sources.py 출력 폴더> [모델=small]
출력: <폴더>/census.json  (재료별 길이·말 길이·말 비율·언어·구간 텍스트)
판정 기준: Whisper 구간 중 no_speech_prob<0.6 · avg_logprob>-1.0 · 0.4초 이상만 '말'로 센다(헛들음 걸러내기).
⚠️ 노래 가사도 '말'로 잡힐 수 있다 — census.json의 text를 사람이 훑어 판정할 것.
"""
import json, os, sys, whisper

D = sys.argv[1]
m = whisper.load_model(sys.argv[2] if len(sys.argv) > 2 else "small")
man = json.load(open(os.path.join(D, "manifest.json"), encoding="utf-8"))
outp = os.path.join(D, "census.json")
out = json.load(open(outp, encoding="utf-8")) if os.path.exists(outp) else {}
for it in man:
    h = it["h"]
    if h in out:
        continue
    audio = whisper.load_audio(os.path.join(D, h + ".mp3"))
    total = len(audio) / 16000
    r = m.transcribe(audio, language=None, fp16=False, condition_on_previous_text=False)
    segs = []
    for s in r["segments"]:
        if s["no_speech_prob"] >= 0.6 or s["avg_logprob"] <= -1.0 or s["end"] - s["start"] < 0.4:
            continue
        a = audio[int(s["start"] * 16000):int(s["end"] * 16000)]
        mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(a)).to(m.device)
        _, probs = m.detect_language(mel)
        lang = max(probs, key=probs.get)
        segs.append({"s": round(s["start"], 1), "e": round(s["end"], 1), "lang": lang,
                     "p": round(probs[lang], 2), "text": s["text"].strip()})
    spk = sum(x["e"] - x["s"] for x in segs)
    out[h] = dict(it, total=round(total, 1), speech=round(spk, 1), ratio=round(spk / total, 2) if total else 0,
                  main_lang=r.get("language"), segs=segs)
    print(h, it["plat"], f"{total:.0f}s 말{spk:.0f}s", r.get("language"), flush=True)
    json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
