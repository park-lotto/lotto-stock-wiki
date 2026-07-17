import os, subprocess, shutil, pytest
from shopping_shorts import remotion_render as rr

MOTION = os.path.join(os.path.dirname(rr.__file__), "motion")
HAS_NODE = shutil.which("node") and os.path.isdir(os.path.join(MOTION, "node_modules"))


def test_unavailable_raises(monkeypatch):
    monkeypatch.setattr(rr, "_motion_ready", lambda: False)
    with pytest.raises(rr.RemotionUnavailable):
        rr.render({"videoSrc": "x.mp4"}, "x.mp4", "o.mp4")


@pytest.mark.skipif(not HAS_NODE, reason="node/remotion 미설치 환경에선 True 단언 불가")
def test_motion_ready_true_in_env():
    assert rr._motion_ready() is True          # node 있는 이 환경


def test_motion_ready_false_without_node(monkeypatch):
    monkeypatch.setattr(rr.shutil, "which", lambda _: None)
    assert rr._motion_ready() is False          # node 부재 감지


def test_motion_ready_false_without_modules(monkeypatch, tmp_path):
    monkeypatch.setattr(rr, "MOTION", str(tmp_path))  # node_modules 없음
    assert rr._motion_ready() is False


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


def _fake_stage_run(cmd, **kwargs):
    """node render-scene.mjs / ffmpeg 둘 다 흉내: 마지막 인자(출력경로)에 빈 파일만 생성."""
    class R:
        returncode = 0
        stdout = ""
        stderr = ""
    target = cmd[-1]
    with open(target, "wb") as f:
        f.write(b"0")
    return R()


def test_video_src_path_traversal_blocked(monkeypatch, tmp_path):
    """plan['videoSrc']에 ../ 순회가 섞여도 pub(motion/public) 밖으로 못 나가야 한다.
    실 node/ffmpeg는 subprocess.run 스텁으로 대체(빠른 단위테스트)."""
    monkeypatch.setattr(rr, "_motion_ready", lambda: True)
    monkeypatch.setattr(rr.subprocess, "run", _fake_stage_run)

    pub = os.path.join(MOTION, "public")
    safe_dest = os.path.join(pub, "evil.mp4")
    escaped_dest = os.path.join(MOTION, "evil.mp4")  # pub 한 단계 위 = 순회 성공 시 목적지
    for p in (safe_dest, escaped_dest):
        if os.path.isfile(p):
            os.remove(p)

    src = tmp_path / "src.mp4"
    src.write_bytes(b"source-video")
    out = tmp_path / "o.mp4"

    try:
        rr.render({"videoSrc": "../evil.mp4"}, str(src), str(out))
        assert os.path.isfile(safe_dest), "basename 처리된 파일은 pub 안에 있어야 한다"
        assert not os.path.isfile(escaped_dest), "순회 목적지(pub 밖)에는 아무것도 쓰이면 안 된다"
    finally:
        for p in (safe_dest, escaped_dest):
            if os.path.isfile(p):
                os.remove(p)


def test_video_src_empty_after_basename_falls_back(monkeypatch, tmp_path):
    """videoSrc가 "../"처럼 basename이 빈 문자열이 되는 경우 job_src.mp4로 대체돼야 한다."""
    monkeypatch.setattr(rr, "_motion_ready", lambda: True)
    monkeypatch.setattr(rr.subprocess, "run", _fake_stage_run)

    pub = os.path.join(MOTION, "public")
    fallback_dest = os.path.join(pub, "job_src.mp4")
    if os.path.isfile(fallback_dest):
        os.remove(fallback_dest)

    src = tmp_path / "src.mp4"
    src.write_bytes(b"source-video")
    out = tmp_path / "o.mp4"

    try:
        rr.render({"videoSrc": "../"}, str(src), str(out))
        assert os.path.isfile(fallback_dest)
    finally:
        if os.path.isfile(fallback_dest):
            os.remove(fallback_dest)
