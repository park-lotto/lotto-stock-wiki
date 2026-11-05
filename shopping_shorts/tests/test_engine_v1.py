# -*- coding: utf-8 -*-
"""엔진 v1 결정 파일(hybrid/engine_v1.json) + bench_steps 칸 단위 덮임 — 관제 319, 사장님 11-06 "뭘 쓴다는 거야?"."""
import re

import pytest

from tools.calcopy.hybrid import bench_steps as BS, engine_v1 as E

STATES = {"채택", "임시", "보류"}


# ── 결정 파일 ───────────────────────────────────────────────
def test_rows_well_formed():
    rs = E.rows()
    ids = [r["id"] for r in rs]
    assert len(ids) == len(set(ids))
    assert sum(1 for i in ids if i[1:].isdigit()) == 156          # 규격 v1.4 §0-1 156줄 하나도 안 버림
    for r in rs:
        assert r["state"] in STATES, r["id"]
        assert r["src"], r["id"]
        assert r["stage"] is None or r["stage"] in set(E.STEP_N.values()) | {"제작"}, r["id"]
        for o in r["owners"]:
            assert o["file"] is None or o["file"].endswith(".py"), (r["id"], o)


def test_spec_01_is_generated_from_file():
    """문서 §0-1 = 이 파일에서 만든 것과 줄마다 같다(손으로 고치지 않는다)."""
    if not E.SPEC.is_file():
        pytest.skip("규격 문서 없음(다른 PC)")
    d = E.diff_01()
    assert d["same"], "\n".join(d["diff"][:20])


def test_decision_tables_fully_covered():
    if not E.SPEC.is_file():
        pytest.skip("규격 문서 없음(다른 PC)")
    c = E.coverage()
    assert c["pct"] == 100.0, {k: v["miss"] for k, v in c["per"].items() if v["miss"]}


def test_v1_gate_rows_never_block():
    """결정 파일 행은 측정 자리가 없을 동안 기록만(wait) — 도는 실행을 막지 않는다(Jev v1gate_q1 해결 1.00)."""
    v1 = {r["id"] for r in BS.v1_rows() if r["phase"] == "bm_tear"}
    e = BS.evaluate("bm_tear", {}, ["a"])
    assert v1 and v1 <= set(e["wait"]) and not (v1 & set(e["miss"]))
    assert not any(r["id"] in v1 for r in BS.gate_rows("bm_tear"))     # 실행기 do 는 그대로


@pytest.mark.xfail(strict=True, reason="묶음 ③④⑤ 할 일 — 채택 행 주인 함수가 흐름에서 안 불림(엔진 v1 wire 가 목록을 낸다). 다 이으면 XPASS → 이 표식을 지운다")
def test_adopted_owner_called_by_flow():
    w = E.wiring()
    assert not w["unwired"], {b: ids for b, ids in w["by_bundle"].items()}


# ── bench_steps 칸 단위 덮임(감시 적발 A) ───────────────────────────────
def _keys() -> set[str]:
    ks = set()
    for r in BS.STEPS:
        if not r["out"]:
            continue
        key = r["out"].partition("#")[2] or r["out"]
        ks.add(key)
        ks.add(key.replace("lines[].", ""))
        ks.add(key.split(".")[-1])
    return ks


def _guide() -> list[str]:
    return BS.GUIDE.read_text(encoding="utf-8").splitlines()


def test_strict_slots_each_have_a_row():
    """지침서 §6 'check --strict 가 더 요구하는 칸'·line_read 기본 줄 칸 하나 = 행 하나."""
    g = _guide()
    i = next(k for k, t in enumerate(g) if "더 요구하는 칸" in t)
    strict = set()
    for tok in re.findall(r"`([^`]+)`", g[i + 1]):
        name = re.split(r"[{\[(]", tok)[0]
        strict.add(name)
        m = re.search(r"\{([^}]*)\}", tok)
        if name == "frame0" and m:
            strict.add("face_frac")
    base = next(t for t in g if "기본 칸(" in t)
    inner = re.search(r"lines\{(.*?)\}·no_caption", base)[1]
    line_fields = {re.split(r"[{]", x)[0] for x in re.sub(r"\{[^}]*\}", "", inner).split(",")}
    skel = {"t0", "t1", "text", "notes"}           # 뼈대 칸 — S22-skel(뼈대 파일)이 잰다
    want = (strict | line_fields) - skel
    miss = sorted(x for x in want if x not in _keys())
    assert not miss, f"행 없는 §6 칸: {miss}"


A_SLOTS = {  # 지침서 §3-1 A·§3-2 A 글 → 행이 재는 키
    "줄바꿈 규칙": "wrap", "강조 낱말": "emph_hex", "grow": "emph_grow", "type_cps": "type_cps", "cursor": "cursor", "퇴장": "exit",
    "기울임°": "fonts.title.slant_deg", "낱말 색 hex": "fonts.title.word_hex", "상자 hex": "fonts.title.box_hex", "로고 자리": "fonts.brand",
    "출처 줄 hex/px/y": "layout.source_px", "워터마크 투명도": "layout.watermark.alpha", "above_bands": "layout.above_bands", "bg_rgb": "layout.bg_rgb",
    "줄 높이": "fonts.title.bands",
}
EXTRA = {"sticker_xy": "잉?·와우 자리", "reveal_t": "반전·공개 시점", "narr_off": "원음 구간 나레 끔", "face_frac": "0초 얼굴 비율", "*.jpg": "썸네일 jpg"}


def test_section3_A_slots_each_have_a_row():
    g = "\n".join(_guide())
    ks = _keys()
    for phrase, key in A_SLOTS.items():
        assert phrase in g, f"지침서에 '{phrase}' 없음 — 표를 다시 맞춘다"
        assert key in ks, f"§3 A '{phrase}' → 행 없음({key})"
    for key, what in EXTRA.items():
        assert key in ks or any(r["out"] and r["out"].endswith(key) for r in BS.STEPS), what


def test_motion_is_line_ratio_not_presence(tmp_path):
    """감시 적발 B: 자막 22줄 중 등장 곡선 3줄이면 막는다(옛 '값 있음'은 통과)."""
    import json
    ch = tmp_path / "channel" / "s" / "뜯기" / "a"
    ch.mkdir(parents=True)
    J = {"captions": {"items": [{"t0": i} for i in range(22)]}, "caption_motion": {"starts": [{}] * 3, "ends": [{}] * 22}}
    (ch / "뜯기.json").write_text(json.dumps(J), encoding="utf-8")
    e = BS.evaluate("bm_tear", BS.measure(tmp_path, "bm_tear", "s", ["a"])["rows"], ["a"])
    assert "S31-motion" in e["miss"] and "S31-motion-end" in e["ok"], e["why"].get("S31-motion")
