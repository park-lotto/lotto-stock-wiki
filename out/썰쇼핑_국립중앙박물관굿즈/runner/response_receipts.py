"""Durable single-identity delivery receipts; recovery GET never repeats a tool.

Request keys stay in the private work folder, never in checkpoints, diagnostics,
provider requests or the server's persisted plaintext. Existing paid receipts and
outputs are neither removed nor rewritten. Native Windows/macOS OS locks protect
concurrent delivery attempts.

■ 2026-10-05 (2차 A · 원장 W2-01·02·05 · 누락 M1) — 재전송은 **같은 신원**으로만
    서버 `admit()` 은 같은 (request_id, request_sha, key) 를 조건부 생성으로 받으므로 같은 신원은
    **최대 1회** 실행된다. 그래서 첫 POST 가 5xx(1102 제외)·연결 실패면 같은 바이트·같은 헤더로 다시
    보낸다(main 의 `_open_retry` 와 같은 3회·1초/2초 — 새 숫자를 짓지 않는다). 재전송이 409(이미 접수)를
    받거나, 헤더 뒤 본문이 끊기면(M1 · KT·LAX 본문 정지) **POST 를 다시 하지 않고**
    회수 GET 으로 넘어간다(★2026-10-19 신고 #318: 헤더 전 시간 초과는 «못 닿음» 이라 같은 신원 재전송 쪽 — `_post`) — 서버는 응답을 보내기 전에 완료 영수증을 저장하므로 대개 그 자리에서 받는다.
    회수 GET 409 의 `X-Volcano-Response-State` 가 «unadmitted»(1101 — 우리 코드가 돌기 전 죽음)면
    봉인(`POST …/seal-unadmitted`)으로 «실행 안 됨» 을 원자적으로 확정하고, 열쇠로 MAC 한 증명이 맞을 때만
    그 기록을 보관한 뒤 **지금 payload** 로 새 요청을 보낸다. «admitted»(접수했고 완료가 없다)는 다시
    실행하지 않는다 — ★2026-10-06(W2-05 · 사장님 결정 12): 서버가 접수 시각으로 «15분 넘게 완료 없음 = 끝났다»
    를 확인해 «admitted-dead» 라고 말하면 그때만 unadmitted 와 같은 봉인 길로 닫고 새로 보낸다(시간은 서버가 정한다). 상태 헤더가 없거나 봉인 끝점이 없으면(옛 서버·되돌린 서버) 예전처럼 멈춘다.
    401·403·429 는 여전히 그 실행의 모든 요청을 멈춘다(전역 규칙 6-2).
"""
import base64
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import urllib.error
import urllib.parse
import urllib.request
import uuid


class RecoveryPending(RuntimeError):
    pass


class ServiceRefused(RecoveryPending):
    pass


class ResendSealed(Exception):
    """The server proved (MAC) the original request was never admitted; send it anew.

    Raised only from a recovery of an EXISTING record. The caller releases the
    lock and submits the current payload as a new request (new identity).
    """


#: 잠금 주인 기록(#190) — OS 잠금은 잡은 프로세스가 죽으면 저절로 풀리므로 «잠겨 있다» 는 «지금 살아 있는 실행기가 쥐고 있다» 이다.
#: 그 실행기가 누구인지(PID·언제부터·무슨 일) 옆 파일에 적어 두고, 못 잡은 쪽이 그대로 말한다. 기다리는 고리·강제 해제는 두지 않는다.
OWNER_SUFFIX = '.owner'


def record_lock_owner(lock_path, purpose):
    """잠금을 잡은 직후 부른다 — 실패해도 잠금 자체는 유효하다(주인 글은 설명일 뿐)."""
    import time
    owner = {'pid': os.getpid(), 'since': time.time(), 'purpose': str(purpose or '')[:200]}
    target = str(lock_path) + OWNER_SUFFIX
    tmp = target + '.' + str(os.getpid()) + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(owner, fh, ensure_ascii=False)
        os.replace(tmp, target)          # 읽는 쪽이 반쯤 쓴 글을 보지 않게
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        return None
    return owner


def clear_lock_owner(lock_path):
    """잠금을 풀기 직전에 부른다 — 다음 주인이 옛 주인 글을 물려받지 않게."""
    with contextlib.suppress(OSError):
        os.unlink(str(lock_path) + OWNER_SUFFIX)


