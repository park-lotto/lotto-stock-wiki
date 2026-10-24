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
# 일본어에선 안 쓰는 간체자·중국어 허사(관제 254). 的·了 는 일본어 한자말(画期的·完了)에도 있어 넣지 않는다
_ZH_MARK = re.compile("[别很把跟你她它这们个吗呢吧么还没给让说过对时为样东车门见长发问题实现买卖单冲热线经级运动开关风饭质钱铁锅绝净脏试谁啥咋哪您俩呀啦嘛哦刷扫挂叠带边头儿该无处变软轻贵听觉认识办场]")   # 일본어 한자말에도 쓰는 글자(就·我·会·国·来·洗…)는 뺐다
_JA_CHARS = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
# 자막 토큰에서 뺄 글자(공백·문장부호) — caption_tokens 와 tts_timestamps.words_from_alignment 가 같이 쓴다(한 벌).
_TOKEN_SKIP = re.compile(r"[\s、。！？!?,.…「」『』～~'\"()（），；：“”]")

LANG_LABEL = {"en": "영어", "ja": "일본어", "ko": "한국어", "zh": "중국어"}   # 화면 문구 공용
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

_PROMPT_JA = """You are a native Japanese short-form copywriter. Rewrite a Korean shopping-shorts narration as the voice-over a Japanese TikTok/YouTube Shorts creator would actually SAY out loud.
Return exactly {n} lines in the same order, one per input line, never merge/split, never empty.
Keep meaning, product name{product_hint}, numbers and calls to action.
Output Japanese only (no Korean, no romaji-only lines, no notes).

Style rules (2026-10-23, 사장님: 일본인이 듣기에 문어체라 어색함):
- This is speech, not writing. Do NOT translate word by word: rephrase into how a Japanese person would naturally say the same thing, even if the wording changes. Korean idioms become the natural Japanese expression (기립박수 친 → 思わず拍手した / 絶賛した, 그 지옥 → あの地獄みたいな時間, 미친 발명품 → ヤバすぎる発明品).
- Register (decided from the Korean script, follow it on EVERY line): {register}
- Banned written-style patterns: 〜ということ / 文末の〜こと / 〜である / 〜にて / 〜消え去った / 〜となっております / 〜でございます / long noun-modifier chains. End lines with spoken endings instead.
- Do not add facts or phrases that are not in the Korean line (no 見つけたよ, no 急いでチェックしてみて unless the Korean line asks for it) and do not drop any. Keep product nouns faithful (발난로 → 足元ヒーター, 바지 → ズボン). Keep numbers exactly; keep currency as written (원 → ウォン, never 円).
- Each line is one short rhythmic voice-over line (about 30 Japanese characters or less, no long compound sentences).
- Feel, not grammar: the lines are ONE story told with emotion. Link them the way Japanese speakers do (でもさ / しかも / なのに / 〜したら / 〜から / 〜し), put real reactions where the Korean has them (はぁ？ / え、待って / マジで / ほんとに), and keep the Korean sound words as Japanese ones (쓱 → サッと, 딱 → ポンと, 빵빵 → パンパン, 싹 → スッキリ).
- Vary the endings like a real speaker. Never end three lines in a row the same way (not every line 〜んだよ / 〜なんだって). Mix: 体言止め, 〜じゃん, 〜の, 〜よね, 〜し, 〜ちゃう, 〜だけ.

Real lines from top Japanese shopping shorts (style reference only — do NOT copy their content):
 casual: 引越しの荷造りが終わって壁を見たらさ、ピン穴だらけだったの。 / はぁ？ってなったよね。 / ちょっと見てて、ぎゅっと絞ってヘラですーっ、それだけ。 / 30秒で穴が消えた。 / いちいち開けるの面倒だし、ナイフで切るとべっとべとになるから。 / ぽんっと出てくるのがちょっと快感。 / もうこれ、ポーチ界のチートアイテムじゃん。 / しかもご飯が全然くっつかないんだよ。
 polite: 最初は固く見えても時間が経つと緩んで、結局ネズミがまた入り込んできたんです。 / ですが、最近は全く別の方法が登場しました。 / 時間が経つほどどんどん固くなって、簡単には壊せなくなるんです。

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
    if _KANA.search(t):
        return "ja"
    if _CJK.search(t):
        # 가나 없이 한자만: 중국어 표지(간체 전용자·중국어 허사)가 있으면 중국어, 없으면 종전대로 일본어(「1980円」「送料無料」 회귀 금지).
        # 작업 전체 언어는 job_lang 이 따로 센다(가나 줄이 하나도 없으면 한자만 있는 줄 = 중국어) — 관제 254
        return "zh" if _ZH_MARK.search(t) else "ja"
    if len(_LATIN_WORD.findall(t)) >= 3:
        return "en"
    return "ko"


def is_char_lang(lang):
    """띄어쓰기 없이 **글자 하나하나**로 다루는 언어인가(일본어·중국어) — 자막 토큰·자막 나누기·타임스탬프가 같이 쓴다."""
    return lang in ("ja", "zh")


def is_japanese(text):
    return lang_of(text) == "ja"


def is_foreign_sentence(text):
    """한국어 다듬기·한국어 계수를 건너뛸 외국어 문장인가(영어·일본어·중국어)."""
    return lang_of(text) in ("en", "ja", "zh")


def foreign_ratio(lines, lang):
    """줄 목록 중 lang_of == lang 인 줄 비율(0~1). 검사 도구가 쓴다."""
    ls = [x for x in (lines or []) if (x or "").strip()]
    if not ls:
        return 0.0
    return sum(1 for x in ls if lang_of(x) == lang) / len(ls)


def asr_language(text):
    """ASR(받아쓰기) 폴백에 줄 언어 힌트 — 일본어 'ja' · 영어 'en' · 그 외 'ko'(종전)."""
    return {"ja": "ja", "en": "en", "zh": "zh"}.get(lang_of(text), "ko")


def caption_tokens(text, lang=None):
    """자막 정렬·나누기 토큰. 일본어는 띄어쓰기가 없어 **글자 하나하나**(공백·문장부호 제외), 그 외는 split().
    lang: 조각(구절)을 셀 때 **문장 전체의 언어**로 세라고 넘긴다 — 일본어 문장 속 "OK" 같은 조각이
    한국어 규칙(split)으로 세어지면 글자 단위 ref 와 개수가 어긋난다. 없으면 text 로 판정."""
    t = text or ""
    if not t.strip():
        return []
    if is_char_lang(lang or lang_of(t)):
        return [c for c in t if not _TOKEN_SKIP.match(c)]
    return t.split()


def english_ratio(lines):
    """줄 목록 중 영어 줄 비율(0~1). 검사 도구·테스트가 쓴다."""
    ls = [x for x in (lines or []) if (x or "").strip()]
    if not ls:
        return 0.0
    return sum(1 for x in ls if is_english(x)) / len(ls)


_JA_WRITTEN = re.compile(r"(ということ[。！!]*$|消え去|である[。]*$|における|となっております)")
_KO_POLITE = re.compile(r"(요|니다|니까|세요|죠|시죠|십시오)[.!?~…\s]*$")
_REG_POLITE = ("POLITE. The Korean uses 존댓말, so write spoken です・ます only — never casual endings. "
               "Natural spoken polite forms: 〜なんです / 〜ですよね / 〜ちゃうんです / 〜してみてください / 〜ですよ.")
_REG_CASUAL = ("CASUAL. The Korean is 반말 narration, so write friendly casual spoken Japanese: "
               "〜なんだって / 〜しちゃう / 〜んだよね / 〜ってこと / 〜してみて.")


def ja_register(lines):
    """한국어 대본 말투 → 'polite'|'casual'. 문장 끝 존댓말 줄이 3분의 1 이상이면 존댓말(관제 254, 2026-10-23 사장님 "존댓말 대본은 존댓말로")."""
    src = [(x or "").strip() for x in (lines or []) if (x or "").strip()]
    n = sum(1 for x in src if _KO_POLITE.search(x))
    return "polite" if src and n * 3 >= len(src) else "casual"


# ── 네 언어 바로 옮기기(관제 254, 2026-10-23 사장님 "일어 중국어 영어 한국어 모두 바로 이동이 되게") ──
# ★lang_of 는 손대지 않는다 — 자막 토큰·성우 차단·말속도가 그걸 써서, 한자만 있는 줄을 'zh'로 바꾸면 기존 일본어 작업이 흔들린다.
#   번역 엔진의 원문 판정은 여기 detect_lang 한 곳(가나가 있으면 일본어, 한자만 있으면 중국어).
def detect_lang(text):
    """번역 엔진용 원문 언어 'ko'|'ja'|'zh'|'en'|None."""
    t = text or ""
    if _HANGUL.search(t):
        return "ko"
    if _KANA.search(t):
        return "ja"
    if _CJK.search(t):
        return "zh"
    if len(_LATIN_WORD.findall(t)) >= 2:
        return "en"
    return None


def source_lang(lines):
    """줄 목록의 원문 언어 — 줄마다 detect_lang 을 세어 가장 많은 것. 가나가 한 줄이라도 있으면 일본어
    (일본어 대본 속 한자만 있는 짧은 줄 "絶賛発売中"이 중국어로 세어져도 흔들리지 않게)."""
    from collections import Counter
    c = Counter(x for x in (detect_lang(y) for y in (lines or [])) if x)
    if not c:
        return "ko"
    if c.get("ja"):
        return "ja"
    return c.most_common(1)[0][0]


_LANG_EN = {"ko": "Korean", "ja": "Japanese", "zh": "Chinese (Mandarin, Simplified)", "en": "English"}
_JA_POLITE = re.compile(r"(です|ます|ません|でした|ました|ください|でしょう)[よねか]?[。！!？?…\s]*$")


def register_of(lines, src):
    """원문 말투 'polite'|'casual'. 높임이 문법에 있는 한국어·일본어만 판정, 중국어·영어 원문은 'casual'(쇼츠 기본)."""
    pat = {"ko": _KO_POLITE, "ja": _JA_POLITE}.get(src)
    xs = [(x or "").strip() for x in (lines or []) if (x or "").strip()]
    if not pat or not xs:
        return "casual"
    return "polite" if sum(1 for x in xs if pat.search(x)) * 3 >= len(xs) else "casual"


_REGISTER_ANY = {
    ("ja", "polite"): "POLITE: spoken です・ます only (〜なんです / 〜ですよね / 〜ちゃうんです / 〜してみてください).",
    ("ja", "casual"): "CASUAL: friendly casual spoken Japanese (〜なんだって / 〜しちゃう / 〜んだよね / 〜じゃん / 〜してみて).",
    ("ko", "polite"): "POLITE: 자연스러운 해요체 구어(~거든요 / ~더라고요 / ~잖아요 / ~해 보세요). 합쇼체(~습니다)는 마지막 권유 정도만.",
    ("ko", "casual"): "CASUAL: 친구한테 말하듯 반말 썰체(~했거든 / ~더라 / ~잖아 / ~해 봐).",
    ("zh", "polite"): "抖音带货口播的亲切口吻(家人们 / 真的 / 你们一定要试试), 不要书面敬语.",
    ("zh", "casual"): "抖音带货口播的随意口吻(真的绝了 / 谁懂啊 / 直接 / 太香了), 不要书面语.",
    ("en", "polite"): "Warm, friendly creator voice-over (contractions OK).",
    ("en", "casual"): "Casual, punchy creator voice-over (contractions, short sentences).",
}

_STYLE_ANY = {
    "ja": ("Banned written-style: 〜ということ / 文末の〜こと / 〜である / 〜にて / 〜消え去った / 〜となっております. "
           "Link lines like a speaker (でもさ / しかも / なのに / 〜したら / 〜から / 〜し), keep sound words as Japanese ones (サッと / ポンと / パンパン / スッキリ). "
           "Never end three lines in a row the same way. About 30 characters or less per line.\n"
           "Real lines from top Japanese shopping shorts (style only, do NOT copy): 引越しの荷造りが終わって壁を見たらさ、ピン穴だらけだったの。 / はぁ？ってなったよね。 / "
           "ちょっと見てて、ぎゅっと絞ってヘラですーっ、それだけ。 / もうこれ、ポーチ界のチートアイテムじゃん。 / 最初は固く見えても時間が経つと緩んで、結局ネズミがまた入り込んできたんです。"),
    "ko": ("번역투 금지: ~하는 것이다 / ~에 있어서 / ~되어지다 / ~을 통해 / 명사 나열. 한국 쇼핑 쇼츠 내레이션처럼 말하듯 쓴다. "
           "의성어·의태어를 살린다(쓱 / 딱 / 빵빵 / 싹). 같은 끝맺음을 세 줄 연속 쓰지 않는다. 한 줄 30자 안팎."),
    "zh": ("用简体中文。这是口播不是文章: 不要书面语(之 / 其 / 乃 / 予以 / 进行… / 该产品), 不要逐字翻译, 用中国人自然的说法和语气词(啊 / 吧 / 呢 / 真的). "
           "拟声拟态词用中文自然的(唰一下 / 啪地一按 / 鼓鼓的). 不要连续三句同样的结尾. 每句20个汉字左右."),
    "en": ("Natural American TikTok/Shorts voice-over, not a translation: rephrase idioms, use contractions, short punchy lines, "
           "keep sound words natural in English (just slip it on / press once / puffs right up)."),
}

_PROMPT_ANY = """You are a native {tgt_name} short-form copywriter. Rewrite a {src_name} shopping-shorts narration as the voice-over a native {tgt_name} TikTok/Shorts creator would actually SAY out loud.
Return exactly {n} lines in the same order, one per input line, never merge/split, never empty.
Keep meaning, product name{product_hint}, numbers and calls to action. Do not add facts or phrases that are not in the line, and do not drop any. Keep numbers exactly; keep the currency as written.
Output {tgt_name} only (no {src_name}, no notes, no quotes, no romanization).

