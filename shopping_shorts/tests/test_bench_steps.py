# -*- coding: utf-8 -*-
"""벤치마킹 단계별 칸 표(hybrid/bench_steps) + 단계 관문(flow_bench._step_gate) — 관제 319, 사장님 11-06 '단계별 지침과 검수'."""
import json

import pytest

from tools.calcopy.hybrid import bench_steps as BS, flow, flow_bench as FB


# ── 표 ↔ 지침서 ───────────────────────────────────────────────
def test_guide_every_line_covered():
    c = BS.coverage()
    assert c["pct"] == 100.0 and not c["miss"], f"표에 없는 지침서 줄: {c['miss'][:20]}"
    assert not c["beyond"]


def test_guide_anchors_not_shifted():
    assert BS.anchors_ok() == []


def test_rows_well_formed():
    ids = [r["id"] for r in BS.STEPS]
    assert len(ids) == len(set(ids))
    for r in BS.STEPS:
        assert bool(r["none"]) != bool(r["phase"]), r["id"]            # 단계가 있거나, 해당 단계 없음 이유가 있거나 — 둘 중 하나만
        if r["phase"]:
            assert r["phase"] in {k for k, _ in FB.STAGES} or r["phase"] == "bm_setup", r["id"]
            assert r["owner"] and ":" in r["owner"] and r["check"], r["id"]
            assert (BS.CAL / r["owner"].split(":")[0]).is_file(), r["owner"]
            if r["phase"] in BS.GATE_PHASES and r["check"][0] != "owner":
                assert r["out"], r["id"]


# ── 대조표: 주인 함수가 흐름에서 불리나 ───────────────────────────────
def test_every_blocking_owner_is_called_by_bench_flow():
    w = BS.wiring()
    assert w["missing"] == [], f"흐름이 안 부르는 주인 함수(이어야 할 것): {w['missing']}"
    assert w["stale"] == [], f"'함수 안 이음'으로 적었는데 실제로 불림: {w['stale']}"


def test_graph_sees_known_edges():
    got = BS.reached()
    assert BS._owner_key("engine/kal_analyze.py:check_doc") in got        # c_bm_fill → K.check_doc
    assert BS._owner_key("engine/analyze.py:analyze") in got              # c_bm_tear → BM.tear → A.analyze


# ── 재기·판정 ───────────────────────────────────────────────
def _work(tmp_path, lines=None, tear_extra=None):
    ch = tmp_path / "channel" / "s"
    (ch / "뜯기" / "a").mkdir(parents=True)
    J = {"probe": {"w": 1080, "h": 1920}, "layout": {"window": [0, 0, 1080, 1920], "caption_band": [1200, 1400], "bg_rgb": [0, 0, 0]},
         "captions": {"items": [{"t0": 0, "t1": 1}]}, "cuts": {"times": [], "zoom": {"n": 1}}, "fonts": {"top3": ["a"], "title": {"x": 1}},
         "audio": {"bench": {"I": -14.0}}, "sfx_rules": {}, "bgm_rules": {}, "voice_rules": {}, "overlay_rules": {}, "text_fx": {}, "caption_motion": {}}
    J.update(tear_extra or {})
    (ch / "뜯기" / "a" / "뜯기.json").write_text(json.dumps(J), encoding="utf-8")
    (ch / "뜯기" / "a" / "frame.json").write_text("{}", encoding="utf-8")
    (ch / "preset" / "틀").mkdir(parents=True)
    for f in ("frame.json", "manifest.json"):
        (ch / "preset" / "틀" / f).write_text("{}", encoding="utf-8")
    return tmp_path


def test_measure_is_read_only(tmp_path):
    W = _work(tmp_path)
    before = sorted(p.as_posix() for p in W.rglob("*"))
    BS.measure(W, "bm_tear", "s", ["a"])
    assert sorted(p.as_posix() for p in W.rglob("*")) == before


def test_tear_full_passes_failed_slot_misses(tmp_path):
    W = _work(tmp_path)
    e = BS.evaluate("bm_tear", BS.measure(W, "bm_tear", "s", ["a"])["rows"], ["a"])
    assert e["miss"] == [], e["why"]
    W2 = _work(tmp_path / "x", tear_extra={"overlay_rules": {"failed": "건너뜀(--no-materials)"}, "probe": {"w": 720, "h": 1280}})
    e2 = BS.evaluate("bm_tear", BS.measure(W2, "bm_tear", "s", ["a"])["rows"], ["a"])
    assert "S3-over" in e2["miss"] and "S21-size" in e2["miss"]


def test_no_measure_is_miss_not_pass():
    e = BS.evaluate("bm_tear", {}, ["a"])
    assert e["miss"] and not e["ok"]            # 잰 값이 없으면 통과가 아니다


def test_wait_rows_never_block(tmp_path):
    e = BS.evaluate("bm_read", {}, ["a"])
    waits = {r["id"] for r in BS.STEPS if r["phase"] == "bm_read" and r["wait"] and r["out"] and r["check"][0] != "owner"}
    assert waits and waits <= set(e["wait"]) and not (waits & set(e["miss"]))


