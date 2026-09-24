# -*- coding: utf-8 -*-
"""뜨거운사람들 대본 규칙 — 판정과 지시문이 같은 객체(channelkit.lint.Rule). import 하면 창고에 등록된다.

대본 모양(script):
  {"person": "방시혁",
   "title": {"h1": "전 세계를 한국어로", "h2": "떼창하게 만든 남자", "emph": 2, "emph_color": "red"|"yellow"},
   "groups": [{"lines": ["하이브 창업주", "그의 이름 \\"방시혁\\""], "text": "…", "mark": false, "red": ["단어"],
               "scene": "english visual description", "query": "youtube search words"}],
   "queries": ["검색어", …]}
근거 수치: channel/hotpeople/역분석_2026-09-25.md
"""
import re
from functools import lru_cache

from PIL import ImageFont

from shopping_shorts.channelkit import lint
from shopping_shorts.channelkit.lint import Issue, Rule, REJECT, WARN
from . import spec


def _groups(s):
    return s.get("groups") or []


@lru_cache(maxsize=8)
def _font(path, px):
    return ImageFont.truetype(path, px)


def ink_width(text, path=None, px=None, bolden=None):
    """PIL 잉크 폭(px). 굵게 처리(외곽선)만큼 양쪽에 더한다."""
    f = _font(path or spec.SUB_FONT, px or spec.SUB_FONT_PX)
    b = spec.SUB_BOLDEN_PX if bolden is None else bolden
    l, t, r, btm = f.getbbox(text, stroke_width=b)
    return r - l


def sub_seconds(text):
    """자막 노출시간 — 원본 48자막 회귀(1.69+0.037×글자수), 1.3~3.1초로 자름."""
    n = len(re.sub(r"\s", "", text))
    return round(min(spec.SUB_SEC_MAX, max(spec.SUB_SEC_MIN, spec.SUB_SEC_BASE + spec.SUB_SEC_PER_CHAR * n)), 2)


def r_count(s, ctx):
    n = len(_groups(s))
    if spec.SUB_COUNT_MIN <= n <= spec.SUB_COUNT_MAX:
        return []
    return [Issue("hp_count", REJECT, "groups", str(n), f"자막은 {spec.SUB_COUNT_MIN}~{spec.SUB_COUNT_MAX}개(원본 24~28)")]


