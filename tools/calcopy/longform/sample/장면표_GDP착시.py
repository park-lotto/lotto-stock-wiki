# 장면표 — 1인당 GDP 4만 달러의 착시 (211문장)
SKIP = []
PARA = [16, 47, 56, 63, 71, 77, 85, 91, 97, 106, 118, 121, 125, 129, 132, 142, 147, 154, 158, 164, 168, 171, 178, 184, 189, 200, 203, 208]

S = []
def add(a, b, t, **k): S.append(dict(s=[a, b], type=t, **k))
KR = " Korean people, South Korea setting, documentary photo, 16:9"

# ── 훅 ──
add(1, 1, "ai", prompt="Seoul skyline at golden hour with glittering skyscrapers and the Han River, cinematic documentary photo, 16:9", bubble=(1, "우리 이제 부자 나라?", "잘사는"))
add(2, 3, "bignum", bg_ai="Night view of Seoul city lights from a mountain viewpoint, 16:9", v0=0, v1=43512, fmt="{:,.0f}달러", count_word="사상",
    label="한국 1인당 GDP (2026년 IMF 전망)", sub="사상 첫 4만 달러 돌파", sub_word=(3, "4만"), src="경향신문 2026.10.13 (IMF)")
add(4, 4, "stock", ai="Stacks of Korean won banknotes on a wooden table, close-up, documentary photo, 16:9", bubble=(4, "1인당 5845만 원", "5800"))
add(5, 5, "stock", ai="A happy Korean family of four sitting at a dining table at home, warm light, documentary photo, 16:9", bubble=(5, "4인 가족 = 2억 3천만 원?", "2억"))
add(6, 6, "typo", items=[(6, "", "나도 [[부자]] 됐네?", "ivory", "C", "S1", "stamp")])
add(7, 7, "stock", ai="Korean office worker in a cubicle staring at a smartphone banking app with a tired expression, documentary photo, 16:9", bubble=(7, "월급날 맞아..?", "통장"))
add(8, 8, "stock", ai="Currency exchange board in a Seoul street, blurred numbers, documentary photo, no readable text, 16:9", bubble=(8, "환율 때문 아니야?", "환율"))
add(9, 10, "typo", items=[(9, "", "그것만은", "ivory", "C", "S1", "stamp"), (9, "아니었습니다", "[[아니었습니다]]", "black", "C", "S1", "whip", "pink")])
add(11, 12, "bignum", bg_ai="Container ships at Busan port at dusk with cranes, 16:9", v0=0, v1=18.8, fmt="{:.1f}%", count_word="18.8", label="3분기 실질 GDI (전년 동기 대비)", sub="1977년 4분기 이후 최고", sub_word=(12, "1977"), src="이투데이 2026.10.27 (한국은행)")
add(13, 13, "stock", ai="Quiet Korean shopping street with few customers, shopkeeper waiting at the door, documentary photo, 16:9", stamp=(13, "소비 감소"))
add(14, 14, "vs", left="나라: 49년 만의 소득", right="국민: 지갑을 닫음", sub="같은 3분기에 벌어진 일", title="같은 나라, 다른 숫자", at=[(14, "나라는"), (14, "국민은"), (14, "")])
add(15, 15, "typo", items=[(15, "", "그 돈은 다", "ivory", "C", "S1", "stamp"), (15, "어디로", "[[어디로]] 간 거냐", "black", "C", "S1", "whip", "lime")])

# ── 가격 ──
add(16, 16, "stock", ai="Middle-aged Korean economist with East Asian face looking at a large wall chart in a Seoul office, documentary photo, 16:9")
add(17, 21, "bar", title="IMF가 본 올해 한국 1인당 GDP", sub="(단위 : 달러)", unit="달러",
    items=[("2025년 실적", 36107, "3만6107"), ("4월 전망", 37412, "3만7412"), ("10월 전망", 43512, "4만3512")], hl=2, reveal=20, src="헤럴드경제 2026.01.10 · 경향신문 2026.10.13")
