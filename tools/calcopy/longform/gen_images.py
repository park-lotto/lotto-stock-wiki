# shots.py 의 AI 장면을 gpt-image(Codex 내장 이미지 생성)로 만든다.
# 사용: python -I gen_images.py [ai|stock-fallback] [동시개수]
import os, sys, subprocess, time, concurrent.futures as cf, importlib.util, glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("shots", os.path.join(HERE, "shots.py")); sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
MODE = sys.argv[1] if len(sys.argv) > 1 else "ai"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
OUT = os.path.join(HERE, "assets", "img"); os.makedirs(OUT, exist_ok=True)
STYLE = " Photorealistic documentary photograph, natural lighting, slightly desaturated, 16:9 landscape 1536x864. No text, no letters, no logos, no watermarks in the image."

jobs = []
for k, s in enumerate(sh.S):
    if "img" in s: continue  # 다른 샷 그림을 다시 씀
    if MODE == "ai" and s["type"] == "ai":
        jobs.append((f"s{s['s'][0]:03d}", s["prompt"]))
    elif MODE == "stock-fallback":
        if s["type"] == "stock": jobs.append((f"s{s['s'][0]:03d}", s["ai"]))
        elif "bg_ai" in s: jobs.append((f"s{s['s'][0]:03d}", s["bg_ai"]))

def run(job):
    name, prompt = job
    png = os.path.join(OUT, name + ".png")
    if os.path.exists(png): return name, "skip"
    p = prompt.replace("'", "") + STYLE
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write",
           f"$imagegen 내장 이미지 생성 도구로만 그린다. 코드·SVG·PIL로 그리지 않고 이 작업 외의 파일은 만들거나 고치지 않는다. 그림: {p}. 그림을 한 장 만든 뒤 바로 끝낸다. 파일 복사는 하지 않아도 된다(읽기 전용이어도 괜찮다). 이미지 생성 도구 자체가 아예 없을 때만 마지막 줄에 IMAGEGEN_UNAVAILABLE 을 쓴다."]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=OUT, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, shell=(os.name == "nt"))
    if os.path.exists(png): return name, f"ok {time.time()-t0:.0f}s"
    out = (r.stdout or "") + (r.stderr or "")
    # 이 실행의 세션 폴더에서만 가져온다(동시 실행 때 섞이지 않게)
    import re, shutil
    m = re.search(r"session id:\s*([0-9a-f-]{36})", out)
    if m:
        gen = sorted(glob.glob(os.path.expanduser(f"~/.codex/generated_images/{m[1]}/*.png")), key=os.path.getmtime)
        if gen: shutil.copy(gen[-1], png); return name, f"ok(session) {time.time()-t0:.0f}s"
        return name, "fail: 세션 폴더에 그림 없음 " + m[1]
    if "IMAGEGEN_UNAVAILABLE" in out: return name, "UNAVAILABLE"
    return name, "fail: 세션 ID 못 찾음 " + out[-200:]

with cf.ThreadPoolExecutor(N) as ex:
    for name, r in ex.map(run, jobs):
        print(name, r, flush=True)

