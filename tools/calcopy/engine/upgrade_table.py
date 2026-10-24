# -*- coding: utf-8 -*-
"""업그레이드 자 — "벤치보다 낫다"를 측정값으로 (관제 263 지시서 05, 2026-10-25 · 표준 §4-2 · 지침서 §2-6-1).

    PYTHONUTF8=1 py tools/calcopy/engine/upgrade_table.py <업그레이드판> <doc_dir> <work_dir> [--axes cap_look,cut_rhythm,…] [--fit] [--no-write]

업그레이드 판(`base` 로 1차 판 상속)의 `upgrades:[{axis,what,why,source,expect,verify}]` 항목마다 벤치 vs 우리 측정 셋을 내고
`<doc>/업그레이드_측정.json {items:[{axis,what,bench,ours,better,why}], better_n, human_n, unmeasured_n, total, gates:{upgrade}}` 로 쓴다.
판에 `upgrades` 칸이 없고 `_diff`(옛 변형판 꼴, 예 연예인레시피판)만 있으면 `_diff` 칸을 upgrades 꼴로 바꿔 읽는다(판 파일은 안 고친다).

판단 주인: '나아짐' 판정 = 이 파일 BETTER(축마다 한 줄). 측정은 **새로 재지 않고 기존 주인 함수를 부른다** — 벤치·우리 같은 함수:
  장면↔대사 = oneshot/scene_fit.measure_render(우리 · 품질 관문이 남긴 <doc>/장면대사.json 을 먼저 읽음) · quality_gate.bench_fit(벤치 줄판독 fit)
  정지 = quality_gate.freezes(우리 완성본 · 벤치 원본 — 같은 함수·같은 문턱)
  효과 밀도 = kal_analyze._stats(벤치 상위 편 편마다) · kal_analyze.match_from_render(우리, media=False) → 같은 칸(sfx.rate·transition.rate·sticker.rate·meme.rate·fx.rate.나레)
  훅 = kal_analyze.scene_cuts(첫 컷 — 벤치 원본·우리 완성본) · kal_analyze.frame0_kind(줄판독) / 썸네일 표식(관문 0초 측정)
  소리 = hybrid.common.lufs · kal_analyze.bench_media_cached(벤치 LUFS) · 받아쓰기 = <doc>/품질관문.json '나레 받아쓰기 ↔ 대본'(quality_gate 가 check_line_sync 로 잰 것)
  말속도·쉼 = 자막 조각 cps 편차(벤치 줄판독·우리 자막표 — 같은 함수 _cps_cv) · 쉼 = <doc>/품질관문.json 'B18 쉼'(checks.pauses_between)
  자막 가독성 = kal_analyze.frame_metrics(글자 높이·채움↔외곽 ΔE) — 벤치 원본·우리 완성본 프레임, 같은 띠
  못 재는 축(script·cap_enter·cap_exit·pointer) 또는 verify='사람 판정' = 'human'(사장님)
'벤치 상위 편' = 조회 상위 50%(C:/숏템_칼카피/<slug>/top.json views, 없는 편은 src_dir/<id>.info.json view_count).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
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


# ---------------------------------------------------------------- 축별 측정(벤치·우리 같은 함수) → {bench, ours, better, why}
def m_scene_fit(C: Ctx) -> dict:
    from tools.calcopy.hybrid import quality_gate as QG
    bench = QG.bench_fit(C.bench)
    p = C.doc / "장면대사.json"
    if p.exists():
        ours, src = _jl(p).get("summary"), f"{p.name}(scene_fit.measure_render — 관문이 남긴 것)"
    elif C.allow_llm and C.has_final():
        from tools.calcopy.oneshot import scene_fit
        ours, src = scene_fit.measure_render(C.work, out=p)["summary"], "scene_fit.measure_render(지금 잼)"
    else:
        ours, src = None, "장면대사.json 없음(--fit 으로 재면 Claude 호출)"
    if not bench or not ours or ours.get("mean") is None:
        return {"bench": bench, "ours": ours, "better": None, "why": f"미측정 — 벤치 {'있음' if bench else '줄판독 fit 칸 없음'} · 우리 {src}"}
    better = ours["mean"] > bench["mean"] and ours["below_rate"] <= bench["below_rate"]
    return {"bench": {"mean": bench["mean"], "below_rate": bench["below_rate"], "n_docs": bench["n_docs"]},
            "ours": {"mean": ours["mean"], "below_rate": ours["below_rate"], "judged": ours.get("judged")}, "better": better,
            "why": f"평균↑·7 미만 비율↓ 둘 다여야 — 우리 {ours['mean']}/{ours['below_rate']} vs 벤치 {bench['mean']}/{bench['below_rate']} · 우리 출처 {src}"}


def m_cut_rhythm(C: Ctx) -> dict:
    """정지·멈춤 = quality_gate.freezes(창 안 같은 그림 0.3초+) — 우리 완성본 0건이면 나아짐(표준 §4-2). 벤치 원본도 같은 함수로 잰다(참고)."""
    from tools.calcopy.hybrid import quality_gate as QG
    if not C.has_final():
        return {"bench": None, "ours": None, "better": None, "why": "완성본 없음(미측정)"}
    ours = QG.freezes(C.final(), C.win())
    bench, cp = {}, None
    if C.src and C.bench_win():
        cache, cp = C.cache("_upgrade_freeze_cache.json")
        for d in C.bench:
            mp4 = C.src / f"{d.get('id')}.mp4"
            if not mp4.exists():
                continue
            k = _key(mp4, list(C.bench_win()) + [QG.FREEZE_SEC])
            if k not in cache:
                cache[k] = QG.freezes(mp4, C.bench_win())
            bench[d["id"]] = len(cache[k])
        _save_cache(cache, cp)
    return {"bench": {"freezes_per_doc": bench, "median": statistics.median(bench.values()) if bench else None},
            "ours": {"freezes": len(ours), "spans": ours}, "better": len(ours) == 0,
            "why": f"멈춤(창 안 같은 그림 ≥{QG.FREEZE_SEC}초) 우리 {len(ours)}건 — 0건이어야 나아짐 · 벤치 원본 같은 함수 {bench or '없음'}"}


def _density_val(key: str, s: dict | None):
    if s is None:
        return None
    v = s.get(key) if isinstance(s, dict) else None
    if key == "transition.rate":                # 분포 → cut 밖 전환 비율 하나로
        return None if v is None else round(1.0 - float(v.get("cut", 0.0)), 3)
    return _num(v)


def m_density(C: Ctx, axis: str) -> dict:
    key = DENSITY_KEY[axis]
    top = C.top()
    bv = {d["id"]: _density_val(key, C.K._stats(d.get("lines") or [], float(d.get("dur") or 0))) for d in top}
    bv = {k: v for k, v in bv.items() if v is not None}
    M = C.ours_match()
    row = next((r for r in (M or {}).get("rows") or [] if r["key"] == key), None)
    ours = _density_val(key, {key: row["ours"]}) if row else None
    if not bv or ours is None:
        return {"bench": bv or None, "ours": ours, "better": None, "why": f"미측정 — 벤치 상위 편 {list(bv) or '없음'} · 우리 {'match 없음' if M is None else '칸 없음'}"}
    lo, hi = min(bv.values()), max(bv.values())
    return {"bench": {"top_ids": list(bv), "per_doc": bv, "range": [lo, hi]}, "ours": ours, "better": lo - 1e-9 <= ours <= hi + 1e-9,
            "why": f"{key}{'(cut 밖 비율)' if key == 'transition.rate' else ''} 우리 {ours} — 벤치 조회 상위 50% {len(bv)}편 범위 {lo}~{hi} 안이면 나아짐"}


def _first_cut(K, mp4: Path, win) -> float | None:
    ts = [t for t in K.scene_cuts(str(mp4), win) if t > HOOK_SEC]
    return round(ts[0], 2) if ts else None


def m_thumb(C: Ctx) -> dict:
    """훅 = 첫 컷 길이(scene_cuts — 벤치 원본·우리 완성본 같은 함수) + 0초 종류(card/scene). 0초 얼굴·물건 비율은 아직 안 잰다(why 에 적음)."""
    if not C.has_final():
        return {"bench": None, "ours": None, "better": None, "why": "완성본 없음(미측정)"}
    K = C.K
    top = C.top()
    cache, cp = C.cache("_upgrade_firstcut_cache.json")
    bfc = {}
    for d in top:
        mp4 = C.src / f"{d['id']}.mp4" if C.src else None
        if mp4 and mp4.exists():
            k = _key(mp4, list(C.bench_win() or []))
            if k not in cache:
                cache[k] = _first_cut(K, mp4, C.bench_win())
            if cache[k] is not None:
                bfc[d["id"]] = cache[k]
    _save_cache(cache, cp)
    from collections import Counter
    f0b = Counter(k for k in (K.frame0_kind(d) for d in top) if k).most_common(1)
    f0b = f0b[0][0] if f0b else None
    ofc = _first_cut(K, C.final(), C.win())
    row = next((r for r in (C.ours_match() or {}).get("rows") or [] if r["key"] == "thumb.frame0"), None)
    gr = C.gate_row("썸네일 맨 앞 2프레임")
    f0o = ("card" if gr["ok"] else "scene") if gr and gr.get("ok") is not None else (row or {}).get("ours")
    if not bfc or ofc is None or not f0b or not f0o:
        return {"bench": {"first_cut": bfc, "frame0": f0b}, "ours": {"first_cut": ofc, "frame0": f0o}, "better": None, "why": "미측정 — 첫 컷·0초 종류 한쪽 없음"}
    lo, hi = min(bfc.values()), max(bfc.values())
    ok = lo - 0.05 <= ofc <= hi + 0.05 and f0o == f0b
    return {"bench": {"top_ids": list(bfc), "first_cut": bfc, "range": [lo, hi], "frame0": f0b}, "ours": {"first_cut": ofc, "frame0": f0o}, "better": ok,
            "why": f"첫 컷 우리 {ofc}초 vs 상위 편 {lo}~{hi}초(±0.05) · 0초 우리 {f0o} vs 상위 편 최빈 {f0b} — 둘 다 안이면 나아짐 · 0초 얼굴/물건 비율은 미측정"}


def m_bgm(C: Ctx) -> dict:
    """소리 = LUFS −14±1(hybrid.common.lufs) + 나레 받아쓰기 100%(관문 행). 벤치 LUFS 는 bench_media_cached(참고 — 벤치 원본은 −14 통일 전 값)."""
    if not C.has_final():
        return {"bench": None, "ours": None, "better": None, "why": "완성본 없음(미측정)"}
    from tools.calcopy.hybrid.common import lufs
    I, tp = lufs(C.final())
    bl = None
    if C.src and C.bench:
        bm = C.K.bench_media_cached(str(C.src), [d.get("id") for d in C.bench], C.bench_win())
        bl = {k: v.get("lufs") for k, v in (bm.get("per") or {}).items()}
    asr = C.gate_row("나레 받아쓰기")
    asr_ok = asr.get("ok") if asr else None
    lufs_ok = abs(I - LUFS_TARGET) <= LUFS_TOL
    better = None if asr_ok is None else (lufs_ok and asr_ok is True)
    return {"bench": {"lufs_per_doc": bl}, "ours": {"lufs": I, "tp": tp, "asr_ok": asr_ok, "asr": (asr or {}).get("value")}, "better": better,
            "why": f"LUFS {I}(목표 {LUFS_TARGET}±{LUFS_TOL} {'○' if lufs_ok else '×'}) · 받아쓰기 {('○' if asr_ok else '×') if asr_ok is not None else '미측정(품질관문.json 없음)'} — 둘 다 ○이어야 나아짐"}


def _cps_cv(lines: list[dict], K) -> float | None:
    """나레 자막 조각 cps(글자/표시 초)의 변동계수 — 벤치 줄판독·우리 자막표 같은 함수."""
    xs = []
    for l in lines:
        if K._sp(l.get("speaker")) != "나레":
            continue
        d = float(l.get("t1") or 0) - float(l.get("t0") or 0)
        n = K._chars(l.get("text") or "")
        if d > 0.05 and n:
            xs.append(n / d)
    if len(xs) < 3:
        return None
    m = statistics.mean(xs)
    return round(statistics.pstdev(xs) / m, 3) if m else None


def m_speech(C: Ctx) -> dict:
    K = C.K
    bcv = {d.get("id"): _cps_cv(d.get("lines") or [], K) for d in C.bench}
    bcv = {k: v for k, v in bcv.items() if v is not None}
    tp = C.R / "자막표.json"
    ocv = _cps_cv(K._ours_lines({"rows": _jl(tp).get("rows") or []})[0], K) if tp.exists() else None
    b18 = C.gate_row("B18 쉼")
    if not bcv or ocv is None:
        return {"bench": bcv or None, "ours": ocv, "better": None, "why": "미측정 — 조각 cps 한쪽 없음"}
    bmed = round(statistics.median(bcv.values()), 3)
    pause_ok = b18.get("ok") if b18 else None
    better = ocv <= bmed and (pause_ok is not False)
    return {"bench": {"cps_cv_per_doc": bcv, "median": bmed}, "ours": {"cps_cv": ocv, "pause_ok": pause_ok, "pause": (b18 or {}).get("value")}, "better": better,
            "why": f"나레 조각 cps 편차(변동계수) 우리 {ocv} ≤ 벤치 중앙 {bmed} {'○' if ocv <= bmed else '×'} · 쉼 0.22~0.30 {('○' if pause_ok else '×') if pause_ok is not None else '미측정'}"}


def _grab(mp4: Path, t: float, dst: Path) -> Path | None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(dst)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    return dst if r.returncode == 0 and dst.exists() else None


def _look(K, png: Path, band) -> dict | None:
    import numpy as np
    m = K.frame_metrics(str(png), band)
    if not m.get("box") or not m.get("fill_hex") or not m.get("outline_hex"):
        return None
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]   # noqa: E731
    dE = float(np.linalg.norm(K._lab(rgb(m["fill_hex"])) - K._lab(rgb(m["outline_hex"]))))
    return {"h": m["h"], "dE": round(dE, 1)}


def m_cap_look(C: Ctx, n: int = 6) -> dict:
    """자막 가독성 = 글자 잉크 높이 h·채움↔외곽 ΔE(kal_analyze.frame_metrics) — 벤치 상위 편 원본·우리 완성본 나레 조각 가운데 프레임, 같은 띠(줄판독 layout.caption_band ±30)."""
    if not C.has_final():
        return {"bench": None, "ours": None, "better": None, "why": "완성본 없음(미측정)"}
    K = C.K
    bands = [tuple((d.get("layout") or {}).get("caption_band") or ()) for d in C.bench]
    bands = [b for b in bands if len(b) == 2]
    if not bands:
        return {"bench": None, "ours": None, "better": None, "why": "벤치 줄판독 layout.caption_band 없음(미측정)"}
    band = (int(statistics.median(b[0] for b in bands)) - 30, int(statistics.median(b[1] for b in bands)) + 30)
    tmp = C.work / "upgrade_look"

    def grab_set(mp4: Path, lines: list[dict], tag: str) -> list[dict]:
        out = []
        for i, l in enumerate([l for l in lines if K._sp(l.get("speaker")) == "나레" and float(l.get("t1") or 0) - float(l.get("t0") or 0) > 0.3][:n]):
            p = _grab(mp4, (float(l["t0"]) + float(l["t1"])) / 2, tmp / f"{tag}_{i}.png")
            v = _look(K, p, band) if p else None
            if v:
                out.append(v)
        return out
    b = []
    for d in C.top():
        mp4 = C.src / f"{d['id']}.mp4" if C.src else None
        if mp4 and mp4.exists():
            b += grab_set(mp4, d.get("lines") or [], d["id"])
    tp = C.R / "자막표.json"
    o = grab_set(C.final(), K._ours_lines({"rows": _jl(tp).get("rows") or []})[0], "ours") if tp.exists() else []
    if not b or not o:
        return {"bench": b or None, "ours": o or None, "better": None, "why": f"미측정 — 글자 못 찾음(벤치 {len(b)}·우리 {len(o)}장, 띠 {band})"}
    bh, bd = statistics.median(x["h"] for x in b), statistics.median(x["dE"] for x in b)
    oh, od = statistics.median(x["h"] for x in o), statistics.median(x["dE"] for x in o)
    return {"bench": {"h": bh, "dE": bd, "n": len(b)}, "ours": {"h": oh, "dE": od, "n": len(o)}, "better": (od > bd) or (oh > bh),
            "why": f"대비↑ 또는 크기↑ — ΔE 우리 {od} vs 벤치 {bd} · 높이 우리 {oh}px vs 벤치 {bh}px (띠 {band}, 상위 편 프레임 {len(b)}장·우리 {len(o)}장)"}


def measure_axis(C: Ctx, axis: str) -> dict:
    if axis in HUMAN_AXES:
        return {"bench": None, "ours": None, "better": "human", "why": f"{axis} = 측정 함수 없는 축(표준 §4-2 '못 재는 칸') — 사장님 판정"}
    if axis in DENSITY_KEY:
        return m_density(C, axis)
    return {"scene_fit": m_scene_fit, "cut_rhythm": m_cut_rhythm, "thumb": m_thumb, "bgm": m_bgm, "speech": m_speech, "cap_look": m_cap_look}[axis](C)


# ---------------------------------------------------------------- 판정 한 곳
def measure(style, doc, work, base_doc=None, base_work=None, extra_axes: tuple = (), allow_llm: bool = False, write: bool = True) -> dict:
    """(판단 주인 — 업그레이드 자) 판 upgrades 항목마다 측정 → <doc>/업그레이드_측정.json.
    better: True/False(측정값) · 'human'(사람 판정 — 따로 셈) · None(미측정 — 나아짐으로 안 친다).
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
        m = {"bench": None, "ours": None, "better": "human", "why": f"verify='{it.get('verify')}' — 사장님 판정"} if human and it.get("axis") not in HUMAN_AXES else get(it["axis"])
        row = {"axis": it["axis"], "what": it.get("what"), "bench": m["bench"], "ours": m["ours"], "better": m["better"], "why": m["why"],
               "item_why": it.get("why"), "source": it.get("source"), "expect": it.get("expect"), "verify": it.get("verify"), "evidence_ok": evidence_ok(it)}
        if Cb and it["axis"] not in HUMAN_AXES and not human:
            row["first"] = measure_axis(Cb, it["axis"]).get("ours")
        out.append(row)
    ref = [{"axis": ax, **get(ax), "_note": "참고(판 upgrades 항목 아님 — --axes)"} for ax in extra_axes]
    better_n = sum(r["better"] is True for r in out)
    human_n = sum(r["better"] == "human" for r in out)
    un_n = sum(r["better"] is None for r in out)
    meas_n = sum(r["better"] in (True, False) for r in out)
    res = {"style": name, "base": st.get("base"), "table": TABLE_VERSION, "upgrades_from": src, "doc": str(doc), "work": str(work),
           "bench_ids": [d.get("id") for d in C.bench], "bench_top_ids": C.top_ids(), "views": C.views(),
           "items": out, "better_n": better_n, "measured_n": meas_n, "human_n": human_n, "unmeasured_n": un_n, "total": len(out),
           "evidence_ok_n": sum(r["evidence_ok"] for r in out),
           "gates": {"upgrade": {"better": f"{better_n}/{meas_n}", "human": human_n, "unmeasured": un_n, "total": len(out),
                                 "ok": bool(out) and meas_n > 0 and better_n == meas_n and un_n == 0}},
           "reference": ref}
    if write and Path(doc).exists():
        (Path(doc) / "업그레이드_측정.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return res


def upgrade_table(st, doc, work) -> dict:
    """quality_gate.gate 가 업그레이드 판에서 찾는 이름(getattr(kal_analyze, 'upgrade_table')) 과 같은 꼴 — kal_analyze 에 잇는 한 줄은 페이블 결정(지시서 05)."""
    return measure(st, doc, work)


def table_md(r: dict) -> str:
    mark = lambda b: {True: "○", False: "×", "human": "사람", None: "미측정"}.get(b, str(b))   # noqa: E731
    L = [f"# 업그레이드 측정 {r['style']}(base {r['base']}) — 나아짐 {r['better_n']}/{r['measured_n']} · 사람 {r['human_n']} · 미측정 {r['unmeasured_n']} · 전체 {r['total']} · 근거 기록 {r['evidence_ok_n']}/{r['total']}",
         f"(upgrades 출처 {r['upgrades_from']} · 벤치 상위 편 {r['bench_top_ids']})", "", "| 축 | 무엇 | 벤치 | 우리 | 나아짐 | 근거 기록 | 왜 |", "|---|---|---|---|---|---|---|"]
    for x in r["items"]:
        L.append(f"| {x['axis']} | {str(x['what'])[:40]} | {json.dumps(x['bench'], ensure_ascii=False, default=str)[:80]} | "
                 f"{json.dumps(x['ours'], ensure_ascii=False, default=str)[:80]} | {mark(x['better'])} | {'○' if x['evidence_ok'] else '×'} | {x['why'][:120]} |")
    for x in r.get("reference") or []:
        L.append(f"| (참고) {x['axis']} | --axes | {json.dumps(x['bench'], ensure_ascii=False, default=str)[:80]} | {json.dumps(x['ours'], ensure_ascii=False, default=str)[:80]} | {mark(x['better'])} | - | {x['why'][:120]} |")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--base-doc", help="1차 판 완성본 doc(같은 축의 1차 값 참고 — --base-work 와 함께)"); ap.add_argument("--base-work")
    ap.add_argument("--axes", default="", help="판 upgrades 와 별개로 참고로 더 잴 축(쉼표) — 표준 15종 이름")
    ap.add_argument("--fit", action="store_true", help="장면대사.json 이 없으면 scene_fit.measure_render 로 잰다(Claude 호출)")
    ap.add_argument("--no-write", action="store_true")
    A = ap.parse_args(argv)
    doc = Path(A.doc) if Path(A.doc).is_absolute() else ROOT / A.doc
    r = measure(A.style, doc, Path(A.work), base_doc=A.base_doc, base_work=A.base_work, extra_axes=tuple(x for x in A.axes.split(",") if x),
                allow_llm=A.fit, write=not A.no_write)
    print(table_md(r))
    print(f"\n결과: {doc / '업그레이드_측정.json'}" if not A.no_write else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
