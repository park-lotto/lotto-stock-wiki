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


def test_rhythm_cuts_splits_long_and_hook():
    out = RB.rhythm_cuts(_cuts(), 9.0, R, log=lambda m: None)
    hook = [c["t0"] for c in out[1:] if 0.1 < c["t0"] <= 3.0]
    assert len(hook) >= 2
    n1 = [c for c in out if c["line"] == "N1"]
    assert len(n1) == 3 and n1[1]["ss"] > n1[0]["ss"] and n1[1]["crop"] != n1[0]["crop"]     # 이어서·칸 바꿈
    o1 = [c for c in out if c["line"] == "O1"]
    assert all(abs((c["ss"] - o1[0]["ss"]) - (c["t0"] - o1[0]["t0"])) < 1e-3 for c in o1)      # 원음 입 맞춤 그대로
    pj = [c for c in out if c["src"] == "p.jpg"]
    assert all(c["ss"] == 0 for c in pj)                                                       # 그림은 ss 안 옮김
    assert RB.rhythm_cuts(_cuts(), 9.0, {}, log=lambda m: None) == _cuts()                       # 칸 없으면 그대로


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
