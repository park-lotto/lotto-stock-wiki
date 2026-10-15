# -*- coding: utf-8 -*-
"""칼카피 대조 도구 1판 — 원본 영상과 우리 영상을 **같은 자**(bench_one.measure)로 재서 차이표·나란히 그림을 낸다.

설계: docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §6-5 · 2026-10-15-칼카피진행판-design.md §6·§8

    PYTHONUTF8=1 py tools/calcopy/engine/compare.py <원본.mp4> <우리.mp4> --out <폴더> [--layout bench|single]
                    [--asr-orig 원본받아쓰기.json --asr-ours 우리받아쓰기.json]
                    [--rules-json 원본_뜯기.json 우리_뜯기.json]

출력(폴더): 차이표.json · 차이표.md · side_by_side.jpg · verdict.json
판단 주인: ① 값 뽑기 = `_value()`, ② 값 뽑기 = `_rule_value()`, 안/밖 = `_judge()`/`_row()`, 통과/미달 = `verdict()` — 여기 한 곳.
재는 함수는 전부 bench(probe·layout·captions·cuts·audio) — 여기서 새로 재지 않는다.

차이표 두 층(사장님 10-16):
  ① 픽셀 수준(틀·자막·컷·길이) — verdict 에 들어감.
  ② 규칙 수준(효과음·배경음·짤·목소리) — 같은 파일인지가 아니라 규칙만. 표에만 남기고 verdict 제외.
     bench 에 없는 값은 --rules-json(분석기 analyze.py 의 뜯기.json 두 개)에서 읽고, 없으면 failed:미측정.
     뜯기.json 에 `rules: {<항목키>: 값}` 이 있으면 그 값이 먼저다(분석기가 직접 잰 값을 꽂는 입구).
상태: in(기준 안) · out(기준 밖) · failed:<이유>(못 잼) · 참고(설계에 기준 수치 없음)
verdict: ① 기준 항목이 전부 in 이면 "통과". 하나라도 out 이거나 failed 면 "미달"(못 잰 것을 통과로 치지 않는다).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.calcopy.engine import bench_one  # noqa: E402
from shopping_shorts.channelkit.bench import probe  # noqa: E402

# ── 기준(설계 §6 표 그대로). kind: px=절대 px · rgb=채널 최대차 · rel=원본 대비 % · canvas_h=화면 높이 대비 %
#    · eq=같아야 함 · db=절대 dB · pct=원본 대비 %
TOL = {
    "frame.window": ("px", 4, "영상 창 x,y,w,h 차 ≤ 4px"),
    "frame.bg_rgb": ("rgb", 8, "배경 RGB 채널 최대차 ≤ 8"),
    "frame.caption_band": ("px", 4, "자막 띠 y0,y1 차 ≤ 4px (틀 좌표 기준 §6-1)"),
    "frame.caption_pos": ("eq", None, "자막 자리(위/아래/안) 같음"),
    "frame.caption_ink": ("eq", None, "자막 잉크 극성 같음"),
    "cap.top_y": ("canvas_h", 6, "첫 줄 y 중앙 차 ≤ 화면 높이의 6%"),
    "cap.lines": ("eq", None, "줄 수(중앙) 같음"),
    "cap.line_w": ("rel", 6, "줄 폭 중앙 차 ≤ 6%"),
    "cap.size_px": ("rel", 6, "첫 줄 높이 중앙 차 ≤ 6%"),
    "cap.stroke": ("px", 1, "획 두께 중앙 차 ≤ 1px"),
    "cap.outline": ("eq", None, "외곽선 유무(다수) 같음 — bench는 굵기 px를 안 재고 유무만 잰다"),
    "cap.anim": ("eq", None, "등장효과 종류(최빈) 같음"),
    "cap.sub_sec": ("rel", 15, "자막당 초 중앙 차 ≤ 15%"),
    "cut.median": ("rel", 15, "컷 길이 중앙 차 ≤ 15%"),
    "cut.p90": ("rel", 15, "컷 길이 p90 차 ≤ 15%"),
    "len.duration": ("rel", 15, "길이 차 ≤ 15%"),
}

# ② 규칙 수준(사장님 10-16): 같은 파일인지 말고 규칙만. verdict 에는 넣지 않고 표에만 남긴다.
#    bench 에 없는 값은 --rules-json(분석기 뜯기.json)에서 읽고, 없으면 failed:미측정.
RULE_TOL = {
    "sfx.per_sec": ("rel", 30, "효과음 발수/초 차 ≤ 30%"),
    "sfx.after_event": ("pctp", 20, "효과음 자리(자막 교체·컷 ±0.2s) 비율 차 ≤ 20%p"),
    "bgm.present": ("eq", None, "배경음 있음/없음 같음"),
    "bgm.lufs": ("db", 1.5, "배경음 LUFS 차 ≤ 1.5dB"),
    "mix.lufs": ("db", 1.5, "통합 LUFS(믹스) 차 ≤ 1.5dB — 배경음만 뗀 값 아님"),
    "bgm.duck": ("db", 3, "덕킹 dB 차 ≤ 3dB"),
    "meme.count": ("abs", 1, "짤 편당 개수 차 ≤ 1"),
    "meme.pos": ("bucket", 1, "짤 자리(훅/중간/끝) 칸마다 개수 차 ≤ 1"),
    "voice.gender": ("eq", None, "목소리 성별 구성 같음"),
    "voice.roles": ("eq", None, "목소리 역할(화자) 수 같음"),
    "speech.cps": ("rel", 10, "말속도(글자/초) 차 ≤ 10%"),
}
ALL_TOL = {**TOL, **RULE_TOL}
HOOK_S = 3.0   # 짤 자리: 훅 = 가운데 시각 < 3초(bench audio OPEN_S 와 같은 '오프닝'), 끝 = 길이−3초 이후, 나머지 중간
EVENT_TOL_S = 0.2  # 효과음 '자막 교체·컷에 붙음' = bench CUT_SUB_TOL 과 같은 ±0.2s

# (key, 묶음, 이름, 잰 함수)
ITEMS = [
    ("frame.window", "틀", "영상 창 [x,y,w,h]", "layout.measure_video"),
    ("frame.bg_rgb", "틀", "배경 RGB", "layout.measure_video"),
    ("frame.caption_pos", "틀", "자막 자리", "layout._caption"),
    ("frame.caption_ink", "틀", "자막 잉크 극성", "layout._caption"),
    ("frame.caption_band", "틀", "자막 띠 [y0,y1)", "layout._caption"),
    ("frame.above_bands", "틀", "창 위 고정 띠 [[y0,y1)…]", "layout.measure_video(above_bands)"),
    ("frame.band_rgb", "틀", "띠 색", "-"),
    ("cap.top_y", "자막", "첫 줄 y 중앙(px)", "captions.caption_lines"),
    ("cap.lines", "자막", "줄 수 중앙", "captions.caption_lines"),
    ("cap.line_w", "자막", "줄 폭 중앙(px)", "captions.caption_lines"),
    ("cap.size_px", "자막", "첫 줄 높이 중앙(px)", "captions.glyph_style"),
    ("cap.stroke", "자막", "획 두께 중앙(px)", "captions.glyph_style"),
    ("cap.outline", "자막", "외곽선 있음(다수)", "captions.glyph_style"),
    ("cap.shadow", "자막", "그림자 있음(다수)", "captions.glyph_style"),
    ("cap.anim", "자막", "등장효과(최빈)", "captions.caption_anim"),
    ("cap.sub_sec", "자막", "자막당 초 중앙", "captions.caption_spans"),
    ("cap.count", "자막", "자막 개수", "captions.caption_changes"),
    ("cut.median", "컷", "컷 길이 중앙(초)", "cuts.shot_lengths"),
    ("cut.p90", "컷", "컷 길이 p90(초)", "cuts.shot_lengths"),
    ("cut.first", "컷", "첫 컷 시각(초)", "cuts.shot_lengths"),
    ("cut.eq_sub", "컷", "자막=컷 일치율(%)", "cuts.cut_eq_sub"),
    ("cut.shots", "컷", "샷 수", "cuts.scene_detect+merge_close+cut_verify"),
    ("audio.tp", "소리", "True Peak(dBTP)", "audio.ebur128"),
    ("len.duration", "길이", "길이(초, 프레임÷fps)", "probe.info"),
]

RULE_ITEMS = [
    ("sfx.per_sec", "효과음", "효과음 발수/초", "뜯기.json audio.composition.sfx_per_sec(audio_comp.spikes)"),
    ("sfx.after_event", "효과음", "효과음 중 자막 교체·컷 ±0.2s 비율(%)", "뜯기.json sfx 시각 × bench captions.changes+cuts"),
    ("bgm.present", "배경음", "배경음 있음", "뜯기.json rules.bgm.present"),
    ("bgm.lufs", "배경음", "배경음 LUFS", "뜯기.json rules.bgm.lufs"),
    ("mix.lufs", "배경음", "통합 LUFS(믹스)", "audio.ebur128"),
    ("bgm.duck", "배경음", "덕킹 dB(나레 구간−말 없는 구간)", "뜯기.json audio.composition.duck_db"),
    ("meme.count", "짤", "짤 개수/편", "뜯기.json materials.per_shot(kind=짤·밈)"),
    ("meme.pos", "짤", "짤 자리 {훅,중간,끝}", "뜯기.json materials.per_shot(kind=짤·밈) t 가운데"),
    ("voice.gender", "목소리", "화자 성별(정렬)", "뜯기.json audio.composition.speakers.gender"),
    ("voice.roles", "목소리", "화자 수", "뜯기.json audio.composition.speakers"),
    ("speech.cps", "목소리", "말속도(글자/초)", "compare.asr_cps(speechmatics 단어 시각)"),
]


class Fail(Exception):
    """이 항목은 못 잼 — 이유를 표에 남긴다."""


# ── 값 뽑기(측정 결과 → 항목 값). 재기는 bench 가 했다 ─────────────────────────
def _items(m):
    return [it for it in m.get("captions", {}).get("items", []) if it.get("lines", 0) > 0]


def _glyph(m):
    g = m.get("captions", {}).get("glyph", [])
    if not g:
        raise Fail("글꼴 표본 없음(" + (m["errors"].get("captions") or "glyph_style None") + ")")
    return g


def _shots(m):
    c = m.get("cuts")
    if not c or c.get("cuts") is None:
        raise Fail(m["errors"].get("cuts") or "컷 결과 없음")
    import shopping_shorts.channelkit.bench.cuts as cuts_mod
    return cuts_mod.shot_lengths(c["cuts"], m["probe"]["duration"]), c


def asr_cps(path: str) -> float:
    """speechmatics json(results[type=word]) → 글자/초 = 단어 글자 수 합 ÷ (마지막 단어 끝 − 첫 단어 시작)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    ws = [r for r in d.get("results", []) if r.get("type") == "word"]
    if not ws:
        raise Fail("받아쓰기에 단어 없음")
    chars = sum(len(r["alternatives"][0]["content"].replace(" ", "")) for r in ws)
    span = float(ws[-1]["end_time"]) - float(ws[0]["start_time"])
    if span <= 0:
        raise Fail("받아쓰기 시간 폭 0")
    return round(chars / span, 2)