def r_lines(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        lines = g.get("lines") or []
        if not 1 <= len(lines) <= 2:
            out.append(Issue("hp_lines", REJECT, f"groups[{i}]", str(lines), "자막 한 개는 1~2줄(원본 232개 중 231개)"))
            continue
        for ln in lines:
            w = ink_width(ln)
            if w > spec.SUB_MAX_INK_W:
                out.append(Issue("hp_lines", REJECT, f"groups[{i}]", ln,
                                 f"줄이 너무 길다 {w}px > {spec.SUB_MAX_INK_W}px — 줄을 나누거나 줄여라(대략 14자 안쪽)"))
        if " ".join(lines).replace(" ", "") != (g.get("text") or " ".join(lines)).replace(" ", ""):
            out.append(Issue("hp_lines", REJECT, f"groups[{i}]", g.get("text", ""), "text와 lines 글자가 다르다"))
    return out


def r_first_mark(s, ctx):
    gs = _groups(s)
    if gs and gs[0].get("mark"):
        return []
    return [Issue("hp_first_mark", REJECT, "groups[0]", "", "첫 자막은 형광펜(mark:true) — 원본 9/9편")]


def r_mark_max(s, ctx):
    n = sum(1 for g in _groups(s) if g.get("mark"))
    return [] if n <= spec.MARK_MAX else [Issue("hp_mark_max", REJECT, "groups", str(n), f"형광펜은 편당 {spec.MARK_MAX}개 이하(원본 232개 중 15개)")]


def r_red(s, ctx):
    out = []
    for i, g in enumerate(_groups(s)):
        lines = g.get("lines") or []
        for w in g.get("red") or []:
            if not w or not any(w in ln for ln in lines):     # 줄을 넘어가는 빨강은 그릴 수 없다
                out.append(Issue("hp_red", REJECT, f"groups[{i}]", w, "빨강 단어는 한 줄 안에 그대로 있어야 한다"))
    return out


def r_name_early(s, ctx):
    name = (s.get("person") or "").strip()
    if not name:
        return [Issue("hp_name", REJECT, "person", "", "주인공 이름(person)을 적어라")]
    early = " ".join(g.get("text") or " ".join(g.get("lines") or []) for g in _groups(s)[:spec.NAME_REVEAL_BY])
    last = name.split()[-1]
    if name in early or last in early:
        return []
    return [Issue("hp_name", REJECT, "groups", name, f"이름 공개는 {spec.NAME_REVEAL_BY}번째 자막 안에(원본 2~3번째: 그의 이름 \"○○○\")")]


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _norm_nums(text):
    return {n.replace(",", "") for n in _NUM.findall(text or "")}


def r_numbers_sourced(s, ctx):
    """지어낸 숫자 금지 — 대본·제목의 숫자는 조사 원문(source_text)에 있어야 한다. 단위 변환(억·조)은 원문 표기를 따라라."""
    src = _norm_nums(ctx.get("source_text", ""))
    if not src:
        return [Issue("hp_numbers", REJECT, "source", "", "조사 원문이 비었다 — research 단계부터")]
    out = []
    t = s.get("title") or {}
    where = [("title", f"{t.get('h1', '')} {t.get('h2', '')}")] + [
        (f"groups[{i}]", g.get("text") or " ".join(g.get("lines") or [])) for i, g in enumerate(_groups(s))]
    for w, text in where:
        for n in _norm_nums(text):
            if n not in src:
                out.append(Issue("hp_numbers", REJECT, w, n, "원문에 없는 숫자 — 지어내지 마라(원문 표기 그대로 쓰거나 숫자를 빼라)"))
    return out


def r_headline(s, ctx):
    t = s.get("title") or {}
    out = []
    for k in ("h1", "h2"):
        v = (t.get(k) or "").strip()
        if not v:
            out.append(Issue("hp_headline", REJECT, f"title.{k}", "", "헤드라인은 두 줄(h1·h2)"))
            continue
        w = ink_width(v, spec.HEAD_FONT, spec.HEAD_FONT_PX, spec.HEAD_BOLDEN_PX)
        if w > 1000:
            out.append(Issue("hp_headline", REJECT, f"title.{k}", v, f"헤드라인 한 줄이 너무 길다 {w}px > 1000px(원본 8~10자)"))
    if t.get("emph") not in (1, 2) or t.get("emph_color") not in ("red", "yellow"):
        out.append(Issue("hp_headline", REJECT, "title.emph", str(t.get("emph")), "강조 줄 emph(1|2)와 emph_color(red|yellow)를 정하라"))
    return out


def r_queries(s, ctx):
    q = [x for x in (s.get("queries") or []) if str(x).strip()]
    if 3 <= len(q) <= spec.POLICY_FOOTAGE_QUERIES:
        return []
    return [Issue("hp_queries", REJECT, "queries", str(len(q)), f"영상 검색어 3~{spec.POLICY_FOOTAGE_QUERIES}개(인물 인터뷰·경기·무대 등 실제 영상이 나올 말)")]


@lru_cache(maxsize=4)
def _cmap(path):
    from fontTools.ttLib import TTFont
    return set(TTFont(path)["cmap"].getBestCmap())


def missing_glyphs(text, path=None):
    """글꼴에 없는 글자 → 렌더하면 □(두부). 2026-09-25 실측: 주아체에 가운뎃점(·) 없음."""
    try:
        cm = _cmap(path or spec.SUB_FONT)
    except ImportError:          # fontTools 없는 파이썬 — PIL로 두부 모양과 대조
        f = _font(path or spec.SUB_FONT, 40)
        tofu = f.getmask("￿").getbbox()
        return sorted({c for c in text if not c.isspace() and f.getmask(c).getbbox() == tofu})
    return sorted({c for c in text if not c.isspace() and ord(c) not in cm})


def r_glyphs(s, ctx):
    out = []
    t = s.get("title") or {}
    for w, text, font in [("title", f"{t.get('h1', '')}{t.get('h2', '')}", spec.HEAD_FONT)] + [
            (f"groups[{i}]", "".join(g.get("lines") or []), spec.SUB_FONT) for i, g in enumerate(_groups(s))]:
        miss = missing_glyphs(text, font)
        if miss:
            out.append(Issue("hp_glyphs", REJECT, w, "".join(miss), "글꼴에 없는 글자 — 화면에 □로 나온다. 다른 글자로(·→, 또는 띄어쓰기)"))
    return out


_NEWS_END = re.compile(r"(했다|였다|이었다|이다|한다|된다|었다|았다)[.!]?$")


def r_ending(s, ctx):
    bad = [i for i, g in enumerate(_groups(s))
           if not (g.get("text") or "").lstrip().startswith(("\"", "'", "“"))
           and _NEWS_END.search((g.get("text") or " ".join(g.get("lines") or [])).strip())]
    if len(bad) <= 1:
        return []
    return [Issue("hp_ending", WARN, "groups", str(bad), "이 채널은 ~음/~함/~임/~됨 명사형으로 끝낸다(따옴표 인용 제외)")]


RULES = [
    Rule("hp_count", REJECT, f"자막(groups)은 {spec.SUB_COUNT_MIN}~{spec.SUB_COUNT_MAX}개. 한 개 = 한 컷 ≈ 2초.", r_count),
    Rule("hp_lines", REJECT, "자막 한 개는 lines 1~2줄, 한 줄은 대략 14자 안쪽. 대부분 두 줄로 나눈다. text = lines를 공백으로 이은 것.", r_lines),
    Rule("hp_first_mark", REJECT, "첫 자막은 반드시 형광펜(mark:true) — 충격적인 인용이나 반전 사실.", r_first_mark),
    Rule("hp_mark_max", REJECT, f"형광펜(mark)은 편당 {spec.MARK_MAX}개 이하 — 첫 자막 + 결정적 인용 1~2개.", r_mark_max),
    Rule("hp_red", REJECT, "빨간 글자(red)는 핵심 단어 1~2개만, 자막 줄에 적힌 그대로.", r_red),
    Rule("hp_name", REJECT, f"주인공 이름은 {spec.NAME_REVEAL_BY}번째 자막 안에 공개(예: 그의 이름 \"○○○\"). person 칸에 이름.", r_name_early),
    Rule("hp_numbers", REJECT, "숫자(연도·금액·순위·기록)는 조사 원문에 있는 것만, 원문 표기 그대로. 없으면 숫자를 빼라.", r_numbers_sourced),
    Rule("hp_headline", REJECT, "헤드라인 h1·h2 각 8~10자, 한 줄(emph 1|2)을 red 또는 yellow로 강조. \"~한 남자/여자/아이돌\" 형.", r_headline),
    Rule("hp_queries", REJECT, f"queries: 유튜브에서 그 인물의 실제 영상(인터뷰·경기·무대·뉴스)이 나올 검색어 3~{spec.POLICY_FOOTAGE_QUERIES}개. 영어 이름 포함.", r_queries),
    Rule("hp_glyphs", REJECT, "가운뎃점(·)·특수기호·이모지 쓰지 마라 — 글꼴에 없어 □로 나온다. 쉼표·따옴표·마침표·말줄임(...)은 된다.", r_glyphs),
    Rule("hp_ending", WARN, "끝맺음은 반말 명사형 ~음/~함/~임/~됨/~짐, 또는 명사로 끊기(\"그렇게 5년.\"). 인용은 따옴표.", r_ending),
]
for _r in RULES:
    lint.register(_r)
IDS = [r.id for r in RULES]
