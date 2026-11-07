# -*- coding: utf-8 -*-
"""#1625 김미향(피쉬) — 글자 시각이 없는 목소리는 줄 경계만 받아쓰기(spans_by_speech)로 찾고 자막 덩어리 시각은 글자 수 어림이라
말이 빠른 앞 덩어리 뒤 다음 덩어리가 늦게 넘어갔다(앞 줄 끝 덩어리가 다음 줄 첫 덩어리와 같이 뜸).
주인 narr_align.speech_align — 합성 입구(synth_cached)에서 받아쓰기 낱말 시각으로 글자 시각을 한 번 만들어 사이드카에 둔다.
줄 경계·자막 덩어리·이름 끊김이 모두 그 한 시계를 쓴다."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import narr_align as NA  # noqa: E402
from tools.calcopy.engine import narr_verify as NV  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

TEXT = "가나다라, 마바사아자차카."
WORDS = [{"w": "가나다라", "s": 0.0, "e": 0.4}, {"w": "마바사아자차카", "s": 1.5, "e": 2.5}]   # 앞 덩어리는 빠르고 쉼이 길다


def test_speech_align_times_from_words(monkeypatch, tmp_path):
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": WORDS)
    a = NA.speech_align(TEXT, tmp_path / "x.mp3", log=lambda *x: None)
    assert "".join(a["characters"]) == TEXT
    s = a["character_start_times_seconds"]
    assert s[0] == 0.0 and s[TEXT.index("마")] == 1.5
    assert 0.4 <= s[TEXT.index(",")] <= 1.5          # 부호는 앞뒤 글자 사이
    assert [p[0] for p in NA.punct_slots(TEXT, a)] == [",", "."]


def test_caption_chunk_follows_speech_not_char_count(monkeypatch, tmp_path):
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": WORDS)
    a = NA.speech_align(TEXT, tmp_path / "x.mp3", log=lambda *x: None)
    L = {"id": "N1", "kind": "tts", "tts": TEXT, "caps": [{"text": "가나다라,"}, {"text": "마바사아자차카."}]}
    st = RB.narr_cap_starts(L, {"dur": 2.6, "raw": [0.0, 2.6], "tempo": 1.0}, a, 0)
    assert abs(st[1] - 1.5) < 0.05, st               # 글자 수 어림이면 2.6×4/11 = 0.95초


def test_poor_asr_keeps_old_path(monkeypatch, tmp_path):
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": [{"w": "전혀", "s": 0.0, "e": 0.3}])
    assert NA.speech_align(TEXT, tmp_path / "x.mp3", log=lambda *x: None) is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_synth_cached_fills_align_once(monkeypatch, tmp_path):
    out = tmp_path / "narr_full.mp3"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=220:d=3", str(out)], check=True)
    key = NA.voice_key(TEXT, "fs-x", None, NA.TTS_MODEL, "fish", None)
    NA.sidecar_of(out).write_text(json.dumps({"key": key, "align": None}), encoding="utf-8")   # 피쉬 합성 캐시(글자 시각 없음)
    calls = []
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": calls.append(p) or WORDS)
    a = NA.synth_cached(TEXT, "fs-x", None, out, log=lambda *x: None, provider="fish")
    assert a and a["character_start_times_seconds"][TEXT.index("마")] == 1.5
    assert json.loads(NA.sidecar_of(out).read_text(encoding="utf-8"))["align"] == a      # 사이드카에 — 다음엔 받아쓰기 없이
    assert NA.synth_cached(TEXT, "fs-x", None, out, log=lambda *x: None, provider="fish") == a and len(calls) == 1
