# -*- coding: utf-8 -*-
"""배치·자리 검출 일반화 시험 (관제 263 지시서 03 · 표준 §3-3 A1·A2·A3).

① 전환: 본보기 편 줄판독 transition = zoomblur 3/10 → place() transitions 에 zoomblur 3±1, 전부 컷 경계 ±1프레임, 짧은 컷(<1.2초) 경계엔 없음
② 효과음: 줄판독 sfx 6발(훅 2·공개 2·끝 2, 띵 3·휙 2·뽁 1) → 역할·종류 비율 ±1발, 0.3초 안 겹침 0
③ 자리: 얼굴 겹친 물건 상자 = None · 자막 띠 덮는 꾸밈 = None · 확신 < 0.6 = None · 손 상자 재현(샥탬 재료가 이 PC 에 있을 때)
④ 회귀: 키치잇판 9편 계획 시간표(이 PC 에 있을 때) — 등장·강조·스티커·효과음·번쩍이 렌더 때 저장한 배치와 같다
⑤ 효과음 신호표: channel/<slug>/_kal/sfx_events.json 으로 센 counted.sfx = 옛 공유 파일(접두 키)로 센 것
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import placement as PL  # noqa: E402

FPS = 30


def _style(line_reads: Path, rules: dict) -> dict:
    return {"name": "시험판", "bench": {"channel": "__placement_test", "line_reads": str(line_reads)},
            "placement": {"rules": rules},
            "caption": {"pack": "x", "pack_default": {}, "variant_for": {}},
            "frame": {"flash_sec": 0.1}, "cuts": {"transition": {"kinds": {"cut": 1.0}, "ms": 0}},
            "sfx_files": {"ding": "팩01/ding.wav", "whoosh": "팩01/whoosh.wav", "pop": "팩01/pop.wav", "gain_db": -8}}


def _bench_read(tmp_path: Path, lines: list[dict]) -> Path:
    d = tmp_path / "줄판독"
    d.mkdir()
    (d / "REF.json").write_text(json.dumps({"id": "REF", "lines": lines}, ensure_ascii=False), encoding="utf-8")
    return d


def _ours(n: int = 11, short: tuple = ()) -> tuple[list[dict], list[dict]]:
    """우리 덩어리 n 줄(줄마다 한 덩어리·한 컷) — 줄 k 컷 길이 2초, short 에 든 줄은 0.8초."""
    rows, cuts, t = [], [], 0.0
    roles = ["훅", "훅"] + ["본문"] * (n - 6) + ["공개", "공개", "끝", "끝"]
    for k in range(n):
        d = 0.8 if k in short else 2.0
        rows.append({"line": f"L{k}", "j": 0, "speaker": "narr" if k % 3 else "orig", "text": f"줄 {k} 진짜 좋아요", "t0": round(t, 3),
                     "t1": round(t + d, 3), "role": roles[k], **({"key": "제품"} if k in (7, 8) else {})})
        cuts.append({"t0": round(t, 3), "t1": round(t + d, 3), "dur": d})
        t += d
    return rows, cuts


# ① 전환 ─────────────────────────────────────────────────────────────
def test_transition_zoomblur_follows_bench_on_cut_bounds(tmp_path):
    lines = [{"t0": k, "t1": k + 1, "speaker": "나레", "text": "가", "transition": "zoomblur" if k in (2, 5, 8) else "cut"} for k in range(11)]
    st = _style(_bench_read(tmp_path, lines), {"transition": {}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    p = PL.place(rows, st, "seed", cuts=cuts)
    zb = [x for x in p["transitions"] if x["kind"] == "zoomblur"]
    assert abs(len(zb) - 3) <= 1, p["transitions"]
    bounds = [c["t0"] for c in cuts[1:]]
    assert all(min(abs(x["t"] - b) for b in bounds) <= 1 / FPS for x in zb)
    assert PL.check_place(p, st)["slots"]["transitions"]["ours"].get("zoomblur") == len(zb)


def test_transition_skips_short_cuts(tmp_path):
    lines = [{"t0": k, "t1": k + 1, "speaker": "나레", "text": "가", "transition": "zoomblur"} for k in range(11)]
    st = _style(_bench_read(tmp_path, lines), {"transition": {}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours(short=(4, 5))
    p = PL.place(rows, st, "seed", cuts=cuts)
    bad = {cuts[4]["t0"], cuts[5]["t0"], cuts[6]["t0"]}          # 짧은 컷(4·5)의 앞·뒤 경계
    assert p["transitions"] and not [x for x in p["transitions"] if x["t"] in bad], p["transitions"]


def test_flash_rule_becomes_transition_and_flashes_view(tmp_path):
    lines = [{"t0": 0, "t1": 1, "speaker": "나레", "text": "가"}]
    st = _style(_bench_read(tmp_path, lines), {"flash": {"share": 1.0}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    p = PL.place(rows, st, "seed", cuts=cuts)
    assert p["flashes"] == [x["t"] for x in p["transitions"] if x["kind"] == "flash"] and len(p["flashes"]) == 1
    assert p["transitions"][0]["ms"] == 100


# ② 효과음 ────────────────────────────────────────────────────────────
def test_sfx_follows_bench_roles_and_kinds(tmp_path):
    spec = [("훅", "띵"), ("훅", "휙"), ("공개", "띵"), ("공개", "뽁"), ("끝", "띵"), ("끝", "휙")]
    lines = [{"t0": 2.0 * k, "t1": 2.0 * k + 1.5, "speaker": "나레", "text": "가", "role": r, "sfx": {"kind": s, "t": 2.0 * k - 0.03, "basis": "파형 솟음"}}
             for k, (r, s) in enumerate(spec)]
    st = _style(_bench_read(tmp_path, lines), {"sfx": {"max": 9}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    p = PL.place(rows, st, "seed", cuts=cuts)
    sx = p["sfx"]
    assert len(sx) == 6, sx
    roles = Counter(e["role"] for e in sx)
    for r in ("hook", "reveal", "end"):
        assert abs(roles.get(r, 0) - 2) <= 1, roles
    kinds = Counter(e["kind"] for e in sx)
    assert abs(kinds.get("ding", 0) - 3) <= 1 and abs(kinds.get("whoosh", 0) - 2) <= 1 and abs(kinds.get("pop", 0) - 1) <= 1, kinds
    assert all(b["t"] - a["t"] >= 0.3 for a, b in zip(sx, sx[1:]))
    assert all(abs(e["t"] - (r["t0"] - 0.03)) < 1e-6 for e in sx for r in rows if abs(r["t0"] - 0.03 - e["t"]) < 0.01)   # 벤치 편차 −0.03 반영
    assert PL.check_place(p, st)["bad"] == []


# ③ 자리 ──────────────────────────────────────────────────────────────
def test_sticker_target_pending_without_locator_is_unresolved(tmp_path):
    lines = [{"t0": 0, "t1": 1, "speaker": "나레", "text": "대박!", "sticker": [{"what": "💎"}]}]
    st = _style(_bench_read(tmp_path, lines), {"stickers": {"gem": {"target": "object"}}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    p = PL.place(rows, st, "seed", cuts=cuts)
    gem = [s for r in p["rows"] for s in r["stickers"] if s["kind"] == "gem"]
    assert gem and gem[0]["site"] == "pending" and "x" not in gem[0]
    assert not PL.check_place(p, st)["ok"]
    got = PL.place(rows, st, "seed", cuts=cuts, locate=lambda tg, row, s: {"x": 40.0, "y": 60.0, "w": 100, "h": 90, "conf": 0.9, "face_clear": True})
    gem = [s for r in got["rows"] for s in r["stickers"] if s["kind"] == "gem"]
    assert gem[0]["site"] == "detected" and gem[0]["x"] == 40.0
    none = PL.place(rows, st, "seed", cuts=cuts, locate=lambda tg, row, s: None)
    assert not [s for r in none["rows"] for s in r["stickers"] if s["kind"] == "gem"]      # 못 찾으면 안 붙인다


def test_fixed_without_why_is_rejected(tmp_path):
    lines = [{"t0": 0, "t1": 1, "speaker": "나레", "text": "대박!", "sticker": [{"what": "💎"}]}]
    st = _style(_bench_read(tmp_path, lines), {"stickers": {"gem": {"target": {"fixed": {"x": 50, "y": 41}}}}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    assert not [s for r in PL.place(rows, st, "s", cuts=cuts)["rows"] for s in r["stickers"] if s["kind"] == "gem"]
    st["placement"]["rules"]["stickers"]["gem"]["target"]["why"] = "벤치 BRa 2.1초 프레임 실측"
    assert [s for r in PL.place(rows, st, "s", cuts=cuts)["rows"] for s in r["stickers"] if s["kind"] == "gem"][0]["site"] == "fixed"


def test_meme_rate_zero_gives_none_and_rate_places(tmp_path):
    lines = [{"t0": 0, "t1": 1, "speaker": "나레", "text": "가"}]
    st = _style(_bench_read(tmp_path, lines), {"meme": {"rate": 0}})
    st["placement"]["counted"] = PL.count(st)
    rows, cuts = _ours()
    assert not [s for r in PL.place(rows, st, "s", cuts=cuts)["rows"] for s in r["stickers"] if s["kind"] == "meme"]
    st["placement"]["rules"]["meme"] = {"rate": 0.2, "len_s": 1.0}
    out = [dict(r) for r in rows]
    log = []
    for r, rk in zip(out, PL.row_roles(out)):
        r.update(first=True, lex=PL.lex_of(r["text"]), stickers=[], role_key=rk)
    PL.meme_step(out, st, "s", None, log, files=["a.mp4", "b.mp4", "c.mp4"])
    memes = [s for r in out for s in r["stickers"] if s["kind"] == "meme"]
    assert len(memes) == 2 and len({m["src"] for m in memes}) == 2 and all(m["site"] == "pending" for m in memes)


def test_on_target_caption_band_and_window():
    from tools.calcopy.hybrid import fx_target as FT
    band = (880, 1030)
    assert FT.on_target([400, 900, 600, 1010], kind="circle", caption_band=band) is None                 # 원이 자막 띠를 덮는다
    assert FT.on_target([0, 434, 1080, 1486], size=(140, 180), canvas=(0, 434, 1080, 1052), caption_band=band) is None   # 창 가득 — 화살표 둘 곳 없음
    r = FT.on_target([400, 1100, 600, 1300], size=(140, 180), canvas=(0, 434, 1080, 1052), caption_band=band)
    assert r and r["side"] in ("below", "left", "right") and not (r["box"][3] > band[0] and r["box"][1] < band[1])
    assert FT.on_target([400, 700, 600, 850], size=(140, 180), canvas=(0, 434, 1080, 1052), caption_band=band)["side"] == "above"


def _hand_case(name: str):
    from tools.calcopy.hybrid import fx_target as FT
    c = next((c for c in FT.hand_cases() if name in c["편"]), None)
    if not c or not Path(c["src"]).exists():
        pytest.skip(f"샥탬 재료 원본 없음({name}) — 이 PC 전용 시험")
    return FT, c, FT.hand_canvas(c)


def test_find_object_face_overlap_is_none():
    FT, c, rgb = _hand_case("10편")
    fb = FT.faces(rgb, (0, 434, 1080, 1052))
    assert fb, "YuNet 얼굴 못 찾음"
    face = fb[0]["box"]
    assert FT.find("object", rgb, win=(0, 434, 1080, 1052), detector=lambda *a: (face, 0.9, "시험")) is None
    hand = FT.find("object", rgb, win=(0, 434, 1080, 1052), detector=lambda *a: (c["hand"], 0.9, "시험"))
    assert hand and FT.iou(hand["box"], c["hand"]) >= 0.99 and hand["face_clear"] is True
    assert FT.find("object", rgb, win=(0, 434, 1080, 1052), detector=lambda *a: (c["hand"], 0.4, "시험")) is None    # 확신 < 0.6


def test_caption_side_avoids_band_and_face():
    FT, c, rgb = _hand_case("10편")
    r = FT.find("caption_side", rgb, win=(0, 434, 1080, 1052), size=(200, 120), caption_band=(880, 1030))
    assert r and (r["box"][3] <= 880 or r["box"][1] >= 1030)


@pytest.mark.skipif(not __import__("os").environ.get("FX_TARGET_LIVE"), reason="Claude CLI 실호출 — FX_TARGET_LIVE=1 일 때만")
def test_find_object_claude_hits_hand_box():
    FT, c, rgb = _hand_case("10편")
    r = FT.find("object", rgb, win=(0, 434, 1080, 1052), what="노란 웃는 얼굴 수세미 Scrub Daddy")
    assert r and FT.iou(r["box"], c["hand"]) >= 0.5, r


# ④ 회귀 ──────────────────────────────────────────────────────────────
def _summary(p: dict):
    return (p["reference"], dict(Counter(r["enter"] for r in p["rows"])), sum(1 for r in p["rows"] if r.get("emph")),
            dict(Counter(s["kind"] for r in p["rows"] for s in r["stickers"])), [(e["t"], e["kind"]) for e in p["sfx"]], p["flashes"])


def test_kitchit_saved_plans_unchanged():
    from tools.calcopy.hybrid import styles as ST
    files = sorted((ROOT / "channel/yanshottem").glob("*/키치잇판/plan/계획_시간표.json"))
    if not files:
        pytest.skip("키치잇판 계획 시간표 없음 — 이 PC 전용 시험")
    st = ST.load("키치잇판")
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        S = json.loads((f.parent.parent / "대본.json").read_text(encoding="utf-8"))
        rows = [{k: v for k, v in r.items() if k != "show"} for r in d["timeline"]["rows"]]
        p = PL.place(rows, st, S.get("slug") or "x", cuts=d["timeline"]["cuts"])
        assert _summary(p) == _summary(d["placement"]), f.parent.parent.parent.name


# ⑤ 효과음 신호표 ──────────────────────────────────────────────────────
def test_channel_sfx_events_matches_legacy_shared_file(monkeypatch):
    from tools.calcopy.hybrid import styles as ST
    legacy = ROOT / "channel/starpickroom/_tools/결과/sfx_events_rules.json"
    for pan, slug in (("키치잇판", "kitchit"), ("꿀템노트판", "kkultemnote"), ("스타픽룸판", "starpickroom")):
        own = ROOT / "channel" / slug / "_kal" / "sfx_events.json"
        assert own.exists(), f"{own} 없음 — sfx_events.py {slug} 로 만든다"
        st = ST.load(pan)
        assert PL.sfx_events_path(st) == (own, None)
        new = PL._sfx_table(st)
        monkeypatch.setattr(PL, "sfx_events_path", lambda s, _p=legacy, _k=slug: (_p, _k))
        old = PL._sfx_table(st)
        monkeypatch.undo()
        assert new == old and len(new) == 8, (pan, new, old)


def test_sfx_no_overlap_on_dense_chunks(tmp_path):
    """촘촘한 덩어리(0.15초 간격)에도 효과음은 0.3초 안에 두 발 안 놓는다(사보타주 S9 — 간격 검사를 끄면 실패해야 한다)."""
    lines = [{"t0": 0.5 * k, "t1": 0.5 * k + 0.4, "speaker": "나레", "text": "가", "role": "훅", "sfx": {"kind": "띵", "t": 0.5 * k}} for k in range(4)]
    st = _style(_bench_read(tmp_path, lines), {"sfx": {"max": 9}})
    st["placement"]["counted"] = PL.count(st)
    rows = [{"line": "L0", "j": j, "speaker": "narr", "text": f"덩어리 {j}", "t0": round(0.15 * j, 3), "t1": round(0.15 * j + 0.15, 3), "role": "훅"} for j in range(8)]
    rows += [{"line": "L1", "j": 0, "speaker": "orig", "text": "끝", "t0": 1.2, "t1": 3.0, "role": "끝"}]
    p = PL.place(rows, st, "seed", cuts=[{"t0": 0.0, "t1": 1.2}, {"t0": 1.2, "t1": 3.0}])
    sx = p["sfx"]
    assert sx and all(b["t"] - a["t"] >= 0.3 for a, b in zip(sx, sx[1:])), sx
