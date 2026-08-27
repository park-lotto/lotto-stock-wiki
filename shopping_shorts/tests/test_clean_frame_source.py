# -*- coding: utf-8 -*-
"""청소된 화면을 어디서 뜰지 — 판단은 _clean_frame_src 한 곳 (2026-08-27).

★사고: 2단계를 완성본 1편 청소로 바꾸면서 clean_sources가 비게 됐는데, 그걸
  '자막제거 했나'의 판정으로 쓰던 화면들이 조용히 **원본을 보여줬다**.
    - clean_thumb  → 404 (AFTER 칸이 검게)
    - poster·beatframe → 원본 자막·워터마크가 그대로 (사장님 제보: "5단계 보면 안 지워져있자나")
  청소 자체는 정상이었다(청소본 프레임 실측: 자막 깨끗이 제거됨). 화면만 딴 파일을 봤다.
"""
from pathlib import Path

import pytest

from shopping_shorts import app as A


def _plan(n=3):
    return {"beats": [{"beat_idx": i, "target_seconds": 10.0,
                       "primary": {"video_id": f"s{i}", "start": 0.0, "end": 10.0},
                       "alternates": []} for i in range(n)]}


class Test청소화면_출처판단:
    def test_소스별_청소본이_있으면_그걸_쓴다(self, tmp_path):
        job = {"clean_sources": {"s0": "/clean/s0.mp4"}, "clean_status": "ready"}
        srcs, final, ratio, tag = A._clean_frame_src(job, tmp_path, 0)
        assert srcs == {"s0": "/clean/s0.mp4"}
        assert final is None and tag == "_clean"

    def test_완성본만_있으면_완성본에서_뜬다(self, tmp_path):
        cvp = tmp_path / "clean_preview.mp4"
        cvp.write_text("x")
        job = {"clean_sources": None, "clean_status": "ready",
               "clean_video_path": str(cvp), "edit_plan": _plan()}
        srcs, final, ratio, tag = A._clean_frame_src(job, tmp_path, 1)
        assert srcs == {}
        assert final == str(cvp), "완성본을 안 쓰면 원본 자막이 그대로 보인다"
        assert 0.3 < ratio < 0.7, ratio          # 3칸 중 가운데
        assert tag == "_clean", "캐시 이름을 안 가르면 원본 프레임이 재사용된다"

    def test_청소_전이면_아무것도_안_준다(self, tmp_path):
        job = {"clean_status": None, "edit_plan": _plan()}
        assert A._clean_frame_src(job, tmp_path, 0) == ({}, None, None, "")

    def test_청소중이면_아직_원본(self, tmp_path):
        cvp = tmp_path / "clean_preview.mp4"; cvp.write_text("x")
        job = {"clean_status": "cleaning", "clean_video_path": str(cvp), "edit_plan": _plan()}
        assert A._clean_frame_src(job, tmp_path, 0)[1] is None

    def test_파일이_사라졌으면_원본으로_폴백(self, tmp_path):
        job = {"clean_status": "ready", "clean_video_path": str(tmp_path / "없다.mp4"),
               "edit_plan": _plan()}
        assert A._clean_frame_src(job, tmp_path, 0) == ({}, None, None, "")

    def test_칸마다_다른_지점(self, tmp_path):
        cvp = tmp_path / "c.mp4"; cvp.write_text("x")
        job = {"clean_status": "ready", "clean_video_path": str(cvp), "edit_plan": _plan()}
        r0 = A._clean_frame_src(job, tmp_path, 0)[2]
        r2 = A._clean_frame_src(job, tmp_path, 2)[2]
        assert r0 < r2, "칸이 달라도 같은 그림이면 꾸미기 배경이 전부 같아진다"


class Test판단이_흩어지지_않았나:
    """★0순위-B — 화면 라우트가 clean_sources를 직접 보고 판단하면 이 사고가 재발한다."""

    def test_화면_라우트는_공용함수를_쓴다(self):
        import inspect
        for fn in (A.api_produce_mix_beatframe,):
            body = inspect.getsource(fn)
            assert "_clean_frame_src" in body, f"{fn.__name__}이 공용 판단을 안 쓴다"
            assert 'job.get("clean_sources")' not in body, \
                f"{fn.__name__}이 clean_sources를 또 직접 본다"
