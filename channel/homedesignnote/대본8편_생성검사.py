# -*- coding: utf-8 -*-
"""남은 8편 대본.json 생성 + 자체 검사(글자 수·토막 이어붙임·토막 ≤13자·고조 수)."""
import json, re, sys, os
ROOT = sys.argv[1]
OUT = os.path.join(ROOT, "channel")
P = "제품"; S = "유사"; M = "짤"

def chars(s):  # 공백 뺀 글자 수(문장부호 포함) — 작품1 총알람 260 계산과 같은 방식
    return len(s.replace(" ", ""))

def norm(s):
    return re.sub(r"[\s,.·?!]", "", s)

# line = (role, climax, text, tts or None, [(토막, 검색어, kind)])
HDN = dict(channel="homedesignnote", brand="잇썸홈",
           preset="channel/homedesignnote/preset/전체화면_가운데자막",
           voice={"name": "박창수", "voice_id": "tc_6059dad0b83880769a50502f"},
           cps=8.32, rule="재료 = 같은 제품 실영상만(짤·유사 0)")
EVN = dict(channel="재미썸홈", brand="재미썸홈",
           preset="channel/evenshopping/preset/숏템템플릿/manifest.json",
           voice={"name": "필재", "voice_id": "tc_68257f68bc6e3c161ab5078d"},
           cps=8.8, rule="재료 = 제품 실영상 + 유사·연상 영상 + 짤")

WORKS = []

# ───────────── 잇썸홈 ─────────────
WORKS.append(dict(base=HDN, dir="homedesignnote/작품2_나이키핸즈프리", topic="나이키 핸즈프리 운동화(Nike Go FlyEase)",
  facts={"편지": "2012년 뇌성마비 16세 Matthew Walzer가 나이키에 편지 → 디자이너 Tobie Hatfield 개발(dogonews·goodthingsguy 2021-02)",
         "시제품마다 학생 검사": "버전마다 Walzer에게 보내 확인(같은 기사)",
         "경첩": "bi-stable hinge — 열린 상태·닫힌 상태 둘 다 유지, 밟으면 닫힘(나이키 발표)",
         "뒤꿈치 킥스탠드": "kickstand heel — 반대 발로 뒤꿈치 눌러 벗음(나이키 발표)",
         "임산부·부모님 효도템": "사회 반응 과장(사장님 허용)"},
  lines=[
  ("훅", "①센 시작", "혼자 신발 신는 게 서러웠던 한 학생이 나이키에 편지 한 통을 보냈는데, 그걸 읽은 나이키가 손 안 대고 신는 신발을 만들어버렸대요.", None,
   [("혼자 신발 신는 게", "Nike FlyEase Matthew Walzer putting on shoes"), ("서러웠던 한 학생이", "Matthew Walzer Nike FlyEase story"), ("나이키에 편지 한 통을", "Matthew Walzer letter to Nike"),
    ("보냈는데", "Matthew Walzer letter Nike close up"), ("그걸 읽은 나이키가", "Nike FlyEase designer Tobie Hatfield"), ("손 안 대고", "Nike Go FlyEase hands free step in"),
    ("신는 신발을", "Nike Go FlyEase on feet"), ("만들어버렸대요", "Nike Go FlyEase product reveal")]),
  ("도입", None, "운동화 신을 때마다 쪼그려 앉아 뒤꿈치 구겨 넣는 거 귀찮잖아요.", None,
   [("운동화 신을 때마다", "Nike Go FlyEase vs regular sneaker putting on"), ("쪼그려 앉아", "Nike Go FlyEase review crouching tie shoes"), ("뒤꿈치 구겨 넣는 거", "Nike Go FlyEase review heel squash regular shoe"), ("귀찮잖아요", "Nike Go FlyEase review struggling shoes")]),
  ("도입(증거)", "②권위", "근데 나이키가 이거 하나에 몇 년을 갈아 넣으면서 시제품마다 그 학생한테 먼저 신겨봤다는데,", None,
   [("근데 나이키가", "Nike FlyEase Tobie Hatfield design"), ("이거 하나에 몇 년을", "Nike FlyEase prototype development"), ("갈아 넣으면서", "Nike FlyEase sketches prototypes"),
    ("시제품마다", "Nike FlyEase prototypes table"), ("그 학생한테 먼저", "Matthew Walzer wearing FlyEase"), ("신겨봤다는데", "Matthew Walzer testing Nike FlyEase")]),
  ("설명", "③진짜 핵심 반전", "진짜 핵심은 이건데, 밑창 가운데가 경첩처럼 꺾여 있어서 발 쑥 넣고 꾹 밟으면 신발이 알아서 착 닫혀요.", None,
   [("진짜 핵심은 이건데", "Nike Go FlyEase close up"), ("밑창 가운데가", "Nike Go FlyEase sole hinge close up"), ("경첩처럼 꺾여 있어서", "Nike Go FlyEase bistable hinge open"),
    ("발 쑥 넣고", "Nike Go FlyEase foot slide in"), ("꾹 밟으면", "Nike Go FlyEase step down"), ("신발이 알아서 착 닫혀요", "Nike Go FlyEase shoe closes slow motion")]),
  ("효과", "④심지어", "심지어 벗을 땐 반대쪽 발로 뒤꿈치만 툭 차면 끝이라 손 쓸 일이 아예 없더라고요.", None,
   [("심지어 벗을 땐", "Nike Go FlyEase taking off"), ("반대쪽 발로", "Nike Go FlyEase kickstand heel other foot"), ("뒤꿈치만 툭 차면", "Nike Go FlyEase kickstand heel step off"),
    ("끝이라", "Nike Go FlyEase shoe opens kickstand"), ("손 쓸 일이 아예", "Nike Go FlyEase hands free walking"), ("없더라고요", "Nike Go FlyEase hands free review")]),
  ("효과·행동유도", "⑤난리", "요즘엔 임산부들이랑 부모님 효도템으로 신발장마다 들여놓는다고 난리래요.", None,
   [("요즘엔 임산부들이랑", "Nike Go FlyEase pregnant woman"), ("부모님 효도템으로", "Nike Go FlyEase elderly"), ("신발장마다", "Nike Go FlyEase pair on shelf"), ("들여놓는다고 난리래요", "Nike Go FlyEase colorways lineup")]),
  ]))

