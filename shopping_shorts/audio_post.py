"""TTS mp3 후처리: 속도 미세보정(atempo)과 무음삭제(silenceremove)를 ffmpeg 한 패스로.

ElevenLabs speed는 0.7~1.2만 지원해, 그 이상(1.3~1.5) 속도는 여기서 atempo로 얹는다.
무음삭제는 나레이션 사이 쉬는 구간을 잘라 빠르게 이어붙인다(레벨: off/weak/mid/strong)."""
import os
import subprocess
import tempfile

# 레벨별 silenceremove 파라미터. stop_duration=자를 최소 무음길이(초), stop_threshold=무음 판정 dB.
# 강할수록 짧은 무음까지 자르고(작은 duration), 판정 임계도 관대(높은 dB).
_SILENCE = {
    "weak":   "silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-40dB",
    "mid":    "silenceremove=stop_periods=-1:stop_duration=0.4:stop_threshold=-38dB",
    "strong": "silenceremove=stop_periods=-1:stop_duration=0.25:stop_threshold=-35dB",
}


def _silence_filter(level):
    """레벨 문자열 → silenceremove 필터 문자열. off/미지정이면 None."""
    return _SILENCE.get(level or "off")


def post_process(in_path, out_path, tempo=1.0, silence_trim="off"):
    """in_path mp3에 속도(tempo)·무음삭제를 적용해 out_path로. 둘 다 no-op이면 in_path 그대로 반환.

    tempo: atempo 배율(1.0=변화없음). silence_trim: off/weak/mid/strong."""
    filters = []
    if tempo and abs(tempo - 1.0) > 1e-3:
        filters.append(f"atempo={tempo:.3f}".rstrip("0").rstrip("."))
    sf = _silence_filter(silence_trim)
    if sf:
        filters.append(sf)
    if not filters:
        return in_path
    # ffmpeg는 같은 파일을 입력이자 출력으로 쓰지 못한다(in-place 시 입력이 잘려 실패).
    # in==out이면 임시파일에 쓴 뒤 원자적으로 교체한다.
    same = os.path.abspath(str(in_path)) == os.path.abspath(str(out_path))
    if same:
        fd, target = tempfile.mkstemp(suffix=".mp3", dir=os.path.dirname(os.path.abspath(str(out_path))))
        os.close(fd)
    else:
        target = str(out_path)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(in_path), "-af", ",".join(filters),
             "-q:a", "4", target],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
    except Exception:
        if same and os.path.exists(target):
            os.remove(target)
        raise
    if same:
        os.replace(target, str(out_path))
    return str(out_path)
