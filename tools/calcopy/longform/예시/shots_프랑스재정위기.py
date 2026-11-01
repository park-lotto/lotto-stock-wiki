# 샷리스트 — 경고/손실 회피 대본(169문장, 152번 제외)
# s=[시작문장, 끝문장] · type: stock|ai|quote|bignum|bar|table|labels|vs|cycle|rating|ladder|pct
# stock: q=Pexels 검색어(영어), ai=키가 없을 때 대신 그릴 장면 · bubble=(문장번호, 문구) · stamp=(문장번호, 문구)
SKIP = [152]
# 단락 전환 쉼(0.5초)을 이 문장 앞에 넣는다
PARA = [15, 19, 23, 33, 53, 57, 63, 69, 80, 86, 95, 102, 118, 120, 127, 133, 140, 145, 151, 160, 166]

S = []
def add(a, b, t, **k): S.append(dict(s=[a, b], type=t, **k))

# ── 훅 ───────────────────────────────────────────────
add(1, 2, "ai", prompt="Overcast evening street in Paris, Eiffel Tower in the distance, three office workers in coats looking worriedly at their smartphones, cinematic documentary photo, muted desaturated colors, 16:9",
    bubble=(1, "요즘 프랑스 왜 이래..?", "프랑스 얘기"))
add(3, 3, "stock", q="athens parliament greece", ai="Athens Greek parliament building with Greek flag under grey sky, documentary photo, 16:9")
add(4, 4, "quote", article="a004", circle_at=[(4, "그리스보다")], style="paper", text="프랑스 국채 발행 금리가 과거 재정 위기 진원지였던\n그리스나 이탈리아보다도 높은 수준이다.", hl=["그리스나 이탈리아보다도 높은 수준"], src="연합뉴스 2026.10.07")
add(5, 5, "stock", q="eiffel tower tourists", ai="Tourists taking photos in front of the Eiffel Tower, luxury shopping street nearby, documentary photo, 16:9")
add(6, 6, "quote", article="a006", circle_at=[(6, "피치가"), (6, "정기")], style="dark", img=11, text="피치, 프랑스 신용등급 A+ 유지했지만\n전망 '안정적' → '부정적'으로 낮춰…\n정기 평가 일정에 없던 조치", hl=["'부정적'", "정기 평가 일정에 없던 조치"], src="한국경제 2026.10.31")
add(7, 7, "stock", q="paris cafe terrace people", ai="Parisian cafe terrace with people relaxing, documentary photo, 16:9", bubble=(7, "잠깐 경기 탓이겠지~", "경기가"))
add(8, 8, "bignum", bg_q="euro banknotes stack", bg_ai="Stacks of euro banknotes on a dark table, 16:9", v0=0, v1=119, fmt="{:.0f}%", count_word="1년",
    label="프랑스 국가부채 (GDP 대비)", sub="1년 경제 규모보다 많은 빚", sub_word=(8, "1년 경제"), src="매일신문 2026.10.22 (INSEE)")
add(13, 13, "stock", q="paris skyline storm clouds", ai="Paris skyline under dark storm clouds, dramatic, 16:9")
add(14, 14, "typo", items=[(14, "", "어쩌다", "ivory", "C", "S1", "stamp"), (14, "이렇게", "이렇게 [[된 거냐]]", "black", "C", "S1", "whip", "pink")])
# ── 시장의 경고 ─────────────────────────────────────
add(15, 16, "bignum", bg_q="financial chart screen", bg_ai="Bond market trading screen with yield charts, dark, 16:9",
    v0=0, v1=4.98, fmt="{:.2f}%", count_line=16, count_word="코앞", sub_word=(16, "2002년"), label="프랑스 국채 10년물 금리 (10월 20일 장중)", sub="2002년 이후 최고 수준", src="매일신문 2026.10.22")
