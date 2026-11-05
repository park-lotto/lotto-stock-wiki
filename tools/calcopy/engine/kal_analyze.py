# -*- coding: utf-8 -*-
"""프리셋 채널 분석 도구 — 한 입구 (관제 097, 2026-10-20). 방법은 `tools/calcopy/칼카피_분석지침서.md`.

  frames   <mp4> --out <dir> [--y0 0 --y1 1920] [--fps 2] [--max-strips 80]
           2fps 시트 + 10fps 글자 띠 변화(견본 channel/starpickroom/_tools/sheets.py 그대로 부름) → change_<id>.json
           + 바뀌는 지점마다 0.1초 띠(±0.3초) strips/ + 판독목록.json  (판독은 사람 눈 — 이 도구는 볼 프레임만 고른다)
           + 30fps 픽셀 실측 seg_<id>.json(capseg 자막 띠)·cut_<id>.json(cutdet 컷)·segsheet_<id>_NN.jpg — engine/readline_tools (--no-readline 로 끔)
  skeleton <뜯기.json> [--vtt <id>.ko.vtt] --out 줄판독/<id>.json
  skeleton <frames 폴더> --spec <spec.py> --mp4 <원본> [--sfx-raw] [--profile] --out 줄판독/<id>.json   (눈 spec + 픽셀 실측 → readline_tools.build_lr)
           줄판독 뼈대: t0·t1·text 는 기계값(뜯기 OCR·vtt), 나머지 칸은 null(=눈으로 채움). _todo 가 남아 있으면 check 가 거절.
  check    <줄판독.json ...> [--strict]
           칸 누락·꾸밈 없는 줄 칸(enter/emph/sticker/sfx)·이름 근거(화면 글자)·시간 겹침·role 어휘. 오류 있으면 종료코드 1.
  rules    <줄판독 dir|json...> [--out 초안.md] [--json 결과.json]
           붙는 조건 규칙 + 빈도(분모 포함) — 화자별·자리(훅/본문/끝)별·역할별. 스타일분석.md §1 표 초안.
  match    --bench <줄판독 dir> --ours <자막표|줄판독.json> [--ours-mp4 final.mp4] [--bench-tteutgi <뜯기 dir>] [--out md]
           재현일치도: 우리 시험편을 벤치와 같은 자로(길이·컷 중앙·말속도·LUFS·효과 붙은 줄 비율·자리·조각 자수·표시 초·등장 최빈).

판단 주인(0순위-C): 규칙+빈도 = rules_of · 재현일치도 자·합격선 = MATCH_RULES + match_table · 칸 검사 = check_doc.
소리 도구(sfx_*·bgm_fp·voice_fp·narr_report)는 여기서 다루지 않는다(관제 235 세션이 engine/ 로 옮기는 중).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- 줄판독 칸 (지침서 §2 와 짝)
LINE_REQUIRED = ("t0", "t1", "speaker", "text", "layer", "enter", "emph", "sticker", "sfx", "scene", "cut_at")
LINE_STRICT = ("role", "y", "fill_hex", "fit", "transition", "motion", "confidence")   # transition·motion·confidence = 표준 §11 ⑩(06 이 채우는 칸을 검사가 봐야 미측정이 안 숨는다) · --strict 에서만 오류
STRICT_NONNULL = ("transition", "motion", "confidence")   # null 도 미측정으로 센다(표준 §11 ⑩ — transition null 이 숨었다)
DOC_REQUIRED = ("id", "dur", "title_lines", "source_label", "lines", "beats", "narr_share", "notes")
ROLE_VOCAB = ("훅", "다리", "고조", "공개", "증거", "반전", "질문", "답", "끝", "이음", "본문")
SPEAKER_RE = re.compile(r"^(나레|원음|제3자|불명|연예인|본인)")
NAME_RE = re.compile(r"^(?:원음|연예인|본인)\s*[:(（]\s*([^\s)）(（:·,—–/?]+)")   # 괄호·콜론 뒤 첫 낱말 = 이름(설명문은 note 로)
MIN_N = 5          # 규칙 후보로 쓰려면 분모 ≥5 (키치잇 효과음 '표본 3개라 규칙으로 안 씀' 과 같은 선)
HOOK_S = 3.0       # 훅 = 첫 3초(engine/rules.py HOOK_S 와 같다)
END_FRAC = 0.85    # 끝 = 길이 85% 이후(engine/rules.py END_FRAC)


def _sp(speaker) -> str:
    s = (speaker or "").strip()
    if s.startswith("나레") or s in ("narr", "tts"):   # 공용 렌더러(render_bench) 자막표 = narr/orig
        return "나레"
    if s.startswith(("원음", "연예인", "본인")) or s == "orig":
        return "원음"
    if s.startswith("제3자"):
        return "제3자"
    return "불명"


def _chars(t: str) -> int:
    return len(re.sub(r"\s+", "", t or ""))


def _has(v) -> bool:
    return bool(v) if not isinstance(v, str) else bool(v.strip())


ENTER_VOCAB = ("instant", "append", "typing", "pop", "glitch", "wipe", "slide", "rainbow", "fade", "shake", "기타")   # append = 쌓기(렌더는 cut 과 같지만 측정은 따로 — 표준 §11 ⑪)
_ENTER_KO = (("쌓기", "append"), ("쌓이", "append"), ("타이핑", "typing"), ("글리치", "glitch"), ("rgb", "glitch"), ("무지개", "rainbow"), ("색 순환", "rainbow"), ("색순환", "rainbow"),
             ("와이프", "wipe"), ("닦아", "wipe"), ("슬라이드", "slide"), ("팝", "pop"), ("확대", "pop"), ("커진", "pop"), ("페이드", "fade"),
             ("흔들", "shake"), ("한 번에", "instant"), ("즉시", "instant"), ("컷인", "instant"))


def enter_key(v) -> str:
    """등장 칸 어휘 정규화(한 곳) — 1판 줄판독의 자유 서술('기타: RGB분리 글리치 입장…')을 ENTER_VOCAB 으로 접는다.
    'instant(타이핑 아님) + 스티커' 처럼 instant 가 앞머리면 instant. 못 접으면 '기타'."""
    if v is None:
        return "instant"
    s = str(v).strip()
    head = re.split(r"[\s(（:+·]", s, 1)[0].lower()
    if head in ENTER_VOCAB and head != "기타":
        return head
    if head == "cut":
        return "instant"
    low = s.lower().replace("타이핑 아님", "").replace("타이핑 없음", "")
    for en_key, en in (("typ", "typing"), ("glitch", "glitch"), ("wipe", "wipe"), ("slide", "slide"), ("rainbow", "rainbow"), ("fade", "fade"), ("shake", "shake"), ("pop", "pop")):
        if en_key in head:                      # 자막팩 키(sprTypeGlow·typeFlash·rgbGlitch…)
            return en
    for ko, en in _ENTER_KO:
        if ko in low:
            return en
    return "기타"


VARIANT_FX = ("빨강", "팝", "글리치", "hook", "pop", "glitch")   # 꾸밈인 자막 변형(훅 빨강·팝+글리치) — 벤치 줄판독 한국어 서술·우리 자막표 변형 키 둘 다(15 ⓑ, 10-25)
VARIANT_NOT = ("썸네일",)                                         # 0~2프레임 표지 카드 = thumb.frame0 칸이 잰다(자막 꾸밈 아님)


def variant_fx(v) -> bool:
    s = str(v or "").strip().lower()
    return bool(s) and not s.startswith(VARIANT_NOT) and any(k in s for k in VARIANT_FX)


EMPH_PLAIN_DE = 10.0      # 강조 낱말 색 ↔ 줄 채움색 ΔE76 이 이보다 작으면 '색 아닌 강조'(크기·굵기·밑줄·움직임) — 표준 §11-4 ㉙


def emph_kind(l: dict) -> str | None:
    """강조 종류(한 곳): 'color'(강조색이 줄 채움색과 ΔE ≥ 10) · 'plain'(색 아닌 강조 — ΔE < 10 또는 색을 안 바꿈) · None(강조 없음·줄색 모름)."""
    em = [e for e in (l.get("emph") or []) if e]
    if not em:
        return None
    fill = l.get("fill_hex")
    if not (isinstance(fill, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", fill)):
        return None
    import numpy as np
    f = _lab([int(fill[i:i + 2], 16) for i in (1, 3, 5)])
    des = []
    for e in em:
        h = e.get("hex") if isinstance(e, dict) else None
        if isinstance(h, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", h):
            des.append(float(np.linalg.norm(_lab([int(h[i:i + 2], 16) for i in (1, 3, 5)]) - f)))
    return "color" if any(d >= EMPH_PLAIN_DE for d in des) else "plain"


def _decorated(l: dict) -> dict:
    """줄 하나의 꾸밈 유무 — 분모 계산의 기준(한 곳). variant = 훅 빨강·팝 같은 변형(기본·기본(흰/노랑)·손글씨는 꾸밈 아님)."""
    enter = enter_key(l.get("enter"))
    return {"enter_fx": enter not in ("instant", "append", "cut", None), "emph": _has(l.get("emph")),   # append(쌓기)는 꾸밈이 아니라 등장 방식 — 비율은 enter 로 따로 센다
            "sticker": _has(l.get("sticker")), "sfx": _has(l.get("sfx")), "variant": variant_fx(l.get("variant")),
            "emph_color": emph_kind(l) == "color", "emph_plain": emph_kind(l) == "plain"}   # emph 의 갈래(색 강조 / 색 아닌 강조, ㉙) — any 는 emph 가 이미 센다


def _pos(l: dict, dur: float) -> str:
    mid = ((l.get("t0") or 0) + (l.get("t1") or 0)) / 2
    if mid < HOOK_S:
        return "훅"
    if dur and mid >= dur * END_FRAC:
        return "끝"
    return "본문"


# ---------------------------------------------------------------- check
def check_doc(d: dict, strict: bool = False) -> dict:
    """줄판독 json 한 편 검사 → {"errors": [...], "warnings": [...]}."""
    errs, warns = [], []
    for k in DOC_REQUIRED:
        if k not in d:
            errs.append(f"문서 칸 누락: {k}")
    if d.get("_todo"):
        errs.append(f"미기입 칸 남음(_todo): {d['_todo'][:3]}…" if len(d["_todo"]) > 3 else f"미기입 칸 남음(_todo): {d['_todo']}")
    lines = d.get("lines") or []
    if not lines:
        errs.append("lines 비어 있음")
    dur = float(d.get("dur") or 0)
    # 화면 글자 = 제목·출처·본문·메모·name_evidence 에 있는 글
    screen = " ".join([*(t.get("text", "") if isinstance(t, dict) else str(t) for t in d.get("title_lines") or []),
                       str(d.get("source_label") or ""), *(str(l.get("text") or "") for l in lines),
                       *(str(n) for n in d.get("notes") or []), *(str(n) for n in d.get("name_evidence") or [])])
    by_layer = defaultdict(list)
    for i, l in enumerate(lines):
        tag = f"줄{i}({l.get('t0')}~{l.get('t1')})"
        for k in LINE_REQUIRED:
            if k not in l:
                errs.append(f"{tag} 칸 누락: {k}" + (" — 꾸밈 없는 줄도 enter/emph/sticker/sfx 를 적어야 분모가 선다" if k in ("enter", "emph", "sticker", "sfx") else ""))
        for k in LINE_STRICT:
            if k not in l:
                (errs if strict else warns).append(f"{tag} 칸 누락(strict): {k}")
            elif l[k] is None and k in STRICT_NONNULL:
                (errs if strict else warns).append(f"{tag} 칸 비어 있음(strict): {k} — 없으면 'none'(전환 없음)·값을 적는다")
        t0, t1 = l.get("t0"), l.get("t1")
        if isinstance(t0, (int, float)) and isinstance(t1, (int, float)):
            if t1 <= t0:
                errs.append(f"{tag} t1 ≤ t0")
            if dur and t1 > dur + 0.15:
                errs.append(f"{tag} t1 {t1} > dur {dur}")
            by_layer[l.get("layer") or "채널"].append((t0, t1, i))
        sp = l.get("speaker")
        if sp is None:
            errs.append(f"{tag} speaker 미기입")
        elif not SPEAKER_RE.match(str(sp)):
            errs.append(f"{tag} speaker 어휘 밖: {sp!r} (나레|원음:<이름>|제3자|불명)")
        else:
            m = NAME_RE.match(str(sp))
            if m and m.group(1) not in screen:
                errs.append(f"{tag} 이름 근거 없음: '{m.group(1)}' 가 화면 글자(제목·출처·자막·notes·name_evidence)에 없다 → '불명' 또는 근거 추가")
        if "role" in l and l["role"] is not None and str(l["role"]).split("·")[0] not in ROLE_VOCAB:
            errs.append(f"{tag} role 어휘 밖: {l['role']!r} ({'|'.join(ROLE_VOCAB)})")
        if l.get("enter") is None and "enter" in l:
            errs.append(f"{tag} enter 미기입(꾸밈 없으면 'instant')")
        if l.get("emph") is None or l.get("sticker") is None:
            if "emph" in l or "sticker" in l:
                errs.append(f"{tag} emph/sticker 는 null 말고 [] (없음도 분모)")
    for layer, segs in by_layer.items():
        if "원본" in str(layer):          # 원본 박힌 층은 자막+스티커가 겹칠 수 있다 — 벤치 자막(채널 층)만 한 줄 규칙
            continue
        segs.sort()
        for (a0, a1, i), (b0, b1, j) in zip(segs, segs[1:]):
            if b0 < a1 - 0.05:
                errs.append(f"줄{i}·줄{j} 시간 겹침({layer} 층 {a0}~{a1} / {b0}~{b1}) — 같은 층은 겹칠 수 없다")
    return {"errors": errs, "warnings": warns}


# ---------------------------------------------------------------- skeleton
def _vtt(path: str) -> list[dict]:
    out, t = [], None
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"(\d+):(\d+):(\d+)\.(\d+)\s*-->\s*(\d+):(\d+):(\d+)\.(\d+)", raw)
        if m:
            g = [int(x) for x in m.groups()]
            t = (g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000)
            continue
        if t and raw.strip() and not raw.startswith(("WEBVTT", "Kind:", "Language:")):
            txt = re.sub(r"<[^>]+>", "", raw).strip()
            if txt and (not out or out[-1]["text"] != txt):
                out.append({"t0": round(t[0], 2), "t1": round(t[1], 2), "text": txt})
    return out


LOUD_STEP_S = 0.25    # skeleton-01 원본 시간표 음량 열 간격(회원 2170: 0.25초 음량)


def loud_track(mp4: str, step: float = LOUD_STEP_S) -> list[float]:
    """(프로그램) 0.25초마다 RMS dB — 원본 시간표 음량 열(skeleton-01). 소리 읽기는 asr_local.pcm(16k) 한 곳."""
    from tools.calcopy.engine.asr_local import pcm, _db, SR
    a = pcm(mp4)
    n = max(1, int(SR * step))
    return [round(_db(a[i:i + n]), 1) for i in range(0, len(a), n)]


def skeleton(vid: str, tteutgi: dict, vtt: str | None = None, loud: list | None = None) -> dict:
    """줄판독 뼈대 — 기계값만 채우고 눈으로 볼 칸은 null. check 가 _todo 로 거절한다.
    skeleton-01: 받아쓰기 낱말 시각(뜯기 audio.transcript.words — tear_llm 스피치매틱스)을 줄마다 words 열로, loud(0.25초 RMS dB, loud_track)를 줄 구간 loud 열로."""
    pr = tteutgi.get("probe") or {}
    lay = tteutgi.get("layout") or {}
    items = (tteutgi.get("captions") or {}).get("items") or []
    cuts = [float(c) for c in (tteutgi.get("cuts") or {}).get("times") or []]
    asr = _vtt(vtt) if vtt else []
    words = [w for w in (((tteutgi.get("audio") or {}).get("transcript") or {}).get("words") or []) if isinstance(w, dict)]
    lines = []
    for it in items:
        t0, t1 = float(it.get("t0", 0)), float(it.get("t1", 0))
        text = " ".join(it.get("text") or []) if isinstance(it.get("text"), list) else str(it.get("text") or "")
        near = [a["text"] for a in asr if a["t0"] < t1 and a["t1"] > t0]
        lines.append({"t0": t0, "t1": t1, "speaker": None, "text": text, "layer": None, "role": None,
                      "enter": None, "y": [it.get("top_y"), None] if it.get("top_y") else None, "fill_hex": None,
                      "emph": [], "sticker": [], "sfx": None, "scene": None, "fit": None,
                      "cut_at": [round(c, 2) for c in cuts if cut_in_line(c, t0, t1)],
                      "words": [{"t0": round(float(w["start"]), 2), "t1": round(float(w["end"]), 2), "text": w.get("text")} for w in words
                                if float(w["start"]) < t1 and float(w["end"]) > t0],
                      "loud": loud[int(t0 / LOUD_STEP_S):max(int(t0 / LOUD_STEP_S) + 1, int(t1 / LOUD_STEP_S))] if loud else None,
                      "_asr": near, "_src": "뜯기 OCR(기계값 — 눈으로 확인)"})
    todo = ["speaker", "layer", "role", "enter", "fill_hex", "emph", "sticker", "sfx", "scene", "fit", "beats", "narr_share", "form"]
    return {"id": vid, "dur": pr.get("duration"), "fps": pr.get("fps"), "size": [pr.get("w"), pr.get("h")],
            "title_lines": [], "source_label": None, "form": None, "_form_vocab": "형식(유형) 한 낱말 — 예 리액션·랭킹·사연·정보·리뷰(rules-05, 형식별 집계)",
            "layout": {"window": lay.get("window"), "caption_band": lay.get("caption_band"), "title_y": None, "source_y": None, "logo_y": None, "watermark": None},
            "lines": lines, "beats": None, "narr_share": None, "notes": [], "name_evidence": [],
            "_todo": todo, "_made_by": "kal_analyze.skeleton(기계값 뼈대 — 판독 전)"}


# ---------------------------------------------------------------- rules
def _norm_line(l: dict, dur: float) -> dict:
    d = _decorated(l)
    sp = _sp(l.get("speaker") or l.get("kind"))
    enter = enter_key(l.get("enter"))
    role = str(l.get("role")).split("·")[0] if l.get("role") else None
    return {"sp": sp, "enter": enter, "pos": _pos(l, dur), "role": role, "chars": _chars(l.get("text")),
            "sec": max(0.0, float(l.get("t1") or 0) - float(l.get("t0") or 0)), "any": any(d.values()), **d}


def rules_of(docs: list[dict]) -> dict:
    """(판단 주인) 줄판독 모음 → 붙는 조건 규칙 + 빈도. 분모를 항상 같이 낸다."""
    FX = ("enter_fx", "emph", "emph_color", "emph_plain", "sticker", "sfx", "variant")   # variant = 훅 빨강·팝 변형(15 ⓑ) · emph_color/plain = ㉙ 강조 갈래
    by_sp = defaultdict(lambda: {"n": 0, "enter": Counter(), "chars": [], "sec": [], **{k: 0 for k in FX}, "any": 0})
    by_pos = defaultdict(lambda: {"n": 0, "enter": Counter(), **{k: 0 for k in FX}, "any": 0})
    by_role = defaultdict(lambda: {"n": 0, "enter": Counter(), **{k: 0 for k in FX}, "any": 0})
    first_chunk = defaultdict(lambda: {"n": 0, "enter": Counter()})   # 화자 바뀐 첫 덩어리
    plain = {"n": 0, "denom": 0}
    eps = []
    beats = defaultdict(list)          # rules-09 역할별 첫 등장 %
    gaps = defaultdict(list)           # rules-09 같은 역할 반복 간격(초)
    tails = []                         # rules-09 마지막 말 줄 끝 → 영상 끝(초)
    by_layer = defaultdict(lambda: {"n": 0, "enter": Counter(), "hex": set(), "y": [], "repeat": 0})   # rules-18
    for d in docs:
        dur = float(d.get("dur") or 0)
        lines = [l for l in d.get("lines") or [] if (l.get("layer") or "채널") != "원본박힘"]
        N = [_norm_line(l, dur) for l in lines]
        prev = None
        for n in N:
            for tbl, key in ((by_sp, n["sp"]), (by_pos, n["pos"]), (by_role, n["role"] or "역할없음")):
                r = tbl[key]
                r["n"] += 1
                r["enter"][n["enter"]] += 1
                for k in FX:
                    r[k] += int(n[k])
                r["any"] += int(n["any"])
            by_sp[n["sp"]]["chars"].append(n["chars"])
            by_sp[n["sp"]]["sec"].append(n["sec"])
            if n["sp"] != prev:
                first_chunk[n["sp"]]["n"] += 1
                first_chunk[n["sp"]]["enter"][n["enter"]] += 1
            prev = n["sp"]
            plain["denom"] += 1
            plain["n"] += int(not n["any"])
        for role in BEAT_ROLES:
            ts = [float(l.get("t0") or 0) for l in lines if str(l.get("role") or "").split("·")[0] == role]
            if ts and dur:
                beats[role].append(round(ts[0] / dur * 100, 1))
                gaps[role] += [round(b - a, 2) for a, b in zip(ts, ts[1:])]
        spk = [l for l in lines if _sp(l.get("speaker")) in ("나레", "원음")]
        if spk and dur:
            tails.append(round(dur - max(float(l.get("t1") or 0) for l in spk), 2))
        main_lines = [l for l in lines if (l.get("layer") or "채널") == "채널"]
        for l in d.get("lines") or []:
            lay = str(l.get("layer") or "채널")
            r = by_layer[lay]
            r["n"] += 1
            r["enter"][enter_key(l.get("enter"))] += 1
            r["hex"].update(_hexes(l.get("fill_hex")))
            y = l.get("y")
            if isinstance(y, (list, tuple)) and y and isinstance(y[0], (int, float)):
                r["y"].append(y[0])
            if lay != "채널" and _repeats(l, main_lines):
                r["repeat"] += 1
        narr = [n for n in N if n["sp"] == "나레"]
        cuts = sorted({round(float(c), 2) for l in lines for c in (l.get("cut_at") or []) if isinstance(c, (int, float))})
        eps.append({"id": d.get("id"), "dur": dur, "form": d.get("form"), "lines": len(N), "narr_lines": len(narr),
                    "narr_sec": round(sum(n["sec"] for n in narr), 2), "speech_sec": round(sum(n["sec"] for n in N), 2),
                    "narr_share_lines": round(len(narr) / len(N), 3) if N else None,
                    "narr_share_dur": round(sum(n["sec"] for n in narr) / dur, 3) if dur and narr else (0.0 if dur else None),
                    "chunk_chars_med": statistics.median([n["chars"] for n in N]) if N else None,
                    "chunk_sec_med": round(statistics.median([n["sec"] for n in N]), 2) if N else None,
                    "fx_lines": sum(n["any"] for n in N), "cuts_marked": len(cuts),
                    "narr_cps": round(sum(n["chars"] for n in narr) / max(1e-6, sum(n["sec"] for n in narr)), 2) if narr else None})
    # 규칙 후보: 조건(화자/자리/역할/첫 덩어리) × 효과 → 비율·분모·등급
    rules = []
    base = {k: sum(v[k] for v in by_sp.values()) / max(1, sum(v["n"] for v in by_sp.values())) for k in FX}

    def grade(k, n):
        if n < MIN_N:
            return "표본부족"
        return "강" if k / n >= 0.6 else "중" if k / n >= 0.3 else "약"
    for cond_name, tbl in (("화자", by_sp), ("자리", by_pos), ("역할", by_role)):
        for key, r in tbl.items():
            if cond_name == "역할" and key == "역할없음":
                continue
            for e, c in r["enter"].items():
                rules.append({"cond": f"{cond_name}={key}", "effect": f"enter={e}", "k": c, "n": r["n"], "rate": round(c / r["n"], 2), "grade": grade(c, r["n"])})
            for k in FX:
                rules.append({"cond": f"{cond_name}={key}", "effect": k, "k": r[k], "n": r["n"], "rate": round(r[k] / r["n"], 2),
                              "base": round(base[k], 2), "grade": grade(r[k], r["n"])})
    for key, r in first_chunk.items():
        for e, c in r["enter"].items():
            rules.append({"cond": f"화자전환 첫 덩어리={key}", "effect": f"enter={e}", "k": c, "n": r["n"], "rate": round(c / r["n"], 2), "grade": grade(c, r["n"])})
    rules.sort(key=lambda x: (-x["n"], -x["rate"]))

    def fin(tbl):
        out = {}
        for k, r in tbl.items():
            o = {kk: (dict(vv) if isinstance(vv, Counter) else vv) for kk, vv in r.items() if kk not in ("chars", "sec")}
            if r.get("chars"):
                o["chars_med"] = statistics.median(r["chars"])
                o["sec_med"] = round(statistics.median(r["sec"]), 2)
                o["cps"] = round(sum(r["chars"]) / max(1e-6, sum(r["sec"])), 2)
            out[k] = o
        return out
    by_form = defaultdict(list)
    for e in eps:
        by_form[e.get("form") or "형식 미기입"].append(e["dur"])
    beat_pos = {r: {"n": len(v), "med_pct": statistics.median(v), "min_pct": min(v), "max_pct": max(v),
                    "gap_med_s": statistics.median(gaps[r]) if gaps[r] else None} for r, v in beats.items() if v}
    layers = {k: {"n": v["n"], "enter": dict(v["enter"]), "hex_kinds": len(v["hex"]), "y_med": statistics.median(v["y"]) if v["y"] else None,
                  "repeat_rate": round(v["repeat"] / v["n"], 2) if v["n"] and k != "채널" else None} for k, v in by_layer.items()}
    return {"n_docs": len(docs), "episodes": eps, "by_speaker": fin(by_sp), "by_pos": fin(by_pos), "by_role": fin(by_role),
            "by_form": {k: {"n": len(v), "min": min(v), "max": max(v)} for k, v in by_form.items()},
            "beat_pos": beat_pos, "tail_s": {"med": statistics.median(tails), "min": min(tails), "max": max(tails)} if tails else None,
            "by_layer": layers,
            "first_chunk": {k: {"n": v["n"], "enter": dict(v["enter"])} for k, v in first_chunk.items()},
            "plain": plain, "base_rate": {k: round(v, 2) for k, v in base.items()}, "rules": rules, "min_n": MIN_N}


BEAT_ROLES = ("반전", "공개", "고조", "끝")   # rules-09 박자 시점 % 를 재는 역할(ROLE_VOCAB 안)


def _repeats(l: dict, main_lines: list[dict]) -> bool:
    """rules-18: 다른 층 줄 글이 같은 시각 본 자막 줄 글을 되풀이하나(공백 뺀 글자 절반 이상 겹침)."""
    a = re.sub(r"\s", "", str(l.get("text") or ""))
    if len(a) < 2:
        return False
    t0, t1 = float(l.get("t0") or 0), float(l.get("t1") or 0)
    for m in main_lines:
        if float(m.get("t0") or 0) < t1 and float(m.get("t1") or 0) > t0:
            b = re.sub(r"\s", "", str(m.get("text") or ""))
            if b and sum(c in b for c in a) >= len(a) / 2:
                return True
    return False


def rules_md(R: dict, title: str = "") -> str:
    L = [f"# 붙는 조건 규칙+빈도 초안 {title}(kal_analyze rules, 편 {R['n_docs']})", "",
         "## 편 표", "| 편 | 길이 | 줄 | 나레 줄 | 나레 초/말 초 | 나레 줄 비율 | 나레 초/편 길이 | 조각 자수 중앙 | 조각 초 중앙 | 꾸밈 붙은 줄 | 나레 자/초 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in R["episodes"]:
        L.append(f"| {e['id']} | {e['dur']} | {e['lines']} | {e['narr_lines']} | {e['narr_sec']}/{e['speech_sec']} | {e['narr_share_lines']} | {e['narr_share_dur']} | {e['chunk_chars_med']} | {e['chunk_sec_med']} | {e['fx_lines']}/{e['lines']} | {e['narr_cps']} |")
    L += ["", f"꾸밈 없는 줄(enter instant·강조 0·스티커 0·효과음 0) = **{R['plain']['n']}/{R['plain']['denom']}**", "",
          "## 화자별", "| 화자 | 줄 | 등장(enter) | 강조 | 스티커 | 효과음 | 꾸밈 어느 하나 | 자수 중앙 | 초 중앙 | 자/초 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in R["by_speaker"].items():
        L.append(f"| {k} | {r['n']} | {', '.join(f'{a} {b}' for a, b in sorted(r['enter'].items(), key=lambda x: -x[1]))} | {r['emph']}/{r['n']} | {r['sticker']}/{r['n']} | {r['sfx']}/{r['n']} | {r['any']}/{r['n']} | {r.get('chars_med')} | {r.get('sec_med')} | {r.get('cps')} |")
    L += ["", "## 자리별(훅=첫 3초 · 끝=85% 이후)", "| 자리 | 줄 | 등장 | 강조 | 스티커 | 효과음 | 꾸밈 어느 하나 |", "|---|---|---|---|---|---|---|"]
    for k in ("훅", "본문", "끝"):
        r = R["by_pos"].get(k)
        if r:
            L.append(f"| {k} | {r['n']} | {', '.join(f'{a} {b}' for a, b in sorted(r['enter'].items(), key=lambda x: -x[1]))} | {r['emph']}/{r['n']} | {r['sticker']}/{r['n']} | {r['sfx']}/{r['n']} | {r['any']}/{r['n']} |")
    if any(k != "역할없음" for k in R["by_role"]):
        L += ["", "## 역할별", "| 역할 | 줄 | 등장 | 강조 | 스티커 | 효과음 |", "|---|---|---|---|---|---|"]
        for k, r in R["by_role"].items():
            L.append(f"| {k} | {r['n']} | {', '.join(f'{a} {b}' for a, b in sorted(r['enter'].items(), key=lambda x: -x[1]))} | {r['emph']}/{r['n']} | {r['sticker']}/{r['n']} | {r['sfx']}/{r['n']} |")
    else:
        L += ["", "(role 칸이 없어 역할별 표 없음 — 새 줄판독은 role 필수)"]
    L += ["", "## 화자 바뀐 첫 덩어리의 등장", "| 화자 | 첫 덩어리 수 | 등장 |", "|---|---|---|"]
    for k, r in R["first_chunk"].items():
        L.append(f"| {k} | {r['n']} | {', '.join(f'{a} {b}' for a, b in sorted(r['enter'].items(), key=lambda x: -x[1]))} |")
    L += ["", f"## 규칙 후보 (분모 ≥{R['min_n']} · 비율 ≥0.6 강 / ≥0.3 중 / 그 밑 약 · base = 전체 줄 평균)", "| 조건 | 효과 | k/n | 비율 | base | 등급 |", "|---|---|---|---|---|---|"]
    for c in R["rules"]:
        if c["k"] == 0 and c["grade"] != "표본부족":
            continue
        L.append(f"| {c['cond']} | {c['effect']} | {c['k']}/{c['n']} | {c['rate']} | {c.get('base', '')} | {c['grade']} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- match (재현일치도)
# (키, 자 종류, 허용폭, 기준인지(verdict 에 들어가나), 근거)
MATCH_RULES = [
    ("len.duration", "rel", 15, True, "길이 차 ≤15%(검수 B1·compare len.duration)"),
    ("cut.median", "rel_slow", 30, True, "컷 길이 중앙 ±30%, 벤치보다 빠르면 미달 쪽(검수 B4)"),
    ("speech.cps.나레", "rel", 10, True, "나레 말속도(자막 글자/표시 초) 차 ≤10%(compare speech.cps)"),
    ("chunk.chars", "rel", 15, True, "자막 조각 자수 중앙 차 ≤15%(검수 A9 범위)"),
    ("chunk.sec", "rel", 15, True, "자막당 표시 초 중앙 차 ≤15%(compare cap.sub_sec)"),
    ("enter.mode.나레", "eq", None, True, "나레 줄 등장 최빈 같음(compare cap.anim)"),
    ("enter.mode.원음", "eq", None, True, "원음 줄 등장 최빈 같음"),
    ("fx.rate.나레", "pctp", 20, True, "나레 줄 중 꾸밈 붙은 비율 차 ≤20%p(시작문서 §0-1 12-1 ④ '효과 붙은 줄 비율')"),
    ("fx.rate.원음", "pctp", 20, True, "원음 줄 중 꾸밈 붙은 비율 차 ≤20%p"),
    ("fx.pos", "pctp", 20, True, "꾸밈 붙은 줄의 자리(훅/본문/끝) 분포 칸마다 차 ≤20%p(compare sfx.after_event 와 같은 폭)"),
    ("plain.rate", "pctp", 20, True, "꾸밈 없는 줄 비율 차 ≤20%p('없는 것도 스타일')"),
    ("mix.lufs", "db", 1.5, False, "통합 LUFS 차 ≤1.5dB(검수 B2) — 하이브리드는 −14 통일이라 참고"),
    ("narr.share", "range", None, False, "나레 줄 비율이 벤치 min~max 안 — 하이브리드는 설계상 다름, 참고"),
    # ↓ 표준 §4-1 추가 칸(관제 263 지시서 04, 2026-10-24). 우리 쪽 값은 match_from_render 가 렌더 기록(자막표·시간표·썸네일)에서 채운다.
    ("transition.rate", "pctp", 20, True, "컷 전환 종류 분포(cut·flash·zoomblur·black·기타) 칸마다 차 ≤20%p(표준 §4-1 A1)"),
    ("sfx.rate", "rel0", 30, True, "효과음 발/초 차 ≤30%, 벤치 0이면 우리도 0(표준 §4-1 A2)"),
    ("sticker.rate", "pctp", 20, True, "스티커 붙은 줄 비율 차 ≤20%p(표준 §4-1 A3)"),
    ("meme.rate", "pctp", 20, True, "짤 화면 줄 비율 차 ≤20%p(표준 §4-1 A3 · 줄판독 screen/scene 에 '짤')"),
    ("thumb.frame0", "eq", None, True, "0초 첫 화면 종류(card=글 얹은 표지 2프레임 / scene=그냥 장면) 벤치 최빈과 같음(표준 §4-1 A6)"),
    # ↓ 개정안 kal v2(11-06) — 받아쓰기 자(asr_stats, 벤치 = 뜯기 transcript · 우리 = verify 가 우리 완성본을 뜯은 transcript). 우리 받아쓰기 실측이 쌓이기 전이라 참고.
    ("speech.cps.asr", "rel", 10, False, "말 구간 음절/초(받아쓰기 구절 글자 ÷ 말 구간 합) 차 ≤10%(readlines-09 — 자막 표시 초가 아닌 말 시각)"),
    ("speech.gap", "rel0", 50, False, "1.5초 넘는 말 빈틈 수 ±50%, 벤치 0이면 우리도 0(readlines-09)"),
    ("first.land", "db", 1.0, False, "첫 문장 착지 시각(받아쓰기 첫 문장 끝) 차 ≤1초(readlines-11)"),
    ("end.form", "eq", None, False, "끝맺음 꼴(end_form — 구독CTA·질문·예고·요약·쿠션·전언·감상·없음) = 벤치 최빈(rules-11)"),
    # ↓ 칼카피 엔진 v1 §7-3 R7 칸(관제 319 묶음①). 벤치 = 프리셋 r7.json summary(bm_tear 실측), 우리 = r7.media(완성본) — 같은 자가 있는 칸만 기준(Jev 해결 0.99·뿌리 0.57).
    #   R7 칸이 없는 판(벤치마킹 2판 프리셋이 아님 — 하이브리드 공용 렌더 등)은 'skip'(기준에서 빠짐, 사유 표시). seg(R1 구간)는 근거 Jev 미달이라 칸 없음.
    ("crop.x", "px", 60, True, "화면 상자 x 가운데 차 중앙 ≤60px(§7-3) — 짝 없는 클립형 = 벤치 쇼츠 화면 상자 분포 중앙과 대조(짝 대조 아님)"),
    ("end.sec", "abs", 0.5, True, "끝 검정 길이 차 ≤0.5초(§7-3 end, 같은 자 r7.media)"),
    ("caption.size", "rel", 15, False, "자막 글자 높이 ±15%(§7-3) — 우리 쪽 같은 자 없음이라 참고"),
    ("title.lines", "eq", None, False, "제목 줄 수 = 벤치 최빈(§7-3) — 우리 쪽 같은 자 없음이라 참고"),
]
R7_KEYS = ("crop.x", "end.sec", "caption.size", "title.lines")
# 업그레이드 판(base 있음)에서도 필수인 뼈대 칸 — 표준 §11 ③(페이블 10-25). 겉모양(바꿔도 됨) = framecmp·mix.lufs·narr.share·thumb.frame0·meme.rate·스티커 종류
MATCH_SKELETON = ("len.duration", "cut.median", "speech.cps.나레", "chunk.chars", "chunk.sec", "enter.mode.나레", "enter.mode.원음",
                  "fx.rate.나레", "fx.rate.원음", "fx.pos", "plain.rate", "sfx.rate", "transition.rate", "sticker.rate")
TRANS_VOCAB = ("cut", "flash", "zoomblur", "black", "기타")


def transition_key(v) -> str | None:
    """줄판독 transition 칸 어휘 정규화(한 곳). None·'none(같은 컷 안…)' = 전환 없음(None)."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s or s.startswith(("none", "없음", "-")):
        return None
    if s.startswith("cut") or s.startswith("컷"):
        return "cut"
    if any(k in s for k in ("flash", "흰", "번쩍", "white")):
        return "flash"
    if any(k in s for k in ("zoom", "blur", "줌", "블러")):
        return "zoomblur"
    if any(k in s for k in ("black", "검은", "검정", "암전")):
        return "black"
    return "기타"


