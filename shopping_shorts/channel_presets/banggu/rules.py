# -*- coding: utf-8 -*-
"""방구석 대본 규칙 — 판정과 지시문이 같은 표에서 나온다(뜨거운사람들 rules.py 와 같은 생각).

대본 모양(script):
  {"kind": "hidden|mechanism|substitute", "title": "낭독 제목",
   "lines": [{"role": "소개", "text": "..."}, ...],      ← 신호어가 붙은 최종 문장(script.to_lines 가 만든다)
   "comment": "마지막 혼잣말 한 줄 또는 빈칸"}
ctx: {"source_text": 원본 영상들의 말 전부, "material": material.extract 결과, "product": 제품명}
근거 수치: spec.py
"""
import re
from collections import namedtuple

from . import spec

REJECT, WARN = "reject", "warn"
Issue = namedtuple("Issue", "rule level where found why")
Rule = namedtuple("Rule", "id level prompt check")

_FLAT = re.compile(spec.FLAT_END)
_CLOSE = re.compile(spec.CLOSE_END)
_YOU = re.compile(spec.YOU_WORDS)
_CTA = re.compile(spec.CTA_WORDS)
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def body(s):
    return [(L.get("role") or "", (L.get("text") or "").strip()) for L in (s.get("lines") or []) if (L.get("text") or "").strip()]


def chars(t):
    return len(re.sub(r"\s", "", t or ""))


def _strip_tail(t):
    return re.sub(r"\s*(ㅋㅋ+|ㄷㄷ+|\.\.\?|[.?!…])+\s*$", "", t.strip())


def r_flat(s, ctx):
    bad = [t for _, t in body(s) if _FLAT.search(_strip_tail(t))]
    return [Issue("bg_flat", REJECT, "lines", t[-14:], "평서 종결(~다/~요/~습니다)은 0 — 12편 81문장에 한 번도 없다") for t in bad]


def r_close(s, ctx):
    b = body(s)
    if not b or _CLOSE.search(b[-1][1].strip()):
        return []
    return [Issue("bg_close", REJECT, "lines[-1]", b[-1][1][-14:], "본문 마지막 줄은 '~다고/~라고(ㅋㅋ·ㄷㄷ)'로 닫는다(12/12편)")]


def r_you(s, ctx):
    return [Issue("bg_you", REJECT, "lines", t[:20], "보는 사람에게 말 걸지 않는다(12편 0)") for _, t in body(s) if _YOU.search(t)]


def r_cta(s, ctx):
    txt = [t for _, t in body(s)] + [s.get("comment") or ""]
    return [Issue("bg_cta", REJECT, "lines", t[:20], "권하는 말·구매 유도 0") for t in txt if _CTA.search(t)]


def r_length(s, ctx):
    n = sum(chars(t) for _, t in body(s))
    if spec.BODY_CHARS_MIN <= n <= spec.BODY_CHARS_MAX:
        return []
    return [Issue("bg_length", REJECT, "lines", str(n), f"본문은 공백 빼고 {spec.BODY_CHARS_MIN}~{spec.BODY_CHARS_MAX}자(원본 155~226)")]


def r_lines(s, ctx):
    n = len(body(s))
    out = []
    if not spec.BODY_LINES_MIN <= n <= spec.BODY_LINES_MAX:
        out.append(Issue("bg_lines", REJECT, "lines", str(n), f"본문 문장은 {spec.BODY_LINES_MIN}~{spec.BODY_LINES_MAX}개"))
    out += [Issue("bg_line_long", REJECT, "lines", t[:16], f"한 문장은 {spec.LINE_CHARS_MAX}자 이하") for _, t in body(s) if chars(t) > spec.LINE_CHARS_MAX]
    return out


def r_title(s, ctx):
    t = (s.get("title") or "").strip()
    out = []
    if not spec.TITLE_MIN <= len(t) <= spec.TITLE_MAX:
        out.append(Issue("bg_title_len", REJECT, "title", str(len(t)), f"제목은 {spec.TITLE_MIN}~{spec.TITLE_MAX}자"))
    if re.search(r'[",?!.…:;]', t) or re.search(r"(는데|다고|니다|어요|아요)$", t):
        out.append(Issue("bg_title_form", REJECT, "title", t[-8:], "제목은 문장부호 없이 명사로 끝낸다"))
    return out


def r_numbers(s, ctx):
    src = set(_NUM.findall(ctx.get("source_text") or ""))
    txt = " ".join([s.get("title") or ""] + [t for _, t in body(s)])
    bad = [n for n in _NUM.findall(txt) if n not in src]
    return [Issue("bg_number", REJECT, "lines", n, "숫자는 원본 영상의 말에 나온 것만") for n in bad]


def r_sourced_words(s, ctx):
    """재료에 없는 꾸밈말·나라 — 버텍스 시험에서 실제로 지어낸 낱말 목록(spec.HYPE_WORDS)."""
    src = ctx.get("source_text") or ""
    txt = " ".join([s.get("title") or ""] + [t for _, t in body(s)])
    bad = [w for w in spec.HYPE_WORDS + spec.COUNTRIES if w in txt and w not in src]
    return [Issue("bg_unsourced", REJECT, "lines", w, "이 말은 원본 영상에 없다 — 빼라") for w in bad]


def r_comment(s, ctx):
    c = (s.get("comment") or "").strip()
    if not c:
        return []
    out = []
    if "ㅋㅋ" not in c:
        out.append(Issue("bg_comment_kk", REJECT, "comment", c[-8:], "혼잣말 한 줄은 ㅋㅋ로 끝난다(6/6편)"))
    if len(c) > spec.COMMENT_MAX:
        out.append(Issue("bg_comment_len", REJECT, "comment", str(len(c)), f"혼잣말은 {spec.COMMENT_MAX}자 이하"))
    if re.search(r"(다고|라고)\s*ㅋㅋ", c) and not re.search(r"냐고\s*ㅋㅋ", c):
        out.append(Issue("bg_comment_voice", REJECT, "comment", c[-10:], "혼잣말은 전해 듣는 말끝(~다고)이 아니라 내 감상이다 — '~네 ㅋㅋ'·'~는데 ㅋㅋ'·'~겠네 ㅋㅋ'"))
    return out