add(22, 22, "stock", ai="Puzzled Korean man reading a newspaper on a subway platform, documentary photo, 16:9", bubble=(22, "반년 만에?", "반년"))
add(23, 25, "vs", left="실질 : 얼마나 만들었나", right="명목 : 얼마에 팔았나", sub="뉴스의 달러 숫자는 명목 쪽이다", title="성장에는 두 가지가 있다", at=[(24, "실질은"), (25, "명목은"), (25, "")])
add(26, 26, "ai", prompt="Korean street food stall selling bungeoppang fish-shaped pastries in winter, steam rising, documentary photo, 16:9", bubble=(26, "붕어빵 가게로 치면", "붕어빵"))
add(27, 27, "ai", prompt="Close-up of bungeoppang fish-shaped pastries lined up on an iron griddle, documentary photo, 16:9", img=26, variant=True, bubble=(27, "100개 → 103개", "103"))
add(28, 29, "bar", title="붕어빵 가게 매출 (예시)", sub="(개수 × 가격)", unit="원",
    items=[("작년 100개 × 1000원", 100000, "10만 원"), ("올해 103개 × 1100원", 113300, "11만3300원")], hl=1, reveal=29, src="설명용 예시")
add(30, 31, "typo", items=[(30, "", "더 구운 건", "ivory", "C", "S1", "stamp"), (30, "3개", "[[3개]]뿐", "black", "C", "S0", "stamp", "lime")])
add(32, 34, "bar", title="올해 한국 성장률 전망 (정부)", sub="(단위 : %)", unit="%",
    items=[("실질 성장", 3.0, "3.0%"), ("경상(명목) 성장", 12.3, "12.3%")], hl=1, reveal=32, reveal_word="명목", src="뉴데일리 2026.07.19")
add(35, 35, "stock", ai="Macro photo of a silicon wafer with iridescent patterns held by gloved hands, 16:9")
add(36, 36, "bignum", bg_ai="Semiconductor clean room with workers in white suits, yellow light, 16:9", v0=0, v1=56.6, fmt="{:.1f}%", count_word="56.6", label="2분기 수출 디플레이터 상승률", sub="반도체 중심", sub_word=(36, "반도체"), src="머니투데이 2026.09.08")
add(37, 37, "stock", ai="Rows of AI data center server racks with blue lights, documentary photo, 16:9")
add(38, 38, "stock", ai="Robotic automated semiconductor fab with overhead rails, no people, documentary photo, 16:9", bubble=(38, "똑같이 만들었는데", "똑같은"))
add(39, 40, "quote", style="dark", bg_ai="Glass headquarters of an international financial institution in Washington, no logos, 16:9",
    text="AI 산업의 과실은 첨단 반도체를 대규모로\n생산할 수 있는 극소수 국가,\n대만과 한국이 주로 가져가고 있다", hl=["대만과 한국"], src="경향신문 2026.10.13 (IMF 평가 요약)")
add(41, 42, "bar", title="2026년 1인당 GDP 전망 (IMF)", sub="(단위 : 달러)", unit="달러", orient="h",
    items=[("대만", 43950, "약 4만3950"), ("한국", 43512, "4만3512"), ("일본", 35400, "3만5400")], hl=1, reveal=42, src="경향신문 2026.10.13")
add(43, 44, "stock", ai="Business people shaking hands and smiling in a bright Seoul office lobby, documentary photo, 16:9")
add(45, 45, "stock", ai="Huge cargo ship loaded with containers leaving a Korean port, aerial documentary photo, 16:9")
add(46, 46, "typo", items=[(46, "", "누구", "ivory", "L", "S1", "stamp"), (46, "주머니로", "[[주머니]]로 갔나", "black", "C", "S1", "whip", "pink")])