WORKS.append(dict(base=HDN, dir="homedesignnote/작품3_총알람", topic="총 쏘는 알람시계(반다이 Gun O'Clock 류)",
  facts={"적외선 총·과녁 가운데 불": "알람 시 과녁이 올라오고 빛나는 가운데를 맞혀야 꺼짐(GIGAZINE 2008-09-26)",
         "어려움 모드 5발": "보통 1발, 어려움 모드 5발(GIGAZINE 2008-09-26)",
         "시간 재는 사격 게임 모드": "타임트라이얼 모드(GIGAZINE·TechCrunch 2008)",
         "알람 끄기 장인": "재미 단어(설명서 R3 예)",
         "아빠들이 먼저 일어나 총 잡음": "사회 반응 과장(사장님 허용)",
         "쓰지 않은 것": "움직이는 과녁(재료 영상·기사 모두 확인 안 됨) · 반다이·누워서 못 맞힘·명중 시 쓰러짐(재미썸홈 작품1과 겹침)"},
  lines=[
  ("훅", "①센 시작", "알람 끄기 장인들 깨우다 지쳐버린 일본 장난감 회사가 아예 알람시계에 장난감 총을 달아버렸대요.", None,
   [("알람 끄기 장인들", "gun alarm clock review"), ("깨우다 지쳐버린", "gun alarm clock ringing bed"), ("일본 장난감 회사가", "Gun O'Clock box"),
    ("아예 알람시계에", "gun alarm clock close up"), ("장난감 총을 달아버렸대요", "gun alarm clock infrared gun")]),
  ("도입", None, "알람 울리면 눈도 안 뜨고 손만 뻗어서 끄는 거 다들 한 번씩 해봤잖아요.", None,
   [("알람 울리면", "gun alarm clock alarm ringing"), ("눈도 안 뜨고", "gun alarm clock sleeping in bed"), ("손만 뻗어서 끄는 거", "gun alarm clock reaching hand"), ("다들 한 번씩 해봤잖아요", "gun alarm clock review bed")]),
  ("도입(증거)", "②숫자", "근데 이거 어려움 모드로 맞춰두면 과녁을 다섯 발이나 맞혀야 꺼진다는데,", None,
   [("근데 이거 어려움 모드로", "gun alarm clock settings mode"), ("맞춰두면", "gun alarm clock setting buttons"), ("과녁을 다섯 발이나", "gun alarm clock shooting multiple shots"), ("맞혀야 꺼진다는데", "gun alarm clock hit target")]),
  ("설명", "③진짜 핵심 반전", "진짜 핵심은 이건데, 알람이 울리면 과녁 가운데에 불이 들어오고 총으로 거길 정확히 맞혀야만 소리가 뚝 그쳐요.", None,
   [("진짜 핵심은 이건데", "gun alarm clock close up"), ("알람이 울리면", "gun alarm clock target pops up"), ("과녁 가운데에", "gun alarm clock target center"), ("불이 들어오고", "gun alarm clock target light"),
    ("총으로 거길 정확히", "gun alarm clock aiming"), ("맞혀야만", "gun alarm clock shooting target"), ("소리가 뚝 그쳐요", "gun alarm clock alarm stops")]),
  ("효과", "④심지어", "심지어 알람 말고도 누가 더 빨리 맞히나 시간 재는 사격 게임 모드까지 들어 있어서", None,
   [("심지어 알람 말고도", "gun alarm clock game mode"), ("누가 더 빨리 맞히나", "gun alarm clock time trial"), ("시간 재는", "gun alarm clock timer display"), ("사격 게임 모드까지", "gun alarm clock shooting game"), ("들어 있어서", "gun alarm clock playing")]),
  ("효과·행동유도", "⑤난리", "요즘엔 애들보다 아빠들이 아침마다 먼저 일어나서 총부터 잡는다고 난리래요.", None,
   [("요즘엔 애들보다", "gun alarm clock kids"), ("아빠들이 아침마다", "gun alarm clock man morning"), ("먼저 일어나서", "gun alarm clock wake up"), ("총부터 잡는다고 난리래요", "gun alarm clock holding gun")]),
  ]))

