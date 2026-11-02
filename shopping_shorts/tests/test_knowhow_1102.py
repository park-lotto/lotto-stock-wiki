"""막혔을 때 노하우(관제 304) — 상황 글로 막힘표·가이드·경험이 나온다. 모든 막힘표의 읽을 곳 파일이 실제로 있어야 한다."""
import json
from pathlib import Path

from tools.calcopy.hybrid import flow as F


def test_every_blocker_points_to_real_guide():
    for x in json.loads(F.BLOCKERS_FILE.read_text(encoding="utf-8"))["items"]:
        assert x["do"], x["id"]
        for f in x["read"]:
            assert (F.GUIDE_DIR / f).is_file(), (x["id"], f)


def test_query_finds_blocker_and_guide():
    r = F.knowhow(query="HTTP Error 403: Forbidden")
    assert r["matched"][0]["id"] == "yt_block" and r["stage"] == "bench" and "가이드" in r["guide"]
    r = F.knowhow(query="1단 × B14 효과음 과다")
    assert any(x["id"] == "sfx" for x in r["matched"]) and "지난 제작 경험" in r["lessons"]


def test_stage_only_and_unknown():
    assert F.knowhow(stage="product")["matched"]
    assert F.knowhow(query="처음 보는 말")["stage"] == "setup"


def test_task_carries_blocker_table():
    st = {"version": "키치잇판", "log": [], "tries": {}, "phase": "plan"}
    t = F._task(st, F._Stop("같은 장면이 다시 나와요", "다시", retry="plan", detail="B13 재사용"), "plan_got", "plan")
    assert "이 상황 막힘표" in t["ask"] and "다른 구간" in t["ask"]
