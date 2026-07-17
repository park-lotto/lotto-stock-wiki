import os, subprocess, shutil, pytest
from shopping_shorts import remotion_render as rr

MOTION = os.path.join(os.path.dirname(rr.__file__), "motion")
HAS_NODE = shutil.which("node") and os.path.isdir(os.path.join(MOTION, "node_modules"))


def test_unavailable_raises(monkeypatch):
    monkeypatch.setattr(rr, "_motion_ready", lambda: False)
    with pytest.raises(rr.RemotionUnavailable):
        rr.render({"videoSrc": "x.mp4"}, "x.mp4", "o.mp4")


@pytest.mark.skipif(not HAS_NODE, reason="node/remotion 미설치")
def test_real_render_makes_nonempty_mp4(tmp_path):
    src = os.path.join(MOTION, "public", "full.mp4")  # 이전 세션 산출물이 있으면 사용
    if not os.path.isfile(src):
        pytest.skip("샘플 조립본 없음")
    plan = {"videoSrc": "full.mp4", "durationInFrames": 60, "themeName": "warm",
            "sections": [{"s": 0, "e": 2, "label": "T"}],
            "beats": [{"s": 0, "e": 2, "cap": "테스트"}], "fx": []}
    out = str(tmp_path / "o.mp4")
    rr.render(plan, src, out)
    assert os.path.getsize(out) > 10000
