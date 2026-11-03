# -*- coding: utf-8 -*-
"""숏템리폿 현장썰 1편 — 가짜 잠자리(모기 퇴치 장식) 렌더 (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/hottemreport/현장썰_01_가짜잠자리/make_render.py [--dry] [--gain 0,0,0,0]

길 = 얜샷템 최은경 make_render(원음 블록↔나레 블록 교대) 그대로, 틀·자막 외관 = 숏템리폿(make_frame_숏템리폿 v3 · 박스 자막).
  필재 1회(tools/calcopy/engine/tts_pause.py, 속도 1.24, render/narr_full.mp3) → 마침표 쉼 가운데서 줄마다 자르기(정렬 시각+쉼 고친 양)
  → 줄마다 8.0자/초로 atempo(줄끼리 평균 ±8%, 상한 1.27) → 원음 4구간 사이에 끼운 narr_gapped.wav
  → 재료_render.json(페이지 1개 × cuts — 원음 입 맞춤 시각) → 자막 전부 caption_events emph(나레 흰·원음 하늘, 박스)
  → narr_video.build(BGM 없음, line_asr=False) → hottem_audio.add_source_bed(원음 구간만 소리, 나머지 무음 = 원음 구간 밖 영어 말 0)
  → BGM(passo_bem_solto, 원음 창 −10dB 덕킹) 섞기·LUFS → render/final.mp4
판단 주인: 원음 구간·자막 = 대본.json final.orig_audio · 화면 소스 = 재료.json blocks · 시각 계산 = 이 파일 timeline() 한 곳.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv, hottem_audio as ha  # noqa: E402
from shopping_shorts import bgm_lib  # noqa: E402

D = Path(__file__).resolve().parent
W = Path("C:/숏템_칼카피/hottemreport/현장썰_01_가짜잠자리")
SRC = W / "src"
R = W / "render"
RAW = R / "narr_full.mp3"
WAV = R / "narr_gapped.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 최은경 편과 같은 원음 다듬기
CPS = 7.8                 # 핫템 나레 말속도(OE11 계획 8.03자/초 · OE 받아쓰기 낱말 기준 7.77)
GAP_NO = 0.25             # 나레↔원음 사이
GAP_NN = 0.30             # 나레↔나레(문장 쉼)
LEAD = 0.10               # 원음 컷은 소리보다 0.1초 먼저 화면이 바뀐다
TAIL = 0.60
LUFS_NARR = -15.3
LUFS_FINAL = -15.5        # OE11 우리 판 −15.5 · 핫템 현장썰 4편 −15.3~−18.8 · 벤치 PIHC −14.1
LIMIT = 0.89
BGM, BGM_DB, DUCK_DB = "passo_bem_solto", -32.0, -10.0   # OE11 과 같은 곡(나레 대비 0.15 ≈ −16.5dB)
NARR_RGB, ORIG_RGB = [255, 255, 255], [80, 200, 255]      # 핫템: 나레 흰 / 원음 하늘
GAINS = [10.6, 9.9, 15.5, 10.6]   # 원음 창 올림(dB) — 1판(0dB) 실측 원음 −27.1/−26.4/−32.0/−27.1 vs 나레 중앙 −14.5 → 나레 −2dB 목표


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"실패: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-600:]}")
    return r


def lufs(p, a=None, b=None):
    cmd = ["ffmpeg", "-hide_banner"] + (["-ss", f"{a:.3f}", "-to", f"{b:.3f}"] if a is not None else []) + ["-i", str(p), "-af", "ebur128", "-f", "null", "-"]
    e = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def nchar(s):
    return len(re.sub(r"[\s,.!?~]", "", s))


def line_cuts():
    """마침표 쉼 가운데(쉼 고친 뒤 시각) — 정렬(align.json) 시각 + 앞 쉼들이 늘고 준 양."""
    al = json.loads(Path(str(RAW) + ".align.json").read_text(encoding="utf-8"))
    from tools.calcopy.engine.tts_pause import pause_slots
    log = json.loads((R / "narr_full.pauses.json").read_text(encoding="utf-8"))["pauses"]
    slots = pause_slots(al)
    assert len(slots) == len(log), (len(slots), len(log))
    from tools.calcopy.engine.tts_pause import XF_SEC
    # ★shape 는 이음매마다 XF_SEC 겹침(쉼 자리마다 2번) — 안 빼면 뒤로 갈수록 예상이 늦어져 다음 문장 첫 소리(ㅊ·ㅅ·ㅎ)를 잘랐다
    #   (10-18 1·2차: '처음'→'또', '세 개가'→'이거', '효과'→'휴가' 로 받아쓰기됨). 예상 뒤 실제 쉼(-45dB·0.06초 이상) 가운데에 붙인다.
    sil = [(x, y) for x, y in ha._silences(str(RAW), "-45dB", 0.06)]
    out, shift = [], 0.0
    for k, ((kind, a, b), lg) in enumerate(zip(slots, log)):
        if kind == ".":
            t = a + shift - (2 * k + 1) * XF_SEC + lg["now"] / 2
            near = min(sil, key=lambda q: abs((q[0] + q[1]) / 2 - t), default=None)
            if near is None or abs((near[0] + near[1]) / 2 - t) > 0.3:
                raise SystemExit(f"마침표 쉼을 못 찾음: 예상 {t:.3f}, 가장 가까운 쉼 {near}")
            out.append(round((near[0] + near[1]) / 2, 3))
        shift += lg["now"] - lg["was"]
    return out


def narr_lines(S):
    lines = S["final"]["lines"]
    cuts = line_cuts()
    assert len(cuts) == len(lines) - 1, cuts
    bounds = [0.0] + cuts + [None]
    cut = []
    for k, l in enumerate(lines):
        raw = R / f"narr_{l['id']}_raw.wav"
        a, b = bounds[k], bounds[k + 1]
        run(["ffmpeg", "-y", "-i", RAW, "-ss", f"{a:.3f}"] + (["-to", f"{b:.3f}"] if b else []) + ["-ac", "1", "-ar", "48000", raw])
        segs, _ = nv.speech_segments(str(raw))
        cut.append((raw, max(0.0, segs[0][0] - 0.02), segs[-1][1], nchar(l["text"])))
    ideal = [(s1 - s0) * CPS / n for _, s0, s1, n in cut]
    base = sum(ideal) / len(ideal)
    out = []
    for (raw, s0, s1, n), ti, l in zip(cut, ideal, lines):
        tempo = round(min(max(ti, base * 0.90), base * 1.10, 1.27), 3)   # B17 줄별 늘림·줄임 ±10%
        wav = R / f"narr_{l['id']}.wav"
        run(["ffmpeg", "-y", "-i", raw, "-af", f"atrim={s0:.3f}:{s1 + 0.03:.3f},asetpts=N/SR/TB,atempo={tempo}", "-ac", "1", "-ar", "48000",
             "-c:a", "pcm_s16le", wav])
        sg, dur = nv.speech_segments(str(wav))
        out.append({"id": l["id"], "wav": str(wav), "dur": round(dur, 3), "tempo": tempo, "chars": n, "speech": round(sg[-1][1] - sg[0][0], 3),
                    "cps": round(n / (sg[-1][1] - sg[0][0]), 2), "segs": [[round(a, 3), round(b, 3)] for a, b in sg]})
    return out


def timeline(S, M, NL):
    """블록 시각(소리) + 화면 조각. 화면 조각: 자기 소스가 있는 블록에서 바뀌고, 'cont' 블록은 다음 원음 컷을 앞으로 늘린다(같은 소스 연속)."""
    O = {o["id"]: o for o in S["final"]["orig_audio"]}
    N = {x["id"]: x for x in NL}
    V = M["blocks"]
    t, prev, blocks = 0.0, None, []
    for bid in S["final"]["order"]:
        if bid.startswith("O"):
            o = O[bid]
            a0 = round(t + (GAP_NO if prev else 0.0), 3)
            a1 = round(a0 + o["span"][1] - o["span"][0], 3)
            blocks.append({"id": bid, "kind": "원음", "a0": a0, "a1": a1, "audio_ss": o["span"][0], "src": V[bid]["src"]})
            t, prev = a1, "O"
        else:
            n0 = round(t + (0.0 if prev is None else GAP_NN if prev == "N" else GAP_NO), 3)
            n1 = round(n0 + N[bid]["dur"], 3)
            blocks.append({"id": bid, "kind": "나레", "n0": n0, "n1": n1})
            t, prev = n1, "N"
    dur = round(t + TAIL, 3)
    # 화면 조각
    pieces, pend = [], []
    for b in blocks:
        v = V[b["id"]]
        if v.get("follow"):   # 앞 조각 화면이 그대로 이어진다(같은 소스 한 줄기)
            assert not pend, b["id"]
            continue
        if v.get("cont"):
            pend.append(b)
            continue
        if b["kind"] == "원음":
            vs = (pend[0]["n0"] if pend else b["a0"] - LEAD)
            ss = round(b["audio_ss"] - (b["a0"] - vs), 3)
        else:
            vs, ss = b["n0"], v["ss"]
            assert not pend, f"cont 뒤에 원음이 아닌 블록 {b['id']}"
        pieces.append({"block": b["id"], "covers": [x["id"] for x in pend] + [b["id"]], "src": v["src"], "ss": ss, "vs": round(vs, 3),
                       "src_crop": v.get("src_crop"), "why": v.get("why")})
        pend = []
    pieces[0]["vs"] = 0.0
    for i, p in enumerate(pieces):
        p["ve"] = pieces[i + 1]["vs"] if i + 1 < len(pieces) else dur
        p["src_end"] = round(p["ss"] + p["ve"] - p["vs"], 3)
    # 소스 장면 경계 가드: 조각 끝 0.4초 안에 원본 컷이 있으면 그 컷 1프레임 앞에서 끊고 다음 조각을 그만큼 일찍 시작(다음 장면 몇 프레임 번쩍 방지)
    for i, p in enumerate(pieces[:-1]):
        for c in M["scene_cuts"][p["src"]]:
            if p["src_end"] - 0.4 < c <= p["src_end"] and c > p["ss"]:
                sh = round(p["src_end"] - c + 1 / 30, 3)
                p["ve"] = round(p["ve"] - sh, 3); p["src_end"] = round(p["src_end"] - sh, 3)
                q = pieces[i + 1]; q["vs"] = p["ve"]; q["ss"] = round(q["ss"] - sh, 3)
                p["guard"] = f"원본 컷 {c} 앞에서 끊음(−{sh}초)"
    for p in pieces:   # 시작 쪽: 조각 시작 0.3초 안에 원본 컷이 있으면 앞 장면이 잠깐 보인다 → 경보(손으로 고친다)
        bad = [c for c in M["scene_cuts"][p["src"]] if p["ss"] < c < p["ss"] + 0.3]
        if bad:
            print(f"[경보] 조각 {p['block']} 시작 {p['ss']} 바로 뒤 원본 컷 {bad} — 앞 장면 {round(bad[0] - p['ss'], 3)}초 보임")
    return blocks, pieces, dur


def gapped(blocks, NL, dur):
    N = {x["id"]: x for x in NL}
    fc, lab, t, ins = [], [], 0.0, []
    for i, b in enumerate(x for x in blocks if x["kind"] == "나레"):
        if b["n0"] - t > 1e-3:
            fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{b['n0'] - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        ins += ["-i", N[b["id"]]["wav"]]
        t = b["n0"] + N[b["id"]]["dur"]
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{dur - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y"] + ins + ["-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", WAV])


def spread(caps, a, b, speech):
    """자막 조각을 [a,b] 안 말소리 시간에 글자 수 비례로(최은경 편 spread 와 같은 꼴)."""
    speech = [(max(s, a), min(e, b)) for s, e in speech if e > a and s < b] or [(a, b)]
    tot = sum(e - s for s, e in speech)
    n = [nchar(c) for c in caps]
    N_ = sum(n)

    def at(frac):
        need = frac * tot
        for s, e in speech:
            if need <= e - s + 1e-9:
                return s + need
            need -= e - s
        return speech[-1][1]
    out, acc = [], 0
    for c, k in zip(caps, n):
        t0 = a if acc == 0 else at(acc / N_)
        acc += k
        out.append({"t0": round(t0, 3), "text": c})
    return out


def captions(S, blocks, NL):
    O = {o["id"]: o for o in S["final"]["orig_audio"]}
    L = {l["id"]: l for l in S["final"]["lines"]}
    N = {x["id"]: x for x in NL}
    cp = []
    for b in blocks:
        if b["kind"] == "원음":
            segs, _ = nv.speech_segments(str(R / f"orig_{b['id']}.wav"), noise="-38dB", d=0.12)
            sp = [(b["a0"] + s, b["a0"] + e) for s, e in segs]
            cp += [dict(c, kind="원음") for c in spread(O[b["id"]]["caps"], b["a0"], b["a1"], sp)]
        else:
            sp = [(b["n0"] + s, b["n0"] + e) for s, e in N[b["id"]]["segs"]]
            cp += [dict(c, kind="나레") for c in spread(L[b["id"]]["caps"], b["n0"], b["n1"], sp)]
    return cp


def ramp(a, b, g, up=0.06, down=0.08, depth=6.0):
    st = 4
    out = [[round(a + up * i / st, 3), round(a + up * (i + 1) / st, 3), round(g - 12 * (1 - (i + 1) / st), 2)] for i in range(st)]
    out.append([round(a + up, 3), round(b - down, 3), g])
    out += [[round(b - down + down * i / st, 3), round(b - down + down * (i + 1) / st, 3), round(g - depth * (i + 1) / st, 2)] for i in range(st)]
    return out


def bgm_mix(src_mp4, out_mp4, win, dur):
    bgm = bgm_lib.path_of(BGM)
    k = 10 ** (DUCK_DB / 20)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win)
    tmp = R / "work_bgm.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bgm, "-t", f"{dur:.3f}", "-af", f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={BGM_DB}:TP=-6:LRA=11,"
         f"volume='{terms}':eval=frame,afade=t=out:st={dur - 0.5:.3f}:d=0.5", "-c:a", "pcm_s16le", tmp])
    mixed = R / "work_mix.wav"
    run(["ffmpeg", "-y", "-i", src_mp4, "-i", tmp, "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", mixed])
    I = lufs(mixed)
    g = round(LUFS_FINAL - I, 2)
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", src_mp4, "-i", mixed, "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit={LIMIT}:attack=3:release=40:level=false[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out_mp4])
        got = lufs(out_mp4)
        if abs(got - LUFS_FINAL) <= 0.3:
            break
        g = round(g + (LUFS_FINAL - got), 2)
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g, "final_I": got}


def emph_box(text, cap, rgb, dst, dy=0):
    """강조 자막 = 숏템리폿 틀 자막과 같은 박스 + 색 글자(make_render_숏템리폿._emph_box 와 같은 꼴 — 그 파일은 import 시 렌더가 돌아 부를 수 없다)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(nv._font_file(cap["font"]), int(round(cap["size"])))
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    cx, cy = cap["x"], cap["y"] + cap["line_h"] / 2 + dy
    l, t, r, b = dr.textbbox((cx, cy), text, font=font, anchor="mm")
    bx = cap.get("box") or {"rgb": (10, 10, 14), "pad": 30, "radius": 22}; pad = bx["pad"]
    dr.rounded_rectangle([l - pad, t - pad, r + pad, b + pad], radius=bx["radius"], fill=tuple(bx["rgb"]) + (255,))
    dr.text((cx, cy), text, font=font, fill=tuple(int(v) for v in rgb) + (255,), anchor="mm")
    im.save(dst)
    return Path(dst)


