# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 파이프라인(tools/calcopy/hybrid) — 정답은 검수 통과한 장윤정 테클라 편 실제 자료로 고정 (관제 097, 2026-10-18).

실제 파일(채널 문서·C:/숏템_칼카피)이 없는 PC 에선 그 시험만 건너뛴다. 렌더·서버 호출은 하지 않는다(증명 렌더 결과물 render_info.json 만 읽는다).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import checks, legacy_import, name_check, render_itssum as RI, render_jaemi as RJ, thumb  # noqa: E402
from tools.calcopy.hybrid.common import jload, nchar  # noqa: E402

DOC = ROOT / "channel/yanshottem"
TEST = Path("C:/숏템_칼카피/yanshottem/_hybrid_pipeline_test/장윤정")
OLD_ITSSUM_MD5 = "f20e40b533452a959605eeb118008bcb"      # 옛 B표.md 의 완성본 MD5


def _need(*ps):
    for p in ps:
        if not Path(p).exists():
            pytest.skip(f"표본 없음: {p}")


# ── 잇썸 시간표: 옛 편(장윤정) 대본·재료 그대로 → 옛 B표와 같은 줄 시각 ──────────────────
def test_itssum_timeline_matches_old_b_table(tmp_path):
    """증명 때 옮겨 둔 v2 문서(채널 폴더 원본은 다른 에이전트가 고치는 중이라 고정본을 쓴다)."""
    _need(TEST / "doc/잇썸홈판/대본.json")
    S, M = jload(TEST / "doc/잇썸홈판/대본.json"), jload(TEST / "doc/잇썸홈판/재료.json")
    _need(TEST / "잇썸홈판/render/render_info.json")
    sent = {x["id"]: x["dur"] for x in jload(TEST / "잇썸홈판/render/render_info.json")["sentences"]}   # 증명 렌더의 문장 길이(초)
    T = RI.timeline(S, M, sent)
    assert T["h_id"] == "H" and T["b_ids"] == ["B1", "B2", "B3", "B4", "B5"]
    assert abs(T["lines"]["O"][0] - 3.27) < 0.01 and abs(T["a_end"] - 11.01) < 0.01     # 옛 B표: 원음 3.27~11.01
    assert len(T["opos"]) == 4 and len(T["a_shots"]) == 8 and len(T["cuts"]) == 8
    assert all(c["over"] == 0 for c in T["cuts"])
    assert [round(a["t0"], 2) for a in T["a_shots"][:2]] == [0.0, round(T["o0"] / 2, 2)]


def test_itssum_a_shot_longer_than_source_shot_stops(tmp_path):
    _need(DOC / "하이브리드_장윤정/잇썸홈판/대본.json")
    S, M = legacy_import.itssum(DOC / "하이브리드_장윤정/잇썸홈판", tmp_path / "doc", "장윤정")
    M["A"]["O"][0]["max"] = 0.5                                   # 1.18초 컷에 샷 경계 0.5초
    with pytest.raises(Exception, match="원본 샷보다 길다"):
        RI.timeline(S, M, {"H": 3.07, "B1": 3.38, "B2": 3.75, "B3": 2.29, "B4": 3.85, "B5": 3.19})


@pytest.mark.parametrize("celeb", ["함익병", "박세리", "최은경"])
def test_itssum_legacy_forms_convert_and_timeline(tmp_path, celeb):
    """네 꼴(한 줄기·pieces·H/O·O1/O2) 전부 canonical 로 바뀌고 시간표가 선다."""
    d = DOC / f"하이브리드_{celeb}/잇썸홈판"
    _need(d / "대본.json", d / "재료.json")
    S, M = legacy_import.itssum(d, tmp_path / celeb, celeb)
    assert M["A"]["H"] and M["A"]["O"]
    sent = {l["id"]: nchar(l["tts"]) / S["cps_target"] for l in RI.tts_lines(S)}
    T = RI.timeline(S, M, sent)
    assert T["a_end"] > T["o0"] > 0 and T["end"] > T["a_end"]
    assert len(T["cuts"]) == len(M["B"])


# ── 재미썸: make.py 상수 → v2, 시간표(어림) ───────────────────────────────────────
def test_jaemi_legacy_import_and_plan_timeline(tmp_path):
    d = DOC / "하이브리드_장윤정/재미썸홈판"
    _need(d / "make.py")
    S, M = legacy_import.jaemi(d, tmp_path / "doc", "장윤정")
    assert len(S["lines"]) == 8 and len(S["pieces"]) == 21 and S["tts_tempo"] == {"all": 1.12, "last": 1.01}
    assert len(M["A"]) == 6 and len(M["B"]) == 9 and M["F1"][1]["from_piece"] == 2
    RJ.check_pieces(S)
    assert RJ.piece_lines(S)[:4] == [0, 0, 0, 1]
    T = RJ.timeline(S, M, None, None, est_cps=S["cps_target"])
    assert T["nF1"] == 3 and abs(T["o_len"] - 7.74) < 0.01 and len(T["b_groups"]) == 9
    assert RJ.punct_marks(S) == [",", ".", ",", ".", ".", ".", ".", ","]