def _value(key: str, m: dict, asr: str | None):
    if "probe" not in m:
        raise Fail(m["errors"].get("probe", "probe 실패"))
    vl = m.get("vl")
    if key.startswith("frame.") and key != "frame.band_rgb" and not vl:
        raise Fail(m["errors"].get("layout", "layout 실패"))
    if key == "frame.window":
        if not vl["window"]:
            raise Fail("영상 창 못 찾음")
        return list(vl["window"])
    if key == "frame.bg_rgb":
        return list(vl["bg_rgb"])
    if key == "frame.caption_pos":
        return vl["caption"].get("pos")
    if key == "frame.caption_ink":
        return vl["caption"].get("ink")
    if key == "frame.caption_band":
        if not vl["caption"].get("band"):
            raise Fail("자막 띠 못 찾음")
        return list(vl["caption"]["band"])
    if key == "frame.above_bands":
        return m.get("layout", {}).get("above_bands", [])
    if key == "frame.band_rgb":
        raise Fail("bench에 띠 색을 재는 자가 없음(layout은 창 밖 배경 RGB만 잰다)")
    if key.startswith("cap."):
        if m["errors"].get("captions") and not m.get("captions", {}).get("spans"):
            raise Fail(m["errors"]["captions"])
    if key == "cap.top_y":
        its = _items(m)
        if not its:
            raise Fail("줄 있는 자막 없음")
        return float(st.median(it["top_y"] for it in its))
    if key == "cap.lines":
        its = _items(m)
        if not its:
            raise Fail("줄 있는 자막 없음")
        return float(st.median(it["lines"] for it in its))
    if key == "cap.line_w":
        ws = [w for it in _items(m) for w in it["widths"]]
        if not ws:
            raise Fail("줄 폭 없음")
        return float(st.median(ws))
    if key == "cap.size_px":
        return float(st.median(g["line_h"] for g in _glyph(m)))
    if key == "cap.stroke":
        s = [g["stroke"] for g in _glyph(m) if g.get("stroke")]
        if not s:
            raise Fail("획 두께 None")
        return float(st.median(s))
    if key == "cap.outline":
        g = _glyph(m)
        return sum(1 for x in g if x["outline"]) * 2 > len(g)
    if key == "cap.shadow":
        g = _glyph(m)
        return sum(1 for x in g if x["shadow"]) * 2 > len(g)
    if key == "cap.anim":
        g = _glyph(m)
        return Counter(x["anim"] for x in g).most_common(1)[0][0]
    if key == "cap.sub_sec":
        sp = m["captions"]["spans"]
        if not sp:
            raise Fail("자막 구간 없음")
        return round(float(st.median(b - a for a, b in sp)), 3)
    if key == "cap.count":
        return len(m["captions"]["spans"])
    if key == "cut.median":
        s, _ = _shots(m)
        return round(float(np.median(s)), 3)
    if key == "cut.p90":
        s, _ = _shots(m)
        return round(float(np.percentile(s, 90)), 3)
    if key == "cut.first":
        s, _ = _shots(m)
        return round(float(s[0]), 3)
    if key == "cut.shots":
        s, _ = _shots(m)
        return len(s)
    if key == "cut.eq_sub":
        _, c = _shots(m)
        if not c.get("cut_eq_sub"):
            raise Fail("자막 교체 시각 없음")
        a, b = c["cut_eq_sub"]
        return round(100.0 * a / max(b, 1), 1)
    if key in ("audio.lufs", "audio.tp", "mix.lufs"):
        a = m.get("audio")
        if not a:
            raise Fail(m["errors"].get("audio", "audio 실패"))
        if not a.get("has_audio"):
            raise Fail("소리 스트림 없음")
        v = a.get("TP" if key == "audio.tp" else "I")
        if v is None:
            raise Fail("ebur128 요약 없음")
        return v
    if key == "len.duration":
        return m["probe"]["duration"]
    raise KeyError(key)


