# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 3호 장윤정 테클라 수건 — 잇썸홈판 렌더(엔진 코드는 안 고친다, 2026-10-17). 정본 = 하이브리드_함익병/잇썸홈판/make_render.py 를 그대로 따르고 A 구간만 여러 컷·원음 4조각으로 바꿈.

    PYTHONUTF8=1 py channel/yanshottem/하이브리드_장윤정/잇썸홈판/make_render.py --plan    # TTS 전 계획 시트(추정 말속도)
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_장윤정/잇썸홈판/make_render.py           # TTS 1회(있으면 재사용) → 렌더

흐름: 박창수 Typecast 1회(H + B1~B5 한 번에) → 무음으로 문장 6개 자르기 → 같은 atempo(8.32자/초 목표)
  → 소리 시간표 [H · 원음 O(1275.06~1283.22) · B1~B5] (문장 사이 쉼 0.28초)
  → A 구간 = 얜샷템 틀(frame_장윤정.json, 1080×1080 창) — 재료.json A.H(TTS 밑 제품 컷 2)·A.O(원음 밑 컷 6), 자막은 emph(나레 노랑·원음 흰)
  → B 구간 = 잇썸홈 틀(homedesignnote 전체화면_가운데자막 프리셋) — 재료.json 컷, 자막 조각=대본 caps
  → 이어 붙임(30fps 재인코딩) → 나레+원음+BGM(honwaka_puppu 나레−14.4dB, 원음 창 −10dB 더 덕킹) → −9 LUFS(두유노 렌더와 같은 사슬)
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
W = Path("C:/숏템_칼카피/yanshottem/하이브리드_장윤정/잇썸홈판")
DESK = Path.home() / "Desktop" / "칼카피영상" / "얜샷템" / "하이브리드" / "칼카피_얜샷템_장윤정테클라수건_잇썸홈판.mp4"
R = W / "render"
FRAME_SRC = ROOT / "channel/mantem/frame_얜샷템.json"
FRAME_A = D / "frame_장윤정.json"
PRESET_B = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"
BGM = ROOT / "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3"
GAP = 0.20           # 문장 사이 넣는 무음 — 앞뒤 TTS 숨 꼬리 포함 실측 쉼 0.26~0.31(B18)
GAP_AB = 0.20        # 원음 끝(샷 경계) → B1 첫 말
TAIL = 0.50
TARGET_LUFS, TP = -8.6, -3.2
O_HP = "highpass=f=90"


def run(cmd):
    return subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def lufs(p, extra=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(p)] + (extra or []) + ["-af", "ebur128=peak=true", "-f", "null", "-"]
    e = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def nchar(s):
    return len(re.sub(r"[\s,.!?]", "", s))


def load():
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    return S, M


def frame_a(S):
    fr = json.loads(FRAME_SRC.read_text(encoding="utf-8"))
    next(l for l in fr["layers"] if l.get("role") == "title")["text"] = S["title"]
    next(l for l in fr["layers"] if l.get("role") == "label")["text"] = S["source_label"]
    fr.setdefault("made_from", {})["episode"] = "얜샷템 하이브리드_장윤정 잇썸홈판 — title·label 글만 바꿈"
    FRAME_A.write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    return fr


# ── TTS ────────────────────────────────────────────────────────────────
def tts_lines(S):
    return [l for l in S["lines"] if l["kind"] == "tts"]


def tts_once(S):
    full = R / "narr_full.mp3"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(S["voice"]["voice_id"])(" ".join(l["tts"] for l in tts_lines(S)), str(full))
        print("Typecast 1회:", full)
    return full