def describe_lock_owner(lock_path):
    """못 잡은 쪽이 실패 글 끝에 붙이는 한 줄 — 누가·언제부터·무슨 일, 그리고 무엇을 하면 되는지."""
    import time
    try:
        with open(str(lock_path) + OWNER_SUFFIX, encoding='utf-8') as fh:
            owner = json.load(fh)
        pid, since = int(owner['pid']), float(owner['since'])
    except (OSError, ValueError, KeyError, TypeError):
        return (' 잡고 있는 실행기가 주인 기록을 남기지 않았습니다(옛 판 실행기일 수 있음). 그 실행기가 끝나면 다시 실행하세요 —'
                ' 같은 작업 폴더에 실행기를 두 개 띄우지 마세요. 잠금 파일: ' + str(lock_path))
    elapsed = max(0, int(time.time() - since))
    started = time.strftime('%m-%d %H:%M:%S', time.localtime(since))
    purpose = str(owner.get('purpose') or '')
    return (f' 잡고 있는 실행기: PID {pid} · {started} 부터({elapsed // 60}분 {elapsed % 60}초째)'
            + (f' · 하는 일: {purpose}' if purpose else '')
            + '. 그 실행기가 끝나면 다시 실행하세요(같은 명령을 바로 다시 띄우면 또 막힙니다).'
            f' 응답이 없는 채 남은 것이면 PID {pid} 를 끝낸 뒤 다시 실행하세요.')


#: main 의 `_open_retry` 와 같은 횟수·간격(3회 · 1초/2초). Cloudflare 문서에 1101 재시도 숫자는 없다
#: («공식 숫자 없음» — 원장 §9-7). 바깥 서비스(TTS)의 `API_RETRY` 는 가져다 쓰지 않는다(원장 §5-6).
ATTEMPTS = 3


def _sleep(attempt):
    import time
    time.sleep(1 + attempt)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()


def _observe_transport_error(observation, exc):
    """요청 진단에 «어떤 전송 실패였나» 를 남긴다 — 예외 이름과 OS 오류 번호만(글·경로·주소·본문 없음).

    신고 #318(2026-10-19): «받지 못했음» 112건 중 15건이 0~43ms 만에 실패했는데 진단에 예외 종류가 없어
    (시도마다의 `last` 는 화면 알림에만 갔다) 원인을 가를 수 없었다. 실패한 시도 수도 함께 센다.
    """
    reason = getattr(exc, 'reason', None)
    cause = reason if isinstance(reason, BaseException) else exc
    kind = type(exc).__name__ if cause is exc else type(exc).__name__ + '>' + type(cause).__name__
    number = getattr(cause, 'winerror', None) or getattr(cause, 'errno', None)
    try:
        observation['transport_error'] = kind
        if type(number) is int:
            observation['transport_errno'] = number
        else:
            observation.pop('transport_errno', None)
        observation['failed_attempts'] = int(observation.get('failed_attempts') or 0) + 1
    except Exception:  # noqa: BLE001 — 진단 칸 쓰기 실패가 원래 실패를 가리면 안 된다
        pass


_ADMITTED = ('서버가 이 요청을 접수했지만 완료 응답이 아직 없습니다(처리 중이거나 처리 도중 끊겼습니다). '
             '실행됐을 수 있어 같은 요청을 다시 보내지 않았습니다. 잠시 뒤 같은 명령으로 다시 실행하면 '
             '결과를 다시 확인합니다. 영수증과 결과를 보존했습니다.')
_UNADMITTED_SEALED = ('서버가 이 요청을 받지 못했음을 확인했습니다(실행되지 않음 · 봉인 기록 보존). '
                      '같은 명령으로 다시 실행하면 새 요청으로 보냅니다.')
#: 같은 논리 요청이 서버에서 «접수 뒤 완료 없이 끝남» 으로 이미 한 번 봉인됐는데 또 그렇다 — 자동으로 다시 보내지 않는다
#:   (A2 검토 minor ⑦: 끝남의 주원인은 1102·CPU 사망이고, 원장 §5-3 «끊길 때마다 다른 수강생이 1101» · 전역 규칙 6-2 자동 재시도 금지).
#:   사람이 그 폴더에 표식 파일(RESEND_MARKER)을 만들었을 때만 한 번 다시 보낸다(쓰고 나면 지운다).
RESEND_MARKER = 'resend-once'
_DEAD_AGAIN = ('서버가 이 요청을 접수했지만 또 완료하지 못하고 끝났습니다(같은 요청 두 번째 · 서버 자원 한도로 끊겼을 수 있음). '
               '자동으로 다시 보내지 않습니다 — 다시 보내면 서버가 또 끊길 수 있습니다. 영수증과 결과를 보존했습니다. '
               '한 번 더 보내 보려면 작업 폴더의 {marker} 파일을 만든 뒤 같은 명령을 실행하세요(한 번 쓰고 지웁니다).')
