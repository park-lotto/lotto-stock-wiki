"""스타일 설명서 2차 판 — cards/(1차) → cards_v2/
사장님 결정(2026-10-19): 67·68·69 삭제 / 55+65+74+75+76 → 정체숨김 / 56+70+71+72+73 → 오용활용법 / 나머지 13개 유지.
1차 판 결함 7가지(첫 줄 약함·'논란'·사실 지어냄 vs 분위기 과장·고정 약한 마무리·한 줄 두 셀링·예문 베끼기·CTA 두 번/잔재)를 전 카드에 반영.
사용: py build_v2.py → cards_v2/*.json + *.md"""
import copy, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(HERE, "..", "cards")


def load(prefix):
    return json.load(open(glob.glob(os.path.join(V1, prefix + "*.json"))[0], encoding="utf-8"))


def nospace(t):
    return re.sub(r"\s", "", t or "")


# ── 공통 규칙(전 카드 앞머리에 들어간다) ─────────────────────────────
FIRST_LINE = {
    "formula": "첫 줄 = [구체 불편·장면 또는 평범한 겉모습] + [놀라운 점·큰 반응] — 두 덩어리가 **둘 다** 있어야 한다(노바 엥포인트: 평범한 대상인데 예상 밖 성질/결과라고?!)",
    "length": "길이 상한 없음. 짧게 줄이려고 불편 장면을 빼지 마라(1차 판 11~17자 제한이 첫 줄을 '자취생 환장한 천재의 발명품'처럼 흔하게 만들었다).",
    "slot_fill": "근거에 없는 {나라}·{판매처}·{회사}·{인물}·{직책} 슬롯은 **빼고 끝내지 말고 불편 장면으로 바꿔 채운다** — 예: '{나라} 천재' → '집 안 훤히 들여다보여 빡친 사람들'.",
    "question": "질문형 첫 줄은 'X인데 [놀라운 점]이라고요?' 꼴 — 놀라운 점 없는 'X라고요?'는 금지.",
    "strong_examples(구조만, 다른 제품)": [
        "아침마다 알람 끄고 다시 자던 애들 깨우다 현타 온 엄마들 환장하게 만든 발명품  ← 불편 장면 + 큰 반응",
        "딱 봤을 땐 그냥 휴대폰 케이스처럼 생긴 이게 SNS에서 난리가 났다는데  ← 평범한 겉모습 + 반전 예고",
        "그냥 수건인데 머리 감고 두르기만 하면 5분 만에 다 마른다고요?  ← 평범한 대상 + 놀라운 점(숫자는 근거 있을 때만)",
    ],
    "weak_examples(이렇게 쓰지 마라)": [
        "자취생 환장한 천재의 발명품  ← 불편 장면 없음",
        "주부들 기립박수 치게 만든 제품  ← 흔한 말뿐",
        "이게 랩이라고요?  ← 놀라운 점 없음",
    ],
}
FACT_VS_MOOD = {
    "allowed_mood(분위기 과장 — 권장)": ["환장", "떼돈", "돈방석", "난리", "판도가 뒤집혔다", "품절 대란", "입소문이 터졌다", "생지옥", "미쳤다", "기립박수"],
    "forbidden_facts(사실 지어냄 — 근거 번호 없으면 0)": ["나라(미국·한국·일본…)", "회사·브랜드·매장 권위(이케아도·다이소도·코스트코 직원도 — 판매처가 근거에 있어도 '직원/본사/디자이너가 ~했다'는 주장은 근거 필요)",
                                                   "인물·직책의 실제 행동", "숫자·시간(10분 만에·3초·수백만)", "인증·특허·수상", "의학 효능"],
    "rule": "분위기 과장은 세게 써라. 사실 지어냄만 0으로. 근거 판정은 사실 지어냄만 센다.",
}
BANNED_WORDS = {"논란": "제품을 깎는 말 — '난리'·'입소문'으로", "진짜 물건이라고": "고정된 약한 마무리", "완벽하다고": "고정된 약한 마무리",
                "이러니 난리가 날 만하다고": "고정된 약한 마무리"}
