# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 1호 한고은 채소통 — 재미썸홈판 렌더(엔진 코드 수정 없음, 관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/재미썸홈판/make_render.py [front|back|join|all]

앞 11초 = 얜샷템 틀(channel/mantem/frame_얜샷템.json, 제목·출처만 바꿈) — 앞 편 annapick 1편 make_render 와 같은 길:
  나레 무음 끼우기 → narr_video.build(line_asr=False, 자막 전부 caption_events emph: 원음 흰·나레 노랑) → hottem_audio.add_source_bed(원음 = 한고은 말만)
  → BGM sweets 원음 창 덕킹 → render/front.mp4
뒤 = 재미썸홈(숏템 t11, frameRule body_all) — 정본 channel/evenshopping/작품1_총알람/render.py(--v4) 와 같은 길:
  필재 나레(make_tts.py 1회 합성) → narr_video.time_steps(줄 시작 고정·줄 안 글자 비례) → 묶음 컷 재료(1080×1408) → scene_style.compose
  → 숏템 효과음팩(sfx_pack density=low) · BGM 없음 → render/back.mp4
이음 = 컷 1곳(앞 원음 '귀찮으니까' 끝 → 뒤 다리 나레). 소리는 그대로 이어 붙인다 → render/final.mp4 → 바탕화면 칼카피영상/얜샷템.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(D))
import make_plan as MP  # noqa: E402
from tools.calcopy import narr_video as nv, hottem_audio as ha  # noqa: E402

W = MP.W
SRC = W / "src"
R = W / "render"
FPS = 30
LUFS_ALL = MP.PRESET["measured"]["lufs"]["I"]   # −13.4 재미썸홈(이븐쇼핑 47편) — 앞도 같은 크기로 맞춰 이음매 소리 급변 없게
TP = -2.0
DESK = Path.home() / "Desktop/칼카피영상/얜샷템/칼카피_얜샷템_한고은채소통_재미썸홈판.mp4"
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"
TTEUTGI = ROOT / "channel/annapick/뜯기/itYwQVyuCcc/뜯기.json"
VOICE = "hge_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
GAINS = [15.0, 15.0]             # 원음 창 올림(앞 편 실측 +15dB)
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
SFX_ROLES = [k for k, _ in MP.LINES]


def run(cmd):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")


def run_bytes(cmd):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True).stdout


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def norm_to(src_mp4, out_mp4, target, raw_wav=None):
    """소리를 target LUFS 로(압축 약하게 + 리미터) — 반복 보정."""
    raw = raw_wav or (R / f"_{Path(out_mp4).stem}_raw.wav")
    if raw_wav is None:
        run(["ffmpeg", "-y", "-i", str(src_mp4), "-vn", "-ac", "2", "-ar", "44100", str(raw)])
    mix = R / f"_{Path(out_mp4).stem}_mix.wav"
    gain = target - lufs(raw)[0]
    for _ in range(10):
        run(["ffmpeg", "-y", "-i", str(raw), "-af",
             f"acompressor=threshold=0.125:ratio=4:attack=2:release=60,volume={gain:.2f}dB,alimiter=limit={10 ** (TP / 20):.4f}:level=false:attack=1:release=30",
             "-ar", "44100", str(mix)])
        oI, _ = lufs(mix)
        if abs(oI - target) <= 0.3:
            break
        gain += (target - oI) * 0.9
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_mp4)])
    return round(gain, 2)


# ───────────────────────── 앞(얜샷템) ─────────────────────────
def ramp(a, b, g, up=0.08, down=0.10, depth=6.0):
    st = 4
    out = [[round(a + up * i / st, 3), round(a + up * (i + 1) / st, 3), round(g - 12 * (1 - (i + 1) / st), 2)] for i in range(st)]
    out.append([round(a + up, 3), round(b - down, 3), g])
    out += [[round(b - down + down * i / st, 3), round(b - down + down * (i + 1) / st, 3), round(g - depth * (i + 1) / st, 2)] for i in range(st)]
    return out