WORKS.append(dict(base=HDN, dir="homedesignnote/작품4_아이스큐브", topic="스테인리스 아이스큐브(냉매 젤 충전 스테인리스 얼음)",
  facts={"냉매 젤": "속에 밀봉 젤(판매처 설명 다수: Sharper Image 등)",
         "녹지 않음·재사용": "얼음 아님 → 녹지 않음, 씻어 다시 냉동(판매처 설명)",
         "돌 얼려 넣던 게 시작": "위스키 스톤 유래 소문(전언 '~라는데', 사장님 소문 허용)",
         "홈카페 난리": "사회 반응 과장(사장님 허용)",
         "쓰지 않은 것": "'영국에서 처음 나와 떼돈'(초안) — 출처 없음, 뺌"},
  lines=[
  ("훅", "①센 시작", "비싼 위스키에 얼음 넣었다가 물 탄 맛 돼서 속상했던 위스키 덕후들이 결국 얼음 대신 쇠로 만든 얼음을 넣기 시작했대요.", None,
   [("비싼 위스키에", "whiskey glass pour stainless steel ice cubes"), ("얼음 넣었다가", "ice cube melting whiskey"), ("물 탄 맛 돼서", "melted ice watered down drink"), ("속상했던 위스키 덕후들이", "whiskey stainless steel ice cubes review"),
    ("결국 얼음 대신", "stainless steel ice cubes set"), ("쇠로 만든 얼음을", "stainless steel ice cubes close up"), ("넣기 시작했대요", "stainless steel ice cube drop into whiskey slow motion")]),
  ("도입", None, "얼음 넣으면 금방 녹아서 마지막 한 모금은 맹물 맛 나잖아요.", None,
   [("얼음 넣으면", "stainless steel ice cubes vs ice"), ("금방 녹아서", "ice melting in glass comparison"), ("마지막 한 모금은", "stainless steel ice cubes vs ice test"), ("맹물 맛 나잖아요", "melted ice water in glass")]),
  ("도입(유래)", "②유래", "원래는 스코틀랜드에서 돌을 차갑게 얼려서 술에 넣던 게 시작이라는데,", "원래는 스코틀랜드에서 돌을 차갑게 얼려서 술에 넣던 게 시작이라는데,",
   [("원래는 스코틀랜드에서", "stainless steel ice cubes whiskey bar"), ("돌을 차갑게 얼려서", "stainless steel ice cubes freezer"), ("술에 넣던 게", "stainless steel ice cube whiskey glass"), ("시작이라는데", "stainless steel ice cubes whiskey review")]),
  ("설명", "③진짜 핵심 반전", "진짜 핵심은 이건데, 속에 냉매 젤이 꽉 차 있어서 얼려두면 녹지도 않고 음료를 끝까지 차갑게 잡아준대요.", None,
   [("진짜 핵심은 이건데", "stainless steel ice cube close up"), ("속에 냉매 젤이", "stainless steel ice cube gel inside"), ("꽉 차 있어서", "stainless steel ice cube cut open"),
    ("얼려두면", "stainless steel ice cubes freezer take out"), ("녹지도 않고", "stainless steel ice cubes vs ice melting"), ("음료를 끝까지", "stainless steel ice cubes drink"), ("차갑게 잡아준대요", "stainless steel ice cubes frost cold")]),
  ("효과", "④심지어", "심지어 다 마시고 물에 헹궈서 다시 냉동실에 넣으면 끝이라 얼음틀 채울 일이 사라지더라고요.", None,
   [("심지어 다 마시고", "stainless steel ice cubes tongs take out"), ("물에 헹궈서", "stainless steel ice cubes rinse"), ("다시 냉동실에 넣으면", "stainless steel ice cubes put in freezer"), ("끝이라", "stainless steel ice cubes storage box"), ("얼음틀 채울 일이", "ice cube tray"), ("사라지더라고요", "stainless steel ice cubes reusable")]),
  ("효과·행동유도", "⑤난리", "요즘엔 홈카페 하는 분들까지 아이스 라떼 밍밍해지는 거 막는다고 난리래요.", "요즘엔 홈카페 하는 분들까지 아이스 라떼 밍밍해지는 거 막는다고 난리래요.",
   [("요즘엔 홈카페", "home cafe iced coffee stainless steel ice cubes"), ("하는 분들까지", "stainless steel ice cubes coffee"), ("아이스 라떼", "stainless steel ice cubes iced latte"), ("밍밍해지는 거 막는다고", "stainless steel ice cubes iced coffee"), ("난리래요", "stainless steel ice cubes drink pour")]),
  ]))