LINE_RULE = "한 줄 = 한 장면·셀링 하나. 셀링 두 개를 한 줄에 몰지 마라(…하거나 …해도 완벽하다는 거 ✗). 가장 센 장면은 아껴 둔 자리에서 단독 한 줄."
LANDING = "마무리는 이 제품이 바꾼 결과를 **크게 과장한 한 줄**(분위기 과장 허용). 고정 문구(진짜 물건이라고·완벽하다고·난리가 날 만하다고) 금지."
COPY_RULE = ("참고 대본·예문·틀 문장과 **공백 뺀 7자 이상 같은 구절 0**. 틀은 문장이 아니라 칸 구조다 — 단어를 이 제품의 말로 새로 고른다. "
             "참고 대본은 줄별 뼈대([글자 수] …끝말)로만 실었다: 호흡·끝말만 본뜬다.")
CTA_RULE = "댓글 유도는 **마지막 칸 한 번만**. 중간 칸에서 '댓글'·'남겨주시면'·'보내드릴게요'를 쓰지 마라."
COMMON_CHECKS = ["첫 줄에 [구체 불편·장면/평범한 겉모습]과 [놀라운 점·큰 반응]이 둘 다 있나", "'논란' 0", "근거 없는 나라·회사·인물·숫자·시간·판매처 권위 0",
                 "분위기 과장이 빠져 밋밋해지지 않았나(마무리 포함)", "한 줄에 셀링 하나", "참고 대본·틀과 7자 이상 같은 구절 0", "고정 약한 마무리 0"]


def skeleton(text):
    """참고 대본 원문 → 줄별 뼈대([칸] [글자 수] …끝말 2어절). 베끼기를 막고 호흡·끝말만 남긴다."""
    parts = [p.strip() for p in re.split(r"\s*/\s*|(?<=[.?!])\s+", text or "") if p.strip()]
    out = []
    for p in parts:
        tag = ""
        m = re.match(r"^(\[[^\]]+\])\s*(.*)$", p)
        if m:
            tag, p = m.group(1) + " ", m.group(2)
        w = p.split()
        tail = " ".join(w[-2:]) if len(w) >= 2 else p
        out.append("%s[%d자] …%s" % (tag, len(nospace(p)), tail))
    return " / ".join(out)


def scrub(o):
    """문자열 전체 치환 — '논란' 틀 제거, 고정 마무리 제거."""
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    if isinstance(o, str):
        s = o
        for a, b in [("바이럴이 터지며 논란인", "바이럴이 터지며 난리 난"), ("논란이 되고 있는", "난리 난"), ("논란인", "난리 난"), ("논란 끝에", "입소문 끝에"),
                     ("논란", "화제"), (" / 진짜 물건이라고", ""), ("진짜 물건이라고 / ", ""), ("진짜 물건이라고", "{이 제품이 바꾼 결과를 크게 과장}다고"),
                     (" / 완벽하다고", ""), ("이러니 난리가 날 만하다고", "이러니 {결과 과장}다고")]:
            s = s.replace(a, b)
        return s
    return o


def finish(card, platform_ig=False, notes=()):
    c = scrub(copy.deepcopy(card))
    for t in c.get("title_molds", []):           # 길이 상한 제거
        t.pop("len", None)
    if isinstance(c.get("title_rules"), dict):
        c["title_rules"].pop("len", None)
    for s in c.get("slots", []):
        if s.get("key") in ("title", "hook") or s.get("name", "").startswith(("제목", "훅")):
            s["len"] = "상한 없음 — 첫 줄 공식(두 덩어리)"
    for r in c.get("refs", []):                   # 예문 베끼기 방지
        if r.get("text"):
            r["text"] = skeleton(r["text"])
    c["first_line"] = FIRST_LINE
    c["fact_vs_mood"] = FACT_VS_MOOD
    c["banned_words"] = BANNED_WORDS
    c["line_rule"] = LINE_RULE
    c["landing"] = LANDING
    c["copy_rule"] = COPY_RULE
    if platform_ig:
        c["cta_rule"] = CTA_RULE
    c["checks"] = list(COMMON_CHECKS) + [x for x in (c.get("checks") or []) if isinstance(x, str)] if isinstance(c.get("checks"), list) else list(COMMON_CHECKS) + [c.get("checks")]
    c["v2_notes"] = list(notes)
    return c


