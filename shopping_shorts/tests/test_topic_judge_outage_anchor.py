# -*- coding: utf-8 -*-
"""제품군 판정 AI(Gemini)가 죽었을 때 대본 생성이 통째로 막히던 사고의 회귀 테스트.

실사고 2026-09-25 work 4bd606509402 / job cafa17d6856b (사장님 "이렇게 계속뜬다"):
  · 재료 7편의 제품명이 5가지 표기(손가락 젓가락 / 스낵용 핑거 젓가락 / 3D 프린팅 손가락 젓가락 /
    손가락 칩 집게 / 핑거 젓가락) → 이름 일치로 못 묶어 AI 판정이 필요
  · Gemini 503 → judge_unavailable → 2:2 동률 → ambiguous → 주제 None
  · 고른 씨앗(이븐쇼핑 3VRdQWiPTXY)은 화면 재료에서 빠져(useFootage=false) job에 없다 → 선택 카드로도 못 붙임
  · → 422 "영상 자료 판정 응답을 검증하지 못했습니다" 가 6번 연속.

그런데 이 작업은 **직전 생성에서 이미 '손가락 젓가락'으로 주제를 확정**해 화면에 "고정 주제 손가락 젓가락"
을 보여주고 있었다. 그 확정값은 이 작업의 저장 상태(s2.materials.topic_product)에 있다 — 판정 AI가
없을 때는 그것을 정본으로 쓴다(임의 합의가 아니라 **이 작업이 이미 확정한 값**이다).
"""
import pytest

from shopping_shorts import topic_contract
from shopping_shorts import app as app_mod


def _source(sid, product, scene, full_text):
    return {"source_id": sid, "full_text": full_text,
            "source_brief": {"product": product},
            "segments": [{"seg_id": "%s-0" % sid, "scene_desc": scene}]}


FINGER_SOURCES = [
    _source("s0", "손가락 젓가락", "손가락에 젓가락을 끼워 과자를 집는다", "손가락 젓가락으로 과자를 집습니다."),
    _source("s1", "손가락 젓가락", "젓가락을 손가락에 장착한다", "손가락에 끼우고 집기만 하면 됩니다."),
    _source("s2", "스낵용 핑거 젓가락", "치토스를 집는 손", "치토스 가루가 손에 안 묻어요."),
    _source("s3", "스낵용 핑거 젓가락", "키보드 옆에서 과자를 집는다", "게임하면서 과자를 먹습니다."),
    _source("s4", "3D 프린팅 손가락 젓가락", "3D 프린터로 출력한 집게", "3D 프린터로 만든 손가락 젓가락입니다."),
    _source("s5", "손가락 칩 집게", "칩을 집는 집게", "칩 집게로 과자를 집습니다."),
    _source("s6", "핑거 젓가락", "손가락에 끼운 젓가락", "핑거 젓가락입니다."),
]


class _Store:
    def __init__(self, saved_topic):
        self.job = {"customer_id": 0, "extract": {s["source_id"]: s for s in FINGER_SOURCES}}
        self.saved_topic = saved_topic

    def get_mix_job(self, _jid):
        return self.job

    def get_produce_work(self, _wid, customer_id=0):
        mat = {"topic_product": self.saved_topic, "topic_explicit": False} if self.saved_topic else {}
        return {"job_id": "job", "state": {"s2": {"materials": mat}}}


@pytest.fixture
def judge_down(monkeypatch):
    def unavailable(_rows):
        raise RuntimeError("503 UNAVAILABLE")
    topic_contract._RESOLUTION_CACHE.clear()
    monkeypatch.setattr(topic_contract, "_judge_membership", unavailable)
    monkeypatch.setattr(app_mod, "_facts_block_for_job", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_sul_block_for_sources", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_wow_block_for", lambda *_a, **_k: "")
    yield
    topic_contract._RESOLUTION_CACHE.clear()


# 고른 씨앗은 job 밖의 영상이다(이븐쇼핑 원문) — 재료 어느 편과도 원문이 같지 않다.
SEED_ITEM = {"structure": {}, "category": "",
             "full_text": "미국 천재가 만들어 떼돈번 제품의 정체 최근 원래는 젓가락질을 못하는 서양인들을 위해"}
BODY = {"work_id": "work", "job_id": "job", "selected_shortcode": "3VRdQWiPTXY"}


def test_real_case_is_tied_and_unresolved_when_judge_is_down(judge_down):
    rows = [dict(s) for s in FINGER_SOURCES]
    r = topic_contract.resolve_membership(rows)
    assert r["method"] == "unresolved" and r["error"] == "judge_unavailable"
    assert r["ambiguous"] is True and r["product"] == ""


def test_saved_work_topic_anchors_materials_when_judge_is_down(judge_down):
    """이 작업이 이미 확정한 주제가 있으면 판정 AI 없이도 그 제품군 재료로 생성한다."""
    kept, *_ = app_mod._materials_for_generate(SEED_ITEM, dict(BODY), _Store("손가락 젓가락"), 0)
    assert kept, "재료가 있는데 0편이면 생성이 막힌다"
    # 씨앗 항목(3VRdQWiPTXY)은 종전대로 함께 실린다 — job 재료는 확정 주제 그룹(s0·s1)만.
    job_ids = {s["source_id"] for s in kept if s.get("source_id", "").startswith("s")}
    assert job_ids == {"s0", "s1"}
    assert all(s["topic_product"] == "손가락 젓가락" for s in kept if s.get("source_id"))


def test_saved_topic_matching_no_group_does_not_invent_one(judge_down):
    """저장된 주제가 지금 재료 어느 그룹과도 안 맞으면(재료를 다 바꿨다) 억지로 고르지 않는다."""
    with pytest.raises(ValueError):
        app_mod._materials_for_generate(SEED_ITEM, dict(BODY), _Store("접이식 선반"), 0)


def test_first_generation_without_saved_topic_says_ai_outage_not_validation(judge_down):
    """처음 생성이라 확정 주제가 없으면 막히되, 문구는 진짜 원인(AI 과부하)을 말한다.
    종전 문구 "영상 자료 판정 응답을 검증하지 못했습니다"는 사용자가 뭘 해야 할지 알 수 없었다."""
    with pytest.raises(ValueError) as e:
        app_mod._materials_for_generate(SEED_ITEM, dict(BODY), _Store(""), 0)
    msg = str(e.value)
    assert "과부하" in msg or "503" in msg
    assert "검증하지 못했습니다" not in msg
