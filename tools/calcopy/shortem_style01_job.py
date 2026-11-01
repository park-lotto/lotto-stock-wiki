"""칼카피 대본을 라이브 숏템메이커(관리자 작업)로 — 고정 스타일 01(fixed_s0034, 전장면고정형) **기본값** 그대로.
틀·폰트·자막·짤·효과음·배경음은 전부 숏템 엔진 주인 함수가 정한다(여기선 작업만 만든다).
서버에서: python3 /tmp/shortem_style01_job.py <대본.json> <소스작업id>   (소스작업 = 유튜브 소스 주소·목소리를 빌려 올 작업)
"""
import sys, json, uuid
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import config

scr = json.load(open(sys.argv[1], encoding="utf-8"))
src_id = sys.argv[2]
hook1, hook2 = sys.argv[3], sys.argv[4]
st = Store(config.DB_PATH)
src = st.get_mix_job(src_id)
script = "\n".join([" ".join(scr["title"].split())] +   # 제목에 줄바꿈이 있으면 나레 두 줄로 쪼개진다(735682f308a2 실측)
[L["text"] for L in scr["lines"]])
# ★다른 작업의 장면꾸미기 손질(폰트·워터마크·배지·자막 위치)을 복사하지 않는다 — 화면 기본값(precision20-ui.js snapshot)과 같은 모양만
style = {"version": 1, "mode": "continuous", "presetId": "fixed_s0034", "sceneIndex": 0, "frameKind": "frame",
         "hookMotion": "pop", "hookBandMotion": "", "bodyCaptionMotion": "", "fontSet": "", "fontSets": {},
         "titleDeco": "", "hookMotionSpeed": 0.72, "hookCaptionMode": "visible",
         "text": {"channel": "숏템메이커", "hook1": hook1, "hook2": hook2, "bodyTitle": scr["title"], "caption": ""}}
deco = {"extra_texts": [], "motion": None, "sfx_pack": "auto", "bgm": {"lib": "qiuqiu", "volume": 15},
        "watermark": None, "scene_style": style}
new = uuid.uuid4().hex[:12]
st.create_mix_job(new, src.get("urls") or [], src.get("target_seconds") or 27, "free",
                  subtitle_removal=False, given_script=script, customer_id=0)
st.update_mix_job(new, voice=src.get("voice"), deco=deco, caption_style=src.get("caption_style"),
                  headcopy=src.get("headcopy"))
st.enqueue("mix", {"job_id": new})
print("NEW", new)
print(script)
