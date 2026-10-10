"""분석 신호등 조회의 부하(관제 171, 2026-10-10 사장님 "이것도 고칠 수 있음 고쳐").

라이브 실측: 웹 서버 py-spy 60초 표본 2,657개 중 2,373개(89.3%)가 `api_basket_analysis_status`,
잎의 73.8%가 DB 연결 열기(`Store._conn`). 영상마다 조회 3~5번, 조회마다 새 연결 — 영상 100개면 연결 수백 개.
상태만 필요한데 대본 JSON도 통째로 읽고 있었다.

여기 테스트 ①②는 **고치기 전 코드에서 실패**한다(연결 수·대본 읽기). ③은 줄인 길이 원래 판정과 같은 답을 내는지 본다.
"""
import sqlite3
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t.db")
    st = Store(path)
    st.save_script("DONE1", {"segments": [{"seg_id": "a-0"}], "full_text": "말"})
    st.save_script("MEDIA9", {"segments": [], "full_text": "말"})          # 인스타 주소로 물어도 미디어코드로 찾는다
    st.enqueue("prewarm", {"shortcode": "QUEUED1", "url": "u"})
    st.autoload_mark_attempt("FAILED1")
    st.autoload_mark_error("FAILED1", "Fresh cookies needed")
    for _ in range(ap._AUTOLOAD_MAX_ATTEMPTS):
        st.autoload_mark_attempt("FAILED1")
    st.autoload_mark_attempt("TRIED1")
    return path


CODES = ["DONE1", "https://www.instagram.com/reel/MEDIA9/?igsh=x", "QUEUED1", "FAILED1", "TRIED1", "NOBODY1"]


def _status(db_path, codes):
    with patch.object(ap, "DB_PATH", db_path):
        return ap.api_basket_analysis_status(request=None, shortcodes=",".join(codes))


def test_영상이_100개여도_연결은_하나다(db):
    Store(db)                                   # 스키마 준비는 미리(이건 요청 비용이 아니다)
    codes = [f"X{i}" for i in range(94)] + CODES
    opened = []
    real = sqlite3.connect

    def counting(*a, **k):
        opened.append(1)
        return real(*a, **k)

    with patch.object(sqlite3, "connect", counting):
        out = _status(db, codes)
    assert len(out["items"]) == 100
    assert len(opened) == 1, f"연결 {len(opened)}개 — 요청 하나는 연결 하나여야 한다(수리 전: 영상마다 3~5개)"


def test_신호등은_대본을_읽지_않는다(db):
    def boom(self, c):
        raise AssertionError("상태 조회가 대본 내용을 읽었다 — has_script 로 있나 없나만 물어야 한다")

    with patch.object(ap.Store, "get_script", boom):
        out = _status(db, CODES)
    assert out["items"]["DONE1"]["state"] == "done"


def test_줄인_길도_원래_판정과_같은_답을_낸다(db):
    """상태만 묻는 길(need_data=False)이 내용까지 읽는 길과 state·reason·attempts 가 전부 같다."""
    st = Store(db)
    seen = set()
    for c in CODES:
        full = ap._analysis_state(st, c)[1]
        lite_data, lite = ap._analysis_state(st, c, need_data=False)
        assert lite == full, f"{c}: {lite} != {full}"
        assert lite_data is None
        seen.add(full["state"])
    assert seen == {"done", "pending", "gave_up", "idle"}, f"픽스처가 네 상태를 다 못 만든다: {seen}"
    out = _status(db, CODES)["items"]
    assert [out[c]["state"] for c in CODES] == ["done", "done", "pending", "gave_up", "pending", "idle"]


def test_reuse는_스레드끼리_연결을_나누지_않고_끝나면_닫는다(db):
    import threading
    st = Store(db)
    got = {}
    with st.reuse():
        mine = st._conn()
        assert st._conn() is mine
        t = threading.Thread(target=lambda: got.setdefault("other", st._conn()))
        t.start(); t.join()
        with st.reuse():                        # 겹쳐 불러도 바깥 연결을 닫지 않는다
            assert st._conn() is mine
        assert st._conn() is mine
    assert got["other"] is not mine
    assert st._conn() is not mine
    with pytest.raises(sqlite3.ProgrammingError):
        mine.execute("SELECT 1")                # 블록이 끝나면 닫혀 있다
