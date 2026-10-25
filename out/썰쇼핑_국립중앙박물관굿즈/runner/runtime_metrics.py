"""Local execution observations. Never infer a provider bill from request counts."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time

# Hot updates refresh code in this module object while active contexts still
# own tokens. Keep their variables (and prior observation failures) alive.
if '_WORKDIR' not in globals():
    _WORKDIR = ContextVar('volcano_metrics_workdir', default=None)
if '_STAGE' not in globals():
    _STAGE = ContextVar('volcano_metrics_stage', default=None)
if '_UNIT' not in globals():
    _UNIT = ContextVar('volcano_metrics_unit', default=None)
if '_BROKEN' not in globals():
    _BROKEN = set()


def current():
    return _WORKDIR.get()


def current_stage():
    return _STAGE.get()


@contextmanager
def stage(name):
    token = _STAGE.set(_label(name))
    try:
        yield
    finally:
        _STAGE.reset(token)


@contextmanager
def unit(name):
    """A non-sensitive work item label, inherited by component spans in workers."""
    token = _UNIT.set(_label(name))
    try:
        yield
    finally:
        _UNIT.reset(token)


@contextmanager
def context(workdir=None):
    valid = isinstance(workdir, str) and os.path.isabs(workdir)
    token = _WORKDIR.set(os.path.realpath(workdir) if valid else current())
    try:
        yield
    finally:
        _WORKDIR.reset(token)


def _failure(workdir):
    # Observation failures must not cause completed paid work to be repeated.
    try:
        (Path(workdir) / '.volcano-runtime-incomplete').touch(exist_ok=True)
    except OSError:
        pass
    if workdir not in _BROKEN:
        _BROKEN.add(workdir)
        try:
            print('[계측] 실행 시간 기록이 불완전합니다. 작업은 계속하며 비용 절감을 확인한 것으로 표시하지 않습니다.', file=sys.stderr)
        except Exception:
            pass


@contextmanager
def _database(workdir):
    os.makedirs(workdir, exist_ok=True)
    if os.path.realpath(workdir) in _BROKEN:
        # Persist a prior failure as soon as storage permits it. A later process
        # cannot interpret a partial ledger as a complete observation history.
        (Path(workdir) / '.volcano-runtime-incomplete').touch(exist_ok=True)
    # Concurrent observations were lost in native Windows CI; a writer lock
    # exceeding one second reproduces the loss. SQLite waits only locally: it
    # never re-executes the measured work or resubmits a paid request. Bound the
    # wait so a persistently unavailable disk still records incomplete metrics.
    connection = sqlite3.connect(str(Path(workdir) / '.volcano-runtime.sqlite3'), timeout=10)
    try:
        connection.execute('PRAGMA synchronous=FULL')
        connection.execute('CREATE TABLE IF NOT EXISTS spans (id INTEGER PRIMARY KEY, kind TEXT, stage TEXT, started REAL, ended REAL, seconds REAL, outcome TEXT)')
        # A side table keeps old ledgers readable without ALTER/migration races.
        connection.execute('CREATE TABLE IF NOT EXISTS span_units (span_id INTEGER PRIMARY KEY, unit TEXT)')
        connection.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, operation TEXT, outcome TEXT, request_sha256 TEXT, observed REAL)')
        connection.execute('CREATE TABLE IF NOT EXISTS provider_responses (id INTEGER PRIMARY KEY, operation TEXT, request_sha256 TEXT, observed REAL, metadata TEXT)')
        yield connection
        connection.commit()
    finally:
        connection.close()


def _label(value):
    return value if isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', value) else 'unknown'


@contextmanager
def span(kind, stage=None, *, publish=False):
    workdir = current()
    row = None
    if workdir:
        try:
            with _database(workdir) as db:
                row = db.execute('INSERT INTO spans(kind,stage,started,outcome) VALUES(?,?,?,?)',
                    (_label(kind), _label(stage or _STAGE.get()), time.time(), 'unfinished')).lastrowid
                if _UNIT.get() is not None:
                    db.execute('INSERT INTO span_units(span_id,unit) VALUES(?,?)', (row, _UNIT.get()))
        except Exception:
            _failure(workdir)
    if publish and workdir:
        export(workdir)
    # Record the body only: storage/publication delays are observation overhead.
    # An interrupted body keeps its early durable reservation as unfinished; on
    # exit its wall interval is replaced with the actual component boundaries.
    started_wall = time.time()
    # Python 3.12 on Windows uses coarse GetTickCount64 for monotonic;
    # perf_counter_ns uses the high-resolution performance counter instead.
    started = time.perf_counter_ns()
    outcome = 'completed'
    try:
        yield
    except BaseException as error:
        outcome = 'waiting' if type(error).__name__ in ('ClientReviewPending', 'ClientReviewInputError', 'TranscriptionPending') else 'failed'
        raise
    finally:
        ended = time.time()
        seconds = max(0, time.perf_counter_ns()-started) / 1_000_000_000
        if row is not None:
            try:
                with _database(workdir) as db:
                    db.execute('UPDATE spans SET started=?,ended=?,seconds=?,outcome=? WHERE id=?',
                        (started_wall, ended, seconds, outcome, row))
            except Exception:
                _failure(workdir)

        if publish and workdir:
            export(workdir)


def event(operation, outcome, request_sha256=None):
    workdir = current()
    if not workdir:
        return
    key = request_sha256 if isinstance(request_sha256, str) and re.fullmatch('[a-f0-9]{64}', request_sha256) else None
    try:
        with _database(workdir) as db:
            db.execute('INSERT INTO events(operation,outcome,request_sha256,observed) VALUES(?,?,?,?)',
                       (_label(operation), _label(outcome), key, time.time()))
    except Exception:
        _failure(workdir)


def provider_response(operation, request_sha256, response, payload, *, service=None,
                      model=None, json_received=False, seconds=None, outcome=None):
    """Observe per-attempt elapsed time and response codes/counts, never content."""
    workdir = current()
    if not workdir:
        return
    try:
        def identifier(value):
            return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,256}', value) else None
        ids = {}
        headers = getattr(response, 'headers', None)
        if headers is not None:
            for name, value in headers.items():
                if name.lower() in ('x-request-id', 'request-id', 'x-goog-request-id') and identifier(value):
                    ids[name.lower()] = value
        payload = payload if isinstance(payload, dict) else {}
        model = identifier(payload.get('modelVersion') or payload.get('model') or model)
        usage = {}
        raw_usage = payload.get('usageMetadata') or payload.get('usage') or {}
        if isinstance(raw_usage, dict):
            for name in ('promptTokenCount','candidatesTokenCount','totalTokenCount',
                         'thoughtsTokenCount','cachedContentTokenCount','toolUsePromptTokenCount',
                         'prompt_tokens','completion_tokens','total_tokens'):
                value = raw_usage.get(name)
                if type(value) is int and value >= 0:
                    usage[name] = value
            for name, fields in (('prompt_tokens_details', ('cached_tokens','audio_tokens')),
                                 ('completion_tokens_details', ('reasoning_tokens','audio_tokens',
                                     'accepted_prediction_tokens','rejected_prediction_tokens'))):
                details = raw_usage.get(name)
                if isinstance(details, dict):
                    values = {key:details[key] for key in fields
                              if type(details.get(key)) is int and details[key] >= 0}
                    if values:
                        usage[name] = values
        candidates = payload.get('candidates') or payload.get('choices')
        candidate = candidates[0] if isinstance(candidates, list) and candidates else None
        finish = (candidate.get('finishReason') or candidate.get('finish_reason')) if isinstance(candidate, dict) else None
        finish = finish if finish in ('STOP','MAX_TOKENS','SAFETY','RECITATION','OTHER',
            'BLOCKLIST','PROHIBITED_CONTENT','SPII','MALFORMED_FUNCTION_CALL','IMAGE_SAFETY',
            'UNEXPECTED_TOOL_CALL','TOO_MANY_TOOL_CALLS','stop','length','tool_calls',
            'function_call','content_filter') else None
        seconds = seconds if type(seconds) in (int,float) and math.isfinite(seconds) and seconds >= 0 else None
        outcome = outcome if outcome in ('response_received','http_error','transport_error','json_error','read_error') else None
        status = getattr(response, 'status', None)
        metadata = dict(service=identifier(service) or 'unknown', request_ids=ids, model=model, usage=usage,
                        http_status=status if type(status) is int and 100 <= status <= 599 else None,
                        response_json=json_received is True, seconds=seconds, outcome=outcome,
                        timing_scope='http_attempt_through_json_parse' if seconds is not None else None,
                        finish_reason=finish)
        key = request_sha256 if isinstance(request_sha256, str) and re.fullmatch('[a-f0-9]{64}', request_sha256) else None
        with _database(workdir) as db:
            db.execute('INSERT INTO provider_responses(operation,request_sha256,observed,metadata) VALUES(?,?,?,?)',
                       (_label(operation), key, time.time(), json.dumps(metadata, allow_nan=False)))
        export(workdir)
    except Exception:
        _failure(workdir)


def report(workdir):
    with _database(workdir) as db:
        # Aggregate totals and per-unit records must observe the same ledger,
        # even when another worker starts or finishes between these SELECTs.
        db.execute('BEGIN')
        return _snapshot(db,workdir)


def _snapshot(db, workdir):
    spans = db.execute('SELECT kind,stage,started,ended,seconds,outcome FROM spans ORDER BY started').fetchall()
    events = db.execute('SELECT operation,outcome,COUNT(*) FROM events GROUP BY operation,outcome').fetchall()
    records = [dict(zip(('id','kind','stage','started','ended','seconds','outcome','unit'), row))
               for row in db.execute('SELECT s.id,s.kind,s.stage,s.started,s.ended,s.seconds,s.outcome,u.unit '
                   'FROM spans s LEFT JOIN span_units u ON s.id=u.span_id ORDER BY s.started,s.id')]
    responses = [dict(id=row[0], operation=row[1], request_sha256=row[2], observed=row[3],
                      **dict({'seconds':None, 'timing_scope':None, 'outcome':None, 'finish_reason':None},
                             **json.loads(row[4]))) for row in db.execute(
                          'SELECT id,operation,request_sha256,observed,metadata FROM provider_responses ORDER BY id')]
    groups, stages = {}, {}
    unfinished = 0
    clock_discontinuity = False
    intervals = []
    for kind, stage, begin, end, seconds, outcome in spans:
        if seconds is None:
            unfinished += 1
        for dest, key in ((groups,kind),(stages,kind+':'+stage)):
            entry = dest.setdefault(key, {'completed':0, 'failed':0, 'waiting':0, 'unfinished':0, 'seconds':0})
            entry[outcome] += 1
            entry['seconds'] += seconds or 0
        if end is not None:
            clock_discontinuity |= abs((end-begin)-(seconds or 0)) > 1
            intervals.append((begin, max(begin,end)))
    # A drive span contains execution/MCP spans. Merge overlap instead of
    # double-counting nested calls or concurrent executions as elapsed time.
    active, edge = 0, float('-inf')
    for begin, end in sorted(intervals):
        active += max(0, end-max(begin,edge))
        edge = max(edge,end)
    first = min((r[2] for r in spans), default=None)
    last = max((r[3] or r[2] for r in spans), default=first)
    for dest in (groups, stages):
        for entry in dest.values(): entry['seconds'] = round(entry['seconds'],6)
    operations = {}
    for operation, outcome, count in events:
        operations.setdefault(operation,{})[outcome] = count
    return {'version':1, 'scope':'work_directory',
            'snapshot_validity':'requires_current_ledger_read',
            'authoritative_reader':'runtime_metrics.report(workdir)',
            'first_started_at':first,
            'last_observed_at':last, 'elapsed_seconds':None if clock_discontinuity else round(max(0,(last or 0)-(first or 0)),6),
            'active_seconds':None if clock_discontinuity else round(active,6),
            'clock_discontinuity':clock_discontinuity, 'unfinished_spans':unfinished,
            'measurement_complete':not unfinished and not clock_discontinuity and os.path.realpath(workdir) not in _BROKEN
                and not (Path(workdir) / '.volcano-runtime-incomplete').exists(),
            'spans':groups, 'stages':stages, 'operations':operations, 'records':records,
            'provider_responses':responses,
            'billing':{'status':'not_measured','actual_total':None,'currency':None},
            'coverage':{'timing':'explicit driver, execute and component spans since instrumentation; work directory cumulative; nested seconds overlap',
                        'operations':'explicitly instrumented operations only; submitted is not confirmed billed',
                        'provider_responses':'per HTTP attempt through response JSON parsing (or transport failure); excludes reservations, retry sleep and observation; concurrent durations overlap and are not added to wall time; returned IDs/codes/token counts are not confirmed billing',
                        'excluded':['host model usage and billing','provider invoices','work before instrumentation'],
                        'quality':'timing completion is not audiovisual quality approval'}}


def export(workdir=None):
    workdir = workdir or current()
    if not workdir:
        return None
    temporary = None
    try:
        # Serialize snapshot AND publication across processes. An older export
        # must never replace the JSON after a newer snapshot has been published.
        with _database(workdir) as db:
            db.execute('BEGIN IMMEDIATE')
            result = _snapshot(db,workdir)
            fd, temporary = tempfile.mkstemp(prefix='.runtime-report-', dir=workdir)
            with os.fdopen(fd,'w',encoding='utf8') as output:
                json.dump(result,output,ensure_ascii=False,indent=2,allow_nan=False)
            os.replace(temporary, str(Path(workdir) / 'runtime-report.json'))
        return result
    except Exception:
        _failure(workdir)
        # This JSON is derived, never a paid artifact. Keeping a prior success
        # after a failed publication would conceal the current unfinished span.
        # If permissions also prevent removal, the incomplete marker plus the
        # snapshot's explicit refresh requirement still identify the fallback.
        try:
            (Path(workdir) / 'runtime-report.json').unlink(missing_ok=True)
        except OSError:
            pass
        return None
    finally:
        if temporary:
            try:
                if os.path.exists(temporary): os.unlink(temporary)
            except OSError:
                _failure(workdir)
