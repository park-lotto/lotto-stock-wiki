# -*- coding: utf-8 -*-
"""방구석 계열 썰 갈래(숨은 이유·원리·대체) 대본 시험대 — 지금 엔진과 같은 깔때기(script_generate._call_json, Vertex 먼저)로 쓴다.

서버에서(핫패치 금지 — /tmp 에 올려 실행, 서비스 환경을 실어야 Vertex 스위치가 실제와 같다):
  scp try_banggu_styles.py ubuntu@…:/tmp/ ; scp ../../../tools/seed_analyzer/cases.py …:/tmp/
  set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && python3 /tmp/try_banggu_styles.py --out /tmp/banggu_try.json

두 가지를 같은 씨앗·재료로 잰다:
  T1 지금 길   story_writer.write(style=새 갈래의 제목 각도·흐름) — 스타일만 얹으면 몸통이 바뀌는가
  T2 전용 칸   갈래 전용 칸(schema)+지침으로 같은 깔때기 호출 — 어색한 곳·지어낸 곳이 어디인가
검사(코드): 평서 종결(~다/~요) · 보는 사람에게 거는 말 · 권하는 말 · 재료에 없는 숫자 · 글자 수 · 모델이 '재료 없음'이라 신고한 칸.
★어색함·지어냄의 최종 판정은 사람이 읽고 한다 — 이 검사는 거르는 그물일 뿐이다.
"""
import argparse, json, re, sys

sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.append("/tmp")      # ★맨 뒤에 — 앞에 두면 /tmp 의 남의 스크립트가 라이브러리 이름을 가린다(2026-10-06: /tmp/h2.py 가 httpx 의 h2 대신 불려 실행됨)
from cases import CASES  # noqa: E402

CASES = dict(CASES)
CASES["두피앰플빗"] = {
    "product": "두피 앰플 빗",
    "seed": ("두피 에센스 손에 다 묻고 머리만 떡져서 빡쳤던 분들 이거 보세요. 빗 뒷면에 앰플을 그냥 부어 넣으면 되고 "
             "빗질할 때마다 롤러볼이 굴러가면서 머리카락 사이사이로 쏙쏙 들어가요. 손에는 하나도 안 묻고 두피에만 발라지는데 "
             "빗질하면서 마사지까지 되니까 저녁마다 이것만 쓰게 되더라고요."),
    "feats": [
        {"name": "앰플 충전", "claim": "빗 뒷면 덮개를 열어 앰플을 부어 넣는다", "pain": "튜브를 손에 짜서 바르다 손가락 사이로 흘러내리고 머리만 떡짐"},
        {"name": "균일 도포", "claim": "빗살과 롤러볼이 머리카락 사이로 앰플을 밀어 넣는다", "pain": "손으로는 한쪽만 뭉치고 정작 두피엔 안 닿음"},
        {"name": "손 안 묻음", "claim": "손에 묻히지 않고 두피에만 발린다", "pain": "바르고 나면 손 씻으러 가야 하고 끈적임이 남음"},
        {"name": "두피 마사지", "claim": "빗질하면서 두피 마사지가 된다", "pain": "따로 마사지기를 또 사서 써야 했음"},
    ],
}

COMMON = """■ 이번 대본 스타일 = **커뮤니티 썰(전해 듣는 말)**. 게시글을 읽어 주듯, 남에게 들은 이야기를 옮기는 말투다.

■ 말투 (방구석·선물가게 39편 실측)
- 화자는 써 본 사람이 아니다. 전부 **전해 듣는 말**로 쓴다: ~다는 · ~라는데 · ~다고 함 · ~다고
- 문장 끝은 이 중에서만: **~는데**(다음 줄로 넘김) · **~다고 / ~다고 함**(닫음) · **~는 거** · **~음 / ~됨** · 명사로 끝
  ★ "~다." "~요." "~습니다" 로 끝나는 줄은 한 줄도 쓰지 마라(실측 81문장 중 0).
- 움직이는 주체는 "사람들이" 또는 **별명 붙은 무리**(빵돌이들 · 러너들 · 살림 고수들 · 맛잘알들). '나'·'여러분'은 쓰지 않는다.
- 보는 사람에게 말 걸지 마라. 사라·써 보라·구독·댓글 같은 권하는 말 0.
- 한 줄은 8~18자 두 토막쯤(자막 두 줄). 설명서 문장("A 기능이 있어 편리함")은 쓰지 마라.

■ 재료 밖 사실을 지어내지 마라
- 나라·회사·상표·가격·수치·"품절"·"1위"는 **씨앗이나 재료에 나온 것만** 쓴다.
- 이 갈래의 본체 칸(아래 ★)에 쓸 재료가 없으면 억지로 채우지 말고, 그 칸을 빈칸("")으로 두고 `missing`에 무엇이 없는지 적어라.
- 씨앗의 말투·문장을 베끼지 마라. 내용만 가져와 이 말투로 새로 쓴다.

■ 분량: 공백 빼고 170~240자.
"""