def test_jaemi_auto_punct_matches_hand_values():
    """자동 문장부호 자리 어림이 손으로 잰 PUNCT_AT(장윤정)와 0.2초 안에서 맞는다 — narr_pre.wav 는 증명 렌더가 남긴 것."""
    pre = TEST / "재미썸홈판/render/narr_pre.wav"
    _need(pre, TEST / "doc/재미썸홈판/대본.json")
    S = jload(TEST / "doc/재미썸홈판/대본.json")
    from tools.calcopy.hybrid.common import silences
    auto = RJ.auto_punct_at(S, pre, silences(pre, "-40dB", 0.08))
    hand = S["punct_at"]
    assert [k for k, _ in auto] == [k for k, _ in hand]
    diff = [abs(a - b) for (_, a), (_, b) in zip(auto, hand)]
    assert max(diff) < 0.2, diff


# ── 증명 렌더 결과 = 옛 B표 ───────────────────────────────────────────────
def test_proof_itssum_final_is_bit_identical_to_old():
    f = TEST / "잇썸홈판/render/final.mp4"
    _need(f)
    from tools.calcopy.hybrid.common import md5
    assert md5(f) == OLD_ITSSUM_MD5


def test_proof_jaemi_report_matches_old_b_table():
    p = TEST / "재미썸홈판/render/render_info.json"
    _need(p)
    rep = jload(p)["report"]
    assert abs(rep["dur"] - 27.2) <= 0.15 and abs(rep["lufs"] - (-14.1)) <= 0.3
    assert rep["cps_out"] == 8.38 and rep["b_cut_median"] == 1.8 and rep["end_cut"] == 2.9 and rep["sfx"] == 8
    assert rep["line_rates"] == [8.54, 8.58, 8.81, 7.23, 8.29, 8.32, 8.3, 9.07]


# ── 검사 규칙 단위 ─────────────────────────────────────────────────────────
def test_reuse_rule_flags_overlap_but_not_forward_continuation():
    a = {"src": "x.mp4", "ss": 224.8, "dur": 1.18, "t0": 3.27, "t1": 4.45, "line": "O"}
    b = {"src": "x.mp4", "ss": 226.4, "dur": 2.8, "t0": 4.45, "t1": 7.25, "line": "O"}       # 이어 붙인 원음 조각(앞으로만)
    c = {"src": "x.mp4", "ss": 225.0, "dur": 1.0, "t0": 20.0, "t1": 21.0, "line": "B4"}      # 나중에 같은 장면 재사용
    assert checks.reuse_violations([a, b]) == []
    assert len(checks.reuse_violations([a, b, c])) >= 1


def test_aba_rule():
    seq = [{"src": "a.mp4", "t0": 0}, {"src": "b.mp4", "t0": 1}, {"src": "a.mp4", "t0": 2}]
    assert checks.aba_violations(seq)
    assert not checks.aba_violations(seq[:2] + [{"src": "c.mp4", "t0": 2}])


def test_name_dict_apply_and_pick():
    assert name_check.apply("최은경 씨가 자라에서 산 로퍼인데요.", "최은경") == "최, 은경 씨가 자라에서 산 로퍼인데요."
    assert name_check.apply("장윤정 씨가", "장윤정") == "장윤정 씨가"
    res = [{"cand": "최은경", "texts": ["최화정이 산", "최영경이"]}, {"cand": "최, 은경", "texts": ["최은경이 산", "최은경이"]}]
    assert name_check.pick("최은경", res)["cand"] == "최, 은경"
    assert name_check.pick("최은경", res[:1]) is None


def test_face_judge_rules():
    ok, why, _ = thumb.judge([], 1080, 1080)
    assert not ok and "0개" in why
    big = {"x": 400, "y": 300, "w": 200, "h": 260, "conf": 0.95, "lm": [(450, 380), (550, 380), (500, 440), (460, 500), (540, 500)]}
    assert thumb.judge([big], 1080, 1080)[0]
    small = dict(big, h=150, w=120)
    assert not thumb.judge([small], 1080, 1080)[0]
    side = dict(big, x=0)
    assert not thumb.judge([side], 1080, 1080)[0]


def test_face_check_rejects_product_start_and_passes_face_frame():
    """옛 잇썸홈판(제품 컷 시작) 0초는 × — 사장님 10-18 규칙. 원음 구간 프레임은 얼굴 ○."""
    f = TEST / "잇썸홈판/render/final.mp4"
    _need(f, thumb.MODEL)
    r = thumb.face_check(f, (0, 420, 1080, 1080), None, log=lambda *a: None)
    assert not r["ok"] and r["frames"][0]["why"].startswith("얼굴 0")
    det = thumb._detector()
    im = thumb._frame(f, 10.5, (0, 420, 1080, 1080))
    s, info = thumb.score(det, im)
    assert s > 0 and info["h_frac"] >= thumb.FACE_MIN_FRAC_THUMB