# ── 통합 1: 정체 숨김 (55+65+74+75+76) ──────────────────────────────
def build_jungche():
    b = load("55_")
    c = copy.deepcopy(b)
    c.update(id="정체숨김", name="유튜브 「정체 숨김」(이건 바로 OO 계열 통합)",
             role="정체 숨김극 — 정체를 감춘 채 불편 장면·소문으로 끌고 가다 중반에 '이건 바로'로 갚고 효능 2단 고조, 마지막에 가장 센 장면. "
                  "통합 전 55·65·74·75·76은 라이브에서 같은 프롬프트였고(A 결과 동일), 1차 판 별도 카드도 같은 뼈대로 나왔다 → 한 스타일 안에서 후킹 유형을 돌린다.",
             merged_from=[55, 65, 74, 75, 76])
    c["title_molds"] = [
        {"no": "T1", "mold": "{불편 장면}에 빡친 {대상} 환장하게 만든 천재의 발명품", "source": "라이브 A 첫 줄(사장님 선택) · 55"},
        {"no": "T2", "mold": "{불편 장면}에 빡친 {대상} 구원한 천재의 발명품", "source": "75"},
        {"no": "T3", "mold": "딱 봤을 땐 {흔한 겉모습}인데 {대상}이 환장한 {제품군}의 정체", "source": "55 ③ 겉모습 반전 + 라이브 A 미끼"},
        {"no": "T4", "mold": "{대상}이 유독 많이 쓰는 {흔한 겉모습}의 정체", "source": "74 T1"},
        {"no": "T5", "mold": "{불편 장면} 싫은 {대상}이 찾아낸 기가 막힌 해답", "source": "76 T1"},
        {"no": "T6", "mold": "{나라} 천재가 만들어 떼돈 번 {제품군}의 정체", "source": "55 T1 — {나라}가 근거에 있을 때만, 없으면 T1·T2로"},
        {"no": "T7", "mold": "역발상으로 돈방석 앉은 {불편 장면} 천재의 발명품", "source": "55 T5"},
        {"no": "T8", "mold": "{권위자}도 당황한 {불편 장면} 해결템", "source": "65 — 권위자는 근거에 있는 판매처·제조사만, 없으면 '만든 사람도'"},
    ]
    c["hook_types"] = [
        {"key": "성과", "name": "① 성과형", "when": "개발자·나라·특허 근거가 있을 때(없으면 이 유형을 고르지 마라)", "titles": ["T6", "T7"],
         "line_mold": "{불편}에 빡쳐서 만든 이 물건 하나로 만든 사람이 돈방석에 앉았다는데(사실 슬롯은 근거)"},
        {"key": "집단환장", "name": "② 집단 환장형", "when": "특정 집단의 불편이 화면에 뚜렷할 때", "titles": ["T1", "T4"],
         "line_mold": "{구체 불편 장면}에 스트레스받던 {대상} 사이에서 이게 난리가 났다는데"},
        {"key": "겉모습반전", "name": "③ 겉모습 반전형", "when": "겉보기에 흔한 다른 물건처럼 생겼을 때", "titles": ["T3"],
         "line_mold": "딱 봤을 땐 흔한 {겉모습}처럼 생긴 이게 SNS에서 난리가 났다는데"},
        {"key": "구원해답", "name": "④ 구원·해답형", "when": "불편이 아주 뚜렷하고 대상이 분명할 때", "titles": ["T2", "T5"],
         "line_mold": "{불편} 때문에 생지옥이던 {대상} 사이에서 이게 해답으로 터졌다는데"},
        {"key": "끝까지숨김", "name": "⑤ 끝까지 숨김(65 짧은 판)", "when": "화면이 정체를 다 보여 줄 때 — reveal 칸을 빼고 '이게'로만 부른다(6칸·160~200자)", "titles": ["T8"],
         "line_mold": "요즘 {대상} 사이에서 이게 하나 난리가 났는데 쓰는 방법이 진짜 기상천외하다는데"},
    ]
    c["rotation"] = {"drafts": 2, "rule": "시안 2개는 서로 다른 유형(①은 근거 있을 때만 후보). 같은 고객 연속 생성 시 직전 유형 회피(nth). 이름(55·74·75·76·65)은 유형 이름으로 남는다."}
    for s in c["slots"]:
        if s["key"] == "land":
            s["mold"] = "이러니 {대상}이 환장하고 {결과 과장}다고 — 이 제품이 바꾼 생활을 크게"
            s["does"] = "결과 과장 한 줄로 세게 닫기(CTA 없음)"
        if s["key"] == "bait":
            s["does"] = "엥포인트 — 평범한 겉모습 또는 구체 불편 장면 + '그게 난리' 예고, 끝은 ~다는데"
        if s["key"] == "fame":
            s["mold"] = "이걸 만든 천재가 돈방석에 앉았다는 소문까지 돌았다는데 / {대상} 입소문으로 판도가 뒤집혔다는데(분위기 과장 허용, 나라는 근거)"
    c["length"] = dict(b["length"], note="⑤ 끝까지 숨김은 160~200자 짧은 판")
    c.pop("variant_of", None); c.pop("variant_notes", None)
    refs = []
    for p in ["55_", "75_", "65_"]:
        refs += load(p).get("refs", [])[:2]
    c["refs"] = refs
    return finish(c, notes=["55·65·74·75·76 통합", "첫 줄 T1 = 라이브 A(사장님 선택) 꼴", "마무리 '진짜 물건이라고' 제거", "'논란' 제거"])


