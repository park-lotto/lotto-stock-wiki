# -*- coding: utf-8 -*-
"""효과음·배경음악·짤·목소리 **규칙**(같은 파일 찾기 아님 — 자리·빈도·종류만, 사장님 2026-10-16).

sfx_rules     발수/초 · 자리 분포(자막 교체 직후 / 컷 직후 / 둘 다 아님, ±0.15초) · 종류 분포(제미나이 오디오 판독)
bgm_rules     있음/없음 · 분위기 태그(≤3) · 나레 중 덕킹 dB(audio.composition 값 재사용) · 시작 시각 · 끝 페이드
overlay_rules 짤·스티커·이모지·화살표: 1초 간격 프레임을 제미나이가 보고 얹힌 그림·종류·상자 → 프레임 차분으로 구간 다듬기
voice_rules   성별·역할 수·말속도·톤 한 줄
"""
from __future__ import annotations

import numpy as np

from shopping_shorts.channelkit.bench import probe, audio as baudio
from shopping_shorts.channelkit.bench.constants import SR

NEAR_S = 0.15           # "직후" = 사건 뒤 0~0.15초 (사장님 ±0.15초)
SFX_KINDS = ["띵", "휙", "펑", "웃음", "탄성", "기타"]
OVERLAY_KINDS = ["한국연예인_리액션", "해외밈_캐릭터", "해외_리액션영상", "애니·만화컷", "이모지·스티커", "글자짤", "화살표·도형", "기타"]
OV_FPS = 10             # 구간 다듬기 표본 fps
OV_PIX = 12.0           # 화소 회색 차 < 12 = 같은 화소
OV_LIFT = 0.15          # 같은 화소 비율이 바깥 기준선보다 0.15 높으면 얹힌 그림이 아직 있다(미검증)
OV_MIN = 0.3
OV_MERGE_BOX = 0.12     # 이웃 초의 상자 중심 차 < 12% = 같은 등장
HOOK_S = 3.0            # 훅 = 첫 3초
END_FRAC = 0.85         # 끝 = 편 길이 85% 이후
TRANSITION = ("근데", "그런데", "하지만", "그래서", "결국", "알고 보니", "알고보니", "그러자", "그때", "그 순간", "반전", "사실",
              "문제는", "그러니까", "드디어")
EMPHASIS = ("!", "?", "ㄷㄷ", "ㅋㅋ", "미쳤", "대박", "소름", "진짜", "인정", "ㅠ")


def _near(t: float, evs: list[float]) -> bool:
    return any(0 <= t - e <= NEAR_S or abs(t - e) <= NEAR_S for e in evs)


def sfx_rules(comp: dict, sub_changes: list[float], cuts: list[float], dur: float, asr: dict) -> dict:
    sfx = comp.get("sfx") if isinstance(comp, dict) else None
    if not sfx:
        return {"failed": (comp or {}).get("failed") or "솟음 측정 없음"}
    ts = [t for t, _ in sfx["times"]]
    pos = {"자막교체_직후": 0, "컷_직후": 0, "둘다": 0, "둘다_아님": 0}
    for t in ts:
        a, b = _near(t, sub_changes), _near(t, cuts)
        pos["둘다" if a and b else "자막교체_직후" if a else "컷_직후" if b else "둘다_아님"] += 1
    n = max(1, len(ts))
    out = {"ok": True, "per_sec": round(len(ts) / max(dur, 1e-6), 3), "count": len(ts),
           "position": {k: round(v / n, 3) for k, v in pos.items()},
           "method": f"audio_comp.spikes 시각 vs 자막 교체·컷 시각 ±{NEAR_S}s (솟음 문턱 미검증)"}
    kinds = [str(x.get("kind")) for x in (asr.get("sfx") or []) if isinstance(x, dict)]
    if kinds:
        c = {}
        for k in kinds:
            k = k if k in SFX_KINDS else "기타"
            c[k] = c.get(k, 0) + 1
        out["kinds"] = {k: round(v / len(kinds), 3) for k, v in sorted(c.items(), key=lambda kv: -kv[1])}
        out["kinds_n"] = len(kinds)
        out["kinds_method"] = "제미나이 오디오 판독(받아쓰기와 같은 호출)"
    return out


def _end_fade(path: str, dur: float) -> dict:
    x = baudio.mono(path)
    if x is None or dur < 3:
        return {"failed": "소리 없음/너무 짧음"}

    def db(a, b):
        y = x[int(a * SR):int(b * SR)]
        return float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9)) if y.size else -120.0
    last, before = db(dur - 0.5, dur), db(dur - 2.0, dur - 1.0)
    return {"fade": bool(before - last > 6.0), "last0.5s_db": round(last, 1), "prev_db": round(before, 1),
            "method": "마지막 0.5초 RMS가 끝 2~1초 전보다 6dB 넘게 낮으면 페이드(전체 섞인 소리, 미검증)"}


