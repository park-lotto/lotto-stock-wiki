"""4회차 세로 쇼츠 2~4편(사장님 11-04 "이런 걸로 3개 더") — 1편(make_short.py 타투 편)과 같은 뼈대, Jev 나눔 A안(0.61·0.96)
① 클로드 창(claude_ui2.html?v=<편>)에 편마다 다른 한 줄 → 20배속 제작 → 완성 카드 ▶
② 그 편의 완성 쇼츠(src/<원본>.mp4) 앞 10초 원음
③ 나레이션 sh0N(필재 1.1배) + 세로 카드(short_cards.html?c=sh0N, 카드 원본 = cards/sh0N.js)
→ seg/yt4_<편>.mp4 (1080x1920, -14 LUFS)
편별 값(한 줄·제목·단계·대본 줄)은 아래 SHORTS 한 곳 — uiv/<원본>/v.js 는 여기서 만든다.
usage: py make_shorts.py [sh02 sh03 sh04]"""
import json, random, shutil, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from make_open2 import run, dur, mix, A, BGM

W = Path(__file__).resolve().parent
SEG = W / "seg"
FPS = 30
FAST = 2.5          # 8배속 화면을 2.5배 더 = 20배속(short_cap k2 표시와 짝)
CLIP = 10.0
ZOOM = "crop=550:180:560:860,scale=1080:-2"   # 입력창 글자 자리(make_short.py 와 같은 실측)
FOREIGN = ["준비 확인", "영상 확인", "해외 원본 찾기", "제품 확인", "자료 조사", "원본 정리", "원음 정리", "대본 쓰기", "대본 확인", "장면 맞추기", "글자 지우기·영상 만들기", "완성본 검사", "완성"]
SHOP = ["준비 확인", "소재 확인", "제품 확인", "자료 조사", "재료 영상 모으기", "대본 쓰기", "대본 확인", "장면 맞추기", "목소리·영상 만들기", "완성본 검사", "완성"]   # = flow.py FORMAT_STAGES 쇼핑형
MSG = json.loads((W / "cards" / "msg.json").read_text(encoding="utf-8"))
SHORTS = {
    "sh02": dict(src="sun", topic="한국 선크림 백탁 쇼츠", title="한국 선크림 백탁이 진짜 없어??", stages=FOREIGN,
                 bot="숏클로 만들게요. 외국인이 한국 선크림을 써 보는 쇼츠 — 해외 원본 영상부터 찾겠습니다.",
                 d1="해외 원본형 · 제품 장면 있음", d2="외국인이 한국 선크림을 바르는 영상", prod="제품 화면 확인 — 흰 통 선크림",
                 script=["발라 보더니", "세상에!!", "문질러", "진짜 다 사라졌어", "하얀 자국 대신", "피부가 유리알 됐어"],
                 render=None, sub="원본 찾기 → 대본 → 장면 → 자막"),
    "sh03": dict(src="ottogi", topic="오뚜기 숨은 제품", title="오뚜기가 일반인한테 절대 안 파는 이것", stages=SHOP,
                 bot="숏클로 만들게요. 오뚜기가 일반인한테 안 파는 제품 썰 — 소재부터 확인하겠습니다.",
                 d1="쇼핑형 · 썰 소재", d2="오뚜기가 일반인한테 안 파는 제품", prod="제품 확인 — 버터 스프레드",
                 script=["오뚜기가 일반인한테는 절대 안 파는 것", "절대 안 팔 근데 맛잘알들은 결국", "찰떡같은 대체품을 찾아냈는데", "무스 메이플버터", "부드럽게 쭉 발린다는데", "단짠 조합 미쳤다고"],
                 render="목소리 · 자막 · 영상 합치기", sub="소재 → 대본 → 장면 → 목소리"),
    "sh04": dict(src="lego", topic="레고 이름 유래 쇼츠", title="레고라는 이름, 무슨 뜻인지 알아?", stages=SHOP,
                 bot="숏클로 만들게요. 레고라는 이름이 어디서 왔는지 — 소재부터 확인하겠습니다.",
                 d1="쇼핑형 · 이름 유래 썰", d2="레고라는 이름의 뜻", prod="제품 확인 — 레고 클래식",
                 script=["레고라는 이름, 무슨 뜻인지 알아?", "원래는 덴마크의 한 목수가", "사다리랑 다리미판에", "가게 이름을 지을 때", "그 두 낱말 앞 글자를 따서 붙인 거죠", "덕분에 지금은 전 세계 거실 바닥에서"],
                 render="목소리 · 자막 · 영상 합치기", sub="소재 → 대본 → 장면 → 목소리"),
}


