# -*- coding: utf-8 -*-
"""구조 템플릿 슬롯 조립 — 사장님 지시("딱 들어갈 말들만 있음 되게", 2026-08-19).

★검증의 초점은 "어떤 재료가 와도 **틀이 흔들리지 않는가**"다.
"""
from shopping_shorts import spine_fill as sf

# 라이브 spine 56(유튜브 오용형)의 실제 templates·beat_roles.
SPINE56 = {
    "beat_roles": ["title", "origin", "notice", "cases", "twist"],
    "templates": {
        "origin": ["이게 원래는 {본래용도} 개발된 제품이었음",
                   "원래대로라면 {본래용도} 사용하는게 정석이었음"],
        "notice": ["그런데 사람들은 {속성}을 눈치채고 이걸 엉뚱한 용도로 사용하기 시작하는데",
                   "근데 사람들은 {속성}에 주목하면서"],
        "twist": ["근데 미친 사용법은 따로 있었는데 {용도}"],
    },
}
SLOTS = {"본래용도": "의류 태그 부착용", "속성": "옷감이 손상되지 않는 점",
         "용도": "바지 밑단 줄임", "용도들": "바지 밑단 줄임으로 쓰는가 하면 커튼 길이 조절로도 쓰고요",
         "제품군": "수선도구", "제품": "태그건"}


def test_틀이_글자그대로_지켜진다():
    """★모델이 쓰면 어미가 흔들린다(실측: '…제품이었음' → '…였거든요?').
    조립은 흔들릴 자리가 없다."""
    beats, missing = sf.fill(SPINE56, SLOTS)
    got = {b["role"]: b["text"] for b in beats}
    assert got["origin"] == "이게 원래는 의류 태그 부착용 개발된 제품이었음"
    assert got["twist"] == "근데 미친 사용법은 따로 있었는데 바지 밑단 줄임"
    assert missing == ["title", "cases"]      # 템플릿이 없는 칸은 정직하게 보고한다


def test_CTA는_붙을_자리가_없다():
    """유튜브 썰쇼핑은 no_cta인데 모델 생성본엔 CTA가 붙었다(실측). 조립본엔 없다."""
    beats, _ = sf.fill(SPINE56, SLOTS)
    full = " ".join(b["text"] for b in beats)
    for w in ("남겨주", "댓글", "구독", "링크"):
        assert w not in full


def test_슬롯이_비면_그_문장을_안_쓴다():
    """★빈칸이 그대로 나가는 게 최악이다('이게 원래는  개발된 제품이었음')."""
    beats, missing = sf.fill(SPINE56, {"속성": "봉 없이 걸린다"})
    got = {b["role"]: b["text"] for b in beats}
    assert "origin" not in got and "origin" in missing
    assert got["notice"].startswith("그런데 사람들은 봉 없이 걸린다")


def test_슬롯적은_변형이_대신_걸린다():
    """재료가 부족한 영상에서도 문장이 나오게 — 변형을 여러 개 두는 이유."""
    spine = {"beat_roles": ["bait"],
             "templates": {"bait": ["최근 딱 봤을 때는 평범한 이 {제품군}이",
                                    "딱 봤을 때는 용도를 알기 힘든 이 제품이"]}}
    beats, missing = sf.fill(spine, {})           # 제품군이 없다
    assert not missing
    assert beats[0]["text"] == "딱 봤을 때는 용도를 알기 힘든 이 제품이"


def test_모르는_슬롯_템플릿은_건너뛴다():
    spine = {"beat_roles": ["x"], "templates": {"x": ["{없는슬롯} 어쩌고", "기본 문장"]}}
    beats, _ = sf.fill(spine, {"없는슬롯": "값"})
    assert beats[0]["text"] == "기본 문장"


def test_사례_나열은_개수에_따라_말이_바뀐다():
    assert sf._join_cases(["바지 밑단"]) == "바지 밑단으로 쓰더라고요"
    out = sf._join_cases(["바지 밑단", "커튼 길이", "침대커버", "네번째"])
    assert "쓰는가 하면" in out and "네번째" not in out      # 최대 3개


def test_빈_재료는_슬롯을_안_만든다():
    """빈 문자열을 담아두면 템플릿이 '채워졌다'고 착각한다."""
    s = sf.slots_from_facts({"title": "", "why": []}, {"misuses": []})
    assert s == {}


def test_커버리지가_미리_알려준다():
    done, total, missing = sf.coverage(SPINE56, SLOTS)
    assert (done, total) == (3, 5) and missing == ["title", "cases"]


