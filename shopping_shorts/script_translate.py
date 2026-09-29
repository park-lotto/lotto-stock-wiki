# -*- coding: utf-8 -*-
"""대본 영어모드 변환(2026-09-29 사장님 "한국어 대본 뽑고 영어모드로 변환만 되게").

★판단 주인: 이 파일 `to_english` 하나(관제 029). 한국어 대본은 지금 경로(스타일·검사·장면 매칭) 그대로
  끝내고, 5단계에서 **문장별 번역만** 한다. 프롬프트·게이트·스파인은 건드리지 않는다.
★계약: 줄 수가 같아야 한다 — 비트마다 장면(covers·src_seg)이 문장 순서에 묶여 있어 줄이 늘거나
  줄면 컷 배정이 어긋난다. 어긋나면 ValueError(호출부가 화면에 그대로 띄운다). 조용히 잘라 맞추지 않는다.
"""
import re

from shopping_shorts import script_generate

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")

_PROMPT = """You are translating a Korean short-form shopping video narration into natural spoken American English.
Translate EACH line separately and return exactly {n} lines in the same order.

Rules:
- Keep it conversational and punchy, like a TikTok/YouTube Shorts voice-over (short sentences, contractions OK).
- Keep the meaning, product name{product_hint}, numbers and calls to action. Do not add or drop information.
- One output line per input line. Never merge or split lines. Never leave a line empty.
- Output English only (no Korean, no notes, no quotes around lines).

Input lines (JSON array):
{lines}
"""

_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
}


def is_english(text):
    """영어 문장인가 — 한글이 없고 라틴 글자가 있으면 참. (naturalize 우회·모드 판정이 같이 쓴다)"""
    t = text or ""
    return bool(_LATIN.search(t)) and not _HANGUL.search(t)


def english_ratio(lines):
    """줄 목록 중 영어 줄 비율(0~1). 검사 도구·테스트가 쓴다."""
    ls = [x for x in (lines or []) if (x or "").strip()]
    if not ls:
        return 0.0
    return sum(1 for x in ls if is_english(x)) / len(ls)


def to_english(lines, product="", *, call=None, tries=2):
    """한국어 문장 목록 → 같은 길이의 영어 문장 목록.

    call: 테스트가 갈아끼우는 (prompt, schema) -> dict. 기본은 script_generate._call_json(키풀·Vertex 깔때기).
    실패(빈 응답·줄 수 불일치·한글 잔존)는 ValueError — 호출부가 그대로 화면에 띄운다.
    """
    import json
    src = [(x or "").strip() for x in (lines or [])]
    if not src or any(not x for x in src):
        raise ValueError("번역할 문장이 비어 있어요 — 대본을 먼저 확정해 주세요")
    if all(is_english(x) for x in src):
        return list(src)          # 이미 영어 — 두 번 번역하지 않는다
    call = call or (lambda p, s: script_generate._call_json(p, s))
    hint = f" ('{product}')" if (product or "").strip() else ""
    prompt = _PROMPT.format(n=len(src), product_hint=hint,
                            lines=json.dumps(src, ensure_ascii=False))
    last = ""
    for _ in range(max(1, tries)):
        got = call(prompt, _SCHEMA) or {}
        out = [str(x or "").strip() for x in (got.get("lines") or [])]
        if len(out) != len(src):
            last = f"줄 수가 안 맞아요(원문 {len(src)}줄 → 번역 {len(out)}줄)"
            continue
        if any(not x for x in out):
            last = "빈 줄이 섞여 나왔어요"
            continue
        bad = [i for i, x in enumerate(out) if _HANGUL.search(x)]
        if bad:
            last = f"{len(bad)}줄에 한글이 남았어요"
            continue
        return out
    raise ValueError("영어 변환에 실패했어요 — " + (last or "AI 응답이 비었어요") + ". 잠시 후 다시 눌러 주세요")


def apply_lang(plan, lang, product="", *, call=None):
    """edit_plan의 비트 문장을 lang('en'|'ko')으로 바꾼다. 반환: 바뀐 비트 수.

    en: narration → narration_ko에 보관하고 영어로 교체(이미 보관돼 있으면 그 원문을 다시 번역하지 않고 재사용).
    ko: narration_ko가 있으면 되돌린다.
    ★자막 메타 무효화는 호출부(app)가 mix_pipeline.invalidate_caption_meta로 한다 — 대본이 바뀌는 모든 경로의 규칙.
    """
    beats = [b for b in (plan or {}).get("beats") or [] if isinstance(b, dict)]
    if not beats:
        raise ValueError("문장이 없어요 — 3단계 영상 매칭을 먼저 끝내 주세요")
    changed = 0
    if lang == "en":
        src = [b.get("narration_ko") or b.get("narration") or "" for b in beats]
        out = to_english(src, product, call=call)
        for b, ko, en in zip(beats, src, out):
            if not b.get("narration_ko"):
                b["narration_ko"] = ko
            if (b.get("narration") or "") != en:
                b["narration"] = en
                changed += 1
        plan["lang"] = "en"
        return changed
    if lang == "ko":
        for b in beats:
            ko = b.get("narration_ko")
            if ko and (b.get("narration") or "") != ko:
                b["narration"] = ko
                changed += 1
        plan["lang"] = "ko"
        return changed
    raise ValueError("lang은 'en' 또는 'ko'")
