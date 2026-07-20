"""P1 후속(장면스파인): freeze 정지 구간이 '죽은 정지'가 아니라 완만한 켄번즈 줌으로
살아있는지 검증(2026-07-19). 사장님 육안 피드백 — 재렌더에서 마지막 프레임이 뚝 멈춰
어색하다. 원인: _speed_and_freeze가 나눈 freeze초를 tpad clone으로 '픽셀 동일' 홀드해서다.

처방: _extend_with_frozen_motion — 움직이는 클립 뒤에 마지막 프레임을 홀드하되 전체
(play+freeze)에 켄번즈를 얹어 정지 구간 프레임들이 서로 달라야(=움직임) 한다.
tpad→zoompan 순서는 출력이 잘리지 않는다(실측 2026-07-19; 예전 버그는 반대 순서였음).
"""
import subprocess

import pytest

from shopping_shorts import video_assemble as va


def _mk_detailed_video(path, dur):
    # 줌 움직임을 측정하려면 화면에 디테일이 필요하다(단색은 줌해도 안 변함) → testsrc.
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"testsrc=size=720x1280:rate=30:duration={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _frame_gray(video, t, n=48):
    """t초 프레임을 n×n 그레이 rawvideo로 뽑아 바이트 리스트로(외부 의존성 없이 비교용)."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video),
                          "-frames:v", "1", "-vf", f"scale={n}:{n}", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    return list(out)


def _mean_abs_diff(a, b):
    m = min(len(a), len(b))
    return sum(abs(a[i] - b[i]) for i in range(m)) / m if m else 0.0


def test_frozen_tail_has_motion(tmp_path):
    src = tmp_path / "sub.mp4"
    _mk_detailed_video(src, 1.0)                       # 움직이는 1초 클립
    out = tmp_path / "frozen.mp4"
    va._extend_with_frozen_motion(src, play_out=1.0, freeze=1.0, out_path=out)

    # 총 길이 보존 = play_out + freeze (오디오/자막 싱크 불변).
    assert va._probe_duration(out) == pytest.approx(2.0, abs=0.15)

    # 정지 구간(1.0~2.0초) 안의 두 프레임이 서로 달라야 한다 = 켄번즈로 살아있음.
    # 죽은 정지(tpad clone 단독)면 이 값이 ~0이다.
    f_mid = _frame_gray(out, 1.4)
    f_late = _frame_gray(out, 1.9)
    assert _mean_abs_diff(f_mid, f_late) > 2.0