# ── 조사 자동 교정 ────────────────────────────────────────────────────────
# 슬롯 값은 영상마다 받침이 갈린다. 한 형태로 고정하면 반드시 어색해진다.
def test_조사가_받침에_맞춰_바뀐다():
    f = lambda v, t: sf.fill_one("{용도}" + t, {"용도": v})
    assert f("커튼", "로 쓰고") == "커튼으로 쓰고"          # 받침 O
    assert f("연필", "로 쓰고") == "연필로 쓰고"            # ㄹ 받침은 '로'
    assert f("바지 밑단 줄임", "로 쓰고") == "바지 밑단 줄임으로 쓰고"
    assert f("점", "을 눈치채고") == "점을 눈치채고"
    assert f("걸린다", "을 눈치채고") == "걸린다를 눈치채고"


def test_한글이_아니면_조사를_안_건드린다():
    """영문·숫자 슬롯에 받침 규칙을 들이대면 더 이상해진다."""
    assert sf.fill_one("{제품}로 쓴다", {"제품": "IKEA"}) == "IKEA로 쓴다"


def test_슬롯이_아닌_조사는_안_건드린다():
    """★문장 전체를 훑어 고치면 원래 문장의 조사까지 바꾼다 — 치환 자리에서만 고친다."""
    out = sf.fill_one("사람들은 {속성}을 눈치채고", {"속성": "봉 없이 걸린다"})
    assert out.startswith("사람들은 ")      # '사람들은'이 '사람들는'이 되지 않는다


# ── 여러 영상의 재료 합치기 ────────────────────────────────────────────────
# 사장님: "같은 해외영상이나 여러영상을 가져와도 거기에 딱 들어갈 말들만 있음 되게"
def test_여러영상_재료를_합친다():
    """★한 편만 보면 칸이 빈다 — 실측 2편 모두 misuses가 0건이라 cases·twist가
    통째로 못 채워졌다. 여러 편을 겹쳐야 '엉뚱한 용도'가 보인다."""
    m = sf.merge_sul([
        {"misuses": ["바지 밑단 줄임"], "category_word": "수선도구"},
        {"misuses": ["커튼 길이 조절", "바지 밑단 줄임"], "original_use": ["태그 부착"]},
        {"misuses": ["침대커버 고정"]},
    ])
    assert m["misuses"] == ["바지 밑단 줄임", "커튼 길이 조절", "침대커버 고정"]  # 순서 유지·중복 제거
    slots = sf.slots_from_facts({}, m)
    assert slots["용도들"].startswith("바지 밑단 줄임으로 쓰는가 하면")


def test_합칠_때_깨진_항목은_건너뛴다():
    assert sf.merge_sul([None, "문자열", {"misuses": "단일문자열"}]) == {"misuses": ["단일문자열"]}


def test_합쳐서_빈칸이_메워진다():
    """1편으로는 3/5칸, 3편을 합치면 5/5칸."""
    one = {"original_use": ["태그 부착"], "hidden_property": ["옷감 손상 없음"]}
    two = {"misuses": ["바지 밑단 줄임", "커튼 길이 조절"]}
    spine = dict(SPINE56, templates=dict(SPINE56["templates"],
                                         title=["제조사도 예상 못 한 활용법"],
                                         cases=["{용도들}"]))
    d1 = sf.coverage(spine, sf.slots_from_facts({}, one))
    d3 = sf.coverage(spine, sf.slots_from_facts({}, sf.merge_sul([one, two])))
    assert d1[0] == 3 and d3[0] == 5, (d1, d3)


def test_나열_마지막에도_조사가_붙는다():
    """실측 버그: '아이들 간식용로도' — 나열 꼬리의 조사를 빼먹었다."""
    out = sf._join_cases(["인테리어 소품", "기념일 선물", "아이들 간식용"])
    assert out == "인테리어 소품으로 쓰는가 하면 기념일 선물, 아이들 간식용으로도 쓰고요"


def test_twist는_cases와_다른_사례를_쓴다():
    """실측 버그: cases도 twist도 '인테리어 소품' — 반전이 죽는다."""
    slots = sf.slots_from_facts({}, {"misuses": ["인테리어 소품", "기념일 선물", "간식 보관"]})
    assert slots["용도"] == "인테리어 소품"
    assert slots["용도끝"] == "간식 보관"
    spine = {"beat_roles": ["cases", "twist"],
             "templates": {"cases": ["{용도들}"],
                           "twist": ["근데 미친 사용법은 따로 있었는데 {용도끝}"]}}
    beats, _ = sf.fill(spine, slots)
    cases, twist = beats[0]["text"], beats[1]["text"]
    assert "간식 보관" in twist and not twist.endswith("인테리어 소품")
    assert cases.startswith("인테리어 소품")


