# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 3호 최은경 자라 스웨이드 로퍼 — 잇썸홈판 렌더(엔진 코드는 안 고친다, 2026-10-17).
정본 = 하이브리드_함익병/잇썸홈판/make_render.py — 원음이 두 토막(O1·O2)이라 A 시간표·화면·소리만 바꿈.

    PYTHONUTF8=1 py channel/yanshottem/하이브리드_최은경/잇썸홈판/make_render.py --plan    # TTS 전 계획 시트(추정 말속도)
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_최은경/잇썸홈판/make_render.py           # TTS 1회(있으면 재사용) → 렌더

흐름: 박창수 Typecast 1회(H + B1~B5 한 번에) → 무음으로 문장 6개 자르기 → 같은 atempo(8.32자/초 목표)
  → 소리 시간표 [H · 원음 O(1275.06~1283.22) · B1~B5] (문장 사이 쉼 0.28초)
  → A 구간 = 얜샷템 틀(frame_함익병.json, 1080×1080 창) — 원본 한 줄기, 자막은 emph(나레 노랑·원음 흰)
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
W = Path("C:/숏템_칼카피/yanshottem/하이브리드_최은경/잇썸홈판")
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드/칼카피_얜샷템_최은경자라로퍼_잇썸홈판.mp4")
R = W / "render"
FRAME_SRC = ROOT / "channel/mantem/frame_얜샷템.json"
FRAME_A = D / "frame_최은경.json"
PRESET_B = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"
BGM = ROOT / "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3"
GAP = 0.20           # 문장 사이 넣는 무음 — 앞뒤 TTS 숨 꼬리 포함 실측 쉼 0.26~0.31(B18)
GAP_AB = 0.20        # 원음 끝 → B1 첫 말
GAP_OO = 0.25        # 원음 O1 끝 → O2 시작(원본에서 잘라 낸 사이)
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
    fr.setdefault("made_from", {})["episode"] = "얜샷템 하이브리드_최은경 잇썸홈판 — title·label 글만 바꿈"
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
        src_l = (S.get("tts_override") or {}).get(l["id"]) or full   # 이름 발음 고친 줄만 따로 합성한 파일(10-17 '최은경' 오인식)
        run(["ffmpeg", "-y", "-i", src_l, "-filter_complex", ";".join(fc), "-map", "[o]", "-ar", "48000", "-ac", "1", p])
        out.append({"id": l["id"], "wav": str(p), "dur": round(dur_of(p), 3), "chars": c, "raw": [round(a, 3), round(b, 3)], "tempo": tl,
                    "pauses": cuts})
    print(f"atempo 기본 {tempo} · 평균 {mean:.2f}자/초")
    for o in out:
        print(f"  {o['id']}: {o['chars']}자 → {o['dur']}초 ({o['chars'] / o['dur']:.2f}자/초) tempo {o['tempo']}")
    return out, tempo, inner


# ── 시간표(판단 주인: 이 함수 한 곳) ────────────────────────────────────

# ── 시간표(판단 주인: 이 함수 한 곳) ────────────────────────────────────
B_IDS = ("B1", "B2", "B3", "B4", "B5", "B6")


