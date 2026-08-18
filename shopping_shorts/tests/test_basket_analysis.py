"""즐겨찾기 분석 버튼·신호등(2026-08-18 사장님 요청).

사장님 말: "즐겨찾기에 넣어두고 분석버튼 만들고, 다 되면 분석완료로. 확인해서
제작소로 보내고 안 된 건 제작소에서 기다리면 된다."

여기서 못박는 것:
  ① 신호등 판정은 **한 곳**(_analysis_state)에서 나온다 — 제작소 1단계 카드와
     즐겨찾기가 같은 영상을 다르게 말하면 사장님이 어느 쪽을 믿을지 모른다(0순위-B).
  ② 분석 버튼은 담을 때와 **같은 경로**(_enqueue_prewarm)로 건다 — 새 경로를 만들면
     둘이 서로 다르게 동작한다.
  ③ 이미 끝난 것은 다시 걸지 않는다(공짜로 도는 게 아니다).
  ④ 화면 배선(버튼·API 호출)이 실제로 붙어 있다.
"""
import pathlib
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store

PAGE = pathlib.Path(__file__).resolve().parents[1] / "static" / "collection.html"


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "t.db")
    Store(path)
    return path


def _status(db_path, codes):
    with patch.object(ap, "DB_PATH", db_path):
        return ap.api_basket_analysis_status(request=None, shortcodes=",".join(codes))


def _analyze(db_path, codes, cid=0):
    with patch.object(ap, "DB_PATH", db_path), patch.object(ap, "_cid", lambda r: cid):
        return ap.api_basket_analyze(request=None, body={"shortcodes": codes})


def test_결과가_있으면_분석완료로_보인다(db):
    with patch.object(ap.Store, "get_script", lambda self, c: {"segments": []}):
        out = _status(db, ["ABC"])
    assert out["items"]["ABC"]["state"] == "done"


def test_결과가_없고_시도도_없으면_분석중이다(db):
    out = _status(db, ["ABC"])
    assert out["items"]["ABC"]["state"] == "pending"


def test_가망없는_실패는_실패로_보이고_이유가_붙는다(db):
    store = Store(db)
    store.autoload_mark_attempt("ABC")      # 실제 순서: 선래치 → 실패기록
    store.autoload_mark_error("ABC", "login required — Fresh cookies needed")
    out = _status(db, ["ABC"])
    got = out["items"]["ABC"]
    assert got["state"] == "gave_up", "기다려도 안 오는 것은 '분석 중'으로 두면 안 된다"
    assert got["reason"], "왜 안 되는지 화면에 보여줄 문구가 있어야 한다"


def test_분석버튼은_담기예열과_같은_경로로_건다(db):
    called = []
    with patch.object(ap, "_enqueue_prewarm",
                      lambda store, sc, url, **kw: called.append((sc, url))):
        out = _analyze(db, ["ABC"])
    assert out["queued"] == 1 and called and called[0][0] == "ABC"


def test_이미_끝난것은_다시_걸지_않는다(db):
    called = []
    with patch.object(ap.Store, "get_script", lambda self, c: {"segments": []}), \
         patch.object(ap, "_enqueue_prewarm", lambda *a, **k: called.append(1)):
        out = _analyze(db, ["ABC"])
    assert out["skipped"] == 1 and out["queued"] == 0 and not called


def test_제작소_1단계_카드도_같은_판정을_쓴다(db):
    """source_brief가 자기만의 판정을 다시 짜면 두 화면이 어긋난다 — 그 회귀를 막는다."""
    seen = []
    real = ap._analysis_state
    with patch.object(ap, "_analysis_state",
                      lambda store, sc: (seen.append(sc), real(store, sc))[1]):
        with patch.object(ap, "DB_PATH", db):
            ap.api_produce_source_brief(request=None, shortcode="ABC")
    assert seen == ["ABC"]


@pytest.mark.parametrize("needle", [
    "/api/basket/analysis_status",   # 신호등 조회
    "/api/basket/analyze",           # 분석 걸기
    "analyzeSelected()",             # 툴바 일괄 분석
    "selectAnalyzed()",              # 완료된 것만 골라 제작소로
    "analyzeOne(",                   # 카드별 분석
    "분석완료",
])
def test_화면에_배선돼_있다(needle):
    assert needle in PAGE.read_text(encoding="utf-8")
