"""기간 탭(전체/7일/30일) — 이미 받아둔 이력을 다시 보여줄 뿐 추가 크롤은 0이다.

등급제로 상단(48시간)이 얇아져도 이 줄이 재고를 메운다.
실측(서버 reference.db): 7일 댓글500+ 182건 / 30일 1000+ 360건.
"""
import re
from pathlib import Path

import pytest

from shopping_shorts.store import Store

_INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    # 쓰기 경로(_record_history)는 private이라 테스트는 표를 직접 채운다 —
    # 여기서 검증하려는 건 '읽기(hits_since)'지 수집 경로가 아니다.
    with s._conn() as c:
        for sc, user, comments, views in [
            ("new_hit", "a", 900, 50000),      # 오늘 터진 것
            ("old_big", "b", 5000, 900000),    # 크게 터진 것
            ("quiet", "c", 10, 300),           # 조용한 것 — 문턱 아래
        ]:
            c.execute(
                "INSERT INTO reel_history(shortcode, username, name, category, url,"
                " thumb, caption, views, comments, first_seen, last_seen, upload_ts)"
                " VALUES(?,?,'','','','','',?,?,datetime('now'),datetime('now'),'')",
                (sc, user, views, comments))
    return s


class TestHitsSince:
    def test_문턱넘은것만_준다(self, store):
        got = {i["shortcode"] for i in store.hits_since(30, min_comments=500)}
        assert got == {"new_hit", "old_big"}

    def test_댓글순_정렬(self, store):
        got = [i["shortcode"] for i in store.hits_since(30, min_comments=500)]
        assert got == ["old_big", "new_hit"]      # 5000 > 900

    def test_문턱을_올리면_줄어든다(self, store):
        # 30일 탭이 1000을 쓰는 이유 — 500이면 '명예의전당'이 안 된다
        got = {i["shortcode"] for i in store.hits_since(30, min_comments=1000)}
        assert got == {"old_big"}

    def test_카드가_기대하는_필드가_다_있다(self, store):
        item = store.hits_since(30, min_comments=500)[0]
        for k in ("shortcode", "username", "name", "category", "url",
                  "thumb", "caption", "views", "comments"):
            assert k in item, f"카드 렌더에 필요한 {k}가 없다"

    def test_limit이_걸린다(self, store):
        assert len(store.hits_since(30, min_comments=1, limit=1)) == 1

    def test_결과없어도_죽지않는다(self, store):
        assert store.hits_since(30, min_comments=999999) == []


class TestApiWiring:
    def test_days0은_종전동작(self):
        # 기본값이 바뀌면 라이브 첫 화면이 통째로 달라진다 — 시그니처를 못 박는다
        import inspect
        from shopping_shorts.app import api_reference
        sig = inspect.signature(api_reference)
        assert sig.parameters["days"].default == 0
        assert sig.parameters["platform"].default == "instagram"

    def test_days가_store로_전달된다(self, monkeypatch):
        from shopping_shorts import app as app_mod
        seen = {}

        class _S:
            def hits_since(self, days, min_comments=500):
                seen["days"], seen["min"] = days, min_comments
                return []

            def removed_usernames(self):
                return set()

        monkeypatch.setattr(app_mod, "Store", lambda *a, **k: _S())
        monkeypatch.setattr(app_mod, "_attach_vision_tags", lambda *a, **k: None)
        monkeypatch.setattr(app_mod, "_attach_durations", lambda *a, **k: None)
        monkeypatch.setattr(app_mod, "_attach_posted_at", lambda *a, **k: None)
        app_mod.api_reference(platform="instagram", days=7, min_comments=500)
        assert seen == {"days": 7, "min": 500}


class TestFrontend:
    def test_기간탭_3개가_있다(self):
        html = _INDEX.read_text(encoding="utf-8")
        spans = re.findall(r'data-span="(\d+)"', html)
        assert spans == ["0", "7", "30"]

    def test_30일탭은_문턱1000(self):
        html = _INDEX.read_text(encoding="utf-8")
        assert "30: 1000" in html.replace(" ", " ")

    def test_기간0일땐_days파라미터를_안붙인다(self):
        # 붙이면 첫 화면이 이력 조회로 새버린다
        html = _INDEX.read_text(encoding="utf-8")
        assert "if(SPAN_DAYS > 0){" in html