def bgm_rules(asr: dict, comp: dict, path: str, dur: float) -> dict:
    b = asr.get("bgm") if isinstance(asr, dict) else None
    if not isinstance(b, dict):
        return {"failed": "제미나이 배경음악 판독 없음", "end": _end_fade(path, dur)}
    duck = (comp or {}).get("duck_db")
    return {"ok": True, "present": bool(b.get("present")), "mood": [str(m) for m in (b.get("mood") or [])][:3],
            "start_s": b.get("start"), "fade_out_said": b.get("fade_out"),
            "duck_db": duck, "end": _end_fade(path, dur),
            "method": "있음·분위기·시작 = 제미나이 오디오 판독 / 덕킹 = audio.composition.duck_db 재사용 / 끝 페이드 = RMS 실측"}


def voice_rules(comp: dict, transcript: dict, asr: dict) -> dict:
    if not isinstance(comp, dict) or comp.get("failed"):
        return {"failed": (comp or {}).get("failed") or "소리 구성 없음"}
    sp = comp.get("speakers") or []
    ko = [s for s in sp if "ko" in s.get("langs", [])]
    return {"ok": True, "genders": [s["gender"] for s in ko] or [s["gender"] for s in sp],
            "roles": len(ko), "speakers_all": len(sp), "cps": (transcript or {}).get("cps"),
            "narration": comp.get("narration"), "tone": str(asr.get("voice_tone") or "") or None,
            "method": "audio.composition 화자(한국어 화자 = 역할) + 받아쓰기 cps + 제미나이 톤 한 줄"}


# ── 짤·스티커 ─────────────────────────────────────────────────────────────
OV_PROMPT = ('각 그림은 세로 숏폼 영상의 1초 간격 프레임이다(라벨에 시각). 영상 위에 **덧얹은 그림**(짤·스티커·이모지·화살표·도형·'
             '글자짤·리액션 영상 작은 창)이 있으면 적어라. 자막 띠 글자·맨 위 제목·채널 로고·원본 영상 속 물건은 빼라. '
             'kind 사전: ' + " | ".join(OVERLAY_KINDS) + ' (해외밈_캐릭터=개구리·고양이 등). '
             'box = [x,y,w,h] 화면 대비 0~1, full = 화면 전체를 덮으면 true. what = 무엇인지 짧게. 없으면 overlays 빈 목록.\n'
             'JSON만: {"items":[{"label":"프레임 3s","overlays":[{"kind":"이모지·스티커","what":"엄지 이모지","box":[0.5,0.4,0.2,0.1],"full":false}]}]}')


def _caption_at(t: float, items: list[dict]) -> str:
    for it in items:
        if it["t0"] <= t < it["t1"]:
            return " ".join(it.get("text") or [])
    return ""


def _slot(t: float, dur: float, items: list[dict]) -> str:
    if t < HOOK_S:
        return "훅"
    if t >= END_FRAC * dur:
        return "끝"
    cap = _caption_at(t, items)
    if cap.strip().startswith(TRANSITION):
        return "전환어 뒤"
    if any(e in cap for e in EMPHASIS):
        return "강조어"
    return "중간"


def _refine(path: str, W: int, H: int, box, full: bool, t0: float, t1: float, dur: float) -> tuple[float, float, str]:
    """1초 표본으로 본 구간 [t0,t1]을 ±1.5초 넓혀 10fps로 보고, 상자 안 화소 중 t0 프레임과 거의 같은(|차|<OV_PIX) 비율이
    바깥 기준선(앞뒤 1초 중앙값)+OV_LIFT 를 넘는 연속 구간. 결과는 제미나이가 본 [t0, t1] 을 항상 포함한다.
    (2026-10-16 실측: 움직이는 이모지·카운트다운은 상자 평균 차분으로는 0.1초로 줄어들었다 → 같은 화소 비율로 바꿈. 문턱 미검증)"""
    a, b = max(0.0, t0 - 1.5), min(dur, t1 + 1.5)
    if full:
        x0, y0, x1, y1 = 0, 0, W, H
    else:
        x0, y0 = int(max(0, box[0]) * W), int(max(0, box[1]) * H)
        x1, y1 = int(min(1, box[0] + box[2]) * W), int(min(1, box[1] + box[3]) * H)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return t0, min(dur, t1 + 1.0), "상자 너무 작음 — 1초 표본 구간"
    w, h = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
    fr = [f.astype(np.float32) for f in probe.frames(path, f"fps={OV_FPS},crop={w}:{h}:{x0}:{y0}", w, h, "gray", ss=a, dur=b - a)]
    if len(fr) < 5:
        return t0, min(dur, t1 + 1.0), "프레임 못 읽음 — 1초 표본 구간"
    ref_i = min(len(fr) - 1, int(round((t0 - a) * OV_FPS)))
    same = np.array([(np.abs(f - fr[ref_i]) < OV_PIX).mean() for f in fr])
    edge = np.concatenate([same[:OV_FPS], same[-OV_FPS:]])
    thr = max(OV_MIN, float(np.median(edge)) + OV_LIFT)
    i = j = ref_i
    while i > 0 and same[i - 1] >= thr:
        i -= 1
    while j < len(fr) - 1 and same[j + 1] >= thr:
        j += 1
    s0, s1 = min(t0, a + i / OV_FPS), max(t1, a + (j + 1) / OV_FPS)
    return round(s0, 2), round(s1, 2), f"상자 안 같은 화소 비율 ≥ max({OV_MIN}, 바깥중앙값+{OV_LIFT}) 연속 ∪ 1초 표본 구간({OV_FPS}fps, 미검증)"


