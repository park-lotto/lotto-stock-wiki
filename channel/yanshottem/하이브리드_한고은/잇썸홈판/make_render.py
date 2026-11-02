# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 1호 한고은 채소통 — 잇썸홈판 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17).

    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/잇썸홈판/make_render.py [--no-back] [--mix-only]

흐름(사장님 확정): 연예인 원음 → 우리 TTS 한마디 → 원음 → '저 영상 보고 나도 샀다'(다리) → 좋다 ①② → 반응 → 사고 싶게.
  앞(0~11.88초) = 얜샷템 틀(channel/mantem/frame_얜샷템.json) — 박세리 편 make_render 와 같은 길(narr_video.build, 원음 자막 흰·나레 노랑 emph)
  뒤(다리~끝)   = 잇썸홈 프리셋(channel/homedesignnote/preset/전체화면_가운데자막) — 공용 제작기 preset_make 를 부르기만(back/대본.json·재료.json)
  → 두 영상을 이음매 1곳에서 잇고, 소리는 [원음+TTS | 뒤 나레] 한 줄 + BGM honwaka_puppu 한 곡(이음매에서 안 끊김) → 마스터(잇썸홈 manifest master 값).
시각의 주인 = 이 파일 FRONT 표. TTS = 박창수 Typecast 앞 1회(front/tts_front.mp3) + 뒤 덩어리 6개(preset_make 캐시) — 다시 부르지 않는다.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv  # noqa: E402

D = Path(__file__).resolve().parent
W = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/잇썸홈판")
SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/src")
SRCV = "hge_LcQv9yOh3Wc.mp4"
CACHE = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/src/_make_cache")
FW, BW, R = W / "front", W / "back", W / "render"
PRESET = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"
TTEUTGI = ROOT / "channel/annapick/뜯기/itYwQVyuCcc/뜯기.json"
TITLE = "한고은이 TV 보고 산\n두 달 가는 채소 보관통"
LABEL = "출처 : 고은언니 한고은"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 한고은 편(annapick)과 같은 약한 처리
TTS = FW / "tts_final.wav"      # 박창수 1회(tts_front.mp3) → 앞뒤 무음 정리 → 쉼표 쉼 0.39→0.26초 → atempo 0.95(8.4자/초)
BGM = ROOT / "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3"
BGM_DB_BELOW = 14.4             # 잇썸홈 manifest sound.bgm_level_db_below_voice
MASTER_PRE = "dynaudnorm=f=100:g=9:p=0.9:m=20,acompressor=threshold=0.125:ratio=8:attack=1:release=40"
TARGET_LUFS, TP_DB = -9.0, -2.0
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/칼카피_얜샷템_한고은채소통_잇썸홈판.mp4")