# ── 통합 2: 오용·활용법 (56+70+71+72+73) ────────────────────────────
def build_oyong():
    b = load("56_")
    c = copy.deepcopy(b)
    c.update(id="오용활용법", name="유튜브 「오용·활용법」(원래 이렇게 쓰는 거 아닌데 계열 통합)",
             role="오용 반전극 — 정체는 처음부터 밝히고, '원래 용도'와 '사람들이 찾아낸 엉뚱한 쓰임' 사이의 간극으로 붙잡는다. "
                  "통합 전 56·70·71·72·73은 라이브에서 같은 프롬프트였고(A 결과 동일), 1차 판 별도 카드는 다섯 편 모두 같은 '초보→중수' 사다리로 나왔다 → 첫 줄 유형과 몸통을 따로 돌린다.",
             merged_from=[56, 70, 71, 72, 73])
    c["title_molds"] = [
        {"no": "M1", "mold": "{판매처}도 예상 못한 {불편 장면} 해결 미친 활용법", "source": "70 — 판매처는 근거에 있을 때만, 없으면 '만든 사람도'"},
        {"no": "M2", "mold": "만든 사람도 예상 못한 {흔한 물건}의 미친 활용법", "source": "56 M8"},
        {"no": "M3", "mold": "{본래 용도}용으로 팔다가 {새 용도}템 돼 버린 {흔한 물건}", "source": "71 X11"},
        {"no": "M4", "mold": "만든 사람 의도랑 정반대로 팔리는 {흔한 물건}", "source": "71 X12"},
        {"no": "M5", "mold": "{판매처}가 계산 못 한 {흔한 물건}의 진짜 쓰임", "source": "71 X13 — 판매처 근거"},
        {"no": "M6", "mold": "아는 사람만 몰래 쓴다는 {흔한 물건}의 진짜 용도", "source": "72 S6(직원 근거 없을 때 기본)"},
        {"no": "M7", "mold": "{집단} 덕후들이 찾아낸 {흔한 물건}의 천재적인 활용법", "source": "56 M4"},
        {"no": "M8", "mold": "{판매처}도 감탄한 {흔한 물건}의 뜻밖의 활용법", "source": "73 G7 — 판매처 근거"},
    ]
    c["hook_types"] = [
        {"key": "권위자부정", "name": "① 권위자 부정", "when": "판매처·제조사가 근거에 있을 때(없으면 '만든 사람도')", "titles": ["M1", "M2", "M5"],
         "line_mold": "만든 사람도 예상 못한 {흔한 물건}의 미친 활용법"},
        {"key": "실수", "name": "② 용도 뒤집힘(실수)", "when": "본래 용도와 새 용도가 정반대일 때", "titles": ["M3", "M4"],
         "line_mold": "{본래 용도}하라고 만든 건데 사람들이 {새 용도}로 쓰기 시작했다는데"},
        {"key": "몰래", "name": "③ 아는 사람만 몰래", "when": "기본은 '아는 사람만' — '직원·전문가가 쓴다'는 근거(후기·영상)가 있을 때만 '{판매처} 직원도 몰래'", "titles": ["M6"],
         "line_mold": "아는 사람들만 몰래 쓰고 있었다는 {흔한 물건}의 진짜 용도가 있는데"},
        {"key": "감탄", "name": "④ 덕후 감탄", "when": "쓰는 집단(살림·캠핑·육아)이 화면에 뚜렷할 때", "titles": ["M7", "M8"],
         "line_mold": "요즘 {집단} 덕후들 사이에서 {흔한 물건} 하나로 난리가 났는데"},
    ]
    c["bodies"] = [
        {"key": "L", "name": "고수 사다리", "rule": "초보(약한 쓰임) → 중수(센 쓰임) → '근데 진짜 미친 사용법은 따로 있었는데'(가장 센 쓰임). ★가장 센 장면(예: 거꾸로 뒤집어도 안 쏟아짐)을 초보 칸에 두지 마라 — 최강 카드는 항상 마지막."},
        {"key": "N", "name": "빠른 나열", "rule": "'{쓰임1}로 쓰는 건 기본이고 / 심지어 {쓰임2}까지 / 근데 진짜 미친 사용법은 {쓰임3}' — 사다리 단어(초보·중수) 없이 속도로."},
        {"key": "O", "name": "한 방", "rule": "한 사람이 이걸 엉뚱한 곳에 써 버리면서 화제가 된 장면 하나를 길게(순간 → 벌어진 일 → 반응) 풀고 마지막에 최강 쓰임 한 줄."},
    ]
    c["rotation"] = {"drafts": 2, "rule": "시안 2개는 첫 줄 유형도 몸통도 서로 다르게(예: ①+L / ③+N). 같은 고객 연속 생성 시 직전 조합 회피. 70~73 이름은 첫 줄 유형 이름으로 남는다."}
    for s in c["slots"]:
        if s["key"] == "bait":
            s["mold"] = "요즘 {집단} 사이에서 {흔한 물건} 하나로 난리가 났는데(엥포인트: 흔한 물건 + 엉뚱한 쓰임 예고)"
        if s["key"] == "cases":
            s["mold"] = "몸통(bodies) L/N/O 에 따라 — 가장 약한 쓰임부터"
        if s["key"] == "escalation":
            s["mold"] = "L: 그나마 중수들은 {쓰임2}까지 해 버리는데 / N·O: 심지어 {쓰임2}로 바꿔 버렸다는 거"
        if s["key"] == "twist":
            s["does"] = "가장 놀라운 쓰임 단독 한 줄 — 화면에서 가장 센 장면"
        if s["key"] == "land":
            s["mold"] = "{결과 한 구절} 이거였네? / 당장 {가까운 사람}한테 알려 줘야겠는데? — 이 제품 말로 새로"
    refs = []
    for p in ["56_", "71_", "72_"]:
        refs += load(p).get("refs", [])[:2]
    c["refs"] = refs
    return finish(c, notes=["56·70·71·72·73 통합", "몸통 L/N/O 분리, 사다리에서 최강 카드 강등 금지", "'논란' 제거", "'직원도 몰래'는 근거 있을 때만"])


