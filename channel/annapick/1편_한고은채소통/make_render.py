# -*- coding: utf-8 -*-
"""얜샷템 한고은 채소 보관통 — 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/annapick/1편_한고은채소통/make_render.py [--dry] [--gain 6,6,6]

틀 = 얜샷템(만템 색톤) channel/mantem/frame_얜샷템.json — 제목·출처 줄만 이 편 값으로.
흐름(아이템홈 1편 3판 make_render 와 같은 길):
  미나 1회 narr_mina.mp3 → atempo 1.55 narr_t155.wav(타입캐스트 0·일레븐 재호출 0)
  → 나레 2줄을 대본.json 시각표(원음 3구간 사이)에 끼운 narr_gapped.wav(처음 3.20초 = 원음 훅 자리 무음)
  → 재료.json 9컷을 자막 페이지별 shots[].cuts 로 묶은 재료_render.json
  → 원음 자막(caption_events emph, 흰색 — 만템: 나레 노랑·원음 흰) → narr_video.build(BGM 없음, line_asr=False)
  → hottem_audio.add_source_bed(컷 단위 소리 시간표, 원음 = 한고은 말만) → BGM 원음 창 덕킹 섞기·LUFS → render/final.mp4
★엔진과 다르게 한 것(보고 대상): ① line_asr=False ② 원음 소리 시간표를 컷 단위 파일로 ③ BGM 을 편 스크립트에서 덕킹해 섞음
  ④ 나레 무음 끼우기를 gap_tts 대신 여기서(gap_tts 는 '맨 앞 무음'을 못 넣는다 — 이 편은 원음으로 시작)
  ⑤ 원음 자막 자리: 만템은 원음 자막이 나레보다 약 100px 아래인데 emph 는 같은 자리만 — 색만 흰색으로 가름.
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
W = Path("C:/숏템_칼카피/annapick/1편_한고은채소통")
SRC = W / "src"
R = W / "render"
NARR = R / "narr_t155.wav"
WAV = R / "narr_gapped.wav"
VOICE = "hge_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 아이템홈 3판 v4 와 같은 약한 처리
GAINS = [15.0, 14.5, 15.0]       # 원음 창 올림(dB) — 실측: +6 → 원음 −22 vs 나레 −11~−13(10dB 차) · +13 → −18 vs −13~−16 · 벤치 나레가 원음보다 약 3dB 큼
LUFS_NARR = -15.0
LUFS_FINAL = -17.0                # 벤치 itY −18.2 ±1.5 안 · 채널 중앙 −16.15
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
TITLE = "샐러드 1kg 사는 한고은의\n두 달 가는 채소 보관통"
LABEL = "출처 : 고은언니 한고은"
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def gapped(S):
    """대본.json 시각표대로 나레 2줄을 무음 사이에 놓는다 — 줄 i 는 lines[i].slice 구간을 t_final(줄 시작)에."""
    lines = S["final"]["lines"]
    starts = [c["t0"] for c in S["captions_plan"] if c["kind"] == "나레"]
    blocks, prev = [], None
    for c in S["captions_plan"]:
        if c["kind"] == "나레" and prev != "나레":
            blocks.append((c["t0"], "나레"))
        prev = c["kind"]
    total = S["final"]["check"]["total_sec"]
    parts, t = [], 0.0
    fc, lab = [], []
    for i, (l, (t0, _)) in enumerate(zip(lines, blocks)):
        a, b = l["slice"]
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{t0 - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        t = t0 + (b - a)
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{total - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y", "-i", str(NARR), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(WAV)])
    return blocks, total


def ramp(a, b, g, up=0.08, down=0.10, depth=6.0):
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
         f"volume='{terms}':eval=frame,afade=t=out:st={dur - 0.6:.3f}:d=0.6", "-c:a", "pcm_s16le", str(tmp)])
    mixed = R / "work_mix.wav"
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    I = lufs(mixed)
    g = round(LUFS_FINAL - I, 2)
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(mixed), "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g}


def main(render=True):
    R.mkdir(parents=True, exist_ok=True)
    if not (SRC / VOICE).exists():
        run(["ffmpeg", "-y", "-i", str(SRC / "hge_LcQv9yOh3Wc.mp4"), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    blocks, dur0 = gapped(S)
    # ★엔진 우회 ⑥: narr_video 는 나레 줄 시작을 쉼으로 찾는데(line_starts) 원음 자리 무음이 길어 둘째 줄을 못 찾는다(--dry 실측 3.997초로 틀림).
    #   → 렌더용 대본은 나레를 마침표 없는 한 문장으로 넘겨 페이지 1개(컷은 shots[].cuts 로 재료.json 시각 그대로),
    #     자막은 전부 caption_events emph 로 대본 captions_plan 시각에 얹는다(나레 = 틀 자막색 노랑, 원음 = 흰).
    L = [" ".join(l["text"].rstrip(".") for l in S["final"]["lines"]) + "."]
    steps, dur = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    pages = [0.0, dur]
    O = S["final"]["orig_audio"]
    win = [tuple(o["t_final"]) for o in O]
    print("dur", dur, "(계획", dur0, ") pages", pages, "orig windows", win)
    # 컷 = 재료.json t_final 그대로(계획 = 렌더). 페이지별로 묶는다
    cuts = [(s, s["t_final"][0], s["t_final"][1]) for s in M["shots"]]
    shots_r, tl, aud = [], [], []
    for p in range(len(pages) - 1):
        a, b = pages[p], pages[p + 1]
        cc = [(x, s, e) for x, s, e in cuts if a - 1e-6 <= s < b - 1e-6]
        shots_r.append({"i": p, "full": True, "kind": "원본재편집", "src": cc[0][0]["src"], "ss": cc[0][0]["ss"], "src_crop": cc[0][0]["src_crop"],
                        "cuts": [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": round(e - s, 3), "plan_i": x["i"]} for x, s, e in cc],
                        "t_final": [round(a, 3), round(b, 3)]})
    for x, s, e in cuts:
        tl.append([round(s, 3), round(e, 3)])
        snd = {"i": len(aud), "src": x["src"], "ss": x["ss"], "plan_i": x["i"], "t_final": [round(s, 3), round(e, 3)]}
        if x.get("mute") or not x.get("audio_src"):
            snd["mute"] = True
        else:
            snd["audio_src"] = VOICE
            snd["audio_ss"] = x["audio_ss"]
        aud.append(snd)
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py — 자막 페이지 × shots[].cuts(재료.json t_final 그대로)", "cand_dir": M["cand_dir"],
                                                  "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"], "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    # 자막 = captions_plan 전부(나레 노랑 = 틀 자막색, 원음 흰) — 각 조각은 다음 조각 시작까지(빈 틈 없이), 마지막은 끝까지
    fr0 = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr0["layers"] if l.get("role") == "caption")["rgb"]
    cp = S["captions_plan"]
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": ycol if c["kind"] == "나레" else [255, 255, 255], "t0": round(c["t0"], 3),
                   "dur": round(b - c["t0"], 3), "who": c["kind"]})
    S["caption_events"] = ev
    SR = dict(S, final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장(엔진 우회 ⑥) — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "pages": pages, "dur": dur, "tts": "일레븐랩스 미나 1회 → atempo 1.55"})
    (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads(FRAME.read_text(encoding="utf-8"))
    for l in fr["layers"]:
        if l.get("role") == "title":
            l["text"] = TITLE
        if l.get("role") == "label":
            l["text"] = LABEL
    (D / "frame_render.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in steps:
        print(f"  step {s['t0']:6.2f}-{s['t1']:6.2f} L{s['line']} new_cut={s['new_cut']} {s['text']}")
    for e in ev:
        print(f"  emph {e['t0']:6.2f}+{e['dur']:.2f} {e['text']}")
    if not render:
        return
    plan_ = {"tteutgi": str(ROOT / "channel/annapick/뜯기/itYwQVyuCcc/뜯기.json"), "frames": [{"frame": str(D / "frame_render.json"), "t_end": None}],
             "script": str(D / "대본_render.json"), "tts": str(WAV), "materials": str(D / "재료_render.json"), "out": str(R), "bgm": None,
             "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gg = [r for w, g in zip(win, gains) for r in ramp(w[0], min(w[1] + 0.10, dur), g)]
    ha.add_source_bed(str(final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                      1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    Path(final).replace(R / "final_narr.mp4")
    res = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur)
    print(json.dumps(res, ensure_ascii=False))
    narr_spans = [(b[0], b[0] + l["est_sec"]) for b, l in zip(blocks, S["final"]["lines"])]
    print("나레", json.dumps(ha.measure(str(R / "final.mp4"), narr_spans), ensure_ascii=False))
    print("원음", json.dumps(ha.measure(str(R / "final.mp4"), win), ensure_ascii=False))
    print("전체", json.dumps(ha.measure(str(R / "final.mp4"), [(0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
