# -*- coding: utf-8 -*-
"""썰풀다(도파민썰템 벤치) 상위 50편 → 소리·화자 구성 스타일 4갈래 전수 분류 (관제 097, 2026-10-17).

    PYTHONUTF8=1 py channel/sseolpulda/style_classify.py               # 없는 편만 새로 재고 표 다시 씀
    PYTHONUTF8=1 py channel/sseolpulda/style_classify.py --no-measure  # 새로 재지 않고 있는 것만으로 표
    PYTHONUTF8=1 py channel/sseolpulda/style_classify.py --only=<id>,<id>  # 그 편만 다시 잼

스타일(사장님 정의):
  나레만    해외 원작 + 한국어 나레 1명, 원음 끔
  나레+원음 한국어 나레 + 해외 원음(현장 소리·대사)
  자막만    한국어 나레 없음 — 원작(원음 또는 BGM)에 대본 자막만
  역할극    한국어 목소리 2명 이상이 역할을 나눠 말함(나레+역할 포함)

자료 쓰는 순서(기존 자료 먼저 — 사장님 10-17 지적):
  A 기존 1차(10-15, 50편 전부): 원자료/judge/<id>.json(제미나이 영상 판독: voice.narration·roles·script)
                                 원자료/asr/<id>.json(스피치매틱스 한국어 단어 시각, 화자분리 없음)
  B 기존 뜯기 3판(10-16, 10편): C:/숏템_칼카피/sseolpulda/engine_뜯기3/<id>/뜯기.json audio.composition·transcript
  C 새로 잼(기존에 없는 '원음 유무'·대사 구절이 필요한 편만): analyze.audio_and_tone(제미나이 무료 받아쓰기 1회 +
     bench 소리 + audio_comp.composition). 프롬프트 = analyze.ASR_PROMPT + ROLE_PROMPT_EXTRA(대사 따로 끊기). 버텍스 금지.
  피치(audio_comp.pitch_stats)는 로컬 mp4 로만 잰다(호출 없음).

판정(이 파일 classify 한 곳. audio_comp 는 다른 세션 공용이라 고치지 않음):
  자막만  A judge narration=False 이고 (B kind ∈ {원음만+자막, 나레 없음} 또는 스피치매틱스 한국어 단어 0) → 새로 안 잼
          (스피치매틱스는 한국어 고정이라 영어도 한국어 단어로 받아씀 — ZdeZ 영어 원음이 18단어로 나옴. 단어 수만으론 못 정함)
  역할극  (1) 받아쓰기(B 또는 C)에 한국어 dialog 구절 + 한국어 화자 2명 이상
          (2) R2: 역할 구간(받아쓰기 dialog 구절 ∪ judge 대본의 역할 줄을 스피치매틱스 단어 시각에 맞춘 구간)의 피치 중앙값이
              나머지 한국어 말소리(나레) 피치와 ROLE_PITCH_SEMI 반음 이상 차이
  나레+원음  한국어 나레 + 원음 구절(kind=source 또는 lang 이 실제 외국어 코드) 또는 음악 아닌 현장음(ambient)
  나레만  나머지(한국어 나레 있음)
  역할극 > 나레+원음 > 나레만 순. 역할극이면서 원음도 있으면 evidence 에 남김.

보정 근거(2026-10-17 실측):
  R1 oJZDImhYdXw: 뜯기 3판 받아쓰기가 14.9~24.6초(9.7초 '구절 미분할')를 나레 한 구절로 묶어 대사가 묻힘 → kind '나레 1명'.
     자막 시각으로 자른 피치: 나레 151~160Hz / 사장 대사 258Hz / 개발팀 대사 208Hz. 7DYbxVNz5q8 역할 목소리 269·254Hz vs 나레 137~150Hz
     와 같은 꼴 → 같은 목소리로 읽은 게 아니라 목소리를 바꿨는데 받아쓰기가 구절을 안 끊어 화자 분리를 놓친 것.
  R2 문턱 4반음: oJZD 대사 +5.4~+7.9반음, 7DYb 역할 +9.4~+10.5반음. 7DYb 나레 창끼리도 +5.7반음(15.5~16.8초)까지 흔들려서
     '역할 줄로 지목된 구간'에만 적용한다(아무 창에나 쓰면 들뜬 나레를 역할로 오판).
  R4 iZ-TprLYezA: 제미나이 받아쓰기 2회 빈 답(소리 -14.4 LUFS) + 스피치매틱스 한국어 단어 0 → 자막만. judge 는 TTS 나레·순위 대본이라 했으나
     두 받아쓰기 모두 말소리를 못 찾음(judge 가 화면 자막을 읽은 것으로 봄 — 귀로 확인 안 함).
  R3 원음 구절: 제미나이 lite 대체 모델은 lang 을 'unknown' 으로 비워 audio_comp 가 원음으로 셈(7DYb C 재측정 5구절 전부 unknown)
     → lang ∈ FOREIGN 또는 kind=source 만 원음으로 친다.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["BRAINBULB_VERTEX"] = "0"

from shopping_shorts.channelkit.bench import probe, audio as baudio  # noqa: E402
from tools.calcopy.engine import gemini_free, audio_comp  # noqa: E402
from tools.calcopy.engine.analyze import audio_and_tone  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "원자료"
TOP50 = RAW / "top50.json"
BASE = Path("C:/숏템_칼카피/sseolpulda")
MP4 = BASE / "mp4"
ENG3 = BASE / "engine_뜯기3"
OUT = BASE / "style50"
STYLES = ["나레만", "나레+원음", "자막만", "역할극"]
VERSION = "style_classify 2판 2026-10-17"

ROLE_PROMPT_EXTRA = ('\n추가 규칙: 이야기 속 인물의 말(직접 인용·따옴표 대사)은 나레이터와 같은 목소리여도 반드시 별도 구절로 끊고 '
                     'kind=dialog 로 적어라. 그 대사 목소리가 나레이터와 다른 사람·다른 합성 목소리면 다른 화자 라벨을 써라. '
                     '구절 하나는 8초를 넘기지 마라.')
ROLE_PITCH_SEMI = 4.0
ALIGN_MIN = 0.6          # judge 역할 줄 글자 중 스피치매틱스 글자와 맞은 비율이 이 이상이어야 구간으로 씀
FOREIGN = {"en", "ja", "zh", "es", "fr", "de", "ru", "pt", "it", "vi", "th", "id", "hi", "ar", "tr"}
NARR_NAMES = {"나레", "나레이터", "나레이션", "narrator"}
MUSIC_ONLY = re.compile(r"[\s,./·]*(배경\s*음악|음악|BGM|bgm|music|노래)[\s,./·]*")
KNOWN = {"ZdeZRtCeAC4": "자막만", "w-Ygny1f8O8": "나레+원음", "7DYbxVNz5q8": "역할극", "oJZDImhYdXw": "역할극"}


def _j(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _norm(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "")


# ── 기존 자료 A ──────────────────────────────────────────────
def sm_words(vid: str) -> list[dict]:
    a = _j(RAW / "asr" / f"{vid}.json") or {}
    return [{"t0": r["start_time"], "t1": r["end_time"], "w": r["alternatives"][0]["content"]}
            for r in a.get("results", []) if r.get("type") == "word"]


def judge_role_lines(j: dict) -> list[str]:
    """judge 대본에서 나레가 아닌 인물 줄(한글 있는 것만 — 영어 원음 인물 줄은 원음 증거)."""
    out = []
    for ln in (j.get("script") or "").split("\n"):
        ln = ln.strip()
        m = re.match(r"^\(?([^\s:()]{1,8})\)?\s*:\s*(.+)$", ln)
        if m and m.group(1) not in NARR_NAMES:
            out.append(m.group(2))
        out += re.findall(r"\*([^*]{2,})\*", ln)
    return [t for t in out if re.search(r"[가-힣]", t)]


def align(line: str, words: list[dict]) -> tuple[float, float, float] | None:
    """역할 줄을 스피치매틱스 단어 시각에 맞춘다 → (시작, 끝, 맞은 비율)."""
    chars, times = [], []
    for w in words:
        for c in _norm(w["w"]):
            chars.append(c)
            times.append((w["t0"], w["t1"]))
    hay, need = "".join(chars), _norm(line)
    if not hay or not need:
        return None
    sm = difflib.SequenceMatcher(None, hay, need, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
    if not blocks:
        return None
    # 가장 긴 블록 둘레(줄 길이 × 1.5 안)만 모은다 — 대본 다른 곳의 같은 낱말에 끌려가지 않게
    big = max(blocks, key=lambda b: b.size)
    lo, hi = big.a - big.b - 2, big.a + (len(need) - big.b) + 2
    got = [b for b in blocks if b.a >= lo - len(need) // 2 and b.a + b.size <= hi + len(need) // 2]
    hit = sum(b.size for b in got) / len(need)
    if hit < ALIGN_MIN:
        return None
    a0, a1 = min(b.a for b in got), max(b.a + b.size for b in got) - 1
    return times[a0][0], times[a1][1], round(hit, 2)


# ── 새로 재기 C ──────────────────────────────────────────────
def _llm(parts, prompt, tag=""):
    return gemini_free.ask(parts, prompt + ROLE_PROMPT_EXTRA, tag)


def measure_new(vid: str) -> dict:
    p = MP4 / f"{vid}.mp4"
    if not p.exists():
        return {"failed": "mp4 없음(다운로드 실패)"}
    meta = probe.info(str(p))
    gemini_free.CALLS.clear()
    res, _ = audio_and_tone(str(p), meta, _llm, None)
    res.pop("bench", None)
    return {"duration": meta.get("duration"), "audio": res, "llm_calls": list(gemini_free.CALLS),
            "measured_at": time.strftime("%Y-%m-%d %H:%M"), "prompt_extra": ROLE_PROMPT_EXTRA}


def eng3(vid: str) -> dict | None:
    R = _j(ENG3 / vid / "뜯기.json")
    if not R:
        return None
    a = R.get("audio") or {}
    return {"duration": (R.get("probe") or {}).get("duration"), "audio": {k: a.get(k) for k in ("transcript", "composition", "asr_extra")},
            "from": str(ENG3 / vid / "뜯기.json")}


# ── 판정 ─────────────────────────────────────────────────────
def _semi(a: float, b: float) -> float:
    return 12 * math.log2(a / b)


def _overlap(a0, a1, spans) -> bool:
    return any(a0 < b1 and b0 < a1 for b0, b1 in spans)


def classify(vid: str, j: dict, words: list[dict], m: dict | None, used: list[str]) -> dict:
    v = j.get("voice") or {}
    ev: dict = {"judge_voice": v, "sm_ko_words": len(words), "sm_ko_sec": round(sum(w["t1"] - w["t0"] for w in words), 1)}
    comp = ((m or {}).get("audio") or {}).get("composition") or {}
    # 자막만 — 기존 자료로 끝나는 경우
    if v.get("narration") is False and (comp.get("kind") in ("원음만+자막", "나레 없음") or (not words and not m)):
        return {"style": "자막만", "reason": f"judge 나레 없음 + {'뜯기3판 ' + comp['kind'] if comp.get('kind') else '스피치매틱스 한국어 단어 0'}",
                "evidence": ev, "sources": used}
    if m and "빈 답" in str(comp.get("failed") or "") and not words:
        # R4: 제미나이 받아쓰기 빈 답 + 스피치매틱스(한국어 고정) 단어 0 = 두 받아쓰기 모두 말소리 못 찾음 → 자막만(judge 와 충돌이면 표시)
        return {"style": "자막만", "reason": "R4: 제미나이 빈 답 + 스피치매틱스 한국어 단어 0" + (" — judge 는 나레 있다고 함(충돌, 귀 확인 안 함)" if v.get("narration") else ""),
                "evidence": ev, "sources": used}
    if not m or (m or {}).get("failed") or comp.get("failed"):
        return {"style": "미분류", "reason": (m or {}).get("failed") or comp.get("failed") or "원음 유무 미측정(새 측정 없음)",
                "evidence": ev, "sources": used}
    tr = (m.get("audio") or {}).get("transcript") or {}
    segs = tr.get("segments") or []
    narr = [s for s in segs if s["kind"] == "narration" and s["lang"] == "ko"]
    dialog = [s for s in segs if s["kind"] == "dialog" and s["lang"] == "ko"]
    ko_spk = sorted({s["speaker"] for s in narr + dialog})
    src = [s for s in segs if s["kind"] == "source" or s["lang"] in FOREIGN]
    amb = str(tr.get("ambient") or "").strip()
    amb_src = bool(amb) and not MUSIC_ONLY.fullmatch(amb)
    ev.update({"asr_model": tr.get("model"), "engine_kind": comp.get("kind"), "ko_speakers": ko_spk, "n_narr": len(narr),
               "n_dialog": len(dialog), "n_source": len(src), "source_text": [s["text"][:40] for s in src][:5], "ambient": amb,
               "warnings": tr.get("warnings")})
    has_ko = bool(narr or dialog)
    if not has_ko and v.get("narration") is False:
        return {"style": "자막만", "reason": f"받아쓰기 한국어 말소리 없음 + judge 나레 없음(엔진 kind '{comp.get('kind')}')", "evidence": ev, "sources": used}
    if not has_ko:
        return {"style": "미분류", "reason": (f"한국어 나레는 있음(스피치매틱스 {len(words)}단어·judge 나레) — 그러나 제미나이 받아쓰기가 구절 0개라 원음 유무를 못 잼"
                                             if len(words) >= 10 else f"받아쓰기엔 한국어 말소리 없음, judge 는 나레 있음 — 충돌(엔진 kind '{comp.get('kind')}')"),
                "evidence": ev, "sources": used}
    role, why = False, []
    if dialog and len(ko_spk) >= 2:
        role = True
        why.append(f"받아쓰기 한국어 대사 {len(dialog)}구절 + 한국어 화자 {len(ko_spk)}명")
    # R2 피치 — 역할 구간 = 받아쓰기 dialog ∪ judge 역할 줄 정렬
    spans = [(s["start"], s["end"]) for s in dialog]
    jl = judge_role_lines(j)
    al = [(t, align(t, words)) for t in jl]
    spans += [(r[0], r[1]) for _, r in al if r]
    ev["judge_role_lines"] = [{"text": t[:30], "span": r} for t, r in al]
    if spans and role:      # (1)로 정해진 편도 피치를 같이 남긴다(제미나이 화자 분리만 믿지 않게 — 교차 확인용, 판정은 안 바꿈)
        x = baudio.mono(str(MP4 / f"{vid}.mp4")) if (MP4 / f"{vid}.mp4").exists() else None
        nspans = [{"start": w["t0"], "end": w["t1"]} for w in words if not _overlap(w["t0"], w["t1"], spans)]
        pn = audio_comp.pitch_stats(x, nspans) if x is not None and nspans else None
        pd = audio_comp.pitch_stats(x, [{"start": a, "end": b} for a, b in spans]) if x is not None else None
        if pn and pd:
            d = round(_semi(pd["f0_median_hz"], pn["f0_median_hz"]), 2)
            ev["R2_pitch"] = {"narr_hz": pn["f0_median_hz"], "role_hz": pd["f0_median_hz"], "diff_semi": d, "thr": ROLE_PITCH_SEMI,
                              "cross_check_only": True}
            why.append(f"피치 교차확인 {d:+.1f}반음" + ("" if abs(d) >= ROLE_PITCH_SEMI else " (문턱 미만 — 제미나이 화자 분리만 근거)"))
    elif spans:
        x = baudio.mono(str(MP4 / f"{vid}.mp4")) if (MP4 / f"{vid}.mp4").exists() else None
        nspans = [{"start": w["t0"], "end": w["t1"]} for w in words if not _overlap(w["t0"], w["t1"], spans)]
        pn = audio_comp.pitch_stats(x, nspans) if x is not None and nspans else None
        pd = audio_comp.pitch_stats(x, [{"start": a, "end": b} for a, b in spans]) if x is not None else None
        if pn and pd:
            d = round(_semi(pd["f0_median_hz"], pn["f0_median_hz"]), 2)
            ev["R2_pitch"] = {"narr_hz": pn["f0_median_hz"], "role_hz": pd["f0_median_hz"], "diff_semi": d, "thr": ROLE_PITCH_SEMI,
                              "role_sec": round(sum(b - a for a, b in spans), 1)}
            if abs(d) >= ROLE_PITCH_SEMI:
                role = True
                why.append(f"R2: 역할 구간 {len(spans)}개 피치 {d:+.1f}반음(나레 {pn['f0_median_hz']}Hz→역할 {pd['f0_median_hz']}Hz)")
            else:
                why.append(f"역할 줄 {len(spans)}구간 있으나 나레와 같은 목소리(피치 {d:+.1f}반음)")
        else:
            ev["R2_pitch"] = {"failed": "mp4 없음" if x is None else "유성음 프레임 20개 미만"}
            why.append("역할 줄은 있으나 피치 못 잼")
    elif jl and not spans:
        why.append(f"judge 역할 줄 {len(jl)}개가 말소리에 안 맞음(자막에만 있는 대사로 봄)")
    source = bool(src or amb_src)
    ev["source_audio_kept"] = source
    if role:
        style = "역할극"
        if source:
            why.append("원음도 있음")
    elif source:
        style = "나레+원음"
        why.append(f"원음 구절 {len(src)}개" + (f", 현장음 '{amb}'" if amb_src else ""))
    else:
        style = "나레만"
        why.append(f"한국어 화자 {len(ko_spk)}명, 원음 구절 0·현장음 없음")
    return {"style": style, "reason": " / ".join(why), "evidence": ev, "sources": used}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="쉼표로 묶은 id 목록(-로 시작하는 id 때문에 쉼표 형식)")
    ap.add_argument("--no-measure", action="store_true")
    A = ap.parse_args()
    A.only = [x.strip() for x in A.only.split(',') if x.strip()] if A.only else None
    OUT.mkdir(parents=True, exist_ok=True)
    top = _j(TOP50)
    rows = []
    for rank, t in enumerate(top, 1):
        vid = t["id"]
        f = OUT / f"{vid}.json"
        old = _j(f) or {}
        j = _j(RAW / "judge" / f"{vid}.json") or {}
        words = sm_words(vid)
        used = ["A:judge(1차 10-15)", "A:스피치매틱스 asr(1차 10-15)"]
        m = eng3(vid)
        if m:
            used.append("B:뜯기 3판(10-16)")
        else:
            m = old.get("measure")
            only_hit = bool(A.only) and vid in A.only
            # 기존 자료만으로 자막만이면 새로 안 잰다
            pre = classify(vid, j, words, None, used)
            stale = (not m or m.get("failed") or ((m.get("audio") or {}).get("composition") or {}).get("failed"))
            if not A.no_measure and pre["style"] != "자막만" and (only_hit or (not A.only and stale)):
                print(f"[{rank}/50] {vid} 새로 잼", flush=True)
                m = measure_new(vid)
            if m and not m.get("failed"):
                used.append(f"C:새 받아쓰기({m.get('measured_at')}, {((m.get('audio') or {}).get('transcript') or {}).get('model')})")
        c = classify(vid, j, words, m, used)
        rec = {"id": vid, "rank": rank, "views": t["views"], "title": t.get("title", ""), "version": VERSION,
               "known": KNOWN.get(vid), "classify": c, "measure": m if (m and "from" not in m) else ({"from": m["from"]} if m else None)}
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        rows.append(rec)
        print(f"  {rank:2d} {vid} → {c['style']} | {c['reason'][:110]}", flush=True)
    write_report(rows)


def write_report(rows: list[dict]) -> None:
    summ = []
    for s in STYLES + ["미분류"]:
        rs = sorted([r for r in rows if r["classify"]["style"] == s], key=lambda r: -r["views"])
        v = [r["views"] for r in rs]
        summ.append({"style": s, "n": len(rs), "views_median": int(st.median(v)) if v else None, "views_max": v[0] if v else None,
                     "ids": [r["id"] for r in rs], "top3": [{"id": r["id"], "views": r["views"], "title": r["title"][:40]} for r in rs[:3]]})
    check = [{"id": k, "want": w, "got": next((r["classify"]["style"] for r in rows if r["id"] == k), None)} for k, w in KNOWN.items()]
    J = {"version": VERSION, "made_at": time.strftime("%Y-%m-%d %H:%M"), "n": len(rows), "styles": summ, "known_check": check,
         "rules": {"ROLE_PROMPT_EXTRA": ROLE_PROMPT_EXTRA, "ROLE_PITCH_SEMI": ROLE_PITCH_SEMI, "ALIGN_MIN": ALIGN_MIN},
         "rows": [{"rank": r["rank"], "id": r["id"], "views": r["views"], "style": r["classify"]["style"], "reason": r["classify"]["reason"],
                   "sources": r["classify"]["sources"], "title": r["title"]} for r in rows]}
    (HERE / "스타일_전수분류.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# 썰풀다(도파민썰템 벤치) 상위 50편 — 소리·화자 구성 스타일 전수 분류", "",
         f"- 만든 때 {J['made_at']} · `{VERSION}` · 다시 돌리기: `PYTHONUTF8=1 py channel/sseolpulda/style_classify.py`",
         "- 판정 규칙·보정 근거: `channel/sseolpulda/style_classify.py` 머리말. 편별 원자료: `C:/숏템_칼카피/sseolpulda/style50/<id>.json`",
         "- 자료 표기: A = 1차(10-15) judge·스피치매틱스, B = 뜯기 3판(10-16), C = 이번에 새로 잰 제미나이 무료 받아쓰기", "",
         "## 스타일별", "", "| 스타일 | 편수 | 조회 중앙값 | 최대 | 대표 3편 |", "|---|---:|---:|---:|---|"]
    for s in summ:
        if s["n"]:
            L.append(f"| {s['style']} | {s['n']} | {s['views_median']:,} | {s['views_max']:,} | "
                     + " · ".join(f"{t['id']}({t['views']:,})" for t in s["top3"]) + " |")
        else:
            L.append(f"| {s['style']} | 0 | - | - | - |")
    L += ["", "## 사람이 아는 편 대조", "", "| id | 정답 | 판정 | 맞음 |", "|---|---|---|---|"]
    L += [f"| {c['id']} | {c['want']} | {c['got']} | {'O' if c['want'] == c['got'] else 'X'} |" for c in check]
    L += ["", "## 50편 전체", "", "| 순위 | id | 조회 | 스타일 | 판정 자료 | 근거 | 제목 |", "|---:|---|---:|---|---|---|---|"]
    for r in J["rows"]:
        src = ",".join(s.split(":")[0] for s in r["sources"])
        L.append(f"| {r['rank']} | {r['id']} | {r['views']:,} | {r['style']} | {src} | {r['reason'].replace('|', '/')[:140]} | "
                 f"{r['title'][:30].replace('|', '/')} |")
    # 근거 세기 — 사장님이 짚을 곳을 먼저 드러낸다
    weak = []
    for r in rows:
        c, e = r["classify"], r["classify"].get("evidence") or {}
        p2 = (e.get("R2_pitch") or {}).get("diff_semi")
        if c["style"] == "역할극" and (p2 is None or abs(p2) < ROLE_PITCH_SEMI):
            weak.append(f"- {r['id']} 역할극 — 제미나이 화자 분리만 근거(피치 차 {p2}반음 < {ROLE_PITCH_SEMI}; 비슷한 높이의 다른 목소리면 피치로 못 가름)")
        if c["style"] == "나레+원음" and not e.get("n_source"):
            weak.append(f"- {r['id']} 나레+원음 — 원음 말소리 구절 0, 제미나이 현장음 설명('{e.get('ambient')}')만 근거")
        if "충돌" in c["reason"] or c["style"] == "미분류":
            weak.append(f"- {r['id']} {c['style']} — {c['reason']}")
        if "lite" in str(e.get("asr_model")):
            weak.append(f"- {r['id']} {c['style']} — 받아쓰기가 대체 모델({e.get('asr_model')}) 결과")
    J["weak"] = weak
    (HERE / "스타일_전수분류.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    i = L.index("## 50편 전체")
    L[i:i] = ["## 근거가 약한 편(귀로 확인할 후보)", ""] + (weak or ["- 없음"]) + [""]
    L += ref_section()
    (HERE / "스타일_전수분류.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("표:", {s["style"]: s["n"] for s in summ}, "\n대조:", check)


REF_DIR = BASE / "참고_hqGynmRWxpY"
REF_EYE = [  # sheet.jpg(컷마다 가운데 프레임 33장)를 눈으로 본 것 — 2026-10-17
    "33컷 전부 아래에 같은 출처 표기 '@capuanovincenzo', 같은 두 요리사·같은 주방, 반죽→소스→치즈→화덕→완성 한 과정 순서 → 원작 1편으로 보임"
    " (원작 계정의 여러 영상을 이어 붙였는지는 원본과 대조 안 함 — 미확인)",
    "화면 틀: 위 검정 띠에 노란 고정 제목 2줄('이탈리아인들이 환장하는 반죽'), 가운데 원작 영상, 아래 출처 표기",
    "자막 3종: ①흰 글자+검정 외곽선 = 한국어 나레 자막 ②괄호 작은 글자 = 원음 속 말·몸짓 의역('(이렇게 하란 말이야)'·'(드루와 드루와)')"
    " ③노랑·초록 글자 = 원음 대사 번역('나폴리 전통 치즈 프로볼라~'·'가자! 화덕으로!'·'그건 미국식이고')",
]


def ref_section() -> list[str]:
    R, meta = _j(REF_DIR / "뜯기" / "뜯기.json"), _j(REF_DIR / "meta.json")
    if not R or not meta:
        return ["", "## 참고 영상 hqGynmRWxpY", "", "- 아직 안 잼"]
    a = R.get("audio") or {}
    c, tr, cu = a.get("composition") or {}, a.get("transcript") or {}, R.get("cuts") or {}
    segs = tr.get("segments") or []
    src = [x for x in segs if x["kind"] == "source" or x["lang"] in FOREIGN]
    ko = [x for x in segs if x["lang"] == "ko" and x["kind"] in ("narration", "dialog")]
    mats = (R.get("materials") or {}).get("share_by_count")
    L = ["", "## 참고 영상 — hqGynmRWxpY (사장님 '해외쇼츠 스타일' 참고, 썰풀다 50편 밖)", "",
         f"- 채널 **{meta.get('channel')}** ({meta.get('uploader_id')}) · 조회 {meta.get('view_count'):,} · 좋아요 {meta.get('like_count'):,} · "
         f"{meta.get('duration')}초 · 올린 날 {meta.get('upload_date')} · 제목 '{meta.get('title')}'",
         f"- 잰 길: 뜯기 전체 `tools/calcopy/engine/analyze.py`(엔진 {R.get('engine')}, {R.get('measured_at')}) → `{REF_DIR / '뜯기'}`",
         f"- 소리: 엔진 kind **{c.get('kind')}** · 원음 {c.get('source_audio_kept')} · 한국어 말 {len(ko)}구절 {tr.get('ko_speech_sec')}초 · "
         f"원음 말소리 {len(src)}구절({', '.join(sorted({x['lang'] for x in src}))}): " + " / ".join(x['text'] for x in src),
         "- 화자: " + ", ".join(f"{s_['n']} {s_['gender']}/{s_['voice_guess']} {s_['share']:.0%} {s_['kinds']}{s_['langs']}" for s_ in c.get("speakers") or [])
         + " → 한국어 나레 목소리 1명 + 원작 속 이탈리아어 말소리('짜잔' 1구절은 ko 로 적혔으나 S2=원작 화자)",
         f"- 컷: {(cu.get('bench') or {}).get('shots')}컷 · 컷 길이 중앙 {(cu.get('shot_len') or {}).get('median')}초 · 분당 {cu.get('cut_per_min')} · 첫 컷 {cu.get('first_cut')}초",
         f"- 제작법(컷마다 제미나이 판독): {mats}",
         f"- 자막: {(R.get('captions') or {}).get('n_spans')}개, 띠 y{(R.get('captions') or {}).get('region')}"]
    L += [f"- (눈) {t}" for t in REF_EYE]
    L += ["- **판정: 나레+원음** — 한국어 나레 1명 + 원작 원음(이탈리아어 대사)을 살림. 썰풀다 나레+원음 편들과 다른 점: "
          "원작 1편을 59초 통째로 따라가고(썰풀다 50편 길이 중앙 26.1초 — 1차 분석), 원음 대사를 번역·의역 자막(괄호·색 글자)으로 따로 보여준다. "
          "→ 4갈래 안에서는 '나레+원음'이지만 '원작 1편 따라가기 + 원음 대사 번역 자막'은 새 갈래 후보(가칭 '해외쇼츠 해설형')로 적어 둔다."]
    return L


if __name__ == "__main__":
    main()
