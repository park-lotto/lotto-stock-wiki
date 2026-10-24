# -*- coding: utf-8 -*-
"""업그레이드 자 — "벤치보다 낫다"를 측정값으로 (관제 263 지시서 05, 2026-10-25 · 표준 §4-2 · 지침서 §2-6-1).

    PYTHONUTF8=1 py tools/calcopy/engine/upgrade_table.py <업그레이드판> <doc_dir> <work_dir> [--axes cap_look,cut_rhythm,…] [--fit] [--no-write]

업그레이드 판(`base` 로 1차 판 상속)의 `upgrades:[{axis,what,why,source,expect,verify}]` 항목마다 벤치 vs 우리 측정 셋을 내고
`<doc>/업그레이드_측정.json {items:[{axis,what,bench,ours,better,why}], better_n, human_n, unmeasured_n, total, gates:{upgrade}}` 로 쓴다.
판에 `upgrades` 칸이 없고 `_diff`(옛 변형판 꼴, 예 연예인레시피판)만 있으면 `_diff` 칸을 upgrades 꼴로 바꿔 읽는다(판 파일은 안 고친다).

판단 주인: '나아짐' 판정 = 이 파일 BETTER(축마다 한 줄). 측정은 **새로 재지 않고 기존 주인 함수를 부른다** — 벤치·우리 같은 함수:
  장면↔대사 = 루브릭 자 하나(scene_fit.RUBRIC_V, 표준 §11-4 ㉕) — 벤치 = fit_target(판 targets.scene_fit > channel/<slug>/_kal/상위편_목표.json) · 우리 = <doc>/장면대사.json(scene_fit.measure_render). 자 어긋나면 ✗. 줄판독 눈 fit 은 안 씀
  정지 = quality_gate.freezes(우리 완성본 · 벤치 원본 — 같은 함수·같은 문턱)
  효과 밀도 = kal_analyze._stats(벤치 상위 편 편마다) · kal_analyze.match_from_render(우리, media=False) → 같은 칸(sfx.rate·transition.rate·sticker.rate·meme.rate·fx.rate.나레)
  훅 = kal_analyze.scene_cuts(첫 컷 — 벤치 원본·우리 완성본) · kal_analyze.frame0_kind(줄판독) / 썸네일 표식(관문 0초 측정)
  소리 = hybrid.common.lufs · kal_analyze.bench_media_cached(벤치 LUFS) · 받아쓰기 = <doc>/품질관문.json '나레 받아쓰기 ↔ 대본'(quality_gate 가 check_line_sync 로 잰 것)
  말속도·쉼 = 나레 TTS 줄 자/초 변동계수(⑲ 줄 단위 — 우리 render_info.line_cps, 목표 판 targets.speech.cps_cv > 상위편_목표.json speech, 식 script_audit._cv) · 쉼 = <doc>/품질관문.json 'B18 쉼'
  자막 가독성 = kal_analyze.frame_metrics(글자 높이·채움↔외곽 ΔE) — 벤치 원본·우리 완성본 프레임, 같은 띠
  못 재는 축(script·cap_enter·cap_exit·pointer) 또는 verify='사람 판정' = 'human'(사장님)
L3(표준 §11-2 ⑱) = l3_verdict: 측정 가능한 축 전부(MEASURABLE) 중 better_n ≥ ceil(측정 축/2) ∧ worse_n = 0 — better = 상위 편 좋은 쪽 사분위(p75/p25), worse = 상위 편 중앙보다 나쁨(밀도는 범위 밖).
'벤치 상위 편' = 조회 상위 50%(C:/숏템_칼카피/<slug>/top.json views, 없는 편은 src_dir/<id>.info.json view_count).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TABLE_VERSION = "upgrade_table:v1(2026-10-25)"
DATA = Path("C:/숏템_칼카피")
# 표준 §2-3 요소 15종 — 카드·규칙빈도·판 설정·검사 도구가 같은 글자를 쓴다(이름 밖이면 거절)
AXES15 = ("cap_look", "cap_enter", "cap_emph", "cap_exit", "transition", "cut_rhythm", "scene_fit", "bgm", "sfx", "meme",
          "sticker", "pointer", "thumb", "speech", "script")
HUMAN_AXES = ("script", "cap_enter", "cap_exit", "pointer")          # 측정 함수가 없는 축(표준 §4-2 '못 재는 칸')
DENSITY_KEY = {"sfx": "sfx.rate", "transition": "transition.rate", "sticker": "sticker.rate", "meme": "meme.rate", "cap_emph": "fx.rate.나레"}
LUFS_TARGET, LUFS_TOL = -14.0, 1.0                                   # 표준 §4-2 소리: LUFS −14±1
HOOK_SEC = 0.2                                                       # 첫 컷 = 0.2초 넘은 첫 장면 경계(맨 앞 2프레임 썸네일 카드 경계는 뺀다)


def _jl(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _num(x):
    return x if isinstance(x, (int, float)) else None


# ---------------------------------------------------------------- 판 → upgrades
_DIFF_AXIS = {"caption.pack": ("cap_look", "측정값"), "placement.rules.stickers": ("sticker", "사람 판정"), "frame.": ("cap_look", "사람 판정")}


def upgrades_of(st: dict) -> tuple[list[dict], str]:
    """판의 upgrades 목록. 없고 `_diff` 만 있으면 칸마다 upgrades 꼴로(why = _diff 글 · source = '_diff' — 근거 기록 아님)."""
    if st.get("upgrades"):
        return list(st["upgrades"]), "upgrades"
    out = []
    for k, v in (st.get("_diff") or {}).items():
        if k == "그대로":
            continue
        ax, verify = next((a for p, a in _DIFF_AXIS.items() if k.startswith(p)), ("script", "사람 판정"))
        out.append({"axis": ax, "what": k, "why": v, "source": "_diff", "expect": "", "verify": verify, "_from_diff": True})
    return out, ("_diff" if out else "없음")


def check_axes(items: list[dict]) -> None:
    bad = [(i, it.get("axis")) for i, it in enumerate(items) if it.get("axis") not in AXES15]
    if bad:
        raise ValueError(f"upgrades 축 이름이 표준 15종 밖: {bad} — 허용 {AXES15}")


def evidence_ok(it: dict) -> bool:
    """근거 기록 유무(표준 §4-2 · 지침서 §2-6-1 '무엇을→왜(수치·채널·편)→출처') — why·source 가 다 있고 출처가 _diff(겉모양 전후 글)가 아닐 것."""
    return bool(str(it.get("why") or "").strip()) and bool(str(it.get("source") or "").strip()) and it.get("source") != "_diff"


# ---------------------------------------------------------------- 벤치 쪽 모음
class Ctx:
    """한 번 읽은 것은 다시 안 읽는다(벤치 줄판독·상위 편·우리 match·캐시)."""

    def __init__(self, st: dict, doc: Path, work: Path, allow_llm: bool = False):
        from tools.calcopy.engine import kal_analyze as K
        self.K, self.st, self.doc, self.work = K, st, Path(doc), Path(work)
        self.R = self.work / "render"
        B = st.get("bench") or {}
        self.slug = B.get("channel")
        lrp = K._abs(B.get("line_reads"))
        self.bench = K._load_docs([str(lrp)]) if lrp and lrp.exists() else []
        self.src = Path(B["src_dir"]) if B.get("src_dir") else None
        self.allow_llm = allow_llm
        self._m = {}

    # 조회 상위 50%
    def views(self) -> dict:
        if "views" in self._m:
            return self._m["views"]
        v = {}
        tp = DATA / (self.slug or "_") / "top.json"
        if tp.exists():
            try:
                for r in _jl(tp):
                    if isinstance(r, dict) and r.get("id") and _num(r.get("views")) is not None:
                        v[r["id"]] = float(r["views"])
            except ValueError:
                pass
        for d in self.bench:
            i = d.get("id")
            if i and i not in v and self.src and (self.src / f"{i}.info.json").exists():
                vc = _num(_jl(self.src / f"{i}.info.json").get("view_count"))
                if vc is not None:
                    v[i] = float(vc)
        self._m["views"] = v
        return v

    def top(self) -> list[dict]:
        v = self.views()
        docs = sorted([d for d in self.bench if d.get("id") in v], key=lambda d: -v[d["id"]])
        return docs[:max(1, math.ceil(len(docs) / 2))] if docs else []

    def top_ids(self) -> list[str]:
        return [d["id"] for d in self.top()]

    def bench_win(self):
        return self.K._win_arg(None, self.bench)

    def win(self):
        return tuple((self.st.get("frame") or {}).get("window") or (0, 0, 1080, 1920))

    def final(self) -> Path:
        return self.R / "final.mp4"

    def has_final(self) -> bool:
        return self.final().exists()

    def ours_match(self) -> dict | None:
        if "match" not in self._m:
            ok = (self.R / "자막표.json").exists() and (self.R / "timeline.json").exists()
            self._m["match"] = self.K.match_from_render(self.st, self.doc, self.work, media=False) if ok else None
        return self._m["match"]

    def gate_row(self, what_prefix: str) -> dict | None:
        p = self.doc / "품질관문.json"
        if not p.exists():
            return None
        return next((r for r in _jl(p).get("rows") or [] if str(r.get("what") or "").startswith(what_prefix)), None)

    def cache(self, name: str) -> tuple[dict, Path | None]:
        if not self.src:
            return {}, None
        p = self.src / name
        try:
            return (_jl(p) if p.exists() else {}), p
        except ValueError:
            return {}, p


def _save_cache(c: dict, p: Path | None):
    if p:
        try:
            p.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass                                # 캐시를 못 써도 값은 그대로


def _key(p: Path, extra) -> str:
    return f"{p.name}|{p.stat().st_size}|{int(p.stat().st_mtime)}|{extra}"


# ---------------------------------------------------------------- 축별 측정(벤치·우리 같은 함수) → {bench, ours, better, worse, why}
# 비교 대상 = 벤치 상위 편(조회 상위 50%). better = 상위 편 '좋은 쪽 사분위'(표준 §12-2: 높을수록 좋은 칸 p75 · 낮을수록 좋은 칸 p25)에 닿음 ·
# worse = 상위 편 중앙보다 나쁨(밀도는 상위 편 범위 밖). 둘 다 아니면 '비슷함'(나아짐도 나빠짐도 아님). 표준 §11-2 ⑱.
def _q(xs, p: float):
    import numpy as np
    xs = [float(x) for x in xs if isinstance(x, (int, float))]
    return round(float(np.percentile(xs, p)), 3) if xs else None


def _top_or_all(C: "Ctx") -> tuple[list[dict], str]:
    t = C.top()
    return (t, "상위 편(조회 상위 50%)") if t else (C.bench, "전체 편(조회수 없음 — 상위 편 못 가름)")


def _miss(why: str, bench=None, ours=None) -> dict:
    return {"bench": bench, "ours": ours, "better": None, "worse": None, "why": why}


TARGET_FILE = "상위편_목표.json"      # channel/<slug>/_kal/ — 벤치 상위 편 같은 자 재측정(표준 §12-5, scene_fit.bench_measure·placement count --top)


def _rubric_ok(src) -> bool:
    from tools.calcopy.oneshot.scene_fit import RUBRIC_V
    return RUBRIC_V in json.dumps(src, ensure_ascii=False, default=str)


def fit_target(C: "Ctx") -> dict | None:
    """(판단 주인: scene_fit 축 벤치 목표, 표준 §11-4 ㉕ — 자는 루브릭 하나) 판 targets.scene_fit(07 이 상위편_목표.json 에서 복사, _from 에 RUBRIC_V)이 있으면 그 칸,
    없으면 channel/<slug>/_kal/상위편_목표.json scene_fit. 줄판독 눈 fit 은 목표로 쓰지 않는다(보조·상관 검증용). → {goal_mean, goal_below, med_mean, med_below, rubric_ok, src}"""
    t = (C.st.get("targets") or {}).get("scene_fit")
    p = ROOT / "channel" / (C.slug or "_") / "_kal" / TARGET_FILE
    sf = (_jl(p).get("scene_fit") if p.exists() else None) or None
    if t:
        mv = list(((t.get("mean") or {}).get("bench_top_values") or {}).values())
        bv = list(((t.get("below7") or {}).get("bench_top_values") or {}).values())
        rub_ok = _rubric_ok({k: t.get(k) for k in ("_from", "rubric")})
        same = bool(sf) and rub_ok and _rubric_ok(sf.get("rubric"))     # 중앙값 칸이 판에 없으면(07 복사 꼴) 같은 자의 원본 파일에서 — 자가 다르면 안 가져온다
        return {"goal_mean": (t.get("mean") or {}).get("ours_goal"), "goal_below": (t.get("below7") or {}).get("ours_goal"),
                "med_mean": _q(mv, 50) if mv else (sf.get("median_mean") if same else None),
                "med_below": _q(bv, 50) if bv else (sf.get("median_below7") if same else None),
                "rubric_ok": rub_ok, "rubric_src": t.get("_from") or t.get("rubric"), "src": "판 targets.scene_fit" + ("" if mv else f"(중앙 = {TARGET_FILE})")}
    if not sf:
        return None
    return {"goal_mean": sf.get("p75_mean"), "goal_below": sf.get("p25_below7"), "med_mean": sf.get("median_mean"), "med_below": sf.get("median_below7"),
            "rubric_ok": _rubric_ok(sf.get("rubric")), "rubric_src": sf.get("rubric"), "src": str(p.relative_to(ROOT)).replace("\\", "/")}


def m_scene_fit(C: Ctx) -> dict:
    """장면↔대사 = 루브릭 자 하나(scene_fit RUBRIC_V) — 벤치 = fit_target(판 targets > 상위편_목표.json) · 우리 = <doc>/장면대사.json(scene_fit.measure_render).
    나아짐 = 평균 ≥ 목표(p75) ∧ 7 미만 ≤ 목표(p25) · 나빠짐 = 평균 < 상위 편 중앙 ∨ 미만 > 중앙. ★자(RUBRIC_V)가 어긋나면 미측정이 아니라 ✗(㉕)."""
    from tools.calcopy.oneshot.scene_fit import RUBRIC_V
    T = fit_target(C)
    p = C.doc / "장면대사.json"
    if p.exists():
        O = _jl(p)
        ours, orub, src = O.get("summary"), O.get("rubric"), f"{p.name}(scene_fit.measure_render — 관문이 남긴 것)"
    elif C.allow_llm and C.has_final():
        from tools.calcopy.oneshot import scene_fit
        O = scene_fit.measure_render(C.work, out=p)
        ours, orub, src = O["summary"], O.get("rubric"), "scene_fit.measure_render(지금 잼)"
    else:
        ours, orub, src = None, None, "장면대사.json 없음(--fit 으로 재면 Claude 호출)"
    if not T:
        return _miss(f"미측정 — 벤치 목표 없음(판 targets.scene_fit·channel/{C.slug}/_kal/{TARGET_FILE} 둘 다 없음) · 우리 {src}", None, ours)
    bench = {k: T[k] for k in ("goal_mean", "goal_below", "med_mean", "med_below", "src", "rubric_src")}
    if not ours or ours.get("mean") is None:
        return _miss(f"미측정 — 우리 {src}", bench, ours)
    bad = [w for w, ok in ((f"벤치 목표({T['src']}) 자 {T['rubric_src']!r}", T["rubric_ok"]), (f"우리 장면대사.json 자 {orub!r}", RUBRIC_V == orub)) if not ok]
    if bad:
        return {"bench": bench, "ours": {"mean": ours["mean"], "below_rate": ours.get("below_rate"), "rubric": orub}, "better": False, "worse": True,
                "why": f"✗ 자 불일치(표준 §11-4 ㉕ — 미측정이 아니라 ✗): {' · '.join(bad)} ≠ {RUBRIC_V}"}
    if None in (T["goal_mean"], T["goal_below"], T["med_mean"], T["med_below"]):
        return _miss(f"미측정 — 벤치 목표 칸 빠짐({T['src']})", bench, ours)
    better = ours["mean"] >= T["goal_mean"] and ours["below_rate"] <= T["goal_below"]
    worse = ours["mean"] < T["med_mean"] or ours["below_rate"] > T["med_below"]
    return {"bench": bench, "ours": {"mean": ours["mean"], "below_rate": ours["below_rate"], "judged": ours.get("judged"), "rubric": orub}, "better": better, "worse": worse,
            "why": f"{RUBRIC_V} · 우리 평균 {ours['mean']}·7 미만 {ours['below_rate']} — 나아짐 = 평균 ≥{T['goal_mean']} ∧ 미만 ≤{T['goal_below']} · "
                   f"나빠짐 = 평균 <{T['med_mean']} 또는 미만 >{T['med_below']}(상위 편 중앙) · 벤치 {T['src']} · 우리 {src}"}


def m_cut_rhythm(C: Ctx) -> dict:
    """정지·멈춤 = quality_gate.freezes(창 안 같은 그림 0.3초+) — 나아짐 = 0건(표준 §4-2) · 나빠짐 = 상위 편 중앙보다 많음(벤치 없으면 1건 이상)."""
    from tools.calcopy.hybrid import quality_gate as QG
    if not C.has_final():
        return _miss("완성본 없음(미측정)")
    ours = QG.freezes(C.final(), C.win())
    docs, grp = _top_or_all(C)
    bench, cp = {}, None
    if C.src and C.bench_win():
        cache, cp = C.cache("_upgrade_freeze_cache.json")
        for d in docs:
            mp4 = C.src / f"{d.get('id')}.mp4"
            if not mp4.exists():
                continue
            k = _key(mp4, list(C.bench_win()) + [QG.FREEZE_SEC])
            if k not in cache:
                cache[k] = QG.freezes(mp4, C.bench_win())
            bench[d["id"]] = len(cache[k])
        _save_cache(cache, cp)
    med = _q(list(bench.values()), 50)
    worse = len(ours) > (med if med is not None else 0)
    return {"bench": {"group": grp, "freezes_per_doc": bench, "median": med},
            "ours": {"freezes": len(ours), "spans": ours}, "better": len(ours) == 0, "worse": worse,
            "why": f"멈춤(창 안 같은 그림 ≥{QG.FREEZE_SEC}초) 우리 {len(ours)}건 — 나아짐 = 0건 · 나빠짐 = {grp} 중앙 {med if med is not None else '(벤치 없음 → 0)'}건 초과 · 벤치 {bench or '없음'}"}


def _density_val(key: str, s: dict | None):
    if s is None:
        return None
    v = s.get(key) if isinstance(s, dict) else None
    if key == "transition.rate":                # 분포 → cut 밖 전환 비율 하나로
        return None if v is None else round(1.0 - float(v.get("cut", 0.0)), 3)
    return _num(v)


def m_density(C: Ctx, axis: str) -> dict:
    key = DENSITY_KEY[axis]
    docs, grp = _top_or_all(C)
    bv = {d["id"]: _density_val(key, C.K._stats(d.get("lines") or [], float(d.get("dur") or 0))) for d in docs}
    bv = {k: v for k, v in bv.items() if v is not None}
    M = C.ours_match()
    row = next((r for r in (M or {}).get("rows") or [] if r["key"] == key), None)
    ours = _density_val(key, {key: row["ours"]}) if row else None
    if not bv or ours is None:
        return _miss(f"미측정 — 벤치 {grp} {list(bv) or '없음'} · 우리 {'match 없음' if M is None else '칸 없음'}", bv or None, ours)
    # 판정 = 편 길이 환산 정수 개수 범위(표준 §11-3 ⑳) — 주인 placement.density_goal (지시서 15, 여기는 부르기만)
    from tools.calcopy.hybrid import placement as PL
    ball = [v for v in (_density_val(key, C.K._stats(d.get("lines") or [], float(d.get("dur") or 0))) for d in C.bench) if v is not None]
    return PL.density_axis(key, bv, ball, ours, C.R, grp)


def _first_cut(K, mp4: Path, win) -> float | None:
    ts = [t for t in K.scene_cuts(str(mp4), win) if t > HOOK_SEC]
    return round(ts[0], 2) if ts else None


def m_thumb(C: Ctx) -> dict:
    """훅 = 첫 컷 길이(scene_cuts — 벤치 원본·우리 완성본 같은 함수) + 0초 종류(card/scene). 첫 컷은 좋은 방향이 정해지지 않아 상위 편 범위 안 + 0초 같음 = 나아짐, 아니면 나빠짐.
    0초 얼굴·물건 비율은 아직 안 잰다(why 에 적음)."""
    if not C.has_final():
        return _miss("완성본 없음(미측정)")
    K = C.K
    docs, grp = _top_or_all(C)
    cache, cp = C.cache("_upgrade_firstcut_cache.json")
    bfc = {}
    for d in docs:
        mp4 = C.src / f"{d['id']}.mp4" if C.src else None
        if mp4 and mp4.exists():
            k = _key(mp4, list(C.bench_win() or []))
            if k not in cache:
                cache[k] = _first_cut(K, mp4, C.bench_win())
            if cache[k] is not None:
                bfc[d["id"]] = cache[k]
    _save_cache(cache, cp)
    from collections import Counter
    f0b = Counter(k for k in (K.frame0_kind(d) for d in docs) if k).most_common(1)
    f0b = f0b[0][0] if f0b else None
    ofc = _first_cut(K, C.final(), C.win())
    row = next((r for r in (C.ours_match() or {}).get("rows") or [] if r["key"] == "thumb.frame0"), None)
    gr = C.gate_row("썸네일 맨 앞 2프레임")
    f0o = ("card" if gr["ok"] else "scene") if gr and gr.get("ok") is not None else (row or {}).get("ours")
    if not bfc or ofc is None or not f0b or not f0o:
        return _miss("미측정 — 첫 컷·0초 종류 한쪽 없음", {"first_cut": bfc, "frame0": f0b}, {"first_cut": ofc, "frame0": f0o})
    lo, hi = min(bfc.values()), max(bfc.values())
    ok = lo - 0.05 <= ofc <= hi + 0.05 and f0o == f0b
    return {"bench": {"group": grp, "first_cut": bfc, "range": [lo, hi], "frame0": f0b}, "ours": {"first_cut": ofc, "frame0": f0o}, "better": ok, "worse": not ok,
            "why": f"첫 컷 우리 {ofc}초 vs {grp} {lo}~{hi}초(±0.05) · 0초 우리 {f0o} vs 최빈 {f0b} — 둘 다 안이면 나아짐, 아니면 나빠짐 · 0초 얼굴/물건 비율은 미측정"}


def m_bgm(C: Ctx) -> dict:
    """소리 = LUFS −14±1(hybrid.common.lufs) + 나레 받아쓰기 100%(관문 행) — 둘 다 ○ 나아짐, 하나라도 × 나빠짐(통일값·받아쓰기는 벤치와 상관없는 바닥 기준).
    벤치 LUFS 는 bench_media_cached(참고 — 벤치 원본은 −14 통일 전 값)."""
    if not C.has_final():
        return _miss("완성본 없음(미측정)")
    from tools.calcopy.hybrid.common import lufs
    I, tp = lufs(C.final())
    bl = None
    if C.src and C.bench:
        bm = C.K.bench_media_cached(str(C.src), [d.get("id") for d in C.bench], C.bench_win())
        bl = {k: v.get("lufs") for k, v in (bm.get("per") or {}).items()}
    if I is None or (isinstance(I, float) and math.isnan(I)):
        return _miss(f"LUFS 못 잼({I} — 소리 줄 없음?)", {"lufs_per_doc": bl})
    asr = C.gate_row("나레 받아쓰기")
    asr_ok = asr.get("ok") if asr else None
    lufs_ok = abs(I - LUFS_TARGET) <= LUFS_TOL
    if not lufs_ok or asr_ok is False:          # 바닥 기준 하나라도 × = 측정된 나빠짐(받아쓰기를 못 쟀어도)
        better, worse = False, True
    elif asr_ok is None:                        # LUFS 만 ○ — 받아쓰기 없이는 나아짐을 못 정한다(미측정)
        better, worse = None, None
    else:
        better, worse = True, False
    return {"bench": {"lufs_per_doc": bl}, "ours": {"lufs": I, "tp": tp, "asr_ok": asr_ok, "asr": (asr or {}).get("value")}, "better": better, "worse": worse,
            "why": f"LUFS {I}(목표 {LUFS_TARGET}±{LUFS_TOL} {'○' if lufs_ok else '×'}) · 받아쓰기 {('○' if asr_ok else '×') if asr_ok is not None else '미측정(품질관문.json 없음)'} — 둘 다 ○ 나아짐, 하나라도 × 나빠짐"}


def ours_line_cps(C: "Ctx") -> tuple[dict, str]:
    """우리 나레 TTS 줄(문장)마다 자/초(⑲ 줄 단위) — 렌더가 적은 render_info.line_cps(주인 render_itssum.line_cps, 나온 소리 기준)를 먼저,
    없으면(옛 렌더) 같은 식 = 대본 tts 글자(common.nchar) ÷ s_<줄>.wav 길이(관문 '줄별 말속도' 가 쓰던 입력)."""
    ri = C.R / "render_info.json"
    t = (_jl(ri).get("line_cps") if ri.exists() else None) or {}
    if t:
        return {k: float(v) for k, v in t.items() if isinstance(v, (int, float))}, "render_info.line_cps"
    from tools.calcopy.hybrid.common import dur_of, nchar
    S = _jl(C.doc / "대본.json") if (C.doc / "대본.json").exists() else {}
    out = {}
    for l in S.get("lines") or []:
        w = C.R / f"s_{l.get('id')}.wav"
        if l.get("kind") == "tts" and w.exists() and nchar(l.get("tts") or ""):
            d = dur_of(w)
            if d:
                out[l["id"]] = round(nchar(l["tts"]) / d, 2)
    return out, "대본 tts 글자 ÷ s_<줄>.wav(render_info.line_cps 없는 옛 렌더)"


def speech_target(C: "Ctx") -> dict | None:
    """말속도 편차 목표(TTS 줄 단위, ⑲) — 판 targets.speech.cps_cv(07) > 상위편_목표.json speech.cps_cv(15). 조각 단위 spread 는 다른 자라 안 쓴다."""
    t = ((C.st.get("targets") or {}).get("speech") or {}).get("cps_cv")
    src = "판 targets.speech.cps_cv"
    if not t:
        p = ROOT / "channel" / (C.slug or "_") / "_kal" / TARGET_FILE
        t = ((_jl(p).get("speech") or {}).get("cps_cv") if p.exists() else None)
        src = f"channel/{C.slug}/_kal/{TARGET_FILE} speech.cps_cv"
    if not t:
        return None
    vals = list((t.get("bench_top_values") or t.get("per_video") or {}).values())
    return {"goal": t.get("ours_goal") if t.get("ours_goal") is not None else t.get("p25"), "median": _q(vals, 50), "values": t.get("bench_top_values") or t.get("per_video"), "src": src}


def m_speech(C: Ctx) -> dict:
    """말속도 = 나레 TTS 줄(문장) 자/초의 변동계수(⑲ 줄 단위 — 변동계수 식은 15 의 script_audit._cv) · 낮을수록 좋음.
    나아짐 ≤ 목표(상위 편 p25) · 나빠짐 > 상위 편 중앙 · 쉼 0.22~0.30(관문 B18 행) × 면 나빠짐."""
    from tools.calcopy.hybrid.script_audit import _cv
    T = speech_target(C)
    rates, src = ours_line_cps(C)
    ocv = _cv(list(rates.values()))
    b18 = C.gate_row("B18 쉼")
    if not T or T["goal"] is None or T["median"] is None:
        return _miss(f"미측정 — 줄 단위 말속도 목표 없음(판 targets.speech.cps_cv·{TARGET_FILE} speech) · 우리 cv {ocv}", T, ocv)
    if ocv is None:
        return _miss(f"미측정 — 우리 나레 줄 자/초 3줄 미만({src})", T, rates or None)
    pause_ok = b18.get("ok") if b18 else None
    better = ocv <= T["goal"] and pause_ok is not False
    worse = ocv > T["median"] or pause_ok is False
    return {"bench": T, "ours": {"line_cps_cv": ocv, "line_cps": rates, "src": src, "pause_ok": pause_ok, "pause": (b18 or {}).get("value")},
            "better": better, "worse": worse,
            "why": f"나레 TTS 줄 자/초 변동계수 우리 {ocv}({src}) — 나아짐 ≤{T['goal']}(p25) · 나빠짐 >{T['median']}(상위 편 중앙) · 목표 {T['src']} · "
                   f"쉼 0.22~0.30 {('○' if pause_ok else '×') if pause_ok is not None else '미측정'}"}


def _grab(mp4: Path, t: float, dst: Path) -> Path | None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(dst)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    return dst if r.returncode == 0 and dst.exists() else None


def _look(K, png: Path, band) -> dict | None:
    import numpy as np
    try:
        m = K.frame_metrics(str(png), band)
    except statistics.StatisticsError:      # 옛 frame_metrics(04 수리 전)가 글자 사이 빈 칸 0개 프레임에서 median([]) — 그 프레임은 셈 밖
        return None
    if not m.get("box") or not m.get("fill_hex") or not m.get("outline_hex"):
        return None
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]   # noqa: E731
    dE = float(np.linalg.norm(K._lab(rgb(m["fill_hex"])) - K._lab(rgb(m["outline_hex"]))))
    return {"h": m["h"], "dE": round(dE, 1)}


H_TOL, DE_TOL = 4, 5.0          # kal_analyze.FRAME_PASS 폭(±4px · ΔE 5) — 이만큼 안쪽 차이는 '같음'


def m_cap_look(C: Ctx, n: int = 6) -> dict:
    """자막 가독성 = 글자 잉크 높이 h·채움↔외곽 ΔE(kal_analyze.frame_metrics) — 벤치 상위 편 원본·우리 완성본 나레 조각 가운데 프레임, 같은 띠(줄판독 layout.caption_band ±30).
    나아짐 = ΔE 또는 h 가 상위 편 p75 이상(다른 하나는 중앙−폭 안) · 나빠짐 = h 가 중앙−4px 미만 또는 ΔE 가 중앙−5 미만."""
    if not C.has_final():
        return _miss("완성본 없음(미측정)")
    K = C.K
    bands = [tuple((d.get("layout") or {}).get("caption_band") or ()) for d in C.bench]
    bands = [b for b in bands if len(b) == 2]
    if not bands:
        return _miss("벤치 줄판독 layout.caption_band 없음(미측정)")
    band = (int(statistics.median(b[0] for b in bands)) - 30, int(statistics.median(b[1] for b in bands)) + 30)
    tmp = C.work / "upgrade_look"
    tried = {"n": 0}

    def grab_set(mp4: Path, lines: list[dict], tag: str) -> list[dict]:
        out = []
        for i, l in enumerate([l for l in lines if K._sp(l.get("speaker")) == "나레" and float(l.get("t1") or 0) - float(l.get("t0") or 0) > 0.3][:n]):
            tried["n"] += 1
            p = _grab(mp4, (float(l["t0"]) + float(l["t1"])) / 2, tmp / f"{tag}_{i}.png")
            v = _look(K, p, band) if p else None
            if v:
                out.append(v)
        return out
    docs, grp = _top_or_all(C)
    b = []
    for d in docs:
        mp4 = C.src / f"{d['id']}.mp4" if C.src else None
        if mp4 and mp4.exists():
            b += grab_set(mp4, d.get("lines") or [], d["id"])
    tp = C.R / "자막표.json"
    o = grab_set(C.final(), K._ours_lines({"rows": _jl(tp).get("rows") or []})[0], "ours") if tp.exists() else []
    if not b or not o:
        return _miss(f"미측정 — 글자 못 찾음(벤치 {len(b)}·우리 {len(o)}장, 띠 {band})", b or None, o or None)
    hs, ds = [x["h"] for x in b], [x["dE"] for x in b]
    gh, gd, mh, md = _q(hs, 75), _q(ds, 75), _q(hs, 50), _q(ds, 50)
    oh, od = statistics.median(x["h"] for x in o), statistics.median(x["dE"] for x in o)
    worse = oh < mh - H_TOL or od < md - DE_TOL
    better = (od >= gd or oh >= gh) and not worse
    return {"bench": {"group": grp, "h_p75": gh, "dE_p75": gd, "h_median": mh, "dE_median": md, "n": len(b)}, "ours": {"h": oh, "dE": od, "n": len(o)},
            "better": better, "worse": worse,
            "why": f"ΔE 우리 {od} vs {grp} p75 {gd}·중앙 {md} · 높이 우리 {oh}px vs p75 {gh}·중앙 {mh}px — 나빠짐 = 높이 <중앙−{H_TOL} 또는 ΔE <중앙−{DE_TOL} "
                   f"(띠 {band}, 잰 프레임 벤치 {len(b)}장·우리 {len(o)}장 / 시도 {tried['n']}장 — 나머지는 글자 못 찾음)"}


MEASURABLE = ("scene_fit", "cut_rhythm", "thumb", "bgm", "speech", "cap_look") + tuple(DENSITY_KEY)   # L3 '측정 가능한 축'(표준 §4-2·§11-2 ⑱)


def measure_axis(C: Ctx, axis: str) -> dict:
    if axis in HUMAN_AXES:
        return {"bench": None, "ours": None, "better": "human", "worse": None, "why": f"{axis} = 측정 함수 없는 축(표준 §4-2 '못 재는 칸') — 사장님 판정"}
    if axis in DENSITY_KEY:
        return m_density(C, axis)
    return {"scene_fit": m_scene_fit, "cut_rhythm": m_cut_rhythm, "thumb": m_thumb, "bgm": m_bgm, "speech": m_speech, "cap_look": m_cap_look}[axis](C)


# 외부 주인 대기(표준 §11-5 ㉜) — 그 축의 결함을 고칠 손이 팩 주인(자막팩·모션팩·효과음팩)에게 있고 요청이 걸려 있을 때만.
# 근거 = 판 <칸>._pending.pack(칸 = 그 축의 판 칸) 또는 channel/<slug>/_kal/팩요청.md 의 '### <판>#n' 제목에 그 축 낱말. 우리 원인 축(cap_emph·sticker 등 판·placement 칸)은 목록에 없다 = 그대로 worse.
PACK_AXIS = {"cap_look": {"cells": ("caption",), "kw": ("자막 크기", "size:", "line_pitch", "줄 간격")},
             "transition": {"cells": ("cuts",), "kw": ("전환",)},
             "sfx": {"cells": ("sfx_files",), "kw": ("효과음팩", "효과음 팩")}}
PACK_REQ_FILE = "팩요청.md"


def _file_date(p: Path) -> str:
    r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(p)], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = (r.stdout or "").strip()
    return d or time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))


def pending_pack(C: "Ctx", axis: str) -> dict | None:
    """(판단 주인: 외부 팩 대기 근거) 그 축 요청이 있으면 {req, title, date, src}, 없으면 None(= 나빠짐 그대로)."""
    A = PACK_AXIS.get(axis)
    if not A:
        return None
    for cell in A["cells"]:
        pk = (((C.st.get(cell) or {}).get("_pending") or {}).get("pack")) if isinstance(C.st.get(cell), dict) else None
        if pk:
            return {"req": f"{C.st.get('name')}:{cell}._pending.pack", "title": str(pk)[:160], "date": None, "src": f"판 {cell}._pending.pack"}
    p = ROOT / "channel" / (C.slug or "_") / "_kal" / PACK_REQ_FILE
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8")
    for nm in [x for x in (C.st.get("name"), C.st.get("base")) if x]:
        m = re.search(rf"<!-- 판:{re.escape(nm)} -->(.*?)<!-- /판:{re.escape(nm)} -->", txt, re.S)
        for h in re.findall(r"^### (\S+#\d+) (.+)$", m.group(1) if m else "", re.M):
            if any(k in h[1] for k in A["kw"]):
                return {"req": h[0], "title": h[1][:160], "date": _file_date(p), "src": str(p.relative_to(ROOT)).replace("\\", "/")}
    return None


def l3_verdict(axes: dict) -> dict:
    """(판단 주인 — L3 '벤치보다 낫다', 표준 §11-2 ⑱ · §11-5 ㉜) 측정된 축(better 가 True/False) 중 better_n ≥ ceil(측정/2) ∧ worse_n = 0.
    나빠진 축에 외부 팩 대기(m['pending_pack'])가 걸려 있으면 worse_n 에서 빼고 pending 으로 센다 — 그래도 l3_ok 는 아니다(상태 'L3(팩 대기 n)').
    human·미측정은 따로 센다."""
    meas = {a: m for a, m in axes.items() if m.get("better") in (True, False)}
    better = sorted(a for a, m in meas.items() if m["better"] is True)
    bad = sorted(a for a, m in meas.items() if m.get("worse") is True)
    pending = {a: meas[a]["pending_pack"] for a in bad if meas[a].get("pending_pack")}
    worse = [a for a in bad if a not in pending]
    need = math.ceil(len(meas) / 2) if meas else 1
    core = bool(meas) and len(better) >= need and not worse
    ok = core and not pending
    state = "L3" if ok else (f"L3(팩 대기 {len(pending)})" if core else "×")
    return {"l3_ok": ok, "state": state, "better_n": len(better), "worse_n": len(worse), "pending_n": len(pending), "measured_n": len(meas), "need_better": need,
            "better_axes": better, "worse_axes": worse, "pending_pack": [{"axis": a, **v} for a, v in pending.items()],
            "human_axes": sorted(a for a, m in axes.items() if m.get("better") == "human"),
            "unmeasured_axes": sorted(a for a, m in axes.items() if m.get("better") is None),
            "rule": "better_n ≥ ceil(측정 축/2) ∧ worse_n = 0 ∧ 팩 대기 0 (비교 = 벤치 상위 편 좋은 쪽 사분위, 표준 §11-2 ⑱·§12-2 · 팩 대기 = §11-5 ㉜)"}


# ---------------------------------------------------------------- 판정 한 곳
def measure(style, doc, work, base_doc=None, base_work=None, extra_axes: tuple = (), allow_llm: bool = False, write: bool = True,
            all_axes: bool = True) -> dict:
    """(판단 주인 — 업그레이드 자) 측정 가능한 축 전부(all_axes) + 판 upgrades 항목 → <doc>/업그레이드_측정.json.
    축 판정 better: True(상위 편 좋은 쪽 사분위) / False · worse: True(상위 편 중앙보다 나쁨) · 'human'(사람 판정 — 따로 셈) · None(미측정).
    L3 = l3_verdict(축 표) — 판 upgrades 항목 축만이 아니라 측정 가능한 축 전부(나빠진 축을 숨기지 않는다).
    base_doc·base_work = 1차 판 완성본 doc·work(있으면 같은 축의 1차 값을 'first' 칸에 — 1차보다도 나아졌나 참고)."""
    from tools.calcopy.hybrid import styles as ST
    name = style if isinstance(style, str) else style.get("name")
    st = ST.load(style) if isinstance(style, str) else style
    items, src = upgrades_of(st)
    check_axes(items)
    for ax in extra_axes:
        if ax not in AXES15:
            raise ValueError(f"--axes 이름이 표준 15종 밖: {ax}")
    C = Ctx(st, doc, work, allow_llm=allow_llm)
    Cb = Ctx(ST.load(st['base']) if st.get('base') else st, base_doc, base_work, allow_llm=False) if base_doc and base_work else None
    memo: dict = {}

    def get(ax):
        if ax not in memo:
            memo[ax] = measure_axis(C, ax)
        return memo[ax]
    out = []
    for it in items:
        human = str(it.get("verify") or "").startswith("사람") or it.get("axis") in HUMAN_AXES
        m = ({"bench": None, "ours": None, "better": "human", "worse": None, "why": f"verify='{it.get('verify')}' — 사장님 판정"}
             if human and it.get("axis") not in HUMAN_AXES else get(it["axis"]))
        row = {"axis": it["axis"], "what": it.get("what"), "bench": m["bench"], "ours": m["ours"], "better": m["better"], "worse": m.get("worse"), "why": m["why"],
               "item_why": it.get("why"), "source": it.get("source"), "expect": it.get("expect"), "verify": it.get("verify"), "evidence_ok": evidence_ok(it)}
        if Cb and it["axis"] not in HUMAN_AXES and not human:
            row["first"] = measure_axis(Cb, it["axis"]).get("ours")
        out.append(row)
    want = list(dict.fromkeys((list(MEASURABLE) if all_axes else []) + [it["axis"] for it in items] + list(extra_axes)))
    axes = {a: get(a) for a in want}
    for a, m in axes.items():
        if m.get("worse") is True and m.get("better") is False:
            pp = pending_pack(C, a)
            if pp:
                m["pending_pack"] = pp
                m["why"] += f" · ★외부 팩 대기 {pp['req']}({pp['src']}{' ' + pp['date'] if pp.get('date') else ''}) — worse_n 에서 빼고 따로 셈(㉜)"
    L3 = l3_verdict(axes)
    human_n = sum(r["better"] == "human" for r in out)
    res = {"style": name, "base": st.get("base"), "table": TABLE_VERSION, "upgrades_from": src, "doc": str(doc), "work": str(work),
           "bench_ids": [d.get("id") for d in C.bench], "bench_top_ids": C.top_ids(), "views": {d.get("id"): C.views().get(d.get("id")) for d in C.bench},
           "items": out, "axes": axes,
           "better_n": L3["better_n"], "worse_n": L3["worse_n"], "measured_n": L3["measured_n"], "l3_ok": L3["l3_ok"],
           "human_n": human_n, "unmeasured_n": len(L3["unmeasured_axes"]), "total": len(out),
           "items_better_n": sum(r["better"] is True for r in out), "items_worse_n": sum(r.get("worse") is True for r in out),
           "evidence_ok_n": sum(r["evidence_ok"] for r in out), "l3": L3,
           "gates": {"upgrade": {"better": f"{L3['better_n']}/{L3['measured_n']}", "better_n": L3["better_n"], "worse_n": L3["worse_n"],
                                 "measured_n": L3["measured_n"], "l3_ok": L3["l3_ok"], "ok": L3["l3_ok"] and bool(out), "state": L3["state"],
                                 "pending_pack": L3["pending_pack"], "need_better": L3["need_better"],
                                 "human": human_n, "worse_axes": L3["worse_axes"], "total": len(out)}}}
    if write and Path(doc).exists():
        (Path(doc) / "업그레이드_측정.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def upgrade_table(st, doc, work) -> dict:
    """quality_gate.gate 가 업그레이드 판에서 찾는 이름(getattr(kal_analyze, 'upgrade_table')) 과 같은 꼴 — kal_analyze 에 잇는 한 줄은 페이블 결정(지시서 05)."""
    return measure(st, doc, work)


def table_md(r: dict) -> str:
    mark = lambda b: {True: "○", False: "×", "human": "사람", None: "미측정"}.get(b, str(b))   # noqa: E731
    L3 = r["l3"]
    L = [f"# 업그레이드 측정 {r['style']}(base {r['base']}) — {L3['state']} · 나아짐 {L3['better_n']}/{L3['measured_n']}(필요 ≥{L3['need_better']}) · 나빠짐 {L3['worse_n']} {L3['worse_axes']} · 팩 대기 {L3['pending_n']} {[x['axis'] + '=' + x['req'] for x in L3['pending_pack']]} · 사람 {r['human_n']} · 미측정 축 {L3['unmeasured_axes']}",
         f"(upgrades 출처 {r['upgrades_from']} {r['total']}건 · 근거 기록 {r['evidence_ok_n']}/{r['total']} · 벤치 상위 편 {r['bench_top_ids']})", "",
         "## 축 표(L3 판정 대상 — 측정 가능한 축 전부)", "| 축 | 벤치 | 우리 | 나아짐 | 나빠짐 | 왜 |", "|---|---|---|---|---|---|"]
    for a, x in r["axes"].items():
        L.append(f"| {a} | {json.dumps(x['bench'], ensure_ascii=False, default=str)[:90]} | {json.dumps(x['ours'], ensure_ascii=False, default=str)[:70]} | "
                 f"{mark(x['better'])} | {'나빠짐' if x.get('worse') is True else ('-' if x.get('worse') is False else '미측정')} | {x['why'][:150]} |")
    L += ["", "## 판 upgrades 항목", "| 축 | 무엇 | 나아짐 | 나빠짐 | 근거 기록 |", "|---|---|---|---|---|"]
    for x in r["items"]:
        L.append(f"| {x['axis']} | {str(x['what'])[:50]} | {mark(x['better'])} | {'나빠짐' if x.get('worse') is True else ('-' if x.get('worse') is False else '미측정')} | {'○' if x['evidence_ok'] else '×'} |")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--base-doc", help="1차 판 완성본 doc(같은 축의 1차 값 참고 — --base-work 와 함께)"); ap.add_argument("--base-work")
    ap.add_argument("--axes", default="", help="(측정 가능한 축은 기본으로 다 잰다) 더 잴 축(쉼표) — 표준 15종 이름")
    ap.add_argument("--items-only", action="store_true", help="판 upgrades 항목 축만(L3 는 측정 가능한 축 전부가 기준 — 시험용)")
    ap.add_argument("--fit", action="store_true", help="장면대사.json 이 없으면 scene_fit.measure_render 로 잰다(Claude 호출)")
    ap.add_argument("--no-write", action="store_true")
    A = ap.parse_args(argv)
    doc = Path(A.doc) if Path(A.doc).is_absolute() else ROOT / A.doc
    r = measure(A.style, doc, Path(A.work), base_doc=A.base_doc, base_work=A.base_work, extra_axes=tuple(x for x in A.axes.split(",") if x),
                allow_llm=A.fit, write=not A.no_write, all_axes=not A.items_only)
    print(table_md(r))
    print(f"\n결과: {doc / '업그레이드_측정.json'}" if not A.no_write else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