def _is_meme(l: dict) -> bool:
    if l.get("meme"):
        return True
    return any("짤" in str(l.get(k) or "") for k in ("screen", "scene"))


def _sfx_n(l: dict) -> int:
    v = l.get("sfx")
    if isinstance(v, list):
        return len([x for x in v if x])
    return 1 if _has(v) else 0


def sfx_rate_p90(docs: list[dict]) -> tuple[float | None, list[float]]:
    """(판단 주인: 효과음 밀도 상한) 벤치 편별 발/초의 p90 — 배치(placement.sfx_step)가 지키고 검사(quality_gate.sfx_excess)가 잰다. 줄판독 없으면 None."""
    import numpy as np
    dens = [sum(_sfx_n(l) for l in d.get("lines") or []) / float(d["dur"]) for d in docs if d.get("dur")]
    return (float(np.percentile(dens, 90)), dens) if dens else (None, [])


def frame0_kind(d: dict) -> str | None:
    """줄판독 frame0(0초 첫 화면) → card(글 얹은 표지) / scene(그냥 장면). 칸 없으면 None(미측정)."""
    f0 = d.get("frame0")
    if not isinstance(f0, dict):
        return None
    return "card" if str(f0.get("text") or "").strip() else "scene"


def _ours_lines(o: dict) -> tuple[list[dict], float]:
    """우리 쪽 입력 = 줄판독 꼴(lines) 또는 자막표 꼴(rows: 스타픽룸형 speaker/emph list · 키치잇형 kind/emph str)."""
    if "lines" in o:
        return list(o["lines"]), float(o.get("dur") or 0)
    rows = []
    sfx_t = [float(s["t"]) for s in o.get("sfx_in_video") or [] if isinstance(s, dict) and s.get("t") is not None]
    for r in o.get("rows") or []:
        emph = r.get("emph")
        emph = [emph] if isinstance(emph, str) and emph else (emph or [])
        st = r.get("sticker") or []
        st = [st] if isinstance(st, (str, dict)) else st
        t0, t1 = float(r.get("t0") or 0), float(r.get("t1") or 0)
        rows.append({"t0": t0, "t1": t1, "speaker": r.get("speaker") or r.get("kind"), "text": r.get("text"),
                     "enter": r.get("enter") or "instant", "emph": emph, "sticker": st,
                     "sfx": next((f"{t}" for t in sfx_t if t0 <= t < t1), None), "role": r.get("role"), "layer": "채널", "variant": r.get("variant")})
    for c in o.get("cards") or []:      # 댓글카드 자막(render_bench frame.comment.track lines) — 줄판독의 카드 줄과 같은 칸(제3자·fade·꾸밈 없음)
        rows.append({"t0": float(c["t0"]), "t1": float(c["t1"]), "speaker": "제3자", "text": c["text"], "enter": "fade", "emph": [], "sticker": [],
                     "sfx": None, "role": None, "layer": "채널", "variant": None})
    for x in o.get("lyrics") or []:     # 가사 2줄(render_bench lyric_plan) — 줄판독 가사 줄과 같은 칸(즉시·일본어 줄 색 = 강조)
        rows.append({"t0": float(x["t0"]), "t1": float(x["t1"]), "speaker": "제3자", "text": f"{x['jp']} / {x['ko']}", "enter": "instant",
                     "emph": [{"word": x["jp"]}], "sticker": [], "sfx": None, "role": None, "layer": "채널·가사", "variant": None})
    rows.sort(key=lambda r: r["t0"])
    return rows, float(o.get("dur") or (max((r["t1"] for r in rows), default=0)))