def split_sentences(full, n):
    """무음 -40dB ≥0.16초 중 긴 것 n-1개 = 문장 경계. 반환 [(a,b)] 말 구간."""
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(full), "-af", "silencedetect=n=-40dB:d=0.16", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    total = dur_of(full)
    sil = list(zip(st, en + [total] * (len(st) - len(en))))
    head = sil[0][1] if sil and sil[0][0] <= 0.02 else 0.0
    tail = sil[-1][0] if sil and sil[-1][1] >= total - 0.02 else total
    inner = [s for s in sil if s[0] > head + 0.05 and s[1] < tail - 0.05]
    cut = sorted(sorted(inner, key=lambda s: s[1] - s[0], reverse=True)[:n - 1])
    edges = [head] + [x for s in cut for x in s] + [tail]
    return [(edges[2 * i], edges[2 * i + 1]) for i in range(n)], inner


def make_sentences(S, full):
    """문장 자르기 → 쉼 고치기(tts_pauses: 원본 초 구간 → 늘림 뒤 목표 초, B18) → atempo.
    atempo 는 전체 한 값(B17), 평균보다 3% 넘게 빠른 줄만 그 줄을 평균까지 늦춘다(B15, 늦춤 ≤10%)."""
    L = tts_lines(S)
    spans, inner = split_sentences(full, len(L))
    if S.get("tts_spans"):          # 손으로 확인한 문장 구간이 있으면 그것(자동 분할은 쉼표 쉼이 문장 끝보다 길 때 틀린다)
        spans = [tuple(S["tts_spans"][l["id"]]) for l in L]
    P = S.get("tts_pauses") or {}
    chars = [nchar(l["tts"]) for l in L]

    def eff(l, a, b, tempo):     # 쉼 고친 뒤 원본 길이
        return (b - a) - sum(e - s for s, e, _ in P.get(l["id"], [])) + sum(t * tempo for _, _, t in P.get(l["id"], []))
    tempo = 1.1
    for _ in range(5):
        speech = sum(eff(l, a, b, tempo) for l, (a, b) in zip(L, spans))
        tempo = round(min(1.25, max(0.85, S["cps_target"] / (sum(chars) / speech))), 4)
    durs = [eff(l, a, b, tempo) / tempo for l, (a, b) in zip(L, spans)]
    mean = sum(chars) / sum(durs)
    out = []
    for l, (a, b), c, d in zip(L, spans, chars, durs):
        tl = tempo
        if c / d > mean * 1.03:
            tl = round(max(tempo * 0.9, tempo * mean / (c / d)), 4)
        elif c / d < mean * 0.9:      # 이 편 추가: TTS가 유난히 늘어지게 읽은 줄(B1 6.71자/초)은 ≤10% 당긴다(B17)
            tl = round(min(tempo * 1.1, tempo * mean * 0.95 / (c / d)), 4)
        pts = [max(0, a - 0.02)]
        cuts = sorted(P.get(l["id"], []))
        fc, lab, x = [], [], pts[0]
        for k, (s0, e0, tg) in enumerate(cuts):
            fc.append(f"[0:a]atrim={x:.3f}:{s0:.3f},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono[a{k}]"); lab.append(f"[a{k}]")
            fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{tg * tl:.3f},aformat=sample_fmts=fltp[z{k}]"); lab.append(f"[z{k}]")
            x = e0
        fc.append(f"[0:a]atrim={x:.3f}:{b + 0.03:.3f},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono[aE]"); lab.append("[aE]")
        fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1,atempo={tl}[o]")
        p = R / f"s_{l['id']}.wav"
        run(["ffmpeg", "-y", "-i", full, "-filter_complex", ";".join(fc), "-map", "[o]", "-ar", "48000", "-ac", "1", p])
        out.append({"id": l["id"], "wav": str(p), "dur": round(dur_of(p), 3), "chars": c, "raw": [round(a, 3), round(b, 3)], "tempo": tl,
                    "pauses": cuts})
    print(f"atempo 기본 {tempo} · 평균 {mean:.2f}자/초")
    for o in out:
        print(f"  {o['id']}: {o['chars']}자 → {o['dur']}초 ({o['chars'] / o['dur']:.2f}자/초) tempo {o['tempo']}")
    return out, tempo, inner


