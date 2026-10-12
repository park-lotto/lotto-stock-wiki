# -*- coding: utf-8 -*-
"""자막제거 결과를 쓸지 말지 — '원본으로 되돌리기' 취소 버튼(2026-09-20 이윤정 고객 요청).

이 기능의 값어치는 **되돌려도 돈이 안 나간다**는 데 있다. 그래서 여기서 지키는 것은
'토글이 된다'가 아니라 **청소 결과가 살아남는가**다 — 지워지면 되살릴 때 VMake를
다시 불러 과금된다. 그 불변식을 테스트로 박아 둔다.
"""
import json

import pytest

from shopping_shorts import app as A
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(A, "DB_PATH", str(db))
    return Store(str(db))


def _mkjob(store, job_id="J1", cid=7, *, cleaned=True):
    store.create_mix_job(job_id, ["http://x/1"], 30, "hook", subtitle_removal=True,
                         customer_id=cid)
    if cleaned:
        store.update_mix_job(job_id, clean_status="ready",
                             clean_video_path="/tmp/clean.mp4")
    return job_id


def _call(monkeypatch, cid, body):
    monkeypatch.setattr(A, "_cid", lambda request: cid)
    r = A.api_produce_mix_clean_use(None, body)
    if hasattr(r, "body"):
        return json.loads(r.body), getattr(r, "status_code", 200)
    return r, 200


def test_off_then_on_keeps_clean_result(store, monkeypatch):
    """되돌렸다 되살려도 청소 결과는 그대로 — 이게 '0원'의 근거다."""
    jid = _mkjob(store)

    d, _ = _call(monkeypatch, 7, {"job_id": jid, "use": False})
    assert d["ok"] and d["use"] is False
    j = store.get_mix_job(jid)
    assert not j["subtitle_removal"]                 # 렌더·캡컷이 원본을 쓴다
    assert j["clean_status"] == "ready"              # ★결과는 살아 있다
    assert j["clean_video_path"] == "/tmp/clean.mp4"

    d, _ = _call(monkeypatch, 7, {"job_id": jid, "use": True})
    assert d["ok"] and d["use"] is True
    j = store.get_mix_job(jid)
    assert j["subtitle_removal"]
    assert j["clean_video_path"] == "/tmp/clean.mp4"


def test_cannot_turn_on_without_result(store, monkeypatch):
    """지운 적이 없는데 켜면 렌더가 말없이 VMake를 불러 과금된다 — 막는다."""
    jid = _mkjob(store, "J2", cleaned=False)
    store.update_mix_job(jid, subtitle_removal=0)

    d, code = _call(monkeypatch, 7, {"job_id": jid, "use": True})
    assert code == 400 and not d["ok"]
    assert "먼저 자막 지우기" in d["error"]
    assert not store.get_mix_job(jid)["subtitle_removal"]


def test_other_customer_denied(store, monkeypatch):
    """남의 job_id로 남의 설정을 못 바꾼다."""
    jid = _mkjob(store, "J3", cid=7)

    d, code = _call(monkeypatch, 999, {"job_id": jid, "use": False})
    assert code == 403 and not d["ok"]
    assert store.get_mix_job(jid)["subtitle_removal"]     # 그대로


def test_missing_job(store, monkeypatch):
    d, code = _call(monkeypatch, 7, {"job_id": "nope", "use": False})
    assert code == 404 and not d["ok"]


def test_status_exposes_clean_in_use(store, monkeypatch):
    """화면의 버튼이 현재 상태를 그대로 비추려면 상태 API가 실어 줘야 한다."""
    jid = _mkjob(store, "J4")
    monkeypatch.setattr(A, "_cid", lambda request: 7)

    r = A.api_mix_status(jid, None)
    if hasattr(r, "body"):
        r = json.loads(r.body)
    assert r.get("clean_in_use") is True

    _call(monkeypatch, 7, {"job_id": jid, "use": False})
    r = A.api_mix_status(jid, None)
    if hasattr(r, "body"):
        r = json.loads(r.body)
    assert r.get("clean_in_use") is False