SPEECH_GAP_S = 1.5   # readlines-09 '말 빈틈' = 받아쓰기 구절 사이 1.5초 넘는 쉼


def asr_stats(asr: list | None) -> dict:
    """(판단 주인 · readlines-09·11) 받아쓰기 구절(뜯기 audio.transcript.segments 꼴 start/end/text) → 말 구간 음절/초 · 1.5초 넘는 빈틈 수 · 첫 문장 착지(첫 구절 끝).
    벤치·우리 같은 함수(받아쓰기 없으면 None — match 가 미측정)."""
    seg = sorted([x for x in asr or [] if isinstance(x, dict) and str(x.get("text") or "").strip()], key=lambda x: float(x["start"]))
    if not seg:
        return {"speech.cps.asr": None, "speech.gap": None, "first.land": None}
    sec = sum(max(0.0, float(x["end"]) - float(x["start"])) for x in seg)
    ch = sum(len(re.sub(r"\s", "", str(x["text"]))) for x in seg)
    gaps = sum(1 for a, b in zip(seg, seg[1:]) if float(b["start"]) - float(a["end"]) > SPEECH_GAP_S)
    first = next((x for x in seg if re.search(r"[.?!]$|[다요죠래]$", str(x["text"]).strip())), seg[0])
    return {"speech.cps.asr": round(ch / sec, 2) if sec else None, "speech.gap": gaps, "first.land": round(float(first["end"]), 2)}


def _stats(lines: list[dict], dur: float, asr: list | None = None) -> dict:
    N = [_norm_line(l, dur) for l in lines if (l.get("layer") or "채널") != "원본박힘"]
    s = {"n": len(N), "dur": dur, **asr_stats(asr)}
    s["end.form"] = end_form(_last_texts(lines))["form"] if lines else None
    for sp in ("나레", "원음"):
        g = [n for n in N if n["sp"] == sp]
        s[f"fx.rate.{sp}"] = round(sum(n["any"] for n in g) / len(g), 3) if g else None
        s[f"enter.mode.{sp}"] = Counter(n["enter"] for n in g).most_common(1)[0][0] if g else None
        s[f"speech.cps.{sp}"] = round(sum(n["chars"] for n in g) / max(1e-6, sum(n["sec"] for n in g)), 2) if g else None
    s["chunk.chars"] = statistics.median([n["chars"] for n in N]) if N else None
    s["chunk.sec"] = round(statistics.median([n["sec"] for n in N]), 2) if N else None
    s["plain.rate"] = round(sum(not n["any"] for n in N) / len(N), 3) if N else None
    fx = [n for n in N if n["any"]]
    s["fx.pos"] = {k: round(sum(n["pos"] == k for n in fx) / len(fx), 3) for k in ("훅", "본문", "끝")} if fx else None
    s["narr.share"] = round(sum(n["sp"] == "나레" for n in N) / len(N), 3) if N else None
    # 표준 §4-1 추가 칸(04) — 원본박힘 층 뺀 같은 줄 모음에서
    L = [l for l in lines if (l.get("layer") or "채널") != "원본박힘"]
    tr = [k for k in (transition_key(l.get("transition")) for l in L) if k]
    s["transition.rate"] = {k: round(tr.count(k) / len(tr), 3) for k in TRANS_VOCAB if k in tr} if tr else None
    s["sfx.rate"] = round(sum(_sfx_n(l) for l in L) / dur, 3) if dur else None
    s["sticker.rate"] = round(sum(_has(l.get("sticker")) for l in L) / len(L), 3) if L else None
    s["meme.rate"] = round(sum(_is_meme(l) for l in L) / len(L), 3) if L else None
    return s


def _med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.median(xs) if xs else None


# fx.pos '해당 없음' 문턱(10-26 잇썸홈 두유노판, 코디 승인): 우리 꾸밈 줄 0 → 자리 분포 정의 안 됨. 벤치 꾸밈 없는 줄 중앙이 이 값 이상인
# 채널(두유노 실측 0.947 — 벤치 6편 꾸밈 줄 ~5%, 전부 훅)만 '해당 없음'. 0.9 = plain.rate 허용폭 20%p 안에서 꾸밈 0 편이 이미 같다고 보는 쪽의
# 보수적 하한(벤치 꾸밈 10% 미만). 꾸밈 많은 벤치(<0.9)는 계속 미달. 검수단축_wip.patch ⑧(측정 못 함 = 해당 없음)과 같은 판단 — 그 패치를 붙일 때 이 줄과 합칠 것.
FXPOS_NA_PLAIN = 0.9

HYBRID_OWN_KEYS = ("cut.median", "speech.cps.나레", "chunk.sec", "enter.mode.원음")   # 하이브리드 판이 벤치와 일부러 다른 칸(앞 원음 + 뒤 판매 이야기 · 고정 배속 목소리)


def style_targets(st: dict) -> dict:
    """판에 why 가 붙은 실측 목표값 {MATCH key: (값, why)} — HYBRID_OWN_KEYS 중 판 칸이 있는 것만(코디네이터 10-25 결정).
    speech.cps.나레 = 판 cps_target(+_why_cps_target) · cut.median = 판 cuts.cut_median(+cuts.why) · chunk.sec = 판 caption.chunk_sec(+caption.why) ·
    enter.mode.원음 = 판 caption.orig_enter_mode(+caption.why). 칸이 없으면 목표 없음(비교 안 함)."""
    out = {}
    if st.get("cps_target") is not None and st.get("_why_cps_target"):
        out["speech.cps.나레"] = (float(st["cps_target"]), st["_why_cps_target"])
    C, P = st.get("cuts") or {}, st.get("caption") or {}
    from tools.calcopy.hybrid import styles as _STY       # cut.median 목표 = 판 rhythm.cut_median(읽기 주인 styles.rhythm, 관제263 10-25 — 모든 판 필수 칸)
    rc = _STY.rhythm(st).get("cut_median")
    if rc:
        out["cut.median"] = (float(rc["v"]), rc["why"])
    elif C.get("cut_median") is not None and C.get("why"):
        out["cut.median"] = (float(C["cut_median"]), C["why"])
    if P.get("chunk_sec") is not None and P.get("why"):
        out["chunk.sec"] = (float(P["chunk_sec"]), P["why"])
    if P.get("orig_enter_mode") and P.get("why"):
        out["enter.mode.원음"] = (str(P["orig_enter_mode"]), P["why"])
    return out


SPAN_MIN = 3     # 벤치 편별 범위로 넓히려면 벤치 편이 이만큼은 있어야 한다


def _bench_span(key: str, B: list[dict], bm: dict):
    """(E 넓히기, 사장님 10-26 '너무 빡빡한 건 줄여라 — 벤치가 못 넘는 문턱은 너무 빡빡') 벤치 편별 값의 범위 — 스칼라 칸 (lo, hi) · 분포 칸 {칸: (lo, hi)}.
    벤치 편이 SPAN_MIN 편 미만이면 None(넓히지 않음). 근거: 벤치 한 편을 우리로 놓고 나머지와 같은 자로 잰 자기 통과율(loo2 — chunk.sec 50%·sfx.rate 51%·chunk.chars 62%·fx.pos 62%)."""
    if key == "cut.median":
        vals = [float(x) for x in bm.get("cut_median") or [] if isinstance(x, (int, float))]
    elif key in ("fx.pos", "transition.rate"):
        bs = [s[key] for s in B if s.get(key)]
        if len(bs) < SPAN_MIN:
            return None
        ks = sorted({k for x in bs for k in x})
        return {k: (min(x.get(k, 0.0) for x in bs), max(x.get(k, 0.0) for x in bs)) for k in ks}
    else:
        vals = [float(s[key]) for s in B if isinstance(s.get(key), (int, float))]
    return (min(vals), max(vals)) if len(vals) >= SPAN_MIN else None


def _in_span(o, span) -> bool:
    return bool(span) and isinstance(o, (int, float)) and span[0] - 1e-9 <= o <= span[1] + 1e-9


def _r7_row(key: str, kind: str, tol, core: bool, why: str, r7: dict | None) -> dict:
    """(판단 주인 · R7 칸 대조) r7 = {bench: r7.json summary, ours: r7.media(완성본) | None, branch: 갈래}. 못 잰 쪽 = failed(통과 아님)."""
    if not r7 or not r7.get("bench"):
        return {"key": key, "bench": None, "ours": None, "diff": "R7 칸 없음", "judge": "skip", "core": False,
                "why": why + " — 이 판에 R7 칸(r7.json)이 없다(벤치마킹 2판 프리셋이 아님)"}
    B, O = r7["bench"], r7.get("ours") or {}
    if key == "crop.x":
        from tools.calcopy.engine import r7 as R7
        if r7.get("branch") != R7.BRANCH_CLIP:
            return {"key": key, "bench": None, "ours": (O.get("crop") or {}).get("x_off_med"), "diff": "짝 대조 측정 없음", "judge": "failed", "core": core,
                    "why": why + f" — 갈래 {r7.get('branch')}: 확정 짝과의 컷별 x 차 측정이 아직 없다(숏박스 시험 묶음)"}
        b, o = (B.get("crop") or {}).get("x_off_med"), (O.get("crop") or {}).get("x_off_med")
    elif key == "end.sec":
        b, o = (B.get("end") or {}).get("sec"), (O.get("end") or {}).get("sec")
    elif key == "caption.size":
        b, o = (B.get("orig_caption") or {}).get("size_px"), None
    else:
        b, o = (B.get("title") or {}).get("lines"), None
    if b is None or o is None:
        return {"key": key, "bench": b, "ours": o, "diff": "미측정" if b is None else "우리 쪽 같은 자 없음", "judge": "failed", "core": core, "why": why}
    if kind in ("px", "abs"):
        diff = round(float(o) - float(b), 2)
        judge = "in" if abs(diff) <= tol else "out"
    elif kind == "rel":
        diff = round((o - b) / b * 100, 1) if b else None
        judge = "in" if diff is not None and abs(diff) <= tol else "out"
    else:
        diff, judge = ("" if o == b else "다름"), ("in" if o == b else "out")
    return {"key": key, "bench": b, "ours": o, "diff": diff, "judge": judge, "core": core, "why": why}


