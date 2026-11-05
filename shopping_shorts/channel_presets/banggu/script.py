# -*- coding: utf-8 -*-
"""대본 — 검증된 재료(material) + 규칙표(rules) + 갈래별 칸 → 대본. 반려되면 사유를 붙여 고쳐 쓰게 한다.

지금 숏템 엔진(story_writer)과 같은 원리: **모델은 칸만 채우고, 신호어는 코드가 붙인다.**
칸은 39편에서 되풀이된 뼈대(channel/banggu/역분석_2026-10-05.md §13)에서 왔다.
예시는 **모양만** 보여 준다 — 원본 문장을 베끼지 않게 없는 제품으로 쓴 가짜 예시다.
"""
import json
import re

from . import material as mat
from . import rules, spec

# 갈래별 칸: (모델이 내는 키, 역할 이름, 여러 줄인가)
SLOTS = {
    "hidden": [("intro", "소개", False), ("doubt", "의문", False), ("look", "살펴봄", True),
               ("real", "진짜이유", False), ("bonus", "덤", False)],
    "mechanism": [("intro", "소개", False), ("wonder", "의문", False), ("old", "기존", False),
                  ("how", "원리", True), ("bonus", "덤", False)],
    "substitute": [("origin", "원조", False), ("lack", "아쉬움", False), ("crowd", "무리", False),
                   ("proof", "근거", True), ("payoff", "끝", False)],
}

_STRUCT = {
    "hidden": """[구조 — 숨은 이유형: "사람들이 이걸 사는 진짜 이유는 겉보기와 다르다"]
title   읽어 주는 제목. 제품 종류 낱말로 끝나는 명사구(예: "~다는 ○○의 정체", "○○계의 1황")
intro   남들이 이미 좋아한다는 말 + 제품. **명사로 끝낸다**  ([재료] buzz 가 있을 때만 그 말을 쓴다. 없으면 제품이 무엇인지만)
doubt   "사람들이 이걸 사는 이유는 단순히 {surface} 때문이 아니라는데" — [재료] surface 로. ("하지만"은 우리가 붙인다)
look    1~3줄. 첫 줄은 "{부위·구성}을 살펴보니"로 열고 특징을 말한다. 줄 끝은 ~고 / ~다고 함
        (이 뒤에 우리가 "그러나 정작 ○○ 꽂힌 포인트는 따로 있다는데"를 넣는다 — 쓰지 마라)
real    [재료] real 을 한 줄로. "~해서라고" 또는 "~다고"로 끝낸다 ("그건 바로"는 우리가 붙인다)
bonus   남는 장점 하나("무엇보다"는 우리가 붙인다). 없으면 빈 문자열. 쓰면 "~다고"로 끝낸다
comment 맨 끝 혼잣말 한 줄(내 감상, ㅋㅋ). 없으면 빈 문자열""",
    "mechanism": """[구조 — 원리형: "어떻게 그게 되지?"를 묻고 작동 방식으로 푼다]
title   읽어 주는 제목. 겉보기에 말이 안 되는 점 + 제품 종류, 명사로 끝
intro   제품을 한 줄로(명사로 끝). 없어도 되면 빈 문자열
        (이 뒤에 우리가 "이 ○○을 본 사람들이 놀란 부분이 있는데"를 넣는다 — 쓰지 마라)
wonder  "어떻게 {wonder}~할 수가 있냐는 거" — 반드시 '어떻게'가 들어가고 '~냐는 거'로 끝난다 ("바로"는 우리가 붙인다)
old     "보통 {제품 종류}은 {old_way}~인데 {old_flaw}~단점이 있었음" — [재료] old_way·old_flaw 가 없으면 빈 문자열 ("사실"은 우리가 붙인다)
how     1~3줄. [재료] how 의 작동 방식을 풀어 쓴다. 마지막 줄은 "~다는 거" 또는 "~다고 함" ("하지만 이건"은 우리가 붙인다)
bonus   다른 장점 하나, "~다고"로 끝낸다 ("심지어"는 우리가 붙인다)
comment 맨 끝 혼잣말 한 줄(내 감상, ㅋㅋ). 없으면 빈 문자열""",
    "substitute": """[구조 — 대체형: "비싼 원조 대신 이걸 찾아냈다"]
title   읽어 주는 제목. 원조가 당했다는 꼴(예: "영업기밀을 빼앗겨버린 ○○", "결국 털려버린 ○○"), 명사로 끝
origin  원조 소개 — 사람들이 원래 무엇에 돈·수고를 들였나. **명사로 끝낸다**
lack    [재료] original_lack — 원조의 아쉬운 점. "~는데" 또는 "~되었음"으로 끝낸다 ("하지만"은 우리가 붙인다)
crowd   "{별명 붙은 무리}은 {노력} 끝에 이걸 발견해버렸는데" — 무리는 [재료]에 나온 사람들. 없으면 "사람들은" ("그럼에도"는 우리가 붙인다)
proof   2~3줄. [재료] same_proof — 원조만큼 된다는 근거. 줄 끝은 ~고 / ~다고 함
payoff  [재료] gain — "{이득}~라 {원조}를 부를(살) 이유가 없어져버렸다고" 꼴로 닫는다 ("무엇보다"는 우리가 붙인다)
comment 맨 끝 혼잣말 한 줄(내 감상, ㅋㅋ). 없으면 빈 문자열""",
}