def main(render=True):
    R.mkdir(parents=True, exist_ok=True)
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    for k, f in M["voice_src"].items():
        if not (SRC / f).exists():
            run(["ffmpeg", "-y", "-i", SRC / M["files"][k], "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, SRC / f])
    NL = narr_lines(S)
    for x in NL:
        print("나레", {k: v for k, v in x.items() if k != "segs"})
    blocks, pieces, dur = timeline(S, M, NL)
    gapped(blocks, NL, dur)
    for b in blocks:
        if b["kind"] == "원음":
            run(["ffmpeg", "-y", "-ss", f"{b['audio_ss']:.3f}", "-t", f"{b['a1'] - b['a0']:.3f}", "-i", SRC / M["voice_src"][b["src"]], "-ac", "1", "-ar", "48000",
                 R / f"orig_{b['id']}.wav"])
        print("블록", b)
    win = [(b["a0"], b["a1"]) for b in blocks if b["kind"] == "원음"]
    print("dur", dur, "원음 창", win)
    for p in pieces:
        print(f"  화면 {p['vs']:6.2f}-{p['ve']:6.2f} ({p['ve'] - p['vs']:.2f}s) {p['src']} {p['ss']:.2f}~{p['src_end']:.2f} {p['covers']}")
    shots_r = [{"i": 0, "full": True, "kind": "원본재편집", "src": M["files"][pieces[0]["src"]], "ss": pieces[0]["ss"],
                "cuts": [dict({"src": M["files"][p["src"]], "ss": p["ss"], "dur": round(p["ve"] - p["vs"], 3), "block": p["block"]},
                              **({"src_crop": p["src_crop"]} if p.get("src_crop") else {})) for p in pieces]}]
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py 가 만든 렌더용 — 페이지 1개 × cuts(원음 입 맞춤 시각)", "cand_dir": str(SRC).replace("\\", "/"),
                                                  "shots": shots_r, "pieces": pieces}, ensure_ascii=False, indent=1), encoding="utf-8")
    tl, aud, t = [], [], 0.0
    for b in blocks:
        if b["kind"] != "원음":
            continue
        if b["a0"] > t + 1e-3:
            tl.append([round(t, 3), b["a0"]]); aud.append({"i": len(aud), "src": M["files"]["pp"], "ss": 0.0, "mute": True})
        tl.append([b["a0"], b["a1"]]); aud.append({"i": len(aud), "src": M["files"][b["src"]], "ss": b["audio_ss"], "audio_src": M["voice_src"][b["src"]], "audio_ss": b["audio_ss"], "id": b["id"]})
        t = b["a1"]
    if dur > t + 1e-3:
        tl.append([round(t, 3), dur]); aud.append({"i": len(aud), "src": M["files"]["pp"], "ss": 0.0, "mute": True})
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": str(SRC).replace("\\", "/"), "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    cp = captions(S, blocks, NL)
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": NARR_RGB if c["kind"] == "나레" else ORIG_RGB, "t0": c["t0"], "dur": round(b - c["t0"], 3), "who": c["kind"]})
    L = [" ".join(l["text"].replace(",", "").rstrip(".") for l in S["final"]["lines"]) + "."]
    SR = dict(S, captions_plan=cp, caption_events=ev, final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장 — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "blocks": blocks, "pieces": pieces, "dur": dur, "narr": NL})
    (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads((ROOT / "channel/hottemreport/칼카피_OE11/frame_숏템리폿.json").read_text(encoding="utf-8"))
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = S["titles"]["hook"]
    fr["source"] = "칼카피_OE11/frame_숏템리폿.json(숏템리폿 v3) 그대로 — 제목 글만 이 편"
    (D / "frame_render.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in ev:
        print(f"  자막 {e['t0']:6.2f}+{e['dur']:.2f} [{e['who']}] {e['text']}")
    if not render:
        return
    nv.emph_png = emph_box
    plan_ = {"tteutgi": None, "frames": [{"frame": str(D / "frame_render.json"), "t_end": None}], "script": str(D / "대본_render.json"), "tts": str(WAV),
             "materials": str(D / "재료_render.json"), "out": str(R), "bgm": None, "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gg = [r for w, g in zip(win, gains) for r in ramp(w[0], min(w[1] + 0.06, dur), g)]
    ha.add_source_bed(str(final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                      1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    Path(final).replace(R / "final_narr.mp4")
    res = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur)
    narr_spans = [(b["n0"], b["n1"]) for b in blocks if b["kind"] == "나레"]
    rep = {"mix": res, "gains": gains, "narr": ha.measure(str(R / "final.mp4"), narr_spans), "orig": ha.measure(str(R / "final.mp4"), win),
           "all": ha.measure(str(R / "final.mp4"), [(0, dur)])}
    (R / "audio_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
