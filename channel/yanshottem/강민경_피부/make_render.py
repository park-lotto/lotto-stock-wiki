# -*- coding: utf-8 -*-
"""얜샷템 강민경 포트레 스킨 틴트 — 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17). 장윤정 편 make_render.py 와 같은 길.
    PYTHONUTF8=1 py channel/yanshottem/강민경_피부/make_render.py [--dry] [--gain 0,0,0]

틀 = 얜샷템(만템 색톤) channel/mantem/frame_얜샷템.json — _build_json.py 가 제목·출처 줄만 바꾼 frame_강민경.json.
흐름(안나픽 한고은 채소통 make_render 와 같은 길):
  미나 1회 narr_mina.mp3(11.92초) → atempo 1.55 narr_t155.wav(7.70초, 타입캐스트 0·일레븐 재호출 0)
  → 나레 3줄을 대본.json 블록 시각(원음으로 시작 O1 → N1 → O2 → N2 → O3 → N3 끝)에 끼운 narr_gapped.wav
  → 재료.json 11컷을 한 페이지 shots[].cuts 로 묶은 재료_render.json(컷 = 재료.json t_final 그대로)
  → 자막 = captions_plan 전부 caption_events emph(나레 노랑 = 틀 자막색 · 원음 흰) → narr_video.build(BGM 없음, line_asr=False)
  → hottem_audio.add_source_bed(컷 단위 소리 시간표, 원음 = 강민경 말만) → BGM 원음 창 덕킹 섞기·LUFS → render/final.mp4
★엔진과 다르게 한 것(한고은 편과 같음): ① line_asr=False ② 원음 소리 시간표를 컷 단위 파일로 ③ BGM 을 편 스크립트에서 덕킹
  ④ 나레 무음 끼우기를 여기서(원음으로 시작) ⑤ 렌더용 대본은 나레를 한 문장으로(페이지 1개) — 자막은 전부 emph.
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
W = Path("C:/숏템_칼카피/yanshottem/강민경_피부")
SRC = W / "src"
R = W / "render"
NARR = R / "narr_t155.wav"
WAV = R / "narr_gapped.wav"
SRC_MP4 = "kmk_WmEjrZFVRB4.mp4"
VOICE = "kmk_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
GAINS = [0.0, 0.0, 0.0]          # 원음 창(O1 · O2 · O3) 올림 dB — 원본 구간 −16.8/−18.5/−15.5 LUFS
LUFS_NARR = -15.0
LUFS_FINAL = -18.2               # 벤치 v1MZ9s9kl0Y 실측 −18.7 LUFS(±1.5)
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
FRAME = D / "frame_강민경.json"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def gapped(S, total):
    """대본.json 나레 줄 i 의 slice(narr_t155 안 말 구간)를 그 블록 시작(t_final[0])에 놓고 나머지는 무음."""
    fc, lab, t = [], [], 0.0
    for i, l in enumerate(S["final"]["lines"]):
        a, b = l["slice"]; t0 = l["t_final"][0]
        if t0 - t > 1e-3:
            fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{t0 - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        t = t0 + (b - a)
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{total - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y", "-i", str(NARR), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(WAV)])


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def ramp(a, b, g, up=0.06, down=0.10, depth=6.0):
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


def merged_windows(O):
    """이어 붙은 원음 블록은 창 하나로 — 블록 경계에서 올림이 꺼졌다 켜지지 않게."""
    out = []
    for o in O:
        a, b = o["t_final"]
        if out and abs(out[-1][1] - a) < 1e-3:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def main(render=True):
    R.mkdir(parents=True, exist_ok=True)
    if not (SRC / VOICE).exists():
        run(["ffmpeg", "-y", "-i", str(SRC / SRC_MP4), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    total = S["final"]["check"]["dur_est"]
    gapped(S, total)
    L = [" ".join(l["text"].replace(",", "").rstrip(".") for l in S["final"]["lines"]) + "."]
    steps, dur = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    pages = [0.0, dur]
    win = merged_windows(S["final"]["orig_audio"])
    print("dur", dur, "(계획", total, ") orig windows", win)
    cuts = [(s, s["t_final"][0], s["t_final"][1]) for s in M["shots"]]
    shots_r = [{"i": 0, "full": True, "kind": "원본재편집", "src": cuts[0][0]["src"], "ss": cuts[0][0]["ss"], "src_crop": cuts[0][0]["src_crop"],
                "cuts": [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": round(e - s, 3), "plan_i": x["i"]} for x, s, e in cuts],
                "t_final": [0.0, round(dur, 3)]}]
    tl, aud = [], []
    for x, s, e in cuts:
        tl.append([round(s, 3), round(e, 3)])
        snd = {"i": len(aud), "src": x["src"], "ss": x["ss"], "plan_i": x["i"], "t_final": [round(s, 3), round(e, 3)]}
        if x.get("mute") or not x.get("audio_src"):
            snd["mute"] = True
        else:
            snd["audio_src"] = VOICE
            snd["audio_ss"] = x["audio_ss"]
        aud.append(snd)
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py — 페이지 1 × shots[].cuts(재료.json t_final 그대로)", "cand_dir": M["cand_dir"],
                                                  "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"], "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr["layers"] if l.get("role") == "caption")["rgb"]
    cp = S["captions_plan"]
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": ycol if c["kind"] == "나레" else [255, 255, 255], "t0": round(c["t0"], 3),
                   "dur": round(b - c["t0"], 3), "who": c["kind"]})
    SR = dict(S, caption_events=ev, final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장 — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "pages": pages, "dur": dur, "tts": "일레븐랩스 미나 1회 → atempo 1.55"})
    (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in ev:
        print(f"  emph {e['t0']:6.2f}+{e['dur']:.2f} {e['text']}")
    if not render:
        return
    plan_ = {"tteutgi": str(D / "뜯기/v1MZ9s9kl0Y/뜯기.json"), "frames": [{"frame": str(FRAME), "t_end": None}],
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
    narr_spans = [(l["t_final"][0], l["t_final"][0] + l["slice"][1] - l["slice"][0]) for l in S["final"]["lines"]]
    print("나레", json.dumps(ha.measure(str(R / "final.mp4"), narr_spans), ensure_ascii=False))
    print("원음", json.dumps(ha.measure(str(R / "final.mp4"), win), ensure_ascii=False))
    print("전체", json.dumps(ha.measure(str(R / "final.mp4"), [(0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
