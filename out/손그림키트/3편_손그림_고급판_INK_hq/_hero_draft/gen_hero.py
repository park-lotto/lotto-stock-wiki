"""레퍼런스(ink_explainer, 혼자스 스타일) 그림체로 우리 주인공을 버텍스 그림 모델로 만든다 → trace.py 로 펜 획 추출.
쓰기: py gen_hero.py <이름> "<인물·포즈·표정 설명>" [기준그림.png] [--color]
--color = 컬러판(STYLE 의 "NO color" 머리말 대신 STYLE_COLOR, 기준그림=흑백 선화)
기준그림을 주면 같은 인물로 표정·포즈만 바꾼다(일관성). 사장님 10-29 버텍스 사용 승인.
"""
import base64, os, sys, time
import requests, google.auth, google.auth.transport.requests

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = ("Clean black ink line-art illustration, Korean webtoon style, realistic adult proportions, "
         "crisp thin uniform outlines, light hatching only on hair, NO color, NO grey fill, pure white background, "
         "upper body, centered with margin, single character, no text, no frame, no border. ")
STYLE_COLOR = ("Clean Korean webtoon line-art illustration with soft flat coloring, pure white background, "
               "single character, no text. ")
c, proj = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
c.refresh(google.auth.transport.requests.Request())
URL = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/global/publishers/google/models/gemini-2.5-flash-image:generateContent"


def gen(name, desc, ref=None, ar="1:1", color=False):
    parts = []
    if ref:
        parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(open(ref, "rb").read()).decode()}})
        if not color:
            desc = "Same person as the reference image: identical face, hairstyle and clothes. " + desc
    parts.append({"text": (STYLE_COLOR if color else STYLE) + desc})
    for _ in range(20):
        r = requests.post(URL, headers={"Authorization": "Bearer " + c.token},
                          json={"contents": [{"role": "user", "parts": parts}],
                                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ar}}}, timeout=300)
        if r.status_code == 429:
            time.sleep(25); continue
        if not r.ok:
            sys.exit(f"{name} {r.status_code} {r.text[:300]}")
        cand = (r.json().get("candidates") or [{}])[0]
        for q in (cand.get("content") or {}).get("parts") or []:
            if "inlineData" in q:
                out = os.path.join(HERE, name + ".png")
                open(out, "wb").write(base64.b64decode(q["inlineData"]["data"]))
                print("ok", out)
                return
        print(name, "그림 없음 — 다시 시도", cand.get("finishReason"), file=sys.stderr)   # 빈 응답(parts 없음)은 재시도
    sys.exit(f"{name} 그림 없음(20회)")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--color"]
    gen(a[0], a[1], a[2] if len(a) > 2 else None, color="--color" in sys.argv)
