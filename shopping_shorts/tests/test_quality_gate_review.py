# -*- coding: utf-8 -*-
"""품질 관문 검토(10-25, 대상 9a8507108·dc128f353·0ea3970d4)로 드러난 느슨함 — 사보타주 시험.

③ 전환 '해당 없음 ○' = 배치 기록(placement.transitions_step)에 비율 출처가 있고 반올림한 원하는 개수가 0 일 때만
④ 나레 받아쓰기 = 스피치매틱스 낱말 시각(narr_verify.heard_words) — 위스퍼 small 단독 판정 금지(칼카피_시작 12번)
⑥ 스티커 모자람 = check_place bad
② 되감김 '경계에서만 센다' = check_seams.split_by_bounds(주인) · 시간표에 컷이 없으면 옛 판정(전부 센다)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

FIX = Path(__file__).with_name("fixtures") / "quality_gate"


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True, stdin=subprocess.DEVNULL, capture_output=True)


# ---------------------------------------------------------------- ③ 전환
def _trans_style(share):
    return {"placement": {"rules": {"transition": {}}, "counted": {}}, "cuts": {"transition": {"kinds": {"zoomblur": share}}}, "frame": {}}


def _rows_cuts(cut_len, n=10):
    out = [{"t0": i * cut_len, "t1": (i + 1) * cut_len, "line": f"N{i}", "speaker": "narr", "role_key": None} for i in range(n)]
    return out, [{"t0": i * cut_len, "t1": (i + 1) * cut_len} for i in range(n)]


def _tab(rec):
    return {"check": {"slots": {"transitions": {"ours": {}, "plan": rec}}}}


def test_transition_legacy_render_records():
    """옛 렌더 자막표(기록 전) — 실제 로그 줄·bench_expect 그대로."""
    from tools.calcopy.hybrid.quality_gate import drop_verdict, trans_plan_of
    bench = [0.175]                                                 # 키치잇판 벤치 drop 중앙(98 #95)
    ep12 = {"log": ["전환 [] (본보기 J7GxfaVdwSU 줄판독 34줄 비율 {'zoomblur': 0.03}, 컷 경계 17·붙일 수 있는 9(≥1.2초))"],
            "check": {"slots": {"transitions": {"bench_expect": {"zoomblur": 0.5}, "ours": {}, "cut_bounds": 17}}}}
    ep13 = {"log": ["전환 [] (판 cuts.transition.kinds 비율 {'zoomblur': 0.02}, 컷 경계 15·붙일 수 있는 10(≥1.2초))"],
            "check": {"slots": {"transitions": {"bench_expect": {}, "ours": {}, "cut_bounds": 15}}}}
    gimi = {"log": ["스티커 spark_lines 본보기 1개 중 0개만(조건 맞는 덩어리 모자람)"], "check": {"slots": {"transitions": {"ours": {}}}}}   # real20_gimi 키치잇판
    assert drop_verdict([], bench, trans_plan_of(ep12))[0] is True     # 1/34×17 = 0.5 → 0
    assert drop_verdict([], bench, trans_plan_of(ep13))[0] is True     # 0.02×15 = 0.3 → 0
    ok, msg = drop_verdict([], bench, trans_plan_of(gimi))             # 비율 출처 없음 — 9a8507108 판(planned 0 → ○)은 통과시켰다
    assert ok is False and "기록 없음" in msg, msg
    assert drop_verdict([], bench, None)[0] is False
    p = trans_plan_of({"log": ["전환 [(3.2, 'zoomblur'), (9.0, 'black')] (벤치 합계 비율 {'zoomblur': 0.1, 'black': 0.07}, 컷 경계 14·붙일 수 있는 8(≥1.2초))"]})
    assert p["picked"] == {"zoomblur": 1, "black": 1} and p["want_raw"]["zoomblur"] == 1.4


def test_transition_step_record_and_verdict():
    from tools.calcopy.hybrid.placement import transitions_step
    from tools.calcopy.hybrid.quality_gate import drop_verdict, trans_plan_of
    bench = [0.175]
    out, cuts = _rows_cuts(1.0)                                     # 컷 1.0초 × 10 — 붙일 수 있는(≥1.2초) 경계 0
    rec = {}
    assert transitions_step(out, _trans_style(0.2), "s", None, cuts, [], rec) == []
    assert rec["src"] and rec["want"] == 2 and rec["want_raw"]["zoomblur"] == 1.8 and rec["eligible"] == 0 and rec["picked"] == {}
    ok, msg = drop_verdict([], bench, trans_plan_of(_tab(rec)))      # 원하는 1.8 → 2 인데 못 고름 = ×
    assert ok is False and "모자라" in msg, msg
    out, cuts = _rows_cuts(2.0)
    rec = {}
    assert len(transitions_step(out, _trans_style(0.2), "s", None, cuts, [], rec)) == 2
    ok, msg = drop_verdict([], bench, trans_plan_of(_tab(rec)))      # 골랐는데 완성본 경계 0 = 그리기 빠짐 ×
    assert ok is False and "그리기 빠짐" in msg, msg
    rec = {}
    transitions_step(out, _trans_style(0.02), "s", None, cuts, [], rec)   # 0.02 × 9 = 0.18 → 0
    assert rec["want"] == 0 and drop_verdict([], bench, trans_plan_of(_tab(rec)))[0] is True
    rec = {}
    transitions_step(out, {"placement": {"rules": {}, "counted": {}}, "frame": {}}, "s", None, cuts, [], rec)   # 비율 출처 없음
    assert rec["src"] is None and drop_verdict([], bench, trans_plan_of(_tab(rec)))[0] is False


def test_check_place_carries_transition_plan():
    from tools.calcopy.hybrid.placement import check_place
    style = {"placement": {"rules": {}, "counted": {"videos": [{"id": "R", "slots": {}, "stickers": {}}]}}}
    plan = {"src": "x", "want": 0, "want_raw": {"zoomblur": 0.3}, "picked": {}}
    r = check_place({"reference": "R", "rows": [], "sfx": [], "trans_plan": plan}, style)
    assert r["slots"]["transitions"]["plan"] == plan


# ---------------------------------------------------------------- ④ 나레 받아쓰기 — ep12 실측 표(계획 N3 12.579 / SM 12.54 / whisper 12.12)
def _ep12():
    return json.loads((FIX / "ep12_narr_sm_words.json").read_text(encoding="utf-8"))


def test_narr_sync_speechmatics_ep12_and_shifted_n3():
    from tools.calcopy.engine.check_line_sync import LIMIT_SM
    from tools.calcopy.hybrid.quality_gate import narr_sync_rows
    F = _ep12()
    rows = {r["line"]: r for r in narr_sync_rows(F["narr"], F["lines"], F["words"]["real"])}
    assert all(r["ok"] for r in rows.values()), rows
    assert rows["N3"]["t0"] == 12.579 and rows["N3"]["heard_t0"] == 12.54
    assert abs(12.579 - 12.12) > LIMIT_SM                           # whisper 12.12 로 판정하면 정상 편이 걸린다 — 위스퍼로 정하지 않는 이유
    for k, heard in (("e0.0", 12.54), ("e0.4", 12.18), ("e0.8", 11.79)):     # N3 소리를 0·0.4·0.8초 앞당긴 합성(진짜 스피치매틱스로 받아씀)
        rs = {r["line"]: r for r in narr_sync_rows(F["narr"], F["lines"], F["words"][k])}
        assert rs["N3"]["heard_t0"] == heard, (k, rs["N3"])
        assert rs["N3"]["ok"] is (k == "e0.0"), (k, rs["N3"])
        assert all(r["ok"] for l, r in rs.items() if l != "N3"), k


def test_gate_narr_row_uses_speechmatics_not_whisper(tmp_path, monkeypatch):
    from tools.calcopy.engine import check_line_sync as LS
    from tools.calcopy.engine import narr_verify as NV
    from tools.calcopy.hybrid.quality_gate import gate
    F = _ep12()
    doc, R = tmp_path / "doc", tmp_path / "work" / "render"
    doc.mkdir(); R.mkdir(parents=True)
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=108x192:r=30:d=1", "-pix_fmt", "yuv420p", R / "final.mp4")
    _ffmpeg("-f", "lavfi", "-i", "sine=f=300:d=29", "-ar", "48000", R / "voice.wav")
    (R / "timeline.json").write_text(json.dumps({"cuts": [], "lines": F["lines"], "end": 28.5}), encoding="utf-8")
    (R / "자막표.json").write_text(json.dumps({"rows": [], "check": {"ok": True, "reference": "x", "worst_slot_diff": 0}}), encoding="utf-8")
    (doc / "대본.json").write_text(json.dumps({"lines": [{**l, "kind": "tts"} for l in F["narr"]]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(LS, "asr_segments", lambda p: [(0.0, 28.0, "위스퍼가 들은 글")])     # 위스퍼는 판정에 안 쓰인다
    calls = []
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": calls.append(p) or F["words"]["e0.4"])

    def narr_row():
        r = gate("잇템로그판", doc, tmp_path / "work", only=("소리",), eye_pack=False, log=lambda *a: None)
        return next(x for x in r["rows"] if x["what"] == "나레 받아쓰기 ↔ 대본")
    row = narr_row()
    assert row["ok"] is False and "N3" in row["value"] and "스피치매틱스" in row["value"], row
    assert calls and Path(calls[0]).name == "voice.wav"
    assert not (R / "voice_narr.wav").exists()                      # 원음 무음 처리본을 더는 안 만든다
    monkeypatch.setattr(NV, "heard_words", lambda p, lang="ko": F["words"]["real"])
    assert narr_row()["ok"] is True

    def boom(p, lang="ko"):
        raise RuntimeError("키 없음")
    monkeypatch.setattr(NV, "heard_words", boom)
    row = narr_row()
    assert row["ok"] is None and "참고(판정 안 함)" in row["value"], row     # 스피치매틱스를 못 쓰면 미측정 — 위스퍼로 ○/× 를 정하지 않는다


# ---------------------------------------------------------------- ⑥ 스티커 모자람 — 10-25 렌더 21판 자막표 실측
ITL = (["circle_arrow", "kk_doodle", "spark_lines"], {"circle_arrow": 0.5, "kk_doodle": 0.333, "other": 0.5, "spark_lines": 0.167})   # 잇템로그판 rules·counted
KIT = (["gem", "spark_lines", "kk_doodle"], {"circle_arrow": 0.25, "spark_lines": 0.375, "kk_doodle": 0.125, "gem": 0.125})          # 키치잇판


def test_sticker_short_against_reference():
    from tools.calcopy.hybrid.placement import sticker_short
    assert sticker_short({"circle_arrow": 1, "spark_lines": 1}, {"circle_arrow": 1, "spark_lines": 1}, *ITL)[0] == []        # ep12_rule
    assert sticker_short({"kk_doodle": 2, "circle_arrow": 1, "other": 1}, {"circle_arrow": 1, "kk_doodle": 2}, *ITL)[0] == []   # ep13_v3
    bad, tab = sticker_short({"kk_doodle": 2, "circle_arrow": 1, "other": 1}, {}, *ITL)                                    # ep13_fit_plan: 하나도 안 붙임
    assert bad and "circle_arrow" in bad[0] and "other" in tab and not any("other" in b for b in bad), (bad, tab)
    assert sticker_short({"circle_arrow": 1, "spark_lines": 1}, {}, *KIT)[0] == []                                         # 박정수 키치잇판(납품 ○) — 강조선은 벤치 8편 중 3편
    assert sticker_short({"circle_arrow": 1}, {}, ITL[0], None)[0]                                                          # 벤치 비율 모르면 그릴 수 있는 종류 전부 필수


def test_check_place_flags_sticker_short():
    from tools.calcopy.hybrid.placement import check_place
    style = {"placement": {"rules": {"stickers": {"circle_arrow": {}}},
                           "counted": {"stickers": {"circle_arrow": 0.5}, "videos": [{"id": "R", "slots": {}, "stickers": {"circle_arrow": 1}}]}}}
    placed = {"reference": "R", "rows": [{"slot": "x", "enter": "cut", "stickers": [], "line": "N1"}], "sfx": []}
    r = check_place(placed, style)
    assert r["ok"] is False and any("circle_arrow" in b for b in r["bad"]), r
    placed["rows"][0]["stickers"] = [{"kind": "circle_arrow"}]
    assert check_place(placed, style)["ok"] is True


# ---------------------------------------------------------------- ② 되감김 경계 — 주인 check_seams.split_by_bounds
def test_seams_bounds_split_owner():
    from tools.calcopy.engine.check_seams import split_by_bounds
    rw = [{"t": 11.3, "되감김_초": 0.233}]                        # ep12_rule 옛 완성본(gate_cache 29101387…) — O2 saA 17~21.36 한 조각 안 빠른 손짓
    bounds = [1.318, 2.839, 5.599, 6.446, 7.292, 8.139, 12.579, 13.85, 15.121]
    assert split_by_bounds(rw, bounds) == ([], rw)
    assert split_by_bounds(rw, None) == (rw, [])                 # 시간표에 컷이 없으면 전부 센다(옛 관문은 빈 경계로 걸러 0개 = 통과였다)
    assert split_by_bounds(rw, []) == (rw, [])
    assert split_by_bounds([{"t": 12.6}], bounds)[0] == [{"t": 12.6}]
