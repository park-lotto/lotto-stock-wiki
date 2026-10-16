# -*- coding: utf-8 -*-
"""핫템 2편(HONOR 로봇 폰) 렌더 감싸기 — 10-16 오푸스(핫템 담당). 엔진 코드는 안 고친다.

★임시 우회 2개(엔진 요청으로 보고 — 주인이 받아 주면 이 파일의 우회를 지운다):
  1) hottem_audio.sentence_breaks 가 2·3번 줄 끝을 틀리게 골랐다(11.408·13.669 — 실제 9.75·12.79, 제미나이 받아쓰기로 확인).
     → 확인한 줄 끝 BR 로 gap_tts 를 돌린다(narr_gapped.wav 는 이미 만듦 — 여기선 다시 안 만든다).
  2) narr_video.time_steps 가 글자 비례라 줄 시작이 실제 말보다 0.46~0.75초 늦게 잡혔다(자막·컷 늦음).
     → 줄 시작을 '줄 끝 쉼 다음 첫 말 구간'에 고정하고, 줄 안에서만 글자 비례(같은 snap 0.4)로 나눈다.
흐름: 시각 계산 → 재료.json·대본.json 시각 갱신 → narr_video.build → hottem_audio.add_source_bed → final_src.mp4
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv, hottem_audio as ha  # noqa: E402

D = Path(__file__).resolve().parent
MK = Path("C:/숏템_칼카피/hottemreport/칼카피_로봇폰/make")
WAV = MK / "narr_gapped.wav"
BR = [3.455, 7.112, 9.75, 12.79, 17.046, 21.814]      # 원 TTS(narr_full.mp3) 줄 끝 쉼 가운데 — 받아쓰기로 확인
GAPS = {0: 3.0, 3: 4.5}                                # 줄 번호 뒤 무음(초)
END = 1.0


def line_starts(segs):
    """줄 k(≥1) 시작 = (줄 k-1 끝 + 앞에 끼운 무음) 다음 첫 말 구간 시작."""
    out, shift = [0.0], 0.0
    for k, b in enumerate(BR):
        shift += GAPS.get(k, 0.0)
        t = b + shift
        out.append(next(a for a, _ in segs if a >= t - 1e-3))
    return out


def time_steps_lines(steps, audio, snap=0.4, _lines=None):
    segs, dur = nv.speech_segments(audio)
    W = line_starts(segs)
    sent_line = [li for li, l in enumerate(_lines) for x in re.split(r"(?<=[?.!])\s+", l.strip()) if x]
    out = []
    for li in range(len(_lines)):
        st = [s for s in steps if sent_line[s["sent"]] == li]
        ws, we = W[li], (W[li + 1] if li + 1 < len(W) else dur)
        loc = [(max(a, ws), min(b, we)) for a, b in segs if b > ws and a < we]
        tot_sp = sum(b - a for a, b in loc)
        tot_ch = sum(s["chars"] for s in st)
        c, starts = 0, []
        for s in st:
            x = c / tot_ch * tot_sp
            t = loc[-1][1]
            for a, b in loc:
                if x <= b - a:
                    t = a + x
                    break
                x -= b - a
            near = min((a for a, _ in loc), key=lambda a: abs(a - t))
            starts.append(near if abs(near - t) <= snap else t)
            c += s["chars"]
        starts[0] = 0.0 if li == 0 else ws
        for i in range(1, len(starts)):
            starts[i] = max(starts[i], starts[i - 1] + 0.3)
        out += [dict(s, t0=round(t, 3)) for s, t in zip(st, starts)]
    for i, s in enumerate(out):
        s["t1"] = round(out[i + 1]["t0"] if i + 1 < len(out) else dur, 3)
    return out, dur


def main(render=True):
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    lines = [l["text"] for l in S["final"]["lines"]]
    steps, dur = time_steps_lines(nv.steps_of(lines, 10, "replace"), str(WAV), _lines=lines)
    cuts = sorted(set([0.0] + [s["t0"] for s in steps if s["new_cut"]])) + [dur]
    shots_t = [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a > 0.05]
    g1 = (round(BR[0] + 0, 3), round(BR[0] + GAPS[0], 3))
    g2s = BR[3] + GAPS[0]
    g2 = (round(g2s, 3), round(g2s + GAPS[3], 3))
    gend = (round(dur - END, 3), round(dur, 3))
    sh = M["shots"]
    a1, a4 = shots_t[1][0], shots_t[4][0]
    sh[1]["ss"] = round(5.6 - (g1[0] - a1), 3); sh[1]["audio_ss"] = sh[1]["ss"]
    sh[4]["ss"] = round(18.5 - (g2[0] - a4), 3); sh[4]["audio_ss"] = 18.5   # 페이블 10-16: 이 컷 소리는 노래부터 통째
    sh[1]["overlays"][0]["t"] = [round(g1[0] - a1 + 0.3, 2), round(g1[0] - a1 + 1.7, 2)]
    sh[4]["overlays"][0]["t"] = [round(g2[0] - a4 + 0.4, 2), round(g2[0] - a4 + 1.9, 2)]
    for k, (a, b) in enumerate(shots_t):
        sh[k]["t_final"] = [round(a, 3), round(b, 3)]
        sh[k]["src_span"] = [round(float(sh[k]["ss"]), 2), round(float(sh[k]["ss"]) + b - a, 2)]
    M["sfx"][0]["t"] = round(g1[0] + 0.3, 2); M["sfx"][0]["why"] = "😲 등장(원음1 시작 +0.3)"
    M["sfx"][1]["t"] = round(g2[0] + 0.4, 2); M["sfx"][1]["why"] = "🕺 등장(원음2 시작 +0.4)"
    M["sfx"][2]["t"] = round(shots_t[6][0], 2); M["sfx"][2]["why"] = "반전 줄 시작(컷6)"
    M.pop("timing_est", None)
    M["timing"] = {"tts": f"{MK / 'narr_full.mp3'} (필재 tc_68257f68bc6e3c161ab5078d · 템포 1.24 · 184자 · 24.637초 · 10-16 1회, 쉼표 뺀 원문)",
                   "narr_gapped": f"{WAV} {dur}초 — 줄 끝 BR {BR}(받아쓰기 확인) 중 0번 줄 뒤 3.0 · 3번 줄 뒤 4.5 · 끝 1.0",
                   "shots": [list(x) for x in shots_t], "gaps": [list(g1), list(g2), list(gend)],
                   "how": "make_render.time_steps_lines(줄 시작 고정 + 줄 안 글자 비례) — narr_video.build 에 같은 함수로 넘김"}
    ev = S["caption_events"]
    # 강조 자막은 다음 줄 첫 조각까지 유지(1판: gap 끝~다음 말 시작 0.17·0.35초에 앞 줄 마지막 조각이 다시 떴다)
    nxt = lambda t: next(s["t0"] for s in steps if s["t0"] >= t - 1e-3)
    ev[0]["t0"], ev[0]["dur"] = g1[0], round(nxt(g1[1]) - g1[0], 3)
    ev[1]["t0"], ev[1]["dur"] = g2[0], round(nxt(g2[1]) - g2[0], 3)
    ev[2]["t0"], ev[2]["dur"] = gend[0], END
    for e in ev:
        e.pop("est", None)
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print("dur", dur, "gaps", g1, g2, gend)
    for s in steps:
        print(f"  {s['t0']:6.2f} {s['text']}")
    for k, s in enumerate(sh):
        print(k, s["src"], s["t_final"], s["src_span"], s.get("audio_ss"))
    if not render:
        return
    nv.time_steps = lambda st, audio, snap=0.4: time_steps_lines(st, audio, snap, _lines=lines)   # 우회 2
    plan = {"tteutgi": str(ROOT / "channel/hottemreport/칼카피_OE11/뜯기2/뜯기.json"),
            "frames": [{"frame": str(D / "frame_로봇폰.json"), "t_end": None}], "script": str(D / "대본.json"), "tts": str(WAV),
            "materials": str(D / "재료.json"), "out": str(MK), "bgm": "passo_bem_solto", "bgm_ratio": 0.15, "lufs": -15.3,
            "chunk": 10, "caption_mode": "replace"}
    final = nv.build(plan)
    print("final", final)
    gg = [[g1[0], g1[1], 9.0], [g2[0], g2[1], 7.5]]   # 원음 구간만 올림(1판 실측 −22.2/−21.9 LUFS → OE11 −16.7/−18.1 근방)
    res = ha.add_source_bed(str(MK / "final.mp4"), str(MK / "timeline.json"), str(D / "재료.json"), str(WAV),
                            str(MK / "final_src.mp4"), 1.0, 10.0, work=str(MK / "srcbed"), gap_gain=gg)
    print(json.dumps(res, ensure_ascii=False))
    print(json.dumps(ha.measure(str(MK / "final_src.mp4"), [(0, g1[0]), g1, (g1[1], g2[0]), g2, (g2[1], gend[0]), (0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv)
