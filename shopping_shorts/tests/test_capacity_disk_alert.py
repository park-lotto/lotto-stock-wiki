"""디스크가 꽉 찬 날만 골라서 무시하던 경보 침묵 (2026-09-18 실사고).

증상: 서버 디스크가 **0바이트**가 됐는데 경보가 한 번도 안 왔다.
      그 사이 yt-dlp가 `OSError: [Errno 28] No space left on device`로 죽어
      "대본 분석해서 정확히 찾기"가 실패하고 있었지만 아무도 몰랐다.
      고객 제보로 겨우 발견했다.

★원인: `min((x["min_disk_free_gb"] or 9999) for x in d)`
  **0.0은 falsy다.** 그래서 디스크가 완전히 찬 날(0.0GB)만 골라 9999로 바뀌었다.
  가장 위험한 값이 정확히 그 값이라는 이유로 사라진 것이다.

  라이브 실측(2026-09-18):
      09-17  0.0GB   ← 실제로 꽉 찼던 날
      09-16  0.0GB   ← 실제로 꽉 찼던 날
      09-15  259.5GB
      → min_free = **259.5** (0.0 두 개가 증발) → danger(<50) 끝내 안 뜸

여기서 못 박는 것:
  1. 0.0GB가 살아남아 danger가 뜬다(본체).
  2. None(표본 없음)은 계속 걸러진다 — 그것까지 0으로 세면 반대로 가짜 경보가 된다.
  3. 표본이 하나도 없으면 danger가 아니라 unknown/ok다(빈 DB로 경보 울리지 않게).
"""
import sqlite3

import pytest

from shopping_shorts import capacity_watch as cw


def _db(tmp_path, rows):
    """capacity_samples에 (날짜, 디스크여유) 표본을 심은 임시 DB."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "t.db"
    conn = sqlite3.connect(str(p))
    cw.ensure_schema(conn)
    for at, free in rows:
        conn.execute(
            "INSERT INTO capacity_samples(at,running,queued,workers,load1,cores,"
            " disk_used_gb,disk_free_gb,net_tx_gb,net_rx_gb) "
            "VALUES(?,0,0,1,0.1,4,10.0,?,1.0,1.0)", (at, free))
    conn.commit()
    conn.close()
    return p


def _dates(n=3):
    """오늘 기준 최근 n일 (verdict는 7일 창을 본다)."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    return [(now - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]


def test_zero_free_disk_raises_danger(tmp_path):
    """★본체: 여유 0.0GB인 날이 있으면 danger여야 한다.

    종전 코드(`x or 9999`)는 여기서 259.5를 골라 ok/warn을 냈다.
    """
    d0, d1, d2 = _dates(3)
    db = _db(tmp_path, [(d0, 0.0), (d1, 0.0), (d2, 259.5)])
    v = cw.verdict(db, cores=4)
    assert v["level"] == "danger", f"디스크 0GB인데 danger가 아니다: {v}"
    assert "디스크" in v["msg"]


def test_zero_is_not_swallowed_by_larger_values(tmp_path):
    """0.0이 큰 값들 사이에 섞여 있어도 최솟값으로 잡혀야 한다."""
    ds = _dates(4)
    db = _db(tmp_path, [(ds[0], 300.0), (ds[1], 0.0), (ds[2], 280.0), (ds[3], 290.0)])
    v = cw.verdict(db, cores=4)
    assert v["level"] == "danger", f"0.0이 묻혔다: {v}"


def test_healthy_disk_is_not_danger(tmp_path):
    """여유가 넉넉하면 디스크로 danger를 내지 않는다(가짜 경보 방지)."""
    ds = _dates(3)
    db = _db(tmp_path, [(d, 300.0) for d in ds])
    v = cw.verdict(db, cores=64)
    assert v["level"] != "danger" or "디스크" not in v["msg"], f"멀쩡한데 경보: {v}"


def test_empty_db_is_unknown_not_danger(tmp_path):
    """표본이 없으면 경보가 아니라 unknown — 빈 DB로 울리면 안 된다."""
    db = _db(tmp_path, [])
    v = cw.verdict(db, cores=4)
    assert v["level"] == "unknown"


@pytest.mark.parametrize("free,expect_disk_danger", [(49.0, True), (51.0, False)])
def test_threshold_boundary(tmp_path, free, expect_disk_danger):
    """50GB 경계: 미만이면 danger, 이상이면 디스크 사유로는 danger가 아니다."""
    day = _dates(1)[0]
    db = _db(tmp_path / f"c{free}", [(day, free)])
    v = cw.verdict(db, cores=64)
    is_disk_danger = v["level"] == "danger" and "디스크" in v["msg"]
    assert is_disk_danger is expect_disk_danger, f"free={free}GB → {v}"
