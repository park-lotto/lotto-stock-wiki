"""대화형 샘플 A/B — 일레븐랩스 사장님 키(customer_id=0)로 줄마다 합성. 결과는 /tmp/tiki2/raw 에만 쓴다.
서버에서: sudo bash -c 'set -a; . /etc/shopping-shorts.env; set +a; cd /tmp/tiki2 && python3 /tmp/gen11.py'
(코드·DB 안 건드림. tts 사용 기록 한 줄만 남는다)"""
import json, os, sys
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts import tts
P = {p["preset_id"]: p for p in json.load(open("/home/ubuntu/lotto-stock-wiki/shopping_shorts/assets/voice_presets.json", encoding="utf-8"))}
CAST = {"나레이션": "kr-mina-natural", "언니": "kr-kanna-natural", "동생": "kr-yura-natural"}
A = [("동생", "언니 요거트 매일 사 먹어? 그거 비싸잖아."), ("언니", "사 먹긴. 만들어 먹지."),
     ("동생", "면포로 짜는 거? 그거 귀찮아서 난 못 해."), ("언니", "이거 부어 놓고 냉장고에 넣으면 끝이야."),
     ("동생", "그럼 통에 덕지덕지 붙는 건?"), ("언니", "뒤집으면 덩어리째 쏙 빠져."),
     ("동생", "아 나도 살래. 어디 거야?"), ("언니", "댓글에 요거트 남기면 알려줄게.")]
B = [("나레이션", "요거트 매일 사 먹던 언니가 갑자기 안 사기 시작했는데요."), ("언니", "사 먹긴 왜 사 먹어. 이거 부어 놓으면 끝인데."),
     ("나레이션", "면포에 짜고 그릇 올리던 걸 이게 알아서 해 준다는 거예요."), ("나레이션", "다 만들고 뒤집으면 덩어리째 쏙 빠지고요."),
     ("언니", "이거 산 뒤로 요거트 한 번도 안 샀어."), ("나레이션", "댓글에 요거트 남겨주시면 정보 보내드릴게요.")]
os.makedirs("/tmp/tiki2/raw", exist_ok=True)
plan = {"A_묻고답하기": A, "B_나레이션+언니한마디": B}
done = {}
for name, seq in plan.items():
    for i, (who, text) in enumerate(seq):
        p = P[CAST[who]]
        out = f"/tmp/tiki2/raw/{name}_{i:02d}_{who}.mp3"
        if not os.path.exists(out):
            tts.synthesize_tts(text, out, voice_id=p["base_voice_id"], voice_settings=p["voice_settings"],
                               speed=1.2, model_id=p["model_id"], customer_id=0)
        done.setdefault(name, []).append({"who": who, "text": text, "file": os.path.basename(out), "size": os.path.getsize(out)})
json.dump({"cast": CAST, "plan": done}, open("/tmp/tiki2/plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: [d["size"] for d in v] for k, v in done.items()})