def match_table(bench_docs: list[dict], ours: dict, ours_media: dict | None, bench_media: dict | None, own_len: tuple | None = None,
                own_targets: dict | None = None, r7: dict | None = None) -> dict:
    """(판단 주인) 벤치 줄판독 모음 ↔ 우리 한 편을 MATCH_RULES 자로. 못 잰 항목은 failed(통과로 치지 않는다).
    own_len = 판 length (min, max). 판 길이 범위가 벤치 편 길이 범위와 **아예 안 겹치면**(하이브리드: 앞 원음 + 뒤 판매 이야기 25~30초 ↔ 벤치 단독 10~21초,
    판 length.why · channel/kitchit/하이브리드_판설계.md §1) 판이 일부러 정한 다른 길이다 — len.duration 은 그 판 범위로 잰다(관제263). 겹치면 옛 그대로.
    own_targets = style_targets(판). 하이브리드 판(위 조건)의 HYBRID_OWN_KEYS 칸은 벤치가 아니라 판 목표값과 같은 자·같은 합격선으로 비교하고,
    판 목표가 없는 칸은 비교하지 않는다(judge 'skip', 사유 표시 — 미측정 아님, 기준 칸에서 빠짐). 코디네이터 10-25 결정(페이블 재검토 대기, 표준 §12)."""
    B = [_stats(d.get("lines") or [], float(d.get("dur") or 0), d.get("_asr")) for d in bench_docs]
    ol, odur = _ours_lines(ours)
    O = _stats(ol, odur, ours.get("_asr"))
    om, bm = ours_media or {}, bench_media or {}
    brange_all = (min(s["dur"] for s in B), max(s["dur"] for s in B)) if B else None
    hybrid = bool(own_len and brange_all and (own_len[0] > brange_all[1] or own_len[1] < brange_all[0]))
    rows = []
    for key, kind, tol, core, why in MATCH_RULES:
        if key in R7_KEYS:
            rows.append(_r7_row(key, kind, tol, core, why, r7))
            continue
        if hybrid and key == "cut.median" and key not in (own_targets or {}):     # 페이블 10-25 재검토: 컷 길이는 '비교 안 함'이 아니라 판 목표와 비교 — 목표가 없으면 미달
            rows.append({"key": key, "bench": None, "ours": om.get("cut_median"), "diff": "판 rhythm.cut_median 없음", "judge": "failed", "core": core,
                         "why": why + " — 하이브리드 판: 판 rhythm.cut_median(벤치 실측 + why)과 비교해야 하는데 칸이 없다(표준 §4-1, 페이블 10-25)"})
            continue
        if hybrid and key in HYBRID_OWN_KEYS and key not in (own_targets or {}):
            o = {"cut.median": om.get("cut_median")}.get(key, O.get(key))
            rows.append({"key": key, "bench": None, "ours": o, "diff": "비교 안 함", "judge": "skip", "core": False,
                         "why": why + " — 하이브리드 판: 판에 why 붙은 실측 목표값이 없어 비교 안 함(미측정 아님 · 코디네이터 10-25 결정, 페이블 재검토 대기)"})
            continue
        if key == "len.duration":
            b, o = _med([s["dur"] for s in B]), odur or om.get("duration")
            brange = (min(s["dur"] for s in B), max(s["dur"] for s in B)) if B else None
            if own_len and brange and (own_len[0] > brange[1] or own_len[1] < brange[0]) and o is not None:
                lo, hi = float(own_len[0]), float(own_len[1])
                rows.append({"key": key, "bench": b, "ours": o, "diff": f"판 {lo:g}~{hi:g}(벤치 {brange[0]:g}~{brange[1]:g} 와 안 겹침)",
                             "judge": "in" if lo <= o <= hi else "out", "core": core,
                             "why": why + " — 판 길이가 벤치 범위와 안 겹치는 판(하이브리드)은 판 length 범위로(판 length.why)"})
                continue
        elif key == "cut.median":
            b, o, brange = _med(bm.get("cut_median") or []), om.get("cut_median"), None
        elif key == "mix.lufs":
            b, o, brange = _med(bm.get("lufs") or []), om.get("lufs"), None
        elif key == "fx.pos":
            bs = [s["fx.pos"] for s in B if s["fx.pos"]]
            b = {k: round(_med([x[k] for x in bs]), 3) for k in ("훅", "본문", "끝")} if bs else None
            o, brange = O["fx.pos"], None
        elif key == "narr.share":
            vals = [s["narr.share"] for s in B if s["narr.share"] is not None]
            b, o, brange = _med(vals), O["narr.share"], ((min(vals), max(vals)) if vals else None)
        elif key == "transition.rate":          # 분포(dict) — 벤치는 편마다 분포의 칸별 중앙값
            bs = [s[key] for s in B if s.get(key)]
            ks = sorted({k for x in bs for k in x})
            b = {k: round(_med([x.get(k, 0.0) for x in bs]), 3) for k in ks} if bs else None
            o, brange = (ours.get("transition_rate") or O.get(key)), None
        elif key == "thumb.frame0":
            c = Counter(k for k in (frame0_kind(d) for d in bench_docs) if k)
            b, o, brange = (c.most_common(1)[0][0] if c else None), ours.get("frame0_kind"), None
        elif key == "sfx.rate" and ours.get("sfx_rate") is not None:   # 렌더 기록(자막표.sfx 발 수 / 길이) — 줄에 접으면 한 줄 여러 발을 놓친다
            b, o, brange = _med([s[key] for s in B]), ours["sfx_rate"], None
        elif kind == "eq":
            c = Counter(s[key] for s in B if s[key])
            b, o, brange = (c.most_common(1)[0][0] if c else None), O[key], None
        else:
            b, o, brange = _med([s[key] for s in B]), O[key], None
        span = _bench_span(key, B, bm)            # 벤치 편별 범위 — 허용 폭 밖이어도 벤치 편 범위 안이면 같다(E, 10-26)
        if hybrid and key in HYBRID_OWN_KEYS:          # 판 목표값으로 비교(같은 kind·tol)
            b, brange, span = own_targets[key][0], None, None
            why = why + f" — 하이브리드 판: 판 목표 {b}(판 why: {str(own_targets[key][1])[:80]}…)와 비교"
        if b is None and o is None and key.endswith((".원음", ".나레")) and B and all(s.get("n") for s in B):
            judge, diff = "in", "둘 다 그 화자 줄 0(해당 없음)"      # 벤치 전 편에 그 화자 줄이 없고 우리도 없다 = 같다(10-26 두유노: 원음 0/119 — 옛 판정은 '미측정'으로 미달)
        elif key == "fx.pos" and o is None and O.get("n") and (_med([s["plain.rate"] for s in B if s.get("plain.rate") is not None]) or 0) >= FXPOS_NA_PLAIN:
            judge, diff = "in", f"우리 꾸밈 0 · 벤치 꾸밈 없는 줄 중앙 ≥{FXPOS_NA_PLAIN} — 자리 분포 해당 없음(꾸밈 비율은 fx.rate·plain.rate 칸이 잰다)"
        elif b is None or o is None:
            judge, diff = "failed", "미측정"
        elif key == "cut.median" and om.get("n_cuts") == 1 and \
                sum(p.get("n_cuts") == 1 for p in (bm.get("per") or {}).values()) * 2 > len(bm.get("per") or {}):
            # 한 샷 영상의 '컷 길이' = 영상 길이 — 길이 차를 컷 리듬 차로 읽던 결함(10-27 별헤는쏭: 벤치 4/5 한 샷 · 우리 한 샷 13.4초가 '빠름' 미달). 길이는 len.duration 칸이 잰다
            judge, diff = "in", f"둘 다 한 샷(컷 없음) — 벤치 {sum(p.get('n_cuts') == 1 for p in bm['per'].values())}/{len(bm['per'])}편 한 샷"
        elif kind == "rel":
            diff = round((o - b) / b * 100, 1) if b else None
            judge = "in" if (brange and brange[0] <= o <= brange[1]) or (diff is not None and abs(diff) <= tol) or _in_span(o, span) else "out"
        elif kind == "rel0":                    # 벤치 0 이면 우리도 0 이어야 같다(0 나누기 대신)
            diff = round((o - b) / b * 100, 1) if b else (0.0 if not o else "벤치 0")
            # 편 하나의 발 수는 정수 — 벤치 비율×길이에 가장 가까운 정수(차 ≤ 0.5발)면 같다(placement 가 개수를 round(비율×길이)로 정하는 것과 같은 자, 10-25 ep12 sfx 0.051×28.5=1.45 → 1발이 ±30% 로는 1·2발 둘 다 미달)
            n_ok = bool(b and odur and key.endswith(".rate") and abs((o - b) * odur) <= 0.5)
            judge = "in" if (b and abs(diff) <= tol) or (not b and not o) or n_ok or _in_span(o, span) else "out"
        elif kind == "rel_slow":
            diff = round((o - b) / b * 100, 1)
            judge = "in" if -tol * 0.5 <= diff <= tol or (span and b <= o <= span[1] + 1e-9) else "out"   # 빠른 쪽(음수)은 절반만 허용 — B4 '원본보다 빠르면 반려 쪽' · 느린 쪽만 벤치 가장 느린 편까지(사장님 10-26 '휙휙 지나가 집중 안 됨' — 빠른 쪽은 안 넓힌다)
        elif kind == "db":
            diff = round(o - b, 2)
            judge = "in" if abs(diff) <= tol else "out"
        elif kind == "pctp":
            if isinstance(b, dict):
                diff = {k: round((o.get(k, 0.0) - b.get(k, 0.0)) * 100, 1) for k in sorted(set(b) | set(o))}   # 한쪽에만 있는 칸은 0으로(분포 비교)
                judge = "in" if all(abs(v) <= tol or (isinstance(span, dict) and span.get(k, (0.0, 0.0))[0] - 1e-9 <= o.get(k, 0.0) <= span.get(k, (0.0, 0.0))[1] + 1e-9)
                                    for k, v in diff.items()) else "out"
            else:
                diff = round((o - b) * 100, 1)
                judge = "in" if abs(diff) <= tol or _in_span(o, span) else "out"
        elif kind == "range":
            diff = f"벤치 {brange[0]}~{brange[1]}" if brange else ""
            judge = "in" if brange and brange[0] <= o <= brange[1] else "out"
        else:  # eq
            diff = "" if o == b else "다름"
            judge = "in" if o == b else "out"
        rows.append({"key": key, "bench": b, "ours": o, "diff": diff, "judge": judge, "core": core, "why": why,
                     **({"bench_span": span} if span and kind in ("rel", "rel0", "rel_slow", "pctp") else {})})
    core = [r for r in rows if r["core"]]
    verdict = "통과" if core and all(r["judge"] == "in" for r in core) else "미달"
    return {"verdict": verdict, "rows": rows, "n_bench": len(B), "ours_n_lines": O["n"]}


def with_pixel(T: dict, bench_mp4: str, ours_mp4: str, out_dir: str) -> dict:
    """(판단 주인 · 1차 프리셋 관문 하나) 줄 단위 자(MATCH_RULES) + 픽셀·소리 자(compare.py 24칸)를 한 판정으로.
    둘 다 통과여야 통과. compare 는 따로 판정하지 않고 여기서만 합친다(10-23 사장님 '덧대기 없애자')."""
    from tools.calcopy.engine import compare as _cmp
    res = _cmp.compare(bench_mp4, ours_mp4, out_dir)
    v = res["verdict"]
    # 오른쪽 위 '광고' 표시(사장님 10-22 모든 렌더 의무, ad_mark) = 화면 맨 위(y<100) 띠 하나 — 벤치에 없어도 프리셋 차이가 아니다
    ub = [b for b in (res["ours"].get("bands") or []) if isinstance(b, (list, tuple)) or isinstance(b, dict)]
    def _y0(b):
        return ((b.get("band") or [b.get("y0", 0)])[0] if isinstance(b, dict) else b[0]) or 0
    if any(_y0(b) < 100 for b in ub) and "창 위 고정 글자 띠 개수" in v["out"]:
        ob = res["orig"].get("bands") or []
        if len([b for b in ub if _y0(b) >= 100]) == len(ob):
            v = {**v, "out": [x for x in v["out"] if x != "창 위 고정 글자 띠 개수"], "n_in": v["n_in"] + 1, "ad_mark": "광고 표시 띠 1개 뺌"}
            v["verdict"] = "통과" if not v["out"] and not v["failed"] else "미달"
    T["pixel"] = {"verdict": v["verdict"], "n_in": v["n_in"], "n_criteria": v["n_criteria"], "out": v["out"],
                  "failed": v["failed"], "table": str(Path(out_dir) / "차이표.md")}
    T["line_verdict"] = T["verdict"]
    T["verdict"] = "통과" if T["line_verdict"] == "통과" and v["verdict"] == "통과" else "미달"
    return T