# ── 환율과 인구 ──
add(47, 48, "typo", items=[(47, "", "숫자를 키운 것 [[둘]] 더", "ivory", "C", "S1", "stamp"), (48, "환율", "① [[환율]]", "black", "C", "S1", "whip", "lime")])
add(49, 50, "stock", ai="Korean won and US dollar banknotes side by side on a desk, close-up, documentary photo, 16:9")
add(51, 53, "table_like", title="환율에 따라 달라지는 4만 달러", sub="(7월 추산, 뉴데일리)", unit="원",
    items=[("평균 1487원", 39164, "3만9164달러"), ("1456원 이하", 40000, "4만 달러 돌파")], hl=1, reveal=52, src="뉴데일리 2026.07.19")
add(54, 54, "stock", ai="Modest Korean apartment kitchen table with household bills and a calculator, documentary photo, 16:9", bubble=(54, "우리 집은 그대로", "살림"))
add(55, 55, "quote", style="beige", bg_ai="Trading floor screens showing a currency chart, blurred, 16:9",
    text="달러 기준 소득은 환율에 따라 달라지므로\n실질 생산능력이 그대로여도\n4만달러 달성 여부가 바뀔 수 있다", hl=["실질 생산능력이 그대로여도"], src="머니투데이 2026.09.08 내용 요약")
add(56, 56, "typo", items=[(56, "인구", "② [[인구]]", "black", "C", "S1", "stamp", "lime")])
add(57, 57, "stock", ai="Empty Korean elementary school classroom with small desks, documentary photo, 16:9")
add(58, 59, "ai", prompt="A whole pizza on a table with three pairs of hands taking slices, top view, documentary photo, 16:9", bubble=(59, "피자는 그대로", "피자가"))
add(60, 60, "stock", ai="Elderly Korean people walking in a quiet rural town street, documentary photo, 16:9")
add(61, 62, "stock", img=35, ai="Macro photo of a silicon wafer, 16:9", bubble=(62, "환율·인구는 양념", "양념"))
add(63, 66, "bar", title="올해 실질 성장률 전망", sub="(단위 : %)", unit="%",
    items=[("한국 (4월 IMF)", 1.9, "1.9%"), ("한국 (10월 IMF)", 3.3, "3.3%"), ("대만 (7월 전망)", 9.64, "9.64%")], hl=2, reveal=64, src="경향신문 2026.10.13 · 뉴데일리 2026.07.19")
add(67, 67, "stock", ai="Taiwan Taipei skyline at dusk, documentary photo, 16:9")
add(68, 70, "stock", ai="Aerial view of Seoul Gangnam district with dense high-rise buildings at noon, documentary photo, 16:9", bubble=(70, "값이 올라서 커졌다", "값이"))

# ── 돈의 주소 ──
add(71, 72, "stock", ai="Close-up of a Korean pay slip on a desk with a pen, numbers blurred, no readable text, documentary photo, 16:9", bubble=(71, "내 월급 아님", "월급"))
add(73, 73, "stock", ai="Small Korean snack bar with tteokbokki on the counter, owner cooking, documentary photo, 16:9")
add(74, 76, "stock", ai="Heavy steel bank vault door slightly open, documentary photo, 16:9", bubble=(76, "회사 금고까지 합친 평균", "회사가"))
add(77, 79, "typo", items=[(77, "", "돈은 어디로?", "ivory", "C", "S1", "stamp"), (78, "", "[[볼 수 있습니다]]", "black", "C", "S1", "whip", "lime")])
add(80, 82, "bar", title="2분기 소득 증가율 (전기 대비)", sub="(단위 : %)", unit="%",
    items=[("기업 몫(총영업잉여)", 18.5, "18.5%"), ("일하는 사람 몫(피용자보수)", 1.9, "1.9%")], hl=0, reveal=81, src="머니투데이 2026.09.08")
