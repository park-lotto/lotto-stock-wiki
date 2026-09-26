# -*- coding: utf-8 -*-
"""이야기 작가 — 씨앗 결로 쓰고 화면은 나중에 붙인다 (2026-09-22 사장님 승인).

★왜 새 모듈인가: 기존 `backbone_assemble.write_lines*`는 **화면 묶음(groups_out)을 먼저 받아**
  그 화면에 맞춰 대본을 쓴다. 그래서 화면이 대본을 끌고 갔다(핸드오프: "두 달간 14번 전부
  문장↔장면 매칭을 더 잘하는 법이었다. 전부 두더지").
  여기서는 **대본이 먼저**다 — 씨앗 결 + 제품 특징으로 쓰고, 컷은 `assign_cuts`가 뒤에 붙인다.
  노바 작가(썰쇼핑 1위)가 쓰는 순서와 같다(2026-09-22 영상 정독).

★플랫폼으로 갈린다(실측):
  유튜브 썰  — 반말 · CTA 없음 · 고조 = 순간→벌어지는일→없애버림 · 신호어 17가지
  인스타     — 존댓말 · CTA · 고조 = before→after 체험담 · `~더라고요` 95~98% · 신호어 5가지
  섞으면 둘 다 망가진다.

★표현은 자유다(2026-09-22 사장님 "어짜피 이건 후킹싸움이야"):
  불편·상황·인물·수치·효능을 화면 밖에서 가져와도 된다. 사용자가 고칠 수 있다.
  단 **claim(제품이 하는 일)은 화면에 보이는 것만** — 그래야 컷을 붙일 수 있다.

시험대 원본: tools/seed_analyzer/{insta_writer,try_forced,pain_extract}.py
"""
import re

from shopping_shorts import script_generate as _sg

# ── 신호어 세트 — 코드가 칸 순서대로 박는다 ────────────────────────────────
# ★모델에게 고르게 하면 가장 흔한 하나로 쏠린다(실측 2026-09-22: 2편 모두
#   "이게 진짜 말도 안 되는 게"). 세트마다 한 자리는 비워 기계 티를 없앤다.
# ★위치가 고정된 프리셋(2026-09-22 히트작 전문 5편·채널 5곳 정독 — 전부 같은 연결):
#     공개 "이건 바로 X" → [1] 이게 말도 안 되는게 (기존 X와 달리) …해 준다는 거
#                      → [2] 심지어 …까지 …한다는 거  → [3] 근데 진짜 충격적인 포인트는 …다고 → 마무리 …라는데
#   공개 뒤 첫 신호어까지 중앙값 3어절, 첫 자리는 "이게 말도 안 되는게"가 50편 중 31편. "심지어"는 두 번째 자리 말이다
#   (사장님 화면 확인: 대비 앞에 심지어가 붙어 어색했다). 프리셋은 **낱말만** 다르고 위치·세기 순서는 같다.
YT_SETS = {
    "A": ["이게 말도 안 되는게", "심지어", "근데 진짜 충격적인 포인트는"],
    "B": ["이게 말도 안 되는 게", "게다가", "진짜 충격적인 포인트는"],
    "C": ["진짜 말도 안 되는게", "심지어", "근데 진짜 미친 포인트는"],
    "D": ["이게 말도 안 되는게", "거기다", "진짜 미친 포인트는"],
    "E": ["", "심지어", "근데 진짜 충격적인 포인트는"],
    "F": ["이게 미친 포인트인게", "게다가", "충격적인 건"],
    "G": ["이게 말도 안 되는게", "심지어", "더 대박인 건"],
    "H": ["진짜 말도 안 되는게", "거기다", "근데 진짜 충격적인 포인트는"],
}
_ALL_SIGNAL_WORDS = sorted({w for v in YT_SETS.values() for w in v if w} | {"심지어", "게다가", "거기다", "진짜 미친 건", "진짜 대박인 건", "미친 포인트는", "충격적인 포인트는", "이게 진짜 미친 게", "근데 진짜"})   # 모델이 반전을 자기 신호어로 열면 뗀다("근데 진짜 충격적인 포인트는 진짜 미친 건 …" 실측)
# 인스타는 낱말이 다르다(실측: 심지어 73·게다가 39·대박인 건 21·거기다 7·무엇보다 6).
# 썰의 "진짜 미친 포인트는"·"이게 말도 안 되는게"는 인스타에 거의 없다.
IG_SETS = {
    "A": ["", "심지어", "무엇보다"],
    "B": ["게다가", "", "대박인 건"],
    "C": ["", "거기다", "심지어"],
    "D": ["심지어", "", "게다가"],
    "E": ["", "대박인 건", "거기다"],
}

_EXPR = """■ 표현은 자유롭게 — 후킹이 전부다
불편·상황·인물·수치·효능·가격은 **화면에 없어도 쓸 수 있다.** 그 제품을 쓰는 사람이
겪을 법한 일이면 된다. 사용자가 나중에 고치니 세게, 구체적으로 써라.
★다만 장면을 아주 못 만들 정도로 화면과 동떨어진 말은 피해라 — 이 재료로 화면을 붙인다."""

# ── 길이 프리셋(2026-09-22 사장님 "두 개 다 프리셋으로 — 길이 숫자 말고 재밌게") ──────────────
#   short 한입썰 = 히트작 기준(썰 601편 중앙 203자·23초, 30초 이하 84%) — 지금 기본.
#   full  풀코스썰 = 긴 구조(345자·약 46초: 고조1 뒤 장면 풀이 3~4줄 + 심지어 2줄 + 마지막 셀링 3줄).
#   풀코스는 재료 화면보다 길어질 수 있다 — 화면 길이로 자르지 않는다(사용자가 배속을 올려 맞춘다).
LENGTH_PRESETS = {
    "short": {"label": "한입썰", "seconds": 25, "cap_by_footage": True},
    "full":  {"label": "풀코스썰", "seconds": 46, "cap_by_footage": False},
}

# 한입썰 칸 크기 — 썰 히트작 49편 실측(2026-09-22, 공백 제외 글자 중앙값): 훅 16 · 미끼 53 · 공개 11 ·
#   첫 칸(말도 안 되는게 ~ 버렸다는 거) 80 · 심지어 칸 39 · 충격 포인트 칸 48 · 전체 226.
#   ★우리 결함(사장님 job 먼지스펀지): 대비 줄 51~62자 + 고조1 세 줄 ~70자 = 첫 칸 자리가 120~130자 → 37초.
#   히트작은 "기존 X와 달리"가 첫 칸 **안에** 들어가 한 덩어리 80자다. 강제로 자르지 않고 칸 크기를 실측대로 준다.
SHORT_BLOCK = """
■ 칸 크기 (썰 히트작 49편 실측 — 공백 뺀 글자 수. 이 크기로 쓰면 저절로 23초 안팎이 된다)
  훅 16자 · 미끼 53자 · 공개 11자 · 고조1 한 덩어리 80자 · 고조2 39자 · 반전(충격 포인트) 48자 · 마무리 12자
  ★contrast(대비)는 **빈칸**으로 두고, 그 말("~하던 기존 X와는 달리")은 고조1의 moment 첫머리에 넣어라.
    히트작은 "이게 말도 안 되는게 [기존 X와 달리 / 원래는 X였지만] 순간 → 지옥 → 없애 버렸다는 거"가 한 덩어리다.
  ★고조는 2칸까지. 3칸째를 만들면 반전 자리를 먹는다.
"""

FULL_BLOCK = """
■ 풀코스 — 고조를 끝까지 풀어 쓴다 (히트작 시안 실측: 18줄·345자)
칸을 늘리지 말고 **한 칸을 깊게** 판다:
  고조1   moment→what_happens→erased 3줄 뒤에 **detail 3~4줄** — 쓰는 장면을 손으로 따라가듯 (~올리면 / ~않고 / ~끝이라 / ~버리는데)
  고조2   2줄 (심지어 …해서 / …많다는데)
  finale  마지막 셀링 3줄 — 앞에서 안 한 장점 2개를 장면으로 (~안 차고 / ~되니 / ~줄여 버렸다고)  ※ twist 대신 finale를 채워라
예시(줄 그대로 흉내 내지 말고 **모양**만):
  이건 바로 아기를 눕힌 채로 통째로 드는 이동식 침대
  이게 진짜 말도 안 되는 게
  겨우 재워놓고 바닥에 내려놓는 순간
  등이 닿자마자 눈을 번쩍 떠서 처음부터 다시 재우던 그 지옥을
  재우는 자리랑 옮기는 자리를 아예 하나로 합쳐서 없애 버렸다는 거
  아기를 눕힌 채로 손잡이만 잡아 올리면
  양쪽이 몸을 받쳐 줘서 자세가 무너지지 않고
  거실이든 안방이든 차 안이든 그냥 내려놓기만 하면 끝이라
  옮겨 심는 과정 자체가 사라져 버리는데
  심지어 살살 흔들어 주면 그 안에서 곤히 잠들어 버려서
  밤중 수유 때도 옆에 붙여 놓고 쓰는 사람이 많다는데
  근데 진짜는 여기부터
  안쪽은 통기 메쉬라 여름에도 등에 땀이 안 차고
  커버는 통째로 벗겨 세탁기에 돌려 버리면 되니
  짐이란 짐은 이거 하나로 다 줄여 버렸다고
"""

IG_FULL_BLOCK = """
■ 풀코스 — 상황극을 끝까지 끌고 간다 (인스타 히트작 실측: 300자 넘는 편은 3%뿐이고 전부 이 꼴 — 336자·108만 조회)
칸을 얇게 늘리지 말고 **사건을 이어 붙인다**:
  beats     before/after **3쌍** — 쌍마다 다른 자리(주방→욕실→손목·기관지처럼 축을 바꿔라)
  reaction  주변 사람 반응 **2줄** — 그걸 본 시어머니·남편·친정엄마가 뭐라고 했나, 그래서 하나 더 주문했다 같은 후속 사건
  feeling·cta는 그대로
예시(모양만):
  얼마 전에 구축 아파트로 이사를 오게 됐는데 시어머니가 집에 놀러 오셔서는 주방이며 욕실이며 어쩜 이렇게 깨끗하냐고 청소 업체 불렀냐고 하시는 거예요
  회사 청소 업체 사장님이 추천해 준 3만 원짜리 스팀 청소기인데 그냥 이걸로 한 번 쫙 청소해 줬더니 입주 청소비 100만 원은 아낀 것 같다고
  독한 세제도 필요 없고 물로만 99.9% 살균 청소가 돼서 좋다고 말씀드렸더니 표정이 싹 굳으시면서
  매번 독한 세제 풀어서 박박 닦느냐고 손목도 아프고 기관지도 안 좋았었는데 왜 이런 게 있다고 말을 안 해줬냐 하시더라고요
  죄송하다고 하고 하나 바로 주문해 드렸는데 한 번 써보시고는 주방 찌든 기름때부터 화장실 줄눈 곰팡이까지 순식간에 녹아내린다고 엄청 좋아하시는 거 있죠
  그래서 친정 엄마 것도 하나 주문했는데 댓글에 나도 남겨주세요
"""

