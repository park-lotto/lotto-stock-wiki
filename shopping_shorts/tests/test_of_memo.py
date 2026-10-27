"""원본 찾기 한 편 안에서 같은 검색어·같은 후보 정보를 다시 받지 않는다(10-27 완주시험: 콜라겐 검색어 4개×2사이트를 렌즈·같은 종류에서 두 번).

주인 = runner_ops._memo(작업 폴더/_of_memo) — _web_links(검색어마다)·_metas(주소마다)가 부른다.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def test_metas_second_call_uses_memo(tmp_path, monkeypatch):
    from tools.calcopy import origin_find as OF
    calls = []
    monkeypatch.setattr(OF, "meta", lambda u: calls.append(u) or {"title": "t " + u})
    monkeypatch.setattr(R, "OF_MEMO", tmp_path / "_of_memo")
    us = ["https://www.tiktok.com/@a/video/1", "https://www.tiktok.com/@b/video/2"]
    a = R._metas(us)
    b = R._metas(us)
    assert a == b and len(calls) == 2                       # 두 번째는 저장본


def test_metas_failure_not_memoized(tmp_path, monkeypatch):
    from tools.calcopy import origin_find as OF
    calls = []
    monkeypatch.setattr(OF, "meta", lambda u: calls.append(u) or {"why": "못 엶"})
    monkeypatch.setattr(R, "OF_MEMO", tmp_path / "_of_memo")
    R._metas(["https://www.tiktok.com/@a/video/1"])
    R._metas(["https://www.tiktok.com/@a/video/1"])
    assert len(calls) == 2                                   # 실패는 다음에 다시 시도


def test_web_links_reuses_query(tmp_path, monkeypatch):
    opened = []

    class Pg:
        context = types.SimpleNamespace(add_cookies=lambda c: None)
        mouse = types.SimpleNamespace(wheel=lambda *a: None)

        def goto(self, url, **k):
            opened.append(url)

        def wait_for_timeout(self, ms):
            pass

        def content(self):
            return "https://www.tiktok.com/@x/video/123 https://www.instagram.com/reel/AbC1/"

    class Ctx:
        def __enter__(self):
            return Pg()

        def __exit__(self, *a):
            return False
    from tools.calcopy import lens as LN
    monkeypatch.setattr(LN, "lens_page", lambda: Ctx())
    monkeypatch.setattr(R, "_tiktok_cookies", lambda: None)
    monkeypatch.setattr(R, "CACHE", None)
    monkeypatch.setattr(R, "OF_MEMO", tmp_path / "_of_memo")
    a = R._web_links(["korean collagen mask reaction"])
    n = len(opened)
    b = R._web_links(["korean collagen mask reaction", "new words"])
    assert a and {x["url"] for x in a} <= {x["url"] for x in b}
    assert len(opened) == n + 2                              # 새 검색어만 열었다(틱톡·구글 2번)
