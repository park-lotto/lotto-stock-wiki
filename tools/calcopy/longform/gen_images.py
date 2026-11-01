# shots.py 의 AI 장면·실사 대체 그림 → assets/img/sNNN.png
# 사용: 작업 폴더에서 python -X utf8 <경로>/gen_images.py [동시개수]
# 고객 제미나이 키를 쓴다. LONGFORM_VERTEX=<프로젝트> 면 그 버텍스 프로젝트로 만든다(gcloud 로그인 필요).
import concurrent.futures as cf, importlib.util, os, sys, time, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys
from google import genai
from google.genai import types

WORK = os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd())
OUT = os.path.join(WORK, "assets", "img"); os.makedirs(OUT, exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
MODEL = os.environ.get("LONGFORM_IMAGE_MODEL") or "gemini-3.1-flash-lite-image"
VERTEX = os.environ.get("LONGFORM_VERTEX", "")
STYLE = " Photorealistic documentary photograph, natural lighting, slightly desaturated. No text, no letters, no logos, no watermarks."
spec = importlib.util.spec_from_file_location("shots", os.path.join(WORK, "shots.py")); sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)

jobs = []
for s in sh.S:
    if "img" in s: continue  # 다른 샷 그림을 다시 쓴다
    if os.path.exists(os.path.join(WORK, "assets", "stock", f"s{s['s'][0]:03d}.mp4")): continue  # 실사를 받은 칸은 그리지 않는다
    p = s.get("prompt") or s.get("ai") or s.get("bg_ai")
    if p: jobs.append((f"s{s['s'][0]:03d}", p))
if os.environ.get("LONGFORM_IMAGE_REVERSE"): jobs.reverse()   # 다른 모델로 뒤에서부터 같이 채울 때
client = genai.Client(vertexai=True, project=VERTEX, location="global") if VERTEX else genai.Client(api_key=keys.get("gemini"))


def run(job):
    name, prompt = job
    png = os.path.join(OUT, name + ".png")
    if os.path.exists(png): return name, "skip"
    msg = ""
    for k in range(6):
        try:
            t0 = time.time()
            r = client.models.generate_content(model=MODEL, contents=prompt + STYLE, config=types.GenerateContentConfig(
                response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="16:9")))
            for part in r.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    open(png, "wb").write(part.inline_data.data)
                    return name, f"ok {time.time() - t0:.0f}s"
            msg = "빈 답(안전 필터일 수 있음)"
        except Exception as e:  # noqa: BLE001 — 한도·일시 오류는 잠깐 뒤 다시
            msg = str(e)[:160]
            if "429" in msg: time.sleep(30 + k * 15)   # 분당 한도 — 짧게 재시도하면 계속 걸린다
        time.sleep(3 + k * 5)
    return name, "fail " + msg


print(f"그림 {len(jobs)}장", flush=True)
bad = 0
with cf.ThreadPoolExecutor(N) as ex:
    for name, r in ex.map(run, jobs):
        if not r.startswith(("ok", "skip")):
            bad += 1; print(name, r, flush=True)
print("실패", bad)
sys.exit(1 if bad else 0)