add(17, 18, "stock", q="euro banknotes counting", ai="Hands counting euro banknotes on a desk, 16:9", bubble=(18, "이 나라 좀 불안한데?"))
add(19, 20, "ai", prompt="Two young Korean friends at a cafe table, one handing an envelope of money to the other, friendly, warm light, documentary photo, 16:9", bubble=(20, "그래, 빌려줄게~", "그냥 빌려주"))
add(21, 22, "ai", prompt="Nervous man at a cluttered desk covered with unpaid bills and loan papers, holding his head, documentary photo, 16:9", bubble=(21, "이자가 왜 이렇게 올랐지..?", "이자 좀"))
add(23, 25, "quote", article="a023", circle_at=[(24, "2010년")], style="paper", img=24, bg_q="frankfurt skyline", bg_ai="Frankfurt financial district skyline, 16:9",
    text="투자자들이 프랑스 국채를 팔고 안전 자산인 독일 국채를 사면서\n두 나라 국채 금리 차이가 2010~2012년\n유로존 재정 위기 이후 최고 수준으로 벌어졌다.", hl=["2010~2012년", "유로존 재정 위기 이후 최고 수준"], src="연합뉴스 2026.10.07")
add(26, 26, "stock", q="tokyo financial district", ai="Tokyo financial district skyscrapers, businesspeople, 16:9", src="연합뉴스 2026.10.07")
add(27, 28, "bignum", bg_q="euro coins", bg_ai="Euro coins scattered on a table, close-up, 16:9",
    v0=1.20, v1=1.12, fmt="{:.2f}달러", count_line=28, count_word="17개월", sub_word=(28, "제일 낮은"), label="유로/달러 환율 — 17개월 만에 최저", sub="10월 5일, 1.12달러 아래로", src="연합뉴스 2026.10.07")
add(29, 29, "quote", article="a029", circle_at=[(29, "10년 전")], style="dark", bg_q="european union flags brussels", bg_ai="European Union flags in front of a glass building in Brussels, 16:9",
    text="프랑스에서 시작된 국채 매도세가 유럽 전역으로 번지며\n10년 전 유로존 부채위기의 악몽까지 떠올리게 하고 있다.", hl=["10년 전 유로존 부채위기의 악몽"], src="월스트리트저널(연합뉴스 2026.10.07 인용)")
add(30, 31, "quote", style="beige", bg_q="business man office window", bg_ai="La Defense financial district skyline in Paris at dusk, no people, 16:9",
    text="프랑스는 수십 년간 유럽에서 무임승차를 해왔고\n방만한 재정으로도 제재 없이 넘어갔다…\n이제는 사람들이 주시하기 시작했다.\n— 카르미냑 케빈 토제 포트폴리오 자문역", hl=["무임승차"], src="연합뉴스 2026.10.07")
add(32, 32, "stock", q="paris street pedestrians", ai="Busy Paris street with pedestrians, 16:9", bubble=(32, "프랑스인데 설마~"))
# ── 빚이 빚을 낳는 구조 ─────────────────────────────
add(33, 33, "typo", items=[(33, "", "빚이", "ivory", "L", "S1", "stamp"), (33, "얼마나", "[[얼마나]] 되냐", "black", "C", "S1", "whip", "lime")])
add(34, 34, "stock", img=33, clip=33, q="calculator bills documents", ai="Calculator and stacks of financial documents on a desk, 16:9")
add(35, 36, "stock", q="economist analyzing charts", ai="Economist analyzing charts on multiple monitors, 16:9")
add(37, 37, "labels", bg_q="paris rain", bg_ai="Rainy Paris street at night, 16:9", items=[(37, "많은 빚"), (37, "+ 오랜 저성장")])
add(38, 39, "bignum", bg_q="euro banknotes", bg_ai="Piles of euro banknotes, 16:9", v0=0, v1=35955, fmt="joeok", count_word="3조",
    label="프랑스 국가부채 (2026년 2분기 말)", sub="GDP의 119%", sub_word=(39, "119"), src="매일신문 2026.10.22 (INSEE)")
add(40, 40, "stock", q="empty wallet", ai="Empty wallet open on a table next to bills, 16:9")
add(41, 42, "bar", title="GDP 대비 프랑스 국가부채 비율", sub="(단위 : %)", unit="%",
    items=[("2025년", 115.7, "115.7%"), ("2026년 2분기", 119, "119%"), ("2028년 전망", 124, "약 124%")], hl=2, reveal=42,
    src="피치(한국경제 2026.10.31) · INSEE(매일신문 2026.10.22)")
