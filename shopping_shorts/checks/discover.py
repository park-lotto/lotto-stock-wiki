"""폴더를 읽어 항목을 찾는다 — 손 목록 없음(설계 D5·D6). 파일을 두면 다음 실행부터 포함된다.

계약: import가 깨진 항목은 discover()의 반환 리스트에서 조용히 빠지되,
절대 무언(無言)으로 삼키지 않는다 — logger.warning으로 남기고 LAST_ERRORS에
(모듈명, 예외요약)을 채운다. 러너(Task 4)는 discover() 호출 뒤 LAST_ERRORS를
읽어 GRAY(판정 불가) 결과로 기록해야 한다.
"""
import importlib
import logging
import pkgutil
from datetime import datetime, timedelta, timezone

_PREFIX = {"health": "h_", "flows": "flow_"}
_UNIT = {"m": 60, "h": 3600}

logger = logging.getLogger(__name__)

# discover() 호출마다 초기화됨 — 이번 발견에서 import 실패한 항목 목록.
# 각 원소: (모듈 전체경로, 예외 repr 요약)
LAST_ERRORS = []


def discover(kind):
    LAST_ERRORS.clear()
    pkg = importlib.import_module(f"shopping_shorts.checks.{kind}")
    mods = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if not info.name.startswith(_PREFIX[kind]):
            continue
        full_name = f"{pkg.__name__}.{info.name}"
        try:
            m = importlib.import_module(full_name)
        except Exception as exc:
            logger.warning("checks discover: %s import 실패: %r", full_name, exc, exc_info=True)
            LAST_ERRORS.append((full_name, repr(exc)))
            continue
        meta = getattr(m, "META", None)
        if isinstance(meta, dict) and "name" in meta:
            mods.append(m)
    return mods


def _seconds(every):
    return int(every[:-1]) * _UNIT[every[-1]]


def is_due(every, last_ts, now=None):
    if not last_ts:
        return True
    now_dt = datetime.fromisoformat(now) if now else datetime.now(timezone.utc)
    last = datetime.fromisoformat(last_ts)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now_dt - last >= timedelta(seconds=_seconds(every))