def test_사례가_하나뿐이면_반전_몫을_비운다():
    """2026-08-20 변경 — 예전엔 같은 값을 용도·용도끝에 다 넣어 cases와 twist가
    **같은 문장을 두 번** 말했다. 이제는 반전 몫을 비워 twist 템플릿이 안 걸리게 하고,
    호출부가 그 칸을 모델에 맡긴다(겹친 문장을 내놓는 것보다 낫다)."""
    slots = sf.slots_from_facts({}, {"misuses": ["하나뿐"]})
    assert slots["용도"] == "하나뿐"
    assert not slots.get("용도끝")     # 빈 값은 아예 담기지 않는다


def test_실측구조_초보vs고수():
    """살림킹왕짱 실제 자막에서 뽑은 결 — cases는 명사 나열이 아니라 대비 구조다."""
    slots = sf.slots_from_facts({}, {"misuses": ["환기", "주방 벽에 설치해 요리", "빨래 건조"]})
    assert slots["용도"] == "환기" and slots["용도2"] == "주방 벽에 설치해 요리"
    spine = {"beat_roles": ["cases"],
             "templates": {"cases": ["초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요",
                                     "{용도들}"]}}
    assert sf.fill(spine, slots)[0][0]["text"] == \
        "초보들은 기껏해야 환기 정도가 전부였는데 고수들은 주방 벽에 설치해 요리까지 하더라고요"


def test_사례가_하나면_대비구조를_안_쓴다():
    """{용도2}가 없으면 그 문장은 안 걸리고 나열형으로 내려간다 — 빈칸이 안 나간다."""
    slots = sf.slots_from_facts({}, {"misuses": ["환기"]})
    spine = {"beat_roles": ["cases"],
             "templates": {"cases": ["초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요",
                                     "{용도들}"]}}
    assert sf.fill(spine, slots)[0][0]["text"] == "환기로 쓰더라고요"


def test_고조_연결어_템플릿이_사례3개면_걸린다():
    """게이트가 '고조 심화 1회'를 요구한다. 실측 대본에도 '심지어'가 있다."""
    # ★2026-08-20: 반전 몫을 먼저 떼면서 cases가 쓰는 사례가 하나씩 줄었다. 그대로 두면
    #   사용처 3개(실측 오용형 20편 중 6편 = 30%)에서 '심지어'가 사라져 게이트에 걸린다.
    #   → **2슬롯짜리에도 고조어를 넣은 변형**을 앞에 둬서 그 구간을 살린다.
    tmpl = ["초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요 심지어 {용도3}까지 한다는 거",
            "초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 심지어 {용도2}까지 하더라고요",
            "초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요"]
    spine = {"beat_roles": ["cases"], "templates": {"cases": tmpl}}
    # 사용처 4개 → cases가 3개를 쓴다(용도·용도2·용도3). 고조어 1회.
    s4 = sf.slots_from_facts({}, {"misuses": ["A하기", "B하기", "C하기", "D하기"]})
    assert sf.fill(spine, s4)[0][0]["text"].count("심지어") == 1
    # 사용처 3개 → cases가 2개를 쓰고 나머지 1개는 반전 몫. 그래도 고조어 1회.
    s3 = sf.slots_from_facts({}, {"misuses": ["A하기", "B하기", "C하기"]})
    assert sf.fill(spine, s3)[0][0]["text"].count("심지어") == 1
    # 사용처 2개 → cases가 1개뿐이라 대비 문장 자체가 안 걸린다(없는 사례를 지어내지 않는다).
    s2 = sf.slots_from_facts({}, {"misuses": ["A하기", "B하기"]})
    assert not sf.fill(spine, s2)[0]


def test_서술격조사_이었음이_안_깨진다():
    """★실측 사고: '{제품군}이었음'의 '이'를 주격조사로 보고 '주얼리가었음'을 만들었다.
    받침 O는 '이었음', 받침 X는 '였음'이 맞다."""
    f = lambda v: sf.fill_one("이게 원래는 {제품군}이었음", {"제품군": v})
    assert f("수납장") == "이게 원래는 수납장이었음"      # 받침 O(ㅇ)
    assert f("주얼리") == "이게 원래는 주얼리였음"        # 받침 X
    assert f("주방도구") == "이게 원래는 주방도구였음"    # '구'는 받침이 없다
    assert f("holder") == "이게 원래는 holder이었음"     # 한글이 아니면 안 건드린다


