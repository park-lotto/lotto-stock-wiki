"""
젠슨황 방한 영상 — 씬별 이미지 생성 (Gemini 2.0 Flash)
레퍼런스: public/images/jh/ref_*.jpeg
출력: public/images/jh/gen_*.jpeg
"""

import os, base64, json, urllib.request, urllib.error
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyBnXfHkFh5YCOZdHYmKwqWXwVh7mrtF7U0"
BASE = Path(__file__).parent.parent / "remotion-stock/public/images/jh"
BASE.mkdir(parents=True, exist_ok=True)

def read_img_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def generate(scene_id, prompt, ref_paths):
    print(f"\n[씬{scene_id}] 생성 중...")

    parts = []
    for rp in ref_paths:
        p = BASE / rp
        if p.exists():
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": read_img_b64(p)
                }
            })
    parts.append({"text": prompt})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
    }).encode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={API_KEY}"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP 오류 {e.code}: {e.read().decode()}")
        return
    except Exception as e:
        print(f"  오류: {e}")
        return

    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            img_data = base64.b64decode(part["inlineData"]["data"])
            out = BASE / f"gen_s{scene_id:02d}.jpeg"
            out.write_bytes(img_data)
            print(f"  저장: {out.name} ({len(img_data)//1024}KB)")
            return
    print("  이미지 데이터 없음")


SCENES = [
    (
        1,
        "A man in a black leather jacket standing on a dark keynote stage with dramatic spotlight. Arms spread wide. Server racks in background glowing blue. Cinematic, photorealistic.",
        ["ref_jensen.jpeg"]
    ),
    (
        2,
        "Three Korean businessmen in suits sitting around a round Korean BBQ grill table at night. Meat grilling on charcoal. Seoul neon signs visible through rainy window. Warm Edison bulb lighting. Vintage industrial restaurant interior. Cinematic.",
        ["ref_leejy.jpeg", "ref_jungus.jpeg", "ref_jensen.jpeg"]
    ),
    (
        3,
        "Korean stock market chart on dark screen. Sharp red candlestick surge going up dramatically. Numbers glowing. Dark cinematic background. Financial data visualization.",
        []
    ),
    (
        4,
        "Futuristic humanoid robot in factory or lab environment. Cinematic dramatic lighting. Physical AI concept. Dark background with teal accent light.",
        []
    ),
    (
        5,
        "Seoul city aerial night view. Stock index numbers floating as light overlay. Golden hour. Cinematic wide shot.",
        []
    ),
]

for scene_id, prompt, refs in SCENES:
    generate(scene_id, prompt, refs)

print("\n완료!")