# ── 유튜브 썰 ────────────────────────────────────────────────────────────
YT_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "string"},
        "bait": {"type": "string"},
        "reveal": {"type": "string"},
        "contrast": {"type": "string"},
        "escalations": {"type": "array", "items": {"type": "object", "properties": {
            "moment": {"type": "string"},
            "what_happens": {"type": "string"},
            "erased": {"type": "string"},
            "from_pain": {"type": "string"},
            "feat": {"type": "integer"},
            "detail": {"type": "array", "items": {"type": "string"}},     # 풀코스: 없앤 뒤 장면 풀이 3~4줄
        }, "required": ["moment", "what_happens", "erased", "from_pain", "feat"]},
            # ★고조는 **2칸 무조건**(2026-09-26 사장님 "고조2는 무조건 들어가야 된다"). 히트작 실측 프리셋도
            #   고조1 80자·고조2 39자 둘이다. 모델이 1칸만 쓰고 끝내던 것을 구조(minItems)로 막는다.
            "minItems": 2},
        "twist": {"type": "string"},
        "twist_feat": {"type": "integer"},      # 반전이 근거로 삼은 재료 번호 — 그 특징의 컷이 붙는다(2026-09-22)
        "finale": {"type": "array", "items": {"type": "string"}},       # 풀코스: 마지막 셀링 2~3줄(반전 대신)
        "closing": {"type": "string"},
    },
    "required": ["hook", "bait", "reveal", "contrast", "escalations", "twist", "closing"],
}

YT_BRIEF = """너는 한국 쇼핑 숏폼 나레이션 작가다. 유튜브 썰쇼핑 대본을 써라.

■ 말투 = 남 얘기 전하는 혼잣말 (썰 히트작 520편 실측 — 청자에게 말 거는 반말은 4%뿐이다)
보는 사람에게 말을 걸지 마라. "~있지?" "~해봐" "다들 알지?" 같은 대화체는 이 채널 말투가 아니다.
줄 끝은 **이 중에서** 고른다 (실측 빈도순):
  본문   ~는 거 · ~는데 · ~다는데 · ~라는데 · ~버림 · ~였음 · ~이라고 · ~있다고 · ~거임
  X 셔츠 단추 사이로 속살 삐져나와서 끙끙 앓았던 적 다들 있지?
  O 방아쇠 한번 당겨서 투명 핀으로 싹 고정해 없애 버렸다는 거

■ 훅(첫 줄) = 썰 히트작 제목 그대로의 꼴 — **[놀란 사람]도 [감탄] [천재의 발명품/활용법/정체]** (히트작 25편 첫 줄 실측)
  전 세계 주부들 환장한 미국 천재의 발명품 / 일본 천재가 만들어 떼돈 번 제품의 정체 / 개발자도 전혀 몰랐던 미친 사용법
  제조사도 감탄한 뜻밖의 활용법 / 비 맞던 육아맘들 구원한 일본 천재의 발명품 / 수영 어깨를 뒤집은 미국 천재의 발명품
  치과 무서운 사람들 기립박수 치게 만든 제품 / 명품 디자이너도 감탄한 미친 활용법 / 역발상으로 돈방석 앉은 육아천재의 발명품
  이케아도 놀라버린 조명 활용법 / 다이소 가면 무조건 사야 되는 필수템 / 한국 천재가 만들어 돈방석 앉은 제품
  → 첫 줄엔 반드시 **누가 놀랐나(권위자·대상)** 와 **얼마나 컸나(떼돈·돈방석·환장·구원·기립박수)** 가 들어간다.
  X 과자 먹다 손 더러워지는 이유   ← 불편만 말하고 놀란 사람도 크기도 없다. 이런 첫 줄은 쓰지 마라.
  O 게이머들 환장하게 만든 미국 천재의 발명품

■ 설명문을 쓰지 마라
"A는 B 기능이 있어 편리합니다" 같은 문장은 한 줄도 쓰지 마라.
제품 설명서가 아니라 그 장면을 보고 있는 사람의 말이다.
  X 원래 두피 영양제는 손에 묻어서 바르기 불편하지만
  O 겨우 짜서 바르려는데 손가락 사이로 다 흘러내리고 머리만 떡져서

■ reveal — 짧게 끊어라
"이건 바로 {제품명}." 로 끝낸다. 뒤에 설명을 이어 붙이지 마라.
실측(썰채널 30편): 공개 줄은 거의 전부 제품명만 말하고 바로 다음 칸으로 넘어간다.

■ contrast — 기존 것의 한계 → 이게 뭘 해 주는지까지 **한 줄로 끝까지** 말한다
"~와는 달리"에서 끊지 마라 (히트작 실측: 달리 뒤에 바로 다음 칸이 온 편 0, 전부 "~해 준다는 거"로 절을 닫았다).
  X 온도를 유지만 시켜 주던 기존 컵홀더와는 달리
  O 온도를 유지만 시켜 주던 기존 컵홀더와는 달리 버튼 한 번에 영하 3도까지 떨어뜨려 준다는 거
신호어는 우리가 앞에 붙인다. 댈 게 없으면 빈칸으로 둬라 (실측 492편 중 4편만 쓴 드문 칸이다).

■ escalations — 재료의 불편이 **진짜 괴로운 것만** 넣어라
칸 수를 채우려 하지 마라. 1개여도 2개여도 된다.
from_pain에는 근거로 삼은 특징을 적어라. 댈 게 없으면 그 칸을 만들지 마라.
칸을 여는 신호어는 **우리가 붙인다. 네가 쓰지 마라.** moment는 신호어 다음에 이어질 말로 시작해라.

칸 하나는 이렇게 채운다 (없는 걸 지어내지 말고 **있는 불편을 깊게 파라**):
  moment        그 불편이 벌어지는 순간을 현재형으로   "겨우 재워놓고 바닥에 내려놓는 순간"
  what_happens  그때 벌어지는 일 + 반복되는 괴로움    "등이 닿자마자 눈을 번쩍 떠서 다시 재우던 그 지옥을"
  erased        그걸 통째로 없앤 방식, 강한 동사로 끊기 "자리를 아예 하나로 합쳐서 없애 버렸다는 거"
  ★what_happens가 "~을/를"로 끝나면 erased는 그 목적어를 받는 서술어로 이어져야 한다.

■ twist는 앞 고조와 **다른 축**이어야 한다 (위생·보관·휴대 같은 다른 걱정거리). 근거로 삼은 재료 번호를 twist_feat에 적어라 — 그 번호의 화면이 붙는다.
■ closing(마무리)은 **남의 말 한 토막**이다 — 이 중에서 고른다 (썰 히트작 실측):
  요즘 품절 대란이라는데 / 주부들 사이에서 난리라는데 / 벌써 품절 난리라는데 / 이러니 떼돈을 벌었다고 / 완벽하다고 / 진짜 물건이라고
  X 구할 수 있을 때 챙겨 · X 한번 써 봐 · X 궁금하면 댓글   ← 보는 사람에게 시키는 말은 이 채널에 없다
■ bait(미끼)는 **소문·성과**다 — 끝은 "~다는데/~라는데/~는 거". 결과("없애 버렸다")는 여기서 말하지 마라, 그건 고조1의 마지막 줄 몫이다.
  "다들 알지/공감할 텐데" 같이 보는 사람을 부르는 꼬리는 히트작에 없다.
  O 손에 묻고 줄줄 흘러내려 머리만 떡지던 사람들 사이에서 이게 난리가 났다는데
  O 물기나 닦으라던 스펀지를 소파랑 블라인드 먼지까지 걷어내는 용도로 쓴다는 소문이 돌면서 품절 대란이라는데
■ 나라·사람은 지어내지 마라 — "{나라} 천재"의 나라는 씨앗이나 재료에 나온 것만 쓴다. 없으면 나라를 빼고 "천재의 발명품"으로.

■ 표현 재료 (골라 쓰는 것이다. 안 맞으면 쓰지 마라)
  의태어  싹·착·탁·쓱·확·쏙·슥·쭉·뚝딱·똑·푹·사르르·살살·번쩍
  고통    지옥·진절머리·빡쳤던·노이로제·스트레스·귀찮·답답·짜증
  없애기  없애 버렸다는 거 · 사라져 버리는데 · 줄여 버렸다고 · 날려 버려서
  증언    난리라는데 · 품절 대란 · 입소문이 터지며 · 쓰는 사람이 많다는데
  폭넓히기 거실이든 안방이든 차 안이든

""" + _EXPR + """

■ 지키는 것
- 문장을 마침표로 딱 끊지 말고 연결어미로 이어라.
- 씨앗의 말투는 가져오되 문장은 베끼지 말고 새로 써라."""

# ── 인스타 ───────────────────────────────────────────────────────────────
IG_SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},
        "scene": {"type": "string"},
        "ask": {"type": "string"},
        "reveal": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "before": {"type": "string"},
            "after": {"type": "string"},
            "from_pain": {"type": "string"},
            "feat": {"type": "integer"},
        }, "required": ["before", "after", "from_pain", "feat"]}},
        "feeling": {"type": "string"},
        "reaction": {"type": "array", "items": {"type": "string"}},   # 풀코스: 주변 사람 반응 2줄(시어머니·친정엄마·남편)
        "cta": {"type": "string"},
    },
    "required": ["opening", "scene", "ask", "reveal", "beats", "feeling", "cta"],
}

