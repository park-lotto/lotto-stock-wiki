# -*- coding: utf-8 -*-
"""구절 맞춤을 켠 칸의 **컷 경계가 자막 구절 경계와 1:1로 맞는가** — 컷 리듬을 넣기 전과 같은지 대조한다
(2026-09-24 사장님 "경계 나누기도 잘 맞는지 예전같이 그것도 확인해").

  py tools/seed_analyzer/phrase_boundary_check.py --job <job.json>     # {"plan":..., "src":...}

무엇을 재나
  ① 켬: 컷 경계(누적 out_dur)가 자막 구절 시작 시각과 같은가 (허용 0.02초)
  ② 컷 수 = 구절 수인가
  ③ 예전과 같은가: 컷 리듬 표식을 **뗀** 같은 칸(= 리듬 도입 전 코드가 보던 상태)과 컷 목록이 일치하는가
  ④ 끔: 리듬 규칙(홀드 한 컷 / 조각 한 번씩)으로 돌아가는가
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.environ.get("LSW_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def _phrase_bounds(beat, tts):
    """자막 구절 경계(초) — ★서버 _plan_phrase_clips와 **같은 함수 조합**으로 만든다(0순위-B).
    전엔 저장된 cap_durs를 그대로 누적해 재다가 0.02~0.04초 어긋남이 났다. 서버는 tts에 맞춰
    다시 계산한 값(_caption_durations)과 트림 보정(_adjust_caps_for_trim)을 쓴다 —
    잣대가 다르면 멀쩡한 코드를 틀렸다고 말한다(검사 도구가 헛것을 재는 꼴)."""
    from shopping_shorts import video_assemble as va
    caps = va._caption_segments(beat.get("narration") or "", beat.get("caption_lines"))
    if not caps or tts <= 0.1:
        return []
    lead, rd = va._adjust_caps_for_trim(beat)
    durs = va._caption_durations(caps, tts, real_durs=rd)
    if not durs:
        return []
    out, t = [], float(lead or 0.0)
    for d in durs[:-1]:
        t += d
        out.append(min(tts, t))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    a = ap.parse_args()
    from shopping_shorts import video_assemble as va
    d = json.load(open(a.job, encoding="utf-8"))
    plan, src = d["plan"], d["src"]
    bad = 0
    for b in plan.get("beats") or []:
        tts = float(b.get("target_seconds") or 0)
        if tts <= 0:
            continue
        on = copy.deepcopy(b); on["phrase_sync"] = True
        old = copy.deepcopy(on); old.pop("cut_rhythm", None)        # 리듬 도입 전 상태
        off = copy.deepcopy(b); off["phrase_sync"] = False
        c_on = va.plan_beat_clips_for(on, tts, src) or []
        c_old = va.plan_beat_clips_for(old, tts, src) or []
        c_off = va.plan_beat_clips_for(off, tts, src) or []
        bounds, t, cuts = _phrase_bounds(on, tts), 0.0, []
        for c in c_on[:-1]:
            t += float(c.get("out_dur") or 0)
            cuts.append(round(t, 3))
        gap = max((min(abs(x - y) for y in bounds) for x in cuts), default=0.0) if bounds else None
        same = ([(c["video_id"], round(c["start"], 3), round(c["out_dur"], 3)) for c in c_on]
                == [(c["video_id"], round(c["start"], 3), round(c["out_dur"], 3)) for c in c_old])
        okn = (len(c_on) == len(bounds) + 1) if bounds else None
        flag = ""
        if bounds and (gap is None or gap > 0.02):
            flag += " ✗경계어긋남"
        if not same:
            flag += " ✗예전과다름"
        if okn is False:
            flag += " ✗컷수≠구절수"
        if flag:
            bad += 1
        print("%d %-4s %.1f초 | 켬 컷 %d(구절 %d) 최대오차 %s · 예전과 %s | 끔 컷 %d%s" % (
            b.get("beat_idx", -1), b.get("role") or "", tts, len(c_on), len(bounds) + 1 if bounds else 0,
            ("%.3f초" % gap) if gap is not None else "-", "같음" if same else "다름", len(c_off), flag))
    print("어긋난 칸 %d개" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
