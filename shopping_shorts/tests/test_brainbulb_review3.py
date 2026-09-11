# -*- coding: utf-8 -*-
"""아스트라 3라운드 코드 리뷰가 요구한 테스트 — 지적 하나마다 재현 → 수정 확인.

① 효과음 2개 이상 실제 합성(입력 인덱스 버그)  ② 대본 변경 → 재합성(옛 음성 재사용)  ③ 반려 후 재개가 검사를 건너뛰지 않음
④ 비용 누적 상한  ⑤ 검수: 나레 파일 없음 = 실패  ⑥ 검수: 화면 밖 줄 반려
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts.brainbulb import spec, pipeline, render, review, voice, sfx, timing as tmod

FX = Path(__file__).parent / "fixtures" / "brainbulb"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
pytestmark = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")


def _script(job="parksuhong", n=None):
    p = json.loads((FX / job / "payload.json").read_text(encoding="utf-8"))
    groups = []
    for g in p["groups"][: n or len(p["groups"])]:
        ng = {"text": g["text"], "color": g["color"], "role": g["role"]}
        if g.get("img") is not None:
            ng["img"] = g["img"]
        if g.get("meme"):
            ng["meme"] = "경악/충격"
        groups.append(ng)
    groups[-1]["role"] = "PUNCH"
    for g in groups[:-1]:
        if g["role"] == "PUNCH":
            g["role"] = "NARR"
    return {"title": p["title"], "groups": groups}


def _tone(out, dur, freq=440):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
                    "-ar", "44100", "-ac", "2", out], check=True, stdin=subprocess.DEVNULL)


def _fake_tts(text, out):
    _tone(out, round(0.35 + 0.07 * len(text), 3))


# ① 효과음 2개 이상 — 실제 ffmpeg 합성
def test_sfx_bed_mixes_multiple_files_and_skips_missing(tmp_path):
    s = _script(n=6)
    sfx_dir = tmp_path / "sfx"; sfx_dir.mkdir()
    plan = sfx.plan([{"color": g["color"]} for g in s["groups"]])
    for x in plan[:4]:                                  # 4개만 만들고 2개는 누락
        _tone(str(sfx_dir / os.path.basename(x["file"])), 0.2, 880)
    t = tmod.build(1.0, [1.0] * 6, [{"text": g["text"], "color": g["color"], "role": g["role"]} for g in s["groups"]])
    out = render.sfx_bed(plan, t, str(sfx_dir), str(tmp_path), t["total"])
    assert out and os.path.exists(out)
    assert abs(tmod.wav_seconds(out) - t["total"]) <= 0.1


# ② 대본이 바뀌면 그 컷만 다시 합성, 나머지는 재사용
def test_voice_resynthesizes_only_changed_text(tmp_path):
    s = _script(n=5)
    calls = []
    def tts(text, out):
        calls.append(text); _fake_tts(text, out)
    v1 = voice.synth_all(s, str(tmp_path), tts)
    assert len(calls) == 6                              # 카드 + 5컷
    s2 = json.loads(json.dumps(s)); s2["groups"][2]["text"] = "완전히 다른 문장이다"
    v2 = voice.synth_all(s2, str(tmp_path), tts, spent_chars=v1["spent_chars"])
    assert calls[6:] == ["완전히 다른 문장이다"]           # 바뀐 컷 하나만
    assert v2["synthesized"] == [3]
    assert open(str(tmp_path / "tts" / "03.txt"), encoding="utf-8").read() == "완전히 다른 문장이다"


# ④ 비용은 잡당 누적
def test_voice_budget_is_cumulative(tmp_path):
    s = _script(n=5)
    v1 = voice.synth_all(s, str(tmp_path), _fake_tts)
    with pytest.raises(RuntimeError, match="누적"):
        voice.synth_all(s, str(tmp_path / "other"), _fake_tts, spent_chars=spec.POLICY_MAX_TTS_CHARS - 1)


# ③ 반려 후 재개해도 voice로 건너뛰지 않는다
def test_pipeline_rejected_script_does_not_advance(tmp_path):
    bad = {"title": {"h1": "제목", "h2": "숫자 3개", "card": "한 문장"},
           "groups": [{"text": "쉼표가, 있다", "color": "WHITE", "role": "PUNCH", "img": 1}]}
    r = pipeline.run_all(str(tmp_path), source_text="소재", llm=lambda _: json.dumps(bad, ensure_ascii=False), tts=_fake_tts)
    assert r["status"] == "failed" and r["step"] == "script"
    assert pipeline.next_step(str(tmp_path)) == "script"          # 다시 script부터
    r2 = pipeline.run_all(str(tmp_path), source_text="소재", llm=lambda _: json.dumps(bad, ensure_ascii=False), tts=_fake_tts)
    assert r2["status"] == "failed" and r2["step"] == "script"
    assert "voice" not in pipeline.load(str(tmp_path))["data"]


# ⑤ 검수: 나레 파일 없음 → 실패(빈 목록으로 통과하지 않는다)
def test_review_fails_when_narration_missing(tmp_path):
    s = _script(n=4)
    r = pipeline.run_all(str(tmp_path), source_text="소재", llm=lambda _: json.dumps(s, ensure_ascii=False), tts=_fake_tts)
    assert r["status"] == "ok", r
    d = pipeline.load(str(tmp_path))["data"]
    rep = review.run(d["render"]["mp4"], d["subtitle"]["path"], str(tmp_path / "없는파일.wav"), d["timing"])
    assert not rep["ok"]
    assert any(c["name"] == "narration_silence" and not c["ok"] for c in rep["checks"])
    assert any(c["name"] == "stream_sync" and c["ok"] for c in rep["checks"])


# ⑥ 검수: 화면 밖 줄이 ASS에 있으면 반려
def test_review_rejects_out_of_bounds_line(tmp_path):
    s = _script(n=4)
    r = pipeline.run_all(str(tmp_path), source_text="소재", llm=lambda _: json.dumps(s, ensure_ascii=False), tts=_fake_tts)
    assert r["status"] == "ok", r
    d = pipeline.load(str(tmp_path))["data"]
    ass = open(d["subtitle"]["path"], encoding="utf-8").read()
    bad = ass.replace("}방송인 박수홍", "}방송인 박수홍이 아주아주아주 길게 말했다고 한다 정말로")
    p = tmp_path / "bad.ass"; p.write_text(bad, encoding="utf-8")
    rep = review.run(d["render"]["mp4"], str(p), d["render"]["narr"], d["timing"])
    assert any(c["name"] == "subtitle_bounds" and not c["ok"] for c in rep["checks"])
