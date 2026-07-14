from shopping_shorts.narration_naturalize import (
    naturalize, merge_profile, DEFAULT_PROFILE, _enforce_total_tag_cap,
)


def _only(stage):
    """해당 스테이지만 켜고 나머지 전부 끈 프로파일."""
    p = merge_profile({})
    for k, v in p.items():
        if isinstance(v, dict) and "on" in v:
            v["on"] = (k == stage)
    return p


def test_merge_profile_fills_defaults():
    p = merge_profile({"spoken_style": {"intensity": 0.9}})
    assert p["spoken_style"]["intensity"] == 0.9
    assert p["spoken_style"]["on"] is True          # 기본 채워짐
    assert p["normalize"]["on"] is True

def test_normalize_percent_and_units():
    p = _only("normalize")
    assert naturalize("50% 할인, 3kg 무게", p) == "오십 퍼센트 할인, 삼 킬로그램 무게"

def test_normalize_decimal():
    p = _only("normalize")
    assert naturalize("3.5kg", p) == "삼 점 오 킬로그램"

def test_off_is_noop():
    p = _only("normalize")
    p["normalize"]["on"] = False
    assert naturalize("50%", p) == "50%"

def test_spoken_style_converts_formal_endings():
    p = _only("spoken_style")
    p["spoken_style"]["intensity"] = 1.0   # 전부 변환
    # 문어체 종결 → 서울 구어체
    assert naturalize("이건 정말 좋습니다.", p) == "이건 정말 좋아요."
    assert naturalize("가격이 저렴합니다.", p) == "가격이 저렴해요."

def test_spoken_style_intensity_partial_deterministic():
    p = _only("spoken_style")
    p["spoken_style"]["intensity"] = 0.5   # 절반만(앞에서부터 결정적)
    # 히트 문장: 좋습니다(o) 편합니다(o) → 2개. take=int(2*0.5)=1 → 앞의 1개만 변환.
    src = "좋습니다. 쌉니다. 편합니다. 예쁩니다."  # 4개 종결
    out = naturalize(src, p)
    assert out == "좋아요. 쌉니다. 편합니다. 예쁩니다."   # 앞에서부터 절반(=1개)만
    assert out == naturalize(src, p)                     # 결정적

def test_spoken_style_preserves_whitespace():
    # 구분자 없는(공백 없는) 문장 경계에서도 공백을 새로 삽입/삭제하지 않음
    p = _only("spoken_style"); p["spoken_style"]["intensity"] = 1.0
    # 쌉니다는 매핑에 없어 그대로 유지. 첫 문장만 변환, 공백 훼손 없음.
    assert naturalize("좋습니다.쌉니다.", p) == "좋아요.쌉니다."

def test_spoken_style_off_noop():
    p = _only("spoken_style"); p["spoken_style"]["on"] = False
    assert naturalize("좋습니다.", p) == "좋습니다."

def test_pronunciation_dict_replace():
    p = _only("pronunciation")
    p["pronunciation"]["dict"] = {"SNS": "에스엔에스", "AI": "에이아이"}
    assert naturalize("SNS와 AI", p) == "에스엔에스와 에이아이"

def test_pronunciation_longest_first():
    p = _only("pronunciation")
    p["pronunciation"]["dict"] = {"A": "에이", "AI": "에이아이"}
    # 긴 키 우선(AI가 A로 먼저 안 깨지게)
    assert naturalize("AI", p) == "에이아이"

def test_phrasing_inserts_comma_after_connectives():
    p = _only("phrasing")
    p["phrasing"]["intensity"] = 1.0
    # 2음절 연결어미(은데) 뒤에만 쉼표 삽입 → 호흡. 단음절 '고'는 오탐방지로 제외됨.
    assert naturalize("이게 싸고 좋은데 품질도 최고예요", p) == "이게 싸고 좋은데, 품질도 최고예요"

def test_phrasing_no_false_positive_on_noun():
    # '고'/'며'를 목록에서 뺐으므로 명사('참고','최고')가 오탐되지 않음
    p = _only("phrasing"); p["phrasing"]["intensity"] = 1.0
    assert naturalize("참고 하세요", p) == "참고 하세요"        # 오탐 없음(불변)
    assert naturalize("싸고 좋은데 최고예요", p) == "싸고 좋은데, 최고예요"  # 은데 뒤에만

def test_phrasing_skip_if_already_punctuated():
    p = _only("phrasing"); p["phrasing"]["intensity"] = 1.0
    assert naturalize("좋은데, 좋아요", p) == "좋은데, 좋아요"   # 이미 쉼표면 중복삽입 안 함

def test_phrasing_off_noop():
    p = _only("phrasing"); p["phrasing"]["on"] = False
    assert naturalize("싸고 좋은데 최고", p) == "싸고 좋은데 최고"

