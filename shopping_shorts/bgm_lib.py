"""3단계 배경음 목록(관제 146, 2026-10-06 사장님 "쇼츠 BGM 10곡 먼저 넣어").

곡 목록·파일 위치·"쇼츠 전용" 판단의 주인은 이 파일 하나다.
- 고른 곡은 deco.bgm.lib(곡 id)로 저장된다. 파일 경로로 바꾸는 건 mix_pipeline.resolve_deco_media 한 곳
  (렌더·캡컷이 같은 함수를 부른다) — 그래서 완성본과 캡컷에 같은 곡이 들어간다.
- 목록 곡은 상업 음원이라 쇼츠에만 쓴다(모음 영상 설명란: "롱폼에서는 사용하면 안되고").
  롱폼은 완성 쇼츠의 소리를 그대로 쓰므로(link_longform), 목록 곡을 쓴 영상은 롱폼을 막는다(shorts_only).
"""
import json
import os
import re

LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bgm_lib")
_ID_RE = re.compile(r"^[a-z0-9_]{1,40}$")


def list_tracks():
    """[{id, title, artist}] — 파일이 실제로 있는 곡만."""
    try:
        with open(os.path.join(LIB_DIR, "catalog.json"), encoding="utf-8") as f:
            tracks = json.load(f).get("tracks") or []
    except (OSError, ValueError):
        return []
    return [{"id": t["id"], "title": t.get("title") or t["id"], "artist": t.get("artist") or ""}
            for t in tracks if path_of(t.get("id"))]


def path_of(track_id):
    """곡 id → mp3 절대경로. 모르는 id·파일 없음이면 None."""
    tid = str(track_id or "")
    if not _ID_RE.match(tid):
        return None
    p = os.path.join(LIB_DIR, tid + ".mp3")
    return p if os.path.isfile(p) else None


SPEED_MIN, SPEED_MAX = 0.5, 2.0       # ffmpeg atempo 한 단으로 되는 범위(음 높이 유지)
VOLUME_MAX = 60


def speed_of(bgm):
    """배경음 속도(배속) — 렌더(video_assemble)·캡컷(capcut_draft)·저장(app)이 모두 이 값을 쓴다. 기본 1.0."""
    try:
        s = float((bgm or {}).get("speed", 1.0))
    except (TypeError, ValueError, AttributeError):
        return 1.0
    if s != s:                         # NaN
        return 1.0
    return round(max(SPEED_MIN, min(SPEED_MAX, s)), 2)


def enabled_for(store, job):
    """이 작업에 배경음 목록을 보여 주나 — 관리자 설정 bgm_lib_enabled.
    기본 "admin"(2026-10-06 사장님 "관리자만 봐야 한다") = 사장님 계정(customer_id 0) 작업만 / "1"·"on" = 전 회원 / "off" = 아무도."""
    mode = str(store.get_setting("bgm_lib_enabled", "admin") or "admin").strip().lower()
    if mode in ("1", "on"):
        return True
    return mode == "admin" and int((job or {}).get("customer_id") or 0) == 0


def shorts_only(deco):
    """이 꾸미기가 쇼츠 전용 곡을 쓰나 — 롱폼을 만들면 안 되는가."""
    bgm = (deco or {}).get("bgm") or {}
    return bool(isinstance(bgm, dict) and path_of(bgm.get("lib")))
