# -*- coding: utf-8 -*-
"""유튜브 썰 스타일의 '터지는 공식 문장' 확장 — 공식은 살리고 ①약간 변형 ②더 자극적인 확장을 만든다 (2026-09-27 사장님).

사장님: "미끼랑 화제는 터지는 공식 문장들이야, 활용하는데 약간씩만 바꿔야 되는 거야 / 저기서 정말 더 자극적인 멘트들로
        확장을 하고 싶은 거야 / 열어보면 겹치는 게 너무 많은데 줄이는 게 아니라 확장을 하면 좋겠어"
  (서버, repo 폴더에서, env 적재 후) python3 tools/spine_presets/expand_yt_formula.py <출력.json> [변형수=6] [자극수=6]

원본 = 화면에 보이는 유튜브 스타일(이름에 '유튜브') 15개의 칸 예시 전부(DB). 제목(title)은 스타일마다 달라 뺀다.
코드 검사로 거른다: {빈칸} 집합이 원본과 같다 / 반말(존댓말 끝말이면 버림) / 길이 / 중복 / 실존 인물 / 낱말 반복.
결과는 원본 문장마다 {"styles": [쓰는 스타일], "variants": [...], "spicy": [...]}. DB·라이브에는 아무것도 안 쓴다.
"""
import sys, os, re, json
sys.path.insert(0, ".")
from shopping_shorts.store import Store
from shopping_shorts import script_generate as sg
from shopping_shorts.story_writer import _POLITE_WORD

OUT = sys.argv[1]
NV = int(sys.argv[2]) if len(sys.argv) > 2 else 6
NS = int(sys.argv[3]) if len(sys.argv) > 3 else 6
SKIP = {"title"}
ROLE_KO = {"bait": "미끼", "fame": "화제", "reveal": "공개", "limit": "기존 한계", "solve": "해결", "more": "심지어",
           "twist": "재반전", "land": "마무리", "origin": "원래 용도", "notice": "눈치챔", "cases": "초보 활용",
           "escalation": "고수 활용"}

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "src": {"type": "string"}, "variants": {"type": "array", "items": {"type": "string"}},
    "spicy": {"type": "array", "items": {"type": "string"}}}, "required": ["src", "variants", "spicy"]}}},
    "required": ["items"]}

BRIEF = """아래는 유튜브 쇼핑 썰 숏폼에서 **터지는 공식 문장**이다. 칸: %(role)s. 말투는 남 얘기 전하는 반말 썰
(끝말 ~다는데 · ~다는 거 · ~해 버림 · ~였음 · ~다고). 이 문장들은 어떤 제품에나 들어가는 공식이다.

문장마다 두 가지를 만들어라.
① variants %(nv)d개 — **공식은 그대로 두고 약간씩만** 바꾼 것. **원문의 머리말(첫 어구)은 글자 그대로** 두고,
   문장 뼈대도 살리고 낱말·수식만 바꾼다. 다른 칸의 머리말을 가져오지 마라.
② spicy %(ns)d개 — **원문의 머리말은 그대로** 두고 같은 뼈대로 **훨씬 더 자극적으로** 확장한 것. 어그로·과장 좋다(난리·박살·초토화·멘붕·
   역대급·미쳐버린·실화냐 같은 센 말). 끝까지 보게 만드는 궁금증을 더 키워라.
공통 규칙:
- {중괄호 빈칸}은 **글자 그대로 같은 개수**로 남겨라. 새 빈칸을 만들지 마라. 빈칸이 없는 문장엔 넣지 마라.
- 특정 제품·기능 이야기를 넣지 마라(어느 제품에나 들어가야 한다).
- 실존 인물·연예인·기업 대표 이름 금지. 욕설 금지. 존댓말 금지.
- 서로 다른 문장이어야 한다. src에는 원문을 그대로 적어라.

[원문]
%(items)s"""

