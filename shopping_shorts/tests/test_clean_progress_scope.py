# -*- coding: utf-8 -*-
"""자막제거 진행 표시 — 완성본 1편 경로는 '편'이 아니라 범위(고른 장면 N개/전체)를 말한다(2026-09-27)."""
from shopping_shorts import app as A
from shopping_shorts import mix_pipeline as mp


def test_final_path_reports_scope_not_source_count(monkeypatch):
    monkeypatch.setattr(mp, "_clean_strategy", lambda j: "final")
    job = {"urls": ["a", "b", "c", "d", "e"], "clean_sources": None, "clean_cuts": ["2|s2|0.00"]}
    done, total, scope = A._clean_progress(job, "cleaning")
    assert (done, total) == (0, 1) and scope == {"mode": "picked", "n": 1}         # "5편 중 0편"이 아니다
    done, total, scope = A._clean_progress(dict(job, clean_cuts=None), "ready")
    assert (done, total) == (1, 1) and scope["mode"] == "all"


def test_sources_path_keeps_old_count(monkeypatch):
    monkeypatch.setattr(mp, "_clean_strategy", lambda j: "sources")
    job = {"urls": ["a", "b", "c"], "clean_sources": {"s0": "x", "s1": "y"}}
    assert A._clean_progress(job, "cleaning")[:2] == (2, 3)


def test_running_placeholder_uses_edit_cut_not_first_source_middle():
    """지우는 동안 자리표시 그림은 편성 컷(clean_pick_thumb)이어야 한다 — 첫 소스 한가운데(clean_thumb 기본)가 아니라."""
    from pathlib import Path
    src = (Path(A.__file__).parent / "static" / "produce.html").read_text(encoding="utf-8")
    i = src.index("async function startCleanPreview("); j = src.index("function updateCleanProgress", i)
    body = src[i:j]
    assert "clean_pick_thumb" in body and "_phUrl" in body
    assert body.count("<img src=\"'+_phUrl+'\"") == 2                                    # BEFORE·지우는 중 그림 둘 다 편성 컷 주소
    assert body.count("clean_thumb/'+encodeURIComponent(myJob)+'?kind=original&t=") == 1  # 옛 주소는 대체 경로(_phUrl 폴백) 한 곳뿐
    assert "clean_scope" in src[j:j + 1500]
