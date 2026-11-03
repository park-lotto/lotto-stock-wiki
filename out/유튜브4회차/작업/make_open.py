"""오프닝: 클로드 창(실사 재현)에서 한마디 타이핑 → 13단계 → 완성 카드 → 완성 쇼츠 재생. 소리 = 키보드 타다닥 + 엔터 톡 + 단계 톡 + 완성 딩 + 쇼츠 원음."""
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
    # 키 소리 한 개 합성(짧은 잡음 + 고역 강조 + 빠른 감쇠)
    key = W / "key.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=d=0.045:c=white:a=0.9:r=48000", "-af",
         "highpass=f=1800,lowpass=f=7000,afade=t=out:st=0.004:d=0.04,volume=1.6", str(key)])
    R = random.Random(3)
    ev = []  # (시각, 파일, 볼륨)
    for k in range(TL["LEN"]):
        ev.append((TL["T0"] + k * TL["CH"] + R.uniform(-0.02, 0.03), key, R.uniform(0.55, 1.0)))
    ev.append((TL["SEND"], SFX / "05_톡.mp3", 0.9))
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
    print("오프닝", out, json.dumps(TL))


if __name__ == "__main__":
    main()
