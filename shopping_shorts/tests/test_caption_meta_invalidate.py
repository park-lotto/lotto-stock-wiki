"""대본이 바뀌면 자막 메타(caption_lines·cap_durs·cap_lead)를 반드시 버린다(2026-08-15).

실사고(잡 409f894230c6): cap_durs·cap_lead는 합성 시점에만 계산되고 무효화가 없어서,
대본 편집 뒤 렌더가 **옛 대본 기준** 타이밍으로 자막을 그렸다(구절 수 전 칸 불일치 +
낡은 lead → 자막이 mp3보다 늦게 끝남). 판단은 mix_pipeline.invalidate_caption_meta
한 곳에 있고(0순위-B), 편집 경로 두 곳(/api/mix/candidate 편집·/shorten)이 부른다.
"""
from fastapi.testclient import TestClient

import shopping_shorts.app as app_mod
import shopping_shorts.mix_pipeline as mp
from shopping_shorts.store import Store

_STALE = {"caption_lines": ["옛 대본", "구절들"], "cap_durs": [1.1, 0.9], "cap_lead": 0.21}


def test_invalidate_caption_meta_unit():
    beat = {"narration": "새 대사", **_STALE}
    mp.invalidate_caption_meta(beat)
    assert beat["caption_lines"] is None
    assert beat["cap_durs"] is None
    assert beat["cap_lead"] == 0.0


def _cand(hook, extra=None):
    b = {"beat_idx": 0, "narration": hook,
         "primary": {"video_id": "v1", "start": 0.0, "end": 2.0}}
    b.update(extra or {})
    return {"recommended": True, "score": 0.5,
            "story": {"hook": hook}, "plan": {"beats": [b]}}


def test_candidate_edit_clears_stale_caption_meta(tmp_path, monkeypatch):
    """/api/mix/candidate에 narrations를 실어 대본을 고치면 그 비트의 자막 메타가 비워진다."""
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    store = Store(tmp_path / "t.db")
    store.create_mix_job("J1", ["https://x/1"], 30, "template")
    store.set_mix_candidates("J1", [_cand("원래 훅 대사", extra=_STALE)])
    client = TestClient(app_mod.app)
    r = client.post("/api/mix/candidate",
                    json={"job_id": "J1", "index": 0, "narrations": ["고쳐 쓴 훅 대사"]})
    assert r.json() == {"ok": True, "edited": True}
    beat = store.get_mix_job("J1")["edit_plan"]["beats"][0]
    assert beat["narration"] == "고쳐 쓴 훅 대사"
    assert beat["caption_lines"] is None, "옛 대본의 자막줄이 남았다"
    assert beat["cap_durs"] is None, "옛 대본 기준 구절 타이밍이 남았다"
    assert beat["cap_lead"] == 0.0, "옛 lead가 남아 자막 시작이 밀린다"


def test_candidate_unedited_beat_keeps_caption_meta(tmp_path, monkeypatch):
    """안 고친 비트(원문 그대로)는 실측 타이밍을 그대로 쓴다 — 과잉 무효화 금지."""
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    store = Store(tmp_path / "t.db")
    store.create_mix_job("J1", ["https://x/1"], 30, "template")
    store.set_mix_candidates("J1", [_cand("원래 훅 대사", extra=_STALE)])
    client = TestClient(app_mod.app)
    r = client.post("/api/mix/candidate",
                    json={"job_id": "J1", "index": 0, "narrations": ["원래 훅 대사"]})
    assert r.json() == {"ok": True, "edited": False}
    beat = store.get_mix_job("J1")["edit_plan"]["beats"][0]
    assert beat["cap_durs"] == [1.1, 0.9] and beat["cap_lead"] == 0.21


def test_shorten_clears_stale_caption_meta(tmp_path, monkeypatch):
    """✂ 자동 줄이기도 caption_lines만이 아니라 cap_durs·cap_lead까지 지운다."""
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(app_mod, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(mp, "synthesize_line", lambda *a, **k: "")
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 2.0)
    monkeypatch.setattr(mp, "_MAX_SLOWMO", 1.0)
    monkeypatch.setattr(app_mod._edit_plan, "conform_narration", lambda n, b, **k: "짧은 대사")
    store = Store(app_mod.DB_PATH)
    store.create_mix_job("j1", ["u0"], 20, "free")
    plan = {"beats": [{"beat_idx": 0, "narration": "이거 정말 너무 길게 늘어지는 대사예요",
                       "role": "훅", "sync_gap": 1.5,
                       "primary": {"seg_id": "s0-0", "start": 0.0, "end": 2.0},
                       "alternates": [], **_STALE}]}
    store.update_mix_job("j1", edit_plan=plan)
    client = TestClient(app_mod.app)
    r = client.post("/api/produce/mix/j1/shorten", json={"beat_idx": 0})
    assert r.json()["ok"] and r.json()["changed"] is True
    beat = store.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert beat["caption_lines"] is None
    assert beat["cap_durs"] is None
    assert beat["cap_lead"] == 0.0
