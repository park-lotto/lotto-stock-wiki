"""엔진 섞인 대화 대본 합성 — 타입캐스트(필재 등 ssfm-*) 줄은 줄마다, 일레븐(eleven_v3) 줄은 **이어진 덩어리째** 대화 API로.
결과: /tmp/tiki2/mix/<name>/seg_NN_<화자들>.mp3 (+ segs.json). 이어 붙이기·간격·속도는 PC에서(assemble_mixed.py).
서버: sudo bash -c 'set -a; . /etc/shopping-shorts.env; set +a; python3 /tmp/gen_mixed.py /tmp/a.json [...]'
★타입캐스트는 typecast_tts.synthesize 를 직접 부른다 — tts.synthesize_tts 는 TYPECAST_ENABLED=0 이면 미나로 바꿔치기하므로(use_fallback)."""
import json, os, sys, requests
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import tts, typecast_tts
P = {p["preset_id"]: p for p in json.load(open("/home/ubuntu/lotto-stock-wiki/shopping_shorts/assets/voice_presets.json", encoding="utf-8"))}
if not typecast_tts.api_key(0):
    print("타입캐스트 키 없음 — 필재 합성 불가"); sys.exit(1)
for f in sys.argv[1:]:
    S = json.load(open(f, encoding="utf-8"))
    out = f"/tmp/tiki2/mix/{S['name']}"; os.makedirs(out, exist_ok=True)
    groups = []                                   # [(engine, [line,...])]
    for l in S["lines"]:
        eng = "tc" if typecast_tts.is_typecast(P[S["cast"][l[0]]]["model_id"]) else "el"
        if eng == "el" and groups and groups[-1][0] == "el":
            groups[-1][1].append(l)
        else:
            groups.append((eng, [l]))
    meta = []
    for i, (eng, ls) in enumerate(groups):
        path = f"{out}/seg_{i:02d}.mp3"
        if eng == "tc":
            p = P[S["cast"][ls[0][0]]]
            typecast_tts.synthesize(typecast_tts.strip_v3_tags(ls[0][1]), path, voice_id=p["base_voice_id"], speed=1.0,
                                    emotion=p["voice_settings"].get("emotion"), intensity=p["voice_settings"].get("emotion_intensity"),
                                    model_id=p["model_id"])
        else:
            r = requests.post("https://api.elevenlabs.io/v1/text-to-dialogue",
                              headers={"xi-api-key": tts._api_key(0), "Content-Type": "application/json"},
                              json={"model_id": "eleven_v3", "inputs": [{"text": l[1], "voice_id": P[S["cast"][l[0]]]["base_voice_id"]} for l in ls]},
                              timeout=180)
            if r.status_code != 200:
                print("실패", S["name"], i, r.status_code, r.text[:200]); break
            open(path, "wb").write(r.content)
        meta.append({"file": os.path.basename(path), "engine": eng, "who": [l[0] for l in ls], "text": [l[1] for l in ls]})
    json.dump(meta, open(f"{out}/segs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(S["name"], len(meta), "조각", [m["engine"] for m in meta])
