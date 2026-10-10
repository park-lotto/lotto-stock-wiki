"""'분석 중' 영구 고착(관제 172, 2026-10-10).

라이브 실측: 시도 1~2회·오류 없음·대본 없음·대기줄 없음인 영상 35개(가장 오래된 것 76일)가 영원히 '분석 중'.
화면은 '분석 중'이 하나라도 있으면 20초마다 다시 묻는다 → 그런 영상을 담은 고객 10명의 탭이 밤새 조회를 보냈다.
①②③은 **고치기 전 코드에서 실패**한다.
"""
import pathlib
import sqlite3

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store

PAGE = (pathlib.Path(__file__).resolve().parents[1] / "static" / "collection.html").read_text(encoding="utf-8")


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t.db")
    Store(path)
    return path


def _age(db_path, code, sec):
    """마지막 시도를 sec초 전에 시작한 것으로 만든다(실제 저장 행의 시각을 옮긴다)."""
    c = sqlite3.connect(db_path)
    c.execute("UPDATE produce_autoload SET updated_at=datetime('now', ?) WHERE shortcode=?", (f"-{int(sec)} seconds", code))
    c.commit()
    c.close()


def _state(db_path, code):
    return ap._analysis_state(Store(db_path), code, need_data=False)[1]


@pytest.mark.parametrize("attempts", [1, 2])
def test_끊긴_지_오래된_시도는_분석중이_아니다(db, attempts):
    st = Store(db)
    for _ in range(attempts):
        st.autoload_mark_attempt("STUCK")
    _age(db, "STUCK", ap._AUTOLOAD_STALL_SEC + 5)
    got = _state(db, "STUCK")
    assert got["state"] == "gave_up", f"아무도 안 도는 영상이 {got['state']} — 화면이 영원히 다시 묻는다"
    assert "끊겼" in got["reason"]


def test_오류를_남기고_멈춘_것도_사유와_함께_끝난다(db):
    st = Store(db)
    st.autoload_mark_attempt("ERR1")
    st.autoload_mark_error("ERR1", "예열 추출 실패: read timed out")
    assert not ap._is_hopeless_error("예열 추출 실패: read timed out")
    _age(db, "ERR1", ap._AUTOLOAD_STALL_SEC + 5)
    got = _state(db, "ERR1")
    assert got["state"] == "gave_up" and got["reason"]


def test_화면은_안_보이는_탭에서_다시_묻지_않는다():
    line = next(l for l in PAGE.splitlines() if "_pollTimer=setTimeout" in l)
    assert "!document.hidden" in line, "숨은 탭이 20초마다 조회를 보낸다"
    assert "visibilitychange" in PAGE          # 다시 보는 순간 읽는 길이 살아 있어야 숨은 동안 멈춰도 된다


def test_방금_시작한_시도는_여전히_분석중이다(db):
    st = Store(db)
    st.autoload_mark_attempt("FRESH")
    _age(db, "FRESH", ap._AUTOLOAD_STALL_SEC - 60)
    assert _state(db, "FRESH")["state"] == "pending"


def test_대기줄에_있으면_오래돼도_분석중이다(db):
    st = Store(db)
    st.autoload_mark_attempt("QUEUED")
    _age(db, "QUEUED", ap._AUTOLOAD_STALL_SEC * 3)
    st.enqueue("prewarm", {"shortcode": "QUEUED", "url": "u"})
    assert _state(db, "QUEUED")["state"] == "pending"


def test_끊긴_영상은_분석_버튼으로_다시_걸린다(db):
    """'분석 실패'로 보인 뒤 버튼을 누르면 실제로 대기줄에 들어가야 한다(막다른 길 금지)."""
    from unittest.mock import patch
    st = Store(db)
    st.autoload_mark_attempt("STUCK")
    _age(db, "STUCK", ap._AUTOLOAD_STALL_SEC + 5)
    with patch.object(ap, "DB_PATH", db), patch.object(ap, "_cid", lambda r: 0):
        out = ap.api_basket_analyze(request=None, body={"shortcodes": ["STUCK"],
                                                        "urls": {"STUCK": "https://www.tiktok.com/@x/video/1"}})
    assert out["items"]["STUCK"] == "queued", out
    assert _state(db, "STUCK")["state"] == "pending"