- This is speech, not writing. Do NOT translate word by word: say the same thing the way a native speaker naturally would.
- Register (decided from the original script, follow it on EVERY line): {register}
- {style}

Input lines (JSON array):
{lines}
"""


def _is_lang(text, lang):
    """출력 줄이 그 언어로 쓰였나 — 번역 결과 검사 한 곳."""
    t = text or ""
    if lang == "ko":
        return bool(_HANGUL.search(t)) and not _KANA.search(t)
    if lang == "ja":   # 가나가 있어야 일본어 — 한자만이면 중국어를 그대로 돌려준 것일 수 있다
        return bool(_KANA.search(t)) and not _HANGUL.search(t)
    if lang == "zh":
        return bool(_CJK.search(t)) and not _KANA.search(t) and not _HANGUL.search(t)
    if lang == "en":
        return bool(_LATIN.search(t)) and not (_HANGUL.search(t) or _KANA.search(t) or _CJK.search(t))
    return False


_FIDELITY_SCHEMA = {
    "type": "object",
    "properties": {"bad": {"type": "array", "items": {"type": "object", "properties": {
        "i": {"type": "integer"}, "problem": {"type": "string"}, "fix": {"type": "string"}},
        "required": ["i", "problem", "fix"]}}},
    "required": ["bad"],
}

_FIDELITY_PROMPT = """You are checking a {src_name} → {tgt_name} shopping-shorts voice-over adaptation, line by line.
Natural rewording, sound words, slang and tone changes are GOOD and must NOT be flagged.
Flag a line ONLY if its meaning changed: a fact, object, action, number, product feature or claim was added, dropped or became different
(e.g. "footprints on the clothes" became "dirty footprints"; "it handles everything" became a new claim).
Also flag mistranslated product or object words (e.g. "air foam iron" became "air portrait iron").
For each flagged line give: i (0-based index), problem (short, in Korean), fix (the corrected {tgt_name} line, same natural spoken style{register}).
The fix must carry exactly the original's meaning: do NOT add hype, exclamations or claims that are not in the original.
Return {{"bad": []}} when every line keeps the meaning.