def front_plan():
    """앞 시각표 — H 원음 0~3.10 · TTS 3.20~ · O5 원음(788.18~791.55 + 791.62~793.59)."""
    t_tts = dur_of(R / "front_tts.wav")
    H, O5 = MP.ORIG["H"], MP.ORIG["O5"]
    h_len = round(H["audio"][0][1] - H["audio"][0][0], 3)
    tts0 = round(h_len + 0.10, 3)
    o5_0 = round(tts0 + t_tts + 0.10, 3)
    seg_a = round(O5["audio"][0][1] - O5["audio"][0][0], 3)
    seg_b = round(O5["audio"][1][1] - O5["audio"][1][0], 3)
    total = round(o5_0 + seg_a + seg_b, 3)
    hs, ts, (oa, ob) = H["shots"][0], MP.FRONT_TTS_SHOT, O5["shots"]
    h_scr = round(h_len + 0.04, 3)   # 화면은 원본 컷(783.92) 전까지
    shots = [  # (src, ss, crop, t0, t1, audio_ss)
        ("hge_LcQv9yOh3Wc.mp4", hs["ss"], hs["crop"], 0.0, h_scr, H["audio"][0][0], hs["seen"]),
        ("hge_LcQv9yOh3Wc.mp4", ts["ss"], ts["crop"], h_scr, o5_0, None, ts["seen"]),
        ("hge_LcQv9yOh3Wc.mp4", oa["ss"], oa["crop"], o5_0, round(o5_0 + seg_a, 3), O5["audio"][0][0], oa["seen"]),
        ("hge_LcQv9yOh3Wc.mp4", ob["ss"], ob["crop"], round(o5_0 + seg_a, 3), total, O5["audio"][1][0], ob["seen"]),
    ]
    caps = [(t, c, "원음") for t, c in H["caps"]]
    fc = MP.FRONT_TTS["caps"]
    n = [MP.nchar(c) for c in fc]
    acc = 0
    for c, k in zip(fc, n):
        caps.append((round(tts0 + t_tts * acc / sum(n), 3), c, "나레")); acc += k
    caps += [(round(o5_0 + t, 3), c, "원음") for t, c in O5["caps"]]
    return {"t_tts": t_tts, "tts0": tts0, "o5_0": o5_0, "total": total, "shots": shots, "caps": caps,
            "windows": [(0.0, h_len), (o5_0, total)]}