IG_BRIEF = """너는 인스타 릴스 쇼핑 대본 작가다. **겪은 일을 이야기하듯** 써라.

■ 이건 설명이 아니라 상황극이다
  X 이 제품은 콩알만큼 떼어 붙이면 고정되는 기능이 있습니다
  O 어느 날 언니네 갔더니 식탁 위 소품들이 하나도 안 굴러다니길래 뭐 했냐고 물어봤거든요

■ 말투 (인스타 641편 실측)
- 존댓말 1인칭. 문장 끝은 **~더라고요 / ~거든요 / ~어요 / ~습니다**.
- 유튜브 썰 어미(`~다는데` · `~버렸다는 거` · `~는 거임`)를 쓰면 인스타가 아니다.
- 감탄으로 여는 편이 많다(38%): "와…", "아니 이거".

■ 대사는 따옴표 없이 **간접화법**으로 (실측: 따옴표 대사 0%)
  "비결이 뭐냐니까 창문에 그냥 이 페인트를 바른 거래요"
  "놀라서 뭐 했냐고 물어봤더니 트레이너한테 추천 받았다는 거예요"
ask 칸이 이 자리다. 인물(친구·언니·엄마·지인)은 이야기를 사게 하는 장치이니 자연스럽게 등장시켜라.

■ beats — 겪은 일을 before/after로
  before  이걸 모를 때 내가 어떻게 하고 있었나. 그 장면과 짜증을 그대로.
  after   쓰고 나서 어떻게 달라졌나. **기능이 아니라 장면으로.**
  from_pain  이 칸이 어느 특징에서 나왔는지 적어라.
  ★before·after 각각 끝까지 말한 한 문장이다 — "~했는데."처럼 이어질 말을 끊어 두지 마라. 끝은 ~거든요 / ~더라고요 / ~어요.
칸 수를 채우려 하지 마라. 억지로 늘리면 안 쓴 것만 못하다.

■ feeling — 결과를 숫자가 아니라 **생활의 장면**으로
  "이거 들고 간 날부터 물에서 나오지를 않아요" · "간만에 신혼 때로 돌아간 것 같아요"

■ cta — 권하지 않는다 (인스타 641편 실측: "써보세요/해보세요"로 닫은 편 1%)
  이 중 하나로 닫아라:  댓글에 '낱말' 남겨주세요  ·  나도 남겨주시면 정보 보내드릴게요  ·  (소감 한 줄로 끝)
  X 여러분도 꼭 한번 써보세요
  O (이 제품·이 이야기에 맞는 말) + 댓글에 '낱말' 남겨주세요   ※ 예문을 베끼지 마라 — 실측: 예문이 2/3편에 그대로 복사됐다

""" + _EXPR + """

■ 지키는 것
- 시간 표지를 자연스럽게(37%): 얼마 전 · 어느 날 · 요즘 · 처음엔.
- 문장을 길게 이어 붙여라. 딱딱 끊으면 이야기가 아니라 목록이 된다."""


def _feats_block(feats):
    # ★번호를 매긴다 — 고조 칸이 **어느 재료에서 나왔는지 번호(feat)로** 답하게 한다.
    #   글로 적게 하면 풀어 쓴다(2026-09-22 실측: 특징 '원터치 타공 및 고정'을 "원터치 타공으로 수선 고민 해결"로
    #   적어 글자 대조가 실패 → 그 줄이 근거 컷을 못 받고 아무 컷이나 받았다).
    rows = ["(고조 칸마다 feat에 아래 **재료 번호**를 적어라. 그 번호의 화면이 그 칸에 붙는다.)"]
    for i, f in enumerate(feats or []):
        tag = ""
        if "new" in f:        # pick_diff_feats가 단 표시 — 차별점(새 특징)과 씨앗이 이미 한 말을 모델이 구분하게
            tag = (("  [새 특징 — 씨앗에 없음, 영상 %d개가 보여줌]" % f.get("videos", 0)) if f["new"]
                   else "  [씨앗이 이미 말함 — 고조1에만 쓸 수 있다]")
        rows.append("%d. %s — %s%s" % (i + 1, f.get("name") or "", f.get("claim") or "", tag))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    return "\n".join(rows)


def _pick(sets, key, nth=0):
    """세트를 정해진 규칙으로 고른다. nth는 **순번으로 더한다** —
    해시에 섞으면 한 작업의 1안과 3안이 우연히 같은 세트가 된다(2026-09-22 실측)."""
    import zlib
    names = sorted(sets)
    i = (zlib.crc32(str(key).encode("utf-8")) % len(names) + int(nth)) % len(names)
    return names[i], sets[names[i]]


def _seed_last(seed_text):
    """씨앗의 마지막 포인트(마지막 문장). ★문장이 하나뿐이면 빈칸 — 그걸 지시문에 넣으면 씨앗 **첫 줄**이 보여
    훅이 베껴진다(story_hook.instruction: "씨앗 문장은 절대 보여주지 않는다", 테스트가 잡았다)."""
    parts = [p.strip() for p in re.split(r"[.!?\n]", seed_text or "") if len(p.strip()) >= 8]
    if len(parts) < 2:
        return ""
    last = parts[-1][:120]
    return "" if _gram_share(parts[0], last) > 0.3 else last


def _diff_rule(feats, twist_n, seed_text, seed_points=None):
    """차별점 지시(pick_diff_feats가 new 표시를 단 재료가 있을 때만). 새 특징이 없으면 빈 문자열 = 종전 그대로.
    ★새 특징이 **1개뿐**이면 반전만 새 특징, 고조2는 고조1과 **다른** 씨앗 특징(2026-09-26 실측: 새 1개로 고조2·반전을
      둘 다 채우라 했더니 같은 특징을 두 번 말했다 — '1인분 포장' → '개별 포장이라 신선')."""
    new = [i + 1 for i, f in enumerate(feats or []) if f.get("new")]
    if not new:
        return ""
    old = [i + 1 for i, f in enumerate(feats or []) if "new" in f and not f.get("new")]
    rows = ["■ 차별점 — 이 대본이 씨앗 영상과 달라지는 곳은 **특징(셀링포인트)**이다. 씨앗이 이미 한 말을 또 하면 같은 영상이 된다."]
    if len(new) >= 2:
        if old:
            rows.append("  씨앗이 이미 말한 특징(재료 %s번)은 **고조1에서만** 쓸 수 있다." % ", ".join(map(str, old)))
        rows.append("  고조2부터는 **새 특징(재료 %s번)**으로만 채워라." % ", ".join(map(str, [n for n in new if n != twist_n] or new)))
    else:
        rows.append("  고조는 칸마다 **서로 다른 특징**을 쓴다(같은 번호를 두 칸에 쓰지 마라). 재료 %d번은 **반전 전용**이다." % new[0])
    if twist_n:
        rows.append("  반전(twist)은 **재료 %d번**으로 쓰고 twist_feat에 %d을 적어라 — 여러 영상이 공통으로 보여준 가장 센 새 특징이다."
                    % (twist_n, twist_n))
    pts = [p for p in (seed_points or []) if p]
    if pts:
        rows.append("  ★씨앗이 이미 말한 것 — 반전과 고조2에는 **이 내용을 쓰지 마라**(표현만 바꿔도 같은 내용이면 안 된다):")
        rows += ["    - %s" % p for p in pts[:10]]
    return "\n".join(rows)


def _seed_word_hits(text, seed_points, product=""):
    """문장 속에 씨앗 셀링포인트의 **특징 낱말**이 몇 개 나오나(제품명 낱말은 뺀다 — 어느 줄에나 나온다)."""
    skip = set(_words(product))
    sw_ = {w for w in _words(" ".join(seed_points or [])) if w not in skip}
    t = re.sub(r"\s+", "", text or "")
    return sorted(w for w in sw_ if w in t)


def _diff_violations(out, feats, twist_n, seed_text, seed_points=None, product=""):
    """모델 출력이 차별점 규칙을 어긴 곳(다시 쓰라는 말로). 없으면 []."""
    bad = []
    n_new = sum(1 for f in feats or [] if f.get("new"))
    def _is_old(n):
        return isinstance(n, int) and 1 <= n <= len(feats or []) and "new" in feats[n - 1] and not feats[n - 1].get("new")
    escs = out.get("escalations") or []
    seen = [e.get("feat") for e in escs]
    for i, e in enumerate(escs[1:], start=2):
        n = e.get("feat")
        if n_new >= 2 and _is_old(n):
            bad.append("고조%d가 씨앗이 이미 말한 %d번 특징을 썼다. 새 특징 번호로 바꿔라" % (i, n))
        if isinstance(n, int) and n in seen[:i - 1]:
            bad.append("고조%d가 앞 고조와 같은 %d번 특징을 또 썼다. 다른 특징으로" % (i, n))
        if n_new == 1 and twist_n and n == twist_n:
            bad.append("고조%d가 반전 전용 %d번을 썼다. 다른 특징으로" % (i, n))
    # ★내용 대조(2026-09-26 실측: 번호는 새 특징이라 적고 글은 씨앗 내용 — "비싼 브랜드 제품을 압도"·"온 집안 물컵을 이걸로").
    #   씨앗 문장을 마침표로 나누는 방식은 마침표 없는 씨앗에서 아예 안 돌았다 → 씨앗 셀링포인트 목록의 낱말로 본다.
    for label, t in [("반전", out.get("twist") or "")] + [
            ("고조%d" % (i + 2), " ".join(str(e.get(k) or "") for k in ("moment", "what_happens", "erased")))
            for i, e in enumerate(escs[1:]) if n_new >= 2]:
        hits = _seed_word_hits(t, seed_points, product)
        if len(hits) >= 2:
            bad.append("%s가 씨앗이 이미 말한 내용(%s)을 썼다. 새 특징으로 새로 써라" % (label, ", ".join(hits[:4])))
    # 번호를 **안 적은** 건 위반이 아니다(write가 twist_n으로 채운다). 다른 번호를 적었을 때만 다시 쓴다.
    if twist_n and out.get("twist_feat") is not None and out.get("twist_feat") != twist_n:
        bad.append("반전(twist)은 재료 %d번으로 쓰고 twist_feat=%d" % (twist_n, twist_n))
    tw = (out.get("twist") or "").strip()
    last = _seed_last(seed_text)
    if tw and last:
        from shopping_shorts import story_hook
        if story_hook.copied(tw, last) or _gram_share(tw, last) > 0.4:
            bad.append("반전 문장이 씨앗의 마지막 포인트를 옮겼다. 새 특징으로 새로 써라")
    return bad


