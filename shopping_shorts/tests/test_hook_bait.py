"""스팸성 훅 필터(is_engagement_bait) — 오늘 실측 문구로 고정.

훅 오염원은 인스타 참여유도 멘트(댓글/프로필/DM 남겨주세요 류). 실제 스토리 훅은 통과,
참여유도 멘트는 차단해야 한다."""
from shopping_shorts.hook_harvest import is_engagement_bait

# 오늘(2026-07-22) 실제 흡수분에서 뽑힌 참여유도성 훅 — 전부 차단(True)돼야 한다
BAIT = [
    "📩 제품 정보 DM으로 바로 보내드려요",
    "⚠️ 팔로우 후 댓글 남겨주셔야 오류 없이 정상 발송됩니다",
    "🔗 프로필 링크 No.284 에서도 바로 확인 가능해요",
    "‘책상’ 남겨주세요 정보 보내드릴게요",
    "♥️댓글에 나도 남겨주세요😉",
    "💬 댓글에 \"아무거나 두글자\" 남겨주시면",
    "‼️💡 아무글자 남기면 정보 전송됩니다.",
    "💖 디엠없으면 요청함/숨김함도 확인해보세요.",
    "댓글에 [빵] 남겨주시면 레시피 바로 알려드릴게요!",
]

# 오늘 실제로 뽑힌 진짜 스토리 훅 — 전부 통과(False)해야 한다
REAL = [
    "빵집 사장님들도 절대 안 알려주는",
    "친구 남편이 피부과의사인데",
    "평생 써먹는 대파 보관 비법 알아왔어요🔥",
    "여러분 새송이버섯은 무조건 이렇게 드셔보세요!🍄",
    "남편이 생일 선물로 사준 가방보고 저 소리질렀잖아요",
    "시댁 갔다가 욕 한바가지 먹을 뻔했어요 😅",
    "만원으로 끝내는 키 크는 습관, 이거 진짜 효과있어요 ✨",
]


def test_bait_blocked():
    for t in BAIT:
        assert is_engagement_bait(t) is True, f"차단 실패: {t}"


def test_real_hooks_pass():
    for t in REAL:
        assert is_engagement_bait(t) is False, f"오차단(진짜 훅): {t}"


def test_empty_is_not_bait():
    assert is_engagement_bait("") is False
    assert is_engagement_bait(None) is False
