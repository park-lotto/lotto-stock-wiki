import json, sys, os
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import tts, tts_timestamps as tt
D = "/tmp/staybro_tts"
lines = json.load(open(D + "/lines.json", encoding="utf-8"))
for i, line in enumerate(lines):
    out = D + "/tts_%d.mp3" % i
    tts.synthesize_tts(line, out, voice_id="aiUUgjHa4mpHf6UenZuf", model_id="eleven_v3", speed=1.0,
                       voice_settings={"stability": 0.55, "similarity_boost": 0.78, "style": 0.15},
                       previous_text=lines[i - 1] if i else None, next_text=lines[i + 1] if i + 1 < len(lines) else None)
    print(i, os.path.getsize(out), os.path.exists(tt.sidecar_path(out)))
