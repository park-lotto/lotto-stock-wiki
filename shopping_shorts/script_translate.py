# -*- coding: utf-8 -*-
"""대본 영어모드 변환(2026-09-29 사장님 "한국어 대본 뽑고 영어모드로 변환만 되게").

★판단 주인: 이 파일 `to_english` 하나(관제 029). 한국어 대본은 지금 경로(스타일·검사·장면 매칭) 그대로
  끝내고, 5단계에서 **문장별 번역만** 한다. 프롬프트·게이트·스파인은 건드리지 않는다.
★2026-10-21 일본어모드(관제 248): 언어 판정 `lang_of` 도 여기 한 곳이다 — naturalize 우회·성우 차단·
  말속도·ASR 언어·자막 토큰·폰트 폴백이 전부 이걸 import 한다(0순위-B). 번역은 `translate(lines, lang)`.
★계약: 줄 수가 같아야 한다 — 비트마다 장면(covers·src_seg)이 문장 순서에 묶여 있어 줄이 늘거나
  줄면 컷 배정이 어긋난다. 어긋나면 ValueError(호출부가 화면에 그대로 띄운다). 조용히 잘라 맞추지 않는다.
"""
import re

from shopping_shorts import script_generate

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_JA_CHARS = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
# 자막 토큰에서 뺄 글자(공백·문장부호) — caption_tokens 와 tts_timestamps.words_from_alignment 가 같이 쓴다(한 벌).
_TOKEN_SKIP = re.compile(r"[\s、。！？!?,.…「」『』～~'\"()（）]")

LANG_LABEL = {"en": "영어", "ja": "일본어", "ko": "한국어"}   # 화면 문구 공용
# "글자로 치는 문자"(비교·중복 판정용 정규화) — 한글·숫자·라틴 + 가나·CJK 한자. 2026-10-21 라이브 e2e(job e582f0e0c9b4)에서
#   edit_plan._narr_key 가 [^0-9A-Za-z가-힣] 만 남겨 일본어 줄 11개 중 10개가 빈 키("")가 되어 enforce_script_order 가
#   칸 11 → 1 로 뭉갰다. 같은 정규식이 edit_plan(_narr_key·_dup_key)·scene_style(_word_key)·storyboard(_compact) 4벌이라
#   여기 한 곳(letters_only)으로 모은다(0순위-B).
LETTERS = "0-9A-Za-z가-힣぀-ヿ一-鿿"
_NOT_LETTERS = re.compile("[^" + LETTERS + "]+")


def letters_only(text):
    """비교·중복 판정용 정규화 — 공백·문장부호를 걷어내고 글자(한글·숫자·라틴·가나·한자)만 남긴다."""
    return _NOT_LETTERS.sub("", text or "")

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

