# shots.py 의 AI 장면·실사 대체 그림 → assets/img/sNNN.png
# 사용: 작업 폴더에서 python -X utf8 <경로>/gen_images.py [동시개수]
# 그리는 곳은 SHORCL_IMAGE_ENGINE 하나로 고른다: codex(기본, 코덱스 구독) | gemini(고객 제미나이 키) .
# gemini 일 때 SHORCL_VERTEX=<프로젝트> 면 그 버텍스 프로젝트로 만든다(gcloud 로그인 필요).
import concurrent.futures as cf, importlib.util, os, re, shutil, subprocess, sys, time, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WORK = os.path.abspath(os.environ.get("SHORCL_WORK") or os.getcwd())
OUT = os.path.join(WORK, "material", "img"); os.makedirs(OUT, exist_ok=True)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
MODEL = os.environ.get("SHORCL_IMAGE_MODEL") or "gemini-3.1-flash-lite-image"
VERTEX = os.environ.get("SHORCL_VERTEX", "")
STYLE = " Photorealistic documentary photograph, natural lighting, slightly desaturated. No text, no letters, no logos, no watermarks."
spec = importlib.util.spec_from_file_location("shots", os.path.join(WORK, "장면표.py")); sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)

jobs = []
for s in sh.S:
    if "img" in s: continue  # 다른 샷 그림을 다시 쓴다
    if os.path.exists(os.path.join(WORK, "material", "video", f"s{s['s'][0]:03d}.mp4")): continue  # 실사를 받은 칸은 그리지 않는다
    p = s.get("prompt") or s.get("ai") or s.get("bg_ai")
    if p: jobs.append((f"s{s['s'][0]:03d}", p))
if os.environ.get("SHORCL_IMAGE_REVERSE"): jobs.reverse()   # 다른 모델로 뒤에서부터 같이 채울 때
ENGINE = os.environ.get("SHORCL_IMAGE_ENGINE") or "codex"
if ENGINE not in ("codex", "gemini"): sys.exit(f"없는 그림 엔진: {ENGINE}")
SAVED = re.compile(r"[A-Za-z]:[^\s`'\"]*generated_images[^\s`'\"]*?\.png", re.I)
if ENGINE == "gemini":
    import keys
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=VERTEX, location="global") if VERTEX else genai.Client(api_key=keys.get("gemini"))


def ask_gemini(prompt, png):
    r = client.models.generate_content(model=MODEL, contents=prompt + STYLE, config=types.GenerateContentConfig(
        response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="16:9")))
    for part in r.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            open(png, "wb").write(part.inline_data.data)
            return ""
    return "빈 답(안전 필터일 수 있음)"


def ask_codex(prompt, png):
    """코덱스 내장 그림 도구로 그리고, 코덱스가 저장한 파일을 받아 온다."""
    ask = f"Use your built-in image generation tool once to make one 16:9 landscape image: {prompt}{STYLE} Do not edit any files. When done, print only the full path of the generated image."
    r = subprocess.run([shutil.which("codex") or "codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"], input=ask, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    log = r.stdout + r.stderr; found = SAVED.findall(log)
    if not found or not os.path.exists(found[-1]): return "코덱스가 그림을 남기지 않음: " + " ".join(log.split())[-160:]
    shutil.copyfile(found[-1], png); return ""


def run(job):
    name, prompt = job
    png = os.path.join(OUT, name + ".png")
    if os.path.exists(png): return name, "skip"
    msg = ""
    for k in range(6):
        try:
            t0 = time.time()
            msg = (ask_codex if ENGINE == "codex" else ask_gemini)(prompt, png)
            if not msg: return name, f"ok {time.time() - t0:.0f}s"
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