def _gram_share(a, b, n=4):
    """a의 n글자 조각 중 b에도 있는 비율(글자만)."""
    ca, cb = re.sub(r"[^가-힣A-Za-z0-9]", "", a or ""), re.sub(r"[^가-힣A-Za-z0-9]", "", b or "")
    ga = {ca[i:i + n] for i in range(max(0, len(ca) - n + 1))}
    gb = {cb[i:i + n] for i in range(max(0, len(cb) - n + 1))}
    return len(ga & gb) / len(ga) if ga else 0.0


def write(product, seed_text, feats, platform="yt", style=None, key="", nth=0, note=None, seconds=0, preset="short",
          hook_slots=None, twist_n=0, seed_points=None):
    """대본 한 편 → [{beat, text}]. 실패하면 [](호출부가 옛 경로로 간다).

    platform: "yt"(유튜브 썰) | "ig"(인스타)
    style:    {"name","hook_angle","flow","extra"} — 고객이 고른 스타일(없으면 기본 흐름)
    hook_slots(썰, 2026-09-26): 씨앗의 홀린 요인(권위자·대상·나라…). 주면 첫 줄은 **꼴 은행**(story_hook)에서 회전해
              고른 꼴로 쓰고, 씨앗 첫 줄을 베끼면 다른 꼴로 1회 재작성 → 그래도면 결정적 채움. None이면 종전 그대로.
    """
    ig = (platform == "ig")
    hook_mold = None
    if not ig and hook_slots is not None:
        from shopping_shorts import story_hook
        hook_mold, _ = story_hook.pick(hook_slots, key, nth, seed_text)
        if hook_mold and style:
            style = dict(style, hook_angle="")       # 꼴은 은행이 정한다 — 씨앗 첫 줄 꼴(_seed_style)은 쓰지 않는다
    brief = IG_BRIEF if ig else YT_BRIEF
    if preset == "full":
        brief += IG_FULL_BLOCK if ig else FULL_BLOCK
    elif not ig:
        brief += SHORT_BLOCK
    if style:
        brief += ("\n\n■ 이번 대본의 스타일: %s\n스토리라인: %s\n첫 줄 각도: %s\n%s"
                  % (style.get("name") or "", style.get("flow") or "",
                     style.get("hook_angle") or "", style.get("extra") or ""))
    if seconds:
        # ★분량은 **칸 수로** 맞춘다 — 칸을 얇게 쓰면 설명문이 된다(시험대 실측: 4칸을 만들다 칸마다 1줄로 쪼그라듦).
        #   안 넘기면 재료 컷이 동난다(2026-09-22 실측 job 13d4cab55fba: 쓸 컷 27개·48.8초에 대본 45.7초 → 4줄이 컷 없음).
        from shopping_shorts.script_gate import SPEECH_CHARS_PER_SEC as _CPS
        brief += ("\n\n■ 분량: 전체 **%d자 안팎**(읽으면 약 %d초). 넘치면 고조 **칸 수를 줄여라** — "
                  "칸 하나를 얇게 쓰지 마라. 남긴 칸은 깊게 파라." % (int(seconds * _CPS), int(seconds)))
    if hook_mold:
        from shopping_shorts import story_hook
        brief += "\n\n■ " + story_hook.instruction(hook_mold, hook_slots)
    _diff = _diff_rule(feats, twist_n, seed_text, seed_points) if not ig else ""
    if _diff:
        brief += "\n\n" + _diff
    prompt ="%s\n\n[제품] %s\n\n[씨앗 — 이 제품으로 터진 영상의 말]\n%s\n\n[재료]\n%s" % (
        brief, product or "", (seed_text or "").strip(), _feats_block(feats))
    schema = IG_SCHEMA if ig else (_short_schema() if preset == "short" else YT_SCHEMA)
    out = _sg._call_json(prompt, schema, note=note) or {}
    if not ig and _n_escalations(out) < MIN_ESCALATIONS:
        # ★고조2 무조건(2026-09-26 사장님). 스키마 minItems로도 모델이 빈 문자열 칸을 채워 올 수 있어
        #   내용이 있는 고조 칸을 세고, 모자라면 **무엇이 모자란지 말해 1회 다시** 쓴다. 그래도 모자라면 반려([]) —
        #   호출부(make_drafts)가 why에 남겨 화면이 이유를 보인다(조용히 얇은 대본을 내보내지 않는다).
        if note is not None:
            note["escalation_retry"] = _n_escalations(out)
        out = _sg._call_json(prompt + ESCALATION_RETRY_BLOCK % _n_escalations(out), schema, note=note) or {}
        if _n_escalations(out) < MIN_ESCALATIONS:
            if note is not None:
                note["reason"] = "고조2 없음(%d칸)" % _n_escalations(out)
            return []
    if _diff:
        _bad = _diff_violations(out, feats, twist_n, seed_text, seed_points, product)
        if _bad:
            # ★차별점 검사(2026-09-26): 고조2·반전이 씨앗 특징을 쓰거나 반전이 씨앗 문장을 옮기면 **1회** 다시 쓴다.
            #   그래도 어기면 그대로 낸다(대본이 안 나오는 것보다 낫다) — note에 남겨 화면·점검이 본다.
            if note is not None:
                note["diff_retry"] = _bad
            out2 = _sg._call_json(prompt + "\n\n■ 다시 써라 — " + " / ".join(_bad), schema, note=note) or {}
            if out2 and _n_escalations(out2) >= MIN_ESCALATIONS:
                out = out2
                _left = _diff_violations(out, feats, twist_n, seed_text, seed_points, product)
                if _left and note is not None:
                    note["diff_left"] = _left
    if _diff and twist_n and out.get("twist_feat") is None and (out.get("twist") or "").strip():
        out = dict(out, twist_feat=twist_n)     # 반전 줄은 지정 특징(새 특징 1위)의 근거 컷을 받는다
    lines = _to_lines(out, ig, key, nth, feats, preset=preset)
    if not ig and lines and hook_slots is not None:
        lines = _guard_hook(lines, prompt, schema, hook_slots, key, nth, seed_text, feats, preset, note)
    return lines


def _guard_hook(lines, prompt, schema, hook_slots, key, nth, seed_text, feats, preset, note):
    """첫 줄이 씨앗 첫 줄을 베꼈으면 → 다른 꼴로 1회 재작성 → 그래도면 결정적 채움(story_hook.resolve).
    ★판정·채움은 story_hook 한 곳. 여기는 순서만 정한다. 재작성 결과는 고조2 규칙도 다시 본다."""
    from shopping_shorts import story_hook
    if not story_hook.copied(lines[0].get("text"), seed_text):
        return lines
    mold2, _ = story_hook.pick(hook_slots, key, nth + 1, seed_text)
    if mold2:
        if note is not None:
            note["hook_retry"] = lines[0].get("text")
        out2 = _sg._call_json(prompt + "\n\n■ 첫 줄을 다시 써라 — 씨앗 영상의 첫 문장과 너무 비슷하다. "
                              + story_hook.instruction(mold2, hook_slots), schema, note=note) or {}
        if _n_escalations(out2) >= MIN_ESCALATIONS:
            lines2 = _to_lines(out2, False, key, nth, feats, preset=preset)
            if lines2 and not story_hook.copied(lines2[0].get("text"), seed_text):
                return lines2
    fixed, why = story_hook.resolve(lines[0].get("text"), hook_slots, key, nth, seed_text)
    if note is not None:
        note["hook_fix"] = why
    lines[0] = dict(lines[0], text=fixed)
    return lines


MIN_ESCALATIONS = 2      # 썰: 고조1(불편→없앰) + 고조2(심지어) — 히트작 프리셋과 같은 수
ESCALATION_RETRY_BLOCK = ("\n\n■ 다시 써라 — 고조 칸이 %d개뿐이다. **고조 칸은 정확히 2개**여야 한다. 두 번째 고조는 "
                          "첫 번째와 **다른 특징·다른 장면**(재료의 다른 번호)으로 쓰고, moment·what_happens·erased를 다 채워라. "
                          "다른 칸은 그대로 두어도 된다.")


def _n_escalations(out):
    """내용이 채워진 고조 칸 수 — moment·what_happens·erased 중 하나라도 글이 있으면 1칸으로 센다."""
    n = 0
    for e in (out or {}).get("escalations") or []:
        if isinstance(e, dict) and any((e.get(k) or "").strip() for k in ("moment", "what_happens", "erased")):
            n += 1
    return n


# 한입썰 칸별 최대 글자(공백 포함) — 썰 히트작 49편 실측 75% 지점을 조금 넘는 값. 지시문은 모델이 넘기지만
#   스키마 maxLength는 구조라 넘길 수 없다(2026-09-22 실측: 같은 SHORT_BLOCK 지시로 한 씨앗은 227자, 다른 씨앗은 47초·380자).
_SHORT_MAX = {"hook": 26, "bait": 62, "reveal": 22, "contrast": 0, "moment": 40, "what_happens": 46, "erased": 40,
              "twist": 60, "closing": 22}


def _short_schema():
    import copy
    sc = copy.deepcopy(YT_SCHEMA)
    pr = sc["properties"]
    for k in ("hook", "bait", "reveal", "twist", "closing"):
        pr[k]["maxLength"] = _SHORT_MAX[k]
    pr["contrast"]["maxLength"] = 1                       # 한입썰은 대비를 고조1 안에 녹인다(빈칸)
    esc = pr["escalations"]["items"]["properties"]
    for k in ("moment", "what_happens", "erased"):
        esc[k]["maxLength"] = _SHORT_MAX[k]
    pr["escalations"]["maxItems"] = 2
    return sc


def _group_of(from_pain, feats):
    """고조 칸이 댄 근거(from_pain) → 특징 번호. 못 찾으면 -1(구조 줄처럼 남는 컷을 받는다).
    모델은 특징 이름을 적기도 하고 불편 문장을 적기도 한다 — 둘 다 본다."""
    fp = re.sub(r"\s+", "", from_pain or "")
    if not fp:
        return -1
    for i, f in enumerate(feats or []):
        nm = re.sub(r"\s+", "", f.get("name") or "")
        pn = re.sub(r"\s+", "", f.get("pain") or "")
        if (nm and (nm in fp or fp in nm)) or (pn and (pn[:8] in fp or fp[:8] in pn)):
            return i
    return -1


