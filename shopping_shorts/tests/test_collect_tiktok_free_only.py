"""틱톡 자동 수집은 무료 경로(계정 시드=yt-dlp)만 쓴다(2026-07-24 사장님 '과금 없는 구조').
키워드 시드는 Apify 유료라 기본 자동 경로에서 빠지고, 명시 옵션일 때만 돈다."""
from shopping_shorts import service


def _seeds(monkeypatch, rows):
    class S:
        def list_seeds(self, p): return rows
        def prev_base_platform(self, p, sc): return None
        def prev_delta_platform(self, p, sc): return None
        def save_run_platform(self, *a, **k): pass
        def save_last_run_platform(self, *a, **k): pass
        def get_setting(self, k, d=None): return d
    monkeypatch.setattr(service, "Store", lambda *a, **k: S())


def test_default_skips_paid_keyword_search(monkeypatch):
    _seeds(monkeypatch, [{"kind": "account", "value": "@a"}, {"kind": "ko", "value": "살림꿀팁"}])
    called = {"acc": 0, "paid": 0}
    monkeypatch.setattr(service, "tt_fetch", lambda acc: (called.__setitem__("acc", called["acc"] + 1), [])[1])
    monkeypatch.setattr(service, "tt_search_full",
                        lambda kw, max_results=None: (called.__setitem__("paid", called["paid"] + 1), [])[1])
    monkeypatch.setattr(service, "build_tiktok_items", lambda *a, **k: [])
    monkeypatch.setattr(service, "apply_grades", lambda items: None)
    service._collect_tiktok()
    assert called["acc"] == 1          # 무료 계정 경로는 돈다
    assert called["paid"] == 0         # 유료 키워드 경로는 안 돈다(기본)


def test_opt_in_runs_paid_keyword_search(monkeypatch):
    _seeds(monkeypatch, [{"kind": "ko", "value": "살림꿀팁"}])
    called = {"paid": 0}
    monkeypatch.setattr(service, "tt_fetch", lambda acc: [])
    monkeypatch.setattr(service, "tt_search_full",
                        lambda kw, max_results=None: (called.__setitem__("paid", called["paid"] + 1), [])[1])
    monkeypatch.setattr(service, "build_tiktok_items", lambda *a, **k: [])
    monkeypatch.setattr(service, "apply_grades", lambda items: None)
    service._collect_tiktok(include_paid_keywords=True)
    assert called["paid"] == 1         # 명시 옵션일 때만 유료 경로
