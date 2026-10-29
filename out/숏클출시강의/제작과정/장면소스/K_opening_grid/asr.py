import numpy as np, wave
from faster_whisper import WhisperModel
m=WhisperModel("small",device="cpu",compute_type="int8")
for i in (6,5,1,4):
    w=wave.open(f"aud/s{i}.wav"); a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
    segs,_=m.transcribe(a,language="ko",vad_filter=True,word_timestamps=True)
    print("==",i)
    for s in segs: print(f"{s.start:.1f}-{s.end:.1f} {s.text}")
