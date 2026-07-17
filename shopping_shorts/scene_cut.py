"""컷 경계 검출·프레임 절단 — DB도 HTTP도 Gemini도 모르는 순수 함수.

★초로 반올림하지 마라. 30fps 영상은 프레임이 1/30초 간격에만 존재하므로
반올림된 초(4.13)는 '프레임이 없는 시각'이 되고, ffmpeg가 다음 프레임에
붙이면서 다음 컷의 첫 프레임이 딸려 들어온다(설계 §3.4 실측 증명).
"""
import re
import subprocess
from pathlib import Path


def _ffprobe(args):
    # stdin=DEVNULL — pytest 기본 캡처(--capture=fd)가 fd 0을 무효화해서
    # 이게 없으면 테스트에서 OSError [WinError 6]이 난다. 실서비스에선 무해.
    r = subprocess.run(["ffprobe", "-v", "error"] + args,
                       capture_output=True, text=True, check=False,
                       stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"ffprobe 실패: {r.stderr.strip() or '출력 없음'}")
    return r.stdout.strip()


def video_fps(path):
    """r_frame_rate를 유리수로 정확히 읽는다(30/1 → 30.0)."""
    raw = _ffprobe(["-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                    "-of", "csv=p=0", str(path)])
    num, _, den = raw.partition("/")
    try:
        return int(num) / int(den or 1)
    except (ValueError, ZeroDivisionError) as e:
        raise RuntimeError(f"fps 해석 실패: {raw!r}") from e


def video_frame_count(path):
    """★비디오 스트림의 총 프레임 수. format=duration을 쓰면 안 된다 —
    그건 오디오와 비디오 중 긴 값이라 화면 없는 꼬리가 붙는다(설계 §3.5)."""
    raw = _ffprobe(["-select_streams", "v:0", "-count_frames",
                    "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", str(path)])
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"프레임 수 해석 실패: {raw!r}") from e


_PTS_RE = re.compile(r"pts_time:([\d.]+)")

# 다른 트랙(frame_extract.py)이 이미 쓰는 값. 실측상 낮춰도 쓸 만한 구간은
# 안 늘고 부스러기만 폭증한다(설계 §3.3) — 건드리지 마라.
DEFAULT_THRESHOLD = 0.3
MIN_SECONDS = 0.5


def _boundary_frames(path, threshold, fps):
    """showinfo가 stderr로 뱉는 pts_time → 프레임 번호."""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
        stdin=subprocess.DEVNULL)
    return {round(float(m) * fps) for m in _PTS_RE.findall(r.stderr)}


def extract_poster(path, frame_no, fps, out_path):
    """frame_no번째 프레임을 180px 폭 썸네일로 뽑는다(분할 미리보기용).

    실패해도 예외를 던지지 않는다 — 포스터 없이도 컷 목록은 떠야 한다
    (scene_assets.make_poster와 같은 관례). stdin=DEVNULL은 이 모듈의 다른
    subprocess 호출과 같은 이유(pytest 기본 캡처가 fd 0을 무효화하는 것 방지)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0, frame_no) / fps:.6f}",
           "-i", str(path), "-frames:v", "1", "-vf", "scale=180:-1", str(out_path)]
    subprocess.run(cmd, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    return out_path if out_path.exists() else None


def detect_cuts(path, threshold=DEFAULT_THRESHOLD, min_seconds=MIN_SECONDS):
    """컷 경계를 프레임 번호로. 반환 (start_frame, end_frame) — end는 미포함.

    ★병합하지 않는다. 짧은 조각을 이웃과 이어붙이면 그 사람의 '편집 결정'까지
    가져오게 되고(설계 §3.2), 그건 표절 회피(§7)와 정면으로 부딪힌다.
    min_seconds보다 짧은 건 전환 찌꺼기이므로 그냥 버린다.
    """
    if not Path(path).exists():
        raise RuntimeError(f"소스 없음: {path}")
    fps = video_fps(path)
    total = video_frame_count(path)
    inner = {f for f in _boundary_frames(path, threshold, fps) if 0 < f < total}
    bounds = [0] + sorted(inner) + [total]
    floor = round(min_seconds * fps)
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)
            if bounds[i + 1] - bounds[i] >= floor]
