# -*- coding: utf-8 -*-
"""최종렌더 전 안내 API — 정본이면 바뀐 장면 초수·크레딧만 알린다."""
import json
import shutil

from shopping_shorts import app as A
from shopping_shorts import clean_base as cb


def _setup(tmp_path, monkeypatch, setting="1"):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 0.0, "end": 2.5}, "alternates": []}]}
    work = tmp_path / "jobx"; work.mkdir()
    (work / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    cb.save_base(work, sig="x", path=str(work / "final_clean_x.mp4"), plan={"beats": plan["beats"][:1]},
                 cuts=[{"video_id": "s0", "beat_idx": 0, "src": 1.0, "fin": 0.0, "dur": 2.0}])
    job = {"edit_plan": plan, "subtitle_removal": 1, "customer_id": 0, "clean_tier": "basic"}
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    class _S:
        def get_mix_job(self, j): return job
        def get_setting(self, k, d=None): return setting
    monkeypatch.setattr(A, "Store", lambda db: _S())
    # 안내 초 = 증분 청소가 보낼 초(원본 파일을 찾는 조각만, 2026-09-27) — 이 가짜 job 엔 urls 가 없어 원본 지도를 직접 준다
    from shopping_shorts import mix_pipeline as _mp
    monkeypatch.setattr(_mp, "_resolve_sources", lambda j, w: {"s0": str(work / "s0.mp4"), "s1": str(work / "s1.mp4")})
    return job


def test_preview_lists_uncovered_seconds(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    out = A.api_produce_mix_clean_base_preview("jobx")
    assert out["enabled"] is True and out["base"] is True
    assert out["uncovered"] == [{"beat_idx": 1, "seconds": 2.5}]
    assert out["est_credits"] == 6      # 기본 등급 1초 2크레딧 × 올림(2.5→3)


def test_preview_zero_when_all_covered(tmp_path, monkeypatch):
    job = _setup(tmp_path, monkeypatch)
    job["edit_plan"]["beats"] = job["edit_plan"]["beats"][:1]
    job["edit_plan"]["beats"][0]["caption_lines"] = ["가", "나"]
    out = A.api_produce_mix_clean_base_preview("jobx")
    assert out["uncovered"] == [] and out["extend"] == [] and out["est_credits"] == 0


def test_preview_disabled_when_switch_off(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, setting="")
    out = A.api_produce_mix_clean_base_preview("jobx")
    assert out["enabled"] is False


def test_produce_html_asks_before_render():
    """렌더 전 확인은 이제 **서버가 강제**한다(2026-09-27): /api/mix/render 가 409 + 안내를 주면 화면이 그 문구로 묻고
    표식(confirm_clean·confirm_secs)을 실어 다시 보낸다. 동작 검사는 test_clean_consent 의 node 테스트가 한다."""
    from pathlib import Path
    html = Path(A.__file__).parent.joinpath("static", "produce.html").read_text(encoding="utf-8")
    body = html.split("async function renderFinal(){", 1)[1].split("async function pollFinal(", 1)[0]
    assert "need_clean_confirm" in body and "confirm_secs" in body and "추가 과금 없음" in body