add(43, 44, "bar", title="GDP 대비 프랑스 재정적자", sub="(단위 : %)", unit="%",
    items=[("2025년", 5.1, "5.1%"), ("2026년 전망", 5.4, "5.4%")], hl=1, ref=(3, "EU 기준 3%"), ref_at=44, reveal=43, reveal_word="더 커질", src="피치(한국경제 2026.10.31)")
add(45, 46, "quote", article="a045", circle_at=[(45, "적자를"), (45, "300억")], style="paper", bg_q="paris government building", bg_ai="French government ministry building, 16:9",
    text="르코르뉘 내각, 내년도 재정적자를 GDP의 4.7%로 낮추는 방안 승인…\n지출 300억 유로 절감 추진", hl=["4.7%", "300억 유로"], src="연합뉴스 2025.10.15")
add(47, 47, "typo", items=[(47, "", "계획은 매년", "ivory", "C", "S1", "stamp"), (47, "숫자는", "숫자는 [[안 바뀐다]]", "black", "C", "S1", "whip", "pink")])
add(48, 48, "bignum", bg_q="old french coins", bg_ai="Old French documents and coins, archival, 16:9", v0=0, v1=52, fmt="{:.0f}년 연속 적자", count_word="1974",
    label="프랑스 나라 살림 (1974년 이후)", sub="흑자 0번", sub_word=(48, "한 번도"), src="매일신문 2026.10.22")
add(49, 50, "stock", q="gas stove flame", ai="Blue gas stove flame, close-up, 16:9")
add(51, 52, "stock", q="money printing press", ai="Stack of government bond certificates and budget documents on a desk, no people, 16:9")
add(53, 53, "typo", items=[(53, "", "빚의 크기보다", "ivory", "C", "S1", "stamp"), (53, "이자", "[[이자]]", "black", "C", "S0", "stamp", "pink")])
add(54, 54, "stock", img=53, clip=53, q="hourglass", ai="Hourglass with sand running out on a desk, 16:9")
add(55, 56, "quote", article="a055", circle_at=[(55, "1조"), (55, "4천억")], style="dark", bg_q="stock exchange board", bg_ai="Stock exchange board, dark, 16:9",
    text="2030년까지 만기 도래 부채가 1조 달러가 넘으며,\n이를 갚기 위해 내년에만 약 3,800억 달러 규모의\n국채를 발행해야 할 판이다.", hl=["1조 달러", "3,800억 달러"], src="연합뉴스 2026.10.07")
add(57, 59, "ai", prompt="Young Korean office worker at home at night looking at a loan statement on a laptop, stressed, documentary photo, 16:9", bubble=(59, "또 이자야..?"))
add(60, 61, "bar", title="프랑스 국채 이자 비용", sub="(단위 : 억 유로)", unit="억 유로",
    items=[("2026년", 626, "626억"), ("2027년 전망", 729, "729억")], hl=1, badge=(61, "+16.5%"), src="매일신문 2026.10.22")
add(62, 62, "stock", q="defense ministry building", ai="Classical French government ministry building facade with French flag, no people, 16:9", src="연합뉴스 2026.10.07")
add(63, 64, "vs", left="경제가 크는 속도", right="이자율", sub="성장률 > 이자율이면 빚 비율은 버틸 만하다", title="빚을 버티는 조건",
    at=[(63, "크는 속도"), (63, "이자율"), (64, "")])
add(65, 66, "bar", title="프랑스 경제성장률 (2026년)", sub="(전 분기 대비, 단위 : %)", unit="%",
    items=[("1분기", -0.2, "-0.2%"), ("2분기", 0.0, "0%")], hl=1, src="조선비즈 2026.10.20")
add(67, 67, "ai", prompt="Giant snowball rolling down a snowy mountain slope growing bigger, dramatic cinematic, 16:9")
add(68, 68, "quote", style="beige", bg_q="bank of france building", bg_ai="Classical central bank building in Paris, 16:9",
    text="부채가 경제에 '점진적인 목조르기'가 될 위험이 있다.\n— 프랑스 중앙은행 총재", hl=["'점진적인 목조르기'"], src="연합뉴스 2026.10.07")