_DEAD_SEALED = ('서버가 이 요청을 접수했지만 완료하지 못하고 끝났음을 확인했습니다(봉인 기록 보존). '
                '같은 명령으로 다시 실행하면 새 요청으로 보냅니다.')


def _admitted_message(retry_after):
    """W2-05 — 서버가 «언제 끝났다고 볼지» 를 Retry-After 로 말하면 그 시각을 알려 준다(실행기 상수 없음)."""
    try:
        seconds = int(retry_after)
    except (TypeError, ValueError):
        return _ADMITTED
    if seconds < 0:
        return _ADMITTED
    minutes = max(1, -(-seconds // 60))
    return (_ADMITTED + f' 약 {minutes}분 뒤에도 완료가 없으면 서버가 «끝났다» 로 확인해 주고, '
            '그때 같은 명령을 다시 실행하면 새 요청으로 보냅니다.')


def logical_hash(url, tool, preset, step, payload, source):
    h = hashlib.sha256()
    encoder = json.JSONEncoder(ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    for part in encoder.iterencode([url, tool, preset, step, payload, source]):
        h.update(part.encode())
    return h.hexdigest()


class Delivery:
    def __init__(self, directory, logical_sha, *, save, io_path):
        self.directory = directory
        self.logical_sha = logical_sha
        self.save = save
        self.io_path = io_path
        self.folder = io_path(os.path.join(directory, '.volcano-responses', logical_sha))
        self.path = os.path.join(self.folder, 'current.json')
        self.record = None
        self.lock = None
        self.sealed_from = None

    def __enter__(self):
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        self.lock = open(os.path.join(self.folder, 'lock'), 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close(); self.lock = None
            raise RecoveryPending('같은 요청의 결과를 다른 실행기가 확인하고 있습니다. 새 요청은 보내지 않았습니다.'
                                  + describe_lock_owner(os.path.join(self.folder, 'lock'))) from None
        record_lock_owner(os.path.join(self.folder, 'lock'), '요청 결과 확인 ' + self.logical_sha[:12])
        try:
            try:
                with open(self.path, encoding='utf-8') as fh:
                    self.record = json.load(fh)
            except FileNotFoundError:
                self.record = None
            if self.record is not None:
                r = self.record
                if (r.get('version') != 1 or r.get('logical_sha') != self.logical_sha
                        or r.get('status') not in ('reserved', 'pending', 'ready', 'refused')
                        or not isinstance(r.get('request_id'), str) or len(r['request_id']) != 32
                        or not isinstance(r.get('request_sha'), str) or len(r['request_sha']) != 64
                        or not isinstance(r.get('key'), str) or len(r['key']) != 64):
                    raise ValueError('invalid receipt')
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise RecoveryPending('기존 요청 영수증을 읽지 못했습니다. 기록을 보존했고 새 요청은 보내지 않았습니다.') from None

    def __exit__(self, *unused):
        if self.lock is not None:
            clear_lock_owner(os.path.join(self.folder, 'lock'))
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0); msvcrt.locking(self.lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_UN)
            self.lock.close(); self.lock = None

    def _publish(self):
        # Each phase is separate: publishing ready/current cannot overwrite the
        # original pending identity if a later durable write fails.
        archive = os.path.join(self.folder, self.record['request_id'] + '.' + self.record['status'] + '.json')
        if not os.path.exists(archive):
            self.save(archive, self.record)
        self.save(self.path, self.record)

    def save_context(self, blobs, reviews):
        # Shared immutable local originals: later polling generations reuse each
        # fingerprint rather than copying large evidence into every phase record.
        originals = self.io_path(os.path.join(self.directory, '.volcano-responses', 'originals'))
        os.makedirs(originals, mode=0o700, exist_ok=True)
        refs = {}
        for name, data in blobs.items():
            sha = hashlib.sha256(data).hexdigest()
            path = os.path.join(originals, sha + '.json')
            if not os.path.exists(path):
                self.save(path, {'data': data.decode('utf8', 'surrogatepass')})
            refs[name] = sha
        context = {'blobs': refs, 'reviews': reviews}
        sha = hashlib.sha256(json.dumps(context, ensure_ascii=True, sort_keys=True).encode()).hexdigest()
        path = os.path.join(originals, sha + '.context.json')
        if not os.path.exists(path):
            self.save(path, context)
        self.context_sha = sha

    def load_context(self):
        try:
            sha = self.record['context_sha']
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                raise ValueError('context fingerprint invalid')
            originals = self.io_path(os.path.join(self.directory, '.volcano-responses', 'originals'))
            with open(os.path.join(originals, sha + '.context.json'), encoding='utf8') as f:
                context = json.load(f)
            if hashlib.sha256(json.dumps(context, ensure_ascii=True, sort_keys=True).encode()).hexdigest() != sha:
                raise ValueError('context fingerprint differs')
            blobs = {}
            for name, sha in context['blobs'].items():
                if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                    raise ValueError('original fingerprint invalid')
                with open(os.path.join(originals, sha + '.json'), encoding='utf8') as f:
                    data = json.load(f)['data'].encode('utf8', 'surrogatepass')
                if hashlib.sha256(data).hexdigest() != sha:
                    raise ValueError('original fingerprint differs')
                blobs[name] = data
            return blobs, context['reviews']
        except (OSError, ValueError, KeyError, TypeError):
            raise RecoveryPending('응답 복원용 원본을 확인하지 못했습니다. 기록을 보존하고 새 요청은 보내지 않았습니다.') from None

    def prepare(self, request, account=None):
        if self.record is None or self.record['status'] == 'reserved':
            self.record = {'version': 1, 'logical_sha': self.logical_sha,
                'request_id': uuid.uuid4().hex,
                'request_sha': hashlib.sha256(request.data).hexdigest(),
                'key': secrets.token_hex(32), 'status': 'pending',
                'context_sha': getattr(self, 'context_sha', None),
                'rpc_id': json.loads(request.data)['id'],
                'credential_sha': hashlib.sha256((request.get_header('Authorization') or '').encode()).hexdigest()}
            if isinstance(account, str) and account:
                self.record['account'] = account   # 서버 caps 의 계정 지문 — 봉인 때 같은 계정인지 본다
            self._publish()  # A failed durable write means no HTTP attempt.
            first = True
        else:
            first = False
        return first

    def _headers(self):
        r = self.record
        return {'X-Volcano-Request-ID': r['request_id'],
            'X-Volcano-Request-SHA256': r['request_sha'],
            'X-Volcano-Receipt-Key': r['key'], 'X-Volcano-Response-Receipt': '1',
            # 이 판이 알아듣는 회수 상태 — 서버는 이 낱말이 없는 옛 실행기에게 admitted-dead 를 옛 낱말로 번역한다(A2 검토 major ①)
            'X-Volcano-Response-States': 'admitted-dead'}

    def save_response(self, raw):
        try:
            if json.loads(raw).get('id') != self.record['rpc_id']:
                raise ValueError('wrong response RPC ID')
        except (ValueError, AttributeError, TypeError):
            raise RecoveryPending('원래 요청과 응답의 번호가 일치하지 않습니다. 새 요청은 보내지 않았습니다.') from None
        r = dict(self.record, status='ready', response=base64.b64encode(raw).decode('ascii'),
                 response_sha=hashlib.sha256(raw).hexdigest())
        self.record = r
        self._publish()

    def _saved(self):
        try:
            raw = base64.b64decode(self.record['response'], validate=True)
            if hashlib.sha256(raw).hexdigest() != self.record['response_sha']:
                raise ValueError('response fingerprint mismatch')
            value = json.loads(raw)
            if value.get('id') != self.record['rpc_id']:
                raise ValueError('response RPC identity differs')
            return value
        except (ValueError, KeyError, TypeError):
            raise RecoveryPending('보존된 서버 응답을 완전히 확인하지 못했습니다. 새 요청은 보내지 않았습니다.') from None

    def exchange(self, request, observation, *, timeout, read, on_refusal=None,
                 limit_exceeded=None, notify=None, account=None):
        first = self.prepare(request, account)
        observation['client_request_id'] = self.record['request_id']
        if not first:
            credential_sha = hashlib.sha256((request.get_header('Authorization') or '').encode()).hexdigest()
            if self.record['status'] == 'refused' and self.record.get('credential_sha') == credential_sha:
                raise ServiceRefused('이 요청은 서비스에서 거부했습니다. 거부 기록을 보존했으며 자동 재전송·결과 조회를 하지 않습니다.')
            # ★자격이 바뀐 refused(출입증 만료 뒤 새 출입증 · 원장 W2-07)는 pending 과 같은 회수 길을 탄다 —
            #   거부는 «그 자격» 에 대한 서비스의 답이었다. 새 자격의 회수 GET 이 다시 401/403/429 면 다시 굳는다.
            if self.record['status'] == 'ready' and self.record.get('credential_sha') == credential_sha:
                return self._saved()
            # Client restart reaches only an authenticated read endpoint. An
            # absent receipt, pending execution or rejection never causes POST.
            return self.recover(request, timeout=timeout, on_refusal=on_refusal, existing=True)
        for key, value in self._headers().items():
            request.add_header(key, value)
        return self._post(request, observation, timeout=timeout, read=read, on_refusal=on_refusal,
                          limit_exceeded=limit_exceeded, notify=notify)

    def _post(self, request, observation, *, timeout, read, on_refusal, limit_exceeded, notify):
        """첫 전송 — 같은 신원으로만 다시 보내고, 접수가 의심되면 회수로 넘어간다(머리말)."""
        for attempt in range(ATTEMPTS):
            try:
                return read(request, timeout, observation, self.save_response)
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403, 429):
                    self._record_refusal(exc, on_refusal)
                    raise
                if exc.code == 409:
                    # 같은 신원의 재전송을 서버가 «이미 접수» 로 막았다 — 앞 시도가 닿았다. 결과는 회수로 받는다.
                    exc.close()
                    break
                if exc.code < 500 or (limit_exceeded is not None and limit_exceeded(exc)):
                    raise          # 4xx 는 사람이 고칠 일 · 1102 는 서버가 돌다 끊긴 것(다시 보내면 또 끊긴다)
                _observe_transport_error(observation, exc)
                last = 'HTTP %d' % exc.code
                exc.close()
            except (OSError, http.client.HTTPException, ValueError) as exc:
                _observe_transport_error(observation, exc)
                # 헤더 뒤(본문·JSON)에서 끊겼다 — 서버가 응답을 시작했다(받았다). 다시 보내지 않고 회수한다.
                if observation.get('phase') != 'headers':
                    break
                # ★헤더를 못 받은 채 시간이 다 된 것도 같은 신원으로 다시 보낸다(2026-10-19 · 신고 #318).
                #   같은 신원은 서버 admit() 의 조건부 생성으로 최대 1회만 실행된다 — 앞 시도가 늦게 닿았거나
                #   서버가 아직 돌고 있으면 이 재전송은 409(이미 접수)가 되어 위에서 회수로 간다(실행 0회 추가).
                #   예전에는 시간 초과 한 번이면 재전송 없이 회수 → «미접수» 봉인 → 실행 중단이었다. 실측(10-12~10-18):
                #   «받지 못했음» 112건 전부 HTTP 응답이 없었고(cf-ray 0 — 1101·1102·5xx 아님) 그중 120초 시간 초과 78건의
                #   91% 가 KT(AS4766)·미국 경유 회선이었다 — 요청이 Cloudflare Worker 에 닿지 않은 회선 정지다.
                #   시도 횟수는 그대로 ATTEMPTS(3회) — 세 번 다 못 닿으면 예전처럼 회수·봉인 뒤 멈춘다.
                last = type(exc).__name__
            if attempt + 1 < ATTEMPTS:
                if notify is not None:
                    notify('서버가 일시적으로 응답하지 못했다(%s) — 같은 요청 신원으로 다시 보낸다(서버는 같은 신원을 한 번만 실행한다)' % last)
                _sleep(attempt)
        return self.recover(request, timeout=timeout, on_refusal=on_refusal, existing=False)

    def _get(self, request, timeout):
        parts = urllib.parse.urlsplit(request.full_url)
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc,
            '/responses/v1/' + self.record['request_id'], '', ''))
        headers = self._headers()
        headers['Authorization'] = request.get_header('Authorization')
        headers['User-Agent'] = request.get_header('User-agent') or 'volcano-runner'
        recovery = urllib.request.Request(url, headers=headers, method='GET')
        last = None
        for attempt in range(ATTEMPTS):
            try:
                response = urllib.request.urlopen(recovery, timeout=timeout)
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise
                last = exc
                exc.close()
            except (OSError, http.client.HTTPException) as exc:
                last = exc
            else:
                # ★본문까지 받은 것을 한 번의 회수로 센다(2026-10-23 인물형 롱폼 신고 · cf-ray …-MRS): 첫 전송 본문이
                #   IncompleteRead 로 끊겨 회수로 왔는데, 회수는 머리만 다시 받아 보고 본문 끊김은 그 자리에서 멈췄다
                #   (같은 회선이면 본문도 또 끊긴다). 회수 GET 은 저장된 응답을 읽기만 하므로 머리 끊김과 같은 횟수(ATTEMPTS)로 다시 받는다.
                try:
                    return response.headers, response.read()
                except (OSError, http.client.HTTPException) as exc:
                    last = exc
                finally:
                    response.close()
            if attempt + 1 < ATTEMPTS:
                _sleep(attempt)
        raise last

    def recover(self, request, *, timeout, on_refusal, existing):
        """회수 GET — 받으면 영수증에 저장하고, 못 받으면 서버가 말한 상태대로 멈추거나 봉인한다."""
        credential_sha = hashlib.sha256((request.get_header('Authorization') or '').encode()).hexdigest()
        try:
            head, raw = self._get(request, timeout)
            if (head.get('X-Volcano-Response-Receipt') != '1'
                    or head.get('X-Volcano-Request-SHA256') != self.record['request_sha']
                    or head.get('X-Volcano-Response-SHA256') != hashlib.sha256(raw).hexdigest()):
                raise RecoveryPending('원래 서버 응답의 영수증을 확인하지 못했습니다. 새 요청은 보내지 않았습니다.')
            self.record = dict(self.record, credential_sha=credential_sha)
            self.save_response(raw)
            return self._saved()
        except urllib.error.HTTPError as exc:
            state = exc.headers.get('X-Volcano-Response-State') if exc.headers is not None else None
            code = exc.code
            exc.close()
            if code in (401, 403, 429):
                self._record_refusal(exc, on_refusal)
                raise ServiceRefused('서비스가 결과 조회를 거부했습니다. 이 실행의 다른 요청도 중지합니다.') from None
            if code == 409 and state == 'admitted':
                raise RecoveryPending(_admitted_message(
                    exc.headers.get('Retry-After') if exc.headers is not None else None)) from None
            # W2-05 — admitted-dead: 서버가 «접수했지만 완료 없이 끝났다» 를 기록(접수 시각)으로 확인했다.
            #   봉인이 그 접수를 원자적으로 닫은 뒤에만 새로 보낸다(unadmitted 와 같은 길 · 같은 MAC 증명).
            if code == 409 and state in ('unadmitted', 'sealed', 'admitted-dead') and self.record['status'] != 'ready':
                # ★ready(응답을 이미 가진 기록)는 봉인하지 않는다 — 자격이 바뀌어 회수 GET 이 409 인 것은
                #   «실행 안 됨» 이 아니라 «다른 자격» 이다(옛 계약 그대로 멈춘다).
                marker = None
                if state == 'admitted-dead' and self._dead_before():
                    marker = os.path.join(self.folder, RESEND_MARKER)
                    if not os.path.exists(marker):
                        raise RecoveryPending(_DEAD_AGAIN.format(marker='/'.join(
                            ('.volcano-responses', self.logical_sha, RESEND_MARKER))))
                self._seal(request, timeout=timeout, on_refusal=on_refusal)
                if marker is not None:
                    os.remove(marker)       # 봉인이 끝났다 — 사람 표식은 한 번만 쓴다
                if existing:
                    raise ResendSealed()
                raise RecoveryPending(_DEAD_SEALED if getattr(self, 'sealed_from', None) == 'admitted-dead'
                                      else _UNADMITTED_SEALED) from None
            raise RecoveryPending('원래 서버 응답을 아직 회수하지 못했습니다. 영수증과 결과를 보존했고 새 요청은 보내지 않았습니다.') from None
        except (OSError, http.client.HTTPException) as exc:
            raise RecoveryPending('원래 서버 응답 조회 연결을 확인하지 못했습니다. 기록을 보존했고 새 요청은 보내지 않았습니다.') from exc

    def _dead_before(self):
        """이 논리 요청의 앞선 요청이 «접수 뒤 완료 없이 끝남» 으로 봉인된 적이 있나 — 보관본(`*.sealed.json`)의 증명으로 본다."""
        try:
            names = os.listdir(self.folder)
        except OSError:
            return False
        for name in names:
            if not name.endswith('.sealed.json') or name == self.record['request_id'] + '.sealed.json':
                continue
            try:
                with open(os.path.join(self.folder, name), encoding='utf-8') as fh:
                    proof = (json.load(fh) or {}).get('seal_proof') or {}
            except (OSError, ValueError, AttributeError):
                return True     # 읽지 못한 봉인 보관본 — 끝남이었는지 모른다. 자동 재전송 쪽으로 기울지 않는다(사람 표식으로 푼다)
            if isinstance(proof, dict) and proof.get('sealed_from') == 'admitted-dead':
                return True
        return False

    def _seal(self, request, *, timeout, on_refusal):
        """서버에 «미접수» 봉인을 받고, 열쇠로 MAC 한 증명이 맞을 때만 이 기록을 닫는다(reserved)."""
        parts = urllib.parse.urlsplit(request.full_url)
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc,
            '/responses/v1/' + self.record['request_id'] + '/seal-unadmitted', '', ''))
        headers = self._headers()
        headers['Authorization'] = request.get_header('Authorization')
        headers['User-Agent'] = request.get_header('User-agent') or 'volcano-runner'
        headers['Content-Type'] = 'application/json'
        sealing = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
        unknown = RecoveryPending('서버가 이 요청을 받지 못했는지 확정하지 못했습니다. 실행됐을 수 있어 새 요청은 '
                                  '보내지 않았습니다. 영수증과 결과를 보존했습니다.')
        try:
            response = urllib.request.urlopen(sealing, timeout=timeout)
            try:
                proof = json.loads(response.read())
            finally:
                response.close()
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403, 429):
                self._record_refusal(exc, on_refusal)
                raise ServiceRefused('서비스가 결과 확인을 거부했습니다. 이 실행의 다른 요청도 중지합니다.') from None
            raise unknown from None       # 405(봉인 끝점이 없는 옛 서버)·409(신원 불일치) — 예전처럼 멈춘다
        except (OSError, http.client.HTTPException, ValueError):
            raise unknown from None
        mac = proof.get('mac') if isinstance(proof, dict) else None
        claimed = {k: v for k, v in proof.items() if k != 'mac'} if isinstance(proof, dict) else {}
        import hmac as _hmac
        expected = _hmac.new(bytes.fromhex(self.record['key']), _json_bytes(claimed), hashlib.sha256).hexdigest()
        if (not isinstance(mac, str) or not _hmac.compare_digest(mac, expected)
                or claimed.get('request_id') != self.record['request_id']
                or claimed.get('request_sha') != self.record['request_sha']):
            raise unknown
        # ★봉인은 **부른 계정의** 이름공간만 본다. 다른 계정으로 만든 요청이면 그 계정의 접수는 안 보이므로
        #   «미접수» 가 증명이 아니다. 요청을 만들 때 계정 지문을 알았으면(caps) 같은 계정일 때만 새로 보낸다.
        #   지문이 없는 기록(이 수리 전 실행기가 남긴 것)은 비교할 것이 없다 — 남는 위험은 원장 §4-2 의
        #   «결정적인 서버 단계 한 번 재계산» 이다.
        if self.record.get('account') and claimed.get('account') != self.record['account']:
            raise RecoveryPending('이 요청은 다른 계정으로 보낸 것이라 지금 계정으로는 실행 여부를 확정할 수 없습니다. '
                                  '새 요청은 보내지 않았습니다. 처음 보낸 계정으로 다시 실행하세요.')
        if claimed.get('state') == 'admitted':
            raise RecoveryPending(_ADMITTED)
        if claimed.get('state') != 'sealed':
            raise unknown          # complete(그 사이 완료)·unknown — 다음 실행의 회수 GET 이 받는다
        archive = os.path.join(self.folder, self.record['request_id'] + '.sealed.json')
        if not os.path.exists(archive):
            self.save(archive, dict(self.record, status='sealed', seal_proof=proof))
        self.record = dict(self.record, status='reserved')
        self._publish()
        self.sealed_from = claimed.get('sealed_from')

    def _record_refusal(self, error, on_refusal):
        # Stop the shared Client BEFORE a disk write can replace the refusal
        # with an unrelated storage exception and trigger feedback/cache traffic.
        if on_refusal is not None:
            on_refusal()
        try:
            self.refuse()
        except Exception as failure:
            error.close()
            raise ServiceRefused(
                f'서비스가 HTTP {error.code}로 요청을 거부하여 이 실행의 모든 추가 요청을 중지했습니다. '
                '거부 영수증 저장도 실패했습니다 (' + type(failure).__name__ + '). '
                '기존 접수 기록은 보존했으며 자동 재전송하지 않습니다.') from failure

    def acknowledge(self, expected_id):
        # Only the durable caller may advance a generation, after saving the
        # next state. step() itself never consumes a completed response.
        if (self.record is not None and self.record['status'] == 'ready'
                and self.record['request_id'] == expected_id):
            self.record = dict(self.record, status='reserved')
            self._publish()

    def refuse(self):
        self.record = dict(self.record, status='refused')
        self._publish()


