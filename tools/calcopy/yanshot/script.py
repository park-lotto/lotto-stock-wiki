# -*- coding: utf-8 -*-
"""③ 대본 — 판단 주인: script(B, T, W) (관제 097, 2026-10-17).

만템 결(channel/mantem/비교_만템_아이템홈_얜샷템1편.md §2·§3): 원음으로 열고 나레 2줄 —
  N1 "[인물]이 [수식] [제품 정체]이라는데"(첫 낱말 = 인물) · N2 마무리 "~라네요/~났네요".
무료 제미나이 1회(검사에 걸리면 고치기 1회 더). 검사 = script_engine 의 claim_off(최상급·단정)·spacing_off(띄어쓰기)·
number_ranges(범위 숫자) 재사용 + 이 채널 꼴(어미·글자 수·TTS 숫자/영문/기호 0·벤치 나레 3어절 연속 베끼기 0·제목 2줄 길이).
사실은 원본 받아쓰기·제목·설명란에서만(근거 없는 문장 금지), 공식 아닌 해석은 전언체.
"""
from __future__ import annotations

import re
from pathlib import Path

from tools.calcopy.yanshot.common import GEM_MODELS, StageError, jsave, norm, vtt_words

CPS = 8.4                   # 만템 나레 말속도(자/초)
PADS = 0.12 + 0.45          # N1 끝 쉼 + N2 끝 여유(정본 장윤정 NARR_PAD)
LINE_MIN, LINE_MAX = 16, 34  # 줄 글자(공백 뺌) — B17: 35자 넘는 문장은 TTS 말투가 바뀐다
TITLE_MAX = 12
CAP_MAX = 13                # A9 자막 조각
LEN_AIM = 0.93              # 완성 길이 목표 = 벤치 × 이것(B1 ±15% 안, 만템 결은 나레가 짧은 쪽)
N1_END = ("라는데", "이라는데", "다는데")
N2_END = ("라네요", "났네요", "다네요", "이라네요")


def narr_target(B: dict, T: dict) -> tuple[int, int]:
    """나레 두 줄 글자 목표(합) — 벤치 길이 − 원음 길이를 8.4자/초로. B1(길이 ±15%)을 지키려고 줄 글자를 여기서 정한다."""
    need = max(4.6, min(9.0, B["dur"] * LEN_AIM - T["orig_total"])) - PADS
    tot = int(round(need * CPS))
    lo = max(2 * LINE_MIN, tot - 6)
    hi = min(2 * LINE_MAX, tot + 4)
    return lo, hi


def bench_narration(B: dict, T: dict) -> str:
    """벤치 자막 중 지문이 안 맞은 낱말 = 벤치 채널의 나레(베끼기 검사용)."""
    spans = [(s["b0"] - 0.05, s["b1"] + 0.3) for s in T["fingerprint"]]
    return " ".join(w for t, w in vtt_words(B["vtt"]) if w != ">>" and not any(a <= t <= b for a, b in spans))


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def transcript_excerpt(T: dict, keywords: list[str], max_chars: int = 2600) -> str:
    """원본 받아쓰기 발췌 — 원음 블록 ±45초 + 제품 낱말이 든 줄. 줄 머리에 [분:초]."""
    words = vtt_words(T["source"]["vtt"])
    kws = [norm(k) for k in keywords if norm(k)]
    lines, cur, t0 = [], [], None
    for t, w in words:
        if t0 is None:
            t0 = t
        cur.append(w)
        if re.search(r"[.?!]$", w) or len(cur) >= 14:
            lines.append((t0, " ".join(cur))); cur, t0 = [], None
    if cur:
        lines.append((t0, " ".join(cur)))
    near = [(o["spans"][0][0] - 45, o["spans"][-1][1] + 45) for o in T["orig"]]
    pick = [(t, s) for t, s in lines if any(a <= t <= b for a, b in near) or any(k in norm(s) for k in kws)]
    out, n = [], 0
    for t, s in pick:
        row = f"[{_mmss(t)}] {s}"
        if n + len(row) > max_chars:
            break
        out.append(row); n += len(row)
    return "\n".join(out)