# ── 앞 구간 시각표(판단 주인) ───────────────────────────────────────────────
O1 = (780.62, 783.84)                       # '정말 난 너무 놀랬어. 한 달, 두 달이 가도 너무 신선해요.' — 끝 '요'가 783.82까지(1판 783.72 자르기 → 받아쓰기 끝말 '놀랬어'로 들림)
N_T0 = 3.32                                 # 원음 끝 +0.10
N_DUR = 3.203                               # tts_final.wav 실측
O5_T0 = round(N_T0 + N_DUR + 0.12, 3)       # 6.543
O5A = [(788.18, 791.55), (791.62, 793.66)]  # 소리 — 둘째 조각 +0.07초(annapick 근거.md §2: '귀찮으니까' 끝 793.64까지 — 1판 793.59 는 받아쓰기 '괜찮으니까' 2/3)
FRONT_DUR = round(O5_T0 + sum(b - a for a, b in O5A), 3)
SHOTS = [  # t0, ss, crop(1920×1080 → 정사각 창)
    (0.0, 780.62, [480, 0, 880, 880]),      # 한고은 얼굴(원음 그 샷) — 오른쪽 그림 꾸밈(x≥1395)·아래 자막(y≥930) 밖
    (3.20, 745.10, [520, 0, 880, 880]),     # 비닐째 온 샐러드 채소를 꺼내는 한고은('1kg 하면 요렇게 와요' 샷) — 자막 y≥915 밖
    (O5_T0, 788.18, [560, 0, 840, 840]),    # 상추 담은 통에 투명 뚜껑 덮는 손(노란 소매) — '[이거 진짜 꿀팁이야]' y≥855 밖
    (round(O5_T0 + 3.37, 3), 791.55, [710, 200, 715, 715]),   # '저는 씻어서 보관해요. 귀찮으니까' 한고은 얼굴 — 빨간 꾸밈 글 y≤190 밖
]
N_CHUNKS = [(0.0, "채소를 1킬로씩 사는"), (1.07, "한고은 씨가,"), (1.927, "TV 보고 샀다는"), (2.61, "보관통이에요")]   # 쉼표 쉼 1.667~1.927 실측 · 안쪽 경계는 글자 비율
O1_CAPS = [(0.0, "정말 난 너무 놀랬어"), (1.33, "한 달, 두 달이 가도"), (2.43, "너무 신선해요")]              # annapick 대본.json captions_plan 시각
O5_CAPS = [(0.06, "그냥 보관을 하셔서"), (1.18, "먹고 싶을 때"), (2.22, "씻어서 하셔도 되고"), (3.54, "저는 씻어서 보관해요"), (4.62, "귀찮으니까")]


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError(f"{' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def lufs(p, extra=""):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", (extra + "," if extra else "") + "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def captions():
    ycol = next(l for l in json.loads(FRAME.read_text(encoding="utf-8"))["layers"] if l.get("role") == "caption")["rgb"]
    caps = [(t, x, "원음") for t, x in O1_CAPS] + [(N_T0 + t, x, "나레") for t, x in N_CHUNKS] + [(O5_T0 + t, x, "원음") for t, x in O5_CAPS]
    ev = []
    for j, (t, txt, who) in enumerate(caps):
        b = caps[j + 1][0] if j + 1 < len(caps) else FRONT_DUR
        ev.append({"kind": "emph", "text": txt, "rgb": ycol if who == "나레" else [255, 255, 255], "t0": round(t, 3), "dur": round(b - t, 3), "who": who})
    return ev


def front_video():
    FW.mkdir(parents=True, exist_ok=True)
    gap = FW / "narr_gapped.wav"
    run(["ffmpeg", "-y", "-i", TTS, "-filter_complex",
         f"anullsrc=r=48000:cl=mono,atrim=0:{N_T0}[g0];[0:a]aresample=48000,aformat=channel_layouts=mono[p];"
         f"anullsrc=r=48000:cl=mono,atrim=0:{FRONT_DUR - N_T0 - N_DUR:.3f}[g1];[g0][p][g1]concat=n=3:v=0:a=1[a]",
         "-map", "[a]", "-c:a", "pcm_s16le", gap])
    ev = captions()
    L = ["채소를 1킬로씩 사는 한고은 씨가 TV 보고 샀다는 보관통이에요."]
    cuts = []
    for k, (t0, ss, crop) in enumerate(SHOTS):
        t1 = SHOTS[k + 1][0] if k + 1 < len(SHOTS) else FRONT_DUR
        cuts.append({"src": SRCV, "ss": ss, "src_crop": crop, "dur": round(t1 - t0, 3), "plan_i": k})
    M = {"_note": "make_render.py 앞 구간 — 페이지 1개 × cuts(FRONT 표 시각 그대로)", "cand_dir": str(SRC),
         "shots": [{"i": 0, "full": True, "kind": "원본재편집", "src": SRCV, "ss": SHOTS[0][1], "src_crop": SHOTS[0][2], "cuts": cuts, "t_final": [0.0, FRONT_DUR]}]}
    S = {"final": {"lines": [{"text": L[0], "note": "렌더용 한 문장(박세리·annapick 편과 같은 우회) — 원문은 ../대본.json"}]}, "caption_events": ev}
    (FW / "재료_front.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    (FW / "대본_front.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads(FRAME.read_text(encoding="utf-8"))
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = TITLE
        if l.get("role") == "label":
            l["text"] = LABEL
    (D / "frame_front.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    plan = {"tteutgi": str(TTEUTGI), "frames": [{"frame": str(D / "frame_front.json"), "t_end": None}], "script": str(FW / "대본_front.json"),
            "tts": str(gap), "materials": str(FW / "재료_front.json"), "out": str(FW / "build"), "bgm": None, "lufs": -15.0,
            "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan)
    shutil.copyfile(final, FW / "front_video.mp4")
    return ev


def back_video():
    # TTS 캐시(덩어리마다) — 2판은 바뀐 줄(반응) 1덩어리만 새로 받는다(--allow-tts). 캐시는 1판 자리(src/_make_cache)를 그대로 쓴다.
    r = subprocess.run([sys.executable, str(ROOT / "tools/calcopy/engine/preset_make.py"), str(PRESET), str(D / "back"), "--test", "--out", str(BW),
                        "--allow-tts", "--cache", str(CACHE)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    (BW / "preset_make_stdout.txt").write_text(r.stdout, encoding="utf-8")
    if not (BW / "video.mp4").exists() or "실패" in r.stdout.split("요약")[-1]:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])


def voice_track(front_d, back_d):
    """[원음 O1 | TTS | 원음 O5] + 뒤 나레 — 원음은 TTS 와 같은 LUFS 로 맞춘다(한 사람 목소리 크기처럼 튀지 않게)."""
    v = SRC / "hge_voice.wav"
    if not v.exists():
        run(["ffmpeg", "-y", "-i", SRC / SRCV, "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, v])
    tI, _ = lufs(TTS)
    parts, fc, lab = [], [], []
    o1 = FW / "o1.wav"
    run(["ffmpeg", "-y", "-i", v, "-af", f"atrim={O1[0]}:{O1[1]},asetpts=N/SR/TB", "-ar", "48000", o1])
    o5 = FW / "o5.wav"
    run(["ffmpeg", "-y", "-i", v, "-filter_complex", f"[0:a]atrim={O5A[0][0]}:{O5A[0][1]},asetpts=N/SR/TB[a];[0:a]atrim={O5A[1][0]}:{O5A[1][1]},asetpts=N/SR/TB[b];"
         "[a][b]concat=n=2:v=0:a=1[o]", "-map", "[o]", "-ar", "48000", o5])
    g1, g5 = round(tI - lufs(o1)[0], 2), round(tI - lufs(o5)[0], 2)
    narr = BW / "narr_lines.wav" if (BW / "narr_lines.wav").exists() else BW / "narr.wav"
    fv = FW / "front_voice.wav"
    run(["ffmpeg", "-y", "-i", o1, "-i", TTS, "-i", o5, "-filter_complex",
         f"[0:a]volume={g1}dB,afade=t=in:d=0.02,afade=t=out:st={O1[1] - O1[0] - 0.04:.3f}:d=0.04[a];"
         f"anullsrc=r=48000:cl=mono,atrim=0:{N_T0 - (O1[1] - O1[0]):.3f}[g0];[1:a]aresample=48000[t];"
         f"anullsrc=r=48000:cl=mono,atrim=0:{O5_T0 - N_T0 - N_DUR:.3f}[g1];[2:a]volume={g5}dB,afade=t=in:d=0.02[c];"
         "[a][g0][t][g1][c]concat=n=5:v=0:a=1,aformat=channel_layouts=mono[o]", "-map", "[o]", "-ar", "48000", fv])
    allv = R / "voice_all.wav"
    run(["ffmpeg", "-y", "-i", fv, "-i", narr, "-filter_complex",
         f"[0:a]apad=whole_dur={front_d:.3f}[f];[1:a]aresample=48000,aformat=channel_layouts=mono,apad=whole_dur={back_d:.3f}[b];[f][b]concat=n=2:v=0:a=1[o]",
         "-map", "[o]", "-ar", "48000", allv])
    return allv, {"tts_lufs": tI, "o1_gain": g1, "o5_gain": g5, "narr": str(narr)}


def master(voice, total):
    vI, _ = lufs(voice)
    bI, _ = lufs(BGM)
    g = round((vI - BGM_DB_BELOW) - bI, 2)
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-i", voice, "-stream_loop", "-1", "-i", BGM, "-filter_complex",
         f"[1:a]aresample=48000,aformat=channel_layouts=mono,volume={g}dB,atrim=0:{total:.3f},afade=t=out:st={total - 0.6:.3f}:d=0.6[b];"
         f"[0:a]apad=whole_dur={total:.3f}[n];[n][b]amix=inputs=2:normalize=0:duration=first[o]", "-map", "[o]", "-ar", "44100", raw])
    gain, mix = 16.0, R / "mix.wav"
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", raw, "-af", f"{MASTER_PRE},volume={gain:.2f}dB,alimiter=limit={10 ** (TP_DB / 20):.4f}:level=false:attack=1:release=30",
             "-ar", "44100", mix])
        oI, _ = lufs(mix)
        if oI >= TARGET_LUFS - 0.05 or gain >= 24:   # 2판: 1판 상한 22(−9.8) → 24(−9.4). 26·28 은 AAC 뒤 최고점 −0.1 이라 안 씀
            break
        gain += 2.0
    return mix, {"bgm_gain_db": g, "master_gain_db": gain, "mix_lufs": oI}


def main():
    R.mkdir(parents=True, exist_ok=True)
    if "--mix-only" not in sys.argv:
        ev = front_video()
        if "--no-back" not in sys.argv:
            back_video()
    else:
        ev = captions()
    fv, bv = FW / "front_video.mp4", BW / "video.mp4"
    fd, bd = dur_of(fv), dur_of(bv)
    vid = R / "video.mp4"
    run(["ffmpeg", "-y", "-i", fv, "-i", bv, "-filter_complex",
         "[0:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[a];[1:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[b];[a][b]concat=n=2:v=1:a=0[v]",
         "-map", "[v]", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", vid])
    total = dur_of(vid)
    voice, vinfo = voice_track(fd, bd)
    mix, minfo = master(voice, total)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, R / "sheet_1s.jpg")
    shutil.copyfile(R / "sheet_1s.jpg", D / "final_sheet_1s.jpg")
    DESK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(final, DESK)
    info = {"front_s": fd, "back_s": bd, "seam_s": fd, "total_s": dur_of(final), "lufs_tp": lufs(final), **vinfo, **minfo,
            "captions_front": ev, "orig_windows": [[0.0, round(O1[1] - O1[0], 3)], [O5_T0, FRONT_DUR]]}
    (R / "render_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k != "captions_front"}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
