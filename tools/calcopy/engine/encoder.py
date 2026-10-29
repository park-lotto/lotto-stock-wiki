"""영상 인코더 고르기 — 주인 함수 venc() 하나(사장님 10-25: "화질 같게, GPU 있으면 GPU 우선, 없으면 CPU").

우리 PC(RTX 3080 Ti)도 회원 PC도 같은 코드: NVENC 가 실제로 돌면 GPU, 아니면 지금 그대로 libx264.
화질 맞춤(실측 10-25, VMAF·1080x1920·10초 2편, ffv1 원본 대비):
  x264 crf16 veryfast  84.15 / 85.63  (5.38MB / 4.89MB, CPU 23.8s / 18.4s)
  nvenc cq23           84.25 / 85.95  (5.18MB / 5.60MB, CPU 11.8s /  9.0s)
  → crf16 ↔ cq22(cq23 에서 한 칸 더 좋게, 여유). 근거 98 #79.
강제: 환경변수 SHORTEM_ENCODER=cpu|gpu (기본 auto).
GPU 인코딩이 실패하면(세션 수 한도·드라이버) 같은 명령을 CPU 로 다시 돈다 — cpu_retry(), 경보는 stderr 한 줄.
"""
from __future__ import annotations

import os
import subprocess
import sys

_KIND: str | None = None
CQ_OF_CRF = {16: 22, 30: 34}       # x264 crf → nvenc cq (같은 화질, 위 실측)


def kind() -> str:
    """'gpu' | 'cpu' — 한 프로세스에서 한 번만 잰다."""
    global _KIND
    if _KIND:
        return _KIND
    want = (os.environ.get("SHORTEM_ENCODER") or "auto").strip().lower()
    if want in ("cpu", "gpu"):
        _KIND = want
        return _KIND
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-c:v", "h264_nvenc",
                            "-f", "null", "-"], stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        _KIND = "gpu" if r.returncode == 0 else "cpu"
    except Exception:  # noqa: BLE001 — ffmpeg 없음·시간 초과 = CPU(아래에서 어차피 ffmpeg 가 다시 실패를 알린다)
        _KIND = "cpu"
    return _KIND


def venc(crf: int = 16, preset: str = "veryfast") -> list[str]:
    """영상 인코딩 인자. CPU 면 지금까지와 한 글자도 같다."""
    if kind() == "gpu":
        return _gpu(CQ_OF_CRF.get(int(crf), int(crf) + 6))
    return ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]


def _gpu(cq: int) -> list[str]:
    return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(cq), "-b:v", "0", "-pix_fmt", "yuv420p"]


_GPU_N = len(_gpu(0))


def cpu_retry(cmd) -> list | None:
    """GPU 인자가 든 명령이면 CPU 인자로 바꾼 명령(다시 돌리기용), 아니면 None. 실패한 GPU 는 이 프로세스에서 끈다."""
    c = [str(x) for x in cmd]
    if "h264_nvenc" not in c:
        return None
    global _KIND
    _KIND = "cpu"
    i = c.index("h264_nvenc") - 1                      # venc() GPU 인자 묶음의 첫 칸 '-c:v'
    cq = int(c[i + 9])
    crf = next((k for k, v in CQ_OF_CRF.items() if v == cq), cq - 6)
    print(f"[encoder] GPU 인코딩 실패 → CPU 로 다시(crf {crf})", file=sys.stderr, flush=True)
    return c[:i] + ["-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast"] + c[i + _GPU_N:]


def run(cmd, **kw) -> subprocess.CompletedProcess:
    """subprocess.run 과 같되 GPU 인코딩이 실패하면 CPU 로 한 번 더."""
    check = kw.pop("check", False)
    r = subprocess.run([str(x) for x in cmd], **kw)
    if r.returncode != 0:
        alt = cpu_retry(cmd)
        if alt:
            r = subprocess.run(alt, **kw)
    if check and r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, r.args, r.stdout, r.stderr)
    return r
