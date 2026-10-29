"""Shared run-stop marker, compatible with tools/lib/run_refusal.mjs.

The latest user policy ends the run on the first service refusal. No request
spacing/retry numbers are introduced. Existing receipts/media stay untouched.
The Node job supervisor observes this marker and cancels the child tree.
"""
import json
import os
from pathlib import Path
import re
import threading
from datetime import datetime, timezone

_stopped = set()
# 이 프로세스에서 실행마다 처음 남은 거부의 종류(2026-10-06 · 롱폼 피사체가 «한도·속도·로그인» 거부면 멈추지 않고 그 밖은 막는다 —
# 실행을 시작할 때 이미 걸린 표식의 종류를 알아야 가른다). 표식 파일(run_refusal.mjs 와 같은 모양)은 그대로 두고 프로세스 안에만 적는다 —
# 다른 프로세스가 남긴 표식·종류 없이 남긴 표식은 종류를 모른다(None).
_kinds = {}
_lock = threading.Lock()


class RunServiceRefused(RuntimeError):
    code = 'RUN_SERVICE_REFUSED'

    def __init__(self):
        super().__init__('서비스 거부로 이 실행의 모든 요청을 중단했습니다. 접수 기록과 결과를 보존하고 원인을 확인하세요. 자동 재시도하지 않습니다.')


def _scope(env=None):
    env = os.environ if env is None else env
    run_id = env.get('INFO3D_RUN_ID')
    if run_id and not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', run_id):
        raise ValueError('잘못된 실행 ID')
    root = Path(env.get('INFO3D_REFUSAL_ROOT') or env.get('INFO3D_ROOT') or Path(__file__).resolve().parent.parent)
    marker = root / 'work' / '_provider_health' / 'run_refusals' / (run_id + '.json') if run_id else None
    return str(marker or root.resolve()), marker, run_id


def assert_allowed(env=None):
    key, marker, _ = _scope(env)
    with _lock:
        if key in _stopped:
            raise RunServiceRefused()
    if marker:
        try:
            marker.stat()
        except FileNotFoundError:
            return
        except OSError:
            pass
        raise RunServiceRefused()


def refusal_kind(env=None):
    """이 실행에서 처음 남은 거부의 종류(mark_refusal 의 kind) — 모르면 None."""
    key, _marker, _ = _scope(env)
    with _lock:
        return _kinds.get(key)
def mark_refusal(status=None, env=None, kind=None):
    key, marker, run_id = _scope(env)
    with _lock:
        _stopped.add(key)
        if kind and key not in _kinds:              # 첫 거부 하나 — 같은 잠금 안에서 적어 «표식을 본 쪽» 이 종류도 본다
            _kinds[key] = str(kind)
    if marker:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            with marker.open('x', encoding='utf-8', newline='\n') as stream:
                json.dump({'version': 1, 'runId': run_id, 'at': datetime.now(timezone.utc).isoformat(),
                           'pid': os.getpid(), 'httpStatus': status}, stream)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
        except OSError as error:
            raise RunServiceRefused() from error
