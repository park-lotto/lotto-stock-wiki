# -*- coding: utf-8 -*-
"""얜샷템 한 명령 파이프라인(tools/calcopy/yanshot) 단계 함수 시험 — 정답은 검수 통과한 정본 편 실제 자료로 고정 (관제 097, 2026-10-17).

정본: channel/yanshottem/장윤정_덴마크수건/build_plan.py ORIG · channel/annapick/1편_한고은채소통/make_plan.py BLOCKS.
자막 지문 픽스처 = tools/calcopy/yanshot/fixtures/*.vtt(벤치·원본 자동자막). 무음 경계 시험은 원본 영상이 있는 PC 에서만(없으면 건너뜀).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.yanshot import plan as pl, render as rd, script as sc, trace as tr  # noqa: E402
from tools.calcopy.yanshot.common import vtt_words  # noqa: E402

F = ROOT / "tools/calcopy/yanshot/fixtures"
JYJ_SRC_MP4 = Path("C:/숏템_칼카피/yanshottem/장윤정_덴마크수건/src/jyj_XzCEZtLDV-A.mp4")
HGE_SRC_MP4 = Path("C:/숏템_칼카피/annapick/1편_한고은채소통/src/hge_LcQv9yOh3Wc.mp4")
TOL = 0.3


def _words(name):
    return vtt_words(F / name)


# ── ② trace: 원본 확정(지문) ───────────────────────────────────────
@pytest.mark.parametrize("bench,src,decoy", [
    ("jyj_bench_ySJLtV0K1PY.vtt", "jyj_src_XzCEZtLDV-A.vtt", "hge_src_LcQv9yOh3Wc.vtt"),
    ("hge_bench_itYwQVyuCcc.vtt", "hge_src_LcQv9yOh3Wc.vtt", "jyj_src_XzCEZtLDV-A.vtt"),
])
def test_fingerprint_picks_true_source(bench, src, decoy):
    bw = _words(bench)
    real = tr.score(tr.fingerprint(bw, _words(src)))
    fake = tr.score(tr.fingerprint(bw, _words(decoy)))
    assert real >= tr.CONFIRM_CHARS and real >= 5 * max(fake, 1), (real, fake)


def _blocks(bench, src, dur, kws):
    bw, sw = _words(bench), _words(src)
    return tr.word_spans(sw, tr.fingerprint(bw, sw), dur - tr.narr_est(dur), kws, bw)


def test_jyj_blocks_hit_canonical_sentences():
    """정본 장윤정 O1('저는 수건 미치는 애거든요' 224.80~)·O3('확실히 짱짱하다/도톰하다' 261.95~265.45) 가 원음 블록으로 나온다 + 훅이 맨 앞."""
    bl = _blocks("jyj_bench_ySJLtV0K1PY.vtt", "jyj_src_XzCEZtLDV-A.vtt", 24.57, ["수건"])
    assert bl[0]["said"].startswith("저는 수건 미치는"), bl[0]["said"]
    assert abs(bl[0]["t0"] - 224.80) <= 0.3
    o3 = next(b for b in bl if "짱짱" in b["said"])
    assert abs(o3["t0"] - 261.95) <= 0.3 and abs(o3["t1"] - 265.45) <= 0.35
    assert all(">>" not in b["said"] for b in bl)


def test_hge_blocks_hit_canonical_sentences():
    """정본 한고은 H(780.62~783.72 '정말 난 너무 놀랬어 … 너무 신선해요')·O2(763.30~771.90) — 벤치가 지문 앞에 쓴 원음까지 앞으로 넓힌다."""
    bl = _blocks("hge_bench_itYwQVyuCcc.vtt", "hge_src_LcQv9yOh3Wc.vtt", 25.0, ["채소", "보관"])
    assert bl[0]["said"].startswith("정말 난 너무"), bl[0]["said"]
    assert abs(bl[0]["t0"] - 780.62) <= TOL
    o2 = next(b for b in bl if b["said"].startswith("이렇게 갑자기"))
    assert abs(o2["t0"] - 763.30) <= TOL


# ── ② trace: 무음 경계(원본 소리) — 정본 구간 ±0.3초 ─────────────────
needs_jyj = pytest.mark.skipif(not JYJ_SRC_MP4.exists(), reason="장윤정 원본 영상 없음")
needs_hge = pytest.mark.skipif(not HGE_SRC_MP4.exists(), reason="한고은 원본 영상 없음")


def _close(spans, want):
    assert len(spans) == len(want), (spans, want)
    for (a, b), (x, y) in zip(spans, want):
        assert abs(a - x) <= TOL and abs(b - y) <= TOL, (spans, want)


@needs_jyj
def test_snap_jyj_o1_cuts_pause():
    """정본 O1 [[224.80,225.98],[226.40,…]] — 225.98~226.40 쉼을 잘라 낸다(끝은 정본이 다음 문장까지 더해 231.00 이라 첫 문장 끝 227.44 로 잰다)."""
    sp = tr.snap_spans(JYJ_SRC_MP4, 224.959, 227.439)
    _close(sp, [[224.80, 225.98], [226.40, 227.44]])


@needs_jyj
def test_snap_jyj_o3_exact():
    _close(tr.snap_spans(JYJ_SRC_MP4, 262.12, 265.759), [[261.95, 263.02], [264.56, 265.45]])


@needs_hge
def test_snap_hge_hook_and_o2():
    _close(tr.snap_spans(HGE_SRC_MP4, 780.76, 784.04), [[780.62, 783.72]])
    _close(tr.snap_spans(HGE_SRC_MP4, 763.36, 772.24), [[763.30, 771.90]])


def test_turn_piece_stops_at_speaker_change():
    words = [(0.0, "어"), (0.3, "좋다."), (1.0, ">>"), (1.0, "왜"), (1.2, "이렇게"), (1.5, "작은"), (1.8, "거야?")]
    a, b = tr._turn_piece(words, 0, 6)
    assert (a, b) == (3, 6)


def test_coverage_merged_or_split():
    said = "저는 수건 미치는 애거든요"
    assert tr.coverage(said, "저는 수건 미치는 애거든요 그리고 다른 말") >= 0.95
    assert tr.coverage(said, "백 오십만 원 왔다 보시면") < tr.ASR_COVER


# ── ③ script 검사 ─────────────────────────────────────────────────
def _draft(n1="장윤정이 덴마크에서 물어물어 사 왔다는 테클라 수건이라는데", n2="매장이 없다 보니 비슷한 디자인까지 많이 나온다는 수건이라네요"):
    return {"title": ["수건에 미친 장윤정이", "덴마크서 사 온 수건"],
            "N1": {"text": n1.replace("덴마크에서 ", "덴마크에서, "), "tts": n1, "facts": ["f1"]},
            "N2": {"text": n2.replace("보니 ", "보니, "), "tts": n2, "facts": ["f2"]},
            "facts": {"f1": {"text": "제가 덴마크에서 왔거든요 여기를 물어 물어 사 왔어요 테클라", "at": "0:10"},
                      "f2": {"text": "매장은 없고 이런 디자인으로 아주 많이 나와요", "at": "4:08"}}}


def test_script_checks_pass_canonical():
    B = {"person": "장윤정"}
    assert sc.checks(_draft(), B, "장윤정이 덴마크까지 가서 쟁여운 수건이라는데", 40, 60) == {}


@pytest.mark.parametrize("n1,why", [
    ("장윤정이 덴마크에서 물어물어 사 왔다는 테클라 수건이에요", "끝 어미"),
    ("장윤정이 덴마크에서 1kg 사 왔다는 테클라 수건이라는데", "숫자·영문"),
    ("덴마크에서 장윤정이 물어물어 사 왔다는 테클라 수건이라는데", "인물 이름"),
    ("장윤정이 덴마크까지 가서 쟁여운 역대급 테클라 수건이라는데", "베낌"),
])
def test_script_checks_catch(n1, why):
    bad = sc.checks(_draft(n1=n1), {"person": "장윤정"}, "장윤정이 덴마크까지 가서 쟁여운 수건이라는데", 40, 60)
    assert any(why in x for x in bad.get("N1", [])), bad


def test_caps_of_max13():
    assert all(len(c.replace(" ", "")) <= 13 for c in sc.caps_of("글씨가 작은 메뉴판을 볼 때, 줄을 쭉 늘려서 아주 편하게 확인한다네요"))


# ── ④ plan 규칙 ───────────────────────────────────────────────────
def _cut(i, ss, dur, who="main", sync=False):
    return {"i": i, "ss": ss, "dur": dur, "who": who, "sync": sync}


def test_rule_check_reuse_and_rewind():
    assert pl.rule_check([_cut(0, 100, 1.5), _cut(1, 200, 1.5), _cut(2, 101.5, 1.6)], 1.5)       # B13 ±3초 재사용
    assert any("되감김" in v for v in pl.rule_check([_cut(0, 100, 1.5), _cut(1, 100.8, 1.6)], 1.5))
    assert pl.rule_check([_cut(0, 100, 1.5), _cut(1, 102.0, 1.6), _cut(2, 300, 1.6)], 1.5) == []   # 바로 다음 컷 앞으로 이어짐은 허용
    assert any("끝 컷" in v for v in pl.rule_check([_cut(0, 100, 1.5), _cut(1, 300, 1.0)], 1.5))


def test_crop_avoids_overlay_text():
    c = pl.crop_for({"cx": 0.5, "text": [[0.55, 0.30, 0.75, 0.40]]})      # 오른쪽 위 글자 → 왼쪽으로 비켜 자른다
    x, y, s, _ = c
    assert x + s <= 0.55 * 1920 - 12 and s >= pl.CROP_MIN, c
    assert pl.crop_for({"cx": 0.1, "text": []})[0] == 0


def test_cut_out_keeps_tail_after_sync():
    assert pl.cut_out([(1036.84, 1041.37)], [(1037.01, 1038.32)]) == [(1036.84, 1037.01), (1038.32, 1041.37)]


# ── ⑤ make: 줄별 배속 ─────────────────────────────────────────────
def test_tempo_plan_even_and_bounded():
    tp = rd.tempo_plan([25, 26], [4.7, 5.27])
    mean = (4.7 + 5.27) / (51 / 8.4)
    assert all(abs(x / mean - 1) <= 0.1 + 1e-6 for x in tp)
    assert [round(c / (t / f), 1) for c, t, f in zip([25, 26], [4.7, 5.27], tp)] == [8.4, 8.4]
    tp2 = rd.tempo_plan([10, 30], [3.0, 3.0])            # 한 줄만 극단 → ±10% 로 묶임
    m2 = 6.0 / (40 / 8.4)
    assert all(abs(x / m2 - 1) <= 0.1 + 1e-6 for x in tp2)