def match_md(T: dict, title: str = "") -> str:
    L = [f"# 재현일치도 {title}(kal_analyze match · 벤치 {T['n_bench']}편 · 우리 줄 {T['ours_n_lines']}) — **{T['verdict']}**", "",
         "| 항목 | 벤치 | 우리 | 차 | 판정 | 기준 | 자·합격선 |", "|---|---|---|---|---|---|---|"]
    for r in T["rows"]:
        L.append(f"| {r['key']} | {r['bench']} | {r['ours']} | {r['diff']} | {'✓' if r['judge'] == 'in' else '✗' if r['judge'] == 'out' else '비교 안 함' if r['judge'] == 'skip' else '미측정'} | {'기준' if r['core'] else '참고'} | {r['why']} |")
    if T.get("pixel"):
        P = T["pixel"]
        L += ["", f"## 픽셀·소리(compare 같은 자) — {P['verdict']} ({P['n_criteria']}칸 중 안 {P['n_in']})",
              f"- 밖: {', '.join(P['out']) or '없음'} · 미측정: {', '.join(P['failed']) or '없음'} · 표 `{P['table']}`",
              f"- 줄 단위 판정 {T['line_verdict']} + 픽셀 판정 {P['verdict']} → **최종 {T['verdict']}**"]
    L += ["", "판정 = 기준 항목 전부 ✓ 일 때만 통과(미측정은 통과가 아니다). 참고 항목은 하이브리드 설계상 다른 값(−14 LUFS 통일·나레 비율)."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 매체 측정(컷·LUFS) — 벤치와 우리를 **같은 함수**로 잰다
SCENE_T = 0.3   # bench.cuts.SCENE_T 와 같은 문턱. 창 밖(검정 틀·제목)은 안 바뀌어 전체 프레임 점수가 묽어지므로 창을 잘라 잰다


def scene_cuts(mp4: str, win: tuple | None = None, th: float = SCENE_T, merge_s: float = 0.2) -> list[float]:
    """창 크롭 뒤 ffmpeg scene 감지 → 컷 시각(0.2초 안 묶음은 하나). 재현일치도의 컷 자(벤치·우리 공용)."""
    import subprocess
    vf = (f"crop={win[2]}:{win[3]}:{win[0]}:{win[1]}," if win else "") + f"select='gt(scene,{th})',showinfo"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", mp4, "-vf", vf, "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    out = []
    for t in ts:
        if out and t - out[-1] < merge_s:
            continue
        out.append(round(t, 2))
    return out



# ---------------------------------------------------------------- 눈 판정 칸(전환 종류·0초 첫 화면) — 관제 319 Ruling 17
# 시각은 프로그램(scene_cuts), 종류는 눈(오푸스 review — flow_bench.EYE_ASK 한 곳). 벤치 편·시험 편을 같은 자·같은 넣기 규칙으로.
CUT_LINE_PAD = 0.1      # 컷이 그 줄 몫인 창: t0-0.1 ≤ c < t1+0.1 (skeleton cut_at 과 같은 자 — 한 곳)
EYE_CUTS_MAX = 12       # 한 편에서 눈으로 볼 컷 수 상한 — 넘으면 고르게 뽑는다(그림 수가 review 를 무겁게 하지 않게)
EYE_PRE_S = 0.2         # 컷 그림 = 컷 0.2초 앞부터
EYE_WIN_S = 0.4         # 0.4초 동안 이어진 프레임 전부(2프레임 흰 번쩍임·검은 화면도 보이게 — agy 초당 1장으로는 못 본다)
EYE_FRAME_H = 240       # 띠 그림 한 칸 높이(px)
EYE_F0_H = 480          # 0초 그림 한 칸 높이 — 표지 글을 읽을 수 있게
EYE_COLS = 4            # 띠 그림 가로 칸 수 — 넘으면 다음 줄로(한 줄 12칸은 1만 px 넘게 길어져 보는 쪽에서 작게 줄어든다 · 실측 13896×240)
F0_KINDS = ("card", "scene")


def cut_in_line(c: float, t0: float, t1: float) -> bool:
    """(판단 주인) 컷 시각 c 가 그 줄(t0~t1) 몫인가 — skeleton cut_at·apply_eye 가 같이 쓴다."""
    return t0 - CUT_LINE_PAD <= c < t1 + CUT_LINE_PAD


def _ff(args: list) -> None:
    import subprocess
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("프레임 뽑기 실패: " + (r.stderr or b"").decode("utf-8", "replace")[-300:])


def eye_frames(mp4: str, out_dir, win: tuple | None = None) -> dict:
    """(프로그램 — 판단 없음) 눈 판정용 그림. 0초 첫 프레임 0~3번(표지 2프레임 + 그 뒤 바뀌나)을 가로로 한 장, scene_cuts 컷마다 컷 EYE_PRE_S 앞부터
    EYE_WIN_S 동안 이어진 프레임을 가로 띠 한 장. 컷이 EYE_CUTS_MAX 넘으면 고르게 뽑는다. 프레임 뽑기라 인코딩(venc)과 무관.
    → {"dur", "fps", "n_cuts_all", "frame0": <그림>, "cuts": [{"t", "img"}]} (경로는 out_dir 안 절대 경로 — 부르는 쪽이 상대로 바꾼다)."""
    import shutil
    from shopping_shorts.channelkit.bench import probe
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)          # 지난 시험 편 그림이 섞이지 않게
    out.mkdir(parents=True)
    meta = probe.info(mp4)
    fps = float(meta.get("fps") or 30) or 30.0
    dur = float(meta.get("duration") or 0)
    crop = f"crop={win[2]}:{win[3]}:{win[0]}:{win[1]}," if win else ""
    f0 = out / "frame0.jpg"
    _ff(["-i", mp4, "-vf", f"{crop}scale=-2:{EYE_F0_H},tile=2x2", "-frames:v", "1", "-q:v", "3", str(f0)])
    cuts = [c for c in scene_cuts(mp4, win) if c > 0.05]
    allc = len(cuts)
    if len(cuts) > EYE_CUTS_MAX:
        step = len(cuts) / EYE_CUTS_MAX
        cuts = [cuts[int(i * step)] for i in range(EYE_CUTS_MAX)]
    n = max(8, min(24, round(fps * EYE_WIN_S)))
    n = -(-n // EYE_COLS) * EYE_COLS          # 칸을 꽉 채우는 수(남는 칸이 있으면 tile 이 뒤 프레임을 더 끌어온다)
    items = []
    for k, c in enumerate(cuts):
        img = out / f"cut_{k:02d}.jpg"
        _ff(["-ss", f"{max(0.0, c - EYE_PRE_S):.3f}", "-i", mp4, "-vf", f"{crop}scale=-2:{EYE_FRAME_H},tile={EYE_COLS}x{n // EYE_COLS}",
             "-frames:v", "1", "-q:v", "3", str(img)])
        items.append({"t": round(float(c), 3), "img": str(img)})
    return {"dur": round(dur, 2), "fps": round(fps, 3), "n_cuts_all": allc, "frame0": str(f0), "cuts": items,
            "made_by": "kal_analyze.eye_frames(scene_cuts + ffmpeg 프레임 띠)"}


def eye_check(eye, n_cuts: int | None = None) -> list[str]:
    """(판단 주인) 눈 판정 꼴 검사 — {"cuts": [{"t", "kind"}], "frame0": {"kind": card|scene, "text"}}. 빈 목록 = 통과."""
    if not isinstance(eye, dict):
        return ["눈 판정이 없다"]
    errs = []
    cs = eye.get("cuts")
    if not isinstance(cs, list):
        errs.append("cuts 칸 없음")
        cs = []
    if n_cuts is not None and len(cs) != n_cuts:
        errs.append(f"컷 {n_cuts}개 중 {len(cs)}개만 판정")
    for i, c in enumerate(cs):
        if not isinstance(c, dict) or not isinstance(c.get("t"), (int, float)):
            errs.append(f"컷{i} 시각 없음")
        elif transition_key(c.get("kind")) is None:
            errs.append(f"컷{i} 종류 어휘 밖: {c.get('kind')!r} ({'|'.join(TRANS_VOCAB)})")
    f0 = eye.get("frame0")
    if not isinstance(f0, dict) or f0.get("kind") not in F0_KINDS:
        errs.append("frame0.kind 는 card | scene")
    elif f0["kind"] == "card" and not str(f0.get("text") or "").strip():
        errs.append("frame0 card 인데 표지 글(text)이 비었다")
    return errs


def apply_eye(lines: list[dict], eye: dict) -> dict:
    """(판단 주인 — 넣기 규칙 한 곳) 눈 판정 → 줄 transition + 문서 frame0. 벤치 줄판독(bm_fill)·우리 편(ours_from_remake)이 같이 부른다.
    컷 → 그 컷이 cut_in_line 인 줄 중 가장 늦게 시작하는 줄(= 그 컷에서 시작하는 줄), 그런 줄이 없으면 가장 가까운 줄.
    한 줄에 컷이 여럿이면 cut 아닌 종류를 먼저(드문 전환이 묻히지 않게). 컷 없는 줄 = 'none'(전환 없음 — strict 검사의 null 금지).
    frame0 = {"text", "kind"} — card 면 표지 글, scene 이면 '' (frame0_kind 가 읽는 꼴). 꼴이 틀리면 ValueError(조용히 넣지 않는다)."""
    errs = eye_check(eye)
    if errs:
        raise ValueError("눈 판정 꼴 오류: " + " / ".join(errs[:4]))
    got: dict[int, list[str]] = defaultdict(list)
    for c in eye["cuts"]:
        t, k = float(c["t"]), transition_key(c["kind"])
        if not lines:
            break
        inn = [i for i, l in enumerate(lines) if cut_in_line(t, float(l["t0"]), float(l["t1"]))]
        i = max(inn, key=lambda j: float(lines[j]["t0"])) if inn else \
            min(range(len(lines)), key=lambda j: min(abs(t - float(lines[j]["t0"])), abs(t - float(lines[j]["t1"]))))
        got[i].append(k)
    for i, l in enumerate(lines):
        ks = got.get(i) or []
        l["transition"] = next((k for k in ks if k != "cut"), "cut") if ks else "none"
    f0 = eye["frame0"]
    return {"kind": f0["kind"], "text": str(f0.get("text") or "").strip() if f0["kind"] == "card" else "", "_by": "눈 판정(eye_frames 그림)"}

def media_of(mp4: str, win: tuple | None = None) -> dict:
    from shopping_shorts.channelkit.bench import audio, probe
    meta = probe.info(mp4)
    dur = float(meta.get("duration") or 0)
    # 컷 자 = compare 와 같은 함수(bench_one.measure → cuts.scene_detect+merge_close+cut_verify) 한 벌 — 10-23 꿀템노트에서
    # 옛 scene_cuts(창 크롭 scene>0.3)가 같은 원본의 크롭 바꿈 컷을 놓쳐 2.21초(compare 0.867초)로 쟀다. 두 자가 다르면 판정이 둘이 된다.
    from tools.calcopy.engine import bench_one, compare as _cmp
    sh, cd = _cmp._shots(bench_one.measure(mp4, layout_mode="bench"))
    lens = [round(x, 3) for x in sh if x > 0.05]
    e = audio.ebur128(mp4)
    return {"duration": round(dur, 2), "cut_median": round(statistics.median(lens), 2) if lens else None, "n_cuts": len(lens),
            "cut_at": [round(float(t), 3) for t in (cd.get("cuts") or [])],      # 컷 시각(훅 0.1~3초 경계 수 = 판 rhythm.hook_cuts_3s 자, 관제263 10-25)
            "lufs": e.get("I"), "tp": e.get("TP"), "win": list(win) if win else None,
            "method": "probe.info + bench_one.measure 컷(compare 와 같은 자) + bench.audio.ebur128"}


ours_media_of = media_of


def bench_media_src(src_dir: str, ids: list[str], win: tuple | None) -> dict:
    out = {"cut_median": [], "lufs": [], "ids": [], "per": {}}
    for vid in ids:
        p = Path(src_dir) / f"{vid}.mp4"
        if not p.exists():
            continue
        m = media_of(str(p), win)
        out["per"][vid] = m
        out["ids"].append(vid)
        if isinstance(m["cut_median"], (int, float)):
            out["cut_median"].append(m["cut_median"])
        if isinstance(m["lufs"], (int, float)):
            out["lufs"].append(m["lufs"])
    out["method"] = "media_of(같은 자: 창 크롭 scene 감지 + ebur128)"
    return out


def _win_arg(s: str | None, docs: list[dict]) -> tuple | None:
    """--win x,y,w,h 또는 줄판독 layout.window [x0,y0,x1,y1] → (x,y,w,h)."""
    if s:
        x, y, w, h = [int(v) for v in s.split(",")]
        return (x, y, w, h)
    for d in docs:
        w = (d.get("layout") or {}).get("window")
        if w and len(w) == 4:
            x0, y0, x1, y1 = w
            return (x0, y0, x1 - x0, y1 - y0)
    return None


def bench_media_of(tteutgi_dir: str, ids: list[str]) -> dict:
    out = {"cut_median": [], "lufs": [], "ids": []}
    for vid in ids:
        p = Path(tteutgi_dir) / vid / "뜯기.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        cm = ((d.get("cuts") or {}).get("bench") or {}).get("shot_median")
        lu = ((d.get("audio") or {}).get("bench") or {}).get("I")
        out["cut_median"].append(cm)
        out["lufs"].append(lu)
        out["ids"].append(vid)
    out["cut_median"] = [x for x in out["cut_median"] if isinstance(x, (int, float))]
    out["lufs"] = [x for x in out["lufs"] if isinstance(x, (int, float))]
    out["method"] = "뜯기.json cuts.bench.shot_median · audio.bench.I (⚠ 우리 쪽과 자가 다르다 — --bench-src 를 쓰면 같은 자)"
    return out


def _abs(p: str | None) -> Path | None:
    if not p:
        return None
    return Path(p) if Path(p).is_absolute() else ROOT / p


def upgrade_table(st, doc, work) -> dict:
    """업그레이드 자 — 주인은 engine/upgrade_table.py(지시서 05). quality_gate 가 이 이름으로 부른다(한 줄 연결, 순환 import 피해 늦게 부름)."""
    from tools.calcopy.engine import upgrade_table as _U
    return _U.upgrade_table(st, doc, work)


BENCH_MEDIA_CACHE = "_bench_media_cache.json"


def bench_media_cached(src_dir: str, ids: list[str], win: tuple | None) -> dict:
    """bench_media_src 와 같은 값·같은 꼴 — 벤치 원본 한 편 측정(media_of, 편당 2~3분)을 src_dir/_bench_media_cache.json 에 남겨 다시 안 잰다.
    열쇠 = 편 id·파일 크기·수정 시각·창 — 원본이 바뀌면 다시 잰다(10-24 실측: 관문 한 번 20분 중 대부분이 벤치 6편 재측정)."""
    cp = Path(src_dir) / BENCH_MEDIA_CACHE
    try:
        cache = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    except (OSError, ValueError):
        cache = {}
    out = {"cut_median": [], "lufs": [], "ids": [], "per": {}}
    for vid in ids:
        p = Path(src_dir) / f"{vid}.mp4"
        if not p.exists():
            continue
        key = f"{vid}|{p.stat().st_size}|{int(p.stat().st_mtime)}|{list(win) if win else None}"
        m = cache.get(key) or media_of(str(p), win)
        cache[key] = m
        out["per"][vid] = m
        out["ids"].append(vid)
        if isinstance(m["cut_median"], (int, float)):
            out["cut_median"].append(m["cut_median"])
        if isinstance(m["lufs"], (int, float)):
            out["lufs"].append(m["lufs"])
    try:
        cp.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass                                # 캐시를 못 써도 값은 그대로(다음에 다시 잴 뿐)
    out["method"] = "media_of(같은 자) — 편별 캐시 " + BENCH_MEDIA_CACHE
    return out


def match_from_render(style, doc, work, media: bool | dict = True, frame0_kind_measured: str | None = None) -> dict:
    """(어댑터 — 관제 263 지시서 04) 공용 렌더러(render_bench) 산출 → match_table. 판단은 match_table 한 곳(여기서 새로 판정하지 않는다).
    style = 판 이름 또는 판 dict · 벤치 = 판 bench.line_reads(줄판독) + bench.src_dir(같은 자로 컷·LUFS) ·
    우리 = work/render/자막표.json(rows·sfx·transitions·flashes) + timeline.json(cuts·end) + final.mp4 + doc/썸네일.json.
    frame0_kind_measured = 품질 관문이 완성본에서 잰 0초 종류(card/scene) — 없으면 썸네일.json 의 pick 으로(선언값, rows 에 표시)."""
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(style) if isinstance(style, str) else style
    doc, R = Path(doc), Path(work) / "render"
    B = st.get("bench") or {}
    lrp = _abs(B.get("line_reads"))
    bench = _load_docs([str(lrp)]) if lrp and lrp.exists() else []
    tab = json.loads((R / "자막표.json").read_text(encoding="utf-8"))
    T = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
    dur = float(T.get("end") or 0)
    lines, _ = _ours_lines({"rows": tab.get("rows") or [], "cards": tab.get("cards") or [], "lyrics": tab.get("lyrics") or [],
                            "dur": dur, "sfx_in_video": tab.get("sfx") or []})   # 효과음 = 덩어리 꾸밈(벤치 _decorated 와 같은 자 — 10-26 전엔 안 넘겨 우리 fx.rate 가 늘 0 이었다)
    # 짤: 시간표 컷에 meme 표시가 있으면 그 컷과 겹치는 줄 = 짤 화면
    memes = [(float(c["t0"]), float(c["t1"])) for c in T.get("cuts") or [] if c.get("meme") or c.get("kind") == "meme"]
    for l in lines:
        if any(a < l["t1"] and l["t0"] < b for a, b in memes):
            l["screen"] = "밈짤"
    # 전환: 컷 경계마다 하나 — 종류 = 자막표 transitions(렌더러가 실제로 그린 것) > flashes(옛 키) > cut
    marks = [(float(e["t"]), e.get("kind", "cut")) for e in tab.get("transitions") or [] if isinstance(e, dict)]
    marks += [(float(f.get("t") if isinstance(f, dict) else f), "flash") for f in tab.get("flashes") or []]
    kinds = []
    for c in (T.get("cuts") or [])[1:]:
        t = float(c["t0"])
        kinds.append(next((k for tt, k in marks if abs(tt - t) <= 0.05), "cut"))
    tr = {k: round(kinds.count(k) / len(kinds), 3) for k in TRANS_VOCAB if k in kinds} if kinds else None
    sp = doc / "썸네일.json"
    declared = ("card" if json.loads(sp.read_text(encoding="utf-8")).get("pick") else "scene") if sp.exists() else "scene"
    ours = {"lines": lines, "dur": dur, "transition_rate": tr,
            "sfx_rate": round(len(tab.get("sfx") or []) / dur, 3) if dur else None,
            "frame0_kind": frame0_kind_measured or declared}
    om = bm = None
    if media:
        x, y, w, h = (st.get("frame") or {}).get("window") or (0, 0, 1080, 1920)
        om = media if isinstance(media, dict) else media_of(str(R / "final.mp4"), (x, y, w, h))     # 품질 관문이 이미 잰 완성본 media_of 결과(dict)면 그대로(10-26 검수 단축 ①)
        if B.get("src_dir"):
            bm = bench_media_cached(B["src_dir"], [d.get("id") for d in bench], _win_arg(None, bench))
    LD = st.get("length") or {}
    Tm = match_table(bench, ours, om, bm, own_len=(LD["min"], LD["max"]) if "min" in LD and "max" in LD else None, own_targets=style_targets(st))
    Tm.update({"ours_media": om, "bench_media": bm, "bench_ids": [d.get("id") for d in bench], "line_reads": str(lrp) if lrp else None,
               "frame0_from": "완성본 측정" if frame0_kind_measured else "썸네일.json pick(선언)",
               "made_by": "kal_analyze.match_from_render"})
    return Tm


# ---------------------------------------------------------------- 벤치마킹 시험 편(remake.py 결과) ↔ 벤치 줄판독 (관제 319 Ruling 10)
# 줄판독 등장 어휘(ENTER_VOCAB) ↔ 프리셋 frame.json 자막 enter.kind(schema: pop|fade|rise|typewriter|none, 없으면 null) — 양쪽에 다 있는 것만.
ENTER_FRAME = {"instant": None, "typing": "typewriter", "pop": "pop", "fade": "fade"}
ENTER_MS = 300          # frame 자막 enter 가 비어 있을 때 새로 넣는 등장 시간(ms) — calcopy_frame/schema.py 예시값(28줄). 이미 있으면 그 ms 그대로
# (판단 주인) 어긋난 대조 칸 → 프리셋 frame.json 의 고칠 자리. 여기 없는 칸은 frame 자리가 아니다(대본·재료·목소리 몫) — 잡도리 후보를 안 낸다.
MATCH_FIX = {"enter.mode.나레": "layers[text:caption].enter", "enter.mode.원음": "layers[text:caption].enter"}


def _cap_of(layers) -> dict | None:
    return next((l for l in layers or [] if isinstance(l, dict) and l.get("kind") == "text" and l.get("role") == "caption"), None)


def _caption_at(frame: dict | None) -> tuple[dict | None, str]:
    """(판단 주인) 자막 줄을 그리는 층과 그 층의 flat 자리 머리(preset_save.flat 꼴). 한 틀이면 머리 ''.
    틀 여러 장(to_frame_multi 꼴 — 훅 카드·본편)이면 자막 층이 있는 본편 틀(id 'body' 먼저, 없으면 자막 있는 마지막 틀) → 'frames[<id>].'.
    실측(최종 검토, 방구 게시글형): 최상위 layers 만 보면 자막을 못 찾아 우리 등장이 instant 로 잡히고 잡도리 후보가 0개였다."""
    f = frame or {}
    cap = _cap_of(f.get("layers"))
    if cap is not None:
        return cap, ""
    frs = [x for x in f.get("frames") or [] if isinstance(x, dict) and _cap_of(x.get("layers"))]
    if not frs:
        return None, ""
    fr = next((x for x in frs if x.get("id") == "body"), frs[-1])
    return _cap_of(fr["layers"]), f"frames[{fr.get('id')}]."


def _caption_layer(frame: dict | None) -> dict | None:
    return _caption_at(frame)[0]


def _frame_enter(v) -> str:
    k = v.get("kind") if isinstance(v, dict) else v
    if k in (None, "none"):
        return "instant"
    inv = {f: m for m, f in ENTER_FRAME.items() if f}
    return inv.get(str(k), enter_key(k))


def _sfx_times(audio: dict) -> list[float]:
    out = []
    for s in audio.get("sfx") or []:      # remake_video: [{file,t,db}] · narr_video: [[file,t,db]]
        t = s.get("t") if isinstance(s, dict) else (s[1] if isinstance(s, (list, tuple)) and len(s) > 1 else None)
        if isinstance(t, (int, float)):
            out.append(float(t))
    return out


def ours_from_remake(out_dir, frame: dict | None = None, eye: dict | None = None) -> dict:
    """(어댑터) remake.py 결과 폴더 → _ours_lines 의 lines 꼴. 판정은 match_table 한 곳(여기서 판정하지 않는다).
    시각 = timeline.json — narr_video steps[{text,t0,t1}](누적형 둘째 단계는 새로 붙은 마지막 줄만) · remake_video beats[{t0,dur,caption_lines}](빈 줄 뺌).
    화자 = remake_log.kind(tts·human → 나레, none → 모름 None — 원음만 꼴은 줄마다 화자를 기록하지 않는다).
    등장 = 프리셋 frame 자막 enter(렌더가 그 값으로 그린다 · frame 을 안 주면 None). 효과음 = audio.json sfx 시각. 줄 꾸밈(강조·스티커)은 기록이 없어 비운다(→ 미측정).
    전환·0초 화면 = eye(완성본 프레임 눈 판정 — 벤치 줄판독과 같은 apply_eye)를 주면 넣고, 안 주면 비운다(→ 미측정)."""
    out = Path(out_dir)
    T = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    lp, ap = out / "remake_log.json", out / "audio.json"
    kind = json.loads(lp.read_text(encoding="utf-8")).get("kind") if lp.is_file() else None
    sp = "나레" if kind in ("tts", "human") else None
    cap = _caption_layer(frame)
    enter = _frame_enter(cap.get("enter")) if cap else None
    if isinstance(T.get("steps"), list) and T["steps"]:
        rows = [(float(s["t0"]), float(s["t1"]), str(s.get("text") or "").split("\n")[-1]) for s in T["steps"] if "t0" in s and "t1" in s]
        dur = float(T.get("dur") or max((r[1] for r in rows), default=0))
    elif isinstance(T.get("beats"), list) and T["beats"]:
        rows = [(float(b["t0"]), round(float(b["t0"]) + float(b["dur"]), 3), " ".join(b.get("caption_lines") or [])) for b in T["beats"]]
        dur = max((r[1] for r in rows), default=0.0)
        rows = [r for r in rows if r[2].strip()]
    else:
        raise ValueError("timeline.json 에 줄 시각(steps·beats)이 없다")
    sfx = _sfx_times(json.loads(ap.read_text(encoding="utf-8"))) if ap.is_file() else None
    lines = [{"t0": a, "t1": b, "text": t, "speaker": sp, "enter": enter, "layer": "채널",
              "sfx": next((f"{x}" for x in sfx or [] if a <= x < b), None)} for a, b, t in rows]
    f0 = apply_eye(lines, eye) if eye is not None else None
    return {"lines": lines, "dur": dur, "sfx_rate": round(len(sfx) / dur, 3) if sfx is not None and dur else None, "kind": kind,
            "frame0_kind": frame0_kind({"frame0": f0}) if f0 else None}


def ours_from_preset_make(out_dir, wdir=None) -> dict:
    """(어댑터 · 판정 없음) preset_make.make_one 결과 폴더 → _ours_lines 의 lines 꼴(kal.step_make 가 우리줄.json 으로 쓴다, 11-06 make-00).
    시각 = timeline.json pieces[{text,line,t0,t1}](make_one 이 씀). 화자 = 작업 폴더 대본.json lines[line].kind == 'orig' → 원음, 그 밖 → 나레(대본이 없으면 None).
    등장·꾸밈·효과음은 이 기록에 없어 비운다(→ match_table 미측정)."""
    out = Path(out_dir)
    T = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    pcs = [p for p in (T.get("pieces") or []) if "t0" in p and "t1" in p]
    if not pcs:
        raise ValueError(f"{out}/timeline.json 에 pieces 시각이 없다")
    raw = []
    if wdir and (Path(wdir) / "대본.json").is_file():
        S = json.loads((Path(wdir) / "대본.json").read_text(encoding="utf-8"))
        raw = S.get("lines") or S.get("spine55") or []

    def spk(i):
        if not raw or i is None or not (0 <= int(i) < len(raw)):
            return None
        return "원음" if raw[int(i)].get("kind") == "orig" else "나레"
    lines = [{"t0": float(p["t0"]), "t1": float(p["t1"]), "text": str(p.get("text") or "").replace("\n", " / "), "speaker": spk(p.get("line")),
              "enter": None, "layer": "채널", "sfx": None} for p in pcs]
    return {"lines": lines, "dur": round(max(l["t1"] for l in lines), 3), "from": "preset_make timeline.json"}


WATCH_AT = (0.0, 1.0, 2.0)     # 시청 묶음 첫 화면 시각(verify-07 회원 근거: 0·1·2초 프레임)
WATCH_TAIL_S = 0.5             # 끝 0.5초 클립(끝 끊김 확인)


def watch_pack(bench_mp4: str, ours_mp4: str, out_dir) -> dict:
    """(프로그램 — 판단 없음) 사람 시청 판정 묶음(verify-07): 벤치·우리 0·1·2초 프레임 나란히 한 장 + 우리 끝 0.5초 클립 + 두 원본 경로.
    판정은 사람이 _kal/시청판정.json 에 적는다(kal.step_verify 가 sha256 짝으로 읽는다)."""
    import shutil
    from shopping_shorts.channelkit.bench import probe
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)          # 지난 시험 편 그림이 섞이지 않게
    out.mkdir(parents=True)
    imgs = []
    for tag, mp4 in (("bench", bench_mp4), ("ours", ours_mp4)):
        for t in WATCH_AT:
            p = out / f"{tag}_{t:.0f}s.jpg"
            _ff(["-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=-2:640", "-q:v", "3", str(p)])
            imgs.append(p)
    side = out / "나란히_0_1_2초.jpg"
    args = []
    for p in imgs:
        args += ["-i", str(p)]
    _ff(args + ["-filter_complex", "".join(f"[{i}]" for i in range(len(imgs))) + f"xstack=inputs={len(imgs)}:layout="
                + "|".join(f"{'+'.join(['w0'] * (i % 3)) or '0'}_{'h0' if i >= 3 else '0'}" for i in range(len(imgs))), str(side)])
    dur = float(probe.info(ours_mp4).get("duration") or 0)
    tail = out / "우리_끝0.5초.mp4"
    from tools.calcopy.engine import encoder   # 인코딩 주인 = encoder.venc(GPU 우선·CPU 대체)
    r = encoder.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, dur - WATCH_TAIL_S):.3f}", "-i", ours_mp4, *encoder.venc(20), "-c:a", "aac", str(tail)], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("끝 클립 만들기 실패: " + (r.stderr or b"").decode("utf-8", "replace")[-300:])
    return {"dir": str(out), "side": str(side), "tail": str(tail), "bench": bench_mp4, "ours": ours_mp4, "frames": [str(p) for p in imgs]}


