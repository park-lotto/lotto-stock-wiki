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
NOWIN = {k: v for k, v in ITS.items() if k != "preset"}


def test_window_from_preset_manifest():
    assert ma.window_of(ITS) == (1080, 1920) and ma.window_of(JAE) == (1080, 1407) and ma.window_of(NOWIN) is None


def test_allowed_rejects_foreign_text_dark_and_lowres():
    assert ma.allowed(cell("A", 3), "product", ITS, 1080)
    assert not ma.allowed(cell("A", 3, text=True), "product", NOWIN, 1080)    # A5 — 창(프리셋) 모르면 미리보기 글자로 버린다
    assert ma.allowed(cell("A", 3, text=True), "product", ITS, 1080)          # 창이 있으면 잘라 본 1080 검사(verify_cuts)가 판정(10-18 구석 로고)
    assert not ma.allowed(cell("A", 3, dark=True), "product", ITS, 1080)
    assert not ma.allowed(cell("A", 3), "product", ITS, 480)                  # A4


def test_allowed_same_product_only_channel():
    assert not ma.allowed(cell("A", 3, product="no"), "similar", ITS, 1080)   # 잇썸홈: 연상 영상 금지
    assert ma.allowed(cell("A", 3, product="no"), "similar", JAE, 1080)       # 재미썸홈: 허용
    assert ma.allowed(cell("A", 3, product="similar"), "before", ITS, 1080)   # 비교 토막은 같은 종류 다른 제품
    assert not ma.allowed(cell("A", 3, product="similar"), "product", ITS, 1080)


def test_demo_and_situation_kinds_10_18():
    """10-18 사장님 '대사에 맞는 영상매칭이 안됐다' — 잇썸홈도 같은 종류 시연(demo)·문제 상황(situation) 칸을 받는다(짤·연상은 여전히 금지)."""
    assert ma.allowed(cell("A", 3, product="similar"), "demo", ITS, 1080)     # 다른 브랜드 같은 종류 시연(물컵 진동 등)
    assert not ma.allowed(cell("A", 3, product="no"), "demo", ITS, 1080)      # 시연인데 제품 종류가 안 보이면 아님
    assert ma.allowed(cell("A", 3, product="no"), "situation", ITS, 1080)     # 출장 가방·호텔 욕실
    assert not ma.allowed(cell("A", 3, product="no"), "meme", ITS, 1080)
    assert not ma.allowed(cell("A", 3, product="no"), "situation", JAE, 1080)  # 재미썸홈은 similar 로 받는다


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
    p = ma.select(ts, _needs(ts), {0: [(0, 9), (1, 9)]}, cells, META, NOWIN)
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
        return {"res": 1080, "duration": {"A": 60, "B": 75}.get(vid, 90), "title": vid, "channel": "c", "info": "x"}

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


def test_reupload_red_green():
    acc = [{"id": "rBCN", "duration": 275.0}]
    assert ma.reupload_of({"duration": 275.4}, acc) == "rBCN"        # 빨강: 같은 길이 재업(cFL4 = rBCN 실사례)
    assert ma.reupload_of({"duration": 120.0}, acc) is None          # 초록: 다른 길이
    assert ma.reupload_of({"duration": 20.0}, [{"id": "x", "duration": 20.0}]) is None   # 짧은 영상은 판정 안 함


def test_dark_by_luma_even_if_model_says_bright():
    c = cell("A", 3)
    c["luma"] = 20.0
    assert not ma.allowed(c, "product", ITS, 1080)          # 1판 검정 컷 실사례
    c["luma"] = 120.0
    assert ma.allowed(c, "product", ITS, 1080)


def test_ban_cells_after_1080_text_check_changes_pick():
    ts = toks(1)
    cells = {0: cell("A", 10.0), 1: cell("A", 40.0)}
    p = ma.select(ts, _needs(ts), {0: [(0, 9), (1, 7)]}, cells, META, ITS)
    assert p[0]["cell_t"] == 10.0
    p[0]["verify"] = "text"
    ma.ban_cells([p[0]], cells)
    p2 = ma.select(ts, _needs(ts), {0: [(0, 9), (1, 7)]}, cells, META, ITS)
    assert p2[0]["cell_t"] == 40.0


def test_cut_centred_on_described_frame():
    ts = toks(1, dur=1.0)
    p = ma.select(ts, _needs(ts), {0: [(0, 9)]}, {0: cell("A", 10.0, interval=4.6)}, META, ITS)
    assert p[0]["src_t0"] <= 10.0 <= p[0]["src_t1"]           # 칸 간격 4.6초여도 설명한 프레임이 컷 안


