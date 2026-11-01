"""Bridge a detached longform reviewer to the current Volcano review contract.

The pipeline's schemas and media stay intact. The shared runtime owns native
CLI selection, immutable media, typed replies, refusal and paid request budgets.
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import tempfile

import volcano_run as R


def _valid(value, schema):
    """Validate the responseSchema subset issued by this pipeline's reviewers."""
    if not schema:
        return isinstance(value, (dict, list))
    if value is None:
        return schema.get('nullable') is True or str(schema.get('type')).lower() == 'null'
    kind = str(schema.get('type') or '').lower()
    if 'enum' in schema and value not in schema['enum']:
        return False
    if 'anyOf' in schema and not any(_valid(value, branch) for branch in schema['anyOf']):
        return False
    if kind == 'object':
        if not isinstance(value, dict) or any(key not in value for key in schema.get('required') or []):
            return False
        properties = schema.get('properties') or {}
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            return False
        return all(_valid(value[key], rule) for key, rule in properties.items() if key in value)
    if kind == 'array':
        return (isinstance(value, list) and len(value) >= schema.get('minItems', 0)
                and len(value) <= schema.get('maxItems', math.inf)
                and all(_valid(item, schema.get('items')) for item in value))
    if kind in ('integer', 'number'):
        return (type(value) in ((int,) if kind == 'integer' else (int, float))
                and math.isfinite(value) and value >= schema.get('minimum', -math.inf)
                and value <= schema.get('maximum', math.inf))
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'string':
        return (isinstance(value, str) and len(value) >= schema.get('minLength', 0)
                and len(value) <= schema.get('maxLength', math.inf)
                and ('pattern' not in schema or re.search(schema['pattern'], value) is not None))
    return not kind


def _settings():
    path = os.environ.get('VOLCANO_REVIEW_CONTEXT')
    if not path:
        raise R.StepError('롱폼 검수 실행 설정이 없습니다. longform_seed부터 서버 설정을 다시 받으세요.')
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict) or not value.get('directory'):
        raise R.StepError('롱폼 검수 설정의 작업 경로가 없습니다.')
    value['policy'] = R.validate_review_policy(value.get('policy'))
    return value


def file_part(path):
    """Preserve original visual evidence for a reviewer that already reads files."""
    return {'inline_data': {'mime_type': R._photo_image_mime(path),
                            'data': base64.b64encode(Path(path).read_bytes()).decode('ascii')}}


def engine():
    settings = _settings()
    return ('evolink' if settings['policy']['provider'] == 'evolink' else
            (settings.get('client') or {}).get('provider') or 'client')