_LEAD_CONJ = re.compile(r"^(근데|그런데|그리고|또|그래서|또한)\s+")
_RANK_ONE = re.compile(r"말도 안 되는|미친 포인트인게")   # 위치[1] 낱말(한 줄 단독으로 둘 수 있는 것)


def _to_lines(o, ig, key, nth, feats=None, preset="short"):
    """모델 출력 → [{role, text, group}]. group = 그 줄이 말하는 특징 번호(-1 = 구조 줄).
    ★신호어는 칸의 **첫 줄 앞에 붙인다** — 따로 한 줄로 두면 3글자짜리 줄에 컷이 배정된다."""
    esc_keys = ("before", "after") if ig else ("moment", "what_happens", "erased")
    if ig:
        escs = o.get("beats") or []
        _, sigs = _pick(IG_SETS, key, nth)
        all_sigs = list(sigs)
        rows = [("훅", o.get("opening"), -1), ("장면", o.get("scene"), -1)]
        if (o.get("ask") or "").strip():
            rows.append(("물어봄", o["ask"], -1))
        rows.append(("공개", o.get("reveal"), -1))
        tail = [("소감", o.get("feeling"), -1), ("CTA", o.get("cta"), -1)]
        if preset == "full":
            tail = [("반응", t.strip(), -1) for t in (o.get("reaction") or [])[:2] if (t or "").strip()] + tail
    else:
        escs = o.get("escalations") or []
        _, sigs = _pick(YT_SETS, key, nth)
        all_sigs = list(sigs)          # 중복 제거는 세트 전체로 본다(대비가 첫 신호어를 가져가도)
        rows = [("훅", o.get("hook"), -1), ("미끼", o.get("bait"), -1), ("공개", o.get("reveal"), -1)]
        if (o.get("contrast") or "").strip():
            # ★위치[1] 신호어는 대비에 붙는다("이게 말도 안 되는게 기존 X와 달리 Y해 준다는 거") — 대비가 없으면 고조1에.
            rows.append(("대비", _LEAD_CONJ.sub("", o["contrast"].strip()), -1))
        _tf = o.get("twist_feat")
        _tg = (_tf - 1) if isinstance(_tf, int) and 1 <= _tf <= len(feats or []) else -1
        tail = [("반전", o.get("twist"), _tg), ("마무리", o.get("closing"), -1)]
        # 슬롯 = 대비(있으면) → 고조들 → 반전. 프리셋 낱말을 이 순서로 앞에서부터 하나씩 준다(위치 고정).
        # 위치[3](가장 센 말)은 **반전 전용**. 대비·고조는 위치[1]·[2]를 순서대로 받고, 남으면 빈칸.
        slot_words = list(sigs[:2])
        last_word = sigs[2] if len(sigs) > 2 else ""
        if (o.get("contrast") or "").strip() and slot_words:
            w = slot_words.pop(0)
            if w:
                if preset == "full":      # 풀코스: 신호어 [1]은 한 줄 단독(히트작 시안 실측)
                    rows.insert(len(rows) - 1, ("대비", w, -1))
                else:
                    rows[-1] = ("대비", w + " " + rows[-1][1], -1)
        sigs = slot_words + [""] * 8
    for i, e in enumerate(escs):
        n = e.get("feat")
        gi = (n - 1) if isinstance(n, int) and 1 <= n <= len(feats or []) else _group_of(e.get("from_pain"), feats)
        sig = sigs[i] if i < len(sigs) else ""
        # ★인스타는 신호어를 **after 줄**에 붙인다(2026-09-22 실측: 히트작 641편의 신호어 146개 중 과거 불편
        #   "전에는~" 앞에 온 것 0개. before 줄에 붙이면 "게다가 전에는 …했거든요"가 돼 10편 중 4편이 어색했다).
        sig_key = "after" if ig else esc_keys[0]
        for k in esc_keys:
            t = (e.get(k) or "").strip()
            if not t:
                continue
            if sig and (k == sig_key or not (e.get(sig_key) or "").strip()):
                t = _LEAD_CONJ.sub("", t)      # "게다가 근데 이건…" — 신호어 뒤 접속사 겹침(실측 7줄 중 1)
                if not ig and preset == "full" and i == 0 and _RANK_ONE.search(sig):
                    rows.append(("고조%d" % (i + 1), sig, gi)); sig = ""     # [1]은 한 줄 단독
                else:
                    t, sig = sig + " " + t, ""
            rows.append(("고조%d" % (i + 1), t, gi, k))          # k = moment/what_happens/erased(썰) · before/after(인스타)
        if not ig and preset == "full":
            for t in (e.get("detail") or [])[:4]:                          # 장면 풀이 3~4줄
                if (t or "").strip():
                    rows.append(("고조%d" % (i + 1), t.strip(), gi))
    if not ig and preset == "full" and any((t or "").strip() for t in (o.get("finale") or [])):
        fin = [t.strip() for t in (o.get("finale") or []) if (t or "").strip()][:3]
        tail = ([("반전", last_word, _tg)] if last_word else []) + [("반전", t, _tg) for t in fin] + [("마무리", o.get("closing"), -1)]
        last_word = ""
    if not ig:
        left = [last_word] if last_word else []
        if left and (tail[0][1] or "").strip():
            tw = tail[0][1].strip()
            for w in sorted(_ALL_SIGNAL_WORDS, key=len, reverse=True):   # 모델이 이미 어떤 신호어로 열었으면 떼고 붙인다
                if tw.startswith(w + " "):
                    tw = tw[len(w):].strip()
            tail[0] = ("반전", left[0] + " " + _LEAD_CONJ.sub("", tw), tail[0][2])
    rows += tail
    return _drop_repeat_signal(
        [{"role": r[0], "text": re.sub(r"\s+", " ", r[1]).strip(), "group": r[2], "sub": (r[3] if len(r) > 3 else "")}
         for r in rows if (r[1] or "").strip()], all_sigs)


# ── 재료에서 특징 + 불편(pain) 뽑기 (모델 1회) ─────────────────────────────
# ★정의는 여기 한 곳(0순위-B). 시험대 tools/seed_analyzer/pain_extract.py는 이걸 가져다 쓴다.
#   근거(라이브 실측 2026-09-22, 최근 57 job·3,880 세그): shot_role '문제' 132·'before' 339,
#   57 job 중 43개(75%)에 문제/before 세그가 있다 — 뽑는 사람이 없었을 뿐이다.
PROBLEM_ROLES = {"문제", "before"}
PROBLEM_WORDS = re.compile(r"불편|어려움|번거|귀찮|지저분|엉키|엉망|힘들|고생|낭비|"
                           r"문제|손상|망가|샌다|흘러|끈적|답답|공감")

FEATS_SCHEMA = {
    "type": "object",
    "properties": {"feats": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"},
        "claim": {"type": "string"},
        "pain": {"type": "string"},
        "from_cuts": {"type": "array", "items": {"type": "string"}},
        "seed_quote": {"type": "string"},   # 씨앗이 이미 말했으면 그 씨앗 문장(인용) — 빈칸 = 새 특징(2026-09-26)
        "seed_point": {"type": "integer"},  # seed_points의 몇 번과 같은가(1부터). 없으면 0
    }, "required": ["name", "claim", "pain", "from_cuts", "seed_quote", "seed_point"]}},
        # ★씨앗이 말한 셀링포인트를 **먼저** 적게 한다 — 인용만 시켰더니 빠뜨렸다(09-26 실측: 이어폰 씨앗의
        #   "특수 실리콘 패드가 … 압박감은 줄이고"를 두고 '유연한 소재'를 새 특징이라 했다).
        "seed_points": {"type": "array", "items": {"type": "string"}},
        # ★홀린 요인(2026-09-26, 노바 2단계) — 첫 줄 꼴의 빈칸 재료. 이름은 스파인 문형 슬롯과 같다(story_hook.SLOT_KEYS).
        "hook": {"type": "object", "properties": {
            "권위자": {"type": "string"}, "대상": {"type": "string"}, "나라": {"type": "string"},
            "제품군": {"type": "string"}, "불편함": {"type": "string"}, "장소": {"type": "string"}, "계기": {"type": "string"}}}},
    "required": ["feats", "hook"],
}

FEATS_BRIEF = """아래는 같은 제품을 찍은 영상들의 장면 태깅이다.
이 제품의 특징 후보를 **5~6개** 뽑아라. 서로 겹치는 건 하나로 합치고 약한 건 버려라.

특징마다 다섯 가지를 적는다:
  name   짧은 이름
  claim  이 제품이 실제로 하는 일 (화면에 보이는 것만)
  pain   ★**이게 없을 때 뭐가 괴로운가** — 기능을 뒤집어 쓰지 말고, 그 사람이 겪던 장면으로 적어라
         X 고정이 안 된다                     (기능을 뒤집은 말 — 쓸모없다)
         O 조금만 건드려도 쓰러지고 굴러다녀서 매번 다시 세워야 했다
  from_cuts  그 특징이 **화면에 실제로 보이는** 컷 번호들 (목록에 있는 번호만. 지어내지 마라)
  seed_quote ★씨앗 영상의 말에 이 특징이 **이미 나오면** 그 씨앗 문장을 **그대로 옮겨** 적어라. 안 나오면 빈 문자열.
             (대본의 차별점을 가른다 — 씨앗이 이미 한 말을 또 하면 같은 영상이 된다. 비슷한 말이면 나온 것으로 본다)
  seed_point 아래 seed_points 중 이 특징과 **같은 것의 번호**(1부터). 없으면 0.

★seed_points를 **먼저** 채워라 — 씨앗 영상의 말이 자랑한 셀링포인트를 빠짐없이, 한 줄에 하나씩 짧게.
  (소재·구조·기능·수치·가격·맛·용도… 씨앗이 말했으면 전부. 이 목록에 있는 건 이 대본의 차별점이 될 수 없다)

pain을 적는 법:
- 태깅에 **[문제]·[before] 컷**이 있으면 먼저 거기서 가져와라. 제작자가 찍어 둔 불편이다.
- `용처` 설명에 "~의 어려움", "~하는 불편함"처럼 적혀 있으면 그대로 쓴다.
- ★화면에 그 장면이 없어도 된다(2026-09-22 사장님). 카메라는 제품이 **잘 되는 모습**을 찍지
  불편한 장면은 거의 안 찍는다(실측: 문제 컷이 3,880개 중 132개=3.4%).
  그러니 **그 제품을 쓰는 사람이라면 누구나 겪을 법한 불편**을 구체적인 장면으로 적어라.
    O 테이프로 붙이면 나중에 누렇게 떠서 떼어낼 때 자국이 남는다
- 기능을 뒤집어 쓰지 마라.  X 고정이 안 된다  /  X 도포가 균일하지 않다

★claim(이 제품이 하는 일)은 화면에 보이는 것만 쓴다. pain은 화면 밖에서 와도 된다.

■ hook — 첫 줄 빈칸 재료(**홀린 요인**). 씨앗·재료에 **실제로 나온 것만**, 각 20자 이내, 없으면 빈 문자열:
  권위자  이 제품을 보고 놀랄 만한 전문가·회사·직군 (예: 개발자, 제조사, 안경사, 호텔 직원)
  대상    이 제품으로 구원받는 사람들 — 복수형 (예: 게이머들, 육아맘들, 자취생들)
  나라    씨앗·재료에 나온 나라만 (예: 한국, 미국, 일본). ★없으면 빈칸 — 지어내지 마라
  제품군  제품 종류 짧게 (예: 열수축 필름, 손가락 젓가락)
  불편함  이 제품이 없앤 불편 한 토막, 명사형 (예: 리모컨 손때, 과자 가루 손)
  장소    구매처·쓰는 곳 (예: 다이소, 이케아, 호텔)
  계기    시작된 계기 (예: 육아 불편, 게이머의 짜증)"""