# ── 시간표(판단 주인: 이 함수 한 곳) ────────────────────────────────────
def timeline(S, M, sent):
    """sent = {id: dur}. 반환 dict: 줄 시각·자막 조각 시각·컷 시각."""
    L = {l["id"]: l for l in S["lines"]}
    O = L["O"]
    o_len = sum(b - a for a, b in O["spans"])
    t, lines = 0.0, {}
    lines["H"] = [0.0, sent["H"]]
    o0 = sent["H"] + GAP
    lines["O"] = [o0, o0 + o_len]
    a_end = o0 + o_len                                  # 원음 마지막 조각 끝(264.56~265.45 샷 안)
    t = a_end + GAP_AB
    for k in ("B1", "B2", "B3", "B4", "B5"):
        lines[k] = [t, t + sent[k]]
        t = t + sent[k] + GAP
    end = lines["B5"][1] + TAIL
    caps = []
    for k in ("H", "B1", "B2", "B3", "B4", "B5"):
        a, b = lines[k]
        cs = L[k]["caps"]
        w = [nchar(c) for c in cs]
        x = a
        for j, (c, ww) in enumerate(zip(cs, w)):
            y = x + (b - a) * ww / sum(w)
            caps.append({"line": k, "j": j, "text": c, "t0": round(x, 3), "t1": round(y, 3), "kind": "나레"})
            x = y
    for c, s0, s1 in O["caps_rel"]:
        caps.append({"line": "O", "j": 0, "text": c, "t0": round(o0 + s0, 3), "t1": round(o0 + s1, 3), "kind": "원음"})
    caps.sort(key=lambda c: c["t0"])
    # 자막은 다음 자막(또는 그 구간 끝)까지 유지 — A·B 경계를 넘지 않는다
    for i, c in enumerate(caps):
        seg_end = a_end if c["line"] in ("H", "O") else end
        nxt = caps[i + 1]["t0"] if i + 1 < len(caps) else end
        c["show"] = [c["t0"], round(min(nxt, seg_end) if nxt <= seg_end else seg_end, 3)]
    # 컷: 줄의 첫 컷은 그 줄 시작(B1 은 A 끝)에서, 줄 안 경계는 그 컷 첫 조각 시작에서
    cuts = []
    for i, m in enumerate(M["B"]):
        tok0 = next(c for c in caps if c["line"] == m["line"] and c["j"] == m["toks"][0])
        first_of_line = i == 0 or M["B"][i - 1]["line"] != m["line"]
        t0 = (a_end if i == 0 else lines[m["line"]][0]) if first_of_line else tok0["t0"]
        cuts.append(dict(m, t0=round(t0, 3)))
    for i, c in enumerate(cuts):
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else round(end, 3)
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c["dur"] > c["max"] else 0.0
    return {"lines": {k: [round(a, 3), round(b, 3)] for k, (a, b) in lines.items()}, "a_end": round(a_end, 3), "end": round(end, 3),
            "o0": round(o0, 3), "caps": caps, "cuts": cuts}


def crop_vf(c, w, h):
    x, y, cw, ch = c
    return f"crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos,setsar=1,fps=30"


