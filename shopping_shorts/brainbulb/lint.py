# -*- coding: utf-8 -*-
"""대본 린터 — 규칙표 하나에서 **프롬프트 지시문**과 **판정**을 둘 다 뽑는다.

왜 한 표인가: 숏템메이커에서 헌장은 CTA를 쓰라 하고 게이트는 벌줬다("시켜놓고 벌주기", 2026-08-22).
규칙이 두 곳에 있으면 반드시 어긋난다. 여기서는 규칙의 지시문과 검사가 같은 객체다.

규칙 원천: 볼케이노 서버 반려 원문 13개 + 경고 4개 (channel/volcano/뇌전구_역분석_8편_2026-09-12.md §4, 전편 §2)
판정은 데이터를 고치지 않는다 — 반려(reject)/경고(warn)와 사유만 낸다.
"""
import re
from dataclasses import dataclass, field

from . import spec, layout

REJECT, WARN = "reject", "warn"


@dataclass
class Issue:
    rule: str
    level: str
    where: str
    found: str
    why: str


@dataclass
class Rule:
    id: str
    level: str
    prompt: str                 # LLM에게 주는 지시문 (한 줄)
    check: object               # fn(script, ctx) -> [Issue]
    needs_layout: bool = False


_FORMAL = re.compile(r"(습니다|습니까|십시오)[.!?]?$")
_FORMAL_HARD = re.compile(r"(습니까|십시오)[.!?]?$")
_CLOSED = re.compile(r"(다|임|음|됨|요|야|네|지|까|냐|죠)[.!?]?$")
_TITLE_PUNCT = re.compile(r'[",?!.…:;]')
_ABSTRACT_TAIL = ("이유", "사연", "진실", "비밀", "정체", "이야기", "상황", "사실", "근황", "결말")


def _groups(s):
    return s.get("groups") or []


def r_title_punct(s, ctx):
    out = []
    for k in ("h1", "h2"):
        v = (s.get("title") or {}).get(k, "") or ""
        if _TITLE_PUNCT.search(v):
            out.append(Issue("title_punct", REJECT, f"title.{k}", v, "제목에는 구두점을 쓰지 않습니다"))
    return out


def r_comma(s, ctx):
    return [Issue("comma", REJECT, f"groups[{i}]", g["text"], "이 채널 자막에 쓰지 않는 부호입니다 [',']")
            for i, g in enumerate(_groups(s)) if "," in g.get("text", "")]


