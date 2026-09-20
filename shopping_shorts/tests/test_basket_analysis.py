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


def test_아무도_안_건_영상은_분석전이다(db):
    """결과가 없다고 전부 '분석 중'이라고 하면, 아무도 안 건 영상 앞에서
    오지 않을 결과를 기다리게 된다 — 대기줄에 없으면 '분석 전'이어야 한다."""
    out = _status(db, ["ABC"])
    assert out["items"]["ABC"]["state"] == "idle"


def test_대기줄에_있으면_분석중이다(db):
    store = Store(db)
    store.enqueue("prewarm", {"shortcode": "ABC", "url": "u"})
    out = _status(db, ["ABC"])
    assert out["items"]["ABC"]["state"] == "pending", \
        "걸어둔 분석은 페이지를 옮겨도 '분석 중'으로 남아야 한다"


def test_가망없는_실패는_실패로_보이고_이유가_붙는다(db):
    store = Store(db)
    store.autoload_mark_attempt("ABC")      # 실제 순서: 선래치 → 실패기록
    store.autoload_mark_error("ABC", "login required — Fresh cookies needed")
    out = _status(db, ["ABC"])
    got = out["items"]["ABC"]
    assert got["state"] == "gave_up", "기다려도 안 오는 것은 '분석 중'으로 두면 안 된다"
    assert got["reason"], "왜 안 되는지 화면에 보여줄 문구가 있어야 한다"


def test_분석버튼은_담기예열과_같은_경로로_건다(db):
    """★즐겨찾기에 실제로 담긴 항목으로 부른다 — 담기지 않은(=주소 없는) 코드로 부르면
    실제 화면에선 일어나지 않는 경로를 시험하게 된다(2026-08-28)."""
    Store(db).mix_basket_toggle("ABC", url="https://www.instagram.com/reel/ABC/",
                                customer_id=0)
    called = []
    with patch.object(ap, "_enqueue_prewarm",
                      lambda store, sc, url, **kw: called.append((sc, url, kw))):
        out = _analyze(db, ["ABC"])
    assert out["queued"] == 1 and called and called[0][0] == "ABC"
    assert called[0][1], "주소를 실어 보내야 워커가 받을 게 있다"
    assert called[0][2].get("manual") is True,         "사람이 직접 누른 분석은 일일 상한을 건너뛰어야 한다(2026-08-28 조율가 제보)"


def test_주소가_없으면_조용히_넘기지_않고_이유를_말한다(db):
    """종전엔 주소 없는 항목도 '걸었다'고 답하고 큐엔 아무것도 안 남아, 화면이 몇 초 뒤
    '분석 전'으로 되돌아가기만 했다 — 왜인지 아무도 말해주지 않았다."""
    out = _analyze(db, ["NOURL"])
    assert out["queued"] == 0 and out["items"]["NOURL"] == "no_url" and out["note"]


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
