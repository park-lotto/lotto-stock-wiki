import subprocess
import pytest
from shopping_shorts import scene_cut


def _make_video(path, seconds=2, fps=30, with_audio=True, longer_audio=0.0):
    """테스트용 합성 영상. longer_audio>0이면 오디오가 비디오보다 그만큼 길다
    (실측: 릴스 3편 중 2편이 이 모양이었다 — 스펙 §3.5)."""
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"testsrc=size=320x568:rate={fps}:duration={seconds}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i",
                f"sine=frequency=440:duration={seconds + longer_audio}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac"]
    cmd += [str(path)]
    subprocess.run(cmd, check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return path


def test_video_fps_reads_exact_rational(tmp_path):
    f = _make_video(tmp_path / "a.mp4", seconds=1, fps=30)
    assert scene_cut.video_fps(f) == 30.0


def test_video_frame_count_counts_video_not_audio(tmp_path):
    # 오디오가 0.5초 더 길다 — 컨테이너 길이를 쓰면 프레임 수가 부풀려진다
    f = _make_video(tmp_path / "b.mp4", seconds=2, fps=30, longer_audio=0.5)
    assert scene_cut.video_frame_count(f) == 60


def test_video_fps_raises_on_missing_file(tmp_path):
    with pytest.raises(RuntimeError):
        scene_cut.video_fps(tmp_path / "nope.mp4")


def test_video_frame_count_raises_on_missing_file(tmp_path):
    with pytest.raises(RuntimeError):
        scene_cut.video_frame_count(tmp_path / "nope.mp4")


def test_video_fps_reads_non_integer_rational(tmp_path):
    """★24000/1001 같은 NTSC 프레임레이트도 정확해야 한다. 이 모듈의 존재 이유가
    프레임 번호 계산이고, fps가 틀리면 round(t*fps)가 통째로 틀어진다."""
    f = tmp_path / "ntsc.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x568:rate=24000/1001:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    fps = scene_cut.video_fps(f)
    assert abs(fps - 24000 / 1001) < 1e-9      # 23.976023976...
    assert fps != 24.0                          # 24로 반올림돼 있으면 실패


def _make_three_scene_video(path, fps=30):
    """색이 확 바뀌는 3장면(각 1초). 경계는 30·60프레임에 있어야 한다.

    ★색 선택 주의: ffmpeg의 scene 점수는 주로 luma(밝기) 차이로 계산된다.
    CSS "red"(Y≈76)와 "green"(Y≈75)은 밝기가 거의 같아 육안으론 확 바뀌어도
    scene 점수가 문턱값 0.3을 못 넘는다(실측 확인됨). black/white/red는
    두 경계 모두 밝기 차가 커서 안정적으로 검출된다."""
    parts = []
    for color in ("black", "white", "red"):
        p = path.parent / f"_{color}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", f"color=c={color}:size=320x568:rate={fps}:duration=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL)
        parts.append(p)
    lst = path.parent / "_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return path


def test_detect_cuts_returns_ordered_frame_pairs_within_video(tmp_path):
    """detect_cuts의 진짜 계약: 0에서 시작하거나 total에 닿는다는 보장은 없다
    (min_seconds 미만 찌꺼기는 버려지므로 — 실 릴스는 항상 이 모양이다, 아래
    test_detect_cuts_drops_edge_fragment_shorter_than_min 참고). 보장되는 건
    프레임 쌍이 [0, total] 안에 있고, 순서대로, 서로 안 겹친다는 것뿐이다."""
    f = _make_three_scene_video(tmp_path / "three.mp4")
    total = scene_cut.video_frame_count(f)
    cuts = scene_cut.detect_cuts(f)
    assert cuts
    prev_end = 0
    for a, b in cuts:
        assert isinstance(a, int) and isinstance(b, int)   # ★초가 아니라 프레임
        assert b > a
        assert 0 <= a and b <= total                        # [0, total] 안
        assert a >= prev_end                                 # 순서대로, 안 겹침
        prev_end = b


def test_detect_cuts_finds_the_two_boundaries(tmp_path):
    f = _make_three_scene_video(tmp_path / "three.mp4")
    cuts = scene_cut.detect_cuts(f)
    starts = [a for a, _ in cuts]
    assert 30 in starts and 60 in starts        # 색이 바뀌는 지점


def test_detect_cuts_drops_fragments_shorter_than_min(tmp_path):
    f = _make_three_scene_video(tmp_path / "three.mp4")
    # 최소 2초 → 1초짜리 장면은 전부 탈락, 남는 게 없다
    assert scene_cut.detect_cuts(f, min_seconds=2.0) == []


def _make_two_scene_video(path, fps=30, short_seconds=0.2, long_seconds=1.0):
    """짧은(short_seconds) 장면 + 긴(long_seconds) 장면 2개를 붙인다.
    black→white — luma 차가 확실해야 scene 경계가 안정적으로 검출된다
    (red/green 금지 사유는 _make_three_scene_video의 주석 참고)."""
    parts = []
    for color, secs in (("black", short_seconds), ("white", long_seconds)):
        p = path.parent / f"_edge_{color}.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", f"color=c={color}:size=320x568:rate={fps}:duration={secs}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL)
        parts.append(p)
    lst = path.parent / "_edge_list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return path


def test_detect_cuts_drops_edge_fragment_shorter_than_min(tmp_path):
    """★맨 앞의 짧은 조각은 버려진다 — 첫 컷이 0프레임에서 시작하지 않는다.
    실 릴스가 이 모양이다(컨트롤러 실측: 원 경계가 3프레임부터 시작, (0,3)이 버려져
    첫 컷이 (3,28)이 됨). 합성 픽스처만 보면 '항상 0부터'라고 착각하게 된다."""
    f = _make_two_scene_video(tmp_path / "edge.mp4")
    total = scene_cut.video_frame_count(f)
    cuts = scene_cut.detect_cuts(f)          # 기본 min_seconds=0.5초 → 0.2초 조각은 버려짐
    assert cuts
    assert cuts[0][0] != 0                    # 맨 앞 찌꺼기가 버려져 0에서 시작하지 않는다
    assert cuts[-1][1] == total               # 남은 건 긴 장면 하나뿐, 끝까지 이어진다


def test_detect_cuts_never_exceeds_video_frames(tmp_path):
    # 오디오가 1초 더 긴 영상 — 경계가 비디오 끝을 넘으면 안 된다
    f = _make_video(tmp_path / "longaudio.mp4", seconds=2, fps=30, longer_audio=1.0)
    total = scene_cut.video_frame_count(f)
    for _, b in scene_cut.detect_cuts(f, min_seconds=0.1):
        assert b <= total
