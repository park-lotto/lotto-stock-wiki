# -*- coding: utf-8 -*-
"""확정 썰 대본 → 대화형(나레이션·인물 대사) 대본 변환 (관제 128, 2026-10-05 사장님 "대화형으로").

★판단 주인: 이 파일 하나.
  - 어떤 틀이 있고 누가 말하나(FORMS) · 화자별 기본 성우(cast_of) · 변환(convert) · 장면 출처 재배치(remap_beat_sources)
  - 칸의 화자·연기 지시는 job.script_structure["dialogue"]["lines"][i] 에만 둔다(줄 i = 칸 i, edit_plan.script_sentences).
    ★연기 지시([curious] 등)를 narration 글자에 넣지 않는다 — _caption_segments가 그대로 자막에 찍는다.
★계약(사실 검사): 원문에 없는 숫자를 만들지 않는다 · 원문 줄을 하나도 빠뜨리지 않는다(src 로 덮는다).
  실패는 ValueError(호출부가 화면에 그대로 띄운다). 조용히 고쳐 맞추지 않는다.
샘플·근거: tools/voice_format/ (썰1~5 대본, 사장님 청취 2026-10-05).
"""
import json
import re

from shopping_shorts import script_generate

# 일레븐 v3 연기 지시 — 이 목록 밖은 버린다(엉뚱한 태그를 읽어 버리는 것 방지)
TAGS = ("curious", "laughs", "skeptical", "casual", "doubtful", "cheerful", "excited",
        "friendly", "sighs", "whispers", "surprised", "happy")

FORMS = {
    "narr_then_talk": {
        "desc": "제품 정체까지는 나레이션 썰, 그 뒤는 동생·언니 대화로 의심 → 충격 포인트",
        "label": "나레이션 → 대화",
        "roles": ("나레이션", "동생", "언니"),
        "cast": {"나레이션": "tc-piljae-natural", "동생": "kr-yooni-natural", "언니": "kr-mina-natural"},
        "rule": "훅·문제·'이건 바로 (제품)'까지는 나레이션이 썰 말투 그대로 말한다. 그 뒤부터 동생(묻고 의심하는 쪽)과 "
                "언니(써 본 쪽)가 반말로 주고받으며 '말도 안 되는 게 → 심지어 → 충격 포인트'를 푼다. 동생 의심이 점점 커지고 "
                "언니가 충격 포인트로 뒤집는다. 마지막 한 줄은 나레이션.",
    },
    "escalate_talk": {
        "desc": "처음부터 대화 — 동생 의심이 칸마다 커지다 충격 포인트에서 뒤집힘",
        "label": "고조 계단 대화",
        "roles": ("동생", "언니"),
        "cast": {"동생": "kr-yooni-natural", "언니": "kr-mina-natural"},
        "rule": "처음부터 끝까지 동생과 언니의 반말 대화. 언니가 훅을 던지고, 동생 의심이 칸마다 한 계단씩 커진다"
                "('거기서 거기지' → '장식 아니고?' → '그게 다야?' → '그래도 ~면 끝이잖아'). 언니는 그 의심에 답하며 "
                "썰 칸(문제 → 이건 바로 → 말도 안 되는 게 → 심지어 → 충격 포인트)을 하나씩 공개한다. 동생이 인정하며 끝난다.",
    },
    "talk_sandwich": {
        "desc": "대화로 문제를 열고, 가운데는 나레이션 썰, 다시 대화로 마무리",
        "label": "대화로 열고 닫기",
        "roles": ("나레이션", "동생", "언니"),
        "cast": {"나레이션": "tc-piljae-natural", "동생": "kr-yooni-natural", "언니": "kr-mina-natural"},
        "rule": "동생이 문제 상황을 혼잣말/불평으로 열고 언니가 '그럼 이거 써 봐'로 넘긴다. 가운데는 나레이션이 썰 말투로 "
                "'이건 바로 → 말도 안 되는 게 → 심지어 → 충격 포인트'를 쭉 말한다. 마지막 두 줄은 다시 동생·언니 대화로 닫는다.",
    },
    "narr_monologue": {
        "desc": "나레이션 썰 사이사이 주인공 혼잣말(한숨·놀람·만족)",
        "label": "나레이션 + 독백",
        "roles": ("나레이션", "독백"),
        "cast": {"나레이션": "tc-piljae-natural", "독백": "kr-mina-natural"},
        "rule": "나레이션이 썰 칸을 처음부터 끝까지 그대로 말한다. 그 사이 2~4곳에 주인공의 짧은 혼잣말(독백)을 넣는다 — "
                "문제를 겪는 한숨, 제품을 처음 본 반응, 기능을 확인한 반응, 마지막 만족. 독백은 짧게(15자 안팎).",
    },
    "objector": {
        "desc": "1인칭 '나' + 반대하는 사람 — '그냥 반품해' 반복 뒤 태세전환",
        "label": "반대자 상황극",
        "roles": ("나", "반대자"),
        "cast": {"나": "kr-mina-natural", "반대자": "tc-piljae-natural"},
        "rule": "'나'가 1인칭으로 사건을 열고(나레이션 겸 대사), 반대자(아빠·남편 등 한 명, 대사 안에서 호칭으로만 밝힘)가 "
                "같은 반대 말(예: '그냥 반품해')을 2~3번 되풀이한다. '나'는 반대할 때마다 썰 칸 하나씩(문제 → 심지어 → "
                "충격 포인트)으로 반박한다. 마지막에 반대자가 태세전환하며 되풀이하던 말을 뒤집는다.",
    },
}

