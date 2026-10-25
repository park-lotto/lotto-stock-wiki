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
    import copy
    st = ST.load("키치잇판")
    st_old = copy.deepcopy(st)                 # 10-25 관제263 판 cuts.transition.kinds(벤치 실측 전환) 넣기 전 계획은 그 칸 없이 만든 것
    st_old["cuts"]["transition"]["kinds"] = {"cut": 1.0}
    for x in (st, st_old):                     # 10-25 관제263 판 rhythm.plain_share(꾸밈 없는 덩어리) 넣기 전 계획은 그 칸 없이 만든 것
        x.pop("rhythm", None)
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        S = json.loads((f.parent.parent / "대본.json").read_text(encoding="utf-8"))
        rows = [{k: v for k, v in r.items() if k != "show"} for r in d["timeline"]["rows"]]
        made_new = any("판 cuts.transition.kinds" in str(x) for x in d["placement"].get("log") or [])
        p = PL.place(rows, st if made_new else st_old, S.get("slug") or "x", cuts=d["timeline"]["cuts"])
        assert _summary(p) == _summary(d["placement"]), f.parent.parent.parent.name


# ⑤ 효과음 신호표 ──────────────────────────────────────────────────────
def test_channel_sfx_events_matches_legacy_shared_file(monkeypatch, tmp_path):
    """옛 공유 파일 1회 변환(sfx_events.convert)으로 센 counted.sfx = 옛 공유 파일(접두 키)로 센 것. 06 이 채널을 다시 재도(--detect) 변환 자체는 같아야 한다."""
    E = _sfx_events()
    legacy = ROOT / "channel/starpickroom/_tools/결과/sfx_events_rules.json"
    for slug in ("kitchit", "kkultemnote", "starpickroom"):
        p = tmp_path / f"{slug}.json"
        p.write_text(json.dumps({"_meta": {}, **E.convert(slug)}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(PL, "sfx_events_path", lambda s, _p=p: (_p, None))
        new = PL._sfx_table({"bench": {}})
        monkeypatch.setattr(PL, "sfx_events_path", lambda s, _p=legacy, _k=slug: (_p, _k))
        old = PL._sfx_table({"bench": {}})
        monkeypatch.undo()
        assert new == old and len(new) == 8, (slug, new, old)


# ⑥ 효과음 신호표 검출(engine/sound/sfx_events — 06 결손 3건, 10-25) ─────────────────
def _sfx_events():
    sys.path.insert(0, str(ROOT / "tools/calcopy/engine/sound"))
    import sfx_events as E
    return E


def test_low_band_thumps_found():
    """저역 '쿵·붐'(100~400Hz) — 신박 줄판독 정답 rAt 8.6·11.15 · bpj 14.73(±0.1초)."""
    E = _sfx_events()
    import sfx_fp as F
    for vid, truth in (("rAt34vkQ0OY", (8.6, 11.15)), ("bpjoacs2S6Q", (14.73,))):
        f = Path(f"C:/숏템_칼카피/sinbak/src/{vid}.mp4")
        if not f.exists():
            pytest.skip("신박 원본 없음 — 이 PC 전용 시험")
        low = [e["t"] for e in E.detect(F.load(str(f))) if e["kind"] == "low"]
        for t in truth:
            assert any(abs(t - x) <= 0.1 for x in low), (vid, t, low)


def test_asr_hallucination_means_no_words(tmp_path):
    E = _sfx_events()

    def w(path, words):
        p = tmp_path / path
        p.write_text(json.dumps({"words": [{"w": a, "t0": b, "t1": c} for a, b, c in words]}, ensure_ascii=False), encoding="utf-8")
        return str(p)
    assert E.asr_words(w("a.json", [("Thank", 0, 1.4), ("you", 1.4, 1.5), ("for", 1.5, 1.6), ("watching,", 1.6, 5.8), ("please", 5.8, 5.9),
                                     ("subscribe", 5.9, 6.0), ("and", 6.0, 6.1), ("hit", 6.1, 6.2), ("that", 6.2, 6.3), ("like", 6.3, 6.4), ("button!", 6.4, 6.5)]))[0] == []
    assert E.asr_words(w("b.json", [("구독과", 0, 0.5), ("좋아요", 0.5, 1.0), ("부탁드려요!", 1.0, 1.6)]))[0] == []
    assert E.asr_words(w("c.json", [("Music", 0, 3.0)]))[0] == []
    assert E.asr_words(w("d.json", [(f"ご{k}", k * 0.1, k * 0.1) if k % 2 else (f"飯{k}", k * 0.1, k * 0.1 + 0.08) for k in range(20)]))[0] == []   # 길이0 낱말 50%
    ok, why = E.asr_words(w("e.json", [("오늘", 0, 0.4), ("신라면", 0.4, 1.0), ("끓여", 1.0, 1.4), ("볼게요", 1.4, 1.9), ("구독과", 20, 20.5), ("좋아요", 20.5, 21)]))
    assert [x["w"] for x in ok] == ["오늘", "신라면", "끓여", "볼게요"] and why.startswith("ok")


def test_asr_filter_keeps_candidates_near_cut_or_sticker():
    """샤크탱크 QMJ 7.26·7.36 '띠링' = 번쩍(컷) 7.067 직후 — 낱말 안이어도 남긴다. 표식 먼 낱말 안 후보는 거른다."""
    E = _sfx_events()
    row = {"cand": [{"t": 7.26, "kind": "broad"}, {"t": 7.36, "kind": "tonal"}, {"t": 3.0, "kind": "broad"}, {"t": 9.5, "kind": "low"}],
           "markers": {"cut": [7.07], "sticker": [], "cap": [3.0], "switch": []}}
    E.asr_filter(row, [{"w": "이거", "t0": 7.1, "t1": 7.5}, {"w": "진짜", "t0": 2.8, "t1": 3.2}])
    assert [(c["t"], bool(c.get("keep_why"))) for c in row["cand_kept"]] == [(7.26, True), (7.36, True), (9.5, False)]
    assert [c["t"] for c in row["cand_in_words"]] == [3.0] and row["asr_words"] == 2


def test_placement_counts_kept_candidates_only(tmp_path, monkeypatch):
    """신호표에 받아쓰기 거름(cand_kept)이 있으면 배치 세기는 남은 후보만 센다(낱말 안 오탐은 효과음 아님)."""
    p = tmp_path / "sfx.json"
    p.write_text(json.dumps({"_meta": {}, "V1": {"cand": [{"t": 1.0, "near": {"cap": 0.1}}, {"t": 2.0, "near": {"cap": 0.1}}],
                                                 "cand_kept": [{"t": 2.0, "near": {"cap": 0.1}}]},
                             "V2": {"cand": [{"t": 1.0, "near": {"switch": 0.2}}]}}), encoding="utf-8")
    monkeypatch.setattr(PL, "sfx_events_path", lambda s: (p, None))
    assert PL._sfx_table({"bench": {}}) == {"V1": ["cap"], "V2": ["switch"]}


# ⑦ 강조색 고르기(표준 §11-3 ㉒) ─────────────────────────────────────────────
def _emph_rows():
    return [{"line": "N1", "speaker": "narr", "text": "연어로 만든 한국 크림을", "variant": "hook", "emph": [{"word": "연어"}]},      # ep13 R1 훅 빨강 위 주황
            {"line": "N2", "speaker": "narr", "text": "분홍 알갱이마다", "variant": "", "emph": [{"word": "분홍"}]}]                # 나레 노랑 위 주황(벤치 ro1l 쌍)


@pytest.mark.parametrize("pack,hook_emph", [("ititemlog", []),                                   # 1차 팩(주황 하나) — 훅 빨강 위 주황 색상각<30° → 강조 없음+로그
                                            ("ititemlog_v2", [{"word": "연어", "color": "#E78DC3"}])])   # v2 팩 — 다음 후보 분홍(1a6bb76d7)
def test_emph_color_rule_on_red_hook(pack, hook_emph):
    """업그레이드 판 강조색(㉒·㉘): 훅 빨강 위 주황은 안 된다 — 팩 후보에 따라 강조 없음(로그) 또는 색상각 ≥30° 다음 후보. 노랑↔주황은 남는다."""
    import copy
    from tools.calcopy.hybrid import styles as ST
    st = copy.deepcopy(ST.load("잇템로그판_v2"))
    assert st.get("upgrades"), "업그레이드 판이어야 규칙이 돈다"
    st["caption"]["pack"] = pack
    out, log = _emph_rows(), []
    PL.emph_color_step(out, st, log)
    assert out[0]["emph"] == hook_emph, (out, log)
    for e in out[0]["emph"]:
        assert e["color"] != "#F07A09" and (PL.hue_gap("#E30004", e["color"]) is None or PL.hue_gap("#E30004", e["color"]) >= 30)
    if not hook_emph:
        assert any("N1" in x and "색상환" in x for x in log), log
    assert out[1]["emph"] == [{"word": "분홍", "color": "#F07A09"}]          # 벤치가 쓴 노랑↔주황은 남는다(LCh 39.6°)


def test_emph_color_rule_off_for_first_pan():
    from tools.calcopy.hybrid import styles as ST
    st = ST.load("잇템로그판")
    out, log = _emph_rows(), []
    PL.emph_color_step(out, st, log)
    assert out == _emph_rows() and not log                                   # 1차 판 = 벤치 색 쌍 그대로


def test_pick_emph_color_conditions():
    assert PL.pick_emph_color("#F7EB0E", ["#101010"], 18.0, "#000000")[0] is None                  # 검정 외곽선과 대비 1.2 < 3
    assert PL.pick_emph_color("#FFFFFF", ["#F5F5F5"], 18.0, "#000000")[0] is None                  # ΔE < 문턱
    c, why = PL.pick_emph_color("#E30004", ["#F07A09", "#F7EB0E"], 18.0, "#000000")
    assert c == "#F7EB0E" and "색상환" in why[0]                                                  # 첫 후보 탈락 → 다음 후보
    assert PL.emph_threshold("ititemlog")[0] == pytest.approx(17.97, abs=0.01)                      # 벤치 줄판독 색 강조 쌍 최소
    assert PL.emph_threshold("__없는채널__")[0] == PL.EMPH_DE_FALLBACK
    assert PL.emph_threshold("kitchit")[0] >= 10                                                   # 같은 색 흔들림(ΔE 5.5·7.4)은 문턱이 아니다


def test_hue_rule_skipped_for_low_chroma():
    """㉘: 한쪽 채도 C* < 20 이면 색상각 규칙 건너뜀 — 흰 줄(#FDFCFD) 위 연분홍(#F2D6E0, C*≈11)은 색상각과 무관하게 ΔE·명도만."""
    assert PL.hue_gap("#FDFCFD", "#F2D6E0") is None and PL.hue_gap("#E30004", "#E0B8A8") is None     # C* 11.4·18.1(15~20 사이 — 옛 15 문턱이면 비교했다)
    assert PL.hue_gap("#E30004", "#F07A09") == pytest.approx(20.6, abs=0.1)                          # 둘 다 C* ≥ 20


# ⑧ sfx_events 후속 4건 + ㉞(10-25) ──────────────────────────────────────────
def test_ncc_ignores_digital_silence_window():
    """굿레터 kfmZ 끝 impact-bass 0.941(28.66) = 디지털 무음 창 분모 거짓 — 무음 창은 판정 안 함(−80dB 잡음 깔면 0.38)."""
    E = _sfx_events()
    import sfx_ncc as N
    import sfx_fp as F
    w = Path("C:/숏템_칼카피/goodletter/work/wav/kfmZ_t4Bbss.wav")
    if not w.exists():
        pytest.skip("굿레터 wav 없음 — 이 PC 전용 시험")
    T, _ = N.templates()
    k = next(k for k in T if "impact-bass-2" in k)
    hits = N.scan(F.load(str(w)), {k: T[k]}, 0.3)
    assert not [h for h in hits if h["ncc"] >= 0.5], hits


def test_meta_asr_dir_reads_own_plain_folder(tmp_path):
    E = _sfx_events()
    assert E.meta_asr_dir({"asr_filter": {"asr": str(tmp_path).replace("\\", "/")}}) == str(tmp_path).replace("\\", "/")
    assert E.meta_asr_dir({"asr_filter": {"asr": "없는/폴더"}}) is None


def test_keep_window_follows_cut_density():
    E = _sfx_events()
    sparse = {"dur": 30.0, "markers": {"cut": [5.0, 15.0, 25.0]}}
    dense = {"dur": 30.0, "markers": {"cut": [round(0.4 * k, 2) for k in range(75)]}}          # 0.4초마다 컷(방구석 꼴)
    assert E.keep_window(sparse)[0] == 0.3
    w, ch = E.keep_window(dense)
    assert w < 0.3 and (w == 0 or ch <= E.KEEP_CHANCE)
    row = {**dense, "cand": [{"t": 6.15, "kind": "broad"}]}
    E.asr_filter(row, [{"w": "말", "t0": 6.0, "t1": 6.3}])
    assert not row["cand_kept"] and len(row["cand_in_words"]) == 1                          # 촘촘한 컷 곁 0.15초는 유의하지 않다


def test_bgm_beat_chain(monkeypatch):
    E = _sfx_events()
    import bgm_fp as B
    monkeypatch.setattr(B, "tempo", lambda x: {"low": 139.7, "low_ac": 0.5, "all": 69.8, "all_ac": 0.6})   # 옥타브 → 빠른 쪽
    cand = [{"t": t, "kind": "low"} for t in (8.61, 9.46, 11.19, 11.61, 14.40, 20.0)]
    E.mark_bgm_beats(cand, None)
    assert [c["t"] for c in cand if c.get("kind_class") == "bgm_beat"] == [8.61, 9.46, 11.19, 11.61]
    row = {"dur": 30, "markers": {}, "cand": cand}
    E.asr_filter(row, [], {"lines": [{"t0": 9.4, "t1": 10, "sfx": {"kind": "쿵", "t": 9.46}}]})
    assert [c["t"] for c in row["cand_bgm"]] == [8.61, 11.19, 11.61]                          # 판독 자리(9.46)는 박자여도 숨기지 않는다
    k = {c["t"]: c for c in row["cand_kept"]}
    assert k[9.46]["ear_pending"] and k[14.40]["confidence"] == "신호" and k[14.40]["ear_pending"]
    assert row["sfx_count"] == {"sure": 0, "pending": 3}


def test_eye_read_wins_over_word_filter():
    E = _sfx_events()
    row = {"dur": 20, "markers": {}, "cand": [{"t": 5.0, "kind": "broad"}, {"t": 9.0, "kind": "broad"}, {"t": 12.0, "kind": "tonal"}]}
    read = {"lines": [{"t0": 4.8, "t1": 6, "sfx": {"kind": "휙", "t": 5.02}}, {"t0": 11.9, "t1": 13, "sfx": {"kind": "띵", "t": 12.05}}]}
    E.asr_filter(row, [{"w": "그래서", "t0": 4.9, "t1": 5.2}, {"w": "진짜", "t0": 8.9, "t1": 9.2}], read)
    k = {c["t"]: c for c in row["cand_kept"]}
    assert set(k) == {5.0, 12.0} and [c["t"] for c in row["cand_in_words"]] == [9.0]
    assert k[5.0]["confidence"] == "눈" and k[5.0]["ear_pending"] and "판독 우선" in k[5.0]["keep_why"]
    assert k[12.0]["confidence"] == "눈" and not k[12.0].get("ear_pending")
    assert row["sfx_count"] == {"sure": 1, "pending": 1}


def test_tone_only_for_profiled_channel():
    E = _sfx_events()
    assert E.tone_cands("x.mp4", "kitchit") == []                                            # 프로필 없음 = 순음 검출 안 씀
    f = Path("C:/숏템_칼카피/evenshopping/src/1kfqEB2b1xM.mp4")
    if not f.exists():
        pytest.skip("이븐쇼핑 원본 없음 — 이 PC 전용 시험")
    reads = E._reads("evenshopping")
    truth = [float(l["sfx"]["t"]) for l in reads["1kfqEB2b1xM"]["lines"] if isinstance(l.get("sfx"), dict) and "띵" in str(l["sfx"].get("kind")) and isinstance(l["sfx"].get("t"), (int, float))]
    got = [e["t"] for e in E.tone_cands(str(f), "evenshopping")]
    assert truth and all(any(abs(t - g) <= 0.15 for g in got) for t in truth), (truth, got)
