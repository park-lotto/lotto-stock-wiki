"""대화 샘플 2차 — 말투가 어색한 원인 가르기(2026-10-05 사장님 "말투가 왜 이렇게 어색해?").

1차(gen11)는 **줄마다 따로** 합성했다. eleven_v3는 앞뒤 문맥(previous_text)을 안 받으므로(tts.py가 v3면 뺀다)
줄마다 '혼자 읽는' 억양이 된다 — 묻고 답하는 주고받기 억양이 없다. 이걸 가르려고 세 판을 만든다.
  V1 같은 대사 · 대화 API(/v1/text-to-dialogue) 한 번에 → 문맥 효과만
  V2 말로 하는 대사(구어 어미·말줄임) · 대화 API → 대본 문체 효과
  V3 V2 + v3 감정 태그([curious] 등) · 대화 API → 연기 지시 효과
서버에서: sudo bash -c 'set -a; . /etc/shopping-shorts.env; set +a; cd /tmp/tiki2 && python3 /tmp/gen_dialogue.py'
결과는 /tmp/tiki2/dlg/*.mp3 에만 쓴다(코드·DB 안 건드림)."""
import json, os, sys, requests
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import tts
P = {p["preset_id"]: p for p in json.load(open("/home/ubuntu/lotto-stock-wiki/shopping_shorts/assets/voice_presets.json", encoding="utf-8"))}
VID = {"동생": P["kr-yura-natural"]["base_voice_id"], "언니": P["kr-kanna-natural"]["base_voice_id"]}
V1 = [("동생", "언니 요거트 매일 사 먹어? 그거 비싸잖아."), ("언니", "사 먹긴. 만들어 먹지."),
      ("동생", "면포로 짜는 거? 그거 귀찮아서 난 못 해."), ("언니", "이거 부어 놓고 냉장고에 넣으면 끝이야."),
      ("동생", "그럼 통에 덕지덕지 붙는 건?"), ("언니", "뒤집으면 덩어리째 쏙 빠져."),
      ("동생", "아 나도 살래. 어디 거야?"), ("언니", "댓글에 요거트 남기면 알려줄게.")]
V2 = [("동생", "언니는 요거트 맨날 사 먹어? 그거 은근 비싸잖아."), ("언니", "사 먹긴 뭘 사 먹어~ 그냥 만들어 먹지."),
      ("동생", "아 면포로 짜는 거? 난 그거 귀찮아서 못 하겠던데."), ("언니", "아니 아니, 이거 그냥 부어 놓고 냉장고에 넣으면 끝이야."),
      ("동생", "근데 통에 막 덕지덕지 붙지 않아?"), ("언니", "뒤집으면 덩어리째 쏙 빠져. 봐 봐."),
      ("동생", "헐 나도 살래. 이거 어디 거야?"), ("언니", "댓글에 요거트 남기면 알려 줄게.")]
TAG = ["[curious]", "[laughs]", "[skeptical]", "[casual]", "[doubtful]", "[cheerful]", "[excited]", "[friendly]"]
V3 = [(w, f"{TAG[i]} {t}") for i, (w, t) in enumerate(V2)]
key = tts._api_key(0)
os.makedirs("/tmp/tiki2/dlg", exist_ok=True)
for name, seq in {"V1_같은대사_대화API": V1, "V2_구어대사_대화API": V2, "V3_구어+감정태그": V3}.items():
    out = f"/tmp/tiki2/dlg/{name}.mp3"
    if os.path.exists(out):
        continue
    r = requests.post("https://api.elevenlabs.io/v1/text-to-dialogue",
                      headers={"xi-api-key": key, "Content-Type": "application/json"},
                      json={"model_id": "eleven_v3", "inputs": [{"text": t, "voice_id": VID[w]} for w, t in seq]},
                      timeout=180)
    if r.status_code != 200:
        print(name, "실패", r.status_code, r.text[:200]); continue
    open(out, "wb").write(r.content)
    print(name, len(r.content), "bytes")
json.dump({"V1": V1, "V2": V2, "V3": V3}, open("/tmp/tiki2/dlg/scripts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