_PROMPT_JA = """You are translating a Korean short-form shopping video narration into natural spoken Japanese (conversational です・ます調, punchy, like a TikTok/YouTube Shorts voice-over).
Translate EACH line separately and return exactly {n} lines in the same order.
Keep meaning, product name{product_hint}, numbers and calls to action.
One output line per input line, never merge/split, never empty.
Output Japanese only (no Korean, no romaji-only lines, no notes).

Style rules (2026-10-21, checked against real scripts):
- ONE consistent polite register across all lines: です・ます (〜なんです / 〜ますよ are fine). Sentence-final noun phrases (体言止め) are fine for punch. Never switch to casual imperatives (〜してね / 〜しろ); for calls to action use 〜してください(ね).
- Do not add anything that is not in the Korean line (no 「紹介します」, no 「SNSで」, no extra adjectives or framing) and do not drop anything.
- Keep product nouns faithful to the Korean words (e.g. 발난로 → 足元ヒーター, not a different product category). Keep numbers exactly; keep currency as written (원 → ウォン — never convert to 円).
- Each line must read like one short, rhythmic voice-over line (no long compound sentences).

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


_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def is_english_sentence(text):
    """영어 **문장**인가 — 한글 없이 영어 단어 3개 이상. naturalize 우회 판정은 이것만 쓴다.
    ("AI"·"3.5kg"·"A"처럼 한국어 대본에 낀 짧은 영문 토큰은 문장이 아니다 — 발음 사전·숫자 읽기가 계속 돌아야 한다.)"""
    return lang_of(text) == "en"


def lang_of(text):
    """이 문장의 언어 'ko'|'ja'|'en' — **언어 판정의 유일한 주인**(2026-10-21 관제 248, 0순위-B).
    한글이 있으면 ko · 없고 가나/CJK 한자가 있으면 ja · 그 외 영어 단어(2자+) 3개 이상이면 en · 아니면 ko.
    ("AI"·"3.5kg" 같은 짧은 영문 토큰은 한국어 대본의 일부로 본다 — is_english_sentence 종전 규칙과 같다.)"""
    t = text or ""
    if _HANGUL.search(t):
        return "ko"
    if _JA_CHARS.search(t):
        return "ja"
    if len(_LATIN_WORD.findall(t)) >= 3:
        return "en"
    return "ko"


def is_japanese(text):
    return lang_of(text) == "ja"


def is_foreign_sentence(text):
    """한국어 다듬기·한국어 계수를 건너뛸 외국어 문장인가(영어·일본어)."""
    return lang_of(text) in ("en", "ja")


def foreign_ratio(lines, lang):
    """줄 목록 중 lang_of == lang 인 줄 비율(0~1). 검사 도구가 쓴다."""
    ls = [x for x in (lines or []) if (x or "").strip()]
    if not ls:
        return 0.0
    return sum(1 for x in ls if lang_of(x) == lang) / len(ls)


def asr_language(text):
    """ASR(받아쓰기) 폴백에 줄 언어 힌트 — 일본어 'ja' · 영어 'en' · 그 외 'ko'(종전)."""
    return {"ja": "ja", "en": "en"}.get(lang_of(text), "ko")


def caption_tokens(text, lang=None):
    """자막 정렬·나누기 토큰. 일본어는 띄어쓰기가 없어 **글자 하나하나**(공백·문장부호 제외), 그 외는 split().
    lang: 조각(구절)을 셀 때 **문장 전체의 언어**로 세라고 넘긴다 — 일본어 문장 속 "OK" 같은 조각이
    한국어 규칙(split)으로 세어지면 글자 단위 ref 와 개수가 어긋난다. 없으면 text 로 판정."""
    t = text or ""
    if not t.strip():
        return []
    if (lang or lang_of(t)) == "ja":
        return [c for c in t if not _TOKEN_SKIP.match(c)]
    return t.split()


def english_ratio(lines):
    """줄 목록 중 영어 줄 비율(0~1). 검사 도구·테스트가 쓴다."""
    ls = [x for x in (lines or []) if (x or "").strip()]
    if not ls:
        return 0.0
    return sum(1 for x in ls if is_english(x)) / len(ls)


def translate(lines, lang, product="", *, call=None, tries=2):
    """한국어 문장 목록 → 같은 길이의 lang('en'|'ja') 문장 목록.

    call: 테스트가 갈아끼우는 (prompt, schema) -> dict. 기본은 script_generate._call_json(키풀·Vertex 깔때기).
    실패(빈 응답·줄 수 불일치·한글 잔존·일본어 아닌 줄)는 ValueError — 호출부가 그대로 화면에 띄운다.
    """
    import json
    if lang not in ("en", "ja"):
        raise ValueError("지원하지 않는 언어예요: %r" % (lang,))
    src = [(x or "").strip() for x in (lines or [])]
    if not src or any(not x for x in src):
        raise ValueError("번역할 문장이 비어 있어요 — 대본을 먼저 확정해 주세요")
    # 이미 그 언어면 두 번 번역하지 않는다. 영어는 종전 판정(is_english: 한글 0·라틴 있음)을 그대로 둔다(회귀 금지).
    already = is_english if lang == "en" else (lambda x: lang_of(x) == "ja")
    if all(already(x) for x in src):
        return list(src)
    call = call or (lambda p, s: script_generate._call_json(p, s))
    hint = f" ('{product}')" if (product or "").strip() else ""
    tmpl = _PROMPT if lang == "en" else _PROMPT_JA
    prompt = tmpl.format(n=len(src), product_hint=hint,
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
        if lang == "ja":
            not_ja = [i for i, x in enumerate(out) if not _JA_CHARS.search(x)]
            if not_ja:
                last = f"{len(not_ja)}줄이 일본어가 아니에요"
                continue
        return out
    raise ValueError(LANG_LABEL[lang] + " 변환에 실패했어요 — " + (last or "AI 응답이 비었어요") + ". 잠시 후 다시 눌러 주세요")


def to_english(lines, product="", *, call=None, tries=2):
    """한국어 문장 목록 → 같은 길이의 영어 문장 목록(= translate(lines, 'en')). 서명·동작은 종전 그대로."""
    return translate(lines, "en", product, call=call, tries=tries)


def job_lang(job):
    """이 작업의 대본 언어('ja'|'en'|'ko') — 판단은 여기 한 곳. edit_plan.lang이 있으면 그것, 없으면 확정 대본(given_script)의
    줄들의 lang_of 를 세어 'ja' 또는 'en' 이 80% 이상이면 그 언어(2단계에서 외국어모드로 확정한 작업은 given_script가 그 언어)."""
    plan = (job or {}).get("edit_plan") or {}
    if isinstance(plan, dict) and plan.get("lang") in ("en", "ja", "ko"):
        return plan["lang"]
    lines = [x.strip() for x in str((job or {}).get("given_script") or "").splitlines() if x.strip()]
    if not lines:
        return "ko"
    for lang in ("ja", "en"):
        if sum(1 for x in lines if lang_of(x) == lang) / len(lines) >= 0.8:
            return lang
    return "ko"
