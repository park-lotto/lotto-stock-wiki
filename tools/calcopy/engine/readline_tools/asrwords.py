# -*- coding: utf-8 -*-
"""낱말 시각 받아쓰기(asrwords) — 로컬 위스퍼(faster-whisper small int8, 무료)로 낱말마다 시각 → sfx 후보가 말 구간 안인지 거를 때 쓴다.

어디서 왔나: 06 워커들이 세션 임시 폴더 asr_local.py 로 반복해서 쓰던 것을 옮김(설정 그대로: language=ko · word_timestamps · vad_filter 끔 · cpu_threads 8).
엔진 받아쓰기(engine/asr_local.transcribe)와 다른 점: 저쪽은 구절(쉼으로 끊은 문장)·음높이·크기를 내고 vad 를 켠다 — 이쪽은 낱말 시각이 목적이라 vad 를 끈다.
모델 불러오기·pcm 은 engine/asr_local 의 것을 그대로 쓴다(한 곳).
출력(json): {model, segments:[{t0,t1,text}], words:[{t0,t1,w,p}]}

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/asrwords.py <out_dir> <mp4 ...>        # <out_dir>/<id>.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_M = {}


def model(name: str = "small"):
    if name not in _M:
        from tools.calcopy.engine.asr_local import _import_whisper
        WhisperModel = _import_whisper()
        _M[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=8)
    return _M[name]


def words(mp4: str, name: str = "small", lang: str = "ko") -> dict:
    from tools.calcopy.engine.asr_local import pcm
    segs, info = model(name).transcribe(pcm(mp4), language=lang, word_timestamps=True, vad_filter=False)
    ws, ss = [], []
    for s in segs:
        ss.append({"t0": round(s.start, 2), "t1": round(s.end, 2), "text": s.text})
        for w in s.words or []:
            ws.append({"t0": round(w.start, 2), "t1": round(w.end, 2), "w": w.word, "p": round(w.probability, 2)})
    return {"model": f"faster-whisper {name} int8 (local)", "segments": ss, "words": ws}


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 2:
        print(__doc__)
        return 2
    out = Path(a[0])
    out.mkdir(parents=True, exist_ok=True)
    for mp4 in a[1:]:
        d = words(mp4, os.environ.get("SHORTEM_WHISPER_MODEL", "small"))
        p = out / f"{Path(mp4).stem}.json"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(Path(mp4).stem, len(d["segments"]), len(d["words"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