def timeline(S, M, sent):
    """sent = {id: dur}. 반환 dict: 줄 시각·자막 조각 시각·A 화면 조각·B 컷 시각."""
    L = {l["id"]: l for l in S["lines"]}
    O1, O2 = L["O1"], L["O2"]
    lines = {"H": [0.0, sent["H"]]}
    o1 = sent["H"] + GAP
    lines["O1"] = [o1, o1 + O1["span"][1] - O1["span"][0]]
    o2 = lines["O1"][1] + GAP_OO
    lines["O2"] = [o2, o2 + O2["span"][1] - O2["span"][0]]
    a_end = round(round((lines["O2"][1] + 0.03) * 30) / 30, 4)

    def f1(s):          # O1 원본 초 → 완성본 초
        return o1 + s - O1["span"][0]

    def f2(s):
        return o2 + s - O2["span"][0]
    A = M["A"]
    hs, s1, s2 = A["H_shot"], A["O1_shots"], A["O2_shots"]
    pieces = []
    # H: 제품 컷 — O1 첫 화면(508.33) 바로 앞까지 원본 그대로 이어 읽는다
    t_o1v = f1(s1[0]["shot"][0])
    # 제품 컷은 원본 샷 안쪽(앞뒤 0.03·0.1초 버림 — -ss 탐색 오차로 이웃 샷 프레임이 새는 것 실측 2.17초)만 쓴다.
    # H 가 그보다 길면(이름 고친 H 2.69초) 제품 컷을 그만큼 느리게(slow = 필요 길이/쓸 수 있는 길이, 도는 제품이라 3% 안팎은 안 보임)
    h0, h1 = hs["shot"][0] + 0.03, s1[0]["shot"][0] - 0.1
    slow = max(1.0, t_o1v / (h1 - h0))
    assert slow <= 1.08, ("H 가 제품 컷보다 너무 길다", slow)
    if A.get("H_face"):     # 2026-10-18 첫 화면 = 최은경 얼굴(사장님 '썸네일·첫 화면은 무조건 연예인') — 제품 컷 대신 원본 얼굴 샷
        hf = A["H_face"]
        assert hf["ss"] + t_o1v <= hf["shot"][1] - 0.03, ("H 얼굴 샷이 짧다", hf, t_o1v)
        pieces.append({"src": hf["src"], "ss": hf["ss"], "t0": 0.0, "t1": t_o1v, "crop": hf["crop"], "who": "H 얼굴"})
    else:
        pieces.append({"src": hs["src"], "ss": max(h0, h1 - t_o1v), "t0": 0.0, "t1": t_o1v, "crop": hs["crop"], "who": "H 제품", "slow": round(slow, 4)})
    t_o1end = f1(s1[-1]["shot"][1] - 0.08)          # O1 마지막 샷 끝(원본 컷 512.57) 직전까지
    for k, sh in enumerate(s1):
        t0 = f1(sh["shot"][0]) if k else t_o1v
        t1 = f1(sh["shot"][1]) if k + 1 < len(s1) else t_o1end
        pieces.append({"src": sh["src"], "ss": sh["shot"][0], "t0": t0, "t1": t1, "crop": sh["crop"], "who": f"O1 샷{k}"})
    # O2 첫 샷은 O1 화면 끝에서 시작(O2 말 앞 빈 사이를 O2 원본 앞부분으로 채움)
    sh = s2[0]
    t_cut = f2(sh["shot"][1] - 0.08)
    ss2 = O2["span"][0] - (o2 - t_o1end)
    assert ss2 >= sh["shot"][0], ("O2 앞 채움이 샷 밖", ss2)
    pieces.append({"src": sh["src"], "ss": ss2, "t0": t_o1end, "t1": t_cut, "crop": sh["crop"], "who": "O2 샷0"})
    pieces.append({"src": s2[1]["src"], "ss": s2[1]["shot"][0], "t0": t_cut, "t1": a_end, "crop": s2[1]["crop"], "who": "O2 꼬리(J컷)"})
    for p_ in pieces:
        p_["t0"], p_["t1"] = round(p_["t0"], 3), round(p_["t1"], 3)
    t = a_end + GAP_AB
    for k in B_IDS:
        lines[k] = [t, t + sent[k]]
        t = t + sent[k] + GAP
    end = lines[B_IDS[-1]][1] + TAIL
    caps = []
    for k in ("H",) + B_IDS:
        a, b = lines[k]
        cs = L[k]["caps"]
        w = [nchar(c) for c in cs]
        x = a
        for j, (c, ww) in enumerate(zip(cs, w)):
            y = x + (b - a) * ww / sum(w)
            caps.append({"line": k, "j": j, "text": c, "t0": round(x, 3), "t1": round(y, 3), "kind": "나레"})
            x = y
    for O, f in ((O1, f1), (O2, f2)):
        for c, s0, s1_ in O["caps"]:
            caps.append({"line": O["id"], "j": 0, "text": c, "t0": round(f(s0), 3), "t1": round(f(s1_), 3), "kind": "원음"})
    caps.sort(key=lambda c: c["t0"])
    for i, c in enumerate(caps):
        seg_end = a_end if c["line"] in ("H", "O1", "O2") else end
        nxt = caps[i + 1]["t0"] if i + 1 < len(caps) else end
        if c["kind"] == "원음" and c["line"] == "O1" and nxt > c["t1"] + 0.05:
            nxt = c["t1"] + 0.05                           # O1 끝 자막은 말 끝나고 내린다(O2 앞 빈 사이)
        c["show"] = [c["t0"], round(min(nxt, seg_end) if nxt <= seg_end else seg_end, 3)]
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
    return {"lines": {k: [round(a, 3), round(b, 3)] for k, (a, b) in lines.items()}, "a_end": a_end, "end": round(end, 3),
            "a_pieces": pieces, "caps": caps, "cuts": cuts}


