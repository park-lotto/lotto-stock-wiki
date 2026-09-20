# -*- coding: utf-8 -*-
"""오늘 제작 현황판 — 통계 집계와 목록(2026-09-02 사장님 요청).

여기서 고정하는 것:
  ① 통계는 서버가 낸다 — 화면이 또 분류하면 두 벌이 된다(0순위-B).
  ② 영상 파일 경로는 절대 내보내지 않는다(has_video 불리언만).
  ③ '오늘'은 KST 기준이다 — 서버가 UTC라 그냥 두면 하루가 9시간 어긋난다.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from shopping_shorts.store import Store

KST = timezone(timedelta(hours=9))


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


@pytest.fixture()
def store(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    now = datetime.now(timezone.utc)
    with sqlite3.connect(st.path if hasattr(st, "path") else str(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO customers(id, username, password_hash, salt, name) "
                  "VALUES (7,'kim','h','s','김사장')")
        rows = [
            ("j_done", 7, "done", None, _iso(now - timedelta(minutes=30)),
             _iso(now - timedelta(minutes=20)), "/tmp/out.mp4"),
            ("j_run", 7, "rendering", None, _iso(now - timedelta(minutes=5)),
             _iso(now - timedelta(minutes=1)), None),
            ("j_fail", 8, "failed", "Gemini 키 소진", _iso(now - timedelta(minutes=50)),
             _iso(now - timedelta(minutes=49)), None),
        ]
        for jid, cid, status, err, created, updated, vp in rows:
            c.execute(
                "INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, status, "
                "error, created_at, updated_at, customer_id, video_path) "
                "VALUES (?,'[]',30,'A',?,?,?,?,?,?)",
                (jid, status, err, created, updated, cid, vp))
        c.commit()
    return st


def _since_today():
    now_kst = datetime.now(KST)
    return now_kst.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc).isoformat()


def test_피드는_최신먼저_주고_이름을_붙인다(store):
    feed = store.production_feed(_since_today())
    assert [j["job_id"] for j in feed] == ["j_run", "j_done", "j_fail"]
    assert feed[1]["who"] == "김사장"          # customers.name을 붙여 준다
    assert feed[2]["who"] == "cid8"            # 회원 행이 없어도 화면이 빈칸이 되지 않는다


def test_영상_경로는_내보내지_않는다(store):
    feed = store.production_feed(_since_today())
    for j in feed:
        assert "video_path" not in j, "서버 파일 경로가 화면으로 새면 안 된다"
    assert [j["has_video"] for j in feed] == [False, True, False]


def test_기간_밖의_job은_안_들어온다(store):
    future = _iso(datetime.now(timezone.utc) + timedelta(minutes=1))
    assert store.production_feed(future) == []


def test_통계는_서버가_낸다(monkeypatch):
    """상태 분류(완성/진행/실패)와 인원수는 API가 계산해 내려준다."""
    from shopping_shorts import app as A

    jobs = [
        {"customer_id": 7, "status": "done", "has_video": True},
        {"customer_id": 7, "status": "rendering", "has_video": False},
        {"customer_id": 8, "status": "failed", "has_video": False},
        {"customer_id": 8, "status": "done", "has_video": False},   # 완성인데 파일 없음
    ]
    monkeypatch.setattr(A.Store, "production_feed",
                        lambda self, since, limit=300: jobs)
    monkeypatch.setattr(A, "_require_admin", lambda request: None)

    out = A._admin_production(request=None, days=0)
    assert out["stat"] == {"total": 4, "done": 2, "running": 1, "failed": 1,
                           "made": 1, "people": 2}
    # 화면이 '진행 중'을 자기 맘대로 정하지 않도록 목록을 함께 내려준다
    assert "rendering" in out["running_states"]


def test_오늘_경계는_KST다():
    from shopping_shorts import app as A

    since = datetime.fromisoformat(A._prod_since_iso(0))
    assert since.astimezone(KST).hour == 0, "KST 자정이 기준이어야 한다"
    assert since <= datetime.now(timezone.utc)
