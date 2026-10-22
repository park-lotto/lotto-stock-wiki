"""여행 숏폼 오프닝 '그림이 여행이 된다' 재료 그림 — 버텍스 gemini-2.5-flash-image(세로 9:16).

    py tools/travel/work_skybay/opening/gen_images.py [이름 ...]     (없으면 전부, 이미 있으면 건너뜀)

출력 = ~/숏템자료/모션그래픽엔진/work/2026-10-22_숙소_오프닝/img/
그림체 고정 블록(STYLE)을 모든 프롬프트 맨 앞에 똑같이 — 제작방법.md '그림체 기준판'.
같은 인물 유지 = 기본 그림(couple_color)을 넣고 "Keep the exact same two characters… Only change:" 편집(제작방법.md 실측: 위치·크기 거의 일치).
호텔 모양 = 공식 사진(두 타워가 꼭대기에서 이어진 건물)을 참고 그림으로 넣는다.
"""
import base64
import sys
import time
from pathlib import Path

import google.auth
import google.auth.transport.requests
import requests

HERE = Path(__file__).resolve().parent
OUT = Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-22_숙소_오프닝/img"
PHOTO = HERE.parent / "photos"

STYLE = ("Korean webtoon illustration, clean confident ink outlines, soft cel shading, warm natural light, "
         "attractive and tasteful, no text, no logo, no watermark. ")
PAPER = "on a plain warm cream sketch-paper background (#efebe3) with faint paper grain, nothing else in the background"
COUPLE = ("a stylish Korean couple in their early 30s on a weekend seaside trip: "
          "the woman has shoulder-length wavy dark brown hair, a white linen midi dress and a woven straw sun hat, small tan shoulder bag; "
          "the man has short neat black hair, a light sky-blue linen short-sleeve shirt, beige chino pants, white sneakers, "
          "a canvas weekender bag on his shoulder")
KEEP = ("Keep the exact same two characters (same faces, hair, outfits, colors, proportions and drawing style) and the same cream paper background. "
        "Only change: ")

JOBS = {
    "couple_color": (STYLE + COUPLE + ", standing side by side facing the viewer, smiling at each other, full body, "
                     "centered, their bodies occupy the middle 55% of the image height, feet at 78% height, " + PAPER, None),
    "couple_line": ("Convert this into a clean black ink line drawing only: confident pen outlines, no color, no shading, no fill, "
                    "same pose, same position and size, same cream paper background. No text.", "couple_color"),
    "couple_side": (KEEP + "they turn three-quarters away from the viewer toward the upper center, holding hands, the woman on the left and the man on the right, "
                    "looking at each other over the shoulder, full body at the same size and position. " + PAPER, "couple_color"),
    "couple_backA": (KEEP + "show them from behind walking away from the viewer holding hands, the woman on the left and the man on the right, "
                     "her left foot stepping forward, full body at the same size and position. " + PAPER, "couple_color"),
    "couple_backB": (KEEP + "show them from behind walking away from the viewer holding hands, the woman on the left and the man on the right, "
                     "her right foot stepping forward, full body at the same size and position. " + PAPER, "couple_color"),
    "bg_line": ("Loose but precise black ink perspective sketch on warm cream paper (#efebe3), vertical composition: "
                "a seaside promenade seen from the walkway, one-point perspective converging toward the upper center; "
                "the sea and a sandy beach on the left, a row of slim street lamps and a low railing along the promenade, "
                "and at the vanishing point a tall white hotel exactly like the reference photo: two tall towers joined at the very top by a "
                "horizontal bridge-like block with a rooftop infinity pool. Thin construction lines, no color, no shading fill, no people, no text.",
                "ref_hotel"),
    "bg_color": ("Paint this ink sketch with soft transparent watercolor in a warm sunset palette: lilac and peach sky with a pink-orange glow, "
                 "turquoise sea, golden sand, the white hotel catching warm light, its rooftop pool glowing aqua. "
                 "Keep every ink line, the composition and the perspective exactly the same. No people, no text.", "bg_line"),
}


def gen(name, prompt, ref):
    c, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    c.refresh(google.auth.transport.requests.Request())
    parts = []
    if ref:
        rp = PHOTO / "00.jpg" if ref == "ref_hotel" else OUT / (ref + ".png")
        mime = "image/jpeg" if rp.suffix == ".jpg" else "image/png"
        parts.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(rp.read_bytes()).decode()}})
    parts.append({"text": prompt})
    url = ("https://aiplatform.googleapis.com/v1/projects/%s/locations/global/publishers/google/models/"
           "gemini-2.5-flash-image:generateContent" % project)
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    for _ in range(8):
        r = requests.post(url, headers={"Authorization": "Bearer " + c.token}, json=body, timeout=300)
        if r.status_code == 429:       # 연달아 부르면 429 — 25~30초 쉬고 다시(제작방법.md 실측)
            time.sleep(28)
            continue
        if not r.ok:
            sys.exit("%s 실패 %s %s" % (name, r.status_code, r.text[:300]))
        for q in r.json()["candidates"][0]["content"].get("parts", []):
            if "inlineData" in q:
                (OUT / (name + ".png")).write_bytes(base64.b64decode(q["inlineData"]["data"]))
                print("ok", name, flush=True)
                return
        sys.exit("%s 그림 없음" % name)
    sys.exit("%s 429 8번" % name)


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for n in names or list(JOBS):
        if (OUT / (n + ".png")).exists():
            print("있음", n)
            continue
        gen(n, *JOBS[n])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