WORKS.append(dict(base=HDN, dir="homedesignnote/작품5_옥수수커터", topic="옥수수 알 커터(원형 칼날 corn stripper)",
  facts={"미국 요리 프로그램 7개 실험": "America's Test Kitchen 옥수수 커터 7종 시험(americastestkitchen.com equipment_reviews/2316)",
         "원형 칼날 위→아래": "원형 corn stripper 사용법(판매·리뷰 영상에서 재료 단계 확인)",
         "3초·스무 개": "결과 과장(사장님 허용)",
         "쓰지 않은 것": "'미국 주부가 만들었다'(초안) — 출처 없음 → '미국 사람들'(일반)로"},
  lines=[
  ("훅", "①센 시작", "옥수수 삶아놓고 알 하나하나 떼다 손톱이 남아나질 않던 미국 사람들이 결국 옥수수를 한 방에 털어버리는 칼을 만들어버렸대요.", None,
   [("옥수수 삶아놓고", "boiled corn on the cob pot"), ("알 하나하나 떼다", "removing corn kernels by hand"), ("손톱이 남아나질 않던", "peeling corn kernels fingers"), ("미국 사람들이 결국", "corn stripper review"),
    ("옥수수를 한 방에", "corn stripper one stroke"), ("털어버리는 칼을", "round corn stripper tool close up"), ("만들어버렸대요", "corn kernel stripper product")]),
  ("도입", None, "옥수수 알 하나씩 떼다 보면 손목은 시큰거리고 하루가 다 가잖아요.", None,
   [("옥수수 알 하나씩", "removing corn kernels one by one"), ("떼다 보면", "picking corn kernels slow"), ("손목은 시큰거리고", "corn stripper review hand"), ("하루가 다 가잖아요", "pile of corn cobs kitchen")]),
  ("도입(증거)", "②숫자·권위", "근데 미국 요리 프로그램에서 이런 옥수수 칼만 일곱 개를 놓고 실험까지 했다는데,", None,
   [("근데 미국", "corn stripper review kitchen"), ("요리 프로그램에서", "corn stripper test kitchen"), ("이런 옥수수 칼만", "corn strippers comparison"), ("일곱 개를 놓고", "corn stripper tools lineup"), ("실험까지 했다는데", "corn stripper test review")]),
  ("설명", "③진짜 핵심 반전", "진짜 핵심은 이건데, 옥수수 세워놓고 동그란 칼날을 위에서 쭉 내리기만 하면 알이 한 줄씩 통째로 우수수 떨어져요.", None,
   [("진짜 핵심은 이건데", "round corn stripper close up"), ("옥수수 세워놓고", "corn cob standing upright cutting board"), ("동그란 칼날을", "round corn stripper blade ring"),
    ("위에서 쭉 내리기만 하면", "round corn stripper push down cob"), ("알이 한 줄씩 통째로", "corn kernels strips falling"), ("우수수 떨어져요", "corn kernels falling slow motion")]),
  ("효과", "④심지어", "심지어 한 통 까는 데 3초면 끝이라 스무 개를 까도 손목이 멀쩡하더라고요.", "심지어 한 통 까는 데 삼 초면 끝이라 스무 개를 까도 손목이 멀쩡하더라고요.",
   [("심지어 한 통 까는 데", "corn stripper fast"), ("3초면 끝이라", "corn stripper seconds"), ("스무 개를 까도", "corn stripper many cobs"), ("손목이 멀쩡하더라고요", "corn stripper easy one hand")]),
  ("효과·행동유도", "⑤난리", "옥수수 철만 되면 엄마들 사이에서 이거 하나로 손목 살렸다고 난리래요.", None,
   [("옥수수 철만 되면", "fresh corn harvest"), ("엄마들 사이에서", "corn stripper kitchen mom"), ("이거 하나로", "round corn stripper product"), ("손목 살렸다고 난리래요", "bowl full of corn kernels")]),
  ]))

# ───────────── 재미썸홈 (이븐쇼핑 뼈대) ─────────────
WORKS.append(dict(base=EVN, dir="evenshopping/작품2_식기세척기", topic="싱크대 매립형 식기세척기(FOTILE)",
  title_lines=["웍 설거지에 지친", "중국 천재의 발명품"], bodyTitle="웍 설거지에 지친 중국 천재의 발명품?",
  facts={"냄비까지": "접시·냄비·채소 세척(CHEAA 2017)",
         "40개 도시 1,000가구": "2011년부터 개발팀 40개 도시 1,000여 가구 방문, 요리 전 과정 관찰(CHEAA·IDEO)",
         "세계 최초": "2015년 세계 최초 싱크대 식기세척기(회사 주장, China Daily·CHEAA)",
         "8달 만에 30%": "출시 8개월 만에 중국 시장 30%(IDEO 사례 — 회사 쪽 주장)",
         "맞벌이 이혼 막는 싱크대": "사회 반응 과장(사장님 허용)",
         "쓰지 않은 것": "허리·수백만 대·초음파 농약·신혼부부 주방공사(잇썸홈 작품1과 겹침)"},
  hype={"①센 시작": "지친 중국 천재 … 떼돈 번", "②권위": "세계 최초로 … 이 회사", "③진짜 핵심 반전": "출시 여덟 달 만에 30%", "④심지어": "40개 도시 천 가구", "⑤~까지 난리": "이혼 막는 싱크대로 난리라고"},
  lines=[
  ("title", None, "기름 범벅 웍 설거지하다 지친 중국 천재가 만들어 떼돈 번 싱크대의 정체.", None,
   [("기름 범벅 웍", "greasy wok washing sink", S), ("설거지하다 지친", "tired washing dishes sink", S), ("중국 천재가 만들어", "FOTILE sink dishwasher", P), ("떼돈 번 싱크대의 정체", "money rain meme", M)]),
  ("bait", None, "최근 맞벌이 커플들 사이에서 바이럴이 터지며 논란인 싱크대가 있는데,", None,
   [("최근 맞벌이 커플들", "couple kitchen after work tired", S), ("사이에서", "couple arguing dishes", S), ("바이럴이 터지며", "phone scrolling viral", S), ("논란인 싱크대가 있는데", "FOTILE in sink dishwasher closed lid", P)]),
  ("reveal", None, "이건 바로 싱크대 속 식기세척기.", None,
   [("이건 바로", "surprised gasp meme", M), ("싱크대 속 식기세척기", "FOTILE in sink dishwasher open lid", P)]),
  ("solve", None, "이게 말도 안 되는 게 기존 식기세척기는 접시만 넣었지만 이건 기름 범벅 냄비까지 통째로 넣고 돌린다는 거.", None,
   [("이게 말도 안 되는 게", "shocked face meme", M), ("기존 식기세척기는", "regular dishwasher rack plates", S), ("접시만 넣었지만", "loading plates dishwasher", S),
    ("이건 기름 범벅 냄비까지", "FOTILE sink dishwasher pot inside", P), ("통째로 넣고 돌린다는 거", "FOTILE sink dishwasher washing spray", P)]),
  ("more", None, "심지어 개발팀이 중국 40개 도시 천 가구를 찾아가서 밥하는 걸 따라다니며 만들었다는데,", "심지어 개발팀이 중국 사십 개 도시 천 가구를 찾아가서 밥하는 걸 따라다니며 만들었다는데,",
   [("심지어 개발팀이", "engineers design team meeting", S), ("중국 40개 도시", "China city skyline aerial", S), ("천 가구를 찾아가서", "apartment buildings China", S),
    ("밥하는 걸", "Chinese home cooking wok", S), ("따라다니며 만들었다는데", "FOTILE dishwasher R&D lab", P)]),
  ("more2", None, "세계 최초로 싱크대랑 식기세척기를 하나로 합친 게 바로 이 회사라고.", None,
   [("세계 최초로", "first place trophy meme", M), ("싱크대랑 식기세척기를", "FOTILE in sink dishwasher top view", P), ("하나로 합친 게", "FOTILE sink dishwasher installation", P), ("바로 이 회사라고", "FOTILE showroom", P)]),
  ("twist", None, "근데 진짜 충격적인 포인트는 출시 여덟 달 만에 중국 시장 점유율 30%를 먹어버렸다고.", "근데 진짜 충격적인 포인트는 출시 여덟 달 만에 중국 시장 점유율 삼십 퍼센트를 먹어버렸다고.",
   [("근데 진짜", "jaw drop meme", M), ("충격적인 포인트는", "FOTILE sink dishwasher close up", P), ("출시 여덟 달 만에", "calendar pages flipping", S), ("중국 시장 점유율", "FOTILE store display", P), ("30%를 먹어버렸다고", "stonks meme", M)]),
  ("land", None, "그래서 요즘엔 설거지 당번 정하다 싸우던 집들마다 이혼 막는 싱크대로 난리라고.", None,
   [("그래서 요즘엔", "FOTILE sink dishwasher kitchen", P), ("설거지 당번 정하다", "rock paper scissors couple", S), ("싸우던 집들마다", "couple arguing kitchen", S),
    ("이혼 막는 싱크대로", "FOTILE sink dishwasher clean dishes", P), ("난리라고", "crowd cheering meme", M)]),
  ]))

