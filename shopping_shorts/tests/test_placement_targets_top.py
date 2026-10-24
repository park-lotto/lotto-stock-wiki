# -*- coding: utf-8 -*-
"""지시서 15(관제 263, 표준 §12-4) — 효과 밀도·말속도 상위 편 목표.

  · placement.place targets 모드: 업그레이드 판(targets 칸)은 꾸밈·효과음 개수를 상위 편 p75 쪽으로(상한 max) — 1차 판은 결과 그대로
  · 조용한 0발 금지(⑮): rules.sfx 없는 판 → 로그 ⚠ + check_place ×
  · script_audit tts_cps_spread: 편차 큰 대본 실패 + 다시 나누기 제안 / 고른 대본 통과
  · render_itssum.make_sentences(spread): 타입캐스트만 줄별 ±8%, 미나(고정 배속 1.35)는 그대로
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import placement as PL  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402


def _rows():
    """나레 16덩어리(7줄, 줄마다 key 있는 덩어리 하나 이상) + 원음 6덩어리 — 잇템로그 ep13 꼴(28초)."""
    out, t = [], 0.0
    plan = [("N1", "narr", ["연어로 만든 크림을|연어", "얼굴에 바르고", "경악한 외국인이 있다는데요?"]),
            ("O1", "orig", ["진짜야 연어래|연어", "뭐?"]),
            ("N2", "narr", ["분홍 알갱이마다|분홍", "성분이 들었다는데|성분"]),
            ("N3", "narr", ["얼굴에 올리고", "스르르 녹아 버렸어요|녹아"]),
            ("O2", "orig", ["어머 세상에!", "진짜 세상에!|세상에"]),
            ("N4", "narr", ["다른 외국인도", "소리부터 질렀는데|소리"]),
            ("O3", "orig", ["우와!", "이게 뭐야?|뭐야"]),
            ("N5", "narr", ["댓글 보니까", "한두 알이면 충분하다던데|한두 알"]),
            ("N6", "narr", ["버블티 펄 같다는|버블티", "사람도 있다고 하고"]),
            ("N7", "narr", ["아 나도 오늘 밤엔", "캡슐 딱 두 알만|두 알", "발라 봐야겠다"])]
    for line, sp, caps in plan:
        for j, c in enumerate(caps):
            text, _, key = c.partition("|")
            r = {"line": line, "j": j, "speaker": sp, "text": text, "t0": round(t, 3), "t1": round(t + 1.27, 3)}
            if key:
                r["key"] = key
            out.append(r)
            t += 1.27
    return out


def _deco(r):
    return r.get("enter") not in ("cut", "instant", "append", None) or bool(r.get("emph")) or bool(r.get("stickers"))


TG = {"fx_rate_narr": {"goal": 0.18, "cap": 0.231, "src": "시험"}, "fx_rate_orig": {"goal": 0.056, "cap": 0.111, "src": "시험"},
      "sfx_rate": {"goal": 0.051, "cap": 0.067, "src": "시험"}}


def test_no_sfx_rule_warns_and_check_fails():
    """사보타주 짝: 고치기 전 placement 는 rules.sfx 없는 판에서 '효과음 0발(판 규칙 sfx 없음)' 로그만 남기고 check_place ok=True(조용한 0발)."""
    st = copy.deepcopy(ST.load("잇템로그판"))
    del st["placement"]["rules"]["sfx"]
    p = PL.place(_rows(), st, "seed")
    assert p["sfx"] == []
    assert any(w.startswith("⚠ 효과음 0발") for w in p.get("warn") or []), p.get("warn")
    assert any(l.startswith("⚠ 효과음 0발") for l in p["log"])
    chk = PL.check_place(p, st)
    assert chk["ok"] is False and any("효과음 0발" in b for b in chk["bad"]), chk["bad"]
    # 벤치에 효과음이 정말 없으면 판에 0 을 적는다 → 경고 없음(없는 것도 스타일)
    st["placement"]["rules"]["sfx"] = {"max": 0, "why": "시험 — 벤치 0발"}
    p2 = PL.place(_rows(), st, "seed")
    assert not p2.get("warn") and p2["sfx"] == []


def test_first_pan_unchanged_and_v2_without_targets_equals_first():
    """1차 판(targets 없음) = 옛 동작: 목표 모드 칸이 안 생기고, v2 에서 목표 모드를 끄면 1차 판과 자막표·효과음·전환이 같다."""
    rows = _rows()
    a = PL.place(rows, ST.load("잇템로그판"), "ep13")
    b = PL.place(rows, ST.load("잇템로그판_v2"), "ep13", targets=False)
    assert "targets" not in a and not any("목표 밀도" in l for l in a["log"])
    for k in ("rows", "sfx", "transitions", "reference"):
        assert a[k] == b[k], k
    assert PL.density_targets(ST.load("잇템로그판")) is None


def test_targets_fill_density_to_goal_within_cap():
    st = ST.load("잇템로그판_v2")
    rows = _rows()
    p = PL.place(rows, st, "ep13", targets=TG)
    narr = [r for r in p["rows"] if r["speaker"] == "narr"]
    got = sum(_deco(r) for r in narr) / len(narr)
    assert abs(got - 0.18) <= 0.20 and got <= 0.231 + 1e-9, got
    assert sum(_deco(r) for r in narr) == 3                      # round(0.18×16)=3, 상한 floor(0.231×16)=3
    assert all(r["emph"][0]["word"] == r["key"] for r in narr if r.get("emph_by") == "targets")   # 종류 = 1차 그대로(강조 낱말 = 대본 key)
    assert narr[0].get("emph"), "역할 순서 훅 먼저"
    dur = rows[-1]["t1"]
    want, cap = PL._want(0.051, 0.067, dur)
    assert len(p["sfx"]) == want and (cap is None or len(p["sfx"]) <= cap)
    chk = PL.check_place(p, st)
    assert "targets" in chk["slots"] and not [b for b in chk["bad"] if "목표 밀도" in b], chk["bad"]
    # 1차로 돌리면 강조는 본보기 비율만(목표 모드 아님)
    a = PL.place(rows, ST.load("잇템로그판"), "ep13")
    assert sum(_deco(r) for r in a["rows"] if r["speaker"] == "narr") < 3


def test_targets_sfx_roles_rule_and_cap_check():
    """rules.sfx.roles(03→15 넘김) = 그 역할에만 · 목표 밖이면 check_place ×."""
    st = copy.deepcopy(ST.load("잇템로그판_v2"))
    st["placement"]["rules"]["sfx"]["roles"] = ["훅"]
    p = PL.place(_rows(), st, "ep13", targets=TG)
    assert p["sfx"] and all(e.get("role") in ("hook", None) for e in p["sfx"]), p["sfx"]
    bad = PL.check_place({**p, "targets": {"sfx_rate": {"goal": 0.051, "cap": 0.067, "ours": 0.5}}}, st)["bad"]
    assert any("목표 밀도 sfx_rate" in b for b in bad)


def test_density_targets_reads_top_file_same_ruler():
    """v2 목표 = 상위편_목표.json density(placement.py count 잇템로그판 --top · kal_analyze._stats — upgrade_table 과 같은 자)."""
    tg = PL.density_targets(ST.load("잇템로그판_v2"))
    p = ROOT / "channel/ititemlog/_kal/상위편_목표.json"
    D = json.loads(p.read_text(encoding="utf-8")).get("density")
    if not D:
        pytest.skip("상위편_목표.json density 없음 — count 잇템로그판 --top 전")
    assert tg["sfx_rate"]["goal"] == D["sfx_rate"]["p75"] and tg["fx_rate_narr"]["cap"] == D["fx_rate_narr"]["max"]
    assert "상위편_목표.json" in tg["sfx_rate"]["src"]


def test_sticker_kind_new_vocab():
    assert PL.sticker_kind("기타(노랑 물음표 + 동심원 그림 애니)") == "question"
    assert PL.sticker_kind("노랑 글자 라벨 '3600원'(검은 외곽)") == "yellow_label"
    assert PL.sticker_kind("기타(마우스 손가락 포인터 — 클릭 시늉)") == "cursor"
    assert PL.sticker_kind("주황 손그림 X(#f95d32)") == "hand_x"
    assert PL.sticker_kind("💎 다이아") == "gem"


def _script(caps_per_line):
    return {"lines": [{"id": f"N{i + 1}", "kind": "tts", "tts": " ".join(c) + ".", "caps": [{"text": x} for x in c]} for i, c in enumerate(caps_per_line)]}


def test_tts_cps_spread_uneven_fails_with_suggestion_even_passes():
    st = ST.load("잇템로그판")
    uneven = _script([["댓글 보니", "캡슐은 한두 알이면 충분하다던데"], ["다른 외국인", "처음 보고는 소리부터 질렀는데"],
                      ["분홍 알갱이", "연어에서 뽑은 성분이 들었다는데"]])
    ok, why = SA.rule_check({"kind": "tts_cps_spread", "max": 0.10}, uneven, st)
    assert ok is False and "제안" in why and "→" in why, why
    R = SA.cps_spread(uneven, {"max": 0.10}, st)
    assert R["suggest"] and all(s["cv_if"] < R["cv"] for s in R["suggest"])
    even = _script([["댓글 보니까 캡슐은", "한두 알이면 충분하다던데"], ["다른 외국인도 처음", "보고는 소리부터 질렀는데"],
                    ["분홍 알갱이마다 연어", "에서 뽑은 성분이 들었다"]])
    ok2, why2 = SA.rule_check({"kind": "tts_cps_spread", "max": 0.10}, even, st)
    assert ok2 is True, why2


def test_speech_rule_from_targets_only_on_upgrade_pan():
    assert SA.speech_rule(ST.load("잇템로그판")) is None
    r = SA.speech_rule(ST.load("잇템로그판_v2"))
    assert r and r["kind"] == "tts_cps_spread" and r["level"] in ("chunk", "line")


def test_fine_tempos_bounds():
    rates = [8.4, 7.3, 7.9, 6.4]
    base = [1.2 * 0.9001, 1.2, 1.2, min(1.2 * 1.0999, RI.TEMPO_MAX)]                     # 옛 ±10% 규칙 배속(빠른 줄 −10%·느린 줄 +10%, 상한 1.25)
    assert RI.fine_tempos(rates, 1.2, None, 7.5, base) is None                           # 1차 판(목표 없음) = 안 함
    assert RI.fine_tempos([7.5, 7.5, 7.6, 7.5], 1.2, 0.06, 7.5, [1.2] * 4) is None       # 이미 목표 이하 = 안 함
    t = RI.fine_tempos(rates, 1.2, 0.01, 7.5, base)
    assert t and all(min(b, 1.2 * 0.92) - 1e-4 <= x <= max(b, min(1.2 * 1.08, RI.TEMPO_MAX)) + 1e-4 for x, b in zip(t, base)), t   # 배속은 4자리 반올림
    assert t[0] <= base[0] + 1e-4, "옛 규칙이 이미 더 고친 줄은 덜 고치지 않는다(10-25 ep13 0.0571→0.0636 회귀)"
    est = lambda tls: [r * x / 1.2 for r, x in zip(rates, tls)]  # noqa: E731
    import statistics as S
    cv = lambda xs: S.pstdev(xs) / S.mean(xs)  # noqa: E731
    assert cv(est(t)) <= cv(est(base)) + 1e-9
    assert RI.spread_of(ST.load("잇템로그판")) is None and RI.spread_of(ST.load("키치잇판")) is None


def _fake_narr(tmp: Path) -> Path:
    """줄 3개 꼴 가짜 목소리(소리 0.9·1.6·0.8초 + 0.3초 쉼) — ffmpeg 로 만든다(합성 아님)."""
    p = tmp / "narr_full.wav"
    f = "sine=f=220:d={d},volume=0.5"
    parts = ";".join(f"{f.format(d=d)}[s{i}];anullsrc=r=48000:cl=mono,atrim=0:0.3[z{i}]" for i, d in enumerate((0.9, 1.6, 0.8)))
    cat = "".join(f"[s{i}][z{i}]" for i in range(3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", f"{parts};{cat}concat=n=6:v=0:a=1,aformat=sample_rates=48000:channel_layouts=mono[o]",
                    "-map", "[o]", str(p)], check=True)
    return p


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
@pytest.mark.parametrize("voice,fixed", [("kr-mina-expressive", True), ("tc_61130d6cf89dd58a4c13295d", False)])
def test_make_sentences_spread_mina_untouched_typecast_fine(tmp_path, voice, fixed):
    full = _fake_narr(tmp_path)
    S = {"voice": {"voice_id": voice}, "cps_target": 8.6,
         "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사."}, {"id": "N2", "kind": "tts", "tts": "가나다라마바사아자차카."},
                   {"id": "N3", "kind": "tts", "tts": "가나다라마바사아자."}],
         "tts_spans": {"N1": [0.0, 0.9], "N2": [1.2, 2.8], "N3": [3.1, 3.9]}}
    R0, R1 = tmp_path / "a", tmp_path / "b"
    R0.mkdir(); R1.mkdir()
    a, ta, _ = RI.make_sentences(S, full, R0, log=lambda *x: None)
    b, tb, _ = RI.make_sentences(S, full, R1, log=lambda *x: None, spread=0.01)
    fix = json.loads((R1 / "line_cps_fix.json").read_text(encoding="utf-8"))
    if fixed:
        assert ta == tb == 1.35 and [x["tempo"] for x in a] == [x["tempo"] for x in b], "미나 = 고정 배속 그대로"
        assert fix["applied"] is False and fix["fixed_voice"] is True
    else:
        assert fix["applied"] is True and fix["cv_after_est"] < fix["cv_before"], fix
        assert all(tb * 0.9 - 1e-4 <= x["tempo"] <= min(tb * 1.1, RI.TEMPO_MAX) + 1e-4 for x in b)      # 옛 ±10% 안 · 새로 더한 몫은 ±8% 안(fine_tempos)
