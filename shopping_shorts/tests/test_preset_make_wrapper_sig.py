# -*- coding: utf-8 -*-
"""PC 제작기 장면 캐시(preset_make.compose_cached)는 scene_style.render_layers·video_assemble._run_ffmpeg 를 껍데기로 바꿔 끼운다.
원래 함수에 인자가 새로 생기면 껍데기가 그 인자를 못 받아 PC 제작기 굽기가 멈춘다(10-29 _run_ffmpeg timeout → 11-03 TypeError, 2주 동안 아무도 몰랐다).
원래 함수 인자 꼴이 바뀌면 이 시험이 깨진다 — 껍데기(layers_cached·ff)와 캐시 열쇠를 같이 맞춘 뒤 아래 꼴을 고친다."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shopping_shorts import scene_style as SS, video_assemble as VA  # noqa: E402
from tools.calcopy.engine import preset_make as PM  # noqa: E402

LAYERS = ["timeline", "snapshot", "output", "headcopy", "job_id", "only"]     # layers_cached 가 받는 것(only = 부분 렌더 → 캐시 없이 그대로)
FFMPEG = ["cmd", "cwd", "timeout"]                                   # ff 가 받는 것(cmd·cwd + 나머지는 **kw 로 그대로)


def test_render_layers_signature_matches_cache_wrapper():
    assert list(inspect.signature(SS.render_layers).parameters) == LAYERS


def test_run_ffmpeg_signature_matches_cache_wrapper():
    assert list(inspect.signature(VA._run_ffmpeg).parameters) == FFMPEG


def test_ff_wrapper_forwards_every_keyword():
    """껍데기 ff 가 **kw 를 받는지 — 원래 함수 새 인자가 껍데기에서 막히지 않게(소스에서 확인)."""
    src = inspect.getsource(PM.compose_cached)
    assert "def ff(cmd, cwd=None, **kw):" in src and src.count("orig_ff(cmd, cwd, **kw)") >= 2


def test_layers_wrapper_takes_same_params():
    src = inspect.getsource(PM.compose_cached)
    assert "def layers_cached(timeline, snapshot, output, headcopy=None, job_id=None, only=None):" in src