Pairs (JSON, [index, original, adaptation]):
{pairs}
"""


def fidelity_fix(src, out, lang, src_lang, *, call, rounds=2):
    """옮긴 줄마다 원문과 뜻이 같은지 한 번 더 본다(관제 254 — 실측 12방향 중 3줄이 뜻이 바뀌었다:
    「一切直接搞定」 덧붙임 · 「汚れた足跡」 · 「確認してみて」). 뜻이 바뀐 줄만 고친 줄로 바꾼다 — 판단 주인 = 여기 한 곳.
    검사 호출이 실패하면 번역은 그대로 쓰되 경고를 남긴다(번역 자체를 막지 않는다). → (out, 고친 기록 목록)"""
    import json
    import logging
    out, fixed = list(out), []
    idx = list(range(len(src)))           # 1회차 = 전 줄, 2회차 = 1회차에서 고친 줄만(고친 줄이 새로 뜻을 덧붙이는 일 — 실측 「简直绝了」)
    for _round in range(max(1, rounds)):
        got_fixed = _fidelity_once([src[i] for i in idx], [out[i] for i in idx], lang, src_lang, call)
        if got_fixed is None:
            break
        for f in got_fixed:
            i = idx[f["i"]]
            fixed.append({**f, "i": i, "round": _round + 1})
            out[i] = f["after"]
        idx = sorted({idx[f["i"]] for f in got_fixed})
        if not idx:
            break
    return out, fixed


def _fidelity_once(src, out, lang, src_lang, call):
    """fidelity_fix 한 회차 — 고칠 줄 목록 [{i, before, after, problem}] (i 는 이 회차 목록 기준). 호출 실패면 None."""
    import json
    import logging
    try:
        reg = _REGISTER_ANY.get((lang, register_of(src, src_lang)), "")
        got = call(_FIDELITY_PROMPT.format(src_name=_LANG_EN.get(src_lang, "source"), tgt_name=_LANG_EN[lang],
                                           register=(", " + reg) if reg else "",
                                           pairs=json.dumps([[i, a, b] for i, (a, b) in enumerate(zip(src, out))],
                                                            ensure_ascii=False)),
                   _FIDELITY_SCHEMA) or {}
    except Exception as e:      # noqa: BLE001 — 검사 실패는 경보만, 번역 결과는 살린다
        logging.getLogger(__name__).warning("번역 뜻 검사 실패(번역은 그대로): %s", e)
        return None
    fixed, seen = [], set()
    for b in got.get("bad") or []:
        try:
            i, fx = int(b.get("i")), str(b.get("fix") or "").strip()
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(out) and i not in seen and fx and _is_lang(fx, lang) and fx != out[i]:
            seen.add(i)
            fixed.append({"i": i, "before": out[i], "after": fx, "problem": str(b.get("problem") or "")})
    return fixed


def translate(lines, lang, product="", *, source=None, call=None, tries=2, check_meaning=True):
    """문장 목록 → 같은 길이의 lang('ko'|'ja'|'zh'|'en') 문장 목록. source(원문 언어)는 안 주면 source_lang 으로 판정.
    한국어→영어·일본어는 종전 지시문 그대로(회귀 금지), 그 밖의 조합은 _PROMPT_ANY(그 나라 크리에이터 말투)로 바로 옮긴다.

    call: 테스트가 갈아끼우는 (prompt, schema) -> dict. 기본은 script_generate._call_json(키풀·Vertex 깔때기).
    check_meaning: 옮긴 뒤 fidelity_fix 로 뜻이 바뀐 줄만 고친다(관제 254). 호출이 한 번 더 든다.
    실패(빈 응답·줄 수 불일치·한글 잔존·일본어 아닌 줄)는 ValueError — 호출부가 그대로 화면에 띄운다.
    """
    import json
    if lang not in _LANG_EN:
        raise ValueError("지원하지 않는 언어예요: %r" % (lang,))
    src = [(x or "").strip() for x in (lines or [])]
    if not src or any(not x for x in src):
        raise ValueError("번역할 문장이 비어 있어요 — 대본을 먼저 확정해 주세요")
    # 이미 그 언어면 두 번 번역하지 않는다. 영어는 종전 판정(is_english: 한글 0·라틴 있음)을 그대로 둔다(회귀 금지).
    src_lang = source or source_lang(src)
    legacy = src_lang == "ko" and lang in ("en", "ja")
    if legacy:
        already = is_english if lang == "en" else (lambda x: lang_of(x) == "ja")
        if all(already(x) for x in src):
            return list(src)
    elif src_lang == lang:
        return list(src)
    call = call or (lambda p, s: script_generate._call_json(p, s))
    hint = f" ('{product}')" if (product or "").strip() else ""
    if legacy:
        tmpl = _PROMPT if lang == "en" else _PROMPT_JA
        reg = _REG_POLITE if ja_register(src) == "polite" else _REG_CASUAL
        prompt = tmpl.format(n=len(src), product_hint=hint, register=reg,
                             lines=json.dumps(src, ensure_ascii=False))
    else:
        prompt = _PROMPT_ANY.format(tgt_name=_LANG_EN[lang], src_name=_LANG_EN.get(src_lang, "source"), n=len(src),
                                    product_hint=hint, register=_REGISTER_ANY[(lang, register_of(src, src_lang))],
                                    style=_STYLE_ANY[lang], lines=json.dumps(src, ensure_ascii=False))
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
        bad = ([i for i, x in enumerate(out) if _HANGUL.search(x)] if legacy
               else [i for i, x in enumerate(out) if not _is_lang(x, lang)])
        if bad:
            last = f"{len(bad)}줄에 한글이 남았어요" if legacy else f"{len(bad)}줄이 {LANG_LABEL[lang]}가 아니에요"
            continue
        if lang == "ja":
            not_ja = [i for i, x in enumerate(out) if not _JA_CHARS.search(x)]
            if not_ja:
                last = f"{len(not_ja)}줄이 일본어가 아니에요"
                continue
        if lang == "ja" and _ < max(1, tries) - 1 and any(_JA_WRITTEN.search(x) for x in out):
            # 글말 끝맺음(〜ということ·消え去る·である)이 섞이면 한 번 더 받는다 — 일본인 쇼핑 쇼츠 9편 73줄 실측 0건(관제 254).
            # 마지막 시도면 그대로 쓴다(번역 실패로 막지 않는다)
            last = "글말 끝맺음"
            continue
        if check_meaning:
            out, _fixed = fidelity_fix(src, out, lang, src_lang, call=call)
        return out
    raise ValueError(LANG_LABEL[lang] + " 변환에 실패했어요 — " + (last or "AI 응답이 비었어요") + ". 잠시 후 다시 눌러 주세요")


def to_english(lines, product="", *, call=None, tries=2):
    """한국어 문장 목록 → 같은 길이의 영어 문장 목록(= translate(lines, 'en')). 서명·동작은 종전 그대로."""
    return translate(lines, "en", product, call=call, tries=tries)


def job_lang(job):
    """이 작업의 대본 언어('ja'|'zh'|'en'|'ko') — 판단은 여기 한 곳. edit_plan.lang이 있으면 그것, 없으면 확정 대본(given_script)의
    줄들의 lang_of 를 세어 'ja' 또는 'en' 이 80% 이상이면 그 언어(2단계에서 외국어모드로 확정한 작업은 given_script가 그 언어)."""
    plan = (job or {}).get("edit_plan") or {}
    if isinstance(plan, dict) and plan.get("lang") in ("en", "ja", "ko", "zh"):
        return plan["lang"]
    lines = [x.strip() for x in str((job or {}).get("given_script") or "").splitlines() if x.strip()]
    if not lines:
        return "ko"
    # 일본어 대본엔 한자만 있는 줄(「絶賛発売中」)이 섞일 수 있다 — 가나 줄이 하나라도 있으면 ja·zh 를 합쳐 일본어로 센다.
    # 한자만 있는 줄(lang_of 가 표지 없으면 ja 로 보는 줄)은 여기선 가나가 없으면 한자 줄로 센다 → 가나 줄이 없는 대본 = 중국어
    langs = [("zh" if (lg == "ja" and not _KANA.search(x)) else lg) for lg, x in ((lang_of(x), x) for x in lines)]
    if "ja" in langs:
        langs = ["ja" if x == "zh" else x for x in langs]
    for lang in ("ja", "zh", "en"):
        if sum(1 for x in langs if x == lang) / len(lines) >= 0.8:
            return lang
    return "ko"