def make_v(k, c):
    d = W / "uiv" / c["src"]; d.mkdir(parents=True, exist_ok=True)
    src = W / "src" / f"{c['src']}.mp4"; L = dur(src)
    for i in range(16):   # 얼굴·제품 칸 — ui/f*.jpg 와 같은 162x198
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{0.5 + i * (L - 1) / 16:.2f}", "-i", str(src), "-frames:v", "1", "-vf", "crop=1080:1320:0:300,scale=162:198", str(d / f"f{i}.jpg")])
    run(["ffmpeg", "-y", "-v", "error", "-ss", "2", "-i", str(src), "-frames:v", "1", str(d / "thumb.jpg")])
    v = dict(MSG=MSG[k], BOT=c["bot"], STAGES=c["stages"], SCRIPT=c["script"], DIR=f"uiv/{c['src']}", THUMB=f"uiv/{c['src']}/thumb.jpg",
             TITLE=c["title"], TOPIC=c["topic"], D1=c["d1"], D2=c["d2"], PROD=c["prod"])
    if c["render"]: v["RENDER"] = c["render"]
    (d / "v.js").write_text("// make_shorts.py 가 만든다 — 고치려면 SHORTS 를 고친다\nwindow.V = " + json.dumps(v, ensure_ascii=False) + ";\n", encoding="utf-8")


def shoot(url, w, h, scale, out_dir, key, end=None):
    if out_dir.exists(): shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg.goto(url); pg.wait_for_timeout(700)
        TL = pg.evaluate(f"window.{key}")
        for i in range(int((end or TL["END"]) * FPS)):
            pg.evaluate(f"render({i / FPS})")
            pg.screenshot(path=str(out_dir / f"{i:04d}.jpg"), type="jpeg", quality=92)
        b.close()
    return TL


def enc(fd, out):
    run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fd / "%04d.jpg"), "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])


def ui_audio(TL, out):
    """make_open2.build_front 의 소리 그대로(타자·톡·휙·딩·클릭) — 팩 열쇠 소리 파일은 그때 만든 key_팩*.wav"""
    R = random.Random(3); keys = sorted(W.glob("key_팩*.wav")); ev, last = [], -1
    for t in TL["KEYS"]:
        k = R.randrange(len(keys)); k = (k + 1) % len(keys) if k == last else k; last = k
        ev.append((t + R.uniform(-0.008, 0.008), keys[k], R.uniform(0.7, 1.0)))
    ev += [(TL["SEND"], keys[4], 1.0), (TL["SEND"] + 0.03, W / "sfx" / "05_톡.mp3", 0.9), (TL["FF"] - 0.15, A / "팩01" / "whoosh.wav", 0.8)]
    for i in range(TL["N"]):
        s0 = TL["S0"] + i * TL["STEP"]; ev.append((s0, W / "sfx" / "05_톡.mp3", 0.45))
    ev += [(TL["DONE"], A / "팩01" / "ding.wav", 0.7), (TL["PLAY"], A / "팩01" / "click2.wav", 1.0)]
    vol = f"if(lt(t,{TL['FF']:.2f}),0.12,if(lt(t,{TL['DONE']:.2f}),0.2,0.12))"
    mix(ev, TL["END"], out, [(BGM, 0, TL["END"], vol, 0.5, 0.45)])


def caps(sub):
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for k in ("k1", "k2", "k3", "k4"):
            pg.goto((W / "short_cap.html").as_uri() + f"?k={k}&s={sub}"); pg.wait_for_timeout(400)
            pg.screenshot(path=str(W / "frames" / f"cap_{k}.png"), omit_background=True)
        b.close()