def _flat(s: str) -> str:
    return re.sub(r"\s", "", str(s or "")).lower()


def _near(a: str, b: str) -> bool:
    """글자 1~2개만 다른가(같은 길이 바꿈·한 글자 빠짐/더함) — 리포트↔리포터."""
    if a == b or abs(len(a) - len(b)) > 1 or len(b) < 3:
        return False
    if len(a) == len(b):
        return 0 < sum(x != y for x, y in zip(a, b)) <= 2
    s_, l_ = (a, b) if len(a) < len(b) else (b, a)
    return any(l_[:i] + l_[i + 1:] == s_ for i in range(len(l_)))


def name_check(texts: list[str], bench_names: list[str], brand: str | None) -> list[str]:
    """(판단 주인 · verify-m01) 우리 편 글(대본 줄·화면 틀 글)에 벤치 채널명이 남았나 · 우리 브랜드 철자가 1~2자 다른 낱말이 있나(공백 뺀 비교)."""
    bad = []
    flat = [_flat(t) for t in texts if t]
    for n in [x for x in bench_names if x and len(_flat(x)) >= 2]:
        hit = [t for t in flat if _flat(n) in t]
        if hit:
            bad.append(f"벤치 채널명 '{n}' 남음 {len(hit)}곳")
    if brand and len(_flat(brand)) >= 3:
        b = _flat(brand)
        for t in texts:
            for w in re.findall(r"[0-9A-Za-z가-힣]+", str(t or "")):
                if b in w.lower():            # 철자 맞는 브랜드가 든 낱말은 통과
                    continue
                for k in range(len(w) - len(b) + 2):
                    for L in (len(b) - 1, len(b), len(b) + 1):
                        piece = w[k:k + L].lower()
                        if len(piece) == L and _near(piece, b):
                            bad.append(f"브랜드 철자 다름 '{w}' ≠ '{brand}'")
                            break
    return sorted(set(bad))


HYGIENE = {   # verify-14(J124) 금지 표 한 곳 — 개인정보 낱말 + 유도 말 짝이 같은 줄에 있으면 미달
    "개인정보": ("생년월일", "주민번호", "주민등록", "전화번호", "휴대폰번호", "핸드폰번호", "집주소", "주소"),
    "유도": ("댓글", "적어", "남겨", "알려", "써주", "써 주"),
}


def text_hygiene(texts: list[str], table: dict = HYGIENE) -> list[str]:
    """(판단 주인 · verify-14) 낱말 단위 — 개인정보 낱말과 유도 말이 같은 글에 함께 있으면 그 글. 띠·년생은 허용(표에 없음)."""
    out = []
    for t in texts:
        t = str(t or "")
        toks = re.findall(r"[가-힣A-Za-z0-9]+", t)
        pi = [w for w in toks if any(w.startswith(k) for k in table["개인정보"])]
        lure = [w for w in toks if any(w.startswith(k) for k in table["유도"])]
        if pi and lure:
            out.append(f"'{t[:40]}' — {pi[0]} + {lure[0]}")
    return out


def attach_bench_asr(docs: list[dict], tteutgi_dir) -> int:
    """verify 가 벤치 줄판독마다 뜯기.json 받아쓰기 구절을 _asr 로 붙인다(asr_stats 재료) → 붙인 편 수."""
    n = 0
    for d in docs:
        p = Path(tteutgi_dir) / str(d.get("id")) / "뜯기.json"
        if p.is_file():
            seg = (((json.loads(p.read_text(encoding="utf-8")).get("audio") or {}).get("transcript") or {}).get("segments"))
            if seg:
                d["_asr"] = seg
                n += 1
    return n


def title_of(top: list[dict], k: int = 10) -> dict:
    """(판단 주인 · apply-08) 벤치 제목 꼴 — 조회순 제목들의 길이 중앙·두 토막 비율(쉼표·／·| 나 따옴표로 두 덩이)·숫자·따옴표·물음표 비율 + 조회 상위 k편 제목.
    3안 짓기·같은 문장 0 검사는 사람/대본 단계(이 함수는 꼴만)."""
    T = [x for x in sorted(top or [], key=lambda x: -(x.get("views") or 0)) if str(x.get("title") or "").strip()]
    if not T:
        return {"n": 0}
    ts = [str(x["title"]).strip() for x in T]
    two = re.compile(r"[,，/／|｜]|[\"“”'‘’「」『』].+[\"“”'‘’「」『』]\s*\S")
    return {"n": len(ts), "chars_med": statistics.median(len(t) for t in ts),
            "two_part_rate": round(sum(bool(two.search(t)) for t in ts) / len(ts), 2),
            "number_rate": round(sum(bool(re.search(r"\d", t)) for t in ts) / len(ts), 2),
            "quote_rate": round(sum(bool(re.search(r"[\"“”'‘’「」『』]", t)) for t in ts) / len(ts), 2),
            "question_rate": round(sum("?" in t for t in ts) / len(ts), 2),
            "top": [{"title": x["title"], "views": x.get("views")} for x in T[:k]]}


def scene_table(out_dir) -> tuple[str, list[str]]:
    """(apply-15) 시험편 make 출력(timeline.json groups·pieces) → 장면표.md 글 + 빈칸 목록. 행 = 컷(group) 하나. 화면 상황 칸은 사람(Claude 눈)이 채운다 — 빈칸 검사에서 뺀다."""
    T = json.loads((Path(out_dir) / "timeline.json").read_text(encoding="utf-8"))
    G, P = T.get("groups") or [], T.get("pieces") or []
    L = ["| # | 시각 | 클립(원본·구간) | 화면 상황(앵글 — 사람) | 자막·나레 |", "|---|---|---|---|---|"]
    empty = []
    for i, g in enumerate(G, 1):
        t0 = float(g.get("t0") or 0)
        t1 = t0 + float(g.get("dur") or 0)
        cap = " / ".join(str(p.get("text") or "").replace("\n", " ") for p in P if float(p.get("t0") or 0) < t1 and float(p.get("t1") or 0) > t0)
        clip = f"{Path(str(g.get('src') or '')).name} {g.get('ss')}s+{g.get('src_span') or g.get('dur')}s"
        for k, v in (("시각", g.get("dur")), ("클립", g.get("src")), ("자막·나레", cap)):
            if v in (None, "", 0):
                empty.append(f"#{i} {k}")
        L.append(f"| {i} | {t0:.2f}~{t1:.2f} | {clip} | | {cap} |")
    return "\n".join(L) + "\n", empty