# ── 계획 시트(TTS 전) ───────────────────────────────────────────────────
def plan_sheet(S, M, T, path):
    import io
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(nv._font_file("Cafe24Ohsquare"), 22)
    src = Path(M["cand_dir"])
    rows = []
    for a in a_shots(S, M, T):
        rows.append((f"A {a['t0']:.2f}~{a['t1']:.2f} {a['src']}@{a['ss']}  {a['see'][:30]}", src / a["src"],
                     [a["ss"] + 0.05, a["ss"] + (a["t1"] - a["t0"]) / 2, a["ss"] + (a["t1"] - a["t0"]) - 0.05], a["crop"], (300, 300)))
    L = {l["id"]: l for l in S["lines"]}
    for c in T["cuts"]:
        txt = " ".join(L[c["line"]]["caps"][c["toks"][0]:c["toks"][1] + 1])
        rows.append((f"{c['line']} {c['t0']:.2f}~{c['t1']:.2f} ({c['dur']:.2f}s max {c['max']}) {Path(c['src']).stem}@{c['ss']}  「{txt}」",
                     src / c["src"], [c["ss"] + 0.05, c["ss"] + c["dur"] / 2, c["ss"] + c["dur"] - 0.05], c["crop"], (169, 300)))
    W_, H_ = 1200, 340
    sheet = Image.new("RGB", (W_, H_ * len(rows)), (20, 20, 20))
    for r, (label, video, ts, crop, size) in enumerate(rows):
        d = ImageDraw.Draw(sheet)
        d.text((8, r * H_ + 6), label, font=font, fill=(255, 230, 0))
        for k, t in enumerate(ts):
            p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                                f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]},scale={size[0]}:{size[1]}", "-f", "image2pipe", "-vcodec", "png", "-"],
                               capture_output=True).stdout
            im = Image.open(io.BytesIO(p)).convert("RGB")
            sheet.paste(im, (8 + k * (size[0] + 10), r * H_ + 36))
    sheet.save(path, quality=85)
    return path


# ── 렌더 ────────────────────────────────────────────────────────────────
def a_shots(S, M, T):
    """A 구간 컷 시각(판단 주인: 이 함수) — H 제품 컷 2개가 H+쉼을 반씩, O 컷은 원음 상대 초 at 그대로."""
    out = []
    h = M["A"]["H"]
    edges = [0.0, round(T["o0"] / 2, 3), T["o0"]]
    for k, c in enumerate(h):
        out.append(dict(c, t0=edges[k], t1=edges[k + 1]))
    O = M["A"]["O"]
    for k, c in enumerate(O):
        t0 = T["o0"] + c["at"]
        t1 = T["o0"] + O[k + 1]["at"] if k + 1 < len(O) else T["a_end"]
        out.append(dict(c, t0=round(t0, 3), t1=round(t1, 3)))
    return out


