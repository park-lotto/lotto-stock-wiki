"""2차 판 기계 검사 — 사장님이 A 를 고른 이유와 48쌍 직접 판정에서 나온 결함을 잡는다(2026-10-19).
①'논란' ②예문·틀·참고 대본과 7자+ 겹침 ③CTA(댓글) 2회 이상 ④근거에 없는 고유명사·숫자·시간 ⑤고정 약한 마무리
⑥같은 소재에서 스타일끼리 줄 뼈대 유사도(줄 첫 4어절 일치 비율) ⑦첫 줄 판정(버텍스 1회: 구체 불편·장면 / 놀라운 점 → 0~2점)
+ 근거 판정 결과를 사실 지어냄과 분위기 과장으로 나눠 센다.
ab_measure.py --v2 가 이 모듈을 쓴다. 단독으로도 import 해서 쓴다."""
import re

NATIONS = ["일본", "미국", "독일", "중국", "한국", "프랑스", "영국", "스웨덴", "이탈리아", "대만", "해외", "전 세계", "전세계"]
BRANDS = ["코스트코", "다이소", "쿠팡", "이마트", "홈플러스", "올리브영", "아마존", "알리", "테무", "네이버", "이케아", "글래드", "GLAD", "반다이", "나이키", "스타벅스"]
ROLE_CLAIMS = ["직원도", "직원들", "본사", "디자이너", "설계자", "기획자", "약사", "의사", "원장", "전문가들"]
TIME_RE = re.compile(r"\d+\s*(?:분|초|시간|일|년|개월|배|%|만|천|억)|(?:몇|수백|수천|수만|수억)\s*(?:분|초|만|천|억)")
WEAK_ENDINGS = ["진짜 물건이라고", "완벽하다고", "난리가 날 만하다고", "진짜 물건"]
MOOD_WORDS = ["환장", "떼돈", "돈방석", "난리", "판도", "품절", "대란", "입소문", "바이럴", "화제", "인기", "대박", "기립박수", "소문", "열광", "핫한", "유명",
              "사이에서", "주문 폭주", "구원", "천재", "미친", "충격", "역대급"]
SIGNAL_WHITELIST = ["이게말도안되는게", "이게진짜말도안되는게", "근데진짜충격적인포인트는", "근데진짜충격적인건", "진짜충격적인포인트는", "근데진짜미친포인트는",
                    "근데진짜미친사용법은따로있었는데", "진짜미친사용법은따로있었는데", "이게미친포인트인게", "근데진짜는여기서부터", "궁금하신분들은댓글에",
                    "댓글에", "남겨주세요", "남겨주시면", "보내드릴게요", "이건바로", "말도안되는게", "있는거있죠", "하더라고요", "되더라고요", "더라고요",
                    "알고보니", "심지어", "진작알았으면", "반신반의했는데", "이게진짜미친포인트인게", "근데진짜", "충격적인포인트는", "미친포인트는"]


def ns(t):
    return re.sub(r"\s", "", t or "")


def has_nonron(lines):
    return [l for l in lines if "논란" in l]


def copy_fragments(lines, source_text, evidence_text, k=7):
    """lines 와 source_text(프롬프트 속 틀·예문·참고 대본)의 공백 뺀 k자 이상 공통 구절. 근거·장면 글, 신호어 화이트리스트에 든 구절은 뺀다."""
    src, ev = ns(source_text), ns(evidence_text)
    out = []
    for l in lines:
        t = ns(l)
        i, best = 0, []
        while i + k <= len(t):
            j = i + k
            if t[i:j] in src:
                while j < len(t) and t[i:j + 1] in src:
                    j += 1
                frag = t[i:j]
                if frag not in ev and not any(frag in w or w in frag and len(frag) - len(w) < k for w in SIGNAL_WHITELIST):
                    best.append(frag)
                i = j
            else:
                i += 1
        out += best
    return out


def cta_count(lines):
    return sum(1 for l in lines if "댓글" in l)


def made_facts(lines, evidence_text):
    text = "\n".join(lines)
    ev = evidence_text
    return {"nations": [w for w in NATIONS if w in text and w not in ev],
            "brands": [w for w in BRANDS if w in text and w not in ev],
            "role_claims": [w for w in ROLE_CLAIMS if w in text and w not in ev],
            "numbers_times": [m for m in TIME_RE.findall(text) if ns(m) not in ns(ev)]}


def weak_ending(lines):
    last = ns(lines[-1]) if lines else ""
    return [w for w in WEAK_ENDINGS if ns(w) in last]


def first4(line):
    return " ".join(line.split()[:4])


def skeleton_sim(lines, others):
    """이 시안의 줄 첫 4어절 중 같은 소재 다른 스타일 시안에도 있는 비율(최댓값과 그 상대)."""
    mine = [first4(l) for l in lines if len(l.split()) >= 4]
    if not mine:
        return 0.0, ""
    best, who = 0.0, ""
    for name, ol in others.items():
        theirs = set(first4(l) for l in ol if len(l.split()) >= 4)
        r = sum(1 for m in mine if m in theirs) / len(mine)
        if r > best:
            best, who = r, name
    return round(best, 2), who


def split_claims(claims):
    mood, fact = [], []
    for c in claims or []:
        (mood if any(w in c for w in MOOD_WORDS) else fact).append(c)
    return mood, fact


FIRST_SCHEMA = {"type": "object", "properties": {"pain_or_scene": {"type": "boolean"}, "surprise": {"type": "boolean"}, "why": {"type": "string"}},
                "required": ["pain_or_scene", "surprise", "why"]}


def judge_first(first_line, vertex_json):
    p = ("쇼핑 쇼츠 대본의 첫 줄(훅) 하나다. 두 가지를 판정하라.\n"
         "pain_or_scene: 구체적인 불편·괴로운 장면이나 '평범한 겉모습'(딱 봤을 땐 흔한 X처럼 생긴)이 들어 있나 — '자취생', '주부들' 같은 대상 이름만 있으면 false.\n"
         "surprise: 놀라운 점(예상 밖 성질·결과)이나 큰 반응(환장·난리·떼돈·기립박수 등)이 들어 있나 — 질문만 있고 놀라운 점이 없으면 false.\n"
         "why: 한 줄 이유.\n첫 줄: " + first_line)
    d = vertex_json(p, FIRST_SCHEMA, tag="measure:first") or {}
    return int(bool(d.get("pain_or_scene"))) + int(bool(d.get("surprise"))), d
