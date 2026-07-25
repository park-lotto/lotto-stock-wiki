"""지워진 자막 영역 감지 — 원본 vs 자막제거본 프레임을 diff해서 '어디가 지워졌나'를 구한다.

VMake 자막제거(vmake_client.remove_subtitles)는 깨끗한 영상만 돌려주고 지운 좌표는 안 준다.
하지만 자막제거 단계에선 우리 손에 **원본**(VMake 입력)과 **클린본**(출력)이 둘 다 있으므로,
둘을 프레임 단위로 비교하면 "지속적으로 바뀐 영역 = 소각자막이 있던 자리"를 직접 구할 수 있다.

핵심은 **빈도(frequency) 필터**다: 소각자막은 영상 내내 같은 자리에 있어 그 픽셀이 거의 모든
프레임에서 원본↔클린이 다르다(고빈도). 움직이는 배경/피사체의 인페인팅 잔차는 프레임마다 위치가
달라 특정 픽셀에서 보면 저빈도 → 걸러진다. 그래서 '절반 이상 프레임에서 바뀐' 픽셀만 남긴다.

박스 좌표계: x_pct/y_pct = 영역 **중심**(자막이 translate(-50%,-50%) 중심배치라 그대로 스냅 가능),
w_pct/h_pct = 영역 크기(%). score = 넓이비율 × 박스내 평균빈도 (소스 여러 개일 때 1등 고를 정렬키).
"""
from __future__ import annotations

from pathlib import Path

# 감지는 best-effort — numpy/PIL이 없어도 파이프라인이 죽지 않게 지연 임포트로 감싼다.
_GRID_W, _GRID_H = 270, 480       # 두 프레임을 이 격자로 정규화(VMake가 해상도 바꿔도 %는 불변)
_DIFF_THRESH = 28                  # 그레이스케일 절대차 이진화 임계(0~255)
_FREQ_THRESH = 0.5                 # 이 비율 이상 프레임에서 바뀐 픽셀만 '지속 변화'로 인정
_MIN_AREA_PCT = 0.5                # 박스 넓이가 화면의 이 % 미만이면 잡음으로 보고 버림
_SAMPLES = 8                       # 비교할 프레임 장수


def _bbox_from_frames(orig_frames, clean_frames,
                      diff_thresh=_DIFF_THRESH, freq_thresh=_FREQ_THRESH,
                      min_area_pct=_MIN_AREA_PCT):
    """정규화된 그레이스케일 프레임 두 묶음(numpy 2D 배열 리스트, 같은 크기)을 받아
    지워진 자막 박스(dict) 또는 None을 반환. ffmpeg 없이 테스트 가능한 순수 코어."""
    import numpy as np

    n = min(len(orig_frames), len(clean_frames))
    if n == 0:
        return None
    h, w = orig_frames[0].shape
    heat = np.zeros((h, w), dtype=np.float32)
    for a, b in zip(orig_frames[:n], clean_frames[:n]):
        d = np.abs(a.astype(np.int16) - b.astype(np.int16))
        heat += (d > diff_thresh).astype(np.float32)
    freq = heat / n
    persistent = freq >= freq_thresh
    if not persistent.any():
        return None
    ys, xs = np.where(persistent)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    bw, bh = (x1 - x0 + 1), (y1 - y0 + 1)
    w_pct = bw / w * 100.0
    h_pct = bh / h * 100.0
    area_pct = w_pct * h_pct / 100.0   # (w%*h%)/100 = 화면 대비 넓이 %
    if area_pct < min_area_pct:
        return None
    cx_pct = (x0 + bw / 2.0) / w * 100.0
    cy_pct = (y0 + bh / 2.0) / h * 100.0
    mean_freq = float(freq[persistent].mean())
    return {
        "x_pct": round(cx_pct, 2), "y_pct": round(cy_pct, 2),
        "w_pct": round(w_pct, 2), "h_pct": round(h_pct, 2),
        "score": round(area_pct * mean_freq, 4),
    }


def _extract_gray_frames(video_path, timestamps, work, tag):
    """video_path에서 주어진 타임스탬프(초)마다 1프레임씩 뽑아 _GRID로 리사이즈한
    그레이스케일 numpy 배열 리스트로 반환. 실패한 프레임은 건너뛴다."""
    import numpy as np
    from PIL import Image
    from shopping_shorts.video_assemble import _run_ffmpeg

    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, t in enumerate(timestamps):
        png = work / f"_subrgn_{tag}_{i}.png"
        try:
            _run_ffmpeg(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(video_path),
                         "-frames:v", "1", "-q:v", "3", str(png)])
            img = Image.open(png).convert("L").resize((_GRID_W, _GRID_H))
            frames.append(np.asarray(img, dtype=np.uint8))
        except Exception:
            continue
        finally:
            try:
                png.unlink()
            except OSError:
                pass
    return frames


def detect_erased_region(original_path, clean_path, work, samples=_SAMPLES):
    """원본과 자막제거본을 비교해 지워진 자막 박스(dict) 또는 None을 반환.

    best-effort: 의존성 부재·ffmpeg 실패·지속 변화 없음 등 어떤 이유로든 못 구하면
    조용히 None(호출부는 clean 성공을 되돌리지 않는다). 원본에 자막이 없었으면 자연히 None.
    """
    try:
        from shopping_shorts.video_assemble import _probe_duration
    except Exception:
        return None
    try:
        dur = min(_probe_duration(original_path), _probe_duration(clean_path))
    except Exception:
        return None
    if not dur or dur <= 0:
        return None
    # 시작·끝의 인트로/아웃트로 프레임을 피해 가운데를 고르게 샘플링
    ts = [dur * (i + 0.5) / samples for i in range(samples)]
    orig = _extract_gray_frames(original_path, ts, work, "o")
    clean = _extract_gray_frames(clean_path, ts, work, "c")
    if not orig or not clean:
        return None
    try:
        return _bbox_from_frames(orig, clean)
    except Exception:
        return None


def pick_primary(regions):
    """소스별 박스 dict들의 리스트에서 score 최대(넓고 자주 쓰인) 박스를 1번으로 반환.
    빈 리스트/전부 None이면 None."""
    valid = [r for r in regions if r]
    if not valid:
        return None
    return max(valid, key=lambda r: r.get("score", 0.0))
