"""쇼츠 소리를 구간별 언어로 가른다(로컬 whisper small) — 원본 외국어 음성 vs 한국어 나레이션 비율·위치."""
import json, glob, sys, whisper, numpy as np
m = whisper.load_model("small")
ids = [x["sc"] for x in json.load(open("foreign.json", encoding="utf-8"))] + ["pNn1UL5VQXU"]
out = {}
for sc in ids:
    f = glob.glob(f"aud/{sc}.*")[0]
    audio = whisper.load_audio(f); total = len(audio) / 16000
    r = m.transcribe(audio, language="ko", fp16=False, condition_on_previous_text=False)
    segs = []
    for s in r["segments"]:
        a = audio[int(s["start"] * 16000):int(s["end"] * 16000)]
        if len(a) < 16000 * 0.4: continue
        mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(a)).to(m.device)
        _, probs = m.detect_language(mel)
        lang = max(probs, key=probs.get)
        segs.append({"s": round(s["start"], 1), "e": round(s["end"], 1), "lang": lang, "p": round(probs[lang], 2), "ko_text": s["text"].strip()[:40]})
    spk = sum(x["e"] - x["s"] for x in segs)
    fo = sum(x["e"] - x["s"] for x in segs if x["lang"] != "ko")
    out[sc] = {"total": round(total, 1), "speech": round(spk, 1), "foreign": round(fo, 1), "segs": segs}
    print(sc, f"{total:.0f}초 말{spk:.0f} 외국어{fo:.0f}", flush=True)
json.dump(out, open("lang_out.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