add(83, 84, "bignum", bg_ai="Corporate glass tower looking up from the street in Seoul, 16:9", v0=0, v1=48.2, fmt="{:.1f}%", count_word="48.2", label="2분기 총영업잉여 (전년 동기 대비)", sub="기업 몫의 증가 속도", sub_word=(84, "속도"), src="머니투데이 2026.09.08")
add(85, 86, "stock", ai="Korean labor and management representatives sitting across a negotiation table, documentary photo, 16:9")
add(87, 88, "stock", img=38, ai="Automated semiconductor fab, 16:9", variant=True, bubble=(88, "이익은 회사로 먼저", "회사로"))
add(89, 90, "stock", ai="Calendar and paperwork on a Korean company HR desk, documentary photo, no readable text, 16:9", bubble=(89, "임금은 1년에 한 번", "1년에"))
add(91, 93, "bignum", bg_ai="Piggy bank and coins on a dark table, 16:9", v0=0, v1=45.6, fmt="{:.1f}%", count_word="45.6", label="2분기 총저축률", sub="1970년 통계 작성 이후 최고", sub_word=(93, "1970"), src="머니투데이 2026.09.08")
add(94, 95, "bar", title="2분기 총저축률 vs 국내총투자율", sub="(단위 : %)", unit="%",
    items=[("총저축률", 45.6, "45.6%"), ("국내총투자율", 24.2, "24.2%")], hl=1, reveal=94, src="머니투데이 2026.09.08")
add(96, 96, "stock", ai="Commuters crossing a Seoul street at rush hour, documentary photo, 16:9")

# ── 줄어든 월급 ──
add(97, 98, "bignum", bg_ai="Korean office workers walking to work in the morning, 16:9", v0=0, v1=403.6, fmt="{:.1f}만원", count_word="403", label="2분기 월평균 명목임금", sub="1년 전보다 2.1% 증가", sub_word=(98, "2.1"), src="데일리안 2026.08.27 (고용노동부)")
add(99, 101, "vs", left="월급 +2.1%", right="물가 +3.0%", sub="살 수 있는 물건은 줄어든다", title="2분기 월급과 물가", at=[(99, "물가가"), (100, "물가가"), (101, "")])
add(102, 104, "bar", title="2분기 실질임금 (월평균)", sub="(단위 : 만원)", unit="만원",
    items=[("작년 2분기", 339.8, "339.8만"), ("올해 2분기", 337, "337만")], hl=1, reveal=103, src="데일리안 2026.08.27 (고용노동부)")
add(105, 105, "stock", img=1, ai="Seoul skyline", variant=True, stamp=(105, "역대급 소득"))
add(106, 107, "stock", ai="Crowd of Korean office workers seen from behind on a crosswalk, documentary photo, 16:9")
add(108, 110, "bar", title="6월 임금총액 (사업체 규모별)", sub="(단위 : 만원)", unit="만원",
    items=[("300인 이상", 593.3, "593만 (+4.4%)"), ("300인 미만", 369.8, "369만 (+2.3%)")], hl=0, reveal=110, src="데일리안 2026.08.27 (고용노동부)")
add(111, 112, "typo", items=[(111, "", "큰 회사만", "ivory", "C", "S1", "stamp"), (111, "물가를", "물가를 [[앞질렀다]]", "black", "C", "S1", "whip", "pink")])
add(113, 114, "bignum", bg_ai="White envelope and Korean won banknotes on a Korean office desk, no people, 16:9", v0=0, v1=17.2, fmt="{:.1f}%", count_word="17.2", label="6월 상용근로자 특별급여 증가율", sub="성과급 등", sub_word=(113, "성과급"), src="데일리안 2026.08.27 (고용노동부)")
add(115, 117, "stock", ai="Two Korean colleagues looking in opposite directions on a split street, one in a luxury area one in an old alley, documentary photo, 16:9", bubble=(117, "둘 다 사실", "둘 다"))
add(118, 119, "typo", items=[(118, "", "[[K자]] 경제", "ivory", "C", "S0", "stamp"), (119, "위쪽", "위는 오르고 아래는 내리고", "black", "C", "S1", "whip", "lime")])
add(120, 120, "stock", ai="Young Korean job seeker sitting alone on a bench holding a resume folder, documentary photo, 16:9")