def test_read_lines_check(tmp_path):
    ch = tmp_path / "channel" / "s" / "줄판독"
    ch.mkdir(parents=True)
    ln = {"t0": 0, "t1": 1, "speaker": "나레", "layer": "채널", "enter": "instant", "y": [1, 2], "emph": [], "sticker": [], "sfx": None,
          "scene": "x", "transition": "cut"}
    (ch / "a.json").write_text(json.dumps({"lines": [ln, {**ln, "speaker": None}], "frame0": {"kind": "scene"}, "beats": ["a"], "narr_share": 1.0,
                                           "_unread": [], "name_evidence": []}), encoding="utf-8")
    e = BS.evaluate("bm_read", BS.measure(tmp_path, "bm_read", "s", ["a"])["rows"], ["a"])
    assert "S31-sp" in e["miss"] and "1/2" in e["why"]["S31-sp"]
    assert "S31-layer" in e["ok"] and "S31-emph" in e["ok"]


# ── 흐름 관문 ───────────────────────────────────────────────
def _st(phase, **bm):
    return {"fmt": "벤치마킹", "phase": phase, "log": [], "tries": {}, "bm": {"slug": "s", "style": "틀", "name": "n", **bm}}


def _vid(i):
    return {"id": i, "mp4": f"src/{i}.mp4", "v360": f"src/{i}_360.mp4", "title": i, "views": 1}


def _gate(rows):
    return {"phase": "bm_tear", "ids": ["a"], "rows": rows}


def _tear_m(gate):
    m = {"bm_tear": {"presets": [{"style": "틀", "sources": ["a"]}], "failed": [], "r7": {}, "r7_failed": []}}
    if gate is not None:
        m["gate"] = gate
    return m


def test_tear_do_carries_gate():
    st = _st("bm_tear", videos=[_vid("a")])
    r = flow.step(st, {}, {}, {})
    cmds = [d["cmd"] for d in r["do"]]
    assert cmds[0] == "bm_tear" and cmds[-1] == "bm_gate" and r["do"][-1]["phase"] == "bm_tear"


def test_tear_with_empty_slots_goes_back_not_forward(tmp_path):
    """칸 빈 뜯기 결과로 다음 단계(뼈대)로 가면 안 된다 — 다시 재기(bm_tear)."""
    W = _work(tmp_path, tear_extra={"overlay_rules": {"failed": "건너뜀"}})
    g = BS.measure(W, "bm_tear", "s", ["a"])
    st = _st("bm_tear_got", videos=[_vid("a")])
    r = flow.step(st, _tear_m(g), {}, {})
    assert r["status"] == "execute"
    assert [d["cmd"] for d in r["do"]][0] == "bm_tear", r["do"]        # 뼈대(bm_skel)로 가지 않는다
    assert "S3-over" in st["bm"]["gate"]["bm_tear"]["miss"]


def test_tear_same_miss_three_times_stops(tmp_path):
    W = _work(tmp_path, tear_extra={"overlay_rules": {"failed": "건너뜀"}})
    g = BS.measure(W, "bm_tear", "s", ["a"])
    st = _st("bm_tear_got", videos=[_vid("a")])
    for _ in range(flow.REDO_STUCK - 1):
        r = flow.step(st, _tear_m(g), {}, {})
        assert r["status"] == "execute"
        st["phase"] = "bm_tear_got"
    r = flow.step(st, _tear_m(g), {}, {})
    assert r["status"] == "stop" and "S3-over" in json.dumps(r, ensure_ascii=False)


def test_tear_missing_gate_report_stops():
    st = _st("bm_tear_got", videos=[_vid("a")])
    r = flow.step(st, _tear_m(None), {}, {})
    assert r["status"] == "stop"


def test_tear_full_slots_goes_to_skel(tmp_path):
    W = _work(tmp_path)
    st = _st("bm_tear_got", videos=[_vid("a")])
    r = flow.step(st, _tear_m(BS.measure(W, "bm_tear", "s", ["a"])), {}, {})
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_skel"
    assert st["bm"]["gate"]["bm_tear"]["miss"] == [] and st["bm"]["gate"]["bm_tear"]["wait"] is not None


def test_runner_gate_and_rules_registered():
    from tools.calcopy.hybrid import runner_ops as R
    assert "bm_gate" in R.CMDS and "bm_rules" in R.CMDS and "bm_gate" in R.CMD_LABEL and "bm_rules" in R.CMD_LABEL


def test_runner_rules_writes_kal_files(tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    d = tmp_path / "channel" / "s" / "줄판독"
    d.mkdir(parents=True)
    ln = {"t0": 0, "t1": 1, "speaker": "나레", "text": "이거 진짜 좋아요", "layer": "채널", "enter": "instant", "emph": [], "sticker": [], "sfx": None}
    (d / "a.json").write_text(json.dumps({"id": "a", "dur": 2, "lines": [ln]}), encoding="utf-8")
    r = R.c_bm_rules(tmp_path, {"slug": "s", "ids": ["a"]})
    assert r["docs"] == 1
    for p in ("channel/s/_kal/규칙빈도.json", "channel/s/_kal/대본언어.json", "channel/s/팔레트.json"):
        assert (tmp_path / p).is_file(), p