WORKS.append(dict(base=EVN, dir="evenshopping/작품3_나이키핸즈프리", topic="나이키 핸즈프리 운동화(Nike Go FlyEase)",
  title_lines=["찍찍이까지 다 버린", "나이키 천재의 신발"], bodyTitle="찍찍이까지 다 버린 나이키 천재의 신발?",
  facts={"끈·지퍼·찍찍이·다이얼 실험": "개발 중 벨크로·지퍼·케이블 다이얼 시험(goodthingsguy·wearemitu 2021)",
         "접힌 채 서 있음": "bi-stable hinge 열린 상태 유지, 안 신을 땐 클로그 모양으로 받쳐 섬(stirworld)",
         "르브론 농구화에서 힌트": "르브론 제임스와 만든 Zoom Soldier에서 영감(goodthingsguy)",
         "밴드가 당겨지며 닫힘": "midsole tensioner(나이키 발표)",
         "초대받은 회원만": "2021-02 출시 때 일부 나이키 회원 초대 판매(나이키 발표 — 재료 단계에서 기사 한 번 더 확인)",
         "출근 직장인 난리": "사회 반응 과장(사장님 허용)",
         "쓰지 않은 것": "편지 이야기·뒤꿈치 차서 벗기·임산부/부모님(잇썸홈 작품2와 겹침)"},
  hype={"①센 시작": "실험하다 지친 나이키 천재 … 떼돈 번", "②권위": "르브론 제임스 농구화", "③진짜 핵심 반전": "초대받은 회원만", "④심지어": "심지어 이 아이디어가", "⑤~까지 난리": "직장인들까지 … 난리라고"},
  lines=[
  ("title", None, "끈, 지퍼, 찍찍이까지 실험하다 지친 나이키 천재가 만들어 떼돈 번 신발의 정체.", None,
   [("끈 지퍼", "tying shoelaces close up", S), ("찍찍이까지", "velcro shoe strap close up", S), ("실험하다 지친", "tired designer desk", S), ("나이키 천재가 만들어", "Nike Go FlyEase", P), ("떼돈 번 신발의 정체", "money rain meme", M)]),
  ("bait", None, "최근 출근길 직장인들 사이에서 바이럴이 터지며 논란인 운동화가 있는데,", None,
   [("최근 출근길", "morning commute crowd street", S), ("직장인들 사이에서", "office worker rushing shoes", S), ("바이럴이 터지며", "phone scrolling viral", S), ("논란인 운동화가 있는데", "Nike Go FlyEase pair", P)]),
  ("reveal", None, "이건 바로 손 안 대고 신는 나이키 운동화.", None,
   [("이건 바로", "surprised gasp meme", M), ("손 안 대고 신는", "Nike Go FlyEase hands free step in", P), ("나이키 운동화", "Nike Go FlyEase product shot", P)]),
  ("solve", None, "이게 말도 안 되는 게 신발이 반으로 접힌 채로 입 쩍 벌리고 서 있어서 발만 쑥 밀어 넣으면 된다는 거.", None,
   [("이게 말도 안 되는 게", "shocked face meme", M), ("신발이 반으로 접힌 채로", "Nike Go FlyEase open position", P), ("입 쩍 벌리고 서 있어서", "Nike Go FlyEase kickstand open on floor", P), ("발만 쑥", "Nike Go FlyEase foot slide in", P), ("밀어 넣으면 된다는 거", "Nike Go FlyEase step in slow motion", P)]),
  ("more", None, "심지어 이 아이디어가 르브론 제임스 농구화에서 힌트를 얻은 거라는데,", None,
   [("심지어 이 아이디어가", "lightbulb idea meme", M), ("르브론 제임스", "LeBron James basketball dunk", S), ("농구화에서", "Nike Zoom Soldier basketball shoe", S), ("힌트를 얻은 거라는데", "Nike FlyEase design sketch", P)]),
  ("more2", None, "발이 들어가는 순간 감싼 밴드가 탁 당겨지면서 저절로 닫힌다고.", None,
   [("발이 들어가는 순간", "Nike Go FlyEase foot entering", P), ("감싼 밴드가", "Nike Go FlyEase tensioner band close up", P), ("탁 당겨지면서", "Nike Go FlyEase closing", P), ("저절로 닫힌다고", "Nike Go FlyEase closed on foot", P)]),
  ("twist", None, "근데 진짜 충격적인 포인트는 처음 나왔을 땐 돈이 있어도 못 사고 초대받은 회원만 살 수 있었다고.", None,
   [("근데 진짜", "jaw drop meme", M), ("충격적인 포인트는", "Nike Go FlyEase close up", P), ("처음 나왔을 땐", "Nike Go FlyEase launch", P), ("돈이 있어도 못 사고", "sold out sign store", S),
    ("초대받은", "Nike app phone screen", S), ("회원만 살 수 있었다고", "Nike Go FlyEase box unboxing", P)]),
  ("land", None, "그래서 요즘엔 신발 신다 지각할 일 없다고 출근 전쟁 치르는 직장인들까지 장만한다고 난리라고.", None,
   [("그래서 요즘엔", "morning alarm rush", S), ("신발 신다 지각할 일", "late running to work", S), ("없다고", "Nike Go FlyEase walking out door", P), ("출근 전쟁 치르는", "crowded subway commute", S),
    ("직장인들까지", "office worker walking sneakers", S), ("장만한다고", "Nike Go FlyEase unboxing", P), ("난리라고", "crowd cheering meme", M)]),
  ]))

