"""썸네일 JSON이 mix_jobs에 저장·복원되는가 (설계 Q4).

★update_mix_job은 화이트리스트다(store.py:1240-1242 주석). 세 곳 중 하나라도
빠지면 '에러도 없이 조용히 무시'된다 — 그래서 왕복 테스트가 이 배선의 유일한 자물쇠.
"""
import json
import sqlite3

from shopping_shorts.store import Store


def _new_job(s, job_id="j1"):
    s.create_mix_job(job_id, ["https://x/1"], 30, "template")


def test_thumbnail_defaults_to_none(tmp_path):
    s = Store(tmp_path / "t.db")
    _new_job(s)
    assert s.get_mix_job("j1")["thumbnail"] is None  # 기존 행 하위호환


def test_thumbnail_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    _new_job(s)
    payload = {
        "frame_ts": 4.7,
        "layers": [{"text": "요즘 강남언니들", "font": "TmonMonsori.ttf", "size": 124,
                    "color": "#FFE100", "outline": {"color": "#000000", "w": 4},
                    "box": None, "rot": 0, "x": 0.5, "y": 0.18}],
        "results": ["thumb_1.png"],
        "selected": "thumb_1.png",
    }
    s.update_mix_job("j1", thumbnail=payload)
    assert s.get_mix_job("j1")["thumbnail"] == payload  # 왕복 = 3곳 다 배선됨


def test_thumbnail_written_to_column_not_swallowed(tmp_path):
    """화이트리스트 누락 시 update가 '조용히 무시'되는 걸 컬럼에서 직접 잡는다."""
    db = tmp_path / "t.db"
    s = Store(db)
    _new_job(s)
    s.update_mix_job("j1", thumbnail={"frame_ts": 1.0, "layers": [], "results": [], "selected": None})
    raw = sqlite3.connect(db).execute(
        "SELECT thumbnail_json FROM mix_jobs WHERE job_id='j1'").fetchone()[0]
    assert raw is not None, "thumbnail_json이 NULL — update_mix_job 화이트리스트에 안 들어갔다"
    assert json.loads(raw)["frame_ts"] == 1.0


def test_thumbnail_none_clears(tmp_path):
    s = Store(tmp_path / "t.db")
    _new_job(s)
    s.update_mix_job("j1", thumbnail={"frame_ts": 1.0, "layers": [], "results": [], "selected": None})
    s.update_mix_job("j1", thumbnail=None)
    assert s.get_mix_job("j1")["thumbnail"] is None


def test_thumbnail_hangul_not_escaped(tmp_path):
    """ensure_ascii=False 관례(headcopy_json과 동일)."""
    db = tmp_path / "t.db"
    s = Store(db)
    _new_job(s)
    s.update_mix_job("j1", thumbnail={"layers": [{"text": "강남언니"}]})
    raw = sqlite3.connect(db).execute(
        "SELECT thumbnail_json FROM mix_jobs WHERE job_id='j1'").fetchone()[0]
    assert "강남언니" in raw