def seg_ui(ui, ua, TL, out):
    a, s, f, d, e = 0.3, TL["SEND"] + 0.15, TL["FF"], TL["DONE"] + 0.3, TL["END"]
    t0, t1, t2, t3 = s - a, f - a, (d - f) / FAST, e - d
    fc = (f"[0:v]split=2[z][c];[z]trim={a}:{s},setpts=PTS-STARTPTS,{ZOOM},setsar=1[p0];"
          f"[c]crop=1120:1080:550:0,scale=1080:-2,setsar=1,split=3[u1][u2][u3];"
          f"[u1]trim={s}:{f},setpts=PTS-STARTPTS[p1];[u2]trim={f}:{d},setpts=(PTS-STARTPTS)/{FAST}[p2];[u3]trim={d}:{e},setpts=PTS-STARTPTS[p3];"
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
    run(["ffmpeg", "-y", "-v", "error", "-i", str(ui), "-i", str(ua), "-loop", "1", "-t", f"{L:.3f}", "-i", str(W / "paper.png"),
         *sum([["-i", str(W / "frames" / f"cap_{k}.png")] for k in ("k1", "k2", "k3")], []),
         "-filter_complex", fc, "-map", "[v]", "-map", "[au]", "-t", f"{L:.3f}",
         "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "pcm_s16le", str(out)])
    return L


def seg_clip(src, out):
    run(["ffmpeg", "-y", "-v", "error", "-t", f"{CLIP}", "-i", str(src), "-i", str(W / "frames" / "cap_k4.png"),
         "-filter_complex", f"[0:v]scale=1080:1920,setsar=1[s];[s][1:v]overlay=0:0,fps=30,format=yuv420p[v];[0:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=out:st={CLIP - 0.4}:d=0.4[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "pcm_s16le", str(out)])


def build(k):
    c = SHORTS[k]; make_v(k, c)
    ui, ua = SEG / f"{k}_ui.mp4", SEG / f"{k}_ui.wav"
    TL = shoot((W / "claude_ui2.html").as_uri() + f"?v={c['src']}", 1536, 864, 1.25, W / "frames" / f"{k}_ui", "TL"); enc(W / "frames" / f"{k}_ui", ui)
    ui_audio(TL, ua)
    caps(c["sub"])
    L1 = seg_ui(ui, ua, TL, SEG / f"{k}_seg1.mkv")
    seg_clip(W / "src" / f"{c['src']}.mp4", SEG / f"{k}_seg2.mkv")
    HT = shoot((W / "short_cards.html").as_uri() + f"?c={k}", 1080, 1920, 1, W / "frames" / f"{k}_cards", "HT")
    hv = SEG / f"{k}_cards.mp4"; enc(W / "frames" / f"{k}_cards", hv)
    hl = HT["END"]; P = A / "팩01"
    ev = [(0.0, W / "voice" / f"{k}.mp3", 1.0)] + [(t, P / "whoosh.wav", 0.35) for t in HT["POPS"][1:]]
    ha = SEG / f"{k}_cards.wav"; mix(ev, hl, ha, [(BGM, 40, hl, "0.055", 0.8, 1.2)])
    raw = SEG / f"yt4_{k}_raw.mkv"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(SEG / f"{k}_seg1.mkv"), "-i", str(SEG / f"{k}_seg2.mkv"), "-i", str(hv), "-i", str(ha),
         "-filter_complex", "[0:v]setsar=1[v0];[1:v]setsar=1[v1];[2:v]setsar=1,fps=30,format=yuv420p[v2];"
         "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];[3:a]aresample=48000,aformat=channel_layouts=stereo[a2];"
         "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-threads", "4", "-crf", "19", "-preset", "veryfast", "-c:a", "pcm_s16le", str(raw)])
    e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = json.loads(e[e.rindex("{"):e.rindex("}") + 1])
    fin = SEG / f"yt4_{k}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "copy", "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']},aresample=48000",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(fin)])
    print(k, fin.name, round(dur(fin), 2), "초 = 창", round(L1, 2), "+ 완성본", CLIP, "+ 카드", hl, flush=True)


if __name__ == "__main__":
    for k in (sys.argv[1:] or list(SHORTS)):
        build(k)
