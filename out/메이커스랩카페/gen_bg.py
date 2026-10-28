import sys, os; sys.path.insert(0, r"C:\Users\CH\Desktop\로또의 주식"); sys.stdout.reconfigure(encoding="utf-8")
import warnings; warnings.filterwarnings("ignore")
from concurrent.futures import ThreadPoolExecutor
from google.genai import types
from shopping_shorts import vertex_route
D = os.path.dirname(os.path.abspath(__file__))
cl = vertex_route.client(cid=0)
BASE = ("Ultra premium tech brand key visual, deep midnight navy to black background, "
        "subtle film grain, soft volumetric light, glassmorphism, cinematic, Apple-keynote quality, "
        "absolutely no text, no letters, no logos, no numbers, no watermark. ")
JOBS = {
 "bg_title": ("21:9", BASE + "Wide banner. Left side mostly empty dark space for headline. On the right, two floating "
              "glossy glass vertical smartphone screens playing short-form videos, one glowing warm amber gold, one glowing electric violet-cyan, "
              "thin light trails connecting them."),
 "bg_gate":  ("9:16", BASE + "Tall vertical poster. Top third: empty dark space with faint aurora glow. Middle: two large frosted glass "
              "cards side by side, left card rim-lit warm amber gold, right card rim-lit electric violet-cyan, cards are EMPTY blank. "
              "Bottom third: calm dark gradient space, empty."),
 "bg_icon":  ("1:1", BASE + "Square app icon background. Centered abstract glossy 3D glass emblem made of two interlocking rounded "
              "shapes, one amber gold and one violet-cyan, on deep navy. Minimal, iconic."),
}
def run(item):
    name, (ar, prompt) = item
    r = cl.models.generate_content(model="gemini-3-pro-image", contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=ar)))
    for p in r.candidates[0].content.parts:
        if getattr(p, "inline_data", None) and p.inline_data.data:
            open(os.path.join(D, name + ".png"), "wb").write(p.inline_data.data); return name, "OK"
    return name, "이미지 없음"
import time
for it in [i for i in JOBS.items() if not os.path.exists(os.path.join(D, i[0] + ".png"))]:
    for k in range(4):
        try: print(run(it)); break
        except Exception as e: print("재시도", k, str(e)[:60]); time.sleep(20)
if 0:
    for n, s in ex.map(run, JOBS.items()): print(n, s)
