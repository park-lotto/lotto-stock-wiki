# -*- coding: utf-8 -*-
"""오류 신고함 + 틀린 키 사전 차단 — 2026-08-24 사장님 지시.

배경(둘 다 같은 사고에서 나왔다):
· 김만기님(cid 192)이 일레븐랩스 키 대신 '키 ID'를 등록 → 제작 4회 전부
  `400 text-to-speech` 로 실패. 화면엔 "처리 중 문제"만 떠서 원인을 알 수 없었고,
  서버 DB를 뒤져서야 알았다. 시스템은 이미 그 키를 status='bad'로 알고 있었다.
"""
import json
import time

import pytest

from shopping_shorts import app
from shopping_shorts.store import Store


@pytest.fixture()
def st(tmp_path, monkeypatch):
    s = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(app, "DB_PATH", str(tmp_path / "t.db"))
    return s


def _key(s, cid, service, status):
    with s._conn() as c:
        c.execute("INSERT INTO customer_keys(customer_id, service, key_enc, key_hash, status, "
                  "created_at) VALUES(?,?,?,?,?,?)",
                  (cid, service, "x", "%s-%s" % (cid, service), status, int(time.time())))


# ── 오류 신고함 ──────────────────────────────────────────────────
def test_신고를_저장하고_읽는다(st):
    rid = st.add_bug_report(192, "영상이 안 만들어져요", page_url="https://x/produce?work=abc",
                            job_id="fd61681a970e", work_id="abc", step="5",
                            user_agent="UA", console=["TypeError: x"])
    r = st.list_bug_reports()[0]
    assert r["id"] == rid and r["customer_id"] == 192
    assert r["job_id"] == "fd61681a970e" and r["step"] == "5"
    assert json.loads(r["console_json"]) == ["TypeError: x"]
    assert r["status"] == "open" and st.open_bug_report_count() == 1


def test_확인함으로_바꾸면_안본_신고에서_빠진다(st):
    rid = st.add_bug_report(1, "이상해요")
    st.set_bug_report_status(rid, "done", "안내함")
    assert st.open_bug_report_count() == 0
    assert st.list_bug_reports(status="open") == []
    assert st.list_bug_reports()[0]["note"] == "안내함"


def test_답장을_남기면_고객이_안읽은_목록에_뜬다(st):
    rid = st.add_bug_report(192, "영상 실패")
    assert st.my_bug_replies(192) == []          # 답장 전엔 없다
    st.reply_bug_report(rid, "키를 다시 등록해 주세요")
    got = st.my_bug_replies(192)
    assert len(got) == 1 and got[0]["reply"] == "키를 다시 등록해 주세요"
    assert st.open_bug_report_count() == 0       # 답장 = 처리완료


def test_고객이_확인하면_다시_안뜬다(st):
    rid = st.add_bug_report(192, "영상 실패")
    st.reply_bug_report(rid, "고쳤습니다")
    st.mark_bug_reply_read(rid, 192)
    assert st.my_bug_replies(192) == []


def test_남의_답장은_못_읽음처리한다(st):
    """★고객 A가 남의 신고 id를 넣어도 건드리지 못해야 한다."""
    rid = st.add_bug_report(192, "영상 실패")
    st.reply_bug_report(rid, "고쳤습니다")
    st.mark_bug_reply_read(rid, 999)             # 남이 시도
    assert len(st.my_bug_replies(192)) == 1      # 그대로 남아 있다


def test_남의_답장은_목록에_안_보인다(st):
    rid = st.add_bug_report(192, "영상 실패")
    st.reply_bug_report(rid, "고쳤습니다")
    assert st.my_bug_replies(193) == []


# ── 틀린 키 사전 차단 ────────────────────────────────────────────
def test_개인전용_키가_틀리면_제작을_막는다(st):
    _key(st, 192, "elevenlabs", "bad")
    r = app._bad_key_block(192)
    assert r is not None and r.status_code == 422
    body = json.loads(bytes(r.body).decode())
    assert body["error_code"] == "bad_key"
    assert "ElevenLabs" in body["error"] and "sk_" in body["error"]


def test_공용풀_키가_틀린_건_막지_않는다(st):
    """★제미니·유튜브는 풀의 다른 키로 돈다 — 막으면 멀쩡히 될 일을 막는 꼴이다."""
    _key(st, 193, "gemini", "bad")
    _key(st, 193, "youtube", "bad")
    assert app._bad_key_block(193) is None


def test_정상_키는_통과한다(st):
    _key(st, 57, "elevenlabs", "ok")
    assert app._bad_key_block(57) is None


def test_비로그인은_통과한다(st):
    assert app._bad_key_block(0) is None


def test_틀린_키가_여러개면_모두_알려준다(st):
    _key(st, 5, "elevenlabs", "bad")
    _key(st, 5, "vmake", "bad")
    body = json.loads(bytes(app._bad_key_block(5).body).decode())
    assert "ElevenLabs" in body["error"] and "Vmake" in body["error"]


def test_조회가_깨져도_제작을_막지_않는다(st, monkeypatch):
    """가드가 죽어서 제작이 통째로 멈추면 그게 더 나쁘다(fail-open)."""
    def boom(*a, **k):
        raise RuntimeError("DB 고장")
    monkeypatch.setattr(Store, "bad_key_services", boom)
    assert app._bad_key_block(192) is None
