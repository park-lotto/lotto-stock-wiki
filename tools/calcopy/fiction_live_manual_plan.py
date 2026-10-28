import sys, json, collections
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import config
J = "15755fec2ddb"
st = Store(config.DB_PATH); j = st.get_mix_job(J); p = j["edit_plan"]
segs = {s["seg_id"]: dict(video_id=k, seg_id=s["seg_id"], start=s["start"], end=s["end"], scene_desc=s.get("scene_desc") or "")
        for k, v in j["extract"].items() if isinstance(v, dict) for s in v.get("segments") or [] if s.get("seg_id")}
TONE = {413: "의심_황당", 163: "놀람", 607: "충격_입막", 604: "충격_입막"}
def meme(aid, head):
    return {"asset_id": aid, "match_type": "meme", "head_sec": head, "vid": "meme_%d" % aid, "emotion": TONE[aid],
            "scene_min": 0.6, "owner": 0, "manual": 1}
def cuts(*ids): return [segs[i] for i in ids]
Y = "grab_youtube_"; T = "grab_tiktok_"
v = dict(j.get("voice") or {})
def vo(vid, emo=None, inten=1.0):
    d = json.loads(json.dumps(v)); d.update({"voice_id": vid, "preset_id": None, "speed": 1.15})
    d["settings"] = {"emotion": emo or "normal", "emotion_intensity": inten}; return d
angry = vo("tc_5feb2085cca1a479e73bac37", "angry", 1.3)      # 사장(윗선) — 용식이
staff = vo("tc_61c2f7741330d213c238cba6")                    # 개발팀(실무자) — 김건
B = [
 ("hook", "면도기 개발팀이 사장님 경악하게 만든 사연", cuts(Y+"6d2c6d8a555e-0", Y+"280e5f623bb5-0"), None, None),
 ("setup", "한 소형가전 브랜드에서 평범하게 쓰기 좋은 면도기나 만들라 했더니", cuts(Y+"dd54ae37a5f6-7", Y+"6d2c6d8a555e-1"), None, None),
 ("escalation", "개발팀이 수조 속에 푹 담가도 멀쩡한 완전 방수를 박아버리더니", cuts(Y+"6d2c6d8a555e-2", Y+"dd54ae37a5f6-26", T+"457cd095e3f4-12"), None, None),
 ("escalation", "손으로 누르면 턱선 라인 따라 좌우로 꺾이는 미친 헤드까지 달아버린 거임", cuts(Y+"280e5f623bb5-2", Y+"6d2c6d8a555e-10"), None, None),
 ("limit", "이렇게 날카롭게 만들었다가 고객들 피부 베여서 피 보면 어쩌려고 그래?", cuts(Y+"dd54ae37a5f6-8", Y+"dd54ae37a5f6-3"), meme(413, 2.0), angry),
 ("limit", "사장님이 식은땀 흘리며 말리자", cuts(Y+"6d2c6d8a555e-5"), meme(163, 1.1), None),
 ("solve", "턱에 바짝 밀어도 상처 안 나게 이중보호 시스템으로 막아놨는데요?", cuts(Y+"dd54ae37a5f6-22", Y+"dd54ae37a5f6-23", T+"457cd095e3f4-8"), None, staff),
 ("solve", "라며 뻔뻔하게 받아쳤다는 거", cuts(Y+"57db523c65c6-8"), meme(607, 1.0), None),
 ("twist", "근데 진짜 소름 돋는 건 쉐이빙 크림 하나 안 바른 건조한 맨살에 대고 슥 밀어도 미끄러지듯 깎인다고", cuts(Y+"51d3b4268b65-1", Y+"e3aca2e3b05e-1", Y+"57db523c65c6-6"), meme(604, 1.5), None),
]
beats = []
for i, (role, narr, sc, mm, vo) in enumerate(B):
    b = {"beat_idx": i, "role": role, "narration": narr, "primary": sc[0], "alternates": sc[1:], "scene_override": sc, "pinned": True}
    if mm: b["cutaway"] = mm
    if vo: b["voice_override"] = vo
    beats.append(b)
p["beats"] = beats
u = [x["seg_id"] for b in beats for x in b["scene_override"]]
print("컷", len(u), "중복", len(u) - len(set(u)), collections.Counter(x.rsplit("-", 1)[0] for x in u).most_common(2))
st.update_mix_job(J, edit_plan=p)