def r_enum(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        if g.get("color") not in spec.COLORS:
            out.append(Issue("enum", REJECT, f"groups[{i}].color", str(g.get("color")), f"색은 {'/'.join(spec.COLORS)} 중 하나"))
        if g.get("role") not in spec.ROLES:
            out.append(Issue("enum", REJECT, f"groups[{i}].role", str(g.get("role")), f"역할은 {'/'.join(spec.ROLES)} 중 하나"))
        has_img = isinstance(g.get("img"), int)
        meme = g.get("meme")
        if not has_img and not meme:
            out.append(Issue("enum", REJECT, f"groups[{i}]", g.get("text", ""), "컷마다 img(슬롯 번호) 또는 meme(감정)이 있어야 합니다"))
        if meme and meme not in spec.EMOTIONS:
            out.append(Issue("enum", REJECT, f"groups[{i}].meme", str(meme), f"밈 감정은 다음 문자열 그대로: {' · '.join(spec.EMOTIONS)}"))
    return out


def r_nonwhite_run(s, ctx):
    out, run = [], 0
    for i, g in enumerate(_groups(s)):
        run = run + 1 if g.get("color") != "WHITE" else 0
        if run == 3:
            out.append(Issue("nonwhite_run", REJECT, f"groups[{i - 2}..{i}]", g.get("text", ""),
                             "강조색을 이만큼 연달아 쓰지 않습니다 — 사이에 WHITE를 두세요"))
    return out


def r_formal(s, ctx):
    gs = _groups(s)
    out = [Issue("formal", REJECT, f"groups[{i}]", g["text"], "격식체 의문·청유는 이 채널이 쓰지 않습니다")
           for i, g in enumerate(gs) if _FORMAL_HARD.search(g.get("text", "").strip())]
    n = sum(1 for g in gs if _FORMAL.search(g.get("text", "").strip()))
    if gs and n * 2 > len(gs):
        out.append(Issue("formal", REJECT, "groups", f"{n}/{len(gs)}", "격식 종결(-습니다)이 너무 많습니다 — 이 채널은 거의 쓰지 않습니다(반말체: ~였다/~임/~됨)"))
    return out


def r_h2_abstract(s, ctx):
    h2 = ((s.get("title") or {}).get("h2") or "").strip()
    if any(h2.endswith(w) for w in _ABSTRACT_TAIL):
        return [Issue("h2_abstract", REJECT, "title.h2", h2, "h2는 이유·사연 같은 추상명사로 끝내지 않습니다 — 숫자·구체어로")]
    return []


def r_card(s, ctx):
    card = ((s.get("title") or {}).get("card") or "").strip()
    if not card:
        return [Issue("card", REJECT, "title.card", "", "오프닝 카드 문장이 없습니다")]
    if len(re.findall(r"[.!?]", card.rstrip(".!?"))) > 0:
        return [Issue("card", REJECT, "title.card", card, "카드는 읽어주는 한 문장입니다 — 낱말로 끊거나 두 문장을 쓰지 않습니다")]
    return []


def r_words(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        for ln in g.get("lines") or [g.get("text", "")]:
            if len(ln.split()) > spec.POLICY_MAX_WORDS_PER_LINE:
                out.append(Issue("words", REJECT, f"groups[{i}]", ln, "한 줄에 어절이 너무 많습니다"))
    return out


def r_layout(s, ctx):
    """배치 실패 = 두 줄로도 화면에 안 들어감 (서버: '줄나눔은 서버가 하므로 글자를 줄이거나 두 카드로 쪼개라')"""
    return [Issue("layout", REJECT, f["where"], f["found"], "한 줄이 너무 깁니다 — 글자를 줄이거나 두 카드로 쪼개세요")
            for f in (ctx.get("layout_fails") or [])]


def r_punch(s, ctx):
    n = sum(1 for g in _groups(s) if g.get("role") == "PUNCH")
    if n != 1:
        return [Issue("punch", REJECT, "groups", str(n), "PUNCH는 영상당 정확히 1컷(마지막 컷)입니다")]
    return []


def r_first_open(s, ctx):
    gs = _groups(s)
    if gs and _CLOSED.search(gs[0].get("text", "").strip()):
        return [Issue("first_open", WARN, "groups[0]", gs[0]["text"], "첫 장면에서 문장을 끝내면 다음으로 끌고 가는 힘이 약합니다")]
    return []


def r_last_closed(s, ctx):
    gs = _groups(s)
    if not gs:
        return []
    g = gs[-1]
    out = []
    if not _CLOSED.search(g.get("text", "").strip()):
        out.append(Issue("last_closed", WARN, f"groups[{len(gs) - 1}]", g["text"], "마지막 문장이 끝나지 않았습니다. 닫아 주세요"))
    if g.get("color") == "WHITE" or g.get("role") != "PUNCH":
        out.append(Issue("last_punch", WARN, f"groups[{len(gs) - 1}]", g["text"], "마지막 컷은 WHITE로 닫지 않습니다 — RED PUNCH 단정문이 이 채널 결입니다"))
    return out


def r_line1_end(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        ls = g.get("lines") or []
        if len(ls) > 1 and _CLOSED.search(ls[0].strip()) and ls[0].strip()[-1] in ".!?다":
            out.append(Issue("line1_end", WARN, f"groups[{i}].lines[0]", ls[0], "윗줄에서 문장이 끝났습니다. 아랫줄로 넘기는 쪽이 이 채널 결입니다"))
    return out


def r_meme_ratio(s, ctx):
    gs = _groups(s)
    if not gs:
        return []
    n = sum(1 for g in gs if g.get("meme"))
    r = n / len(gs)
    if r < 0.10 or r > 0.25:
        return [Issue("meme_ratio", WARN, "groups", f"{n}/{len(gs)}", "밈은 전체의 14~18%가 이 채널 관행입니다")]
    return []


def r_copy(s, ctx):
    src = (ctx.get("source_text") or "").replace(" ", "")
    if not src:
        return []
    out = []
    for i, g in enumerate(_groups(s)):
        t = g.get("text", "").replace(" ", "")
        if len(t) >= spec.POLICY_COPY_MIN_CHARS and t in src:
            out.append(Issue("copy", REJECT, f"groups[{i}]", g["text"], "원문 문장을 줄인 것이지 다시 쓴 것이 아닙니다 — 다시 쓰세요"))
    return out


RULES = [
    Rule("title_punct", REJECT, "제목(h1·h2)에는 구두점을 쓰지 마라 (따옴표·물음표·마침표 포함).", r_title_punct),
    Rule("comma", REJECT, "자막 본문에 쉼표(,)를 쓰지 마라.", r_comma),
    Rule("enum", REJECT, f"색은 {'/'.join(spec.COLORS)}, 역할은 {'/'.join(spec.ROLES)}만. 컷마다 img(슬롯 번호) 또는 meme(감정) 중 하나. 밈 감정은 다음 문자열 그대로: {' · '.join(spec.EMOTIONS)}.", r_enum),
    Rule("nonwhite_run", REJECT, "흰색이 아닌 강조색을 3컷 연달아 쓰지 마라. 사이에 WHITE를 둬라.", r_nonwhite_run),
    Rule("formal", REJECT, "나레는 반말체(~였다/~했다 또는 ~임/~됨). '-습니다'가 과반이면 안 되고 '-습니까/-십시오'는 쓰지 마라.", r_formal),
    Rule("h2_abstract", REJECT, "h2(노란 아랫줄)에는 숫자를 넣고, 이유·사연 같은 추상명사로 끝내지 마라.", r_h2_abstract),
    Rule("card", REJECT, "카드는 오프닝에서 읽어주는 한 문장. 낱말로 끊지 마라.", r_card),
    Rule("words", REJECT, f"한 줄은 {spec.POLICY_MAX_WORDS_PER_LINE}어절 이하. 한 컷은 짧게(12~14자 한 줄 또는 두 줄).", r_words, needs_layout=True),
    Rule("layout", REJECT, "줄나눔은 우리가 한다 — lines를 쓰지 마라. 컷이 두 줄로도 안 들어가면 반려되니 글자를 줄이거나 두 컷으로 쪼개라.", r_layout, needs_layout=True),
    Rule("punch", REJECT, "PUNCH는 마지막 컷 하나뿐. RED 색으로 짧은 단정문.", r_punch),
    Rule("copy", REJECT, "원문을 요약하지 말고 다시 써라. 원문 문장을 그대로 줄여 쓰지 마라.", r_copy),
    Rule("first_open", WARN, "첫 컷에서 문장을 끝내지 마라 — 다음 컷으로 끌고 가라.", r_first_open),
    Rule("last_closed", WARN, "마지막 컷은 문장을 닫아라. WHITE가 아니라 RED PUNCH로.", r_last_closed),
    Rule("line1_end", WARN, "(줄나눔 참고) 두 줄 컷의 윗줄에서 문장이 끝나지 않게 컷을 짜라.", r_line1_end, needs_layout=True),
    Rule("meme_ratio", WARN, "밈 컷은 전체의 14~18% (4~5컷). 첫 밈은 6~8번째 컷, 마지막 컷은 밈.", r_meme_ratio),
]


def prompt_block():
    """규칙표 → 프롬프트 지시문. 판정과 같은 객체에서 나오므로 어긋날 수 없다."""
    return "\n".join(f"- {r.prompt}" for r in RULES)


def lint(script, *, source_text="", do_layout=True, fonts_dir=None):
    """→ (issues, script_with_lines). 원본 script는 손대지 않는다."""
    ctx = {"source_text": source_text}
    s = dict(script)
    if do_layout:
        gl, fails = layout.layout_groups(_groups(script), fonts_dir)
        s["groups"] = gl
        ctx["layout_fails"] = fails
    issues = []
    for r in RULES:
        if r.needs_layout and not do_layout:
            continue
        issues += r.check(s, ctx)
    return issues, s


def rejects(issues):
    return [i for i in issues if i.level == REJECT]


def feedback(issues):
    """실패 항목을 재작성 지시로. 규칙의 사유만 나열한다 — script_gate.gate_feedback의 '분량 처방' 자동 첨부 없음(아스트라 지적)."""
    bad = rejects(issues)
    if not bad:
        return ""
    return ("\n\n[재작성 지시 — 방금 쓴 것이 아래를 어겼다. 해당 부분만 그대로 고쳐라. 칸 개수·순서는 유지]\n"
            + "\n".join(f"- {i.where} «{i.found}»: {i.why}" for i in bad))