WORKS.append(dict(base=EVN, dir="evenshopping/작품4_아이스큐브", topic="스테인리스 아이스큐브(냉매 젤 충전)",
  title_lines=["얼음 녹아 답답했던", "주방 천재의 발명품"], bodyTitle="얼음 녹아 답답했던 주방 천재의 발명품?",
  facts={"숟가락과 같은 스테인리스": "304(식기 등급) 스테인리스(판매처 설명)",
         "물이 안 생김": "얼음이 아니라 녹지 않음(판매처 설명)",
         "속에 젤": "밀봉 젤, 냉동실 보관(판매처 설명)",
         "콜라·맥주·와인": "모든 음료용(판매처 설명)",
         "바텐더들이 몰래 쓴다": "소문(전언 '~라고', 사장님 허용)",
         "국가": "발명 국가·인물 출처 없음 → '주방 천재'로 두고 나라를 붙이지 않음",
         "쓰지 않은 것": "돌 얼려 넣던 유래·씻어 재냉동·홈카페(잇썸홈 작품4와 겹침)"},
  hype={"①센 시작": "답답했던 주방 천재 … 떼돈 번", "②권위": "숟가락이랑 똑같은 스테인리스", "③진짜 핵심 반전": "바텐더들까지 몰래", "④심지어": "속에 차가운 젤", "⑤~까지 난리": "캠핑족들 사이에서 난리라고"},
  lines=[
  ("title", None, "술 마시다 얼음 녹는 게 답답했던 주방 천재가 만들어 떼돈 번 얼음의 정체.", None,
   [("술 마시다", "whiskey glass bar drinking", S), ("얼음 녹는 게 답답했던", "ice melting glass timelapse", S), ("주방 천재가 만들어", "stainless steel ice cubes set", P), ("떼돈 번 얼음의 정체", "money rain meme", M)]),
  ("bait", None, "최근 홈술족 사이에서 바이럴이 터지며 논란인 얼음이 있는데,", None,
   [("최근 홈술족", "drinking at home sofa", S), ("사이에서", "home bar drinks night", S), ("바이럴이 터지며", "phone scrolling viral", S), ("논란인 얼음이 있는데", "stainless steel ice cubes close up", P)]),
  ("reveal", None, "이건 바로 영원히 안 녹는 쇠 얼음.", None,
   [("이건 바로", "surprised gasp meme", M), ("영원히 안 녹는 쇠 얼음", "stainless steel ice cubes drop into glass", P)]),
  ("solve", None, "이게 말도 안 되는 게 숟가락이랑 똑같은 스테인리스라 아무리 담가놔도 물이 한 방울도 안 생긴다는 거.", None,
   [("이게 말도 안 되는 게", "shocked face meme", M), ("숟가락이랑 똑같은", "stainless steel spoons", S), ("스테인리스라", "stainless steel ice cubes metal shine", P), ("아무리 담가놔도", "stainless steel ice cubes in drink", P), ("물이 한 방울도", "stainless steel ice cubes vs ice melting test", P), ("안 생긴다는 거", "stainless steel ice cubes dry glass", P)]),
  ("more", None, "심지어 겉은 쇠인데 속에 차가운 젤이 숨어 있어서 냉동실에 넣어두기만 하면 꽁꽁 얼어붙는데,", None,
   [("심지어 겉은 쇠인데", "stainless steel ice cube in hand", P), ("속에 차가운 젤이", "stainless steel ice cube gel inside", P), ("숨어 있어서", "stainless steel ice cube cut open", P), ("냉동실에", "opening freezer door", S), ("넣어두기만 하면", "stainless steel ice cubes freezer", P), ("꽁꽁 얼어붙는데", "frost frozen ice cubes", P)]),
  ("more2", None, "위스키뿐 아니라 콜라랑 맥주, 와인까지 다 된다고.", None,
   [("위스키뿐 아니라", "stainless steel ice cubes whiskey", P), ("콜라랑 맥주", "stainless steel ice cubes soda beer", P), ("와인까지 다 된다고", "stainless steel ice cubes wine glass", P)]),
  ("twist", None, "근데 진짜 충격적인 포인트는 마지막 한 모금까지 첫 모금 맛 그대로라 바텐더들까지 비싼 술 지키려고 몰래 쓴다고.", None,
   [("근데 진짜", "jaw drop meme", M), ("충격적인 포인트는", "stainless steel ice cube splash slow motion", P), ("마지막 한 모금까지", "last sip drink glass", S), ("첫 모금 맛 그대로라", "whiskey tasting sip", S),
    ("바텐더들까지", "bartender bar counter", S), ("비싼 술 지키려고", "expensive whiskey bottle pour", S), ("몰래 쓴다고", "stainless steel ice cubes bar", P)]),
  ("land", None, "그래서 요즘엔 캠핑 갈 때 얼음 한 봉지 대신 이거 한 통 챙긴다고 캠핑족들 사이에서 난리라고.", None,
   [("그래서 요즘엔", "stainless steel ice cubes box set", P), ("캠핑 갈 때", "camping tent outdoor", S), ("얼음 한 봉지 대신", "bag of ice", S), ("이거 한 통 챙긴다고", "stainless steel ice cubes storage case", P), ("캠핑족들 사이에서", "friends camping drinks", S), ("난리라고", "crowd cheering meme", M)]),
  ]))