PROMPT = """너는 한국 유튜브 쇼츠 채널 '얜샷템'(연예인 쇼핑템) 나레이션 작가다. 아래 원본 영상(연예인 본인 채널)에서 연예인 말(원음)을 그대로 쓰고,
그 사이에 우리 나레이션 2줄만 넣는다. 영상 짜임: 원음 → N1 → 원음 … → N2(끝).

[인물] {person}  [제품] {product}  [브랜드] {brand}
[원본] {src_channel} 「{src_title}」 ({src_date})
[원본 설명란] {src_desc}
[원음으로 쓰는 말(본인 말 그대로, 나레에서 되풀이 금지)]
{orig}
[원본 받아쓰기 발췌 — 사실은 여기·제목·설명란에서만]
{excerpt}
[경쟁 채널 나레(베끼지 말 것 — 같은 어절 3개 연속 금지)] {bench_narr}

규칙:
- N1: 첫 낱말이 인물 이름("{person}이/가 …"), 꼴 "[인물]이 [수식] [제품 정체]이라는데" — 끝은 '라는데' 또는 '다는데'.
- N2: 마무리 한 줄, 끝은 '라네요' 또는 '다네요'(전언). 원음에서 안 나온 디테일(어디서·왜·어떻게 쓰나)을 근거로.
- ★글자 수(공백 뺀 TTS 글): N1 약 {n1}자, N2 약 {n2}자(합 {lo}~{hi}자, 한 줄 {lmin}~{lmax}자). 영상 길이가 이 글자 수로 정해지니 꼭 지켜라.
- text = 화면 자막용(쉼표로 끊어 읽기 조각 표시, 조각마다 13자 이하). tts = 읽는 글: 숫자·영문·기호·약어 금지(소리 나는 대로 한글로, 예 '1kg'→'일 킬로'), 조사·어미를 빼지 말고 말하듯.
- 근거 없는 사실·최상급(가장·최초·유일·역대급·1위·품절·대란)·숫자 단정 금지. 공식 발표가 아닌 해석은 '~라는데/~라네요' 전언.
- facts: 줄마다 기댄 근거 번호. 근거 글은 원본에서 그대로 옮기고 [분:초] 를 붙인다.
- title: 화면 위 2줄 제목 — 1줄 인물·상황(흰), 2줄 제품(민트), 줄마다 {tmax}자 이하. 경쟁 채널 제목 「{bench_title}」과 다른 말.
- desc: 설명란 첫 2줄(무엇을 왜 소개하나, 사실만).
JSON만:
{{"title":["",""],"N1":{{"text":"","tts":"","facts":["f1"]}},"N2":{{"text":"","tts":"","facts":["f2"]}},
 "facts":{{"f1":{{"text":"","at":"분:초"}}}},"desc":""}}"""

FIX = """\n\n[직전 답]\n{prev}\n[검사에 걸린 것 — 이것만 고쳐서 같은 JSON 으로 다시]\n{bad}"""


def _tts_len(s: str) -> int:
    return len(re.sub(r"[\s.,!?~…'\"“”‘’]", "", s or ""))


def checks(D: dict, B: dict, bench_narr: str, lo: int, hi: int) -> dict:
    """(판단 주인) 이 채널 대본 검사 — 빈 dict = 통과. 엔진 검사(claim_off·spacing_off·number_ranges)는 부르기만."""
    from tools.calcopy.engine import script_engine as se
    bad: dict = {}
    facts = {k: {"text": (v or {}).get("text", "") if isinstance(v, dict) else str(v)} for k, v in (D.get("facts") or {}).items()}
    lines = []
    for key, ends in (("N1", N1_END), ("N2", N2_END)):
        L = D.get(key) or {}
        t, tts = (L.get("text") or "").strip(), (L.get("tts") or "").strip()
        lines.append({"text": t, "facts": L.get("facts") or []})
        why = []
        if not t or not tts:
            why.append("빈 줄")
        core = re.sub(r"[.!?~\s]+$", "", tts)
        if not core.endswith(ends):
            why.append(f"끝 어미 {ends} 아님")
        n = _tts_len(tts)
        if not LINE_MIN <= n <= LINE_MAX:
            why.append(f"TTS {n}자(한 줄 {LINE_MIN}~{LINE_MAX})")
        if re.search(r"[0-9A-Za-z%&+/#@*()\[\]]", tts):
            why.append("TTS 에 숫자·영문·기호(A11)")
        if key == "N1" and B.get("person") and not norm(tts).startswith(norm(B["person"])):
            why.append("첫 낱말이 인물 이름이 아님")
        miss = [f for f in (L.get("facts") or []) if f not in facts]
        if not (L.get("facts")) or miss:
            why.append(f"근거 번호 없음/모름 {miss}")
        bw = bench_narr.split()
        tw = re.sub(r"[,.!?]", "", t).split()
        for i in range(len(tw) - 2):
            if " ".join(tw[i:i + 3]) in " ".join(bw):
                why.append(f"벤치 나레 베낌 '{' '.join(tw[i:i + 3])}'"); break
        if why:
            bad[key] = why
    tot = sum(_tts_len((D.get(k) or {}).get("tts")) for k in ("N1", "N2"))
    if not lo <= tot <= hi:
        bad["합"] = [f"두 줄 TTS {tot}자(목표 {lo}~{hi} — 벤치 길이 맞춤)"]
    bench_pts = {"points": {}}
    for k, v in se.claim_off(lines, facts, bench_pts).items():
        bad.setdefault(("N1", "N2")[k], []).append(f"근거 없는 최상급·단정 {v}")
    for k, v in se.spacing_off([l["text"] for l in lines], facts).items():
        bad.setdefault(("N1", "N2")[k], []).append(f"띄어쓰기 {v}")
    for k, v in se.number_ranges([l["text"] for l in lines], facts).items():
        bad.setdefault(("N1", "N2")[k], []).append(f"범위 숫자 한쪽만 {v}")
    tl = D.get("title") or []
    if len(tl) != 2 or any(not x or len(x.replace(" ", "")) > TITLE_MAX for x in tl):
        bad["title"] = [f"제목 2줄·줄마다 {TITLE_MAX}자 이하 아님: {tl}"]
    return bad