def setup_preflight(client, payload, execute, *, save, io_path):
    """Migration setup owns a separate durable checkpoint, not the video state."""
    original = dict(payload)
    identity = logical_hash(client.url, 'volcano_video', client.preset, 'setup', original, None)
    directory = io_path(os.path.join(original['workdir'], '.volcano-responses', 'preflight'))
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = os.path.join(directory, identity + '.json')
    try:
        with open(path, encoding='utf8') as f:
            state = json.load(f)
        if state.get('identity') != identity or not isinstance(state.get('payload'), dict):
            raise ValueError('preflight identity mismatch')
        payload = state['payload']
    except FileNotFoundError:
        payload = original
        state = {'identity': identity, 'payload': payload}
        save(path, state)
    except (ValueError, TypeError, KeyError):
        raise RecoveryPending('설치 사전점검 기록을 확인하지 못했습니다. 기존 제작 상태를 보존했습니다.') from None
    previous = getattr(client, '_receipt_durable_owner', False)
    client._receipt_durable_owner = True
    try:
        restore_handoff(client, state, 'setup', payload, None, save=save, io_path=io_path)
        ready = client.step('setup', payload=payload, tool='volcano_video')
        if ready.get('status') == 'execute':
            payload = dict(payload, **execute(ready))
            state = {'identity': identity, 'payload': payload}
            marker = handoff(client, 'setup', payload, None)
            if marker is not None:state['response_handoff'] = marker
            save(path, state)
            client.acknowledge_response()
            ready = client.step('setup', payload=payload, tool='volcano_video')
        return ready
    finally:
        client._receipt_durable_owner = previous