WORKS.append(dict(base=EVN, dir="evenshopping/작품5_옥수수커터", topic="옥수수 알 커터(원형 칼날 corn stripper)",
  title_lines=["옥수수 까다 현타 온", "주방 천재의 발명품"], bodyTitle="옥수수 까다 현타 온 주방 천재의 발명품?",
  facts={"링 칼날에 끼워 밀기": "원형 corn stripper 사용법(재료 단계에서 영상 확인)",
         "40년도 더 전 특허": "US4402137 'Single element corn ear stripper'(1983 등록, Google Patents)",
         "생옥수수·삶은 옥수수": "ATK 시험이 생 5·삶은 5개로 시험(americastestkitchen.com)",
         "얼려두고 1년 내내": "쓰임 과장(사장님 허용) — 기능 아님",
         "국가": "발명 인물 출처 없음 → '주방 천재'로",
         "쓰지 않은 것": "요리 프로그램 7개 실험·3초·손톱·손목 살렸다(잇썸홈 작품5와 겹침)"},
  hype={"①센 시작": "현타 온 주방 천재 … 떼돈 번", "②권위": "40년도 더 전에 특허", "③진짜 핵심 반전": "얼려두면 일 년 내내", "④심지어": "심지어 이런 칼이", "⑤~까지 난리": "필수템으로 난리라고"},
  lines=[
  ("title", None, "옥수수 알 까다 현타 온 주방 천재가 만들어 떼돈 번 칼의 정체.", None,
   [("옥수수 알 까다", "removing corn kernels by hand", S), ("현타 온 주방 천재가", "tired cook kitchen", S), ("만들어", "round corn stripper", P), ("떼돈 번 칼의 정체", "money rain meme", M)]),
  ("bait", None, "최근 콘치즈 덕후들 사이에서 바이럴이 터지며 논란인 주방템이 있는데,", None,
   [("최근 콘치즈 덕후들", "corn cheese skillet", S), ("사이에서", "corn cheese melting", S), ("바이럴이 터지며", "phone scrolling viral", S), ("논란인 주방템이 있는데", "corn stripper tool close up", P)]),
  ("reveal", None, "이건 바로 동그란 옥수수 알 커터.", None,
   [("이건 바로", "surprised gasp meme", M), ("동그란 옥수수 알 커터", "round corn stripper ring blade", P)]),
  ("solve", None, "이게 말도 안 되는 게 칼로 썰면 알이 사방으로 튀었는데 이건 링 모양 칼날에 옥수수를 쏙 끼워서 쭉 밀면 알이 통째로 벗겨진다는 거.", None,
   [("이게 말도 안 되는 게", "shocked face meme", M), ("칼로 썰면", "cutting corn kernels knife", S), ("알이 사방으로 튀었는데", "corn kernels flying mess", S), ("이건 링 모양 칼날에", "round corn stripper ring blade close up", P),
    ("옥수수를 쏙 끼워서", "corn cob into round corn stripper", P), ("쭉 밀면", "round corn stripper push down", P), ("알이 통째로", "corn kernels falling off cob", P), ("벗겨진다는 거", "corn kernels strip off slow motion", P)]),
  ("more", None, "심지어 이런 칼이 미국에선 40년도 더 전에 특허까지 나온 물건인데,", "심지어 이런 칼이 미국에선 사십 년도 더 전에 특허까지 나온 물건인데,",
   [("심지어 이런 칼이", "round corn stripper product", P), ("미국에선", "American flag waving", S), ("40년도 더 전에", "old vintage kitchen 1980s", S), ("특허까지 나온 물건인데", "patent drawing document", S)]),
  ("more2", None, "생옥수수든 삶은 옥수수든 다 된다고.", None,
   [("생옥수수든", "raw corn on the cob", S), ("삶은 옥수수든", "boiled corn steaming", S), ("다 된다고", "corn stripper cooked corn", P)]),
  ("twist", None, "근데 진짜 충격적인 포인트는 여름에 알만 까서 얼려두면 일 년 내내 옥수수밥이랑 콘치즈를 해 먹을 수 있다고.", None,
   [("근데 진짜", "jaw drop meme", M), ("충격적인 포인트는", "round corn stripper kernels bowl", P), ("여름에 알만 까서", "bowl full of corn kernels", P), ("얼려두면", "corn kernels freezer bag", S),
    ("일 년 내내", "calendar pages flipping", S), ("옥수수밥이랑", "corn rice cooker", S), ("콘치즈를", "corn cheese skillet", S), ("해 먹을 수 있다고", "corn cheese spoon scoop", S)]),
  ("land", None, "그래서 요즘엔 옥수수를 박스째 사다가 한 번에 다 까서 냉동실 채우는 집들 사이에서 필수템으로 난리라고.", None,
   [("그래서 요즘엔", "round corn stripper kitchen", P), ("옥수수를 박스째 사다가", "box of corn cobs", S), ("한 번에 다 까서", "corn stripper many cobs", P), ("냉동실 채우는", "full freezer bags", S),
    ("집들 사이에서", "family kitchen", S), ("필수템으로 난리라고", "crowd cheering meme", M)]),
  ]))