# ── 경고 1 : 연금 ───────────────────────────────────
add(69, 70, "typo", items=[(69, "", "줄이면 되잖아?", "ivory", "C", "S1", "stamp"), (70, "", "근데 [[안 된단]] 말이야", "black", "C", "S1", "stamp", "pink")])
add(71, 72, "bar", title="프랑스 GDP 대비 지출", sub="(단위 : %)", unit="%", orient="h",
    items=[("정부 지출", 57, "57% 넘음"), ("연금 지출", 14, "14% 안팎")], hl=1, badge=(71, "OECD 1·2위", "1등"), src="연합뉴스 2026.10.08 · 토론토 중앙일보 2026.10.27")
add(73, 74, "bar", title="연금 순 소득대체율", sub="(평균 소득자 기준)", unit="%", orient="h",
    items=[("프랑스", 70, "70% 이상"), ("OECD 평균", 61.4, "61.4%"), ("독일·영국", 55, "55% 안팎")], hl=0, reveal=74, src="OECD (토론토 중앙일보 2026.10.27 · 조선비즈 2026.10.20)")
add(75, 76, "stock", q="elderly couple cafe", ai="Elderly French couple at a cafe, 16:9", bubble=(75, "월급보다 연금이 많다?"), stamp=(76, "과장"))
add(77, 79, "table", title="은퇴자 vs 전체 인구 소득 (월 중간값)", cols=["항목", "금액", "기준"],
    rows=[["은퇴자 소득 중간값", "1,970유로", "2021년 (Drees)"], ["전체 인구 소득 중간값", "1,930유로", "2021년 (Drees)"]],
    hl_rows=[0], row_at=[(78, "은퇴한"), (78, "전체 국민")], src="Drees (토론토 중앙일보 2026.10.27)")
add(80, 82, "ai", prompt="Vintage 1980s photograph of retirees relaxing in a Paris park, film grain, faded colors, 16:9",
    big=(81, "1982년 · 은퇴 나이 ~~65세~~ → [[60세]]"), src="매일신문 2026.10.22 · 토론토 중앙일보 2026.10.27")
add(83, 83, "bar", title="프랑스 사회복지지출", sub="(GDP 대비, 단위 : %)", unit="%",
    items=[("1980년", 20.1, "20.1%"), ("2024년", 32.6, "32.6%")], hl=1, src="lafinancepourtous · 조선비즈 2026.10.20")
add(84, 85, "stock", q="protest crowd street signs", ai="Crowd of protesters with signs on a city street, 16:9")
add(86, 86, "typo", items=[(86, "", "2023년", "ivory", "L", "S1", "stamp"), (86, "마크롱", "마크롱의", "black", "R", "S1", "whip"), (86, "승부수", "승부수", "lime", "C", "S0", "stamp")])
add(87, 88, "table", title="마크롱 연금개혁 (2023년 9월 시행)", cols=["항목", "이전", "개혁"],
    rows=[["은퇴 나이", "62세", "매년 3개월씩 → 2030년 64세"], ["완전연금 납입 기간", "42년", "2027년부터 43년"]],
    hl_rows=[0], row_at=[(87, "62세"), (88, "43년")], src="연합뉴스 2025.10.15")
add(89, 90, "bignum", count_line=90, img=90, bg_q="large protest crowd", bg_ai="Huge crowd of protesters filling a boulevard, aerial, 16:9",
    v0=0, v1=100, fmt="{:.0f}만 명+", count_word="100만", label="연금개혁 반대 시위", sub="2023년", src="토론토 중앙일보 2026.10.27")
add(91, 92, "quote", article="a091", circle_at=[(91, "2028년"), (92, "4억")], style="paper", bg_q="paris parliament speech", bg_ai="Empty podium with microphones in a parliament chamber, no people, 16:9",
    text="현재부터 2028년 1월까지 정년 연장은 없을 것.\n(연금개혁 중단 비용 2026년 4억 유로, 2027년 18억 유로)\n— 르코르뉘 총리", hl=["2028년 1월까지", "4억 유로", "18억 유로"], src="연합뉴스 2025.10.15")