# ── ② 규칙 값(뜯기.json 에서 읽는다 — 여기서 새로 재지 않는다) ─────────────────
def _get(R: dict, path: str):
    cur = R
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            raise Fail("미측정(뜯기.json에 " + path + " 없음)")
        cur = cur[k]
    if isinstance(cur, dict) and cur.get("failed"):
        raise Fail("미측정(" + path + ": " + str(cur["failed"]) + ")")
    return cur


def _memes(R: dict) -> list[float]:
    per = _get(R, "materials.per_shot")
    if isinstance(R.get("materials"), dict) and R["materials"].get("failed"):
        raise Fail("미측정(materials: " + str(R["materials"]["failed"]) + ")")
    if any(r.get("failed") for r in per):
        raise Fail("미측정(제작법 판독 실패한 컷 있음)")
    return [(r["t"][0] + r["t"][1]) / 2 for r in per if r.get("kind") == "짤·밈"]


def _rule_value(key: str, m: dict, R: dict | None, asr: str | None):
    """R = 그 영상의 뜯기.json. R['rules'][key] 가 있으면 그 값이 먼저다(분석기가 같은 항목을 직접 잰 경우)."""
    if key == "mix.lufs":
        return _value(key, m, None)
    if key == "speech.cps":
        if not asr:
            raise Fail("미측정(받아쓰기 --asr-orig/--asr-ours 없음)")
        return asr_cps(asr)
    if R is None:
        raise Fail("미측정(--rules-json 없음)")
    if isinstance(R.get("rules"), dict) and key in R["rules"]:
        return R["rules"][key]
    if key == "sfx.per_sec":
        return _get(R, "audio.composition.sfx_per_sec")
    if key == "sfx.after_event":
        sfx = _get(R, "audio.composition.sfx")
        ts = [float(x[0]) for x in sfx.get("first", [])]
        if len(ts) != sfx.get("count"):
            raise Fail(f"미측정(효과음 시각이 {len(ts)}/{sfx.get('count')}개만 있음 — 전체 목록 필요)")
        if not ts:
            return 0.0
        ev = list(m.get("captions", {}).get("changes", [])) + list((m.get("cuts") or {}).get("cuts") or [])
        return round(100.0 * sum(1 for t in ts if any(abs(t - e) <= EVENT_TOL_S for e in ev)) / len(ts), 1)
    if key in ("bgm.present", "bgm.lufs"):
        raise Fail("미측정(bench·뜯기.json에 배경음만 뗀 값 없음 — rules." + key + " 로 넣어야 함)")
    if key == "bgm.duck":
        return _get(R, "audio.composition.duck_db")
    if key == "meme.count":
        return len(_memes(R))
    if key == "meme.pos":
        dur = m["probe"]["duration"]
        b = {"훅": 0, "중간": 0, "끝": 0}
        for t in _memes(R):
            b["훅" if t < HOOK_S else "끝" if t >= dur - HOOK_S else "중간"] += 1
        return b
    if key == "voice.gender":
        return sorted(s.get("gender", "unknown") for s in _get(R, "audio.composition.speakers"))
    if key == "voice.roles":
        return len(_get(R, "audio.composition.speakers"))
    raise KeyError(key)