_PROMPT = """너는 한국 쇼핑 쇼츠 대본 작가다. 아래 '확정 썰 대본'을 같은 내용의 **{label}** 대본으로 바꿔라.

틀 규칙: {rule}
화자는 이 중에서만: {roles}

반드시 지킬 것:
- 원문에 있는 사실만 쓴다. 원문에 없는 숫자·가격·구매처·후기·효과를 새로 만들지 않는다.
- 원문 줄을 하나도 빠뜨리지 않는다. 각 줄의 src 에 그 줄이 옮긴 원문 줄 번호(0부터)를 적는다.
- 썰 흐름(훅 → 문제 → 이건 바로 → 말도 안 되는 게 → 심지어 → 충격 포인트 → 마무리)과 고조는 살린다.
- 대사는 실제로 말하듯 짧고 자연스럽게. 한 줄 = 한 사람의 한 번 말. 6~12줄.
- 나레이션이 아닌 대사는 **끝맺은 한 마디**로 쓴다('~스트레스를'처럼 조사로 끊긴 줄 금지).
- 문장 부호를 꼭 붙인다: 묻는 말은 '?', 놀람은 '!', 나머지는 '.' — 성우가 부호를 보고 억양을 정한다.
- tag 는 그 줄의 연기 지시 하나: {tags} 중에서 고르거나 "". 대사(text)에 대괄호를 쓰지 않는다.

확정 썰 대본(번호: 줄):
{lines}
"""

_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object",
        "properties": {"speaker": {"type": "string"}, "text": {"type": "string"},
                       "tag": {"type": "string"}, "src": {"type": "array", "items": {"type": "integer"}}},
        "required": ["speaker", "text", "tag", "src"]}}},
    "required": ["lines"],
}

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_CUT_END = re.compile(r"(을|를|에서|으로|에게|와|과|의)$")      # 대사가 조사로 끊긴 줄(말로 하면 어색)
_PUNCT_END = re.compile(r"[.?!~…]$")                          # 성우 억양의 근거


def numbers(text):
    """글 속 숫자 집합(쉼표 제거). 사실 검사가 쓴다."""
    return {n.replace(",", "") for n in _NUM.findall(text or "")}


def cast_of(form, override=None):
    """화자 → 성우 프리셋 id. 틀 기본값 위에 사람이 고른 것(override)만 덮는다."""
    base = dict(FORMS[form]["cast"])
    for k, v in (override or {}).items():
        if k in base and v:
            base[k] = v
    return base


def check(src_lines, out, form):
    """변환 결과 검사 — 문제 목록(빈 목록이면 통과). convert 와 검사 도구가 같이 쓴다."""
    roles = set(FORMS[form]["roles"])
    errs = []
    if not 4 <= len(out) <= 14:
        errs.append(f"줄 수 {len(out)}(4~14 밖)")
    covered = set()
    for i, ln in enumerate(out):
        if ln.get("speaker") not in roles:
            errs.append(f"{i}줄 화자 '{ln.get('speaker')}' 틀 밖")
        t = (ln.get("text") or "").strip()
        if not t:
            errs.append(f"{i}줄 빈 대사")
        if "[" in t or "]" in t:
            errs.append(f"{i}줄 대사에 대괄호")
        if t and ln.get("speaker") != "나레이션" and _CUT_END.search(t):
            errs.append(f"{i}줄 대사가 조사로 끊김")
        if t and not _PUNCT_END.search(t):
            errs.append(f"{i}줄 끝 문장 부호 없음")
        for s in ln.get("src") or []:
            if isinstance(s, int) and 0 <= s < len(src_lines):
                covered.add(s)
            else:
                errs.append(f"{i}줄 src {s} 범위 밖")
    missing = [i for i in range(len(src_lines)) if i not in covered]
    if missing:
        errs.append(f"원문 줄 빠짐 {missing}")
    used = {ln.get("speaker") for ln in out}
    if roles - used:
        errs.append(f"안 쓴 화자 {sorted(roles - used)}")
    new_nums = numbers(" ".join(ln.get("text") or "" for ln in out)) - numbers(" ".join(src_lines))
    if new_nums:
        errs.append(f"원문에 없는 숫자 {sorted(new_nums)}")
    return errs