_EXAMPLE = {
    "hidden": {"title": "마트 직원들이 먼저 쓴다는 장바구니",
               "intro": "계산대 앞에서 유독 자주 보인다는 접이식 장바구니",
               "doubt": "사람들이 이걸 사는 이유는 단순히 접혀서가 아니라는데",
               "look": ["바닥을 살펴보니 딱딱한 판이 들어 있어 계란을 담아도 기울지 않고", "손잡이가 두 겹이라 어깨에 메도 된다고 함"],
               "real": "트렁크에 펼쳐 두면 장 본 게 굴러다니지 않아서라고",
               "bonus": "", "comment": "아니 이걸 왜 이제 알았냐 ㅋㅋ"},
    "mechanism": {"title": "물 없이 설거지가 된다는 수세미",
                  "intro": "",
                  "wonder": "세제도 물도 없이 어떻게 기름때가 닦일 수가 있냐는 거",
                  "old": "보통 수세미는 거품으로 기름을 띄우는 방식인데 물을 계속 틀어 놔야 한다는 단점이 있었음",
                  "how": ["올 하나하나가 갈고리 모양이라 기름을 긁어 안으로 가둬 버리는 구조라", "마른 채로 한 번 훑기만 해도 팬이 뽀득해진다는 거"],
                  "bonus": "쓰고 나서 털기만 하면 다시 쓸 수 있다고", "comment": "아니 이러면 고무장갑이 왜 필요함 ㅋㅋ"},
    "substitute": {"title": "결국 털려버린 동네 열쇠집",
                   "origin": "문 잠기면 일단 부르고 보던 열쇠 출장",
                   "lack": "한밤중에 부르면 출장비부터 붙어 부담이 컸다는데",
                   "crowd": "자꾸 열쇠 잃어버리던 자취생들은 검색 끝에 이걸 발견해버렸는데",
                   "proof": ["문고리째 바꿔 끼우는 방식이라 드라이버 하나면 달 수 있고", "한 번 달아 두면 번호만 누르면 열린다고 함"],
                   "payoff": "출장 한 번 값이면 달 수 있어서 열쇠집을 부를 이유가 없어져버렸다고", "comment": "아 진작 달 걸 ㅋㅋ"},
}

_LEAD = re.compile(r"^(하지만|그러나|그런데|근데|사실|바로|심지어|무엇보다|게다가|그럼에도|그건 바로|하지만 이건|이건)\s+")


def _batchim(word):
    w = re.sub(r"[^가-힣]", "", word or "")
    return bool(w) and (ord(w[-1]) - 0xAC00) % 28 != 0


def josa(word, with_b, without_b):
    return word + (with_b if _batchim(word) else without_b)