def bgm_mix(src_mp4, out_mp4, win, dur):
    from shopping_shorts import bgm_lib
    bgm = bgm_lib.path_of(BGM)
    k = 10 ** (DUCK_DB / 20)
    dur = dur_of(src_mp4)   # 영상 길이 그대로(소리가 짧으면 -shortest 가 끝 '귀찮으니까'를 잘랐다 — 10.94 vs 11.03 실측)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win)
    tmp = R / "front_bgm.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bgm, "-t", f"{dur:.3f}", "-af", f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={BGM_DB}:TP=-6:LRA=11,"
         f"volume='{terms}':eval=frame,afade=t=out:st={dur - 0.6:.3f}:d=0.6", "-c:a", "pcm_s16le", str(tmp)])
    mixed = R / "front_mixraw.wav"
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono,apad[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         f"[m][b]amix=inputs=2:normalize=0:duration=longest,atrim=0:{dur:.3f},aresample=44100,aformat=channel_layouts=stereo[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    return norm_to(src_mp4, out_mp4, LUFS_ALL, raw_wav=mixed)


def front():
    R.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    hg = SRC / "hge_LcQv9yOh3Wc.mp4"
    if not hg.exists():
        os.link(MP.HG, hg)   # 재료 담당 폴더는 읽기만 — 하드링크
    if not (SRC / VOICE).exists():
        run(["ffmpeg", "-y", "-i", str(hg), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    P = front_plan()
    total = P["total"]
    wav = R / "front_gapped.wav"
    run(["ffmpeg", "-y", "-i", str(R / "front_tts.wav"), "-af", f"aresample=48000,aformat=channel_layouts=mono,adelay={int(P['tts0'] * 1000)},apad=whole_dur={total:.3f},atrim=0:{total:.3f}",
         "-c:a", "pcm_s16le", "-ar", "48000", str(wav)])
    L = [MP.FRONT_TTS["text"]]
    steps, dur = nv.time_steps(nv.steps_of(L, 10, "replace"), str(wav), lines=L, asr=False)
    shots_r = [{"i": 0, "full": True, "kind": "원본재편집", "src": P["shots"][0][0], "ss": P["shots"][0][1], "src_crop": P["shots"][0][2],
                "cuts": [{"src": s, "ss": ss, "src_crop": cr, "dur": round(b - a, 3), "plan_i": i} for i, (s, ss, cr, a, b, au, _) in enumerate(P["shots"])],
                "t_final": [0.0, round(dur, 3)]}]
    tl = [[a, b] for _, _, _, a, b, _, _ in P["shots"]]
    aud = []
    for i, (s, ss, cr, a, b, au, _) in enumerate(P["shots"]):
        x = {"i": i, "src": s, "ss": ss, "plan_i": i, "t_final": [a, b]}
        if au is None:
            x["mute"] = True
        else:
            x["audio_src"], x["audio_ss"] = VOICE, au
        aud.append(x)
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py front() — 앞 4컷(얜샷템 틀)", "cand_dir": str(SRC), "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "front_audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "front_audio_materials.json").write_text(json.dumps({"cand_dir": str(SRC), "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    fr0 = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr0["layers"] if l.get("role") == "caption")["rgb"]
    cp = P["caps"]
    ev = []
    for j, (t0, text, who) in enumerate(cp):
        b = cp[j + 1][0] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": text, "rgb": ycol if who == "나레" else [255, 255, 255], "t0": t0, "dur": round(b - t0, 3), "who": who})
    S = {"final": {"lines": [{"text": L[0]}]}, "caption_events": ev, "render": {"windows": P["windows"], "dur": dur, "plan": {k: v for k, v in P.items() if k != "shots"}}}
    (D / "대본_render.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    for l in fr0["layers"]:
        if l.get("role") == "title":
            l["text"] = MP.FRONT_TITLE
        if l.get("role") == "label":
            l["text"] = MP.FRONT_LABEL
    (D / "frame_render.json").write_text(json.dumps(fr0, ensure_ascii=False, indent=1), encoding="utf-8")
    out = R / "front_build"
    plan_ = {"tteutgi": str(TTEUTGI), "frames": [{"frame": str(D / "frame_render.json"), "t_end": None}], "script": str(D / "대본_render.json"),
             "tts": str(wav), "materials": str(D / "재료_render.json"), "out": str(out), "bgm": None, "lufs": -15.0, "chunk": 10,
             "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    # build 완성본 소리는 받아쓰기 길이(10.94초)에서 끝난다 — 영상 길이까지 무음을 채워야 끝 원음 '귀찮으니까'가 안 잘린다(엔진 우회 ⑦)
    vlen = dur_of(final)
    padded = R / "front_build_pad.mp4"
    run(["ffmpeg", "-y", "-i", str(final), "-af", f"apad=whole_dur={vlen:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(padded)])
    final = str(padded)
    gg = [r for w, g in zip(P["windows"], GAINS) for r in ramp(w[0], min(w[1] + 0.10, vlen), g)]
    ha.add_source_bed(str(final), str(R / "front_audio_timeline.json"), str(R / "front_audio_materials.json"), str(wav), str(R / "front_src.mp4"),
                      1.0, 10.0, work=str(R / "front_srcbed"), gap_gain=gg)
    g = bgm_mix(R / "front_src.mp4", R / "front.mp4", P["windows"], dur)
    rep = {"dur": dur_of(R / "front.mp4"), "lufs": lufs(R / "front.mp4"), "gain": g, "plan": {k: v for k, v in P.items() if k != "shots"},
           "orig": ha.measure(str(R / "front.mp4"), P["windows"]), "narr": ha.measure(str(R / "front.mp4"), [(P["tts0"], P["tts0"] + P["t_tts"])])}
    (R / "front.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("FRONT", json.dumps(rep, ensure_ascii=False))


# ───────────────────────── 뒤(재미썸홈 t11) ─────────────────────────
def clip_of(g, n, out):
    """묶음 컷 하나 → 1080×1408 영상(n 프레임). 영상 = 크롭→확대, 사진 = 각인 흐림 뒤 천천히 확대(1.00→1.06)."""
    x, y, w, h = g["crop"]
    if g["src"].startswith("img:"):
        im = MP.still_img(g["src"][4:]).crop((x, y, x + w, y + h)).resize((1080 * 2, 1408 * 2))
        png = R / "parts" / f"{out.stem}.png"
        im.save(png)
        z = f"zoompan=z='1+0.06*on/{max(1, n - 1)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1408:fps={FPS}"
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-vf", f"{z},setsar=1", "-frames:v", str(n), "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", str(out)])
        return
    p = MP.path_of(g["src"])
    run(["ffmpeg", "-y", "-ss", f"{g['ss']:.3f}", "-i", str(p), "-an", "-vf",
         f"crop={w}:{h}:{x}:{y},scale=1080:1408:flags=lanczos,setsar=1,fps={FPS}", "-frames:v", str(n),
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])


def back():
    narr = R / "back_narr_fix.wav"
    lines = [s for _, s in MP.LINES]
    rows, _, _ = MP.back_rows()
    steps, li, used = [], 0, 0
    for r in rows:
        n = MP.nchar(r["caption"])
        while used >= MP.nchar(lines[li]):
            li, used = li + 1, 0
        steps.append({"text": r["caption"], "chars": n, "new_cut": True, "line": li}); used += n
    # 시각 = make_tts --fix 가 줄을 갈라 붙인 줄 말 구간(계산값 그대로 — 받아쓰기 시각은 실행마다 흔들림, 작품1 수정3 교훈).
    #   줄 안 조각은 글자 비례, 줄 첫 조각은 그 줄 말 시작에서(앞 줄 자막은 쉼 동안 유지).
    FX = json.loads((R / "tts.json").read_text(encoding="utf-8"))["fix"]
    dur = dur_of(narr)
    timed = []
    for k, (a, b) in enumerate(FX["spans"]):
        mine = [s_ for s_ in steps if s_["line"] == k]
        tot, acc = sum(s_["chars"] for s_ in mine), 0
        for s_ in mine:
            timed.append({**s_, "t0": round(a + (b - a) * acc / tot, 3)}); acc += s_["chars"]
    timed[0]["t0"] = 0.0
    for i, s_ in enumerate(timed):
        s_["t1"] = timed[i + 1]["t0"] if i + 1 < len(timed) else dur
    how = "줄 구간(make_tts --fix) + 줄 안 글자 비례"
    spans = [tuple(x) for x in FX["spans"]]
    line_rate = [round(MP.nchar(l) / (b - a), 2) for l, (a, b) in zip(lines, spans)]
    END = round(dur + 0.5, 3)
    timed[-1]["t1"] = END
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir()
    cuts, groups = [], []
    for k, (st, r) in enumerate(zip(timed, rows)):
        f0, f1 = round(st["t0"] * FPS), round(st["t1"] * FPS)
        if r["cont"]:
            g = groups[-1]; g["f1"] = f1; g["pieces"].append(k + 1)
        else:
            groups.append({"src": r["src"], "ss": r["src_t0"], "crop": r["crop"], "kind": r["kind"], "f0": f0, "f1": f1, "pieces": [k + 1], "seen": r["seen"]})
        cuts.append({"i": k + 1, "t0": round(f0 / FPS, 3), "t1": round(f1 / FPS, 3), "caption": r["caption"], "line": st["line"], "cut": len(groups)})
    lst = []
    for gi, g in enumerate(groups):
        n = max(1, g["f1"] - g["f0"])
        out = parts / f"p{gi:02d}.mp4"
        clip_of(g, n, out)
        lst.append(f"file '{out.as_posix()}'")
        g["t0"], g["t1"], g["dur"] = round(g["f0"] / FPS, 3), round(g["f1"] / FPS, 3), round(n / FPS, 3)
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "back_material.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(parts / "list.txt"), "-c", "copy", str(mat)])
    total = cuts[-1]["t1"]

    from shopping_shorts import scene_style
    T = MP.PRESET["sample_title"]
    snap = scene_style.validate_snapshot({"mode": "story", "presetId": MP.PRESET["template"]["preset_id"], "frameRule": "body_all",
                                          "text": {"channel": MP.PRESET["brand"]["channel_name"], "hook1": T["hook1"], "hook2": T["hook2"], "bodyTitle": MP.BODY_TITLE}})
    tl = [{"beat_idx": i, "t0": c["t0"], "dur": round(c["t1"] - c["t0"], 3), "narration": c["caption"], "caption_lines": [c["caption"]], "role": "body",
           "primary": {"video_id": "s0", "start": c["t0"], "end": c["t1"]}} for i, c in enumerate(cuts)]
    vid = R / "back_video.mp4"
    shutil.rmtree(R / "back_work", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(vid), R / "back_work", {"text": f"{T['hook1']}\n{T['hook2']}", "body_title": MP.BODY_TITLE})

    import numpy as np
    from shopping_shorts import sfx_pack as SP
    a = np.frombuffer(run_bytes(["ffmpeg", "-v", "error", "-i", str(narr), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"]), dtype=np.float32)
    k20 = int(0.02 * 44100); fr = a[: len(a) // k20 * k20].reshape(-1, k20)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    vmed = float(np.median(rms[rms > rms.max() - 30]))
    ngain = -17.5 - vmed
    stl = []
    for li, line in enumerate(lines):
        mine = [c for c in cuts if c["line"] == li]
        t0, t1 = mine[0]["t0"], mine[-1]["t1"]
        stl.append({"beat_idx": li, "t0": t0, "dur": round(t1 - t0, 3), "narration": " ".join(c["caption"] for c in mine),
                    "caption_lines": [c["caption"] for c in mine], "cap_durs": [round(c["t1"] - c["t0"], 3) for c in mine],
                    "cap_lead": 0.0, "cap_offset": 0.0, "role": SFX_ROLES[li]})
    pname, pdir = SP.pack_for(0)
    pack = {"name": pname, "dir": pdir, "density": "low", "level": "normal", "mute_beats": []}
    plan = SP.plan_events(stl, density="low")
    evs = SP.events(stl, pack)
    (R / "back_sfx_events.json").write_text(json.dumps({"pack": pname, "plan": plan, "events": evs, "timeline": stl}, ensure_ascii=False, indent=1), encoding="utf-8")
    ins, flt, lab = ["-i", str(narr)], [], []
    for j, (path, t, mul) in enumerate(evs):
        ins += ["-i", path]
        ms = int(round(t * 1000))
        flt.append(f"[{1 + j}:a]aresample=44100,aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{j}]"); lab.append(f"[s{j}]")
    flt.append(f"[0:a]aformat=channel_layouts=mono,volume={ngain:.2f}dB,apad=whole_dur={total:.3f}[n]")
    flt.append(f"[n]{''.join(lab)}amix=inputs={1 + len(lab)}:normalize=0:duration=first,aformat=channel_layouts=stereo[o]")
    raw = R / "back_mix_raw.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[o]", "-ar", "44100", "-ac", "2", str(raw)])
    gain = norm_to(vid, R / "back.mp4", LUFS_ALL, raw_wav=raw)
    rep = {"dur": dur_of(R / "back.mp4"), "lufs": lufs(R / "back.mp4"), "timing": how, "line_rate": line_rate, "pieces": len(cuts), "cuts": len(groups),
           "cut_median": round(sorted(g["dur"] for g in groups)[len(groups) // 2], 3), "cut_min": min(g["dur"] for g in groups),
           "last_cut": groups[-1]["dur"], "sfx": len(evs), "pack": pname, "mix_gain_db": gain, "max_caption": max(len(c["caption"]) for c in cuts)}
    (R / "back_timeline.json").write_text(json.dumps({"report": rep, "cuts": cuts, "groups": groups, "tl": tl}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("BACK", json.dumps(rep, ensure_ascii=False))


# ───────────────────────── 잇기 ─────────────────────────
def join():
    f, b = R / "front.mp4", R / "back.mp4"
    final = R / "final.mp4"
    fc = ("[0:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[v0];[1:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[v1];"
          "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
          "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    run(["ffmpeg", "-y", "-i", str(f), "-i", str(b), "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    DESK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(final, DESK)
    md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, DESK)]
    rep = {"final": str(final), "desktop": str(DESK), "md5": md5, "dur": dur_of(final), "lufs": lufs(final), "seam": dur_of(f)}
    (R / "final.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("FINAL", json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("front", "all"):
        front()
    if what in ("back", "all"):
        back()
    if what in ("join", "all"):
        join()
