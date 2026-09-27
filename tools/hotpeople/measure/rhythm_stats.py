# -*- coding: utf-8 -*-
"""리듬·후킹 간격 실측 — 컷 시각(재계산)·자막 시각(cuts.json)·강조 위치(subs_flat.json)에서.
표본 폴더에서: PYTHONUTF8=1 py ../measure/rhythm_stats.py → rhythm.json + 콘솔
잰 것: 컷=자막 경계 일치율(±0.2s) · 첫 컷 길이 · 컷 길이 표준편차 · 최장 무변화 구간(컷·자막 교체 합침) ·
       변화 이벤트 간격 · 재후킹 간격(형광펜·빨강·숫자·따옴표 자막 등장 시각) · 자막 커버리지.
컷 검출은 cuts.py와 같은 자(슬롯 crop, scene>0.3, 0.2초 이후) — 두 곳이 다르면 안 되므로 같은 명령을 쓴다.
"""
import subprocess, json, glob, statistics as st

cuts = json.load(open("cuts.json", encoding="utf-8"))
flat = json.load(open("subs_flat.json", encoding="utf-8")) if glob.glob("subs_flat.json") else []
by_vid = {}
for s in flat:
    by_vid.setdefault(s["vid"], []).append(s)


def cut_times(f):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", "crop=1080:790:0:483,select='gt(scene,0.3)',metadata=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True).stdout
    return [float(l.split("pts_time:")[1]) for l in r.splitlines() if "pts_time:" in l and float(l.split("pts_time:")[1]) > 0.2]


out = {}
for f in sorted(glob.glob("*.mp4")):
    if f not in cuts: continue
    c = cuts[f]; dur = c["dur"]; subs = c["sub_times"]; ct = cut_times(f)
    segs = [b - a for a, b in zip([0] + ct, ct + [dur])]
    match = sum(1 for t in ct if any(abs(t - s) <= 0.2 for s in subs))
    events = sorted(set([round(t, 1) for t in ct] + [round(t, 1) for t in subs]))
    gaps = [b - a for a, b in zip([0] + events, events + [dur])]
    vid = f[:11]; ss = by_vid.get(vid, [])
    starts = [0] + subs
    hooks = sorted(starts[s["i"] - 1] for s in ss if (s.get("mark") or s.get("red") or s["num"] or s["quote"]) and s["i"] - 1 < len(starts))
    hgaps = [b - a for a, b in zip(hooks, hooks[1:])]
    out[vid] = {"dur": dur, "cuts": len(ct) + 1, "first_cut": round(segs[0], 2), "cut_std": round(st.pstdev(segs), 2),
                "cut_eq_sub": f"{match}/{len(ct)}", "cut_eq_sub_pct": round(100 * match / max(len(ct), 1)),
                "longest_still": round(max(gaps), 2), "event_gap_med": round(st.median(gaps), 2),
                "hook_n": len(hooks), "rehook_gap_med": round(st.median(hgaps), 2) if hgaps else None,
                "rehook_gap_max": round(max(hgaps), 2) if hgaps else None}
    print(vid, out[vid])
json.dump(out, open("rhythm.json", "w"), ensure_ascii=False, indent=1)
if out:
    v = list(out.values())
    print(f"\n컷=자막 일치 {st.median([x['cut_eq_sub_pct'] for x in v])}% (범위 {min(x['cut_eq_sub_pct'] for x in v)}~{max(x['cut_eq_sub_pct'] for x in v)}) · "
          f"첫 컷 중앙 {st.median([x['first_cut'] for x in v])}s · 컷 std 중앙 {st.median([x['cut_std'] for x in v])} · "
          f"최장 무변화 중앙 {st.median([x['longest_still'] for x in v])}s (최대 {max(x['longest_still'] for x in v)}) · "
          f"변화 간격 중앙 {st.median([x['event_gap_med'] for x in v])}s · "
          f"재후킹 간격 중앙 {st.median([x["rehook_gap_med"] for x in v if x["rehook_gap_med"]] or [0])}s (편당 강조 자막 {st.median([x['hook_n'] for x in v])}개)")
