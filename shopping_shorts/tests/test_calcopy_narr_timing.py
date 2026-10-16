# -*- coding: utf-8 -*-
"""나레 줄 끝·줄 시작 (관제 097, 10-16 핫템 HONOR 실측 결함 2개).
  ① hottem_audio.sentence_breaks — 벽시계 글자 비례는 쉼표 쉼이 쌓여 줄 끝을 엉뚱한 쉼으로 골랐다(2·3번 줄 11.408·13.669, 받아쓰기 9.75·12.79)
     → 말 시간(쉼 뺀 시간) 기준 글자 비례 + 같은 거리면 긴 쉼.
  ② narr_video.time_steps — 전체 글자 비례라 줄 시작이 실제 말보다 0.46~0.75초 늦었다 → 줄 시작 = 줄 끝 쉼 다음 첫 말 구간(line_starts).
답 아는 입력: 합성 '나레'(톤=말, 무음=쉼)에서 줄 경계를 안다. 쉼표 쉼(0.5초)이 문장 끝 쉼(0.3초)보다 길고 첫 줄에 몰려 있다."""
import math
import shutil
import struct
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy import hottem_audio as ha  # noqa: E402
from tools.calcopy import narr_video as nv  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 필요")

LINES = ["가나다, 라마바, 사아자, 차카타.", "가나다라마바사아자차카타.", "가나다라마바사아자차카타."]
CH, COMMA, END_P = 0.1, 0.5, 0.3       # 글자당 말 0.1초 · 쉼표 쉼 0.5 · 문장 끝 쉼 0.3


def _synth(path: Path, commas: bool = True, ch0: float = CH):
    """줄 0: (쉼표면) 3자 말 + 쉼표 쉼 ×3 + 3자, 아니면 12자 말(글자당 ch0초) · 줄 1·2: 12자 말. 앞뒤 0.2초 무음.
    돌려주는 값 = (줄 끝 쉼 가운데들, 줄 시작들)."""
    sr, frames, t = 48000, [], 0.0

    def tone(sec):
        nonlocal t
        frames.extend(int(8000 * math.sin(2 * math.pi * 220 * i / sr)) for i in range(int(sec * sr)))
        t += sec

    def rest(sec):
        nonlocal t
        frames.extend([0] * int(sec * sr))
        t += sec
    rest(0.2)
    starts, breaks = [0.2], []
    if commas:
        for k in range(4):
            tone(3 * ch0)
            if k < 3:
                rest(COMMA)
    else:
        tone(12 * ch0)
    for li in (1, 2):
        breaks.append(t + END_P / 2)
        rest(END_P)
        starts.append(t)
        tone(12 * CH)
    rest(0.2)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", v) for v in frames))
    return breaks, starts


def test_breaks_use_speech_time_not_wall_clock(tmp_path):
    wav = tmp_path / "n.wav"
    breaks, _ = _synth(wav)
    got = ha.sentence_breaks(str(wav), LINES)
    assert len(got) == 2 and all(abs(g - b) <= 0.05 for g, b in zip(got, breaks)), (got, breaks)


def test_line_starts_anchor_to_real_speech(tmp_path):
    """줄마다 말 빠르기가 다르다(줄 0 이 1.5배 느림 — HONOR 처럼 TTS 가 줄마다 속도가 다름). 전체 글자 비례는 줄 1 시작을 줄 0 안에 놓는다."""
    wav = tmp_path / "n.wav"
    _, starts = _synth(wav, commas=False, ch0=0.15)
    lines = ["가나다라마바사아자차카타.", LINES[1], LINES[2]]
    steps = nv.steps_of(lines, 6, "replace")
    new, _ = nv.time_steps(steps, str(wav), lines=lines, asr=False)
    old, _ = nv.time_steps([{k: v for k, v in s.items() if k != "line"} for s in steps], str(wav))
    first = lambda out, li: next(o["t0"] for o, s in zip(out, steps) if s["line"] == li)   # noqa: E731
    for li in (1, 2):
        assert abs(first(new, li) - starts[li]) <= 0.15, (li, first(new, li), starts[li])
    # 대조군(사보타주 = lines 안 줌, 종전 전체 글자 비례): 줄 1 시작이 실제와 0.3초 넘게 어긋난다 — 이 잣대가 그 결함을 잡는다
    assert abs(first(old, 1) - starts[1]) > 0.3, (first(old, 1), starts[1])


