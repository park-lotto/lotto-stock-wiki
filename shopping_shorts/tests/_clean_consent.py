# -*- coding: utf-8 -*-
"""테스트용: 라우트가 확인창에서 받아 큐에 싣는 **고객 동의 값**을 만든다(2026-09-27 서버 동의 관문).
워커(run_render·run_clean_sources)를 직접 부르는 테스트는 라우트를 건너뛰므로, 라우트와 같은 판정
(mix_pipeline.clean_charge_plan)으로 잰 초를 그대로 실어 부른다 — 동의 없이 부르면 과금 없이 멈춘다."""
from pathlib import Path

from shopping_shorts import mix_pipeline as mp


def consent(store, job, work, mode):
    plan = mp.clean_charge_plan(store, job, Path(work), mode=mode)
    return {"confirm_clean": True, "confirm_secs": plan["seconds"]}
