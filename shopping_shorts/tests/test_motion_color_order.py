from unittest.mock import patch

from shopping_shorts import video_assemble


def _run(deco, tmp_path):
    """_burn_captions를 ffmpeg 없이 돌리고, 실행된 커맨드를 돌려준다."""
    seen = {}

    def fake_run(cmd, cwd=None):
        seen["cmd"] = cmd
        return None

    plan = {"beats": [{"beat_idx": 0, "role": "hook", "narration": "훅 문장"}]}
    with patch.object(video_assemble, "_run_ffmpeg", fake_run), \
         patch.object(video_assemble, "_resolve_font", return_value=str(tmp_path / "f.ttf")), \
         patch.object(video_assemble, "shutil"), \
         patch.object(video_assemble, "_probe_duration", return_value=3.0):
        video_assemble._burn_captions("in.mp4", plan, {0: "a.mp3"}, str(tmp_path / "out.mp4"),
                                      tmp_path, headcopy=None, caption_style=None, deco=deco)
    return seen["cmd"]


def test_색감필터는_scale직후_drawtext앞에_온다(tmp_path):
    cmd = _run({"motion": {"color_filter": "eq=saturation=1.5"}}, tmp_path)
    vf = cmd[cmd.index("-vf") + 1]
    assert "eq=saturation=1.5" in vf
    assert vf.index("eq=saturation=1.5") < vf.index("drawtext"), \
        "색감이 drawtext 뒤에 오면 자막색이 물든다"
    assert vf.index("scale=") < vf.index("eq=saturation=1.5")


def test_색감필터가_없으면_vf_무변경(tmp_path):
    cmd = _run({}, tmp_path)
    vf = cmd[cmd.index("-vf") + 1]
    assert "eq=" not in vf
