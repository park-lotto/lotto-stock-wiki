# -*- coding: utf-8 -*-
"""narr_video 자막 사건 — 빈 자막(blank)·강조 자막(emph) (관제 097, 10-16 핫템 담당 요청).
진짜로 렌더해서(합성 회색 영상 + 톤/무음 '나레' + 썰풀다 틀 B) 프레임 잉크로 잰다 — 계산 대조가 아니다.
  ① 보통 구간: 자막 띠에 흰 잉크가 있다(이 잣대가 자막을 잡는다는 대조군)
  ② blank 구간: 흰 잉크 0
  ③ emph 구간: 흰 잉크 0 + emph rgb 에 가까운 잉크가 있다"""
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FRAME = ROOT / "channel" / "sseolpulda" / "칼카피_mY" / "frame_mY.json"
EMPH_RGB = [80, 170, 255]


def _tts(path: Path):
    """말(톤) 1.2초 · 쉼 0.6초 반복 3번 = 5.4초 — silencedetect 가 말 구간 3개로 잡는다."""
    sr = 48000
    frames = []
    for k in range(3):
        frames += [int(8000 * math.sin(2 * math.pi * 220 * i / sr)) for i in range(int(1.2 * sr))]
        frames += [0] * int(0.6 * sr)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", v) for v in frames))


def _frame_at(mp4: Path, t: float, png: Path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(png)], check=True)
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(png).convert("RGB")).astype(int)


@pytest.mark.skipif(not shutil.which("node") or not shutil.which("ffmpeg") or not FRAME.exists(), reason="렌더러(node)·ffmpeg·틀 필요")
def test_blank_and_emph_caption_events_in_rendered_frames(tmp_path):
    from tools.calcopy import narr_video
    cand = tmp_path / "cand"; cand.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x606060:s=1280x720:d=7:r=30", "-pix_fmt", "yuv420p",
                    str(cand / "gray.mp4")], check=True)
    tts = tmp_path / "tts.wav"; _tts(tts)
    script = {"final": {"lines": [{"text": "첫 번째 문장이에요."}, {"text": "두 번째 문장이에요."}, {"text": "세 번째 문장이에요."}]},
              "caption_events": [{"kind": "blank", "t0": 1.9, "dur": 1.0},
                                 {"kind": "emph", "text": "와아!", "rgb": EMPH_RGB, "t0": 3.7, "dur": 1.0}]}
    (tmp_path / "s.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    mats = {"cand_dir": str(cand), "shots": [{"src": "gray.mp4", "ss": 0, "full": True}] * 3}
    (tmp_path / "m.json").write_text(json.dumps(mats), encoding="utf-8")
    final = narr_video.build({"frames": [{"frame": str(FRAME), "t_end": None}], "script": str(tmp_path / "s.json"), "tts": str(tts),
                              "materials": str(tmp_path / "m.json"), "out": str(tmp_path / "out"), "chunk": 30, "caption_mode": "replace", "line_asr": False})
    cap = next(l for l in json.loads(FRAME.read_text(encoding="utf-8"))["layers"] if l.get("role") == "caption")
    y0, y1 = int(cap["y"]) - 10, int(cap["y"] + cap["line_h"]) + 10

    def band(t):
        a = _frame_at(Path(final), t, tmp_path / f"f{t}.png")[y0:y1]
        white = int(((a[..., 0] > 225) & (a[..., 1] > 225) & (a[..., 2] > 225)).sum())
        near = int((abs(a - EMPH_RGB).max(-1) < 40).sum())
        return white, near

    w_norm, _ = band(0.6)
    w_blank, n_blank = band(2.4)
    w_emph, n_emph = band(4.2)
    assert w_norm > 500, f"대조군: 보통 구간 흰 자막 잉크가 잡혀야 한다({w_norm})"
    assert w_blank == 0 and n_blank == 0, f"blank 구간 자막 잉크 0 이어야(흰 {w_blank}, 강조색 {n_blank})"
    assert w_emph == 0, f"emph 구간 흰 자막 0 이어야({w_emph})"
    assert n_emph > 500, f"emph 구간 잉크 색 = rgb {EMPH_RGB} 이어야({n_emph})"


def test_apply_caption_events_cuts_text_only():
    from tools.calcopy.narr_video import apply_caption_events
    steps = [{"t0": 0.0, "t1": 2.0, "text": "가"}, {"t0": 2.0, "t1": 4.0, "text": "나"}]
    out = apply_caption_events(steps, [{"kind": "blank", "t0": 1.5, "dur": 1.0}], 4.0)
    assert [(r["t0"], r["t1"], r["text"]) for r in out] == [(0.0, 1.5, "가"), (1.5, 2.5, ""), (2.5, 4.0, "나")]
    assert apply_caption_events(steps, [], 4.0) == [{"t0": 0.0, "t1": 2.0, "text": "가"}, {"t0": 2.0, "t1": 4.0, "text": "나"}]
