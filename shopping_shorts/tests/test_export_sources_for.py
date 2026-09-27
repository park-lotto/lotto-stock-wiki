"""캡컷·ZIP 내보내기의 재료 = 완성본이 쓴 소스·청소 그대로 (mix_pipeline.export_sources_for / clean_route, 2026-09-27).

사고: ZIP(`/api/mix/export`)엔 청소 분기가 없어, 정본 없는 자막제거 job 에서 **원본(자막 박힌) 조각**을 담았다
(서버 4 job 104컷). 캡컷 라우트는 따로 적은 분기로 청소 완성본 조각을 썼다 = 같은 판단이 세 벌(렌더·캡컷·ZIP).
여기서는 실제 job·실제 mp4(ffmpeg)로 라우트를 불러 ZIP 조각이 **어느 파일에서** 잘리는지 본다.
"""
import zipfile
from pathlib import Path

from shopping_shorts import app as app_module, export_bundle, mix_pipeline as mp
from shopping_shorts.store import Store
from shopping_shorts.tests.test_app_export import _mk_video, _seed


def _zip_cuts(monkeypatch, client, part="sources"):
    rec = []
    real = export_bundle._cut_clip

    def spy(src, a, e, out):
        rec.append((str(src), float(a), float(e), Path(str(out)).name))
        return real(src, a, e, out)
    monkeypatch.setattr(export_bundle, "_cut_clip", spy)
    r = client.get("/api/mix/export/j1", params={"part": part} if part else None)
    return r, rec


def _subtitle_job_with_clean_final(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    store = Store(app_module.DB_PATH)
    store.update_mix_job("j1", subtitle_removal=1, clean_status="ready", clean_video_path=None)
    job = store.get_mix_job("j1")
    work = app_module._MIX_WORK_DIR / "j1"
    _mk_video(work / f"final_clean_{mp._clean_sig(job)}.mp4", 4)
    return client, store, work


def test_zip_uses_cleaned_final_pieces_like_capcut(monkeypatch, tmp_path):
    """정본 없는 자막제거 job: ZIP 조각은 청소된 완성본 조각에서 잘린다(원본 s0 아님) — 캡컷과 같은 재료."""
    client, store, work = _subtitle_job_with_clean_final(monkeypatch, tmp_path)
    r, rec = _zip_cuts(monkeypatch, client)
    assert r.status_code == 200, r.text
    assert rec, "ZIP 조각이 하나도 없다"
    assert all(Path(s).name.startswith("capcut_src_s0_") for s, *_ in rec), [Path(s).name for s, *_ in rec]
    assert not any(Path(s).parent.name == "s0" for s, *_ in rec), "★원본(자막 박힌) 소스가 ZIP 에 들어갔다"
    # 캡컷과 같은 목록: 같은 함수가 같은 칸·같은 컷 수로 준다
    job = store.get_mix_job("j1")
    z = mp.export_sources_for(store, job, "j1", work, 0)
    c = mp.export_sources_for(store, job, "j1", work, 0, for_capcut=True)
    assert z["route"] == c["route"] == "final"
    assert sorted(z["source_video_paths"]) == sorted(c["source_video_paths"]) == ["s0"], "소스 영상별(s0) 한 파일"
    assert [b["beat_idx"] for b in z["timeline"]] == [b["beat_idx"] for b in c["timeline"]]
    assert [round(b["dur"], 3) for b in z["timeline"]] == [round(b["dur"], 3) for b in c["timeline"]]


def test_zip_without_subtitle_removal_uses_originals(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    r, rec = _zip_cuts(monkeypatch, client)
    assert r.status_code == 200 and rec
    assert all(Path(s).parent.name == "s0" for s, *_ in rec)


def test_zip_refuses_subtitled_sources_when_clean_final_missing(monkeypatch, tmp_path):
    """청소 완성본이 있어야 하는데 없으면 sources 만 409 — 전체 ZIP 은 조각 없이(srt·script 는 준다)."""
    client = _seed(monkeypatch, tmp_path)
    Store(app_module.DB_PATH).update_mix_job("j1", subtitle_removal=1, clean_status="ready", clean_video_path=None)
    r, rec = _zip_cuts(monkeypatch, client)
    assert r.status_code == 409 and not rec
    r2, rec2 = _zip_cuts(monkeypatch, client, part="")
    assert r2.status_code == 200 and not rec2
    out = app_module._MIX_WORK_DIR / "j1" / "export_all.zip"
    names = zipfile.ZipFile(out).namelist()
    assert "captions.srt" in names and not any(n.startswith("sources/") for n in names)


def test_clean_route_single_rule(monkeypatch):
    base = {"path": "/w/final_clean_x.mp4"}
    assert mp.clean_route({"subtitle_removal": 1}, base) == "base"
    assert mp.clean_route({"subtitle_removal": 0}, None) == "none"
    assert mp.clean_route({"subtitle_removal": 1}, None, skip_clean=True) == "none"
    assert mp.clean_route({"subtitle_removal": 1, "clean_sources": {"s0": "/c.mp4"}}, None) == "sources"
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    assert mp.clean_route({"subtitle_removal": 1}, None) == "final"
    monkeypatch.setattr(mp, "_FINAL_CLEAN", False)
    assert mp.clean_route({"subtitle_removal": 1}, None) == "sources"          # 렌더: 앞으로 만들 방식(스위치)
    assert mp.clean_route({"subtitle_removal": 1}, None, made=True) == "final"  # 내보내기: 이미 만든 완성본
    assert mp.clean_route({"subtitle_removal": 1, "clean_sources": {"s0": "/c"}}, None, made=True) == "sources"


def test_with_clean_sources_only_overlays_known_ids():
    assert mp.with_clean_sources({"s0": "/o0", "s1": "/o1"}, {"s1": "/c1", "s9": "/c9"}) == {"s0": "/o0", "s1": "/c1"}