def _job(directory, stage, system, parts, schema, capabilities=None):
    binding = dict(stage=stage, system=system, parts=parts, schema=schema)
    capabilities = R._review_capabilities(capabilities)
    if capabilities: binding["capabilities"] = capabilities
    raw = json.dumps(binding, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    folder = Path(directory) / 'jobs'; folder.mkdir(parents=True, exist_ok=True)
    media = Path(directory) / 'media'; media.mkdir(parents=True, exist_ok=True)
    prompt = [str(system)]; images = []; videos = []; audios = []
    for i, part in enumerate(parts):
        if 'text' in part:
            prompt.append(str(part['text']))
        data = part.get('inline_data') or part.get('inlineData')
        if data:
            mime = data.get('mime_type') or data.get('mimeType')
            suffix = R._review_media_suffix(mime)
            content = base64.b64decode(data['data'], validate=True)
            content_sha = hashlib.sha256(content).hexdigest()
            path = media / (content_sha + suffix)
            with R._asr_lock(str(path) + '.publish.lock', blocking=True):
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != content_sha:
                    # The filename alone cannot bind cached bytes to inline_data.
                    # Restore the exact supplied evidence before any reviewer sees it.
                    fd, temporary = tempfile.mkstemp(dir=media, suffix='.part')
                    try:
                        with os.fdopen(fd, 'wb') as handle:
                            handle.write(content)
                            handle.flush(); os.fsync(handle.fileno())
                        os.replace(temporary, path)
                    finally:
                        if os.path.exists(temporary): os.unlink(temporary)
            row = {'path': str(path), 'mime': mime, 'label': f'part-{i}'}
            if mime.startswith('image/'):
                images.append(row)
            elif mime.startswith('video/'):
                videos.append(row)
            elif mime.startswith('audio/'):
                audios.append(row)
            prompt.append(f'첨부 자료 part-{i}')
        elif set(part) - {'text'}:
            raise R.StepError('롱폼 검수에서 읽지 못한 자료 형식이 있습니다. 실제 자료를 생략하지 않습니다.')
    prompt += ['JSON 객체 {"result": ...} 하나로 답하세요. result는 다음 원래 검수 스키마를 충족해야 합니다:',
               json.dumps(schema, ensure_ascii=False, sort_keys=True)]
    return {'qc_contract': 'longform_review_v1', 'out': str(folder / (digest + '.json')),
            'prompt': '\n'.join(prompt), 'images': images, 'videos': videos, 'audios': audios,
            'binding': {'stage': stage, 'schema': schema},
            **({'capabilities': capabilities} if capabilities else {})}, digest


PENDING_WAIT_S = 12 * 3600


class ReviewWaitExpired(R.StepError):
    """답 대기 상한을 넘김 — 실패가 아니라 «답 대기 중» 이다. stopped 를 쓰지 않아 status 가 pending 을 보여 주고 재개하면 같은 요청에서 이어진다."""


def review(stage, system, parts, schema, *, api_call, api_provider="evolink", capabilities=None, validator=None, with_provenance=False, timeout=None):
    settings = _settings()
    directory = Path(settings['directory'])
    job, key = _job(directory, stage, system, parts, schema, capabilities)
    valid = lambda value: _valid(value, schema) and (validator is None or validator(value))
    pending_dir = directory / 'pending'; pending_dir.mkdir(parents=True, exist_ok=True)
    stopped_dir = directory / 'stopped'; stopped_dir.mkdir(parents=True, exist_ok=True)
    pending_path = pending_dir / (key + '.json')
    stopped_path = stopped_dir / (key + '.json')
    stopped_path.unlink(missing_ok=True)
    try:
        while True:
            settings = _settings()  # status can deliver answers without restarting production.
            policy = settings['policy']
            if policy['provider'] == 'client':
                try:
                    client = dict(settings.get('client') or {})
                    if timeout is not None: client['timeout'] = timeout
                    answer = R.client_review(job, replies=settings.get('replies'), client=client,
                        validator=lambda value: isinstance(value, dict) and 'result' in value and valid(value['result']))
                except R.ClientReviewPending as error:
                    R._photo_write_state(str(pending_path), error.request)
                    # Poll for a changed answer/selection, not another model or
                    # login attempt. A status poll alone is not authorization to
                    # repeat a CLI invocation that could not finish.
                    # 사장님 규칙 6-00(상한 없는 대기 금지 · 2026-10-09): 사람이 답을 넣을 때까지 1초씩 보되 PENDING_WAIT_S 를 넘기면
                    # 멈춘다. 요청 파일(pending)은 그대로 남아 재개하면 같은 요청에서 이어진다(다시 보내지 않는다). 공식 숫자는 없다 —
                    # 사람이 검수할 하루 작업 시간을 넉넉히 덮는 값으로 정했다.
                    deadline = time.monotonic() + PENDING_WAIT_S
                    while _settings() == settings:
                        if time.monotonic() >= deadline:
                            raise ReviewWaitExpired(f'롱폼 검수 답을 {PENDING_WAIT_S // 3600}시간 동안 받지 못해 기다리기를 멈췄습니다. 요청은 '
                                              f'{pending_path} 에 남아 있으니 답을 넣고 재개하면 같은 요청에서 이어집니다(다시 보내지 않습니다).')
                        time.sleep(1)
                    continue
                result = answer['result']
            else:
                # An explicit paid request uses the same project-wide durable
                # budget and keeps an unknown attempt from being sent again.
                if job.get('capabilities') or api_provider != 'evolink':
                    raise R.StepError('선택한 EvoLink 검수는 이 요청의 제공자 또는 웹검색 기능과 맞지 않습니다. 다른 API로 자동 전환하지 않습니다.')
                paid_path = job['out'] + '.paid.json'
                with R.review_receipt_lock(paid_path):
                    try:
                        paid = json.loads(Path(paid_path).read_text(encoding='utf-8'))
                    except FileNotFoundError:
                        paid = None
                    if paid is not None:
                        if (not isinstance(paid, dict) or paid.get('request_sha256') != key
                                or paid.get('status') != 'complete' or not valid(paid.get('answer'))):
                            raise R.StepError('이 롱폼 유료 검수의 이전 결과가 불명확합니다. 같은 요청을 다시 보내지 않습니다.')
                        result = paid['answer']
                    else:
                        R.review_request_attempt(policy, settings.get('budget'), key)
                        R._photo_write_state(paid_path, {'status': 'pending', 'request_sha256': key})
                        result = api_call()
                        if not valid(result):
                            raise R.StepError('롱폼 유료 검수 답이 원래 스키마를 충족하지 못했습니다.')
                        R._photo_write_state(paid_path, {'status': 'complete', 'request_sha256': key, 'answer': result})
            pending_path.unlink(missing_ok=True)
            if with_provenance:
                receipt = json.loads(Path(job['out'] + '.client-receipt.json').read_text(encoding='utf-8'))
                return result, {k: receipt[k] for k in ('engine', 'request_sha256')}
            return result
    except ReviewWaitExpired:
        # 답 대기 상한(6-00): 요청(pending)은 남기고 stopped 는 쓰지 않는다 — 실패로 보이면 재개 길이 끊긴다(B4 검토 MAJOR-1).
        raise
    except Exception as error:
        # Preserve a visible terminal outcome, then re-raise. It must not become
        # a successful review or a reason to silently choose another provider.
        error.review_stopped = True
        stopped = {'status': 'review_stopped', 'code': getattr(error, 'code', 'longform_review_failed'),
                   'why': str(error) if isinstance(error, R.StepError) else type(error).__name__}
        if isinstance(error, R.ProviderRefusalError):
            stopped.update(origin=error.origin, reason_code=error.reason_code, reason=error.reason)
        R._photo_write_state(str(stopped_path), stopped)
        raise
