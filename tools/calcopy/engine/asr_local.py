# -*- coding: utf-8 -*-
"""받아쓰기 창구(고객 PC 모드) — 위스퍼(로컬, 기본) · 스피치매틱스(고객 키가 있을 때) (관제 234, 2026-10-19 사장님 "받아쓰기는 위스퍼 / 스피치매틱스도 후보").

제미나이는 소리를 직접 듣지만, 고객 PC 모드의 AI(고객 Claude)는 소리를 못 듣는다. 그래서 소리 파트는 여기서
**글(구절·시각) + 잰 소리 특징(구절별 음높이·크기, 음악 유무)** 으로 바꿔 Claude 에게 넘긴다(client_llm.describe_audio).

  transcribe(audio_path) -> {"engine": "whisper:small"|"speechmatics", "lang", "segments": [{start,end,text,f0,db}], "dur"}

- 위스퍼 = faster-whisper(CTranslate2, CPU int8). 모델 = SHORTEM_WHISPER_MODEL(기본 small) — 설치팩은 모델 폴더를 같이 깐다
  (SHORTEM_WHISPER_DIR, 처음부터 다 깔려 있게). 오디오는 ffmpeg 로 16kHz PCM 으로 풀어 배열로 넘긴다(av 의존 없음).
- 구절 = 낱말 시각에서 쉼(≥ PAUSE_S)마다 끊는다(위스퍼 기본 구절은 6초 한 덩어리로 나온다 — 10-19 실측).
- 스피치매틱스 = transcribe(engine='speechmatics')(칼카피 내부) 또는 SHORTEM_ASR=speechmatics(고객) 이고 키가 있을 때(speechmatics_key — 환경변수·~/.volcano/keys/speechmatics). 없으면 위스퍼.
"""
from __future__ import annotations

import os
import subprocess

SR = 16000
PAUSE_S = 0.35
_MODEL = {}


def pcm(path: str):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def _yin(w, lo: int, hi: int, thr: float = 0.15) -> int | None:
    """YIN(누적 평균 정규화 차이) — 주기가 있는 소리만 lag 를 돌려준다. 잡음은 None(10-19: 자기상관 0.3 문턱은 분홍·갈색 잡음도 100% '음높이'로 잡았다)."""
    import numpy as np
    n = len(w) - hi
    d = np.array([np.sum((w[:n] - w[t:t + n]) ** 2) for t in range(hi + 1)])
    cm = d.copy()
    cm[1:] = d[1:] * np.arange(1, hi + 1) / np.maximum(np.cumsum(d[1:]), 1e-12)
    cand = np.where(cm[lo:hi] < thr)[0]
    if not len(cand):
        return None
    k = lo + int(cand[0])
    while k + 1 < hi and cm[k + 1] < cm[k]:
        k += 1
    return k


def _f0(x) -> float | None:
    """구절의 대표 음높이(Hz, YIN) — 성별 짐작 재료(남 ~85–180, 여 ~165–255). 주기 있는 창이 3개 미만이면 None."""
    import numpy as np
    if len(x) < SR // 5:
        return None
    lo, hi = SR // 400, SR // 70
    vals = []
    for i in range(0, len(x) - 1024 - hi, 1600):
        w = x[i:i + 1024 + hi]
        if np.sqrt((w ** 2).mean()) < 0.01:
            continue
        k = _yin(w.astype(np.float64), lo, hi)
        if k:
            vals.append(SR / k)
    return round(float(np.median(vals)), 1) if len(vals) >= 3 else None


def _db(x) -> float:
    import numpy as np
    r = float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
    return round(20 * np.log10(r + 1e-9), 1)


def _import_whisper():
    """faster_whisper → huggingface_hub 가 `import filelock`(pip 패키지)을 하는데, 엔진 파일을 스크립트로 띄우면
    sys.path[0] = tools/calcopy/engine 이라 엔진의 filelock.py 가 대신 잡힌다(10-19 실측 ImportError BaseFileLock).
    그 한 번만 엔진 폴더를 경로에서 빼고 불러온다."""
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != here]
    shadow = sys.modules.get("filelock")
    if shadow is not None and os.path.dirname(os.path.abspath(getattr(shadow, "__file__", "") or "")) == here:
        del sys.modules["filelock"]
    try:
        from faster_whisper import WhisperModel
        import filelock  # noqa: F401 — 모델 만들 때(WhisperModel(...)) 늦게 불리는 huggingface_hub 가 쓰는 진짜 패키지를 먼저 잡아 둔다
        import huggingface_hub.utils  # noqa: F401
    finally:
        sys.path[:] = saved
    return WhisperModel


def _whisper(a) -> dict:
    WhisperModel = _import_whisper()
    name = os.environ.get("SHORTEM_WHISPER_MODEL", "small")
    root = os.environ.get("SHORTEM_WHISPER_DIR")
    if name not in _MODEL:
        _MODEL[name] = WhisperModel(os.path.join(root, name) if root else name, device="cpu", compute_type="int8")
    segs, info = _MODEL[name].transcribe(a, vad_filter=True, word_timestamps=True)
    words = [w for s in segs for w in (s.words or [])]
    out, cur = [], None
    for w in words:
        if cur and (w.start - cur["end"] >= PAUSE_S):
            out.append(cur)
            cur = None
        if not cur:
            cur = {"start": float(w.start), "end": float(w.end), "text": w.word.strip()}
        else:
            cur["end"] = float(w.end)
            cur["text"] = (cur["text"] + w.word).strip()
    if cur:
        out.append(cur)
    return {"engine": f"whisper:{name}", "lang": info.language, "segments": out}


