# -*- coding: utf-8 -*-
"""재료 찾기 자동화(material_auto) — 판정 주인(allowed·reuse_conflict·select)과 전체 흐름(가짜 통로·가짜 모델) 시험 (관제 097, 2026-10-17).
빨강/초록 짝: 같은 소스 ±3초 재사용(사장님 10-17 재미썸홈 수정2 같은 컷 두 번) · 되감김(B13) · 남의 글자(A5) · 잇썸홈 같은 제품만."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import material_auto as ma  # noqa: E402

ITS, JAE = ma.CHANNELS["잇썸홈"], ma.CHANNELS["재미썸홈"]


def cell(vid, t, product="same", text=False, dark=False, what="sink dishwasher", interval=2.0):
    return {"vid": vid, "t": t, "interval": interval, "img": "", "what": what, "action": "", "people": "none",
            "text": text, "dark": dark, "cg": False, "product": product}


def toks(n, line=0, dur=0.8):
    return [{"i": k, "text": f"토막{k}", "t0": k * dur, "dur": dur, "line": line, "line_text": ""} for k in range(n)]


META = {"A": {"res": 1080}, "B": {"res": 1080}, "LOW": {"res": 480}}


# ── allowed ────────────────────────────────────────────────────────────────
def test_allowed_rejects_foreign_text_dark_and_lowres():
    assert ma.allowed(cell("A", 3), "product", ITS, 1080)
    assert not ma.allowed(cell("A", 3, text=True), "product", ITS, 1080)      # A5
    assert not ma.allowed(cell("A", 3, dark=True), "product", ITS, 1080)
    assert not ma.allowed(cell("A", 3), "product", ITS, 480)                  # A4


def test_allowed_same_product_only_channel():
    assert not ma.allowed(cell("A", 3, product="no"), "similar", ITS, 1080)   # 잇썸홈: 연상 영상 금지
    assert ma.allowed(cell("A", 3, product="no"), "similar", JAE, 1080)       # 재미썸홈: 허용
    assert ma.allowed(cell("A", 3, product="similar"), "before", ITS, 1080)   # 비교 토막은 같은 종류 다른 제품
    assert not ma.allowed(cell("A", 3, product="similar"), "product", ITS, 1080)


# ── reuse_conflict (사장님 10-17) ──────────────────────────────────────────
def test_reuse_conflict_red_within_3s():
    used = [("A", 10.0, 10.8)]
    assert ma.reuse_conflict("A", 12.5, 13.3, used)            # 끝 10.8 → 시작 12.5 = 1.7초 안
    assert ma.reuse_conflict("A", 9.5, 10.3, used)             # 겹침
    assert ma.reuse_conflict("A", 7.0, 7.8, used)              # 앞쪽 2.2초 안


def test_reuse_conflict_green():
    used = [("A", 10.0, 10.8)]
    assert ma.reuse_conflict("A", 14.0, 14.8, used) is None    # 3.2초 떨어짐
    assert ma.reuse_conflict("B", 10.0, 10.8, used) is None    # 다른 소스
    assert ma.reuse_conflict("A", 10.8, 11.6, used, prev=("A", 10.0, 10.8)) is None   # 바로 앞 컷 이어 가기


def test_reuse_conflict_rewind():
    assert ma.reuse_conflict("A", 30.0, 30.8, [("A", 40.0, 40.8)], prev=("A", 40.0, 40.8)) == "되감김(B13)"


# ── select ─────────────────────────────────────────────────────────────────
def _needs(ts, kind="product"):
    return {t["i"]: {"need": "x", "keywords": [], "kind": kind} for t in ts}


def test_select_red_duplicate_input_is_not_used_twice():
    """빨강: 서로 떨어진 두 토막(다른 줄)이 모두 같은 소스 같은 칸을 1순위로 받으면 두 번째는 다른 칸."""
    ts = [{"i": 0, "text": "a", "t0": 0, "dur": 0.8, "line": 0, "line_text": ""},
          {"i": 1, "text": "b", "t0": 0.8, "dur": 0.8, "line": 1, "line_text": ""},
          {"i": 2, "text": "c", "t0": 1.6, "dur": 0.8, "line": 2, "line_text": ""}]
    cells = {0: cell("A", 11.0), 1: cell("A", 13.0), 2: cell("B", 5.0), 3: cell("C", 7.0)}
    ranked = {0: [(0, 9)], 1: [(2, 8)], 2: [(1, 9), (3, 6)]}      # 토막2 1순위 A@13 은 토막0 A@10.2~11 과 3초 안
    meta = {**META, "C": {"res": 1080}}
    p = ma.select(ts, _needs(ts), ranked, cells, meta, ITS)
    assert p[0]["vid"] == "A" and p[2]["vid"] == "C"
    spans = [(x["vid"], x["src_t0"], x["src_t1"]) for x in p if x.get("vid")]
    for k, (v, a, b) in enumerate(spans):
        for (v2, a2, b2) in spans[k + 1:]:
            assert not (v == v2 and a2 < b + ma.REUSE_GAP and b2 > a - ma.REUSE_GAP), "같은 소스 ±3초 두 번"


def test_select_green_far_apart_same_source_allowed():
    ts = [{"i": 0, "text": "a", "t0": 0, "dur": 0.8, "line": 0, "line_text": ""},
          {"i": 1, "text": "b", "t0": 0.8, "dur": 0.8, "line": 1, "line_text": ""}]
    cells = {0: cell("A", 11.0), 1: cell("A", 31.0)}
    p = ma.select(ts, _needs(ts), {0: [(0, 9)], 1: [(1, 9)]}, cells, META, ITS)
    assert [x["vid"] for x in p] == ["A", "A"] and not p[1]["cont"]


def test_select_continuation_merges_neighbours_B4():
    """같은 줄 이웃 토막이 앞 컷 다음 칸을 후보로 가지면 한 컷으로 이어 간다(cont)."""
    ts = toks(3)
    cells = {0: cell("A", 11.0), 1: cell("A", 13.0), 2: cell("B", 50.0)}
    ranked = {0: [(0, 9)], 1: [(2, 9), (0, 7)], 2: [(1, 8), (2, 6)]}
    p = ma.select(ts, _needs(ts), ranked, cells, META, ITS)
    assert p[1]["cont"] and p[1]["vid"] == "A" and abs(p[1]["src_t0"] - p[0]["src_t1"]) < 1e-6
    assert ma.cut_lengths(p)[0] >= 1.6


def test_select_rejects_text_and_lowres_then_none():
    ts = toks(1)
    cells = {0: cell("A", 5.0, text=True), 1: cell("LOW", 5.0)}
    p = ma.select(ts, _needs(ts), {0: [(0, 9), (1, 9)]}, cells, META, ITS)
    assert p[0].get("none")


def test_select_meme_no_repeat():
    ts = toks(3)
    for t in ts:
        t["line"] = t["i"]
    needs = {0: {"need": "", "keywords": [], "kind": "meme"}, 1: {"need": "", "keywords": [], "kind": "product"},
             2: {"need": "", "keywords": [], "kind": "meme"}}
    p = ma.select(ts, needs, {1: [(0, 9)]}, {0: cell("A", 5.0)}, META, JAE, memes={0: "fm_x", 2: "fm_x"})
    assert p[0]["src"] == "meme:fm_x" and p[2].get("none")


def test_cap_memes():
    ts = toks(20)
    needs = {t["i"]: {"need": "", "keywords": [], "kind": "meme"} for t in ts}
    ma._cap_memes(ts, needs, JAE)
    assert sum(1 for n in needs.values() if n["kind"] == "meme") == 3      # 15% × 20


# ── 대본 꼴 두 가지 ─────────────────────────────────────────────────────────
def test_norm_script_pieces_assigns_lines():
    sj = {"spine55": [{"line": "가나다 라마."}, {"line": "바사 아자차."}],
          "pieces": [{"i": 1, "t0": 0, "dur": 1, "caption": "가나다"}, {"i": 2, "t0": 1, "dur": 1, "caption": "라마."},
                     {"i": 3, "t0": 2, "dur": 1, "caption": "바사"}, {"i": 4, "t0": 3, "dur": 1, "caption": "아자차."}]}
    _, ts = ma.norm_script(sj)
    assert [t["line"] for t in ts] == [0, 0, 1, 1]


# ── 전체 흐름(가짜 통로·모델) ───────────────────────────────────────────────
class FakeNet:
    requests = 0
    bytes = 0

    def __init__(self, wd):
        self.wd, self.searched, self.sections = wd, [], []

    def search(self, q, n):
        self.searched.append(q)
        assert n <= ma.PER_QUERY
        return [{"id": "A", "duration": 60}, {"id": "B", "duration": 60}] if "dish" in q else []

    def meta(self, vid):
        return {"res": 1080, "duration": 60, "title": vid, "channel": "c", "info": "x"}

    def preview(self, vid, info):
        return None   # 프레임은 아래 패치로

    def section(self, vid, info, a, b):
        self.sections.append((vid, a, b))
        return None


def fake_llm(parts, prompt, tag):
    if tag == "ma_queries":
        return {"product": "sink dishwasher", "needs": [{"i": k, "need": "sink dishwasher", "keywords": ["sink", "dishwasher"], "kind": "product"}
                                                        for k in range(4)],
                "queries": [{"q": f"dish {k}", "purpose": "product", "toks": [0]} for k in range(15)]}, None
    if tag.startswith("ma_match"):
        ids = [int(x) for x in __import__("re").findall(r"^(\d+):", prompt, flags=8)]
        toks_ = [int(x) for x in __import__("re").findall(r"^(\d+)\. «", prompt, flags=8)]
        return {"picks": [{"tok": t, "cands": [[ids[(k * 4 + j) % len(ids)], 9 - j] for j in range(3)]} for k, t in enumerate(toks_)]}, None
    if tag.startswith("ma_requery"):
        return {"queries": []}, None
    return {}, None


def test_plan_materials_end_to_end_fake(tmp_path, monkeypatch):
    def fake_tag_all(vids, net, state, product, llm, wd, log):
        for vid in vids:
            if vid in state["tagged"]:
                continue
            state["tagged"].add(vid)
            for k in range(30):
                state["cells"][len(state["cells"])] = cell(vid, 1.0 + 2 * k)
    monkeypatch.setattr(ma, "_tag_all", fake_tag_all)
    monkeypatch.setattr(ma, "plan_sheet", lambda picks, toks, wd: [])
    sj = {"topic": "식기세척기", "lines": [{"i": 0, "text": "가 나 다 라"}],
          "tokens": [{"i": k, "line": 0, "text": f"토막{k}", "t0": k, "dur": 0.8} for k in range(4)]}
    net = FakeNet(tmp_path)
    out = ma.plan_materials(sj, "잇썸홈", tmp_path, net=net, llm=fake_llm)
    assert len(net.searched) <= ma.MAX_QUERIES                         # 검색어 상한
    assert out["stats"]["empty"] == 0 and len(out["shots"]) == 4
    spans = [(s["vid"], s["src_t0"], s["src_t1"], s["cont"]) for s in out["shots"]]
    for k, (v, a, b, _) in enumerate(spans):                          # 이어 가기 아닌 같은 소스 ±3초 재사용 없음
        for (v2, a2, b2, c2) in spans[k + 2:]:
            assert not (v == v2 and a2 < b + ma.REUSE_GAP and b2 > a - ma.REUSE_GAP)
    assert net.sections                                                # 구간만 받기 요청
    assert json.loads((tmp_path / "재료_auto.json").read_text(encoding="utf-8"))["channel"] == "잇썸홈"


def test_llm_stops_after_too_many_429():
    llm = ma.LLM(lambda p, q, t: (None, "429"))
    with pytest.raises(ma.Stop):
        for _ in range(ma.MAX_429 + 1):
            llm([], "x", "t")


def test_compare_human_criteria():
    auto = {"shots": [{"i": 0, "caption": "a", "vid": "X", "src": "X", "src_t0": 11.0, "seen": "s"},
                      {"i": 1, "caption": "b", "vid": "Y", "src": "Y", "src_t0": 5.0, "seen": "s"}]}
    human = {"shots": [{"i": 0, "src": "src_X.mp4", "ss": 9.0, "ours": "h"}, {"i": 1, "src": "src_X.mp4", "ss": 5.0, "ours": "h"}]}
    r = ma.compare_human(auto, human)
    assert r["same_seg"] == 1 and r["rows"][1]["same_src"] is False