STYLES = {
    "숨은이유": {
        "name": "커뮤니티 썰 「사는 이유는 따로 있다는데」",
        "hook_angle": "제품명으로 끝나는 짧은 제목 — 「{권위·화제}가 ~다는 {제품}의 정체」「{분야}계의 1황」 꼴. 16자 안팎, 명사로 끝낸다",
        "flow": "제목 → 소개(남들이 이미 좋아한다는 수식+제품, 명사로 끝) → 의문(사는 이유는 단순히 OO 때문이 아니라는데) → 살펴봄(기능 둘) → 한 번 더 꺾음(정작 꽂힌 포인트는 따로 있다는데 그건 바로) → 진짜 이유 → 전해 듣는 말로 닫음",
        "brief": """■ 갈래 = 숨은 이유형 — "사람들이 이걸 사는 진짜 이유는 겉보기와 다르다"
칸:
  title    제목(읽어 줌). 제품명으로 끝나는 명사구, 12~20자
  intro    남들이 이미 좋아한다는 수식 + 제품. **명사로 끝**  예) 코스트코에 가면 꼭 사야한다는 EMMI 티라미수
  doubt  ★"하지만 사람들이 이걸 사는 이유는 단순히 {겉 이유} 때문이 아니라는데" — 겉 이유 = 누구나 그것 때문에 산다고 여기는 것
  look     "{부위·구성}을 살펴보니" 로 열고 특징 1~2개. 2~3줄, 끝은 ~고 / ~다고 함
  turn   ★"그러나 정작 {무리}가 꽂힌 포인트는 따로 있다는데" — 무리는 재료·씨앗에 나온 사람들만
  real   ★"그건 바로 {진짜 이유}" 1~2줄, 끝은 "~해서라고" 또는 "~다고"
  comment  끝에 말투를 바꾼 혼잣말 한 줄(선택, 없으면 "") 예) 아 이걸 어떻게 참냐고 ㅋㅋ
모양 예시(문장을 흉내 내지 말고 모양만):
  마케팅 천재가 만들었다는 티라미수 / 코스트코에 가면 꼭 사야한다는 EMMI 티라미수 / 하지만 사람들이 이걸 구매하는 이유는 단순히 맛 때문이 아니라는데 /
  패키지를 살펴보니 특이하게도 플라스틱이 아닌 유리컵에 담겨있고 / 문제는 바로 이 컵에 있었음 / 고작 서비스 유리컵이면서 식세기도 견뎌내는 단단한 내구성에 온 집안 물컵을 이걸로 바꾸는 사람도 있다고 함""",
        "keys": ["title", "intro", "doubt", "look", "turn", "real", "comment"],
        "labels": ["제목", "소개", "의문", "살펴봄", "꺾음", "진짜이유", "댓글"],
    },
    "원리": {
        "name": "커뮤니티 썰 「어떻게 그게 되냐는 거」",
        "hook_angle": "겉보기에 말이 안 되는 점을 단 제품명 — 「물감을 전혀 묻힐 수 없는 붓」「{분야}시장 씹어먹은 {제품}」 꼴. 명사로 끝낸다",
        "flow": "제목 → 의문(이걸 본 사람들이 놀란 부분이 있는데 / 바로 어떻게 ~냐는 거) → 기존 방식과 단점(사실 보통 OO은 ~방식인데) → 이 제품의 방식(하지만 이건 ~) → 덤(심지어) → 전해 듣는 말로 닫음",
        "brief": """■ 갈래 = 원리형 — "어떻게 그게 되지?"를 묻고 원리로 푼다
칸:
  title    제목. 겉보기에 말이 안 되는 점 + 제품명, 명사로 끝, 12~20자
  wonder ★"이 {제품군}을 본 사람들이 놀란 부분이 있는데" + "바로 {어떻게 ~할 수가 있냐}는 거" 2줄
  old    ★"사실 보통 {제품군}은 {기존 방식}~인데 {단점}~단점이 있었음" — 기존 방식·단점은 재료의 '이게 없을 때'에서만
  how    ★"하지만 이건 {어떻게 되는지}~라 {효과}~다는 거" 2~3줄 — 재료에 나온 작동 방식만
  bonus    "심지어 {다른 장점 하나}~다고" 1~2줄
  comment  혼잣말 한 줄(선택)
모양 예시(모양만):
  러닝시장을 씹어먹어버린 오픈형 이어폰 / 최근에 이 이어폰을 본 사람들이 놀란 부분이 있는데 / 바로 착용한 느낌도 안 드는데 어떻게 귀에서 안 떨어질 수가 있냐는 거 /
  사실 오픈형 이어폰은 귀를 압박해 고정되는 방식인데 이런 방식 때문에 장시간 착용이 힘들다는 단점이 있었음 / 하지만 이건 특수 실리콘 패드와 휘어지는 본체 설계로 압박 없이도 떨어지지 않는 이어폰을 만들어냈다는 거 /
  심지어 월등히 저렴한 가격 때문에 부담 없이 쓸 수 있어서라고""",
        "keys": ["title", "wonder", "old", "how", "bonus", "comment"],
        "labels": ["제목", "의문", "기존", "원리", "덤", "댓글"],
    },
    "대체": {
        "name": "커뮤니티 썰 「OO에 갈 이유가 없어져버렸다고」",
        "hook_angle": "누구나 아는 비싼 원조가 당했다는 각도 — 「영업기밀을 빼앗겨버린 {원조}」「결국 해킹당해버린 {원조}」 꼴",
        "flow": "제목 → 원조 소개(명사로 끝) → 원조의 아쉬운 점(값·구하기 어려움) → 포기 못 한 무리가 찾아냄 → 같다는 근거 → 값 이득·원조에 갈 이유가 없어졌다고",
        "brief": """■ 갈래 = 대체형 — "비싼 원조 대신 이걸 찾아냈다"
★원조 = 이 제품이 **대신하는 것**(업체 시공·전문가 서비스·비싼 기존 제품). 씨앗·재료에 그런 비교 대상이 없으면 이 갈래는 못 쓴다 — 전부 빈칸으로 두고 missing에 "원조 없음"이라고 적어라. 원조를 지어내지 마라.
칸:
  title    제목. 원조가 당했다는 꼴, 명사로 끝
  origin   원조 소개 — 사람들이 원래 무엇에 돈·수고를 들였나. 명사로 끝
  lack   ★원조의 아쉬운 점 — "~는데"로 끝. 값이면 재료에 나온 값만
  crowd  ★"그럼에도 포기 못 한 {별명 붙은 무리}은 … 끝에 이걸 발견해버렸는데"
  proof    같다는(충분하다는) 근거 1~2줄 — 재료에 나온 것만, 끝은 ~다고 함
  payoff   "무엇보다 {이득}~라 {원조}를 부를(살) 이유가 없어져버렸다고"
  comment  혼잣말 한 줄(선택)
모양 예시(모양만):
  결국 해킹당해버린 비요뜨 / 비요뜨 먹을 때마다 항상 모자란 초코링 / 하지만 초코링은 독일 수입 제품이라는 답을 하자 똑같은 초코링을 구할 방법이 없게 되었음 /
  그럼에도 포기 못한 맛잘알 코난들은 수많은 시행착오 끝에 2가지 초코링을 발견해버렸는데 / 두 제품 모두 육안으로는 거의 동일하고 맛에도 거의 차이가 없다고 함 / 무엇보다 대용량 하나 사두면 훨씬 이득이라고""",
        "keys": ["title", "origin", "lack", "crowd", "proof", "payoff", "comment"],
        "labels": ["제목", "원조", "아쉬움", "무리", "근거", "끝", "댓글"],
    },
}