# ── 사람이 덜 필요한 호황 ──
add(121, 122, "stock", ai="Busy Korean electronics factory floor with East Asian workers in uniform on an assembly line, documentary photo, 16:9")
add(123, 124, "stock", ai="Lively Korean neighborhood restaurant full of workers eating dinner, documentary photo, 16:9", bubble=(124, "돈이 돌던 시절", "돌았거든"))
add(125, 126, "stock", img=38, ai="Automated semiconductor fab, 16:9", bubble=(126, "사람보다 기계", "기계로"))
add(127, 127, "bignum", bg_ai="Large lithography machine in a clean room, 16:9", v0=0, v1=4.1, fmt="{:.1f}%", count_word="4.1", label="3분기 설비투자 증가율", sub="반도체 제조용 기계 중심", sub_word=(127, "기계가"), src="이투데이 2026.10.27")
add(128, 128, "quote", style="dark", bg_ai="Empty modern factory hall at night, 16:9", text="반도체 산업의 취업유발계수는\n제조업 평균보다 낮다", hl=["제조업 평균보다 낮다"], src="주간경향 2026.08.21 (세미나 지적)")
add(129, 131, "bar", title="9월 수출 증가율 (전년 동월 대비)", sub="(단위 : %)", unit="%",
    items=[("반도체 외", 23, "23%"), ("전체", 83.5, "83.5%"), ("반도체", 263, "263%")], hl=2, reveal=130, src="산업통상부 9월 수출입동향")
add(132, 133, "bignum", bg_ai="Korean factory gate with a few workers leaving at dusk, 16:9", v0=0, v1=16000, fmt="{:,.0f}명", count_word="1만", label="9월 제조업 취업자 증가", sub="전년 동월 대비", sub_word=(133, "겨우"), src="아이뉴스24 2026.10.16 (국가데이터처)")
add(134, 135, "bar", title="9월 취업자 증감 (전년 동월 대비)", sub="(단위 : 만 명)", unit="만",
    items=[("보건복지", 20.7, "+20.7만"), ("60세 이상", 17.2, "+17.2만"), ("제조업", 1.6, "+1.6만")], hl=0, reveal=135, src="아이뉴스24 2026.10.16 (국가데이터처)")
add(136, 139, "bignum", bg_ai="Young Koreans lined up with resumes at a job fair, 16:9", v0=0, v1=47, fmt="{:.0f}개월째", count_word="47", label="청년(15~29세) 취업자 감소 행진", sub="9월 14만7천 명 감소", sub_word=(138, "47"), src="아이뉴스24 2026.10.16 (국가데이터처)")
add(140, 140, "stock", ai="Young Korean woman studying at a library desk at night with a job prep book, documentary photo, 16:9", bubble=(140, "청년 고용률 44.0%", "44"))
add(141, 141, "bar", title="9월 취업자 감소 업종", sub="(단위 : 만 명)", unit="만",
    items=[("숙박·음식점", 9.7, "-9.7만"), ("건설업", 4.8, "-4.8만")], hl=0, reveal=141, src="아이뉴스24 2026.10.16 (국가데이터처)")
add(142, 144, "stock", img=57, ai="Empty classroom", variant=True, bubble=(144, "인구 탓만은 아니다", "설명이"))
add(145, 146, "stock", img=120, ai="Young job seeker", variant=True)

# ── 닫힌 지갑 ──
add(147, 149, "bignum", bg_ai="Bank of Korea style central bank building exterior, no logos, 16:9", v0=0, v1=1.0, fmt="{:.1f}%", count_word="1%", label="3분기 실질 GDP 성장률 (전기 대비)", sub="한은 8월 전망 0.3%", sub_word=(149, "0.3"), src="이투데이 2026.10.27 (한국은행)")
add(150, 151, "bignum", bg_ai="Empty Korean supermarket aisle with a lonely shopping cart, 16:9", v0=0, v1=-0.2, fmt="{:.1f}%", count_word="0.2", label="3분기 민간소비 (전기 대비)", sub="2022년 4분기 이후 첫 감소", sub_word=(151, "2022"), src="이투데이 2026.10.27 (한국은행)")
add(152, 153, "bar", title="3분기 업종별 성장률 (전기 대비)", sub="(단위 : %)", unit="%",
    items=[("제조업", 2.0, "2.0%"), ("서비스업", 0.2, "0.2%")], hl=1, reveal=152, reveal_word="서비스업", src="이투데이 2026.10.27")
