"""공유(카톡)에 **영상 + 선택 썸네일**을 함께 싣는 계약 (2026-08-04).

배경: 6단계에서 썸네일을 골라도 `thumbnail_json.selected`를 **읽는 곳이 0곳**이었다
(handoff/썸네일.md ⏭3). 그래서 8단계 최종렌더 화면에도 안 뜨고, 카톡으로는 영상만 갔다.

여기서 못 박는 것:
  1. /api/share/t/{sid} 가 선택 썸네일 PNG를 준다(로그인 불필요 = allowlist).
  2. 안 골랐으면 404 — 공유 페이지는 그걸로 '썸네일 없음'을 판단해 **영상만** 보낸다(500 금지).
  3. /s/{sid} 가 __THUMB__ 자리를 실제 경로/빈문자로 **치환**한다(치환이 안 되면 페이지가
     리터럴 "__THUMB__"을 URL로 믿고 깨진다 — 실제로 이게 유일한 배선점이다).
  4. 8단계가 물어보는 /api/produce/thumb/selected/{job} 계약.
  5. 경로순회·만료 봉인.
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_META = json.dumps({"frame_ts": 1.0, "layers": [{"text": "테스트", "x": 0.5, "y": 0.2}]})


@pytest.fixture
def env(tmp_path, monkeypatch):
    """job 하나 + 완성 영상(video_path) 실파일까지 갖춘 상태."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(app_module, "_SHARE_STORE", {})   # 테스트 간 격리
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j1", ["https://x/1"], 30, "template")
    vid = tmp_path / "final.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    s.update_mix_job("j1", status="done", video_path=str(vid))
    return TestClient(app_module.app), s, tmp_path


def _save_and_select(c):
    """실제 라우트로 저장 → 선택(픽스처가 DB를 손으로 심으면 진짜 배선을 안 탄다)."""
    r = c.post("/api/produce/thumb/save",
               data={"job_id": "j1", "meta": _META},
               files={"file": ("x.png", _PNG_1PX, "image/png")})
    assert r.status_code == 200, r.text
    name = r.json()["name"]
    r2 = c.post("/api/produce/thumb/select", json={"job_id": "j1", "name": name})
    assert r2.status_code == 200 and r2.json()["ok"] is True
    return name


# ── 1·2. 공유 썸네일 서빙 ────────────────────────────────────────
def test_share_thumb_serves_selected_png(env):
    c, _s, _tp = env
    _save_and_select(c)
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    r = c.get(f"/api/share/t/{sid}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert r.content == _PNG_1PX          # 고른 그 PNG가 그대로 나가야 한다


def test_share_thumb_404_when_nothing_selected(env):
    """안 골랐으면 404. 500이면 공유 페이지가 통째로 막힌다 = 영상도 못 보낸다."""
    c, _s, _tp = env
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    assert c.get(f"/api/share/t/{sid}").status_code == 404
    assert c.get(f"/api/share/v/{sid}").status_code == 200   # 영상은 여전히 나간다


def test_share_thumb_404_when_saved_but_not_selected(env):
    """저장만 하고 selected가 없으면 안 보낸다 — '고른 것'만 나가는 게 계약이다."""
    c, s, _tp = env
    c.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
           files={"file": ("x.png", _PNG_1PX, "image/png")})
    thumb = s.get_mix_job("j1")["thumbnail"]
    assert thumb.get("results") and not thumb.get("selected")
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    assert c.get(f"/api/share/t/{sid}").status_code == 404


def test_share_thumb_dl_is_attachment(env):
    c, _s, _tp = env
    _save_and_select(c)
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    r = c.get(f"/api/share/t/{sid}?dl=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")


def test_share_thumb_expired_sid_is_403(env):
    c, _s, _tp = env
    _save_and_select(c)
    assert c.get("/api/share/t/nonexistent").status_code == 403


# ── 3. /s/{sid} 치환 = 유일한 배선점 ────────────────────────────
def test_share_page_wires_thumb_url_when_selected(env):
    c, _s, _tp = env
    _save_and_select(c)
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    html = c.get(f"/s/{sid}").text
    assert "__THUMB__" not in html          # 치환 안 되면 페이지가 리터럴을 URL로 믿는다
    assert f"/api/share/t/{sid}" in html
    assert f'const V="/api/share/v/{sid}", T="/api/share/t/{sid}"' in html


def test_share_page_thumb_empty_when_not_selected(env):
    """썸네일이 없으면 T=""가 되고 페이지는 예전대로 영상만 보낸다(회귀 방지)."""
    c, _s, _tp = env
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    html = c.get(f"/s/{sid}").text
    assert "__THUMB__" not in html
    assert f'const V="/api/share/v/{sid}", T=""' in html
    assert f"/api/share/v/{sid}" in html    # 영상 경로는 그대로


def test_share_page_share_sheet_sends_both_files(env):
    """공유 버튼이 '영상+썸네일 2개'를 넘기는 코드가 실제로 페이지에 있나."""
    c, _s, _tp = env
    _save_and_select(c)
    sid = c.get("/api/share/link/j1").json()["url"].rsplit("/", 1)[-1]
    html = c.get(f"/s/{sid}").text
    assert "navigator.share({files:[f,tf]" in html      # ① 둘 다
    assert "navigator.canShare({files:[f,tf]})" in html  # 기기가 거절하면 ②로
    assert "navigator.share({files:[f]" in html          # ② 영상만 폴백 보존


# ── 4. 8단계가 물어보는 곳 ──────────────────────────────────────
def test_selected_endpoint_reports_url(env):
    c, _s, _tp = env
    name = _save_and_select(c)
    d = c.get("/api/produce/thumb/selected/j1").json()
    assert d["ok"] is True and d["name"] == name
    assert d["url"] == f"/api/produce/thumb/file/j1/{name}"
    assert c.get(d["url"]).status_code == 200      # 준 URL이 진짜로 열려야 한다


def test_selected_endpoint_null_when_none(env):
    """안 골랐으면 200 + name=None. 404면 프런트가 오류로 오인해 카드가 깨진다."""
    c, _s, _tp = env
    r = c.get("/api/produce/thumb/selected/j1")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "name": None, "url": None}


def test_selected_endpoint_404_unknown_job(env):
    c, _s, _tp = env
    assert c.get("/api/produce/thumb/selected/nope").status_code == 404


# ── 5. 봉인 ─────────────────────────────────────────────────────
def test_selected_path_helper_blocks_traversal(env):
    """DB에 경로순회 문자열이 들어와도 파일로 안 새어나간다(selected는 DB 경유 문자열)."""
    _c, s, _tp = env
    s.update_mix_job("j1", thumbnail={"results": ["a.png"], "selected": "../../secret.png"})
    assert app_module._selected_thumb_path(s.get_mix_job("j1")) is None


def test_selected_path_helper_none_for_missing_file(env):
    """DB엔 이름이 있는데 파일이 사라졌으면 None — 그래야 404로 떨어져 영상만 간다."""
    _c, s, _tp = env
    s.update_mix_job("j1", thumbnail={"results": ["gone.png"], "selected": "gone.png"})
    assert app_module._selected_thumb_path(s.get_mix_job("j1")) is None


def test_share_thumb_path_is_public_allowlisted():
    """/api/share/t/ 가 로그인 게이트 allowlist에 있나. 없으면 폰(쿠키 없음)에서 302/401이
    나 썸네일이 통째로 안 붙는다 — 이 한 줄이 빠지면 기능이 조용히 죽는다."""
    import inspect
    src = inspect.getsource(app_module)
    assert 'path.startswith("/api/share/t/")' in src