def speechmatics_key() -> str:
    """키 자리 한 곳: 환경변수 SPEECHMATICS_API_KEY → SPEECHMATICS_KEY → ~/.volcano/keys/speechmatics(볼케이노 실행기와 같은 자리, 값 한 줄).
    10-21 사장님 '스피치매틱스 승인' — 서버(/etc/shopping-shorts.env·DB)에는 키가 없고 이 PC 볼케이노 키 파일에 있다(실측)."""
    v = (os.environ.get("SPEECHMATICS_API_KEY") or os.environ.get("SPEECHMATICS_KEY") or "").strip()
    if v:
        return v
    p = os.path.expanduser("~/.volcano/keys/speechmatics")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def _speechmatics(path: str) -> dict:
    """고객 키 스피치매틱스(batch). 실패하면 예외 — 부르는 쪽이 위스퍼로 다시."""
    import json
    import time
    import requests
    key = speechmatics_key()
    H = {"Authorization": f"Bearer {key}"}
    cfg = {"type": "transcription", "transcription_config": {"language": "auto", "operating_point": "enhanced"}}
    with open(path, "rb") as f:
        r = requests.post("https://asr.api.speechmatics.com/v2/jobs", headers=H, files={"data_file": f},
                          data={"config": json.dumps(cfg)}, timeout=120)
    r.raise_for_status()
    jid = r.json()["id"]
    for _ in range(120):
        time.sleep(3)
        s = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}", headers=H, timeout=30).json()["job"]["status"]
        if s == "done":
            break
        if s in ("rejected", "deleted"):
            raise RuntimeError(f"speechmatics {s}")
    t = requests.get(f"https://asr.api.speechmatics.com/v2/jobs/{jid}/transcript?format=json-v2", headers=H, timeout=60).json()
    out, cur = [], None
    for it in t.get("results", []):
        if it.get("type") != "word":
            continue
        w = it["alternatives"][0]["content"]
        if cur and it["start_time"] - cur["end"] >= PAUSE_S:
            out.append(cur)
            cur = None
        if not cur:
            cur = {"start": it["start_time"], "end": it["end_time"], "text": w}
        else:
            cur["end"] = it["end_time"]
            cur["text"] += " " + w
    if cur:
        out.append(cur)
    return {"engine": "speechmatics", "lang": (t.get("metadata", {}).get("language_identification") or {}).get("predicted_language", ""),
            "segments": out}


def transcribe(path: str, engine: str | None = None) -> dict:
    """engine='speechmatics' = 칼카피 내부(사장님 승인 10-21, 유료·가장 정확). 고객 설치는 SHORTEM_ASR=speechmatics 일 때만(고객 키 과금 — 기본 위스퍼 그대로)."""
    a = pcm(path)
    res = None
    if (engine or os.environ.get("SHORTEM_ASR")) == "speechmatics" and speechmatics_key():
        try:
            res = _speechmatics(path)
        except Exception as e:  # noqa: BLE001 — 고객 키 실패는 이유를 남기고 위스퍼로(조용히 삼키지 않는다)
            res = None
            why = f"speechmatics 실패: {str(e)[:120]} → 위스퍼"
    if res is None:
        res = _whisper(a)
        if "why" in locals():
            res["note"] = why
    for s in res["segments"]:
        x = a[int(s["start"] * SR):int(s["end"] * SR)]
        s["f0"], s["db"] = _f0(x), _db(x)
    res["dur"] = round(len(a) / SR, 2)
    res["db_all"] = _db(a)
    res["bed"] = _bed(a, res["segments"])
    return res


def _bed(a, segs) -> dict:
    """말 없는 구간에 깔린 소리(배경음악·현장음) — 1초 창마다 크기와 '음 높낮이가 이어지는 정도'(음악다움).
    10-19 실측: 남성 보컬 노래가 깔린 원본에서 위스퍼가 가사 두 마디만 말로 잡아 '배경음악 없음'으로 오판했다
    → 말 없는 구간이 크고(> -35dB) 음높이가 꾸준히 잡히면(음악) 그 숫자를 Claude 에게 준다."""
    import numpy as np
    speech = np.zeros(len(a), bool)
    for s in segs:
        speech[int(s["start"] * SR):int(s["end"] * SR)] = True
    wins, loud, tonal = 0, 0, 0
    for i in range(0, len(a) - SR, SR):
        if speech[i:i + SR].mean() > 0.5:
            continue
        x = a[i:i + SR]
        wins += 1
        if _db(x) > -35:
            loud += 1
            if _f0(x) is not None:
                tonal += 1
    return {"nonspeech_s": wins, "loud_s": loud, "tonal_s": tonal,
            "loud_share": round(loud / wins, 2) if wins else 0.0, "tonal_share": round(tonal / wins, 2) if wins else 0.0}
