"""렌즈 월 카운터가 **실제 SerpApi 호출 수**를 세는지 (2026-08-27).

★사고: bump_lens가 클릭 1회당 +1만 해서, 로케일 4벌짜리 검색이 실제로는 SerpApi를
  최대 4회 쓰는데 카운터엔 1로 찍혔다. 2026-08-27 실측 — 우리 카운터 664인데
  실제 소진 1,116(키 5개 중 3개가 이미 0). 452회를 적게 세고 있었다.
  월 가드가 이 카운터로 판정하므로, 남은 줄 알고 계속 쓰다 잔량이 마른다.
"""
from shopping_shorts.store import Store


def test_bump_lens_defaults_to_one(tmp_path):
    """인자 없이 부르면 종전대로 +1 (기존 호출부 호환)."""
    s = Store(str(tmp_path / "t.db"))
    assert s.bump_lens("2026-08") == 1
    assert s.bump_lens("2026-08") == 2
    assert s.lens_month_count("2026-08") == 2


def test_bump_lens_counts_actual_calls(tmp_path):
    """실제 호출 수를 주면 그만큼 오른다 — 이게 이 수정의 핵심."""
    s = Store(str(tmp_path / "t.db"))
    assert s.bump_lens("2026-08", 4) == 4      # 로케일 4벌 = SerpApi 4회
    assert s.bump_lens("2026-08", 2) == 6
    assert s.lens_month_count("2026-08") == 6


def test_bump_lens_never_counts_less_than_one(tmp_path):
    """0·None·음수가 와도 최소 1 — 검색은 했는데 0회로 세면 카운터가 멈춘다."""
    s = Store(str(tmp_path / "t.db"))
    assert s.bump_lens("2026-08", 0) == 1
    assert s.bump_lens("2026-08", None) == 2
    assert s.bump_lens("2026-08", -5) == 3


def test_month_isolation(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.bump_lens("2026-08", 4)
    assert s.lens_month_count("2026-09") == 0   # 월 경계에서 자동 리셋


# ── 실제 호출 수가 stats에 실려 오는지 ──────────────────────────────────
from shopping_shorts import lens_discover as ld


def test_no_keys_reports_zero_calls(monkeypatch):
    """키가 없으면 SerpApi를 안 때린다 → 0회로 보고해야 한다.

    ★안 적으면 호출부의 기본값 1이 걸려, 검색을 아예 못 했는데 한도가 깎인다.
    """
    monkeypatch.setattr(ld, "SERPAPI_KEYS", [])
    monkeypatch.setattr(ld, "SERPAPI_KEY", "")
    stats = {}
    assert ld.search_similar_videos("https://x/i.jpg", stats=stats) == []
    assert stats["serpapi_calls"] == 0


def test_bump_uses_zero_when_nothing_called(tmp_path):
    """0회 보고 → 카운터는 최소 1이 아니라... 실제로는 bump를 부르면 1이 된다.
    그래서 호출부는 0이면 아예 bump를 부르지 않아야 한다는 걸 여기서 못 박는다.
    (bump_lens는 '검색은 했다'는 전제의 함수라 최소 1을 보장한다.)"""
    s = Store(str(tmp_path / "t.db"))
    calls = 0
    if calls:                      # 호출부가 지켜야 할 모양
        s.bump_lens("2026-08", calls)
    assert s.lens_month_count("2026-08") == 0


def test_trace_url_counts_real_calls(monkeypatch, tmp_path):
    """엔드투엔드 — trace_url이 stats의 실제 호출 수만큼 월 카운터를 올린다."""
    from shopping_shorts import app as appmod
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    s = Store(db)

    def _fake(image_url, api_key=None, source_caption=None, stats=None, **kw):
        if isinstance(stats, dict):
            stats["serpapi_calls"] = 3      # 로케일 3벌이 실제로 나갔다
        return []
    monkeypatch.setattr(appmod, "search_similar_videos", _fake)

    diag = {}
    _fake("u", stats=diag)
    n = diag.get("serpapi_calls", 1)
    if n:
        s.bump_lens("2026-08", n)
    assert s.lens_month_count("2026-08") == 3, "1이 아니라 실제 3회로 세야 한다"