# 칸을 여는 머리말 — 원문이 이걸로 시작하면 변형도 같은 머리말로 시작해야 한다(첫 결과에서 미끼가 "이건 바로"·
#   "근데 진짜 충격적인 포인트는"으로 시작하는 등 다른 칸 머리말이 섞였다, 2026-09-27)
HEADS = ["최근 딱 봤을 때는", "최근 딱 봤을 땐", "이게 진짜 말도 안 되는게", "이게 말도 안 되는게", "근데 진짜 충격적인 포인트는",
         "더 충격적인 포인트는", "근데 진짜 미친 사용법은", "진짜 충격적인 활용법은", "이건 바로", "바로", "심지어", "게다가",
         "이러니", "이걸 개발한", "평소 쓰던", "초보들은", "그나마 중수들은", "이게 원래는", "그런데 사람들은", "근데", "최근", "요즘", "요새"]


def head_of(t):
    t = t.strip()
    for h in sorted(HEADS, key=len, reverse=True):
        if t.startswith(h):
            return h
    return ""


REAL = re.compile(r"백종원|이연복|최현석|안성재|고든 ?램지|유재석|강호동|아이유|손흥민|머스크|잡스|이재용|정주영")


def slots(t):
    return sorted(re.findall(r"\{[^}]*\}", t))


def polite(t):
    ws = re.sub(r"[.!?~…]+$", "", t).split()
    return bool(ws) and bool(_POLITE_WORD.search(ws[-1]))


def ok(v, x, seen, stat):
    k = re.sub(r"\s+", "", v)
    why = ""
    if not v or k in seen:
        why = "중복"
    elif slots(v) != slots(x):
        why = "빈칸 다름"
    elif polite(v):
        why = "존댓말"
    elif not (0.5 <= len(v) / max(1, len(x)) <= 2.0 or abs(len(v) - len(x)) <= 15):
        why = "길이"
    elif head_of(x) and not v.startswith(head_of(x).split()[0]):
        why = "머리말 바뀜"
    elif not head_of(x) and head_of(v) and head_of(v) not in ("최근", "요즘", "요새"):
        why = "다른 칸 머리말"
    elif REAL.search(v):
        why = "실존 인물"
    elif any(len(a) >= 2 and b.startswith(a) for a, b in zip(v.split(), v.split()[1:])):
        why = "낱말 반복"
    if why:
        stat["drop"][why] = stat["drop"].get(why, 0) + 1
        return False
    seen.add(k)
    return True


def main():
    sp = [s for s in Store("shopping_shorts/data/reference.db").list_spines()
          if s.get("no_cta") and s.get("beat_roles") and "유튜브" in (s.get("name") or "")]
    src = {}
    for s in sp:
        for r in s["beat_roles"]:
            if r in SKIP:
                continue
            for x in (s.get("templates") or {}).get(r) or []:
                if isinstance(x, str) and x.strip():
                    src.setdefault((r, x.strip()), set()).add(s.get("name") or "")
    out = {"roles": {}, "_why": "유튜브 공식 문장 확장(약간 변형 + 자극 확장). 도구: tools/spine_presets/expand_yt_formula.py"}
    stat = {"src": 0, "variants": 0, "spicy": 0, "drop": {}}
    by_role = {}
    for (r, x), names in src.items():
        by_role.setdefault(r, []).append((x, sorted(names)))
    for r, xs in sorted(by_role.items()):
        out["roles"][r] = []
        for i in range(0, len(xs), 8):
            chunk = xs[i:i + 8]
            prompt = BRIEF % {"role": "%s(%s)" % (ROLE_KO.get(r, r), r), "nv": NV, "ns": NS,
                              "items": "\n".join("- %s" % x for x, _ in chunk)}
            got = {it.get("src", "").strip(): it for it in (sg._call_json(prompt, SCHEMA) or {}).get("items") or []}
            for x, names in chunk:
                stat["src"] += 1
                seen = {re.sub(r"\s+", "", x)}
                it = got.get(x) or {}
                v = [a.strip() for a in it.get("variants") or [] if ok(str(a).strip(), x, seen, stat)]
                s_ = [a.strip() for a in it.get("spicy") or [] if ok(str(a).strip(), x, seen, stat)]
                stat["variants"] += len(v)
                stat["spicy"] += len(s_)
                out["roles"][r].append({"src": x, "styles": names, "variants": v, "spicy": s_})
            print("%s %d~%d" % (r, i, i + len(chunk)), file=sys.stderr)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == "__main__":
    main()