def caps_of(text: str) -> list[str]:
    """화면 자막 조각 — 쉼표에서 끊고, 13자 넘으면 chunk_sentence 로 더 끊는다."""
    from tools.calcopy import narr_video as nv
    out = []
    for c in [x.strip() for x in text.split(",") if x.strip()]:
        c = c.rstrip(".")
        out += [c] if len(c.replace(" ", "")) <= CAP_MAX else nv.chunk_sentence(c, 11)
    return out


def script(B: dict, T: dict, W: Path, ask=None, log=print) -> dict:
    """(판단 주인) 나레 2줄·제목·근거 → W/script.json."""
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    lo, hi = narr_target(B, T)
    bn = bench_narration(B, T)
    src = T["source"]
    orig = "\n".join(f"- {o['id']} [{_mmss(o['spans'][0][0])}] {o['said']}" for o in T["orig"])
    p = PROMPT.format(person=B.get("person"), product=B.get("product"), brand=B.get("brand") or "-", src_channel=src["channel"],
                      src_title=src["title"], src_date=src.get("upload"), src_desc=(src.get("description") or "")[:600].replace("\n", " "),
                      orig=orig, excerpt=transcript_excerpt(T, B.get("keywords") or [B.get("product") or ""]), bench_narr=bn[:300],
                      lo=lo, hi=hi, n1=(lo + hi) // 4, n2=(lo + hi) // 2 - (lo + hi) // 4, lmin=LINE_MIN, lmax=LINE_MAX, tmax=TITLE_MAX, bench_title=B.get("screen_title", "").replace("\n", " / "))
    models = GEM_MODELS
    calls, D, bad = 0, None, None
    prev = ""
    for attempt in range(2):
        prompt = p if attempt == 0 else p + FIX.format(prev=prev, bad="\n".join(f"- {k}: {'; '.join(v)}" for k, v in bad.items()))
        D, why = ask([], prompt, tag=f"yanshot_script_{attempt}", models=models)
        calls += 1
        if D is None:
            raise StageError(f"대본 제미나이 실패: {why}")
        bad = checks(D, B, bn, lo, hi)
        log(f"[script] 시도 {attempt + 1}({D.get('_model')}): N1 '{(D.get('N1') or {}).get('tts')}' · N2 '{(D.get('N2') or {}).get('tts')}' · 걸림 {bad or '없음'}")
        if not bad:
            break
        import json as _j
        prev = _j.dumps({k: D.get(k) for k in ("title", "N1", "N2", "facts")}, ensure_ascii=False)
    if bad:
        jsave(W / "script_fail.json", {"draft": D, "bad": bad})
        raise StageError(f"대본 검사 2회 실패 — {bad} (script_fail.json)")
    S = {"title": D["title"], "desc": D.get("desc") or "", "facts": D["facts"], "bench_narration": bn, "target_chars": [lo, hi], "calls": calls,
         "model": D.get("_model"),
         "lines": [{"id": k, "text": D[k]["text"].strip(), "tts": D[k]["tts"].strip(), "facts": D[k]["facts"], "caps": caps_of(D[k]["text"]),
                    "chars": _tts_len(D[k]["tts"])} for k in ("N1", "N2")]}
    jsave(W / "script.json", S)
    return S


def write_grounds(B: dict, T: dict, S: dict, out: Path):
    """근거.md — 줄마다 출처(원본 구간·받아쓰기)."""
    src = T["source"]
    rows = [f"# 근거 — 얜샷템 {B.get('person')} {B.get('product')} (벤치 {B['id']} {B.get('channel')})", "",
            f"원본: {src['channel']} 「{src['title']}」 {src['url']} (업로드 {src.get('upload')}, {src.get('res')})",
            f"출처 표기: {(B.get('source_label') or {}).get('raw') or '(없음)'} ({(B.get('source_label') or {}).get('from')}) · 지문 맞은 글자 {T['score']}", "",
            "## 나레", "| 줄 | 화면 글 | 읽는 글 | 근거 |", "|---|---|---|---|"]
    for L in S["lines"]:
        g = " · ".join(f"{f}: {(S['facts'].get(f) or {}).get('text', '')} [{(S['facts'].get(f) or {}).get('at', '')}]" for f in L["facts"])
        rows.append(f"| {L['id']} | {L['text']} | {L['tts']} | {g} |")
    rows += ["", "## 원음(본인 말 — 원본 자동자막 낱말 시각 + 무음 경계, 확정 받아쓰기 1회)", "| 블록 | 원본 구간(초) | 말 | 확정 받아쓰기 덮음 | 원본 LUFS |", "|---|---|---|---|---|"]
    for o in T["orig"]:
        rows.append(f"| {o['id']} | {o['spans']} | {o['said']} | {o['asr_sim']} | {o['lufs']} |")
    for d in T.get("dropped") or []:
        rows.append(f"| 뺌 | {d.get('spans', [d.get('t0'), d.get('t1')])} | {d['said']} | {d['why']} | |")
    Path(out).write_text("\n".join(rows) + "\n", encoding="utf-8")