def test_긴_조사가_먼저_매칭된다():
    """('이','가')가 앞서면 '이었/이라고/이야'가 통째로 깨진다 — 순서가 규칙이다."""
    assert sf._JOSA_PAIRS[0] == ("이었", "였")
    assert sf.fill_one("{제품}이라고 부른다", {"제품": "집게"}) == "집게라고 부른다"
    assert sf.fill_one("{제품}이라고 부른다", {"제품": "수건"}) == "수건이라고 부른다"


# ── 해외 원본만 담는 경우(2026-08-19 사장님 지시) ──────────────────────────
# 이븐쇼핑류는 화면에 자기 자막 템플릿이 박혀 있어 그 화면을 못 쓴다 → 같은 제품의
# 해외 원본을 담아 다시 만든다. 그때는 **쿠팡 상품이 아예 없어서** {제품}·{효능}·{나라}가
# 영상에서 나와야 한다. 이 폴백이 없으면 은폐형은 조립 자체가 불가능하다.
VIDEO_ONLY = {"product_name": "유청 분리 요거트 메이커",
              "benefits": ["유청이 저절로 분리된다", "통째로 분해돼 세척이 쉽다"],
              "origin_country": "한국", "category_word": "주방템"}


def test_쿠팡_없이_영상만으로_은폐형_슬롯이_찬다():
    s = sf.slots_from_facts({}, VIDEO_ONLY)
    assert s["제품"] == "유청 분리 요거트 메이커"
    assert s["효능"] == "유청이 저절로 분리된다"
    assert s["효능2"] == "통째로 분해돼 세척이 쉽다"
    assert s["나라"] == "한국"


def test_쿠팡_재료가_있으면_그쪽이_먼저다():
    """상세페이지·리뷰가 영상보다 정확하다. 단 **모자란 칸은 영상이 메운다**."""
    s = sf.slots_from_facts({"title": "쿠팡상품명", "why": ["쿠팡효능"], "origin": "미국"},
                            VIDEO_ONLY)
    assert s["제품"] == "쿠팡상품명" and s["효능"] == "쿠팡효능" and s["나라"] == "미국"
    assert s["효능2"] == "통째로 분해돼 세척이 쉽다"      # 쿠팡 why가 1개뿐 → 영상이 채움


def test_여러_원본의_장점이_합쳐진다():
    """★한 영상이 안 말한 장점을 다른 영상이 보여준다 — 그래서 원본을 여러 편 담는다."""
    m = sf.merge_sul([
        {"benefits": ["유청이 저절로 분리된다"], "product_name": "요거트 메이커"},
        {"benefits": ["통째로 분해돼 세척이 쉽다", "유청이 저절로 분리된다"]},
        {"benefits": ["뚜껑이 계량컵이 된다"]},
    ])
    assert m["benefits"] == ["유청이 저절로 분리된다", "통째로 분해돼 세척이 쉽다",
                             "뚜껑이 계량컵이 된다"]        # 순서 유지·중복 제거
    s = sf.slots_from_facts({}, m)
    assert s["효능"] and s["효능2"] and s["효능"] != s["효능2"]


def test_슬롯출처표가_영상폴백을_명시한다():
    """SLOT_SOURCE는 빈칸↔추출의 계약서다 — 폴백이 생겼으면 표도 그렇게 말해야 한다."""
    from shopping_shorts.sul_facts import SLOT_SOURCE
    assert "sul_facts.product_name" in SLOT_SOURCE["제품"]
    assert "sul_facts.benefits" in SLOT_SOURCE["효능"]


def test_나라가_없어도_authority가_채워진다():
    """★실측(2026-08-19): 해외 원본은 제조국을 잘 안 밝힌다. sul_facts가 지어내지 않고
    비우는 건 옳은데, authority 템플릿 3개가 전부 {나라}를 요구해 그 칸이 통째로
    비었다(영어 원본 1편 → 5/6칸). 슬롯 없는 변형을 뒤에 두면 자동으로 내려간다."""
    tmpl = ["이걸 개발한 {나라}의 천재가 돈방석에 앉았다는데",
            "이걸 만든 천재가 떼돈을 벌었다는데"]
    spine = {"beat_roles": ["authority"], "templates": {"authority": tmpl}}
    assert sf.fill(spine, {"나라": "독일"})[0][0]["text"] == \
        "이걸 개발한 독일의 천재가 돈방석에 앉았다는데"
    assert sf.fill(spine, {})[0][0]["text"] == "이걸 만든 천재가 떼돈을 벌었다는데"
    assert sf.fill(spine, {})[1] == []          # 못 채운 칸 없음


