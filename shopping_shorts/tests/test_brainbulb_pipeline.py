# -*- coding: utf-8 -*-
"""brainbulb 파이프라인 — 린터·배치는 실제 5편 대본으로, 끝까지는 가짜 LLM(실제 대본 반환)·가짜 TTS(사인파)·**진짜 ffmpeg 렌더**로 돈다.

돈 나가는 호출(LLM·Typecast)은 주입으로 대체하고, 그 외(측정·배치·ASS·효과음·렌더·검수)는 실물이다.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts.brainbulb import lint, layout, prompt, pipeline, spec

FX = Path(__file__).parent / "fixtures" / "brainbulb"
JOBS = ["parksuhong", "leedonggun", "taser", "borneo", "parkwi"]
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _script(job):
    p = json.loads((FX / job / "payload.json").read_text(encoding="utf-8"))
    groups = []
    for g in p["groups"]:
        ng = {"text": g["text"], "color": g["color"], "role": g["role"]}
        if g.get("img") is not None:
            ng["img"] = g["img"]
        if g.get("meme"):
            ng["meme"] = "경악/충격"      # payload엔 파일 경로만 있다 → 감정은 enum 아무거나
        groups.append(ng)
    return {"title": p["title"], "region": p.get("region"), "groups": groups}, p.get("transcript") or ""


# ── 린터: 실제 5편은 반려 0건이어야 한다 ─────────────────────────────────────────
@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
@pytest.mark.parametrize("job", JOBS)
def test_real_scripts_pass_lint(job):
    s, src = _script(job)
    issues, laid = lint.lint(s, source_text=src)
    rej = lint.rejects(issues)
    assert not rej, [i.__dict__ for i in rej]
    assert all(g.get("lines") for g in laid["groups"])


def test_lint_catches_synthetic_violations():
    s = {"title": {"h1": "제목에 물음표?", "h2": "이건 사연", "card": "한 문장. 두 문장"},
         "groups": [
             {"text": "쉼표가, 있다", "color": "RED", "role": "NARR", "img": 1},
             {"text": "두번째", "color": "YELLOW", "role": "NARR", "img": 1},
             {"text": "세번째", "color": "PINK", "role": "NARR", "img": 1},
             {"text": "그렇게 되었습니다", "color": "WHITE", "role": "NARR", "img": 1},
             {"text": "하시겠습니까", "color": "WHITE", "role": "NARR"},          # img·meme 없음 + 격식 의문
             {"text": "마지막", "color": "WHITE", "role": "NARR", "img": 2},       # PUNCH 없음
         ]}
    issues, _ = lint.lint(s, do_layout=False)
    ids = {i.rule for i in lint.rejects(issues)}
    assert {"title_punct", "comma", "h2_abstract", "card", "nonwhite_run", "formal", "enum", "punch"} <= ids
    fb = lint.feedback(issues)
    assert "분량" not in fb and "재작성 지시" in fb          # 분량 처방 자동 첨부 없음(아스트라 지적)


def test_prompt_block_and_checks_come_from_same_rules():
    block = lint.prompt_block()
    for r in lint.RULES:
        assert r.prompt in block


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_layout_never_changes_characters_and_stays_inside():
    s, _ = _script("leedonggun")            # 2줄 컷이 24/25인 편
    laid, fails = layout.layout_groups(s["groups"])
    assert not fails
    for g, o in zip(laid, s["groups"]):
        assert "".join(g["lines"]).replace(" ", "") == o["text"].replace(" ", "")
        assert 1 <= len(g["lines"]) <= 2
        for ln in g["lines"]:
            ok, info = layout.fits(g["color"], ln)
            assert ok, (ln, info)


# ── 끝까지: 가짜 LLM + 가짜 TTS + 진짜 렌더 ───────────────────────────────────────
def _fake_tts(text, out_path):
    dur = round(0.35 + 0.07 * len(text), 3)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-ar", "44100", "-ac", "2", out_path], check=True, stdin=subprocess.DEVNULL)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_pipeline_end_to_end_renders_and_reviews(tmp_path):
    s, src = _script("parksuhong")
    fake_llm = lambda _prompt: json.dumps(s, ensure_ascii=False)
    r = pipeline.run_all(str(tmp_path), source_text=src or "소재", llm=fake_llm, tts=_fake_tts)
    assert r["status"] == "ok", r
    job = pipeline.load(str(tmp_path))
    d = job["data"]
    assert d["script"]["attempts"] == 1
    assert len(d["timing"]["groups"]) == len(s["groups"])
    assert os.path.exists(d["render"]["mp4"])
    assert d["review"]["ok"], d["review"]
    # 재개: 이미 끝난 잡은 next_step이 None
    assert pipeline.next_step(str(tmp_path)) is None


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_pipeline_stops_with_reason_when_lint_rejects(tmp_path):
    bad = {"title": {"h1": "제목", "h2": "숫자 3개", "card": "한 문장"},
           "groups": [{"text": "쉼표가, 있다", "color": "WHITE", "role": "PUNCH", "img": 1}]}
    calls = []
    def llm(p):
        calls.append(p); return json.dumps(bad, ensure_ascii=False)
    r = pipeline.run_all(str(tmp_path), source_text="소재", llm=llm, tts=_fake_tts)
    assert r["status"] == "failed" and r["step"] == "script"
    assert "쉼표" in r["fail"]["fix"] or "','" in r["fail"]["fix"]
    assert len(calls) == spec.POLICY_MAX_REWRITES + 1          # 재작성 상한만큼만 돈다
    assert "재작성 지시" in calls[-1]                            # 반려 사유가 다음 프롬프트에 실렸다
