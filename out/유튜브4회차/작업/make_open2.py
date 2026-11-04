"""4회차 오프닝 v2 (사장님 11-04): '외국인 한국화장품 영상 만들어줘..' 타이핑 → 숏클 13단계 8배속 → ▶ 클릭 → 완성 쇼츠 원음 그대로 끝까지
→ 필재 나레이션 '방금 보신 거…'(훅 s00) + 문장마다 바뀌는 화면.
음악 = Mixkit 무료곡 'Tech House vibes'(Jev 1순위, 곡 선택 신뢰 0.18 — 사장님 귀로 확정 필요). 쇼츠 구간은 음악 없음."""
import json, shutil, subprocess, sys, random
from pathlib import Path
from playwright.sync_api import sync_playwright

W = Path(__file__).resolve().parent
A = W.parents[2] / "shopping_shorts" / "assets" / "sfx_packs"
FPS = 30
SHORT = W / "src" / "tattoo.mp4"
VOICE = W / "voice" / "s00_v6.mp3"
BGM = W / "music" / "mixkit_130_tech_house_vibes.mp3"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        sys.stderr.write(r.stderr.decode("utf-8", "replace")[-1500:]); raise SystemExit("실패")


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def frames(html, end, key, out):
    fd = W / "frames" / out.stem
    if fd.exists(): shutil.rmtree(fd)
    fd.mkdir(parents=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1536, "height": 864}, device_scale_factor=1.25)
        pg.goto((W / html).as_uri()); pg.wait_for_timeout(600)
        TL = pg.evaluate(f"window.{key}")
        n = int((TL["END"] if end is None else end) * FPS)
        for i in range(n):
            pg.evaluate(f"render({i / FPS})")
            pg.screenshot(path=str(fd / f"{i:04d}.jpg"), type="jpeg", quality=92)
        b.close()
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"), "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
    return TL


def mix(events, length, out, beds=()):
    """events = [(시각, 파일, 볼륨)] / beds = [(파일, 시작초, 길이, 볼륨식, 페이드인, 페이드아웃)]"""
    inp, fl, k = [], [], 0
    for t, f, v in events:
        inp += ["-i", str(f)]; fl.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={v:.2f},adelay={int(t * 1000)}:all=1[a{k}]"); k += 1
    for f, ss, ln, vol, fi, fo in beds:
        inp += ["-ss", f"{ss:.3f}", "-t", f"{ln:.3f}", "-i", str(f)]
        fl.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume='{vol}':eval=frame,afade=t=in:d={fi},afade=t=out:st={ln - fo:.3f}:d={fo}[a{k}]"); k += 1
    fl.append("".join(f"[a{i}]" for i in range(k)) + f"amix=inputs={k}:normalize=0,apad,atrim=0:{length:.3f}[out]")
    run(["ffmpeg", "-y", "-v", "error", *inp, "-filter_complex", ";".join(fl), "-map", "[out]", str(out)])


def main():
    seg = W / "seg"; seg.mkdir(exist_ok=True)
    # 1) 클로드 창 + 8배속
    ui = seg / "o2_ui.mp4"
    only_hook = "hook" in sys.argv[1:]  # 나레이션 화면만 다시 — 앞 두 구간은 저장본 그대로
    ua = seg / "o2_ui.wav"; sh = seg / "o2_short.mp4"
    if only_hook:
        L, sl = dur(ui), dur(sh.with_suffix(".mkv"))
    else:
        L, sl = build_front(seg, ui, ua, sh)
    _hook_and_join(seg, ui, ua, sh, L, sl)


