"""mix_jobs의 preview 컬럼 — 마이그레이션·쓰기·읽기 세 곳이 다 맞아야 산다.

스펙 §6.1(docs/superpowers/specs/2026-07-17-제작소-1단계-미리보기-design.md).
이 셋 중 하나만 빠져도 **에러 없이 조용히** 실패한다:
  1) ALTER TABLE 안 하면 기존 DB(서버에 실 job 행 있음)에 컬럼이 없음
  2) update_mix_job 화이트리스트(store.py)에 없으면 쓰기가 무시됨
  3) get_mix_job SELECT에 없으면 읽기가 안 됨
그래서 테스트가 셋으로 나뉜다.
"""
import sqlite3

import pytest

from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _mk_job(store, job_id="J1"):
    store.create_mix_job(job_id, ["https://x/1"], 20, "template")


def test_preview_fields_default_to_none(store):
    """★get_mix_job SELECT/반환 dict 누락 시 여기서 죽는다."""
    _mk_job(store)
    job = store.get_mix_job("J1")
    assert job["preview_status"] is None
    assert job["preview_path"] is None
    assert job["preview_error"] is None


def test_update_and_read_preview_fields(store):
    """★update_mix_job 화이트리스트 누락 시 여기서 죽는다(쓰기가 조용히 무시됨)."""
    _mk_job(store)
    store.update_mix_job("J1", preview_status="ready", preview_path="/tmp/p.mp4")
    job = store.get_mix_job("J1")
    assert job["preview_status"] == "ready"
    assert job["preview_path"] == "/tmp/p.mp4"


def test_preview_update_does_not_touch_status(store):
    """★스펙 §6.1의 존재이유 — 기존 status 한 줄기를 오염시키지 않는다.

    status는 downloading→…→ready_for_review→rendering→done 한 줄기라, 미리보기를
    거기 끼우면 최종 렌더 폴링과 서로를 오인한다."""
    _mk_job(store)
    store.update_mix_job("J1", status="ready_for_review")
    store.update_mix_job("J1", preview_status="rendering")
    job = store.get_mix_job("J1")
    assert job["status"] == "ready_for_review", "preview 갱신이 기존 status를 덮었다"
    assert job["preview_status"] == "rendering"


def test_preview_error_roundtrip(store):
    _mk_job(store)
    store.update_mix_job("J1", preview_status="failed", preview_error="ffmpeg 죽음")
    job = store.get_mix_job("J1")
    assert job["preview_status"] == "failed"
    assert job["preview_error"] == "ffmpeg 죽음"


def test_migration_adds_columns_to_existing_db(tmp_path):
    """★기존 DB(컬럼 없음)를 열어도 ALTER TABLE로 컬럼이 생겨야 한다.

    mix_jobs는 CREATE TABLE IF NOT EXISTS라 기존 DB엔 컬럼이 안 생긴다.
    서버 DB(reference.db)엔 이미 실 job 행이 있다 — 이게 안 되면 배포 즉시 500."""
    db = str(tmp_path / "old.db")
    # preview 컬럼이 없던 시절의 mix_jobs를 손으로 만든다
    with sqlite3.connect(db) as c:
        c.execute("""CREATE TABLE mix_jobs (
            job_id TEXT PRIMARY KEY, urls_json TEXT NOT NULL, target_seconds INTEGER NOT NULL,
            structure TEXT NOT NULL, status TEXT NOT NULL, error TEXT, extract_json TEXT,
            edit_plan_json TEXT, video_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            subtitle_removal INTEGER NOT NULL DEFAULT 0, clean_video_path TEXT,
            given_script TEXT, headcopy_json TEXT)""")
        c.execute("INSERT INTO mix_jobs (job_id, urls_json, target_seconds, structure, status,"
                  " created_at, updated_at) VALUES ('OLD', '[]', 20, 'template', 'done', 'x', 'x')")
    s = Store(db)                      # __init__이 마이그레이션을 돈다
    with sqlite3.connect(db) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(mix_jobs)")}
    assert "preview_status" in cols, "기존 DB에 preview_status 컬럼이 안 생겼다"
    assert "preview_path" in cols
    assert "preview_error" in cols
    assert s.get_mix_job("OLD")["preview_status"] is None   # 기존 행도 읽힌다
