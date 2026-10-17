# -*- coding: utf-8 -*-
"""하이브리드 파이프라인 공용 조각 — 경로·명령 실행·소리 재기·글자 수·단계 시간 장부. 판단(시각·컷)은 여기 두지 않는다(렌더러가 주인)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK_BASE = Path("C:/숏템_칼카피/yanshottem")
DOC_BASE = ROOT / "channel" / "yanshottem"
DESK_DIR = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드")
FRAME_A_DEFAULT = ROOT / "channel/mantem/frame_얜샷템.json"
PRESET_ITSSUM_B = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"
PRESET_JAEMI_B = ROOT / "channel/evenshopping/preset/숏템템플릿/manifest.json"
FPS = 30
SR = 48000


class StageError(RuntimeError):
    """단계 실패 — 이유를 들고 멈춘다(조용한 실패 금지)."""


def run(cmd, check=True, timeout=None):
    r = subprocess.run([str(c) for c in cmd], check=False, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        raise StageError(f"명령 실패 rc={r.returncode}: {' '.join(str(c) for c in cmd)[:240]}\n{r.stderr[-1200:]}")
    return r


def dur_of(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def probe(p) -> tuple[int, int, float]:
    j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", p]).stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def lufs(p, extra=None) -> tuple[float, float]:
    """(통합 LUFS, 최고점 dBFS) — ebur128 peak=true."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(p)] + (extra or []) + ["-af", "ebur128=peak=true", "-f", "null", "-"]
    e = run(cmd, check=False).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", e)
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
    return (float(I[-1]) if I else float("nan")), (float(pk[-1]) if pk else float("nan"))


def silences(p, noise="-40dB", d=0.1, merge=0.01) -> list[tuple[float, float]]:
    """무음 구간 [(a,b)] — 맞붙은 무음(최은경 편 9.88~10.17|10.17~10.26)은 하나로."""
    e = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", f"silencedetect=n={noise}:d={d}", "-f", "null", "-"], check=False).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    total = dur_of(p)
    sil = list(zip(st, en + [total] * (len(st) - len(en))))
    out: list[tuple[float, float]] = []
    for a, b in sil:
        if out and a - out[-1][1] < merge:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def nchar(s: str) -> int:
    """읽는 글자 수(한글·영문·숫자만) — 말속도의 분자. 잇썸·재미썸 두 렌더러가 같은 자를 쓴다."""
    return len(re.findall(r"[가-힣A-Za-z0-9]", s or ""))


def md5(p) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jsave(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def frame_png(src, t: float, crop, size) -> "Image":
    """소스 영상 t 초 프레임을 crop=[x,y,w,h] 로 잘라 size 로 — 계획 시트용."""
    import io
    from PIL import Image
    x, y, w, h = crop
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL).stdout
    if not b:
        return Image.new("RGB", size, (60, 0, 0))
    return Image.open(io.BytesIO(b)).convert("RGB")


class Timer:
    """단계별 소요 초 장부(stage_log.json) — 사장님께 '어디서 시간이 가나'를 숫자로 보인다."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.cur: dict = jload(self.path) if self.path.exists() else {"stages": []}

    def done(self, stage: str, sec: float, note: str = "", **extra):
        self.cur["stages"].append({"stage": stage, "sec": round(sec, 1), "note": note, "at": time.strftime("%Y-%m-%d %H:%M:%S"), **extra})
        jsave(self.path, self.cur)

    def __enter__(self):
        self._t0 = time.time()
        return self

    def __exit__(self, *a):
        pass


def timed(timer: Timer, stage: str):
    """with timed(tm, "render"): … — 끝나면 장부에 적는다(예외도 적는다)."""
    class _T:
        def __enter__(self_):
            self_.t0 = time.time()
            return self_

        def __exit__(self_, et, ev, tb):
            timer.done(stage, time.time() - self_.t0, "실패: " + str(ev)[:200] if ev else "")
            return False
    return _T()
