# -*- coding: utf-8 -*-
"""probe — bench의 **유일한** ffmpeg/ffprobe 창구.

다른 bench 모듈은 subprocess로 ffmpeg를 직접 부르지 않는다(설계 §2). 같은 영상을 같은 방식으로
디코딩해야 모듈끼리 숫자가 어긋나지 않는다.

규율(볼케이노 자, 함수 지도 §1-C):
  - 측정용 ffmpeg 호출(ebur128·showinfo)에 `-v error`를 붙이지 않는다 — 요약이 stderr에 있다.
  - 길이 = 프레임 수 ÷ fps (`duration`). 컨테이너 길이는 참고로만 남긴다.
  - 소리는 f32 스테레오로 받는다. 모노는 audio.py가 (L+R)/2로 만든다(`-ac 1`은 +3.01dB).
"""
from __future__ import annotations

import json
import subprocess
from typing import Iterator

import numpy as np

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True)


def ffmpeg_log(args: list[str]) -> str:
    """ffmpeg를 돌리고 stderr(측정 요약이 찍히는 곳)를 문자열로 준다. -v error 금지."""
    r = _run([FFMPEG, "-hide_banner", "-nostats", *args])
    return r.stderr.decode("utf-8", errors="replace")


def info(path: str) -> dict:
    """영상 메타 + 길이(프레임 수 ÷ fps). nb_frames가 없으면 패킷을 센다."""
    r = _run([FFPROBE, "-v", "error", "-show_entries",
              "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels",
              "-show_entries", "format=duration", "-of", "json", path])
    d = json.loads(r.stdout.decode("utf-8", errors="replace") or "{}")
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise ValueError(f"영상 스트림 없음: {path}")
    num, den = v["r_frame_rate"].split("/")
    fps = int(num) / int(den)
    nb = v.get("nb_frames")
    nb = int(nb) if isinstance(nb, str) and nb.isdigit() else None
    if nb is None:
        rc = _run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_packets",
                   "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path])
        txt = rc.stdout.decode().strip().split(",")[0]
        nb = int(txt) if txt.isdigit() else None
    cont = float(d.get("format", {}).get("duration", "nan"))
    return {
        "width": int(v["width"]), "height": int(v["height"]), "fps": round(fps, 3),
        "nb_frames": nb,
        "duration": round(nb / fps, 3) if nb else round(cont, 3),
        "duration_container": round(cont, 3),
        "vcodec": v.get("codec_name"),
        "has_audio": a is not None,
        "asr": int(a["sample_rate"]) if a else None,
        "ach": int(a["channels"]) if a else None,
    }


def frames(path: str, vf: str, w: int, h: int, pix: str = "rgb24") -> Iterator[np.ndarray]:
    """-vf 결과 프레임을 차례로 준다(rgb24 → (h,w,3), gray → (h,w)). vf의 출력 크기가 w×h여야 한다."""
    ch = 3 if pix == "rgb24" else 1
    proc = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", path, "-an", "-vf", vf,
                             "-f", "rawvideo", "-pix_fmt", pix, "-"], stdout=subprocess.PIPE)
    size = w * h * ch
    try:
        while True:
            b = proc.stdout.read(size)
            if len(b) < size:
                break
            a = np.frombuffer(b, np.uint8)
            yield a.reshape(h, w, 3) if ch == 3 else a.reshape(h, w)
    finally:
        proc.stdout.close()
        proc.wait()


def grab(path: str, t: float, vf: str, w: int, h: int, pix: str = "rgb24") -> np.ndarray | None:
    """t초 프레임 한 장(-ss 입력 앞 = 정확 탐색). 못 뽑으면 None."""
    r = _run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", path,
              "-frames:v", "1", "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", pix, "-"])
    ch = 3 if pix == "rgb24" else 1
    if len(r.stdout) < w * h * ch:
        return None
    a = np.frombuffer(r.stdout[:w * h * ch], np.uint8)
    return a.reshape(h, w, 3) if ch == 3 else a.reshape(h, w)


def pcm_stereo(path: str, sr: int) -> np.ndarray | None:
    """f32 스테레오 PCM (N,2) float64. 소리가 없으면 None."""
    r = _run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(sr),
              "-f", "f32le", "-acodec", "pcm_f32le", "-"])
    a = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    if a.size < 4:
        return None
    return a[:(a.size // 2) * 2].reshape(-1, 2)
