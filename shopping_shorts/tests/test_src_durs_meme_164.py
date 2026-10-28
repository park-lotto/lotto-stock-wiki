# -*- coding: utf-8 -*-
"""관제 164: 컷 길이표(_src_durs_for)가 맨 앞 감정짤 파일도 잰다 — 빠지면 짤 칸마다 src_unreadable + clean_cut_drift 경보."""
from shopping_shorts import mix_pipeline as mp


class _St:
    def get_scene_asset(self, aid, customer_id=0):
        return {"media_path": "/m/%s.mp4" % aid} if customer_id == 0 else None


def _job():
    return {"job_id": "j164", "customer_id": 7, "edit_plan": {"beats": [
        {"beat_idx": 0},
        {"beat_idx": 3, "cutaway": {"match_type": "meme", "owner": 0, "asset_id": 1012,
                                     "vid": "meme_1012", "head_sec": 1.37}}]}}


def test_src_durs_includes_meme(monkeypatch):
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, work: {"s0": "/w/s0.mp4"})
    monkeypatch.setattr(mp, "Store", lambda *_a, **_k: _St())
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 1.38 if "1012" in str(p) else 20.0)
    d = mp._src_durs_for(_job(), "/w")
    assert d == {"s0": 20.0, "meme_1012": 1.38}


def test_job_meme_sources_none_without_meme():
    assert mp.job_meme_sources(_St(), {"edit_plan": {"beats": [{"beat_idx": 0}]}}) == {}