def source_block(sources):
    """태깅을 모델이 읽을 형태로. 문제/before 컷을 앞에 모아 눈에 띄게 한다."""
    prob, normal = [], []
    for v in sources or []:
        for x in (v.get("segments") or []) if isinstance(v, dict) else []:
            role = x.get("shot_role") or ""
            up = (x.get("use_point") or "")
            line = "  [%s] %s | 화면:%s%s%s%s" % (
                x.get("seg_id"), role, (x.get("scene_desc") or "")[:70],
                (" | 변화:%s" % (x.get("change") or "")[:40]) if x.get("change") else "",
                (" | 용처:%s" % up[:70]) if up else "",
                (" | 특징:%s" % " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2]))
                if x.get("product_benefits") else "")
            (prob if (role in PROBLEM_ROLES or PROBLEM_WORDS.search(up)) else normal).append(line)
    out = []
    if prob:
        out += ["[불편을 보여주는 컷 — pain은 여기서 가져와라]"] + prob[:20] + [""]
    out.append("[나머지 컷]")
    out += normal[:60]
    return "\n".join(out)


def extract_feats(sources, product="", note=None, seed_text=""):
    """특징 3~4개 + 첫 줄 빈칸 재료(hook 슬롯, note["hook_slots"]). 호출 1회 — 슬롯을 따로 부르지 않는다."""
    prompt = "%s\n\n[제품] %s\n\n%s" % (FEATS_BRIEF, product or "(미상)", source_block(sources))
    if (seed_text or "").strip():
        prompt += "\n\n[씨앗 영상의 말 — hook 빈칸 재료는 여기서 먼저 찾아라]\n" + seed_text.strip()[:1200]
    out = _sg._call_json(prompt, FEATS_SCHEMA, note=note) or {}
    if note is not None:
        from shopping_shorts import story_hook
        note["hook_slots"] = story_hook.clean_slots(out.get("hook"))
    pts = [str(p).strip() for p in (out.get("seed_points") or []) if str(p).strip()]
    if note is not None:
        note["seed_points"] = pts
    feats = out.get("feats") or []
    for f in feats:
        f["_seed_points"] = pts          # pick_diff_feats의 코드 대조용(모델 표시 + 낱말 대조 둘 다 본다)
    return feats


# ★차별점 고르기(2026-09-26 사장님 "대본이 씨앗이랑 거의 똑같다 — 차별 포인트는 기능·특징·장점"; 노바 작가 방식
#   docs/nova_writer_script_2026-09-22.md: 씨앗 7줄 → 시안 18줄, 늘어난 건 씨앗에 없던 셀링포인트).
#   실측 work 28499a00008a: 영상 7개에서 특징 44개가 뽑혔는데 '제일 센 3개'만 남겨 둘이 씨앗이 이미 말한 것(유리컵 재사용…),
#   반전은 씨앗 문장("컵 때문에 샀다가 맛 때문에 또 산다")을 거의 그대로 썼다. 1인분·홈카페 컵 같은 새 특징은 버려졌다.
#   → 모델은 후보와 '씨앗 인용'만 내고 고르는 건 코드가 한다(근거가 셀 수 있는 숫자여야 설명된다):
#     새 특징(씨앗 인용 없음)을 **보여준 영상 수** 순(같으면 컷 수), 씨앗 특징은 고조1용으로 최대 1개.
#     반전 = 새 특징 1위(여러 제작자가 공통으로 보여준 셀링포인트) — 맨 뒤 번호.
DIFF_MIN_NEW = 2


def _feat_videos(f, seg_index):
    return len({(seg_index.get(c) or {}).get("vid") for c in (f.get("from_cuts") or []) if c in seg_index} - {None})


_DIFF_STOP = {"제품", "사용", "가능", "있음", "있는", "없이", "쉽게", "간편", "다른", "용도", "형태", "구성", "한번",
              "하나", "바로", "매우", "정말", "진짜", "특징", "기능", "장점", "효과", "개선", "제공", "적용", "완벽"}
_JOSA = re.compile(r"(으로|에서|에게|까지|부터|이나|이랑|처럼|보다|하고|으로도|로도|에도|과|와|이|가|을|를|은|는|에|의|도|로|만)$")


def _words(t):
    out = []
    for w in re.findall(r"[가-힣A-Za-z0-9]+", t or ""):
        w = _JOSA.sub("", w)
        w = re.sub(r"(한|하게|적인|스러운|로운|진|된|되는|하는|있는)$", "", w)
        if len(w) >= 2 and w not in _DIFF_STOP:
            out.append(w)
    return out


def _in_seed_points(f, seed_points):
    """모델이 인용을 빠뜨려도 코드가 한 번 더 본다 — 특징 **이름** 낱말이 씨앗 셀링포인트에 나오거나,
    설명(claim) 낱말이 2개 이상 나오면 '씨앗이 이미 말함'(09-26 실측: '간편한 세척' ↔ 씨앗 '식기세척기에도 사용')."""
    blob = " ".join(seed_points or [])
    if not blob:
        return False
    if any(w in blob for w in _words(f.get("name"))):
        return True
    return sum(1 for w in set(_words(f.get("claim"))) if w in blob) >= 2


def pick_diff_feats(cands, seg_index, n=4):
    """후보 → (고른 특징, 반전 번호 0-based | -1). 각 특징에 new(bool)·videos(int)를 단다.
    새 특징이 모자라면 있는 만큼만 쓰고 씨앗 특징으로 채운다 — 대본이 안 나오는 것보다 낫다(호출부가 note에 남긴다)."""
    rows = []
    for f in cands or []:
        f = dict(f)
        sp = f.pop("_seed_points", None) or []
        by_model = bool((f.get("seed_quote") or "").strip()) or (isinstance(f.get("seed_point"), int) and f["seed_point"] > 0)
        f["new"] = not (by_model or _in_seed_points(f, sp))
        f["videos"] = _feat_videos(f, seg_index)
        rows.append(f)
    rank = lambda f: (-f["videos"], -len(f.get("from_cuts") or []))
    new = sorted([f for f in rows if f["new"]], key=rank)
    old = sorted([f for f in rows if not f["new"]], key=rank)
    top = new[:1]                                  # 반전 = 새 특징 1위
    picked = old[:1] + new[1:n - 1]
    for f in old[1:]:
        if len(picked) + len(top) >= 3:
            break
        picked.append(f)
    picked += top
    return picked, (len(picked) - 1 if top else -1)


def _rotate(items, key, nth=0):
    """고조에 넣는 특징 순서를 회원·작업 키로 돌린다(2026-09-26) — 같은 씨앗·같은 재료라도 안마다·회원마다
    고조1이 다른 특징으로 시작해 본문이 같아지는 것을 막는다(실측: 같은 작업 A안·B안 미끼·고조가 거의 같은 문장)."""
    import zlib
    items = list(items or [])
    if len(items) < 2:
        return items
    k = (zlib.crc32(str(key).encode("utf-8")) + int(nth)) % len(items)
    return items[k:] + items[:k]


# ── 라이브 연결: 대본 먼저 → 컷은 뒤에 (관리자 스위치 story_writer_enabled) ──────
MIN_LINES = 5      # 훅·공개·고조 1칸(2줄+)·마무리 — 이보다 짧으면 모델이 칸을 비운 것이다


def _hook_angle(sp):
    """스타일 카드의 「제목 후킹」 틀(templates.title)이 있으면 첫 줄은 **그 틀의 빈칸만 채운다**(화면 카드와 같은 원천, 0순위-B).
    없으면 스타일 이름의 각도로 연다. — 2026-09-23 사장님: 훅이 썰 채널보다 약하다(실측 '과자 먹다 손 더러워지는 이유')."""
    t = ((sp.get("templates") or {}).get("title") or [""])[0] if isinstance(sp.get("templates"), dict) else ""
    if t and t.strip():
        return "첫 줄(hook)은 이 제목 틀의 빈칸만 이 제품에 맞게 채워서 쓴다: 「%s」" % t.strip()
    return "스타일 이름 「%s」이 말하는 각도로 첫 줄을 연다" % (sp.get("name") or "")


def _seed_style(seed_text):
    """자동 1안(씨앗 결) — 씨앗 영상의 **첫 줄 꼴**을 훅 몰드로 준다(2026-09-23 사장님 "씨앗의 대본 스타일도 참고가 되게").
    히트작 첫 줄은 그 채널의 제목 꼴이다 — 씨앗이 히트작이면 그 꼴이 곧 정답이다."""
    import re as _re
    first = _re.split(r"[.!?" + chr(10) + "]", (seed_text or "").strip())[0].strip()[:60]
    if len(first) < 6:
        return None
    # ★문장을 통째로 보여주면 베낀다(실측 09-23: 씨앗 "제조사도 전혀 예측 못한 사용처" → 훅 동일). 꼴만 뽑아 준다.
    shape = _re.sub(r"[가-힣A-Za-z0-9]+(도|들|이|가|을|를|의)\s", lambda m: "OO" + m.group(1) + " ", first)
    return {"name": "씨앗 결 이야기", "flow": "", "extra": "",
            "hook_angle": "첫 줄(hook)은 씨앗 첫 줄의 **꼴**을 빌린다 — 「%s」의 OO 자리를 이 제품의 사람·물건으로 바꿔 새 문장을 쓴다. 씨앗 문장을 그대로 쓰지 마라." % shape}


def style_hook_line(sp, slots, seed_text="", key="", nth=0):
    """고른 스타일의 제목 틀(templates.title) 중 **빈칸을 채울 수 있는 것**을 골라 완성 문장으로. 없으면 첫 틀에서
    못 채운 빈칸 낱말만 빼고 쓴다(2026-09-26 사장님 A안: 「OO의 정체」를 골랐는데 은행 꼴 "개발자도 예상 못한…"이 나왔다 —
    그 틀 "{나라} 천재가…"는 나라가 없으면 후보에서 빠지고, 은행이 스타일을 안 보고 다른 꼴을 골랐다). 틀이 없으면 None."""
    tpl = sp.get("templates") if isinstance(sp.get("templates"), dict) else {}
    titles = [t for t in (tpl.get("title") or []) if isinstance(t, str) and t.strip()]
    if not titles:
        return None
    from shopping_shorts import story_hook
    cands = story_hook.candidates(slots or {}, seed_text, molds=titles)
    if cands:
        import zlib
        return cands[(zlib.crc32(str(key).encode("utf-8")) + int(nth)) % len(cands)][1]
    # 채울 틀이 없으면 None — 모델이 틀의 빈칸을 제품에 맞게 채운다(_hook_angle). 빈칸을 빼 버리면
    # "예상 못한 미친 활용법"처럼 누가 놀랐는지가 빠진 약한 첫 줄이 된다(09-26 비교 실측).
    return None


def style_land_lines(sp):
    tpl = sp.get("templates") if isinstance(sp.get("templates"), dict) else {}
    return [t.strip() for t in (tpl.get("land") or []) if isinstance(t, str) and t.strip() and "{" not in t]


def _style_of(sp, slots=None, seed_text="", key="", nth=0):
    """고객이 고른 스타일(스파인) → write()의 style.
    ★첫 줄·마무리는 **스타일이 정한다**(2026-09-26 A안) — 은행(story_hook)은 자동 1안(씨앗 결)에만 쓴다."""
    hook = style_hook_line(sp, slots, seed_text, key, nth)
    lands = style_land_lines(sp)
    extra = ""
    if lands:
        extra = "closing(마무리)은 **이 중 하나를 그대로** 쓴다: " + " / ".join("「%s」" % x for x in lands)
    return {"name": sp.get("name") or "",
            "flow": " → ".join(str(r) for r in (sp.get("beat_roles") or [])),
            # 채울 틀이 없으면 틀의 빈칸을 모델에게 맡기지 않는다(09-26 실측: 권위자 자리에 "천재의 발명품도…"를 넣었다) —
            # 스타일 이름의 각도로만 연다.
            "hook_angle": (("첫 줄(hook)은 **이 문장을 그대로** 쓴다: 「%s」" % hook) if hook
                           else "스타일 이름 「%s」이 말하는 각도로 첫 줄을 연다" % (sp.get("name") or "")),
            "extra": extra, "hook_line": hook, "lands": lands}


def _enforce_style(lines, style):
    """모델이 스타일의 첫 줄·마무리를 안 따랐으면 코드가 바꿔 끼운다(검사가 아니라 결정 — 따를 수밖에 없게).
    첫 줄은 코드가 틀을 채운 문장이 있을 때만 강제한다(채울 재료가 없으면 스타일 이름 각도로 모델이 쓴 줄 그대로)."""
    if not style or not lines:
        return lines
    from shopping_shorts import script_gate
    h = style.get("hook_line")
    if h and lines[0].get("role") == "훅" and script_gate.norm(lines[0].get("text")) != script_gate.norm(h):
        lines[0] = dict(lines[0], text=h)
    lands = style.get("lands") or []
    if lands and lines[-1].get("role") == "마무리":
        if not any(script_gate.norm(x) in script_gate.norm(lines[-1].get("text")) for x in lands):
            lines[-1] = dict(lines[-1], text=lands[0])
    return lines


def _fit_length(lines, limit_secs):
    """대본이 한도를 넘으면 **고조 칸을 뒤에서부터 통째로** 뺀다(최소 1칸은 남긴다). 돌려준 값 = (줄, 뺀 칸 수).
    ★모델은 분량 지시를 안 지킨다(2026-09-22 실측, 목표 25초: 인스타 42·31·54초 / 썰 32·40·35초).
      칸을 얇게 다듬으면 설명문이 되므로 문장은 안 건드리고 칸 단위로만 뺀다 — 칸 하나는 그 자체로 완결이다."""
    from shopping_shorts import backbone_assemble as ba
    lines, dropped = list(lines), 0
    while sum(ba._secs(L["text"]) for L in lines) > limit_secs:
        escs = sorted({L["role"] for L in lines if L["role"].startswith("고조")}, key=lambda r: int(r[2:]))
        if len(escs) <= MIN_ESCALATIONS:      # ★고조2는 길이 때문에도 안 뺀다(2026-09-26 사장님 "무조건")
            break
        lines = [L for L in lines if L["role"] != escs[-1]]
        dropped += 1
    return lines, dropped


def _share_cuts(lines, bs, seg_index):
    """컷이 하나도 없는 줄에 **남는 컷을 나눠 준다**. 돌려준 값 = 끝내 빈 줄 번호들.
    ★assign_cuts는 앞 줄부터 '길이+여유+최소 2컷'을 채워 재료가 빠듯하면 뒤 줄이 빈손이 된다
      (2026-09-22 실측 job 13d4cab55fba: 쓸 컷 27개를 9줄 중 8줄이 다 쓰고 마무리 줄 0컷).
      빈 줄은 3단계 채우기가 대본을 안 보고 메우므로, 넉넉한 줄에서 **빼도 대사 길이를 덮는 컷만** 옮긴다."""
    from shopping_shorts import backbone_assemble as ba

    def secs(s):
        return (seg_index.get(s) or {}).get("secs") or 0.0
    empty = []
    for i, b in enumerate(bs):
        if b and b.get("segs"):
            continue
        need, got = ba._secs(lines[i]["text"]), []
        while sum(secs(s) for s in got) < need:
            donors = [(len(d["segs"]), j) for j, d in enumerate(bs) if j != i and d and len(d.get("segs") or []) > 1
                      and sum(secs(s) for s in d["segs"][:-1]) >= ba._secs(lines[j]["text"])]
            if not donors:
                break
            j = max(donors)[1]
            got.append(bs[j]["segs"].pop())
        bs[i] = {"role": lines[i]["role"], "seg": got[0] if got else "", "segs": got}
        if not got:
            empty.append(i)
    return empty


def _drop_repeat_signal(lines, sigs):
    """모델이 직접 쓴 줄(반전·소감 등)이 **코드가 박은 신호어로 또 시작하면** 떼어 낸다 — 한 편에 "심지어"가 두 번 난다."""
    used = [s for s in sigs if s]
    for L in lines:
        if L.get("group", -1) != -1 or L["role"].startswith("고조") or L["role"] in ("대비", "반전"):   # 코드가 신호어를 박는 줄
            continue
        for s in used:
            if L["text"].startswith(s + " "):
                L["text"] = L["text"][len(s):].strip()
    return lines


# ★"~더라고요/~거든요/~는데요/~잖아요"가 빠져 있었다(2026-09-22 말맛 센서스 실측): 인스타 대표 어미(docstring에도
#   95~98%라 적어 놓고!)를 안 세어, 차량용 홀더 씨앗("더라고요"×3)이 존댓말 어절 2개로 잡혀 **썰(반말)로 써졌다**.
_POLITE_ENDS = r"(어요|아요|에요|예요|해요|세요|네요|죠|니다|니까|더라고요|더라구요|거든요|는데요|잖아요|고요|나요|까요|래요|대요|돼요|져요|봐요|줘요|워요|와요)"
_POLITE_WORD = re.compile(_POLITE_ENDS + r"[.!?~…]*$")
_POLITE_SPLIT = re.compile(_POLITE_ENDS + r"(?=[가-힣])")     # 어미 목록은 위 한 곳(0순위-B)


def seed_platform(seed_text):
    """씨앗의 결 → "ig"(존댓말 체험담) | "yt"(반말 썰). **어절 단위**로 센다.
    ★전사엔 문장부호가 거의 없다(실측 524자에 2개) — 문장으로 나눠 끝말을 보면 한 덩어리가 돼 판정이 무의미하다."""
    # ★자막을 이어 붙인 전사는 문장 사이 띄어쓰기가 없다("안 돼요저도 매번사실") → 어미 뒤에서 한 번 끊어 준다.
    #   히트작 1,116편 대조(2026-09-22): 인스타 존댓말 놓침 38→26, 썰 소개체 362편 오판 0.
    #   문턱(3개·3%)은 그대로 — 2개로 낮추면 놓침 16이 되지만 썰 소개체 12편이 인스타로 넘어간다.
    t = _POLITE_SPLIT.sub(r"\1 ", seed_text or "")
    ws = t.split()
    pol = sum(1 for w in ws if _POLITE_WORD.search(w))
    return "ig" if pol >= 3 and pol / max(1, len(ws)) >= 0.03 else "yt"


def _norm_text(t):
    return re.sub(r"\s+", "", str(t or ""))


def make_drafts(spines, job, seconds=25, job_id="", preset="short", seed_text="", seed_product=""):
    """(drafts, why) — app._backbone_drafts와 같은 계약(비면 why에 이유, 조용한 폴백 금지).

    자동 1안(씨앗 결 그대로) + 고른 스타일 1안. 모델 호출 = 특징 1회 + 안마다 1회.
    ★화면은 씨앗 영상을 안 쓴다(backbone_assemble.assemble과 같은 규칙, 2026-09-21 사장님).

    seed_text/seed_product (2026-09-26): **사용자가 2단계에서 고른 씨앗**의 원문·제품. 씨앗은 화면 재료에서
      빼기(useFootage=false) 때문에 job에 없어서, 종전엔 "job 안에서 가장 긴 한국어 글"이 씨앗 노릇을 했다 —
      실사고 work ea29430903d3: 고른 씨앗은 유튜브 썰(반말)인데 인스타 s5(존댓말 "여러분 다이소에서…")가 씨앗이
      되어 "씨앗 결 이야기"가 다이소 존댓말로 나왔다. 명시값이 오면 그것이 씨앗이고, 없으면 종전 규칙.
    """
    from shopping_shorts import backbone_assemble as ba
    srcs = ba.sources_from_extract((job or {}).get("extract") or {})
    if not srcs:
        return [], "재료 분석(extract)이 아직 없음"
    seed_text = (seed_text or "").strip()
    if len(seed_text) >= 60:
        seed_src = None
        seed_from = "explicit"
        # 고른 씨앗과 같은 글의 영상이 job에도 담겨 있으면 그건 화면에서 뺀다(씨앗 화면 금지 규칙 그대로)
        key = _norm_text(seed_text)
        vis = [s for s in srcs
               if _norm_text(s.get("full_text_ko") or s.get("full_text")) != key]
        product = (seed_product or "").strip()
    else:
        seed_src = ba.seed_source(srcs, (job or {}).get("backbone_main"))
        seed_text = ((seed_src or {}).get("full_text_ko") or (seed_src or {}).get("full_text") or "").strip()
        if len(seed_text) < 60:
            return [], "씨앗 영상의 말이 너무 짧음(%d자)" % len(seed_text)
        seed_from = "job:%s" % (seed_src.get("video_id") or "")
        vis = ba._drop_seed(srcs, seed_src)
        product = ((seed_src.get("source_brief") or {}).get("product") or "").strip()
    seg_index = ba._seg_index(vis)
    note = {}
    feats_cands = extract_feats(vis, product, note=note, seed_text=seed_text)
    if not feats_cands:
        return [], "특징을 못 뽑음(%s)" % (note.get("reason") or "빈 응답")
    hook_slots = note.get("hook_slots") or {}
    # 차별점: 새 특징 우선(영상 수 순)·반전 = 새 특징 1위 — pick_diff_feats 주석
    feats_all, _twist_i = pick_diff_feats(feats_cands, seg_index)
    _n_new = sum(1 for f in feats_all if f.get("new"))

    def _groups_out(fs):
        return {"product": product, "order": list(range(len(fs))), "alt_use": False,
                "groups": [{"name": f.get("name") or "", "claim": f.get("claim") or "",
                            "cuts": [c for c in (f.get("from_cuts") or []) if c in seg_index]}
                           for f in fs]}
    preset = preset if preset in LENGTH_PRESETS else "short"
    if preset != "short":
        seconds = LENGTH_PRESETS[preset]["seconds"]
    plans = [(None, seed_platform(seed_text))]
    for sp in (spines or [])[:1]:
        plans.append((sp, "yt" if sp.get("no_cta") else "ig"))
    backbone_vid = (seed_src or {}).get("video_id")
    drafts, whys = [], []
    for nth, (sp, plat) in enumerate(plans):
        name = (sp or {}).get("name") or "씨앗 결 이야기"
        n = {}
        # ★안마다 특징 순서를 돌린다(본문 다양화) — 컷 배정(groups_out)도 같은 순서로 만든다(줄의 group 번호가 이 목록을 가리킨다)
        #   반전 특징(맨 뒤)은 돌리지 않는다 — 반전 = 새 특징 1위가 안마다 흔들리면 근거가 사라진다.
        if _twist_i >= 0:
            feats = _rotate(feats_all[:-1], job_id or product, nth) + [feats_all[-1]]
        else:
            feats = _rotate(feats_all, job_id or product, nth)
        twist_n = len(feats) if _twist_i >= 0 else 0
        groups_out = _groups_out(feats)
        # ★고른 스타일이 있으면 첫 줄·마무리는 스타일이 정한다 — 첫 줄 꼴 은행은 자동 1안(씨앗 결)에만(2026-09-26 A안).
        #   종전엔 은행이 스타일 첫 줄 지시를 지웠다(write의 hook_angle="") → 「OO의 정체」를 골라도 "개발자도 예상 못한…".
        _style = _style_of(sp, hook_slots, seed_text, job_id or product, nth) if sp else _seed_style(seed_text)
        lines = write(product, seed_text[:1500], feats, platform=plat,
                      style=_style, key=job_id or product, nth=nth, note=n,
                      seconds=seconds, preset=preset, hook_slots=(hook_slots if (plat == "yt" and not sp) else None),
                      twist_n=twist_n, seed_points=note.get("seed_points") or [])
        if sp and plat == "yt":
            lines = _enforce_style(lines, _style)
        n["feats"] = [{"name": f.get("name"), "new": f.get("new"), "videos": f.get("videos"),
                       "cuts": [c for c in (f.get("from_cuts") or []) if c in seg_index]} for f in feats]
        n["twist_n"] = twist_n
        n["n_new"] = _n_new
        if len(lines) < MIN_LINES:
            whys.append("%s: 대본이 %d줄뿐(%s)" % (name, len(lines), n.get("reason") or "칸 빔"))
            continue
        # 한도 = 목표의 1.5배와 '쓸 수 있는 재료 화면 길이의 65%' 중 짧은 쪽 — 화면이 없는 말은 길어 봐야 빈 줄이 된다.
        #   65%의 근거(★job 13d4cab55fba 1건·재료 48.8초뿐이다 — 재료를 넓혀 다시 재라): 대본 31.8초 이하 4편은
        #   빈 줄 0, 33.3초 이상 5편은 빈 줄 1~4. 컷이 덩어리라(2초 대사에 4.8초 컷) 길이 합만큼은 못 쓴다.
        footage = sum(v["secs"] for v in seg_index.values() if v["secs"] >= ba.MIN_CUT_SECS)
        limit = float(seconds) * (1.25 if preset == "short" else 1.5)
        if LENGTH_PRESETS[preset]["cap_by_footage"]:
            limit = min(limit, footage * 0.65)
        lines, n["dropped_escalations"] = _fit_length(lines, limit)
        # ★AI 매칭(2026-09-22 사장님 "매칭은 AI가 해봐"): 줄 전체 + 컷 목록을 한 번에 주고 줄마다 고르게 한다(호출 1회).
        #   빈 줄이 남으면 그 줄만 코드 매칭(assign_cuts)이 채운다. AI가 아예 실패하면 전부 코드 매칭.
        from shopping_shorts import ai_match as _am
        _an = {}
        ai_bs = _am.match(lines, seg_index, backbone_vid, note=_an)
        bs, report = ba.assign_cuts(lines, groups_out, seg_index, backbone_vid)
        code_bs = [dict(b) for b in bs]                        # 코드 매칭 원본(근거 컷) — 아래 장면 고정이 쓴다
        if ai_bs:
            _used = {c for b in ai_bs for c in (b.get("segs") or [])}
            for i, b in enumerate(ai_bs):
                if b.get("segs"):
                    bs[i] = b
                else:                                          # AI가 비운 줄 = 코드 매칭 결과에서 안 겹치는 컷만
                    keep = [c for c in (bs[i].get("segs") or []) if c not in _used]
                    bs[i] = {"role": bs[i].get("role"), "seg": keep[0] if keep else "", "segs": keep}
                    _used.update(keep)
            n["matcher"] = "ai"
        else:
            n["matcher"] = "code(%s)" % (_an.get("reason") or "")
        # ★장면 고정(2026-09-26 사장님 "다른 소스에 나온 고조·반전 장면을 정말 쓰는지, 쓸 수밖에 없는 구조"):
        #   특징 번호가 붙은 줄(고조·반전)은 **그 특징의 근거 컷(from_cuts) 안에서만**. AI는 특징↔근거 컷을 모르고 골랐고,
        #   코드 매칭도 근거 컷이 모자라면 딴 컷을 채웠다(실측 비교: 근거 안 0/7·3/7) → **매칭 방식과 관계없이** 여기서 고정한다.
        #   근거 컷이 줄보다 적으면 같은 근거 컷을 이어 쓴다(구절 이어 틀기로 그 장면이 이어진다). 훅·미끼·공개·마무리는 그대로.
        _locked = 0
        for i, L in enumerate(lines):
            gi = L.get("group", -1)
            if not (isinstance(gi, int) and 0 <= gi < len(groups_out["groups"])):
                continue
            allowed = groups_out["groups"][gi]["cuts"]
            if allowed and not set(bs[i].get("segs") or []) <= set(allowed):
                keep = [c for c in (code_bs[i].get("segs") or []) if c in allowed] or allowed[:1]
                bs[i] = {"role": bs[i].get("role"), "seg": keep[0], "segs": keep}
                _locked += 1
        n["locked_lines"] = _locked
        n["no_cut_lines"] = _share_cuts(lines, bs, seg_index)     # 끝내 빈 줄 = 재료가 대본보다 짧다
        meta = {"product": product, "spine": {"id": (sp or {}).get("id"), "name": name},
                "groups": groups_out, "report": report, "note": n}
        d = ba.to_draft("\n".join(L["text"] for L in lines), bs, meta)
        d["made_by"] = "이야기작가"
        d["length_preset"] = preset
        d["auto_pick"] = sp is None
        d["platform"] = plat
        d["seed_from"] = seed_from          # 점검용: 씨앗이 고른 영상(explicit)인가 job 대체(job:vid)인가
        # ★작가 메모를 안에 남긴다(2026-09-26) — to_draft는 meta.note를 버려서 훅 판정·고조 재작성이 작동했는지
        #   감사(tools/story_hook_audit.py)가 볼 수 없었다("판정 작동: 없음"으로 보임).
        d["writer_note"] = {k: n.get(k) for k in ("hook_fix", "hook_retry", "escalation_retry", "matcher",
                                                  "no_cut_lines", "dropped_escalations", "diff_retry", "diff_left",
                                                  "locked_lines", "twist_n", "n_new") if n.get(k)}
        d["feats_meta"] = n.get("feats") or []    # 점검용: 특징별 새것 여부·영상 수·근거 컷(tools/script_diff 대조)
        d["line_groups"] = [L.get("group", -1) for L in lines]     # 점검용: 줄이 어느 재료에 걸렸나
        d["feat_names"] = [f.get("name") or "" for f in feats]
        drafts.append(d)
    return drafts, "; ".join(whys)
