# -*- coding: utf-8 -*-
"""CTA 잘라내기(2026-09-05) — 유튜브용으로 뒷부분(CTA)만 잘라낸 판을 만드는 기능.

왜 이 테스트가 있나: 이 기능은 **조용히 깨지기 쉬운** 자리에 걸쳐 있다.
  ① store.update_mix_job 화이트리스트에서 빠지면 저장이 에러 없이 무시된다.
  ② CTA 판정을 여기서 새로 적으면 edit_plan._CTA_ROLES가 늘 때 한쪽만 고쳐진다.
  ③ 자를 지점을 초(-t)로 자르면 B프레임 때문에 요청보다 더 담긴다(실측 2프레임).
셋 다 화면엔 정상으로 보이고 결과물만 틀리므로, 코드가 아니라 **결과**로 검사한다.
"""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from shopping_shorts.store import Store
from shopping_shorts.video_assemble import cta_cut_sec


def _plan(*roles):
    return {"beats": [{"beat_idx": i, "role": r, "narration": f"n{i}",
                       "target_seconds": 5} for i, r in enumerate(roles)]}


def _tl(*pairs):
    """(role, t0) → _beat_timeline이 돌려주는 모양의 최소 타임라인."""
    return [{"beat_idx": i, "role": r, "t0": t} for i, (r, t) in enumerate(pairs)]


# ── cta_cut_sec: 자를 지점을 정하는 단일 출처 ────────────────────────────────
def test_cta칸_시작시각을_돌려준다():
    assert cta_cut_sec(_tl(("hook", 0.0), ("body", 5.0), ("cta", 27.4))) == 27.4


@pytest.mark.parametrize("role", ["cta", "CTA", "행동유도", "씨티에이"])
def test_edit_plan의_CTA표기를_그대로_따른다(role):
    """★판정을 여기서 새로 적으면 안 된다 — edit_plan._CTA_ROLES가 늘면 같이 늘어야 한다.

    이 테스트가 깨졌다면 cta_cut_sec가 _is_cta를 안 쓰고 자기 판정을 들고 있다는 뜻이다.
    """
    assert cta_cut_sec(_tl(("hook", 0.0), (role, 12.5))) == 12.5


def test_CTA가_없으면_None():
    assert cta_cut_sec(_tl(("hook", 0.0), ("body", 5.0))) is None


def test_빈_타임라인은_None():
    assert cta_cut_sec([]) is None


def test_첫칸이_CTA면_자르지_않는다():
    """자르면 빈 영상이 된다 — 0초에서 자르라고 하면 안 된다."""
    assert cta_cut_sec(_tl(("cta", 0.0), ("body", 3.0))) is None


# ── DB 왕복: 화이트리스트 누락은 에러 없이 조용히 무시된다 ───────────────────
def _mkjob(db, jid="j1"):
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(db)) as c:
        c.execute("INSERT OR REPLACE INTO mix_jobs "
                  "(job_id,urls_json,target_seconds,structure,status,created_at,updated_at) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (jid, json.dumps(["u"]), 30, "auto", "done", now, now))
    return jid


def test_cta_cut_sec가_DB에_저장되고_읽힌다(tmp_path):
    """★update_mix_job 화이트리스트에서 빠지면 저장이 조용히 무시된다(에러 안 남).

    그러면 렌더는 멀쩡히 끝나고 버튼만 "옛 영상"이라며 거절한다 — 원인을 찾기 어렵다.
    """
    db = tmp_path / "t.db"
    st = Store(str(db))
    jid = _mkjob(db)
    assert st.get_mix_job(jid)["cta_cut_sec"] is None      # 처음엔 비어 있다
    st.update_mix_job(jid, cta_cut_sec=27.4)
    assert st.get_mix_job(jid)["cta_cut_sec"] == 27.4      # ← 화이트리스트 누락 시 여기서 None
    st.update_mix_job(jid, cta_cut_sec=None)               # CTA 없는 대본으로 다시 렌더
    assert st.get_mix_job(jid)["cta_cut_sec"] is None


def test_다른_필드를_고쳐도_cta_cut_sec는_남는다(tmp_path):
    db = tmp_path / "t.db"
    st = Store(str(db))
    jid = _mkjob(db)
    st.update_mix_job(jid, cta_cut_sec=19.2)
    st.update_mix_job(jid, status="done", video_path="/x/final.mp4")
    assert st.get_mix_job(jid)["cta_cut_sec"] == 19.2


# ── 사유 갈라짐: "CTA 없음"과 "옛 영상"은 사장님이 할 일이 다르다 ─────────────
def test_CTA칸이_없으면_옛영상_안내가_아니라_CTA없음이라고_말한다(tmp_path, monkeypatch):
    """★사유를 뭉개면 무엇을 해야 할지 알 수 없다.

    CTA 칸이 없는 대본 → 다시 렌더해도 소용없다(대본을 바꿔야 한다).
    옛 영상 → 다시 렌더하면 된다. 둘을 같은 문구로 뭉개면 헛수고를 시킨다.
    """
    from shopping_shorts import app
    db = tmp_path / "t.db"
    Store(str(db))
    monkeypatch.setattr(app, "DB_PATH", str(db))
    job = {"edit_plan": _plan("hook", "body"), "cta_cut_sec": None}
    cut, why = app._cta_cut_for_job(job)
    assert cut is None
    assert "CTA 칸" in why and "다시 렌더" not in why


def test_옛영상은_다시렌더_안내를_준다(tmp_path, monkeypatch):
    from shopping_shorts import app
    db = tmp_path / "t.db"
    Store(str(db))
    monkeypatch.setattr(app, "DB_PATH", str(db))
    # CTA 칸은 있는데 저장값도 없고 TTS mp3도 없다 = 이 기능이 생기기 전 렌더분
    job = {"edit_plan": _plan("hook", "body", "cta"), "cta_cut_sec": None}
    cut, why = app._cta_cut_for_job(job)
    assert cut is None
    assert "다시 렌더" in why


def test_저장값이_있으면_그대로_쓴다():
    """A경로: 렌더가 저장해둔 값은 인트로 보정까지 끝난 final.mp4 기준이다 —
    여기서 또 인트로를 더하면 두 번 밀린다."""
    from shopping_shorts import app
    job = {"edit_plan": _plan("hook", "cta"), "cta_cut_sec": 27.4,
           "thumbnail": {"intro": True, "intro_sec": 1.5}}
    cut, why = app._cta_cut_for_job(job)
    assert cut == 27.4 and why == ""