def fix_cands(T: dict, frame: dict) -> list[dict]:
    """(판단 주인) match_table 의 어긋난 칸 중 MATCH_FIX 에 자리가 있는 것만 → 잡도리 후보 {path, value, why}(bm_fix 가 못 박는 꼴)."""
    from tools.calcopy.engine import preset_save as P
    F = P.flat(frame)
    cap, head = _caption_at(frame)
    cap = cap or {}
    out, seen = [], set()
    for r in T.get("rows") or []:
        path = head + MATCH_FIX[r["key"]] if r["key"] in MATCH_FIX else None
        if r.get("judge") != "out" or not path or path not in F or r.get("bench") not in ENTER_FRAME:
            continue
        k = ENTER_FRAME[r["bench"]]
        old = cap.get("enter")
        value = None if k is None else {"kind": k, "ms": old["ms"] if isinstance(old, dict) and old.get("ms") else ENTER_MS}
        key = json.dumps([path, value], ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append({"path": path, "value": value, "why": f"{r['key']} 벤치 {r['bench']} · 우리 {r['ours']} ({r['why'][:60]})"})
    return out


def bench_match(line_reads: list[str], work, preset_dir, bench_src=None, eye: dict | None = None, branch: str | None = None) -> dict:
    """(판단 주인) 벤치마킹 시험 편 대조 — 줄 자 = match_table(벤치 줄판독 ↔ ours_from_remake), 관문 = remake.gate_of(픽셀·이음매 기록).
    픽셀 대조는 remake 가 이미 돌린 compare 기록을 읽는다(with_pixel 로 다시 돌리지 않는다 — 같은 compare 두 번, Jev 0.92).
    match_ok = 줄 판정 통과 + 관문 통과. fails = 기준 칸 중 통과 아닌 것(미측정 포함) + '관문:<칸>'. cands = fix_cands."""
    from tools.calcopy.engine import remake as RM
    work, preset_dir = Path(work), Path(preset_dir)
    docs = _load_docs(line_reads)
    if not docs:
        raise ValueError("벤치 줄판독이 없다")
    frame = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    ours = ours_from_remake(work, frame, eye)     # eye = 시험 편 눈 판정(전환·0초 화면 — 벤치 줄판독과 같은 넣기 규칙)
    win = _win_arg(None, docs)
    fin = work / "final.mp4"
    om = media_of(str(fin), win) if fin.is_file() else None          # 완성본이 없으면 컷·LUFS 는 못 잰다(match_table 이 미측정으로)
    bm = bench_media_cached(str(bench_src), [d.get("id") for d in docs], win) if bench_src and Path(bench_src).is_dir() else None
    rp = preset_dir / "r7.json"          # R7 칸(bm_tear 실측 · preset_save.save_r7) — 우리 쪽은 같은 자 r7.media(완성본, 같은 컷 자 media_of cut_at)
    r7 = None
    if rp.is_file():
        from tools.calcopy.engine import r7 as R7
        rs = json.loads(rp.read_text(encoding="utf-8")).get("summary")
        r7 = {"bench": rs, "branch": branch, "ours": R7.media(str(fin), om.get("cut_at"), list(win) if win else None) if om else None}
    T = match_table(docs, ours, om, bm, r7=r7)
    g = RM.gate_of(work)
    fails = [r["key"] for r in T["rows"] if r["core"] and r["judge"] != "in"] + [f"관문:{x}" for x in g["fails"]]
    return {"match_ok": T["verdict"] == "통과" and g["ok"], "fails": fails, "cands": fix_cands(T, frame), "gate_ok": g["ok"], "gate": g,
            "table": {"verdict": T["verdict"], "rows": T["rows"], "n_bench": T["n_bench"]}, "made_by": "kal_analyze.bench_match"}


# ---------------------------------------------------------------- frames (견본 sheets.py 를 그대로 부른다)
def _sheets_mod():
    p = ROOT / "channel/starpickroom/_tools/sheets.py"
    spec = importlib.util.spec_from_file_location("spr_sheets", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def frames_cmd(mp4: str, out: str, y0: int, y1: int, fps: float, max_strips: int,
               readline: bool = True, window: tuple | None = None, cap_band: tuple | None = None, cap_mode: str = "color") -> dict:
    import cv2
    import numpy as np
    S = _sheets_mod()
    outp = Path(out)
    outp.mkdir(parents=True, exist_ok=True)
    vid = Path(mp4).stem
    cap = cv2.VideoCapture(mp4)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1920
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1080
    cap.release()
    y1 = min(y1, H)
    sys.argv = ["sheets.py", mp4, str(outp), "--fps", str(fps), "--y0", str(y0), "--y1", str(y1)]
    S.main()                                     # sheet_<id>_NN.jpg + change_<id>.json
    ch = json.loads((outp / f"change_{vid}.json").read_text(encoding="utf-8"))
    changes = [c["t"] for c in ch["changes"]][:max_strips]
    sdir = outp / "strips"
    sdir.mkdir(exist_ok=True)
    # 바뀌는 지점마다 ±0.3초 를 0.1초 띠로(한 번 훑기)
    wins = [(max(0, t - 0.3), t + 0.3) for t in changes]
    buf = defaultdict(list)
    for t, f in S.frames(mp4, 10):
        for i, (a, b) in enumerate(wins):
            if a - 0.01 <= t <= b + 0.01:
                c = f[y0:y1].copy()
                cv2.putText(c, f"{t:.1f}", (5, 30), 0, 1, (0, 0, 0), 5)
                cv2.putText(c, f"{t:.1f}", (5, 30), 0, 1, (0, 255, 255), 2)
                buf[i].append(cv2.resize(c, None, fx=0.5, fy=0.5))
    items = []
    for i, t in enumerate(changes):
        if not buf[i]:
            continue
        g = np.vstack(buf[i])
        sp = sdir / f"strip_{vid}_{t:05.1f}.jpg"
        sp.write_bytes(cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())
        items.append({"t": t, "strip": str(sp), "why": "글자 띠 변화", "y": next((r["y"] for r in ch["all"] if r["t"] == t), None)})
    lst = {"id": vid, "mp4": mp4, "band": [y0, y1], "fps_sheet": fps, "n_changes": len(ch["changes"]), "n_strips": len(items),
           "sheets": sorted(str(p) for p in outp.glob(f"sheet_{vid}_*.jpg")), "strips": items,
           "note": "판독은 사람 눈 — 시트 0.5초 칸만 보지 말고 strips 의 0.1초 띠에서 바뀌는 프레임을 확대해 본다(지침서 §0 2)"}
    if readline:   # 30fps 픽셀 실측(지시서 13 · 표준 §11 ⑫) — 줄판독 build_lr 의 입력 seg_/cut_ 과 사람 눈용 segsheet
        tall = (y1 - y0) >= 0.4 * H          # 띠가 크면 = 영상 창(kal.py step_frames 가 창을 준다), 작으면 = 자막 띠
        lst["readline"] = readline_measure(mp4, outp, cap_band or (None if tall else (y0, y1)),
                                           window or ((y0, y1) if tall else (0, H)), W, cap_mode)
    (outp / f"판독목록_{vid}.json").write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
    return lst


def readline_measure(mp4: str, outp: Path, cap_band: tuple | None, window: tuple, width: int = 1080, mode: str = "color") -> dict:
    """판독 도구(engine/readline_tools) 를 부른다 — 컷 cutdet(창) · 자막 띠 capseg + 구간 시트 segsheet(자막 띠를 알 때만).
    판단은 각 도구가 한 곳에서. 자막 띠를 모르면 capseg 를 짐작 띠로 돌리지 않고 건너뛴다(--cap-band)."""
    from tools.calcopy.engine.readline_tools import capseg as _cs, cutdet as _cd, segsheet as _ss
    vid = Path(mp4).stem
    cd = _cd.cutdet(mp4, int(window[0]), int(window[1]), width=width)
    (outp / f"cut_{vid}.json").write_text(json.dumps(cd, indent=0), encoding="utf-8")
    r = {"cut": str(outp / f"cut_{vid}.json"), "n_cut": len(cd["cuts"]), "window": [int(window[0]), int(window[1])],
         "build_lr": f"py tools/calcopy/engine/readline_tools/build_lr.py <spec.py> <out.json> --work {outp} --mp4 {mp4}"}
    if not cap_band:
        r["capseg"] = "건너뜀: 자막 띠 모름 — kal_analyze frames --cap-band y0,y1 로 다시"
        return r
    y0, y1 = int(cap_band[0]), int(cap_band[1])
    segs = _cs.capseg(mp4, y0, y1, width=width, mode=mode)
    (outp / f"seg_{vid}.json").write_text(json.dumps(segs, ensure_ascii=False, indent=0), encoding="utf-8")
    sh = _ss.segsheet(mp4, segs, str(outp / f"segsheet_{vid}"), y0, y1)
    r.update({"seg": str(outp / f"seg_{vid}.json"), "n_seg": len(segs), "segsheets": sh["sheets"], "band": [y0, y1], "mode": mode})
    return r


# ---------------------------------------------------------------- palette (채널 색 팔레트 — 역할별 hex·편 수)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def _hexes(v) -> list[str]:
    return [h.upper() for h in _HEX.findall(json.dumps(v, ensure_ascii=False))] if v is not None else []


def palette_of(docs: list[dict]) -> dict:
    """(판단 주인) 줄판독 모음 → 역할별 색 팔레트 {role: [{hex, n_lines, n_docs, docs}]}. 픽셀 중앙값은 줄판독이 적은 hex 그대로(확대 크롭 중앙값)."""
    roles = {"본문": Counter(), "강조": Counter(), "외곽선": Counter(), "글로우": Counter(), "제목": Counter(), "스티커": Counter(), "출처": Counter()}
    docs_of = defaultdict(lambda: defaultdict(set))

    def put(role, hexes, vid):
        for h in hexes:
            roles[role][h] += 1
            docs_of[role][h].add(vid)
    for d in docs:
        vid = d.get("id")
        for t in d.get("title_lines") or []:
            put("제목", _hexes(t.get("colors") if isinstance(t, dict) else t), vid)
        put("출처", _hexes((d.get("layout") or {}).get("source_hex")), vid)
        for l in d.get("lines") or []:
            if "원본" in str(l.get("layer") or ""):
                continue
            put("본문", _hexes(l.get("fill_hex")), vid)
            put("강조", [h for e in (l.get("emph") or []) for h in _hexes(e.get("hex") if isinstance(e, dict) else e)], vid)
            put("외곽선", _hexes(l.get("outline")), vid)
            put("글로우", _hexes(l.get("glow")), vid)
            put("스티커", [h for st in (l.get("sticker") or []) for h in _hexes(st)], vid)
    out = {"n_docs": len(docs), "roles": {}}
    for role, c in roles.items():
        out["roles"][role] = [{"hex": h, "n_lines": n, "n_docs": len(docs_of[role][h]), "docs": sorted(docs_of[role][h])}
                              for h, n in c.most_common()]
    # 비슷한 색 묶기(채널 최대차 ≤ 12 = 같은 색으로 본다 · compare frame.bg_rgb 8 보다 넉넉)
    def rgb(h):
        return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    for role, lst in out["roles"].items():
        groups = []
        for it in lst:
            for g in groups:
                if max(abs(a - b) for a, b in zip(rgb(g["hex"]), rgb(it["hex"]))) <= 12:
                    g["members"].append(it["hex"]); g["n_lines"] += it["n_lines"]; g["docs"] = sorted(set(g["docs"]) | set(it["docs"])); g["n_docs"] = len(g["docs"])
                    break
            else:
                groups.append({**it, "members": [it["hex"]]})
        out["roles"][role] = groups
    return out


# ---------------------------------------------------------------- script (대본 언어 — 어미·말꼴·자수·연결어·감탄어)
_ENDINGS = ("다는데", "라는데", "다네요", "라네요", "대요", "래요", "더라고요", "더라고", "는데요", "거든요", "잖아요", "잖아", "다고?", "라고?", "다고", "라고",
            "네요", "어요", "아요", "해요", "에요", "예요", "습니다", "ㅂ니다", "입니다", "죠", "지", "다", "야", "래", "지?", "요?", "가요?", "나요?", "까?", "니?")
_HONOR = ("요", "습니다", "ㅂ니다", "죠", "네요", "세요")
_REPORT = ("다는데", "라는데", "다네요", "라네요", "대요", "래요", "다고", "라고", "다더라", "라더라", "다던데", "라던데")
_CONNECT = ("근데", "그런데", "하지만", "그래서", "결국", "알고 보니", "알고보니", "그러자", "그때", "그 순간", "사실", "심지어", "게다가", "그리고", "일단", "바로", "진짜")
_EXCLAIM = ("잉?", "와우", "헐", "대박", "미쳤", "소름", "진짜?", "엥?", "어머", "오~", "와~", "ㅋㅋ", "ㅎㅎ", "ㄷㄷ", "ㅠ")


def _ending(text: str) -> str:
    t = re.sub(r"[\s.…?!~]+$", "", (text or "").strip())   # '있다는데..?' → '있다는데'
    for e in sorted(_ENDINGS, key=len, reverse=True):
        if t.endswith(e):
            return e
    return t[-2:] if len(t) >= 2 else t


def script_of(docs: list[dict]) -> dict:
    """(판단 주인) 줄판독 → 화자별 어미 분포·말꼴(존댓말/반말/전언)·자수 분포·연결어·감탄어·역할별 어미. 줄 = 자막 조각이므로 '줄 끝 어미'는 조각 끝 기준(문장 끝은 ?·!·다/요 로 끝나는 조각만)."""
    out = {}
    for sp in ("나레", "원음", "제3자"):    # 제3자 = 나레 없는 자막썰의 댓글카드 글(별헤는쏭 10-27) — 노래 가사 층은 대본이 아니라 뺀다
        texts, roles = [], []
        for d in docs:
            for l in d.get("lines") or []:
                lay = str(l.get("layer") or "")
                if _sp(l.get("speaker")) == sp and "원본" not in lay and "가사" not in lay:
                    texts.append(str(l.get("text") or "")); roles.append(str(l.get("role") or "역할없음").split("·")[0])
        if not texts:
            continue
        sent = [(t, r) for t, r in zip(texts, roles) if re.search(r"[?!.…]$|[다요죠래지야]\s*$", t.strip())]
        end = Counter(_ending(t) for t, _ in sent)
        by_role = defaultdict(Counter)
        for t, r in sent:
            by_role[r][_ending(t)] += 1
        n = len(sent) or 1
        honor = sum(any(_ending(t).endswith(h) for h in _HONOR) for t, _ in sent)
        report = sum(any(e in t[-6:] for e in _REPORT) for t, _ in sent)
        q = sum(t.strip().endswith("?") for t, _ in sent)
        chars = [_chars(t) for t in texts]
        conn = Counter(c for t in texts for c in _CONNECT if c in t)
        exc = Counter(c for t in texts for c in _EXCLAIM if c in t)
        out[sp] = {"n_chunks": len(texts), "n_sentence_end": len(sent),
                   "endings": [{"ending": e, "k": k, "rate": round(k / n, 2)} for e, k in end.most_common(12)],
                   "endings_by_role": {r: dict(c.most_common(5)) for r, c in by_role.items()},
                   "honorific_rate": round(honor / n, 2), "report_rate": round(report / n, 2), "question_rate": round(q / n, 2),
                   "chars": {"med": statistics.median(chars), "p10": sorted(chars)[int(len(chars) * .1)], "p90": sorted(chars)[int(len(chars) * .9)], "max": max(chars)},
                   "connectors": dict(conn.most_common(10)), "exclaims": dict(exc.most_common(10)),
                   "first_lines": [str((d.get("lines") or [{}])[0].get("text") or "") for d in docs if _sp((d.get("lines") or [{}])[0].get("speaker")) == sp][:8],
                   **_flow_of(docs, sp)}
    return out


def script_extra(docs: list[dict]) -> dict:
    """편 단위 대본 칸(화자 무관) — script_of(화자별 표, 소비처가 화자 이름으로 돎)와 따로 둔다: 끝맺음 꼴(rules-11)·제목 통계(rules-25)."""
    return {"end_forms": end_forms(docs), "title_stats": title_stats(docs)}


_CONNECT_END = ("는데", "은데", "고", "더니", "면서", "서", "니까", "지만")     # rules-12 이어지는 조각 끝
_CLOSE_END = ("다", "요", "죠", "까", "네", "래")                                 # rules-12 맺는 조각 끝


def _flow_of(docs: list[dict], sp: str) -> dict:
    """rules-12(Jev 해결 0.64): 자리별(훅·본문·끝 — _pos) 어미 분포 · 같은 어미 연달아 비율 · 잇는 끝:맺는 끝 · 문장(맺는 끝까지 조각 합침) 자수 중앙."""
    pos_end, runs, pairs, sent_chars = defaultdict(Counter), 0, 0, []
    conn = close = 0
    for d in docs:
        dur = float(d.get("dur") or 0)
        L = [l for l in d.get("lines") or [] if _sp(l.get("speaker")) == sp and "원본" not in str(l.get("layer") or "")]
        prev, acc = None, 0
        for l in L:
            t = str(l.get("text") or "").strip()
            e = _ending(t)
            pos_end[_pos(l, dur)][e] += 1
            if prev is not None:
                pairs += 1
                runs += int(e == prev)
            prev = e
            bare = re.sub(r"[\s.…?!~]+$", "", t)
            acc += _chars(t)
            if bare.endswith(_CONNECT_END):
                conn += 1
            elif bare.endswith(_CLOSE_END) or re.search(r"[?!.]$", t):
                close += 1
                sent_chars.append(acc)
                acc = 0
    return {"endings_by_pos": {k: dict(v.most_common(5)) for k, v in pos_end.items()},
            "same_ending_run": round(runs / pairs, 2) if pairs else None,
            "connect_vs_close": f"{conn}:{close}", "sentence_chars_med": statistics.median(sent_chars) if sent_chars else None}


END_FORMS = ("구독CTA", "질문", "예고", "요약", "쿠션", "전언", "감상", "없음")   # rules-11 끝맺음 꼴(분류기 end_form 한 곳 — 벤치·우리 같은 자)


def end_form(texts: list[str]) -> dict:
    """(판단 주인 · rules-11) 마지막 3줄 글 → {form, cta, teaser}. 낱말 규칙 — 벤치 줄판독·우리 우리줄 둘 다 이것으로 잰다."""
    t = " ".join(str(x or "") for x in texts[-3:])
    cta = bool(re.search(r"구독|좋아요|알림", t))
    teaser = "다음 편" in t or "다음편" in t or "2탄" in t
    if cta:
        f = "구독CTA"
    elif teaser:
        f = "예고"
    elif t.strip().endswith("?") or re.search(r"(어떠|어때|어떻게 생각)", t):
        f = "질문"
    elif re.search(r"도움이 되|참고하", t):
        f = "쿠션"
    elif re.search(r"(결국|정리하면|한마디로|요약)", t):
        f = "요약"
    elif any(r in t for r in _REPORT):
        f = "전언"
    elif re.search(r"(ㅋㅋ|ㅠ|대박|소름|미쳤|감동|놀랍)", t):
        f = "감상"
    else:
        f = "없음"
    return {"form": f, "cta": cta, "teaser": teaser}


def _last_texts(lines: list[dict]) -> list[str]:
    L = sorted([l for l in lines if (l.get("layer") or "채널") != "원본박힘" and str(l.get("text") or "").strip()], key=lambda l: float(l.get("t0") or 0))
    return [str(l.get("text")) for l in L[-3:]]


def end_forms(docs: list[dict]) -> dict:
    rows = [end_form(_last_texts(d.get("lines") or [])) for d in docs]
    c = Counter(r["form"] for r in rows)
    return {"mode": c.most_common(1)[0][0] if c else None, "dist": dict(c), "cta_rate": round(sum(r["cta"] for r in rows) / len(rows), 2) if rows else None,
            "teaser_n": sum(r["teaser"] for r in rows), "n": len(rows)}


def title_stats(docs: list[dict]) -> dict | None:
    """rules-25: 줄판독 화면 제목 줄(title_lines) — 자수 중앙(공백 포함/뺌)·어절 중앙·줄 수 최빈·마침표/느낌표/물음표/이모지 비율."""
    T = []
    for d in docs:
        ls = [str(t.get("text") if isinstance(t, dict) else t or "") for t in d.get("title_lines") or []]
        ls = [x for x in ls if x.strip()]
        if ls:
            T.append(ls)
    if not T:
        return None
    full = [" ".join(x) for x in T]
    emo = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    return {"n": len(T), "chars_med": statistics.median(len(x) for x in full), "chars_nospace_med": statistics.median(len(re.sub(r"\s", "", x)) for x in full),
            "words_med": statistics.median(len(x.split()) for x in full), "lines_mode": Counter(len(x) for x in T).most_common(1)[0][0],
            **{f"{k}_rate": round(sum(ch in x for x in full) / len(full), 2) for k, ch in (("period", "."), ("bang", "!"), ("question", "?"))},
            "emoji_rate": round(sum(bool(emo.search(x)) for x in full) / len(full), 2)}


def write_rules(ch_dir, docs: list[dict], title: str = "") -> dict:
    """(주인 · 지침서 §2-2 ⑤ 산출물 쓰기 한 곳) 줄판독 모음 → _kal/규칙빈도_초안.md·규칙빈도.json·대본언어.md·대본언어.json + 팔레트.json.
    집 PC kal.py step_rules 와 회원 흐름 실행기 bm_rules 가 둘 다 이것을 부른다(쓰는 자리 두 벌 금지). 판단은 rules_of·script_of·palette_of."""
    ch = Path(ch_dir)
    kd = ch / "_kal"
    kd.mkdir(parents=True, exist_ok=True)
    R, Sc, P, X = rules_of(docs), script_of(docs), palette_of(docs), script_extra(docs)
    (kd / "규칙빈도_초안.md").write_text(rules_md(R, title), encoding="utf-8")
    (kd / "규칙빈도.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    (kd / "대본언어.md").write_text(script_md(Sc), encoding="utf-8")
    (kd / "대본언어.json").write_text(json.dumps(Sc, ensure_ascii=False, indent=1), encoding="utf-8")
    (kd / "대본언어_편.json").write_text(json.dumps(X, ensure_ascii=False, indent=1), encoding="utf-8")   # rules-11·25
    (ch / "팔레트.json").write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"rules": R, "script": Sc, "palette": P, "script_extra": X}


def script_md(S: dict) -> str:
    L = ["# 대본 언어(kal_analyze script)", ""]
    for sp, r in S.items():
        L += [f"## {sp} — 조각 {r['n_chunks']} · 문장 끝 조각 {r['n_sentence_end']} · 존댓말 {r['honorific_rate']} · 전언 {r['report_rate']} · 의문 {r['question_rate']} · 자수 중앙 {r['chars']['med']}(p10 {r['chars']['p10']}·p90 {r['chars']['p90']}·max {r['chars']['max']})",
              "| 어미 | k | 비율 |", "|---|---|---|"] + [f"| {e['ending']} | {e['k']} | {e['rate']} |" for e in r["endings"]]
        L += ["", "역할별 어미: " + " · ".join(f"{k}={v}" for k, v in r["endings_by_role"].items()),
              "연결어: " + ", ".join(f"{k} {v}" for k, v in r["connectors"].items()) or "연결어: 없음",
              "감탄어: " + ", ".join(f"{k} {v}" for k, v in r["exclaims"].items()) or "감탄어: 없음",
              "첫 줄: " + " / ".join(r["first_lines"]), ""]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- framecmp (벤치 프레임 ↔ 우리 프레임, 같은 좌표 띠에서 잉크 상자·색·좌표 차)
FRAME_PASS = {"xy_px": 4, "h_px": 4, "dE": 5.0}   # 좌표 ±4px(compare frame.caption_band 와 같은 폭) · 색 ΔE76 <5(사장님 ④ 예시, 실측으로 재조정)


def _lab(rgb):
    import numpy as np
    c = np.array(rgb, float) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = M @ c / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


DARK_BG_V = 60   # readlines-08: 고리 바깥 배경 밝기 중앙이 이보다 어두우면 검정 외곽선을 배경과 못 가른다


def outline_of(dark_hex: str | None, bg_v: float | None) -> dict:
    """(판단 주인 · readlines-08) 외곽선 색 — 배경이 어두우면(V < DARK_BG_V) 판별 불가(None)로 적고 판에서는 외곽선 없음으로 둔다."""
    if bg_v is not None and bg_v < DARK_BG_V:
        return {"outline_hex": None, "outline": "판별 불가", "bg_v": round(bg_v, 1)}
    return {"outline_hex": dark_hex, "outline": "있음" if dark_hex else "없음", "bg_v": None if bg_v is None else round(bg_v, 1)}


def frame_metrics(png: str, band: tuple) -> dict:
    """한 프레임의 자막 띠 안 글자 잉크: 상자(x0,y0,x1,y1)·높이·채움색 중앙값 hex·외곽 어두운 색 중앙값."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.fromfile(png, np.uint8), cv2.IMREAD_COLOR)   # 한글 경로: imread 는 조용히 None
    if img is None:
        raise FileNotFoundError(png)
    S = _sheets_mod()
    y0, y1 = band
    crop = img[y0:y1]
    m = S.text_mask(crop)
    # 글자 띠 = 행 밀도가 최대의 25% 넘는 가장 긴 연속 구간(밝은 옷·피부가 외곽선 옆에서 새는 성긴 행을 자른다 — VbpdN 11.0 실측 h75→56)
    def run(prof, frac=0.25, win=15):
        prof = np.convolve(prof.astype(float), np.ones(win) / win, mode="same")   # 글자 가로획 사이 빈 행을 메운다(15px 이동 평균)
        th = prof.max() * frac
        best, cur = (0, -1), None
        for i, v in enumerate(prof):
            if v > th:
                cur = i if cur is None else cur
                if i - cur > best[1] - best[0]:
                    best = (cur, i)
            else:
                cur = None
        return best
    r0, r1 = run(m.sum(1))
    if r1 < 0 or m[r0:r1 + 1].sum() < 20:
        return {"ink": int(m.sum()), "box": None}
    c0, c1 = run(m[r0:r1 + 1].sum(0), 0.05, win=61)   # 어절 사이 빈 칸(~25px)을 넘긴다
    m[:r0] = 0; m[r1 + 1:] = 0
    ys, xs = np.where(m > 0)
    box = [int(c0), int(r0) + y0, int(c1), int(r1) + y0]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    bright = (hsv[..., 2] > 215)
    fill = crop[(m > 0) & bright]
    ring = (cv2.dilate(m, np.ones((7, 7), np.uint8)) > 0)
    dark = crop[ring & (hsv[..., 2] < 60)]
    outside = (cv2.dilate(m, np.ones((21, 21), np.uint8)) > 0) & ~ring       # 고리 바깥 배경(readlines-08)
    bg_v = float(np.median(hsv[..., 2][outside])) if outside.any() else None
    def med(px):
        if len(px) == 0:
            return None
        b, g, r = np.median(px, axis=0).astype(int)
        return f"#{r:02X}{g:02X}{b:02X}"
    # 행간·자간 근사: 잉크 행 투영에서 빈 줄 간격 / 열 투영에서 글자 사이 빈 칸 중앙값
    rows = (m.sum(1) > 3).astype(int)
    gaps_r = [len(g) for g in re.findall(r"0+", "".join(map(str, rows[int(ys.min()):int(ys.max()) + 1])))]
    cols = (m[int(ys.min()):int(ys.max()) + 1].sum(0) > 2).astype(int)
    gaps_c = [len(g) for g in re.findall(r"0+", "".join(map(str, cols[int(xs.min()):int(xs.max()) + 1])))]
    letters = [g for g in gaps_c if g <= 40]       # 40px 넘는 빈 칸 = 어절·줄 끝 — 글자 사이가 아니다. 전부 넘으면 표본 0(미측정 — median([]) 로 죽지 않는다, 10-25)
    return {"ink": int(m.sum()), "box": box, "h": box[3] - box[1], "cx": (box[0] + box[2]) // 2,
            "fill_hex": med(fill), **outline_of(med(dark), bg_v),
            "line_gap_px": statistics.median(gaps_r) if gaps_r else 0,
            "letter_gap_px": statistics.median(letters) if letters else (0 if not gaps_c else None),
            "letter_gap_n": len(letters), "letter_gap_dropped": len(gaps_c) - len(letters)}


SKIN_DIFF = {"y_px": 12, "dE": 10.0}   # 업그레이드 뒤 "얼마나 달라졌나" 측정 기준(지침서 §2-6-1 — 목표·합격선이 아니다)


def frame_compare(bench_png: str, ours_png: str, band: tuple, skin: bool = False) -> dict:
    """skin=False: 1차 프리셋 — 같아야 통과(FRAME_PASS). skin=True: 업그레이드 뒤 달라진 정도 측정(SKIN_DIFF 넘으면 '달라짐' 표시, 판정 아님)."""
    import numpy as np
    a, b = frame_metrics(bench_png, band), frame_metrics(ours_png, band)
    rows = []
    if skin:
        if not (a.get("box") and b.get("box")):
            return {"bench": a, "ours": b, "rows": [{"key": "ink", "bench": a.get("ink"), "ours": b.get("ink"), "diff": "글자 못 찾음", "pass": False}], "verdict": "측정 불가", "pass_rule": SKIN_DIFF}
        dy = abs(b["box"][1] - a["box"][1])
        rows.append({"key": "y0 차(≥12 달라짐)", "bench": a["box"][1], "ours": b["box"][1], "diff": dy, "pass": dy >= SKIN_DIFF["y_px"]})
        for k in ("fill_hex", "outline_hex"):
            if a.get(k) and b.get(k):
                dE = float(np.linalg.norm(_lab([int(a[k][i:i + 2], 16) for i in (1, 3, 5)]) - _lab([int(b[k][i:i + 2], 16) for i in (1, 3, 5)])))
                rows.append({"key": f"{k} ΔE(≥10 달라짐)", "bench": a[k], "ours": b[k], "diff": round(dE, 1), "pass": dE >= SKIN_DIFF["dE"]})
        return {"bench": a, "ours": b, "rows": rows, "verdict": "달라짐" if any(r["pass"] for r in rows) else "벤치와 같음(업그레이드 개선 없음)", "pass_rule": SKIN_DIFF}
    if a.get("box") and b.get("box"):
        rows.append({"key": "cx(가운데 x)", "bench": a["cx"], "ours": b["cx"], "diff": b["cx"] - a["cx"], "pass": abs(b["cx"] - a["cx"]) <= FRAME_PASS["xy_px"]})
        rows.append({"key": "y0(잉크 위)", "bench": a["box"][1], "ours": b["box"][1], "diff": b["box"][1] - a["box"][1], "pass": abs(b["box"][1] - a["box"][1]) <= FRAME_PASS["xy_px"]})
        rows.append({"key": "h(잉크 높이)", "bench": a["h"], "ours": b["h"], "diff": b["h"] - a["h"], "pass": abs(b["h"] - a["h"]) <= FRAME_PASS["h_px"]})
        if a["letter_gap_px"] is None or b["letter_gap_px"] is None:      # 글자 사이 표본 0 — 이 칸은 미측정(통과 아님), 장수는 letter_gap_n 에
            rows.append({"key": "letter_gap_px", "bench": a["letter_gap_px"], "ours": b["letter_gap_px"], "diff": "표본 없음(미측정)", "pass": False})
        else:
            rows.append({"key": "letter_gap_px", "bench": a["letter_gap_px"], "ours": b["letter_gap_px"], "diff": b["letter_gap_px"] - a["letter_gap_px"],
                         "pass": abs(b["letter_gap_px"] - a["letter_gap_px"]) <= 2})
        for k in ("fill_hex", "outline_hex"):
            if a.get(k) and b.get(k):
                dE = float(np.linalg.norm(_lab([int(a[k][i:i + 2], 16) for i in (1, 3, 5)]) - _lab([int(b[k][i:i + 2], 16) for i in (1, 3, 5)])))
                rows.append({"key": k, "bench": a[k], "ours": b[k], "diff": round(dE, 1), "pass": dE < FRAME_PASS["dE"]})
    else:
        rows.append({"key": "ink", "bench": a.get("ink"), "ours": b.get("ink"), "diff": "글자 못 찾음", "pass": False})
    return {"bench": a, "ours": b, "rows": rows, "verdict": "통과" if rows and all(r["pass"] for r in rows) else "미달", "pass_rule": FRAME_PASS}


# ---------------------------------------------------------------- CLI
def _load_docs(paths: list[str]) -> list[dict]:
    files = []
    for p in paths:
        P = Path(p)
        files += sorted(P.glob("*.json")) if P.is_dir() else [P]
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("frames"); a.add_argument("mp4"); a.add_argument("--out", required=True)
    a.add_argument("--y0", type=int, default=0); a.add_argument("--y1", type=int, default=1920); a.add_argument("--fps", type=float, default=2); a.add_argument("--max-strips", type=int, default=80)
    a.add_argument("--no-readline", action="store_true", help="30fps capseg/cutdet/segsheet 건너뜀"); a.add_argument("--window", help="컷 검출 창 y0,y1"); a.add_argument("--cap-band", help="capseg 자막 띠 y0,y1")
    b = sub.add_parser("skeleton"); b.add_argument("tteutgi"); b.add_argument("--vtt"); b.add_argument("--out", required=True); b.add_argument("--id")
    b.add_argument("--spec", help="눈으로 적은 spec.py — 주면 readline_tools.build_lr 로 줄판독을 조립(tteutgi 자리 = frames 폴더)"); b.add_argument("--mp4"); b.add_argument("--sfx-raw"); b.add_argument("--profile")
    c = sub.add_parser("check"); c.add_argument("paths", nargs="+"); c.add_argument("--strict", action="store_true")
    r = sub.add_parser("rules"); r.add_argument("paths", nargs="+"); r.add_argument("--out"); r.add_argument("--json")
    pa = sub.add_parser("palette"); pa.add_argument("paths", nargs="+"); pa.add_argument("--out", required=True)
    sc = sub.add_parser("script"); sc.add_argument("paths", nargs="+"); sc.add_argument("--out"); sc.add_argument("--json")
    fc = sub.add_parser("framecmp"); fc.add_argument("bench_png"); fc.add_argument("ours_png"); fc.add_argument("--band", required=True, help="y0,y1"); fc.add_argument("--out"); fc.add_argument("--skin", action="store_true", help="업그레이드 뒤 달라진 정도 측정(판정 아님)")
    m = sub.add_parser("match"); m.add_argument("--bench", required=True); m.add_argument("--ours", required=True)
    m.add_argument("--ours-mp4"); m.add_argument("--bench-src", help="벤치 원본 mp4 폴더(같은 자로 컷·LUFS)"); m.add_argument("--bench-tteutgi", help="(대안) 뜯기 값 — 자가 다름")
    m.add_argument("--win", help="영상 창 x,y,w,h (없으면 줄판독 layout.window)"); m.add_argument("--out"); m.add_argument("--title", default="")
    m.add_argument("--bench-mp4", help="벤치 대표 1편 mp4 — 주면 픽셀·소리 자(compare)까지 한 판정으로(1차 프리셋 관문)")
    A = ap.parse_args(argv)
    if A.cmd == "frames":
        win = tuple(int(v) for v in A.window.split(",")) if A.window else None
        cb = tuple(int(v) for v in A.cap_band.split(",")) if A.cap_band else None
        lst = frames_cmd(A.mp4, A.out, A.y0, A.y1, A.fps, A.max_strips, readline=not A.no_readline, window=win, cap_band=cb)
        print(f"{lst['id']} 시트 {len(lst['sheets'])} 변화 {lst['n_changes']} 띠 {lst['n_strips']} → {A.out}")
        return 0
    if A.cmd == "skeleton" and A.spec:
        if not A.mp4:
            ap.error("skeleton --spec 는 --mp4 가 필요하다")
        from tools.calcopy.engine.readline_tools import build_lr as _bl
        return _bl.main([A.spec, A.out, "--work", A.tteutgi, "--mp4", A.mp4] + (["--sfx-raw", A.sfx_raw] if A.sfx_raw else [])
                        + (["--profile", A.profile] if A.profile else []))
    if A.cmd == "skeleton":
        tt = json.loads(Path(A.tteutgi).read_text(encoding="utf-8"))
        vid = A.id or Path(A.tteutgi).parent.name
        d = skeleton(vid, tt, A.vtt)
        Path(A.out).parent.mkdir(parents=True, exist_ok=True)
        Path(A.out).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{vid} 뼈대 줄 {len(d['lines'])} → {A.out} (_todo {len(d['_todo'])} 칸은 눈으로)")
        return 0
    if A.cmd == "check":
        bad = 0
        for p in A.paths:
            P = Path(p)
            for f in (sorted(P.glob("*.json")) if P.is_dir() else [P]):
                d = json.loads(f.read_text(encoding="utf-8"))
                r = check_doc(d, strict=A.strict)
                bad += bool(r["errors"])
                print(f"{f.name}: 오류 {len(r['errors'])} 경고 {len(r['warnings'])} (줄 {len(d.get('lines') or [])})")
                for e in r["errors"]:
                    print("   ✗", e)
                if A.strict:
                    for w in r["warnings"][:5]:
                        print("   △", w)
        return 1 if bad else 0
    if A.cmd == "rules":
        docs = _load_docs(A.paths)
        R = rules_of(docs)
        md = rules_md(R, A.paths[0])
        if A.out:
            Path(A.out).write_text(md, encoding="utf-8")
        if A.json:
            Path(A.json).write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
        print(md if not A.out else f"편 {R['n_docs']} 규칙 후보 {len(R['rules'])} → {A.out}")
        return 0
    if A.cmd == "palette":
        P = palette_of(_load_docs(A.paths))
        Path(A.out).write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
        for role, lst in P["roles"].items():
            print(role, [(g["hex"], g["n_lines"], g["n_docs"]) for g in lst[:6]])
        return 0
    if A.cmd == "script":
        S = script_of(_load_docs(A.paths))
        md = script_md(S)
        if A.out:
            Path(A.out).write_text(md, encoding="utf-8")
        if A.json:
            Path(A.json).write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
        print(md if not A.out else f"→ {A.out}")
        return 0
    if A.cmd == "framecmp":
        y0, y1 = [int(v) for v in A.band.split(",")]
        T = frame_compare(A.bench_png, A.ours_png, (y0, y1), skin=A.skin)
        if A.out:
            Path(A.out).write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        for r in T["rows"]:
            print(f"{r['key']:14} 벤치 {r['bench']} 우리 {r['ours']} 차 {r['diff']} {'✓' if r['pass'] else '✗'}")
        print("판정", T["verdict"], T["pass_rule"])
        return 0 if T["verdict"] == "통과" else 1
    if A.cmd == "match":
        bench = _load_docs([A.bench])
        ours = json.loads(Path(A.ours).read_text(encoding="utf-8"))
        win = _win_arg(A.win, bench)
        om = media_of(A.ours_mp4, win) if A.ours_mp4 else None
        ids = [d.get("id") for d in bench]
        bm = bench_media_src(A.bench_src, ids, win) if A.bench_src else (bench_media_of(A.bench_tteutgi, ids) if A.bench_tteutgi else None)
        T = match_table(bench, ours, om, bm)
        T["ours_media"], T["bench_media"] = om, bm
        if A.bench_mp4 and A.ours_mp4:
            with_pixel(T, A.bench_mp4, A.ours_mp4, str(Path(A.out).with_suffix("")) + "_픽셀" if A.out else "_match_픽셀")
        md = match_md(T, A.title)
        if A.out:
            Path(A.out).write_text(md, encoding="utf-8")
            Path(A.out).with_suffix(".json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        print(md)
        return 0 if T["verdict"] == "통과" else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
