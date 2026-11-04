"""4회차 세로 쇼츠(사장님 11-04 "세로로 구성해서, 후킹은 동일한 느낌으로") — Jev 구성 A안(해결 0.35·선택 1.0)
① 클로드 창(seg/o2_ui.mp4 저장본) 가운데 대화 칸을 세로로 잘라 — 타이핑은 실시간, 만드는 과정은 2.5배 더(=20배속)
② 완성 쇼츠 src/tattoo.mp4 앞 10초 원음
③ 나레이션 sh01(필재 1.1배) + 세로 훅 카드 short_hook.html
→ seg/yt4_short.mp4 (1080x1920, -14 LUFS)
usage: py make_short.py [hook]   (hook = ③만 다시 찍고 이어 붙이기)"""
import json, shutil, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from make_open2 import run, dur, mix, A, BGM

W = Path(__file__).resolve().parent
SEG = W / "seg"
FPS = 30
UI_CUT = (0.3, 7.75, 24.55, 27.25)   # 실시간 | 2.5배 | 실시간  (claude_ui2.js: FF=7.75 DONE=24.25 END=27.25)
SEND = 5.85                          # 보내기(5.70) 직후까지는 입력창만 크게 — 1080 폭에서 원래 글자가 30px라 안 읽혔다(시트 실측)
ZOOM = "crop=550:180:560:860,scale=1080:-2"  # 입력창 글자 x615~1060 · y880~1000 (o2_ui.mp4 5.6초 프레임 실측)
FAST = 2.5
TAT = 10.0


def shots():
    fd = W / "frames" / "sh_hook"
    if fd.exists(): shutil.rmtree(fd)
    fd.mkdir(parents=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for k in ("k1", "k2", "k3", "k4"):
            pg.goto((W / "short_cap.html").as_uri() + f"?k={k}"); pg.wait_for_timeout(400)
            pg.screenshot(path=str(W / "frames" / f"cap_{k}.png"), omit_background=True)
        if True:
            pg.goto((W / "short_hook.html").as_uri()); pg.wait_for_timeout(600)
            HT = pg.evaluate("window.HT")
            for i in range(int(HT["END"] * FPS)):
                pg.evaluate(f"render({i / FPS})")
                pg.screenshot(path=str(fd / f"{i:04d}.jpg"), type="jpeg", quality=92)
        b.close()
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"), "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(SEG / "sh_hook.mp4")])
    return HT


def seg_ui():
    a, f, d, e = UI_CUT
    t1 = f - a; t2 = (d - f) / FAST; t3 = e - d
    t0 = SEND - a
    fc = (f"[0:v]split=2[z][c];[z]trim={a}:{SEND},setpts=PTS-STARTPTS,{ZOOM},setsar=1[p0];"
          f"[c]crop=1120:1080:550:0,scale=1080:-2,setsar=1,split=3[u1][u2][u3];"
          f"[u1]trim={SEND}:{f},setpts=PTS-STARTPTS[p1];[u2]trim={f}:{d},setpts=(PTS-STARTPTS)/{FAST}[p2];[u3]trim={d}:{e},setpts=PTS-STARTPTS[p3];"
          f"[1:a]aresample=48000,aformat=channel_layouts=stereo,asplit=3[a1][a2][a3];"
          f"[a1]atrim={a}:{f},asetpts=PTS-STARTPTS[q1];[a2]atrim={f}:{d},asetpts=PTS-STARTPTS,atempo={FAST}[q2];[a3]atrim={d}:{e},asetpts=PTS-STARTPTS[q3];"
          f"[q1][q2][q3]concat=n=3:v=0:a=1[au];"
          f"[2:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,split=2[bg0][bg1];"
          f"[bg0]trim=0:{t0:.3f},setpts=PTS-STARTPTS[b0];[b0][p0]overlay=0:760:shortest=1[w0];"
          f"[p1][p2][p3]concat=n=3:v=1:a=0[ui];[bg1][ui]overlay=0:440:shortest=1[w1];"
          f"[w0][w1]concat=n=2:v=1:a=0,setpts=PTS-STARTPTS[x0];"
          f"[x0][3:v]overlay=0:0:enable='lt(t,{t1:.3f})'[x1];"
          f"[x1][4:v]overlay=0:0:enable='between(t,{t1:.3f},{t1 + t2:.3f})'[x2];"
          f"[x2][5:v]overlay=0:0:enable='gte(t,{t1 + t2:.3f})',fps=30,format=yuv420p[v]")
    L = t1 + t2 + t3
    run(["ffmpeg", "-y", "-v", "error", "-i", str(SEG / "o2_ui.mp4"), "-i", str(SEG / "o2_ui.wav"),
         "-loop", "1", "-t", f"{L:.3f}", "-i", str(W / "paper.png"),
         *sum([["-i", str(W / "frames" / f"cap_{k}.png")] for k in ("k1", "k2", "k3")], []),
         "-filter_complex", fc, "-map", "[v]", "-map", "[au]", "-t", f"{L:.3f}",
         "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "pcm_s16le", str(SEG / "sh_ui.mkv")])
    return L


def seg_tat():
    run(["ffmpeg", "-y", "-v", "error", "-t", f"{TAT}", "-i", str(W / "src" / "tattoo.mp4"), "-i", str(W / "frames" / "cap_k4.png"),
         "-filter_complex", f"[0:v]scale=1080:1920,setsar=1[s];[s][1:v]overlay=0:0,fps=30,format=yuv420p[v];[0:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=out:st={TAT - 0.4}:d=0.4[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "pcm_s16le", str(SEG / "sh_tat.mkv")])


def main():
    HT = shots()
    L1 = seg_ui(); seg_tat()
    hl = HT["END"]; P = A / "팩01"
    ev = [(0.0, W / "voice" / "sh01.mp3", 1.0)] + [(HT[k], P / "pop.wav", 0.4) for k in ("B1", "B2", "B3", "B4")] + \
         [(HT["BZ"], P / "ding.wav", 0.45), (HT["C"], P / "whoosh.wav", 0.4), (HT["D"], P / "whoosh.wav", 0.4), (HT["E"], P / "pop.wav", 0.5), (HT["F"], P / "whoosh.wav", 0.4), (HT["FC"], P / "ding.wav", 0.45)]
    ha = SEG / "sh_hook.wav"; mix(ev, hl, ha, [(BGM, 40, hl, "0.055", 0.8, 1.2)])
    out = SEG / "yt4_short_raw.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(SEG / "sh_ui.mkv"), "-i", str(SEG / "sh_tat.mkv"), "-i", str(SEG / "sh_hook.mp4"), "-i", str(ha),
         "-filter_complex", "[0:v]setsar=1[v0];[1:v]setsar=1[v1];[2:v]setsar=1,fps=30,format=yuv420p[v2];"
         "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];[3:a]aresample=48000,aformat=channel_layouts=stereo[a2];"
         "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "19", "-preset", "veryfast", "-c:a", "pcm_s16le", str(out.with_suffix(".mkv"))])
    raw = out.with_suffix(".mkv")
    e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = json.loads(e[e.rindex("{"):e.rindex("}") + 1])
    fin = SEG / "yt4_short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "copy", "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(fin)])
    print("세로 쇼츠", fin, round(dur(fin), 2), "초 = 창", round(L1, 2), "+ 완성본", TAT, "+ 훅", hl)


if __name__ == "__main__":
    main()