# ── 안/밖 ────────────────────────────────────────────────────────────────
def _judge(key: str, a, b) -> tuple[object, str]:
    """(차, 상태). 기준 없는 항목은 '참고'."""
    if key not in ALL_TOL:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            return round(b - a, 3), "참고"
        if key == "frame.above_bands":
            return (0 if a == b else "다름"), "참고"
        return ("같음" if a == b else "다름"), "참고"
    kind, tol, _ = ALL_TOL[key]
    if kind == "abs":
        d = round(abs(b - a), 3)
        return d, ("in" if d <= tol else "out")
    if kind == "pctp":
        d = round(abs(b - a), 1)
        return f"{d}%p", ("in" if d <= tol else "out")
    if kind == "bucket":
        d = max(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b)) if (a or b) else 0
        return d, ("in" if d <= tol else "out")
    if kind == "eq":
        return ("같음" if a == b else "다름"), ("in" if a == b else "out")
    if kind in ("px", "rgb"):
        if isinstance(a, list):
            if len(a) != len(b):
                return "길이 다름", "out"
            d = max(abs(x - y) for x, y in zip(a, b))
        else:
            d = abs(b - a)
        d = round(float(d), 3)
        return d, ("in" if d <= tol else "out")
    if kind == "db":
        d = round(abs(b - a), 2)
        return d, ("in" if d <= tol else "out")
    if kind == "rel":
        if a == 0:
            d = 0.0 if b == 0 else float("inf")
        else:
            d = abs(b - a) / abs(a) * 100
        return f"{round(b - a, 3)} ({d:.1f}%)", ("in" if d <= tol else "out")
    if kind == "canvas_h":
        raise RuntimeError("canvas_h 는 _row 에서 처리")
    raise KeyError(kind)