add(93, 94, "bignum", bg_q="elderly people park", bg_ai="Elderly people walking in a park, 16:9", v0=0, v1=1700, fmt="{:,.0f}만 명+", count_word="1,700", label="프랑스 은퇴자 수", src="토론토 중앙일보 2026.10.27")
add(95, 96, "pct", value=83, count_at=(96, "여덟"), title_top="연금 제도를 믿지 않는 청년", title="현행 연금 제도가 노후를 보장해 줄 거라고\n믿지 않는다", who="25~34세", src="IFOP 2026.06 (조선비즈 2026.10.20)")
add(97, 97, "stock", q="young man laptop finance", ai="Close-up of a laptop screen showing an investment portfolio chart on a desk, no people, 16:9", bubble=(97, "노후는 내가 따로..", "따로"))
add(98, 98, "quote", style="dark", img=97,
    text="지금의 국가 노후 연금 제도는\n계속 유지될 수 없다고 확신한다.\n— 파리 교외 30대 직장인 (로이터 인터뷰)", hl=["계속 유지될 수 없다"], src="로이터(조선비즈 2026.10.20 인용)")
add(99, 99, "stock", q="young people subway commute", ai="Young commuters on a metro platform, 16:9")
add(100, 100, "typo", items=[(100, "", "연금이 [[무서운]] 이유", "black", "C", "S1", "stamp", "pink")])
add(101, 101, "labels", bg_q="young office workers", bg_ai="Young office workers walking in a business district, 16:9",
    items=[(101, "표 의식해 못 줄임", "못 줄이면"), (101, "→ 빚으로 메움", "빚으로"), (101, "→ 다음 세대로", "다음 세대")])
# ── 경고 2 : 정치 ───────────────────────────────────
add(102, 102, "stock", q="parliament chamber", ai="French National Assembly hemicycle full of deputies, wide shot, 16:9")
add(103, 104, "labels", img=104, bg_q="parliament chamber seats", bg_ai="French National Assembly hemicycle full of deputies, 16:9",
    items=[(103, "좌파 연합 (신인민전선)", "좌파"), (103, "중도 연합 (앙상블)", "중도"), (103, "극우 연합 (국민연합)", "극우")])
add(105, 105, "labels", img=102, items=[(105, "불신임 · 사퇴 위기", "위기에")])
add(106, 107, "table", title="예산 갈등에 흔들린 총리들", cols=["총리", "무슨 일이"],
    rows=[["미셸 바르니에", "2025년 예산안 강행 → 불신임, 석 달 만에 총사퇴"], ["프랑수아 바이루", "2025년 9월 신임투표 부결 (364 대 194) → 사퇴"], ["세바스티앵 르코르뉘", "임명 27일 만에 사임 → 나흘 만에 재임명"]],
    hl_rows=[2], row_at=[(106, "바르니에"), (106, "바이루"), (107, "")], src="연합뉴스 2025.10.15 · 블룸버그 2025.09.08")
add(108, 108, "ai", img=107, prompt="Exterior of an elegant Paris government residence gate with French tricolor flag at dusk, guard booth, no people visible, 16:9", src="연합뉴스 2025.10.15")
add(109, 109, "stock", q="parliament vote session", ai="Members of parliament voting in a chamber, 16:9")
add(110, 111, "bar", title="르코르뉘 불신임안 표결", sub="(가결에 필요한 과반 289표)", unit="표", orient="h",
    items=[("찬성", 271, "271표")], ref=(289, "가결선 289"), hl=0, stamp=(111, "부결"), src="경향신문 2025.10.16 · KBS 2025.10.17")
add(112, 112, "typo", items=[(112, "", "빚 줄이려던 개혁", "ivory", "C", "S1", "stamp"), (112, "살아남으려고", "살아남으려고", "black", "L", "S1", "whip"), (112, "내준", "[[내준]] 셈", "black", "C", "S0", "stamp", "lime")])
add(113, 113, "quote", style="paper", bg_q="elysee palace", bg_ai="Elysee Palace gate in Paris, 16:9",
    text="연금개혁 중단은 모두에게 고통스럽지만\n정치적 안정을 위해 필요한 일이었다.\n— 에마뉘엘 마크롱 대통령", hl=["정치적 안정을 위해"], src="KBS 2025.10.17")
