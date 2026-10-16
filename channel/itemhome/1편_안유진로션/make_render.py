# -*- coding: utf-8 -*-
"""아이템홈(얜샷템) 1편 안유진 로션 — 렌더 감싸기 3판. 엔진 코드는 안 고친다(관제 097, 2026-10-17).

3판(사장님 2판 지적 '19초부터 끊긴다'·'타겟에서 샀어요 무슨 말인지'):
  · 점프 줌 0 — 이어지는 한 장면 = 크롭 하나, 컷은 소스 시각이 뛰거나 다른 장면(eos 제품만 컷)일 때만(재료.json 3판 컷 19개)
  · 원음 = 받아쓰기로 알아들리는 구간만: O1 '이게 제가 엄청 SNS에서 많이 본 아이거든요. 바닐라 캐시미어 향' · O2 '근데 이게 뭔가 …묘하게 중독되는 그런 향'.
    O3('맡아보시면…타겟에서 샀어요', 원본 −34~−37 LUFS 웅얼거림) 뺌 → 나레 3번 줄도 뺌(1판 TTS 를 잘라 씀, 타입캐스트 재호출 0)
  · 원음은 목소리 대역만 살린 IVE 소리(ive_voice_v3.wav: 고역·저역 컷 + 잡음 줄임 + 압축)로 올림 — 2판은 +14~20dB 에 IVE 편집 BGM 까지 커짐
  · 우리 BGM 은 narr_video 밖에서 깔고 원음 창에서 −10dB 덕킹(램프 0.15초) — narr_video BGM 은 전 구간 같은 크기라 덕킹이 안 된다
흐름: TTS 2줄 자르기 → gap_tts → 재료_render.json(페이지 2 × cuts) → narr_video.build(bgm 없음, line_asr=False)
      → hottem_audio.add_source_bed(컷 단위 소리 시간표) → BGM 덕킹 섞기·LUFS 맞춤 → render3/final.mp4
★엔진과 다르게 한 것(보고 대상): ① line_asr=False ② 원음 소리 시간표를 컷 단위 파일로 ③ BGM 을 편 스크립트에서 덕킹해 섞음 ④ 원음 소리 전처리.
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
SRC = Path("C:/숏템_칼카피/itemhome/1편_안유진로션/src")
R0 = Path("C:/숏템_칼카피/itemhome/1편_안유진로션/render")      # 1판 — narr_문정.mp3(타입캐스트 1회) → narr_t110.wav(atempo 1.10)
R = Path("C:/숏템_칼카피/itemhome/1편_안유진로션/render3")
NARR2 = R / "narr_2l.wav"            # narr_t110.wav 앞 2줄(3번 줄 '향 소개 끝엔…' 앞 쉼 가운데 8.40초에서 자름)
CUT_AT = 8.40
WAV = R / "narr_gapped.wav"
GAPS = {"0": 3.30, "end": 7.20}      # O1 3.40·O2 6.92 + 앞 0.08 + 끝 여유(끝 0.45초 BGM)
LEAD = 0.08
LUFS_NARR = -15.0                    # narr_video 나레 목표(BGM 없음)
LUFS_FINAL = -13.8                   # 채널 규칙표 중앙
BGM, BGM_DB, DUCK_DB = "sweets", -24.5, -10.0   # BGM 통합 −24.5 LUFS(2판 실측 경계 바닥 −22~−26dB 맞춤) · 원음 창 −10dB
VOICE = "ive_voice_v4.wav"
# 3판 1차 v3(afftdn 잡음 줄임+강한 압축)는 받아쓰기가 원본보다 나빴다(O1 '바닐라 캐시미어'→'캐슈넛') → 저역만 컷 + 약한 압축
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"
GAINS = [17.0, 17.0]                 # 원음 창 올림(dB) — 3판 1차 [10,8] 실측 −18.8/−20.2 LUFS(나레 −11.7) → +7
TITLE = "안유진이 호텔에서 꺼낸\n묘하게 중독되는 로션"


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def prep():
    R.mkdir(parents=True, exist_ok=True)
    if not NARR2.exists():
        run(["ffmpeg", "-y", "-i", str(R0 / "narr_t110.wav"), "-t", f"{CUT_AT}", "-c:a", "pcm_s16le", str(NARR2)])
    if not WAV.exists():
        S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
        print("gap", ha.gap_tts(str(NARR2), [l["text"] for l in S["final"]["lines"]], GAPS, str(WAV)))
    if not (SRC / VOICE).exists():   # IVE 원본 소리 전체(시각 그대로) — 목소리 대역 전처리
        run(["ffmpeg", "-y", "-i", str(SRC / "ive_8o3M3DmY05E.mp4"), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])


def ramp(a, b, g, up=0.10, down=0.12, depth=6.0):
    st = 4
    out = [[round(a + up * i / st, 3), round(a + up * (i + 1) / st, 3), round(g - 12 * (1 - (i + 1) / st), 2)] for i in range(st)]
    out.append([round(a + up, 3), round(b - down, 3), g])
    out += [[round(b - down + down * i / st, 3), round(b - down + down * (i + 1) / st, 3), round(g - depth * (i + 1) / st, 2)] for i in range(st)]
    return out


def windows(S):
    segs, dur = nv.speech_segments(str(WAV))
    O = S["final"]["orig_audio"]
    gap_starts = [a for (_, a), (b, _) in zip(segs, segs[1:]) if b - a >= 1.0] + [segs[-1][1]]
    win = [(round(gap_starts[k] + LEAD, 3), round(gap_starts[k] + LEAD + O[k]["dur"], 3)) for k in range(len(O))]
    return segs, dur, win, O


def build_cuts(S, steps, pages, win, dur):
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    by = {}
    for sh in M["shots"]:
        by.setdefault(sh["line"], []).append(sh)

    def narr_cuts(bid, a, b, li):
        sh = by[bid]
        ch = [s["t0"] for s in steps if s["line"] == li] + [b]
        if bid == "N2" and len(ch) - 1 >= len(sh):   # N2 = 자막 조각 경계에 컷(병 컷이 '이오에스 바닐라'에 맞게) · N1 = 계획 길이 비례(0.3초 조각 컷 방지)
            bounds = ch[:len(sh)] + [b]
        else:
            tot = sum(x["dur"] for x in sh); bounds = [a]
            for x in sh:
                bounds.append(bounds[-1] + (b - a) * x["dur"] / tot)
        return [(x, bounds[k], bounds[k + 1]) for k, x in enumerate(sh)]

    def orig_cuts(bid, a, b):
        sh, t, out = by[bid], a, []
        for k, x in enumerate(sh):
            e = b if k == len(sh) - 1 else t + x["dur"]
            out.append((x, t, e)); t = e
        return out
    plan = [("N1", 0, 0.0, win[0][0]), ("O1", None, win[0][0], pages[1]), ("N2", 1, pages[1], win[1][0]), ("O2", None, win[1][0], dur)]
    cuts = []
    for bid, li, a, b in plan:
        cuts += narr_cuts(bid, a, b, li) if li is not None else orig_cuts(bid, a, b)
    # 같은 소스 연속 컷: 원본 시각이 앞으로만(무음 컷은 앞 컷 끝으로 당겨 잇는다) + 표
    fixed, audit = [], []
    for x, s_, e in cuts:
        x = dict(x)
        if fixed and fixed[-1][0]["src"] == x["src"]:
            px, ps, pe = fixed[-1]
            pend = round(px["ss"] + (pe - ps), 3)
            if x["ss"] < pend - 1e-3 and x.get("mute") and pend - x["ss"] < 5:
                x["ss"] = pend
            d = round(x["ss"] - pend, 3)
            kind = "이어짐" if abs(d) <= 0.02 else ("앞으로 건너뜀" if d > 0 else ("다른 장면(5초+ 앞)" if d <= -5 else "되감김"))
            audit.append({"t": round(s_, 3), "src": x["src"], "prev_end": pend, "ss": x["ss"], "delta": d, "kind": kind,
                          "crop_same": px["src_crop"][2:] == x["src_crop"][2:]})
        fixed.append((x, s_, e))
    return M, fixed, audit


def bgm_mix(src_mp4, out_mp4, win, dur):
    """우리 BGM 을 원음 창에서 덕킹해 섞고 전체 LUFS 를 맞춘다(편 스크립트 — narr_video 는 BGM 덕킹이 없다)."""
    bgm = bgm_lib.path_of(BGM)
    k = 10 ** (DUCK_DB / 20)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win)
    tmp = R / "work_bgm.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bgm, "-t", f"{dur:.3f}", "-af", f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={BGM_DB}:TP=-6:LRA=11,"
         f"volume='{terms}':eval=frame", "-c:a", "pcm_s16le", str(tmp)])
    mixed = R / "work_mix.wav"
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(["ffmpeg", "-hide_banner", "-i", str(mixed), "-af", "ebur128", "-f", "null", "-"],
                                                                capture_output=True, text=True, encoding="utf-8", errors="replace").stderr)[-1])
    g = round(LUFS_FINAL - I, 2)
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(mixed), "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g}


def main(render=True):
    prep()
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    L = [l["text"] for l in S["final"]["lines"]]
    segs, dur, win, O = windows(S)
    steps, _ = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    pages = [s["t0"] for s in steps if s["new_cut"]] + [dur]
    print("dur", dur, "pages", pages, "orig windows", win)
    M, cuts, audit = build_cuts(S, steps, pages, win, dur)
    (R / "검사_같은소스컷.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    for a_ in audit:
        print("  [컷 연속]", a_)
    shots, tl, aud = [], [], []
    for p in range(len(pages) - 1):
        a, b = pages[p], pages[p + 1]
        cc = [(x, s, e) for x, s, e in cuts if a - 1e-6 <= s < b - 1e-6]
        shots.append({"i": p, "full": True, "kind": "원본재편집", "src": cc[0][0]["src"], "ss": cc[0][0]["ss"], "src_crop": cc[0][0]["src_crop"],
                      "cuts": [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": round(e - s, 3), "plan_i": x["i"]} for x, s, e in cc],
                      "t_final": [round(a, 3), round(b, 3)]})
    for x, s, e in cuts:
        tl.append([round(s, 3), round(e, 3)])
        snd = {"i": len(aud), "src": x["src"], "ss": x["ss"], "plan_i": x["i"], "t_final": [round(s, 3), round(e, 3)]}
        if x.get("mute") or not x.get("audio_src"):
            snd["mute"] = True
        else:
            snd["audio_src"] = VOICE if x["audio_src"] == "ive_8o3M3DmY05E.mp4" else x["audio_src"]
            snd["audio_ss"] = x["audio_ss"]
        aud.append(snd)
    (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py 3판 — 자막 페이지 2개 × shots[].cuts", "cand_dir": M["cand_dir"], "shots": shots},
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"], "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    ev, nxt = [], [pages[1], dur]
    for k, o in enumerate(O):
        cs = [c for c in S["captions_plan"] if c["kind"] == "원음" and o["t_final"][0] - 1e-6 <= c["t0"] < o["t_final"][1] - 1e-6]
        for j, c in enumerate(cs):
            a = win[k][0] + (c["t0"] - o["t_final"][0])
            b = nxt[k] if j == len(cs) - 1 else win[k][0] + (c["t1"] - o["t_final"][0])
            ev.append({"kind": "emph", "text": c["text"], "rgb": [255, 255, 255], "t0": round(a, 3), "dur": round(b - a, 3),
                       "basis": f"{o['id']} 원음 {o['spans']} — 받아쓰기 근거.md §2"})
        o["t_render"] = list(win[k])
    S["caption_events"] = ev
    S["render"] = {"ver": 3, "windows": [list(w) for w in win], "pages": pages, "dur": dur}
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads((ROOT / "channel/itemhome/frame_MfptnwqlGKs.json").read_text(encoding="utf-8"))
    next(l for l in fr["layers"] if l.get("role") == "title")["text"] = TITLE
    (D / "frame_1편.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in steps:
        print(f"  {s['t0']:6.2f}-{s['t1']:6.2f} {s['text']}")
    for e in ev:
        print(f"  {e['t0']:6.2f}+{e['dur']:.2f} {e['text']}")
    for x, s, e in cuts:
        print(f"  cut {s:6.2f}-{e:6.2f} {x['line']} {x['src'][:8]} ss{x['ss']} crop{x['src_crop']}")
    if not render:
        return
    plan_ = {"tteutgi": str(ROOT / "channel/itemhome/뜯기/MfptnwqlGKs/뜯기.json"), "frames": [{"frame": str(D / "frame_1편.json"), "t_end": None}],
             "script": str(D / "대본.json"), "tts": str(WAV), "materials": str(D / "재료_render.json"), "out": str(R), "bgm": None,
             "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gg = [r for w, g, b in zip(win, gains, nxt) for r in ramp(w[0], b, g)]
    ha.add_source_bed(str(final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                      1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    (R / "final.mp4").replace(R / "final_narr.mp4")
    res = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur)
    print(json.dumps(res, ensure_ascii=False))
    spans = [(0, win[0][0])] + [tuple(w) for w in win] + [(win[0][1], win[1][0]), (0, dur)]
    print(json.dumps(ha.measure(str(R / "final.mp4"), spans), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
