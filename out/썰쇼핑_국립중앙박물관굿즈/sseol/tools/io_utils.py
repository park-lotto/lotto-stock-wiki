"""한글 경로 안전 입출력. (OpenCV 는 윈도우에서 한글 경로를 못 연다) + 영상 인코더 자리 한 곳."""
import contextlib
import json
import os
import subprocess

import cv2
import numpy as np

# 영상 인코더 자리 — 볼케이노 실행기의 공통 판정(runner/video_encoder.py)을 쓴다(2026-10-19 GPU 인코딩).
# 고르는 규칙(어느 GPU · 어느 preset 은 CPU 그대로 · 같은 용량 비트레이트)은 그 모듈 한 곳 — 여기서는 고르지 않는다.
# 찾는 자리: VOLCANO_RUNNER_DIR → ~/.volcano/runner(실행기가 돌 때 자기 파일을 설치하는 오래 가는 자리 · 안내형 단계도 찾는다) — 없으면 사유를 보이고 멈춘다.
# 아래 find_video_encoder 는 정본 volcano-mcp tools/venc_lookup.py 를 글자 그대로 복사한 것(tests/test_venc_lookup.py 가 대조) — 여기서 고치지 않는다.
# 값이 있는데 import 가 안 되면 오류다(삼키지 않는다). 사용법: 볼케이노 저장소 docs/2026-10-19_GPU-인코딩-공통모듈.md
def find_video_encoder():
    """(실행기 폴더 Path, video_encoder 모듈) — 못 찾으면 사유를 보이고 멈춘다 · 정본 volcano-mcp tools/venc_lookup.py · 글자 그대로 복사."""
    import importlib.util
    import os
    import sys
    from pathlib import Path
    folder = Path(os.environ.get("VOLCANO_RUNNER_DIR") or Path.home() / ".volcano" / "runner")
    if not (folder / "video_encoder.py").is_file():
        raise SystemExit(f"영상 인코더 모듈이 없습니다: {folder / 'video_encoder.py'}\n"
                         "볼케이노 실행기(작업 폴더의 runner/volcano_drive.py)를 한 번 돌리면(사전 점검 단계) 이 자리에 설치됩니다. "
                         "그 뒤 같은 명령을 다시 실행하세요.")
    module = sys.modules.get("video_encoder")
    if module is None:
        spec = importlib.util.spec_from_file_location("video_encoder", str(folder / "video_encoder.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules["video_encoder"] = module
    return folder, module


RUNNER_DIR, video_encoder = find_video_encoder()


def x264(preset, crf, width, height, fps, *, program="ffmpeg", extra=(), color=True):
    """`-c:v libx264 [-preset P] -crf C [extra]` 대신 펼쳐 쓰는 목록(`*x264(...)`)."""
    return video_encoder.x264(preset, crf, width, height, fps, program=program, extra=extra, color=color)


def run_enc(argv, **kw):
    """`subprocess.run` 과 같은 인자·반환 — 인코더 자리가 있으면 GPU 1번, 실패면 CPU 1번."""
    return video_encoder.subprocess_run(argv, **kw)


def enc_attempts(argv):
    """[(GPU 이름 또는 None, argv)] — 프레임을 흘려 넣는 자리가 직접 돈다(실패하면 프레임을 다시 만든다 · 최대 2번)."""
    return video_encoder.attempts(argv)


def gpu_slot(gpu):
    """GPU 굽기 동시 상한(실행기 모듈 gpu_slots) — CPU 길은 막지 않는다."""
    return video_encoder.gpu_slots if gpu else contextlib.nullcontext()


def enc_failed(gpu, reason):
    video_encoder.failed(gpu, reason)


def imread(path):
    data = np.fromfile(path, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:  # webp/gif 등은 PIL 로
        from PIL import Image
        img = np.array(Image.open(path).convert("RGB"))[:, :, ::-1].copy()
    return img


def imwrite(path, img, quality=95):
    ext = os.path.splitext(path)[1].lower() or ".png"
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext in (".jpg", ".jpeg") else []
    ok, buf = cv2.imencode(ext, img, params)
    if not ok:
        raise IOError("인코딩 실패: " + path)
    buf.tofile(path)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8")
    j = json.loads(r.stdout)
    s = j["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(j["format"]["duration"]), float(num) / float(den or 1)


class VideoReader:
    """ffmpeg 파이프로 start 초부터 fps 고정 프레임을 순서대로 읽는다. 끝나면 마지막 프레임 유지."""

    def __init__(self, path, start=0.0, fps=30, max_w=1440):
        w, h, self.duration, _ = probe(path)
        if w > max_w:  # 불필요하게 큰 원본은 미리 줄여서 받음
            h = int(round(h * max_w / w / 2)) * 2
            w = max_w
        self.w, self.h, self.fps = w, h, fps
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-ss", str(start), "-i", path, "-an", "-vf", f"fps={fps},scale={w}:{h}",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        self.size = w * h * 3
        self.pos = 0
        self.last = None
        self._read()

    def _read(self):
        buf = self.proc.stdout.read(self.size) if self.proc else b""
        if len(buf) < self.size:
            self.close()
            return False
        self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
        self.pos += 1
        return True

    def frame(self, t):
        want = int(t * self.fps) + 1
        while self.pos < want and self._read():
            pass
        return self.last

    def close(self):
        if self.proc:
            self.proc.stdout.close()
            self.proc.kill()
            self.proc = None