def test_same_line_neighbour_without_candidate_continues_previous_cut():
    """같은 문장 이웃 토막에 새 장면이 없으면 앞 컷을 이어 간다(B4) — 다른 문장이면 이어 가지 않고 빈칸."""
    ts = toks(2)
    cells = {0: cell("A", 10.0)}
    p = ma.select(ts, _needs(ts), {0: [(0, 9)], 1: []}, cells, META, ITS)
    assert p[1]["cont"] and p[1]["vid"] == "A" and abs(p[1]["src_t0"] - p[0]["src_t1"]) < 1e-6
    ts2 = [dict(ts[0]), dict(ts[1], line=1)]
    p2 = ma.select(ts2, _needs(ts2), {0: [(0, 9)], 1: []}, cells, META, ITS)
    assert p2[1].get("none") and "후보" in p2[1]["why"]


def test_continuation_stops_far_from_described_frame():
    ts = toks(5, dur=0.9)
    p = ma.select(ts, _needs(ts), {0: [(0, 9)]}, {0: cell("A", 10.0)}, META, ITS)
    assert any(x.get("none") for x in p)                     # 설명 프레임에서 2.5초 넘게 이어 가지 않는다


def test_replan_from_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "plan_sheet", lambda picks, toks, wd: [])
    ts = toks(2)
    ma.save_state(tmp_path, {"topic": "x", "toks": ts, "needs": _needs(ts), "ranked": {0: [(0, 9)], 1: [(1, 8)]}, "memes": {},
                             "cells": {0: cell("A", 10.0), 1: cell("B", 20.0)}, "meta": META, "queries": [{"q": "x"}], "rounds": 0})
    out = ma.replan(tmp_path, "잇썸홈", net=FakeNet(tmp_path), llm=lambda p, q, t: ({}, None), sections=False)
    assert [s["vid"] for s in out["shots"]] == ["A", "B"]


def test_verify_loop_final_picks_all_checked(tmp_path, monkeypatch):
    """1080 검사에 걸린 컷은 다시 고르고, 최종 컷은 전부 검사 결과가 있어야 한다(4판: 두 바퀴 재선택 뒤 최종 컷이 검사 없이 나감)."""
    monkeypatch.setattr(ma, "plan_sheet", lambda picks, toks, wd: [])
    from PIL import Image
    img = tmp_path / "f.jpg"
    Image.new("RGB", (32, 18), "gray").save(img)
    monkeypatch.setattr(ma, "_grab", lambda src, t, out, *win: img)

    class N(FakeNet):
        def section(self, vid, info, a, b):
            return f"{vid}_{a}.mp4"
    calls = []

    def llm(parts, prompt, tag):
        if tag == "ma_verify":
            calls.append(prompt)
            return {"cells": [{"n": 0, "text": len(calls) <= 2}, {"n": 1, "text": False}]}, None
        return {}, None
    ts = [dict(toks(1)[0], i=0, line=0), dict(toks(1)[0], i=1, line=1)]
    cells = {0: cell("A", 10.0), 1: cell("B", 30.0), 2: cell("C", 50.0), 3: cell("D", 70.0)}
    state = {"queries": [], "meta": {**META, "C": {"res": 1080}, "D": {"res": 1080}}, "cells": cells}
    T = {}
    picks, _ = ma.finish_plan(ts, _needs(ts), {0: [(0, 9), (1, 7), (3, 6)], 1: [(2, 9)]}, {}, state, ITS, N(tmp_path), ma.LLM(llm), tmp_path, True, T)
    assert picks[0]["vid"] == "D" and all(p.get("verify") == "ok" for p in picks)


def test_verify_missing_frame_is_not_ok(tmp_path, monkeypatch):
    """프레임을 못 뽑은 컷(잘린 구간)은 모델이 뭐라 하든 'ok' 가 아니다(5판: 1.04초로 잘린 구간이 ok 로 통과)."""
    monkeypatch.setattr(ma, "_grab", lambda src, t, out: None)
    p = [{"i": 0, "vid": "A", "section_file": "x.mp4", "section_ss": 1.0, "dur": 1.0, "src_t0": 0, "src_t1": 1}]
    ma.verify_cuts(p, tmp_path, ma.LLM(lambda a, b, c: ({"cells": [{"n": 0, "text": False}]}, None)))
    assert p[0]["verify"] == "프레임 없음"


