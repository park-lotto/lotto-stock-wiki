# -*- coding: utf-8 -*-
"""필름에서 오려낸 조각(film_*)이 왕복에서 살아남는가 (2026-09-05 고객 다수 제보).

사장님 제보: "자막제거 후에 다시 장면매칭으로 오면 다 지워지고 까만색으로 된다"
— 박세희·왕혜원·다운 등 **여러 고객 전원**. 캡처 증상은 배지 `0-0`, 길이 `0.0`,
띠는 '장면 없음'인데 아래엔 '안 나옴' 카드가 12개.

뿌리: 오려낸 조각은 `apply_scene_lab`이 seg_map **사본**에만 병합하고(원본 보호)
그대로 버린다 — `extra_segs`가 DB에 저장되는 경로가 서버 어디에도 없다.
DB에 남는 건 `scene_override`의 **id 문자열뿐**이고, 다시 열 때 `segments`는
`job["extract"]`에서만 만들어지므로 그 id는 가리킬 곳이 없다.

평소엔 브라우저 localStorage(hydrateExtra)가 가려준다. 자막제거를 다녀와
서버 편성 분기로 열리면 그 복원이 안 돌아 조각이 통째로 증발한다.

★복구는 된다 — id 자체가 `film_<video_id>_<start>_<end>`라 구간이 들어 있고,
  되읽는 함수(`app._film_seg_from_id`)가 이미 있다. 다만 호출처가 썸네일 한 곳뿐이라
  화면 데이터(`/api/mix/scene_lab/{job}`)가 그걸 안 쓴다 — 그래서 여기서 계약으로 박는다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import edit_plan as _edit_plan
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    return TestClient(app_module.app), Store(db)


_SEGS = [
    {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "서랍 열기"},
    {"seg_id": "s0-1", "start": 2.0, "end": 4.5, "text": "b", "scene_desc": "화장대 정리"},
    {"seg_id": "s0-2", "start": 4.5, "end": 6.0, "text": "c", "scene_desc": "거울 덮기"},
]

# 화면(_extraId)이 만드는 것과 **같은 규칙**의 id: film_<vid>_<start>_<end>
FILM_ID = "film_s0_7.20_9.80"


def _seed(store, job_id="j1"):
    store.create_mix_job(job_id, ["u0"], 20, "free")
    store.update_mix_job(
        job_id, status="ready_for_review",
        extract={"s0": {"video_id": "s0", "full_text": "x", "segments": _SEGS}},
        edit_plan={
            "structure": "free", "plagiarism_flags": [],
            "beats": [{"beat_idx": 0, "role": "훅", "narration": "안방 분위기 환하게",
                       "target_seconds": 3.0,
                       "primary": {"video_id": "s0", "seg_id": "s0-1",
                                   "start": 2.0, "end": 4.5},
                       "alternates": [], "effect": "cut"}]})
    return job_id


def _apply_film_cut(client, job_id="j1"):
    """사장님 동작 재현: 필름에서 7.2~9.8초를 오려 1번 칸에 담고 저장."""
    r = client.post(f"/api/mix/scene_lab/{job_id}/apply", json={"payload": {
        "beats": [{"beat_idx": 0, "list": [FILM_ID], "stretch": False}],
        "extra_segs": {FILM_ID: {"video_id": "s0", "start": 7.2, "end": 9.8,
                                 "label": "필름 7.2~9.8초", "text": ""}},
    }})
    assert r.status_code == 200, r.text
    assert r.json().get("ok"), r.text


# ── ① 왕복: 담고 → 다시 열면 조각이 살아 있어야 한다 ────────────────────────

def test_film_seg_survives_reopen(monkeypatch, tmp_path):
    """★이것이 고객 제보 그 자체다 — 다시 열었을 때 조각이 있어야 한다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    _apply_film_cut(client)

    # 편성에는 담겼나(여기까진 종전에도 됐다)
    plan = store.get_mix_job("j1")["edit_plan"]
    ov = [s["seg_id"] for s in (plan["beats"][0].get("scene_override") or [])]
    assert FILM_ID in ov, "담은 조각이 편성에 없다 — 저장 자체가 안 된 것"

    # ★자막제거를 다녀온 것과 같은 상태: 브라우저 저장본 없이 서버에서만 다시 읽는다
    d = client.get("/api/mix/scene_lab/j1").json()
    assert d["ok"], d
    segs = d["data"]["segments"]

    # 편성이 가리키는 id는 **반드시** segments에 있어야 한다.
    # 없으면 화면에서 srcNo()·segNo()가 0이 되어 배지가 '0-0', 길이 0.0,
    # 썸네일은 404 → 검은 칸이 된다(= 사장님이 보신 화면).
    assert FILM_ID in segs, (
        "오려낸 조각이 사라졌다 — 화면에선 '0-0'·검은칸으로 보인다. "
        f"segments 키: {sorted(segs)}")

    # 구간까지 정확히 살아있어야 실제로 그 화면이 나온다(id에 들어있던 값)
    assert abs(segs[FILM_ID]["start"] - 7.2) < 0.01
    assert abs(segs[FILM_ID]["end"] - 9.8) < 0.01
    assert segs[FILM_ID]["video_id"] == "s0"


