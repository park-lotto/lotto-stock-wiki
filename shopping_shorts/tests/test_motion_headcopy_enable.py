from unittest.mock import patch

from shopping_shorts.video_assemble import _headcopy_drawtext_parts


def _hc():
    return {"text": "이거 실화?", "color": "#FFE100", "size": 70, "x": 50, "y": 12}


def test_enable이_없으면_기존처럼_enable절이_안붙는다(tmp_path):
    with patch("shopping_shorts.video_assemble._segmented_drawtext",
               return_value=["drawtext=textfile=hc_0.txt:y=100"]):
        parts = _headcopy_drawtext_parts(_hc(), tmp_path)
    assert parts == ["drawtext=textfile=hc_0.txt:y=100"]
    assert "enable" not in parts[0]


def test_enable을_주면_모든_조각에_붙는다(tmp_path):
    with patch("shopping_shorts.video_assemble._segmented_drawtext",
               return_value=["drawtext=a", "drawtext=b"]):
        parts = _headcopy_drawtext_parts(_hc(), tmp_path, enable="between(t,0,3.000)")
    assert parts == ["drawtext=a:enable='between(t,0,3.000)'",
                     "drawtext=b:enable='between(t,0,3.000)'"]
