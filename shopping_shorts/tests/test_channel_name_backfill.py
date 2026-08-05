"""채널 표시명 보강 — 이미 크롤된(done) 채널의 한글 이름만 가볍게 받아온다(2026-08-06).

배경: 아카이브 크롤이 이제 응답에서 채널명을 주워 담지만(같은 날 커밋), pick_targets가
`− done − gone` 차집합이라 **이미 크롤한 채널은 재크롤 대상에서 영구 제외**된다.
실측: 이름 없는 아카이브 채널 85개 중 84개가 done → 그 84개는 영원히 @아이디로 남는다.

사장님 선택(2번안): 풀 재크롤(채널당 스크롤 수십 회) 대신 **이름만** 받아오는 가벼운 보강.

★이 파일이 지키는 안전 계약 — 이 경로는 계정이 이미 차단돼 세션을 돌려쓰는 중이다.
  요청이 늘면 계정을 잃고, 계정은 IP보다 비싸다(플래그되면 어느 IP에서도 복구 불가).
  1. 채널당 요청 1회 — 스크롤 없음, 릴스 안 긁음.
  2. 회당 상한(PER_RUN_LIMIT) — 84개를 한 번에 몰아치지 않는다.
  3. 이미 이름이 있는 채널은 건드리지 않는다(평생 1회).
  4. 실패는 기록해 무한 재시도를 막는다(삭제·비공개 채널).
"""
import pytest

from shopping_shorts import channel_name_backfill as cnb
from shopping_shorts.store import Store


def _seed(store, archived, named=()):
    with store._conn() as c:
        for u in archived:
            c.execute("INSERT INTO channel_archive(username, shortcode, url, thumbnail, "
                      "views, likes, comments, posted_at, first_seen, last_seen) "
                      "VALUES(?,?,?,?,?,0,0,'','','')", (u, u + "_sc", "u", "t", 10))
        for u, n in named:
            c.execute("INSERT INTO channel_names(username, name, updated_at) "
                      "VALUES(?,?,datetime('now'))", (u, n))


# ── 대상 고르기 ────────────────────────────────────────────────
def test_targets_are_archived_channels_without_names(tmp_path):
    s = Store(tmp_path / "t.db")
    _seed(s, ["homedukddak", "chae2home"], named=[("chae2home", "채이홈")])
    assert cnb._targets(s) == ["homedukddak"], "이름 있는 채널을 또 조회한다"


def test_targets_respect_reel_history_names(tmp_path):
    """수집 이력에 이름이 있으면 조회할 필요가 없다(channel_name_map이 이미 커버)."""
    s = Store(tmp_path / "t.db")
    _seed(s, ["known_ch"])
    with s._conn() as c:
        c.execute("INSERT INTO reel_history(shortcode, username, name, first_seen) "
                  "VALUES('x','known_ch','알려진이름',datetime('now'))")
    assert cnb._targets(s) == []


def test_targets_skip_failed_channels(tmp_path):
    """삭제·비공개 채널을 매번 두드리지 않는다 — 실패가 쌓이면 포기."""
    s = Store(tmp_path / "t.db")
    _seed(s, ["dead_ch"])
    for _ in range(cnb.MAX_FAIL):
        s.bump_channel_name_fail("dead_ch")
    assert cnb._targets(s) == []


def test_targets_are_capped_per_run(tmp_path):
    """84개를 한 번에 몰아치지 않는다 — 429·계정 플래그 계보를 의식한 상한."""
    s = Store(tmp_path / "t.db")
    _seed(s, [f"ch{i:03d}" for i in range(200)])
    assert len(cnb._targets(s)) <= cnb.PER_RUN_LIMIT


# ── 실행: 성공/실패 경로 ───────────────────────────────────────
def test_run_saves_name_and_skips_rest(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    _seed(s, ["homedukddak"])
    calls = []

    def fake_fetch(username, **kw):
        calls.append(username)
        return "홈덕닥 | 살림템"

    monkeypatch.setattr(cnb, "fetch_display_name", fake_fetch)
    out = cnb.run_backfill(db_path=tmp_path / "t.db", sleep_s=0)
    assert calls == ["homedukddak"], "조회 횟수가 채널 수와 다르다"
    assert s.channel_name_map().get("homedukddak") == "홈덕닥 | 살림템"
    assert "성공 1" in out
    # 두 번째 실행 — 이제 이름이 있으니 아예 안 부른다(평생 1회)
    calls.clear()
    cnb.run_backfill(db_path=tmp_path / "t.db", sleep_s=0)
    assert calls == [], "이름을 이미 얻은 채널을 또 조회한다"


def test_run_records_failure(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    _seed(s, ["dead_ch"])
    monkeypatch.setattr(cnb, "fetch_display_name", lambda u, **kw: None)
    cnb.run_backfill(db_path=tmp_path / "t.db", sleep_s=0)
    with s._conn() as c:
        n = c.execute("SELECT fail_count FROM channel_names WHERE username='dead_ch'"
                      ).fetchone()
    assert n and n[0] == 1, "실패를 기록 안 하면 죽은 채널을 영원히 두드린다"
    assert not s.channel_name_map().get("dead_ch"), "실패했는데 이름이 생겼다"


def test_run_survives_one_channel_error(tmp_path, monkeypatch):
    """한 채널이 터져도 나머지는 계속한다(부분 성공)."""
    s = Store(tmp_path / "t.db")
    _seed(s, ["bad_ch", "good_ch"])

    def flaky(username, **kw):
        if username == "bad_ch":
            raise RuntimeError("브라우저 죽음")
        return "좋은이름"

    monkeypatch.setattr(cnb, "fetch_display_name", flaky)
    cnb.run_backfill(db_path=tmp_path / "t.db", sleep_s=0)
    assert s.channel_name_map().get("good_ch") == "좋은이름"


def test_run_with_no_targets_is_noop(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    called = []
    monkeypatch.setattr(cnb, "fetch_display_name", lambda u, **kw: called.append(u))
    out = cnb.run_backfill(db_path=tmp_path / "t.db", sleep_s=0)
    assert called == [] and "0건" in out


# ── 안전 계약(소스 검사) ───────────────────────────────────────
def test_no_scrolling_in_fetch():
    """★스크롤하면 그건 풀 크롤이다 — 이 보강의 존재 이유(가벼움)가 사라진다."""
    import pathlib
    src = (pathlib.Path(cnb.__file__)).read_text(encoding="utf-8")
    for banned in ("mouse.wheel", "max_scrolls", "_SCROLL"):
        assert banned not in src, f"스크롤 경로가 들어왔다: {banned}"


def test_reuses_existing_session_and_proxy():
    """계정 세션·프록시를 새로 발명하지 않는다 — 아카이브 크롤과 같은 슬롯을 쓴다
    (계정↔IP 1:1 배정이 깨지면 인스타가 한 기계로 묶어 본다)."""
    import pathlib
    src = (pathlib.Path(cnb.__file__)).read_text(encoding="utf-8")
    assert "session_slots" in src and "slot_proxy" in src
