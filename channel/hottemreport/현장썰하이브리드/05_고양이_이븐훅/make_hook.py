# -*- coding: utf-8 -*-
"""숏템리폿 고양이 — 이븐쇼핑(재미썸홈 t11) 훅 시작 + 현장썰 + 쿠팡 후기썰 시험 1편 (관제 097, 2026-10-22).

① 이븐 훅 = 재미썸홈 '숏템템플릿' 프리셋(t11 훅 틀)을 scene_style.compose 로 부른다(preset_make template 갈래와 같은 부름).
② ③ = 기존 하이브리드 2차(e58312ebf) 마스터 전 final.mp4 통째 재사용.
이음 = xfade slideleft 0.25초 + sfx_pack whoosh. ① 소리 꼬리(무음) 0.25초만 잘라 ② 소리는 첫 샘플부터.
공용 도구는 고치지 않는다 — 이 파일은 부르기만.
    PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/05_고양이_이븐훅/make_hook.py still|tts|render|master|copy
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

W = Path("C:/숏템_칼카피/hottemreport/현장썰하이브리드/05_고양이_이븐훅")
SRC = Path("C:/숏템_칼카피/hottemreport/현장썰하이브리드/05_고양이/front/src/tt_7667682859624238367.mp4")
PART2 = Path("C:/숏템_칼카피/hottemreport/현장썰하이브리드/05_고양이/hybrid/render/final.mp4")
DESK = Path("C:/Users/CH/Desktop/칼카피영상/숏템리폿/하이브리드/칼카피_숏템리폿_고양이빵봉지집게_이븐훅_시험.mp4")
DRIVE = Path("G:/내 드라이브/칼카피영상/3번 숏템리폿/하이브리드/10_cat_bag_clip_evenhook_test.mp4")
PRESET = ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json"

TEXT = "해외 아빠가 사 오자마자, 딸이 단번에 알아본 이 집게의 정체."
TITLE = {"hook1": "아빠가 사 온 집게", "hook2": "딸이 단번에 알아본 정체", "bodyTitle": "이 집게 정체가 뭐길래?"}
VOICE, VNAME, TEMPO = "tc_6059dad0b83880769a50502f", "박창수", 1.2
CPS_TARGET, ATEMPO_MAX = 8.3, 1.27
LEAD, TAIL, XF = 0.10, 0.30, 0.25          # 나레 앞 · 나레 뒤 쉼 · 이음 겹침
FPS, SR = 30, 48000
CROP_Y = 300                               # 1080x1920 → 1080x1407 창(숏템 t11 본문 칸 비율)
# 컷(원본 초, 길이) — 0초 = 아빠 얼굴 옆 흰 고양이 집게 클로즈업(샷 경계 55.8 뒤), 그다음 끼움·줄 선 봉지(되감김 없음: ② 첫 컷 6.7초와 멂)
CUTS = [(56.0, 1.4, "아빠 얼굴 옆 흰 고양이 집게 클로즈업"), (49.0, 1.1, "흰 고양이 집게를 봉지에 끼움"), (54.5, None, "고양이 집게 단 봉지들 + 딸 엄지")]
CUT_MAX = {54.5: 1.25, 56.0: 2.95, 49.0: 1.5}


def run(c, **k):
    r = subprocess.run([str(x) for x in c], capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode:
        raise SystemExit(f"실패 {c[:4]}…\n{r.stderr[-1500:]}")
    return r


def dur(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def loud(p, extra=None):
    c = ["ffmpeg", "-hide_banner"] + (extra or []) + ["-i", p, "-af", "ebur128=peak=true", "-f", "null", "-"]
    e = subprocess.run([str(x) for x in c], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def nchar(s):
    return len(re.findall(r"[가-힣A-Za-z0-9]", s))


def snap_head():
    from shopping_shorts import scene_style
    M = json.loads(PRESET.read_text(encoding="utf-8"))
    snap = scene_style.validate_snapshot({"mode": "story", "presetId": M["template"]["preset_id"],
                                          "text": {"channel": M["brand"]["channel_name"], **TITLE}})
    head = {"text": f"{TITLE['hook1']}\n{TITLE['hook2']}", "body_title": TITLE["bodyTitle"]}
    return snap, head


def tl(d1):
    return [{"beat_idx": 0, "t0": 0.0, "dur": round(d1, 3), "narration": TEXT, "caption_lines": [TEXT], "role": "hook",
             "primary": {"video_id": "s0", "start": 0.0, "end": round(d1, 3)}}]


def still():
    """TTS 전 틀 확인 — 컷 첫 프레임마다 t11 훅 정지 그림(compose_still = compose 와 같은 기하)."""
    from shopping_shorts import scene_style
    out = W / "still"; out.mkdir(parents=True, exist_ok=True)
    snap, head = snap_head()
    for ss, _, _ in CUTS:
        png = out / f"src_{ss}.png"
        run(["ffmpeg", "-y", "-ss", f"{ss + 0.05}", "-i", SRC, "-frames:v", "1", "-vf", f"crop=1080:1407:0:{CROP_Y}", png])
        scene_style.compose_still(png, tl(3.6), snap, out / f"w_{ss}", 0, out / f"hook_{ss}.jpg", head)
        print("still", out / f"hook_{ss}.jpg")


def tts():
    from tools.calcopy.engine import narr_align as NA
    full = W / "narr_full.mp3"
    NA.synth_cached(TEXT, VOICE, TEMPO, full)
    tight = W / "narr_tight.wav"
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    run(["ffmpeg", "-y", "-i", full, "-af", f"{f},areverse,{f},areverse", "-ar", SR, "-ac", "1", tight])
    d0 = dur(tight); rate = nchar(TEXT) / d0
    at = round(min(ATEMPO_MAX, max(1.0, CPS_TARGET / rate)), 3)
    narr = W / "narr.wav"
    run(["ffmpeg", "-y", "-i", tight, "-af", f"atempo={at}", "-ar", SR, "-ac", "1", narr])
    dn = dur(narr)
    info = {"text": TEXT, "voice": VNAME, "voice_id": VOICE, "tempo": TEMPO, "raw_s": round(d0, 3), "raw_cps": round(rate, 2),
            "atempo": at, "narr_s": round(dn, 3), "cps": round(nchar(TEXT) / dn, 2)}
    if at > 1.0:   # 지침서 §12: 배속을 올린 나레는 받아쓰기로 발음 대조
        from tools.calcopy.engine import asr_local
        r = asr_local.transcribe(str(narr), engine="speechmatics")
        info["asr"] = r.get("text") if isinstance(r, dict) else str(r)
        info["asr_engine"] = r.get("engine") if isinstance(r, dict) else None
    (W / "tts.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))


def render():
    from shopping_shorts import scene_style, sfx_pack as SP
    T = json.loads((W / "tts.json").read_text(encoding="utf-8"))
    narr = W / "narr.wav"
    d1 = round((LEAD + T["narr_s"] + TAIL + XF) * FPS) / FPS          # ① 영상 길이(뒤 0.25초는 이음 겹침)
    R = W / "render"; shutil.rmtree(R, ignore_errors=True); R.mkdir(parents=True)
    # 재료(1080x1407, 원음 없음)
    nfs, used = [], 0
    for k, (ss, ln, _) in enumerate(CUTS):
        n = round((ln if ln else d1 - sum(c[1] for c in CUTS if c[1])) * FPS) if k < len(CUTS) - 1 else round(d1 * FPS) - used
        if ss in CUT_MAX and n / FPS > CUT_MAX[ss] + 1e-6:
            raise SystemExit(f"컷 {ss} {n / FPS:.2f}초 > 원본 샷 {CUT_MAX[ss]}")
        p = R / f"m{k}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{ss:.3f}", "-i", SRC, "-an", "-vf", f"crop=1080:1407:0:{CROP_Y},fps={FPS},setsar=1", "-frames:v", n,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        nfs.append(n); used += n
    (R / "m.txt").write_text("".join(f"file '{(R / f'm{k}.mp4').as_posix()}'\n" for k in range(len(CUTS))), encoding="utf-8")
    mat = R / "material.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "m.txt", "-c", "copy", mat])
    # 틀(t11 훅)
    snap, head = snap_head()
    vid1 = R / "hook_video.mp4"
    scene_style.compose(str(mat), tl(d1), snap, str(vid1), R / "compose", head)
    # 효과음(팩21, low) — 훅 칸 + 이음 자리에 둘째 칸을 세워 whoosh 를 받는다
    j = round(d1 - XF, 3)
    stl = [{"beat_idx": 0, "t0": 0.0, "dur": j, "narration": TEXT, "caption_lines": [TEXT], "cap_durs": [j], "cap_lead": 0.0, "cap_offset": 0.0, "role": "title"},
           {"beat_idx": 1, "t0": j, "dur": 3.0, "narration": "다음", "caption_lines": ["다음"], "cap_durs": [3.0], "cap_lead": 0.0, "cap_offset": 0.0, "role": "body"}]
    pname, pdir = SP.pack_for(0)
    evs_all = SP.events(stl, {"name": pname, "dir": pdir, "density": "low", "level": "normal", "mute_beats": []})
    evs = [e for e in evs_all if e[1] < j - 0.2]                      # ① 안(오프너)
    jev = [e for e in evs_all if j - 0.2 <= e[1] < d1]                # 이음매(휙+틱) — ① 소리를 j 에서 자르므로 합친 뒤에 얹는다
    # ① 소리 = 나레 + 효과음, 길이 j(② 소리는 j 부터)
    ins, flt, lab = ["-i", narr], [f"[0:a]adelay={int(LEAD * 1000)}|{int(LEAD * 1000)}[n]"], ["[n]"]
    for k, (pth, t, mul) in enumerate(evs):
        ins += ["-i", pth]; ms = int(round(t * 1000))
        flt.append(f"[{k + 1}:a]aresample={SR},aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{k}]"); lab.append(f"[s{k}]")
    flt.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,apad=whole_dur={d1},atrim=0:{j:.4f}[m]")
    a1raw = R / "a1_raw.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[m]", "-ar", SR, "-ac", "2", a1raw])
    # 크기 맞춤: ① 나레 LUFS = ② N1 구간(0~3.4초) LUFS
    ref, _ = loud(PART2, ["-t", "3.4"])
    nI, _ = loud(narr)
    a1I, _ = loud(a1raw)
    g = ref - nI                               # 나레 기준으로 맞춘다(효과음은 같이 움직임)
    a1 = R / "a1.wav"
    run(["ffmpeg", "-y", "-i", a1raw, "-af", f"volume={g:.2f}dB", "-ar", SR, "-ac", "2", a1])
    # 합치기
    raw = R / "final_raw.mp4"
    fc = (f"[0:v]fps={FPS},format=yuv420p,setsar=1,settb=1/{FPS * 1000}[v0];[1:v]fps={FPS},format=yuv420p,setsar=1,settb=1/{FPS * 1000}[v1];"
          f"[v0][v1]xfade=transition=slideleft:duration={XF}:offset={j:.4f}[v];"
          f"[2:a]aresample={SR}[a0];[1:a]aresample={SR}[a1];[a0][a1]concat=n=2:v=0:a=1[c]")
    jin, jl = [], ["[c]"]
    for k, (pth, t, mul) in enumerate(jev):
        jin += ["-i", pth]; ms = int(round(t * 1000))
        fc += f";[{3 + k}:a]aresample={SR},aformat=channel_layouts=stereo,volume={mul * 10 ** (g / 20):.4f},adelay={ms}|{ms}[j{k}]"; jl.append(f"[j{k}]")
    fc += ";" + "".join(jl) + f"amix=inputs={len(jl)}:normalize=0:duration=first[a]"
    run(["ffmpeg", "-y", "-i", vid1, "-i", PART2, "-i", a1, *jin, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, raw])
    info = {"d1": d1, "junction": j, "cuts": [{"ss": c[0], "frames": n, "see": c[2]} for c, n in zip(CUTS, nfs)],
            "sfx": [[Path(e[0]).stem, e[1], e[2]] for e in evs], "sfx_junction": [[Path(e[0]).stem, e[1], e[2]] for e in jev], "sfx_all": [[Path(e[0]).stem, e[1]] for e in evs_all],
            "ref_N1_lufs": ref, "narr_lufs": nI, "a1_raw_lufs": a1I, "gain": round(g, 2), "raw": str(raw), "raw_dur": dur(raw), "part2_dur": dur(PART2)}
    (R / "render_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))


def master():
    R = W / "render"
    src, out = R / "final_raw.mp4", R / "final.mp4"
    g = round(-14.0 - loud(src)[0], 2)
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", src, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af",
             f"volume={g}dB,alimiter=limit=0.75:attack=1:release=40:level=false,aresample={SR}", "-c:a", "aac", "-b:a", "192k", "-ar", SR, out])
        lu, pk = loud(out)
        if abs(lu + 14.0) <= 0.2:
            break
        g = round(g + (-14.0 - lu), 2)
    lu, pk = loud(out)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(out, HERE / "final_sheet_1s.jpg")
    seam = R / "seam"; seam.mkdir(exist_ok=True)
    info = json.loads((R / "render_info.json").read_text(encoding="utf-8"))
    j = info["junction"]
    for k in range(-3, 6):
        t = j + k * 0.1
        run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", out, "-frames:v", "1", "-vf", "scale=270:480", seam / f"s{k + 3:02d}_{t:.2f}.png"])
    for t in (0.0, 1.0, 2.0, 3.0):
        run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", out, "-frames:v", "1", R / f"f{int(t)}.png"])
    info.update({"master_gain": g, "lufs": lu, "peak": pk, "dur": dur(out)})
    (R / "render_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print("master", out, dur(out), lu, pk)


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copy():
    out = W / "render/final.mp4"
    DESK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, DESK)
    print("md5 work", md5(out), "desk", md5(DESK), "drive", md5(DRIVE) if DRIVE.exists() else "없음")


if __name__ == "__main__":
    {"still": still, "tts": tts, "render": render, "master": master, "copy": copy}[sys.argv[1]]()
