"""담기·다운로드가 쓰는 인스타 쿠키는 **살아있는 세션 풀**에서 골라야 한다.

★2026-09-21 실사고(사장님 "썸네일이 안보임"): 제작소 씨앗 카드 5장 중 4장이
  회색 필름 아이콘으로 떴다. 추적해 보니 /api/thumb나 화이트리스트 문제가 아니라
  **담길 때부터 mix_basket.thumbnail이 빈 값**이었다(DB 실측: 5건 중 4건 NULL,
  화면에 그림이 뜬 1건만 값 보유 — 화면과 DB가 정확히 일치).

  뿌리는 _ig_cookies_file()의 `Path(_d).glob("*.json")` 한 줄이었다. 이 glob은
  **최상위만** 본다. 그런데 살아있는 계정은 2026-08-09 풀 분리 이후
  `ig_sessions/reference/`(하위 폴더)로 옮겨졌고, 최상위엔 8/9자 낡은 세션
  하나만 남아 있었다. 그래서 "가장 최근 갱신된 세션"이 **6주 묵은 죽은 계정**으로
  뽑혔고, 인스타가 로그인 페이지로 리다이렉트해 메타 수집이 전부 실패했다.
  실측: 최상위 세션 → rate-limit 리다이렉트 / reference 풀 4개 → 4개 전부 성공.

  수집(channel_archive.session_slots)은 하위 폴더를 제대로 보고 있어서 멀쩡했다 —
  **같은 판단("어느 세션을 쓰나")이 두 군데 다르게 적혀 있던 것**이 사고의 형태다
  (0순위-B). 그래서 이 테스트는 "하위 폴더를 본다"가 아니라 **"수집과 같은 목록을
  쓴다"**를 고정한다. 직접 glob을 다시 짜면 같은 사고가 또 갈라진다.
"""
import json
import sys
import types


def _write_state(path, sessionid):
    path.write_text(json.dumps({"cookies": [
        {"name": "sessionid", "value": sessionid, "domain": ".instagram.com",
         "path": "/", "secure": True, "expires": 2147483647},
    ]}), encoding="utf-8")


def test_쿠키는_하위폴더_풀에서_고른다(tmp_path, monkeypatch):
    """최상위에 낡은 세션, reference/에 새 세션 → 새 것을 써야 한다."""
    from shopping_shorts import media_download

    top = tmp_path / "old_top.json"
    _write_state(top, "DEAD-TOP")
    sub = tmp_path / "reference"
    sub.mkdir()
    live = sub / "live_pool.json"
    _write_state(live, "LIVE-POOL")

    monkeypatch.setenv("INSTAGRAM_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(media_download.config, "INSTAGRAM_SESSION_PATH", "", raising=False)

    out = media_download._ig_cookies_file()
    assert out, "쿠키 파일을 못 만들었다"
    body = (tmp_path / out).read_text(encoding="utf-8") if not str(out).startswith(str(tmp_path)) \
        else __import__("pathlib").Path(out).read_text(encoding="utf-8")
    assert "LIVE-POOL" in body, f"하위 폴더의 살아있는 세션을 안 썼다: {out}"
    assert "DEAD-TOP" not in body, "최상위 낡은 세션을 썼다"


def test_죽은세션은_건너뛴다(tmp_path, monkeypatch):
    """풀에 여럿이면 살아있는 것을 쓴다 — mtime만 보면 죽은 최신을 집는다."""
    from shopping_shorts import media_download

    sub = tmp_path / "reference"
    sub.mkdir()
    dead = sub / "a_dead.json"
    alive = sub / "b_alive.json"
    _write_state(dead, "DEAD-SID")
    _write_state(alive, "ALIVE-SID")
    # 죽은 쪽을 더 최신으로 만든다 — mtime 기준이면 이걸 고른다.
    import os
    os.utime(alive, (1, 1))
    os.utime(dead, (10_000_000, 10_000_000))

    monkeypatch.setenv("INSTAGRAM_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(media_download.config, "INSTAGRAM_SESSION_PATH", "", raising=False)
    monkeypatch.setattr(media_download, "_ig_session_alive",
                        lambda p: "b_alive" in str(p))

    out = media_download._ig_cookies_file()
    assert out, "쿠키 파일을 못 만들었다"
    from pathlib import Path
    body = Path(out).read_text(encoding="utf-8")
    assert "ALIVE-SID" in body, "살아있는 세션을 안 골랐다"
    assert "DEAD-SID" not in body, "죽은 세션을 골랐다"


def test_판정불가면_기존동작(tmp_path, monkeypatch):
    """살아있음 판정이 전부 실패해도 쿠키는 나와야 한다(무쿠키 회귀 금지)."""
    from shopping_shorts import media_download

    sub = tmp_path / "reference"
    sub.mkdir()
    only = sub / "only.json"
    _write_state(only, "ONLY-SID")

    monkeypatch.setenv("INSTAGRAM_SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(media_download.config, "INSTAGRAM_SESSION_PATH", "", raising=False)
    monkeypatch.setattr(media_download, "_ig_session_alive", lambda p: False)

    out = media_download._ig_cookies_file()
    assert out, "전부 죽었다고 판정되면 쿠키가 통째로 사라진다 — 종전보다 나쁘다"
    from pathlib import Path
    assert "ONLY-SID" in Path(out).read_text(encoding="utf-8")
