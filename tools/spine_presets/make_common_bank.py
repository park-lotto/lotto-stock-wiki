# -*- coding: utf-8 -*-
"""공통 문구 자산 만들기 — 제품과 무관한 칸(미끼·화제·마무리·공감·댓글유도…)의 예시마다 변형을 만들어
shopping_shorts/story_common_bank.json 에 쌓는다 (2026-09-27 사장님).

사장님: "미끼들이나 마지막부분 등 공통적으로 들어가는 부분들을 많이 만들어놓고 랜덤으로 선택을 못한다면 순번대로 /
        공통부분을 많이 자산으로 만들어놓는 게 자산이야 / 조금씩 변형도 해놓고 / 어떤 게 들어가든 상관없는 지점들 /
        백종원 같은 실물은 빼"
  (서버, repo 폴더에서, env 적재 후) python3 tools/spine_presets/make_common_bank.py <출력.json> [변형수=6]
  → 받아서 검토 뒤 shopping_shorts/story_common_bank.json 으로 커밋. 기존 자산이 있으면 **이어 붙인다**(지우지 않음).

원본 = 등록된 스타일(스파인)의 그 칸 예시 전부(DB). 변형은 원본 하나당 N개, 모델 1회(원본 여러 개를 한 번에).
코드 검사로 거른다: {빈칸} 집합이 원본과 같다 / 말투(존댓말·반말)가 원본과 같다 / 길이 0.6~1.6배 / 원본·서로 중복 아님 /
실존 인물 표지 없음. 걸러진 수는 출력에 남긴다.
"""
import sys, os, re, json
sys.path.insert(0, ".")
from shopping_shorts.store import Store
from shopping_shorts import script_generate as sg

OUT = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
# 제품과 무관한 칸 — 플랫폼별. (story_writer.COMMON_ROLES 와 같은 값이어야 한다 — 거기서 가져온다)
from shopping_shorts.story_writer import COMMON_ROLES, _POLITE_WORD

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "src": {"type": "string"}, "variants": {"type": "array", "items": {"type": "string"}}},
    "required": ["src", "variants"]}}}, "required": ["items"]}

BRIEF = """아래는 쇼핑 숏폼 대본의 '%(role)s' 칸 문장들이다(%(voice)s). 이 칸은 어떤 제품에 넣어도 되는 공통 문장이다.
문장마다 **같은 역할·같은 말투로 조금씩 바꾼 변형 %(n)d개**를 만들어라.
- 뜻과 쓰임은 같게, 낱말·어순·표현을 바꿔 서로 다른 문장처럼 들리게. 너무 똑같거나 어색하면 안 된다.
- {중괄호 빈칸}은 **글자 그대로** 같은 개수로 남겨라(새 빈칸을 만들지 마라). 빈칸이 없는 문장엔 넣지 마라.
- 특정 제품·기능 이야기를 넣지 마라(어느 제품에나 들어가야 한다).
- 실존 인물·연예인·셰프·유튜버·기업 대표 이름을 쓰지 마라. 사람은 '친구·엄마·요리사' 같은 보통명사로.
- 길이는 원문과 비슷하게. src에는 원문을 그대로 적어라.

[원문]
%(items)s"""

VOICE = {"yt": "유튜브 썰 — 남 얘기 전하는 반말, 끝말 ~다는데·~다고·~였음·~버림",
         "ig": "인스타 — 존댓말 1인칭, 끝말 ~거든요·~더라고요·~어요·~세요"}
REAL = re.compile(r"백종원|이연복|최현석|에드워드|고든 ?램지|유재석|강호동|아이유|손흥민|일론|머스크|잡스|김치명인")


def slots(t):
    return sorted(re.findall(r"\{[^}]*\}", t))


def polite(t):
    return any(_POLITE_WORD.search(w) for w in re.sub(r"[.!?~…]+$", "", t).split()[-1:])


def main():
    st = Store("shopping_shorts/data/reference.db")
    src = {}
    for sp in st.list_spines():
        if not sp.get("beat_roles"):
            continue
        plat = "yt" if sp.get("no_cta") else "ig"
        for r in COMMON_ROLES[plat]:
            if r in sp["beat_roles"]:
                for x in (sp.get("templates") or {}).get(r) or []:
                    if isinstance(x, str) and x.strip():
                        src.setdefault((plat, r), set()).add(x.strip())
    bank = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"variants": {}}
    stat = {"src": 0, "made": 0, "kept": 0, "drop": {}}

    def drop(why):
        stat["drop"][why] = stat["drop"].get(why, 0) + 1
    for (plat, role), xs in sorted(src.items()):
        xs = sorted(xs)
        for i in range(0, len(xs), 12):          # 한 호출에 12문장
            chunk = xs[i:i + 12]
            stat["src"] += len(chunk)
            prompt = BRIEF % {"role": role, "voice": VOICE[plat], "n": N,
                              "items": "\n".join("- %s" % x for x in chunk)}
            out = sg._call_json(prompt, SCHEMA) or {}
            got = {it.get("src", "").strip(): it.get("variants") or [] for it in out.get("items") or []}
            for x in chunk:
                have = bank["variants"].setdefault(x, [])
                seen = {re.sub(r"\s+", "", v) for v in have + [x]}
                for v in got.get(x, []):
                    v = str(v).strip()
                    stat["made"] += 1
                    k = re.sub(r"\s+", "", v)
                    if not v or k in seen:
                        drop("중복"); continue
                    if slots(v) != slots(x):
                        drop("빈칸 다름"); continue
                    if polite(v) != polite(x):
                        drop("말투 다름"); continue
                    if not (0.6 <= len(v) / max(1, len(x)) <= 1.6 or abs(len(v) - len(x)) <= 8):   # 짧은 원문(「완벽하다고」)은 글자 수로
                        drop("길이"); continue
                    ws = v.split()
                    if any(len(ws[j]) >= 2 and ws[j + 1].startswith(ws[j]) for j in range(len(ws) - 1)):
                        drop("낱말 반복"); continue          # 실측: "진작 진작에 이렇게 나왔어야 한다는데"
                    if REAL.search(v):
                        drop("실존 인물"); continue
                    have.append(v); seen.add(k); stat["kept"] += 1
            print("%s %s %d~%d 완료" % (plat, role, i, i + len(chunk)), file=sys.stderr)
    bank["_why"] = ("제품과 무관한 칸의 공통 문구 자산(원문 예시 → 변형). story_writer.common_lines가 작업마다 순번으로 고른다. "
                    "만든 도구: tools/spine_presets/make_common_bank.py")
    json.dump(bank, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == "__main__":
    main()