add(114, 114, "typo", items=[(114, "", "자기 대선 공약을", "ivory", "C", "S1", "stamp"), (114, "자기 손으로", "자기 손으로 [[멈췄다]]", "black", "C", "S1", "whip", "pink")])
add(115, 115, "stock", q="tax form calculator money", ai="Tax form with calculator and money, 16:9", bubble=(115, "억만장자 과세!"))
add(116, 117, "stock", q="parliament debate", ai="Empty French National Assembly hemicycle seen from the back rows, red seats, scattered budget documents on desks, no people, 16:9")
add(118, 119, "quote", style="beige", bg_q="paris government", bg_ai="French ministry building facade, 16:9",
    text="프랑스에는 항상 국가에 '마법의 돈'을 요구해\n비용을 치르게 하려는 반사적인 습성이 있다.\n— 실뱅 마이야르 의원", hl=["'마법의 돈'"], src="연합뉴스 2026.10.07")
add(120, 121, "stock", q="ballot box voting", ai="Ballot box and voting envelope, 16:9")
add(122, 124, "table", title="여론조사 선두권의 재정 주장", cols=["정당", "주장", "재정 영향"],
    rows=[["국민연합 (극우)", "정년 60세로 인하", "연 90억 유로 추가 (추산)"], ["굴복하지 않는 프랑스 (극좌)", "중앙은행에 진 빚 동결·탕감 요구", "4,880억 유로"]],
    row_at=[(122, "정년"), (124, "멜랑숑")], src="연합뉴스 2026.10.07")
add(125, 125, "labels", img=120, items=[(125, "지출을 늘리자", "지출을"), (125, "vs", "한쪽은 빚"), (125, "빚을 덜어 달라", "덜어")])
add(126, 126, "quote", article="a126", circle_at=[(126, "대선이"), (126, "믿을 만한")], style="dark", img=125, bg_q="paris election poster", bg_ai="Weathered blank election poster boards on a Paris street wall, torn paper, no faces, no people, 16:9",
    text="피치 \"극우·극좌 후보가 선두를 달리는 분열 속에\n프랑스가 '신뢰할 수 있는 재정 전략'에\n합의하기 어려울 것\"", hl=["'신뢰할 수 있는 재정 전략'"], src="조선비즈 2026.10.31")
# ── 경고 3 : 등급 ───────────────────────────────────
add(127, 129, "rating", grade="A+", before="안정적", after="부정적", at=[(128, "A+"), (129, "전망을"), (129, "부정적")], src="한국경제 2026.10.31")
add(130, 131, "ladder", rows=["AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+"], marks={"AA-": "한국", "A+": "프랑스 · 포르투갈 · 벨기에", "BB+": "← 여기부터 투기등급"},
    hl="A+", note_at=(131, "여섯 칸"), src="피치 기준 (한국경제 2026.10.31)")
add(132, 132, "typo", items=[(132, "", "당장 ~~부도~~?", "ivory", "C", "S1", "stamp"), (132, "아니에요", "그건 [[아니에요]]", "black", "C", "S1", "whip", "lime")])
add(133, 135, "ai", prompt="An envelope labeled report card lying on a desk, dramatic light, unexpected letter, documentary photo, 16:9", bubble=(134, "성적표 예고장..?", "예고장"))
add(136, 137, "cycle", items=["등급 ↓", "이자 ↑", "빚 ↑"], title="등급 · 이자 · 빚의 악순환")
add(138, 139, "bar", title="피치가 본 필요 재정 조정 규모", sub="(GDP 대비, 단위 : %)", unit="%",
    items=[("10월 평가", 3.5, "약 3.5%"), ("8월 평가", 3.0, "3.0%")], hl=0, src="한국경제 2026.10.31")