def test_valid_video_rejects_short_section(tmp_path, monkeypatch):
    f = tmp_path / "s.mp4"
    f.write_bytes(b"0" * 20000)
    monkeypatch.setattr(ma, "_probe_dur", lambda p: 1.04)
    assert not ma._valid_video(f, 2.9)          # 2.9초 요청에 1.04초(실사례)
    assert ma._valid_video(f, 1.2)


def test_gather_shortens_zero_result_query(tmp_path):
    """10-18 실측: 긴 검색어('GearOra M23 portable retractable … review')는 유튜브가 0편 → 앞 낱말로 한 번 더."""
    class N(FakeNet):
        def search(self, q, n):
            self.searched.append(q)
            if len(q.split()) > 4:
                return []
            return [{"id": "A", "duration": 60, "title": "GearOra travel toothbrush"}, {"id": "Z", "duration": 60, "title": "Car Seat Organizer"}]
    net, logs = N(tmp_path), []
    state = {"queries": [], "meta": {}, "previews": [], "tagged": set(), "cells": {}}
    ma._gather([{"q": "GearOra M23 portable retractable sterilizing sonic toothbrush review", "purpose": "product"}], net, state, logs.append)
    assert net.searched == ["GearOra M23 portable retractable sterilizing sonic toothbrush review", "GearOra M23 portable retractable"]
    assert state["previews"] == ["A"] and len(state["queries"]) == 1 and any("검색 줄임" in x for x in logs)   # 브랜드 없는 Z 는 버림


def test_run_timeout_is_one_failed_request(monkeypatch):
    """10-18 실측: yt-dlp 검색 1개 시간 초과가 실행 전체를 죽였다 → 그 요청만 rc 124."""
    import subprocess as sp

    def boom(*a, **k):
        raise sp.TimeoutExpired(a[0], k.get("timeout"))
    monkeypatch.setattr(ma.subprocess, "run", boom)
    r = ma._run(["yt-dlp", "x"], timeout=1)
    assert r.returncode == 124 and r.stdout == ""


def test_gather_excludes_sibling_models(tmp_path):
    """10-18 실측: RG DS 재료에 RG DS Plus·RG DDS·Retroid 비교 영상이 같은 제품으로 태깅돼 섞였다 → 조사 단계 exclude_title 로 검색에서 거름."""
    class N(FakeNet):
        def search(self, q, n):
            return [{"id": "A", "duration": 60, "title": "Anbernic RG DS Review"}, {"id": "P", "duration": 60, "title": "Anbernic RG DS Plus Review"},
                    {"id": "D", "duration": 60, "title": "ANBERNIC RG DDS First Look"}]
    state = {"queries": [], "meta": {}, "previews": [], "tagged": set(), "cells": {}}
    ma._gather([{"q": "Anbernic RG DS", "purpose": "product"}], N(tmp_path), state, lambda *a: None, ["RG DS Plus", "RG DDS"])
    assert state["previews"] == ["A"]


# ── 대사↔장면 검수(fit) — 10-18 사장님 "대사에 맞는 편집포인트의 영상매칭이 안됐다" ──
def test_select_fit_ban_drops_cell_for_that_token_only():
    """검수에서 토막 0에 안 맞는다고 나온 칸(0)은 토막 0 후보에서만 빠지고 다음 후보(2)를 고른다. 이어 가기 대체로도 되살리지 않는다."""
    ts = toks(2)
    cells = {0: cell("A", 11.0), 1: cell("A", 13.0), 2: cell("B", 50.0)}
    ranked = {0: [(0, 9), (2, 8)], 1: [(1, 8)]}
    p0 = ma.select(ts, _needs(ts), ranked, cells, META, ITS)
    assert p0[0]["cid"] == 0
    p1 = ma.select(ts, _needs(ts), ranked, cells, META, ITS, fit_ban={0: {0}})
    assert p1[0]["cid"] == 2 and p1[0]["vid"] == "B"
    p2 = ma.select(toks(2), _needs(ts), {0: [(0, 9)], 1: []}, cells, META, ITS, fit_ban={1: {0}})
    assert p2[1].get("none")          # 토막 1 은 새 후보가 없고, 앞 컷(칸 0) 이어 가기도 금지 → 빈칸(사람이 고른다)


