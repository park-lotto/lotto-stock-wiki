# -*- coding: utf-8 -*-
"""스토리보드 생성 앞단이 라이브 환경에서 돈다(관제 120) — 시안 도구에서 옮길 때 남은 전역 DB 로 라이브 첫 생성이 NameError(2026-10-05)."""
from shopping_shorts import storyboard as sb


def test_writer_head_runs_without_tool_globals():
    fam = {"names": ["유튜브 시험"], "roles": ["title", "hook"], "tpl": {}, "voice": {}, "chain": [], "arc": "", "sit": "",
           "fit": set(), "core": []}
    sb._HEAD_CACHE.clear()
    assert "스토리보드" in sb._writer_head(fam, "")