def test_endings_softens_period_to_ellipsis():
    p = _only("endings"); p["endings"]["intensity"] = 1.0
    # 마침표 종결을 부드러운 여운(…)으로(모두)
    assert naturalize("좋아요. 예뻐요.", p) == "좋아요… 예뻐요…"

def test_endings_partial_deterministic():
    p = _only("endings"); p["endings"]["intensity"] = 0.5
    src = "하나. 둘. 셋. 넷."           # 마침표 4개, take=int(4*0.5)=2 → 앞의 2개만
    assert naturalize(src, p) == "하나… 둘… 셋. 넷."   # 앞에서부터 절반
    assert naturalize(src, p) == naturalize(src, p)  # 결정적

def test_endings_off_noop():
    p = _only("endings"); p["endings"]["on"] = False
    assert naturalize("좋아요.", p) == "좋아요."

def test_fillers_prepends_one_and_caps():
    p = _only("fillers")
    p["fillers"]["intensity"] = 1.0
    p["fillers"]["bank"] = ["음"]
    out = naturalize("이거 진짜 좋아요", p)
    assert out.startswith("음, ")                 # 앞에 추임새 1개
    # 하드캡: intensity=1이어도 max_fillers_per_text(기본1) 초과 안 함
    assert out.count("음,") == 1

def test_fillers_off_noop():
    p = _only("fillers"); p["fillers"]["on"] = False
    assert naturalize("이거 좋아요", p) == "이거 좋아요"

def test_fillers_bank_selection_deterministic_by_beat():
    p = _only("fillers"); p["fillers"]["intensity"] = 1.0
    p["fillers"]["bank"] = ["음", "아", "그"]
    a = naturalize("좋아요", p, beat_index=0, beat_total=3)
    b = naturalize("좋아요", p, beat_index=1, beat_total=3)
    assert a != b            # 비트마다 다른 필러(결정적 순환)
    assert a == naturalize("좋아요", p, beat_index=0, beat_total=3)

def test_emotion_arc_tags_by_role():
    p = _only("emotion_arc"); p["emotion_arc"]["intensity"] = 1.0
    hook = naturalize("이거 봐요", p, beat_role="hook")
    cta = naturalize("링크 눌러요", p, beat_role="cta")
    assert hook.startswith("[") and cta.startswith("[")
    assert hook != cta                    # 역할마다 다른 태그(곡선)

def test_emotion_arc_caps_one_tag_per_beat():
    p = _only("emotion_arc"); p["emotion_arc"]["intensity"] = 1.0
    out = naturalize("좋아요", p, beat_role="hook")
    assert out.count("[") == 1            # 비트당 태그 ≤ 1 (하드캡)

def test_emotion_arc_low_intensity_no_tag():
    p = _only("emotion_arc"); p["emotion_arc"]["intensity"] = 0.0
    assert naturalize("좋아요", p, beat_role="hook") == "좋아요"

def test_emotion_arc_out_of_range_beat_index_no_crash():
    # beat_index > beat_total-1 이어도 pos 클램프로 IndexError 안 남
    p = _only("emotion_arc"); p["emotion_arc"]["intensity"] = 1.0
    out = naturalize("좋아요", p, beat_index=5, beat_total=3)  # 범위 밖
    assert out.endswith("좋아요")            # 크래시 없이 마지막 위치 태그 부여
    assert out.count("[") <= 1

def test_full_pipeline_deterministic():
    p = merge_profile({})   # 전 스테이지 기본 ON
    src = "이건 정말 좋습니다. 50% 할인이고 SNS에서 난리예요"
    p["pronunciation"]["dict"] = {"SNS": "에스엔에스"}
    a = naturalize(src, p, beat_role="hook", beat_index=0, beat_total=3)
    b = naturalize(src, p, beat_role="hook", beat_index=0, beat_total=3)
    assert a == b                          # 완전 결정적

def test_total_tag_cap_across_stages():
    # emotion_arc + intonation 합쳐도 전체 태그 ≤ max_tags_total
    p = merge_profile({})
    p["caps"]["max_tags_total"] = 1
    out = naturalize("좋아요", p, beat_role="hook")
    assert out.count("[") <= 1

def test_intonation_off_noop_when_no_question():
    p = _only("intonation")
    assert naturalize("좋아요", p) == "좋아요"

def test_enforce_total_tag_cap_reduces_exactly():
    # naturalize는 비트당 태그 ≤1만 내보내므로 이 축소경로는 직접 검증.
    src = "[curious] [warm] [excited] 좋아요"   # 태그 3개
    assert _enforce_total_tag_cap(src, 1) == "[curious] 좋아요"          # 앞 1개만 유지
    assert _enforce_total_tag_cap(src, 2) == "[curious] [warm] 좋아요"   # 앞 2개 유지
    assert _enforce_total_tag_cap(src, 0) == "좋아요"                    # 전부 제거
    assert _enforce_total_tag_cap(src, 3) == src                        # cap≥태그수면 무변경