def test_fit_judge_retries_missing_numbers(tmp_path):
    """첫 답에 번호가 빠지면 한 번 더 묻는다(10-18 기준선: 10칸 묶음이 통째로 답 없음)."""
    calls = []

    def fake(parts, prompt, tag):
        calls.append(tag)
        if len(calls) == 1:
            return {"fits": [{"n": 0, "score": 9, "seen": "a", "want": "a"}]}, None
        return {"fits": [{"n": 1, "score": 3, "seen": "b", "want": "c"}]}, None
    r = ma.fit_judge([{"img": "", "piece": "x", "line": "x"}, {"img": "", "piece": "y", "line": "y"}], tmp_path, ma.LLM(fake))
    # 10-25 지시서 14: fit_judge = scene_fit.judge_rubric 껍데기 — 2회 채점, 빠진 번호가 있으면 3회째(중앙값은 받은 점수끼리)
    assert len(calls) == 3 and r[0]["score"] == 9 and r[1]["score"] == 3


def test_match_lines_retries_empty_answer():
    """짝짓기 답이 비면 한 번 더 묻는다(10-18 첫 줄 4토막 후보 0 → 빈칸)."""
    ts = toks(2)
    cells = {0: cell("A", 11.0), 1: cell("B", 20.0)}
    calls = []

    def fake(parts, prompt, tag):
        calls.append(tag)
        return ({"picks": [{"tok": 0, "cands": [[0, 9]]}, {"tok": 1, "cands": [[1, 8]]}]}, None) if len(calls) > 1 else ({}, None)
    r = ma.match_lines(ts, _needs(ts), cells, META, ITS, ma.LLM(fake), log=lambda *a: None)
    assert len(calls) == 2 and r[0][0][0] == 0 and r[1][0][0] == 1


def test_eye_rescue_reranks_by_picture(tmp_path):
    """빈칸·미달 토막은 후보 칸 그림을 대사와 직접 채점해 맞는 칸(≥FIT_MIN)을 앞으로, 안 맞는 칸은 그 토막에서 뺀다."""
    ts = toks(1)
    cells = {0: cell("A", 11.0), 1: cell("B", 20.0), 2: cell("A", 40.0)}
    ranked = {0: [(0, 9), (1, 6), (2, 5)]}

    def fake(parts, prompt, tag):
        return {"fits": [{"n": 0, "score": 3}, {"n": 1, "score": 9}, {"n": 2, "score": 2}]}, None
    ban = {}
    r = ma.eye_rescue([{"i": 0}], ts, _needs(ts), ranked, cells, META, ITS, ban, tmp_path, ma.LLM(fake), log=lambda *a: None)
    assert r[0][0] == (1, 9) and ban[0] == {0, 2}
    p = ma.select(ts, _needs(ts), r, cells, META, ITS, fit_ban=ban)
    assert p[0]["cid"] == 1


def test_eye_rescue_keeps_best_when_none_fit(tmp_path):
    """맞는 칸(≥FIT_MIN)이 하나도 없으면 최고점(≥EYE_FLOOR) 칸을 남긴다 — 다 빼면 빈칸이 된다(10-18 소넷 판정 12칸 빈칸)."""
    ts = toks(1)
    cells = {0: cell("A", 11.0), 1: cell("B", 20.0)}

    def fake(parts, prompt, tag):
        return {"fits": [{"n": 0, "score": 3}, {"n": 1, "score": 5}]}, None
    ban = {}
    r = ma.eye_rescue([{"i": 0}], ts, _needs(ts), {0: [(0, 9), (1, 6)]}, cells, META, ITS, ban, tmp_path, ma.LLM(fake), log=lambda *a: None)
    assert r[0][0][0] == 1 and ban[0] == {0}
    assert ma.select(ts, _needs(ts), r, cells, META, ITS, fit_ban=ban)[0]["cid"] == 1


def test_ban_excluded_blocks_sibling_model_cells():
    """제목에 다른 모델 낱말이 있으면 그 영상 칸은 고르지 않는다(10-18 잇썸홈 RG DS v2 — RG DS Plus 리뷰가 시연 칸으로 들어옴)."""
    ts = toks(1)
    cells = {0: cell("A", 11.0), 1: cell("B", 20.0)}
    meta = {"A": {"res": 1080, "title": "Anbernic RG DS Plus Review"}, "B": {"res": 1080, "title": "Anbernic RG DS Review"}}
    assert ma.ban_excluded(cells, meta, ["RG DS Plus"]) == 1
    p = ma.select(ts, _needs(ts), {0: [(0, 9), (1, 7)]}, cells, meta, ITS)
    assert p[0]["vid"] == "B"
