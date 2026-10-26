# -*- coding: utf-8 -*-
"""고치기 안내·한도(사장님 10-26 "고치기 한도는 계속 다듬어야 된다. 고객도 반려가 이해될 수 있게").

① 반려 원인 → 회원 쉬운 말 사전(REDO_WHY) 전부가 member_ok 통과 + 규칙 이름·수치·파일이 없다.
② 대본 반려 진행 줄 = '대본 쓰기 중 — 다시 쓰는 중(n/6): <쉬운 말>' · reject 칸에도 속사정(JSON·kind) 없음.
③ 같은 원인 묶음 REDO_STUCK(3)번 연속이면 한도 전에 멈추고, 멈춤 문구가 무엇이 안 맞았는지 쉬운 말로 말한다.
④ 원인이 바뀌어 가는 중(하나씩 풀리는 중)이면 계속 · 한도를 넘으면 무엇이 끝내 안 맞았는지 말하며 멈춘다.
⑤ 사전에 없는 원인 = 일반 문구 + 경보 기록(조용히 넘어가지 않는다).
⑥ 다른 단계로 넘어가면 '다시 …' 꼬리가 사라진다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

INNER = re.compile(r"[a-z_]{3,}|\d+\.\d|cps|TTS|json|\.py|규칙|관문|재료|검사|판정|렌더")


def _st(phase="script_got"):
    return {"sid": "t", "version": "키치잇판", "fmt": "연예인형", "phase": phase, "tries": {}, "log": []}


def test_every_redo_word_is_member_friendly():
    assert len(F.REDO_WHY) >= 30
    for k, (say, name) in list(F.REDO_WHY.items()) + [("_", F.REDO_GENERIC)]:
        assert F.member_ok(say) and F.member_ok(name), k
        assert not INNER.search(say) and not INNER.search(name), (k, say, name)
    for causes in (["est_length_short"], ["boundary", "text_left"], [], ["plan_other"]):
        for stuck in (False, True):
            w, f = F.redo_stop_words(causes, stuck)
            assert F.member_ok(w) and F.member_ok(f, need_next=True), (w, f)


def test_checker_would_catch_bad_word():
    """사보타주: 사전에 내부 용어가 들어가면 ①이 잡는다."""
    old = F.REDO_WHY["cap_chars"]
    F.REDO_WHY["cap_chars"] = ("cap_chars 9자 넘음", "자막")
    try:
        with pytest.raises(AssertionError):
            test_every_redo_word_is_member_friendly()
    finally:
        F.REDO_WHY["cap_chars"] = old


AUDIT_SHORT = {"ok": False, "rules": [{"kind": "ending", "ok": True, "why": "x"},
                                      {"kind": "est_length", "ok": False, "why": "어림 길이 23.4초 (26~31, 렌더 뒤 다시 잰다)"},
                                      {"kind": "cap_chars", "ok": False, "why": "자막 덩어리 9자 넘음 [('L6', '얼마나 생기 있어 보이는지')]"}],
               "title": ["제목 1줄 'x' 에 'hi'"]}


def test_script_causes_from_audit():
    assert F._script_causes(AUDIT_SHORT) == ["est_length_short", "cap_chars", "title"]
    long = {"rules": [{"kind": "est_length", "ok": False, "why": "어림 길이 34.0초 (26~31, 렌더 뒤)"}]}
    assert F._script_causes(long) == ["est_length_long"]
    assert F._script_causes({"rules": [{"kind": "text:english", "ok": False}], "error": "꼴"}) == ["text:english", "form"]


def test_script_reject_line_says_try_and_reason(monkeypatch):
    st = _st()
    st["version"] = "v"
    monkeypatch.setattr(F, "_reply", lambda rp, rid, need=(): {"대본": {}, "재료": {}})
    monkeypatch.setattr(F, "_prep_material", lambda st, S, M: M)
    monkeypatch.setattr(F, "audit_script", lambda st, S, M: dict(AUDIT_SHORT))
    monkeypatch.setattr(F, "_script_ask", lambda st, why="": {"id": "script_v", "ask": why})
    monkeypatch.setattr(F, "_fmt", lambda st: "연예인형")
    r = F.ph_script_got(st, {}, {}, {})
    res = F._out(st, "reject", "script_got", review=r["review"], reject=r["reject"])
    assert res["message"].endswith("다시 쓰는 중(1/6): 영상이 기준보다 짧아요"), res["message"]
    assert F.member_ok(res["message"]) and not INNER.search(res["reject"]["why"])
    assert "est_length" in res["review"][0]["ask"]              # 회원 Claude 에게는 속사정 그대로
    assert any("est_length" in x for x in st["log"])


def test_same_cause_three_in_a_row_stops_early_with_reason():
    st = _st()
    F._tries(st, "script", 6, ["ending", "title"])
    F._tries(st, "script", 6, ["ending", "title"])        # 2연속 = 아직 계속(로그에서 2연속은 두 번 다 다음 바퀴에 풀렸다)
    with pytest.raises(F._Stop) as e:
        F._tries(st, "script", 6, ["ending", "title"])
    assert st["tries"]["script"] == 3 < F.LIMITS["script"]
    assert "문장 말끝·제목 색이" in e.value.why and "같은 곳" in e.value.why and F.member_ok(e.value.fix, need_next=True)


def test_changing_causes_keep_going_then_limit_names_cause():
    st = _st()
    seq = [["count", "tts_cps_spread", "title"], ["title"], ["tts_cps_spread"], ["title"], ["ending", "title"], ["ending", "title"]]
    for cs in seq:                                          # 회원 마스크편 첫 바퀴 그대로 — 6번까지 멈추지 않는다(7번째에 통과했다)
        F._tries(st, "script", F.LIMITS["script"], cs)
    with pytest.raises(F._Stop) as e:
        F._tries(st, "script", F.LIMITS["script"], ["cap_chars"])
    assert e.value.why == "여러 번 고쳐 봤지만 자막 길이가 끝내 안 맞았어요"


def test_unknown_cause_generic_and_alarm():
    st = _st("plan_look")
    F._tries(st, "plan", 8, F._plan_causes(["아무도 모르는 이유"]))
    assert st["_redo"]["say"] == F.REDO_GENERIC[0]
    assert any(x.startswith("경보: 회원 문구 없는 반려 원인") for x in st["log"])


def test_plan_causes_map_engine_words():
    got = F._plan_causes(["컷 경계 L8 bOEp.mp4 ss=1.20~2.10 안 원본 장면 경계 [1.53]초 → 짧은 조각 [0.33]초(<0.4)",
                          "컷 6 L4 A.mp4@0.30: 흐림 밖 남의 박힌 글자 1/3장",
                          "계획에서 컷이 원본 샷보다 길다: [('L1', …)]", "진짜 컷 중앙 1.98초 > 판 cut_median"])
    assert got == ["boundary", "text_left", "cut_len", "rhythm"]


def test_tail_goes_away_on_next_stage():
    st = _st("plan_look")
    F._out(st, "execute", "plan")
    F._tries(st, "plan", 8, ["boundary"])
    m = F._out(st, "review", "plan_look")["message"]
    assert m == "장면 맞추기 중 — 장면 다시 맞추는 중(1/8): 장면이 바뀌는 곳에 컷 경계를 맞추는 중이에요", m
    m2 = F._out(st, "execute", "render")["message"]
    assert "다시" not in m2 and "_redo" not in st


# 사장님 10-26(강함) "고객한테 영상 만드는 어떤 요구도 하지 마라" — 해결 줄 = 숏템이 하는 일 · 끝내 안 되면 '다시 시도'만.
# 예외 = 첫 제작 요청 준비 점검(1/13 준비 확인)뿐 — 빠진 키·계정 연결·저장 공간을 거기서 한 번에(사장님 10-26, 주인 runner_ops.need_list → flow.setup_fix).
# 제작 도중(영상 받기 실패·유튜브 막힘 등)엔 '주소 확인·로그인 연결 확인' 같은 요구도 없다.
ASK_CUSTOMER = re.compile(r"주소|알려|이름을|적어|골라|갈까요|피드백|다른 소재|다른 영상|넣어 주시면|확인해 주세요|로그인|연결")
SETTING_ONLY = ("이 PC 준비가 아직 덜 됐어요",)       # 준비 점검 자체가 실패(실행 도구 오류) — 그 밖 준비 문구는 SETUP_WHY(변수)라 여기 안 잡힌다


def test_no_stop_asks_customer_to_make_anything():
    from shopping_shorts.tests.test_member_words import member_texts
    texts = member_texts()
    assert len(texts) >= 40
    bad = [(ln, w, f) for ln, w, f in texts if ASK_CUSTOMER.search(f or "") and not str(w).startswith(SETTING_ONLY)]
    assert not bad, bad
    for w, f in (F.NO_SIMILAR, F.NO_ORIGIN):
        assert not ASK_CUSTOMER.search(f), f
    assert not ASK_CUSTOMER.search(F.member_stop("x{", "y")[1])


def test_ask_checker_catches_old_words():
    """사보타주: 옛 문구(10-26 전)는 걸린다."""
    for f in ("원본 영상 주소를 주시면 바로 만들 수 있어요 · 다른 소재로 갈까요?", "제품 이름을 알려 주시면 그 이름으로 찾아 이어 갈게요",
              "다른 소재 영상을 주세요", "숏템 피드백으로 알려 주시면 확인해 드릴게요",
              "영상 주소가 맞는지, 유튜브 로그인 연결이 되어 있는지 확인해 주세요", "잠시 뒤 다시 시도해 주시면 이어서 찾을게요 · 유튜브 로그인 연결도 확인해 주세요"):
        assert ASK_CUSTOMER.search(f), f
