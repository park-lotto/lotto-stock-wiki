# -*- coding: utf-8 -*-
"""tools 시험 공통 설정.

★묶음 병합의 '30초 모으기'(track.BATCH_GATHER_SEC)는 시험에서 0 — finish 를 실제로 부르는 시험이 약 45개라
  안 끄면 관문이 돌 때마다 22분을 그냥 기다린다(2026-10-15 실측: 관문 시험 11분 → 40분대, 일꾼 CPU 12%).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def _no_batch_gather(monkeypatch):
    try:
        import track
    except Exception:  # noqa: BLE001 — track 을 못 읽는 시험 폴더면 할 일 없음
        return
    monkeypatch.setattr(track, "BATCH_GATHER_SEC", 0, raising=False)
    # ★시험은 PC 의 실제 남은 메모리에 끌려가면 안 된다 — 관문 안에서 돌면 관문 자신의 일꾼 8개가 메모리를 써서
    #   finish 시험 45개가 '남은 메모리 5.6GB' 를 줄줄이 기다렸다(2026-10-15 실측: 같은 시험 119초 vs 3초).
    #   _free_mb 를 직접 바꾸는 시험은 자기 monkeypatch 가 나중에 걸려 그대로 이긴다.
    monkeypatch.setattr(track, "_free_mb", lambda: 10 ** 6, raising=False)