def write(card, fname):
    json.dump(card, open(os.path.join(HERE, fname + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines = ["# %s" % card["name"], "", "> 2차 판(cards_v2) · " + " · ".join(card.get("v2_notes") or []), "", "**역할** — %s" % card.get("role", ""), ""]
    def sec(title, v):
        if v in (None, "", [], {}):
            return
        lines.append("## " + title)
        if isinstance(v, str):
            lines.append(v)
        else:
            lines.append("```json\n" + json.dumps(v, ensure_ascii=False, indent=1) + "\n```")
        lines.append("")
    for k, t in [("first_line", "첫 줄 공식(전 스타일 공통)"), ("fact_vs_mood", "사실 지어냄 vs 분위기 과장"), ("principles", "최우선 원칙"), ("materials", "재료 확보"),
                 ("title_molds", "제목 틀 사전"), ("hook_types", "후킹 유형"), ("bodies", "몸통"), ("rotation", "돌림"), ("slots", "칸 배치"),
                 ("social_proof", "사회적 증거 가공 장치"), ("bridges", "연결"), ("tone", "말투"), ("cta", "CTA"), ("cta_rule", "CTA 규칙"), ("length", "길이"),
                 ("line_rule", "한 줄 규칙"), ("landing", "마무리"), ("copy_rule", "베끼기 금지"), ("banned_words", "금지어"), ("checks", "검수"), ("refs", "참고 대본(줄별 뼈대)")]:
        sec(t, card.get(k))
    open(os.path.join(HERE, fname + ".md"), "w", encoding="utf-8").write("\n".join(lines))


def main():
    write(build_jungche(), "정체숨김")
    write(build_oyong(), "오용활용법")
    keep = [("60_", "60_개발자무릎탁", False), ("66_", "66_답답했잖아", False),
            ("52_", "52_가족갈등반전형", True), ("53_", "53_단정명령형", True), ("54_", "54_물건발견형", True), ("58_", "58_금지경고형", True),
            ("59_", "59_사회증거형", True), ("61_", "61_정체의문형", True), ("62_", "62_무지후회형", True),
            ("calcopy_", "이븐쇼핑", False), ("hdn_", "두유노홈디노", True)]
    for pre, out, ig in keep:
        c = load(pre)
        notes = []
        if pre == "53_":
            # 레시피 전용 스타일 — 물건 소재에선 '레시피' 낱말이 잔재로 남았다(1차 B wrap 마지막 줄)
            def derecipe(o):
                if isinstance(o, dict): return {k: derecipe(v) for k, v in o.items()}
                if isinstance(o, list): return [derecipe(v) for v in o]
                if isinstance(o, str): return o.replace("레시피 보내드릴게요", "방법 정리해서 보내드릴게요").replace("레시피 궁금하면", "방법 궁금하면").replace("레시피를 받는 명분", "방법·정보를 받는 명분")
                return o
            c = derecipe(c)
            c["material_note"] = "물건 소재일 땐 '레시피' 낱말을 쓰지 마라 — '방법·정보'로. (라이브는 레시피 전용: backbone_assemble.pick_hook_spine)"
            notes.append("레시피 잔재 제거")
        if pre == "hdn_":
            for t in c.get("title_molds", []):
                if "깜짝 놀라" in t.get("mold", ""):
                    t["mold"] = "{인물}이 {장소}에 해 둔 걸 보고 {주변 사람} 반응이 컸다는 한 사건 — 문장은 이 제품 말로 새로(원본 첫 문장 그대로 금지)"
            for h in c.get("hook_types", []):
                if "깜짝 놀라" in h.get("line_mold", ""):
                    h["line_mold"] = "{인물}이 {장소}에 {제품 동작}해 둔 걸 본 {주변 사람}들 반응 — 새 문장으로"
            c["principles"] = [p.replace("결과 비유 1개 이상(맹물과 원액·편의점 vs 바리스타)", "결과 비유 1개 이상 — 이 제품에서 새로 만든 익숙한 비유(예시 비유 재사용 금지)") for p in c.get("principles", [])]
            c["refs"] = [r for r in c.get("refs", []) if not str(r.get("id", "")).startswith("script_frame#")]   # 원본 첫 문장 인용은 뼈대로 바꿔도 끝말이 그대로 남는다
            notes.append("지인사건 틀을 문장 대신 구조로(1차 B가 원본 첫 문장·'맹물과 원액'을 베낌), 원본 첫 문장 인용 참고 대본 제거")
        if pre == "calcopy_":
            notes.append("'바이럴이 터지며 논란인' → '난리 난'")
        write(finish(c, platform_ig=ig, notes=notes), out)
    print("ok", sorted(f for f in os.listdir(HERE) if f.endswith(".json")))


if __name__ == "__main__":
    main()