def crop_vf(c, w, h):
    x, y, cw, ch = c
    return f"crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos,setsar=1,fps=30"


# ── 계획 시트(TTS 전) ───────────────────────────────────────────────────

# ── 계획 시트(TTS 전) ───────────────────────────────────────────────────
def _src(M, s):
    return Path(M["cand_dir"]) / s


def plan_sheet(S, M, T, path):
    import io
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(nv._font_file("Cafe24Ohsquare"), 22)
    rows = []
    for p_ in T["a_pieces"]:
        d = p_["t1"] - p_["t0"]
        rows.append((f"A {p_['who']} {p_['t0']:.2f}~{p_['t1']:.2f} src {p_['ss']:.2f}+{d:.2f}", _src(M, p_["src"]),
                     [p_["ss"] + 0.05, p_["ss"] + d / 2, p_["ss"] + d - 0.05], p_["crop"], (300, 300)))
    L = {l["id"]: l for l in S["lines"]}
    for c in T["cuts"]:
        txt = " ".join(L[c["line"]]["caps"][c["toks"][0]:c["toks"][1] + 1])
        rows.append((f"{c['line']} {c['t0']:.2f}~{c['t1']:.2f} ({c['dur']:.2f}s max {c['max']}) {Path(c['src']).stem}@{c['ss']}  「{txt}」",
                     _src(M, c["src"]), [c["ss"] + 0.05, c["ss"] + c["dur"] / 2, c["ss"] + c["dur"] - 0.05], c["crop"], (169, 300)))
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
def render_a(S, M, T, fr):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    parts = R / "a_parts"
    shutil.rmtree(parts, ignore_errors=True)
    parts.mkdir(parents=True)
    lst = []
    for k, p_ in enumerate(T["a_pieces"]):
        n = round(p_["t1"] * 30) - round(p_["t0"] * 30)
        p_["frames"] = n
        out = parts / f"a{k}.mp4"
        vf = crop_vf(p_["crop"], 1080, 1080)
        if p_.get("slow", 1.0) > 1.0:
            vf = f"setpts={p_['slow']}*PTS," + vf
        run(["ffmpeg", "-y", "-ss", f"{p_['ss']:.3f}", "-i", _src(M, p_["src"]), "-an", "-vf", vf, "-frames:v", n,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", out])
        lst.append(f"file '{out.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "a_mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    n = sum(p_["frames"] for p_ in T["a_pieces"])
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": round(n / 30, 3), "narration": "", "caption_lines": [], "role": "hook",
           "primary": {"video_id": "s0", "start": 0.0, "end": round(n / 30, 3)}}]
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(fr))
    seg = R / "a_seg.mp4"
    shutil.rmtree(R / "work_a", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work_a", {"text": S["title"]})
    cap = next(l for l in fr["layers"] if l.get("kind") == "text" and l.get("role") == "caption")
    ins, fc, last = [], "", "0:v"
    caps = [c for c in T["caps"] if c["line"] in ("H", "O1", "O2")]
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
    parts = R / "b_parts"
    shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst, t_fr = [], round(T["a_end"] * 30)
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * 30) - round(c["t0"] * 30)
        c["frames"] = n
        p = parts / f"p{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", _src(M, c["src"]), "-an", "-vf", crop_vf(c["crop"], 1080, 1920), "-frames:v", n,
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
    f = ""
    for a, b, *_ in O.get("mute") or []:
        a, b = a - O["span"][0], b - O["span"][0]
        f += f",volume='if(between(t,{a:.3f},{b:.3f}),max(0,1-min(t-{a:.3f},{b:.3f}-t)/0.02),1)':eval=frame"
    return f


