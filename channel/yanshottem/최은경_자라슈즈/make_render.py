# -*- coding: utf-8 -*-
"""얜샷템 최은경 자라슈즈 — 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/yanshottem/최은경_자라슈즈/make_render.py [--dry] [--gain 3,3,3,3]

틀 = 얜샷템(만템 색톤) channel/mantem/frame_얜샷템.json — 제목·출처 줄만 이 편 값(frame_최은경.json 과 같은 층, 글만 다름).
흐름(안나픽 1편 한고은 make_render 와 같은 길):
  미나 1회 narr_mina_natural.mp3(일레븐랩스, tone natural — expressive·stable 은 받아쓰기에서 '최은경'이 '차유경/최현경/쉬운경'으로 들려 버림)
  → 줄별로 잘라 atempo(줄마다 8.4자/초에 맞춤, 배속 차이 ±10% 안) → 원음 4구간 사이에 끼운 narr_gapped.wav
  → 재료.json 7컷을 원음 입 맞춤 시각으로 다시 놓은 재료_render.json(페이지 1개 × cuts)
  → 자막 전부 caption_events emph(나레 노랑 = 틀 자막색, 원음 흰) → narr_video.build(BGM 없음, line_asr=False)
  → hottem_audio.add_source_bed(원음 구간만 소리, 나머지 무음) → BGM 원음 창 덕킹 섞기·LUFS → render/final.mp4
★엔진과 다르게 한 것(보고 대상): ① line_asr=False ② 원음 소리 시간표를 화면 컷과 따로(원음 구간 단위) — O2 꼬리 0.61초가 다음 컷(J컷)
  ③ BGM 을 편 스크립트에서 덕킹해 섞음 ④ 나레 무음 끼우기를 여기서(맨 앞이 원음) ⑤ 원음 자막 자리 = 나레와 같은 자리(색만 흰)
  ⑥ 렌더용 대본은 나레를 한 문장으로(narr_video 줄 시작 찾기가 긴 무음에서 틀림 — 안나픽 1편과 같은 우회)
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
W = Path("C:/숏템_칼카피/yanshottem/최은경_자라슈즈")
SRC = W / "src"
R = W / "render"
RAW = R / "narr_mina_natural.mp3"
WAV = R / "narr_gapped.wav"
SRC_MP4 = "ceg_5ublOh8gB4o.mp4"
VOICE = "ceg_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
LINE_CUT = [(0.0, 3.95), (4.20, 7.50), (7.70, None)]   # narr_mina_natural.mp3 줄 경계(쉼 3.81~4.24 · 7.20~7.79 실측, 4.01~4.09 숨소리 뺌)
CPS = 8.4                         # 만템 나레 말속도
# 원음 컷 화면 길이 — 원본 컷 경계 프레임 실측(30fps): O1 511.267 · O2 519.467(프라다 사진 그래픽 시작) · O3 527.200 · O4 576.467.
# 재료.json 길이로 끝내면 다음 장면 1프레임이 섞인다(1판 8.5초에 프라다 사진 1프레임) → 2프레임 여유로 자름
VIS_LEN = {"O1": 2.88, "O2": 2.90, "O3": 2.70, "O4": 4.70}
GAP = 0.12                        # 원음↔나레 사이 쉼
GAINS = [7.0, 8.5, 6.5, 8.0]      # 원음 창 올림(dB) — 1차 +3 실측 원음 −11.8/−13.3/−11.7/−12.8 vs 나레 −8.5~−8.8 → 나레와 같은 크기(벤치 원음 −8.1 · 나레 −8.2)
LUFS_NARR = -15.0
LUFS_FINAL = -8.6                 # 벤치 mHHUlYnVgdQ −8.3 LUFS ±1.5
LIMIT = 0.84                      # 최고점 ≤ −0.5 dBFS(aac 넘침 여유)
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
TITLE = "최은경이 자라에서 건진\n명품 같은 주름 로퍼"
LABEL = "출처 : 최은경의 관리사무소"
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def nchar(s):
    return len(re.sub(r"[\s,.!?~]", "", s))


def narr_lines(S):
    """줄마다 자르고(앞뒤 무음 빼고) 8.4자/초가 되게 atempo. → [(wav, 길이, 배속, 자/초)]"""
    out, cut = [], []
    for k, (l, (a, b)) in enumerate(zip(S["final"]["lines"], LINE_CUT)):
        raw = R / f"narr_L{k + 1}_raw.wav"
        cmd = ["ffmpeg", "-y", "-i", str(RAW), "-ss", f"{a:.3f}"] + (["-to", f"{b:.3f}"] if b else []) + ["-ac", "1", "-ar", "48000", str(raw)]
        run(cmd)
        segs, _ = nv.speech_segments(str(raw))
        s0, s1 = max(0.0, segs[0][0] - 0.02), segs[-1][1]
        cut.append((raw, s0, s1, nchar(l["text"])))
    ideal = [(s1 - s0) * CPS / n for _, s0, s1, n in cut]
    base = sum(ideal) / len(ideal)   # B17: 줄별 배속은 평균 ±8% 안(말투 유지) — 그 안에서 8.4자/초에 가장 가깝게
    for k, ((raw, s0, s1, n), ti) in enumerate(zip(cut, ideal)):
        tempo = round(min(max(ti, base * 0.92), base * 1.08), 3)
        wav = R / f"narr_L{k + 1}.wav"
        run(["ffmpeg", "-y", "-i", str(raw), "-af", f"atrim={s0:.3f}:{s1 + 0.03:.3f},asetpts=N/SR/TB,atempo={tempo}", "-ac", "1", "-ar", "48000",
             "-c:a", "pcm_s16le", str(wav)])
        sg, dur = nv.speech_segments(str(wav))
        out.append({"wav": str(wav), "dur": round(dur, 3), "speech": round(sg[-1][1] - sg[0][0], 3), "tempo": tempo,
                    "cps": round(n / (sg[-1][1] - sg[0][0]), 2), "chars": n})
    return out


def timeline(S, M, NL):
    """원음 입 맞춤: O 블록 화면 시작 = 소리 시작 − (audio_ss − ss). 나레는 원음 끝 + GAP."""
    O = {o["id"]: o for o in S["final"]["orig_audio"]}
    shots = {s["line"]: s for s in M["shots"]}
    t, blocks = 0.0, []
    for bid in S["final"]["order"]:
        if bid.startswith("O"):
            sh, o = shots[bid], O[bid]
            off = round(o["spans"][0][0] - sh["ss"], 3)
            a0 = round(t + off, 3)
            blocks.append({"id": bid, "kind": "원음", "vis0": round(t, 3), "vis_len": VIS_LEN.get(bid, sh["dur"]), "a0": a0, "a1": round(a0 + o["dur"], 3),
                           "audio_ss": o["spans"][0][0]})
            t = a0 + o["dur"]
        else:
            k = int(bid[1:]) - 1
            n0 = round(t + GAP, 3)
            blocks.append({"id": bid, "kind": "나레", "line": k, "n0": n0, "n1": round(n0 + NL[k]["dur"], 3)})
            t = n0 + NL[k]["dur"] + GAP
    last = blocks[-1]
    dur = round(last["vis0"] + last["vis_len"], 3)
    last["a1"] = min(last["a1"], dur)   # 끝 원음은 화면 끝에서 자른다(말은 576.30 에 끝 — 받아쓰기)
    # 화면 컷: O = [vis0, vis0+vis_len], N = 앞 O 화면 끝 ~ 다음 O 화면 시작
    cuts = []
    for i, b in enumerate(blocks):
        sh = shots[b["id"]]
        if b["kind"] == "원음":
            cuts.append((sh, b["vis0"], round(min(b["vis0"] + b["vis_len"], blocks[i + 1]["vis0"] if i + 1 < len(blocks) and "vis0" in blocks[i + 1] else dur), 3)))
        else:
            a = cuts[-1][2]
            e = blocks[i + 1]["vis0"]
            cuts.append((sh, a, e))
    return blocks, cuts, dur


def gapped(blocks, NL, dur):
    fc, lab, t = [], [], 0.0
    for i, b in enumerate(x for x in blocks if x["kind"] == "나레"):
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{b['n0'] - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        t = b["n0"] + NL[b["line"]]["dur"]
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{dur - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    ins = []
    for x in NL:
        ins += ["-i", x["wav"]]
    run(["ffmpeg", "-y"] + ins + ["-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(WAV)])


def spread(caps, a, b, speech=None):
    """자막 조각을 [a,b] 안 말소리 시간에 글자 수 비례로 놓는다. speech = 말 구간 [(s,e)](완성본 초) — 쉼에는 경계를 안 둔다."""
    speech = speech or [(a, b)]
    tot = sum(e - s for s, e in speech)
    n = [nchar(c) for c in caps]
    N = sum(n)

    def at(frac):   # 말 시간 비율 → 완성본 초
        need = frac * tot
        for s, e in speech:
            if need <= e - s + 1e-9:
                return s + need
            need -= e - s
        return speech[-1][1]
    out, acc = [], 0
    for c, k in zip(caps, n):
        t0 = a if acc == 0 else at(acc / N)
        acc += k
        out.append({"t0": round(t0, 3), "t1": round(at(acc / N), 3), "text": c})
    return out


def captions(S, blocks, NL):
    O = {o["id"]: o for o in S["final"]["orig_audio"]}
    cp = []
    for b in blocks:
        if b["kind"] == "원음":
            o = O[b["id"]]
            segs, _ = nv.speech_segments(str(R / f"orig_{b['id']}.wav"), noise="-38dB", d=0.12)
            sp = [(b["a0"] + s, b["a0"] + e) for s, e in segs] or None
            for c in spread(o["caps"], b["a0"], b["a1"], sp):
                cp.append(dict(c, kind="원음"))
        else:
            l = S["final"]["lines"][b["line"]]
            for c in spread(l["caps"], b["n0"], b["n1"]):
                cp.append(dict(c, kind="나레"))
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
         f"volume='{terms}':eval=frame,afade=t=out:st={dur - 0.5:.3f}:d=0.5", "-c:a", "pcm_s16le", str(tmp)])
    mixed = R / "work_mix.wav"
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    I = lufs(mixed)
    g = round(LUFS_FINAL - I, 2)
    # 벤치가 −8.3 LUFS 라 크게 올린다 — 리미터가 깎는 만큼 한 번 더 맞춘다(2회)
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(mixed), "-filter_complex",
             f"[1:a]volume={g}dB,alimiter=limit={LIMIT}:attack=3:release=40:level=false[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
        got = lufs(out_mp4)
        if abs(got - LUFS_FINAL) <= 0.4:
            break
        g = round(g + (LUFS_FINAL - got), 2)
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g, "final_I": got}


def main(render=True):
    R.mkdir(parents=True, exist_ok=True)
    if not (SRC / VOICE).exists():
        run(["ffmpeg", "-y", "-i", str(SRC / SRC_MP4), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    NL = narr_lines(S)
    for x in NL:
        print("나레", x)
    blocks, cuts, dur = timeline(S, M, NL)
    gapped(blocks, NL, dur)
    for b in blocks:
        if b["kind"] == "원음":
            run(["ffmpeg", "-y", "-ss", f"{b['audio_ss']:.3f}", "-t", f"{b['a1'] - b['a0']:.3f}", "-i", str(SRC / VOICE), "-ac", "1", "-ar", "48000",
                 str(R / f"orig_{b['id']}.wav")])
        print("블록", b)
    win = [(b["a0"], b["a1"]) for b in blocks if b["kind"] == "원음"]
    print("dur", dur, "orig windows", win)
    for sh, a, e in cuts:
        over = (e - a) - sh["dur"]
        print(f"  컷 {a:6.2f}-{e:6.2f} ({e - a:.2f}s) {sh['line']} ss{sh['ss']} → 소스 {sh['ss']:.2f}~{sh['ss'] + e - a:.2f}" + (f"  ★계획보다 {over:+.2f}s" if over > 0.02 else ""))
    # 렌더용 재료 — 페이지 1개 × cuts
    shots_r = [{"i": 0, "full": True, "kind": "원본재편집", "src": cuts[0][0]["src"], "ss": cuts[0][0]["ss"], "src_crop": cuts[0][0]["src_crop"],
                "cuts": [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": round(e - s, 3), "plan_i": x["i"]} for x, s, e in cuts],
                "t_final": [0.0, dur]}]
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py — 페이지 1개 × cuts(원음 입 맞춤 시각)", "cand_dir": M["cand_dir"],
                                                  "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
    # 소리 시간표 = 원음 구간 단위(화면 컷과 따로) — 원음 구간 밖은 무음
    tl, aud, t = [], [], 0.0
    for b in blocks:
        if b["kind"] != "원음":
            continue
        if b["a0"] > t + 1e-3:
            tl.append([round(t, 3), b["a0"]]); aud.append({"i": len(aud), "src": SRC_MP4, "ss": 0.0, "mute": True})
        tl.append([b["a0"], b["a1"]]); aud.append({"i": len(aud), "src": SRC_MP4, "ss": b["audio_ss"], "audio_src": VOICE, "audio_ss": b["audio_ss"],
                                                   "id": b["id"]})
        t = b["a1"]
    if dur > t + 1e-3:
        tl.append([round(t, 3), dur]); aud.append({"i": len(aud), "src": SRC_MP4, "ss": 0.0, "mute": True})
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"].replace("/src", "/src"), "shots": aud}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    cp = captions(S, blocks, NL)
    fr0 = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr0["layers"] if l.get("role") == "caption")["rgb"]
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": ycol if c["kind"] == "나레" else [255, 255, 255], "t0": c["t0"],
                   "dur": round(b - c["t0"], 3), "who": c["kind"]})
    L = [" ".join(l["text"].replace(",", "") for l in S["final"]["lines"]) + "."]
    steps, dur2 = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    SR = dict(S, captions_plan=cp, caption_events=ev,
              final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장(엔진 우회 ⑥) — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "blocks": blocks, "dur": dur, "narr": NL,
                      "tts": "일레븐랩스 미나 natural 1회(narr_mina_natural.mp3) → 줄별 atempo"})
    (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads(FRAME.read_text(encoding="utf-8"))
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = TITLE
        if l.get("role") == "label":
            l["text"] = LABEL
    (D / "frame_render.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in ev:
        print(f"  자막 {e['t0']:6.2f}+{e['dur']:.2f} [{e['who']}] {e['text']}")
    print("wav dur", dur2)
    if not render:
        return
    plan_ = {"tteutgi": str(ROOT / "channel/yanshottem/최은경_자라슈즈/뜯기/뜯기.json"), "frames": [{"frame": str(D / "frame_render.json"), "t_end": None}],
             "script": str(D / "대본_render.json"), "tts": str(WAV), "materials": str(D / "재료_render.json"), "out": str(R), "bgm": None,
             "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gg = [r for w, g in zip(win, gains) for r in ramp(w[0], min(w[1] + 0.06, dur), g)]
    ha.add_source_bed(str(final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                      1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    Path(final).replace(R / "final_narr.mp4")
    res = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur)
    print(json.dumps(res, ensure_ascii=False))
    narr_spans = [(b["n0"], b["n1"]) for b in blocks if b["kind"] == "나레"]
    print("나레", json.dumps(ha.measure(str(R / "final.mp4"), narr_spans), ensure_ascii=False))
    print("원음", json.dumps(ha.measure(str(R / "final.mp4"), win), ensure_ascii=False))
    print("전체", json.dumps(ha.measure(str(R / "final.mp4"), [(0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