def render_a(S, M, T, fr):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    src = Path(M["cand_dir"])
    n = round(T["a_end"] * 30)
    parts = R / "a_parts"
    shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(a_shots(S, M, T)):
        nf = round(c["t1"] * 30) - round(c["t0"] * 30)
        p = parts / f"a{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", crop_vf(c["crop"], 1080, 1080), "-frames:v", nf,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text(chr(10).join(lst), encoding="utf-8")
    mat = R / "a_mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": round(n / 30, 3), "narration": "", "caption_lines": [], "role": "hook",
           "primary": {"video_id": "s0", "start": 0.0, "end": round(n / 30, 3)}}]
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(fr))
    seg = R / "a_seg.mp4"
    shutil.rmtree(R / "work_a", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work_a", {"text": S["title"]})
    cap = next(l for l in fr["layers"] if l.get("kind") == "text" and l.get("role") == "caption")
    ins, fc, last = [], "", "0:v"
    caps = [c for c in T["caps"] if c["line"] in ("H", "O")]
    for k, c in enumerate(caps):
        png = nv.emph_png(c["text"], cap, cap["rgb"] if c["kind"] == "나레" else [255, 255, 255], R / f"a_cap{k}.png", dy=0)
        ins += ["-loop", "1", "-i", png]
        a, b = c["show"]
        fc += f"{';' if fc else ''}[{last}][{k + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b - 0.001:.3f})'[e{k}]"
        last = f"e{k}"
    out = R / "a_final.mp4"
    run(["ffmpeg", "-y", "-i", seg, *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-frames:v", n,
         "-r", "30", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", out])
    return out, n


def render_b(S, M, T):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    from tools.calcopy.engine import preset_save as P
    src = Path(M["cand_dir"])
    parts = R / "b_parts"
    shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst, t_fr = [], round(T["a_end"] * 30)
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * 30) - round(c["t0"] * 30)
        c["frames"] = n
        p = parts / f"p{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", crop_vf(c["crop"], 1080, 1920), "-frames:v", n,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "b_mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    pre, Mf = P.load(PRESET_B)
    F = P.apply(pre, None, None, Mf["variable_stats"], None, Mf["rules"])
    (R / "frame_b.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    b0 = T["a_end"]
    nb = sum(c["frames"] for c in T["cuts"])
    tl, bi = [], 0
    for c in [c for c in T["caps"] if c["line"].startswith("B")]:
        a, b = c["show"]
        if c is [x for x in T["caps"] if x["line"].startswith("B")][0]:
            a = b0
        a2, b2 = round(a - b0, 3), round(min(b - b0, nb / 30), 3)
        tl.append({"beat_idx": bi, "t0": a2, "dur": round(b2 - a2, 3), "narration": c["text"], "caption_lines": [c["text"]],
                   "role": "hook" if bi == 0 else "body", "primary": {"video_id": "s0", "start": a2, "end": b2}})
        bi += 1
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
    seg = R / "b_seg.mp4"
    shutil.rmtree(R / "work_b", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work_b", {"text": ""})
    return seg, nb


def mute_af(O):
    """원음 안 남의 소리 구간(대본 O.mute, 원본 초)을 끈다 — 20ms 경사."""
    f = ""
    for a, b, *_ in O.get("mute") or []:
        a, b = a - O["span"][0], b - O["span"][0]
        f += f",volume='if(between(t,{a:.3f},{b:.3f}),max(0,1-min(t-{a:.3f},{b:.3f}-t)/0.02),1)':eval=frame"
    return f


def audio(S, T, sent):
    """나레(H·B) + 원음 O + BGM → mix.wav (TARGET_LUFS)."""
    O = next(l for l in S["lines"] if l["id"] == "O")
    jyj = Path(json.loads((D / "재료.json").read_text(encoding="utf-8"))["cand_dir"]) / O["src"]
    o_wav = R / "o_raw.wav"
    ops = []
    for k, (a, b) in enumerate(O["spans"]):      # 조각마다 15ms 페이드(쉼 잘라 낸 이음매)
        p = R / f"o_{k}.wav"
        run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", jyj, "-vn", "-ac", "1", "-ar", "48000",
             "-af", f"{O_HP},afade=t=in:d=0.015,afade=t=out:st={b - a - 0.015:.3f}:d=0.015", p])
        ops.append(p)
    run(["ffmpeg", "-y", *[x for p in ops for x in ("-i", p)], "-filter_complex",
         "".join(f"[{i}:a]" for i in range(len(ops))) + f"concat=n={len(ops)}:v=0:a=1[o]", "-map", "[o]", "-ar", "48000", o_wav])
    # 원음 크기 = 나레 크기(같은 LUFS)
    narr_cat = R / "narr_only.wav"
    lst = "".join(f"file '{Path(s['wav']).as_posix()}'\n" for s in sent)
    (R / "narr_list.txt").write_text(lst, encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "narr_list.txt", "-c", "copy", narr_cat])
    nI, _ = lufs(narr_cat)
    oI, _ = lufs(o_wav)
    og = round(nI - oI, 2)
    pieces = [(s["wav"], T["lines"][s["id"]][0], 0.0) for s in sent] + [(str(o_wav), T["o0"], og)]
    ins, fc = [], []
    for k, (p, t, g) in enumerate(pieces):
        ins += ["-i", p]
        ms = int(round(t * 1000))
        fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,volume={g}dB,adelay={ms}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{T['end']:.3f}[n]")
    voice = R / "voice.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", "48000", voice])
    # BGM: 나레 LUFS − 14.4, 원음 창 −10dB 덕킹(0.15초 경사)
    bI, _ = lufs(BGM)
    g = round((nI - S["bgm"]["db_below_voice"]) - bI, 2)
    k = 10 ** (S["bgm"]["duck_orig_db"] / 20)
    a, b = T["lines"]["O"]
    duck = f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))"
    end = T["end"]
    mix_raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-i", voice, "-stream_loop", "-1", "-i", BGM, "-filter_complex",
         f"[1:a]aresample=48000,aformat=channel_layouts=mono,atrim=0:{end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,volume='{duck}':eval=frame,"
         f"afade=t=out:st={end - 0.6:.3f}:d=0.6[b];[0:a][b]amix=inputs=2:normalize=0:duration=first[o]", "-map", "[o]", "-ar", "48000", mix_raw])
    mix = R / "mix.wav"
    gain, res = 16.0, None
    for _ in range(14):
        run(["ffmpeg", "-y", "-i", mix_raw, "-af", f"dynaudnorm=f=100:g=9:p=0.9:m=20,acompressor=threshold=0.125:ratio=8:attack=1:release=40,"
             f"volume={gain:.2f}dB,alimiter=limit={10 ** (TP / 20):.4f}:level=false:attack=1:release=30", "-ar", "48000", mix])
        res = lufs(mix)
        if res[0] >= TARGET_LUFS - 0.4 or gain >= 40:
            break
        gain += 2.0
    return mix, {"narr_lufs": nI, "orig_raw_lufs": oI, "orig_gain": og, "bgm_gain": g, "master_gain": gain, "mix": res}