add(154, 156, "stock", ai="Car assembly plant with workers on strike holding no signs, standing idle, documentary photo, no readable text, 16:9", bubble=(155, "일회성 빼면 +0.4%", "0.4"))
add(157, 157, "typo", items=[(157, "", "그래도", "ivory", "L", "S1", "stamp"), (157, "1%짜리", "성장에 비하면 [[약하다]]", "black", "C", "S1", "whip", "pink")])
add(158, 160, "bignum", bg_ai="Korean shopper hesitating in front of a market stall, 16:9", v0=0, v1=105.4, fmt="{:.1f}", count_word="105", label="10월 소비자심리지수", sub="전월보다 1.2p 하락", sub_word=(159, "내려"), src="한국은행 2026.10.27")
add(161, 162, "bar", title="10월 소비자동향 세부 지수", sub="(100 미만 = 부정적)", unit="",
    items=[("현재경기판단", 82, "82"), ("취업기회전망", 86, "86")], hl=0, reveal=161, ref=(100, "기준 100"), ref_at=162, src="한국은행 2026.10.27")
add(163, 163, "stock", ai="Korean family with East Asian faces sitting on a floor sofa in a Seoul apartment watching television news in the evening, screen blurred, documentary photo, 16:9")
add(164, 166, "stock", ai="Closed Korean shop with shutters down and a blank for-rent paper on the door, documentary photo, no readable text, 16:9", bubble=(165, "폐업 사유 절반이 사업 부진", "절반이"))
add(167, 167, "stock", ai="Lonely Korean restaurant owner sitting at an empty table during lunchtime, documentary photo, 16:9")
add(168, 169, "labels", bg_ai="Dim silhouette of an empty Korean street market at night, 16:9",
    items=[(169, "반도체 값 상승", "반도체"), (169, "회사가 먼저 번다", "회사가"), (169, "채용은 적다", "사람은"), (169, "월급 < 물가", "월급은"), (169, "소비 부진", "소비가")])
add(170, 170, "stock", ai="Storm clouds gathering over the Seoul skyline, documentary photo, 16:9")

# ── 한쪽 다리 ──
add(171, 172, "typo", items=[(171, "", "다리가", "ivory", "L", "S1", "stamp"), (172, "", "[[반도체 가격]] 하나", "black", "C", "S1", "whip", "pink")])
add(173, 173, "labels", img=35, bg_ai="Silicon wafer", items=[(173, "수출", "수출이"), (173, "기업 이익", "기업"), (173, "명목 소득", "명목")])
add(174, 175, "quote", style="dark", img=37, bg_ai="Server racks", text="AI의 수익성과 생산성 향상에 대한 기대가\n지나치게 낙관적이면\n투자가 급격히 둔화할 수 있다", hl=["투자가 급격히 둔화"], src="경향신문 2026.10.13 (IMF 위험 요인 요약)")
add(176, 176, "stock", ai="Worried Korean investor looking at falling red and blue stock chart on a phone, chart without numbers, documentary photo, 16:9", bubble=(176, "역 부의 효과", "자산이"))
add(177, 177, "bignum", bg_ai="Asian financial district at dusk under grey sky, 16:9", v0=0, v1=-1.7, fmt="{:.1f}%", count_word="1.7", label="AI 효과 미흡 시 아시아 GDP (2028년까지)", sub="IMF 시나리오", sub_word=(177, "2028"), src="경향신문 2026.10.13 (IMF)")
add(178, 179, "stock", img=49, ai="Won and dollar", variant=True, bubble=(179, "달러로 잰 숫자", "환율이"))
add(180, 182, "ai", prompt="Tokyo Shibuya crossing on a cloudy day, documentary photo, 16:9", bubble=(181, "일본, 다시 3만 달러대", "3만"))
add(183, 183, "bignum", bg_ai="Blueprint and calculator on a planning desk, 16:9", v0=0, v1=52100, fmt="{:,.0f}달러", count_word="5만", label="IMF 2028년 1인당 GDP 전망", sub="전망은 전망일 뿐", sub_word=(183, "믿고"), src="경향신문 2026.10.13 (IMF)")
add(184, 186, "stock", ai="Young Korean man with East Asian face smiling on his first day at a car parts factory, wearing a safety vest, documentary photo, 16:9", bubble=(186, "청년 쉬었음 4만 4천 명 감소", "쉬었음"))
add(187, 188, "typo", items=[(188, "", "얼마나 버느냐가 ~~아니라~~", "ivory", "C", "S1", "stamp"), (188, "어디까지", "[[어디까지]] 흘러가느냐", "black", "C", "S1", "whip", "lime")])

