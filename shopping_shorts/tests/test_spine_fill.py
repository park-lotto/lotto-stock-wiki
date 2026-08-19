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
