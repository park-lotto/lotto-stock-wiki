"""폴더를 읽어 항목을 찾는다 — 손 목록 없음(설계 D5·D6). 파일을 두면 다음 실행부터 포함된다."""
import importlib
import pkgutil
from datetime import datetime, timedelta, timezone

_PREFIX = {"health": "h_", "flows": "flow_"}
_UNIT = {"m": 60, "h": 3600}


def discover(kind):
    pkg = importlib.import_module(f"shopping_shorts.checks.{kind}")
    mods = []
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if not info.name.startswith(_PREFIX[kind]):
            continue
        try:
            m = importlib.import_module(f"{pkg.__name__}.{info.name}")
        except Exception:
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