def _row(key, grp, name, method, mo, mu, asr_o, asr_u, layer="pixel", R_o=None, R_u=None) -> dict:
    row = {"key": key, "layer": layer, "group": grp, "name": name, "method": method,
           "criterion": ALL_TOL[key][2] if key in ALL_TOL else None}
    vals = {}
    for side, m, asr, R in (("orig", mo, asr_o, R_o), ("ours", mu, asr_u, R_u)):
        try:
            vals[side] = _value(key, m, asr) if layer == "pixel" else _rule_value(key, m, R, asr)
        except Fail as e:
            vals[side] = None
            row.setdefault("fail", []).append(f"{'원본' if side == 'orig' else '우리'}: {e}")
        except Exception as e:  # noqa: BLE001 — 한 항목 실패로 표 전체를 버리지 않는다(사유는 표에 남는다)
            vals[side] = None
            row.setdefault("fail", []).append(f"{'원본' if side == 'orig' else '우리'}: {type(e).__name__}: {e}")
    row["orig"], row["ours"] = vals["orig"], vals["ours"]
    if row.get("fail"):
        row["diff"] = None
        row["status"] = "failed:" + " / ".join(row.pop("fail"))
        if key not in ALL_TOL:
            row["status"] = "참고(" + row["status"] + ")"
        return row
    a, b = vals["orig"], vals["ours"]
    if key in TOL and TOL[key][0] == "canvas_h":
        H = mo["probe"]["height"]
        d = abs(b - a) / H * 100
        row["diff"] = f"{round(b - a, 1)}px ({d:.1f}% of H{H})"
        row["status"] = "in" if d <= TOL[key][1] else "out"
        return row
    row["diff"], row["status"] = _judge(key, a, b)
    return row


