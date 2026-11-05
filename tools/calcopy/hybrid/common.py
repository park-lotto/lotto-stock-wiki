# -*- coding: utf-8 -*-
"""하이브리드 파이프라인 공용 조각 — 경로·명령 실행·소리 재기·글자 수·단계 시간 장부. 판단(시각·컷)은 여기 두지 않는다(렌더러가 주인)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 얼굴 검출 모델(YuNet) — 주인 한 곳(render_bench·thumb). 회원 PC = 설치본 models/face(환경변수, 숏템 MCP 가 넣는다). OpenCV 는 한글 경로를 못 읽는다
FACE_MODEL = os.environ.get("CALCOPY_FACE_MODEL") or "C:/calcopy_models/face_detection_yunet_2023mar.onnx"
if not os.path.isfile(FACE_MODEL):
    for _d in (ROOT.parent / "models", ROOT / "models"):                    # 회원 설치본 = 엔진 옆(build_win · updater.adoptModels), 옛 설치본 = 엔진 안. 순서는 vision.find_model 과 같다
        if (_d / "face_detection_yunet_2023mar.onnx").is_file():
            FACE_MODEL = str(_d / "face_detection_yunet_2023mar.onnx")
            break
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


RUN_TIMEOUT = float(os.environ.get("SHORTEM_FFMPEG_TIMEOUT") or 3600)   # 명령 한 번 상한(초) — 끝없이 도는 ffmpeg 를 끊는다(관제 285)


def run(cmd, check=True, timeout=RUN_TIMEOUT):
    try:
        r = subprocess.run([str(c) for c in cmd], check=False, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise StageError(f"명령 시간 초과({timeout}초): {' '.join(str(c) for c in cmd)[:240]}")
    if r.returncode != 0:
        from tools.calcopy.engine.encoder import cpu_retry      # GPU 인코딩 실패(세션 한도 등) → 같은 명령 CPU 로 한 번 더(98 #79)
        alt = cpu_retry(cmd)
        if alt:
            r = subprocess.run(alt, check=False, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        raise StageError(f"명령 실패 rc={r.returncode}: {' '.join(str(c) for c in cmd)[:240]}\n{r.stderr[-1200:]}")
    return r


def dur_of(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def video_dur(p) -> float:
    """영상 스트림 길이(초) — 파일 길이(format)는 소리가 더 길면 화면 끝보다 길다. 스트림 칸이 없으면 파일 길이."""
    j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration:format=duration", "-of", "json", p]).stdout)
    return float((j.get("streams") or [{}])[0].get("duration") or (j.get("format") or {}).get("duration") or 0)


def orig_span_over(b: float, f: dict) -> float:
    """(판단 주인 — 원음 구간 끝이 원본 화면 안인가, #4089 박영상) 넘은 초(0 = 안 넘음). f = 원본 파일 정보(runner_ops.dims).
    화면 끝 = 영상 스트림 길이 − 1프레임 = render_bench.src_left(src, 0) 과 같은 자 — 조사·대본 검사(flow)와 계획이 같은 끝을 본다.
    vdur 가 없는 옛 회원 엔진 결과면 옛 기준(파일 길이 + 0.5)으로 — 거짓 반려를 내지 않는다."""
    if f.get("vdur"):
        end = float(f["vdur"]) - 1 / FPS
    elif f.get("dur"):
        end = float(f["dur"]) + 0.5
    else:
        return 0.0
    return max(0.0, round(float(b) - end, 3))


def probe(p) -> tuple[int, int, float]:
    j = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", p]).stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float((j.get("format") or {}).get("duration") or 0)   # 사진(jpg)은 길이 칸이 없을 수 있다(10-27 run4 a편 쿠팡 사진 2장 KeyError → 제품 사진 0장)


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


# (판단 주인 — 소리 내 읽는 글자) 한글·영문·숫자 + 가나·한자. 말속도·자막 시작·글자 시각·받아쓰기 대조가 모두 이 자를 쓴다
#   (11-03 윤상길 일본어판: 곳곳에 한글만 세는 자가 따로 있어 일본어 대본이 0자 → 나눗셈·자막 시각이 깨졌다)
SPOKEN = r"[가-힣A-Za-z0-9\u3040-\u30ff\u4e00-\u9fff]"


JP_FONT = "NotoSansKR-Bold.otf"     # 일본어 글자가 다 있는 글꼴(fontTools: Pretendard 는 가나 일부 누락) — 일본어 대본이면 렌더 글꼴을 이것으로


def script_lang(S: dict | None = None) -> str:
    """(판단 주인 — 이 편 대본 언어) 'ja' = 나레 줄에 가나가 있다 · 아니면 'ko'. 렌더가 정해 SHORTEM_SCRIPT_LANG 에 두면
    같은 실행의 글꼴(render_bench._font)·광고 표시(ad_mark)가 그 값을 읽는다(11-03 윤상길 일본어판 — 사장님 승인)."""
    if S is None:
        return os.environ.get("SHORTEM_SCRIPT_LANG") or "ko"
    kana = re.compile(r"[\u3040-\u30ff]")
    return "ja" if any(kana.search(str(l.get("tts") or "")) for l in S.get("lines") or []) else "ko"


def nchar(s: str) -> int:
    """읽는 글자 수(SPOKEN) — 말속도의 분자. 잇썸·재미썸 두 렌더러가 같은 자를 쓴다."""
    return len(re.findall(SPOKEN, s or ""))


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


# 단계 시간 장부 — 주인은 tools/calcopy/engine/stage_log.py (10-18 엔진으로 옮김). 꼴·경로(stage_log.json) 그대로.
from tools.calcopy.engine.stage_log import Timer, timed  # noqa: E402,F401