# ── 남은 숙제 ──
add(189, 191, "stock", ai="Panel discussion at a Korean economics seminar, speakers at a long table, no readable text, documentary photo, 16:9")
add(192, 194, "stock", ai="Small Korean subcontractor machine shop with a worker at a lathe, documentary photo, 16:9", bubble=(194, "납품대금 연동·상생 기금", "납품"))
add(195, 197, "stock", ai="Korean nurse caring for an elderly patient in a bright clinic, documentary photo, 16:9", bubble=(197, "보건·교육·관광", "보건"))
add(198, 199, "stock", ai="Young engineer and robot arm working together in a bright Korean workshop, documentary photo, 16:9")
add(200, 202, "ai", prompt="Hourglass with sand running out on a desk beside a silicon wafer, documentary photo, 16:9", bubble=(202, "남은 시간은 모른다", "시간이"))

# ── 마무리 ──
add(203, 204, "stock", img=1, ai="Seoul skyline", variant=True, bubble=(204, "진짜로 벌었다", "진짜로"))
add(205, 206, "labels", img=127, bg_ai="Factory", items=[(205, "값이 뛰어서 벌었고", "값이"), (206, "회사에 먼저 쌓였고", "회사"), (206, "아래까지 잘 안 내려왔다", "아래까지")])
add(207, 207, "typo", items=[(207, "", "나라는 [[부자]]", "ivory", "C", "S1", "stamp"), (207, "국민은", "국민은 [[아직]]", "black", "C", "S1", "whip", "pink")])
add(208, 209, "labels", img=106, bg_ai="Commuters", items=[(209, "실질임금", "실질임금"), (209, "민간소비", "민간소비"), (209, "청년 고용", "청년")])
add(210, 211, "stock", img=2, ai="Seoul night", variant=True)

for _s in S:
    if _s["type"] == "table_like":
        _s["type"] = "bar"

Q = {4: "money banknotes counting", 5: "asian family dinner table", 7: "office worker phone tired", 8: "currency exchange money", 13: "empty shopping street", 16: "stock chart analyst office",
     22: "man reading newspaper", 35: "silicon wafer semiconductor", 37: "data center server", 38: "semiconductor factory robot", 43: "business handshake office", 45: "container ship port",
     49: "dollar bills counting", 54: "household bills calculator", 57: "empty classroom", 60: "elderly people walking", 67: "taipei city", 68: "seoul city aerial", 71: "paperwork desk pen",
     73: "street food cooking", 74: "bank vault", 85: "business meeting negotiation", 89: "office paperwork", 96: "seoul crosswalk people", 106: "crowd crossing street", 120: "young man sitting alone bench",
     121: "factory workers assembly line", 123: "restaurant people eating", 140: "student studying library", 154: "car factory assembly", 163: "family watching tv", 164: "closed shop shutter",
     167: "empty restaurant", 170: "storm clouds city", 176: "stock market falling phone", 184: "factory worker young", 189: "conference panel discussion", 192: "machinist lathe workshop",
     195: "nurse elderly care", 198: "robot arm engineer"}
for _s in S:
    if _s["s"][0] in Q and "img" not in _s:
        _s["q"] = Q[_s["s"][0]]
