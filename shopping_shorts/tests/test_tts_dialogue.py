# -*- coding: utf-8 -*-
"""대화형 칸 음성: 일레븐 화자 덩어리는 대화 API 한 번, 타입캐스트는 줄마다 — 칸마다 파일·정렬이 나오는가."""
import base64
import subprocess

import pytest

from shopping_shorts import tts_dialogue, typecast_tts, audio_post


def _tone(path, secs):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency=300:duration={secs}", "-c:a", "libmp3lame", str(path)], check=True)


class _Resp:
    def __init__(self, j): self.status_code, self._j, self.text = 200, j, ""
    def json(self): return self._j


@pytest.fixture
def setup(tmp_path, monkeypatch):
    full = tmp_path / "full.mp3"; _tone(full, 3.0)
    texts = ["언니 그거 뭐야?", "케이블 보호기야."]
    chars = list("[curious] " + texts[0] + texts[1])
    n = len(chars)
    st = [i * 2.8 / n for i in range(n)]; en = [t + 2.8 / n for t in st]
    calls = {"post": [], "tc": []}

    def post(url, headers=None, json=None, timeout=None):
        calls["post"].append(json)
        return _Resp({"audio_base64": base64.b64encode(full.read_bytes()).decode(),
                      "alignment": {"characters": chars, "character_start_times_seconds": st,
                                    "character_end_times_seconds": en},
                      "voice_segments": [{"dialogue_input_index": 0, "start_time_seconds": 0.0, "end_time_seconds": 1.5},
                                         {"dialogue_input_index": 1, "start_time_seconds": 1.6, "end_time_seconds": 2.9}]})

    def tc(text, out, **kw):
        calls["tc"].append(text); _tone(out, 1.0); return None
    monkeypatch.setattr(typecast_tts, "synthesize", tc)
    monkeypatch.setattr(tts_dialogue.tts, "_api_key", lambda cid=0: "k")
    beats = [{"narration": "이제 이걸로 끝났음."}, {"narration": texts[0]}, {"narration": texts[1]}]
    dlg = {"lines": [{"speaker": "나레이션", "tag": ""}, {"speaker": "동생", "tag": "curious"},
                     {"speaker": "언니", "tag": ""}],
           "voices": {"나레이션": {"voice_id": "tc_x", "model_id": "ssfm-v30", "settings": {}},
                      "동생": {"voice_id": "v_d", "model_id": "eleven_v3"},
                      "언니": {"voice_id": "v_u", "model_id": "eleven_v3"}}}
    return tmp_path, beats, dlg, post, calls


def test_groups_and_files(setup):
    tmp, beats, dlg, post, calls = setup
    outs = [str(tmp / f"b{i}.mp3") for i in range(3)]
    tts_dialogue.synthesize(beats, dlg, outs, tempo=1.25, post=post, work_dir=tmp)
    assert calls["tc"] == ["이제 이걸로 끝났음."]                 # 타입캐스트 줄은 줄마다
    assert len(calls["post"]) == 1                               # 일레븐 두 줄은 한 번에
    ins = calls["post"][0]["inputs"]
    assert ins[0]["text"].startswith("[curious] ") and ins[1]["voice_id"] == "v_u"
    durs = [audio_post._audio_dur(o) for o in outs]
    assert all(d and d > 0.3 for d in durs), durs
    assert "_tts_out" not in beats[0]


def test_line_count_mismatch_raises(setup):
    tmp, beats, dlg, post, _ = setup
    with pytest.raises(tts_dialogue.DialogueError, match="다시 변환"):
        tts_dialogue.synthesize(beats[:2], dlg, [str(tmp / "a.mp3"), str(tmp / "b.mp3")], post=post)


def test_missing_voice_raises(setup):
    tmp, beats, dlg, post, _ = setup
    del dlg["voices"]["언니"]
    with pytest.raises(tts_dialogue.DialogueError, match="성우"):
        tts_dialogue.synthesize(beats, dlg, [str(tmp / f"{i}.mp3") for i in range(3)], post=post)
