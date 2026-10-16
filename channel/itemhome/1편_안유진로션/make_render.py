# -*- coding: utf-8 -*-
"""아이템홈 1편(안유진 로션) 렌더 감싸기 — 엔진 코드는 안 고친다(관제 097, 2026-10-17).

흐름: narr_gapped.wav(문정 1회 → atempo 1.10 → gap_tts) 의 말 구간으로 원음 창 3개 시각을 정함
  → 재료.json(계획 23컷)을 자막 페이지 3개(shots[].cuts)로 묶은 재료_render.json
  → 대본.json caption_events(원음 “ ” 자막) 시각을 실제 창에 맞춤
  → narr_video.build(line_asr=False) → final.mp4(나레+BGM)
  → hottem_audio.add_source_bed(소리 시간표 = 컷별 원음/무음, audio_timeline.json) → final_src.mp4 → render/final.mp4
★엔진과 다르게 한 것(보고 대상):
  1) line_asr=False — 받아쓰기 줄 정렬이 무음 끼운 나레에서 줄 1 을 4.70초(실제 7.22)로 잡음(제미나이 구절 시각이 무음을 무시). plan 옵션으로 끔.
  2) 원음 소리 시간표를 페이지(3개)가 아니라 원음 조각 단위로 따로 넘김 — cut_plan_from 이 페이지당 소리 1개(audio_ss 1개)라
     '나레 구간 원음 끔 + 원음 쉼 잘라 붙이기'를 못 한다. 같은 함수(add_source_bed→source_audio_bed)에 시간표 파일만 따로 준다.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv, hottem_audio as ha  # noqa: E402

D = Path(__file__).resolve().parent
R = Path("C:/숏템_칼카피/itemhome/1편_안유진로션/render")
WAV = R / "narr_gapped.wav"
LEAD = 0.08            # 나레 말 끝 → 원음 시작
LUFS = -13.8           # 채널 규칙표 중앙
BGM, BGM_RATIO = "sweets", 0.15
GAINS = [14.5, 14.0, 20.0]   # 2판 실측 원음 창 −14.0/−14.2/−15.0 · 전체 −14.2 · 최고 −1.0 dBFS
TITLE = "안유진이 호텔에서 꺼낸\n묘하게 중독되는 로션"


def windows():
    segs, dur = nv.speech_segments(str(WAV))
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    O = S["final"]["orig_audio"]
    # 말 구간: [N1 앞, N1 뒤] [N2] [N3] — 줄 끝 = 다음 원음 창 시작
    ends = [segs[1][1], segs[2][1], segs[3][1]]
    starts = [0.0, segs[2][0], segs[3][0]]
    win = [(round(ends[k] + LEAD, 3), round(ends[k] + LEAD + O[k]["dur"], 3)) for k in range(3)]
    return segs, dur, starts, win, S, O


def main(render=True):
    segs, dur, starts, win, S, O = windows()
    L = [l["text"] for l in S["final"]["lines"]]
    steps, _ = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
    pages = [s["t0"] for s in steps if s["new_cut"]] + [dur]
    print("dur", dur, "pages", pages, "orig windows", win)
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    by = {}
    for sh in M["shots"]:
        by.setdefault(sh["line"], []).append(sh)
    # 나레 컷 = 그 줄 자막 조각 시각에 맞춰(조각 수와 컷 수가 같으면 조각 경계, 아니면 계획 길이 비례)
    def narr_cuts(bid, a, b, li):
        sh = by[bid]
        ch = [s["t0"] for s in steps if s["line"] == li] + [b]
        if len(ch) - 1 > len(sh):   # 조각이 컷보다 많으면 앞 조각 경계에 컷을 맞춘다(N2) — 같거나 적으면 계획 길이 비례(N1: 0.3초 조각 컷 방지)
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
    plan = [("N1", 0, 0.0, win[0][0]), ("O1", None, win[0][0], pages[1]),
            ("N2", 1, pages[1], win[1][0]), ("O2", None, win[1][0], pages[2]),
            ("N3", 2, pages[2], win[2][0]), ("O3", None, win[2][0], dur)]
    cuts = []
    for bid, li, a, b in plan:
        cuts += narr_cuts(bid, a, b, li) if li is not None else orig_cuts(bid, a, b)
    # 페이지 = 자막 새 문장(3개) — 컷은 shots[].cuts
    shots, tl, aud = [], [], []
    for p in range(3):
        a, b = pages[p], pages[p + 1]
        cc = [(x, s, e) for x, s, e in cuts if s >= a - 1e-6 and s < b - 1e-6]
        shots.append({"i": p, "full": True, "kind": "원본재편집", "src": cc[0][0]["src"], "ss": cc[0][0]["ss"], "src_crop": cc[0][0]["src_crop"],
                      "cuts": [{"src": x["src"], "ss": x["ss"], "src_crop": x["src_crop"], "dur": round(e - s, 3), "plan_i": x["i"]} for x, s, e in cc],
                      "t_final": [round(a, 3), round(b, 3)]})
    for x, s, e in cuts:
        tl.append([round(s, 3), round(e, 3)])
        snd = {"i": len(aud), "src": x["src"], "ss": x["ss"], "plan_i": x["i"], "t_final": [round(s, 3), round(e, 3)]}
        if x.get("mute") or not x.get("audio_src"):
            snd["mute"] = True
        else:
            snd["audio_src"] = x["audio_src"]; snd["audio_ss"] = x["audio_ss"]
        aud.append(snd)
    MR = {"_note": "make_render.py 가 재료.json(계획 23컷)에서 만든 렌더용 — 자막 페이지 3개 × shots[].cuts", "cand_dir": M["cand_dir"], "shots": shots}
    (D / "재료_render.json").write_text(json.dumps(MR, ensure_ascii=False, indent=1), encoding="utf-8")
    AT = {"shots": tl, "dur": dur, "_note": "원음 소리 시간표(컷 단위) — add_source_bed 에 timeline 으로 넘김"}
    AM = {"cand_dir": M["cand_dir"], "shots": aud}
    (R / "audio_timeline.json").write_text(json.dumps(AT, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps(AM, ensure_ascii=False, indent=1), encoding="utf-8")
    # 원음 자막(“ ”) — 원음 창 안 상대 시각(계획) → 실제, 마지막 조각은 다음 나레 시작(페이지)까지
    ev = []
    nxt = [pages[1], pages[2], dur]
    for k, o in enumerate(O):
        cs = [c for c in S["captions_plan"] if c["kind"] == "원음" and o["t_final"][0] - 1e-6 <= c["t0"] < o["t_final"][1] - 1e-6]
        for j, c in enumerate(cs):
            a = win[k][0] + (c["t0"] - o["t_final"][0])
            b = nxt[k] if j == len(cs) - 1 else win[k][0] + (c["t1"] - o["t_final"][0])
            ev.append({"kind": "emph", "text": c["text"], "rgb": [255, 255, 255], "t0": round(a, 3), "dur": round(b - a, 3),
                       "basis": f"{o['id']} 원음 {o['spans']} — 받아쓰기 근거.md §2"})
        o["t_render"] = list(win[k])
    S["caption_events"] = ev
    S.setdefault("render", {})["windows"] = [list(w) for w in win]
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    fr = json.loads((ROOT / "channel/itemhome/frame_MfptnwqlGKs.json").read_text(encoding="utf-8"))
    next(l for l in fr["layers"] if l.get("role") == "title")["text"] = TITLE
    (D / "frame_1편.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in steps:
        print(f"  {s['t0']:6.2f}-{s['t1']:6.2f} {s['text']}")
    for e in ev:
        print(f"  {e['t0']:6.2f}+{e['dur']:.2f} {e['text']}")
    if not render:
        return
    plan_ = {"tteutgi": str(ROOT / "channel/itemhome/뜯기/MfptnwqlGKs/뜯기.json"), "frames": [{"frame": str(D / "frame_1편.json"), "t_end": None}],
             "script": str(D / "대본.json"), "tts": str(WAV), "materials": str(D / "재료_render.json"), "out": str(R), "bgm": BGM,
             "bgm_ratio": BGM_RATIO, "lufs": LUFS, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    final = nv.build(plan_)
    # 원음 창마다 올림(dB) — IVE 원본이 조용함(실측 O1 −28.0·O2 −26.2·O3 −34.0 LUFS, 1판 gain 0 완성본 −26.1/−25.5/−29.6) → 나레 −13.8 근처로
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gg = [[w[0], min(w[1] + 0.1, dur), g] for w, g in zip(win, gains)]
    res = ha.add_source_bed(str(final), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                            1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    print(json.dumps(res, ensure_ascii=False))
    spans = [(0, win[0][0])] + [tuple(w) for w in win] + [(win[0][1], win[1][0]), (win[1][1], win[2][0]), (0, dur)]
    print(json.dumps(ha.measure(str(R / "final_src.mp4"), spans), ensure_ascii=False))
    # 이름 정리: 나레+BGM 만 = final_narr.mp4 · 원음까지 = final.mp4(완성본)
    shutil.move(str(R / "final.mp4"), str(R / "final_narr.mp4"))
    shutil.move(str(R / "final_src.mp4"), str(R / "final.mp4"))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
