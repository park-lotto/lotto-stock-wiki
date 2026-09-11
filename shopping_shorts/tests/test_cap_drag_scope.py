"""자막 드래그 적용 범위(2026-08-31 사장님 "한장면씩 적용이랑 모두 적용").

  · {beat_idx, seg_idx, x_pct, y_pct} → 지금 보이는 자막 한 줄에만 cap_xy_segs 저장
  · {beat_idx, x_pct, y_pct} → 옛 화면 호환: 그 비트 전체에 cap_xy 저장
  · {apply_all: true}        → 모든 장면의 장면별 덮어쓰기를 지운다(전체 설정이 이긴다)
  · 렌더(_beat_cap_style)는 cap_xy를 cap_pos보다 먼저 본다
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts import video_assemble
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _job(store, jid, beats):
    store.create_mix_job(jid, ["u0"], 20, "free")
    store.update_mix_job(jid, status="ready_for_review", edit_plan={"beats": beats})


def test_drag_one_scene_saves_xy_only_there(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "j1", [{"beat_idx": 0, "narration": "가"}, {"beat_idx": 1, "narration": "나"}])
    r = client.post("/api/produce/mix/j1/cappos", json={"beat_idx": 1, "x_pct": 22, "y_pct": 40})
    assert r.status_code == 200 and r.json()["ok"]
    assert r.json()["xy"] == {"x_pct": 22.0, "y_pct": 40.0}
    beats = store.get_mix_job("j1")["edit_plan"]["beats"]
    assert beats[1]["cap_xy"] == {"x_pct": 22.0, "y_pct": 40.0}
    assert not beats[0].get("cap_xy")           # 옆 장면은 안 건드린다
    # 미리보기도 같은 값을 내려준다(보는 것=나오는 것)
    pv = client.get("/api/produce/mix/beats_preview/j1").json()["beats"]
    assert pv[1]["cap_xy"] == {"x_pct": 22.0, "y_pct": 40.0} and pv[0]["cap_xy"] is None


def test_drag_one_visible_caption_saves_only_that_segment(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "seg1", [{"beat_idx": 0, "narration": "첫 문장 두 번째 문장",
                            "caption_lines": ["첫 문장", "두 번째 문장"]}])
    r = client.post("/api/produce/mix/seg1/cappos",
                    json={"beat_idx": 0, "seg_idx": 1, "x_pct": 68, "y_pct": 37})
    assert r.status_code == 200 and r.json()["ok"]
    assert r.json()["cap_xy_segs"] == {"1": {"x_pct": 68.0, "y_pct": 37.0}}
    beat = store.get_mix_job("seg1")["edit_plan"]["beats"][0]
    assert beat["cap_xy_segs"] == {"1": {"x_pct": 68.0, "y_pct": 37.0}}
    assert not beat.get("cap_xy")
    preview = client.get("/api/produce/mix/beats_preview/seg1").json()["beats"][0]
    assert preview["cap_xy_segs"] == beat["cap_xy_segs"]


def test_drag_visible_caption_rejects_invalid_segment(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "seg2", [{"beat_idx": 0, "narration": "한 줄"}])
    r = client.post("/api/produce/mix/seg2/cappos",
                    json={"beat_idx": 0, "seg_idx": 9, "x_pct": 20, "y_pct": 30})
    assert r.status_code == 422
    assert not store.get_mix_job("seg2")["edit_plan"]["beats"][0].get("cap_xy_segs")


def test_button_pos_clears_dragged_xy(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "j2", [{"beat_idx": 0, "narration": "가", "cap_xy": {"x_pct": 10.0, "y_pct": 10.0}}])
    r = client.post("/api/produce/mix/j2/cappos", json={"beat_idx": 0, "pos": "top"})
    assert r.status_code == 200
    b = store.get_mix_job("j2")["edit_plan"]["beats"][0]
    assert b["cap_pos"] == "top" and b["cap_xy"] is None


def test_button_pos_clears_segment_dragged_xy(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "j2s", [{"beat_idx": 0, "narration": "가",
                           "cap_xy_segs": {"0": {"x_pct": 10.0, "y_pct": 10.0}}}])
    r = client.post("/api/produce/mix/j2s/cappos", json={"beat_idx": 0, "pos": "top"})
    assert r.status_code == 200
    b = store.get_mix_job("j2s")["edit_plan"]["beats"][0]
    assert b["cap_pos"] == "top" and b["cap_xy_segs"] is None


def test_apply_all_clears_every_scene_override(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _job(store, "j3", [
        {"beat_idx": 0, "narration": "가", "cap_pos": "top"},
        {"beat_idx": 1, "narration": "나", "cap_xy": {"x_pct": 22.0, "y_pct": 40.0}},
        {"beat_idx": 2, "narration": "다", "cap_xy_segs": {"0": {"x_pct": 30, "y_pct": 50}}},
    ])
    r = client.post("/api/produce/mix/j3/cappos", json={"apply_all": True})
    assert r.status_code == 200 and r.json()["cleared"] == 3
    for b in store.get_mix_job("j3")["edit_plan"]["beats"]:
        assert not b.get("cap_pos") and not b.get("cap_xy") and not b.get("cap_xy_segs")


def test_render_prefers_cap_xy_over_cap_pos():
    base = {"y_pct": 84, "x_pct": 50}
    assert video_assemble._beat_cap_style(base, {}) is base
    assert video_assemble._beat_cap_style(base, {"cap_pos": "top"})["y_pct"] == 18.0
    st = video_assemble._beat_cap_style(base, {"cap_pos": "top", "cap_xy": {"x_pct": 22, "y_pct": 40}})
    assert st["x_pct"] == 22.0 and st["y_pct"] == 40.0
    assert base["y_pct"] == 84                  # 원본은 안 건드린다


def test_render_uses_segment_xy_only_for_target_caption(tmp_path, monkeypatch):
    calls = []

    def fake_segmented(text, style, work, key, x_pct, y_pct, **kwargs):
        calls.append((text, x_pct, y_pct))
        return [f"drawtext=text={text}"]

    monkeypatch.setattr(video_assemble, "_segmented_drawtext", fake_segmented)
    video_assemble._caption_drawtexts(
        "첫 문장 두 번째 문장", 2.0, tmp_path, 0,
        style={"x_pct": 50, "y_pct": 84}, cap_lines=["첫 문장", "두 번째 문장"],
        cap_xy_segs={"1": {"x_pct": 68, "y_pct": 37}},
    )
    assert calls == [("첫 문장", 50.0, 84), ("두 번째 문장", 68.0, 37.0)]
