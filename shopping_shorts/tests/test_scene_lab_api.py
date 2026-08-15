# -*- coding: utf-8 -*-
"""장면실험실 제작소 이식(2026-08-15) — 서버 API 계약 테스트.

핵심 계약:
  ① /api/mix/segments 는 기존 키를 하나도 안 바꾸고 shot_role·is_key·phash만 **추가**한다
     (기존 피커 화면이 이 응답을 쓴다 — 제거·이름변경은 회귀다).
  ② /api/mix/scene_lab/{job} 은 로컬 fetch.py가 만들던 data.json과 같은 모양을 준다
     (같은 UI 파일(scene_lab.html)이 모드 분기 없이 돌기 위한 전제).
  ③ apply/revert 는 edit_plan.apply_scene_lab을 통해 **얹기만** 한다(원본 무파괴) —
     렌더·생성 중엔 409로 막는다(진행 중 잡의 발밑을 빼면 안 된다).
  ④ phash 는 캐시가 없으면 ""/{} 로 폴백 — 소비자는 중복접기만 끈다(깨지지 않는다).
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    return TestClient(app_module.app), Store(db)


_SEGS = [  # 5개 미만 → _build_inventory가 첫·끝을 안 자른다(전부 살아남음)
    {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "반죽 섞기",
     "shot_role": "사용중", "is_key": False},
    {"seg_id": "s0-1", "start": 2.0, "end": 4.5, "text": "b", "scene_desc": "완성 쿠키",
     "shot_role": "완성", "is_key": True},
    {"seg_id": "s0-2", "start": 4.5, "end": 6.0, "text": "c", "scene_desc": "단면"},
]


def _seed(store, job_id="j1", status="ready_for_review"):
    store.create_mix_job(job_id, ["u0"], 20, "free")
    store.update_mix_job(
        job_id, status=status,
        extract={"s0": {"video_id": "s0", "full_text": "x", "segments": _SEGS}},
        edit_plan={
            "structure": "free", "plagiarism_flags": [],
            "beats": [{"beat_idx": 0, "role": "훅", "narration": "이 쿠키 하나로 끝",
                       "target_seconds": 3.0,
                       "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 4.5},
                       "alternates": [], "effect": "cut"}]})


# ── ① /api/mix/segments — 필드 추가(기존 키 불변) ────────────────────────────

def test_segments_adds_shot_role_is_key_phash(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    d = client.get("/api/mix/segments/j1").json()
    assert d["ok"]
    by_id = {s["seg_id"]: s for s in d["segments"]}
    # 기존 키 전부 그대로
    s = by_id["s0-0"]
    for k in ("seg_id", "video_id", "start", "end", "dur", "scene_desc", "text",
              "thumb_url", "used"):
        assert k in s, f"기존 키 {k}가 사라졌다 — 기존 피커 회귀"
    # 새 키
    assert s["shot_role"] == "사용중" and s["is_key"] is False
    assert by_id["s0-1"]["shot_role"] == "완성" and by_id["s0-1"]["is_key"] is True
    assert by_id["s0-2"]["shot_role"] == "기타"          # 없으면 '기타'(실험실 groupOf와 동일)
    assert all(x["phash"] == "" for x in d["segments"])  # 캐시 없음 → 빈 문자열 폴백


def test_segments_phash_from_cache(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    f = tmp_path / "work" / "j1" / "seg_thumbs" / "phash.json"
    f.parent.mkdir(parents=True)
    f.write_text('{"s0-1": "%s"}' % ("10" * 32), encoding="utf-8")
    d = client.get("/api/mix/segments/j1").json()
    by_id = {s["seg_id"]: s for s in d["segments"]}
    assert by_id["s0-1"]["phash"] == "10" * 32
    assert by_id["s0-0"]["phash"] == ""


# ── ② /api/mix/scene_lab/{job} — data.json과 같은 모양 ──────────────────────

def test_scene_lab_data_shape(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    d = client.get("/api/mix/scene_lab/j1").json()
    assert d["ok"]
    data = d["data"]
    assert data["job_id"] == "j1"
    assert data["syll_per_sec"] > 0
    assert set(data["segments"]) == {"s0-0", "s0-1", "s0-2"}
    seg = data["segments"]["s0-1"]
    assert seg["shot_role"] == "완성" and seg["is_key"] is True
    assert seg["video_id"] == "s0" and seg["start"] == 2.0 and seg["end"] == 4.5
    # 자막: 라이브와 같은 함수로 계산된 구절 타임라인(시각이 단조 증가)
    rows = data["captions"]["0"]
    assert rows and all(r["end"] > r["start"] for r in rows)
    assert all(rows[i]["start"] <= rows[i + 1]["start"] for i in range(len(rows) - 1))
    # tts mp3가 없으면 None / 소스 mp4가 없으면 {} — 폴백이 500을 안 낸다
    assert data["tts_dur"]["0"] is None
    assert data["src_duration"] == {}
    assert data["phash"] == {}
    # 비트는 편집안 그대로(실험실 baseList가 primary/alternates를 읽는다)
    assert data["beats"][0]["primary"]["seg_id"] == "s0-1"


def test_scene_lab_data_404s(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    assert client.get("/api/mix/scene_lab/없는잡").status_code == 404
    store.create_mix_job("j2", ["u0"], 20, "free")   # extract 없음
    assert client.get("/api/mix/scene_lab/j2").status_code == 404
    store.update_mix_job(
        "j2", extract={"s0": {"video_id": "s0", "full_text": "x", "segments": _SEGS}})
    r = client.get("/api/mix/scene_lab/j2")          # extract는 있는데 편집안이 아직
    assert r.status_code == 404 and "편집안" in r.json()["error"]


def test_scene_lab_phash_endpoint(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    assert client.get("/api/mix/scene_lab/j1/phash").json() == {"ok": True, "phash": {}}
    assert client.get("/api/mix/scene_lab/없는잡/phash").status_code == 404


# ── ③ apply / revert ─────────────────────────────────────────────────────────

def test_scene_lab_apply_and_revert(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    payload = {"beats": [{"beat_idx": 0, "list": ["s0-0", "s0-2", "유령seg"], "stretch": True}],
               "trims": {"s0-0": [0.5, 1.0]}}
    r = client.post("/api/mix/scene_lab/j1/apply", json={"payload": payload})
    assert r.status_code == 200 and r.json()["applied"] == 1
    plan = store.get_mix_job("j1")["edit_plan"]
    b = plan["beats"][0]
    # 트림 두 토막 + s0-2, 유령은 걸러짐. 원본 primary는 그대로(얹기만).
    assert [(s["seg_id"], s["start"], s["end"]) for s in b["scene_override"]] == \
        [("s0-0", 0.0, 0.5), ("s0-0", 1.0, 2.0), ("s0-2", 4.5, 6.0)]
    assert b["stretch_fill"] is True
    assert b["primary"]["seg_id"] == "s0-1"
    # revert → 100% 원상
    assert client.post("/api/mix/scene_lab/j1/apply", json={"revert": True}).json()["reverted"]
    plan = store.get_mix_job("j1")["edit_plan"]
    assert "scene_override" not in plan["beats"][0]
    assert "scene_lab" not in plan


def test_scene_lab_apply_guards(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    assert client.post("/api/mix/scene_lab/없는잡/apply", json={"revert": True}).status_code == 404
    _seed(store, "jr", status="rendering")           # 렌더 중 → 409
    assert client.post("/api/mix/scene_lab/jr/apply",
                       json={"payload": {"beats": [{"beat_idx": 0, "list": ["s0-0"]}]}}
                       ).status_code == 409
    _seed(store, "je")                               # 빈 payload → 422
    assert client.post("/api/mix/scene_lab/je/apply", json={"payload": {}}).status_code == 422


# ── ④ phash 헬퍼(순수 부분) ──────────────────────────────────────────────────

def test_phash_bits_pure():
    raw = bytes(range(64))                            # 0..63 → 평균 31.5, 뒤 절반이 1
    bits = app_module._lab_phash_bits(raw)
    assert len(bits) == 64 and set(bits) <= {"0", "1"}
    assert bits == "0" * 32 + "1" * 32
    assert app_module._lab_phash_bits(b"") == ""      # 짧으면 빈 값(깨지지 않는다)
    assert app_module._lab_phash_bits(b"x" * 63) == ""


def test_phash_from_missing_jpg_is_empty(tmp_path):
    assert app_module._lab_phash_from_jpg(tmp_path / "없다.jpg") == ""


def test_phash_ensure_writes_cache(monkeypatch, tmp_path):
    # ffmpeg 없이도 돌게 계산부만 스텁 — 캐시 계약(한 번 계산·재사용)만 본다
    monkeypatch.setattr(app_module, "_lab_phash_from_jpg", lambda p: "01" * 32)
    work = tmp_path / "w"
    assert app_module._lab_phash_ensure(work, "s0-0", work / "t.jpg") == "01" * 32
    assert app_module._lab_phash_load(work) == {"s0-0": "01" * 32}
    # 두 번째 호출은 캐시를 그대로 쓴다(계산부가 죽어도 값이 나온다)
    monkeypatch.setattr(app_module, "_lab_phash_from_jpg", lambda p: (_ for _ in ()).throw(RuntimeError))
    assert app_module._lab_phash_ensure(work, "s0-0", work / "t.jpg") == "01" * 32