def _clean(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    for _ in range(2):
        t = _LEAD.sub("", t)
    return t


def material_block(material):
    rows = []
    for k in mat.FIELDS:
        if k in material:
            v = material[k]
            rows.append("  %-13s %s%s" % (k, v["text"], ("   ← 원문: \"%s\"" % v["quote"]) if v.get("quote") else ""))
    return "\n".join(rows)


def build_prompt(product, kind, material, feedback_text="", extra_facts=""):
    return (
        "너는 커뮤니티 썰 채널의 대본 작가다. 게시글을 읽어 주듯, **남에게 들은 이야기를 옮기는 말투**로 25초쯤 되는 대본을 쓴다.\n"
        "화자는 써 본 사람이 아니다. 주체는 '사람들이'나 별명 붙은 무리다. 문장을 마침표로 끊지 말고 '~는데'로 넘기고 '~다고'로 닫는다.\n\n"
        f"[제품] {product}\n\n{_STRUCT[kind]}\n\n[규칙 — 어기면 반려된다]\n{rules.prompt_block()}\n"
        "- 접속 신호어(하지만·사실·바로·심지어·무엇보다·그럼에도·그건 바로)는 **우리가 붙인다. 네가 쓰지 마라.**\n\n"
        "[출력 — JSON 객체 하나만. 키는 아래 예시와 같다]\n"
        f"[예시 — 모양만. 이 제품·문장을 쓰지 마라]\n{json.dumps(_EXAMPLE[kind], ensure_ascii=False)}\n\n"
        "[재료 — 사실은 여기서만. 여기 없는 숫자·나라·'품절'·'1위' 같은 말은 쓰지 마라]\n"
        f"{material_block(material)}\n" + (f"\n[그 밖에 영상에 나온 특징]\n{extra_facts}\n" if extra_facts else "") + (feedback_text or "")
    )


def to_script(out, kind, material):
    """모델 출력(칸) → 대본. 신호어를 여기서 붙인다(붙이는 자리는 이 함수 하나)."""
    lines = []
    for key, role, multi in SLOTS[kind]:
        v = out.get(key)
        vals = [_clean(x) for x in (v if isinstance(v, list) else [v]) if (x or "").strip()]
        if not vals:
            continue
        if kind == "hidden":
            if key == "doubt":
                vals[0] = spec.SIG["but"] + " " + vals[0]
            elif key == "real":
                who = (material.get("real_who") or {}).get("text") or "사람들"
                lines.append({"role": "꺾음", "text": spec.SIG["turn"].format(who=josa(who, "이", "가"))})
                vals[0] = spec.SIG["turn_answer"] + " " + vals[0]
            elif key == "bonus":
                vals[0] = spec.SIG["bonus"][1] + " " + vals[0]
        elif kind == "mechanism":
            if key == "wonder":
                kw = (material.get("kind_word") or {}).get("text") or "제품"
                lines.append({"role": "의문", "text": spec.SIG["wonder"].format(kind_word=josa(kw, "을", "를"))})
                vals[0] = spec.SIG["exactly"] + " " + vals[0]
            elif key == "old":
                vals[0] = spec.SIG["actually"] + " " + vals[0]
            elif key == "how":
                vals[0] = spec.SIG["but"] + " 이건 " + vals[0]
            elif key == "bonus":
                vals[0] = spec.SIG["bonus"][0] + " " + vals[0]
        elif kind == "substitute":
            if key == "lack":
                vals[0] = spec.SIG["but"] + " " + vals[0]
            elif key == "crowd":
                vals[0] = spec.SIG["yet"] + " " + vals[0]
            elif key == "payoff":
                vals[0] = spec.SIG["bonus"][1] + " " + vals[0]
        lines += [{"role": role, "text": t} for t in vals]
    return {"kind": kind, "title": re.sub(r"\s+", " ", (out.get("title") or "").strip()),
            "lines": lines, "comment": re.sub(r"\s+", " ", (out.get("comment") or "").strip())}


def seconds(script):
    n = rules.chars(script.get("title") or "") + sum(rules.chars(t) for _, t in rules.body(script)) + rules.chars(script.get("comment") or "")
    return round(n / spec.CHARS_PER_SEC, 1)


def as_text(script):
    rows = ["[제목] " + (script.get("title") or "")] + ["[%s] %s" % (r, t) for r, t in rules.body(script)]
    if script.get("comment"):
        rows.append("[혼잣말] " + script["comment"])
    return "\n".join(rows)


def generate(product, kind, material, call, *, source_text="", seed_text="", extra_facts="", max_rewrites=None, log=print):
    """→ (script, issues, attempts). 재료가 갈래 자격을 못 채우면 쓰지 않고 ValueError(조용히 지어내지 않는다)."""
    lack = [n for n in spec.KIND_NEEDS[kind] if n not in material]
    if lack:
        raise ValueError("%s 갈래 재료 없음: %s" % (spec.KIND_KO[kind], ", ".join(lack)))
    max_rewrites = spec.POLICY_MAX_REWRITES if max_rewrites is None else max_rewrites
    ctx = {"source_text": source_text, "seed_text": seed_text, "material": material, "product": product}
    fb, last = "", None
    for attempt in range(max_rewrites + 1):
        raw = call(build_prompt(product, kind, material, fb, extra_facts))
        try:
            out = mat.parse(raw)
        except ValueError as e:
            last = ({"kind": kind, "title": "", "lines": [], "comment": ""},
                    [rules.Issue("format", rules.REJECT, "output", str(e)[:60], "JSON 객체 하나만")], attempt + 1)
            fb = "\n\n[재작성 지시] 방금 출력이 JSON이 아니었다. JSON 객체 하나만 출력하라."
            continue
        script = to_script(out, kind, material)
        issues = rules.lint(script, ctx)
        rej = rules.rejects(issues)
        log("[banggu.script] %s 시도 %d: 본문 %d줄 %d자, 반려 %d" % (
            spec.KIND_KO[kind], attempt + 1, len(rules.body(script)), sum(rules.chars(t) for _, t in rules.body(script)), len(rej)))
        last = (script, issues, attempt + 1)
        if not rej:
            return last
        fb = rules.feedback(issues) + "\n\n방금 낸 JSON:\n" + (raw or "").strip()[:4000]
    return last
