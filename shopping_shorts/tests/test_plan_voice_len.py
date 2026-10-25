"""관문 ⑧(G-3) — 계획 컷 길이를 어림이 아니라 진짜 목소리(TTS) 길이로.

주인: 목소리 길이 = render_bench.voice_plan(계획·렌더 공용) · 길이 판정 = render_bench.plan_length_gate.
표본: fixtures/plan_voice_len.json — 이미 만든 편 12개의 줄 캐시로 잰 어림/진짜/완성본 길이(scratchpad g8/measure.py, 합성 막고 복사본에서).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402

FX = json.loads((Path(__file__).parent / "fixtures" / "plan_voice_len.json").read_text(encoding="utf-8"))
ROWS = [r for r in FX["rows"] if "skip" not in r]
ST = {"name": "t", "length": {"min": 26, "max": 31}, "cps_target": 7.0, "timing": {"tail": 0.35}, "voice": {"voice_id": "v"}}


def _doc(tmp_path):
    d = tmp_path / "doc"
    d.mkdir(parents=True)
    S = {"slug": "x", "voice": {"voice_id": "v"}, "cps_target": 7.0,
         "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사.", "caps": ["가나다라마바사"]},
                   {"id": "N2", "kind": "tts", "tts": "아자차카.", "caps": ["아자차카"]}]}
    (d / "대본.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
    (d / "재료.json").write_text(json.dumps({"cand_dir": str(tmp_path), "cuts": {"N1": [{"src": "a.mp4", "ss": 0, "no_snap": True}], "N2": [{"src": "a.mp4", "ss": 5, "no_snap": True}]}}), encoding="utf-8")
    return d


def _stub(monkeypatch, durs, called):
    """합성·받아쓰기·쉼 맞춤을 가짜로(옛 코드에도 있는 이름만 바꾼다 — 옛 코드에서 이 시험이 '어림'으로 실패하는지 보려고)."""
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.hybrid import thumb_rule as TR
    monkeypatch.setattr(STY, "load", lambda name: dict(ST))
    monkeypatch.setattr(RB, "_voice_gate_text", lambda S: None)
    monkeypatch.setattr(RB, "_voice_gate_audio", lambda S, sent, R, log=print: None)

    def tbl(S, R, log=print):
        called.append("tts")
        return R / "narr_full.mp3", None
    monkeypatch.setattr(RB, "tts_by_line", tbl)
    monkeypatch.setattr(RI, "make_sentences", lambda S, full, R, log=print, align=None, spread=None:
                        ([{"id": k, "dur": v, "raw": [0, v], "tempo": 1.0, "wav": str(R / f"s_{k}.wav")} for k, v in durs.items()], 1.0, []))
    monkeypatch.setattr(RB, "fit_voice", lambda S, st, sent, align, log=print: sent)
    monkeypatch.setattr(RB, "plan_rows", lambda S, T, st, locate=None: {"log": "", "transitions": []})
    monkeypatch.setattr(RB, "transitions_of", lambda T, st, placed, log=None: [])
    for name in ("cut_boundary_gate", "cut_content_gate", "cut_length_gate", "cut_still_gate"):
        monkeypatch.setattr(RB, name, lambda *a, **k: [])
    monkeypatch.setattr(TR, "card_text_gate", lambda doc: [])
    monkeypatch.setattr(TR, "card_face_gate", lambda *a, **k: [])


def test_plan_uses_real_voice_length_by_default(monkeypatch, tmp_path):
    """--plan(plan_only) 기본 = 진짜 목소리. 옛 코드(tts 기본 False)는 글자÷cps 어림(N1 = 7자/7 = 1.0초)으로 계획해 실패한다."""
    called = []
    _stub(monkeypatch, {"N1": 12.0, "N2": 14.0}, called)
    d = _doc(tmp_path)
    res = RB.render("t", d, tmp_path / "w", plan_only=True, log=lambda *a: None)
    L = res["timeline"]["lines"]
    assert called == ["tts"]
    assert round(L["N1"][1] - L["N1"][0], 3) == 12.0 and round(L["N2"][1] - L["N2"][0], 3) == 14.0
    assert res["length"]["measured"] is True and res["length"]["ok"] is True


def test_plan_stops_on_length_out_of_range(monkeypatch, tmp_path):
    """진짜 목소리 길이가 판 length 밖이면 계획에서 멈춘다(옛 코드: 계획은 length.ok 만 적고 통과 → 렌더 뒤 bench_check 에서야 ×)."""
    _stub(monkeypatch, {"N1": 16.0, "N2": 16.0}, [])
    with pytest.raises(RB.StageError, match="길이"):
        RB.render("t", _doc(tmp_path), tmp_path / "w", plan_only=True, log=lambda *a: None)
    res = RB.render("t", _doc(tmp_path / "b"), tmp_path / "w2", plan_only=True, log=lambda *a: None, report=True)   # 회원 c_plan = 돌려받기
    assert res["length"]["ok"] is False


def test_guess_mode_skips_tts_and_length_gate(monkeypatch, tmp_path):
    """--guess = 어림(합성 안 함) · 길이 관문 안 봄(어림은 짧게 나와 거짓 걸림)."""
    called = []
    _stub(monkeypatch, {"N1": 12.0, "N2": 14.0}, called)
    res = RB.render("t", _doc(tmp_path), tmp_path / "w", plan_only=True, tts=False, log=lambda *a: None)
    assert called == [] and res["length"]["measured"] is False


def test_length_gate_real_vs_guess_on_made_episodes():
    """이미 만든 편: 진짜 목소리 길이는 전부 판 범위 안(관문 통과) · 어림은 늘 짧고(0.1~3.4초) 5편을 거짓으로 '짧다'."""
    assert len(ROWS) == 12
    real_bad = [r["doc"] for r in ROWS if RB.plan_length_gate({"end": r["real_end"]}, {"length": {"min": r["len"][0], "max": r["len"][1]}}, True)]
    est_bad = [r["doc"] for r in ROWS if RB.plan_length_gate({"end": r["est_end"]}, {"length": {"min": r["len"][0], "max": r["len"][1]}}, True)]
    assert real_bad == []
    assert len(est_bad) == 5
    assert all(r["real_end"] > r["est_end"] for r in ROWS)
    assert RB.plan_length_gate({"end": 23.8}, {"length": {"min": 26, "max": 31}}, False) == []   # 어림이면 판정 안 함


def test_same_engine_plan_equals_final():
    """쉼 맞춤(fit_voice) 뒤 같은 엔진으로 렌더한 편은 계획(진짜 목소리) 길이 = 완성본 길이(프레임 단위)."""
    same = [r for r in ROWS if r["same_engine"]]
    assert same and all(abs(r["real_end"] - r["final"]) < 1 / 30 for r in same)


def test_completed_render_over_range_would_stop():
    """옛 렌더 ep08 blurtest 완성본 32.4초(판 26~31) — 렌더 전 길이 관문이 있었다면 멈췄다."""
    assert RB.plan_length_gate({"end": 32.4}, {"name": "잇템로그판", "length": {"min": 26, "max": 31}}, True)
