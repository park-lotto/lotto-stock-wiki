# -*- coding: utf-8 -*-
"""판 리듬 4칸(관제263 10-25 페이블 눈검수 E1·E2·E3·E4) — 판 칸을 렌더·배치·관문·카드가 따르는가.
주인: 읽기 styles.rhythm · 컷 나눔 render_bench.rhythm_cuts · 그림 비중 render_bench.photo_share/photo_gate · 꾸밈 없음 placement.plain_step ·
동작 컷 material_fit.action_order · 재현 cut.median kal_analyze.match_table."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import styles as ST  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import placement as PL  # noqa: E402
from tools.calcopy.hybrid import material_fit as MF  # noqa: E402

R = {"cut_median": {"v": 1.15, "why": "x"}, "hook_cuts_3s": {"min": 2, "why": "x"}, "plain_share": {"v": 0.2, "tol": 0.1, "why": "x"},
     "photo_share_max": {"v": 0.16, "why": "x"}}


def _cuts():
    return [{"line": "N1", "src": "a.mp4", "ss": 4.5, "crop": [400, 0, 800, 800], "t0": 0.0, "kind": "tts"},
            {"line": "O1", "src": "a.mp4", "ss": 23.2, "crop": [600, 0, 800, 800], "t0": 3.6, "kind": "orig"},
            {"line": "N2", "src": "p.jpg", "ss": 0, "crop": [0, 0, 800, 800], "t0": 5.3, "kind": "tts"}]


def test_rhythm_reader_and_missing():
    assert set(ST.rhythm({"rhythm": R})) == set(ST.RHYTHM_KEYS)
    assert ST.rhythm_missing({"rhythm": {"cut_median": {"v": 1.0}}}) == list(ST.RHYTHM_KEYS)      # why 없으면 없는 칸
    assert ST.rhythm_missing(ST.load("키치잇판")) == []


def test_rhythm_gate_counts_real_cuts_only():
    """판 cut_median·hook_cuts_3s = 렌더 전 관문(rhythm_gate). 같은 샷 이어 붙이기는 컷이 아니라(완성본 컷 감지가 못 봄 — 10-25 박정수 v2 실측)
    진짜 컷(다른 파일·그림·다른 원본 장면)만 센다. 긴 화면이면 멈춤 메시지."""
    T = {"cuts": [{**c, "t1": t1} for c, t1 in zip(_cuts(), (3.6, 5.3, 9.0))], "end": 9.0}
    bad = RB.rhythm_gate(T, {"rhythm": R}, None)
    assert len(bad) == 2 and "N1" in bad[0] and "훅" in bad[1]
    many = [{"line": f"N{k}", "src": f"s{k}.mp4", "ss": 1.0, "t0": round(1.1 * k, 2)} for k in range(9)]
    T2 = {"cuts": [{**c, "t1": many[k + 1]["t0"] if k + 1 < len(many) else 9.9} for k, c in enumerate(many)], "end": 9.9}
    assert RB.rhythm_gate(T2, {"rhythm": R}, None) == []
    assert RB.rhythm_gate(T, {}, None) == []                                                   # 칸 없으면 렌더는 안 막음(카드·관문이 미달로)


def test_photo_gate():
    T = {"cuts": [{**c, "t1": t1} for c, t1 in zip(_cuts(), (3.6, 5.3, 9.0))], "end": 9.0}
    assert RB.photo_share(T["cuts"], 9.0) == round(3.7 / 9.0, 3)
    assert RB.photo_gate(T, {"rhythm": R})
    assert not RB.photo_gate(T, {"rhythm": {**R, "photo_share_max": {"v": 0.5, "why": "x"}}})


def test_plain_step():
    rows = [{"line": f"N{i // 2}", "text": str(i), "speaker": "narr", "enter": "cut", "emph": [{"word": "x"}], "stickers": []} for i in range(10)]
    log = []
    PL.plain_step(rows, {"rhythm": R}, log)
    assert PL.plain_share(rows) == 0.2 and rows[0]["emph"] and rows[1]["emph"]               # 훅(첫 줄)은 안 뺌
    rows2 = [dict(r, emph=[{"word": "x"}]) for r in rows]
    PL.plain_step(rows2, {}, [])
    assert PL.plain_share(rows2) == 0.0


def test_action_order():
    S = {"lines": [{"id": "N3", "kind": "tts", "tts": "하나 사서 따라 발라 봤어요."}, {"id": "N4", "kind": "tts", "tts": "로션처럼 펴져서."}]}
    M = {"cuts": {"N3": [{"src": "cp.jpg", "see": "쿠팡 상품 사진"}, {"src": "a.mp4", "see": "손등에 크림을 펴 바름"}], "N4": [{"src": "cp.jpg", "see": "사진"}]}}
    w = MF.action_order(S, M, log=lambda m: None)
    assert M["cuts"]["N3"][0]["src"] == "a.mp4"
    assert len(w) == 1 and w[0].startswith("N4")
    M2 = {"cuts": {"N3": [{"src": "cp.jpg", "see": "쿠팡 상품 사진"}]}}
    assert MF.action_order({"lines": S["lines"][:1]}, M2, log=lambda m: None)


def test_match_cut_median_no_target_fails():
    from tools.calcopy.engine import kal_analyze as K
    doc = {"dur": 10.0, "lines": [{"t0": 0, "t1": 1, "speaker": "나레", "text": "가나다", "enter": "cut", "emph": [], "sticker": []}]}
    ours = {"rows": [{"t0": 0, "t1": 1, "speaker": "narr", "text": "가나다", "line": "N1"}], "end": 28.0}
    t = K.match_table([doc], ours, {"cut_median": 1.2}, {"cut_median": [1.0]}, own_len=(25, 30), own_targets={})
    row = next(r for r in t["rows"] if r["key"] == "cut.median")
    assert row["judge"] == "failed"
    t2 = K.match_table([doc], ours, {"cut_median": 1.2}, {"cut_median": [1.0]}, own_len=(25, 30), own_targets={"cut.median": (1.15, "w")})
    assert next(r for r in t2["rows"] if r["key"] == "cut.median")["judge"] != "skip"


def test_new_viol_sees_chain():
    """나눈 조각(같은 원본 이어 붙인 앞으로 가기 사슬)은 B13 아님 — _new_viol 이 목록 전체로 판정(짝으로 부르면 첫↔끝 거리 오탐)."""
    p = [{"src": "a.mp4", "ss": 8.0 + 1.24 * k, "dur": 1.24, "t0": 23.17 + 1.24 * k, "t1": 23.17 + 1.24 * (k + 1), "line": "N7"} for k in range(3)]
    assert MF._new_viol(p[:2], p[2], {"a.mp4": 30.0}) == []
    far = {**p[2], "t0": 5.0, "t1": 6.2, "line": "N2"}           # 사슬 밖 가까운 재사용은 그대로 잡는다
    assert MF._new_viol(p[:2], far, {"a.mp4": 30.0})