def main():
    S, M = load()
    R.mkdir(parents=True, exist_ok=True)
    fr = frame_a(S)
    if "--plan" in sys.argv:
        est = {l["id"]: round(nchar(l["tts"]) / S["cps_target"], 3) for l in tts_lines(S)}
        T = timeline(S, M, est)
        (D / "plan").mkdir(exist_ok=True)
        (D / "plan/계획_시간표.json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        print(plan_sheet(S, M, T, D / "plan/계획_시트.jpg"))
        for c in T["cuts"]:
            print(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c['max']} over {c['over']} {c['src']}@{c['ss']}")
        print("A 끝", T["a_end"], "전체", T["end"])
        return
    full = tts_once(S)
    sent, tempo, inner = make_sentences(S, full)
    T = timeline(S, M, {s["id"]: s["dur"] for s in sent})
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise SystemExit("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c["dur"], c["max"]) for c in over]))
    a_mp4, na = render_a(S, M, T, fr)
    b_mp4, nb = render_b(S, M, T)
    lst = R / "ab.txt"
    lst.write_text(f"file '{a_mp4.as_posix()}'\nfile '{b_mp4.as_posix()}'\n", encoding="utf-8")
    vid = R / "video.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-an", "-r", "30", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", vid])
    T["end"] = round((na + nb) / 30, 3)
    mix, A = audio(S, T, sent)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    info = {"tempo": tempo, "sentences": sent, "inner_silences": inner, "timeline": T, "audio": A, "final": str(final),
            "final_dur": dur_of(final), "final_lufs": lufs(final)}
    (R / "render_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print("final", final, info["final_dur"], "LUFS/TP", info["final_lufs"], json.dumps(A, ensure_ascii=False))
    import hashlib
    from tools.calcopy.engine.remake import sheet_1s
    DESK.parent.mkdir(parents=True, exist_ok=True)
    sheet_1s(final, D / "final_sheet_1s.jpg")
    try:
        shutil.copy(final, DESK)
        md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, DESK)]
        print("desktop", DESK, md5)
    except PermissionError as e:      # 바탕화면 파일을 누가 열어 둔 경우 — 완성본은 그대로, 복사만 나중에
        print("desktop 복사 실패(파일 열림):", e)


if __name__ == "__main__":
    main()
