# 터진 대본(히트작) 분류기 — 유형(훅) × 흐름(칸 순서) (2026-09-19 사장님
# "터진 체널과 대본들을 수집해서 누가봐도 안정적으로 잘썼다는 대본" / "새로운 유형이 있다면 꼭 담고").
# 사용(서버):  python3 classify_hits.py corpus.json out.json [--min-views 100000] [--always maison_homedino]
#   corpus.json = [{id,user,views,platform,text,title?}]  (만드는 법은 handoff/장면분량.md 09-19)
# 유형은 기존 15종 중 하나, 안 맞으면 "새유형:<이름>" — 억지로 끼우지 않게 한다(새 유형 발굴이 목적).
import json, sys, time
sys.path.insert(0, "/tmp/ab")
from shopping_shorts import script_generate as sg

TYPES = {
    "오용형": "원래 용도와 다르게 쓰는 법(개발자도 놀란 활용법)",
    "제품정체형": "'이게 뭘까? 정체는 바로 OO' — 정체를 숨겼다 공개",
    "발명품형": "천재·개발자·전문가가 만든 발명품이라 난리",
    "지인증언형": "와이프·친구·엄마 등 가까운 사람이 보여줌/반응(소리질렀어요·혼났어요)",
    "권유지시형": "무조건 이렇게 하세요(레시피·사용법 지시)",
    "물건발견형": "우연히 발견한 물건 소개",
    "금지경고형": "~하지 마세요 / ~챙기지 마세요",
    "사회증거형": "요즘 ~사이에서 유행·난리",
    "정체의문형": "이게 뭔지 아세요? 질문으로 시작",
    "무지후회형": "이걸 이제 알았다 / 모르면 손해",
    "목격담형": "어디서 보고 충격받았다",
    "가성비형": "단돈 OO원 / 가격 대비",
    "만능템형": "이거 하나면 다 된다",
    "다이소지목형": "여러분 다이소(코스트코) 가면 이거 꼭 사오세요",
    "내자랑형": "내가 샀더니/만들어줬더니 다들 물어본다",
}
ROLES = ["훅", "계기(누구와·어디서)", "기존불편", "전환('근데 이건')", "작동·해결", "추가장점('심지어')",
         "유래·권위", "사회증거", "결과·감정", "CTA"]
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "type": {"type": "string"}, "new_type_why": {"type": "string"},
    "hook": {"type": "string"}, "flow": {"type": "array", "items": {"type": "string", "enum": ROLES}},
    "tone": {"type": "string", "enum": ["반말", "존댓말", "섞임"]},
    "strength": {"type": "string"}}, "required": ["id", "type", "hook", "flow", "tone"]}}}, "required": ["items"]}


def prompt(batch):
    types = "\n".join("- %s: %s" % kv for kv in TYPES.items())
    body = "\n\n".join("[%s] %s" % (x["id"], x["text"][:600]) for x in batch)
    return f"""아래는 조회수가 터진 쇼핑 숏폼 대본들이다. 각 대본을 분류하라.

유형(첫 문장=훅이 어떻게 여는가) — 아래 중 하나. **억지로 끼우지 마라.** 어느 것과도 여는 방식이 다르면
"새유형:<짧은 이름>"으로 쓰고 new_type_why에 기존과 뭐가 다른지 한 줄로 적어라.
{types}

hook = 대본의 첫 문장 그대로(고치지 말 것).
flow = 대본이 실제로 말하는 순서대로 칸 이름을 나열(같은 칸 반복 가능). 칸: {", ".join(ROLES)}
tone = 말투. strength = 이 대본이 잘 쓴 이유 한 줄(구체적으로: 어떤 말이 끌어당기나).

{body}"""


def main():
    src, dst = sys.argv[1], sys.argv[2]
    mv = 100000
    always = set()
    a = sys.argv[3:]
    for i, x in enumerate(a):
        if x == "--min-views":
            mv = int(a[i + 1])
        if x == "--always":
            always = set(a[i + 1].split(","))
    C = [x for x in json.load(open(src, encoding="utf-8")) if (x.get("views") or 0) >= mv or x.get("user") in always]
    try:
        done = {r["id"]: r for r in json.load(open(dst, encoding="utf-8"))}
    except Exception:      # noqa: BLE001
        done = {}
    todo = [x for x in C if x["id"] not in done]
    print("대상 %d · 이미 %d · 남음 %d" % (len(C), len(done), len(todo)), flush=True)
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        note = {}
        out = sg._call_json(prompt(batch), SCHEMA, note=note) or {}
        got = {str(r.get("id")): r for r in out.get("items") or []}
        for x in batch:
            r = got.get(x["id"])
            if r:
                done[x["id"]] = dict(x, **{k: r.get(k) for k in ("type", "new_type_why", "hook", "flow", "tone", "strength")})
        json.dump(list(done.values()), open(dst, "w", encoding="utf-8"), ensure_ascii=False)
        print("%d/%d 받음 %d %s" % (i + len(batch), len(todo), len(got), note.get("reason") or ""), flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