def audio(S, M, T, sent):
    """나레(H·B) + 원음 O1·O2 + BGM → mix.wav (TARGET_LUFS)."""
    L = {l["id"]: l for l in S["lines"]}
    o_wavs = []
    for oid in ("O1", "O2"):
        O = L[oid]
        w = R / f"o_{oid}.wav"
        run(["ffmpeg", "-y", "-ss", f"{O['span'][0]:.3f}", "-to", f"{O['span'][1]:.3f}", "-i", M["ceg"], "-vn", "-ac", "1", "-ar", "48000",
             "-af", f"{O_HP}{mute_af(O)},afade=t=in:d=0.02,areverse,afade=t=in:d=0.04,areverse", w])
        o_wavs.append((oid, w))
    narr_cat = R / "narr_only.wav"
    (R / "narr_list.txt").write_text("".join(f"file '{Path(s['wav']).as_posix()}'\n" for s in sent), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "narr_list.txt", "-c", "copy", narr_cat])
    nI, _ = lufs(narr_cat)
    ocat = R / "o_cat.wav"
    run(["ffmpeg", "-y", "-i", o_wavs[0][1], "-i", o_wavs[1][1], "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[o]", "-map", "[o]", ocat])
    oI, _ = lufs(ocat)
    og = round(nI - oI, 2)
    pieces = [(s["wav"], T["lines"][s["id"]][0], 0.0) for s in sent] + [(str(w), T["lines"][oid][0], og) for oid, w in o_wavs]
    ins, fc = [], []
    for k, (p, t, g) in enumerate(pieces):
        ins += ["-i", p]
        ms = int(round(t * 1000))
        fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,volume={g}dB,adelay={ms}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{T['end']:.3f}[n]")
    voice = R / "voice.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", "48000", voice])
    bI, _ = lufs(BGM)
    g = round((nI - S["bgm"]["db_below_voice"]) - bI, 2)
    k = 10 ** (S["bgm"]["duck_orig_db"] / 20)
    a, b = T["lines"]["O1"][0], T["lines"]["O2"][1]
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
        for p_ in T["a_pieces"]:
            print(f"  A {p_['who']} {p_['t0']:6.2f}~{p_['t1']:6.2f} ss {p_['ss']:.2f}")
        for c in T["cuts"]:
            print(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c['max']} over {c['over']} {Path(c['src']).name}@{c['ss']}")
        print("A 끝", T["a_end"], "전체", T["end"])
        return
    full = tts_once(S)
    sent, tempo, inner = make_sentences(S, full)
    T = timeline(S, M, {s["id"]: s["dur"] for s in sent})
    if "--tts-only" in sys.argv:
        print(json.dumps(T["lines"], ensure_ascii=False))
        for c in T["cuts"]:
            print(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c['max']} over {c['over']}")
        return
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
    mix, A = audio(S, M, T, sent)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    DESK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(final, DESK)
    import hashlib
    md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, DESK)]
    info = {"tempo": tempo, "sentences": sent, "inner_silences": inner, "timeline": T, "audio": A, "final": str(final), "desktop": str(DESK),
            "md5": md5, "final_dur": dur_of(final), "final_lufs": lufs(final)}
    (R / "render_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, D / "final_sheet_1s.jpg")
    print("final", final, info["final_dur"], "LUFS/TP", info["final_lufs"], "md5", md5, json.dumps(A, ensure_ascii=False))


if __name__ == "__main__":
    main()
