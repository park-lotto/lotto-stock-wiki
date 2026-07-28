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


# ── 모션 레벨(P1, 2026-07-28) ─────────────────────────────────────────
# 컷별 시간차 모션에너지를 재고, 상대 컷오프로 LOW/MED/PEAK를 매긴다. PEAK 컷은
# 3초 훅 후보(In-Point 자동)로 쓴다. 절대값이 아니라 '이 영상 안에서의 상대'로 보는
# 이유: 조명·해상도·코덱에 따라 절대 에너지가 크게 달라 고정 임계는 못 쓴다.
_YDIF_RE = re.compile(r"lavfi\.signalstats\.YDIF=([\d.]+)")


def _percentile(sorted_vals, q):
    """0~1 분위수(선형보간). sorted_vals는 오름차순, 비어있으면 0.0."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    hi = min(lo + 1, len(sorted_vals) - 1)
    return float(sorted_vals[lo]) * (1 - frac) + float(sorted_vals[hi]) * frac


def motion_thresholds(values, lo_q=0.5, hi_q=0.85):
    """프레임 모션값들 → (lo, hi) 컷오프. lo 미만=LOW, hi 이상=PEAK, 사이=MED.
    분포 기반(분위수)이라 영상마다 자동 적응. 순수 함수(테스트 대상)."""
    s = sorted(float(v) for v in values)
    return _percentile(s, lo_q), _percentile(s, hi_q)


def level_of(energy, lo, hi):
    """모션값 하나 → 'LOW'|'MED'|'PEAK'. 순수 함수."""
    if energy >= hi:
        return "PEAK"
    if energy < lo:
        return "LOW"
    return "MED"


def cut_motion(cuts, motion, lo_q=0.5, hi_q=0.85):
    """컷 목록 + {frame_no: energy} → 컷별 {level, peak_frame, energy}.
    컷 대표값=구간 내 최대 에너지(그 컷이 얼마나 격한가), peak_frame=최대 프레임.
    임계는 전체 프레임 분포에서 한 번만 잡아 컷끼리 상대비교. 순수 함수(테스트 대상)."""
    lo, hi = motion_thresholds(motion.values(), lo_q, hi_q)
    out = []
    for (a, b) in cuts:
        frames = [(f, motion[f]) for f in motion if a <= f < b]
        if frames:
            peak_frame, peak_e = max(frames, key=lambda x: x[1])
        else:
            peak_frame, peak_e = a, 0.0
        out.append({"start": a, "end": b, "peak_frame": peak_frame,
                    "energy": round(peak_e, 3), "level": level_of(peak_e, lo, hi)})
    return out


def frame_motion(path):
    """ffmpeg 1패스로 프레임별 시간차 모션(signalstats YDIF) → {frame_no: energy}.
    YDIF=인접 프레임 루마 평균차 = 화면이 얼마나 바뀌었나(모션 프록시). Gemini/DB 무관 순수 IO."""
    fps = video_fps(path)
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YDIF",
         "-vsync", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    out = {}
    frame_no = 0
    for m in _YDIF_RE.findall(r.stderr):
        out[frame_no] = float(m)
        frame_no += 1
    return out


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
