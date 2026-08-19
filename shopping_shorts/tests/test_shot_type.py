"""직촬(본인 얼굴) 판정 — 재료로 못 쓰는 채널 거르기 (2026-08-19).

사장님: "쇼핑쇼츠로 안되는 채널들이 많을거고 **직촬 본인얼굴 나오는 채널들 안되는거야**"

왜 필요한가:
지금 정리 규칙은 "제품 얘기를 하는가"(쇼핑비율)만 본다. 그런데 직촬 채널은 쇼핑 얘기를
제대로 하기 때문에 **오히려 우량으로 살아남는다.** 우리 목적은 '남의 영상을 재료로 써서
새 영상을 만드는 것'이라, 리뷰어 얼굴이 화면의 주인공이면 재료로 못 쓴다.

C단계 실측(2026-08-19, 표본 31채널): selfshot 17% · product 83%.
살아있는 채널 489개 기준 추정 80여 개가 직촬이고, 그중엔 [연예인결합] 스타일이 붙은
'핫앤템'도 있었다 — 애써 발굴한 채널에도 섞여 있다.

★비용 0원: `subject_tags_vision`가 이미 썸네일을 Gemini에 보낸다. 같은 호출의 프롬프트에
  질문 한 줄, 스키마에 필드 2개를 더할 뿐이라 **호출 수가 안 는다**.
★기존 경로를 안 깨는 게 최우선 — 옛 태그(필드 없음)도 그대로 읽혀야 한다.
"""
import json

from shopping_shorts.store import Store


def test_스키마에_shot_type이_있다():
    from shopping_shorts.video_analysis import _SUBJECT_TAGS_SCHEMA as S
    props = S["properties"]
    assert "shot_type" in props, "shot_type 필드가 없다"
    assert "face_prominent" in props


def test_프롬프트가_직촬을_묻는다():
    from shopping_shorts.video_analysis import _SUBJECT_TAGS_PROMPT as P
    assert "shot_type" in P
    assert "selfshot" in P and "product" in P


def test_기존_subject_keywords는_그대로다():
    """★회귀 방지: 검색이 이 두 필드를 쓴다. 없어지면 랭킹 검색이 통째로 죽는다."""
    from shopping_shorts.video_analysis import _SUBJECT_TAGS_SCHEMA as S
    assert "subject" in S["properties"]
    assert "keywords" in S["properties"]
    assert set(S["required"]) >= {"subject", "keywords"}


def test_shot_type은_required가_아니다():
    """★모델이 안 채워도 태깅 전체가 실패하면 안 된다 — 주제태그가 본업이다."""
    from shopping_shorts.video_analysis import _SUBJECT_TAGS_SCHEMA as S
    assert "shot_type" not in S["required"]
    assert "face_prominent" not in S["required"]


# ── 저장·조회 왕복 ────────────────────────────────────────────────────────
def test_shot_type이_DB왕복에서_살아남는다(tmp_path):
    """★조용한 실패 방지: 판정해도 DB가 안 실어주면 정리 규칙이 영영 못 읽는다."""
    st = Store(str(tmp_path / "t.db"))
    st.save_vision_tags("abc", "미니세탁기", ["세탁기", "자취템"],
                        shot_type="selfshot", face_prominent=True)
    got = st.vision_tags_map(["abc"])["abc"]
    assert got["subject"] == "미니세탁기"
    assert got["shot_type"] == "selfshot"
    assert got["face_prominent"] is True


def test_옛_태그는_빈값으로_읽힌다(tmp_path):
    """★회귀: 이미 쌓인 태그엔 이 필드가 없다. 읽다가 터지면 안 된다."""
    st = Store(str(tmp_path / "t.db"))
    st.save_vision_tags("old", "선풍기", ["선풍기"])      # 새 인자 없이 = 옛 호출부
    got = st.vision_tags_map(["old"])["old"]
    assert got["subject"] == "선풍기"
    assert got.get("shot_type", "") == ""
    assert not got.get("face_prominent")


def test_기존_호출부_시그니처를_안_깬다(tmp_path):
    """vision_tagging.py는 아직 3개 인자로 부른다 — 그대로 돌아야 한다."""
    st = Store(str(tmp_path / "t.db"))
    st.save_vision_tags("x", "s", ["k"])                 # 예외 없이 통과해야 한다
    assert st.vision_tags_map(["x"])["x"]["subject"] == "s"
