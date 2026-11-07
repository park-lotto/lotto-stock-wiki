"""4회차 50대 주인공(o_*) 선화·컬러판 — gen_hero.py 와 같은 모델·문장 틀. 차이: 기준그림을 '그림체만' 참고(다른 사람)."""
import base64, os, sys, time, requests, google.auth, google.auth.transport.requests
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = ("Clean black ink line-art illustration, Korean webtoon style, realistic adult proportions, "
         "crisp thin uniform outlines, light hatching only on hair, NO color, NO grey fill, pure white background, "
         "upper body, centered with margin, single character, no text, no frame, no border. ")
STYLE_COLOR = "Clean Korean webtoon line-art illustration with soft flat coloring, pure white background, single character, no text. "
WHO = ("A Korean man in his mid-50s: round friendly face, short neatly combed salt-and-pepper grey hair, round thin-rimmed glasses, "
       "faint smile lines, slightly rounded build, wearing a plain collared button-up shirt with NO tie. ")
c, proj = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
c.refresh(google.auth.transport.requests.Request())
URL = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/global/publishers/google/models/gemini-2.5-flash-image:generateContent"


def call(name, text, ref):
    parts = [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(open(ref, "rb").read()).decode()}}, {"text": text}]
    for _ in range(20):
        r = requests.post(URL, headers={"Authorization": "Bearer " + c.token},
                          json={"contents": [{"role": "user", "parts": parts}],
                                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}}}, timeout=300)
        if r.status_code == 429:
            time.sleep(25); continue
        if not r.ok:
            return f"{name} 실패 {r.status_code} {r.text[:200]}"
        for q in ((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []:
            if "inlineData" in q:
                open(os.path.join(HERE, name + ".png"), "wb").write(base64.b64decode(q["inlineData"]["data"]))
                return "ok " + name
        time.sleep(5)
    return name + " 실패(재시도 소진)"


POSES = {
    "o_hope": "Standing, holding a smartphone in both hands at chest height and looking down at it with a gentle hopeful smile.",
    "o_laptop_blank": "Sitting behind an open laptop on a desk (laptop seen from behind, screen facing him), one hand scratching the back of his head, puzzled confused look, not holding a phone.",
    "o_phone_wow": "Standing, holding a smartphone in one hand, other hand in a small excited fist, eyes wide with surprise and excitement looking at the phone.",
    "o_laptop_tired": "Sitting behind an open laptop on a desk (laptop seen from behind, the laptop lid drawn with outline only, white and unfilled, no black fill), shoulders slumped, exhausted tired face, eyes half closed, not holding a phone.",
    "o_frustr_head": "Standing, both hands holding his head in frustration, eyes closed, troubled expression, not holding a phone.",
    "o_point_hope": "Standing, not holding a phone, right arm extended to the right side pointing with index finger at something off-frame, left arm relaxed, confident hopeful smile, eyes looking toward the pointing direction.",
}
COLOR = ("Keep every black line of the reference exactly as it is, same pose, same framing, same size. Add only soft flat watercolor-style coloring "
         "with no gradients: skin #F2C9B8, hair grey #9A958F, shirt pale blue #CFDDEA with faint blue-grey #B9C7D4 fold shadows only, glasses frame dark, "
         "laptop or furniture sand #E9DCC6. Pure white background, no new lines, no new objects, no outlines thicker, no text.")

if __name__ == "__main__":
    mode = sys.argv[1]
    names = sys.argv[2:] or list(POSES)
    if mode == "base":      # 첫 장: 그림체만 참고, 다른 사람
        print(call("g_o_hope", STYLE + "Use the reference image ONLY for drawing style, line weight and framing. Draw a DIFFERENT person. " + WHO + POSES["o_hope"], os.path.join(HERE, "style_ref.png")))
    elif mode == "poses":   # 나머지: 첫 장을 기준그림으로 같은 사람
        jobs = [(f"g_{n}", STYLE + "Same person as the reference image: identical face, glasses, hairstyle and clothes. " + POSES[n], os.path.join(HERE, "g_o_hope.png")) for n in names if n != "o_hope"]
        with ThreadPoolExecutor(2) as ex:
            for r in ex.map(lambda a: call(*a), jobs): print(r)
    elif mode == "color":
        jobs = [(f"c_{n}", STYLE_COLOR + COLOR.replace(", laptop or furniture sand #E9DCC6", "" if "laptop" in n else "").replace("laptop or furniture sand #E9DCC6", "laptop or furniture sand #E9DCC6"), os.path.join(HERE, f"g_{n}.png")) for n in names]
        with ThreadPoolExecutor(2) as ex:
            for r in ex.map(lambda a: call(*a), jobs): print(r)
