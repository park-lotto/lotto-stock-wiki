"""부품은행 Phase0 T2 — 8버킷 추출 모듈(TDD). 실제 Gemini 호출 금지: 가짜 call 주입.

스타일 버킷(hook/ending/adverb/cta/price)=리터럴 문구, 내용 버킷(evidence/conflict/
emotion)=슬롯 템플릿(slot_role='template'). ingest_script는 소스 1행 + 부품 N행(pending).
"""
import pytest
from shopping_shorts import pattern_bank
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


FAKE = {
    "hook": ["이거 모르면 손해예요", "99%가 모르는 방법"],
    "ending": ["~하더라고요", "~거든요"],
    "adverb": ["진짜", "완전"],
    "cta": ["댓글로 알려주세요"],
    "price": ["단돈 5천원"],
    "evidence": ["{인물}이 {행위}하니 {결과}가 나왔다"],
    "conflict": ["{인물}이 {문제}로 곤란해하다"],
    "emotion": ["{인물}이 {반응}하며 놀라다"],
    "spine": {"situation_type": "문제해결", "beat_chain": ["훅", "문제", "해결"],
              "emotion_arc": "불안→안도", "appeal": "손실회피"},
}


def fake_call(prompt, schema):
    return FAKE


def test_extract_buckets_with_fake_call():
    out = pattern_bank.extract_buckets("아무 대본 텍스트", call=fake_call)
    assert out["hook"] == FAKE["hook"]
    assert out["evidence"] == FAKE["evidence"]
    assert out["spine"]["situation_type"] == "문제해결"


def test_extract_buckets_empty_text_returns_empty():
    assert pattern_bank.extract_buckets("", call=fake_call) == {}


def test_extract_buckets_failed_call_returns_empty():
    assert pattern_bank.extract_buckets("대본", call=lambda p, s: None) == {}


def test_ingest_script(store):
    res = pattern_bank.ingest_script(store, "대본 전문", source="ig",
                                     url="http://x", product_category="홈템",
                                     call=fake_call)
    assert res["source_id"] is not None
    # 스타일 2+2+2+1+1=8 + 내용 1+1+1=3 = 11
    assert res["added"] == 11
    items = store.list_pattern_items(limit=500)
    assert len(items) == 11
    assert all(it["status"] == "pending" for it in items)
    # 내용 버킷은 slot_role='template'
    ev = store.list_pattern_items(bucket="evidence")
    assert ev[0]["slot_role"] == "template"
    # 스타일 버킷은 slot_role 없음(리터럴)
    hooks = store.list_pattern_items(bucket="hook")
    assert hooks[0]["slot_role"] is None
    # 모든 부품이 이 소스에 귀속
    assert all(res["source_id"] in it["source_ids"] for it in items)


def test_ingest_script_empty_extract(store):
    res = pattern_bank.ingest_script(store, "대본", call=lambda p, s: {})
    assert res == {"source_id": None, "added": 0}
    assert store.list_pattern_items() == []


def test_ingest_negative(store):
    iid = pattern_bank.ingest_negative(store, "확인하셨어요", "cta")
    assert isinstance(iid, int)
    negs = store.list_pattern_items(bucket="cta", is_negative=1)
    assert len(negs) == 1
    assert negs[0]["is_negative"] == 1
    # 네거티브는 일반 목록(is_negative=0)에 안 뜬다
    assert store.list_pattern_items(bucket="cta", is_negative=0) == []
