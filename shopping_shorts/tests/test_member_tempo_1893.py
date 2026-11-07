# -*- coding: utf-8 -*-
"""#1893 김만기 — 회원이 말 빠르기 1.05 를 정했는데(팩 tts.tempo) 렌더가 판 cps_target 8.6 에 맞춰 atempo 1.2288 을 더 걸었다.
같은 판단 두 벌(회원 tempo vs 판 cps_target) → 회원이 정했으면 그 빠르기, 판 맞춤은 건너뛰고 길이는 경고만(사장님 11-02 '회원 요청이 판·검사를 이긴다').

  · 판단 주인 styles.member_tempo — 회원이 바꾼 칸(팩 member.tts.tempo)만, 프리셋 기본값(팩 1)은 아니다
  · render_itssum.member_voice — 렌더·캐시 검사가 같이 불러 S['member_tempo'] 로 make_sentences 에 알린다
  · make_sentences — 타입캐스트(합성이 빠르기를 넣음) = atempo 1.0 · 미나(1.0 으로 받음) = 회원 배속 그대로 · 없으면 옛 동작
  · 길이 관문 ⑧ — 회원 빠르기 편은 권고(soften 이 비운다)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402

TC, MINA = "tc_61130d6cf89dd58a4c13295d", "kr-mina-expressive"


def _pack(tmp: Path, monkeypatch, member: dict) -> None:
    f = tmp / "pack.json"
    f.write_text(json.dumps({"1": {"tts": {"tempo": 1.36}}, "member": member}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(f))


def test_member_tempo_only_member_field(tmp_path, monkeypatch):
    _pack(tmp_path, monkeypatch, {"tts": {"tempo": 1.05}})
    assert ST.member_tempo(ST.load("잇템로그판")) == 1.05
    _pack(tmp_path, monkeypatch, {"tts": {"voice_id": TC}})          # 목소리만 고름 · 빠르기는 프리셋 기본값(팩 1) = 회원이 정한 것 아님
    assert ST.member_tempo(ST.load("잇템로그판")) is None


def test_member_voice_marks_script(tmp_path, monkeypatch):
    _pack(tmp_path, monkeypatch, {"tts": {"voice_id": TC, "tempo": 1.05}})
    S = {"voice": {"voice_id": "tc_old"}, "cps_target": 8.6}
    RI.member_voice(S, ST.load("잇템로그판"))
    assert S["voice"] == {"voice_id": TC, "tempo": 1.05} and S["member_tempo"] == 1.05


def _fake_narr(tmp: Path) -> Path:
    p = tmp / "narr_full.wav"
    f = "sine=f=220:d={d},volume=0.5"
    parts = ";".join(f"{f.format(d=d)}[s{i}];anullsrc=r=48000:cl=mono,atrim=0:0.3[z{i}]" for i, d in enumerate((0.9, 1.6, 0.8)))
    cat = "".join(f"[s{i}][z{i}]" for i in range(3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", f"{parts};{cat}concat=n=6:v=0:a=1,aformat=sample_rates=48000:channel_layouts=mono[o]",
                    "-map", "[o]", str(p)], check=True)
    return p


def _S(voice: str, **kw) -> dict:
    return {"voice": {"voice_id": voice}, "cps_target": 10.0,
            "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사."}, {"id": "N2", "kind": "tts", "tts": "가나다라마바사아자차카."},
                      {"id": "N3", "kind": "tts", "tts": "가나다라마바사아자."}],
            "tts_spans": {"N1": [0.0, 0.9], "N2": [1.2, 2.8], "N3": [3.1, 3.9]}, **kw}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
@pytest.mark.parametrize("voice,member,want", [
    (TC, 1.05, 1.0),        # 타입캐스트는 합성에 1.05 가 이미 들어간다 — 더 걸지 않는다(옛: 판 10자/초 맞춤)
    (MINA, 1.1, 1.1),       # 미나는 1.0 으로 받는다 — 회원 배속 그대로(옛: 서비스 1.35)
])
def test_make_sentences_member_tempo_wins(tmp_path, voice, member, want):
    full = _fake_narr(tmp_path)
    sent, tempo, _ = RI.make_sentences(_S(voice, member_tempo=member), full, tmp_path, log=lambda *x: None)
    assert tempo == want
    assert all(want * 0.9 - 1e-4 <= s["tempo"] <= want * 1.1 + 1e-4 for s in sent), [s["tempo"] for s in sent]   # 줄 고르기(±10%)만 남는다


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_make_sentences_without_member_tempo_unchanged(tmp_path):
    full = _fake_narr(tmp_path)
    _, t_tc, _ = RI.make_sentences(_S(TC), full, tmp_path, log=lambda *x: None)
    _, t_mina, _ = RI.make_sentences(_S(MINA), full, tmp_path, log=lambda *x: None)
    assert t_tc > 1.1 and t_mina == 1.35       # 판 cps_target 맞춤 · 미나 고정 배속 그대로


def test_length_gate_advisory_when_member_tempo(tmp_path, monkeypatch):
    T = {"end": 40.0}
    _pack(tmp_path, monkeypatch, {"tts": {"tempo": 1.05}})
    st = ST.load("잇템로그판")
    g = [(RB.length_gate_name(st), RB.plan_length_gate(T, st, True))]
    assert g[0][1], "길이는 여전히 잰다(경고로 남긴다)"
    assert RB.soften(g, lambda *x: None) == [(g[0][0], [])]
    _pack(tmp_path, monkeypatch, {})
    st = ST.load("잇템로그판")
    g = [(RB.length_gate_name(st), RB.plan_length_gate(T, st, True))]
    assert RB.soften(g, lambda *x: None)[0][1], "회원이 안 정했으면 길이는 그대로 막는다"
