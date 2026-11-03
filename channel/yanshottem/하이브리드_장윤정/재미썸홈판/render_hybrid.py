# -*- coding: utf-8 -*-
"""렌더 — make.py 의 PLAN 상수만 읽는다(시각의 주인 = make.py). 엔진은 부르기만:
  A: narr_video.shot_clip(컷) · narr_video.emph_png(자막) · scene_style.compose(얜샷템 틀 → calcopy_frame.to_snapshot)
  B: scene_style.compose(t11, 재미썸홈, frameRule body_all) · narr_video.time_steps(조각 시각, 줄 시작 받아쓰기) · sfx_pack.events(density low)
    PYTHONUTF8=1 py make.py render
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import make as M
from tools.calcopy import narr_video as N
from shopping_shorts import scene_style, bgm_lib
from shopping_shorts.calcopy_frame import schema, to_snapshot

R, SRC, FPS = M.R, M.SRC, M.FPS
SR = 48000


def run(cmd):
    return M.run(cmd)


def fr(t):
    return round(t * FPS)


# ── 나레: 앞뒤 무음 자르기 + 0.28초 넘는 쉼만 0.28초로(atempo 1.27 뒤 0.22 = B18 하한)(atempo 뒤 ≈0.21~0.26)(쉼 자리는 안 만든다·안 없앤다) → atempo ─────────
def narr_prep():
    """앞뒤 무음 자르기 + 0.28초 넘는 쉼만 0.28초로(atempo 1.27 뒤 0.22 = B18 하한) → atempo. 끝 문장(L7)은 TTS가 빨리 읽어(원속 9.1자/초) 1.27 대신 TEMPO_LAST(B15 끝 문장만)."""
    full, tight, narr = R / "narr_full.mp3", R / "narr_tight.wav", R / "narr.wav"
    f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
    mid = "silenceremove=stop_periods=-1:stop_duration=0.28:stop_threshold=-40dB:stop_silence=0.28"
    run(["ffmpeg", "-y", "-i", str(full), "-af", f"{f},areverse,{f},areverse,{mid}", "-ar", str(SR), "-ac", "1", str(tight)])
    chars = sum(M.nchar(l[2]) for l in M.LINES)
    d0 = M.dur_of(tight)
    segs, _ = N.speech_segments(str(tight), "-40dB", 0.1)
    split = segs[-1][0] - 0.02                    # 마지막 쉼(여럿이던데, |) 끝 = L7 시작
    p1, p2 = R / "narr_p1.wav", R / "narr_p2.wav"
    run(["ffmpeg", "-y", "-i", str(tight), "-af", f"atrim=0:{split:.3f},atempo={M.TEMPO}", "-ar", str(SR), str(p1)])
    run(["ffmpeg", "-y", "-i", str(tight), "-af", f"atrim={split:.3f},asetpts=PTS-STARTPTS,atempo={M.TEMPO_LAST}", "-ar", str(SR), str(p2)])
    pre = R / "narr_pre.wav"
    run(["ffmpeg", "-y", "-i", str(p1), "-i", str(p2), "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-ar", str(SR), "-ac", "1", str(pre)])
    # 쉼 모양 = 엔진 tts_pause.shape(쉼표 0.22·마침표 0.30). 글자 시각 대신 문장부호 자리의 쉼(make.PUNCT_AT 근처 무음)을 넘긴다
    from tools.calcopy.engine import tts_pause as TP
    TP.PAUSE = {",": 0.235, ".": 0.315}   # 이음매 겹침 15ms 만큼 짧게 나와(실측 0.205/0.285) 그만큼 더 줌 → 0.22/0.30
    sil = [(a_, b_) for a_, b_ in _silences(pre)]
    ch, st, en, slots = [], [], [], []
    for kind, at in M.PUNCT_AT:
        a_, b_ = min(sil, key=lambda x: abs((x[0] + x[1]) / 2 - at))
        assert abs((a_ + b_) / 2 - at) < 0.2, (kind, at, a_, b_)
        ch += ["가", kind, "가"]; st += [a_ - 0.05, a_, b_]; en += [a_, b_, b_ + 0.05]; slots.append((a_, b_))
    log = TP.shape(str(pre), {"characters": ch, "character_start_times_seconds": st, "character_end_times_seconds": en}, str(R / "narr_shaped.mp3"))
    run(["ffmpeg", "-y", "-i", str(R / "narr_shaped.mp3"), "-ar", str(SR), "-ac", "1", str(narr)])
    # 줄 머리 = 문장부호 쉼 끝(옮긴 뒤 시각) — PUNCT_AT 1~7 이 줄 0~6 의 끝
    shift, ends = 0.0, []
    for k, ((a_, b_), lg) in enumerate(zip(slots, log)):   # 이음매(15ms 겹침)마다 그만큼 앞당겨진다: 쉼 k 끝까지 이음매 2k+1개
        shift += lg["now"] - lg["was"]
        ends.append(round(b_ + shift - TP.XF_SEC * (2 * k + 1), 3))
    return narr, {"all": M.TEMPO, "last": M.TEMPO_LAST, "split_raw": round(split, 3), "pauses": log}, chars, d0, [0.0] + ends[1:]


def _silences(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "silencedetect=n=-40dB:d=0.08", "-f", "null", "-"],  # 이 편: 샀는데 쉼이 0.098초(필재 1.12배)라 d=0.08
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    import re
    return list(zip(map(float, re.findall(r"silence_start: ([\d.]+)", r)), map(float, re.findall(r"silence_end: ([\d.]+)", r))))


def main():
    R.mkdir(parents=True, exist_ok=True)
    work = R / "work"; shutil.rmtree(work, ignore_errors=True); work.mkdir()
    narr, tempo, chars, d0, line_heads = narr_prep()
    dn = M.dur_of(narr)
    print(f"TTS {chars / d0:.2f}자/초 → atempo {tempo} → {chars / dn:.2f}자/초 ({dn:.2f}초)")
    lines = [l[2] for l in M.LINES]
    pl = M.piece_lines()
    steps = [{"text": p[0], "chars": M.nchar(p[0]), "new_cut": True, "line": li} for p, li in zip(M.PIECES, pl)]
    # 줄 시작 = make.LINE_STARTS(나레 쉼 끝 실측 + 받아쓰기 2초 토막으로 줄 머리 확인) — 엔진 줄 시작 받아쓰기가 빈 답·약한 모델로
    # 0.3~0.5초 어긋나 이 편만 고정값(엔진 요청 기록). 줄 안 조각은 엔진 _place(말 구간 글자 비례) 그대로.
    segs, ndur = N.speech_segments(str(narr))
    W = list(line_heads) + [ndur]
    assert len(W) == len(lines) + 1, W
    timed = []
    for li in range(len(lines)):
        st = [s_ for s_ in steps if s_["line"] == li]
        timed += [{**s_, "t0": round(t_, 3)} for s_, t_ in zip(st, N._place(st, segs, 0.4, W[li], W[li + 1]))]
    for i, s_ in enumerate(timed):
        s_["t1"] = timed[i + 1]["t0"] if i + 1 < len(timed) else round(ndur, 3)
    cut = timed[3]["t0"] - 0.04                     # F1 | B 나눔 — B 첫 줄 말 시작 바로 앞(쉼 안)
    o_len = sum(b - a for _, a, b in M.ORIG)
    f1_at = o_len + M.GAP_O_F1
    A_end = fr(f1_at + cut) / FPS
    # 조각 시각(완성본 초)
    T = []
    for k, s in enumerate(timed):
        if k < 3:
            T.append((f1_at + s["t0"], f1_at + min(s["t1"], cut)))
        else:
            T.append((A_end + s["t0"] - cut, A_end + s["t1"] - cut))
    T[2] = (T[2][0], A_end)
    END = round(T[-1][1] + M.END_PAD, 3)
    T[-1] = (T[-1][0], END)
    T = [(round(a, 3), round(b, 3)) for a, b in T]
    print("A_end", A_end, "END", END)

    # ── A 영상 ─────────────────────────────────────────────────────────
    frame = json.loads(M.FRAME_A.read_text(encoding="utf-8"))
    for l in frame["layers"]:
        if l.get("role") == "title":
            l["text"] = M.TITLE_A
        if l.get("role") == "label":
            l["text"] = M.LABEL_A
    (R / "frame_A.json").write_text(json.dumps(frame, ensure_ascii=False, indent=1), encoding="utf-8")
    spec = schema.validate(frame)
    win = next(l for l in spec["layers"] if l["kind"] == "video")
    cap = next(l for l in spec["layers"] if l["kind"] == "text" and l["role"] == "caption")
    a_shots, t = [], 0.0
    for k, (at, src, ss, crop) in enumerate(M.A_VIS):      # 원음 밑 화면 = make.A_VIS(원음 상대 초)
        nxt = M.A_VIS[k + 1][0] if k + 1 < len(M.A_VIS) else o_len
        a_shots.append({"t0": at, "t1": nxt, "src": src, "ss": ss, "crop": crop})
    t = o_len
    a_shots.append({"t0": t, "t1": T[2][0], "src": M.F1_SHOT[0], "ss": M.F1_SHOT[1], "crop": M.F1_SHOT[2]})
    a_shots.append({"t0": T[2][0], "t1": A_end, "src": M.F1_SHOT2[0], "ss": M.F1_SHOT2[1], "crop": M.F1_SHOT2[2]})
    parts = []
    for k, s in enumerate(a_shots):
        nf = fr(s["t1"]) - fr(s["t0"])
        p = work / f"a{k}.mp4"
        N.shot_clip(SRC / s["src"], s["ss"], nf / FPS, win, 750, True, p, src_crop=s["crop"], frames=nf)
        parts.append(p); s["frames"] = nf
    (work / "a.txt").write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    matA = work / "matA.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "a.txt"), "-c", "copy", str(matA)])
    # A 자막: 원음 흰 · 나레 노랑(틀 자막색) — 다음 자막 시작까지
    caps, ot = [], 0.0
    for name, a, b in M.ORIG:
        for ts, txt in M.ORIG_CAPS:
            if a - 0.01 <= ts < b:
                caps.append((round(ot + ts - a, 3), txt, (255, 255, 255), "원음"))
        ot += b - a
    for k in range(3):
        caps.append((T[k][0], M.PIECES[k][0], tuple(cap["rgb"]), "나레"))
    caps.sort()
    ev = []
    for j, (t0, txt, rgb, who) in enumerate(caps):
        t1 = caps[j + 1][0] if j + 1 < len(caps) else A_end
        if who == "원음" and j + 1 < len(caps) and caps[j + 1][3] == "나레":
            t1 = o_len                           # 원음 마지막 자막은 원음 끝에서 내린다(TTS 전 0.12초 빈칸)
        ev.append({"t0": t0, "t1": round(t1, 3), "text": txt, "rgb": rgb, "who": who})
    ins, fc, last = [], "", "0:v"
    for k, e in enumerate(ev):
        png = N.emph_png(e["text"], cap, e["rgb"], work / f"emph{k}.png", dy=(1920 - win["h"]) // 2 - win["y"])
        ins += ["-loop", "1", "-i", str(png)]
        fc += f"{';' if fc else ''}[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{e['t0']:.3f},{e['t1'] - 0.001:.3f})'[e{k}]"
        last = f"e{k}"
    matA2 = work / "matA_emph.mp4"
    run(["ffmpeg", "-y", "-i", str(matA), *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-t", f"{A_end:.3f}",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-color_range", "tv", str(matA2)])
    tlA = [{"beat_idx": 0, "t0": 0.0, "dur": A_end, "narration": "", "caption_lines": [], "role": "hook",
            "primary": {"video_id": "s0", "start": 0.0, "end": A_end}}]
    snapA = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    vidA = work / "vidA.mp4"
    scene_style.compose(str(matA2), tlA, snapA, str(vidA), work / "composeA", {"text": M.TITLE_A})

    # ── B 영상 ─────────────────────────────────────────────────────────
    Tb = [(a - A_end, b - A_end) for a, b in T[3:]]
    gs = []
    for k, (p, (a, b)) in enumerate(zip(M.PIECES[3:], Tb)):
        if p[1] == "+":
            gs[-1]["t1"] = b; gs[-1]["pieces"].append(k + 3)
        else:
            gs.append({"src": p[1], "ss": p[2], "crop": p[3], "kind": p[4], "t0": a, "t1": b, "pieces": [k + 3], "seen": p[5]})
    lst = []
    for gi, g in enumerate(gs):
        nf = fr(g["t1"]) - fr(g["t0"])
        x, y, h = g["crop"]; w = int(round(h * M.WIN_B[0] / M.WIN_B[1])) // 2 * 2
        out = work / f"b{gi:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{g['ss']:.3f}", "-i", str(SRC / g["src"]), "-an", "-vf",
             f"crop={w}:{h}:{x}:{y},scale={M.WIN_B[0]}:{M.WIN_B[1] + 1}:flags=lanczos,setsar=1,fps={FPS}", "-frames:v", str(nf),
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
        lst.append(f"file '{out.as_posix()}'")
        g.update({"frames": nf, "dur": round(nf / FPS, 3), "src_end": round(g["ss"] + nf / FPS, 3), "t0_final": round(A_end + g["t0"], 3), "t1_final": round(A_end + g["t1"], 3)})
    (work / "b.txt").write_text("\n".join(lst), encoding="utf-8")
    matB = work / "matB.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "b.txt"), "-c", "copy", str(matB)])
    PRE = M.PRESET_B
    snapB = scene_style.validate_snapshot({"mode": "story", "presetId": PRE["template"]["preset_id"], "frameRule": "body_all",
                                           "text": {"channel": PRE["brand"]["channel_name"], "hook1": "", "hook2": "", "bodyTitle": M.BODY_TITLE}})
    tlB = []
    for k, (a, b) in enumerate(Tb):
        tlB.append({"beat_idx": k, "t0": round(a, 3), "dur": round(b - a, 3), "narration": M.PIECES[k + 3][0], "caption_lines": [M.PIECES[k + 3][0]],
                    "role": "body", "primary": {"video_id": "s0", "start": round(a, 3), "end": round(b, 3)}})
    vidB = work / "vidB.mp4"
    scene_style.compose(str(matB), tlB, snapB, str(vidB), work / "composeB", {"text": "", "body_title": M.BODY_TITLE})

    vid = work / "video.mp4"
    (work / "v.txt").write_text(f"file '{vidA.as_posix()}'\nfile '{vidB.as_posix()}'\n", encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "v.txt"), "-an", "-r", "30", "-c:v", "libx264", "-crf", "16",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", str(vid)])
    total = M.dur_of(vid)

    # ── 소리 ─────────────────────────────────────────────────────────
    import numpy as np
    from shopping_shorts import sfx_pack as SP
    # 원음 조각(본인 말) → A 자리, 이음매 15ms 페이드
    oparts, ot = [], 0.0
    for k, (name, a, b) in enumerate(M.ORIG):
        p = work / f"o{k}.wav"
        run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(SRC / M.HAM), "-vn", "-ac", "1", "-ar", str(SR), "-af",
             f"{M.VOICE_AF},afade=t=in:d=0.015,afade=t=out:st={b - a - 0.015:.3f}:d=0.015", str(p)])
        oparts.append((p, ot)); ot += b - a
    f1 = work / "narr_f1.wav"; nb = work / "narr_b.wav"
    run(["ffmpeg", "-y", "-i", str(narr), "-af", f"atrim=0:{cut:.3f},afade=t=out:st={cut - 0.02:.3f}:d=0.02", str(f1)])
    run(["ffmpeg", "-y", "-i", str(narr), "-af", f"atrim={cut:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.01", str(nb)])

    def rms_med(p):
        a = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"], capture_output=True).stdout, dtype=np.float32)
        k20 = int(0.02 * 44100); fr_ = a[: len(a) // k20 * k20].reshape(-1, k20)
        r = 20 * np.log10(np.sqrt((fr_ ** 2).mean(1)) + 1e-9)
        return float(np.median(r[r > r.max() - 30]))
    ngain = -17.5 - rms_med(narr)                 # 목소리 중앙 −17.5dBFS(= sfx_pack 크기 기준, 재미썸홈 작품1과 같은 맞춤)
    ocat = work / "orig_cat.wav"
    run(["ffmpeg", "-y", *[x for p, _ in oparts for x in ("-i", str(p))], "-filter_complex",
         "".join(f"[{i}:a]" for i in range(len(oparts))) + f"concat=n={len(oparts)}:v=0:a=1[o]", "-map", "[o]", str(ocat)])
    ogain = -17.5 - rms_med(ocat)                 # 원음 목소리도 같은 중앙 크기
    # 효과음(B만): 줄 단위 timeline, 역할 = SFX_ROLES, density low
    stl = []
    for li in range(1, len(M.LINES)):
        mine = [k for k in range(3, len(M.PIECES)) if pl[k] == li]
        a, b = Tb[mine[0] - 3][0], Tb[mine[-1] - 3][1]
        stl.append({"beat_idx": li - 1, "t0": round(a, 3), "dur": round(b - a, 3), "narration": " ".join(M.PIECES[k][0] for k in mine),
                    "caption_lines": [M.PIECES[k][0] for k in mine], "cap_durs": [round(Tb[k - 3][1] - Tb[k - 3][0], 3) for k in mine],
                    "cap_lead": 0.0, "cap_offset": 0.0, "role": M.SFX_ROLES[li - 1]})
    pname, pdir = SP.pack_for(0)
    pack = {"name": pname, "dir": pdir, "density": "low", "level": "normal", "mute_beats": []}
    evs = SP.events(stl, pack)
    # 오프너(B 시작 +0.06초)가 다리 첫 말 '저 영상'을 덮어 받아쓰기가 '정말 보고'로 들림(10-17 실측, 나레 단독은 '저 영상') → 틀이 바뀌는 쉼 안(−0.25초)으로 당긴다
    evs = [(pth, (-0.25 if Path(pth).stem == "opener" else tt), mul) for pth, tt, mul in evs]
    (R / "sfx_events.json").write_text(json.dumps({"pack": pname, "plan": SP.plan_events(stl, density="low"), "events": evs, "timeline": stl, "offset": A_end},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    # BGM(A만): 나레 중앙보다 11dB 아래(박세리 편 −16 대비 −27), 원음 창 덕킹, A 끝 0.5초 페이드아웃
    bgm = bgm_lib.path_of(M.BGM_A)
    ins = ["-i", str(f1), "-i", str(nb), "-i", str(ocat), "-stream_loop", "-1", "-i", bgm]
    flt = [f"[0:a]volume={ngain:.2f}dB,adelay={int(f1_at * 1000)}|{int(f1_at * 1000)}[n1]",
           f"[1:a]volume={ngain:.2f}dB,adelay={int(A_end * 1000)}|{int(A_end * 1000)}[n2]",
           f"[2:a]volume={ogain:.2f}dB[o]"]
    bgain = -31.5 - rms_med(bgm)              # BGM 중앙 = 목소리 중앙 −14dB(원음 창은 그보다 −10dB 더)
    duck = 10 ** (M.DUCK_DB / 20)
    flt.append(f"[3:a]aformat=channel_layouts=mono,aresample={SR},atrim=0:{A_end:.3f},volume={bgain:.2f}dB,"
               f"volume='if(lt(t,{o_len + 0.1:.3f}),{duck:.4f},1)':eval=frame,afade=t=in:d=0.3,afade=t=out:st={A_end - 0.5:.3f}:d=0.5[b]")
    lab = ["[n1]", "[n2]", "[o]", "[b]"]
    for j, (path, tt, mul) in enumerate(evs):
        ins += ["-i", path]
        ms = int(round((A_end + tt) * 1000))
        flt.append(f"[{4 + j}:a]aresample={SR},aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{j}]")
        lab.append(f"[s{j}]")
    flt.append("".join(lab) + f"amix=inputs={len(lab)}:normalize=0:duration=longest,atrim=0:{total:.3f},apad=whole_dur={total:.3f}[m]")
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[m]", "-ar", str(SR), "-ac", "1", str(raw)])
    mix = R / "mix.wav"
    gain = 4.0
    for _ in range(10):
        run(["ffmpeg", "-y", "-i", str(raw), "-af", f"acompressor=threshold=0.125:ratio=3:attack=2:release=60,volume={gain:.2f}dB,"
             f"alimiter=limit={10 ** (-1.0 / 20):.4f}:level=false:attack=1:release=30", "-ar", str(SR), "-ac", "2", str(mix)])
        oI, _ = M.lufs(mix)
        if abs(oI - M.TARGET_LUFS) <= 0.3:
            break
        gain += (M.TARGET_LUFS - oI) * 0.9
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", str(vid), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    M.DESK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(final, M.DESK)
    md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, M.DESK)]
    fI, fpk = M.lufs(final)
    # 줄별 말속도(나레 시각 기준)
    starts = [next(s["t0"] for s in timed if s["line"] == li) for li in range(len(lines))] + [ndur]
    rates = [round(M.nchar(lines[i]) / (starts[i + 1] - starts[i]), 2) for i in range(len(lines))]
    rep = {"final": str(final), "desktop": str(M.DESK), "md5": md5, "dur": M.dur_of(final), "lufs": fI, "peak_dbfs": fpk, "atempo": tempo,
           "cps_out": round(chars / dn, 2), "line_rates": rates, "A_end": A_end, "orig_sec": round(o_len, 2), "b_cuts": len(gs),
           "b_cut_median": sorted(g["dur"] for g in gs)[len(gs) // 2], "end_cut": gs[-1]["dur"], "sfx": len(evs), "ngain": round(ngain, 2), "ogain": round(ogain, 2),
           "mix_gain": round(gain, 2), "max_caption": max(len(p[0]) for p in M.PIECES)}
    (R / "timeline.json").write_text(json.dumps({"report": rep, "pieces": [{"i": k + 1, "t": T[k], "caption": M.PIECES[k][0]} for k in range(len(T))],
                                                 "a_shots": a_shots, "a_caps": ev, "b_groups": gs, "timed": timed, "cut": cut}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    M.write_docs(T, gs, est=False, extra={"render": rep})
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, M.D / "plan/완성본_1초시트.jpg")
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