def build_front(seg, ui, ua, sh):
    TL = frames("claude_ui2.html", None, "TL", ui)
    R = random.Random(3)
    keys = []
    for pk in ("팩01", "팩02", "팩03"):
        for j, rate in enumerate((0.92, 1.0, 1.09)):
            kf = W / f"key_{pk}_{j}.wav"
            run(["ffmpeg", "-y", "-v", "error", "-i", str(A / pk / "tick.wav"), "-af",
                 f"aresample=48000,asetrate={int(48000 * rate)},aresample=48000,atrim=0:0.08,afade=t=out:st=0.05:d=0.03", str(kf)])
            keys.append(kf)
    ev, last = [], -1
    for t in TL["KEYS"]:
        k = R.randrange(len(keys)); k = (k + 1) % len(keys) if k == last else k; last = k
        ev.append((t + R.uniform(-0.008, 0.008), keys[k], R.uniform(0.7, 1.0)))
    ev += [(TL["SEND"], keys[4], 1.0), (TL["SEND"] + 0.03, W / "sfx" / "05_톡.mp3", 0.9),
           (TL["FF"] - 0.15, A / "팩01" / "whoosh.wav", 0.8)]
    for i in range(TL["N"]):
        s0 = TL["S0"] + i * TL["STEP"]
        ev.append((s0, W / "sfx" / "05_톡.mp3", 0.45))
        if i == 7:  # 대본 쓰기 — 줄마다 타자 묶음
            for q in range(6):
                for z in range(3): ev.append((s0 + 0.15 + q * 0.16 + z * 0.045, keys[(q + z) % 9], 0.45))
    ev += [(TL["DONE"], A / "팩01" / "ding.wav", 0.7), (TL["PLAY"], A / "팩01" / "click2.wav", 1.0)]
    L = TL["END"]
    vol = f"if(lt(t,{TL['FF']:.2f}),0.12,if(lt(t,{TL['DONE']:.2f}),0.2,0.12))"
    mix(ev, L, ua, [(BGM, 0, L, vol, 0.5, 0.45)])
    # 2) 쇼츠 원음 그대로 끝까지
    sl = dur(SHORT)
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{sl:.3f}", "-i", str(W / "paper.png"), "-i", str(SHORT),
         "-filter_complex", "[1:v]scale=-2:1000,setsar=1[s];[0:v]scale=1920:1080,setsar=1[bg];[bg][s]overlay=(W-w)/2:40,fps=30,format=yuv420p[v];[1:a]aresample=48000,aformat=channel_layouts=stereo[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "pcm_s16le", "-t", f"{sl:.3f}", str(sh.with_suffix(".mkv"))])
    return L, sl


def _hook_and_join(seg, ui, ua, sh, L, sl):
    # 3) 나레이션 훅
    hk = seg / "o2_hook.mp4"
    HT = frames("hook.html", None, "HT", hk)
    hl = HT["END"]
    hev = [(0.0, VOICE, 1.0), (HT["C"], A / "팩01" / "pop.wav", 0.5), (HT["D"], A / "팩01" / "pop.wav", 0.5), (HT["D2"], A / "팩01" / "pop.wav", 0.4),
           (HT["F"] + 0.6, A / "팩01" / "pop.wav", 0.35), (HT["F"] + 0.95, A / "팩01" / "pop.wav", 0.35), (HT["F"] + 1.3, A / "팩01" / "pop.wav", 0.35),
           (HT["G"], A / "팩01" / "whoosh.wav", 0.4), (HT["H"], A / "팩01" / "whoosh.wav", 0.4), (HT["I"], A / "팩01" / "whoosh.wav", 0.4), (HT["J"], A / "팩01" / "ding.wav", 0.5)]
    ha = seg / "o2_hook.wav"; mix(hev, hl, ha, [(BGM, 40, hl, "0.055", 0.8, 0.8)])
    # 4) 이어 붙이기 + 소리 크기 맞춤
    parts = [(ui, ua), (sh.with_suffix(".mkv"), None), (hk, ha)]
    inp, fl = [], []
    for k, (v, a) in enumerate(parts):
        inp += ["-i", str(v)]
        if a: inp += ["-i", str(a)]
    idx, cat = 0, ""
    for v, a in parts:
        vi = idx; ai = idx + 1 if a else idx; idx += 2 if a else 1
        cat += f"[{vi}:v]fps=30,scale=1920:1080,setsar=1,format=yuv420p[v{vi}];[{ai}:a]aresample=48000,aformat=channel_layouts=stereo[x{vi}];"
    vids = [i for i in range(len(inp) // 2) if True]
    order, idx = [], 0
    for v, a in parts:
        order.append(idx); idx += 2 if a else 1
    cat += "".join(f"[v{i}][x{i}]" for i in order) + f"concat=n={len(order)}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    out = seg / "open2.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inp, "-filter_complex", cat, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)])
    print("오프닝v2", out, round(dur(out), 2), "초 = 창", round(L, 2), "+ 쇼츠", round(sl, 2), "+ 훅", round(hl, 2))


if __name__ == "__main__":
    main()
