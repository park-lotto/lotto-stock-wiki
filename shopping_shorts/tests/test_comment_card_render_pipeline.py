from pathlib import Path

from shopping_shorts import mix_pipeline, video_assemble


def test_resolve_deco_media_renders_comment_card_for_final_video(tmp_path):
    deco = {
        "comment_card": {
            "style": "dark_social",
            "author": "로또",
            "text": "완성본에도 나오는 댓글",
            "likes": 1200,
            "x": 50,
            "y": 72,
            "width": 860,
            "start": 1.2,
            "dur": 2.5,
        }
    }
    resolved = mix_pipeline.resolve_deco_media(deco, tmp_path)
    card = resolved["comment_card"]
    assert Path(card["_abspath"]).is_file()
    assert card["style"] == "dark_social"
    assert card["start"] == 1.2
    assert card["dur"] == 2.5


def test_comment_layer_uses_loop_fade_and_slide_up_timing():
    layers = [{
        "_abspath": "card.png",
        "x": 50,
        "y": 72,
        "width": 860,
        "alpha": 1,
        "start": 1.2,
        "dur": 2.5,
        "loop": True,
        "animation": "slide_up",
    }]
    inputs, filters, _, _ = video_assemble._motion_layer_filters(layers, 1, "v0")
    assert inputs[:2] == ["-loop", "1"]
    joined = ";".join(filters)
    assert "fade=t=in:st=1.200:d=0.220:alpha=1" in joined
    assert "fade=t=out:st=3.480:d=0.220:alpha=1" in joined
    assert "sin(PI*(t-1.200)/0.420)" in joined
    assert "between(t,1.200,3.700)" in joined
    assert "shortest=1" in joined