def finish_preflight(client, payload, *, save, io_path):
    """Caller has persisted the original production stage after setup succeeds.

    Restore probe input before ACK, so another wrapper invocation measures the
    environment again. A crash before this explicit handoff retains old ready;
    a crash after it cannot turn a stale module report into a new setup report.
    """
    identity = logical_hash(client.url, 'volcano_video', client.preset, 'setup', payload, None)
    path = io_path(os.path.join(payload['workdir'], '.volcano-responses', 'preflight', identity + '.json'))
    state = {'identity': identity, 'payload': dict(payload)}
    marker = handoff(client, 'setup', payload, None)
    if marker is not None:state['response_handoff'] = marker
    save(path, state)
    client.acknowledge_response()


def handoff(client, step, payload, source):
    """Metadata written atomically WITH the caller's next checkpoint state."""
    held = getattr(client, '_receipt_returned', None)
    if held is None:
        return None
    _directory, logical_sha, request_id = held
    return {'version': 1, 'logical_sha': logical_sha, 'request_id': request_id,
            'next_sha': logical_hash(client.url, client.tool, client.preset, step,
                payload or None, source if step == 'start' else None)}


def restore_handoff(client, state, step, payload, source, *, save, io_path):
    """Finish ACK after a crash without executing an already consumed response."""
    marker = state.get('response_handoff') if isinstance(state, dict) else None
    if marker is None:
        return
    if (not isinstance(marker, dict) or marker.get('version') != 1
            or any(not isinstance(marker.get(key), str) or len(marker[key]) != size
                   or any(c not in '0123456789abcdef' for c in marker[key])
                   for key, size in [('logical_sha',64),('next_sha',64),('request_id',32)])):
        raise RecoveryPending('소비 완료된 요청의 checkpoint 지문을 확인하지 못했습니다. 자동 재실행하지 않습니다.')
    current = logical_hash(client.url, client.tool, client.preset, step,
        payload or None, source if step == 'start' else None)
    if marker['next_sha'] != current:
        return  # Explicitly changed input does not inherit another generation.
    with Delivery(payload['workdir'], marker['logical_sha'], save=save, io_path=io_path) as delivery:
        record = delivery.record
        if record is None:
            raise RecoveryPending('소비 완료된 원래 요청 영수증이 없습니다. 새 유료 요청은 보내지 않습니다.')
        if record['request_id'] == marker['request_id']:
            if record['status'] not in ('ready', 'reserved'):
                raise RecoveryPending('checkpoint와 원래 요청 상태가 다릅니다. 기록을 보존하고 자동 재실행하지 않습니다.')
            delivery.acknowledge(marker['request_id'])
