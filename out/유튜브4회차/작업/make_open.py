"""오프닝: 클로드 창(실사 재현)에서 '외국인 한국화장품 영상 만들어줘..' 타이핑 → 13단계 → 완성 카드 → 완성 쇼츠 재생. 소리 = 키보드 타다닥 + 엔터 톡 + 단계 톡 + 완성 딩 + 쇼츠 원음."""
import json, shutil, subprocess, sys, random
from pathlib import Path
from playwright.sync_api import sync_playwright

W = Path(__file__).resolve().parent
FPS = 30
SFX = W / "sfx"
SHORT = W / "src" / "tattoo.mp4"
SHORT_SS, SHORT_LEN = 0.0, 6.0


def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        sys.stderr.write(r.stderr.decode("utf-8", "replace")[-1500:]); raise SystemExit("실패")


def main():
    if not SHORT.exists():
        SHORT.parent.mkdir(exist_ok=True); raise SystemExit("src/tattoo.mp4 가 없습니다")
    run(["ffmpeg", "-y", "-v", "error", "-ss", "2", "-i", str(SHORT), "-frames:v", "1", str(W / "tattoo_thumb.jpg")])
    fd = W / "frames" / "open"
    if fd.exists(): shutil.rmtree(fd)
    fd.mkdir(parents=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1536, "height": 864}, device_scale_factor=1.25)
        pg.goto((W / "claude_ui.html").as_uri()); pg.wait_for_timeout(500)
        TL = pg.evaluate("window.TL")
        end = TL["DONE"] + 2.6
        n = int(end * FPS)
        for i in range(n):
            pg.evaluate(f"render({i / FPS})")
            pg.screenshot(path=str(fd / f"{i:04d}.jpg"), type="jpeg", quality=92)
        pg.evaluate(f"render({end})"); pg.screenshot(path=str(W / "claude_last.png"))
        b.close()
    ui = W / "open_ui.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"), "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(ui)])
    # 키 소리 = 효과음 팩의 실제 틱 3종(팩01~03) × 높낮이 3단 → 9가지를 돌려 쓴다(같은 소리 연속 금지)
    A = W.parents[2] / "shopping_shorts" / "assets" / "sfx_packs"
    keys = []
    for pk in ("팩01", "팩02", "팩03"):
        for j, rate in enumerate((0.92, 1.0, 1.09)):
            kf = W / f"key_{pk}_{j}.wav"
            run(["ffmpeg", "-y", "-v", "error", "-i", str(A / pk / "tick.wav"), "-af",
                 f"aresample=48000,asetrate={int(48000 * rate)},aresample=48000,atrim=0:0.08,afade=t=out:st=0.05:d=0.03", str(kf)])
            keys.append(kf)
    R = random.Random(3)
    ev = []  # (시각, 파일, 볼륨)
    last = -1
    for t in TL["KEYS"]:
        k = R.randrange(len(keys))
        if k == last: k = (k + 1) % len(keys)
        last = k
        ev.append((t + R.uniform(-0.008, 0.008), keys[k], R.uniform(0.7, 1.0)))
    ev.append((TL["SEND"], keys[4], 1.0)); ev.append((TL["SEND"] + 0.03, SFX / "05_톡.mp3", 0.9))  # 엔터
    for k in range(TL["N"]):
        ev.append((TL["ST0"] + (k + 1) * TL["STEP"], SFX / "05_톡.mp3", 0.25))
    ev.append((TL["DONE"] + 1.0, SFX / "06_딩.mp3", 0.8))
    inp, fl = [], []
    for i, (t, f, v) in enumerate(ev):
        inp += ["-i", str(f)]
        fl.append(f"[{i}:a]aresample=48000,volume={v:.2f},adelay={int(t * 1000)}|{int(t * 1000)}[a{i}]")
    fl.append("".join(f"[a{i}]" for i in range(len(ev))) + f"amix=inputs={len(ev)}:normalize=0,apad,atrim=0:{end:.3f}[out]")
    sfx = W / "open_sfx.wav"
    run(["ffmpeg", "-y", "-v", "error", *inp, "-filter_complex", ";".join(fl), "-map", "[out]", str(sfx)])
    uiav = W / "open_ui_av.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ui), "-i", str(sfx), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(uiav)])
    # 완성 쇼츠 재생(원음) — 종이 배경 가운데 크게
    sh = W / "open_short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", str(SHORT_LEN), "-i", str(W / "paper.png"), "-ss", str(SHORT_SS), "-t", str(SHORT_LEN), "-i", str(SHORT),
         "-filter_complex", "[1:v]scale=-2:1000,setsar=1[s];[0:v][s]overlay=(W-w)/2:40,fps=30,format=yuv420p[v];[1:a]aresample=48000,afade=t=out:st=5.3:d=0.7[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-t", str(SHORT_LEN), str(sh)])
    lst = W / "open_list.txt"; lst.write_text(f"file '{uiav.as_posix()}'\nfile '{sh.as_posix()}'\n", encoding="utf-8")
    (W / "seg").mkdir(exist_ok=True)
    out = W / "seg" / "open.av.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", str(out)])
    # 배경음악(Jev 선택 0.97: 무료곡 Epic Inspiration, 상업곡 금지) — 키 소리 밑에 작게, 쇼츠 원음 구간은 더 줄이고 끝에서 사라짐
    BGM = W.parents[2] / "shopping_shorts" / "assets" / "bgm_lib" / "epic_inspiration.mp3"
    tot = end + SHORT_LEN
    mixed = W / "seg" / "open.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-i", str(BGM), "-filter_complex",
         f"[1:a]aresample=48000,atrim=0:{tot:.3f},volume='if(lt(t,{end:.3f}),0.16,0.06)':eval=frame,afade=t=in:d=0.6,afade=t=out:st={tot - 1.2:.3f}:d=1.2[b];"
         f"[0:a][b]amix=inputs=2:normalize=0:duration=first[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(mixed)])
    print("오프닝", mixed, json.dumps({k: v for k, v in TL.items() if k != "KEYS"}), "키", len(TL["KEYS"]))


if __name__ == "__main__":
    main()