def test_은폐형_고조는_장점3개일_때만():
    """게이트가 고조 1회를 요구한다. 장점이 2개뿐이면 지어내지 않고 기본형으로 내려간다."""
    tmpl = ["근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}까지 된다는 거",
            "근데 진짜 충격적인 포인트는 {효능2}"]
    spine = {"beat_roles": ["twist"], "templates": {"twist": tmpl}}
    s3 = sf.slots_from_facts({}, {"benefits": ["A된다", "B된다", "C된다"]})
    assert "심지어" in sf.fill(spine, s3)[0][0]["text"]
    s2 = sf.slots_from_facts({}, {"benefits": ["A된다", "B된다"]})
    assert "심지어" not in sf.fill(spine, s2)[0][0]["text"]


def test_서술형_슬롯_뒤에_어미를_붙이지_않는다():
    """★실측: '{효능3}까지 된다는 거'가 '아낄 수 있다까지 된다는 거'가 됐다.
    효능·용도 슬롯은 **서술형 문장**이라 뒤에 어미를 덧붙이면 반드시 깨진다."""
    spine = {"beat_roles": ["twist"],
             "templates": {"twist": ["근데 진짜 충격적인 포인트는 {효능2} 심지어 {효능3}"]}}
    s = sf.slots_from_facts({}, {"benefits": ["A", "꾸덕해진다", "비용을 아낄 수 있다"]})
    out = sf.fill(spine, s)[0][0]["text"]
    assert out.endswith("비용을 아낄 수 있다")
    assert "있다까지" not in out


class TestCasesTwistNoOverlap:
    """★나열(cases)과 반전(twist)이 **같은 사용처를 두 번 말하면 안 된다**.

    2026-08-20 재발 버그: `용도끝`을 그냥 마지막 항목으로 뽑아서, 사용처가 2~3개면
    cases가 이미 말한 것을 twist가 그대로 반복했다(반전이 죽는다).
    히트작 200편 오용형 정밀분해 20편의 사용처 개수는 2개 5편·3개 6편 = **55%가 이 구간**.
    """

    CASES = ["초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요 "
             "심지어 {용도3}까지 한다는 거",
             "초보들은 기껏해야 {용도} 정도가 전부였는데 고수들은 {용도2}까지 하더라고요",
             "{용도들}", "{용도}로 쓰더라고요"]
    SPINE = {"beat_roles": ["cases", "twist"],
             "templates": {"cases": CASES,
                           "twist": ["근데 미친 사용법은 따로 있었는데 {용도끝}"]}}
    ALL = ["빨래 바구니", "슬라이딩 신발장", "2층 수납함", "화분 걸이", "책상 정리대"]

    def _beats(self, n):
        slots = sf.slots_from_facts(None, {"misuses": self.ALL[:n]})
        beats, missing = sf.fill(self.SPINE, slots)
        return {b["role"]: b["text"] for b in beats}, missing, slots

    def test_사용처_2개부터_5개까지_반전이_안_겹친다(self):
        for n in (2, 3, 4, 5):
            _b, _m, slots = self._beats(n)
            said = [slots.get(k) for k in ("용도", "용도2", "용도3") if slots.get(k)]
            assert slots["용도끝"] not in said, "사용처 %d개에서 반전이 나열과 겹쳤다" % n

    def test_반전은_언제나_마지막_사용처다(self):
        """실측: 오용형 20편 중 클라이맥스가 마지막인 편이 14편. 원본의 결이다."""
        for n in (2, 3, 4, 5):
            _b, _m, slots = self._beats(n)
            assert slots["용도끝"] == self.ALL[n - 1]

    def test_사용처_1개면_반전을_비워_모델에_넘긴다(self):
        """겹친 문장을 억지로 내놓는 것보다 missing으로 넘기는 게 낫다."""
        beats, missing, slots = self._beats(1)
        assert "twist" in missing
        assert not slots.get("용도끝")
        assert "cases" in beats          # 나열은 그대로 나온다(회귀 0)

    def test_나열은_반전_몫을_빼고_채운다(self):
        """사용처 4개 → cases가 3개(용도·용도2·용도3), twist가 남은 1개."""
        beats, _m, slots = self._beats(4)
        assert (slots["용도"], slots["용도2"], slots["용도3"]) == tuple(self.ALL[:3])
        assert "심지어 2층 수납함" in beats["cases"]
        assert "화분 걸이" in beats["twist"]