add(140, 141, "quote", article="a140", circle_at=[(140, "540억"), (141, "11월")], style="paper", bg_q="french parliament vote", bg_ai="Parliament voting session, 16:9",
    text="증세와 지출 절감으로 540억 유로 규모의 재정을 개선하는 2027년 예산안…\n의회 과반 확보 못 해 세입 부문 표결은 11월 3일로 미뤄져", hl=["540억 유로", "11월 3일로 미뤄져"], src="매일신문 2026.10.22")
add(142, 142, "stock", q="press conference podium", ai="Empty French government press briefing room with a podium, microphones and blue white red French tricolor flags, no people, no American flags, 16:9", src="조선비즈 2026.10.31")
add(143, 143, "stock", q="old empty classroom", ai="An old but tidy public school classroom with worn wooden desks, no people, 16:9")
add(144, 144, "labels", img=143, items=[(144, "고교생 시위 전국 확산", "시위가")], src="매일신문 2026.10.22")
# ── 한국 ─────────────────────────────────────────────
add(145, 145, "typo", items=[(145, "", "우리는 [[괜찮냐]]?", "black", "C", "S1", "stamp", "lime")])
add(146, 148, "bar", title="GDP 대비 정부 부채", sub="(단위 : %)", unit="%", orient="h",
    items=[("프랑스 (2026년 2분기)", 119, "119%"), ("한국 (IMF 전망)", 46.1, "46.1%")], hl=1, reveal=148, reveal_word="40%대", src="매일신문 2026.10.22 · IMF 2026.10.15 보도")
add(149, 149, "quote", style="dark", bg_q="semiconductor factory", bg_ai="Semiconductor wafer factory clean room, 16:9",
    text="반도체 수출 호조와 달리\n실질임금 감소 · 민간소비 부진 · 청년·제조업 고용 악화\n— KDI 분석을 전한 보도 종합", hl=["실질임금 감소", "청년·제조업 고용 악화"], src="세계일보 등 2026.10.15 보도 종합")
add(150, 150, "stock", q="semiconductor wafer", ai="Semiconductor wafer close-up with reflections, 16:9")
add(151, 151, "stock", q="korean elderly people park", ai="Elderly Korean people in a park, 16:9")
add(153, 153, "stock", q="old photo album", ai="Old family photo album with faded 1980s photos, 16:9")
add(154, 155, "bar", title="합계출산율", sub="(단위 : 명)", unit="명", orient="h",
    items=[("프랑스 (2025년)", 1.56, "1.56명"), ("한국 (2025년)", 0.80, "0.80명")], hl=1, src="INSEE 2026.01 · 국가데이터처 2026.02 (잠정)")
add(156, 158, "labels", bg_q="hospital corridor", bg_ai="Hospital corridor, 16:9", items=[(156, "연금 · 건강보험 = 의무지출", "무조건"), (157, "→ 개혁 늦으면 못 줄임", "개혁이"), (158, "→ 부담은 젊은 세대에게", "젊은 세대")])
add(159, 159, "stock", q="seoul office workers crosswalk", ai="Young Korean office workers crossing a Seoul crosswalk, 16:9")
# ── 마무리 ───────────────────────────────────────────
add(160, 161, "stock", q="paris aerial dusk", ai="Aerial view of Paris at dusk, 16:9")
add(162, 163, "stock", q="trading floor screens", ai="Trading floor screens with market data, 16:9")
add(166, 166, "typo", items=[(166, "", "줄이자고 해도", "ivory", "C", "S1", "stamp"), (166, "번번이", "번번이 [[멈춰 서는]] 나라", "black", "C", "S2", "whip", "pink"), (166, "프랑스", "프랑스", "pink", "C", "S0", "stamp")])
add(167, 167, "stock", q="french flag waving", ai="French flag waving against the sky, 16:9")
add(168, 169, "stock", q="seoul night aerial", ai="Aerial view of Seoul at night, 16:9")


# 기사 캡처(assets/article/aNNN.png + json)가 있으면 글자 카드 대신 실제 기사 화면 + 빨간 동그라미
import os as _os
_AD = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets", "article")
for _s in S:
    if _s.get("article") and _os.path.exists(_os.path.join(_AD, _s["article"] + ".png")) and _os.path.exists(_os.path.join(_AD, _s["article"] + ".json")):
        _s["type"] = "article"; _s.pop("src", None)