_FLAT = re.compile(r"(다|요|니다)[.!]?$")
_OKEND = re.compile(r"(다고|라고|냐고|다고 함|는데|은데|인데|건데|는 거|던 거|음|됨|함)\s*(ㅋㅋ|ㄷㄷ)?\s*[.?!]*$")
_YOU = re.compile(r"여러분|당신|님들|보세요|해봐|써봐|있지\?|알지\?")
_CTA = re.compile(r"구독|좋아요|댓글|링크|구매하|사세요|추천드|강추")


def schema_for(st):
    props = {k: ({"type": "array", "items": {"type": "string"}} if k in ("look", "how", "proof", "wonder") else {"type": "string"}) for k in st["keys"]}
    props["missing"] = {"type": "string"}
    return {"type": "object", "properties": props, "required": st["keys"] + ["missing"]}


def feats_block(feats):
    rows = []
    for i, f in enumerate(feats):
        rows.append("%d. %s — %s" % (i + 1, f["name"], f["claim"]))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    return "\n".join(rows)


def audit(lines, case):
    src = case["seed"] + " " + " ".join(f["claim"] + " " + (f.get("pain") or "") for f in case["feats"])
    txt = " ".join(t for _, t in lines)
    body = [t for lab, t in lines if lab not in ("제목", "댓글")]
    nums = [n for n in re.findall(r"\d+", txt) if n not in re.findall(r"\d+", src)]
    return {"글자": len(re.sub(r"\s", "", txt)),
            "평서종결": [t for t in body if _FLAT.search(t.strip()) and not _OKEND.search(t.strip())],
            "말걸기": [t for t in body if _YOU.search(t)], "권하는말": [t for t in body if _CTA.search(t)],
            "재료에없는숫자": nums}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="/tmp/banggu_try.json"); ap.add_argument("--only", default="")
    a = ap.parse_args()
    from shopping_shorts import script_generate as _sg, story_writer as sw, usage_meter, vertex_route
    res = []
    with usage_meter.track(op="대본시험", customer_id=0):          # 관리자(사장님) 문맥 — Vertex 스위치가 관리자에게 켜져 있다
        print("vertex on(script_generate)=", vertex_route.on("script_generate"), "model=", vertex_route.model())
        for cname, c in CASES.items():
            if a.only and a.only not in cname:
                continue
            # T1 — 지금 길에 스타일만 얹는다(숨은 이유형)
            st = STYLES["숨은이유"]; note = {}
            lines = sw.write(c["product"], c["seed"], c["feats"], platform="yt",
                             style={"name": st["name"], "hook_angle": st["hook_angle"], "flow": st["flow"], "extra": ""},
                             key=cname, note=note, preset="short") or []
            row = {"case": cname, "test": "T1 지금 길+스타일(숨은이유)", "auth": note.get("auth"), "note": {k: v for k, v in note.items() if k != "auth"},
                   "lines": [(l.get("role"), l.get("text")) for l in lines]}
            row["audit"] = audit(row["lines"], c); res.append(row)
            print("\n=== %s · %s · auth=%s ===" % (cname, row["test"], row["auth"]))
            for lab, t in row["lines"]:
                print("  [%s] %s" % (lab, t))
            print("  검사:", json.dumps(row["audit"], ensure_ascii=False))
            # T2 — 갈래 전용 칸
            for sname, st in STYLES.items():
                note = {}
                prompt = "%s\n%s\n\n[제품] %s\n\n[씨앗 — 이 제품으로 터진 영상의 말]\n%s\n\n[재료]\n%s" % (
                    COMMON, st["brief"], c["product"], c["seed"], feats_block(c["feats"]))
                out = _sg._call_json(prompt, schema_for(st), note=note) or {}
                lines = []
                for k, lab in zip(st["keys"], st["labels"]):
                    v = out.get(k)
                    for t in (v if isinstance(v, list) else [v]):
                        if (t or "").strip():
                            lines.append((lab, t.strip()))
                row = {"case": cname, "test": "T2 전용 칸(%s)" % sname, "auth": note.get("auth"), "missing": out.get("missing") or "", "lines": lines}
                row["audit"] = audit(lines, c); res.append(row)
                print("\n=== %s · %s · auth=%s ===" % (cname, row["test"], row["auth"]))
                for lab, t in lines:
                    print("  [%s] %s" % (lab, t))
                print("  재료 없음 신고:", row["missing"] or "-")
                print("  검사:", json.dumps(row["audit"], ensure_ascii=False))
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