HONOR = Path("C:/숏템_칼카피/hottemreport/칼카피_로봇폰/make/narr_full.mp3")
HONOR_ASR = [3.455, 7.112, 9.75, 12.79, 17.046, 21.814]   # 줄 끝 쉼 가운데 — 제미나이 받아쓰기로 확인(핫템 담당 make_render.BR0)


@pytest.mark.skipif(not HONOR.exists() or not (ROOT / "channel/hottemreport/칼카피_로봇폰/대본.json").exists(), reason="HONOR 나레 실물 없음")
def test_honor_line_ends_within_015():
    import json
    lines = [l["text"] for l in json.loads((ROOT / "channel/hottemreport/칼카피_로봇폰/대본.json").read_text(encoding="utf-8"))["final"]["lines"]]
    got = ha.sentence_breaks(str(HONOR), lines)
    assert all(abs(g - b) <= 0.15 for g, b in zip(got, HONOR_ASR)), (got, HONOR_ASR)   # 1판: [.., 11.408, 13.669, ..]


def _synth_tight(path: Path):
    """방구석 꼴: 줄 사이 쉼 0.07초(무음 검출에 안 잡힘) · 줄 1·2 가운데 쉼표 쉼 0.5초(쉼 수 = 경계 수). 돌려주는 값 = 줄 시작들."""
    sr, frames, t = 48000, [], 0.0

    def seg(sec, on):
        nonlocal t
        n = int(sec * sr)
        frames.extend((int(8000 * math.sin(2 * math.pi * 220 * i / sr)) for i in range(n)) if on else [0] * n)
        t += sec
    seg(0.2, False)
    starts = [0.2]
    seg(1.2, True)
    seg(0.07, False); starts.append(t)
    seg(0.6, True); seg(0.5, False); seg(0.6, True)
    seg(0.07, False); starts.append(t)
    seg(0.6, True); seg(0.5, False); seg(0.6, True); seg(0.2, False)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", v) for v in frames))
    return starts


def test_no_pause_boundary_falls_back_to_char_ratio(tmp_path):
    """줄 끝 쉼이 없으면(쉼 0.07초로 줄인 나레) 그 경계는 글자 비례로 되돌리고 [경보] — 1판은 줄 1 가운데 쉼표 쉼에 붙어 줄 1 시작이 0.9초 늦었다."""
    wav = tmp_path / "t.wav"
    starts = _synth_tight(wav)
    lines = ["가나다라마바사아자차카타.", "가나다라마바, 사아자차카타.", "가나다라마바, 사아자차카타."]
    steps = nv.steps_of(lines, 6, "replace")
    logs = []
    out, _ = nv.time_steps(steps, str(wav), lines=lines, log=logs.append, asr=False)
    first = next(o["t0"] for o, s in zip(out, steps) if s["line"] == 1)
    assert abs(first - starts[1]) <= 0.3, (first, starts[1])
    assert any("[경보] 줄 1" in m for m in logs), logs


BANGGU3 = Path("C:/숏템_칼카피/banggu/칼카피_3편/render/narr_final.mp3")


@pytest.mark.skipif(not BANGGU3.exists() or not (ROOT / "channel/banggu/칼카피_3편/대본.json").exists(), reason="방구석 3편 나레 실물 없음")
def test_banggu3_second_line_start():
    """방구석 3편 실물: 2줄 실제 말 시작 1.6초(받아쓰기, 방구석 담당) — 64b05f042 는 3.71초로 훅을 늘렸다."""
    import json
    lines = [l["text"] for l in json.loads((ROOT / "channel/banggu/칼카피_3편/대본.json").read_text(encoding="utf-8"))["final"]["lines"]]
    steps = nv.steps_of(lines, 13, "accumulate")
    out, _ = nv.time_steps(steps, str(BANGGU3), lines=lines, log=lambda *_: None, asr=False)
    assert abs(next(o["t0"] for o, s in zip(out, steps) if s["line"] == 1) - 1.6) <= 0.3


