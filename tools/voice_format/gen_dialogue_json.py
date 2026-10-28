"""대화 대본 JSON 하나 → 일레븐 대화 API(eleven_v3) 한 번 합성. 결과는 /tmp/tiki2/dlg/<name>.mp3 에만.
서버: sudo bash -c 'set -a; . /etc/shopping-shorts.env; set +a; python3 /tmp/gen_dialogue_json.py /tmp/a.json [/tmp/b.json ...]'"""
import json, os, sys, requests
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import tts
for _f in sys.argv[1:]:
  S = json.load(open(_f, encoding="utf-8"))
  P = {p["preset_id"]: p for p in json.load(open("/home/ubuntu/lotto-stock-wiki/shopping_shorts/assets/voice_presets.json", encoding="utf-8"))}
  vid = {who: P[pid]["base_voice_id"] for who, pid in S["cast"].items()}
  r = requests.post("https://api.elevenlabs.io/v1/text-to-dialogue",
                    headers={"xi-api-key": tts._api_key(0), "Content-Type": "application/json"},
                    json={"model_id": "eleven_v3", "inputs": [{"text": l[1], "voice_id": vid[l[0]]} for l in S["lines"]]},
                    timeout=180)
  os.makedirs("/tmp/tiki2/dlg", exist_ok=True)
  if r.status_code != 200:
      print("실패", S["name"], r.status_code, r.text[:200]); continue
  out = f"/tmp/tiki2/dlg/{S['name']}.mp3"
  open(out, "wb").write(r.content)
  print(out, len(r.content), "bytes")
