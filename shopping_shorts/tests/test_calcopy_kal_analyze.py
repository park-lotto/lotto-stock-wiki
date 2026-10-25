# -*- coding: utf-8 -*-
"""칼카피 분석 도구 kal_analyze 시험 (관제 097, 2026-10-20).
판단 주인: check_doc(줄판독 칸 검사) · rules_of(붙는 조건 규칙+빈도) · match_table(재현일치도 자·합격선 MATCH_RULES).
사보타주 시험이 들어 있다 — 검사기가 아무것도 안 잡으면 거짓 통과(0순위-A1c)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import kal_analyze as K  # noqa: E402


def _line(t0, t1, speaker="나레", text="가나다라", enter="instant", emph=None, sticker=None, sfx=None, role=None):
    d = {"t0": t0, "t1": t1, "speaker": speaker, "text": text, "layer": "채널", "enter": enter,
         "y": [1100, 1160], "fill_hex": "#FFFFFF", "emph": emph or [], "sticker": sticker or [], "sfx": sfx,
         "scene": "얼굴", "cut_at": [], "transition": "cut"}
    if role:
        d["role"] = role
    return d


def _doc(id_="v1", dur=10.0, lines=None, title="차예련 비빔국수"):
    return {"id": id_, "dur": dur, "title_lines": [{"text": title, "colors": []}], "source_label": "출처: 차장금",
            "layout": {"window": [0, 483, 1080, 1541]}, "lines": lines if lines is not None else [
                _line(0.0, 2.0, "원음:차예련", "맛있어", "instant"),
                _line(2.1, 4.0, "나레", "비빔국수가 있다는데", "typing", emph=[{"word": "비빔국수", "hex": "#FF0000"}]),
                _line(4.1, 6.0, "원음:차예련", "이렇게 비벼요", "instant"),
                _line(8.6, 9.8, "원음:차예련", "눈물 나는 맛", "instant", sticker=[{"what": "하트", "t_in": 8.7}], sfx="띵 8.7"),   # 85% 이후 = 끝
            ], "beats": "훅→나레→본문→끝", "narr_share": "1/4", "notes": [],
            "frame0": {"what": "얼굴+글", "text": "맛있어"}}       # 표준 §4-1 thumb.frame0 칸(관제 263 04)


# ---------- check_doc ----------
def test_check_good_doc_has_no_errors():
    r = K.check_doc(_doc())
    assert r["errors"] == [], r


def test_check_catches_missing_decor_fields():
    d = _doc()
    del d["lines"][2]["sticker"]
    del d["lines"][2]["sfx"]
    r = K.check_doc(d)
    assert any("sticker" in e for e in r["errors"]) and any("sfx" in e for e in r["errors"]), r


def test_check_catches_name_without_screen_evidence():
    d = _doc(title="비빔국수 레시피")          # 제목·출처·본문 어디에도 '차예련' 글자 없음
    r = K.check_doc(d)
    assert any("이름 근거" in e for e in r["errors"]), r


def test_check_catches_time_overlap_and_order():
    d = _doc()
    d["lines"][1]["t0"] = 1.0                   # 0~2.0 원음과 1.0~4.0 나레가 같은 층에서 겹침
    r = K.check_doc(d)
    assert any("겹침" in e for e in r["errors"]), r
    d2 = _doc()
    d2["lines"][1]["t1"] = d2["lines"][1]["t0"]  # 길이 0
    assert any("t1" in e for e in K.check_doc(d2)["errors"])


def test_check_role_vocab_and_strict():
    d = _doc()
    d["lines"][0]["role"] = "아무말"
    r = K.check_doc(d)
    assert any("role" in e for e in r["errors"]), r
    r2 = K.check_doc(_doc(), strict=True)       # role 없는 줄은 strict 에서만 오류
    assert any("role" in e for e in r2["errors"])
    assert not any("role" in e for e in K.check_doc(_doc())["errors"])


# ---------- rules_of ----------
def test_rules_denominators_and_rates():
    docs = [_doc("a"), _doc("b")]
    R = K.rules_of(docs)
    sp = R["by_speaker"]
    assert sp["나레"]["n"] == 2 and sp["원음"]["n"] == 6
    assert sp["나레"]["enter"]["typing"] == 2 and sp["원음"]["enter"]["instant"] == 6
    assert sp["나레"]["emph"] == 2 and sp["원음"]["sticker"] == 2 and sp["원음"]["sfx"] == 2
    # 꾸밈 없는 줄 = 원음 2·3번째 줄(instant·emph 없음·스티커 없음·sfx 없음) → 편마다 2
    assert R["plain"]["n"] == 4 and R["plain"]["denom"] == 8
    # 편 표
    ep = {e["id"]: e for e in R["episodes"]}
    assert ep["a"]["lines"] == 4 and ep["a"]["narr_lines"] == 1
    # 규칙 후보: 분모 5 미만은 '표본 부족'
    cand = {(c["cond"], c["effect"]): c for c in R["rules"]}
    assert cand[("화자=원음", "enter=instant")]["grade"] == "강"
    assert cand[("화자=나레", "enter=typing")]["grade"] == "표본부족"


def test_rules_position_buckets():
    R = K.rules_of([_doc()])
    pos = R["by_pos"]
    assert pos["훅"]["n"] >= 1 and pos["끝"]["n"] >= 1


# ---------- match_table ----------
def _ours(dur=10.0):
    return {"rows": [
        {"line": "O1", "t0": 0.0, "t1": 2.0, "text": "맛있어", "speaker": "원음(성시경)", "enter": "instant", "emph": [], "sticker": []},
        {"line": "N1", "t0": 2.1, "t1": 4.0, "text": "비빔국수가 있다는데", "speaker": "나레", "enter": "typing",
         "emph": [{"word": "비빔국수"}], "sticker": []},
        {"line": "B1", "t0": 4.1, "t1": 6.0, "text": "이렇게 비벼요", "speaker": "원음(성시경)", "enter": "instant", "emph": [], "sticker": []},
        {"line": "B2", "t0": 8.6, "t1": 9.8, "text": "눈물 나는 맛", "speaker": "원음(성시경)", "enter": "instant", "emph": [],
         "sticker": [{"what": "하트"}]},
    ], "sfx_in_video": [{"t": 8.7, "file": "ding.wav"}], "dur": dur,
        "transition_rate": {"cut": 1.0}, "frame0_kind": "card"}   # 표준 §4-1 추가 칸(관제 263 04) — 렌더 기록에서 match_from_render 가 채우는 값


def test_match_same_numbers_pass_and_sabotage_fail():
    bench = [_doc("a"), _doc("b", dur=10.5)]
    T = K.match_table(bench, _ours(10.5), ours_media={"duration": 10.5, "cut_median": 1.5, "lufs": -19.0},
                      bench_media={"cut_median": [1.5, 1.6], "lufs": [-19.4, -18.8]})
    assert T["verdict"] == "통과", [r for r in T["rows"] if r["judge"] != "in"]
    # 사보타주 ①: 길이 30% 길게
    T2 = K.match_table(bench, _ours(14.0), ours_media={"duration": 14.0, "cut_median": 1.5, "lufs": -19.0},
                       bench_media={"cut_median": [1.5, 1.6], "lufs": [-19.4]})
    assert T2["verdict"] == "미달" and any(r["key"] == "len.duration" and r["judge"] == "out" for r in T2["rows"])
    # 사보타주 ②: 우리 나레 줄에 전부 효과를 빼면 효과 붙은 줄 비율이 어긋난다
    o = _ours(10.5)
    o["rows"][1]["enter"] = "instant"
    o["rows"][1]["emph"] = []
    T3 = K.match_table(bench, o, ours_media={"duration": 10.5, "cut_median": 1.5, "lufs": -19.0},
                       bench_media={"cut_median": [1.5], "lufs": [-19.4]})
    assert any(r["key"] == "fx.rate.나레" and r["judge"] == "out" for r in T3["rows"]), T3["rows"]
    # 사보타주 ③: 컷이 벤치보다 2배 빠르면 미달(정신없음 쪽)
    T4 = K.match_table(bench, _ours(10.5), ours_media={"duration": 10.5, "cut_median": 0.7, "lufs": -19.0},
                       bench_media={"cut_median": [1.5, 1.6], "lufs": [-19.4]})
    assert any(r["key"] == "cut.median" and r["judge"] == "out" for r in T4["rows"])


def test_match_missing_media_is_not_pass():
    bench = [_doc("a")]
    T = K.match_table(bench, _ours(10.0), ours_media=None, bench_media=None)
    assert T["verdict"] == "미달" and any(r["judge"] == "failed" for r in T["rows"])


def test_skeleton_from_tteutgi_and_vtt(tmp_path):
    tt = {"probe": {"duration": 8.0, "fps": 30, "w": 1080, "h": 1920},
          "layout": {"window": [0, 483, 1080, 1058], "caption_band": [1103, 1179]},
          "captions": {"items": [{"t0": 0.0, "t1": 1.0, "text": ["맛있어"], "top_y": 1110},
                                 {"t0": 2.0, "t1": 3.5, "text": ["비빔국수가 있다는데"], "top_y": 1112}]},
          "cuts": {"times": [2.4, 5.0]}}
    vtt = tmp_path / "x.ko.vtt"
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n맛있어\n\n00:00:02.000 --> 00:00:03.500\n비빔국수가 있다는데\n", encoding="utf-8")
    d = K.skeleton("vid1", tt, vtt=str(vtt))
    assert d["id"] == "vid1" and len(d["lines"]) == 2
    l0 = d["lines"][0]
    for k in K.LINE_REQUIRED:
        assert k in l0, k
    assert l0["speaker"] is None and l0["enter"] is None and l0["cut_at"] == []   # 컷 2.4 는 줄0(0~1) 밖
    assert d["lines"][1]["cut_at"] == [2.4]
    assert d["_todo"]
    r = K.check_doc(d)
    assert any("미기입" in e for e in r["errors"])  # 뼈대는 그대로 통과하지 않는다


# ---------- kal.py 한 입구(상태·건너뛰기·사람 단계 멈춤) ----------
def test_kal_run_skips_done_and_stops_at_waiting_human(tmp_path, monkeypatch):
    from tools.calcopy.engine import kal
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    calls = []

    def ok(S):
        calls.append("ok"); return "done", {"x": 1}, "됨"

    def human(S):
        calls.append("human"); return "waiting_human", {}, "사람"
    monkeypatch.setattr(kal, "RUN", {"select": ok, "collect": ok, "tteutgi": human, "frames": ok})
    monkeypatch.setattr(kal, "STEPS", ["select", "collect", "tteutgi", "frames"])
    S = kal.State("t", "@t", None, 2, None)
    S.save()
    kal.run(S, log=lambda *a: None)
    assert calls == ["ok", "ok", "human"]                  # frames 는 안 돈다
    assert S.d["steps"]["tteutgi"]["state"] == "waiting_human"
    calls.clear()
    S2 = kal.State("t", "@t", None, 2, None)                 # 다시 실행 → 끝난 단계 건너뜀, 사람 단계부터
    kal.run(S2, log=lambda *a: None)
    assert calls == ["human"]
    monkeypatch.setattr(kal, "RUN", {"select": ok, "collect": ok, "tteutgi": ok, "frames": ok})
    calls.clear()
    kal.run(kal.State("t", "@t", None, 2, None), log=lambda *a: None)
    assert calls == ["ok", "ok"] and json.loads((tmp_path / "channel/t/kal_state.json").read_text(encoding="utf-8"))["steps"]["frames"]["state"] == "done"


def test_script_endings_and_palette():
    docs = [_doc("a")]
    docs[0]["lines"][1]["text"] = "비빔국수가 있다는데..?"
    Sc = K.script_of(docs)
    assert Sc["나레"]["endings"][0]["ending"] == "다는데" and Sc["나레"]["report_rate"] == 1.0 and Sc["나레"]["question_rate"] == 1.0
    P = K.palette_of(docs)
    assert P["roles"]["본문"][0]["hex"] == "#FFFFFF" and P["roles"]["본문"][0]["n_docs"] == 1
    assert P["roles"]["강조"][0]["hex"] == "#FF0000"