# ── 줄 시작 1순위 = 받아쓰기 정렬(10-16 조율자: 쉼 방식이 핫템·방구석에서 세 번 어긋남) ─────────────
def test_asr_line_starts_matches_line_heads():
    segs = [{"start": 0.0, "end": 2.0, "text": "코스트코가 가격표에 숨겨둔 암호"}, {"start": 2.0, "end": 4.0, "text": "문제는 그 할인이 끝나는데 그래서"},
            {"start": 4.0, "end": 6.0, "text": "미국 틱톡에선 별표를"}]
    lines = ["코스트코가 가격표에 숨겨 둔 암호", "문제는 그 할인이, 끝나는데", "그래서 미국 틱톡에선 별표를,", "전혀 없는 말"]
    got = nv.asr_line_starts(lines, segs)
    assert got[0] == 0.0 and got[1] == 2.0 and got[3] is None
    assert 3.5 < got[2] < 4.0, got        # '그래서'는 구절 2 끝쪽 — 구절 안 글자 비례


def test_transcript_cache_means_no_network(tmp_path):
    import hashlib
    import json
    wav = tmp_path / "n.wav"
    _synth(wav)
    calls = []

    def ask(parts, prompt, tag=""):
        calls.append(tag)
        return {"segments": [{"start": 0.0, "end": 1.0, "text": "가나다"}], "_model": "가짜"}, None
    segs, why = nv.tts_transcript(str(wav), ask)
    assert segs and len(calls) == 1 and (tmp_path / "n.wav.asr.json").exists()
    segs2, why2 = nv.tts_transcript(str(wav), ask)
    assert segs2 == segs and len(calls) == 1 and "캐시" in why2          # 같은 파일 = 재호출 0
    c = json.loads((tmp_path / "n.wav.asr.json").read_text(encoding="utf-8"))
    assert c["md5"] == hashlib.md5(wav.read_bytes()).hexdigest()
    _synth(wav, commas=False)                                              # 파일이 바뀌면(md5 다름) 다시 받아쓴다
    nv.tts_transcript(str(wav), ask)
    assert len(calls) == 2


FINAL2 = Path("C:/숏템_칼카피/banggu/칼카피_3편/render/narr_final2.mp3")
FINAL2_TRUE = {3: 8.13, 5: 14.27, 6: 18.40}   # 방구석 담당 실측(쉼↔쉼표 대조): '사실…'·'그래서…'·'심지어…' 줄 시작


@pytest.mark.skipif(not FINAL2.exists() or not FINAL2.with_name(FINAL2.name + ".asr.json").exists(), reason="narr_final2·받아쓰기 캐시 없음")
def test_banggu_final2_line_starts_by_asr():
    """받아쓰기 캐시로(네트워크 0) 줄 시작 오차 ≤0.3초. 빨강 대조군 = 받아쓰기 끔(쉼 방식: 7.42·16.04·19.36)."""
    import json
    lines = [l["text"] for l in json.loads((ROOT / "channel/banggu/칼카피_3편/대본.json").read_text(encoding="utf-8"))["final"]["lines"]]
    steps = nv.steps_of(lines, 13, "accumulate")

    def starts(asr):
        def boom(*a, **k):
            raise AssertionError("캐시가 있는데 받아쓰기를 불렀다")
        out, _ = nv.time_steps(steps, str(FINAL2), lines=lines, log=lambda *_: None, asr=asr, ask=boom)
        return {k: next(o["t0"] for o, s in zip(out, steps) if s["line"] == k) for k in FINAL2_TRUE}
    got = starts(True)
    assert all(abs(got[k] - v) <= 0.3 for k, v in FINAL2_TRUE.items()), got
    off = starts(False)
    assert all(abs(off[k] - v) > 0.3 for k, v in FINAL2_TRUE.items()), off
