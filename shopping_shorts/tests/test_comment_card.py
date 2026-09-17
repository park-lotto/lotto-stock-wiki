from pathlib import Path

from PIL import Image
from PIL import ImageDraw

from shopping_shorts import comment_card


def test_styles_are_the_two_public_presets():
    assert [item["id"] for item in comment_card.styles()] == [
        "dark_social",
        "premium_pop",
    ]


def test_normalize_clamps_values_and_rejects_unknown_style():
    spec = comment_card.normalize({
        "style": "not-a-style",
        "author": "A" * 90,
        "text": "B" * 600,
        "likes": -2,
        "x": 500,
        "y": -10,
        "width": 5000,
        "start": -3,
        "dur": 0.1,
    })
    assert spec["style"] == "dark_social"
    assert len(spec["author"]) == 40
    assert len(spec["text"]) == 280
    assert spec["likes"] == 0
    assert spec["x"] == 100
    assert spec["y"] == 0
    assert spec["width"] == 980
    assert spec["start"] == 0
    assert spec["dur"] == 0.5


def test_render_both_styles_to_nonempty_transparent_png(tmp_path):
    for style in ("dark_social", "premium_pop"):
        out = tmp_path / f"{style}.png"
        result = comment_card.render_to({
            "style": style,
            "author": "마켓",
            "age": "53분 전",
            "text": "이거 정말 개웃기네요 ㅋㅋㅋ 둘이 케미 진짜 좋았음",
            "likes": 38000,
        }, out)
        assert result == out
        assert out.exists()
        with Image.open(out) as image:
            assert image.mode == "RGBA"
            assert image.width == comment_card.CARD_WIDTH
            assert 260 <= image.height <= 720
            alpha = image.getchannel("A")
            assert alpha.getextrema()[0] == 0
            assert alpha.getextrema()[1] > 150


def test_missing_avatar_uses_initial_fallback(tmp_path):
    out = tmp_path / "fallback.png"
    comment_card.render_to({
        "style": "dark_social",
        "author": "로또",
        "text": "프로필 폴백 확인",
        "avatar_path": str(tmp_path / "missing.png"),
    }, out)
    assert out.exists()


def test_cache_key_is_stable_and_changes_with_visible_content():
    base = {"style": "dark_social", "author": "로또", "text": "좋아요"}
    assert comment_card.cache_key(base) == comment_card.cache_key(dict(base))
    assert comment_card.cache_key(base) != comment_card.cache_key({**base, "text": "다른 댓글"})


def test_cache_key_changes_when_renderer_version_changes(monkeypatch):
    spec = {"style": "dark_social", "text": "캐시 버전"}
    before = comment_card.cache_key(spec)
    monkeypatch.setattr(comment_card, "RENDER_VERSION", comment_card.RENDER_VERSION + 1)
    assert comment_card.cache_key(spec) != before


def test_premium_action_pill_has_readable_light_text(tmp_path):
    out = tmp_path / "premium.png"
    comment_card.render_to({"style": "premium_pop", "text": "한 줄 댓글"}, out)
    with Image.open(out).convert("RGB") as image:
        pill = image.crop((comment_card.CARD_WIDTH - 200, image.height - 86,
                           comment_card.CARD_WIDTH - 76, image.height - 59))
        light_pixels = sum(1 for r, g, b in pill.getdata() if r > 230 and g > 230 and b > 230)
        assert light_pixels > 40


def test_wrap_keeps_words_together_when_each_word_fits():
    draw = ImageDraw.Draw(Image.new("RGB", (800, 200)))
    text = "이 방법 알고 나서 진짜 생활이 편해졌어요. 가족들도 어디서 샀냐고 물어봐요!"
    lines = comment_card._wrap(draw, text, comment_card._font(36), 700, 4)
    for word in text.split():
        assert any(word in line for line in lines), f"단어가 중간에서 잘림: {word} / {lines}"
