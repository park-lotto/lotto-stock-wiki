# -*- coding: utf-8 -*-
"""얜샷템 이영자 실내화 — 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/yanshottem/이영자_실내화/make_render.py [--dry] [--gain 10,12]

틀 = 얜샷템(만템 색톤) — _build_json.py 가 만든 frame_이영자.json(frame_얜샷템 에서 제목·출처 글만 바꿈).
흐름(안나픽 1편 한고은채소통 make_render 와 같은 길):
  미나 1회 narr_mina.mp3(9.76초, 나레 전문 1회) → 줄 사이 쉼에서 갈라 atempo N1 1.54·N2 1.45 → narr_tempo.wav(타입캐스트 0·일레븐 재호출 0)
  → 나레 2줄을 대본.json 시각표(원음 2구간 사이)에 끼운 narr_gapped.wav(처음 1.68초 = 원음 훅 자리 무음)
  → 재료.json 6컷을 shots[].cuts 로 묶은 재료_render.json
  → 자막 = captions_plan 전부 caption_events emph(나레 = 틀 자막색 노랑, 원음 = 흰) → narr_video.build(BGM 없음, line_asr=False)
  → hottem_audio.add_source_bed(컷 단위 소리 시간표, 원음 = 이영자 말만 — 원음 O2 위 B롤 컷도 이영자 원음을 이어 깐다) → BGM 원음 창 덕킹 섞기·LUFS → render2/final.mp4
★엔진과 다르게 한 것(보고 대상): ① line_asr=False ② 원음 소리 시간표를 컷 단위 파일로 ③ BGM 을 편 스크립트에서 덕킹해 섞음
  ④ 나레 무음 끼우기를 여기서(gap_tts 는 '맨 앞 무음'을 못 넣는다) ⑤ 원음 자막은 emph 같은 자리·색만 흰색
  ⑥ 렌더용 대본은 나레를 한 문장으로(narr_video line_starts 가 긴 무음 뒤 둘째 줄을 못 찾음 — 안나픽 1편 실측)
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
W = Path("C:/숏템_칼카피/yanshottem/이영자_실내화")
SRC = W / "src"
R = W / "render2"                 # 10-17 수리판(제품 B롤 2컷·마당 표지) — 1판은 render/ 그대로 둔다
MINA = W / "render" / "narr_mina.mp3"   # TTS 재호출 0 — 1판 미나 원음 재사용
NARR = R / "narr_tempo.wav"
WAV = R / "narr_gapped.wav"
VOICE = "yj_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 아이템홈 3판·안나픽 1편과 같은 약한 처리
GAINS = [14.0, 17.0]             # 원음 창 올림(dB) — 벤치: 원음 −14.2/−16.6 vs 나레 −18.4/−17.6(원음이 2~4dB 큼) · 1차 [10,12] 실측 원음 −17.2/−18.1 vs 나레 −16.0/−14.1 → [14,17] 원음 −15.5/−16.2 vs 나레 −18.2/−16.3
LUFS_NARR = -15.0
LUFS_FINAL = -16.8               # 벤치 nt6WIGFmILE 실측 −16.8
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0
FRAME = D / "frame_이영자.json"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def tempo(S):
    """미나 1.0 원음을 줄 사이 쉼(6.86~7.20, 실측)에서 갈라 줄별 atempo — _build_json.py TEMPO 와 같은 값."""
    t1, t2 = [l["atempo"] for l in S["final"]["lines"]]
    run(["ffmpeg", "-y", "-i", str(MINA), "-filter_complex",
         f"[0:a]aresample=48000,aformat=channel_layouts=mono,asplit=2[x][y];"
         f"[x]atrim=0:6.86,asetpts=N/SR/TB,atempo={t1}[a];[y]atrim=7.20:9.76,asetpts=N/SR/TB,afade=t=out:st=2.50:d=0.06,atempo={t2}[b];"
         "[a][b]concat=n=2:v=0:a=1[o]", "-map", "[o]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(NARR)])


def gapped(S):
    """대본.json 시각표대로 나레 2줄을 무음 사이에 놓는다 — 줄 i 는 lines[i].slice 구간을 lines[i].t_final[0] 에."""
    total = S["final"]["check"]["dur"]
    fc, lab, t = [], [], 0.0
    for i, l in enumerate(S["final"]["lines"]):
        a, b = l["slice"]
        t0 = l["t_final"][0]
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{t0 - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=mono[p{i}]"); lab.append(f"[p{i}]")
        t = t0 + (b - a)
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{total - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y", "-i", str(NARR), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(WAV)])
    return total


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
        run(["ffmpeg", "-y", "-i", str(SRC / "yj_BHuue4ga-w0.mp4"), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    tempo(S)
    dur0 = gapped(S)
    L = [" ".join(l["tts"].rstrip(".") for l in S["final"]["lines"]) + "."]
    steps, dur = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    win = [tuple(o["t_final"]) for o in S["final"]["orig_audio"]]
    print("dur", dur, "(계획", dur0, ") orig windows", win)
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
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py — 페이지 1개 × shots[].cuts(재료.json t_final 그대로)", "cand_dir": M["cand_dir"],
                                                  "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"], "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    fr0 = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr0["layers"] if l.get("role") == "caption")["rgb"]
    cp = S["captions_plan"]
    ev = []
    for j, c in enumerate(cp):
        b = cp[j + 1]["t0"] if j + 1 < len(cp) else dur
        ev.append({"kind": "emph", "text": c["text"], "rgb": ycol if c["kind"] == "나레" else [255, 255, 255], "t0": round(c["t0"], 3),
                   "dur": round(b - c["t0"], 3), "who": c["kind"]})
    SR = dict(S, caption_events=ev, final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장(엔진 우회 ⑥) — 원문 줄은 대본.json"}]),
              render={"windows": [list(w) for w in win], "dur": dur, "tts": "일레븐랩스 미나 1회 → 줄별 atempo 1.54/1.45"})
    (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
    for e in ev:
        print(f"  emph {e['t0']:6.2f}+{e['dur']:.2f} {e['who']} {e['text']}")
    if not render:
        return
    plan_ = {"tteutgi": str(D / "뜯기/nt6WIGFmILE/뜯기.json"), "frames": [{"frame": str(FRAME), "t_end": None}],
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
    narr_spans = [tuple(l["t_final"]) for l in S["final"]["lines"]]
    print("나레", json.dumps(ha.measure(str(R / "final.mp4"), narr_spans), ensure_ascii=False))
    print("원음", json.dumps(ha.measure(str(R / "final.mp4"), win), ensure_ascii=False))
    print("전체", json.dumps(ha.measure(str(R / "final.mp4"), [(0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