def convert(lines, form, product="", *, call=None, tries=2):
    """확정 대본 줄 목록 → [{speaker, text, tag, src:[원문 줄 번호]}]. 실패는 ValueError."""
    if form not in FORMS:
        raise ValueError(f"모르는 대화 틀: {form}")
    src = [(x or "").strip() for x in (lines or []) if (x or "").strip()]
    if len(src) < 2:
        raise ValueError("대본이 비어 있어요 — 확정 대본을 먼저 만들어 주세요")
    f = FORMS[form]
    call = call or (lambda p, s: script_generate._call_json(p, s))
    prompt = _PROMPT.format(label=f["label"], rule=f["rule"], roles=", ".join(f["roles"]),
                            tags=", ".join(TAGS),
                            lines="\n".join(f"{i}: {x}" for i, x in enumerate(src)))
    last = []
    for _ in range(max(1, tries)):
        got = call(prompt, _SCHEMA) or {}
        out = []
        for ln in got.get("lines") or []:
            tag = (ln.get("tag") or "").strip().strip("[]").lower()
            out.append({"speaker": (ln.get("speaker") or "").strip(),
                        "text": re.sub(r"\s+", " ", (ln.get("text") or "")).strip(),
                        "tag": tag if tag in TAGS else "",
                        "src": [s for s in (ln.get("src") or []) if isinstance(s, int)]})
        last = check(src, out, form)
        if not last:
            return out
    raise ValueError("대화형 변환에 실패했어요 — " + ("; ".join(last[:3]) or "AI 응답이 비었어요")
                     + ". 잠시 후 다시 눌러 주세요")


def remap_beat_sources(beat_sources, out):
    """원문 줄별 장면 출처 → 대화 줄별. 대화 줄 i 는 자기 src 첫 원문 줄의 출처를 잇는다
    (같은 장면이 여러 칸에 이어질 수 있다 — 같은 내용을 주고받는 칸이라 화면이 이어지는 게 맞다)."""
    if not beat_sources:
        return None
    res = []
    for ln in out:
        s = (ln.get("src") or [None])[0]
        res.append(beat_sources[s] if isinstance(s, int) and 0 <= s < len(beat_sources) else None)
    return res


def apply_to_lines(lines, beat_sources, form, product="", *, call=None):
    """2단계 대본 작가(story_writer.make_drafts)가 안을 확정하기 직전에 부른다 — 줄과 장면 출처가 아직 짝일 때.
    lines = [{text, role, group}], beat_sources = 줄별 출처. 반환 (새 lines, 새 출처, 대화 메타, 실패 이유).
    실패하면 썰 그대로 돌려주고 이유만 싣는다(호출부가 안에 남겨 카드가 보여 준다)."""
    try:
        out = convert([L.get("text") or "" for L in lines], form, product, call=call)
    except Exception as e:      # noqa: BLE001 — 변환 실패가 대본 생성을 막으면 안 된다
        return lines, beat_sources, None, str(e)[:200]
    new_bs = remap_beat_sources(beat_sources, out) or beat_sources
    new_lines = [dict((lines[o["src"][0]] if o.get("src") else {}), text=o["text"]) for o in out]
    return new_lines, new_bs, meta(form, out), ""


def meta(form, out, cast_override=None):
    """job.script_structure["dialogue"] 에 남길 값 — 칸 i 의 화자·연기 지시는 lines[i]."""
    return {"form": form, "cast": cast_of(form, cast_override),
            "lines": [{"speaker": ln["speaker"], "tag": ln["tag"], "src": ln["src"]} for ln in out]}


def of_structure(ss):
    """script_structure → 대화 메타(없거나 모양이 틀리면 None). 합성 경로가 '이 작업이 대화형인가'를 여기서만 묻는다."""
    d = (ss or {}).get("dialogue") if isinstance(ss, dict) else None
    if isinstance(d, dict) and isinstance(d.get("lines"), list) and d["lines"] and isinstance(d.get("voices"), dict):
        return d
    return None


def of_job(job):
    return of_structure((job or {}).get("script_structure"))


def script_text(out):
    """대화 줄 → given_script(줄 = 칸). 연기 지시는 넣지 않는다."""
    return "\n".join(ln["text"] for ln in out)


if __name__ == "__main__":       # 수동 확인: py -m shopping_shorts.dialogue_script <틀> < 대본.txt
    import sys
    print(json.dumps(convert(sys.stdin.read().splitlines(), sys.argv[1]), ensure_ascii=False, indent=1))
