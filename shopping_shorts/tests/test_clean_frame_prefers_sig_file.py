# -*- coding: utf-8 -*-
"""자막제거는 됐는데 6단계 꾸미기엔 원본 자막이 그대로 (2026-09-02 사장님 제보).

★뿌리: clean_video_path는 **2단계 미리보기 때 만든 clean_preview.mp4**에서 멈춘다.
  그 뒤 편성을 바꾸고 최종렌더를 돌리면 새 서명의 청소본(final_clean_{sig}.mp4)이
  생기지만 clean_video_path는 옛 파일 그대로 → clean_final_matches_plan의 mtime 대조가
  stale로 판정 → 꾸미기 컷 프레임이 통째로 **원본**에서 떠 자막이 살아 있었다.

실측(라이브 job 8b5aed8af66b, 2026-09-02): clean_status=ready·subtitle_removal=1인데
  beatframes 캐시가 전부 `_src` 태그(=원본에서 뜸).
  cvp=clean_preview.mp4(00:39) < final_clean_aeff3b87cfcb1ca3.mp4(08:25).

계약: 지금 편성 서명의 청소본 파일이 있으면 그걸 쓰고 fresh=True다.
"""
from pathlib import Path

from shopping_shorts import app as A
from shopping_shorts import mix_pipeline


def _job(plan, cvp):
    return {"clean_status": "ready", "clean_video_path": str(cvp),
            "clean_sources": {}, "edit_plan": plan}


def _mk(p, size=4096):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"0" * size)
    return p


def test_지금_편성의_청소본이_있으면_그걸_쓴다(tmp_path, monkeypatch):
    plan = {"beats": [{"beat_idx": 0, "primary": {"video_id": "s0", "start": 0}}]}
    sig = mix_pipeline._plan_signature(plan)
    stale = _mk(tmp_path / "clean_preview.mp4")
    fresh = _mk(tmp_path / ("final_clean_%s.mp4" % sig))
    monkeypatch.setattr(A, "_resolve_sources", lambda *a, **k: {})
    monkeypatch.setattr(A.frame_extract, "_probe_duration", lambda *a, **k: 30.0)

    cmap, cfin, ratio, tag, is_fresh = A._clean_frame_src(_job(plan, stale), tmp_path, 0)

    assert cfin == str(fresh), "옛 clean_preview를 쓴다 — 컷 프레임이 원본으로 떨어진다"
    assert is_fresh is True, "fresh가 아니면 컷 프레임이 원본에서 뜬다(자막이 남는다)"
    assert tag.startswith("_clean") and tag != "_clean", "캐시 태그가 서명으로 안 갈린다"


def test_서명_청소본이_없으면_종전대로_판정한다(tmp_path, monkeypatch):
    plan = {"beats": [{"beat_idx": 0, "primary": {"video_id": "s0", "start": 0}}]}
    stale = _mk(tmp_path / "clean_preview.mp4")
    monkeypatch.setattr(A, "_resolve_sources", lambda *a, **k: {})
    monkeypatch.setattr(A.frame_extract, "_probe_duration", lambda *a, **k: 30.0)

    cmap, cfin, ratio, tag, is_fresh = A._clean_frame_src(_job(plan, stale), tmp_path, 0)

    assert cfin == str(stale)
    assert is_fresh is False, "편성이 바뀐 뒤 재청소 전이면 원본에서 뜨는 것이 맞다"
    assert tag == "_clean"
