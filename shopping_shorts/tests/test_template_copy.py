from shopping_shorts.template_copy import EVEN_SHOPPING, issues, scene_text, split_hook


def test_explicit_two_line_title_is_never_reflowed():
    assert split_hook("건망증 환자를 살려낸\n일본 천재의 발명품") == (
        "건망증 환자를 살려낸",
        "일본 천재의 발명품",
    )


def test_support_copy_drives_hook_band_and_body_title():
    text = scene_text({
        "text": "친구가 건넨 물건\n써보니 반전이었음",
        "subline": "대체 이걸 건넨 이유는?",
        "copy_family": "instagram_story",
    })
    assert text["hook1"] == "친구가 건넨 물건"
    assert text["hook2"] == "써보니 반전이었음"
    assert text["supportTitle"] == "대체 이걸 건넨 이유는?"
    assert text["bodyTitle"] == "대체 이걸 건넨 이유는?"


def test_even_contract_rejects_overflow_instead_of_shrinking_font():
    assert EVEN_SHOPPING.hook_line_max == 11
    found = issues({
        "hook1": "가나다라마바사아자차카타",
        "hook2": "짧은 둘째 줄",
        "bodyTitle": "보조 제목",
        "caption": "본문 자막",
    })
    assert "훅 제목 1은 공백 포함 11자 이하여야 합니다" in found


def test_youtube_and_instagram_share_the_same_visual_contract():
    youtube = scene_text({"text": "한국 천재가 만든\n뜻밖의 발명품", "subline": "이 물건의 정체는?"})
    instagram = scene_text({"text": "시어머니가 줬는데\n써보니 반전이었음", "subline": "이걸 건넨 이유는?"})
    assert youtube.keys() == instagram.keys()
    assert not issues({**youtube, "caption": "첫 장면"})
    assert not issues({**instagram, "caption": "첫 장면"})