def verdict(rows: list[dict]) -> dict:
    """판정은 ① 픽셀 수준만(사장님 10-16). ② 규칙 수준은 rules_* 로 따로 센다(판정에 안 들어감)."""
    crit = [r for r in rows if r["key"] in TOL]
    outs = [r["name"] for r in crit if r["status"] == "out"]
    fails = [f'{r["name"]} ({r["status"]})' for r in crit if r["status"].startswith("failed")]
    rule = [r for r in rows if r["key"] in RULE_TOL]
    return {"verdict": "통과" if not outs and not fails else "미달", "out": outs, "failed": fails,
            "n_criteria": len(crit), "n_in": sum(1 for r in crit if r["status"] == "in"),
            "rules_note": "② 규칙 수준은 판정에 넣지 않음(표에만)",
            "rules_in": [r["name"] for r in rule if r["status"] == "in"],
            "rules_out": [r["name"] for r in rule if r["status"] == "out"],
            "rules_unmeasured": [r["name"] for r in rule if r["status"].startswith("failed")]}


# ── 나란히 그림 ───────────────────────────────────────────────────────────
N_SHOTS = 8
TILE_W, TILE_H = 270, 480


def _font(size):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/malgun.ttf", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def side_by_side(mo: dict, mu: dict, out_path: str) -> dict:
    """같은 상대 시각 8지점((i+0.5)/8)의 원본(위)·우리(아래) 프레임. 잰 창(초록)·자막 띠(빨강)를 겹쳐 그린다."""
    from PIL import Image, ImageDraw
    lab = 28
    W = TILE_W * N_SHOTS
    img = Image.new("RGB", (W, lab + (TILE_H + lab) * 2), (20, 20, 20))
    dr = ImageDraw.Draw(img)
    f = _font(18)
    missing = []
    for row, (m, name) in enumerate(((mo, "원본"), (mu, "우리"))):
        y_top = lab + row * (TILE_H + lab)
        dr.text((6, y_top - lab + 4), f"{name}: {Path(m['path']).name}", fill=(255, 255, 255), font=f)
        if "probe" not in m:
            missing.append(name)
            continue
        cw, ch = m["probe"]["width"], m["probe"]["height"]
        sx, sy = TILE_W / cw, TILE_H / ch
        vl = m.get("vl") or {}
        for i in range(N_SHOTS):
            rel = (i + 0.5) / N_SHOTS
            t = rel * m["probe"]["duration"]
            fr = probe.grab(m["path"], t, f"scale={TILE_W}:{TILE_H}", TILE_W, TILE_H)
            x0 = i * TILE_W
            if fr is None:
                missing.append(f"{name}@{t:.2f}")
                continue
            img.paste(Image.fromarray(fr), (x0, y_top))
            if vl.get("window"):
                wx, wy, ww, wh = vl["window"]
                dr.rectangle([x0 + wx * sx, y_top + wy * sy, x0 + (wx + ww) * sx - 1, y_top + (wy + wh) * sy - 1],
                             outline=(0, 230, 0), width=2)
            band = (vl.get("caption") or {}).get("band")
            if band:
                dr.rectangle([x0 + 1, y_top + band[0] * sy, x0 + TILE_W - 2, y_top + band[1] * sy],
                             outline=(255, 40, 40), width=2)
            dr.text((x0 + 4, y_top + 4), f"{rel * 100:.0f}% {t:.1f}s", fill=(255, 255, 0), font=_font(16),
                    stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(out_path, quality=88)
    return {"path": out_path, "rel_times": [(i + 0.5) / N_SHOTS for i in range(N_SHOTS)], "missing": missing}


# ── 표 쓰기 ───────────────────────────────────────────────────────────────
def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "있음" if v else "없음"
    if isinstance(v, float):
        return f"{v:g}"
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)