# ── ② 편성이 가리키는 id는 하나도 빠짐없이 그려질 수 있어야 한다 ─────────────

def test_no_orphan_ids_in_override(monkeypatch, tmp_path):
    """0-0 배지의 일반 조건 — override의 어떤 id도 미아가 되면 안 된다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    _apply_film_cut(client)

    d = client.get("/api/mix/scene_lab/j1").json()["data"]
    segs = set(d["segments"])
    orphans = []
    for b in d["beats"]:
        for s in (b.get("scene_override") or []):
            if s.get("seg_id") not in segs:
                orphans.append(s.get("seg_id"))
    assert not orphans, f"segments에 없는 id가 편성에 있다(화면에서 0-0): {orphans}"


# ── ③ 되살리는 함수는 이미 있다 — 계약을 박아 회귀를 막는다 ─────────────────

def test_film_id_roundtrip_parses(monkeypatch, tmp_path):
    """id 문자열만으로 영상·시작·끝이 복원된다(그래서 옛 고객 작업도 살릴 수 있다)."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    job = store.get_mix_job("j1")
    got = app_module._film_seg_from_id(FILM_ID, job)
    assert got, "film_ id를 못 읽는다 — 복구 경로가 끊긴다"
    assert got["video_id"] == "s0"
    assert abs(got["start"] - 7.2) < 0.01 and abs(got["end"] - 9.8) < 0.01


def test_film_id_rejects_unknown_source(monkeypatch, tmp_path):
    """경로 방어는 유지 — 이 잡의 소스가 아니면 통과시키지 않는다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    job = store.get_mix_job("j1")
    assert app_module._film_seg_from_id("film_other_1.00_2.00", job) is None


# ── ④ 저장까지 남아야 다음 사람이 또 안 밟는다 ──────────────────────────────

def test_extra_segs_persisted_in_plan(monkeypatch, tmp_path):
    """apply가 받은 extra_segs가 편성에 남아야 한다.

    ★id 파싱만으로도 film_은 되살아나지만, label·text 같은 사람이 만든 정보는
      id에 없다. 저장해 두면 복원이 파싱에만 기대지 않는다(이중 안전).
    """
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    _apply_film_cut(client)
    plan = store.get_mix_job("j1")["edit_plan"]
    saved = (plan.get("scene_lab") or {}).get("extra_segs") or {}
    assert FILM_ID in saved, (
        "extra_segs가 저장되지 않는다 — 화면 저장본(localStorage)에만 있어서 "
        "다른 PC·자막제거 왕복이면 통째로 증발한다")
    assert abs(float(saved[FILM_ID]["start"]) - 7.2) < 0.01