def overlay_rules(path: str, meta: dict, cap_items: list[dict], llm, jpeg) -> dict:
    W, H, dur = meta["width"], meta["height"], meta["duration"]
    labs = []
    for s in range(int(dur)):
        img = probe.grab(path, s + 0.5, "scale=360:640", 360, 640)
        if img is not None:
            labs.append((s + 0.5, f"프레임 {s + 0.5:.1f}s", jpeg(img, 360)))
    got, errs = {}, []
    for k in range(0, len(labs), 10):
        part = []
        for _, lab, jp in labs[k:k + 10]:
            part += [lab, jp]
        d, err = llm(part, OV_PROMPT, f"ov{k // 10}")
        if err:
            errs.append(err)
            continue
        for it in (d or {}).get("items", []):
            if isinstance(it, dict) and it.get("label"):
                got[str(it["label"]).strip()] = it.get("overlays") or []
    if not got:
        return {"failed": errs[0] if errs else "답 없음", "method": "gemini_free.ask 1초 프레임"}
    seen = []   # [{kind, box, full, what, ts:[...]}]
    for t, lab, _ in labs:
        for o in got.get(lab, []):
            if not isinstance(o, dict):
                continue
            kind = o.get("kind") if o.get("kind") in OVERLAY_KINDS else "기타"
            box = o.get("box") if isinstance(o.get("box"), list) and len(o["box"]) == 4 else [0, 0, 1, 1]
            try:
                box = [float(v) for v in box]
            except (TypeError, ValueError):
                box = [0.0, 0.0, 1.0, 1.0]
            full = bool(o.get("full"))
            cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
            for e in seen:
                ex, ey = e["box"][0] + e["box"][2] / 2, e["box"][1] + e["box"][3] / 2
                if e["kind"] == kind and abs(t - e["ts"][-1]) <= 1.01 and abs(cx - ex) < OV_MERGE_BOX and abs(cy - ey) < OV_MERGE_BOX:
                    e["ts"].append(t)
                    break
            else:
                seen.append({"kind": kind, "box": box, "full": full, "what": str(o.get("what") or ""), "ts": [t]})
    apps = []
    for e in seen:
        s0, s1, how = _refine(path, W, H, e["box"], e["full"], e["ts"][0], e["ts"][-1], dur)
        apps.append({"kind": e["kind"], "what": e["what"], "t": [s0, s1], "t_pct": round(100 * s0 / dur, 1),
                     "len_s": round(s1 - s0, 2), "slot": _slot(s0, dur, cap_items), "full": e["full"],
                     "size_pct": 100.0 if e["full"] else round(100 * e["box"][2] * e["box"][3], 1),
                     "box": [round(v, 3) for v in e["box"]], "seen_at": e["ts"], "interval_method": how})
    tot = {}
    for a in apps:
        tot[a["kind"]] = tot.get(a["kind"], 0) + 1
    slots = {}
    for a in apps:
        slots[a["slot"]] = slots.get(a["slot"], 0) + 1
    n = max(1, len(apps))
    return {"ok": True, "count": len(apps), "per_min": round(len(apps) / max(dur, 1e-6) * 60, 2),
            "kind_share": {k: round(v / n, 3) for k, v in sorted(tot.items(), key=lambda kv: -kv[1])},
            "slot_share": {k: round(v / n, 3) for k, v in sorted(slots.items(), key=lambda kv: -kv[1])},
            "appearances": apps, "errors": errs,
            "method": "gemini_free.ask 1초 프레임(얹힌 그림·종류·상자) → 이웃 초 묶기 → 상자 프레임 차분으로 구간. "
                      f"자리: 훅<{HOOK_S}s / 끝≥{int(END_FRAC * 100)}% / 그 시각 자막이 전환어로 시작=전환어 뒤 / 강조 표지=강조어 / 그 밖 중간"}