_MARK = {"in": "안", "out": "**밖**", "생략": "생략"}


def _table(rows: list[dict]) -> list[str]:
    L = ["| 묶음 | 항목 | 원본 | 우리 | 차 | 기준 | 안/밖 | 잰 함수 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        stt = _MARK.get(r["status"], r["status"])
        L.append(f"| {r['group']} | {r['name']} | {_fmt(r['orig'])} | {_fmt(r['ours'])} | {_fmt(r['diff'])} | "
                 f"{r['criterion'] or '참고(설계에 기준 수치 없음)'} | {stt} | `{r['method']}` |")
    return L


def _load_rules(p: str | None) -> dict | None:
    if not p or p == "-":
        return None
    return json.loads(Path(p).read_text(encoding="utf-8"))


def to_markdown(res: dict) -> str:
    v = res["verdict"]
    L = [f"# 칼카피 대조 차이표", "",
         f"- 원본: `{res['orig']['path']}` ({res['orig'].get('probe', {}).get('duration')}초)",
         f"- 우리: `{res['ours']['path']}` ({res['ours'].get('probe', {}).get('duration')}초)",
         f"- 자: bench_one.measure(layout_mode=`{res['layout_mode']}`) — 두 영상에 같은 함수",
         f"- 규칙 자료(뜯기.json): 원본 `{res['rules_json'][0]}` · 우리 `{res['rules_json'][1]}`",
         f"- **판정(① 픽셀 수준만): {v['verdict']}** (기준 {v['n_criteria']}개 중 안 {v['n_in']}개)",
         f"- ① 밖: {', '.join(v['out']) or '없음'}",
         f"- ① 못 잼: {', '.join(v['failed']) or '없음'}",
         f"- ② 규칙 수준(판정 제외): 안 {len(v['rules_in'])}개 · 밖 {', '.join(v['rules_out']) or '없음'} · "
         f"미측정 {len(v['rules_unmeasured'])}개", "",
         "## ① 픽셀 수준 (판정에 들어감)", ""]
    L += _table([r for r in res["rows"] if r["layer"] == "pixel"])
    L += ["", "## ② 규칙 수준 (같은 파일인지가 아니라 규칙만 — 판정 제외, 표에만)", ""]
    L += _table([r for r in res["rows"] if r["layer"] == "rule"])
    errs = {k: res[k]["errors"] for k in ("orig", "ours") if res[k]["errors"]}
    if errs:
        L += ["", "## 측정 단계 오류", "", "```", json.dumps(errs, ensure_ascii=False, indent=1), "```"]
    L += ["", f"나란히 그림: `{res['side_by_side']['path']}` (위=원본·아래=우리, 같은 상대 시각 8지점, 초록=잰 영상 창·빨강=잰 자막 띠)"]
    return "\n".join(L) + "\n"


def compare(orig: str, ours: str, out_dir: str, layout_mode: str = "bench",
            asr_orig: str | None = None, asr_ours: str | None = None, picture: bool = True,
            rules_orig: str | None = None, rules_ours: str | None = None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    mo = bench_one.measure(orig, layout_mode=layout_mode)
    mu = bench_one.measure(ours, layout_mode=layout_mode)
    R_o, R_u = _load_rules(rules_orig), _load_rules(rules_ours)
    rows = [_row(k, g, n, meth, mo, mu, asr_orig, asr_ours) for k, g, n, meth in ITEMS]
    rows += [_row(k, g, n, meth, mo, mu, asr_orig, asr_ours, "rule", R_o, R_u) for k, g, n, meth in RULE_ITEMS]
    v = verdict(rows)
    sbs = side_by_side(mo, mu, os.path.join(out_dir, "side_by_side.jpg")) if picture else {"path": None}
    slim = lambda m: {"path": m["path"], "probe": m.get("probe"), "vl": m.get("vl"), "errors": m["errors"],  # noqa: E731
                      "layout_method": m.get("layout_method")}
    res = {"tool": "tools/calcopy/engine/compare.py", "layout_mode": layout_mode, "orig": slim(mo), "ours": slim(mu),
           "rows": rows, "verdict": v, "side_by_side": sbs,
           "rules_json": [rules_orig, rules_ours], "criteria": {k: t[2] for k, t in TOL.items()},
           "rule_criteria": {k: t[2] for k, t in RULE_TOL.items()}}
    with open(os.path.join(out_dir, "차이표.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(out_dir, "차이표.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(res))
    with open(os.path.join(out_dir, "verdict.json"), "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="칼카피 대조: 원본 vs 우리, 같은 자로 차이표")
    ap.add_argument("orig")
    ap.add_argument("ours")
    ap.add_argument("--out", required=True)
    ap.add_argument("--layout", default="bench", choices=["bench", "single"],
                    help="bench=bench.run 흐름 그대로(기본) / single=layout1 편 하나 감싸개")
    ap.add_argument("--asr-orig")
    ap.add_argument("--asr-ours")
    ap.add_argument("--rules-json", nargs=2, metavar=("원본_뜯기.json", "우리_뜯기.json"), default=[None, None],
                    help="② 규칙 수준 값(분석기 analyze.py 의 뜯기.json 두 개). 한쪽이 없으면 '-'")
    a = ap.parse_args(argv)
    res = compare(a.orig, a.ours, a.out, a.layout, a.asr_orig, a.asr_ours,
                  rules_orig=a.rules_json[0], rules_ours=a.rules_json[1])
    v = res["verdict"]
    print(f"판정(① 픽셀): {v['verdict']} (기준 {v['n_criteria']} 중 안 {v['n_in']})")
    print("① 밖:", ", ".join(v["out"]) or "없음")
    print("① 못 잼:", ", ".join(v["failed"]) or "없음")
    print(f"② 규칙(판정 제외): 안 {len(v['rules_in'])} · 밖 {', '.join(v['rules_out']) or '없음'} · "
          f"미측정 {len(v['rules_unmeasured'])}")
    print("출력:", os.path.abspath(a.out))
    return 0 if v["verdict"] == "통과" else 1


if __name__ == "__main__":
    sys.exit(main())
