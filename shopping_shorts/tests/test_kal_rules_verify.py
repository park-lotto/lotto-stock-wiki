"""kal 규칙·검증 칸 — 개정안 kal v2 채택(관제 319, 11-06).
rules-05 형식 · rules-09 박자 % · rules-11 끝맺음 꼴 · rules-12 자리별 어미 · rules-18 층별 · rules-25 제목 통계
readlines-08 어두운 배경 외곽선 판별 불가 · readlines-09·11 받아쓰기 자 · skeleton-01 낱말·음량 열
verify-m01 채널명 · verify-14 개인정보 유도 · apply-08 제목 꼴 · apply-15 장면표
"""
import json
from pathlib import Path

from tools.calcopy.engine import kal_analyze as K


def _doc(i, form=None, lines=None, dur=20.0, title=None):
    return {"id": i, "dur": dur, "form": form, "title_lines": title or [], "lines": lines or [
        {"t0": 0.0, "t1": 2.0, "speaker": "나레", "text": "이거 진짜 몰랐는데", "role": "훅", "layer": "채널", "enter": "instant", "emph": [], "sticker": [], "sfx": None},
        {"t0": 2.0, "t1": 4.0, "speaker": "나레", "text": "알고 보니 대박이었다", "role": "본문", "layer": "채널", "enter": "instant", "emph": [], "sticker": [], "sfx": None},
        {"t0": 2.2, "t1": 3.5, "speaker": "나레", "text": "대박이었다", "role": None, "layer": "효과", "enter": "pop", "emph": [], "sticker": [], "sfx": None, "y": [555, 600]},
        {"t0": 14.0, "t1": 16.0, "speaker": "나레", "text": "반전은 여기서", "role": "반전", "layer": "채널", "enter": "instant", "emph": [], "sticker": [], "sfx": None},
        {"t0": 17.0, "t1": 18.0, "speaker": "나레", "text": "구독 눌러줘요", "role": "끝", "layer": "채널", "enter": "instant", "emph": [], "sticker": [], "sfx": None}]}


def test_rules_05_09_18_form_beats_layers():
    R = K.rules_of([_doc("a", "리액션"), _doc("b", "리액션", dur=40.0), _doc("c", "정보", dur=10.0)])
    assert R["by_form"]["리액션"] == {"n": 2, "min": 20.0, "max": 40.0}
    assert R["beat_pos"]["반전"]["med_pct"] == 70.0 and R["tail_s"]["med"] == 2.0
    assert R["by_layer"]["효과"]["repeat_rate"] == 1.0 and R["by_layer"]["효과"]["y_med"] == 555


def test_rules_11_12_25_script_flow_end_title():
    Sc = K.script_of([_doc("a", title=[{"text": "이거 몰랐지?"}]), _doc("b", title=[{"text": "대박 3가지"}])])
    assert Sc["_end_forms"]["mode"] == "구독CTA" and Sc["_end_forms"]["cta_rate"] == 1.0
    assert "훅" in Sc["나레"]["endings_by_pos"] and Sc["나레"]["connect_vs_close"]
    assert Sc["_title_stats"]["n"] == 2 and Sc["_title_stats"]["question_rate"] == 0.5
    assert K.end_form(["그래서 결국 이렇다", "어떻게 생각해?"])["form"] == "질문"
    assert K.end_form(["다음 편에서 계속"])["teaser"]


def test_readlines_09_11_asr_stats_and_match_rows():
    asr = [{"start": 0.5, "end": 2.0, "text": "안녕하세요"}, {"start": 4.0, "end": 5.0, "text": "반가워요"}]
    a = K.asr_stats(asr)
    assert a["speech.gap"] == 1 and a["first.land"] == 2.0 and a["speech.cps.asr"] == round(9 / 2.5, 2)
    assert K.asr_stats(None)["speech.cps.asr"] is None
    d = _doc("a")
    d["_asr"] = asr
    T = K.match_table([d], {"lines": _doc("o")["lines"], "dur": 20.0, "_asr": asr}, {}, {})
    rows = {r["key"]: r for r in T["rows"]}
    assert rows["speech.gap"]["judge"] == "in" and rows["first.land"]["judge"] == "in" and rows["end.form"]["judge"] == "in"
    assert not rows["speech.cps.asr"]["core"]


def test_readlines_08_dark_bg_outline():
    assert K.outline_of("#000000", 30.0)["outline"] == "판별 불가" and K.outline_of("#000000", 30.0)["outline_hex"] is None
    assert K.outline_of("#101010", 200.0)["outline_hex"] == "#101010"


def test_skeleton_01_words_loud():
    tt = {"probe": {"duration": 2.0}, "captions": {"items": [{"t0": 0.0, "t1": 1.0, "text": ["안녕"]}]},
          "audio": {"transcript": {"words": [{"start": 0.1, "end": 0.4, "text": "안녕"}, {"start": 1.5, "end": 1.8, "text": "밖"}]}}}
    d = K.skeleton("v", tt, None, loud=[-20.0, -21.0, -30.0, -40.0, -50.0, -60.0, -70.0, -80.0])
    assert d["lines"][0]["words"] == [{"t0": 0.1, "t1": 0.4, "text": "안녕"}]
    assert d["lines"][0]["loud"] == [-20.0, -21.0, -30.0, -40.0] and "form" in d["_todo"]


def test_verify_m01_name_check():
    bad = K.name_check(["오늘은 이븐 쇼핑 추천", "빌딩리포터였습니다"], ["이븐쇼핑"], "빌딩리포트")
    assert any("이븐쇼핑" in b for b in bad) and any("리포터" in b for b in bad)
    assert K.name_check(["빌딩리포트였습니다"], ["이븐쇼핑"], "빌딩리포트") == []


def test_verify_14_hygiene():
    assert K.text_hygiene(["생년월일 댓글로 적어주세요"])
    assert not K.text_hygiene(["몇 년생인지 댓글로"])
    assert not K.text_hygiene(["생년월일은 중요해요"])


def test_apply_08_title_of():
    t = K.title_of([{"title": "\"진짜?\" 3초 만에 끝", "views": 10}, {"title": "이거 왜 몰랐지?", "views": 99}])
    assert t["top"][0]["views"] == 99 and t["number_rate"] == 0.5 and t["question_rate"] == 1.0 and t["quote_rate"] == 0.5


def test_apply_15_scene_table(tmp_path):
    (tmp_path / "timeline.json").write_text(json.dumps({"groups": [{"src": "a.mp4", "ss": 1.0, "dur": 1.5, "t0": 0.0}, {"src": "b.mp4", "ss": 0, "dur": 1.0, "t0": 1.5}],
                                                         "pieces": [{"text": "가", "t0": 0.0, "t1": 1.5}]}), encoding="utf-8")
    md, empty = K.scene_table(tmp_path)
    assert md.count("\n| ")== 2 and empty == ["#2 자막·나레"]