def r_intro_noun(s, ctx):
    b = [t for r, t in body(s) if r in ("소개", "원조")]
    if not b or not re.search(r"(는데|다고|음|됨|는 거|고|서|면)$", _strip_tail(b[0])):
        return []
    return [Issue("bg_intro_noun", WARN, "소개", b[0][-10:], "소개 줄은 제품(원조) 이름으로 끝나는 명사구(9/12편)")]


def r_copy_seed(s, ctx):
    """씨앗 문장을 옮겨 적으면 같은 영상이 된다 — 한 줄의 6글자 조각 절반 이상이 씨앗에 있으면 반려."""
    seed = re.sub(r"[^가-힣A-Za-z0-9]", "", ctx.get("seed_text") or "")
    out = []
    for _, t in body(s):
        q = re.sub(r"[^가-힣A-Za-z0-9]", "", t)
        g = [q[i:i + 6] for i in range(max(0, len(q) - 5))]
        if len(g) >= 6 and seed and sum(1 for x in g if x in seed) / len(g) > 0.5:
            out.append(Issue("bg_copy", REJECT, "lines", t[:16], "씨앗 영상의 문장을 옮겼다 — 내용만 가져와 새로 써라"))
    return out


def _g3(t):
    q = re.sub(r"[^가-힣A-Za-z0-9]", "", t or "")
    return {q[i:i + 3] for i in range(max(0, len(q) - 2))}


def r_repeat(s, ctx):
    """제목↔첫 줄, 이웃한 두 줄이 같은 말을 되풀이하면 반려 — 원본은 제목이 던지고 소개가 다른 말로 받는다."""
    seq = [("title", s.get("title") or "")] + [(r, t) for r, t in body(s)]
    out = []
    for (ra, a), (rb, b) in zip(seq, seq[1:]):
        ga, gb = _g3(a), _g3(b)
        small = min(len(ga), len(gb))
        if small >= 8 and len(ga & gb) / small > spec.REPEAT_SHARE:
            out.append(Issue("bg_repeat", REJECT, rb, b[:16], "앞 줄(%s)과 같은 말을 되풀이했다 — 다른 내용으로" % ra))
    return out


RULES = [
    Rule("bg_flat", REJECT, "문장 끝에 '~다.'·'~요.'·'~습니다'를 쓰지 않는다. 끝은 ~는데 / ~다고 / ~다고 함 / ~는 거 / ~음·~됨 / 명사.", r_flat),
    Rule("bg_close", REJECT, "본문 마지막 줄은 '~다고' 또는 '~라고'로 닫는다(전해 듣는 말).", r_close),
    Rule("bg_you", REJECT, "보는 사람에게 말 걸지 않는다(여러분·~보세요·~있지? 금지). 주체는 '사람들이'나 별명 붙은 무리.", r_you),
    Rule("bg_cta", REJECT, "사라·추천·구독·댓글·링크 같은 권하는 말을 쓰지 않는다.", r_cta),
    Rule("bg_length", REJECT, f"본문은 공백 빼고 {spec.BODY_CHARS_MIN}~{spec.BODY_CHARS_MAX}자.", r_length),
    Rule("bg_lines", REJECT, f"본문 문장 {spec.BODY_LINES_MIN}~{spec.BODY_LINES_MAX}개, 한 문장 {spec.LINE_CHARS_MAX}자 이하.", r_lines),
    Rule("bg_title", REJECT, f"제목은 {spec.TITLE_MIN}~{spec.TITLE_MAX}자, 문장부호 없이 명사로 끝낸다.", r_title),
    Rule("bg_number", REJECT, "숫자·가격은 [재료]에 나온 것만 그대로 쓴다.", r_numbers),
    Rule("bg_unsourced", REJECT, "품절·난리·1위·직구·쟁여·완벽·나라 이름은 [재료]에 그 말이 있을 때만 쓴다.", r_sourced_words),
    Rule("bg_comment", REJECT, f"comment(혼잣말 한 줄)는 {spec.COMMENT_MAX}자 이하, ㅋㅋ로 끝나는 내 감상('아니 ~네 ㅋㅋ'). '~다고 ㅋㅋ'는 안 된다.", r_comment),
    Rule("bg_repeat", REJECT, "제목과 소개, 이웃한 두 줄이 같은 말을 되풀이하지 않는다(제목이 던진 것을 소개가 다른 말로 받는다).", r_repeat),
    Rule("bg_intro_noun", WARN, "소개 줄은 제품 이름으로 끝나는 명사구로.", r_intro_noun),
    Rule("bg_copy", REJECT, "씨앗 영상의 문장을 그대로 옮기지 않는다 — 내용만 가져와 이 말투로 새로 쓴다.", r_copy_seed),
]


def prompt_block():
    return "\n".join("- " + r.prompt for r in RULES)


def lint(script, ctx):
    out = []
    for r in RULES:
        out += r.check(script, ctx or {})
    return out


def rejects(issues):
    return [i for i in issues if i.level == REJECT]


def feedback(issues):
    bad = rejects(issues)
    if not bad:
        return ""
    return "\n\n[재작성 지시 — 아래를 고쳐 JSON 전체를 다시 내라]\n" + "\n".join(
        "- (%s) «%s» : %s" % (i.where, i.found, i.why) for i in bad)