problems = []
summary = []
for w in WORKS:
    b = w["base"]
    is_evn = b["channel"] == "재미썸홈"
    out_lines = []
    for i, (role, climax, text, tts, shots) in enumerate(w["lines"]):
        sh = []
        for s in shots:
            piece, q = s[0], s[1]
            kind = s[2] if len(s) > 2 else P
            if len(piece) > 13: problems.append(f"{w['dir']} L{i} 토막 13자 초과: {piece}({len(piece)})")
            sh.append({"piece": piece, "query": q, "kind": kind})
        if norm("".join(x["piece"] for x in sh)) != norm(text):
            problems.append(f"{w['dir']} L{i} 토막 이어붙임 불일치\n  {norm(''.join(x['piece'] for x in sh))}\n  {norm(text)}")
        kinds = [x["kind"] for x in sh]
        ln = {"i": i, "text": text, "tts_text": tts or text, "role": role,
              "shot_query": [x["query"] for x in sh], "shots": sh,
              "kind": max(set(kinds), key=kinds.count)}
        if not is_evn: ln["climax"] = climax
        out_lines.append(ln)
    total = sum(chars(l["text"]) for l in out_lines)
    est = round(total / b["cps"], 2)
    climaxes = ([l["climax"] for l in out_lines if l.get("climax")] if not is_evn else list(w["hype"].keys()))
    lo, hi = (180, 230) if not is_evn else (220, 260)
    if not (lo <= total <= hi): problems.append(f"{w['dir']} 글자 수 {total} 범위 밖 {lo}~{hi}")
    if is_evn:
        for k, t in enumerate(w["title_lines"]):
            if len(t) > (11 if k == 0 else 10): problems.append(f"{w['dir']} 제목줄 {k} 길이 {len(t)}: {t}")
    for l in out_lines:
        if re.search(r"[0-9A-Za-z%]", l["tts_text"]): problems.append(f"{w['dir']} L{l['i']} TTS에 숫자·영문·기호: {l['tts_text']}")
    doc = {"채널": b["brand"], "channel": b["channel"], "preset": b["preset"], "topic": w["topic"],
           "목소리": b["voice"], "voice": b["voice"], "cps_target": b["cps"], "재료_규칙": b["rule"],
           "from": ("channel/homedesignnote/대본초안_5편.md" if not is_evn else "channel/homedesignnote/대본초안_5편_이븐쇼핑형.md") + " → 오푸스 10-17 확정(사실 확인·두 채널 차별화)",
           "lines": out_lines, "chars": total, "est_sec": est, "climax": climaxes,
           "facts": w["facts"]}
    if is_evn:
        doc["title_lines"] = w["title_lines"]
        doc["title_slots"] = {"hook1": w["title_lines"][0], "hook2": w["title_lines"][1], "bodyTitle": w["bodyTitle"]}
        doc["hype"] = w["hype"]
        doc["sfx"] = "shopping_shorts/sfx_pack density=low"; doc["bgm"] = None
    else:
        doc["title_lines"] = []
        doc["sfx"] = 0; doc["meme"] = 0
    summary.append((b["brand"], w["topic"], total, est, len(climaxes), out_lines[0]["text"]))
    if "--write" in sys.argv:
        d = os.path.join(OUT, w["dir"]); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "대본.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)

for s in summary: print(" | ".join(map(str, s)))
print("PROBLEMS:", len(problems))
for p in problems: print(" -", p)
