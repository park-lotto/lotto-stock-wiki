# -*- coding: utf-8 -*-
"""볼케이노 실행기 — **서버가 시키는 것만 실행한다.**

■ 이 파일에는 채널 규격이 없다. 일부러 없다.
    무엇을 만들지(프롬프트·크롭 사각형·ffmpeg 인자·TTS 본문·오디오 필터)는 **전부 서버가**
    정해서 내려준다. 여기 있는 건 "받은 것을 그대로 실행하는" 껍데기뿐이다.
    그래서 이 파일을 읽어도 채널 노하우를 알 수 없다.

■ 왜 이 파일이 필요한가
    수강생마다 실행 코드를 새로 짜면 결과가 갈린다. 실제로 갈릴 지점들:
      · 리샘플링을 LANCZOS 가 아닌 걸 쓰면 픽셀이 달라진다
      · JPEG 을 quality=100 · subsampling=0 로 안 쓰면 화질이 떨어진다
      · 라우드니스 측정 인자에 `-v error` 를 붙이면 측정값이 사라져 효과음이 터진다
      · TTS 오디오 필터를 빼먹으면 그룹 길이가 달라져 자막이 통째로 밀린다
    그래서 **검증된 실행기 하나**를 배급한다.

■ 쓰는 법
    from volcano_run import Client, bake_frames, run_argv, measure_lufs
    c = Client(url, token)            # 토큰은 키체인에서 읽어 넘겨라. 파일에 적지 마라
    r = c.step("script", payload={...})

    ★어느 도구를 부를지도 고를 수 있다 — **기본은 `volcano_video`**(수강생 경로).
      조교 계측 체인은 `Client(url, token, tool="volcano_ref")` 로 몬다.
"""

import json
import base64
from pathlib import Path
import builtins
import contextlib
import contextvars
import errno
import copy
import hashlib
import http.client
import tempfile
import uuid
import urllib.parse
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ★Cloudflare 가 파이썬 기본 User-Agent 를 error 1010(403)으로 막는다.
#   우리 서버의 401 이 아니라 앞단 차단이라 "토큰이 틀렸나" 로 오진하기 쉽다.
#
# ★★**실행기가 자기 버전을 스스로 말한다** (2026-08-15).
#   예전에는 `volcano-runner/1.0` 고정 문자열이었다. 그러면 수강생이 **옛 팩을
#   그대로 쓰고 있어도** 서버가 구분할 방법이 없고, "고쳤는데 왜 그대로냐" 의
#   원인을 못 찾는다. 그래서 **자기 소스의 해시**를 붙인다 —
#   서버와 값을 맞출 필요가 없고(조율 지점이 없다), 팩이 바뀌면 저절로 바뀐다.
#   ★읽기에 실패해도 절대 죽지 않는다. 버전을 못 말하는 것보다 실행기가 죽는 게 나쁘다.
def _refresh_updated_code():
    """Runs on reload even when the updater still executing belongs to an old pack."""
    import importlib
    from pathlib import Path
    here = Path(__file__).absolute().parent
    def discard(name):
        source = here / name
        if source.suffix != '.py':
            return
        for path in [source.with_suffix('.pyc'), *(here / '__pycache__').glob(source.stem + '.*.pyc')]:
            if path.is_file() or path.is_symlink():
                path.unlink()
        module = sys.modules.get(source.stem)
        filename = getattr(module, '__file__', None)
        if (source.stem not in ('volcano_run', 'volcano_drive', '__main__') and filename
                and os.path.normcase(os.path.dirname(os.path.abspath(filename))) == os.path.normcase(str(here))):
            if source.stem == 'runtime_metrics':
                # Existing driver/subject references and active ContextVar tokens
                # must keep one module; refresh its code without splitting state.
                importlib.invalidate_caches()
                importlib.reload(module)
            else:
                sys.modules.pop(source.stem, None)
    # Bootstrap only the membership helper, then use its actual installed list.
    # It too may have a cached older definition after the official first update.
    discard('runner_files.py')
    importlib.invalidate_caches()
    from runner_files import STUDENT_FILES
    for name in STUDENT_FILES:
        discard(name)
    importlib.invalidate_caches()


# The environment marker is inherited by newly spawned interpreters. Only a
# reload of this already initialized module has stale Python objects to evict.
# On a first import, eviction can delete the caller (e.g. longform_state) while
# importlib is still initializing it, and also split shared exception identities.
if os.environ.get('VOLCANO_RUNNER_UPDATED') and '_UA' in globals():
    _refresh_updated_code()


def _self_version():
    try:
        from runner_files import identity
        return identity(os.path.dirname(os.path.abspath(__file__)))
    except Exception:  # A missing/corrupt helper must still reach the updater.
        return "unknown"


RUNNER_ID = _self_version()   # 한 번만 잰다 — UA 와 오래 가는 자리 설치(volcano_drive.install_home_runner)가 같이 쓴다
_UA = f"volcano-runner/1.0 ({RUNNER_ID})"


# ★★**찍는 것이 파이프라인을 죽여서는 안 된다** (2026-08-17)
#
# 실물 실측(2026-08-13~2026-08-17, 매일): `'cp949' codec can't encode character '—'`
# 로 실행기가 **9번 죽었다**(8명). 윈도우 콘솔의 기본 인코딩이 cp949 인데 우리
# 메시지에 그 표에 없는 글자가 있다 — `—`(print 문 안에 16회) · `⚠` · `⏸` · `✅`.
# 한글은 cp949 에 있어서 괜찮고, **기호 몇 개 때문에** 이미지·TTS 를 다 굽고 나서
# 죽는다. 돈이 나간 뒤에 죽는 그 부류다.
#
# ★고칠 자리는 **글자가 아니라 출구**다. 문제 글자를 지우는 쪽으로 고치면 다음
#   사람이 새 기호를 넣는 순간 되살아난다(이 저장소가 이미 여러 번 겪은 부류).
# ★콘솔 인코딩을 **바꾸지 않는다.** utf-8 로 갈아 끼우면 옛 콘솔에서 한글이
#   통째로 깨진다(cp949 는 한글을 제대로 찍는다). 못 찍는 글자만 `?` 로 놓는다.
# ★실패해도 조용히 넘어간다 — 출력 설정을 못 바꿨다고 실행기가 죽으면 본말전도다.
def _console_never_dies():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass


_console_never_dies()


# 진행 메시지는 이미 끝난 유료·로컬 작업의 결과가 아니다. Windows의 닫힌 콘솔이나
# 부모 프로세스가 끊은 파이프 때문에 EINVAL/EPIPE가 나면 그 스트림만 더 쓰지 않고,
# 표준출력이 망가진 경우 표준에러로 한 번 우회한다. 다른 쓰기 오류는 디스크 고갈 등
# 실제 장애일 수 있으므로 그대로 올린다.
_PROGRESS_BROKEN_STREAMS = []


def _progress(*values, **kwargs):
    kwargs.setdefault('flush', True)
    requested = kwargs.pop("file", None)
    primary = sys.stdout if requested is None else requested
    streams = [primary]
    if primary is sys.stdout and sys.stderr is not primary:
        streams.append(sys.stderr)
    for stream in streams:
        if any(stream is broken for broken in _PROGRESS_BROKEN_STREAMS):
            continue
        try:
            builtins.print(*values, file=stream, **kwargs)
            return True
        except OSError as exc:
            if exc.errno not in (errno.EINVAL, errno.EPIPE):
                raise
            if not any(stream is broken for broken in _PROGRESS_BROKEN_STREAMS):
                _PROGRESS_BROKEN_STREAMS.append(stream)
    return False


#: 디스크 가득 참으로 보는 errno — ENOSPC(28 · 맥·리눅스·윈도우 CRT 공통) · EDQUOT(사용량 한도 · 있는 OS 만).
DISK_FULL_ERRNOS = frozenset(v for v in (errno.ENOSPC, getattr(errno, 'EDQUOT', None)) if v is not None)
#: 윈도우 API 오류 번호 — ERROR_DISK_FULL(112) · ERROR_HANDLE_DISK_FULL(39). 파이썬이 errno 28 로 옮기지 않는 길(winerror 만)도 같이 본다.
DISK_FULL_WINERRORS = frozenset((112, 39))


def disk_full_note(err, path=None):
    """이 오류가 **이 PC 디스크가 가득 찬 것**이면 사람에게 보일 한 줄, 아니면 None (2026-10-24 · 신고 뇌전구 @…3508d6).

    한 곳 판별: 오류와 그 원인 사슬(__cause__·__context__ · 최대 8단)에서 errno ENOSPC/EDQUOT 또는 윈도우 112·39 를 찾는다.
    예전에는 단계 요청 중 로컬 쓰기의 ENOSPC 가 «서버 응답을 끝까지 확인하지 못했습니다» 로 나가 서버 문제로 읽혔다.
    어느 드라이브인지: 오류의 파일 이름 → 없으면 `path`(작업 폴더). 남은 용량은 그 경로의 가장 가까운 있는 조상에서 잰다.
    """
    hit, seen, cur = None, 0, err
    while cur is not None and seen < 8:
        if isinstance(cur, OSError) and (cur.errno in DISK_FULL_ERRNOS
                                         or getattr(cur, 'winerror', None) in DISK_FULL_WINERRORS):
            hit = cur
            break
        cur = cur.__cause__ or cur.__context__
        seen += 1
    if hit is None:
        return None
    where = hit.filename if isinstance(hit.filename, str) and hit.filename else path
    drive = free = None
    if where:
        probe = os.path.abspath(str(where))
        for _ in range(64):
            if os.path.exists(probe):
                break
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        if os.name == 'nt':
            drive = os.path.splitdrive(probe)[0] or probe
        else:
            mount = probe
            for _ in range(64):
                if os.path.ismount(mount):
                    break
                parent = os.path.dirname(mount)
                if parent == mount:
                    break
                mount = parent
            drive = mount
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            free = None
    room = ('남은 용량 %.1f GB' % (free / 1e9) if free is not None and free >= 1e9 else
            '남은 용량 %d MB' % (free // 1_000_000) if free is not None else '남은 용량을 재지 못함')
    return ('이 PC 디스크가 가득 찼습니다' + (' — 드라이브 %s' % drive if drive else '') + ' · ' + room
            + (' (쓰려던 곳: %s)' % where if where else '')
            + '. 서버 문제가 아닙니다. 그 드라이브의 공간을 비운 뒤 같은 명령으로 이어서 하세요.')


class StepError(RuntimeError):
    """여기서 멈춘다는 뜻. **원인은 두 갈래이고 그것을 타입으로 가른다** — 아래 참조."""


class StepBack(StepError):
    """처방이 «앞 단계 <back_to> 를 다시» 하나뿐인 멈춤 — 구동기가 사람에게 시키지 않고 그 단계로 돌아간다.

    같은 표지(mark · 같은 파일·같은 바이트 / 같은 빠진 칸)에 한 번만(상한) — 돌아가 다시 만든 뒤에도 또 같은 멈춤이면 이 글 그대로
    사람에게 말한다(volcano_drive._drive_loop). 자막(#32 → subtitle)·빠진 그림 칸(render_plan → images) 이 같은 길을 쓴다.
    """

    def __init__(self, message, back_to, mark):
        super().__init__(message)
        self.back_to, self.mark = back_to, mark
        #: 돌아갈 단계에 더할 payload 칸 번호 목록 — {칸 이름: [번호…]} (구동기가 기존 목록과 합친다 · 사진 실사 검수의 flow_redo).
        self.payload_add = {}


class RemoteImageAcquisitionError(StepError):
    """HTTP(S) image acquisition failed before any review request was sent."""


class ProviderRefusalError(StepError):
    """An explicit provider decision, not a parse failure or a source-rights finding."""

    def __init__(self, origin, reason_code, reason, todo=None):
        self.origin = str(origin)
        self.reason_code = str(reason_code)
        self.reason = str(reason)[:600]
        self.todo = None if todo is None else str(todo)
        # ★거부 코드마다 사람이 바로 할 일을 붙인다(2026-10-17 실행기 중단 보고 — 이미지 402 6건·401 7건이 «거절» 한 마디로 끝났다).
        todo_by_code = {"HTTP_402": " ▶ 그 서비스 계정의 크레딧(잔액)이 모자랍니다 — 충전한 뒤 같은 명령을 다시 실행하세요(받아 둔 그림은 다시 사지 않습니다).",
                "HTTP_401": " ▶ 그 서비스 API 키가 맞지 않거나 지워졌습니다 — 키를 다시 넣은 뒤 같은 명령을 다시 실행하세요.",
                "HTTP_403": " ▶ 그 서비스가 이 키·계정의 사용을 막았습니다 — 계정 상태·권한을 확인하세요.",
                "HTTP_429": " ▶ 그 서비스의 요청 한도에 걸렸습니다 — 한도가 풀린 뒤 같은 명령을 다시 실행하세요(새 계정·새 키로 돌리지 마세요)."}
        super().__init__(f"제공자가 요청을 거절했습니다 [{self.origin}/{self.reason_code}]: {self.reason}. "
                         "제공자의 응답이며 소재의 권리 사실을 판정한 것이 아닙니다. 자동 대체 호출은 하지 않습니다."
                         # 부르는 쪽이 그 거절에 맞는 할 일을 정확히 아는 경우(그림 접수 멈춤 — 다시 보낼 시각·표식)는 그 글이 기본 글을 대신한다.
                         + (self.todo if self.todo is not None else todo_by_code.get(self.reason_code, "")))


def _raise_provider_refusal(raw, origin=None):
    """Read only explicit provider refusal fields, before any task-JSON extraction."""
    if not isinstance(raw, dict):
        return
    feedback = raw.get('promptFeedback')
    blocked = feedback.get('blockReason') if isinstance(feedback, dict) else None
    if isinstance(blocked, str) and blocked.strip():
        raise remember_review_refusal(ProviderRefusalError(origin or 'provider.gemini', blocked, f'blockReason={blocked}'))
    candidates = raw.get('candidates')
    for candidate in candidates if isinstance(candidates, list) else []:
        if not isinstance(candidate, dict):
            continue
        reason = candidate.get('finishReason')
        if isinstance(reason, str) and reason in {'SAFETY', 'RECITATION', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII',
                      'IMAGE_SAFETY', 'IMAGE_PROHIBITED_CONTENT', 'IMAGE_RECITATION'}:
            raise remember_review_refusal(ProviderRefusalError(origin or 'provider.gemini', reason, f'finishReason={reason}'))
    choices = raw.get('choices')
    for choice in choices if isinstance(choices, list) else []:
        if not isinstance(choice, dict):
            continue
        message = choice.get('message') or {}
        refusal = message.get('refusal') if isinstance(message, dict) else None
        if isinstance(refusal, str) and refusal.strip():
            raise remember_review_refusal(ProviderRefusalError(origin or 'provider.openai_compatible', 'message.refusal', refusal.strip()))
        if choice.get('finish_reason') == 'content_filter':
            raise remember_review_refusal(ProviderRefusalError(origin or 'provider.openai_compatible', 'content_filter', 'finish_reason=content_filter'))
    if raw.get('stop_reason') == 'refusal':
        raise remember_review_refusal(ProviderRefusalError(origin or 'provider.claude', 'refusal', 'stop_reason=refusal'))


def _raise_cli_refusal(text, origin='provider.claude_cli'):
    # Conservative direct speech only. Merely mentioning copyright, quoting a
    # refusal, or being unable to read a file is not a provider safety refusal.
    text = str(text or '').strip()
    direct = re.match(r"(?:I'm sorry[,.:!]?\s*|Sorry[,.:!]?\s*)?I (?:cannot|can't|won't|will not|am unable to) "
                      r"(?:help|assist|provide|generate|create|process|comply|fulfill)\b", text, re.I)
    # Require a causal restriction, not an unrelated policy word elsewhere in
    # the answer (for example a quoted filename after a missing-file error).
    policy = (r'(?:copyright (?:restrictions?|policy|policies|infringement)|'
              r'(?:provider )?(?:safety|content) polic(?:y|ies))')
    rationale = re.search(
        r'\b(?:(?:because|as|since) (?:it |this (?:request |content )?)?(?:would )?'
        r'violates? (?:the |my |our )?' + policy + r'|'
        r'(?:due to|because of|under) (?:the |my |our )?' + policy + r')(?=[\s,;.!]|$)', text, re.I)
    korean = re.match(r'(?:죄송(?:하지만|합니다)[,.!]?\s*)?(?:저는|제가)\s', text) and re.search(
        r'(?:저작권(?: 제한| 정책| 침해)?|안전 정책|콘텐츠 정책)\s*'
        r'(?:때문에|으로 인해|상|에 따라|에 위배되어|을 위반하므로|를 위반하므로)'
        r'[^.!?\n]*(?:도와드릴 수 없|수행할 수 없|제공할 수 없|생성할 수 없)', text)
    if (direct and rationale) or korean:
        raise remember_review_refusal(ProviderRefusalError(origin, 'explicit_refusal', text))


class RejectedError(StepError):
    """**서버가 반려한 것**(HTTP 200 + `isError`). 메시지에 고칠 방법이 들어 있다.

    ■ 왜 타입을 나눴나 (2026-08-16)
        구동기는 예외가 나면 `feedback(kind="bug")` 로 서버에 한 줄 보고한다.
        그런데 서버 반려도 예외로 오기 때문에, **반려가 전부 '오작동' 으로 쌓였다**
        — 전수 1,518건 중 **58.5%**(887건)가 서버 반려문 그대로였다.
        그 통을 일일 리포트가 "크래시" 로 세고, 아침 알림이 *"서버가 답을 못 준
        것이다 — 수강생이 고칠 수 없다"* 라고 말했다. 실제로 그날 서버 예외는
        **0건**이었고, 그 5건은 전부 본문에 고치는 법이 적힌 반려였다.
    ★문자열로 가르지 마라. 반려문에 무슨 말이 들어올지 우리가 정하지 못한다 —
      가르는 것은 **어디서 났는가**이고, 그건 타입만이 안다.
    ★`StepError` 를 상속한다 — 기존 `except StepError` 자리가 전부 그대로 돈다.
    """


def _request_error_text(text, req):
    """요청에 쓴 인증값과 미디어를 가린 짧은 진단. 오류 사유 자체는 남긴다."""
    detail = str(text)
    for name, value in req.header_items():
        if any(word in name.lower() for word in ("authorization", "key", "token", "cookie")):
            for secret in (str(value), str(value).removeprefix("Bearer ")):
                if secret:
                    detail = detail.replace(secret, "[redacted]")
    from urllib.parse import parse_qsl, urlsplit
    for name, value in parse_qsl(urlsplit(req.full_url).query):
        if any(word in name.lower() for word in ("key", "token", "signature")) and value:
            detail = detail.replace(value, "[redacted]")
    detail = re.sub(r"data:[^\s\"']+", "[media]", detail)
    return " ".join(detail.split())[:600]


def _http_error_detail(exc, req):
    """HTTP 오류의 사유를 보존한다. 요청 인증값/미디어는 로그에 남기지 않는다."""
    try:
        raw = exc.read(4096).decode("utf-8", "replace")
        try:
            obj = json.loads(raw)
            err = obj.get("error", obj) if isinstance(obj, dict) else {}
            detail = str(err.get("message") or err.get("type") or "") if isinstance(err, dict) else str(err)
            if isinstance(err, dict) and err.get("code"):
                detail = str(err["code"]) + (": " + detail if detail else "")
        except ValueError:
            detail = "" if raw.lstrip().startswith("<") else raw
        exc.msg = _request_error_text(str(exc.reason) + (" — " + detail if detail else ""), req)
    except Exception:  # noqa: BLE001
        pass                         # 진단을 못 읽어도 원래 HTTP 상태는 보존한다
    finally:
        exc.close()


#: Cloudflare 가 붙이는 «Worker exceeded resource limits» 오류 번호(공식 문서
#: developers.cloudflare.com/workers/platform/limits — CPU·메모리 한도를 넘으면 1102).
_LIMIT_RE = re.compile(r"error code:\s*1102\b")


def _limit_exceeded(exc):
    """서버가 이 요청을 **계산하다가** CPU·메모리 한도를 넘어 끊겼는가(1102).

    ★1101(파이썬이 켜지다 죽음 — 서버 코드가 안 돌았다)과 반대다. 1102 는 우리 코드가
      **돌았다**. 같은 요청은 같은 계산을 하다 같은 곳에서 또 끊긴다(2026-09-26 실측:
      한 요청이 58번 전부 32.5초에서 끊겼다). 그리고 끊길 때마다 그 데이터센터의
      다른 수강생 요청까지 1101 로 실패했다(Cloudflare workerd #6624).
    """
    return bool(_LIMIT_RE.search(str(getattr(exc, "msg", "") or "")))


def _tls_verify_failed(exc):
    """서버 인증서를 믿을 사슬을 못 지었다(ssl.SSLCertVerificationError) — 연결 전 실패라 HTTP 요청은 나가지 않았다."""
    import ssl
    return isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError)


def _windows_complete_chain(req):
    """Windows 에서만: 그 서버 인증서로 **Windows 가 사슬을 직접 짓게** 한다(`certutil -urlfetch -verify`). True = 지었다.

    ■ 왜 (2026-10-21 win-main 실측 · 리아체 lotteriafont.com)
        Windows 는 신뢰 루트를 다 깔아 두지 않고, 사슬을 지을 때 빠진 루트를 그 자리에서 받아 넣는다(자동 루트 갱신).
        브라우저·PowerShell 은 그 길을 타지만 파이썬(OpenSSL)은 저장소에 **이미 있는** 루트만 읽어 그 길을 못 탄다 —
        GlobalSign Root R6 이 없던 win-main 에서 «self-signed certificate in certificate chain» 으로 글꼴을 못 받았고
        (같은 날 브라우저로는 열림), certutil 이 사슬을 지은 뒤 새 ssl 문맥은 받았다. 수강생 Windows 도 같다.
    ■ 서버에는 TLS 악수 한 번(get_server_certificate)만 — HTTP 요청은 더 보내지 않는다. 루트를 받는 곳은 Windows 갱신 경로다.
    ■ 실패(다른 OS·certutil 없음·시간 초과)면 False — 부르는 쪽이 원래 오류를 그대로 올린다(삼키지 않는다).
    """
    if os.name != "nt":
        return False
    import ssl
    parts = urllib.parse.urlsplit(req.full_url)
    if parts.scheme != "https" or not parts.hostname:
        return False
    try:
        pem = ssl.get_server_certificate((parts.hostname, parts.port or 443), timeout=20)
        with tempfile.TemporaryDirectory() as td:
            leaf = os.path.join(td, "server.cer")
            with open(leaf, "w", encoding="ascii") as fh:
                fh.write(pem)
            # 자식은 한 문(_spawn)으로 띄운다 — 도구 찾기·윈도우 UTF-8 환경이 같은 자리에서 정해진다(test_runner_win [8]).
            #   certutil 이 없으면 _spawn 이 StepError(못 찾음)를 낸다 — 아래에서 다른 실패와 같이 False 다(원래 오류는 부르는 쪽이 올린다).
            done = _spawn(["certutil", "-urlfetch", "-verify", leaf], capture_output=True, timeout=60)
    except (OSError, ValueError, subprocess.SubprocessError, StepError) as exc:
        _progress(f"  [인증서] {parts.hostname} — Windows 사슬 짓기를 못 했다({type(exc).__name__}: {exc})", flush=True)
        return False
    _progress(f"  [인증서] {parts.hostname} — 파이썬이 못 믿은 사슬을 Windows 가 지었다(certutil 종료 {done.returncode}) · 한 번 다시 연결한다", flush=True)
    return done.returncode == 0


def _open_retry(req, timeout, what, before_request=None, observation=None, *, retry_safe=True):
    """`_open_attempts` 그대로 — 단 인증서 사슬 실패는 Windows 가 사슬을 지은 뒤 **한 번만** 다시 연결한다(`_windows_complete_chain`).
    악수 단계 실패라 요청이 나가지 않았으므로 단발 POST(retry_safe=False)도 같다."""
    try:
        return _open_attempts(req, timeout, what, before_request, observation, retry_safe=retry_safe)
    except urllib.error.URLError as exc:
        if not (_tls_verify_failed(exc) and _windows_complete_chain(req)):
            raise
    import ssl
    return _open_attempts(req, timeout, what, before_request, observation, retry_safe=retry_safe,
                          context=ssl.create_default_context())   # 새 문맥 = 저장소를 다시 읽는다


def _open_attempts(req, timeout, what, before_request=None, observation=None, *, retry_safe=True, context=None):
    """일시적 인프라 실패만 다시 던진다. **서버의 반려는 재시도하지 않는다.**

    `tools/call` 과 유료 모델 POST는 접수 여부가 불명확할 수 있으므로
    `retry_safe=False`를 전달한다. 기본 재시도는 멱등 읽기 경로에만 쓴다.


    ■ 왜 필요했나 (2026-08-13 실측)
        서버가 간헐적으로 HTTP 500 을 낸다. `wrangler tail` 로 잡은 예외는
        `NoGilError: Attempted to use PyProxy when Python GIL not held` 이고
        자리는 `preparePython → initPyInstance` — **우리 파이썬이 돌기 전**이다.
        런타임 콜드스타트 실패라 서버 코드로는 잡을 수 없고 로그에도 안 남는다.
        같은 자산을 반복해 받아 재니 40회 중 5회, 65 이벤트 중 6건 = 약 9% 였다.
        재시도가 없으면 팩 3~4개를 받는 `assets` 한 단계에서만 약 4분의 1이 죽고,
        단계가 열댓 개인 파이프라인은 어딘가에서 거의 반드시 한 번 맞는다.

    ■ ★읽기 경로의 5xx만 재시도한다
        과거에는 `POST /` 의 5xx 도 서버 코드 실행 전이라고 가정했다. 실제로
        콜드스타트 실패가 있었지만 모든 5xx·연결 끊김에서 도구 실행 전임을
        증명할 수는 없다. 그래서 유료 작업이 가능한 POST는 호출부에서 단발로
        고정한다. 기본 재시도는 자산을 읽는 GET 경로에만 허용한다.
    ■ ★4xx 는 다시 던지지 않는다 — 401·403·404 는 사람이 고칠 일이고,
        되풀이하면 원인을 늦게 알게 될 뿐이다.
    ■ ★★1102 도 다시 던지지 않는다 (2026-09-26 실측) — 위 «5xx = 파이썬이 안 돌았다»
        전제가 **틀리는 유일한 5xx** 다. 1102 는 서버가 이 요청을 계산하다 CPU·메모리
        한도를 넘어 끊긴 것이라, 다시 보내면 같은 계산을 또 하다 또 끊긴다. 실제로 한
        요청을 3번씩 몇 분마다 되보내 하루 58번 끊겼고, 끊길 때마다 그 데이터센터의
        다른 수강생 요청이 1101 로 실패했다(`_limit_exceeded`).
    ■ ★여기만 실행기에 상수를 둔다
        이 저장소 원칙은 "실행기에 기본값을 두지 마라(서버가 준 값을 써라)" 인데,
        이 재시도가 지키는 것이 바로 **서버에서 값을 받아오는 그 호출**이라
        서버가 줄 수 없다. 그래서 여기 있고, 그 이유를 여기 적는다.
    """
    last = None
    attempts = 3 if retry_safe else 1
    for a in range(attempts):
        if before_request:
            before_request()
        try:
            tls = {"context": context} if context is not None else {}
            if observation is None:
                return urllib.request.urlopen(req, timeout=timeout, **tls)
            # A reservation is bookkeeping; retry sleep and error formatting are
            # outside each actual HTTP attempt. The successful attempt continues
            # through JSON reading/parsing in its caller.
            observation['started_ns'] = time.perf_counter_ns()
            try:
                return urllib.request.urlopen(req, timeout=timeout, **tls)
            except BaseException as error:
                seconds = max(0, time.perf_counter_ns()-observation['started_ns']) / 1_000_000_000
                from runtime_metrics import provider_response
                provider_response('video_review', observation['request_sha256'], error, None,
                    service=observation['service'], model=observation['model'], seconds=seconds,
                    outcome='http_error' if isinstance(error, urllib.error.HTTPError) else 'transport_error')
                raise
        except urllib.error.HTTPError as e:
            _http_error_detail(e, req)
            if e.code < 500:
                raise                       # 사람이 고칠 것 — 되풀이하지 않는다
            if _limit_exceeded(e):
                raise                       # 서버가 **돌다가** 한도에 끊겼다 — 되풀이하면 또 끊긴다
            last = e
        except urllib.error.URLError as e:   # 연결 끊김·이름풀이 실패 등
            if _tls_verify_failed(e):
                raise                       # 인증서 사슬은 되풀이해도 그대로다 — 부르는 쪽(_open_retry)이 Windows 사슬 짓기로 다룬다
            last = e
        except OSError as e:                 # 타임아웃·리셋
            last = e
        if a + 1 < attempts:
            _progress(f"  [재시도] {what} — 서버가 일시적으로 응답하지 못했다 ({last})",
                  flush=True)
            time.sleep(1 + a)
    raise last


def _observe_clock():
    try:
        return time.perf_counter()
    except Exception:  # noqa: BLE001
        return None

def _observe_value(observation, key, value):
    try:
        observation[key] = value
    except Exception:  # noqa: BLE001
        pass

def _observe_elapsed(observation, key, started, ended=None):
    try:
        now = _observe_clock() if ended is None else ended
        if started is not None and now is not None:
            observation[key] = max(0, int((now-started)*1000))
    except Exception:  # noqa: BLE001
        pass


def _read_mcp_response(req, timeout, what, observation, *, complete=None):
    """One exchange; metadata is correlation only, never acceptance proof."""
    started = time.perf_counter()
    response = None
    body_started = json_started = None
    observation['phase'] = 'headers'
    def headers(source):
        values = getattr(source, 'headers', None)
        if values is None:
            return
        ray = values.get('cf-ray')
        if isinstance(ray, str) and re.fullmatch(r'[0-9a-fA-F]{16}(?:-[A-Z]{3})?', ray):
            observation['cf_ray'] = ray
        size = values.get('Content-Length')
        if isinstance(size, str) and re.fullmatch(r'[0-9]{1,18}', size):
            observation['expected_bytes'] = int(size)
    try:
        response = _open_retry(req, timeout, what, retry_safe=False)
        headers(response)
        _observe_elapsed(observation, 'headers_ms', started)
        observation['phase'] = 'body'
        try:
            body_started = _observe_clock()
        except Exception:  # noqa: BLE001
            pass  # Optional timing cannot replace a response/read outcome.
        _observe_value(observation, 'body_progress', 'unknown')
        raw = response.read()
        if complete is not None:
            complete(raw)
        observation['received_bytes'] = len(raw)
        _observe_value(observation, 'body_complete', True)
        _observe_value(observation, 'body_progress', 'complete')
        _observe_elapsed(observation, 'body_ms', body_started)
        observation['phase'] = 'json'
        try:
            json_started = _observe_clock()
        except Exception:  # noqa: BLE001
            pass  # Optional timing cannot replace a response/read outcome.
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        headers(exc)
        raise
    finally:
        now = None
        try:
            now = _observe_clock()
        except Exception:  # noqa: BLE001
            pass  # Preserve the original read/JSON exception.
        if observation.get('phase') == 'headers':
            _observe_elapsed(observation, 'headers_ms', started, now)
        if body_started is not None and 'body_ms' not in observation:
            _observe_elapsed(observation, 'body_ms', body_started, now)
        if json_started is not None:
            _observe_elapsed(observation, 'json_ms', json_started, now)
        observation['elapsed_ms'] = max(0, int((time.perf_counter() - started) * 1000))
        if response is not None:
            close = getattr(response, 'close', None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass


def _read_unreceipted(req, timeout, what, observation):
    """응답 영수증이 **없는** 우리 서버 `tools/call` — 서버가 받지 못한 것이 분명한 실패만 다시 보낸다.

    ■ 2026-10-05 · 원장 §5-6 — 원장 토큰·영수증을 안 쓰는 클라이언트·feedback(작업 폴더 없음)이 이 길이다.
        main 이 `_open_retry` 로 3회(1초/2초) 던지던 길을 되살리되, 서버가 **받았을 수 있는** 실패(시간 초과·
        연결 리셋·본문 끊김)는 빼고 5xx(1102 제외 — 서버가 돌다 끊긴 것)와 «보내기 전» 연결 실패(연결 거부·
        이름풀이 실패)만 다시 보낸다. 새 숫자를 짓지 않는다 — Cloudflare 문서에 1101 재시도 숫자는 없다(원장 §9-7).
        영수증이 있는 요청은 `response_receipts.Delivery` 가 같은 신원 재전송으로 따로 다룬다.
    """
    for attempt in range(3):
        try:
            return _read_mcp_response(req, timeout, what, observation)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or _limit_exceeded(exc) or attempt == 2:
                raise
            why = f"HTTP {exc.code}"
            exc.close()
        except urllib.error.URLError as exc:
            if attempt == 2 or not isinstance(getattr(exc, 'reason', None),
                                              (ConnectionRefusedError, socket.gaierror)):
                raise
            why = type(exc.reason).__name__
        _progress(f"  [재시도] {what} — 서버가 받지 못한 요청({why})이라 다시 보낸다", flush=True)
        time.sleep(1 + attempt)


def _wire_fetch(req, timeout):
    """멱등 wire RPC 한 건 — 연결부터 본문 JSON 까지를 한 시도로 보고 일시적 실패만 3회(1초/2초) 시도한다.

    `_open_retry` 의 기본 길과 같은 판정이다(5xx 중 1102 제외 · 4xx 즉시 · 연결·시간 초과·본문 끊김). 본문이
    끊긴 것도 다시 보낸다 — 이 요청들은 읽기이거나 내용 주소라 두 번 닿아도 결과가 같다(원장 W2-03).
    본문이 JSON 이 아닌 것(ValueError)은 서버가 그렇게 답한 것이라 다시 보내지 않는다.
    """
    for attempt in range(3):
        response = None
        try:
            response = _open_retry(req, timeout, "검수 증거 전송", retry_safe=False)
            return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or _limit_exceeded(exc) or attempt == 2:
                raise
            why = f"HTTP {exc.code}"
        except (OSError, http.client.HTTPException) as exc:
            if attempt == 2:
                raise
            why = type(exc).__name__
        finally:
            close = getattr(response, 'close', None)
            if callable(close):
                close()
        _progress(f"  [재시도] 검수 증거 전송 — 서버가 일시적으로 응답하지 못했다({why})", flush=True)
        time.sleep(1 + attempt)


def _mcp_observation_note(observation):
    # No body, URL, authorization, private path or exception text.
    return " [요청 진단] " + json.dumps(observation, ensure_ascii=True, separators=(',', ':'))


def _same_focus_value(left, right):
    """Match the server's typed JSON comparison without making full wire copies."""
    if left is right:
        return True
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (len(left) == len(right)
                and all(type(k) is str and k in right and _same_focus_value(v, right[k])
                        for k, v in left.items()))
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_focus_value(a, b) for a, b in zip(left, right))
    if type(left) is float:
        return left == right and left.hex() == right.hex()
    return type(left) in (str, int, bool, type(None)) and left == right


_FOCUS_REF_FLAG = "VOLCANO_FOCUS_REF_VERSION"
_FOCUS_PACK_FLAG = "VOLCANO_FOCUS_PACK_VERSION"
# ★측정 행 묶음(pack v1, 2026-09-12). 요청 상한(400,000 구조 토큰)은 문자열 안을 세지 않고
#   숫자도 세지 않지만 숫자 **사이의 쉼표와 괄호**는 센다. 명화관 실측 한 컷이 평균 11,000
#   토큰(자막 OCR 상자 6,500 + 표본별 판정·표본 묶음 6,000)이라 36컷이면 참조 v3 로 중복을
#   없애도 첫 제출 한 번이 상한을 넘었다(2일 413 보고 606건 · 명화관 31명 · 인물형 18명 ·
#   린박스 26명). 숫자 목록은 글자 하나로, 같은 열쇠의 사전 목록은 열(column)로 접는다 —
#   값은 하나도 버리지 않고 서버가 검사 전에 그대로 되돌린다. 서버가 `_meta.focus_pack_version`
#   을 알린 뒤에만 쓴다(옛 서버에는 접힌 모양이 가지 않는다).
_PACK_SEPS = (' ', '|', ';', '/')
_PACK_KEYS = frozenset(('_np', '_cols', '_rows', '_c1'))
# 서버 `entry._JSON_STRUCTURE` 와 같은 자 — 문자열은 하나로, 숫자는 안 세고, 괄호·쉼표·콜론만 센다.
# ★서버 자의 소유 한정자(`*+`)는 **Python 3.11 부터**다 — 실행기는 수강생의 3.9/3.10 에서도 읽혀야 하므로
#   같은 것을 세는 3.9 문법으로 적는다(경계 검사 [96] 이 2026-09-12 19:21 에 `re.error: multiple repeat` 로 잡았다 —
#   그대로 나갔으면 옛 파이썬 수강생은 실행기를 읽는 순간 죽었다). 같은 수를 세는 것은 test_followups_0912 가 서버 자와 대조한다.
_REQUEST_TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"?|[{}\[\],:]')
REQUEST_TOKEN_LIMIT = 400_000


def _request_structure_exceeds_limit(body):
    """Count JSON string/structure tokens like entry without regex capture memory.

    This receives only bytes made by json.dumps. Every quoted string counts
    once; six JSON punctuation bytes count once; numbers and literal letters
    do not count. Stop at the server's existing 400,000-token admission bound.
    """
    count = 0
    quoted = escaped = False
    for byte in body:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:  # backslash
                escaped = True
            elif byte == 34:  # closing quote
                quoted = False
        elif byte == 34:  # opening quote
            quoted = True
            count += 1
        elif byte in (123, 125, 91, 93, 44, 58):  # {}[],:
            count += 1
        if count > REQUEST_TOKEN_LIMIT:
            return True
    return False


def payload_token_report(payload, top=6):
    """Per-field structure-token sizes of the payload as sent — for a 413 to name the culprit.

    2026-09-12 실측: pack v1 배포 뒤에도 새 실행기에서 413 이 났는데(명화관 4명 · 인물형 1명) 413 요청은
    서버가 파싱 전에 거부해 저장되지 않는다 — 어느 칸이 컸는지 실행기 자신이 말해야 한다.
    """
    if not isinstance(payload, dict):
        return '(payload 가 객체가 아님)'
    def count(value):
        return len(_REQUEST_TOKEN.findall(json.dumps(value, ensure_ascii=False).encode()))
    sizes = sorted(((count(value), key) for key, value in payload.items()), reverse=True)
    total = sum(n for n, _ in sizes)
    return (f"합계 {total:,} (상한 {REQUEST_TOKEN_LIMIT:,}) · "
            + ' · '.join(f"{key} {n:,}" for n, key in sizes[:top]))


def _focus_pack_version():
    try:
        return int(os.environ.get(_FOCUS_PACK_FLAG, "0"))
    except ValueError:
        return 0


# ★★협상 결과는 **작업 폴더에도** 적는다 (2026-09-12 F16 실측). 환경변수는 프로세스가 끝나면 사라진다 —
#   구동기는 사람 차례(need_input)마다 끝나고 답을 받은 뒤 **새 프로세스**로 다시 뜬다. 그 첫 요청은
#   서버가 `_meta` 를 말하기 전이라 접지 않은 채 나갔고(새 팩 06d7202f8552 의 413 직전 저장 요청이 전부
#   `_focus_pack` 없음), 명화관 35컷 측정(≈400k 구조 토큰)은 그대로 413 → 구동기 종료 → 재실행 → 또
#   첫 요청 → 413 (한 사람 6분에 30번 · 인물형 2분에 16번). 파일이 있으면 첫 요청부터 접는다.
#   환경변수는 여전히 읽는 자리 하나다 — 파일은 그 값을 **다음 프로세스에 씨앗으로** 넣을 뿐이다.
_SERVER_CAPS_FILE = ".volcano_server_caps.json"
_CAP_FLAGS = ((_FOCUS_REF_FLAG, "focus_ref_version", 2), (_FOCUS_PACK_FLAG, "focus_pack_version", 0))


def _caps_path(workdir):
    if not isinstance(workdir, str) or not workdir.strip() or not os.path.isdir(workdir):
        return None
    return os.path.join(workdir, _SERVER_CAPS_FILE)


def _read_caps(path):
    try:
        with open(path, encoding="utf-8") as fh:
            caps = json.load(fh)
    except (OSError, ValueError):
        return {}
    return caps if isinstance(caps, dict) else {}


def load_server_caps(workdir):
    """Seed this process's capability flags from the workdir file (never lowers a flag)."""
    path = _caps_path(workdir)
    if not path:
        return {}
    caps = _read_caps(path)
    for flag, key, floor in _CAP_FLAGS:
        value = caps.get(key)
        if type(value) is int and value > max(floor, _env_int(flag, floor)):
            os.environ[flag] = str(value)
    # 지문 표지 판은 서버가 마지막으로 알린 값 그대로다(내려갈 수 있다 · `_blob_caps_seen`).
    if _BLOB_FLAG not in os.environ and type(caps.get("blob_version")) is int:
        os.environ[_BLOB_FLAG] = str(caps["blob_version"])
    return caps


def remember_server_caps(workdir, meta):
    """Persist what the server advertised in `_meta`; never raises (a read-only folder must not stop a step)."""
    path = _caps_path(workdir)
    if not path or not isinstance(meta, dict):
        return
    caps = {key: meta[key] for _, key, _ in _CAP_FLAGS if type(meta.get(key)) is int}
    if type(meta.get('response_receipt_version')) is int:
        caps['response_receipt_version'] = meta['response_receipt_version']
    if not caps:
        return
    old = _read_caps(path)
    merged = dict(old)
    for key, value in caps.items():
        if type(merged.get(key)) is not int or value > merged[key]:
            merged[key] = value
    if merged == old:
        return
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(merged, fh)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def _env_int(flag, default):
    try:
        return int(os.environ.get(flag, str(default)))
    except ValueError:
        return default


# ★★큰 칸 지문 표지 (2026-09-26 · 서버 `volcano_blob` 과 **같은 규칙**)
#   A버킷 편집은 측정·편집 상태(`focus_measurements` 2.9MB · `rinbox` 250~320KB)를 모든 요청에
#   통째로 싣고, 서버는 그것을 응답에 네 벌(최상위·next_payload × 글자·구조)로 되돌려 줬다 —
#   명화관 응답 한 번이 12.6MB 였다. 이제 서버가 이미 가진 값은 지문만 보내고, 서버도 이번 요청에
#   실은 값과 같은 값은 지문으로 돌려준다. **실행기가 원본을 쥔다** — 서버 저장소가 비면 통째로 다시 보낸다.
#   ★지문 규칙(`_blob_encode`·`_blob_units`)은 서버 `volcano_blob.encode`·`units` 와 바이트까지 같아야
#     한다 — 검사(`tests/test_blob_protocol.py`)가 두 사본을 같은 값에 태워 대조한다.
_BLOB_FLAG = "VOLCANO_BLOB_VERSION"
_BLOB_CAPS = "source-frame-clock-v1, focus-record-v1, blob-client-missing-v1, blob-v1, agy-review-v1, structured-only, wire-blob-v1, response-refs-v1, response-gzip-v1, review-evidence-ref-v1, pending-review-evidence-ref-v1, response-focus-rows-v1, response-inline-blobs-v1"
#: 표지를 못 푼 응답을 다시 받을 때 — «표지를 풀 수 있다» 를 빼고 알린다(서버가 응답을 통째로 준다).
_BLOB_CAPS_PLAIN = "source-frame-clock-v1, focus-record-v1, agy-review-v1, structured-only, blob-refetch, wire-blob-v1, response-refs-v1, response-gzip-v1, review-evidence-ref-v1, pending-review-evidence-ref-v1, response-focus-rows-v1, response-inline-blobs-v1"
# Matches entry.MAX_REQUEST_BYTES. Actual chunk/unit limits are negotiated
# before any upload; each request keeps the existing 16 MiB HTTP ceiling.
_WIRE_REQUEST_BYTES = 16 * 1024 * 1024
_WIRE_METHOD = "volcano/blob"
_BLOB_MIN_BYTES = 16384
_BLOB_EXCLUDED = frozenset(("frames", "focus_frames"))
_BLOB_KNOWN_FILE = ".volcano_blob_known.json"
_BLOB_KNOWN_MAX = 4096
_BLOB_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BLOB_KNOWN = {}        # 작업 폴더 → {지문: None} (들어온 순서 · 오래된 것부터 버린다)


def _blob_encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8", "surrogatepass")


def _blob_digest(data):
    return hashlib.sha256(data).hexdigest()


def _blob_marker(sha):
    return {"_blob": 1, "sha": sha}


def _blob_is_marker(value):
    return (isinstance(value, dict) and len(value) == 2 and type(value.get("_blob")) is int
            and value["_blob"] == 1 and isinstance(value.get("sha"), str)
            and _BLOB_SHA.match(value["sha"]) is not None)


def _blob_eligible(key):
    return isinstance(key, str) and not key.startswith("_") and key not in _BLOB_EXCLUDED


def _blob_units(payload, skip=()):
    """[(경로, 값, 바이트)] — 서버 `volcano_blob.units` 와 같은 규칙."""
    out = []
    if not isinstance(payload, dict):
        return out
    for key, value in payload.items():
        if not _blob_eligible(key) or _blob_is_marker(value) or key in skip:
            continue
        if isinstance(value, dict):
            kids = []
            for sub, child in value.items():
                if _blob_is_marker(child):
                    continue
                data = _blob_encode(child)
                if len(data) >= _BLOB_MIN_BYTES:
                    kids.append(((key, sub), child, data))
            if kids or any(_blob_is_marker(child) for child in value.values()):
                out.extend(kids)
                continue
        data = _blob_encode(value)
        if len(data) >= _BLOB_MIN_BYTES:
            out.append(((key,), value, data))
    return out


def _blob_version():
    return _env_int(_BLOB_FLAG, 0)


def _blob_known_path(workdir):
    if not isinstance(workdir, str) or not workdir.strip() or not os.path.isdir(workdir):
        return None
    return os.path.join(workdir, _BLOB_KNOWN_FILE)


def _blob_known(workdir):
    key = workdir if isinstance(workdir, str) else ""
    if key not in _BLOB_KNOWN:
        known = {}
        path = _blob_known_path(workdir)
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict) and data.get("v") == 1 and isinstance(data.get("shas"), list):
                    known = {s: None for s in data["shas"] if isinstance(s, str) and _BLOB_SHA.match(s)}
            except (OSError, ValueError):
                known = {}
        _BLOB_KNOWN[key] = known
    return _BLOB_KNOWN[key]


def _blob_remember(workdir, add=(), drop=()):
    """서버가 가진 지문 목록을 고친다. 파일을 못 써도 멈추지 않는다(다음 프로세스가 통째로 보낼 뿐이다)."""
    known = _blob_known(workdir)
    for sha in drop:
        known.pop(sha, None)
    for sha in add:
        if isinstance(sha, str) and _BLOB_SHA.match(sha):
            known.pop(sha, None)
            known[sha] = None
    while len(known) > _BLOB_KNOWN_MAX:
        known.pop(next(iter(known)))
    path = _blob_known_path(workdir)
    if not path:
        return
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "shas": list(known)}, fh)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def _blob_wire(payload, wire, workdir):
    """(보낼 payload, {지문: 바이트}, [통째로 보낸 지문]).

    ★단위는 **실행기가 쥔 값**(접기 전)에서 잰다 — 서버도 표지를 풀고 pack 을 되돌리기 전의 그 값으로 잰다.
    ★`local`(이번 요청의 모든 단위)은 **언제나** 잰다 — 헤더(`blob-v1`)로 «응답의 표지를 풀 수 있다» 고
      알렸으니, 서버가 아직 `blob_version` 을 알리기 전인 첫 요청의 응답에도 표지가 올 수 있다
      (검사가 잡았다: 첫 요청 응답의 표지를 못 풀어 멈췄다).
    ★표지를 **보내는** 것만 서버가 `_meta.blob_version` 을 알린 뒤다(옛 서버에는 안 간다).
    """
    local, inline = {}, []
    if not isinstance(payload, dict) or not isinstance(wire, dict):
        return wire, local, inline
    send = _blob_version() >= 1
    known = _blob_known(workdir) if send else {}
    out = dict(wire)
    for path, _value, data in _blob_units(payload):
        sha = _blob_digest(data)
        local[sha] = data
        if sha not in known:
            inline.append(sha)
            continue
        if len(path) == 1:
            out[path[0]] = _blob_marker(sha)
            continue
        field = out.get(path[0])
        if not isinstance(field, dict) or path[1] not in field:
            inline.append(sha)
            continue
        if field is wire.get(path[0]):
            field = out[path[0]] = dict(field)
        field[path[1]] = _blob_marker(sha)
    return out, local, inline


class _BlobUnknown(StepError):
    """응답의 표지가 이 실행기 사본에 없어 결과를 확정할 수 없다."""


def _blob_take(local, sha, name):
    data = local.get(sha)
    if data is None:
        raise _BlobUnknown(
            f"[{name}] 서버 응답의 지문({sha[:12]})을 풀 원본이 이 실행기에 없습니다 — 서버 쪽 결함입니다"
            "(실행기를 새로 받아도 같습니다). 단계가 이미 실행되었을 수 있으므로 다시 보내지 않았습니다. "
            "접수 기록과 기존 결과를 보존하고 처리 여부를 확인한 뒤 재개하세요.")
    # 통째로 받았을 때와 같은 새 값으로 푼다(JSON 으로 받은 값과 같은 모양 · 서로 공유하지 않는다).
    return json.loads(data.decode("utf-8", "surrogatepass"))


def _blob_resolve(container, local, name, skip=()):
    """최상위 칸·사전 칸의 자식 자리의 표지를 푼다(서버 `volcano_blob.shape` 가 바꾸는 자리).

    ★응답 최상위를 풀 때는 `next_payload` 를 건너뛴다(`skip`) — 그 칸은 따로, 최상위 값을 사본에 더한 뒤
      푼다. 2026-09-27 사고: 건너뛰지 않아 `next_payload` 의 칸 표지를 «사전 칸의 자식» 으로 보고 이번 요청
      사본만으로 풀다 멈췄다(7,558건 · 471명).
    """
    if not isinstance(container, dict):
        return container
    out = None
    for key, value in container.items():
        if not _blob_eligible(key) or key in skip:
            continue
        if _blob_is_marker(value):
            out = dict(container) if out is None else out
            out[key] = _blob_take(local, value["sha"], name)
        elif isinstance(value, dict) and any(_blob_is_marker(child) for child in value.values()):
            out = dict(container) if out is None else out
            out[key] = {sub: (_blob_take(local, child["sha"], name) if _blob_is_marker(child) else child)
                        for sub, child in value.items()}
    return container if out is None else out


def _blob_resolve_result(res, local, name):
    """응답 최상위·next_payload·반려 계약의 next_payload 에서 표지를 푼다."""
    if not isinstance(res, dict):
        return res
    sc = res.get("structuredContent")
    if isinstance(sc, dict):
        sc = _blob_resolve(sc, local, name, skip=("next_payload",))
        if isinstance(sc.get("next_payload"), dict):
            # 서버(`volcano_blob.shape`)는 next_payload 에서 **최상위에 통째로 보낸 값**도 표지로 가리킨다 —
            # 최상위를 먼저 풀고 그 값들을 사본에 더한 뒤 푼다(같은 순서).
            local = dict(local)
            for _p, _v, data in _blob_units(sc, skip=("next_payload",)):
                local.setdefault(_blob_digest(data), data)
            sc = dict(sc, next_payload=_blob_resolve(sc["next_payload"], local, name))
        res = dict(res, structuredContent=sc)
    meta = res.get("_meta")
    if isinstance(meta, dict) and isinstance(meta.get("contract"), dict) \
            and isinstance(meta["contract"].get("next_payload"), dict):
        contract = dict(meta["contract"], next_payload=_blob_resolve(meta["contract"]["next_payload"], local, name))
        res = dict(res, _meta=dict(meta, contract=contract))
    return res


def _blob_learn(res, workdir):
    """서버가 **실제로 둔** 지문(`_meta.blob_stored`)만 «서버가 가진 값» 으로 적는다.

    통째로 보낸 값이라도 서버가 못 뒀으면 적지 않는다 — 다음 요청도 통째로 간다(되묻기 한 번을 아낀다).
    """
    meta = res.get("_meta") if isinstance(res, dict) else None
    stored = meta.get("blob_stored") if isinstance(meta, dict) else None
    if isinstance(stored, list) and stored:
        _blob_remember(workdir, add=[sha for sha in stored if isinstance(sha, str)])


def _blob_caps_seen(workdir, meta):
    """서버가 알린 `blob_version` 을 **그대로** 적는다 — 내려가기도 한다(옛 판으로 되돌린 서버에는 표지를 안 보낸다).

    다른 능력(참조·묶음)은 «내리지 않는다» 가 규칙이지만, 표지는 옛 서버가 못 풀어 반려가 되므로
    능력 선언(`focus_ref_version` 이 든 `_meta`)에 `blob_version` 이 없으면 0 으로 적는다.
    """
    if not isinstance(meta, dict) or type(meta.get("focus_ref_version")) is not int:
        return
    value = meta.get("blob_version")
    value = value if type(value) is int else 0
    os.environ[_BLOB_FLAG] = str(value)
    path = _caps_path(workdir)
    if not path:
        return
    caps = _read_caps(path)
    # 적힌 값이 없는데 0 이면 적을 것이 없다(내릴 값이 없다) — 옛 서버의 능력 파일은 그대로 둔다.
    if caps.get("blob_version", 0) == value:
        return
    caps["blob_version"] = value
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(caps, fh)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


class _PackCollision(ValueError):
    """Real data used a reserved pack key; the payload is sent unpacked."""


def _pack_marker(value):
    """Exact marker shapes pass through unchanged (a checkpoint may already be packed)."""
    if not isinstance(value, dict):
        return False
    keys = set(value)
    if keys == {'_np', 'v'}:
        return type(value['_np']) is int and 1 <= value['_np'] <= 4 and isinstance(value['v'], str)
    if keys == {'_c1', 'v'}:
        return type(value['_c1']) is int and value['_c1'] >= 0 and not isinstance(value['v'], (dict, list))
    if keys == {'_cols', '_rows'}:
        return isinstance(value['_cols'], list) and isinstance(value['_rows'], list)
    return False


def _num_depth(value):
    """Depth of a non-empty, uniformly nested list whose leaves are all int/float (never bool)."""
    if not isinstance(value, list) or not value:
        return None
    if all(type(item) in (int, float) for item in value):
        return 1
    if all(isinstance(item, list) for item in value):
        # Empty inner lists fit any depth: '' is an empty depth-1 leaf, '~' an empty deeper list.
        depths = {_num_depth(item) for item in value if item}
        if None in depths or len(depths) > 1:
            return None
        depth = depths.pop() if depths else 1
        return depth + 1 if depth < 4 else None
    return None


def _struct_tokens(value):
    if isinstance(value, list):
        return 2 + max(0, len(value) - 1) + sum(_struct_tokens(item) for item in value)
    return 0


def _np_encode(value, depth):
    if depth == 1:
        return ' '.join(repr(item) for item in value)
    if not value:
        return '~'                      # an empty list below the top level ('' would mean [[]])
    return _PACK_SEPS[depth - 1].join(_np_encode(item, depth - 1) for item in value)


def _num_parse(text):
    return float(text) if any(c in text for c in '.eEin') else int(text)


def _np_decode(text, depth):
    if depth == 1:
        return [_num_parse(part) for part in text.split(' ')] if text else []
    if text == '~':
        return []
    return [_np_decode(part, depth - 1) for part in text.split(_PACK_SEPS[depth - 1])]


def _const_column(value):
    if not isinstance(value, list) or len(value) < 8 or isinstance(value[0], (list, dict)):
        return False
    first = value[0]
    return all(type(item) is type(first)
               and (repr(item) == repr(first) if isinstance(item, float) else item == first)
               for item in value)


def _focus_pack(value):
    """Lossless structural fold of measurement rows; `_focus_unpack` is its exact inverse."""
    if isinstance(value, dict):
        if _pack_marker(value):
            return value
        if any(key in _PACK_KEYS for key in value):
            raise _PackCollision(str(sorted(set(value) & _PACK_KEYS)))
        return {key: _focus_pack(item) for key, item in value.items()}
    if isinstance(value, list):
        depth = _num_depth(value)
        if depth and _struct_tokens(value) >= 12:
            return {'_np': depth, 'v': _np_encode(value, depth)}
        if _const_column(value):
            return {'_c1': len(value), 'v': value[0]}
        if len(value) >= 3 and all(isinstance(item, dict) for item in value):
            keys = tuple(value[0])
            if keys and all(tuple(item) == keys for item in value) and not _pack_marker(value[0]):
                if any(key in _PACK_KEYS for key in keys):
                    raise _PackCollision(str(sorted(set(keys) & _PACK_KEYS)))
                return {'_cols': list(keys), '_rows': [_focus_pack([item[key] for item in value]) for key in keys]}
        return [_focus_pack(item) for item in value]
    return value


def _focus_unpack(value, depth=0):
    """Server-identical inverse (kept here so a resumed checkpoint can be read locally)."""
    if depth > 96:
        raise ValueError('pack nesting')
    if isinstance(value, dict):
        keys = set(value)
        if keys & _PACK_KEYS:
            if keys == {'_np', 'v'} and _pack_marker(value):
                return _np_decode(value['v'], value['_np'])
            if keys == {'_c1', 'v'} and _pack_marker(value):
                return [value['v']] * value['_c1']
            if keys == {'_cols', '_rows'}:
                cols, rows = value['_cols'], value['_rows']
                if (not isinstance(cols, list) or not cols or any(type(key) is not str for key in cols)
                        or len(set(cols)) != len(cols) or not isinstance(rows, list) or len(rows) != len(cols)):
                    raise ValueError('pack columns')
                columns = [_focus_unpack(row, depth + 1) for row in rows]
                if any(not isinstance(col, list) for col in columns) or len({len(col) for col in columns}) != 1:
                    raise ValueError('pack column length')
                return [dict(zip(cols, vals)) for vals in zip(*columns)]
            raise ValueError('pack marker')
        return {key: _focus_unpack(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [_focus_unpack(item, depth + 1) for item in value]
    return value


def _pack_focus_fields(payload):
    """Pack the three measurement fields once the server said it restores pack v1."""
    if _focus_pack_version() < 1 or not isinstance(payload, dict):
        return payload
    fields = [field for field in ('frames', 'focus_frames', 'focus_measurements')
              if isinstance(payload.get(field), (dict, list))]
    if not fields:
        return payload
    try:
        packed = {field: _focus_pack(payload[field]) for field in fields}
    except _PackCollision:
        return payload
    return dict(payload, _focus_pack=1, **packed)


def _focus_ref_version():
    """The server advertises the newest reference version it restores (`_meta`).

    Kept in the environment, not a module global: self-update reloads modules
    but must not forget what the server said. Default 2 = the older contract.
    """
    try:
        return max(2, int(os.environ.get(_FOCUS_REF_FLAG, "2")))
    except ValueError:
        return 2


def _focus_patch(new, old):
    """Field-level delta of one row against its measured row (reference v3).

    Rows the server judged are never byte-identical to their measurement, so
    v2 shipped them whole (~13k structure tokens each) and 30+ cuts hit the
    server's 400,000-token request limit (HTTP 413). Same shape as the server.
    """
    if isinstance(new, dict) and isinstance(old, dict):
        patch = {}
        changed = {k: _focus_patch(v, old[k]) for k, v in new.items()
                   if k in old and not _same_focus_value(v, old[k])}
        added = {k: v for k, v in new.items() if k not in old}
        removed = [k for k in old if k not in new]
        if changed:
            patch['~'] = changed
        if added:
            patch['+'] = added
        if removed:
            patch['-'] = removed
        return patch
    return {'=': new}


_FOCUS_PATCH_KEYS = frozenset(('=', '~', '+', '-'))


def _focus_apply(old, patch):
    """Restore a v3 row (server-identical rules). Raises ValueError on a forbidden shape."""
    if not isinstance(patch, dict) or not patch or not set(patch) <= _FOCUS_PATCH_KEYS:
        raise ValueError('focus patch shape')
    if '=' in patch:
        if set(patch) != {'='}:
            raise ValueError('focus patch replace')
        return patch['=']
    if not isinstance(old, dict):
        raise ValueError('focus patch base')
    out = dict(old)
    removed = patch.get('-', [])
    added = patch.get('+', {})
    changed = patch.get('~', {})
    if (not isinstance(removed, list) or any(type(k) is not str or k not in old for k in removed)
            or len(removed) != len(set(removed))
            or not isinstance(added, dict) or any(type(k) is not str or k in old for k in added)
            or not isinstance(changed, dict) or any(type(k) is not str or k not in old or k in removed for k in changed)):
        raise ValueError('focus patch keys')
    for k in removed:
        del out[k]
    for k, v in added.items():
        out[k] = v
    for k, sub in changed.items():
        out[k] = _focus_apply(old[k], sub)
    return out


def _unfold_focus_alias(payload, field):
    """Inverse of `_fold_focus_alias` for a checkpoint read back from disk."""
    frames, measured = payload.get(field), payload.get('focus_measurements')
    if not isinstance(frames, dict) or not any(k in frames for k in ('_focus_ref', '_focus_delta')):
        return payload
    ref = frames.get('_focus_ref')
    if (not isinstance(ref, dict) or ref.get('field') != 'focus_measurements'
            or not isinstance(measured, dict)):
        raise StepError(f"{field}: 저장된 측정 참조를 되돌릴 수 없습니다 — focus_measurements 가 함께 저장돼 있지 않습니다. "
                        "저장 상태가 손상됐으니 마지막으로 성공한 next_payload.json 으로 재개하세요.")
    version, keys, delta = ref.get('version'), ref.get('keys'), frames.get('_focus_delta') or {}
    if version == 1:
        return dict(payload, **{field: measured})
    if version not in (2, 3) or not isinstance(keys, list) or not isinstance(delta, dict):
        raise StepError(f"{field}: 저장된 측정 참조의 판({version!r})을 모릅니다 — 실행기 팩을 새로 받으세요.")
    rows = {}
    for key in keys:
        if key in delta:
            try:
                rows[key] = _focus_apply(measured.get(key), delta[key]) if version == 3 else delta[key]
            except ValueError as exc:
                raise StepError(f"{field}: 저장된 측정 참조의 컷 {key} 패치를 되돌릴 수 없습니다 ({exc})") from exc
        elif key in measured:
            rows[key] = measured[key]
        else:
            raise StepError(f"{field}: 저장된 참조의 컷 {key} 가 focus_measurements 에 없습니다 — 저장 상태가 손상됐다")
    return dict(payload, **{field: rows})


def _unfold_focus_recovery(payload):
    if not isinstance(payload,dict) or '_focus_recovery_pack' not in payload:return payload
    if type(payload['_focus_recovery_pack']) is not int or payload['_focus_recovery_pack']!=1:
        raise StepError('저장된 검수 복구 묶음 버전을 확인할 수 없습니다. 원본을 보존하세요.')
    recovery=payload.get('focus_recovery')
    if not isinstance(recovery,dict) or not isinstance(recovery.get('unrepaired_frames'),dict):
        raise StepError('저장된 검수 복구 원문이 올바르지 않습니다. 원본을 보존하세요.')
    try:held=_focus_unpack(recovery['unrepaired_frames'])
    except (ValueError,TypeError) as exc:raise StepError('저장된 검수 복구 원문을 되돌릴 수 없습니다.') from exc
    return dict({k:v for k,v in payload.items() if k!='_focus_recovery_pack'},
                focus_recovery=dict(recovery,unrepaired_frames=held))


def _pack_focus_recovery(payload,caps):
    # Called only with a fresh, successful capability response for this RPC.
    # A persisted capability or our own request header cannot authorize it.
    if caps.get('focus_recovery_pack_version')!=1 or type(caps.get('focus_recovery_pack_version')) is not int:return payload
    recovery=payload.get('focus_recovery')
    if not isinstance(recovery,dict) or not isinstance(recovery.get('unrepaired_frames'),dict):return payload
    try:held=_focus_pack(recovery['unrepaired_frames'])
    except _PackCollision:return payload
    return dict(payload,_focus_recovery_pack=1,focus_recovery=dict(recovery,unrepaired_frames=held))


def unfold_payload(payload):
    """Read a checkpoint back into the shape `fold_payload` started from.

    ★왜 (2026-09-12 실측): 재개 상태는 접힌 채로 저장된다(작게 저장하려고). 그것을 접힌 채로
      메모리에 두면, 그 뒤 서버 응답의 carry 가 `focus_measurements` 를 새 판(컷이 빠지거나
      판정이 바뀐 것)으로 갈아 끼우는 순간 `focus_frames` 의 참조는 **옛 판**을 가리키고, 보내기
      직전의 `fold_payload` 는 이미 접힌 칸을 그대로 두므로 서버가 «측정 참조가 올바르지 않습니다»
      로 반려한다 — 한 사람이 34분에 45번, 배포 전 24시간 227회·78명. 잃어버린 정보는 되돌릴 수
      없으므로 **읽는 순간**(measured 가 아직 같은 판일 때) 되돌리고, 접기는 보낼 때만 한다.
    """
    if not isinstance(payload, dict):
        return payload
    if payload.get('_focus_pack') == 1:
        out = {k: v for k, v in payload.items() if k != '_focus_pack'}
        for field in ('frames', 'focus_frames', 'focus_measurements'):
            if field in out:
                try:
                    out[field] = _focus_unpack(out[field])
                except (ValueError, TypeError) as exc:
                    raise StepError(f"{field}: 저장된 묶음(pack)을 되돌릴 수 없습니다 ({exc}) — 저장 상태가 손상됐다") from exc
        payload = out
    payload = _unfold_focus_recovery(payload)
    for field in ('frames', 'focus_frames'):
        payload = _unfold_focus_alias(payload, field)
    return payload


def _focus_reference_below(value):
    """The row-reference protocol never follows another reference inside data."""
    if isinstance(value, dict):
        return any(key in ('_focus_ref', '_focus_delta') or _focus_reference_below(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_focus_reference_below(item) for item in value)
    return False


def _fold_focus_frames(payload):
    """Keep canonical rows once in both rendering and submitted-result aliases."""
    for field in ('frames', 'focus_frames'):
        payload = _fold_focus_alias(payload, field)
    return payload


def _fold_focus_alias(payload, field):
    """Preserve alias membership/order and every distinct submitted measurement."""
    if not isinstance(payload, dict):
        return payload
    frames, measured = payload.get(field), payload.get('focus_measurements')
    if (not isinstance(frames, dict) or not isinstance(measured, dict) or not frames or not measured
            or any(type(key) is not str for key in frames)
            or any(type(key) is not str for key in measured)
            or any(key in frames or key in measured for key in ('_focus_ref', '_focus_delta'))):
        return payload
    if list(frames) == list(measured) and _same_focus_value(frames, measured):
        return dict(payload, **{field: {'_focus_ref': {'version': 1, 'field': 'focus_measurements'}}})
    if _focus_reference_below(frames) or _focus_reference_below(measured):
        return payload
    if _focus_ref_version() >= 3:
        if not any(key in measured for key in frames):
            return payload
        delta = {}
        for key, row in frames.items():
            if key in measured:
                if _same_focus_value(row, measured[key]):
                    continue
                delta[key] = _focus_patch(row, measured[key])
            else:
                delta[key] = {'=': row}
        return dict(payload, **{field: {
            '_focus_ref': {'version': 3, 'field': 'focus_measurements', 'keys': list(frames)},
            '_focus_delta': delta}})
    delta = {}
    shared = False
    for key, row in frames.items():
        if key in measured and _same_focus_value(row, measured[key]):
            shared = True
        else:
            delta[key] = row
    if not shared:
        return payload
    return dict(payload, **{field: {
        '_focus_ref': {'version': 2, 'field': 'focus_measurements', 'keys': list(frames)},
        '_focus_delta': delta}})


def fold_payload(payload):
    """보내기 **직전에** 무거운 옛 모양을 가벼운 새 모양으로 접는다.

    ■ 왜 (2026-08-17, 실물 여러 명이 여기서 통째로 막혔다)
        서버는 이제 컷마다 **숫자 두 개**(`still`·`jump`)만 받는다. 그런데 **옛
        실행기가 만들어 둔 `next_payload.json`** 에는 프레임 벡터가 그대로 들어 있다.
        그 파일을 다시 보내면 요청이 **3MB** 가 되고, 그러면 이런 일이 벌어진다:
          · MCP 도구로는 못 실린다(실측: MCP 경로 최대 108,340B)
          · 그래서 모델이 **직접 HTTP** 로 보내려 하고, 거기엔 Bearer 토큰이 필요하다
          · 수강생은 토큰이 없다(정상 경로에는 필요가 없다) → **401 · 여기서 끝난다**
        실측(2026-08-17 22:33 vs 22:48, 같은 팩): 3,456,425B ↔ **91,923B**.

    ■ 왜 여기인가 — **모든 길이 이 문을 지난다**
        모델이 손으로 쓴 스크립트도(`finish.py` 같은 것) 서버를 부를 때는 이 `step`
        을 쓴다. 그래서 여기 한 곳에서 접으면 **다시 재지 않고** 낫는다 —
        수강생은 아무것도 안 해도 된다.
    ★값을 **버리지 않는다.** 벡터를 서버가 쓰던 그 관계(`_sig_cor`)로 접으므로
      판정 결과가 같다. 못 접는 모양(모르는 칸)은 **그대로 보낸다** — 접는 자가
      판정을 바꾸면 안 된다.
    """
    if not isinstance(payload, dict):
        return payload
    # Recovery can change one row while all other rows remain canonical. The
    # explicit reference keeps their order and carries every distinct new row.
    payload = _fold_focus_frames(payload)
    payload = _pack_focus_fields(payload)
    # ★shot_scan 원시(card→{a,b,m 벡터})도 여기서 접는다 (2026-08-24) —
    #   46샷 ≈4.2MB 가 그대로 나가면 워커·MCP 어느 길로도 못 간다.
    #   접힌 것(_fold)·이웃접기({still,jump})·모르는 모양은 그대로 둔다.
    ss = payload.get("shot_scan")
    if (isinstance(ss, dict) and ss and "_fold" not in ss
            and any(isinstance(v, dict) and ("m" in v or "a" in v)
                    and "still" not in v for v in ss.values())):
        payload = dict(payload, shot_scan=fold_scan_corr64(ss, list(ss)))
    cs = payload.get("cut_sigs")
    if not isinstance(cs, dict) or not cs:
        return payload
    # ★★`jump` 는 **이웃 컷끼리**다 — 컷 안에서 계산하면 안 된다.
    #   서버가 벡터를 받았을 때 하던 것: `still = cor(a, b)`(같은 컷의 두 시각) ·
    #   `jump = cor(앞컷 m, 이 컷 m)`(컷 경계). 처음 컷의 `jump` 는 없다(이웃이 없다).
    #   ★한 글자 차이로 판정이 조용히 달라진다 — 첫 판을 `cor(m, a)` 로 썼다가
    #     서버 코드를 읽고 잡았다(§4 "옮겨 적을 때 호출부까지 읽어라").
    def _key(k):
        try:
            return (0, int(k))
        except (TypeError, ValueError):
            return (1, 0)

    order = sorted(cs, key=_key)
    out, folded, prev_m = {}, 0, None
    for k in order:
        v = cs[k]
        if isinstance(v, dict) and ("a" in v or "m" in v) and "still" not in v:
            a, b2, m = v.get("a"), v.get("b"), v.get("m")
            ok = isinstance(m, list) and isinstance(prev_m, list)
            out[k] = {
                "still": (_sig_cor(a, b2)
                          if isinstance(a, list) and isinstance(b2, list) else None),
                "jump": (_sig_cor(prev_m, m) if ok else None),
            }
            folded += 1
            prev_m = m if isinstance(m, list) else None
        else:
            out[k] = v
            # 새 모양이면 `m` 이 없다 — 다음 컷의 `jump` 는 그 값이 이미 들어 있다.
            prev_m = None
    if not folded:
        return payload
    _progress(f"  [접기] cut_sigs {folded}개를 옛 모양(프레임 벡터)에서 숫자 두 개로 접었다 "
          f"— 옛 실행기가 만든 payload 다. 다시 재지 않는다")
    new = dict(payload)
    new["cut_sigs"] = out
    return new


def _review_wire_summary(value, replies, *, allow_pending=False):
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value.get("prompt"), str) or not isinstance(value.get("images"), (list, dict))
            or not isinstance(value.get("reply_schema"), dict) or not isinstance(value.get("request_sha256"), str)
            or not _BLOB_SHA.fullmatch(value["request_sha256"]) or not isinstance(replies, dict)):
        return None
    reply = replies.get(value["request_sha256"])
    rejected = value.get("reply_error") or {}
    if (reply is None and not allow_pending) or not isinstance(rejected, dict):
        return None
    fingerprint = rejected.get("submitted_reply_sha256")
    if fingerprint:
        if not isinstance(fingerprint, str) or not _BLOB_SHA.fullmatch(fingerprint):
            return None
        if not allow_pending and fingerprint == hashlib.sha256(json.dumps(reply, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False).encode()).hexdigest():
            return None
    summary = {"request_sha256": value["request_sha256"]}
    if fingerprint:summary["reply_error"] = {"submitted_reply_sha256": fingerprint}
    return summary


def _restore_review_evidence(value, local):
    """Rehydrate this call's originals with depth-bounded traversal and COW.

    No fetch or replay is permitted after a tool may have run. Each occurrence
    gets its own mutable copy, even when two references share a SHA.
    """
    def restore(item):
        ref = item["_review_evidence_ref"]
        saved = local.get(ref.get("sha")) if isinstance(ref, dict) else None
        if (not saved or type(ref.get("version")) is not int or type(ref.get("packed")) is not bool
                or ref != {"version": 1, "sha": ref.get("sha"), "packed": saved["packed"]}
                or item != dict(saved["summary"], _review_evidence_ref=ref)
                or _blob_digest(_blob_encode(saved["value"])) != ref["sha"]):
            raise StepError("응답의 검수 원문 참조를 확인하지 못했습니다. 단계가 실행됐을 수 있어 자동 재전송하지 않습니다. 원문과 접수 기록을 보존하세요.")
        return _focus_unpack(saved["value"]) if saved["packed"] else copy.deepcopy(saved["value"])
    if isinstance(value, dict) and "_review_evidence_ref" in value:
        return restore(value)
    if not isinstance(value, (dict, list)):
        return value
    def frame(item, parent=None, key=None):
        return [item, iter(item.items() if isinstance(item, dict) else enumerate(item)), {}, parent, key]
    stack = [frame(value)]
    while stack:
        current = stack[-1]
        item, iterator, updates, parent, parent_key = current
        try:
            key, child = next(iterator)
        except StopIteration:
            stack.pop()
            out = item.copy() if updates else item
            for key, child in updates.items():out[key] = child
            if parent is None:return out
            if out is not item:parent[2][parent_key] = out
            continue
        if isinstance(child, dict) and "_review_evidence_ref" in child:
            updates[key] = restore(child)
        elif isinstance(child, (dict, list)):
            stack.append(frame(child, current, key))
    return value


def _longform_project_object(value):
    """Match server JSON-object transport acceptance without rewriting originals."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return False
    return isinstance(value, dict)


class Client:
    """서버의 MCP 도구를 부르는 자리.

    ■ ★어느 **도구**를 부르는지 (2026-09-04 신설)
        예전에는 JSON-RPC 본문의 `params.name` 에 `"volcano_video"` 가 **박혀** 있었다.
        그래서 이 팩에 `ref_*` 실행 함수가 20개나 들어 있는데도 조교 계측 도구
        `volcano_ref` 를 **시킬 문이 없었다** — 그 체인은 사람이 15단계를 손으로 이어
        부르는 길 하나뿐이었고, 계약이 한 칸 빠지면 그대로 사고가 됐다.
        ★**기본값은 `volcano_video` 다.** 수강생 480명 경로는 한 글자도 안 바뀐다 —
          `tool` 을 안 주면 예전과 **바이트가 같은 본문**이 나간다
          (`tests/test_ref_runner_tool.py` 가 매번 잰다 — 대조군·자가시험 포함).
        · 클라이언트 단위로 고정: `Client(url, token, tool="volcano_ref")`
        · 한 호출만 다른 도구로:   `c.step("feedback", …, tool="volcano_video")`
        ★클래스 속성으로도 둔다 — 자기 갱신(`self_update`)은 **옛 `__init__` 이 만든
          객체**의 `__class__` 만 새 클래스로 갈아끼우므로 인스턴스에 `tool` 칸이
          없을 수 있다. 그때도 예전과 같은 `volcano_video` 로 간다.
    """

    #: 부를 도구 이름의 기본값. **바꾸지 마라** — 수강생 전원의 경로다.
    tool = "volcano_video"

    def __init__(self, url, token, preset="뇌전구", timeout=120, tool=None):
        self.url, self.token, self.preset, self.timeout = url, token, preset, timeout
        # ★`or` 로 falsy 를 삼키지 않는다: 빈 글자를 주면 «도구 없음» 이라 조용히
        #   기본값으로 새는 대신 여기서 막는다(§"0 과 «없음» 을 가르라" 와 같은 부류).
        if tool is not None and not (isinstance(tool, str) and tool.strip()):
            raise StepError("Client(tool=…) 은 도구 이름 글자여야 한다 "
                            "(안 주면 기본 'volcano_video')")
        self.tool = tool.strip() if isinstance(tool, str) and tool.strip() else type(self).tool
        self._id = 0

    def _rpc_wait(self):
        # Server caps mirror volcano_admin.check_rate's fixed minute window.
        # Counting completion times in a rolling window is conservative: earlier
        # uploads remain counted when preparation starts. No retry is introduced.
        limit=getattr(self,'_rpc_limit',None)
        window=getattr(self,'_rpc_window',None)
        if limit is None:return
        while True:
            now=time.monotonic()
            recent=[stamp for stamp in getattr(self,'_rpc_completed',[]) if now-stamp<window]
            self._rpc_completed=recent
            if len(recent)<limit:return
            time.sleep(max(0,recent[-limit]+window-now))

    def _rpc_record(self):
        now=time.monotonic()
        self._rpc_completed=[stamp for stamp in getattr(self,'_rpc_completed',[]) if now-stamp<60]
        self._rpc_completed.append(now)

    def _wire_rpc(self, params):
        """Idempotent cache traffic only; never invokes a production/paid step."""
        if getattr(self, '_receipt_execution_refused', False):
            raise StepError('서비스 거부로 이 실행의 모든 추가 요청을 중지했습니다.')
        self._id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": _WIRE_METHOD,
                           "params": params}, ensure_ascii=False).encode()
        if len(body) > _WIRE_REQUEST_BYTES:
            raise StepError("증거 조각 요청이 서버 전송 한도를 넘습니다. 원본을 보존하세요.")
        req = urllib.request.Request(self.url, data=body, headers={
            "Authorization": f"Bearer {self.token}", "content-type": "application/json",
            "MCP-Protocol-Version": "2025-11-25", "User-Agent": _UA,
            "X-Volcano-Runner-Caps": _BLOB_CAPS})
        # ★멱등 전송이다(caps·focus_status 는 읽기 · put/put_many 는 내용 주소 · focus_prepare 는 지문별 멱등)
        #   → `_open_retry` 의 기본 길(3회·1초/2초·1102 제외·4xx 즉시)로 다시 던진다 (2026-10-05 · 원장 W2-03).
        #   10-02 에 단발로 바꾼 뒤 caps 500 한 번에 작업이 멈췄다(10-04 1,419건·217명 · 배포 뒤 31건·23명).
        #   401/403/429 는 지금처럼 그 실행의 모든 요청을 멈춘다(전역 규칙 6-2). 요청 간격(`_rpc_wait`)은 그대로다.
        self._rpc_wait()
        try:
            reply = _wire_fetch(req, self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 429):
                self._receipt_execution_refused = True
            detail = "Cloudflare 계산 한도 초과(error code 1102)" if _limit_exceeded(exc) else f"HTTP {exc.code}"
            # 다시 보낸 것은 5xx(1102 제외)뿐이다 — `_open_retry` 와 같은 판정으로 말한다.
            resent = exc.code >= 500 and not _limit_exceeded(exc)
            raise StepError(
                f"서버 전송 규격·증거 요청({params.get('op', 'unknown')})이 {detail}로 중단되었습니다. "
                + ("일시적 실패라 같은 요청을 세 번 보냈지만 모두 실패했습니다. " if resent else "같은 요청을 다시 보내지 않았습니다. ")
                + "이 오류만으로 제작 요청의 접수·완료 여부는 판단할 수 없습니다. "
                "기존 원본, 체크포인트, 검수 증거와 유료 접수 기록을 보존하세요.") from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            resent = isinstance(exc, (OSError, http.client.HTTPException))   # `_wire_fetch` 가 세 번 보냈다
            raise StepError(
                f"서버 전송 규격·증거 요청({params.get('op', 'unknown')})의 응답을 끝까지 확인하지 못했습니다. "
                + ("같은 요청을 세 번 보냈지만 모두 실패했습니다. " if resent else "같은 요청을 다시 보내지 않았습니다. ")
                + "이 오류만으로 제작 요청의 접수·완료 여부는 판단할 수 없습니다. "
                "기존 원본, 체크포인트, 검수 증거와 유료 접수 기록을 보존하세요.") from exc
        finally:
            self._rpc_record()
        if isinstance(reply, dict) and isinstance(reply.get("error"), dict):
            detail = str(reply["error"].get("message") or "전송 거부")[:500]
            raise StepError(f"증거 전송이 중단되었습니다: {detail} 단계는 실행하지 않았습니다. 원본과 현재 상태를 보존하세요.")
        if not isinstance(reply, dict) or not isinstance(reply.get("result"), dict):
            raise StepError("서버 분할 전송 응답을 확인하지 못했습니다. 단계는 실행하지 않았습니다. 증거와 현재 상태를 보존하세요.")
        result=reply["result"]
        if params.get('op')=='caps':
            limit,window=result.get('request_limit'),result.get('request_window_seconds')
            if type(limit) is int and limit>0 and type(window) is int and window==60:
                self._rpc_limit,self._rpc_window=limit,window
        return result

    def _wire_prepare(self, args, tool_name, review_local=None, prepare_focus=None):
        """Move exact folded JSON values to cache, not summaries or paid jobs."""
        caps = self._wire_rpc({"op": "caps"})
        limit, unit_limit, chunk = (caps.get(key) for key in
                                   ("max_request_bytes", "max_unit_bytes", "chunk_bytes"))
        if (caps.get("wire_blob_version") != 1 or
                any(type(v) is not int or v <= 0 for v in (limit, unit_limit, chunk)) or
                limit > _WIRE_REQUEST_BYTES or unit_limit > 16 * 1024 * 1024 or chunk > limit // 4):
            raise StepError("서버 분할 전송 규격을 확인하지 못했습니다. 원본을 보존하세요.")
        restored_limit = caps.get("max_restored_bytes")
        if type(restored_limit) is not int or restored_limit <= 0:
            raise StepError("서버 복원 메모리 규격을 확인하지 못했습니다. 원본을 보존하세요.")
        value = args.get("payload")
        if not isinstance(value, dict):
            raise StepError("대용량 payload는 객체여야 합니다. 원본을 보존하세요.")
        candidates = []
        template = dict(value)
        review_paths = set()
        focus_uploads = []
        # Fresh capability authorizes per-cut original handles, never a larger
        # whole-request restore. Other routes and servers keep the wire limit.
        focus_originals = (type(caps.get("focus_original_ref_version")) is int
            and caps["focus_original_ref_version"] == 1 and tool_name == "volcano_video"
            and args.get("preset") == "인물형 롱폼" and args.get("step") == "longform_seed"
            and ("_focus_pack" not in value or type(value["_focus_pack"]) is int and value["_focus_pack"] == 1))
        if focus_originals:
            def original_rows(rows):
                if not isinstance(rows, dict) or "_focus_ref" in rows or _blob_is_marker(rows):return rows
                changed = None
                for cut, row in rows.items():
                    if not isinstance(cut, str) or not isinstance(row, dict) or _blob_is_marker(row):continue
                    data = _blob_encode(row)
                    if not _BLOB_MIN_BYTES <= len(data) <= unit_limit or _request_structure_exceeds_limit(data):continue
                    sha = _blob_digest(data)
                    if changed is None:changed = dict(rows)
                    changed[cut] = {"_blob": 1, "sha": sha}
                    focus_uploads.append((sha, data))
                return rows if changed is None else changed
            for field in ("frames", "focus_frames", "focus_measurements"):
                if field in template:template[field] = original_rows(template[field])
            recovery = template.get("focus_recovery")
            if isinstance(recovery, dict) and "unrepaired_frames" in recovery:
                held = original_rows(recovery["unrepaired_frames"])
                if held is not recovery["unrepaired_frames"]:
                    template["focus_recovery"] = dict(recovery, unrepaired_frames=held)
        # Retain only per-cut handles before transport placeholders hide them.
        # Include handles just created above; their uploads finish before the
        # preparation callback. Original evidence stays in the normal stores.
        focus_handles = {}
        if prepare_focus is not None:
            for field in ("frames", "focus_frames", "focus_measurements"):
                rows = template.get(field)
                if isinstance(rows, dict) and not _blob_is_marker(rows):
                    focus_handles[field] = {cut: row for cut, row in rows.items()
                                            if _blob_is_marker(row)}
        if caps.get("review_evidence_ref_version") == 1 and review_local is not None:
            rows, replies = template.get("focus_frames"), value.get("focus_review_replies")
            if isinstance(rows, dict) and isinstance(replies, dict):
                rows = dict(rows)
                template["focus_frames"] = rows
                for cut, row in list(rows.items()):
                    if not isinstance(row, dict) or row.get("focus_status") != "pending" or not isinstance(row.get("review_requests"), list):
                        continue
                    selected = list(row["review_requests"])
                    for index, request in enumerate(selected):
                        summary = _review_wire_summary(request, replies,
                            allow_pending=caps.get("pending_review_evidence_ref_version") == 1)
                        if summary is None:continue
                        data = _blob_encode(request)
                        if not _BLOB_MIN_BYTES <= len(data) <= unit_limit or _request_structure_exceeds_limit(data):continue
                        target = ("focus_frames", cut, "review_requests", index)
                        sha = _blob_digest(data)
                        review_local[sha] = {"value": request, "packed": value.get("_focus_pack") == 1, "summary": summary}
                        review_paths.add(target);candidates.append((list(target), data));selected[index] = None
                    if selected != row["review_requests"]:
                        rows[cut] = dict(row, review_requests=selected)
        def collect(item, path):
            if tuple(path) in review_paths:
                return
            data = _blob_encode(item)
            contains_projection = any(p[:len(path)] == tuple(path) for p in review_paths)
            # ★단위는 바이트(unit_limit)만이 아니라 서버 `entry._check_json_structure` 의 구조 토큰 상한
            #   (REQUEST_TOKEN_LIMIT)도 지켜야 한다 — 서버가 단위마다 그 자로 검사한다(volcano_blob.wire_ingest).
            #   2026-10-07 조교 3D쇼츠 axes: 숫자가 빽빽한 계측값이 1.45MB(<2MiB)인데 토큰 50만이라 put_many 가
            #   «blob 조각·지문·JSON 한도 검증에 실패» 로 매번 거부됐다. 넘으면 바이트가 작아도 더 쪼갠다.
            if len(data) <= unit_limit and not contains_projection and not _request_structure_exceeds_limit(data):
                if len(data) >= _BLOB_MIN_BYTES:
                    candidates.append((path, data))
                return
            if isinstance(item, dict):
                for key, child in item.items(): collect(child, path + [key])
            elif isinstance(item, list):
                for index, child in enumerate(item): collect(child, path + [index])
            else:
                raise StepError(f"하나의 검수 값 {len(data)} bytes(구조 토큰 상한 {REQUEST_TOKEN_LIMIT:,})가 단위 최대 {unit_limit} bytes를 넘습니다. 전체 복원 최대 {restored_limit} bytes. 증거를 줄이거나 지우지 말고 관리자에게 보고하세요.")
        for key, item in template.items(): collect(item, [key])
        candidates.sort(key=lambda pair: len(pair[1]), reverse=True)
        refs, uploads = [], list(focus_uploads)
        restored_sizes = []
        def encoded():
            envelope = {"_wire_blob": 1, "value": template, "blobs": refs} if refs else template
            return json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                "params": {"name": tool_name, "arguments": dict(args, payload=envelope)}},
                ensure_ascii=False).encode()
        for path, data in candidates:
            parent = template
            for key in path[:-1]:
                parent[key] = parent[key].copy()
                parent = parent[key]
            parent[path[-1]] = None
            sha = _blob_digest(data)
            projected = tuple(path) in review_paths
            refs.append(dict(path=path, sha=sha, **({"review": 1} if projected else {})))
            uploads.append((sha, data))
            projection = dict(review_local[sha]["summary"], _review_evidence_ref={"version": 1,
                "sha": sha, "packed": review_local[sha]["packed"]}) if projected else None
            restored_sizes.append(len(_blob_encode(projection)) if projected else len(data))
            # Once using transport blobs, remove every large unit: leaving a
            # nearly 16MiB inline body alive duplicates parsed Unicode evidence.
        if ((not refs and not focus_uploads) or len(encoded()) > min(limit, unit_limit)
                or _request_structure_exceeds_limit(encoded())):
            raise StepError(f"증거 인라인 {len(encoded())} bytes를 최대 {min(limit, unit_limit)} bytes에 맞게 나누지 못했습니다(전체 복원 최대 {restored_limit} bytes). 원본을 보존하세요. 단계는 실행하지 않았습니다.")
        if len(encoded()) + sum(restored_sizes) > restored_limit:
            raise StepError(f"증거 복원 {len(encoded()) + sum(restored_sizes)} bytes가 최대 {restored_limit} bytes를 넘습니다(단위 최대 {unit_limit} bytes). 원본을 줄이거나 지우지 말고 관리자에게 보고하세요.")
        batch_limit = caps.get("max_batch_bytes")
        batch_supported = caps.get("put_many_version") == 1
        if batch_supported and (type(batch_limit) is not int or
                not _BLOB_MIN_BYTES <= batch_limit <= min(unit_limit, limit // 4)):
            raise StepError("서버 묶음 전송 규격을 확인하지 못했습니다. 단계는 실행하지 않았습니다.")
        pending, pending_bytes = [], 0
        def flush_batch():
            if not pending:
                return
            saved = self._wire_rpc({"op": "put_many", "items": list(pending)})
            if saved.get("stored") != [item["sha"] for item in pending]:
                raise StepError("서버가 증거 묶음의 모든 저장 지문을 확인하지 못했습니다. 단계는 실행하지 않았습니다.")
            pending.clear()
        # Duplicate logical values need one cache write but retain every path.
        for sha, data in dict(uploads).items():
            if batch_supported and len(data) <= min(chunk, batch_limit):
                if pending_bytes + len(data) > batch_limit:
                    flush_batch(); pending_bytes = 0
                pending.append(dict(sha=sha,size=len(data),part=0,parts=1,
                    data=base64.b64encode(data).decode("ascii")))
                pending_bytes += len(data)
                continue
            flush_batch(); pending_bytes = 0
            parts = (len(data) + chunk - 1) // chunk
            for part in range(parts):
                saved = self._wire_rpc({"op": "put", "sha": sha, "size": len(data),
                    "part": part, "parts": parts,
                    "data": base64.b64encode(data[part*chunk:(part+1)*chunk]).decode("ascii")})
                if part != parts - 1 and saved.get("part") != part:
                    raise StepError("서버가 증거 조각 저장을 확인하지 못했습니다. 단계는 실행하지 않았습니다.")
                if part == parts - 1 and saved.get("stored") != sha:
                    raise StepError("서버가 증거 저장 지문을 확인하지 못했습니다. 단계는 실행하지 않았습니다.")
        flush_batch()
        if prepare_focus is not None:
            prepare_focus(dict(args, payload=focus_handles))
        return dict(args, payload={"_wire_blob": 1, "value": template, "blobs": refs} if refs else template)

    def _prepare_focus_derived(self,args,tool_name,local=None):
        if (tool_name!='volcano_video' or args.get('preset')!='인물형 롱폼'
                or args.get('step') not in ('longform_seed','longform_run')):return False
        value=args.get('payload')
        if isinstance(value,dict) and value.get('_wire_blob')==1:value=value.get('value')
        if not isinstance(value,dict):return False
        shas=[];seen=set()
        for field in ('frames','focus_frames','focus_measurements'):
            rows=value.get(field)
            if not isinstance(rows,dict) or _blob_is_marker(rows) or '_focus_ref' in rows:continue
            for row in rows.values():
                if _blob_is_marker(row) and row['sha'] not in seen:
                    shas.append(row['sha']);seen.add(row['sha'])
        if not shas:return False
        caps=self._wire_rpc({'op':'caps'})
        if caps.get('focus_derived_version')!=1:return False
        width=caps.get('focus_status_batch');missing=[]
        if type(width) is not int or width<=0:raise StepError('검수 원본 조회 규격을 확인하지 못했습니다. 제작 단계는 실행하지 않았습니다.')
        for offset in range(0,len(shas),width):
            batch=shas[offset:offset+width]
            status=self._wire_rpc({'op':'focus_status','shas':batch})
            absent=status.get('missing')
            if (status.get('focus_derived_version')!=1 or not isinstance(absent,list)
                    or any(not isinstance(sha,str) or sha not in batch for sha in absent)
                    or len(set(absent))!=len(absent)):
                raise StepError('검수 원본 조회 결과를 확인하지 못했습니다. 제작 단계는 실행하지 않았습니다.')
            missing.extend(absent)
        # One source per cache-only request. Existing _wire_rpc uses no retries;
        # any refusal exits before the next source or business request is sent.
        for sha in missing:
            result=self._wire_rpc({'op':'focus_prepare','sha':sha})
            if (result.get('focus_derived_version')==1 and result.get('sha')==sha
                    and result.get('ready') is False and sha in (local or {})):
                # Explicit missing original before any business execution. Restore
                # only the locally held canonical evidence, never a paid request.
                data=local[sha];chunk=caps.get('chunk_bytes');unit=caps.get('max_unit_bytes')
                if (not isinstance(data,bytes) or _blob_digest(data)!=sha
                        or type(chunk) is not int or not 0<chunk<=_WIRE_REQUEST_BYTES//4
                        or type(unit) is not int or not 0<len(data)<=unit<=_WIRE_REQUEST_BYTES):
                    raise StepError('검수 원본 복원 규격을 확인하지 못했습니다. 원본과 현재 상태를 보존하세요.')
                parts=(len(data)+chunk-1)//chunk
                for part in range(parts):
                    saved=self._wire_rpc({'op':'put','sha':sha,'size':len(data),'part':part,'parts':parts,
                        'data':base64.b64encode(data[part*chunk:(part+1)*chunk]).decode('ascii')})
                    if (saved.get('stored')!=sha if part==parts-1 else saved.get('part')!=part):
                        raise StepError('검수 원본 복원 결과를 확인하지 못했습니다. 제작 단계는 실행하지 않았습니다.')
                result=self._wire_rpc({'op':'focus_prepare','sha':sha})
            if (result.get('focus_derived_version')!=1 or result.get('sha')!=sha
                    or result.get('ready') is not True):
                raise StepError('검수 원본 준비를 확인하지 못했습니다. 제작 단계는 실행하지 않았으며 원본과 기존 작업 상태를 보존합니다.')
        return True

    def acknowledge_response(self):
        """Advance only after the owning caller durably saved its next state."""
        from response_receipts import Delivery
        held = getattr(self, '_receipt_returned', None)
        if held is not None:
            directory, logical_sha, request_id = held
            with Delivery(directory, logical_sha, save=_photo_write_state,
                          io_path=_review_receipt_io_path) as delivery:
                delivery.acknowledge(request_id)
            self._receipt_returned = None

    def step(self, name, payload=None, source=None, tool=None, _blob_retry=False, _blob_plain=False):
        from response_receipts import RecoveryPending, ServiceRefused
        if getattr(self, '_receipt_execution_refused', False):
            raise StepError('서비스 거부로 이 실행의 모든 추가 요청을 중지했습니다.')
        try:
            with contextlib.ExitStack() as stack:
                return self._step(name, payload, source, tool, _blob_retry, _blob_plain, stack)
        except ServiceRefused as error:
            self._receipt_execution_refused = True
            raise StepError(str(error)) from None
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 429):
                self._receipt_execution_refused = True
            raise
        except RecoveryPending as error:
            raise StepError(str(error)) from None

    def _step(self, name, payload, source, tool, _blob_retry, _blob_plain, _receipt_stack):
        from response_receipts import Delivery, logical_hash
        self._receipt_step_caps = None
        _initial_workdir = payload.get('workdir') if isinstance(payload, dict) else None
        if isinstance(_initial_workdir, str) and os.path.isabs(_initial_workdir):
            # 실패 보고(feedback)에는 workdir 가 없다 — 그 응답의 갱신(`self_update`)이 설치할 작업 폴더를 기억해 둔다.
            self._last_workdir = _initial_workdir
        _delivery = None
        if (isinstance(_initial_workdir, str) and os.path.isabs(_initial_workdir)
                and os.path.isdir(_review_receipt_io_path(_initial_workdir))
                and getattr(self, '_receipt_durable_owner', False)):
            logical_sha = logical_hash(self.url, tool or getattr(self, 'tool', None) or Client.tool,
                self.preset, name, payload, source)
            _delivery = _receipt_stack.enter_context(Delivery(_initial_workdir, logical_sha,
                save=_photo_write_state, io_path=_review_receipt_io_path))
            # An existing pending/refused attempt must never send even a caps
            # request first. Fresh attempts negotiate against the CURRENT account;
            # a work folder's old app-account capability cannot authorize legacy.
            if _delivery.record is None or _delivery.record['status'] == 'reserved':
                if getattr(self, '_receipt_negotiated', None) is None:
                    caps = self._wire_rpc({'op': 'caps'})
                    self._receipt_step_caps = caps
                    self._receipt_negotiated = caps.get('response_receipt_version', 0)
                    # 이 프로세스·이 출입증으로 협상한 계정 지문 — 새 영수증에 적어 봉인 때 같은 계정인지 본다.
                    self._receipt_account = caps.get('response_receipt_account')
                    remember_server_caps(_initial_workdir, caps)
                if self._receipt_negotiated != 1:
                    _delivery.__exit__(None, None, None)
                    _delivery = None
        if _delivery is not None and _delivery.record is not None and _delivery.record['status'] != 'reserved':
            request = urllib.request.Request(self.url, data=b'{}', headers={
                'Authorization': f'Bearer {self.token}', 'User-Agent': _UA})
            # ★디스크에 이미 있는 응답을 서버와 통신 없이 그대로 내주는 길인가 — ready 이고 자격증명이
            #   같을 때다(pending 은 아래 회수 GET 으로 **처음** 받아 오는 것이라 묵은 답이 아니다).
            _stored_answer = (_delivery.record['status'] == 'ready'
                and _delivery.record.get('credential_sha')
                    == hashlib.sha256(f'Bearer {self.token}'.encode()).hexdigest())
            exchange = {}
            from response_receipts import ResendSealed
            try:
                r = _delivery.exchange(request, exchange, timeout=self.timeout,
                    read=lambda *a: (_ for _ in ()).throw(AssertionError('recovery must not POST')),
                    on_refusal=lambda: setattr(self, '_receipt_execution_refused', True))
            except ResendSealed:
                # ★서버가 «앞 요청은 접수된 적이 없다» 를 봉인으로 확정했다(열쇠 MAC 확인 · 원장 W2-01).
                #   앞 기록은 `<request_id>.sealed.json` 으로 보관됐고 이 영수증은 닫혔다 → **지금 payload** 로
                #   새 요청을 보낸다(새 신원). 늦게 도착한 원본은 서버 admit 이 409 로 막는다(실행 안 됨).
                _delivery.__exit__(None, None, None)
                _progress(f"  [{name}] 앞 요청은 서버가 받지 못했음을 확인했다(봉인) — 지금 payload 로 새로 보낸다",
                          flush=True)
                return self.step(name, payload=payload, source=source, tool=tool)
            blobs, reviews = _delivery.load_context()
            return self._finish_step(r, name, payload, source, tool, _blob_retry,
                _delivery, _initial_workdir, blobs, reviews, _stored_answer=_stored_answer)
        preparer = getattr(self, '_prepare_imported_payload', None)
        if callable(preparer):
            payload = preparer(name, payload, source, tool)
        if isinstance(self._receipt_step_caps, dict):
            original_rpc = self._wire_rpc
            caps = self._receipt_step_caps
            self._wire_rpc = lambda params: caps if params == {'op': 'caps'} else original_rpc(params)
            _receipt_stack.callback(setattr, self, '_wire_rpc', original_rpc)
        self._id += 1
        args = {"step": name, "preset": self.preset}
        _workdir = payload.get("workdir") if isinstance(payload, dict) else None
        _blob_local, _blob_inline, _wire_reviews = {}, [], {}
        if payload is not None:
            if isinstance(payload,dict) and self.preset == '쇼핑' and name in ('shop_frame','shop_cuts','shop_render','shop_deliver'):
                if self._wire_rpc({'op':'caps'}).get('local_shop_version') == 1:
                    from local_focus import preserve_wire_evidence
                    payload = preserve_wire_evidence(payload,out_dir=str(payload['workdir']).rstrip('/')+'/local-shop/evidence')
            if isinstance(payload,dict) and name in ('person_frame','person_render','person_deliver'):
                local_caps=self._wire_rpc({'op':'caps'})
                if local_caps.get('local_person_version')==1 and self.preset in local_caps.get('local_person_presets',[]):
                    from local_focus import preserve_wire_evidence
                    payload=dict(preserve_wire_evidence(payload,out_dir=str(payload['workdir']).rstrip('/')+'/local-person/evidence'),local_person_version=1)
            if isinstance(payload,dict) and name in ('stitch_narr','stitch_blocks','stitch_master','deliver'):
                local_caps=self._wire_rpc({'op':'caps'})
                if local_caps.get('local_source_version')==1 and self.preset in (local_caps.get('local_source_presets') or []):
                    from local_source_plan import preserve_wire_evidence
                    payload=preserve_wire_evidence(payload)
            if isinstance(payload,dict) and self.preset == '어랍숏' and name in ('redub_master','deliver'):
                if self._wire_rpc({'op':'caps'}).get('local_redub_version') == 1:
                    from local_focus import preserve_wire_evidence
                    payload = preserve_wire_evidence(payload,out_dir=str(payload['workdir']).rstrip('/')+'/local-redub/evidence')
            if isinstance(payload,dict) and name in ('render_plan','render_mix','deliver'):
                local_caps = self._wire_rpc({'op':'caps'})
                if (local_caps.get('local_render_version') == 1
                        and self.preset in (local_caps.get('local_render_presets') or [])):
                    from local_focus import preserve_wire_evidence
                    payload = dict(preserve_wire_evidence(payload,
                        out_dir=str(payload['workdir']).rstrip('/')+'/local-render/evidence'),
                        local_render_version=1)
            if (self.preset == '인물형 롱폼' and name in ('longform_seed', 'longform_run', 'longform_status', 'longform_deliver')
                    and isinstance(payload, dict) and _longform_project_object(payload.get('longform_project'))
                    and any(k in payload for k in ('frames', 'focus_frames', 'focus_measurements', 'focus_recovery'))):
                # Negotiate before removing dense evidence from the RPC copy.
                # Original payload/checkpoint and exact legacy files stay local.
                if self._wire_rpc({'op': 'caps'}).get('local_focus_version') == 1:
                    from local_focus import preserve_wire_evidence
                    payload = preserve_wire_evidence(payload)
            payload = _unfold_focus_recovery(payload)
            if isinstance(payload, dict):
                load_server_caps(_workdir)     # F16: 새 프로세스의 첫 요청부터 협상된 모양으로
            args["payload"] = fold_payload(payload)
            recovery = payload.get('focus_recovery') if isinstance(payload,dict) else None
            if (self.preset == '인물형 롱폼' and name == 'longform_seed'
                    and isinstance(recovery,dict) and recovery.get('unrepaired_frames')):
                args['payload'] = _pack_focus_recovery(args['payload'],self._wire_rpc({'op':'caps'}))
            # ★서버가 이미 가진 큰 값은 지문만 보낸다(2026-09-26 · `_blob_wire` 머리말).
            #   `_blob_plain` — 응답 표지를 못 풀어 다시 받는 요청이다: 표지도 안 보내고 «풀 수 있다» 도 안 알린다.
            if not _blob_plain:
                args["payload"], _blob_local, _blob_inline = _blob_wire(payload, args["payload"], _workdir)
        if source is not None:
            args["source"] = source
        if tool is not None and not (isinstance(tool, str) and tool.strip()):
            raise StepError("step(tool=…) 은 도구 이름 글자여야 한다 "
                            "(안 주면 이 Client 의 도구)")
        # ★`getattr` 로 읽는다 — 옛 `__init__` 이 만든 객체에는 인스턴스 칸이 없다.
        #   그때는 클래스 속성(= 'volcano_video')이 답한다.
        tool_name = (tool.strip() if isinstance(tool, str) and tool.strip()
                     else getattr(self, "tool", None) or Client.tool)
        client_missing = set()
        if not _blob_plain and isinstance(args.get("payload"), dict):
            for key, value in args["payload"].items():
                if not _blob_eligible(key):
                    continue
                candidates = [value] if _blob_is_marker(value) else (value.values() if isinstance(value, dict) else ())
                for candidate in candidates:
                    if _blob_is_marker(candidate) and candidate["sha"] not in _blob_local:
                        client_missing.add(candidate["sha"])
        transport = {}
        if client_missing:
            # A server ACK is not a local original. Discover support before a
            # potentially paid tools/call, including after a server rollback.
            supported = self._wire_rpc({"op": "caps"}).get("blob_client_missing_version")
            if type(supported) is not int or supported != 1:
                raise StepError("서버가 실행기에 없는 캐시 원문의 복원을 지원하지 않습니다. "
                                "단계는 실행하지 않았습니다. 원본·접수 기록을 보존하고 서버 갱신 후 재개하세요.")
            transport["_volcano_blob_client_missing"] = {"version": 1, "shas": sorted(client_missing)}
        body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                           "params": dict(transport, name=tool_name, arguments=args)},
                          ensure_ascii=False).encode()
        _derived_ready = False
        def prepare_focus(focus_args):
            nonlocal _derived_ready
            _derived_ready = self._prepare_focus_derived(focus_args, tool_name, _blob_local)
        if len(body) > _WIRE_REQUEST_BYTES or _request_structure_exceeds_limit(body):
            args = self._wire_prepare(args, tool_name, _wire_reviews, prepare_focus)
            self._id += 1
            body = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                "params": dict(transport, name=tool_name, arguments=args)}, ensure_ascii=False).encode()
            if len(body) > _WIRE_REQUEST_BYTES or _request_structure_exceeds_limit(body):
                raise StepError("증거 전송 요청이 한도를 넘습니다. 단계는 실행하지 않았습니다.")
        else:
            prepare_focus(args)
        if _derived_ready:
            self._id+=1
            body=json.dumps({"jsonrpc":"2.0","id":self._id,"method":"tools/call",
                "params":dict(transport,name=tool_name,arguments=args)},ensure_ascii=False).encode()
        _exchange = {"client_request_id": uuid.uuid4().hex}
        req = urllib.request.Request(self.url, data=body, headers={
            "X-Volcano-Request-ID": _exchange["client_request_id"],
            "Authorization": f"Bearer {self.token}", "content-type": "application/json",
            "MCP-Protocol-Version": "2025-11-25", "User-Agent": _UA,
            # ★cow-v3 (2026-10-05 · 원장 W2-08 FP2): 이 실행기는 서버가 작업 단계 대신 `status: runner_update` 를
            #   돌려주면 스스로 설치하고 같은 단계로 재시작한다(구동기 `_drive_loop` · B 묶음). 서버는 이 표지를 보고만 그렇게 답한다.
            "X-Volcano-Runner-Update": "cow-v3",
            # ★응답의 지문 표지를 풀 수 있고, structuredContent 만 읽는다고 알린다(서버 `volcano_blob`).
            "X-Volcano-Runner-Caps": _BLOB_CAPS_PLAIN if _blob_plain else _BLOB_CAPS})
        if _derived_ready:
            req.add_header('X-Volcano-Runner-Caps',req.get_header('X-volcano-runner-caps')+', focus-derived-v1')
        if req.get_header('X-volcano-runner-update') == 'cow-v3' and not _driver_runs_fp2():
            # ★FP2 는 **구동기**가 처리한다 — 이 프로세스의 구동기가 그 판이 아니면(자동 설치가 volcano_drive.py 교체에서
            #   끊긴 «새 volcano_run + 옛 volcano_drive» · 구동기 없이 Client 만 쓰는 호출) cow-v2 로 알린다. 그러면 서버는
            #   FP1 설치기로 답하고 그 설치기가 남은 파일을 마저 바꾼다(Z 검토 minor: cow-v3 로 알리면 옛 구동기가 FP2 응답을
            #   못 알아들어 같은 단계를 max_steps 까지 되풀이했다 — 실행 한 번에 서버 요청 40건 · 스스로 안 낫는다).
            req.add_header('X-Volcano-Runner-Update', 'cow-v2')
        if _delivery is not None:
            _delivery.save_context(_blob_local, _wire_reviews)
        self._rpc_wait()
        try:
            # tools/call can already have reached a paid provider when a 5xx or
            # connection reset occurs. A transport error cannot prove otherwise.
            if _delivery is None:
                r = _read_unreceipted(req, self.timeout, f"단계 {name}", _exchange)
            else:
                from response_receipts import RecoveryPending, ServiceRefused
                try:
                    r = _delivery.exchange(req, _exchange, timeout=self.timeout,
                        on_refusal=lambda: setattr(self, '_receipt_execution_refused', True),
                        read=lambda request, timeout, observation, completed: _read_mcp_response(
                            request, timeout, f"단계 {name}", observation, complete=completed),
                        limit_exceeded=_limit_exceeded,
                        notify=lambda message: _progress(f"  [재시도] 단계 {name} — {message}", flush=True),
                        account=getattr(self, '_receipt_account', None))
                except ServiceRefused:
                    raise
                except RecoveryPending as pending:
                    # 같은 신원 재전송·회수까지 해 봤다 — 상태를 말하고 요청 진단(본문·열쇠 없음)을 붙인다.
                    raise StepError(f"[{name}] {pending}" + _mcp_observation_note(_exchange)) from None
        except urllib.error.HTTPError as exc:
            if _limit_exceeded(exc):
                # ★같은 요청을 다시 보내지 않는다(`_open_retry`). 사람·모델에게 **왜 멈췄는지**와
                #   **무엇을 하지 말아야 하는지**를 말한다 — 말하지 않으면 같은 명령을 또 돌린다
                #   (2026-09-26: 끊긴 요청이 몇 분마다 다시 실행됐다).
                raise StepError(
                    f"[{name}] 서버가 이 요청을 계산하다 Cloudflare 한도(CPU·메모리)를 넘어 "
                    "중간에 끊겼습니다(error code 1102). 같은 요청을 다시 보내지 않았습니다 — "
                    "다시 보내도 같은 곳에서 또 끊기고, 그 사이 다른 수강생의 요청까지 실패합니다. "
                    "이 실패는 자동으로 보고됩니다. 같은 명령을 반복 실행하지 말고, 서버 수정이 "
                    "배포된 뒤 같은 명령으로 이어서 진행하세요."
                    + _mcp_observation_note(_exchange)) from exc
            if getattr(exc, "code", None) == 413 and isinstance(args.get("payload"), dict):
                # ★413 은 서버가 파싱 전에 거부해 본문이 어디에도 안 남는다 — 어느 칸이 컸는지 여기서 말한다.
                raise StepError(f"[{name}] {exc} — 보낸 payload 의 칸별 구조 토큰"
                                f"(접기 v{_focus_pack_version()} · 참조 v{_focus_ref_version()}): "
                                + payload_token_report(args["payload"])) from exc
            if getattr(exc, "code", 0) >= 500:
                raise StepError(
                    f"[{name}] 서버가 HTTP {exc.code}을(를) 돌려줬습니다. 요청 접수와 완료 여부를 "
                    "확인할 수 없습니다. 같은 단계를 자동 재전송하지 않았습니다. 기존 작업 폴더의 "
                    "체크포인트, 유료 접수 기록과 결과를 보존하고 처리 결과를 확인한 뒤 재개하세요."
                    + _mcp_observation_note(_exchange)) from exc
            raise
        except (OSError, http.client.HTTPException, ValueError) as exc:
            # 이 PC 의 디스크가 가득 찬 것(로컬 쓰기)은 서버 응답 문제가 아니다 — 판별은 disk_full_note 한 곳.
            _disk = disk_full_note(exc, _workdir)
            if _disk:
                raise StepError(f"[{name}] {_disk}" + _mcp_observation_note(_exchange)) from exc
            # Includes timeout while reading a successful response body and
            # truncated/malformed JSON after the server accepted the POST.
            raise StepError(
                f"[{name}] 서버 응답을 끝까지 확인하지 못했습니다. 요청 접수와 완료 여부를 확인할 수 없습니다. "
                "같은 단계를 자동 재전송하지 않았습니다. 기존 작업 폴더의 체크포인트, "
                "유료 접수 기록과 결과를 보존하고 처리 결과를 확인한 뒤 재개하세요."
                + _mcp_observation_note(_exchange)) from exc
        finally:
            self._rpc_record()
        return self._finish_step(r, name, payload, source, tool, _blob_retry, _delivery, _workdir, _blob_local, _wire_reviews)

    def _finish_step(self, r, name, payload, source, tool, _blob_retry, _delivery, _workdir, _blob_local, _wire_reviews, _stored_answer=False):
        if not isinstance(r, dict):
            raise StepError(f"[{name}] 서버 응답이 JSON 객체가 아닙니다 — 같은 단계로 재개하세요")
        from response_zip import ResponseZipError, restore_response_zip
        try:
            r = restore_response_zip(r)
        except ResponseZipError as exc:
            raise StepError(f"[{name}] 압축된 서버 응답을 완전히 확인하지 못했습니다. 요청이 이미 실행되었을 수 있어 "
                            "자동 재전송하지 않았습니다. 원본·체크포인트·유료 접수 기록을 보존하세요.") from exc
        if "error" in r:
            raise StepError(f"[{name}] {r['error'].get('message')}")
        res = r.get("result")
        # ★빈 결과를 AttributeError 로 죽이지 않는다 (2026-09-12 실측: 린박스 stitch_blocks 에서
        #   `'NoneType' object has no attribute 'get'` 로 실행기가 멎었다). 사람 말로 멈추고 재개하게 한다.
        if not isinstance(res, dict):
            raise StepError(f"[{name}] 서버가 결과 객체 대신 {type(res).__name__} 을(를) 돌려줬습니다 — 같은 단계로 재개하세요")
        meta = res.get("_meta")
        if isinstance(meta, dict) and "response_inline_blobs" in meta:
            from response_inline_blobs import decode_cache
            try:
                _blob_local = decode_cache(res.get("structuredContent"), meta["response_inline_blobs"], _blob_local)
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise StepError(
                    "새 응답 증거를 확인하지 못했습니다. 단계가 이미 실행되었을 수 있어 "
                    "자동 재전송하지 않았습니다. 원본·체크포인트·접수 기록을 보존하세요.") from exc
            meta = dict(meta)
            meta.pop("response_inline_blobs")
            res = dict(res, _meta=meta)
        if isinstance(meta, dict) and "response_refs" in meta:
            from response_refs import restore_response_refs
            try:
                restored = restore_response_refs(res.get("structuredContent"), meta["response_refs"])
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise StepError(f"[{name}] 검수 응답의 참조를 확인하지 못했습니다. 단계가 이미 실행되었을 수 있어 "
                                "자동 재전송하지 않았습니다. 원본·체크포인트·접수 기록을 보존하세요.") from exc
            meta = dict(meta)
            meta.pop("response_refs")
            res = dict(res, structuredContent=restored, _meta=meta)
        if res.get("isError") and isinstance(meta, dict) and meta.get("wire_blob_missing"):
            # The server has not run the tool. Re-upload is a user-controlled
            # resume, not an automatic repeat of a potentially paid step.
            raise StepError(f"[{name}] 저장한 검수 증거 캐시를 찾지 못했습니다. 원본과 접수 기록을 보존하고 같은 상태에서 재개하세요. 단계는 실행하지 않았습니다.")
        # ★서버 저장소에 없던 값 — 그 값만 통째로 **한 번** 다시 보낸다(저장소는 캐시다).
        if res.get("isError") and isinstance(meta, dict) and isinstance(meta.get("blob_missing"), list):
            _blob_remember(_workdir, drop=meta["blob_missing"])
            if not _blob_retry:
                if _delivery is not None:
                    _delivery.acknowledge(_delivery.record['request_id'])  # Explicit proof the tool was not run.
                    _delivery.__exit__(None, None, None)
                return self.step(name, payload=payload, source=source, tool=tool, _blob_retry=True)
            raise StepError(f"[{name}] 서버 저장소가 이번에 보낸 값을 다시 찾지 못했습니다 — 같은 단계로 재개하세요 "
                            f"(지문 {len(meta['blob_missing'])}개)")
        try:
            res = _blob_resolve_result(res, _blob_local, name)
            res = _restore_review_evidence(res, _wire_reviews)
        except _BlobUnknown:
            # The tool may have completed before its response became unreadable.
            # Repeating it to fetch an unmarked result can duplicate paid work.
            raise
        meta = res.get("_meta")
        if isinstance(meta, dict) and isinstance(meta.get("runner_key"), dict):
            # ★활동 중 출입증 갱신 (2026-10-05 · 원장 W2-07 실행기 조각). 서버가 만료 전에 같은 모양의 새 출입증
            #   `{token, expires, url, preset}`(`volcano_tools._runner_key`)을 `_meta.runner_key` 로 주면 **돌고 있는
            #   Client 의 토큰을 바꾼다** — 예전에는 파일만 바뀌고(구동기) 이 프로세스는 옛 토큰으로 계속 보내다
            #   발급+2일에 만료돼 회수 GET 까지 403 → 대기 기록이 refused 로 굳었다. 파일 쓰기는 구동기 몫이다
            #   (`_runner_key_hook` · B 묶음). 값은 찍지 않는다 — 아래 `[알림] {meta}` 에 실리지 않게 먼저 뺀다.
            meta = dict(meta)
            renewed = meta.pop("runner_key")
            res = dict(res, _meta=meta)
            token = renewed.get("token")
            # ★더 늦게 끝나는 출입증만 받는다 (2026-10-05 · Z 검토 major). 이 칸은 응답 영수증에 함께 저장되므로 나중에
            #   회수(GET)·재생한 **옛 응답**의 출입증이 그 사이 새로 받은 출입증을 덮어 되돌렸다(만료가 지났으면 다음 요청 401
            #   → refused). 만료일은 서명 토큰 안(`VOLC-U1.<이메일>.<YYYY-MM-DD>…`)에서 읽는다. 지금 출입증의 만료를 모르면
            #   (형식이 다른 토큰 — 서버는 앱 계정에게만 이 칸을 준다) 예전처럼 받는다.
            _new_exp = _token_expiry(token) or str(renewed.get("expires") or "")
            _cur_exp = _token_expiry(self.token) or getattr(self, "_token_expires", None)
            if isinstance(token, str) and token.strip() and token != self.token \
                    and not (_cur_exp and not (_new_exp > _cur_exp)):
                self.token = token
                self._token_expires = _new_exp or None
                # 실패 보고(feedback)에는 workdir 가 없다 — 이 실행이 다룬 작업 폴더(`_last_workdir`)에 남긴다.
                _key_dir = _workdir if isinstance(_workdir, str) and os.path.isabs(_workdir) \
                    else getattr(self, "_last_workdir", None)
                hook = getattr(self, "_runner_key_hook", None)
                if callable(hook):
                    hook(renewed)
                elif isinstance(_key_dir, str) and os.path.isabs(_key_dir):
                    # 구동기의 저장 한 자리(작업 폴더의 .volcano_runner_key.json — 원자 교체는 B 묶음)
                    from volcano_drive import save_runner_key  # noqa: PLC0415
                    save_runner_key(renewed, _key_dir)
                _progress(f"  [출입증] 서버가 새 실행기 출입증을 줬다(만료 {renewed.get('expires')}) — "
                          "다음 요청부터 새 출입증을 쓴다", flush=True)
            elif isinstance(token, str) and token.strip() and token != self.token:
                _progress("  [출입증] 응답에 실린 출입증이 지금 쓰는 것보다 먼저 끝나 그대로 둔다(되찾은 옛 응답)", flush=True)
        _blob_caps_seen(_workdir, meta)
        _blob_learn(res, _workdir)
        if isinstance(meta, dict) and type(meta.get("focus_ref_version")) is int \
                and meta["focus_ref_version"] > _focus_ref_version():
            os.environ[_FOCUS_REF_FLAG] = str(meta["focus_ref_version"])
        if isinstance(meta, dict) and type(meta.get("focus_pack_version")) is int \
                and meta["focus_pack_version"] > _focus_pack_version():
            os.environ[_FOCUS_PACK_FLAG] = str(meta["focus_pack_version"])
        if isinstance(meta, dict) and isinstance(payload, dict):
            remember_server_caps(payload.get("workdir"), meta)   # F16: 다음 프로세스가 첫 요청부터 접게
        if meta:
            # ★★옛 실행기면 **여기서 스스로 갱신한다** (2026-09-02). 서버가 새 팩의 열쇠 URL·
            #   sha 를 `_meta.runner_update` 로 준다 — 받아 검증하고 파일을 바꾼 뒤 모듈을 다시
            #   읽는다. 구동기가 `updated` 를 보고 다음 단계부터 새 코드로 넘어간다.
            _upd = meta.get("runner_update") if isinstance(meta, dict) else None
            # Active versioned editor jobs retain their installed code. A new
            # job can install the latest pack through the normal assets path.
            _job_pinned = isinstance(payload, dict) and payload.get('runner_pin') is True
            # 디스크의 옛 답(_stored_answer)에 실린 갱신 지시는 그때의 판·6시간 열쇠다 — 따르지 않는다(지나간 판은 403 ·
            #   아래 runner_update 응답 갈래와 같은 이유 · 10-23). 답 자체는 실행 결과라 그대로 쓰고, 갱신은 다음 새 요청이 지금 판으로 받는다.
            if isinstance(_upd, dict) and _upd.get("url") and _upd.get("sha256") \
                    and not os.environ.get(_UPDATED_FLAG) and not _job_pinned and not _stored_answer:
                try:
                    if self_update(_upd, self):
                        self.updated = True
                        if not res.get('isError'):
                            value = self._structured(name, res)
                            if _delivery is not None:
                                self._receipt_returned = (_delivery.directory, _delivery.logical_sha, _delivery.record['request_id'])
                            return value
                except RunnerRelocated:
                    raise                      # 설치는 됐다 — «갱신 실패» 가 아니라 다시 띄울 명령을 그대로 말한다
                except Exception as e:  # noqa: BLE001
                    raise StepError("실행기 자동 갱신 실패로 이 단계 실행을 멈췄습니다. "
                                    "같은 요청을 다시 실행하면 갱신부터 재시도합니다: %s" % e) from e
            if isinstance(meta, dict) and meta.get("runner_outdated") and not getattr(self, 'updated', False):
                # ★★크게 말한다 (2026-09-02 · 48h 실행기 사용자 93명 중 89명이 옛 팩).
                #   한 줄 [알림] 은 아무도 안 읽었다. 이미 올라간 코드는 안 바뀌므로
                #   팩을 새로 받은 뒤 **프로세스를 다시 시작**해야 한다.
                # ★서버 문장만 찍는다 (2026-10-05 · 원장 W2-13). 예전에는 실행기가 «step='assets' 를 다시 부른 뒤
                #   이 프로세스를 다시 시작» 을 자기 코드로 덧붙였다 — FP1(자동 설치) 뒤에는 틀린 지시이고,
                #   `--step assets` 는 체크포인트를 덮는다(W2-12). 무엇을 할지는 그 상황을 아는 서버가 말한다.
                _progress("\n  ★★★ 실행기 팩이 옛것입니다 — " + str(meta["runner_outdated"])[:400] + "\n", flush=True)
            elif not res.get('isError'):
                _progress(f"  [알림] {meta}")
        if res.get('isError'):
            # The server's recovery contract and update used to be discarded here.
            # Installing an update does not turn a rejected video into a success.
            internal = isinstance(meta, dict) and meta.get('error_kind') == 'crash'
            error_type = StepError if internal else RejectedError
            # ★★오류 응답(도구 반려·서버 내부 오류)은 **실행 결과가 아니다** — 영수증에 굳히지 않는다 (2026-10-05).
            #   영수증은 «실행된 단계를 두 번 실행하지 않는다» 를 지키는 장치다. 오류 응답은 그 반대의
            #   증명이다(도구가 끝까지 돌지 않았다 — 바로 위 blob_missing 갈래가 같은 근거로 ACK 한다).
            #   그런데 오류 응답은 누구도 그 뒤 상태로 넘어가지 않으니 ACK 가 없었고, ready 로 남아
            #   **같은 payload 로 다시 뜰 때마다 서버에 묻지 않고 디스크의 옛 답을 그대로 내줬다.**
            #   실측(2026-10-04 · 수치는 저장소 docs 의 render-mix 문서에 있다):
            #     · «요청이 너무 잦습니다 — 잠시 뒤 다시» 가 굳어, 서버는 한 번 막았는데 그 사람은 두 시간
            #       넘게 같은 답만 받았다(기다려도 서버에 닿지 않는다)
            #     · 서버를 고쳐 배포해도 같은 payload 면 고쳐진 서버에 닿지 않는다(강석주 render_mix)
            #   그래서 오류 응답을 사람에게 넘기는 이 자리에서 영수증을 소비한다 — 다음 실행은 서버에 새로
            #   묻는다(영수증 이전의 동작 그대로다). 성공 응답은 손대지 않는다 — 소유자가 다음 상태를
            #   저장한 뒤 명시적으로 ACK 한다는 규율 그대로다. pending(응답을 못 받은 요청)·refused(HTTP
            #   거부)도 그대로다 — 그쪽은 실행 여부를 모르거나 서비스가 멈추라고 한 것이다.
            _consumed = False
            if _delivery is not None:
                try:
                    _delivery.acknowledge(_delivery.record['request_id'])
                    # ★«예외가 없었다» 가 아니라 **실제로 닫혔는가**로 판정한다 — 닫히지 않은 채 아래에서
                    #   새로 물으면 같은 영수증을 다시 읽어 같은 자리로 되돌아온다.
                    _consumed = _delivery.record.get('status') == 'reserved'
                except (OSError, StepError) as _ack_error:
                    # 소비를 못 적어도 **오류는 그대로 사람에게 간다**. 잃는 것은 «다음 실행이 새로 묻기» 뿐이다.
                    _progress(f"  [영수증] 오류 응답의 영수증을 닫지 못했다({type(_ack_error).__name__}) — "
                              "같은 payload 로 다시 뜨면 이 답이 한 번 더 나올 수 있다", flush=True)
            if _stored_answer and _consumed:
                # ★앞 실행(이 수리 전의 실행기 포함)이 남긴 묵은 오류 응답 — 사람에게 다시 보여 주지 않고
                #   **지금 서버에** 묻는다. 방금 영수증을 닫았으므로 아래 호출은 새 요청이고, 그 답이 또
                #   오류면 위 갈래가 닫고 그대로 올린다(되돌아오지 않는다 — 새 답은 _stored_answer 가 아니다).
                _delivery.__exit__(None, None, None)
                _progress(f"  [{name}] 앞 실행이 남긴 오류 응답은 다시 쓰지 않는다 — 서버에 새로 묻는다", flush=True)
                return self.step(name, payload=payload, source=source, tool=tool)
            limited = meta.get('rate_limited') if isinstance(meta, dict) else None
            depth = getattr(self, '_rate_retry_depth', 0)
            if (isinstance(limited, dict) and limited.get('version') == 1
                    and type(limited.get('retry_after')) is int and 1 <= limited['retry_after'] <= 61
                    and type(limited.get('retries')) is int and depth < limited['retries']
                    and (_delivery is None or _consumed)):
                # ★분당 상한 — 서버가 «실행하지 않았다» 고 확답하고 칸이 풀리는 시각을 준다 (2026-10-05 · 원장 W2-06).
                #   예전에는 반려로 작업 전체를 멈췄다(10-04 8계정). 그만큼 기다렸다가 **새 요청으로** 다시 보낸다 —
                #   영수증은 위에서 닫혔다. 그 사이 feedback 은 보내지 않는다(예외를 올리지 않으므로). 횟수는 서버가 준다.
                if _delivery is not None:
                    _delivery.__exit__(None, None, None)
                _progress(f"  [{name}] 서버 분당 상한 — {limited['retry_after']}초 뒤 다시 보낸다(실행되지 않은 요청)",
                          flush=True)
                time.sleep(limited['retry_after'])
                self._rate_retry_depth = depth + 1
                try:
                    return self.step(name, payload=payload, source=source, tool=tool)
                finally:
                    self._rate_retry_depth = depth
            error = error_type(f"[{name}] {res['content'][0]['text']}")
            error.contract = meta.get('contract') if isinstance(meta, dict) else None
            # ★디스크의 옛 답을 다시 보여 주는 것인가(영수증을 못 닫아 새로 묻지 못한 경우뿐 · W2-04) — 구동기가 이 표식을
            #   보고 실패 보고(feedback)를 다시 보내지 않는다(B 묶음 `_report_failure` · 묶음 사이 약속 `replayed`).
            error.replayed = bool(_stored_answer)
            raise error
        value = self._structured(name, res)
        if (_stored_answer and _delivery is not None and isinstance(value, dict)
                and value.get('status') == 'runner_update'):
            # ★★실행기 갱신 응답도 **실행 결과가 아니다** — 위 오류 응답과 같은 부류다 (2026-10-23 · 3D쇼츠 신고 10-22 21:00).
            #   서버는 그 단계를 실행하지 않고(접근 로그 ok=0 · entry `_runner_update`) «그때의 배급 판 + 6시간 열쇠 주소» 를
            #   준다. 디스크에 남은 그 답을 다시 내주면 이미 지나간 판(e9ce4cb953b4)으로 가라는 지시가 되고, 열쇠가 만료된
            #   옛 판 주소는 배급 문이 403 «unsigned historical asset version» 으로 막는다(사전 점검 setup 의 영수증이 그 폴더의
            #   모든 다음 실행에 같은 답을 재생했다 — 새 실행기 889b5f6691dd 에서도). 그래서 오류 응답과 같이 닫고 지금 서버에
            #   묻는다 — 지금 판이면 갱신 없이 단계가 돌고, 아니면 지금 판·새 열쇠의 갱신을 받는다(새 답은 _stored_answer 가 아니다).
            _delivery.acknowledge(_delivery.record['request_id'])
            if _delivery.record.get('status') == 'reserved':
                _delivery.__exit__(None, None, None)
                _progress(f"  [{name}] 앞 실행이 남긴 실행기 갱신 응답은 다시 쓰지 않는다 — 서버에 새로 묻는다", flush=True)
                return self.step(name, payload=payload, source=source, tool=tool)
        if _delivery is not None:
            self._receipt_returned = (_delivery.directory, _delivery.logical_sha, _delivery.record['request_id'])
        return value

    @staticmethod
    def _structured(name, res):
        value = res.get("structuredContent")
        if not isinstance(value, dict):
            text = ""
            try:
                text = str((res.get("content") or [{}])[0].get("text") or "")[:300]
            except Exception:  # noqa: BLE001
                text = ""
            raise StepError(f"[{name}] 서버 결과에 structuredContent 가 없습니다 — 같은 단계로 재개하세요. "
                            + (f"본문: {text}" if text else ""))
        return value


def post_json(endpoint, body, headers, timeout=120, *, before_request=None):
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
                                 headers=dict(headers, **{"Content-Type": "application/json",
                                                          "User-Agent": _UA}))
    if before_request: before_request()
    response = urllib.request.urlopen(req, timeout=timeout)
    try:
        return json.load(response)
    finally:
        close = getattr(response,'close',None)
        if close: close()


def get_json(endpoint, headers, timeout=120):
    """★`User-Agent` 는 **부르는 쪽이 이긴다** — `_UA` 는 기본값이다.

    예전에는 `_UA` 가 뒤에 있어서 **부르는 쪽이 준 UA 가 조용히 무시됐다.**
    서버가 "이 UA 로 부르라" 고 지시하는 자리가 생겼으니(공개 이미지 API) 그 지시가
    실제로 나가야 한다 — 안 나가면 §유령 인자다(받아 놓고 안 읽는 값).
    ★기본값은 그대로 남는다: 파이썬 기본 UA 는 Cloudflare 가 403 으로 막고,
      위키미디어도 UA 정책으로 막는다. 아무도 안 주면 `_UA` 가 쓰인다.
    """
    req = urllib.request.Request(endpoint, headers=dict({"User-Agent": _UA},
                                                        **dict(headers or {})))
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _content_range_start(value):
    """`Content-Range: bytes N-M/T` 의 N(모양이 다르면 None)."""
    m = re.fullmatch(r"\s*bytes\s+(\d+)-(\d+)/(\d+|\*)\s*", str(value or ""))
    return int(m.group(1)) if m else None


_DOWNLOAD_SEEN = contextvars.ContextVar('volcano_download_seen', default=None)


@contextlib.contextmanager
def download_seen():
    """`with download_seen() as seen: download(...)` — 그 안에서 받은 응답마다 머리 칸(`response_facts`)이 `seen` 에 쌓인다.

    ★서명 밖 통로(2026-10-23 · 신고 3건 09:38 뇌전구 sfx `_curl_dl` · 11:48 뇌전구 assets `_curl_download` · 13:59 리센느 `_patch.<locals>.download`):
      처음엔 `download(..., seen=)` 인자로 받았는데, 수강생 쪽 커스텀이 `volcano_run.download` 를 옛 서명(url, out, timeout, headers, resume)의
      자기 함수로 갈아 끼운 실행기에서 `TypeError: unexpected keyword argument 'seen'` 로 자산 받기가 죽었다. `download` 는 갈아 끼워지는 공개
      계약이라 서명을 늘리지 않는다(시험 `test_download_contract` 가 서명과 부르는 쪽 낱말을 고정) — 진단 사실은 이 문맥 변수로만 모은다.
      갈아 끼운 함수가 안 채우면 `seen` 이 비고, `asset_mismatch_facts` 가 «응답 머리 없음» 이라고 말한다. 스레드마다 따로다(contextvars)."""
    seen = []
    token = _DOWNLOAD_SEEN.set(seen)
    try:
        yield seen
    finally:
        _DOWNLOAD_SEEN.reset(token)


def note_response(facts):
    """지금 `download_seen()` 안이면 응답 머리 한 덩어리를 싣는다(밖이면 아무것도 안 한다)."""
    seen = _DOWNLOAD_SEEN.get()
    if seen is not None:
        seen.append(facts)


def download(url, out, timeout=180, headers=None, resume=False):
    """URL 을 `out` 에 받는다. 돌려주는 값 = 받은 바이트 수.

    ★**스트리밍으로 쓴다**(2026-09-25 B11-코드 · SR-19 ② · 01 F18): 예전에는 본문 전체를 메모리로 `.read()` 한 뒤 썼다 — 209MB 참조 팩이
      통째로 메모리에 올랐고, 중간에 끊기면(IncompleteRead·연결 리셋·10054·시간 초과) 그 자리에서 죽었다(`_open_retry` 는 **연결**만 다시 하고
      본문 읽기는 다시 하지 않는다 · 17회·14명). 받는 동안은 `out + ".download"` 에 쓰고 다 받은 뒤에만 `out` 으로 옮긴다(반쪽 파일이 완성본
      이름으로 남지 않게). ★`Content-Length` 보다 적게 오면 끊긴 것이다 — 파이썬 http.client 의 `read(n)` 은 그때 예외 없이 빈 조각을 준다(CPython
      주석 「Ideally, we would raise IncompleteRead」)라 여기서 직접 잰다.
    ★`resume=True`(**우리 서버의 자산**만 — 실행기 `_fetch_asset`·실행기 갱신): 중간에 끊기면 받은 바이트부터 `Range: bytes=N-` 로 **이어받는다**
      (서버 `serve_asset` 이 206 + Content-Range 로 답한다 · 시작 위치가 같을 때만 이어 붙인다 · 200 이면 처음부터 · 416 이면 처음부터).
      이어받기 횟수는 `_open_retry` 와 같은 자(3번 · 1·2초 쉼 — 2026-08-13 콜드스타트 실측 규율)다 — 새 숫자를 짓지 않았다.
      ★남의 서버(그림 결과·사진·이라스토야)는 `resume=False` — 요청 수를 늘리지 않는다(외부 서비스의 연속 요청은 그 스펙 숫자로만 · 전역 규칙 6-2).
      받은 뒤 sha256 대조는 부르는 쪽 몫이다(이어 붙인 바이트도 같은 자로 잰다).
    ★`download_seen()` 안이면(2026-10-23) 받은 응답마다(이어받기 포함) 그 응답의 머리 몇 칸을 `response_facts` 모양으로 붙인다 — 지문이 어긋났을 때
      «누가 그 바이트를 냈나»(우리 Worker 판·Cloudflare 캐시·중간 프록시·리디렉트)를 신고 글에 싣기 위해서다(`asset_mismatch_facts`).
      새 판 주소에 바로 앞 판 바이트가 온 신고가 10-11~10-22 15건인데 서버 경로로는 그 바이트가 나올 수 없어, 응답 쪽 사실이 없으면 못 가린다."""
    import http.client
    # ★UA 는 부르는 쪽이 이긴다(`get_json` 과 같은 이유). 기본값은 `_UA` 다.
    base = dict({"User-Agent": _UA}, **dict(headers or {}))
    what = os.path.basename(out) or url
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    part = out + ".download"
    attempts = 3 if resume else 1
    have, last = 0, None
    try:
        for a in range(attempts):
            if a:
                _progress(f"  [이어받기] {what} — {have:,}B 받은 뒤 끊겼다({last}) · "
                          + (f"{have:,}B 부터 이어 받는다" if have else "처음부터 다시 받는다"), flush=True)
                time.sleep(a)                         # 1·2초(_open_retry 와 같은 쉼)
            hdrs = dict(base, **({"Range": f"bytes={have}-"} if have else {}))
            req = urllib.request.Request(url, headers=hdrs)
            try:
                # ★자산 내려받기도 같은 콜드스타트 실패를 맞는다 — 실측에서 실제로 여기가 죽었다(연결 재시도는 `_open_retry` 몫)
                resp = _open_retry(req, timeout, what)
            except urllib.error.HTTPError as e:
                if have and e.code == 416:            # 이어받을 자리가 서버 쪽 끝을 넘었다 → 처음부터
                    have, last = 0, e
                    continue
                raise
            with resp:
                # ★응답에서 읽는 것은 **필요한 만큼만**(2026-09-25 B11-코드): 상태 코드는 이어받을 때만 보고, 헤더는 있을 때만 본다.
                #   예전 계약은 `.read()` 하나였다 — 실행기 갱신 시험(test_runner_native_update)처럼 urlopen 자리에 본문만 주는 쪽이 있다.
                #   진짜 HTTP 응답(http.client.HTTPResponse)은 늘 status·headers 를 가지므로 이어받기·길이 대조는 그대로 돈다.
                rh = getattr(resp, "headers", None) or {}
                note_response(response_facts(resp, url))
                if have:
                    status = getattr(resp, "status", None) or resp.getcode()
                    if not (status == 206 and _content_range_start(rh.get("Content-Range")) == have):
                        if status == 206:             # 다른 자리부터 준 조각은 이어 붙일 수 없다 → 처음부터 다시(이 응답은 버린다)
                            have, last = 0, RuntimeError(f"Content-Range 시작이 {have} 가 아니다: {rh.get('Content-Range')!r}")
                            continue
                        have = 0                      # 200 — 서버가 Range 를 무시하고 전체를 준다(RFC 9110 허용) → 처음부터 쓴다
                length = rh.get("Content-Length")
                expected = have + int(length) if length and str(length).isdigit() else None
                try:
                    with open(part, "ab" if have else "wb") as fh:
                        for block in iter(lambda: resp.read(1024 * 1024), b""):
                            fh.write(block)
                            have += len(block)
                    if expected is not None and have < expected:
                        raise http.client.IncompleteRead(b"", expected - have)
                except (http.client.HTTPException, OSError) as e:
                    last = e
                    continue
            os.replace(part, out)
            return have
        raise last
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass


#: 이 파일의 받기 함수 그 자체 — 모듈 이름 `download` 은 갈아 끼울 수 있는 공개 계약이라, 비교는 정의 직후 잡은 이 값으로 한다.
_STOCK_DOWNLOAD = download

#: 지문 어긋남 신고에 싣는 응답 머리 — 우리 Worker 가 붙이는 판·키(`serve_asset` `_asset_headers`)와 그 사이 누가 끼었는지 말하는 칸만.
#: 비밀이 없는 칸만 고른다(열쇠 `k` 가 든 요청 주소·Authorization·쿠키는 싣지 않는다).
RESPONSE_FACT_HEADERS = ("x-volcano-sha256", "x-volcano-commit", "x-volcano-key", "x-volcano-etag", "x-volcano-uploaded",
                         "cf-ray", "cf-cache-status", "age", "via", "content-length", "content-range", "etag", "server")


def response_facts(resp, url):
    """응답 하나의 사실 — 상태 코드 · 위 머리 칸(있는 것만) · 리디렉트로 다른 주소가 답했으면 그 호스트·경로(쿼리는 버린다 — 열쇠가 들어 있다)."""
    from urllib.parse import urlsplit
    rh = getattr(resp, "headers", None) or {}
    out = {"status": getattr(resp, "status", None)}
    for name in RESPONSE_FACT_HEADERS:
        value = rh.get(name) if hasattr(rh, "get") else None
        if value is not None:
            out[name] = str(value)[:120]
    final = getattr(resp, "url", None) or (resp.geturl() if hasattr(resp, "geturl") else None)
    if isinstance(final, str) and final:
        a, b = urlsplit(str(url)), urlsplit(final)
        if (a.netloc, a.path) != (b.netloc, b.path):
            out["redirected_to"] = b.netloc + b.path
    return out


def asset_mismatch_facts(seen, got_bytes, got_sha, fetcher=None):
    """지문 어긋남 오류 끝에 붙이는 한 덩어리 — 받은 바이트 수·받은 sha·응답마다 머리 칸. `seen` 이 비면 «응답 머리 없음» 이라고 말한다.

    ★`fetcher`(2026-10-23) = 부르는 쪽이 실제로 쓴 받기 함수. 이 파일의 `download` 는 응답마다 머리를 반드시 싣는다 — 그러니 «응답 머리 없음» 은
      갈아 끼운 받기 함수가 바이트를 냈다는 뜻이다(10-23 신고 2건: 운영은 같은 시각 20/20 새 판). 그 함수의 이름·파일을 적어 «서버가 옛 판을 줬다» 로
      읽히지 않게 한다. 판정(지문 대조)은 그대로다."""
    lines = [f"  받은 바이트 {got_bytes:,} · 받은 sha256 {got_sha}"]
    for i, facts in enumerate(seen or []):
        cells = " · ".join(f"{k}={v}" for k, v in facts.items() if v is not None)
        lines.append(f"  응답{i + 1}: {cells}")
    if not seen:
        lines.append("  응답 머리 없음")
    if fetcher is not None and fetcher is not _STOCK_DOWNLOAD:
        code = getattr(fetcher, "__code__", None)
        where = f"{code.co_filename}:{code.co_firstlineno}" if code else "?"
        name = f"{getattr(fetcher, '__module__', '?')}.{getattr(fetcher, '__qualname__', repr(fetcher))}"
        lines.append(f"  받기 함수가 실행기 것이 아니다: {name} ({where}) — 이 바이트는 그 함수가 냈다. 서버는 판마다 다른 주소"
                     f"(경로 끝 = 판 지문)를 준다 — 그 함수가 주소·이름으로 옛 파일을 다시 쓰고 있으면 그 기억을 지우거나 실행기 기본 받기로 돌아가라")
    return "\n".join(lines)


_SFNT_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")


def _user_fonts_dir():
    """사용자 글꼴 폴더 — 영화 리뷰 롱폼 runner_script._user_fonts_dir 와 같은 자리(관리자 권한 없이 쓰는 곳).
    맥 ~/Library/Fonts · 윈도우 %LOCALAPPDATA%\\Microsoft\\Windows\\Fonts."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(base, "Microsoft", "Windows", "Fonts")
    return os.path.expanduser("~/Library/Fonts")


def _is_sfnt(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(4) in _SFNT_MAGIC
    except OSError:
        return False


def _fetch_font_source(src, label, timeout, expected):
    """배포처 하나에서 글꼴 바이트(sfnt)를 받는다 — 원본 지문(source_sha256)·zip 안 이름/지문·woff 변환·글꼴 지문(expected · 첫 배포처만).
    못 받거나 다르면 StepError(무엇을 받았는지 앞부분까지) — 부르는 쪽(fetch_font)이 다음 배포처로 간다."""
    import io
    import hashlib
    url, kind = src["url"], str(src.get("kind") or "")
    source_expected = str(src.get("source_sha256") or "").lower() or None
    item = src
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    resp = _open_retry(req, timeout, label)
    raw = resp.read()
    # ★전송 압축(Content-Encoding)을 푼다(2026-10-14) — urllib 은 풀어 주지 않는다. 한국저작권위원회 공유마당(권리자가 올린 공식 배포처)은
    #   Accept-Encoding 없이도 gzip 으로 보낸다(실측) — 안 풀면 zip 이 아니라 gzip 바이트를 대조·해제해 멈춘다. 지문은 푼 원본에 둔다.
    enc = str((getattr(resp, "headers", None) or {}).get("Content-Encoding") or "").strip().lower()
    if enc == "gzip":
        import gzip  # noqa: PLC0415
        raw = gzip.decompress(raw)
    elif enc not in ("", "identity"):
        raise StepError(f"글꼴 배포처가 모르는 전송 압축({enc})으로 보냈다 — {url} · 관리자에게 알려 주세요.")
    if source_expected and hashlib.sha256(raw).hexdigest() != source_expected:
        ctype = str((getattr(resp, "headers", None) or {}).get("Content-Type") or "")
        final = str(getattr(resp, "url", "") or url)
        head = raw[:240].decode("utf-8", "replace").replace("\n", " ").replace("\r", " ")
        raise StepError(f"받은 원본({len(raw):,}B · {ctype or '종류 없음'} · 최종 주소 {final})의 sha256 이 명세와 다릅니다 — "
                        f"넣지 않았습니다. 받은 내용 앞부분: {head!r}")
    if kind == "zip":
        import zipfile
        member = item.get("member")
        member_sha = str(item.get("member_sha256") or "").lower() or None
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            if member_sha:
                # ★zip 안 이름이 UTF-8 표시 없이 한글이면 파이썬 판마다 다르게 읽힌다(실측: 청도읍성체 zip — 3.11 이하 cp437 글자 깨짐 ·
                #   3.12+ 유니코드 경로 확장칸) — 이름이 아니라 **내용 지문**으로 그 글꼴 하나를 고른다(글꼴 확장자만 · 하나씩 한 번).
                hits = []
                for n in names:
                    if n.lower().endswith((".ttf", ".otf", ".ttc")):
                        body = z.read(n)
                        if hashlib.sha256(body).hexdigest() == member_sha:
                            hits.append(body)
                if len(hits) != 1:
                    raise StepError(f"글꼴 zip 안에서 지문 {member_sha[:16]} 인 글꼴을 {len(hits)}개 찾았다(하나여야 한다) — 배포처가 "
                                    f"파일을 바꿨다. 관리자에게 이 문구를 알려라.")
                data = hits[0]
            elif member not in names:
                raise StepError(
                    f"글꼴 zip 안에 '{member}' 가 없다 — 배포처가 압축 구성을 바꿨다. "
                    f"들어 있는 것: {[n for n in names if not n.endswith('/')][:10]}\n"
                    "  관리자에게 이 문구를 알려라(서버 명세의 fetch.member 를 고쳐야 한다).")
            else:
                data = z.read(member)
    elif kind in ("woff2", "woff"):
        need = ["fonttools>=4,<5"] + (["brotli>=1,<2"] if kind == "woff2" else [])
        try:
            from fontTools.ttLib import TTFont  # noqa: PLC0415
            if kind == "woff2":
                import brotli  # noqa: F401,PLC0415
        except ImportError:
            # ★없으면 이 실행기 파이썬에 공식 PyPI 판을 한 번 깐다(2026-10-17 영화 리뷰 롱폼 longmovie_seed 2건 — 예전에는 사람에게
            #   pip 명령을 시켰다). 못 깔면 그때 사람에게 말한다.
            _pip_install_once(need, f"{kind} 글꼴을 ttf 로 바꾸기")
            try:
                from fontTools.ttLib import TTFont  # noqa: PLC0415
                if kind == "woff2":
                    import brotli  # noqa: F401,PLC0415
            except ImportError as e:
                raise StepError(
                    f"{kind} 글꼴을 ttf 로 바꾸려면 {' '.join(need)} 가 필요한데 자동 설치가 안 됐다 — "
                    f"`\"{sys.executable}\" -m pip install {' '.join(repr(n) for n in need)}` 뒤 다시 하라. 없는 것: {e}") from e
        f = TTFont(io.BytesIO(raw))
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        data = buf.getvalue()
    else:
        data = raw
    if data[:4] not in _SFNT_MAGIC:
        raise StepError(f"받은 것이 글꼴 파일이 아니다({len(data):,}B · 머리글 {data[:4]!r}) — {url} 이 바뀌었을 수 있다.")
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise StepError("공식 글꼴의 해시가 명세와 다릅니다. 기존 파일을 보존합니다. 배포처 변경 여부를 확인하세요.")
    return data


def fetch_font(item):
    """공식 배포처의 글꼴을 **자동으로** 받아 `dest` 에 넣는다 (2026-09-02).

    ★★왜: `auto_download` 글꼴(서울한강 M·리아체·ONE Mobile POP·11번가 고딕)은 재배포
      근거가 없어 팩에 못 넣고 «주소를 받아 풀어라» 라고 **글로만** 시켰다 — 사람이 안 하면
      렌더 직전 «글꼴을 못 찾는다» 로 멈췄다(48h 4명). 받는 방법은 **전부 서버가 준다**
      (url·kind·zip 안 이름·dest) — 실행기는 기본값을 갖지 않는다(§실행기는 껍데기다).
    ★이미 있으면(sfnt 머리글이 맞는 파일) 다시 받지 않는다.
    ★zip 안 이름이 바뀌었으면 **있는 이름을 보여 주고** 멈춘다 — 아무거나 고르면 다른
      웨이트가 조용히 뽑힌다(§5 조용한 실패).
    ★`source_sha256`(2026-10-11 · 갱상도): **받은 원본 바이트**(woff·woff2·zip)의 지문. 다르면 넣지 않고 멈춘다(재시도 없음).
      변환해 다시 쓴 ttf 는 fontTools 판·저장 시각마다 바이트가 달라 `file_sha256` 으로 잴 수 없다 — 그래서 지문은 원본에만 두고,
      설치한 ttf 옆 `<dest>.source-sha256` 에 그 지문을 적어 «같은 원본에서 만든 변환본이 이미 있다»를 판정한다(다시 받지 않는다).
    ★kind `woff`(WOFF1 · zlib)는 fontTools 만 있으면 된다 — brotli 는 woff2 에만 필요하다.
    """
    import io
    import hashlib
    dest = item["dest"]
    expected = item.get("file_sha256")
    # ★배포처 목록(2026-10-15) — 서버가 준 첫 배포처 + `alternates`(같은 글꼴의 다른 공식 배포 주소 · 각자 원본 지문). 첫 배포처가 받아지지 않거나
    #   엉뚱한 바이트를 주면(을유문화사·청도군 — 수강생 PC 에서 840B·390B, 이 맥에서는 정상 · 무엇을 줬는지 기록이 없었다) 그 내용 앞부분을
    #   남기고 다음 배포처로 간다. 같은 주소를 다시 부르지 않는다(재시도 없음 — 배포처마다 한 번).
    sources = [{k: item.get(k) for k in ("url", "kind", "member", "member_sha256", "source_sha256")}]
    sources += [dict(a) for a in (item.get("alternates") or []) if isinstance(a, dict) and a.get("url")]
    for _name, _v in [("file_sha256", expected)] + [("source_sha256", src.get("source_sha256")) for src in sources]:
        if _v and not re.fullmatch(r"[0-9a-fA-F]{64}", str(_v)):
            raise StepError(f"글꼴 {_name}은 SHA-256 64자리여야 합니다")
    expected = str(expected).lower() if expected else None
    known = {str(src["source_sha256"]).lower() for src in sources if src.get("source_sha256")}
    stamp = dest + ".source-sha256"
    if os.path.exists(dest) and os.path.getsize(dest) > 4096 and _is_sfnt(dest):
        if known:
            try:
                with open(stamp, encoding="utf-8") as fh:
                    matches = fh.read().strip().lower() in known
            except OSError:
                matches = False
        else:
            with open(dest, "rb") as existing:
                matches = not expected or hashlib.sha256(existing.read()).hexdigest() == expected
        if matches:
            _progress(f"  [글꼴] {os.path.basename(dest)} 이미 있다 — 건너뜀")
            return dest
    # ★`installed_in: "user_fonts"`(2026-10-16 · 영화 리뷰 롱폼): 이 글꼴은 받은 뒤 사전 점검이 사용자 글꼴 폴더에 **같은 파일 이름으로**
    #   넣는다(없는 것만 · 덮어쓰지 않는다 — runner_script._install_fonts). 그 자리에 이미 있으면 새로 받아도 설치되지 않고 버려진다 —
    #   그런데 작업 폴더마다 13종을 외부 배포처 7곳에서 다시 받아, 영화 한 편마다 그 배포처 장애(10-16 공유마당 503 · 2명)에 그대로 막혔다.
    #   설치 판정과 같은 자(파일 이름 + sfnt 머리글)로 «이미 설치됨» 을 보고 받지 않는다. 글꼴이 맞는지는 파이프라인 글꼴 해석이 nameID·잉크로 잰다.
    if item.get("installed_in") == "user_fonts":
        installed = os.path.join(_user_fonts_dir(), os.path.basename(dest))
        if os.path.isfile(installed) and os.path.getsize(installed) > 4096 and _is_sfnt(installed):
            _progress(f"  [글꼴] {os.path.basename(dest)} 사용자 글꼴 폴더에 이미 설치됨 — 받지 않는다")
            return installed
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    failures, data, used = [], None, None
    for i, src in enumerate(sources):
        try:
            data = _fetch_font_source(src, os.path.basename(dest), int(item.get("timeout") or 300),
                                      expected if i == 0 else None)
            used = src
            break
        except Exception as e:                 # noqa: BLE001 — 배포처 하나의 실패(연결·HTTP·zip·글꼴 해석)는 사유를 모아 다음 배포처로 · 전부 실패하면 모은 사유로 멈춘다
            failures.append(f"  - {src['url']}\n      → {type(e).__name__}: {e}")
            if i + 1 < len(sources):
                _progress(f"  [글꼴] {os.path.basename(dest)}: {src['url']} 에서 못 받았다 — 다음 공식 배포처로 간다")
    if data is None and item.get("fallback_for"):
        # ★대체 글꼴(2026-10-17 · 영화 리뷰 롱폼 회원 2명 — 공유마당 503 한 번에 seed 가 멈췄다): 그 키의 원래 글꼴(산돌)이 깔려 있으면 쓰이지
        #   않는 글꼴이다. 쓰이는지는 파이프라인 글꼴 해석(원래 글꼴 → 대체표)이 판정하고, 필요한데 없으면 거기서 무엇을 받으면 되는지 말한다.
        #   그래서 여기서 받기를 멈추지 않고 사유를 남긴다 — 서버는 다음 발사(longmovie_run)에도 이 항목을 실어 한 번 더 받는다(재시도 루프 없음).
        _progress(f"  [글꼴] 대체 글꼴 {item.get('ass_name') or os.path.basename(dest)}(«{item['fallback_for']}» 원래 글꼴이 없을 때 쓴다)을 "
                  f"공식 배포처 {len(sources)}곳 모두에서 지금 받지 못했습니다 — 받기는 계속합니다:\n" + "\n".join(failures)
                  + "\n  원래 글꼴이 깔려 있으면 상관없습니다. 없으면 영상 글꼴 해석이 알려 주고, 다음 발사에서 다시 받습니다.")
        return None
    if data is None:
        raise StepError(f"글꼴 {item.get('ass_name') or os.path.basename(dest)} 을(를) 공식 배포처 {len(sources)}곳 모두에서 받지 못했습니다:\n"
                        + "\n".join(failures) + "\n  관리자에게 이 문구를 알려 주세요(배포처가 받은 응답 앞부분이 위에 있습니다).")
    source_expected = str(used.get("source_sha256") or "").lower() or None
    import tempfile
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=os.path.dirname(dest) or ".",
                                         prefix=".font-", suffix=".part", delete=False) as fh:
            tmp = fh.name
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        # The handle is closed before replacing, including on Windows.
        os.replace(tmp, dest)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    if source_expected:
        # 설치가 끝난 뒤에 적는다 — 중간에 끊기면 지문이 없어 다음에 다시 받는다(옛 변환본을 «같다»고 오판하지 않는다).
        with open(stamp, "w", encoding="utf-8") as fh:
            fh.write(source_expected + "\n")
    _progress(f"  [글꼴] {item.get('ass_name') or os.path.basename(dest)} → {dest} ({len(data):,}B)")
    return dest


# ★플래그를 **환경변수**에 둔다 — 모듈 전역은 `importlib.reload` 가 되돌린다(같은 프로세스에서
#   두 번 갱신하며 도는 것을 막는다).
_UPDATED_FLAG = "VOLCANO_RUNNER_UPDATED"


def _driver_runs_fp2():
    """이 프로세스에서 단계를 도는 구동기(`volcano_drive` — 스크립트로 떠도 `__main__` 이 그 모듈로 다시 들어간다)가 FP2
    (`status: runner_update` → 설치·재시작)를 처리하는 판인가. 구동기가 없으면(Client 만 쓰는 호출) False."""
    for name in ("volcano_drive", "__main__"):
        mod = sys.modules.get(name)
        if mod is not None and callable(getattr(mod, "_drive_loop", None)):
            return callable(getattr(mod, "_runner_update_restart", None))
    return False


def _token_expiry(token):
    """서명 토큰(`VOLC-U1.<이메일 b64>.<YYYY-MM-DD>[.p][.ta].<서명>`)의 만료일 글자 · 다른 형식이면 None (Z 검토 major)."""
    parts = token.split(".") if isinstance(token, str) else []
    if len(parts) >= 4 and parts[0] == "VOLC-U1" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[2]):
        return parts[2]
    return None


def _self_update_dir(workdir=None):
    """`self_update` 가 설치할 runner/ — 링크를 **풀지 않은** 자리 (2026-10-05 · Z ③ · B 검토 2회차 minor ②).

    예전에는 `os.path.dirname(os.path.abspath(__file__))` 였다. 파이썬은 스크립트 폴더의 링크를 풀어 모듈을 읽으므로
    (맥 실측 — `sys.path[0]` 가 공용 원본), runner/ 가 공용 폴더로 이어진 링크면 그 자리가 **공용 원본**이 되어 설치가
    다른 작업 폴더의 실행기까지 COW 없이 바꿨다. 구동기의 재개 명령(`volcano_drive._drive_script_path`)과 같은 계약으로:
      ① 이 실행이 다룬 작업 폴더를 알면 그 runner/ — 있으면 그것(링크면 설치기가 연결만 바꾸는 COW 를 한다), **없으면 그 자리에
         새로** 만든다(FP2 `_runner_update_restart` 와 같은 자리). 이 프로세스는 다른 폴더의 코드로 떠 있으므로 `self_update` 가
         설치 뒤 `RunnerRelocated`(다시 띄울 명령)로 멈춘다.
      ② 작업 폴더를 모르면 실행한 스크립트 경로(sys.argv[0] — 링크가 안 풀린 채 남는다)의 폴더 — 그 폴더가 이 모듈과 같은 실체일 때만
      ③ 그 밖(함수로 부른 실행기 등)은 이 모듈의 폴더(예전 그대로)
    ★①의 «없으면 새로» (2026-10-06 · Z 검토 3회차 minor): 예전에는 작업 폴더에 runner/ 가 없으면 ②③으로 넘어가, 작업 폴더 밖
      공용 runner 로 새 작업 폴더를 돌린 실행기가 그 **공용 폴더를 제자리에서** 바꿨다(그 폴더를 쓰는 다른 프로세스 확인 없이 ·
      검토 실험 exp_outside_noworkrunner: 공용 폴더 식별값이 새 판으로 바뀌고 작업 폴더 runner/ 는 없는 채). 작업 폴더를 모를
      때만(②③) 예전처럼 실행한 폴더를 바꾼다.
    """
    if isinstance(workdir, str) and os.path.isabs(workdir):
        return os.path.join(workdir, 'runner')
    here = os.path.dirname(os.path.abspath(__file__))
    script = sys.argv[0] if sys.argv and isinstance(sys.argv[0], str) else ''
    if os.path.basename(script) == 'volcano_drive.py':
        launched = os.path.dirname(os.path.abspath(script))
        try:
            if os.path.realpath(launched) == os.path.realpath(here):
                return launched
        except OSError:
            pass
    return here


class RunnerRelocated(StepError):
    """새 실행기를 설치했지만 이 프로세스가 그 폴더의 코드를 다시 읽을 수 없다 — 사람이 새 실행기로 다시 띄운다.

    (2026-10-06 · Z 검토 2회차 minor) 설치 자리(`_self_update_dir`)와 이 모듈이 읽힌 폴더(`__file__` — 파이썬이 링크를 푼
    실경로)가 설치 뒤 다른 실체면 `importlib.reload` 는 **옛 파일**을 다시 읽는다(작업 폴더 밖 공용 runner 로 다른 작업
    폴더를 돌린 경우 — 그 작업 폴더에 runner/ 가 없었으면 새로 만든 경우도(Z 검토 3회차) · 연결 runner/ 를 COW 로 떼어 낸
    경우). 예전에는 그래도 «새 코드로 이어간다» 고 말하고 옛 코드로 계속 돌았고, `_UPDATED_FLAG` 가 그 프로세스의 재갱신까지
    막았다. 이 실행이 다룬 작업 폴더를 알면 작업 폴더 밖 공용 폴더는 바꾸지 않는다 — 설치는 그 작업 폴더의 runner/ 다
    (`_self_update_dir` ① · 모를 때만 예전처럼 실행한 폴더).
    """


def self_update(item, client=None):
    """서버가 «옛 실행기» 라며 준 새 팩으로 **자기 코드를 갈아끼운다** (2026-09-02).

    ■ 왜
        서버 코드는 배포하면 그 순간 전원에게 적용되는데, 수강생 PC 의 실행기는 새 판의
        `assets` 에서만 다시 받았다 — 도중에 스스로 갱신하는 길이 없어 48h 실행기 사용자
        93명 중 89명이 옛 팩이었다(이미 고친 결함을 계속 밟는다). 서버가 `_meta.runner_update`
        (열쇠 URL·sha256·파일 수)를 주면 여기서 받아 검증하고 **이 폴더의 파일**을 바꾼 뒤
        모듈을 다시 읽는다. 구동기는 다음 단계부터 새 코드로 이어간다(`_drive_loop`).
    ■ 지키는 것
        · sha256·파일 수가 서버 선언과 같을 때만 바꾼다(다른 팩·깨진 팩은 그대로 둔다)
        · safe installer에서 전 파일을 준비한 뒤 폴더를 교체한다. 공용 원본은 읽기만 한다
        · 한 프로세스에서 **한 번만** — 갱신 뒤에도 서버가 옛것이라 하면(명세 미동기)
          같은 일을 되풀이하지 않고 그 사실을 말한다
    돌려주는 것: 바꿨으면 True, 건너뛰었으면 False. 실패는 StepError.
    """
    import hashlib
    import importlib
    import tarfile
    import tempfile
    if os.environ.get(_UPDATED_FLAG):
        _progress("  [실행기] 이 프로세스에서 이미 한 번 갱신했다 — 서버가 아직 옛것이라 하면 "
              "명세와 팩이 어긋난 것이다. 관리자에게 알려라.")
        return False
    missing = []
    for module in item.get("required_modules") or []:
        try:
            importlib.import_module(module)
        except Exception:
            missing.append(module)
    if missing:
        raise StepError("새 실행기의 필수 모듈이 없습니다: %s. 기존 코드로 작업을 계속하지 않습니다.\n%s\n"
                        "준비한 Python으로 같은 작업을 재시작하세요." %
                        (", ".join(missing), item.get("environment_fix") or "env 단계를 다시 확인하세요."))
    here = _self_update_dir(getattr(client, '_last_workdir', None))
    url = str(item["url"])
    if url.startswith("/") and client is not None:
        url = client.url.rstrip("/") + url
    with tempfile.TemporaryDirectory() as td:
        tgz = os.path.join(td, "runner.tar.gz")
        with download_seen() as seen:
            download(url, tgz, headers=({"Authorization": f"Bearer {client.token}"}
                                         if client is not None and getattr(client, "token", None) else None),
                     resume=True)           # 우리 서버의 실행기 팩 — 끊기면 이어받는다(SR-19 ②)
        with open(tgz, "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        if got != item["sha256"]:
            raise StepError(f"새 실행기 팩 sha256 불일치 — 받은 것 {got} ≠ 선언 {item['sha256']}. 바꾸지 않았다.\n"
                            + asset_mismatch_facts(seen, os.path.getsize(tgz), got, fetcher=download))
        with tarfile.open(tgz) as t:
            files = [m for m in t.getmembers() if m.isfile()]
            want_n = int(item.get("n_files") or 0)
            if want_n and len(files) != want_n:
                raise StepError(f"새 실행기 팩 파일 수 불일치 — {len(files)} ≠ 선언 {want_n}. 바꾸지 않았다.")
            # ★설치는 구동기의 **한 자리** `install_runner_files` 다 (2026-10-05 · 원장 W2-08·W2-10 · 묶음 사이 약속 —
            #   B 묶음이 만든다): 파일 단위 원자 교체(윈도우에서 남이 runner/ 를 쥐고 있어도 WinError 32 로 안 죽는다) ·
            #   옛 pyc 정리 · 서버가 선언한 runner_id 를 설치 **전후**로 대조. 예전 `install_runner_pack` 은 폴더 통째 교체였다.
            from volcano_drive import install_runner_files  # noqa: PLC0415
            try:
                changed = install_runner_files(t, here, expect_id=item.get("runner_id") or None)
            except StepError:
                raise
            except Exception as error:
                raise StepError("새 실행기 설치 준비 실패; 기존 파일을 바꾸지 않았습니다: %s" % error) from error
    module_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        same = os.path.normcase(os.path.realpath(here)) == os.path.normcase(os.path.realpath(module_dir))
    except OSError:
        same = False
    if not same:
        wd = getattr(client, '_last_workdir', None)
        if not (isinstance(wd, str) and wd) and os.path.basename(os.path.normpath(here)).lower() == 'runner':
            wd = os.path.dirname(os.path.normpath(here))     # 설치 자리가 <작업 폴더>/runner 다
        command = '"%s" "%s"' % (sys.executable, os.path.join(here, "volcano_drive.py"))
        if isinstance(wd, str) and wd:
            command += ' --workdir "%s"' % wd
        raise RunnerRelocated("새 실행기를 %s 에 설치했습니다(%d개 파일). 이 프로세스는 다른 폴더(%s)의 옛 코드로 떠 있어 "
                              "새 코드로 이어 갈 수 없습니다 — 다음 명령으로 다시 실행하세요(진행은 작업 폴더에 남아 있어 "
                              "이어집니다): %s" % (here, len(changed), module_dir, command))
    os.environ[_UPDATED_FLAG] = "1"
    for mn in ("volcano_run", "volcano_drive"):
        m = sys.modules.get(mn)
        if m is not None:
            importlib.reload(m)
    _progress(f"  ★ 실행기를 새 팩으로 갱신했다({len(changed)}개 파일: {', '.join(changed)[:120]}) — "
          "다음 단계부터 새 코드로 이어간다", flush=True)
    return True


def http_headers(headers):
    """HTTP 헤더로 쓸 수 있는 것만 남긴다 — **값이 문자열인 것**.

    ★구동기 `headers` 는 자격증명 보따리로도 쓰인다(전사 키 등). 그걸 그대로 urllib 에
      넘기면 `expected string or bytes-like object, got 'dict'` 로 죽는데, 재시도 루프가
      그 예외를 삼켜 **나중에 엉뚱한 ffmpeg "파일 없음"** 으로 튀어나온다(실측 2026-08-08).
    """
    return {k: v for k, v in (headers or {}).items() if isinstance(v, str)}


class ApiRefused(Exception):
    """바깥 서비스가 **그만 보내라**고 답했다 — 다시 던지면 안 되는 갈래.

    ★`code` 와 `retry_after` 를 들고 다닌다. 부르는 쪽이 이걸 보고 **멈춘다.**
      예전에는 그냥 Exception 이라 429 도 네트워크 끊김과 똑같이 재시도됐고,
      그것이 수강생 계정 5개를 정지시킨 그 동작이다(2026-08-15).
    """

    def __init__(self, code, msg, retry_after=None):
        super().__init__(msg)
        self.code = int(code)
        self.retry_after = retry_after


def post_bytes(endpoint, body, headers, out, timeout=120):
    """응답 본문을 그대로 파일로 저장한다(TTS 오디오).

    ★HTTP 오류를 **갈래로** 올린다 — 4xx 는 `ApiRefused`, 그 밖은 그대로.
      부르는 쪽이 "다시 던져도 되는가" 를 판정할 수 있어야 한다.
    """
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
                                 headers=dict(http_headers(headers),
                                              **{"Content-Type": "application/json",
                                                 "User-Agent": _UA}))
    try:
        data = urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read()[:300].decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        finally:
            e.close()
        raise ApiRefused(e.code, f"HTTP {e.code} {detail}".strip(),
                         e.headers.get("Retry-After")) from e
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(data)
    return len(data)


def _retry_gate(exc, policy):
    """다시 던져도 되는가 — **서버가 준 정책**으로만 판정한다.

    돌려주는 것: `(다시_던질까, 멈출_때_할_말)`

    ★`policy` 가 없으면 **멈춘다.** 예전 기본값(모두 재시도)으로 떨어지면
      정책을 고쳐도 안 따라오고, 그 상태가 바로 이번 사고였다(§fail-closed).
    """
    p = policy or {}
    ok = [int(x) for x in (p.get("retry_status") or [])]
    # ★`ApiRefused` 든 날것 `HTTPError` 든 **같은 자로 본다** — 한쪽만 보면
    #   다른 경로(이미지 생성)가 옛 동작으로 남는다(실제로 그렇게 갈려 있었다).
    code = getattr(exc, "code", None)
    if code is None:
        return True, None                      # 네트워크·타임아웃 — 일시 장애다
    code = int(code)
    if code in ok:
        return True, None
    note = (p.get("stop_note") or {}).get(str(code))
    if not note:
        note = (f"이 서비스가 HTTP {code} 로 답했습니다. "
                "다시 시도해도 같은 답이 옵니다 — 사람이 고쳐야 합니다.")
    # ★`Retry-After` 는 **한도 갈래에서만** 뜻이 있다. 401·422 에 붙이면
    #   "기다리면 되는 일" 로 읽혀 수강생이 그냥 기다린다(키를 고쳐야 하는데).
    if code in (429, 403) and getattr(exc, "retry_after", None):
        note += f" (서비스가 {exc.retry_after}초 뒤에 다시 오라고 했습니다.)"
    return False, note


# ★★텍스트 파이프의 **인코딩을 플랫폼에 맡기지 않는다** (2026-08-12, 한국어 윈도우 실물).
#
#   `text=True` 만 쓰면 파이썬은 `locale.getpreferredencoding(False)` 로 디코딩한다 —
#   한국어 윈도우에서는 **cp949** 다. 그런데 ffmpeg 은 경로·글꼴 이름을 **UTF-8** 로
#   내보낸다. 작업 폴더나 글꼴에 한글이 있으면 디코딩이 터지고, 그러면 파이프를 읽던
#   스레드가 죽어 **`p.stderr` 가 None** 이 된다. 실제로 `measure_lufs` 가
#   `'NoneType' object has no attribute 'splitlines'` 로 죽었다.
#
#   ★고치는 방식이 `_write` 의 CRLF 와 같다 — **플래그를 자리마다 붙이지 않는다.**
#     붙이는 것을 잊을 수 있으면 언젠가 잊는다. 여기 한 곳에 선언하고 전부 이걸 쓴다.
#   ★`errors="replace"` 인 이유: 측정·판정은 우리가 찾는 ASCII 토큰(`I:`,
#     `pts_time:`)으로 하는데, 그 옆에 못 읽는 바이트가 있다고 **전체가 죽으면 안 된다.**
#     한 글자가 `?` 가 되는 것과 파이프가 통째로 죽는 것은 다른 무게다.
TEXT_PIPE = {"text": True, "encoding": "utf-8", "errors": "replace"}


_NOT_A_PATH = ("pipe:", "concat:", "http://", "https://", "rtmp://", "lavfi", "-")


def missing_inputs(argv):
    """argv 의 `-i <경로>` 가운데 **지금 없는 파일**. 경로가 아닌 입력(lavfi·pipe·URL·
    `%03d` 연번·글롭)은 판정하지 않는다.

    ★★왜 (2026-09-02 · 48h 162건·9명): 윈도우 ffmpeg 는 이름에 한글이 든 **없는** 파일을
      «Illegal byte sequence» 라고 말한다 — `win32_open` 이 `_wsopen` 실패 뒤 ANSI 로
      한 번 더 열어 보며 EILSEQ 로 덮기 때문이다(공식 소스 libavutil/file_open.c). 사람은
      그 말을 «인코딩 문제» 로 읽고 엉뚱한 곳을 고친다. 없는 파일은 **없다고** 말한다.
    """
    out, prev = [], None
    for a in argv or []:
        if prev == "-i":
            s = str(a)
            looks_path = ("/" in s or "\\" in s or os.path.splitext(s)[1]) and "%" not in s \
                and "*" not in s and "?" not in s and not s.startswith(_NOT_A_PATH) \
                and not ("=" in s and "/" not in s and "\\" not in s)
            if looks_path and not os.path.exists(s):
                out.append(s)
        prev = a
    return out


def _missing_msg(argv, miss):
    return ("입력 파일이 없습니다: " + " · ".join(miss) + "\n"
            f"  `{argv[0]}` 이 읽으려는 파일이 아직 없거나 다른 자리에 있습니다. "
            "앞 단계가 만들었어야 할 파일이면 그 단계부터 다시 하세요. "
            "(윈도우 ffmpeg 는 이름에 한글이 있는 없는 파일을 «Illegal byte sequence» 라고 "
            "말합니다 — 인코딩 문제가 아니라 파일이 없다는 뜻입니다)")


# ── ★윈도우에서 자식을 띄우는 자리 — **한 곳** (2026-09-05) ─────────────
#
# ■ 왜 한 곳인가
#     같은 병을 부르는 자리마다 고치면 **반드시 하나가 빠지고 빠진 그 갈래만**
#     윈도우에서 죽는다(§CLAUDE.md 「부르던 아홉 자리를 전부 그리로」).
#     `run_argv` 를 지나는 호출이 25곳이라 여기 한 번 세우면 전부 덮인다.
#
# ■ 무엇을 막나 — 서버 로그 실물에서 나온 둘이다
#     ① `[WinError 2] 지정된 파일을 찾을 수 없습니다` **한 줄만** 나가고 어느
#        프로그램이 없는지 한 글자도 없었다. 수강생은 고칠 수가 없다.
#        실측: 인물형 `person_clips` 2026-09-05 00:37 · 린박스 `start` 09-04 13:18
#        (둘 다 `volcano_run.py:run_argv` → `subprocess.run`).
#        ★`do` 항목 갈래(`volcano_drive.py`)에는 이 문이 **이미 있었다** —
#          `run_argv` 갈래만 빠져 있었다. 그래서 문을 옮기는 게 아니라 **여기 세운다**.
#     ② 자식이 cp949 로 찍어 우리가 utf-8 파이프로 받으면 **글자가 깨진다.**
#        실측: 쇼핑 `shop_footage` 09-04 `UnicodeEncodeError: 'cp949'` ·
#        롱폼 「사전 점검에서 0건이 걸렸습니다」(09-05 3건·2명 — 점검 JSON 이 깨져
#        **진짜 실패 항목이 하나도 안 보이던** 그 사고. 수강생이 원인과 처방을
#        직접 적어 보냈다: *"PYTHONIOENCODING=utf-8 을 주니 그제야 진짜 원인이 나왔다"*).
#        기록도 같은 말을 한다 — `pipeline-portability-env.md` 15-201:
#        「윈도우는 **`PYTHONUTF8=1` 필수**」.
#
# ■ ★맥은 한 글자도 안 바뀐다 (증명 가능하게 만든 것)
#     · 환경변수는 `os.name == "nt"` 에서만 얹는다 → 맥/리눅스는 `env=None` 그대로다.
#     · 도구 문은 **없을 때만** 던진다. 있으면 하던 대로 `subprocess.run` 이다.
#     · `.cmd` 감싸기도 nt 전용이고, 감싸지 않으면 **100% 실패하던** 자리에만 닿는다.
#
# ■ ★argv 를 고치는 것 아닌가
#     아니다. 서버가 준 argv 는 그대로 간다. nt 에서 `.cmd`/`.bat` 인 경우에만
#     `COMSPEC /c` 로 **감싼다** — CreateProcess 가 확장자 없는 이름도, `.cmd` 도
#     못 열기 때문이다(그 자리는 지금 예외 없이 죽는다). 맥에는 그 갈래가 없다.
_WRAP_EXT = (".cmd", ".bat")


def _resolve_tool(tool):
    """이 기계에서 그 도구가 **정말 도는 모양**을 돌려준다. 못 찾으면 None.

    ★「있는가」가 아니라 「도는가」다 — 윈도우의 npm 도구는 `.cmd` 셸 스크립트라
      `shutil.which` 는 **찾아 주는데** CreateProcess 는 못 연다. 그래서 찾은 뒤
      확장자를 보고 감쌀지 정한다(§moon `winexec.py` 와 같은 판단·같은 이유).
    """
    t = str(tool)
    if os.path.isabs(t) and os.path.exists(t):
        found = t
    else:
        found = shutil.which(t)
    if (os.name == "nt" and t.lower() in ("python", "python3", "python.exe", "python3.exe") and sys.executable
            and (not found or "\\windowsapps\\" in os.path.normcase(found))):
        # ★윈도우의 `python`·`python3` 이 없거나 스토어 별칭(WindowsApps 0바이트 스텁 · 돌리면 «Python was not found» rc=9009)이면
        #   이 실행기가 지금 도는 파이썬으로 띄운다(2026-10-17 플리 pli_check 2건). 맥·리눅스와 실제 설치본은 그대로 둔다.
        return [sys.executable]
    if not found:
        return None
    if os.name != "nt":
        # ★★맥·리눅스는 **원래 글자 그대로** 돌려준다 — 찾았다는 사실만 쓰고 argv 는
        #   한 글자도 안 바꾼다. `shutil.which` 와 `execvp` 는 같은 PATH 규칙이라
        #   결과는 같지만, 「고른 것과 도는 것이 같다」를 **값으로** 보장하려면
        #   바꾸지 않는 쪽이 옳다(§CLAUDE.md 「실행기가 명령을 지으면 결과가 갈린다」).
        return [t]
    if os.path.splitext(found)[1].lower() in _WRAP_EXT:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", found]
    return [found]


_PIP_TRIED = {}


def _pip_install_once(specs, why):
    """이 실행기 파이썬에 공식 PyPI 패키지를 깐다 — 같은 묶음은 이 프로세스에서 한 번만(상한 600초). 결과는 bool."""
    key = tuple(specs)
    if key in _PIP_TRIED:
        return _PIP_TRIED[key]
    _progress(f"  · [{why}] 필요한 파이썬 부품이 없어 공식 PyPI 판({' '.join(specs)})을 이 실행기 파이썬에 설치합니다", flush=True)
    try:
        done = _spawn([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", *specs],
                      capture_output=True, timeout=600, **TEXT_PIPE)
        ok, tail = done.returncode == 0, err_gist(done.stderr or done.stdout, 200)
    except (OSError, subprocess.SubprocessError) as exc:
        ok, tail = False, f"{type(exc).__name__}: {exc}"[:200]
    if ok:
        import importlib                                            # noqa: PLC0415
        importlib.invalidate_caches()
    else:
        _progress(f"  ⚠ [{why}] 설치하지 못했습니다: " + tail.strip().replace("\n", " "), flush=True)
    _PIP_TRIED[key] = ok
    return ok


def _is_ytdlp(tool):
    base = os.path.basename(str(tool)).lower()
    return base in ("yt-dlp", "yt-dlp.exe", "yt-dlp.cmd", "yt-dlp.bat")


#: yt-dlp 가 유튜브 JS 도전 과제를 풀 런타임 — 기본으로 켜진 것은 Deno 뿐이다(공식 https://github.com/yt-dlp/yt-dlp/wiki/EJS
#: «Deno (recommended) Enabled by default · Node Enable with --js-runtimes node»). Deno 를 PATH 에 두면 argv 를 한 글자도
#: 바꾸지 않고(run_argv 계약) 유튜브가 풀린다. 없으면 Deno 저자들의 공식 PyPI 재배포판(https://pypi.org/project/deno/ ·
#: «Python redistribution of Deno binaries» · the Deno authors)을 이 실행기 파이썬에 한 번 깐다(볼케이노 uv 설치와 같은 길).
_DENO_PIP_SPEC = "deno>=2,<3"
_DENO_DIR = {}


def _deno_dir_for(env):
    """Deno 실행 파일이 든 폴더 — PATH 에 이미 있으면 None(할 일 없음). 이 프로세스에서 한 번만 판정·설치한다."""
    path = (env or os.environ).get("PATH", "")
    if shutil.which("deno", path=path):
        return None
    if "dir" in _DENO_DIR:
        return _DENO_DIR["dir"]
    import sysconfig
    scripts = sysconfig.get_path("scripts")
    found = shutil.which("deno", path=scripts) if scripts else None
    if not found:
        # 2026-10-17 실행기 중단 보고(유튜브 403 «unable to download video data» 20건·10명) — 최신 yt-dlp(2026.10.10)로
        # 갱신해도 403 이었다. 일부 보고는 «No supported JavaScript runtime could be found. Only deno is enabled by default» 를
        # 함께 남겼다: 유튜브 영상 데이터는 JS 도전 과제를 풀어야 받는다(EJS). 한 번만 깔고, 못 깔면 말하고 그대로 돈다.
        _progress("  · [yt-dlp] 유튜브 JS 풀이용 Deno 가 없어 공식 PyPI 판(" + _DENO_PIP_SPEC + ")을 이 실행기 파이썬에 설치합니다", flush=True)
        try:
            done = _spawn([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", _DENO_PIP_SPEC],
                          capture_output=True, timeout=600, **TEXT_PIPE)
            ok = done.returncode == 0
            why = err_gist(done.stderr or done.stdout, 300)
        except (OSError, subprocess.SubprocessError) as exc:
            ok, why = False, f"{type(exc).__name__}: {exc}"[:300]
        found = shutil.which("deno", path=scripts) if ok and scripts else None
        if not found:
            _progress("  ⚠ [yt-dlp] Deno 를 설치하지 못했습니다 — 유튜브가 403 으로 막으면 https://deno.com 에서 Deno 를 설치하세요. "
                      + why.strip().replace("\n", " ")[:200], flush=True)
    _DENO_DIR["dir"] = os.path.dirname(found) if found else None
    return _DENO_DIR["dir"]


def _ytdlp_runtime_env(env):
    """yt-dlp 자식 환경에 Deno 폴더를 PATH 앞에 둔다(없을 때만 · argv 불변)."""
    folder = _deno_dir_for(env)
    if not folder:
        return env
    base = dict(env if env is not None else os.environ)
    base["PATH"] = folder + os.pathsep + base.get("PATH", "")
    return base


def _child_env():
    """자식에게 물려줄 환경. **윈도우에서만** UTF-8 을 강제한다.

    ★왜 캡처하는 자리에서만 해도 되나 — 여기를 지나는 자식은 전부
      `capture_output=True`(파이프)다. 콘솔로 바로 찍는 자식이 아니므로
      「옛 콘솔에서 한글이 깨진다」(`_console_never_dies` 머리말의 그 걱정)에
      닿지 않는다. 우리 파이프는 utf-8 이니 자식도 utf-8 이어야 짝이 맞는다.
    """
    if os.name != "nt":
        return None                      # ★맥·리눅스는 손대지 않는다
    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


#: 맥 Homebrew 의 libass 든 ffmpeg 실행 파일(`ffmpeg-full` · keg-only라 PATH 에 안 붙는다). 앞에 있는 것이 먼저다.
#: 실행 파일 자리를 통째로 적는다 — 이 실행기는 ffmpeg 이름으로 명령을 짓지 않는다(argv 는 서버가 준다 · 여기는 그 bin 폴더를 PATH 앞에 둘 뿐).
_FULL_FFMPEG_BINS = ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg")


def _prefer_full_ffmpeg():
    """맥에서 `ffmpeg-full` 이 깔려 있으면 그 bin 을 PATH 맨 앞에 둔다 (멱등 · 2026-10-17).

    ★왜: brew 의 기본 `ffmpeg`(9.x)는 libass 없이 나와 자막을 얹는 렌더가 'No such filter: ass' 로 죽는다 — libass 든 판은
      keg-only 인 `ffmpeg-full` 이라 깔아도 PATH 에 안 붙는다(env «자막 필터가 없습니다» 맥 2명 · 한 명은 이미 깔아 두었다).
      서버 argv 는 `ffmpeg` 이름 그대로다(실행기가 argv 를 고치지 않는다) — PATH 순서만 정해 env 측정·렌더가 **같은 판**을 본다.
      자식은 이 프로세스의 환경을 물려받는다(맥 `_child_env` 는 None). 윈도우·리눅스는 손대지 않는다.
    ★매 실행 앞에서 본다 — env 가 이 실행 도중 `brew install ffmpeg-full` 을 했으면 그 다음 명령부터 잡힌다."""
    if sys.platform != "darwin":
        return
    parts = os.environ.get("PATH", "").split(os.pathsep)
    for exe in _FULL_FFMPEG_BINS:
        if os.path.isfile(exe):
            d = os.path.dirname(exe)
            if parts[:1] != [d]:
                os.environ["PATH"] = os.pathsep.join([d] + [x for x in parts if x != d])
            return


#: 실행기가 띄우는 서버 스크립트(쇼핑 master.py 등)·엔진 팩이 같은 인코더 판정(runner/video_encoder.py)을 쓰도록
#: 실행기 폴더를 자식 환경에 남긴다(맥·리눅스 자식은 os.environ 을 물려받고, 윈도우 `_child_env` 도 그것을 복사한다).
os.environ["VOLCANO_RUNNER_DIR"] = os.path.dirname(os.path.abspath(__file__))


def _video_encoder():
    """영상 인코더 자리(`@VENC@` · 서버 `volcano_venc.slot`)를 채우는 한 곳 — PC 마다 1초 시험 굽기로 고른다."""
    import video_encoder                                           # noqa: PLC0415
    video_encoder.configure(
        run=lambda a: _spawn(a, capture_output=True, timeout=video_encoder.PROBE_TIMEOUT, **TEXT_PIPE),
        head=_resolve_tool, log=lambda s: _progress(s, flush=True))
    return video_encoder


def _spawn_encode(argv, kw):
    """인코더 자리가 든 명령 — 이 PC 의 GPU 로 한 번, 실패하면 서버가 준 CPU 인자로 **한 번만** 다시 굽는다(상한 2회)."""
    venc = _video_encoder()
    tries = venc.attempts(argv)
    for gpu, cmd in tries:
        if gpu:
            with venc.gpu_slots:
                done = _spawn(cmd, **kw)
        else:
            done = _spawn(cmd, **kw)
        done.venc = gpu
        done.venc_fallback = gpu is None and len(tries) > 1
        if done.returncode == 0 or gpu is None:
            return done
        err = done.stderr.decode("utf-8", "replace") if isinstance(done.stderr, bytes) else (done.stderr or "")
        venc.failed(gpu, err or f"종료 코드 {done.returncode}")
    # 여기 닿으면 `video_encoder.attempts` 계약(마지막 시도 = 서버가 준 CPU 인자 · gpu None → 위에서 돌려준다)이 깨진 것이다.
    raise RuntimeError("video_encoder.attempts 가 CPU 시도로 끝나지 않았다: %r" % ([g for g, _ in tries],))


def _spawn(argv, *, popen=False, **kw):
    """도구 문 + 윈도우 UTF-8 을 한 번에 씌워 자식을 띄운다."""
    argv = list(argv or [])
    if any(isinstance(a, str) and a.startswith("@VENC@") for a in argv):
        _prefer_full_ffmpeg()             # 판정 기억의 키(ffmpeg 실경로)가 실제로 돌 판을 가리키게
        if popen:
            raise StepError("영상 인코더 자리(@VENC@)가 든 명령은 파이프로 띄우지 않는다 — 서버 응답을 확인하라.")
        return _spawn_encode(argv, kw)
    if not argv:
        raise StepError("실행할 명령이 비어 있다 — 서버 응답의 argv 를 확인하라.")
    _prefer_full_ffmpeg()
    ytdlp = _is_ytdlp(argv[0])
    head = _YTDLP_MODULE.get("head") if ytdlp and _YTDLP_MODULE.get("head") else _resolve_tool(argv[0])
    if head is None and ytdlp:
        head = _ytdlp_module_head("이 컴퓨터에 yt-dlp 가 없음")
    if head is None:
        raise StepError(
            f"'{argv[0]}' 을(를) 이 컴퓨터에서 찾지 못했다 — 이 단계에 필요한 프로그램이다.\n"
            "  설치돼 있는데 이 말이 나오면 PATH 에 없는 것이다(설치 뒤 터미널을 새로 여세요).\n"
            "  `env` 단계가 무엇이 없는지 알려준다 — 설치한 뒤 그 단계부터 다시 하세요.")
    # ★여기만 **날 것**이다 — 이 줄이 `_spawn` 이 되면 무한재귀다(실제로 한 번 그랬다).
    child_env = kw.pop("env", None)
    if child_env is None:
        child_env = _child_env()
    elif os.name == "nt":
        child_env = dict(child_env, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    # The parent's pipe decoder is independent of the child's UTF-8 environment.
    # Apply the same text contract to every tool; binary ffmpeg pipes stay bytes.
    if kw.get("text") or kw.get("universal_newlines"):
        kw.setdefault("encoding", TEXT_PIPE["encoding"])
        kw.setdefault("errors", TEXT_PIPE["errors"])
    if os.name == "nt":
        # ★윈도우 자식은 실행기의 콘솔을 물려받지 않고 제 숨은 콘솔로 띄운다(실행기 공용 규약 `agy_transport_proc.launch_kwargs` 그대로 —
        #   CREATE_NO_WINDOW + 표준 핸들은 부모 것을 명시). 2026-10-23 win-main 실측(scratchpad p142c): 실행기가 붙어 있던 콘솔(conhost)이
        #   사라진 뒤 물려받기로 띄운 자식은 **전부 즉시** 0xC0000142(STATUS_DLL_INIT_FAILED)·출력 0 으로 끝나고(10번 중 10번 · 다시 띄워도 같다),
        #   CREATE_NO_WINDOW 자식은 10번 다 정상이었다. 수강생 보고 1주 26건·16명이 전부 «시작 7초 뒤»(옛 재시도 2+5초를 다 써도 실패)였던 까닭이다.
        #   같은 실측에서 동시 600개(자식마다 conhost 하나)도 0xC0000142 없이 돌았다(p142b). 떼어 띄우는(DETACHED) 호출은 그 뜻 그대로 둔다.
        import agy_transport_proc as _proc                        # noqa: PLC0415
        kw = _proc.launch_kwargs(kw, detached=bool((kw.get("creationflags") or 0) & _proc.DETACHED_PROCESS))
    if _is_ytdlp(argv[0]):
        child_env = _ytdlp_runtime_env(child_env)
    command = head + argv[1:]
    if os.name == 'nt' and len(head) == 3 and head[1] == '/c':
        # cmd removes its outer /s /c quotes, then the batch shim forwards %*.
        # Encode both parser passes; CreateProcess list quoting alone changes
        # percent/caret data and strips a spaced executable's opening quote.
        meta = re.compile(r'([()\[\]%!^"`<>&|;, *?])')
        def escaped(value):
            return meta.sub(r'^\1', value)
        def argument(value):
            value = str(value)
            if any(c in value for c in '\r\n\0'):
                raise StepError('Windows 배치 실행 인수에는 줄바꿈이나 NUL을 넣을 수 없습니다. 본문은 stdin으로 전달하세요.')
            value = re.sub(r'(\\*)"', lambda m: m[1] * 2 + '\\"', value)
            value = re.sub(r'(\\+)$', lambda m: m[1] * 2, value)
            return escaped(escaped('"' + value + '"'))
        line = ' '.join([escaped(os.path.normpath(head[2])), *(argument(v) for v in argv[1:])])
        command = subprocess.list2cmdline(head[:1]) + ' /d /s /v:off /c "' + line + '"'
    if popen:
        return subprocess.Popen(command, env=child_env, **kw)
    done = subprocess.run(command, env=child_env, **kw)
    why = _ytdlp_switch_reason(done) if ytdlp and done.returncode and head != _YTDLP_MODULE.get("head") else None
    if why and _ytdlp_module_head(why):
        # ★이 컴퓨터의 yt-dlp 가 깨졌거나(«No module named 'yt_dlp'» · 2026-10-17 린박스 start 2건) 옛 판이라 유튜브가 막으면
        #   («unable to download video data: HTTP Error 403» · 정치·쇼핑 start 10명 · 신고 #211 — 2026.08.19 판) 사람에게
        #   «winget/brew 로 갱신하라» 고 멈추지 않고, 실행기 파이썬에 공식 최신 판을 한 번 올려 같은 인자로 **한 번만** 다시 받는다
        #   (리센느 c7aa976b 와 같은 방법 · 인자는 그대로 · 머리만 바뀐다). 못 올리면 원래 실패를 그대로 돌려준다.
        _progress(f"  ↻ [yt-dlp] {why} — 실행기 파이썬의 최신 yt-dlp 로 한 번 다시 받습니다", flush=True)
        done = subprocess.run([*_YTDLP_MODULE["head"], *argv[1:]], env=child_env, **kw)
    return done


#: 실행기 파이썬 모듈로 돌리는 yt-dlp 머리 — 한 번 올린 뒤로는 이 프로세스의 yt-dlp 를 전부 이 머리로 부른다
#:   (옛 판이 같은 403 을 유튜브에 또 받으러 가지 않게). 공식 판 = PyPI yt-dlp[default](풀이 스크립트 yt-dlp-ejs 포함 ·
#:   https://github.com/yt-dlp/yt-dlp/wiki/EJS «pip install -U "yt-dlp[default]"»).
#: ★10-19 nightly(`--pre`): yt-dlp README «Release channels» — stable 은 «often "stale" and prone to external breakage»,
#:   nightly 는 «the **recommended channel for regular users**» · pip 설치 명령 그대로 `python -m pip install -U --pre "yt-dlp[default]"`.
#:   win-01 실측: 설치된 판 2026.08.19 = PyPI 최신 stable(10-19) 인데 «The page needs to be reloaded»(아래) 의 수리(#17389 ← PR #17805,
#:   2026-10-10 합침)는 nightly(PyPI 2026.10.10.233141.dev0)에만 있다 — stable 로 «올리기»는 아무것도 안 바꾸고 같은 실패를 한 번 더 받는다.
_YTDLP_MODULE = {}
_YTDLP_PIP = ["--upgrade", "--pre", "yt-dlp[default]"]
#: 판을 올리면 풀리는 실패 — 이 실행기에서 «yt-dlp 가 옛 판» 을 뜻하는 문구의 **한 자리**(_ytdlp_switch_reason 만 읽는다). 출처:
#:   · «HTTP Error 403 · unable to download video data» — 신고 #211(2026.03.17 판 403 · 2026.08.19 판 정상 · 09-17 win-01)
#:   · «Signature extraction failed · nsig extraction failed · challenge solving failed» — 공식 EJS 안내의 풀이 실패 경고
#:     (https://github.com/yt-dlp/yt-dlp/wiki/EJS)
#:   · «The page needs to be reloaded» — yt-dlp 이슈 #16212(2026-03-11 · bashonly «fixed by 92f1d99 … **UPDATE yt-dlp** … pip install -U
#:     "yt-dlp[default]"» · 변경 기록 2026.03.13 «Update ejs to 0.7.0») · #17389(tv_downgraded UNPLAYABLE · PR #17805 로 2026-10-10 닫힘 ·
#:     gamer191 «yt-dlp --update-to nightly · pip: pip install -U --pre yt-dlp») · #17521(#17389 중복 · bashonly «Update yt-dlp»).
#:     같은 문구가 접속 IP 때문일 때도 있다(#16515 bashonly) — 그때는 올린 판으로 한 번 다시 받아도 실패하고 원래 실패를 그대로 돌려준다(상한 1).
#:   · «is older than 90 days» — yt-dlp 자신의 옛 판 경고(yt_dlp/update.py `_get_outdated_warning` «Your yt-dlp version (…) is older
#:     than 90 days!» · #13937 2025-08-06 부터 · `--no-update` 면 안 찍힌다)
#: 429·봇 확인은 유튜브의 거부라 다시 받지 않는다(6-2 · _YTDLP_REFUSED 가 이긴다).
_YTDLP_STALE = re.compile(r"HTTP Error 403|unable to download video data|Signature extraction failed|nsig extraction failed"
                          r"|challenge solving failed|The page needs to be reloaded|is older than 90 days", re.I)
_YTDLP_REFUSED = re.compile(r"HTTP Error 429|Too Many Requests|Sign in to confirm", re.I)


def _ytdlp_module_head(why):
    """실행기 파이썬에 공식 최신 yt-dlp 를 (이 프로세스에서 한 번) 올리고 그 머리를 돌려준다 — 못 올리면 None."""
    if "head" not in _YTDLP_MODULE:
        _YTDLP_MODULE["head"] = [sys.executable, "-m", "yt_dlp"] if _pip_install_once(_YTDLP_PIP, "yt-dlp " + why) else None
    return _YTDLP_MODULE["head"]


def _ytdlp_switch_reason(done):
    """이 yt-dlp 실패가 실행기 파이썬의 최신 판으로 풀리는 부류면 그 까닭(사람 말) · 아니면 None."""
    if _ytdlp_install_broken(done):
        return "이 컴퓨터의 yt-dlp 설치가 깨짐"
    text = done.stderr if isinstance(done.stderr, str) else (done.stderr or b"").decode("utf-8", "replace")
    if _YTDLP_STALE.search(text) and not _YTDLP_REFUSED.search(text):
        return "유튜브가 이 컴퓨터의 yt-dlp 판을 막음(403·풀이 실패·페이지 다시 읽기·90일 넘은 판)"
    return None


def _ytdlp_install_broken(done):
    text = done.stderr if isinstance(done.stderr, str) else (done.stderr or b"").decode("utf-8", "replace")
    return ("No module named 'yt_dlp'" in text or ("ImportError" in text and "yt_dlp" in text)
            or ("from ..compat import" in text and "Traceback" in text))


#: 윈도우 종료 코드(NTSTATUS · 공식 ntstatus.h) 중 «출력 없이» 끝나는 흔한 것 — 실패 글에 뜻을 붙인다(★10-17).
_RUNNER_T0 = time.monotonic()   # 실행기 프로세스가 이 모듈을 올린 때(failure_text «실행기 띄운 지»)

_NTSTATUS = {0xC0000142: "STATUS_DLL_INIT_FAILED — 프로그램이 시작하지 못했다(DLL 초기화 실패 · 띄운 프로그램이 붙을 콘솔 창이 이미 닫혔을 때 등)",
             0x40010004: "DBG_TERMINATE_PROCESS — 다른 프로그램(디버거·보안 프로그램 등)이 이 프로그램을 끝냈다(ntstatus.h «Debugger terminated process»)",
             0xC000013A: "STATUS_CONTROL_C_EXIT — 콘솔 창이 닫혔거나 Ctrl+C·Ctrl+Break 로 끝났다",
             0xC0000005: "STATUS_ACCESS_VIOLATION — 프로그램이 메모리 접근 위반으로 죽었다",
             0xC00000FD: "STATUS_STACK_OVERFLOW — 프로그램이 스택 넘침으로 죽었다",
             0xC0000409: "STATUS_STACK_BUFFER_OVERRUN — 프로그램이 스스로 끝냈다(빠른 실패)"}


def _rc_text(rc):
    """종료 코드를 사람이 읽을 말로 — 맥·리눅스 음수는 신호 이름 · 윈도우 NTSTATUS 는 16진수와 뜻."""
    if rc is None:
        return "없음"
    if rc < 0:
        try:
            return f"{rc}(신호 {signal.Signals(-rc).name})"
        except ValueError:
            return str(rc)
    meaning = _NTSTATUS.get(rc & 0xFFFFFFFF)
    return f"{rc}(0x{rc & 0xFFFFFFFF:08X} {meaning})" if meaning else str(rc)


def err_gist(text, limit):
    """오류 출력을 limit 자 안으로 — **첫 줄(처음 원인) + « … » + 끝**(★10-19 #221).
    끝만 자르면 ffmpeg 의 «Task finished with error code: -22 … Nothing was written» 같은 뒤따름 줄만 남고
    처음 원인 줄(«[mjpeg @…] Non full-range YUV is non-standard …»)이 잘렸다(win-01 Gyan 8.1·N-125875 재현).
    bytes 는 utf-8(깨진 바이트는 대체 글자)로 읽는다. 첫 줄은 limit 의 절반까지 — 남는 몫은 끝(마지막 상태). limit 은 8 이상."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    first = s.split("\n", 1)[0].rstrip()[:limit // 2]
    return first + " … " + s[len(s) - (limit - len(first) - 3):]


#: 묶음 실패 글에 싣는 일감 하나의 오류 몫(글자) — 앞 셋까지. 옛 판은 앞 200자만 실어 Traceback 머리만 남고 끝의 실제 예외 줄이 잘렸다
#: (10-24 쇼핑 shop_footage Vmake 신고 · 10-09 뒤 같은 모양 약 14건). err_gist(첫 줄 + 끝)로 처음 원인과 마지막 예외를 같이 싣는다.
JOB_ERR_LIMIT = 600


def _jobs_head(errs):
    return "\n".join(f"  일감 {i}: {err_gist(str(e), JOB_ERR_LIMIT)}" for i, e in errs[:3])


def failure_text(p, limit=800):
    """실패한 명령의 증거 — 종료 코드(뜻) + 오류 출력 끝. 오류 출력이 비면 표준 출력 끝을 싣는다(★10-17).
    회원 보고 4건(윈도우): «실행 실패: …python.exe» 뒤가 비어 무엇이 왜 죽었는지 알 수 없었다 — 오류 출력만 실었고 종료 코드를 안 실었다.
    출력 없이 끝나는 실패(콘솔 닫힘 0xC000013A·강제 종료 신호)는 종료 코드만이 증거다."""
    err = (p.stderr or "").strip()
    if err:
        tail = err_gist(err, limit)
    else:
        out = (p.stdout or "").strip()
        tail = "(오류 출력 없음)" + (" · 표준 출력 끝:\n" + err_gist(out, limit) if out else " · 표준 출력도 없음")
    took = getattr(p, "elapsed_sec", None)
    # 실행기 프로세스가 뜬 지 몇 초인가 — 자식만 죽었는지(바깥 프로그램) · 실행기를 띄운 쪽의 명령 시간 제한(120·600초 등)에 같이 걸렸는지 가른다(10-23 신고).
    up = round(time.monotonic() - _RUNNER_T0, 1)
    return (f"종료 코드 {_rc_text(p.returncode)}" + (f" · 시작 {took}초 뒤 끝남" if took is not None else "")
            + f" · 실행기 띄운 지 {up}초" + _silent_kill_note(p) + f"\n{tail}")


def _silent_kill_note(p):
    """윈도우에서 파이썬 자식이 트레이스백도 결과 JSON([emit])도 없이 1·15 로 끝났으면 바깥에서 강제 종료된 것이다(10-23 신고).
    파이썬은 스스로 끝날 때 트레이스백을 남기고, 실행기 스크립트는 입구(ENTRY_GUARD)에서 sys.exit·Ctrl+C 까지 JSON 으로 답한다 —
    남는 길은 TerminateProcess 뿐이다: 종료 코드 1 = taskkill /F·Popen.kill/terminate·작업 관리자·보안 프로그램, 15 = os.kill(pid, SIGTERM)."""
    if os.name != "nt" or p.returncode not in (1, 15):
        return ""
    args = getattr(p, "args", None)
    head = os.path.basename(str(args[0] if isinstance(args, (list, tuple)) and args else args or "")).lower()
    text = (p.stderr or "") + (p.stdout or "")
    if not head.startswith("python") or "Traceback" in text or "[emit]" in text:
        return ""
    return (" · 트레이스백·결과 없이 끝남 = 바깥에서 강제 종료(TerminateProcess · "
            + ("코드 1: taskkill /F·작업 관리자·보안 프로그램·부모의 kill" if p.returncode == 1 else "코드 15: 다른 프로그램의 os.kill(SIGTERM)") + ")")


def run_argv(argv, capture=False, env=None):
    """서버가 준 argv 를 **한 글자도 고치지 않고** 실행한다.

    ★돌리기 전에 `-i` 입력이 있는지 본다 — 없으면 ffmpeg 의 헛말 대신 **어느 파일**인지 말한다.
    ★그 다음 **그 프로그램이 이 기계에 있는지** 본다(위 `_spawn` 머리말 참조).
    """
    miss = missing_inputs(argv)
    if miss:
        raise StepError(_missing_msg(argv, miss))
    started = time.monotonic()
    p = _spawn(argv, capture_output=True, env=env, **TEXT_PIPE)
    # 출력 없이 끝난 실패는 «얼마 만에» 가 남은 증거다(바깥 시간 제한·강제 종료와 맞춰 볼 수 있게 · 10-20 정치 politics_status rc=1 출력 0).
    p.elapsed_sec = round(time.monotonic() - started, 1)
    if p.returncode != 0 and not capture:
        raise RuntimeError(f"실행 실패: {argv[0]} …\n{failure_text(p)}")
    return p


def source_mp4(spec):
    """받은 원본(mkv — yt-dlp 가 어떤 코덱이든 다시 굽지 않고 담은 것)을 probe 가 찾는 mp4 로 만든다 (2026-10-22 신고 #34).

    ★한 자리(10-22): 실행기 구동기(`volcano_drive` — youtube·instagram 일감·인물형 acquire_source)와 쇼핑 수급 스크립트
      (`shop/hunt.py` 의 yt-dlp 받기 — runner_dir 의 이 모듈을 불러 쓴다)가 **이 함수 하나**를 부른다. 인자는 서버
      `volcano_ingest.source_mp4_job` 한 곳이 짓는다.
    yt-dlp `--remux-video mp4` 는 VP8·Theora·Vorbis(위키미디어 커먼즈 옛 webm 등)를 mp4 에 못 담아 «Conversion failed» 로 끝났다
    (17건·14명). 코덱은 받은 뒤에야 안다 — 그래서 이 자리에서 한 번 재고, 스트림마다 서버가 준 인자 두 벌(복사 · 다시 굽기) 가운데
    하나를 고른다. 실행기는 인자를 짓지 않는다(고르기만 · 경계 «argv 는 서버가 준다»). 복사로 담기는 원본은 바이트가 그대로다.
    다 되면 임시 파일을 mp4 자리로 옮기고 mkv 는 지운다(yt-dlp 가 remux 뒤 원본을 지우던 것과 같다). 이미 바꿨으면(mkv 없음·mp4 있음) 그대로 둔다.
    """
    src, dst, tmp = spec["input"], spec["output"], spec["tmp"]
    if not os.path.isfile(src):
        if os.path.isfile(dst) and os.path.getsize(dst) > 0:
            return {"status": "kept", "path": dst}
        raise StepError(f"받은 원본이 없습니다: {src} — 바로 앞의 다운로드가 끝나지 않았습니다. 같은 단계를 다시 부르세요.")
    p = run_argv(spec["probe_argv"], capture=True)
    if p.returncode != 0:
        raise StepError(f"받은 원본의 코덱을 재지 못했습니다: {src}\n{failure_text(p)}")
    try:
        streams = json.loads(p.stdout or "{}").get("streams") or []
    except ValueError as error:
        raise StepError(f"받은 원본의 코덱 측정 결과를 읽지 못했습니다: {error}") from error
    first = {}
    for s in streams:
        first.setdefault(s.get("codec_type"), s.get("codec_name"))
    if "video" not in first:
        raise StepError(f"받은 파일에 영상 스트림이 없습니다(소리만 받음): {src} — 영상이 있는 주소인지 확인하세요.")
    pick = {}
    argv = list(spec["head"])
    for kind in ("video", "audio"):
        if kind not in first:
            continue
        way = "copy" if first[kind] in spec["copy_codecs"][kind] else "encode"
        pick[kind] = {"codec": first[kind], "way": way}
        argv += spec[kind][way]
    argv += spec["tail"]
    _progress(f"  [소재 mp4] {os.path.basename(src)} → {os.path.basename(dst)} · "
              + " · ".join(f"{k} {v['codec']} {'복사' if v['way'] == 'copy' else '다시 굽기'}" for k, v in pick.items()))
    done = run_argv(argv, capture=True)
    if done.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
        raise StepError(f"받은 원본을 mp4 로 옮기지 못했습니다: {src}\n{failure_text(done)}")
    os.replace(tmp, dst)
    os.remove(src)
    return {"status": "made", "path": dst, "streams": pick}


def run_vmake_job(item, invoke=None):
    """Shared Vmake completion boundary for a do command and argv-pool jobs."""
    if not all(item.get(k) for k in ("receipt", "script", "out")):
        raise StepError("이 Vmake 계획에는 접수 기록 계약이 없습니다. 같은 단계에서 새 계획을 받으세요.")
    p = (invoke or run_argv)(item["argv"], capture=True)
    try:
        done = json.loads(p.stdout or "")
    except (ValueError, TypeError):
        done = {}
    if not isinstance(done, dict):
        done = {}
    if p.returncode == 3 and done.get("status") == "pending":
        raise TranscriptionPending("Vmake", done.get("message") or "접수 작업 대기 중",
                                   state_file=item["receipt"])
    if p.returncode:
        raise StepError("Vmake 실행 실패:\n" + err_gist(p.stderr or p.stdout, 800))
    rule = item.get("skip_if")
    if (done.get("status") != "complete" or done.get("out") != item["out"]
            or done.get("remove_hardsub") is not False or not rule or not _have(rule)):
        raise StepError("Vmake 완료 파일과 검증 결과가 다릅니다. 원본을 유지합니다.")
    digest = hashlib.sha256()
    with open(item["out"], "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != done.get("sha256"):
        raise StepError("Vmake 완료 파일의 바이트가 검증 결과와 다릅니다. 원본을 유지합니다.")
    if isinstance(item.get("handoff"), dict):
        done["handoff"] = item["handoff"]
    return done


class _SourceReadGuard:
    """Keep Windows source bytes stable while allowing other readers."""
    def __init__(self, path):
        self.path, self.handle, self.close_handle = path, None, None

    def __enter__(self):
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            create = kernel.CreateFileW
            create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                               wintypes.HANDLE)
            create.restype = wintypes.HANDLE
            close = kernel.CloseHandle
            close.argtypes, close.restype = (wintypes.HANDLE,), wintypes.BOOL
            path = os.path.abspath(os.fspath(self.path))
            if not path.startswith('\\\\?\\'):
                path = ('\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\')
                        else '\\\\?\\' + path)
            # No SHARE_WRITE/SHARE_DELETE: reject existing writers and prevent
            # in-place changes or replacement until the caller closes the guard.
            handle = create(path, 0x80000000, 0x00000001, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                error = ctypes.WinError(ctypes.get_last_error())
                raise OSError(f"원본 파일을 읽기 전용으로 보호할 수 없습니다: {self.path}. "
                              f"이 파일에 쓰는 프로그램을 닫고 다시 실행하세요. {error}") from error
            self.handle, self.close_handle = handle, close
        return self

    def __exit__(self, *_exc):
        if self.handle is not None:
            self.close_handle(self.handle)
            self.handle = None


class _ArgvInputDigests:
    """Only this pool invocation may reuse a source digest; changes fail closed."""
    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.saved = {}
        self.guarded = set()
        from contextlib import ExitStack
        self.guards = ExitStack()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self.guards.__exit__(*exc)

    def _guard(self, path):
        if path not in self.guarded:
            self.guards.enter_context(_SourceReadGuard(path))
            self.guarded.add(path)

    @staticmethod
    def _stamp(handle):
        st = os.fstat(handle.fileno())
        changed = st.st_ctime_ns
        if os.name == 'nt':
            # Python's Windows ctime has varied between creation/change time.
            # Query the documented change time of this actual open file.
            import ctypes
            from ctypes import wintypes
            import msvcrt
            class BasicInfo(ctypes.Structure):
                _fields_ = [(name, ctypes.c_longlong) for name in
                            ('created', 'accessed', 'written', 'changed')]
                _fields_.append(('attributes', wintypes.DWORD))
            info = BasicInfo()
            query = ctypes.WinDLL('kernel32', use_last_error=True).GetFileInformationByHandleEx
            query.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
            query.restype = wintypes.BOOL
            if not query(msvcrt.get_osfhandle(handle.fileno()), 0,
                         ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            changed = info.changed
        return _FileBody._stamp(st) + (changed,)

    @staticmethod
    def _hash(handle):
        handle.seek(0)
        h = hashlib.sha256()
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
        return h.hexdigest()

    def digest(self, path):
        """■ 변경 시각(ctime/ChangeTime)만 바뀐 것은 **내용으로** 판정한다 (2026-10-05 · 원장 W2-27).

        변경 시각은 내용 말고도 메타데이터(파일 속성·확장 속성·링크 수)가 바뀔 때 움직인다 — 실측 신고:
        «원본 mp4 내용은 그대로인데 NTFS ChangeTime 만 바뀌어 중단»(인물형 롱폼) · 같은 img43/01.png 로 29회(윈도우) ·
        맥 1건. 그래서 (장치·아이노드·크기·수정 시각)이 그대로이고 변경 시각만 움직였으면 **다시 해시해** 처음 값과
        같을 때만 받아들인다. 내용이 바뀌었으면(해시 다름) 지금처럼 멈춘다 — 판정이 메타데이터 대리값에서 내용 자체로 옮겨 갈 뿐
        느슨해지지 않는다. 크기·수정 시각·아이노드가 바뀐 것은 지금처럼 바로 멈춘다.
        """
        # Parallel cuts share one read, but still open/check the actual source.
        # ★굽는 이 실행 밖의 무엇이 그 파일을 다시 쓴 것이다 — 인물형 롱폼 media/collage/*/atlas.png 는 저자(회원 쪽 클로드)가 쓰는 파일이고
        #   실행기 롱폼 모듈은 media/ 에 쓰지 않는다(신고 10-18·10-22 맥 · 42분 굽는 사이).
        #   새 실행은 처음부터 다시 잰다(self.saved 는 이 실행 안의 기억) — 회원이 바로 할 수 있는 일을 함께 적는다.
        changed_file = (f"렌더 원본 파일이 해시 확인 뒤 바뀌었습니다: {path} — 굽는 동안 다른 프로그램(편집기·동기화·파일 쓰기)이 "
                        "이 파일을 다시 썼습니다. 쓰기를 마친 뒤 같은 명령을 다시 실행하면 바뀐 파일로 처음부터 다시 잽니다")
        with self.lock:
            self._guard(path)
            with open(path, 'rb') as handle:
                stamp = self._stamp(handle)
                saved = self.saved.get(path)
                if saved is not None and saved[0] != stamp:
                    # 메타데이터만 바뀌었는가 — 내용으로 확인한다(위 설명).
                    if saved[0][:4] != stamp[:4] or self._hash(handle) != saved[1]:
                        raise OSError(changed_file)
                if saved is None:
                    value = self._hash(handle)
                else:
                    value = saved[1]
                after = self._stamp(handle)
                if after[:4] != stamp[:4] or stamp[:4] != _FileBody._stamp(os.stat(path)):
                    raise OSError(changed_file)
                if after != stamp:
                    # 읽는 도중 변경 시각만 움직였다 — 한 번 더 읽어 같은 내용이고 그사이 안정했을 때만 받아들인다.
                    again = self._hash(handle)
                    settled = self._stamp(handle)
                    if again != value or settled != after:
                        raise OSError(changed_file)
                    stamp = settled
                self.saved[path] = stamp, value
                return value

    def check(self, paths=None):
        for path in tuple(self.saved) if paths is None else paths:
            self.digest(path)


def _argv_content_receipt(job, input_digests):
    """Optional server-declared input/output content receipt for local render reuse."""
    spec = job['skip_sig']
    def digest(path):
        h = hashlib.sha256()
        with open(path, 'rb') as handle:
            for block in iter(lambda: handle.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()
    inputs = {p: input_digests.digest(p) for p in spec['inputs']}
    output = digest(spec['path'])
    input_digests.check(spec['inputs'])
    return {'sig': spec['sig'], 'inputs': inputs, 'output': output}


def run_argv_pool(jobs, parallel=None):
    """서버가 준 폭으로 argv 일감을 **동시에** 돌린다. 폭이 없으면 직렬이다.

    ■ 왜 안전한가
        각 일감이 독립 프로세스이고 argv 가 한 글자도 안 바뀌므로 동시성이 결과에
        닿지 않는다. 서버 쪽 검사가 이것을 실제 산출물 대조로 증명한다.

    ■ ★깨뜨리는 것 둘 — 실행기가 지켜야 할 것
        ① argv 에 스레드 수 옵션을 **추가하지 마라.** 인코더가 그 값을 파일에 박아
           산출물 바이트가 달라진다. 부하가 걱정되면 폭을 줄여라.
        ② 두 일감이 **같은 출력 경로**를 쓰면 결과가 재현되지 않는다. 그런데 길이만
           보는 검사는 그걸 통과시킨다 — 호출부가 경로 중복을 먼저 막는다.

    ■ 예외를 삼키지 않는다
        일감 하나가 조용히 빠지면 이어붙이기 전까지 아무도 모른다. 하나라도 실패하면
        여기서 멈춘다.
    """
    with _ArgvInputDigests() as input_digests:
        return _run_argv_pool(jobs, parallel, input_digests)


def _run_argv_pool(jobs, parallel, input_digests):
    # ★★서명 재사용 — **서버가 준 서명이 맞을 때만** 건너뛴다 (2026-08-24).
    #   반려 후 재진입이 안 바뀐 블록까지 전부 다시 굽고 있었다. 판정 재료(서명)는
    #   서버가 만든다 — 실행기는 사이드카(`<out>.sig`)와 **대조만** 한다.
    #   ★`_have`(키-인-파일명 캐시)와 다른 자다 — 블록 이름(b00.mp4)은 키를 못 담고,
    #     이름을 바꾸면 concat 목록·정본 재현이 깨진다. 그래서 서명은 옆 파일이다.
    #   ★성공한 뒤에만 사이드카를 쓴다 — 실패한 산출물이 다음 판에 «맞다»로 남으면 안 된다.
    import threading
    completed, completed_lock = {}, threading.Lock()

    def _sig_skip(j):
        r = j.get("skip_sig") or {}
        p, s = r.get("path"), r.get("sig")
        if not (p and s):
            return False
        try:
            if not os.path.exists(p) or os.path.getsize(p) <= int(r.get("min_bytes") or 0):
                return False
            with open(p + ".sig", encoding="utf-8") as handle:
                old = handle.read().strip()
            if not _venc_same(j, p):
                return False
            if 'inputs' in r:
                return json.loads(old) == _argv_content_receipt(j, input_digests)
            return old == s
        except (OSError, ValueError):
            return False

    def _sig_write(j):
        r = j.get("skip_sig") or {}
        if r.get("path") and r.get("sig"):
            receipt = (json.dumps(_argv_content_receipt(j, input_digests), sort_keys=True)
                       if 'inputs' in r else r["sig"])
            with open(r["path"] + ".sig", "w", encoding="utf-8") as f:
                f.write(receipt)
            used = venc_used.get(id(j))
            if used is not None:
                with open(r["path"] + ".venc", "w", encoding="utf-8") as f:
                    f.write(used)

    # ★인코더 자리(@VENC@)가 든 일감 — 같은 묶음(이어 붙일 블록들)이 한 인코더로 구워져야 한다.
    #   GPU·CPU 가 섞이면 같은 H.264 라도 SPS/PPS 가 달라 -c copy 이음이 깨진다. 그래서 «무엇으로 구웠나»를
    #   옆 파일(<out>.venc)에 적고, 지금 이 PC 가 고를 인코더와 다르면 재사용하지 않는다(옛 실행기 산출물 = CPU 이름).
    venc_used = {}

    def _venc_same(j, path):
        venc = _video_encoder()
        want = venc.chosen_name(j.get("argv"))
        if want is None:
            return True
        try:
            with open(path + ".venc", encoding="utf-8") as handle:
                got = handle.read().strip()
        except OSError:
            got = venc.cpu_name(j.get("argv"))
        return got == want

    def _run(j):
        if j.get("cmd") == "vmake_clear":
            result = run_vmake_job(j)
            with completed_lock:
                completed[j["out"]] = result
            return
        # Bind input bytes before rendering, then recheck before publishing reuse.
        spec = j.get("skip_sig") or {}
        if spec.get("path") and spec.get("sig"):
            input_digests.check(spec.get("inputs", []))
        done = run_argv(j["argv"])
        if hasattr(done, "venc"):
            with completed_lock:
                venc_used[id(j)] = done.venc or _video_encoder().cpu_name(j["argv"])
                if done.venc_fallback:
                    venc_used["fallback"] = True
        _sig_write(j)

    def _venc_settle():
        """묶음 안에서 GPU 가 한 번이라도 실패해 CPU 로 구운 일감이 있으면, GPU 로 구운 나머지도 CPU 로 한 번 다시 굽는다
        (일감당 굽기 상한 2회 — GPU 1 + CPU 1). 섞인 블록을 이어 붙이면 화면이 깨진다."""
        if not venc_used.pop("fallback", False):
            return
        venc = _video_encoder()
        redo = [j for j in jobs if venc_used.get(id(j)) not in (None, venc.cpu_name(j.get("argv")))]
        if redo:
            _progress(f"  [인코더] GPU 실패가 있어 같은 묶음 {len(redo)}개를 CPU 로 다시 굽습니다(섞이지 않게)", flush=True)
        for j in redo:
            run_argv(venc.expand(j["argv"], "cpu")[0])
            venc_used[id(j)] = venc.cpu_name(j["argv"])
            _sig_write(j)

    # ★`skip_if`(키-인-파일명 · 유료 하달의 «이미 있다»)도 여기서 본다 (2026-09-02) — 쇼핑
    #   하드섭 제거를 do(직렬)에서 jobs(병렬)로 옮기며 그 규칙이 같이 와야 재과금이 안 난다.
    _keep_jobs = [j for j in jobs if j.get("cmd") == "vmake_clear" or
                  (not _sig_skip(j) and not (j.get("skip_if") and _have(j["skip_if"])))]
    for j in jobs:
        if j.get("cmd") != "vmake_clear" and j.get("skip_if") and _have(j["skip_if"]):
            _progress(f"  [건너뜀] 이미 있다: {j['skip_if'].get('path')}", flush=True)
    if len(_keep_jobs) < len(jobs):
        _progress(f"  [재사용] {len(jobs) - len(_keep_jobs)}/{len(jobs)}개 일감 — "
              "입력 서명이 같다. 바뀐 것만 다시 굽는다", flush=True)
    jobs = _keep_jobs
    if not jobs:
        input_digests.check()
        return completed or None
    n = len(jobs)
    try:
        w = int(parallel or 1)
    except (TypeError, ValueError):
        w = 1
    w = max(1, min(w, n))
    if w == 1:
        for j in jobs:
            _progress(f"  [일감 {j.get('index')}] {j['argv'][0]} …", flush=True)
            _run(j)
        _venc_settle()
        input_digests.check()
        return completed or None
    import queue as _q                                            # noqa: PLC0415
    import threading                                              # noqa: PLC0415
    q, errs, lock = _q.Queue(), [], threading.Lock()
    for j in jobs:
        q.put(j)
    _progress(f"  [일감] {n}개를 폭 {w} 로 동시에 돈다", flush=True)

    def _worker():
        while True:
            try:
                j = q.get_nowait()
            except _q.Empty:
                return
            try:
                _run(j)               # ★성공한 일감만 서명을 남긴다
            except Exception as e:                                # noqa: BLE001
                with lock:
                    errs.append((j.get("index"), e))
            finally:
                q.task_done()

    ts = [threading.Thread(target=_worker, daemon=True) for _ in range(w)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    if errs:
        if all(isinstance(error, TranscriptionPending) for _, error in errs):
            raise errs[0][1]  # Keep the pending contract; completed receipts stay on disk.
        head = _jobs_head(errs)
        raise StepError(f"{len(errs)}/{n} 개 일감이 실패했다.\n{head}")
    _venc_settle()
    input_digests.check()
    return completed or None


def _pool(jobs, width, fn, what, stagger=0.0, stop_on_error=False, stop_on_refusal=False):
    """잡마다 `fn(job)` 을 폭 `width` 로 돌린다. 실패를 **삼키지 않는다.**

    ★같은 산출 경로를 두 잡이 쓰면 결과가 재현되지 않는다 — 먼저 막는다.
    ★`stagger` 는 제공자가 "요청 간격을 두라" 고 한 경우에만 서버가 준다.
    """
    n = len(jobs)
    try:
        w = int(width or 1)
    except (TypeError, ValueError):
        w = 1
    w = max(1, min(w, n))
    # ★★겹침은 **산출물**(out·steps[].out)로 본다 (2026-09-02). 전에는 raw 까지 보고
    #   폭 1 이어도 막아서, 같은 문장 두 블록(같은 캐시 raw)이 14건·1명을 죽였다.
    #   같은 raw 를 쓰는 일감은 **동시에 받으면** `.part` 가 충돌하므로 뒤로 미뤄
    #   직렬로 돌린다 — 두 번째는 첫 번째가 받아 둔 raw 를 skip_if 로 건너뛴다.
    outs = []
    for j in jobs:
        # ★한 일감 안에서는 마지막 step 이 `out` 을 만드는 게 정상이다 — 일감 안 중복은
        #   합치고 **일감 사이** 겹침만 본다.
        _o = {j.get("out")} | {st.get("out") for st in (j.get("steps") or []) if isinstance(st, dict)}
        outs += [o for o in _o if o]
    if len(set(outs)) != len(outs):
        _dupo = sorted({o for o in outs if outs.count(o) > 1})[:3]
        raise StepError(f"{what}: 두 일감이 같은 산출 경로를 쓴다 — 동시에 돌리면 깨진다. "
                        f"({_dupo}) 서버 쪽 문제다 — 관리자에게 알려라.")
    _seen_raw, _first, _dups = set(), [], []
    for j in jobs:
        _r = j.get("raw")
        (_dups if (_r and _r in _seen_raw) else _first).append(j)
        if _r:
            _seen_raw.add(_r)
    if w == 1:
        for j in jobs:
            fn(j)
        return
    if _dups:
        _pool(_first, w, fn, what, stagger=stagger, stop_on_error=stop_on_error,
              stop_on_refusal=stop_on_refusal)
        _progress(f"  [{what}] 같은 원본을 쓰는 일감 {len(_dups)}개는 뒤에 직렬로", flush=True)
        for j in _dups:
            fn(j)
        return
    import queue as _q                                            # noqa: PLC0415
    import threading                                              # noqa: PLC0415
    q, errs, lock = _q.Queue(), [], threading.Lock()
    refusal = []
    for j in jobs:
        q.put(j)
    _progress(f"  [{what}] {n}개를 폭 {w} 로 동시에", flush=True)

    def _worker(slot):
        if stagger:
            time.sleep(stagger * slot)        # 제출을 벌린다(제공자 지침)
        while True:
            # Claim work under the same lock that records fatal failures.
            # Jobs already claimed may finish; queued jobs cannot pass a stale check.
            with lock:
                if (stop_on_error and errs) or (stop_on_refusal and refusal):
                    return
                try:
                    j = q.get_nowait()
                except _q.Empty:
                    return
            try:
                fn(j)
            except Exception as e:                                # noqa: BLE001
                with lock:
                    errs.append((j.get("index", j.get("slot")), e))
                    if isinstance(e, ProviderRefusalError):
                        refusal.append(e)
            finally:
                q.task_done()

    # ContextVars carry the active workdir used by local runtime/cost evidence.
    # Each thread needs its own copy: one Context cannot be entered concurrently.
    contexts = [contextvars.copy_context() for _ in range(w)]
    ts = [threading.Thread(target=ctx.run, args=(_worker, i), daemon=True)
          for i, ctx in enumerate(contexts)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    if stop_on_refusal and refusal:
        raise refusal[0]
    if errs:
        head = _jobs_head(errs)
        failed = StepError(f"{what}: {len(errs)}/{n} 개가 실패했다.\n{head}")
        # 일감마다의 실패가 전부 «이미 알린 정지를 기록에서 다시 보인 것» 이면 묶음도 그렇다(`replayed`) — 하나라도 새 실패면 알린다.
        failed.replayed = all(getattr(e, 'replayed', False) for _, e in errs)
        raise failed


def measure_lufs(argv):
    """서버가 준 측정 argv 를 돌려 stderr 마지막 `I:` 줄의 숫자를 뽑는다.

    ★argv 에 `-v error` 를 **붙이지 마라.** 붙이면 stderr 가 비어 측정값이 사라진다.
      그러면 게인이 1.0 이 되어 효과음이 나레이션보다 크게 터진다.
    """
    p = run_argv(argv, capture=True)
    # ★`p.stderr` 가 **None 일 수 있다.** 예전에는 파이프 디코딩이 터지면 리더가
    #   죽어 None 이 됐고, 여기서 `'NoneType' object has no attribute 'splitlines'`
    #   로 죽었다 — 진짜 원인(인코딩)이 그 트레이스백에 안 보인다.
    #   `TEXT_PIPE` 로 원인은 막았지만, **읽는 쪽도 None 을 견딘다.**
    lines = [ln for ln in (p.stderr or "").splitlines() if ln.strip().startswith("I:")]
    if not lines:
        raise RuntimeError("라우드니스를 못 읽었다 — argv 를 고치지 않았는지 확인하라. "
                           "`-v error` 가 붙으면 측정값이 사라진다. "
                           f"(stderr {len(p.stderr or '')}자)")
    return float(lines[-1].split()[1])



def measure_loudnorm(item):
    """1패스 `loudnorm` JSON 전문. **서버가 2패스 `measured_*` 를 짓는다.**

    ★1패스로 한 번에 걸면 목표에서 0.3~0.8 LU 벗어난다(정본 실측). 재고 되먹여야 붙는다.
    ★argv 는 **서버가 준다** — 여기서 짓지 않는다(자를 바꾸면 그 자는 무엇을 재는지 모른다).
    """
    p = run_argv(item["argv"], capture=True)
    s = p.stderr or ""
    i, j = s.rfind("{"), s.rfind("}")
    if i < 0 or j < i:
        raise RuntimeError(
            "loudnorm 1패스 측정값(JSON)을 못 읽었다 — argv 를 고치지 않았는지 확인하라. "
            "`-v error` 나 `-loglevel error` 가 붙으면 측정값이 사라진다. "
            f"(stderr {len(s)}자)")
    d = json.loads(s[i:j + 1])
    need = ("input_i", "input_lra", "input_tp", "input_thresh", "target_offset")
    miss = [k for k in need if k not in d]
    if miss:
        raise RuntimeError(f"loudnorm JSON 에 {miss} 가 없다 — ffmpeg 판이 다른가")
    return {k: d[k] for k in need}


def measure_peak(item):
    """(통합 LUFS, 트루피크) — **게이트와 같은 자**(`ebur128=peak=true`).

    ★`loudnorm` 의 `TP=` 로는 보장되지 않는다. 내부 192kHz 추정이 ebur128 과
      0.2~0.4dB 어긋나서 같은 설정인데 통과와 실패가 갈렸다(정본 실측).
    ★못 읽으면 **None 으로 말한다** — 0 이 아니다(§"못 잰 것은 0 이 아니다").
    """
    p = run_argv(item["argv"], capture=True)
    tail = (p.stderr or "")[-4000:]
    li = tp = None
    # ★★**마지막** 값을 쓴다 — 첫 값이 아니다 (2026-08-19 실측으로 잡았다).
    #   `ebur128` 은 프레임마다 `… I: -70.0 LUFS …` 를 찍고 **맨 끝 Summary** 에만
    #   통합 라우드니스를 찍는다. `re.search`(첫 매치)는 그 프레임 줄을 집어
    #   **-70.0** 을 돌려줬다(합성 2초 파일 실측: 첫 -70.0 ↔ 요약 -27.8).
    #   이 값은 그냥 보고용이 아니다 — 서버가 `tries` 에 쌓아 **마스터 게인 수렴**에
    #   쓴다(`volcano_tools:5775` · `volcano_stitch:1192`). 틀린 I 로 수렴하면
    #   완성본 라우드니스가 목표에서 벗어난 채 오류 0줄로 나간다.
    #   ★`_measure` 의 `lufs_tp` 갈래는 처음부터 `findall(...)[-1]` 이었다 —
    #     같은 자를 두 곳이 다르게 읽고 있었다.
    _i = re.findall(r"^\s*I:\s*(-?\d+\.?\d*)\s*LUFS", tail, re.M)
    if _i:
        li = float(_i[-1])
    _pk = re.findall(r"^\s*Peak:\s*(-?\d+\.?\d*)\s*dBFS", tail, re.M)
    if _pk:
        tp = float(_pk[-1])
    return {"I": li, "TP": tp}


def measure_lufs_spread(argv):
    """같은 측정에서 **단기 라우드니스 폭**(p90-p10)을 뽑는다 (2026-08-16).

    ■ 왜 필요한가
        완성본이 실물보다 **평평하다**는 것이 사장님 지적("틈이 이렇다고?")의 실체다.
        실측: 레퍼런스 어랍숏 10편 폭 3.0~9.2(중앙 4.8) · 우리 2.1.
        원인을 원음 게인으로 돌려 봤는데 **소재가 균일하면 안 올라간다** —
        AMB_OFF 를 -20.2 → -11.0 으로 9dB 올려도 폭은 2.2 → 3.6 에서 포화한다.
        즉 상수 문제가 아니라 **소재 문제**다. 그래서 돈 쓰기 전에 알려준다.

    ★`measure_lufs` 와 **같은 stderr** 를 쓴다. 따로 돌리면 두 번 굽는다.
    """
    p = run_argv(argv, capture=True)
    xs = []
    for ln in (p.stderr or "").splitlines():
        m = re.search(r"S:\s*(-?[\d.]+)", ln)
        if m:
            v = float(m.group(1))
            if v > -70:                      # ★디지털 무음은 뺀다(§무음까지 세는 자)
                xs.append(v)
    if len(xs) < 20:
        return None                          # ★못 잰 것은 **0 이 아니다.** None 으로 말한다
    xs.sort()
    return round(xs[int(len(xs) * 0.9)] - xs[int(len(xs) * 0.1)], 2)


def _sub_argv(argv, **subs):
    """argv 틀의 자리표(@IN@·@OUT@·@AF@ …)를 채운다 — 서버가 지은 명령에 숫자만
    끼우는 자리다. 자리표가 아닌 인자는 한 글자도 안 바뀐다."""
    return [subs.get(a, a) for a in argv]


def resolve_files(item):
    """Resolve declared local names against existing files, without inventing a path."""
    base = os.path.abspath(item["workdir"])
    roots = [os.path.abspath(p) for p in item.get("roots") or []]
    paths = item.get("paths") or []
    if not paths:
        paths = [os.path.join(root, name) for root in roots if os.path.isdir(root)
                 for name in sorted(os.listdir(root))
                 if os.path.isfile(os.path.join(root, name))
                 and os.path.splitext(name)[1].lower() in item.get("extensions", [])]
    out = []
    for name in paths:
        name = os.fspath(name)
        direct = name if os.path.isabs(name) else os.path.join(base, name)
        if os.path.isfile(direct):
            chosen = os.path.abspath(direct)
        elif os.path.isabs(name):
            raise StepError("지정한 파일이 없습니다: " + name)
        else:
            matches = sorted({os.path.abspath(os.path.join(root, os.path.basename(name)))
                              for root in roots
                              if os.path.isfile(os.path.join(root, os.path.basename(name)))})
            if len(matches) != 1:
                raise StepError("파일을 하나로 찾을 수 없습니다: " + name +
                                (" — 같은 이름이 여러 폴더에 있습니다. 실제 절대경로를 지정하세요." if matches
                                 else " — 자산 설치와 실제 파일 위치를 확인하세요."))
            chosen = matches[0]
        if chosen not in out:
            out.append(chosen)
    return out


def piece_shape(item):
    """나레 조각 **파생 사본**을 만든다 — `NN.shape.wav`(문장 안 크기 기울기) ·
    (실물보다 넓을 때만) `NN.lvl.wav`(줄 크기 좁히기) · `00.lvl.wav`(오프닝 크기).

    ■ 왜 (2026-08-25 · 군림보 끝판 검증이 잡았다)
        보존 완성본의 aconcat 은 `00.lvl → _gap → NN.shape` 를 잇는다 — 그런데
        이식된 체인에는 그 사본을 **만드는 자리가 없었다**(고르는 자리
        `measure_pieces` 만 이식돼, 판정기들은 보존 사본을 주입받아 통과했다).
        체인 혼자 구우면 소리가 평평한 채 나가고 narr.wav 가 보존과 갈린다.
        tikitaka `build.sent_shape_fix`·`line_level_fix`·오프닝 크기 맞춤을
        **그 수식·그 차례**(기울기 → 좁히기 → 오프닝)로 이관했다.

    ★채널 값이 여기 하나도 없다 — 기울기 표(첫/가운데/끝 dB)·흩어짐 목표·오프닝
      상대값·창·문턱 전부 서버 params 다. 문장 묶음(`sents`)도 서버가 문장끝 자
      (volcano_script.sentence_end)로 묶어 보낸다 — 글 판정은 서버 몫이다.
    ★ffmpeg argv 도 서버 틀(@IN@·@OUT@·@AF@)이다 — 실행기는 자리표에 숫자만
      끼운다(render_sfx_bed 의 decode_argv 그 계약 · 경계 검사 「실행기가 ffmpeg
      명령을 짓지 않는다」가 이것을 지킨다). 이득 서식(af_fmt)도 서버가 준다 —
      %.2f 가 곧 보존 굽기의 그 서식이라 한 글자가 갈리면 바이트가 갈린다.
    ★크기만 만진다. 억양이 아니다(목소리는 결재 사항 — tikitaka 그 주석 그대로).
    ★원본을 덮어쓰지 않는다 — 사본을 만들고, 지난 판 사본은 먼저 지운다(멱등).
    ★서버가 이 명령을 줄 때만 돈다(연속 나레 + SENT_SHAPE_DB 채널 = 군림보) —
      옛 서버 응답과 혼재 무해.
    """
    with contextlib.ExitStack() as scope:
        sources = []
        if item.get("raw_provenance") is True:
            d = str(item["dir"]).rstrip("/")
            indices = {int(i) for ss in (item.get("sents") or []) for i in ss} | {0}
            for i in sorted(indices):
                path = f"{d}/{i:02d}.wav"
                if not os.path.isfile(path):
                    raise StepError(f"새 음성의 원본 조각이 없습니다: {path}")
                sources.append(scope.enter_context(_FileBody(path)))
        return _piece_shape_guarded(item, sources)


def _piece_shape_guarded(item, sources):
    import numpy as np

    d = str(item["dir"]).rstrip("/")
    sents = [[int(i) for i in ss] for ss in (item.get("sents") or [])]
    sh = item.get("shape") or {}
    sp = item.get("spread") or {}
    op = item.get("open") or {}
    pr = item.get("probe") or {}
    dec = item["decode_argv"]
    vol = item["vol_argv"]
    af_fmt = str(item.get("af_fmt") or "volume=%.2fdB")
    win, pct = int(pr.get("win") or 320), float(pr.get("pct") or 90)
    idx_all = sorted({i for ss in sents for i in ss})
    provenance = item.get("raw_provenance") is True
    provenance_path = os.path.join(d, ".piece-shape-provenance.json")
    provenance_record = None
    if provenance:
        # 새 raw 뒤에만 확인한다. 일반 timing 재개는 기존 pau 선택을 유지한다.
        # 오프닝 크기는 본문 중앙값에 의존하므로 본문 변경도 오프닝 pau를 무효화한다.
        raw = {}
        for i in sorted(set(idx_all + [0])):
            path = f"{d}/{i:02d}.wav"
            if not os.path.isfile(path):
                raise StepError(f"새 음성의 원본 조각이 없습니다: {path}")
            raw[str(i)] = _asr_identity(path, None)
        for source in sources:
            source.check()
        recipe = {k: v for k, v in item.items() if k not in ("dir", "note", "raw_provenance")}
        fingerprint = hashlib.sha256(json.dumps(
            {"raw": raw, "recipe": recipe}, sort_keys=True, ensure_ascii=False,
            allow_nan=False, separators=(",", ":")).encode()).hexdigest()
        provenance_record = {"version": 1, "sha256": fingerprint}
        previous = None
        try:
            with open(provenance_path, encoding="utf-8") as fh:
                previous = json.load(fh)
        except (OSError, ValueError):
            pass  # 기록이 없거나 손상되면 이전 사본의 정합성을 입증할 수 없다.
        if previous != provenance_record:
            removed = 0
            for i in sorted(set(idx_all + [0])):
                path = f"{d}/{i:02d}.pau.wav"
                if os.path.lexists(path):
                    os.remove(path)
                    removed += 1
            if removed:
                _progress(f"  [음성] 원본·손질 내용이 달라졌거나 기록이 없는 쉼 사본 {removed}개 무효화")
    # 지난 판 사본 제거 — 이 자가 「안 건드린다」로 일찍 돌아가면 묵은 사본이
    # 그대로 이어붙는다(tikitaka 에서 여러 번 난 사고 · build 그대로).
    for i in idx_all + [0]:
        for suf in ("shape", "lvl"):
            p = f"{d}/{i:02d}.{suf}.wav"
            if os.path.exists(p):
                os.remove(p)

    def _p90(path):
        # tikitaka build._p90 축자 — 16k 모노 f32 · 20ms(320표본) RMS dB 의 p90
        r = _spawn(_sub_argv(dec, **{"@IN@": path}), capture_output=True)
        a = np.frombuffer(r.stdout, dtype=np.float32)
        n = a.size // win
        if n < 3:
            return None
        lv = 20 * np.log10(np.sqrt((a[:n * win].reshape(n, win) ** 2).mean(1))
                           + 1e-12)
        return float(np.percentile(lv, pct))

    def _vol(src, dst, gain, eps):
        if abs(gain) < eps:
            _publish_work_file(dst, src=src, what='소리 파일을')
        else:
            run_argv(_sub_argv(vol, **{"@IN@": src, "@OUT@": dst,
                                       "@AF@": af_fmt % gain}))

    ps = {}
    for i in idx_all:
        f = f"{d}/{i:02d}.wav"
        if os.path.exists(f):
            v = _p90(f)
            if v is not None:
                ps[i] = v
    stat = {"n": len(ps), "n_shape": 0, "big": 0, "n_lvl": 0,
            "spread": None, "open_gain": None}

    # ① 문장 안 기울기 — 첫 줄 솟고 끝 줄 꺼짐(가운데 평평 · 표는 서버 값)
    if sh.get("first") is not None and len(ps) >= int(sh.get("min_pieces") or 6):
        nbin = int(sh.get("nbin") or 5)
        want = {0: float(sh["first"]), nbin - 1: float(sh["last"])}
        mid = float(sh.get("mid") or 0.0)
        eps = float(sh.get("copy_eps_db") or 0.05)
        mx = float(sh.get("max_gain_db") or 6.0)
        for ss in sents:
            idx = [i for i in ss if i in ps]
            if len(idx) < int(sh.get("min_lines") or 3):
                continue                      # 짧은 문장은 실측(자리 표)이 없다
            mu = float(np.mean([ps[i] for i in idx]))
            for k, i in enumerate(idx):
                pos = (0 if len(idx) <= 1
                       else min(nbin - 1, int(k / (len(idx) - 1) * (nbin - 0.001))))
                gain = want.get(pos, mid) - (ps[i] - mu)
                if abs(gain) > mx:            # 그건 기울기 문제가 아니다
                    stat["big"] += 1
                    continue
                _vol(f"{d}/{i:02d}.wav", f"{d}/{i:02d}.shape.wav", gain, eps)
                stat["n_shape"] += 1
        # 안 건드린 줄도 사본을 둔다 — 뒤 단계가 shape 를 먼저 집으므로,
        # 빠지면 그 줄만 옛 소리가 된다(build 그대로).
        for i in ps:
            if not os.path.exists(f"{d}/{i:02d}.shape.wav"):
                _publish_work_file(f"{d}/{i:02d}.shape.wav", src=f"{d}/{i:02d}.wav", what='소리 파일을')

    # ② 줄 크기 좁히기 — 실물보다 **넓을 때만**(평평하게 만들지 않는다)
    if sp.get("target_db") is not None:
        vals = []
        for i in idx_all:
            f = f"{d}/{i:02d}.shape.wav"
            if not os.path.exists(f):
                f = f"{d}/{i:02d}.wav"
            if os.path.exists(f):
                v = _p90(f)
                if v is not None:
                    vals.append((i, v))
        if len(vals) >= 6:
            v = np.array([x for _i, x in vals])
            cur = float(np.percentile(v, 90) - np.percentile(v, 10))
            stat["spread"] = round(cur, 2)
            tgt = float(sp["target_db"])
            lo = sp.get("floor_db")
            if not (cur <= tgt or (lo is not None and cur <= float(lo))):
                k2 = 1.0 - tgt / cur
                med = float(np.median(v))
                for i, x in vals:
                    src = f"{d}/{i:02d}.shape.wav"
                    if not os.path.exists(src):
                        src = f"{d}/{i:02d}.wav"
                    _vol(src, f"{d}/{i:02d}.lvl.wav", (med - x) * k2, 0.05)
                    stat["n_lvl"] += 1

    # ③ 오프닝 크기 — 본문 조각(파생 사본 우선) 중앙 + 실물 상대값에 맞춘다.
    #    ★언제나 원본(00.wav)에서 굽는다 — 지난 판 사본을 물면 판마다 준다.
    if op.get("rel_db") is not None:
        intro = f"{d}/{op.get('src') or '00.wav'}"
        if os.path.exists(intro):
            order = list(op.get("body_order") or ("pau", "lvl", "shape", "wav"))
            bp = []
            for i in idx_all:
                # ★for/else 로 쓰지 않는다 — 검사 「조건부 미정의 변수 0건」이
                #   else-continue 를 못 보고 `f` 를 미정의로 잡는다. 정적으로도
                #   무조건 묶이게 None 시작으로 쓴다(행동은 같다).
                f = None
                for kf in order:
                    cand = (f"{d}/{i:02d}.wav" if kf == "wav"
                            else f"{d}/{i:02d}.{kf}.wav")
                    if os.path.exists(cand):
                        f = cand
                        break
                if f is None:
                    continue
                v = _p90(f)
                if v is not None:
                    bp.append(v)
            ip = _p90(intro)
            if bp and ip is not None:
                gain = (float(np.median(bp)) + float(op["rel_db"])) - ip
                stat["open_gain"] = round(gain, 2)
                if abs(gain) > float(op.get("max_gain_db") or 6.0):
                    pass                      # 크기 문제가 아니다 — 기록만 한다
                elif abs(gain) > float(op.get("eps_db") or 0.3):
                    run_argv(_sub_argv(vol, **{
                        "@IN@": intro, "@AF@": af_fmt % gain,
                        "@OUT@": f"{d}/{op.get('out') or '00.lvl.wav'}"}))
    if provenance:
        for source in sources:
            source.check()
        try:
            _asr_save(provenance_path, provenance_record)
        except TranscriptionPending as exc:
            raise StepError("음성 파생 기록 저장 실패 — 저장 공간/권한을 확인하세요") from exc
    return stat


def render_sfx_bed(item):
    """군림보형 효과음 침대 — **자리·크기·자 전부 서버 데이터**로 굽는다.

    ★여기에는 채널 값이 하나도 없다. 어디에(spots) · 무엇을(file) · 몇 dB 아래로
      (below_db) · 어느 창으로 재는지(narr_win·ref) 전부 서버 `params` 다 —
      실행기가 문턱을 스스로 정하면 서버가 고쳐도 이 팩이 안 따라온다(§실행기 규율).
    ★수식·차례는 보존 완성본을 구운 그 코드(tikitaka build.sfx_bed)와 자리까지
      같다 — float32/float64 승격이 한 곳만 달라도 표본이 갈린다(바이트 판정).
    ★팔레트 소리가 **비어 디코드되면 멈춘다** — 원본은 조용히 건너뛰며 배치
      차례를 밀었는데, 그건 팩이 깨졌다는 뜻이라 여기서는 큰 소리로 죽는다
      (§조용한 실패 금지 · 성한 팩에서는 두 길이 같은 바이트를 낸다 — 실측).
    ★서버가 이 명령을 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
    """
    import numpy as np
    import wave

    p = item["params"]
    sr = int(p["sr"])
    dur = float(p["dur"])
    below = float(p["below_db"])
    dec = item["decode_argv"]

    def _pcm(path):
        r = _spawn(_sub_argv(dec, **{"@IN@": path}), capture_output=True)
        return np.frombuffer(r.stdout, dtype=np.float32)

    # 팔레트 전체를 디코드한다 — 침대 버퍼 길이(longest)가 여기서 나온다.
    #   (끝자리 소리를 넣을지 말지가 버퍼 길이에 달려 있어, 쓴 것만 디코드하면
    #    보존 굽기와 판정이 갈릴 수 있다)
    pal = []
    for f in item["palette"]:
        a = _pcm(f)
        if not a.size:
            raise RuntimeError(f"효과음 팔레트 소리가 비어 있다: {f} — 팩이 깨졌다. "
                               "assets 단계에서 sfx 팩을 다시 받아라")
        pal.append((f, a.copy()))
    if not pal:
        raise RuntimeError("효과음 팔레트가 비었다 — sfx 팩을 받아 풀었는지 확인하라")

    def _win_rms(x, win):
        W = max(int(sr * win), 1)
        H = max(W // 4, 1)
        return np.array([float(np.sqrt((x[i:i + W] ** 2).mean() + 1e-18))
                         for i in range(0, max(len(x) - W, 0), H)]) if len(x) > W \
            else np.array([float(np.sqrt((x ** 2).mean() + 1e-18))])

    # 나레 대비 목표 크기 — 서버가 준 창(활성 상위 pct 중앙)으로 잰다
    nx = _pcm(item["narr"])
    if not nx.size:
        raise RuntimeError(f"나레를 못 읽었다: {item['narr']} — narr 인코드가 먼저다")
    nw = _win_rms(nx, float(p["narr_win"]))
    act = nw[nw > np.percentile(nw, float(p["narr_active_pct"]))]
    narr_rms = float(np.median(act)) if act.size else float(p["narr_fallback"])
    target = narr_rms * (10 ** (below / 20))

    def _sfx_ref(a):
        how, wn = p["ref_how"], float(p["ref_win"])
        if how == "head":
            k = max(int(sr * wn), 1)
            return float(np.sqrt((a[:k] ** 2).mean() + 1e-18))
        return float(_win_rms(a, wn).max())

    by_path = dict(pal)
    longest = max(len(a) for _n, a in pal)
    bed = np.zeros(int(sr * dur) + longest, dtype=np.float32)
    used, dropped = [], []
    for s in item["spots"]:
        a = by_path.get(s["file"])
        if a is None:
            a = _pcm(s["file"])
            if not a.size:
                raise RuntimeError(f"효과음을 못 읽었다: {s['file']}")
        ref = _sfx_ref(a) or 1e-6
        # ★전환 타격은 돌출 실측(prom−base)만큼 보통 크기 위로 솟게 한다 —
        #   반올림된 게인 상수를 쓰지 않고 그 자리에서 10^(x/20) 을 계산한다
        #   (서식 하나가 표본을 민다 — 보존 바이트 판정)
        if s.get("prom") is not None:
            one = a * (target * (10 ** ((float(s["prom"]) - float(s["prom_base"])) / 20))
                       / ref)
        else:
            one = a * (target / ref)
        i = int(float(s["t"]) * sr)
        if i + len(one) <= len(bed):
            bed[i:i + len(one)] += one
            used.append(os.path.basename(s["file"]))
        else:
            dropped.append(os.path.basename(s["file"]))
    bed = bed[:int(sr * dur)]
    pk = float(np.abs(bed).max())
    clip = float(p["clip_peak"])
    if pk > clip:
        bed *= clip / pk
    st2 = np.stack([bed, bed], axis=1).reshape(-1)
    with wave.open(item["out"], "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st2 * 32767).astype("<i2").tobytes())
    return {"n": len(used), "files": sorted(set(used)),
            "dropped": dropped, "bytes": os.path.getsize(item["out"]),
            "peak": round(pk, 6), "sig": item.get("sig")}


_SOXR = "resampler=soxr:precision=28"
_MASTER_RESAMPLER = {}      # soxr 가 없는 ffmpeg 이면 {"rs": "resampler=swr"} — 한 번 정하면 그 프로세스 내내 같은 자


def master_drive(item):
    """마스터 드라이브를 **재서 맞춘다** — loudnorm 1패스 자로 이분법.

    ★목표(target_i)·천장(target_tp)·여유(limit_margin)·회수(iters)·허용오차(tol_i)
      전부 서버 `params` 다 — 여기 있는 건 «재고 좁히는» 기계뿐이다.
    ★이분법을 왕복으로 태우면 왕복이 12회다 — 서버가 자를 내려 한 왕복 안에서
      순차 실행·측정한다(measure_pieces 와 같은 규율: 판단 기준은 서버, 실행은 여기).
    ★AAC 는 트루피크를 올린다 — **이 소재로** 실제 인코딩해 재고, 상승분이
      문턱(rise_eps)을 넘어 천장을 뚫으면 limit 을 그만큼 내리고 다시 좁힌다.
    ★서버가 이 명령을 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
    """
    p = item["params"]
    ti, tt = float(p["target_i"]), float(p["target_tp"])
    margin = float(p["limit_margin"])
    iters, tol = int(p["iters"]), float(p["tol_i"])
    lo_off, hi_off = float(p["lo_off"]), float(p["hi_off"])
    rise_eps = float(p["rise_eps"])
    eq = str(p.get("eq") or "")
    mix, out = item["mix"], item["out"]
    n_bakes = [0]

    def _loud(path):
        d = measure_loudnorm({"argv": _sub_argv(item["loud_argv"], **{"@IN@": path})})
        return float(d["input_i"]), float(d["input_tp"]), float(d["input_lra"])

    lim = 10 ** ((tt - margin) / 20)

    def bake(drive):
        def chain(rs):
            return (f"{eq}volume={drive:.4f}dB,"
                    f"aresample=176400:{rs},"
                    f"alimiter=limit={lim:.6f}:level=disabled,"
                    f"aresample=44100:{rs}")
        pr = run_argv(_sub_argv(item["bake_argv"], **{"@AF@": chain(_MASTER_RESAMPLER.get("rs", _SOXR))}), capture=True)
        if (pr.returncode != 0 and "rs" not in _MASTER_RESAMPLER
                and "Requested resampling engine is unavailable" in (pr.stderr or "")):
            # ★이 컴퓨터의 ffmpeg 에 soxr 가 없다(신고 #36 · 렌더가 다 끝난 뒤 마스터에서 죽었다). 사람에게 다른 ffmpeg 를 깔라고
            #   멈추지 않고 ffmpeg 기본 리샘플러(swr)로 같은 사슬을 굽는다 — 결과 음량·트루피크는 아래가 그대로 재서 맞추므로 판정은 같다.
            #   한 번 정하면 이 프로세스의 나머지 굽기도 같은 자(두 자가 섞이지 않게).
            _MASTER_RESAMPLER["rs"] = "resampler=swr"
            _progress("  ⚠ [마스터] 이 ffmpeg 에 soxr 리샘플러가 없어 기본 리샘플러(swr)로 굽습니다", flush=True)
            pr = run_argv(_sub_argv(item["bake_argv"], **{"@AF@": chain(_MASTER_RESAMPLER["rs"])}), capture=True)
        if pr.returncode != 0:
            raise RuntimeError(f"마스터 bake 실패: {err_gist(pr.stderr, 300)}")
        n_bakes[0] += 1
        return _loud(out)

    mi, _mt, _ml = _loud(mix)
    lo, hi = ti - mi - lo_off, ti - mi + hi_off
    got = None
    for _ in range(iters):
        d = (lo + hi) / 2
        ri, rt, rl = bake(d)
        got = (d, ri, rt, rl)
        if rt > tt:                              # 천장을 넘으면 무조건 내린다
            hi = d
            continue
        if abs(ri - ti) <= tol:
            break
        if ri < ti:
            lo = d
        else:
            hi = d
    d, ri, rt, rl = got
    if rt > tt:                                  # 마지막이 넘쳤으면 안전한 쪽으로
        d, ri, rt, rl = (hi,) + bake(hi)

    # AAC 상승분 — 실제 인코딩해 잰다(지어낸 상수를 쓰지 않는다)
    rise = None
    if item.get("aac_argv"):
        m4a = item["m4a"]
        pr = run_argv(_sub_argv(item["aac_argv"], **{"@IN@": out, "@OUT@": m4a}),
                      capture=True)
        if pr.returncode != 0:
            raise RuntimeError(f"AAC 프로브 인코드 실패: {err_gist(pr.stderr, 300)}")
        before = _loud(out)[1]
        after = _loud(m4a)[1]
        try:
            os.remove(m4a)
        except OSError:
            pass
        rise = round(after - before, 3)
        if rise > rise_eps and rt + rise > tt:
            lim = 10 ** ((tt - margin - rise) / 20)
            lo, hi = ti - mi - lo_off, ti - mi + hi_off
            got = None
            for _ in range(iters):
                dd = (lo + hi) / 2
                ri2, rt2, rl2 = bake(dd)
                got = (dd, ri2, rt2, rl2)
                if rt2 + rise > tt:
                    hi = dd
                    continue
                if abs(ri2 - ti) <= tol:
                    break
                if ri2 < ti:
                    lo = dd
                else:
                    hi = dd
            d, ri, rt, rl = got
            if rt + rise > tt:
                d, ri, rt, rl = (hi,) + bake(hi)
    return {"drive": d, "I": ri, "TP": rt, "LRA": rl, "mix_I": mi,
            "rise": rise, "limit": lim, "n_bakes": n_bakes[0],
            "sig": item.get("sig")}


def measure_hf(item):
    """8k~16k 세기(dBFS) — 실물을 잰 그 자(m_opensound 밴드FIR)를 numpy 로 든다.

    ★자가 둘이면 갈린다 — 선형위상 FIR(kaiser) 대역통과를 **파일 전체**에 걸고
      전체 RMS 를 낸다. 탭수·β·대역·표본율 전부 서버 `params` 다.
    ★모노 내리기는 (L+R)/2 다 — ffmpeg `-ac 1` 은 +3.01dB 를 얹는다(실측).
      그래서 argv 는 스테레오로 디코드하고 여기서 내린다.
    ★scipy 없이 계산한다(배급 기계 요건은 numpy 까지다) — firwin(대역통과·
      scale)·fftconvolve('same')를 같은 정의로 재현했고, scipy 자와의 차는
      1e-6dB 아래임을 보존 완성본으로 실측했다(선반 서식 .3f 에 안 닿는다).
    """
    import numpy as np

    p = item["params"]
    sr = int(p["sr"])
    lo, hi = float(p["lo_hz"]), float(p["hi_hz"])
    ntaps, beta = int(p["ntaps"]), float(p["beta"])
    # ★run_argv(capture=True) 는 텍스트 파이프다 — PCM 은 **바이트**로 받아야 한다
    r = _spawn(item["argv"], capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    if a.size < 4:
        raise RuntimeError("고역을 잴 소리를 못 읽었다 — audio_sfx.wav 가 있는지 보라")
    a = a[: (a.size // 2) * 2].reshape(-1, 2)
    x = (a[:, 0] + a[:, 1]) / 2.0
    # FIR 설계 — firwin(ntaps, [lo, hi], pass_zero=False, kaiser β) 재현
    m = np.arange(0, ntaps) - (ntaps - 1) / 2.0
    fl, fh = lo / (sr / 2.0), hi / (sr / 2.0)
    h = fh * np.sinc(fh * m) - fl * np.sinc(fl * m)
    h *= np.kaiser(ntaps, beta)
    h /= float(np.sum(h * np.cos(np.pi * m * ((fl + fh) / 2.0))))
    # 'same' 합성곱 — 한 번의 FFT (2의 거듭제곱 패딩)
    n = int(x.size) + ntaps - 1
    nfft = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:n]
    st = (ntaps - 1) // 2
    y = y[st:st + x.size]
    ms = float((y ** 2).mean())
    return {"hf": float(10 * np.log10(max(ms, 1e-30))), "sig": item.get("sig")}


def measure_openvoice(item):
    """오프닝/본문 목소리 «바닥 위» 크기 — 실물을 잰 그 자(m_openvoice)다.

    20ms 창 RMS(dB)의 p90(구간) − p10(전체 바닥). 창·표본율·구간(-ss/-t) 전부
    서버가 argv·params 로 준다. **판정(얼마나 키울지)은 서버가 한다** — 여기는
    재기만. 너무 짧아 못 재면 ok=False 로 말한다(0 이 아니다).
    """
    import numpy as np

    p = item["params"]
    sr = int(p["sr"])
    W = int(sr * float(p["win"]))

    def lv(argv):
        r = _spawn(argv, capture_output=True)
        a = np.frombuffer(r.stdout, np.float32)
        if a.size < W:
            return None
        n = a.size // W
        rr = np.sqrt((a[:n * W].reshape(n, W) ** 2).mean(axis=1) + 1e-12)
        return 20 * np.log10(rr)

    al = lv(item["all_argv"])
    op = lv(item["open_argv"])
    bd = lv(item["body_argv"])
    if al is None or op is None or bd is None:
        return {"ok": False, "sig": item.get("sig")}
    fl = float(np.percentile(al, 10))
    return {"ok": True, "floor": fl,
            "open": float(np.percentile(op, 90)) - fl,
            "body": float(np.percentile(bd, 90)) - fl,
            "sig": item.get("sig")}


def measure_sfx(item):
    """내가 넣은 효과음 파일들을 **서버가 정한 자로** 잰다 → {파일명: {dur,pk,cen,atk}}.

    ★임계값(어느 범위가 그 부류인가)은 여기 없다 — 서버의 `SFX_ENVELOPE` 가 판정한다.
      여기 있는 건 재는 방법뿐이고, 창 길이·홉·표본율도 서버가 `params` 로 내려준다.
    ★ffmpeg 명령도 서버가 짓는다(파일마다 `argv`). 실행기가 지으면 결과가 갈린다 —
      `-ac 1 -ar 48000` 이 한 글자만 달라도 밝기·레벨이 통째로 어긋난다.
    ★`pcm_f32le` 로 받는다. 16비트로 받으면 같은 소리가 **3.01dB 낮게** 나온다(실측).
    """
    import numpy as np

    p = item["params"]
    sr = int(p["sr"])
    n = int(sr * float(p["win"]))
    hop = int(sr * float(p["hop"]))
    out = {}
    for f in item.get("files") or []:
        raw = _spawn(f["argv"], capture_output=True).stdout
        isz = np.dtype("<f4").itemsize
        x = np.frombuffer(raw[: (len(raw) // isz) * isz], dtype="<f4").astype("float64")
        if x.size < 16:
            continue                       # 소리가 없다 — 재지 않은 것으로 둔다
        dur = x.size / float(sr)
        # 단기 피크 — 창보다 짧은 소리는 0 으로 채워 같은 자로 잰다
        xx = x if x.size >= n else np.concatenate([x, np.zeros(n - x.size)])
        pk = max(20.0 * np.log10(max(float(np.sqrt(np.multiply(
            xx[i:i + n], xx[i:i + n]).mean())), 1e-12))
            for i in range(0, xx.size - n + 1, hop))
        # 밝기 — 스펙트럼 중심
        w = np.abs(np.fft.rfft(np.multiply(x, np.hanning(x.size))))
        fr = np.fft.rfftfreq(x.size, 1.0 / sr)
        cen = float(np.multiply(w, fr).sum() / max(float(w.sum()), 1e-9))
        # 어택 — 최대치의 절반에 처음 닿은 뒤 최대치까지 걸린 시간
        e = np.abs(x)
        k = int(np.argmax(e))
        half = float(e[k]) / 2.0
        on = k
        for i in range(k + 1):
            if e[i] >= half:
                on = i
                break
        out[f["name"]] = {"dur": round(dur, 3), "pk": round(pk, 2),
                          "cen": round(cen, 1), "atk": round((k - on) * 1000.0 / sr, 1)}
    return out


def measure_audio(item):
    """음악을 **서버가 정한 자로** 잰다 → dict.

    ★임계값은 여기 없다. 여기 있는 건 재는 방법(FFT 크기·홉·고역 경계 …)뿐이고
      그것도 서버가 `params` 로 내려준다 — 실행기에 기본값을 두지 않는다는 규칙 그대로다.
    ★ffmpeg 명령도 서버가 짓는다(`loud_argv`·`pcm_argv`). 실행기가 지으면 결과가 갈린다.
    """
    import numpy as np

    p = item["params"]
    lp = run_argv(item["loud_argv"], capture=True)
    txt = lp.stderr or ""
    i, j = txt.rfind("{"), txt.rfind("}")
    if i < 0 or j <= i:
        raise RuntimeError("라우드니스를 못 읽었다 — argv 를 고치지 않았는지 확인하라.")
    ln = json.loads(txt[i:j + 1])

    raw = _spawn(item["pcm_argv"], capture_output=True).stdout
    isz = np.dtype("<f4").itemsize
    x = np.frombuffer(raw[: (len(raw) // isz) * isz], dtype="<f4").astype("float64")
    sr, n, hop = p["sr"], p["n_fft"], p["hop"]
    if x.size < n * p["min_frames"]:
        raise RuntimeError(f"음악이 너무 짧다: {x.size / max(sr, 1):.2f}초")
    nf = 1 + (x.size - n) // hop
    win = np.hanning(n)
    S = np.empty((nf, n // 2 + 1))
    for k in range(nf):
        S[k] = np.abs(np.fft.rfft(np.multiply(x[k * hop:k * hop + n], win)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    e = S.sum(axis=1)
    keep = e > (np.median(e) * p["floor_frac"])
    Sf, ef = S[keep], np.maximum(e[keep], 1e-9)
    cen = np.divide(np.multiply(Sf, freqs[None, :]).sum(axis=1), ef)
    hfr = np.divide(Sf[:, freqs >= p["hf_hz"]].sum(axis=1), ef)

    flux = np.clip(np.diff(S, axis=0), 0, None).sum(axis=1)
    sm = p["onset_smooth"]
    base = np.convolve(flux, np.ones(sm) / float(sm), mode="same")
    peaks, last = 0, -99
    for k in range(1, flux.size - 1):
        if (flux[k] > base[k] * p["onset_k"] and flux[k] >= flux[k - 1]
                and flux[k] >= flux[k + 1] and k - last >= p["onset_gap"]):
            peaks, last = peaks + 1, k

    # ★강약은 **소리가 나는 구간에서만** 잰다. 곡 앞뒤의 디지털 무음을 같이 재면
    #   p5 가 −180dB 로 내려가 강약이 163dB 로 나온다(실측에서 실제로 그랬다).
    #   그러면 "강약 없는 드론" 게이트가 무음 덕에 통과한다 — 조용한 실패다.
    w = max(int(sr * p["env_win"]), 1)
    rms = np.array([float(np.sqrt(np.mean(np.square(x[b * w:(b + 1) * w]))))
                    for b in range(x.size // w)])
    live = rms[rms > max(float(np.median(rms)) * p["floor_frac"], 1e-9)]
    env = 20 * np.log10(np.maximum(live, 1e-9))
    dur = x.size / float(sr)
    return {"dur": round(dur, 2), "lufs": float(ln["input_i"]),
            "tp": float(ln["input_tp"]), "lra": float(ln["input_lra"]),
            "brightness_hz": round(float(np.median(cen)), 1),
            "hf_ratio": round(float(np.median(hfr)), 3),
            "onset_per_s": round(peaks / dur, 2),
            "dyn_db": round(float(np.percentile(env, 95) - np.percentile(env, 5)), 2)}


def _tracking_scene_samples(log, start, duration, tick):
    """Read actual decoded PTS around cuts; nominal FPS cannot locate VFR neighbors."""
    groups={}
    for line in log.splitlines():
        m=re.search(r"Parsed_showinfo_(\d+).*?pts_time:([0-9.]+)",line)
        if m:groups.setdefault(int(m.group(1)),[]).append(start+float(m.group(2)))
    all_frames=sorted(set(groups.get(0,[])))
    cuts=sorted(set(t for t in groups.get(2,[]) if start<t<start+duration))
    chosen=[]
    for cut in cuts:
        before=[t for t in all_frames if t<cut]
        if before:chosen.append(before[-1])
        chosen.append(cut)
    return (all_frames[0] if all_frames else start),cuts,chosen,all_frames


def scene_cuts(item):
    """장면 전환 시각(초) — **서버가 준 argv 를 돌리고 stderr 에서 읽기만 한다.**

    ★argv 를 여기서 짓지 않는다(실행기가 명령을 지으면 결과가 갈린다).
    ★`-v error` 를 붙이면 showinfo 줄이 사라져 **아무것도 안 잡힌다** —
      효과음 게인 사고와 같은 부류라 서버가 그렇게 안 준다.
    """
    p = _spawn(item["argv"], capture_output=True, **TEXT_PIPE)
    if p.returncode != 0:
        raise StepError(f"장면 전환 측정 실패 (exit {p.returncode}): {err_gist(p.stderr, 800)}")
    out = []
    for m in re.finditer(r"pts_time:([0-9.]+)", (p.stderr or "") + (p.stdout or "")):
        out.append(round(float(m.group(1)), 3))
    return sorted(set(out))


def wav_seconds(path):
    import math
    p = run_argv(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "csv=p=0", path], capture=True)
    raw = (p.stdout or '').strip()
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        seconds = float('nan')
    if p.returncode == 0 and raw == 'N/A' and str(path).lower().endswith('.wav'):
        # ★ffprobe 가 머리글에 길이가 없는 WAV 에 «N/A» 를 낸다(2026-10-17 뇌전구 voice · ffmpeg 9.0.1) — PCM WAV 는 표본 수÷표본률이
        #   길이 자체다. 파이썬 wave 로 data 덩이를 읽고, 머리글 크기가 파일보다 크면(스트리밍 머리글) 실제 남은 바이트로 센다.
        try:
            import wave                                             # noqa: PLC0415
            with wave.open(str(path), 'rb') as fh:
                rate, frame_bytes = fh.getframerate(), fh.getsampwidth() * fh.getnchannels()
                frames = fh.getnframes()
                start = fh._data_chunk.offset + 8 if hasattr(fh, '_data_chunk') else None
            if start is not None and frame_bytes:
                frames = min(frames, max(0, (os.path.getsize(path) - start) // frame_bytes))
            seconds = frames / rate if rate else float('nan')
        except (OSError, EOFError, wave.Error, AttributeError) as wave_error:
            raw = f'N/A · wave 로도 못 읽음({type(wave_error).__name__}: {str(wave_error)[:80]})'
    if p.returncode or not math.isfinite(seconds) or seconds <= 0:
        executable = p.args[0] if isinstance(p.args, (list, tuple)) and p.args else 'ffprobe'
        raise StepError(f'길이 측정 실패: {path}\n'
                        f'  ffprobe={executable}, exit={p.returncode}, stdout={raw[:160]!r}\n'
                        f'  {err_gist(p.stderr, 800)}')
    return seconds


def lufs_of(argv):
    """서버가 준 argv 로 재서 **통합 라우드니스와 피크**를 뽑는다.

    ★★argv 를 **여기서 짓지 않는다**(2026-08-19 고침). 예전에는 이 함수가 ffmpeg
      명령을 직접 만들었고, 그러면 서버가 자를 고쳐도 수강생 팩이 안 따라온다 —
      이 저장소가 `-v error`(효과음 +23dB)와 `alimiter` 기본값에서 이미 두 번 당한
      부류다. 경계 검사 *"실행기가 ffmpeg 명령을 짓지 않는다"* 가 그것을 잡았다.

    ★TTS 는 문장마다 크기가 제각각이다(실측 2026-08-18: 같은 편에서 −16.0 ~ **−25.9**).
      그대로 이어 붙이면 한 문장만 확 작게 들린다.
    ★`volumedetect` 의 mean_volume 이 아니라 **EBU R128 통합값**을 쓴다 —
      사람이 느끼는 크기는 평균 진폭이 아니다(이 저장소가 음악에서 이미 쓴 자).
    ★피크도 함께 돌려준다 — 게인만 올리면 **찌그러진다**. 서버가 피크 여유 안에서
      게인을 정할 수 있어야 한다(실측: −25.9 LUFS 파일의 피크가 −9.1dB 라 필요한
      게인 8.9dB 를 다 못 준다).
    """
    p = run_argv(list(argv), capture=True)
    err = p.stderr or ""
    m = re.search(r"Input Integrated:\s*(-?[\d.]+)", err)
    mx = re.search(r"max_volume:\s*(-?[\d.]+)", err)
    return {"lufs": float(m.group(1)) if m else None,
            "peak": float(mx.group(1)) if mx else None}


def frame_seconds(path, fps=None):
    """길이를 **프레임 수**로 잰다 — 이어붙였을 때의 실제 길이다.

    ★컨테이너의 `format=duration` 은 이것과 다를 수 있다(실측 2026-08-18: 조각 26개
      중 4개가 정확히 1프레임씩 더 크게 기록돼 합계가 +0.131초 어긋났고, 그것이
      '누적 드리프트' 로 잘못 보고돼 완주가 막혔다). **이어붙이기는 프레임을 잇는다** —
      같은 조각들을 실제로 concat 하니 프레임 자가 오차 0.0000초로 맞았다.
    ★fps 는 **파일에서 읽는다** — 서버가 알려줄 필요가 없고(그건 명세값이라
      응답에 실으면 노하우가 새 나간다), 소스마다 다를 수도 있다.
    """
    p = run_argv(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                  "-show_entries", "stream=nb_read_frames,r_frame_rate",
                  "-of", "csv=p=0", path], capture=True)
    parts = [x for x in p.stdout.strip().split(",") if x]
    rate = next(x for x in parts if "/" in x)
    frames = int(next(x for x in parts if "/" not in x))
    num, den = rate.split("/")
    return frames / (float(num) / float(den))


# 알맹이가 프레임의 이만큼도 안 되면 "다 띠" 라는 말이라 믿지 않는다.
# ★이건 규격이 아니라 **자기 자신의 건전성 검사**라 실행기에 둔다 — 이 값이 바뀐다고
#   화면이 달라지지 않는다(알맹이가 이만큼 작은 프레임은 애초에 쓸 수 없다).
MIN_CONTENT = 1.0 / 5
# 이보다 얇게 벗기는 것은 **띠가 아니라 잡음**이다(경계 안티에일리어싱 1~2px).
# ★서버의 `BAND_MAX` 가 이미 그만큼은 띠로 안 치므로 여기서 벗겨도 얻는 게 없고,
#   실물 완성본을 1~2px 깎아 "과잉 제거" 로 보이게 만든다(실측 12건 중 11건이 그것).
MIN_BAR = 3


def _content_rect(gray, thr, frac):
    """이 프레임에서 **소재 자신의 검은 띠를 뺀** 알맹이 사각형 (x, y, w, h).

    ★소재가 자체 레터박스를 갖고 있으면 파일 프레임 전체를 창에 맞출 때 그 띠가
      그대로 화면에 들어온다.
    ★`flat`(표준편차)이 아니라 **검은 화소 비율**로 본다 — 워터마크가 얹힌 띠는
      편차가 크지만 여전히 띠다.
    ★★**한 장으로 판정하면 안 된다.** 이 자를 한 장에 걸었더니 화면이 거의 검은
      장면(평균 밝기 1.6)을 레터박스로 읽어, 자체 띠가 **없는** 소재를
      "좌 496 · 하 280" 으로 오판했다. 같은 소재의 밝은 시각에서는 띠가 0 이다.
      레터박스는 **소재의 성질이라 시간에 대해 고정**이고 장면 밝기는 아니다 →
      여러 시각의 **교집합(가장 작은 띠)** 을 쓴다(`_content_rect_over`).
    """
    import numpy as np
    gray = np.asarray(gray).astype(int)
    h, w = gray.shape

    def eat(axis, rev):
        n = h if axis == 0 else w
        k = 0
        for i in range(n):
            j = (n - 1 - i) if rev else i
            line = gray[j] if axis == 0 else gray[:, j]
            # ★`max` 로 보면 **띠 안의 워터마크에서 멈춘다.** 방송 아카이브는 검은 띠
            #   위에 로고를 얹는다 — 그 행은 86~92% 가 검은데 `max` 는 200 이 넘는다
            #   (실측: BEup 컷24 가 상63 에서 멈춰 상46·하96 이 화면에 남았다).
            #   띠는 "**대부분이 검은** 줄" 이므로 중앙값과 검은 화소 비율로 본다.
            if float(np.median(line)) < thr and float((line < thr).mean()) >= frac:
                k += 1
            else:
                break
        return k

    # ★★**수렴할 때까지 반복한다.** 한 번만 벗기면 **이중 레터박스**를 못 잡는다 —
    #   이 자는 행/열 **전체**를 보므로, 좌우 필러박스를 벗기기 전에는 그 안쪽의
    #   상하 띠가 행 통계에 묻힌다(실측: 좌우 146px 을 낀 채 보면 상단 검은 줄이
    #   "17% 만 검은 콘텐츠 행" 으로 보인다). 좌우를 먼저 벗기고 다시 보면 드러난다.
    #   방송 아카이브에 실제로 그 구조가 있고, 그것 때문에 상42·하98 이 화면에 남았다.
    # ★횟수를 세지 않는다 — 매 라운드가 **반드시 줄어들거나**(≥MIN_BAR) 멈추므로
    #   저절로 끝난다. 숫자를 적으면 그게 배급 코드의 상수가 되고, 명세 잎값과
    #   우연히 겹치면 검사 [20](명세 유출)에 걸린다 — 실제로 걸렸다.
    ox, oy = 0, 0
    while True:
        top, bot = eat(0, False), eat(0, True)
        left, right = eat(1, False), eat(1, True)
        top, bot = (top if top >= MIN_BAR else 0), (bot if bot >= MIN_BAR else 0)
        left, right = (left if left >= MIN_BAR else 0), (right if right >= MIN_BAR else 0)
        if not (top or bot or left or right):
            break
        nh, nw = h - top - bot, w - left - right
        # ★전부 검은 프레임(장면 전환 순간)은 알맹이가 없다 — 통째로 돌려준다.
        if nw < w * MIN_CONTENT or nh < h * MIN_CONTENT:
            return [0, 0, w, h]
        gray = gray[top:top + nh, left:left + nw]
        ox, oy = ox + left, oy + top
        h, w = nh, nw
    return [ox, oy, w, h]


def _content_rect_over(grays, thr, frac, dark):
    """여러 프레임의 **교집합** 알맹이 — 띠는 모든 프레임에 있고 어두운 장면은 아니다.

    ★어두워서 아무것도 못 읽는 프레임(거의 전부 검은 것)은 **빼고** 센다.
      그런 프레임은 "띠가 화면 전체" 라고 말하는데 그건 정보가 아니다.
      다 어두우면 뺄 것이 없으므로 전체 프레임을 알맹이로 본다(fail-open이 아니라
      **아무것도 안 자르는 쪽** = 지금까지의 동작 그대로다).
    """
    import numpy as np
    rects = []
    shape = None
    first_shape = None
    for gray in grays:
        a = np.asarray(gray)
        if first_shape is None:
            first_shape = a.shape
        if not float(a.mean()) >= dark:
            continue
        if shape is None:
            shape = a.shape
        # Expand one frame at a time. Keeping all int64 frames multiplies
        # memory by eight before parallel cuts begin detector inference.
        rects.append(_content_rect(a.astype(int), thr, frac))
    if not rects:
        if first_shape is None:
            raise ValueError("content measurement needs at least one frame")
        h, w = first_shape
        return [0, 0, int(w), int(h)]
    h, w = shape
    # ★**중앙값**이다. 처음엔 최소(교집합)를 썼는데 **한 장의 예외에 무너진다** —
    #   컷 시작 프레임 하나가 장면 전환 잔상이면 그 컷의 띠가 통째로 0 이 됐다
    #   (실측: 8장 중 7장이 상135 인데 결과는 상0). 어두운 프레임은 위에서 이미
    #   뺐으므로, 남은 표본의 다수가 동의하는 띠를 택하는 것이 맞다.
    import statistics as _st
    left = int(_st.median([r[0] for r in rects]))
    top = int(_st.median([r[1] for r in rects]))
    right = int(_st.median([w - (r[0] + r[2]) for r in rects]))
    bot = int(_st.median([h - (r[1] + r[3]) for r in rects]))
    cw, ch = w - left - right, h - top - bot
    if cw < w * MIN_CONTENT or ch < h * MIN_CONTENT:
        return [0, 0, int(w), int(h)]
    return [int(left), int(top), int(cw), int(ch)]


def _face_cascade():
    """정면 얼굴 분류기. **없으면 멈춘다** — 조용히 넘어가면 구도가 오류 없이 틀린다.

    ★2026-09-14 실측: opencv 5.0 은 `CascadeClassifier` 를 없앴고, 이 자리가 그 부재를
      `except Exception` 으로 삼켜 엣지 무게중심으로 대체했다 → 얼굴 중심 (.17,.13) 이
      (.49,.44) 가 되어 크롭이 통째로 밀렸다(img43/01.png). 「얼굴이 없다」(None) 와
      「부품이 없다」(예외) 는 다른 말이다. 서버 env 게이트도 같은 부품을 재지만,
      프로브를 지나 실행기 파이썬이 바뀌는 경우까지 여기서 한 번 더 막는다.
    """
    import cv2
    import os
    path = os.path.join(getattr(getattr(cv2, "data", None), "haarcascades", ""),
                        "haarcascade_frontalface_default.xml")
    if not hasattr(cv2, "CascadeClassifier") or not os.path.isfile(path):
        raise StepError("이 opencv(" + str(getattr(cv2, "__version__", "?")) + ")에는 얼굴 부품"
                        "(CascadeClassifier·haarcascade)이 없습니다 — 5.0 부터 빠졌습니다. "
                        "4.x 로 다시 설치하세요 — env 단계가 주는 설치 한 줄을 그대로 쓰면 됩니다")
    # ★2026-10-20 우팔롬아 신고(C:/Users/<수강생>/… · 한글 사용자 이름): 윈도우 OpenCV 는 파일 이름을 ANSI 로 열어 한글 등 비ASCII 경로를
    #   못 연다(persistence.cpp «Can't open file») → 정상 4.x 인데 empty() 였다. 파이썬이 읽어 메모리로 넘긴다 —
    #   OpenCV 의 load(파일) 도 FileStorage 를 열어 read(첫 노드) 하는 것이라(cascadedetect.cpp) 결과가 같다.
    try:
        with open(path, "rb") as f:
            xml = f.read().decode("utf-8")
        fs = cv2.FileStorage(xml, cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)  # 노드를 읽는 동안 살아 있어야 한다
        cas = cv2.CascadeClassifier()
        cas.read(fs.getFirstTopLevelNode())
        fs.release()
    except Exception as exc:  # noqa: BLE001 — 삼키지 않는다. 사유를 붙여 **멈춘다**
        raise StepError("얼굴 부품(CascadeClassifier)을 열지 못했습니다: " + type(exc).__name__ + ": " + str(exc)[:160]
                        + " — opencv 를 4.x 로 다시 설치하세요") from exc
    if cas.empty():
        raise StepError("얼굴 부품 파일을 읽지 못했습니다: " + path + " — opencv 를 4.x 로 다시 설치하세요")
    return cas


def _face_box(gray):
    """가장 큰 정면 얼굴 (x, y, w, h) 또는 None(얼굴이 없다). 일반 OpenCV 기술이다."""
    import cv2
    h0, w0 = gray.shape
    cas = _face_cascade()
    sc = 900 / max(w0, h0)
    gs = cv2.resize(gray, (int(w0 * sc), int(h0 * sc))) if sc < 1 else gray
    f = cas.detectMultiScale(gs, 1.08, 5, minSize=(40, 40))
    if len(f):
        x, y, w, h = max(f, key=lambda r: r[2] * r[3])
        k = 1 / sc if sc < 1 else 1.0
        return [int(x * k), int(y * k), int(w * k), int(h * k)]
    return None


def _edge_center(gray):
    """엣지 무게중심 (cx, cy) 비율. 얼굴이 없을 때의 대체 피사체 위치.

    ★이 자는 **글자에 끌린다** — 자막·로고가 박힌 소재에서 무게중심이 글자로 간다.
      그래서 서버가 "얼굴로 잡은 것인가" 를 알 수 있게 `by` 를 같이 돌려준다.
    """
    import numpy as np
    h0, w0 = gray.shape
    import cv2
    small = cv2.resize(gray, (max(w0 // 8, 1), max(h0 // 8, 1))).astype(float)
    gx = np.abs(np.diff(small, axis=1, prepend=small[:, :1]))
    gy = np.abs(np.diff(small, axis=0, prepend=small[:1, :]))
    e = gx + gy
    if e.sum() <= 0:
        return (0.5, 0.5)
    e = e / e.sum()
    ys = np.arange(e.shape[0], dtype=float).reshape(-1, 1)
    xs = np.arange(e.shape[1], dtype=float).reshape(1, -1)
    return (float(np.multiply(e, xs).sum()) / max(e.shape[1] - 1, 1),
            float(np.multiply(e, ys).sum()) / max(e.shape[0] - 1, 1))


# Canonical CV modules keep their detector/engine cached and mutate its input
# size. The runner executes cuts concurrently, so one lock owns that state.
# ★이 잠금이 지키는 것은 «검출기 상태»다(YuNet 한 벌이 입력 크기를 바꿔 가며 쓴다 · 모듈 적재) — 한 번에 한 장만 추론한다.
#   풀어도 크게 빨라지지 않는다(2026-10-05 실측 · 진짜 모델 · 1080p 24~48장 · 같은 설정끼리도 최대 1.55배 흔들림):
#   onnxruntime 이 한 장에 이미 코어 7개 남짓을 쓴다. i7-9700 8코어: 잠금 1스레드 1318~2058ms/장(RSS 1.06GB) ↔
#   잠금 없이 6스레드 989~1164ms/장(RSS 3.4~3.6GB) = 약 1.3~1.8배에 메모리 약 3.4배 · 12스레드는 6스레드보다 빠르지 않고
#   RSS 5.1~5.5GB. 16GB 기계에서 스레드를 늘려 얻는 것이 없다.
#   그래서 폭은 그대로 1 이고, 잠금이 **잡는 범위만** 추론으로 좁혔다 — 파일 읽기·지문·캐시 조회는 잠금 밖이다.
#   (예전에는 컷 하나의 측정 전체를 잡아, 이미 다 잰 컷도 다른 컷의 몇 분짜리 추론이 끝날 때까지 줄을 섰다.)
_FRAMEVISION_MODULES = {}
_FRAMEVISION_LOADED_IDENTITIES = {}
_FRAMEVISION_LOCK = __import__("threading").RLock()
_FRAMEVISION_RAW_VERSION = 1


def _framevision_identity(root):
    """The installed detector bytes and effective knobs, shared by both callers."""
    import importlib.metadata
    from pathlib import Path
    root = Path(root).expanduser().resolve()
    files = {str(p.relative_to(root)): _image_file_sha(p) for p in sorted(root.rglob('*'))
             if p.is_file() and p.suffix in ('.py', '.onnx')}
    packages = {}
    # onnxruntime 을 주는 배포판은 기계마다 다르다 — 윈도우 env 단계는 onnxruntime-directml 로 깐다(volcano_spec ORT_DML_PIP).
    #   그 이름이 없으면 그 기계의 지문에 onnxruntime 판이 아예 빠져 판이 바뀌어도 못 본다(10-22 뇌전구 신고 조사).
    for name in ('opencv-python', 'opencv-python-headless', 'numpy', 'Pillow', 'onnxruntime', 'onnxruntime-silicon',
                 'onnxruntime-directml'):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: pass
    return {'root':str(root), 'files':files, 'packages':packages,
            'score':float(os.environ.get('MOON_YUNET_SCORE') or '.7'),
            'multiscale':os.environ.get('MOON_YUNET_MULTISCALE', '1') != '0',
            'environment':{k:v for k,v in os.environ.items() if k.startswith('MOON_YUNET')},
            'model_location':'installed framevision/models; canonical runner ignores external model overrides'}


def _framevision_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _framevision_raw_valid(value, width, height):
    """Validate the detector's normalized face xywh and pixel text xyxy."""
    import math
    if not isinstance(value, dict) or set(value) != {'faces', 'texts'}:
        return False
    for kind in ('faces', 'texts'):
        rows = value[kind]
        if not isinstance(rows, list):
            return False
        for box in rows:
            if (not isinstance(box, list) or len(box) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
                return False
            x, y, a, b = box
            if kind == 'faces':
                # The canonical module rounds each normalized component to
                # four decimals, so an edge may exceed 1 by one rounding unit.
                if not (x >= 0 and y >= 0 and a > 0 and b > 0
                        and x + a <= 1.000100001 and y + b <= 1.000100001):
                    return False
            elif not (0 <= x < a <= width and 0 <= y < b <= height):
                return False
    return True


def _framevision_cached(path, key, identity, source, width, height):
    try:
        with open(path, encoding='utf-8') as stream:
            row = json.load(stream)
        if (isinstance(row, dict) and type(row.get('version')) is int
                and row['version'] == _FRAMEVISION_RAW_VERSION and row.get('key') == key
                and row.get('identity') == identity and row.get('input') == source
                and _framevision_raw_valid(row.get('result'), width, height)
                and row.get('result_sha256') == _framevision_digest(row['result'])):
            return row['result']
    except (OSError, ValueError, TypeError):
        pass
    return None


def _framevision_modules(root, identity):
    """Only a miss loads models; model/code/config mutation replaces both sessions."""
    import importlib.util
    modules = _FRAMEVISION_MODULES.get(root)
    if modules is not None and _FRAMEVISION_LOADED_IDENTITIES.get(root) == identity:
        return modules
    _FRAMEVISION_MODULES.pop(root, None)
    _FRAMEVISION_LOADED_IDENTITIES.pop(root, None)
    modules = []
    for name in ('facelib_cv', 'ocrdet'):
        path = os.path.join(root, name + '.py')
        if not os.path.isfile(path):
            missing = StepError('화면 측정 팩이 없습니다: ' + path +
                                ' — assets 단계에서 framevision 팩을 설치한 뒤 이 컷을 다시 측정하세요.')
            # ★환경 원인이라는 표지 (2026-10-05 · 원장 W2-16 · 묶음 사이 약속) — 부르는 쪽(C 묶음 local_focus)이
            #   이 컷을 «영구 blocked» 가 아니라 «팩이 들어오면 다시 잰다» 로 저장할 수 있게 한다.
            missing.code = 'framevision_pack_missing'
            raise missing
        spec = importlib.util.spec_from_file_location('_volcano_' + name, path)
        module = importlib.util.module_from_spec(spec)
        # A same-size source replacement can retain a pyc timestamp. Execute
        # the actual fingerprinted source instead of a possibly stale pyc.
        with open(path, 'rb') as stream:
            exec(compile(stream.read(), path, 'exec'), module.__dict__)
        modules.append(module)
    model_path = os.path.join(root, 'models', modules[0].MODEL_NAME)
    # Capturing the modules list would retain the replaced OCR session in a cycle.
    modules[0].model_path = lambda: model_path
    try:
        modules.append(modules[1].Detector(os.path.join(root, 'models', 'ppocrv5_server_det.onnx')))
    except Exception as exc:
        broken = StepError('글자 측정 모델을 열 수 없습니다 — framevision 팩/onnxruntime 환경을 다시 설치하세요: ' + str(exc))
        broken.code = 'framevision_environment'      # 환경 원인 — 설치가 바뀌면 다시 잰다(W2-16)
        raise broken from exc
    _FRAMEVISION_MODULES[root] = modules
    _FRAMEVISION_LOADED_IDENTITIES[root] = identity
    return modules


def _framevision_measure(paths, width, height, root, cache_dir=None, detector_identity=None, before_measure=None):
    """Packaged canonical YuNet + PP-OCR server detection, boxes in content pixels.

    Models never download as a side effect. Missing pack/dependency is an
    actionable measurement failure, not a made-up central subject.

    ■ 잠금·캐시 (2026-10-05)
        · 추론(모듈 적재 + 얼굴 + 글자)만 `_FRAMEVISION_LOCK` 안이다. 입력 읽기·지문·캐시 조회·집계는 밖이다.
        · 잠금을 얻은 뒤 캐시를 **한 번 더** 읽는다 — 같은 그림을 기다리던 다른 컷이 이미 쟀으면 추론하지 않는다.
        · 캐시 행은 **잰 즉시** 쓴다. 예전에는 호출이 끝나야 한꺼번에 써서, 컷 하나(수십~수백 장)를 재다
          프로세스가 끊기면(창 닫힘·시간 초과로 종료·전원) 그 컷에서 잰 것이 전부 사라졌다.
        · 예전 보장은 그대로다: **실패로 끝난 호출은 아무 행도 남기지 않는다**(입력이 도중에 바뀜·모델이 도중에
          바뀜·검출 실패) — 이 호출이 쓴 행을 도로 지운다. 남는 것은 «끊긴» 호출이 잰 행뿐이고, 그 행들은
          하나하나 «잰 직후 입력 바이트 재확인» 을 통과한 것이다.
    """
    import io
    import statistics
    from PIL import Image
    import numpy as np
    root=os.path.realpath(os.path.expanduser(str(root)))
    identity = _framevision_identity(root)
    if detector_identity is not None and detector_identity != identity:
        raise StepError('피사체 측정 중 모델 또는 설정이 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
    track=[]; texts=[]; counts=[]; face_candidates=[]; text_candidates=[]
    measured = {}; written = []; sources = {}

    def infer(path, content, source_sha):
        """One native inference; the caller holds the detector lock."""
        if before_measure: before_measure()
        modules = _framevision_modules(root, identity)
        detected = modules[0].faces(path)
        with Image.open(io.BytesIO(content)) as image:
            rgb = np.asarray(image.convert('RGB'))
        raw = dict(faces=[[f[k] for k in ('x', 'y', 'w', 'h')] for f in (detected or [])],
                   texts=[list(box) for box in modules[2].boxes(rgb)])
        if not _framevision_raw_valid(raw, width, height):
            raise StepError('피사체·글자 검출 상자의 형태 또는 좌표가 잘못되었습니다.')
        if _image_file_sha(path) != source_sha:
            raise StepError('피사체 측정 중 입력 PNG 바이트가 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
        return raw, detected is not None

    try:
        for path in paths:
            with open(path, 'rb') as stream:
                content = stream.read()
            source_sha = hashlib.sha256(content).hexdigest()
            if path in sources and sources[path] != source_sha:
                raise StepError('피사체 측정 중 입력 PNG 바이트가 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
            sources[path] = source_sha
            with Image.open(io.BytesIO(content)) as image:
                if image.size != (width, height):
                    raise StepError('피사체 측정 PNG 크기가 선언한 알맹이 크기와 다릅니다.')
                source = dict(sha256=source_sha, size=[width, height], mode=image.mode, format=image.format)
            key = _framevision_digest(dict(version=_FRAMEVISION_RAW_VERSION, identity=identity, input=source))
            cached_path = (os.path.join(cache_dir, key + '.json')
                           if cache_dir and source['mode'] == 'RGB' and source['format'] == 'PNG' else None)
            raw = measured.get(key) if cached_path else None
            if raw is None and cached_path:
                raw = _framevision_cached(cached_path, key, identity, source, width, height)
            if raw is None:
                with _FRAMEVISION_LOCK:
                    # A concurrent identical miss observes the preceding receipt:
                    # read once more after waiting for the detector.
                    if cached_path:
                        raw = _framevision_cached(cached_path, key, identity, source, width, height)
                    if raw is None:
                        raw, opened = infer(path, content, source_sha)
                        # None means the canonical face detector could not open the
                        # input. Preserve its old empty output, but never cache it.
                        if cached_path and opened:
                            row = dict(version=_FRAMEVISION_RAW_VERSION, key=key, identity=identity,
                                       input=source, result=raw, result_sha256=_framevision_digest(raw))
                            try:
                                os.makedirs(cache_dir, exist_ok=True)
                                _photo_write_state(cached_path, row)
                                written.append(cached_path)
                            except OSError:
                                # Optional storage must not discard a real successful inference.
                                pass
                        else:
                            cached_path = None
            if cached_path:
                measured[key] = raw
            faces = [dict(zip(('x', 'y', 'w', 'h'), box)) for box in raw['faces']]
            counts.append(len(faces))
            face_candidates.append([[f["x"]*width,f["y"]*height,f["w"]*width,f["h"]*height] for f in faces])
            if faces:
                # Dominant face selection is explicit; this does not prove
                # identity. Temporal continuity wins after the first sample.
                if track:
                    prev=track[-1]
                    picked=min(faces,key=lambda f: (f["x"]+f["w"]/2-(prev[0]+prev[2]/2)/width)**2+
                               (f["y"]+f["h"]/2-(prev[1]+prev[3]/2)/height)**2)
                else:
                    picked=max(faces,key=lambda f:f["w"]*f["h"])
                track.append([picked["x"]*width,picked["y"]*height,
                              picked["w"]*width,picked["h"]*height])
            # Reuse the canonical DBNet server detector. Recognition is
            # intentionally unnecessary: styled text may be unreadable to
            # OCR while its real bounding region can still be detected.
            sample_text=[]
            for x0,y0,x1,y1 in raw['texts']:
                r=[x0,y0,x1-x0,y1-y0]
                if r not in texts: texts.append(r)
                sample_text.append(r)
            text_candidates.append(sample_text)
        if _framevision_identity(root) != identity:
            with _FRAMEVISION_LOCK:
                _FRAMEVISION_MODULES.pop(root, None)
                _FRAMEVISION_LOADED_IDENTITIES.pop(root, None)
            raise StepError('피사체 측정 중 모델 또는 설정이 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
        if any(_image_file_sha(path) != digest for path, digest in sources.items()):
            raise StepError('피사체 측정 중 입력 PNG 바이트가 바뀌었습니다. 기존 결과를 사용하지 않습니다.')
    except Exception as exc:
        # A failed call persists nothing (the former end-of-call rule): a changed
        # model/input or a detector failure rejects every row this call published.
        for stale in written:
            try: os.unlink(stale)
            except OSError: pass
        if getattr(exc, 'code', None) in ('review_budget_exhausted', 'review_budget_unreadable',
                                         'review_provider_not_authorized'):
            raise
        wrapped = StepError("피사체·글자 측정에 실패했습니다 — framevision 팩/환경 설치를 확인하세요: " + str(exc))
        if getattr(exc, 'code', None) in ('framevision_pack_missing', 'framevision_environment'):
            wrapped.code = exc.code      # 환경 원인 표지를 감싸면서 잃지 않는다(W2-16)
        raise wrapped from exc
    face=[statistics.median(r[j] for r in track) for j in range(4)] if track else None
    return {"face":face,"text_boxes":texts,"face_samples":track,
            "face_candidates":face_candidates,"text_candidates":text_candidates,
            "face_sample_counts":counts,"measurement_version":2,
            "subject_detected":bool(track),"face_engine":"yunet", "text_engine":"ppocr-server-det",
            "subject_sample_coverage":len(track)/max(1,len(paths))}


def measure_frame(item):
    """컷 하나에 대해 **서버가 판정할 값**을 잰다 — 판단은 하지 않는다.

    item = {src, tmp, samples, probe, frame_argv}
        samples  이 컷 구간의 시각들 — 움직임·얼굴을 여기서 잰다
        probe    **소재 전역**의 시각들 — 레터박스는 소재의 성질이라 넓게 봐야 한다
    돌려주는 것
        size     [w, h]          소재 프레임 크기
        content  [x, y, w, h]    소재 자신의 검은 띠를 뺀 알맹이(전 표본 교집합)
        face     [x, y, w, h]|None  가장 큰 정면 얼굴 (알맹이 기준 좌표)
        subject  [cx, cy]        피사체 중심 비율 (알맹이 기준)
        by       "face"|"edge"   무엇으로 잡았는가 — 서버가 이걸로 등급을 가른다
        motion   float           이웃 표본 프레임의 평균 절대차(0~255)

    ★전부 일반 기술이다. 목표 크기·중심·반려선은 **서버에만** 있다.
    """
    import numpy as np
    from PIL import Image
    tmp = item["tmp"]

    captured = {}
    captured_times = {}
    grab_fail = []      # 못 뜬 순간의 사유(시각·종료 코드·오류 끝) — 한 장도 못 떴을 때 오류 글에 싣는다(#150)

    def grab(times, tag):
        out = []
        for i, t in enumerate(times):
            # ★확장자가 곧 ffmpeg 출력 형식이다. **서버가 정한다** — 여기서 고르면
            #   서버가 바꿔도 안 따라오고, 형식에 따라 회색값이 달라질 수 있다
            #   (`-pix_fmt gray` 는 실제로 PIL 과 값이 다르다 — 명세 주석 참조).
            p = os.path.join(tmp, f"mf_{tag}{i:03d}{item.get('suffix') or '.png'}")
            argv = [a.replace("@@T@@", f"{float(t):.6f}").replace("@@OUT@@", p)
                    for a in item["frame_argv"]]
            r = _spawn(argv, capture_output=True)
            if r.returncode == 0 and os.path.exists(p):
                with Image.open(p) as image:
                    rgb = np.asarray(image.convert("RGB"))
                    out.append(np.asarray(image.convert("L")))
                captured[(tag, len(out)-1)] = rgb
                captured_times[(tag, len(out)-1)] = capture_actual.get(float(t),float(t))
            else:
                grab_fail.append(f"{float(t):.3f}초 rc={r.returncode} · "
                                 + (" ".join(err_gist(r.stderr, 200).split()) or "오류 출력 없음"))
        return out

    sample_times=list(item["samples"])
    measured_cuts=[];capture_actual={};track_origin=float(item.get("start") or 0)
    if item.get('scene_argv') and item.get('tracking_probe_argv'):
        probe=_spawn(item['tracking_probe_argv'],capture_output=True,**TEXT_PIPE)
        stream=json.loads(probe.stdout)['streams'][0]
        from fractions import Fraction
        rate=float(Fraction(stream['r_frame_rate']));tick=float(Fraction(stream['time_base']))
        start=float(item['start']);end=start+float(item['duration'])
        scene=_spawn(item['scene_argv'],capture_output=True,**TEXT_PIPE)
        track_origin,measured_cuts,neighbors,timeline=_tracking_scene_samples(scene.stderr or '',start,float(item['duration']),tick)
        if not timeline:raise StepError('피사체 추적용 실제 프레임 시각을 읽지 못했습니다. 실행기를 업데이트한 후 재측정하세요.')
        import bisect
        actual=set(neighbors)
        for requested in sample_times:
            i=bisect.bisect_left(timeline,float(requested))
            if i<len(timeline) and timeline[i]<end:actual.add(timeline[i])
        # Seek a source tick before the actual PTS so decoder rounding cannot
        # accidentally select the next frame. Metadata retains the actual PTS.
        capture_actual={max(start,t-tick):t for t in actual}
        sample_times=sorted(capture_actual)
    if item.get("kind") == "image":
        sample_times=sample_times[:1]
    grays = grab(sample_times, "s")
    if not grays:
        # ★마지막 시도의 사유를 싣는다 (2026-10-17 · 신고 #150) — 예전에는 무엇이 왜 실패했는지 알 수 없었다.
        raise StepError(f"컷 프레임을 한 장도 못 떴다 — {item.get('src')} · " + (grab_fail[-1] if grab_fail else "뜬 시각 없음"))
    h0, w0 = grays[0].shape
    bd = item["band"]                       # ★서버가 준다. 실행기에 기본값을 두지 않는다
    # ★★알맹이는 **이 컷 구간에서** 정한다. 전역 표본(probe)을 컷 표본과 **섞으면**
    #   안 된다 — 긴 방송 아카이브는 구간마다 화면비가 다르고, 섞은 중앙값은 어느
    #   구간에도 안 맞는다(실측: 컷 표본만 보면 상135 인데 섞으면 상120 이 되어
    #   구운 조각에 상13·하59 가 남았다).
    # ★컷 구간이 **통째로 어두우면** 거기서는 띠와 어둠을 못 가른다. 그때만 전역으로
    #   물러난다 — 아무것도 못 정하면 프레임 전체다(= 아무것도 안 자른다).
    x, y, cw, ch = _content_rect_over(grays, bd["dark_max"], bd["black_frac"],
                                      bd["frame_dark_min"])
    if [x, y, cw, ch] == [0, 0, int(w0), int(h0)]:
        far = grab(list(item.get("probe") or []), "p")
        if far:
            x, y, cw, ch = _content_rect_over(far, bd["dark_max"], bd["black_frac"],
                                              bd["frame_dark_min"])
    # ★움직임은 **알맹이 안에서** 잰다. 검은 띠는 언제나 안 움직이므로
    #   프레임 전체로 재면 띠가 큰 소재일수록 움직임이 작게 나온다(축이 오염된다).
    from source_motion import pixel_value
    motion = pixel_value(grays, [x, y, cw, ch])
    if item.get('motion_only') is True:
        return {'size': [int(w0), int(h0)], 'content': [x,y,cw,ch],
                'motion': float(motion), 'samples': len(grays), 'by': 'motion'}
    mid = grays[len(grays) // 2][y:y + ch, x:x + cw]
    fb = _face_box(mid) if not item.get("framevision") else None
    if fb:
        cx = (fb[0] + fb[2] / 2) / cw
        cy = (fb[1] + fb[3] / 2) / ch
        by = "face"
    else:
        cx, cy = _edge_center(mid)
        by = "edge"
    extra = {}
    if item.get("framevision"):
        # Canonical YuNet/PP-OCR operate on RGB content, not the old grayscale
        # face sample. Use every cut sample; never rename an edge as a face.
        # Content samples are content-addressed: review_film_frames attaches the
        # very same files, so no second copy is ever made of them.
        paths=[_frozen_png(Image.fromarray(captured[("s",j)][y:y+ch,x:x+cw]), tmp) for j in range(len(grays))]
        cache_options = {'cache_dir': item['framevision_cache']} if item.get('framevision_cache') else {}
        extra = _framevision_measure(paths, cw, ch, item["framevision"], **cache_options)
        extra['sample_paths']=list(paths)
        extra['sample_times']=[captured_times[('s',j)] for j in range(len(grays))]
        extra['face_sample_times']=[captured_times[('s',j)] for j,n in enumerate(extra['face_sample_counts']) if n]
        extra['track_origin']=track_origin
        extra['tracking_version']=1
        extra['track_scene_cuts']=measured_cuts
        extra['tracking_capture_coverage']=len(grays)/max(1,len(sample_times))

        if item.get("preserve_text") is True:
            extra["preserve_text"] = True
        fb=extra.pop("face")
        if fb:
            cx,cy=(fb[0]+fb[2]/2)/cw,(fb[1]+fb[3]/2)/ch
            by="face"
        else:
            cx,cy=0.5,0.5
            by="unresolved"
    return {"size": [int(w0), int(h0)], "content": [x, y, cw, ch],
            "face": fb, "subject": [float(cx), float(cy)],
            # ★자르지 않고 **잰 그대로** 돌려준다. 실행기는 재는 자이고, 몇 자리로
            #   보일지는 서버가 정한다 — 여기에 자릿수를 적으면 그것도 기본값이 된다.
            "by": by, "motion": float(motion), "samples": len(grays), **extra}


_REVIEW_CONTEXT = contextvars.ContextVar('volcano_review_context', default=None)


def current_review_context():
    """Execution-local choices; never infer the active host from installed tools."""
    return {key:value for key,value in (_REVIEW_CONTEXT.get() or {}).items() if key != '_dispatch_guard'}


#: 사람이 «고쳤으니 다시» 를 알린 컷의 검수 범위(2026-10-15 쇼핑 신고). 값은 한 실행의 장부 (잠금, 이미 놓아 준 영수증) 이다.
#:   subject_focus.select_subjects 는 다시 잴 컷의 작업 동안, local_focus 는 그 컷의 화면 글자 검수 동안 연다.
#:   장부는 **한 실행에 하나**(review_retry_registry)를 다시 잴 컷들이 같이 쓴다 — 레시피가 같은 두 컷이 한 영수증을 함께 쓰면
#:   한 컷이 다시 물어 또 실패한 기록을 다른 컷이 또 놓아 주지 않는다(한 실행에서 한 요청은 많아야 한 번 다시 묻는다).
#:   범위 밖(사람이 다시를 안 알린 컷·다른 채널)에서는 아무 영수증도 놓아 주지 않는다 — 같은 유료·구독 요청 자동 반복 금지.
_REVIEW_RETRY = contextvars.ContextVar('volcano_review_retry', default=None)
#: 결과 없이 끝났거나(failed) 끝을 모르는(started) 검수 기록의 결말. 클라이언트 영수증은 «모델을 띄웠다가 결과 없이 끝남»
#:   (outcome pending · attempted true)도 같은 뜻이다 — unfinished_review 한 자리가 판정한다.
UNFINISHED_REVIEW_OUTCOMES = ('started', 'failed')


def review_retry_registry():
    """한 실행의 «다시» 장부 — 이미 놓아 준 (영수증 경로, 요청 키) 를 센다."""
    import threading
    return (threading.Lock(), set())


@contextlib.contextmanager
def review_retry_scope(active, registry):
    """다시 잴 컷의 검수 동안만 «끝나지 않은 영수증을 한 번 놓아 준다» 를 켠다. active 가 거짓이면 아무것도 바꾸지 않는다.
    registry 는 review_retry_registry() 가 한 실행에 한 번 만든 장부다(컷마다 새로 만들지 않는다)."""
    if not active:
        yield
        return
    token = _REVIEW_RETRY.set(registry)
    try:
        yield
    finally:
        _REVIEW_RETRY.reset(token)


def review_retry_active():
    """지금 검수가 사람이 «다시» 를 알린 컷의 범위(review_retry_scope) 안인가 — 그 범위에서만 새 질문을 낸다."""
    return _REVIEW_RETRY.get() is not None


def unfinished_review(saved):
    """검수 기록이 «결과 없이 끝남·끝을 모름» 인가 — 완료·거부·예산 정지·사람 답 대기(시도 안 함)는 아니다."""
    return isinstance(saved, dict) and (saved.get('outcome') in UNFINISHED_REVIEW_OUTCOMES
                                        or (saved.get('outcome') == 'pending' and saved.get('attempted') is True))


def release_unfinished_review(path, key, record, unfinished):
    """사람이 «다시» 를 알린 범위에서, 끝나지 않은 이 요청(key)의 기록을 **한 번** 놓아 준다 — 놓아 주면 True(다시 묻는다).

    부르는 쪽이 path 의 영수증 잠금을 쥔 채 부른다. 옛 기록은 지우지도 옮기지도 않는다: 같은 자리 옆
    <path>.released-<내용 지문>.json 에 한 벌 남기고(내용이 같으면 한 번만), 다음 저장(started)이 고정 자리를 새 시도로 덮는다.
    폴더 구조는 그대로라 프레임 시간축·공유 프레임 검사가 보는 폴더 내용이 바뀌지 않는다(하위 폴더를 만들지 않는다).
    한 범위에서 같은 영수증은 한 번만 놓는다 — 다시 물은 요청이 또 실패하면 그 실패를 그대로 돌려준다(자동 반복 없음)."""
    scope = _REVIEW_RETRY.get()
    if scope is None or not unfinished:
        return False
    lock, released = scope
    ident = (os.fspath(path), key)
    with lock:
        if ident in released:
            return False
        released.add(ident)
    data = json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False)
    keep = _review_receipt_io_path(os.fspath(path) + '.released-' + hashlib.sha256(data.encode()).hexdigest()[:16] + '.json')
    if not os.path.exists(keep):
        _photo_write_state(keep, record)
    return True


def validate_review_policy(value):
    value = {'provider':'client'} if value is None else value
    if (not isinstance(value, dict) or value.get('provider') not in ('client', 'evolink')
            or value.get('provider') == 'client' and 'max_requests' in value
            or value.get('provider') == 'evolink' and
                (type(value.get('max_requests')) is not int or value['max_requests'] <= 0)):
        raise StepError('검수 제공자와 요청 한도가 잘못되었습니다.')
    return dict(value)


def resolve_review_policy(value=None):
    context = _REVIEW_CONTEXT.get()
    return validate_review_policy(context.get('policy') if context is not None else value)


def resolve_review_replies(value=None):
    """Retain request-bound answers from both the response and its local job.

    An empty response map is not a revocation of a supplied answer. Conflicting
    answers for one request must be corrected explicitly, never silently chosen.
    Policy/client authority stays in the execution context; media IDs and reply
    schemas are still validated by client_review before accepting any answer.
    """
    merged = {}
    for replies in (current_review_context().get('replies'),value):
        if replies is None:
            continue
        if not isinstance(replies,dict):
            raise StepError('검수 답은 요청 SHA별 객체여야 합니다.')
        for key, answer in replies.items():
            if key in merged and merged[key] != answer:
                raise StepError('같은 검수 요청 SHA에 서로 다른 답이 있습니다. 서버 응답과 입력의 답을 일치시켜 주세요.')
            merged[key] = answer
    return merged


def _normalize_review_client(value):
    if isinstance(value,str):
        return ({'provider':value,'bin':value,'timeout':120} if value in ('claude','codex') else {'provider':'agy'} if value == 'agy' else {'provider':'host'})
    if not isinstance(value,dict) or value.get('provider') not in ('claude','codex','agy'):
        return {'provider':'host'}
    return dict(value)


def resolve_review_client(value=None, legacy=None):
    context = _REVIEW_CONTEXT.get()
    if context is not None:
        return _normalize_review_client(context.get('client'))
    if value is None and isinstance(legacy,dict):
        return dict(legacy,provider='claude')
    return _normalize_review_client(value)


@contextlib.contextmanager
def review_context(policy=None, client=None, replies=None, budget=None, *, _agy_run_id=None):
    context = dict(_REVIEW_CONTEXT.get() or {})
    # survey restores current_review_context() in a child process. Keep the
    # exact run ID so AGY's durable refusal marker remains shared by both
    # processes; regenerating it would permit another request after refusal.
    inherited_id = context.get('_agy_run_id')
    environment_id = os.environ.get('INFO3D_RUN_ID')
    if _agy_run_id is not None:
        if (not isinstance(_agy_run_id, str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', _agy_run_id)):
            raise StepError('검수 실행 ID가 잘못되었습니다. 기존 실행 기록을 보존하세요.')
        if any(value and value != _agy_run_id for value in (inherited_id, environment_id)):
            raise StepError('검수 실행 ID가 원래 실행과 다릅니다. 기존 거부 기록을 보존하세요.')
        context['_agy_run_id'] = _agy_run_id
    context.update({k:v for k,v in dict(policy=policy,client=client,replies=replies,budget=budget).items() if v is not None})
    # Child context copies share this dispatch/refusal boundary.
    import threading
    context.setdefault('_dispatch_guard', (threading.RLock(), []))
    context.setdefault('_agy_run_id', environment_id or __import__('uuid').uuid4().hex)
    context['policy'] = validate_review_policy(context.get('policy'))
    context['client'] = _normalize_review_client(context.get('client'))
    token = _REVIEW_CONTEXT.set(context)
    try:
        yield context
    finally:
        _REVIEW_CONTEXT.reset(token)



def remember_review_refusal(error):
    guard = (_REVIEW_CONTEXT.get() or {}).get('_dispatch_guard')
    if guard is not None:
        lock, refusals = guard
        # Publish before waiting on any dispatch lock. A cached refusal must
        # become visible even while another previously sent request is reading.
        if not refusals:
            refusals.append(error)
    return error



def check_review_running():
    guard = (_REVIEW_CONTEXT.get() or {}).get('_dispatch_guard')
    if guard is not None and guard[1]:
        first = guard[1][0]
        error = ProviderRefusalError(first.origin,first.reason_code,first.reason)
        error.request_sent = False
        raise error


def _review_spawn(*args, **kwargs):
    check_review_running()
    return _spawn(*args, **kwargs)


@contextlib.contextmanager
def review_dispatch():
    guard = (_REVIEW_CONTEXT.get() or {}).get('_dispatch_guard')
    lock, refusals = guard if guard is not None else (contextlib.nullcontext(), [])
    with lock:
        if refusals:
            first = refusals[0]
            error = ProviderRefusalError(first.origin,first.reason_code,first.reason)
            error.request_sent = False
            raise error
        try:
            yield
        except urllib.error.HTTPError as cause:
            if cause.code not in (401,402,403,429):
                raise
            raise remember_review_refusal(ProviderRefusalError('provider.http',cause.code,str(cause))) from cause
        except ProviderRefusalError as error:
            remember_review_refusal(error)
            raise


def review_context_worker(function):
    """Capture before scheduling; each worker gets an independent Context copy."""
    context = contextvars.copy_context()
    def call(*args, **kwargs):
        return context.copy().run(function, *args, **kwargs)
    return call


def _review_capabilities(value):
    if value is None:
        return []
    if not isinstance(value, list) or any(cap != 'web_search' for cap in value) or len(set(value)) != len(value):
        raise StepError('지원하지 않는 검수 기능입니다. 필요한 자료·검색 기능을 생략하지 않습니다.')
    return list(value)


@review_dispatch()
def client_call(cfg, prompt, image_paths=(), want_keys=(), *, image_labels=None, _before_model=None, capabilities=None):
    """Call exactly the selected client; failure is a handoff, never an API fallback."""
    capabilities = _review_capabilities(capabilities)
    cfg = resolve_review_client(cfg)
    provider = cfg['provider']
    if provider == 'host':
        return None, '현재 대화의 클라이언트 검수 필요'
    if image_labels is not None and (not isinstance(image_labels, list) or len(image_labels) != len(image_paths)
            or any(not isinstance(label, str) or not label or len(label) > 200 for label in image_labels)):
        raise StepError('그림 첨부 번호가 실제 이미지 목록과 다릅니다.')
    binary = shutil.which(str(cfg.get('bin') or ''))
    if not binary:
        return None, provider + ' CLI 없음'
    paths = [os.path.abspath(path) for path in image_paths]
    if any(not os.path.isfile(path) for path in paths):
        return None, 'codex 첨부 이미지 파일 없음'
    labels = image_labels or [f'Candidate #{n+1}' for n in range(len(paths))]
    head = ''.join(f'첨부 이미지 {n+1}: {label}: {path}\n' for n,(label,path) in enumerate(zip(labels,paths)))
    question = head + str(prompt) + '\n출력은 JSON 객체 하나만 — 설명·코드펜스 없이.'
    env = dict(os.environ)
    for name in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','ANTHROPIC_API_KEY',
                 'ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_BEDROCK',
                 'CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY','CLAUDECODE'):
        env.pop(name, None)
    try:
        # Read-only preflight rejects API-key logins before any model request.
        # Never force a login-method migration, which may log the user out.
        auth_command = [binary,'login','status'] if provider == 'codex' else [binary,'auth','status','--json']
        status = _review_spawn(auth_command,capture_output=True,timeout=15,env=env)
        status_text = b'\n'.join(x if isinstance(x,bytes) else str(x or '').encode() for x in (status.stdout,status.stderr)).decode('utf8','replace')
        if provider == 'codex':
            authenticated = status.returncode == 0 and 'Logged in using ChatGPT' in status_text
        else:
            auth = _json_object(status_text) or {}
            authenticated = status.returncode == 0 and auth.get('loggedIn') is True and auth.get('authMethod') == 'claude.ai'
        if not authenticated:
            return None, provider + ' 구독 계정 로그인 확인 필요'
        if provider == 'claude':
            if _before_model is not None: _before_model()
            return claude_call(dict(cfg, _isolated=True, _env=env), prompt, image_paths, want_keys, image_labels=image_labels, capabilities=capabilities)
        if 'web_search' in capabilities:
            help_result = _review_spawn([binary, '--help'], capture_output=True, timeout=15, env=env)
            help_text = help_result.stdout.decode('utf8', 'replace') if isinstance(help_result.stdout, bytes) else str(help_result.stdout or '')
            if help_result.returncode or '--search' not in help_text:
                return None, 'codex CLI의 웹검색 기능 확인 필요'
        with tempfile.TemporaryDirectory(prefix='volcano-client-') as directory:
            command = [binary] + (['--search'] if 'web_search' in capabilities else []) + ['exec','--skip-git-repo-check','--ephemeral','--ignore-user-config',
                '--ignore-rules','--sandbox','read-only','--color','never','--json',
                '-c','approval_policy="never"','-c','mcp_servers={}',
                '-c','features.shell_tool=false',
                '-c',('web_search="live"' if 'web_search' in capabilities else 'web_search="disabled"'),'-c','project_doc_max_bytes=0']
            if cfg.get('model'): command += ['--model',str(cfg['model'])]
            for path in paths: command += ['-i',path]
            command += ['-']
            if _before_model is not None: _before_model()
            result = _review_spawn(command,input=question.encode('utf8'),capture_output=True,
                            timeout=int(cfg.get('timeout') or 120),cwd=directory,env=env)
    except ProviderRefusalError:
        raise
    except Exception as exc:
        return None, provider + ' 실행 실패: ' + type(exc).__name__
    stdout = result.stdout.decode('utf8','replace') if isinstance(result.stdout,bytes) else str(result.stdout or '')
    stderr = result.stderr.decode('utf8','replace') if isinstance(result.stderr,bytes) else str(result.stderr or '')
    # JSONL status events are not task answers. Inspect only final agent messages.
    messages = []
    events = False
    searched = False
    for line in stdout.splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if not isinstance(event,dict): continue
        if event.get('type') in ('thread.started','turn.started','turn.completed','turn.failed','item.started','item.updated','item.completed','error'):
            events = True
            _raise_provider_refusal(event,origin='provider.codex_cli')
            item = event.get('item')
            if (event.get('type') == 'item.completed' and isinstance(item,dict)
                    and item.get('type') == 'web_search' and item.get('status') not in ('failed','incomplete')):
                searched = True
            if event.get('type') == 'item.completed' and isinstance(item,dict) and item.get('type') == 'agent_message':
                messages.append(str(item.get('text') or ''))
    final = messages[-1] if messages else ('' if events else stdout)
    _raise_provider_refusal(_json_object(final),origin='provider.codex_cli')
    _raise_cli_refusal(final, origin='provider.codex_cli')
    if result.returncode:
        # Do not echo CLI stderr: authentication failures can contain credentials.
        return None, f'codex rc={result.returncode}: 로그인 또는 실행 상태 확인 필요'
    if 'web_search' in capabilities and not searched:
        return None, 'codex 웹검색 실행 증거 확인 필요'
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{',final):
        try: obj,_ = decoder.raw_decode(final,match.start())
        except ValueError: continue
        if isinstance(obj,dict) and all(key in obj for key in want_keys or ()):
            return obj,None
    return None, f'codex 출력에서 JSON 을 못 찾았다 ({len(final)}자)'


@review_dispatch()
def claude_call(cfg, prompt, image_paths=(), want_keys=(), *, image_labels=None, capabilities=None):
    """Explicit legacy Claude transport. Selection and fallback belong to the caller.

    CLI availability does not establish account billing or subscription status.
    """
    if image_labels is not None and (not isinstance(image_labels, list) or len(image_labels) != len(image_paths)
            or any(not isinstance(label, str) or not label or len(label) > 200 for label in image_labels)):
        raise StepError('그림 첨부 번호가 실제 이미지 목록과 다릅니다.')
    capabilities = _review_capabilities(capabilities)
    if not isinstance(cfg, dict) or not cfg.get("bin"):
        return None, "claude 설정 없음"
    binp = shutil.which(str(cfg["bin"]))
    if not binp:
        return None, "claude CLI 없음"
    head = ""
    if image_paths:
        # Split film/object questions already supply global IDs. Keep each ID
        # beside its actual file instead of introducing a second local numbering.
        attachments = (f"{label}: {path}" for label, path in zip(image_labels, image_paths)) if image_labels is not None else (
            f"{i}) {p}" for i, p in enumerate(image_paths, start=1))
        head = ("이미지를 읽어라: "
                + " · ".join(attachments)
                + "\n")
    q = head + str(prompt) + "\n출력은 JSON 객체 하나만 — 설명·코드펜스 없이."
    try:
        # ★모델은 서버가 고른다(`cfg["model"]`, 예: haiku) — 실측: 기본 모델은 한 장에 ~40초,
        #   판정 같은 일은 작은 모델이 훨씬 빠르다. 없으면 CLI 기본값.
        # Claude's documented text stdin preserves the whole question without
        # Windows cmd.exe/CreateProcess argument limits or shell metacharacters.
        _cmd = [binp, "-p", "--output-format", "stream-json" if "web_search" in capabilities else "text"]
        if "web_search" in capabilities: _cmd += ["--verbose"]
        if cfg.get('_isolated'):
            allowed = 'Read,WebSearch' if 'web_search' in capabilities else 'Read'
            _cmd += ['--safe-mode','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                     '--tools',allowed,'--allowedTools',allowed,'--permission-mode','dontAsk',
                     '--no-session-persistence']
        if cfg.get("model"):
            _cmd += ["--model", str(cfg["model"])]
        # Binary stdin also prevents Windows' text pipe from rewriting LF to CRLF.
        p = _review_spawn(_cmd, input=q.encode("utf-8"), capture_output=True,
                           timeout=int(cfg.get("timeout") or 120), **({"env":cfg["_env"]} if cfg.get("_env") is not None else {}))
        if isinstance(p.stdout, bytes):
            p.stdout = p.stdout.decode("utf-8", "replace")
        if isinstance(p.stderr, bytes):
            p.stderr = p.stderr.decode("utf-8", "replace")
    except ProviderRefusalError:
        raise
    except Exception as e:  # noqa: BLE001
        return None, "claude 실행 실패: " + str(e)[:120]
    if 'web_search' in capabilities:
        searches = set(); completed = set(); finals = []
        for line in (p.stdout or '').splitlines():
            try: event = json.loads(line)
            except ValueError: continue
            if not isinstance(event, dict): continue
            _raise_provider_refusal(event, origin='provider.claude_cli')
            if event.get('type') == 'result' and isinstance(event.get('result'), str):
                finals.append(event['result'])
            message = event.get('message') or {}
            for part in message.get('content') or [] if isinstance(message, dict) else []:
                if not isinstance(part, dict): continue
                if part.get('type') == 'tool_use' and part.get('name') == 'WebSearch':
                    searches.add(part.get('id'))
                if part.get('type') == 'tool_result' and not part.get('is_error'):
                    completed.add(part.get('tool_use_id'))
        if not (searches & completed) or not finals:
            return None, 'claude 웹검색 실행 증거 확인 필요'
        p.stdout = finals[-1]
    _raise_provider_refusal(_json_object(p.stdout or ''), origin='provider.claude_cli')
    _raise_cli_refusal(p.stdout)
    if p.returncode != 0:
        detail = (p.stderr or "").strip()
        if not detail:
            # Claude reports authentication failures in stdout, even with stderr empty.
            try:
                detail = str(json.loads(p.stdout or "{}").get("result") or "")
            except (ValueError, AttributeError):
                detail = (p.stdout or "").strip()
        return None, "claude rc=%s: %s" % (p.returncode, detail[-160:])
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", p.stdout or ""):
        try:
            obj, _ = dec.raw_decode(p.stdout, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in (want_keys or ())):
            return obj, None
    return None, "claude 출력에서 JSON 을 못 찾았다 (%d자)" % len(p.stdout or "")


def _vision_body(item, images):
    """이미지 호출 본문 — **에보링크 OpenAI 호환** 규약. 서버 `vision_image_body` 와 짝이다.

    ★그림은 **base64** 로 싣는다. 에보링크 호환층은 `image_url` 에 **진짜 URL 을
      넣으면 HTTP 500**(`Invalid request`)을 준다 — 2026-08-22 실측(대조군: 같은
      그림을 base64 로 주면 정상). 여러 장 비교도 base64 로 되고 12장까지 확인했다.
    ★`images` 는 `[(base64, mime), …]` 이고 **순서가 곧 후보 번호**다.
    """
    content = [{"text": item["prompt"], "type": "text"}]
    labels = item.get('image_labels')
    if labels is not None and (not isinstance(labels, list) or len(labels) != len(images)
            or any(not isinstance(label, str) or not label or len(label) > 200 for label in labels)):
        raise StepError('그림 첨부 번호가 실제 이미지 목록과 다릅니다.')
    for n, (b64, mime) in enumerate(images, start=1):
        if labels is not None:
            content.append({'type': 'text', 'text': labels[n-1]})
        elif len(images) > 1:
            content.append({"type": "text", "text": f"Candidate #{n} image"})
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}})
    body = {"model": item["model"], "temperature": 0,
            "messages": [{"role": "user", "content": content}]}
    if item.get("max_tokens"):
        body["max_tokens"] = int(item["max_tokens"])
    return body


def _image_request_size(item, images):
    """The sender's exact JSON bytes, plus decoded media bytes; never omit images."""
    body = _vision_body(item, images)
    media = sum(len(data) // 4 * 3 - len(data) + len(data.rstrip('=')) for data, _ in images)
    return body, media, len(json.dumps(body).encode('utf-8'))


def _image_request_fits(item, media, size):
    for field, actual in (('max_media_bytes', media), ('max_request_bytes', size)):
        limit = item.get(field)
        if limit is not None:
            if type(limit) is not int or limit <= 0:
                raise StepError('그림 검수 요청 크기 상한이 잘못되었습니다: ' + field)
            if actual > limit:
                return False
    return True


class ClientReviewPending(StepError):
    """The connected model must inspect the attached evidence and return JSON."""
    code = 'client_review_pending'

    def __init__(self, request):
        self.request = request
        super().__init__('현재 클라이언트가 실제 검수 자료를 읽고 구조화 답을 반환할 차례입니다.')


class ClientReviewInputError(ClientReviewPending):
    """A malformed reply can be replaced while its actual request stays pending."""
    code = 'client_review_reply_invalid'

    def __init__(self, request, reason):
        super().__init__(request)
        self.args = (reason,)


def review_execution_settings(item):
    """Resolve a scene command through the existing execution authority."""
    context = current_review_context()
    replies = resolve_review_replies(item.get('focus_review_replies'))
    return dict(item, review_policy=resolve_review_policy(item.get('review_policy')),
                review_client=resolve_review_client(item.get('review_client') or item.get('client')),
                focus_review_replies=replies,
                _review_budget=context.get('budget') if context else item.get('review_budget') or
                    item.get('_review_budget') or str(Path(item.get('out_dir') or '.')/'review-budget.sqlite3'))


def review_budget_preflight(policy, ledger):
    """Read-only early stop for new work; actual sends still reserve atomically."""
    import sqlite3
    if (not isinstance(policy, dict) or policy.get('provider') != 'evolink'
            or type(policy.get('max_requests')) is not int or policy['max_requests'] <= 0
            or not ledger):
        exc = StepError('유료 검수는 명시적인 evolink 정책과 양의 요청 한도가 필요합니다.')
        exc.code = 'review_provider_not_authorized'
        raise exc
    path = Path(ledger).resolve()
    if not path.exists():
        return
    try:
        conn = sqlite3.connect(_file_uri(path)+'?mode=ro', uri=True, timeout=30)
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='attempts'").fetchone():
                return
            count = conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as error:
        exc = StepError('검수 요청 기록을 읽지 못했습니다. 기록을 보존하고 새 측정을 시작하지 않았습니다.')
        exc.code = 'review_budget_unreadable'
        raise exc from error
    if count >= policy['max_requests']:
        exc = StepError(f'검수 요청 한도를 사용했습니다 ({count}/{policy["max_requests"]}). 완료·실패·진행 기록을 보존했고 새 API 요청은 보내지 않았습니다.')
        exc.code = 'review_budget_exhausted'
        exc.review_budget_blocked = {'max_requests':policy['max_requests'],'attempts_reserved':0}
        raise exc


def review_request_attempt(policy, ledger, request_sha256, *, attempts=None):
    """Reserve one actual outbound attempt durably, before sending any bytes."""
    import sqlite3
    if (not isinstance(policy, dict) or policy.get('provider') != 'evolink'
            or type(policy.get('max_requests')) is not int or policy['max_requests'] <= 0
            or not ledger):
        exc = StepError('유료 검수는 명시적인 evolink 정책과 양의 요청 한도가 필요합니다.')
        exc.code = 'review_provider_not_authorized'
        raise exc
    os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
    conn = sqlite3.connect(ledger, timeout=30)
    try:
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, request_sha256 TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        count = conn.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        if count >= policy['max_requests']:
            exc = StepError(f'검수 요청 한도를 사용했습니다 ({count}/{policy["max_requests"]}). 완료·실패·진행 기록을 보존했고 새 API 요청은 보내지 않았습니다.')
            exc.code = 'review_budget_exhausted'
            if attempts is not None and attempts.get('reserved',0) == 0:
                exc.review_budget_blocked = {'max_requests':policy['max_requests'],'attempts_reserved':0}
            raise exc
        conn.execute('INSERT INTO attempts (request_sha256) VALUES (?)', (request_sha256,))
        conn.commit()
        from runtime_metrics import event
        event('review', 'reserved', request_sha256)
        if attempts is not None:
            attempts['reserved'] = attempts.get('reserved',0) + 1
    finally:
        conn.close()


def _review_media_suffix(mime, *, image_only=False):
    """Keep the attachment type visible without changing its measured bytes."""
    suffixes = {'image/png':'.png', 'image/jpeg':'.jpg', 'image/webp':'.webp'}
    if not image_only:
        suffixes.update({'video/mp4':'.mp4', 'audio/wav':'.wav'})
    if not isinstance(mime, str) or mime not in suffixes:
        raise StepError(f'검수 자료의 MIME 형식을 지원하지 않습니다: {mime!r}')
    return suffixes[mime]


def _frozen_media_bytes(data, directory, suffix):
    """Content-addressed evidence file — **the name is the freeze**.

    Every measured sample, marked candidate and review attachment is written
    once under its own sha256. Byte-identical pictures (a photo whose content
    rect is the whole frame, a sample with no face to mark, the same candidate
    frozen again for a review request) share one file: a later freeze of the
    same bytes finds it instead of copying.
    ★2026-09-13 실측: 뇌전구 작업 폴더 631MB 중 237MB 가 같은 PNG 를 3~6벌 복사한
      것이었다 — frame_/content_/candidate_ 세 이름 + image_qc 의 <sha> 사본 +
      client_review 의 client-media/<sha> 사본. 보존 층이 둘이었고 서로를 몰랐다.
    """
    digest = hashlib.sha256(data).hexdigest()
    directory = os.fspath(directory) or '.'
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, digest + suffix)
    with _asr_lock(target + '.publish.lock', blocking=True):
        if not os.path.exists(target):
            # The lock covers existence, complete write and publication only.
            fd, temporary = tempfile.mkstemp(dir=directory, suffix='.part')
            try:
                with os.fdopen(fd, 'wb') as stream: stream.write(data)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
        if _image_file_sha(target) != digest:
            raise StepError('보존된 검수 자료의 SHA가 다릅니다.')
    return target, digest


def _frozen_pixels_key(image):
    """What decides the encoded PNG bytes: the pixels, their PNG-relevant info and the encoder.

    Same key ⇒ `image.save(format='PNG')` writes the same bytes. Anything this
    function does not understand returns None and the picture is encoded as before.
    """
    if getattr(image, 'mode', None) not in ('RGB', 'L'):
        return None
    try:
        import zlib
        import PIL
        h = hashlib.sha256()
        h.update(json.dumps(['frozen-png-pixels-v1', image.mode, list(image.size), PIL.__version__,
                             zlib.ZLIB_RUNTIME_VERSION]).encode())
        for name in sorted(image.info, key=repr):
            value = image.info[name]
            h.update(repr(name).encode('utf-8', 'backslashreplace') + b'\0' + type(value).__name__.encode() + b'\0')
            h.update(bytes(value) if isinstance(value, (bytes, bytearray))
                     else repr(value).encode('utf-8', 'backslashreplace'))
            h.update(b'\0')
        h.update(image.tobytes())
        return h.hexdigest()
    except Exception:  # noqa: BLE001 — 열쇠를 못 만들면 되쓰지 않을 뿐이다(예전처럼 굽는다)
        return None


def _frozen_png_known(key, directory, io_directory):
    """The already published PNG of these exact pixels, verified by its own SHA name."""
    if key is None:
        return None
    try:
        with open(os.path.join(io_directory, key + '.pixels'), encoding='ascii') as stream:
            digest = stream.read(80).strip()
    except (OSError, ValueError):
        return None
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        return None
    target = os.path.join(directory, digest + '.png')
    try:
        if _image_file_sha(_review_receipt_io_path(target)) != digest:
            return None
    except OSError:
        return None
    return target


def _frozen_png(image, directory):
    """Encode directly to disk, retaining the exact PNG bytes and SHA identity.

    PNG compression already holds raster/encoder buffers. A second growing
    BytesIO of the complete PNG caused a measured MemoryError in subject review.
    No image size, quality, sample count or existing evidence changes here.

    ■ 같은 픽셀은 다시 굽지 않는다 (2026-10-05)
        피사체 측정은 대기 → 답 → 재개 때마다 앞선 판의 표본을 다시 지나가며 표본마다 PNG 를 두 번
        (알맹이 자르기 · 얼굴 표시) 다시 구웠다 — 결과 파일은 매번 같은 이름(자기 sha256)이라 버려졌다.
        실측 1080p 한 장: 굽기 159ms ↔ 픽셀 지문 16ms + 기존 파일 지문 3ms(i7-9700).
        구운 뒤 «이 픽셀(+PNG 에 실리는 info · 인코더 판) → 이 PNG» 를 `<픽셀 지문>.pixels` 로 옆에 남기고,
        다음에는 그 PNG 가 **자기 이름과 같은 바이트일 때만** 되쓴다. 아니면 예전 그대로 굽는다.
    """
    directory = os.fspath(directory) or '.'
    io_directory = _review_receipt_io_path(directory)
    os.makedirs(io_directory, exist_ok=True)
    pixels = _frozen_pixels_key(image)
    known = _frozen_png_known(pixels, directory, io_directory)
    if known is not None:
        return known
    fd, temporary = tempfile.mkstemp(dir=io_directory, suffix='.part')
    complete = False
    preserve = False
    try:
        with os.fdopen(fd, 'wb') as stream:
            image.save(stream, format='PNG')
            complete = True
            stream.flush()
            os.fsync(stream.fileno())
        digest = _image_file_sha(temporary)
        target = os.path.join(directory, digest + '.png')
        io_target = _review_receipt_io_path(target)
        with _asr_lock(io_target + '.publish.lock', blocking=True):
            if not os.path.exists(io_target):
                os.replace(temporary, io_target)
                _tts_fsync_dir(io_directory)
            if _image_file_sha(io_target) != digest:
                raise StepError('보존된 검수 자료의 SHA가 다릅니다.')
        if pixels is not None:
            # A torn or missing note only costs one more encode: the reader accepts
            # nothing but 64 hex digits naming a PNG whose bytes hash to that name.
            try:
                with open(os.path.join(io_directory, pixels + '.pixels'), 'w', encoding='ascii') as note:
                    note.write(digest)
            except OSError:
                pass
        return target
    except BaseException as error:
        # Encoded evidence survives flush/fsync/publication/hash failure; the
        # recovery path does not claim durability or a successful publication.
        # Only this invocation's incomplete staging file may be removed; paid receipts
        # and previously published media are never touched.
        preserve = complete and os.path.exists(temporary)
        if preserve:
            error.recovery_path = temporary
        raise
    finally:
        if not preserve and os.path.exists(temporary):
            os.unlink(temporary)


def _is_frozen(path, digest, suffix):
    """A file already named by its own sha256 cannot be replaced by a later sample name."""
    return os.path.basename(os.fspath(path)) == digest + suffix


def _client_review_media(path, directory, mime, *, image_only=False):
    """Freeze actual bytes: later sample/refinement names cannot replace evidence.

    A source that is already content-addressed (`<sha256><suffix>`, written by
    `_frozen_media_bytes`) is returned as-is — copying it under the same name
    into another folder froze nothing and doubled every review image.
    """
    suffix = _review_media_suffix(mime, image_only=image_only)
    source = os.path.abspath(path)
    stem = os.path.basename(source)
    if stem.endswith(suffix) and len(stem) == 64 + len(suffix):
        digest = _image_file_sha(source)
        if _is_frozen(source, digest, suffix):
            return {'path':source, 'sha256':digest, 'mime':mime}
    os.makedirs(directory, exist_ok=True)
    # ★한 번 읽으며 복사와 지문을 함께 한다(2026-10-17 쇼핑 shop_footage «검수 자료가 복사 중 바뀌었습니다» — 원본을 먼저 재고
    #   다시 읽어 복사하는 사이에 다른 일꾼이 같은 격자를 다시 굽고 있었다). 증거는 **읽은 그 바이트**이고 그 지문이 이름이다 —
    #   같은 파일을 세 번 해시하던 것(원본·임시·결과)도 한 번으로 줄었다(6-00 중복 지문).
    fd, temporary = tempfile.mkstemp(dir=directory, suffix='.part')
    try:
        hasher = hashlib.sha256()
        with os.fdopen(fd, 'wb') as out, open(source, 'rb') as incoming:
            for chunk in iter(lambda: incoming.read(1024 * 1024), b''):
                hasher.update(chunk)
                out.write(chunk)
        digest = hasher.hexdigest()
        target = os.path.join(directory, digest + suffix)
        with _asr_lock(target + '.publish.lock', blocking=True):
            if not os.path.exists(target):
                os.replace(temporary, target)
            elif _image_file_sha(target) != digest:
                raise StepError('보존된 검수 자료의 SHA가 다릅니다.')
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return {'path':target, 'sha256':digest, 'mime':mime}


def client_review(job, *, replies=None, validator, claude=None, client=None):
    """CLI for actual images; host model handoff for video/audio or unavailable CLI.

    No provider credentials or HTTP call belong to this transport. Video and
    audio are explicit required evidence; an image-only CLI cannot review them.
    """
    selected = resolve_review_client(client, legacy=claude)
    replies = resolve_review_replies(replies)
    media_dir = os.path.join(os.path.dirname(job['out']), 'client-media')
    images = []
    for n, im in enumerate(job.get('images') or []):
        entry = _client_review_media(im['path'], media_dir, im.get('mime') or 'image/png', image_only=True)
        entry['id'] = f'image-{n}-' + entry['sha256']
        if im.get('label'): entry['label'] = im['label']
        images.append(entry)
    request = {'version':1, 'contract':job['qc_contract'], 'prompt':job['prompt'], 'images':images}
    capabilities = _review_capabilities(job.get('capabilities'))
    if capabilities: request['capabilities'] = capabilities
    if job.get('binding') is not None: request['binding'] = job['binding']
    if job.get('video'):
        request['video'] = _client_review_media(job['video'], media_dir, 'video/mp4')
        request['video']['required'] = True
    if job.get('audio'):
        request['audio'] = _client_review_media(job['audio'], media_dir, 'audio/wav')
        request['audio']['required'] = True
    for field, singular, mime in (('videos','video','video/mp4'),('audios','audio','audio/wav')):
        if field in job and not isinstance(job[field],list):
            raise StepError('검수 영상·음성 자료는 파일 목록이어야 합니다.')
        if job.get(field):
            request[field] = []
            for n, media in enumerate(job[field]):
                if not isinstance(media,dict) or not media.get('path'):
                    raise StepError('검수 영상·음성 파일 경로가 없습니다.')
                entry = _client_review_media(media['path'],media_dir,mime)
                entry.update(id=f'{singular}-{n}-'+entry['sha256'],required=True)
                if media.get('label'): entry['label'] = media['label']
                request[field].append(entry)
    if job.get('audio_status'):
        request['audio_status'] = job['audio_status']
    # 답의 모양을 아는 질문은 그 모양(JSON 스키마)을 요청에 싣는다(2026-10-21 쇼핑 신고 510306). 없으면 예전처럼 «답을 JSON 글자로».
    #   글자로 받으면 모델이 JSON 을 한 번 더 이스케이프해야 해서 따옴표가 빠진 답(«Expecting ',' delimiter»)이 나와 그 카드가
    #   대기로 남았다(CLhwIycye5c 재현: 글자 방식 26회 중 4회 · 스키마 방식 11회 중 0회). 질문의 뜻이므로 지문(binding)에 든다.
    if job.get('answer_schema') is not None:
        if not isinstance(job['answer_schema'], dict) or job['answer_schema'].get('type') != 'object':
            raise StepError('검수 답 스키마는 JSON 객체 스키마여야 합니다.')
        request['answer_schema'] = job['answer_schema']
    # Portable identity uses the measured bytes and semantic question, not paths.
    binding = copy.deepcopy(request)
    for field in ('images','video','audio','videos','audios'):
        values = binding.get(field) or []
        for entry in values if isinstance(values,list) else [values]: entry.pop('path',None)
    key = hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    request['request_sha256'] = key
    request['reply_schema'] = {'request_sha256':key, 'answer':'Existing typed JSON answer for the supplied prompt.',
        'reviewed_image_ids':[im['id'] for im in images],
        **({'reviewed_video_sha256':request['video']['sha256']} if 'video' in request else {}),
        **({'reviewed_audio_sha256':request['audio']['sha256']} if 'audio' in request else {}),
        **({'reviewed_video_ids':[entry['id'] for entry in request['videos']]} if 'videos' in request else {}),
        **({'reviewed_audio_ids':[entry['id'] for entry in request['audios']]} if 'audios' in request else {})}
    if capabilities: request['reply_schema']['used_capabilities'] = capabilities
    request['instructions'] = ('현재 연결된 클라이언트가 모든 원본 해상도 이미지와 영상 전체를 읽고, '
        '필수로 표시한 모든 영상·음성 자료를 읽고 직접 들어 화자/장면을 확인하세요. 대본 문맥은 실제 음성의 대체물이 아닙니다. '
        '읽지 못한 자료가 있으면 통과 답을 만들지 말고 미완료로 유지하세요. '
        '자료를 검토한 뒤 reply_schema의 확인 SHA/ID와 prompt의 실제 측정 번호로만 답하세요. 사용자 승인 질문은 필요하지 않습니다.')
    if 'web_search' in capabilities:
        request['instructions'] += ' 웹검색으로 교차 확인하고 실제 확인한 출처 URL을 답에 남기세요. 검색하지 못했으면 used_capabilities 확인을 꾸미지 말고 미완료로 유지하세요.'
    request_path = _review_receipt_io_path(job['out'] + '.client-request.json')
    receipt_path = _review_receipt_io_path(job['out'] + '.client-receipt.json')
    with review_receipt_lock(receipt_path):
        saved = _review_receipt_load(receipt_path, [key])
        # 이 요청에 이미 거절한 답의 지문 — 아래에서 영수증을 놓아 줘도(saved={}) 같은 답을 다시 받아 거절하지 않게 먼저 읽는다.
        rejected_fp = saved.get('rejected_reply_sha256') if saved.get('request_sha256') == key else None
        if saved.get('request_sha256') == key and release_unfinished_review(receipt_path, key, saved, unfinished_review(saved)):
            # 사람이 «다시» 를 알린 컷 — 결과 없이 끝난 모델 실행(구독 AGY 종료 143 등)을 한 번 다시 띄운다(옛 기록은 보존).
            saved = {}
        provider_evidence = saved.get('provider_evidence')
        def save(record):
            if provider_evidence is not None:record['provider_evidence']=provider_evidence
            _review_receipt_save(receipt_path, record)
        def capture_provider_result(evidence):
            nonlocal provider_evidence
            provider_evidence=evidence
            save({'request_sha256':key,'outcome':'started','attempted':True,'engine':selected['provider']})
        if saved.get('request_sha256') == key:
            if saved.get('outcome') == 'refused':
                raise remember_review_refusal(ProviderRefusalError(saved['origin'],saved['reason_code'],saved['reason']))
            if saved.get('outcome') == 'complete' and validator(saved.get('answer')):
                return saved['answer']
        _photo_write_state(request_path, request)
        reply = (replies or {}).get(key)
        fingerprint = None if reply is None else hashlib.sha256(json.dumps(reply,sort_keys=True,ensure_ascii=False,
            separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if fingerprint is not None and selected['provider'] == 'agy' and fingerprint == rejected_fp:
            # ★구독 AGY 검수에 이미 거절한 그 답이 다시 실려 왔다(옛 흐름: AGY 가 결과 없이 끝나면 호스트가 답을 손으로 썼다).
            #   그 답은 영수증(rejected_reply_sha256)에 거절로 남아 있다 — 다시 대조해 또 거절하면 AGY 를 영영 못 띄운다
            #   (2026-10-15 검토 · 실행으로 재현). 이 요청은 AGY 의 몫이니 그 답을 건너뛰고 아래 모델 경로로 간다.
            reply = None
        if reply is not None:
            def invalid_reply(reason):
                pending = dict(request,reply_error={'code':'client_review_reply_invalid',
                    'message':reason,'submitted_reply_sha256':fingerprint})
                _photo_write_state(request_path,pending)
                # 거절 영수증도 이 요청의 모델 시도 사실(attempted·engine)을 잇는다 — 잃으면 «결과 없이 끝난 AGY» 가
                #   «시도 모름» 이 되어 사람의 «다시» 로도 놓아 주지 못하고(unfinished_review) 사전 점검 재시도도 없다
                #   (preflight_only) — 막다른 길(2026-10-15 검토). 구독 AGY 는 모델을 띄운 적이 없으면 attempted=False 로
                #   적는다(다음 실행이 처음 시도로 띄운다 — 같은 요청의 반복이 아니다). 다른 엔진은 예전 영수증 모양 그대로다.
                prior = saved if saved.get('request_sha256') == key else {}
                tried = prior.get('attempted') if 'attempted' in prior else (False if selected['provider'] == 'agy' else None)
                save({'request_sha256':key,'outcome':'pending','reason':reason,'rejected_reply_sha256':fingerprint,
                      **({'attempted':tried,'engine':prior.get('engine') or selected['provider']} if tried is not None else {})})
                # ★거절한 답을 이 실행의 답 지도에서 뺀다 (2026-10-05 · 원장 W2-14 실행기 조각) — 같은 실행의 다른 자리가
                #   같은 요청에 그 답을 다시 대지 않게. 지문은 위 영수증(rejected_reply_sha256)에 남는다. payload 의 두 칸
                #   (review_replies · focus_review_replies)에서 지우는 것은 체크포인트를 쓰는 구동기 몫이다(B 묶음) —
                #   예외에 그 재료를 싣는다(`rejected_reply`). 서버는 같은 지문을 규칙 ①로 버린다(volcano_review_policy).
                shared = current_review_context().get('replies')
                if isinstance(shared, dict) and shared.get(key) == reply:
                    shared.pop(key, None)
                error = ClientReviewInputError(pending,reason)
                error.rejected_reply = {'request_sha256': key, 'reply_sha256': fingerprint}
                raise error
            expected = request['reply_schema']
            if (not isinstance(reply,dict) or reply.get('request_sha256') != key
                    or reply.get('reviewed_image_ids') != expected['reviewed_image_ids']
                    or any(reply.get(field) != expected[field] for field in ('reviewed_video_sha256','reviewed_audio_sha256','reviewed_video_ids','reviewed_audio_ids','used_capabilities') if field in expected)):
                invalid_reply('검수 답의 자료 확인 ID/SHA가 현재 요청과 다릅니다. 같은 요청에 맞게 답을 수정하세요.')
            answer = reply.get('answer')
            try:
                _raise_provider_refusal(answer, origin='provider.client')
            except ProviderRefusalError as exc:
                save({'request_sha256':key,'outcome':'refused',
                    'origin':exc.origin,'reason_code':exc.reason_code,'reason':exc.reason,
                    'request_sent':getattr(exc,'request_sent',True)})
                raise
            if not validator(answer):
                invalid_reply('클라이언트 검수 답의 측정 ID 또는 판정 형식이 잘못되었습니다. 같은 실제 자료를 기준으로 답을 수정하세요.')
            save({'request_sha256':key,'outcome':'complete','answer':answer,'engine':'client','reply':reply})
            return answer
        preflight_only = saved.get('outcome') == 'pending' and (
            saved.get('attempted') is False or saved.get('reason') in {
                provider + suffix for provider in ('claude','codex')
                for suffix in (' 구독 계정 로그인 확인 필요',' CLI 없음')})
        # ★이 요청에 모델을 **실제로 띄웠다가** 결과 없이 끝났는가(사전 점검 실패가 아니라) — 대기 예외에 싣는다(2026-10-08).
        #   쇼핑 수급은 이 표식이 있는 구독 AGY 대기만 «그 후보만 판정 못 함» 으로 넘기고, 사전 점검 실패(설정·설치·자료 바뀜 —
        #   모든 요청에 같은 실패)는 지금처럼 멈춘다. 이어 하기(이미 시도한 영수증)도 같은 표식을 단다(다시 보내지 않는다).
        model_attempted = saved.get('request_sha256') == key and saved.get('attempted') is True
        if (selected['provider'] != 'host' and (selected['provider']=='agy' or not any(request.get(field) for field in ('video','audio','videos','audios')))
                and (saved.get('request_sha256') != key or preflight_only)):
            attempted = False
            def before_model():
                nonlocal attempted
                # Authentication checks make no model request. Record the actual
                # model launch first so an interrupted CLI is never auto-repeated.
                save({'request_sha256':key,'outcome':'started',
                    'attempted':True,'engine':selected['provider']})
                attempted = True
            try:
                options = dict(image_paths=[im['path'] for im in images],want_keys=(),
                    image_labels=[im.get('label') or im['id'] for im in images])
                if capabilities: options['capabilities'] = capabilities
                if selected['provider']=='agy':
                    import agy_review_bridge
                    config=dict(selected,run_id=current_review_context().get('_agy_run_id'))
                    answer,why=agy_review_bridge.review(config,request,before_model=before_model,on_result=capture_provider_result)
                elif client is None and _REVIEW_CONTEXT.get() is None and claude:
                    before_model()
                    answer, why = claude_call(selected, job['prompt'], **options)
                else:
                    answer, why = client_call(selected, job['prompt'], _before_model=before_model, **options)
            except ProviderRefusalError as exc:
                save({'request_sha256':key,'outcome':'refused',
                    'origin':exc.origin,'reason_code':exc.reason_code,'reason':exc.reason,
                    'request_sent':getattr(exc,'request_sent',True)})
                raise
            if answer is not None and validator(answer):
                save({'request_sha256':key,'outcome':'complete','answer':answer,'engine':selected['provider']})
                return answer
            why = why or '클라이언트 검수 형식 확인 필요'
            save({'request_sha256':key,'outcome':'pending',
                'attempted':attempted,'engine':selected['provider'],
                'reason':why})
            model_attempted = attempted
        else:
            why = saved.get('reason') if isinstance(saved.get('reason'), str) else ''
        pending = ClientReviewPending(request)
        pending.model_attempted = bool(model_attempted)
        # ★«연결된 사람·호스트가 답할 차례» 가 아니라 «검수 엔진이 결과 없이 끝남» 인가(2026-10-15 쇼핑 신고 — 구독 AGY 종료 143).
        #   검수는 모델(구독 AGY)의 몫이다(전역 규칙 6-1) — 사람에게 영상·음성 판독 답을 손으로 쓰게 하면 안 된다.
        #   엔진이 구독 AGY 일 때다(모델 실행이 결과 없이 끝났든 사전 점검이 실패했든 — 사람 답으로 못 푼다). 받는 쪽이 opt-in
        #   으로 쓴다(subject_focus.select_subjects · review_film_frames 의 engine_failure_rows — local_focus 를 거치는 채널).
        #   ★claude·codex CLI 는 넣지 않는다(2026-10-15 검토): 그 CLI 는 연결된 호스트 자신이라, CLI 가 결과 없이 끝나도
        #   호스트가 같은 요청에 답할 수 있다(예전 흐름 그대로 — 실행 실패 행으로 바꾸면 호스트 답 길이 닫힌다).
        #   호스트 답 대기(provider host · 영상 못 읽는 CLI 의 위임)도 여기 들지 않는다.
        pending.engine_failed = selected['provider'] == 'agy'
        pending.engine_reason = (why or '')[:1200]
        # 다시 띄워도 같은 실패인 사전 점검(판독 파일이 view_file 한도를 넘음)은 부르는 쪽이 «다시» 대신 다른 길로 푼다.
        pending.engine_code = 'AGY_FILE_TOO_LARGE' if (why or '').startswith('AGY_FILE_TOO_LARGE') else 'client_review_no_result'
        raise pending


def client_video_audio(config, directory):
    """Extract the actual proxy's whole audio; never treat missing sound as silence."""
    probe = config.get('ffprobe') or 'ffprobe'
    def audio_stream(path):
        result = run_argv([probe,'-v','error','-select_streams','a','-show_entries','stream=index',
                           '-of','json',path],capture=True)
        if result.returncode: raise StepError('검수 영상의 실제 오디오 스트림을 확인하지 못했습니다.')
        return bool(json.loads(result.stdout).get('streams'))
    source_has_audio = audio_stream(config['path'])
    proxy_has_audio = audio_stream(config['out'])
    if source_has_audio and not proxy_has_audio:
        raise StepError('검수 proxy에서 원본 음성이 누락되었습니다. 사진만으로 화자 검수를 통과시키지 않습니다.')
    if not proxy_has_audio: return {'audio_status':'measured_no_audio_stream'}
    audio = str(Path(directory)/'review.audio.wav')
    run_argv([config['shrink_argv'][0],'-y','-v','error','-i',config['out'],'-vn','-c:a','pcm_s16le',audio])
    if not os.path.isfile(audio) or os.path.getsize(audio) <= 44:
        raise StepError('검수 음성을 추출하지 못했습니다.')
    return {'audio':audio,'audio_status':'required_original_proxy_audio'}


def cached_client_video_audio(config, directory):
    """Reuse measured audio bytes across handoffs without reusing any judgment."""
    directory = Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    receipt = directory/'audio-evidence.json'
    with _ArgvInputDigests() as sources, review_receipt_lock(str(receipt)):
        inputs = {path:sources.digest(path) for path in (config['path'],config['out'])}
        tools = []
        for executable in (config['shrink_argv'][0],config.get('ffprobe') or 'ffprobe'):
            path = Path(shutil.which(executable) or executable).resolve()
            stat = path.stat()
            tools.append([str(path),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns])
        binding = {'version':1,'inputs':inputs,'tools':tools}
        try:
            saved = json.loads(receipt.read_text(encoding='utf8'))
            result = saved['result']
            valid = saved['binding'] == binding and isinstance(result,dict)
            if result.get('audio_status') == 'measured_no_audio_stream':
                valid = valid and not result.get('audio')
            elif result.get('audio_status') == 'required_original_proxy_audio':
                audio = str(directory/'review.audio.wav')
                valid = valid and result.get('audio') == audio and os.path.isfile(audio) and _image_file_sha(audio) == saved.get('audio_sha256')
            else:
                valid = False
            if valid:
                sources.check()
                return result
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            pass
        result = client_video_audio(config,str(directory))
        sources.check()
        saved = {'binding':binding,'result':result}
        if result.get('audio'): saved['audio_sha256'] = _image_file_sha(result['audio'])
        _photo_write_state(str(receipt),saved)
        return result


def _video_budget_identity_body(config, body):
    """Preserve the earlier question identity when only its output ceiling grows.

    The actual HTTP body is untouched. Prompt, model, thinking policy and
    media still bind the answer; completed AND unknown receipts retain their
    original lock/key when the server removes the old expansion round trip.
    """
    identity = config.get('output_budget_identity')
    if identity is None:
        return body
    generation = body.get('generationConfig') if isinstance(body, dict) else None
    if (not isinstance(identity, dict) or set(identity) != {'initial', 'retry'}
            or any(type(identity.get(k)) is not int or identity[k] <= 0 for k in ('initial', 'retry'))
            or identity['retry'] < identity['initial']
            or config.get('body_kind') != 'gemini_video' or config.get('retry_max_tokens') != 0
            or not isinstance(generation, dict)
            or generation.get('maxOutputTokens') != identity['retry']):
        raise StepError('영상 출력 예산의 재사용 계약이 잘못되었습니다. 기존 검수 기록을 보존합니다.')
    return dict(body, generationConfig=dict(generation, maxOutputTokens=identity['initial']))


def review_semantic_config(value):
    """Transport caps and a declared ceiling upgrade preserve the same question."""
    if not isinstance(value, dict):
        return value
    result = {k:v for k,v in value.items() if k not in {'max_media_bytes','max_request_bytes','size_fit'}}
    if 'output_budget_identity' in result:
        result['body'] = _video_budget_identity_body(value, value.get('body'))
        result['retry_max_tokens'] = result.pop('output_budget_identity')['retry']
    return result


def _image_review_key(job, images, claude):
    # The original-resolution bytes and full request/validation options bind
    # the exact provider body. Enforcement caps never change that question.
    binding = dict(job={k:v for k,v in review_semantic_config(job).items()
                        if k not in {'out','_image_data'}},
                   images=images, claude=claude, version=1)
    # ★같은 바이트를 조각으로 흘려 잰다(2026-10-17 강석주 render_plan MemoryError 2건·2명) — 원본 해상도 그림 바이트가 든 묶음을
    #   json.dumps 로 한 덩어리 글자 + 그 utf-8 사본까지 만들면 후보가 많을 때 메모리가 모자랐다. iterencode 는 json.dumps 와
    #   같은 글자를 내므로 지문(=기존 검수 영수증 열쇠)이 바뀌지 않는다 — 다시 검수(재구매)하지 않는다.
    digest = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False, separators=(',', ':')).iterencode(binding):
        digest.update(chunk.encode('utf-8'))
    return digest.hexdigest()


@contextlib.contextmanager
def review_receipt_lock(path):
    """Share the existing OS lock across processes; a concurrent request is pending."""
    os.makedirs(os.path.dirname(str(path)) or '.',exist_ok=True)
    # 잠금을 **얻는 순간**의 실패만 «다른 실행기가 처리 중» 이다. 예전에는 try 가 yield 까지 감싸 잠금 안의 일이 낸
    #   전사·검수 대기(TranscriptionPending)까지 이 문구로 바꿨다. 잠금은 OS 잠금이라 주인 프로세스가 죽으면 OS 가 푼다 —
    #   잠겨 있다는 것 자체가 주인이 살아 있다는 증거다(낡은 잠금이 없다). 그래서 멈춤이 아니라 대기다(ReviewInProgress
    #   = TranscriptionPending → 구동기의 «N초 뒤 재개» · 10-21 인물형 롱폼 5db32e 45건/1분: 앞서 띄운 실행이 render_plan 을
    #   하는 동안 다시 띄운 실행이 «[실행기 중단]» 신고를 남기고 멈추기를 되풀이했다).
    with contextlib.ExitStack() as held:
        try:
            held.enter_context(_asr_lock(str(path)+'.lock'))
        except TranscriptionPending as cause:
            raise ReviewInProgress() from cause
        yield


class _ImageReviewData:
    """Snapshot every unique URL before review, without retaining a whole cut in RAM.

    The existing declared body/media caps determine when to spill, not a new
    service limit. One anonymous/delete-on-close file preserves the exact base64
    snapshot through every batch and also disappears on process termination.
    Original media and paid review receipts are never moved or removed.
    """
    def __init__(self, units, job):
        _image_request_fits(job, 0, 0)  # validate the declared caps before allocation
        limits = []
        if job.get('max_request_bytes') is not None:
            limits.append(job['max_request_bytes'])
        if job.get('max_media_bytes') is not None:
            limits.append(4 * ((job['max_media_bytes'] + 2) // 3))
        self._limit = min(limits) if limits else None
        self._units = units
        self._memory = {}
        self._locations = {}
        self._batch = {}
        self._spool = None

    def _store(self, url, data):
        encoded = data.encode('ascii')
        self._spool.seek(0, os.SEEK_END)
        offset = self._spool.tell()
        if self._spool.write(encoded) != len(encoded):
            raise OSError('검수 임시 원문을 온전히 저장하지 못했습니다. 새 검수는 보내지 않았습니다.')
        self._locations[url] = (offset, len(encoded), hashlib.sha256(encoded).digest())

    def __enter__(self):
        total = 0
        try:
            for unit in self._units:
                for image in unit['images']:
                    url = image['url']
                    if url in self._memory or url in self._locations:
                        continue
                    data = _fetch_b64(url)
                    if self._spool is None and self._limit is not None and total + len(data) > self._limit:
                        self._spool = tempfile.TemporaryFile(mode='w+b', prefix='volcano-review-')
                        for previous_url, previous_data in self._memory.items():
                            self._store(previous_url, previous_data)
                        self._memory.clear()
                    if self._spool is None:
                        self._memory[url] = data
                    else:
                        self._store(url, data)
                    total += len(data)
            if self._spool is not None:
                # A late unreadable source or disk-full error still precedes any
                # provider call, just as the former eager in-memory snapshot did.
                self._spool.flush()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __getitem__(self, url):
        if self._spool is None:
            return self._memory[url]
        if url not in self._batch:
            offset, length, digest = self._locations[url]
            self._spool.seek(offset)
            data = self._spool.read(length)
            if len(data) != length or hashlib.sha256(data).digest() != digest:
                raise StepError('검수 임시 원문 지문이 달라 새 검수를 보내지 않았습니다. 원본과 기존 검수 기록은 보존됩니다.')
            self._batch[url] = data.decode('ascii')
        return self._batch[url]

    def suspend(self):
        # Keep the exact eager snapshot; only anonymous bytes are parked.
        if self._spool is None:
            self._spool = tempfile.TemporaryFile(mode='w+b',prefix='volcano-review-wait-')
            try:
                for url,data in self._memory.items():self._store(url,data)
                self._spool.flush()
            except BaseException:
                self._spool.close();self._spool=None;raise
            self._memory.clear()
        self._batch.clear()
        return lambda cancelled=False:None

    def release_batch(self):
        self._batch.clear()

    def __exit__(self, *args):
        self._memory.clear()
        self._batch.clear()
        if self._spool is not None:
            self._spool.close()


def image_qc_batches(job, units, headers, *, prompt_for, result_validator, allow_provider=True,
                     review_policy=None, client_replies=None, review_budget=None, client=None):
    """Independent global-ID decisions only. Atomic units may contain image pairs.

    Generic candidate ranking must not use this helper: comparing separate
    candidate groups is a different question. Encode every actual image once;
    use the actual sender body to choose each lossless batch.
    """
    if job.get('qc_contract') not in {'focus_object_v1', 'film_frames_v1'}:
        raise StepError('이 그림 검수 계약은 후보를 나눠 판단할 수 없습니다.')
    if client is None: client = job.get('client')
    native = resolve_review_policy(review_policy)['provider'] == 'client'
    import subject_stage_pool as ST
    with _ImageReviewData(units, job) as loaded, ST.preserve(loaded.suspend):
        combined = []; batches = []; begin = 0; verdict = 'accepted'; summaries = []
        while begin < len(units):
            selected_job = None; end = begin
            for stop in range(begin + 1, len(units) + 1):
                selected = units[begin:stop]
                images = [im for unit in selected for im in unit['images']]
                labels = [label for unit in selected for label in unit.get('labels', [])]
                proposed = dict(job, prompt=prompt_for([unit['metadata'] for unit in selected]),
                                images=images, n_candidates=len(images))
                if labels:
                    proposed['image_labels'] = labels
                data = [(loaded[im['url']], im.get('mime') or 'image/jpeg') for im in images]
                oversized = False
                if proposed.get('max_request_bytes') is not None or proposed.get('max_media_bytes') is not None:
                    _, media, size = _image_request_size(proposed, data)
                    oversized = not _image_request_fits(proposed, media, size)
                    if oversized and (not native or stop != begin + 1):
                        break
                proposed['_image_data'] = data
                selected_job = proposed; end = stop
                if oversized:
                    # Native clients receive bound local files, not the inline API
                    # body measured above. Keep the existing batch grouping, but
                    # allow one indivisible source/crop pair at its original size.
                    break
            if selected_job is None:
                exc = StepError('원본 해상도의 그림 검수 단위 한 개가 요청 크기 상한을 넘습니다. '
                                '원본과 후보를 보존했고 새 요청은 보내지 않았습니다.')
                exc.code = 'review_request_oversize'   # 같은 단위·같은 상한이면 다시 재도 같다(image_qc 의 같은 코드와 한 이름).
                raise exc
            # Retain the original unbatched receipt pathname. Split batches use
            # request-specific receipts and never overwrite a completed peer batch.
            if begin or end != len(units):
                key = _image_review_key(selected_job, selected_job['_image_data'], job.get('claude'))
                selected_job['out'] = str(job['out']) + '.batch_' + key + '.json'
            selected_metadata = [u['metadata'] for u in units[begin:end]]
            data = None; proposed = None; selected = None
            try:
                answer = image_qc([selected_job], headers, retry=1, claude=job.get('claude'),
                    allow_provider=allow_provider, review_policy=review_policy,
                    client_replies=client_replies, review_budget=review_budget, client=client,
                    result_validator=lambda j, a: result_validator(a, selected_metadata))[str(job['index'])]
            except StepError as exc:
                if isinstance(exc, (ProviderRefusalError, ClientReviewPending)) or getattr(exc,'review_budget_blocked',None):
                    raise
                return {'verdict':'unparsed', 'code':getattr(exc,'code','review_execution_failed'),
                        'reason':str(exc)[:1200], 'decisions':combined, 'batches':batches,
                        'pending_ids':[u['metadata'].get('sample',u['metadata'].get('candidateNumber')) for u in units[begin:]]}
            batches.append({'ids':[m.get('sample',m.get('candidateNumber')) for m in selected_metadata],
                            'verdict':answer.get('verdict'), 'request_sha256':answer.get('request_sha256')})
            if not result_validator(answer, selected_metadata):
                return dict(answer, decisions=combined + (answer.get('decisions') or []), batches=batches)
            combined.extend(answer.get('decisions') or [])
            if answer.get('verdict') != 'accepted':
                verdict = 'retry'
            if isinstance(answer.get('summary'), str):
                summaries.append(answer['summary'][:600])
            begin = end
            del selected_job, proposed, data
            loaded.release_batch()
        return {'verdict':verdict, 'decisions':combined, 'batches':batches,
                'summary':' '.join(summaries)[:1200], '_engine':'batched-image-review'}


def _vision_text(raw, pluck):
    """서버가 알려준 자리(`pluck`)에서 글을 꺼낸다. **모양을 여기서 정하지 않는다.**

    ★못 꺼내면 빈 글자다 — 부르는 쪽이 「모른다」로 다룬다.
      파싱 실패를 「통과」로 읽는 것이 가장 위험한 기본값이다.
    """
    cur = raw
    for part in str(pluck or "").replace("]", "").split("."):
        if not part:
            continue
        if "[" in part:
            name, idx = part.split("[", 1)
            if name and not isinstance(cur, dict):
                return ""
            cur = (cur or {}).get(name) if name else cur
            if not isinstance(cur, list):
                return ""
            try:
                cur = (cur or [])[int(idx)]
            except (IndexError, ValueError, TypeError):
                return ""
        else:
            if not isinstance(cur, dict):
                return ""
            cur = cur.get(part)
    if isinstance(cur, list):
        # 네이티브 응답은 최종 글이 여러 part에 나뉠 수 있다. 사고 과정은 답이 아니다.
        return "".join(p["text"] for p in cur if isinstance(p, dict)
                       and isinstance(p.get("text"), str) and not p.get("thought"))
    return cur if isinstance(cur, str) else ""


def _json_object(text):
    """완전한 JSON 객체만 읽는다. 울타리/설명은 벗겨도 잘린 내용을 만들어 채우지 않는다."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(text)
    except ValueError:
        # 배열 안의 객체를 답으로 오인하지 않는다. 기존 형제 파서와 같은 한 객체 추출.
        if text.startswith("["):
            return None
        a, b = text.find("{"), text.rfind("}")
        if a < 0 or b <= a:
            return None
        try:
            obj = json.loads(text[a:b + 1])
        except ValueError:
            return None
    return obj if isinstance(obj, dict) else None


def _review_json_path(item, binding):
    key = hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False).encode('utf8')).hexdigest()
    context = current_review_context()
    directory = (os.path.dirname(context.get('budget') or '') or item.get('out_dir')
                 or os.path.dirname(item.get('image') or '') or '.')
    return key, item.get('out') or os.path.join(directory,'review-'+key+'.json')


def _review_receipt_io_path(path):
    """Keep receipt identities intact while allowing Windows paths past MAX_PATH."""
    path = os.fspath(path)
    if os.name != 'nt':
        return path
    path = os.path.abspath(path)
    if not path.startswith('\\\\?\\'):
        path = ('\\\\?\\UNC\\' + path[2:] if path.startswith('\\\\')
                else '\\\\?\\' + path)
    return path


def _strip_extended_prefix(text):
    """윈도우 확장 경로 접두(`\\\\?\\` · `\\\\?\\UNC\\`)를 벗긴 평범한 경로 글자 — 다른 글자는 그대로."""
    if text.startswith('\\\\?\\UNC\\'):
        return '\\\\' + text[8:]
    if text.startswith('\\\\?\\'):
        return text[4:]
    return text


def _file_uri(path):
    """로컬 파일 → `file://` URI — 실행기 전체가 쓰는 **한 자리** (2026-10-05 · 원장 W2-17).

    ■ 왜 — 윈도우에서 `_review_receipt_io_path`·`longform_state.native_path` 는 긴 경로를 위해 `\\\\?\\` 를 붙인다.
      그 경로에 `Path(...).resolve().as_uri()` 를 쓰면 `file://%3F/E%3A/…` 가 되고(접두의 `?` 가 호스트 자리로 간다)
      `urlopen` 이 WinError 123 으로 죽었다(10-04 6건·5명 · 검수 그림 URL). 접두를 벗긴 뒤 URI 로 바꾼다 —
      resolve 가 다시 붙이면 한 번 더 벗긴다. 맥·리눅스는 예전과 같은 글자다(`Path(p).resolve().as_uri()`).
    ★긴 경로(260자 넘음)의 파일을 읽는 쪽은 URI 를 거치지 말고 `_file_uri_path` 로 되돌려 `_review_receipt_io_path` 로 연다.
    """
    text = os.fspath(path)
    if os.name != 'nt':
        return Path(text).resolve().as_uri()
    text = _strip_extended_prefix(os.path.abspath(_strip_extended_prefix(text)))
    resolved = _strip_extended_prefix(os.path.realpath(text))
    return Path(resolved).as_uri()


def _file_uri_path(url):
    """`file://` URI → 로컬 경로(윈도우는 긴 경로 접두 포함) · file 이 아니면 None."""
    parts = urllib.parse.urlsplit(str(url))
    if parts.scheme.lower() != 'file':
        return None
    local = urllib.request.url2pathname(parts.path)
    if parts.netloc and parts.netloc.lower() != 'localhost':
        local = '\\\\' + parts.netloc + local if os.name == 'nt' else '//' + parts.netloc + local
    return _review_receipt_io_path(local)


def _review_receipt_save(path, record, *, archive_path=None):
    """Mirror first so interruption between writes retains the newest outcome.

    Call under the fixed output lock, after _review_receipt_load has preserved
    any legacy mirror under its own SHA before changing the question.
    """
    key = record['request_sha256']
    archive = archive_path(key) if archive_path else str(path) + '.' + key + '.json'
    _photo_write_state(_review_receipt_io_path(path), record)
    _photo_write_state(_review_receipt_io_path(archive), record)


def _review_receipt_load(path, keys, *, archive_path=None):
    """Preserve every question and restore the selected record to the fixed path."""
    def read(candidate, expected_key=None):
        try:
            record = json.loads(Path(_review_receipt_io_path(candidate)).read_text(encoding='utf8'))
            key = record.get('request_sha256') if isinstance(record,dict) else None
            if (not isinstance(key,str) or not re.fullmatch(r'[0-9a-f]{64}',key)
                    or (expected_key is not None and key != expected_key)):
                raise ValueError('Invalid review receipt identity')
            return record
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as cause:
            error = StepError('저장된 검수 영수증을 읽거나 확인할 수 없습니다. 기록을 보존하며 같은 모델 요청을 다시 보내지 않습니다.')
            error.code = 'review_receipt_unreadable'
            raise error from cause
    def archive(key):
        return archive_path(key) if archive_path else str(path) + '.' + key + '.json'
    legacy = read(path)
    legacy_key = legacy.get('request_sha256')
    if isinstance(legacy_key, str) and re.fullmatch(r'[0-9a-f]{64}', legacy_key):
        # A legacy process may have written a newer state only to this mirror.
        # Preserve its OWN identity even when the next request is different.
        _photo_write_state(_review_receipt_io_path(archive(legacy_key)), legacy)
    for key in keys:
        saved = read(archive(key), expected_key=key)
        if saved.get('request_sha256') == key:
            if saved != legacy:
                _photo_write_state(_review_receipt_io_path(path), saved)
            return saved
    return {}


def _paid_review_json(item, body, headers, *, validator, parse, request=None, preflight=None,
                      local_failure=None):
    """Reuse existing receipt/attempt primitives for text and contact-sheet reviews."""
    context = current_review_context()
    policy = resolve_review_policy(item.get('review_policy'))
    if policy['provider'] != 'evolink':
        raise StepError('유료 검수 제공자를 명시해야 합니다.')
    key, output = _review_json_path(item,{'body':body,'endpoint':item['endpoint'],
        'pluck':item.get('pluck'),'parse':item.get('parse'),'contract':item.get('qc_contract')})
    legacy_receipt = _review_receipt_io_path(output + '.paid-review.json')
    archive_path = lambda sha: output + '.' + sha + '.paid-review.json'
    # Keep every semantic variant. The legacy path remains the common lock and
    # latest-state mirror so an older process already waiting on it sees the
    # same in-flight/completed request. Never replace a keyed terminal record.
    def save(record):
        _review_receipt_save(legacy_receipt, record, archive_path=archive_path)
    with review_receipt_lock(legacy_receipt):
        saved = _review_receipt_load(legacy_receipt, [key], archive_path=archive_path)
        if saved.get('request_sha256') == key:
            if saved.get('outcome') == 'refused':
                raise remember_review_refusal(ProviderRefusalError(saved['origin'],saved['reason_code'],saved['reason']))
            if saved.get('outcome') == 'complete' and validator(saved.get('answer')):
                return saved['answer']
            if preflight is not None and local_failure is not None and local_failure(saved):
                # Diagnose a specific historical local-only failure without
                # rewriting its terminal receipt. Only a still-failing local
                # preflight can lead to a separately identified fitting proxy.
                preflight()
            blocked = saved.get('review_budget_blocked') or {}
            if not (saved.get('outcome') == 'budget_blocked' and
                    type(blocked.get('attempts_reserved')) is int and blocked['attempts_reserved'] == 0):
                error = StepError(saved.get('reason') or '앞선 검수의 완료 여부를 확인할 수 없습니다. 같은 유료 요청은 자동 반복하지 않습니다.')
                error.code = saved.get('code') or 'review_unknown_completion'
                raise error
        # Local validation precedes the durable purchase marker. A completed or
        # uncertain historical request above always wins over changed limits.
        if preflight is not None:
            preflight()
        resolved = headers() if callable(headers) else headers
        if not resolved:
            error = StepError('선택한 유료 검수의 인증 정보가 없습니다.')
            error.code = 'review_key_missing'
            raise error
        attempts = item.get('_review_attempts')
        if attempts is None:
            attempts = {'reserved':0}
        save({'request_sha256':key,'outcome':'started'})
        try:
            if request is None:
                raw = post_json(item['endpoint'],body,resolved,timeout=int(item.get('timeout') or 900),
                    before_request=lambda:review_request_attempt(policy,context.get('budget') if context else item.get('_review_budget'),key,attempts=attempts))
            else:
                raw = request(resolved, policy, attempts)
            _raise_provider_refusal(raw)
            answer = parse(raw)
            _raise_provider_refusal(answer)
            if not validator(answer):
                error = StepError('검수 답의 JSON 형식 또는 판정 번호가 잘못되었습니다.')
                error.code = 'review_contract_invalid'
                raise error
        except Exception as exc:
            record = {'request_sha256':key,'outcome':'failed','code':getattr(exc,'code','review_unknown_completion'),
                      'reason':str(exc)[:1200]}
            if getattr(exc,'review_budget_blocked',None):
                record.update(outcome='budget_blocked',review_budget_blocked=exc.review_budget_blocked)
            if isinstance(exc,ProviderRefusalError):
                record.update(outcome='refused',origin=exc.origin,reason_code=exc.reason_code,reason=exc.reason,
                              request_sent=getattr(exc,'request_sent',True))
            save(record)
            raise
        save({'request_sha256':key,'outcome':'complete','answer':answer})
        return answer


def fact_check(item, headers=None):
    """Compare the actual contact sheet with its supplied numbered descriptions."""
    import base64
    policy = resolve_review_policy(item.get('review_policy'))
    image = item.get('image')
    if not image or not os.path.isfile(image):
        raise StepError(f'대조표가 없다 — {image}')
    def valid(answer):
        return (isinstance(answer,dict) and isinstance(answer.get('items'),list)
            and all(isinstance(row,dict) and type(row.get('cut')) is int
                and 1 <= row['cut'] <= int(item.get('card_count') or 0)
                and isinstance(row.get('why'),str) and bool(row['why'].strip()) for row in answer['items']))
    key, output = _review_json_path(item,{'prompt':item['prompt'],'image_sha256':_image_file_sha(image),
                                        'card_count':item.get('card_count')})
    if policy['provider'] == 'client':
        return client_review({'out':output,'prompt':item['prompt'],'qc_contract':'fact_check_v1',
            'images':[{'path':image,'mime':'image/png','label':'numbered contact sheet'}],
            'binding':{'request_sha256':key,'card_count':item.get('card_count')}},
            validator=valid,client=resolve_review_client(item.get('review_client') or item.get('client'),legacy=item.get('claude')))
    with open(image,'rb') as source: encoded = base64.b64encode(source.read()).decode()
    body = _vision_body(item,[(encoded,'image/png')])
    return _paid_review_json(dict(item,qc_contract='fact_check_v1'),body,headers,validator=valid,
                            parse=lambda raw:_json_object(_vision_text(raw,item.get('pluck'))))


def ask_text(item, headers=None):
    """**글만** 보내고 모델 답을 받는다 — 첨부 없음. `ask_video` 의 형제.

    ■ 왜 따로 있나 (2026-08-23)
        `ask_video` 는 **소재 영상이 반드시 있어야** 한다(`path` 없으면 죽는다).
        그런데 인물형은 대본이 **글(원문)에서** 나온다 — 소재는 대본 뒤에 모은다.
        그래서 영상 첨부를 요구하는 갈래로는 도울 수가 없었고,
        인물형만 **대본 초안이 없는 채널**로 남아 있었다
        (실측: `person_script` 사람당 13회 · 실패율 23.7%).

    ★서버가 준 `body` 를 **한 글자도 고치지 않고** 던진다 — 무엇을 묻는지·어느 모델인지·
      어디로 보내는지는 전부 서버가 정한다(§"실행기에 기본값을 두지 않는다").
    ★`pluck` 도 서버가 준다. 답에서 무엇을 꺼낼지 실행기가 정하면 자가 갈린다.
    """
    context = current_review_context()
    routed = _REVIEW_CONTEXT.get() is not None or item.get('claude') or item.get('review_client') is not None or item.get('client') is not None
    policy = resolve_review_policy(item.get('review_policy'))
    keys = tuple(item.get('claude_keys') or item.get('want_keys') or ())
    def valid(answer): return isinstance(answer,dict) and all(k in answer for k in keys)
    if routed and policy['provider'] == 'client':
        messages = []
        for message in (item.get('body') or {}).get('messages',[]):
            content = message.get('content') or ''
            text = content if isinstance(content,str) else '\n'.join(c.get('text','') for c in content if isinstance(c,dict) and c.get('type') == 'text')
            messages.append('['+str(message.get('role') or 'user')+']\n'+text)
        question = '\n'.join(messages)
        key, output = _review_json_path(item,{'body':item.get('body'),'keys':keys})
        client = resolve_review_client(item.get('review_client') or item.get('client'),legacy=item.get('claude'))
        result = client_review({'out':output,'prompt':question,'qc_contract':'client_draft_v1',
            'binding':{'request_sha256':key}},validator=valid,client=client)
        return dict(result,_engine=client['provider'])
    if routed:
        def parse(raw):
            if str(item.get('parse') or '') == 'json':
                return _json_object(_vision_text(raw,item.get('pluck')))
            return _qc_parse(raw,item.get('pluck'))
        return _paid_review_json(item,item['body'],headers,validator=valid,parse=parse)
    hdr = dict((headers() if callable(headers) else headers) or {})
    if not hdr:
        # ★**선택**이다. 키가 없으면 빈 묶음을 돌려주고 파이프라인은 그대로 간다 —
        #   초안은 «있으면 좋은 것» 이지 없으면 못 만드는 것이 아니다(`fact_check` 와 같다).
        #   ★`None` 이 아니라 **빈 묶음**인 이유: 서버의 타입 규격이 `draft: 묶음` 이고,
        #     서버는 «값» 이 아니라 **«키가 있느냐»** 로 다시 물을지 정한다.
        #     `None` 을 주면 그 키가 사라져 같은 단계를 **영원히 되묻는다**.
        return {}
    body = json.loads(json.dumps(item["body"]))
    raw = post_json(item["endpoint"], body, hdr,
                    timeout=int(item.get("timeout") or 900))
    _raise_provider_refusal(raw)
    # ★서버가 `parse:"json"` 을 선언하면 답 JSON 을 **그대로** 돌려준다 (2026-08-25).
    #   `_qc_parse` 는 검수 칸(verdict·selected…)만 남기는 자라, 임의 모양의 답
    #   (예: 인물·장소 묶음 읽기)이 통째로 사라진다. 어떤 모양을 기대하는지는
    #   서버가 안다 — 실행기는 선언대로 꺼낼 뿐이다. 선언 없으면 옛 동작 그대로
    #   (옛 서버와 혼재 무해).
    if str(item.get("parse") or "") == "json":
        txt = _vision_text(raw, item.get("pluck")) if item.get("pluck") else ""
        obj = _json_object(txt)
        # ★못 읽으면 **빈 묶음** — 「값이 아니라 키가 있느냐」로 서버가 판정한다
        #   (키가 사라지면 같은 것을 영원히 되묻는다 — 위 키 없음 갈래와 같은 이유).
        return obj if isinstance(obj, dict) else {}
    return _qc_parse(raw, item.get("pluck"))


def video_proxy_valid(item, receipt):
    """Reuse only bytes produced for this exact source and encoder command."""
    try:
        return (isinstance(receipt, dict) and receipt.get('version') == 1
                and receipt['path'] == item['out'] and os.path.getsize(receipt['path']) > 0
                and receipt['source_sha256'] == _image_file_sha(item['path'])
                and receipt['argv_sha256'] == hashlib.sha256(json.dumps(item['shrink_argv']).encode()).hexdigest()
                and receipt['sha256'] == _image_file_sha(receipt['path']))
    except (OSError, KeyError, TypeError):
        return False


def prepare_video_proxy(item):
    source_hash = _image_file_sha(item['path'])
    run_argv(item['shrink_argv'])
    if not os.path.isfile(item['out']) or not os.path.getsize(item['out']):
        raise StepError('줄인 영상이 없거나 비었습니다. API를 호출하지 않았습니다.')
    receipt = {'version':1, 'path':item['out'], 'source_sha256':source_hash,
               'argv_sha256':hashlib.sha256(json.dumps(item['shrink_argv']).encode()).hexdigest(),
               'sha256':_image_file_sha(item['out'])}
    if not video_proxy_valid(item, receipt):
        raise StepError('영상 검토 proxy를 만드는 동안 원본 또는 결과가 바뀌었습니다.')
    return receipt


def _video_request_body(item, small, encode=True):
    """One serialization for byte budgeting and the actual submitted request."""
    import base64
    native = item.get('body_kind') == 'gemini_video'
    body = copy.deepcopy(item['body'])
    attachments = item.get('attachments') or []
    if not isinstance(attachments, list) or (attachments and not native):
        raise StepError('추가 후보 그림은 native 영상 첨부 규약에서만 보낼 수 있습니다.')
    media_size = encoded_size = 0
    def data(path):
        nonlocal media_size, encoded_size
        if not path or not os.path.isfile(path) or not os.path.getsize(path):
            raise StepError('미디어 파일이 없거나 비었습니다. API를 호출하지 않았습니다.')
        size = os.path.getsize(path)
        media_size += size; encoded_size += 4 * ((size + 2) // 3)
        if not encode: return ''
        with open(path, 'rb') as fh: return base64.b64encode(fh.read()).decode('ascii')
    video = data(small)
    if native:
        body['contents'][0]['parts'].append({'inline_data':{'mime_type':item.get('mime','video/mp4'),'data':video}})
    else:
        body['messages'][0]['content'].append({'type':'file','file':{'filename':os.path.basename(small),
            'file_data':f"data:{item.get('mime','video/mp4')};base64,{video}"}})
    for attachment in attachments:
        if not isinstance(attachment, dict) or attachment.get('mime') not in ('image/png','image/jpeg','image/webp'):
            raise StepError('후보 그림 첨부 규약이 잘못되었습니다.')
        body['contents'][0]['parts'].append({'inline_data':{'mime_type':attachment['mime'],'data':data(attachment.get('path'))}})
    request_size = len(json.dumps(body).encode('utf-8')) + (0 if encode else encoded_size)
    return body, media_size, request_size


def video_request_sizes(item, small):
    """Exact JSON/base64 bytes, including the declared output-budget retry."""
    body, media, size = _video_request_body(item, small, encode=False)
    if item.get('retry_max_tokens'):
        before = len(json.dumps(body).encode('utf-8'))
        if item.get('body_kind') == 'gemini_video':
            body['generationConfig']['maxOutputTokens'] = int(item['retry_max_tokens'])
        else:
            body['max_tokens'] = int(item['retry_max_tokens'])
        size += max(0, len(json.dumps(body).encode('utf-8')) - before)
    return media, size


def _video_size_preflight(item, small):
    media, size = video_request_sizes(item, small)
    if item.get('max_media_bytes') and media > int(item['max_media_bytes']):
        error = StepError(f"영상과 후보 그림 {media}바이트가 첨부 상한 {item['max_media_bytes']}바이트를 넘습니다. "
                        'API를 호출하지 않았습니다. ' + str(item.get('size_recovery') or '분석 구간을 확인하세요.'))
        error.code = 'video_preflight_size'
        raise error
    if item.get('max_request_bytes') and size > int(item['max_request_bytes']):
        error = StepError(f"영상·대본 요청 크기 {size}바이트가 상한 {item['max_request_bytes']}바이트를 넘습니다. API를 호출하지 않았습니다.")
        error.code = 'video_preflight_size'
        raise error


def ask_video(item, headers=None):
    """Route all source/speaker analysis through the current review contract.

    Proxy/audio receipts preserve the actual media between CLI waits. A new
    transport or process never authorizes a second purchase of the same answer.
    """
    policy = resolve_review_policy(item.get('review_policy') or item.get('_review_policy'))
    config = dict(item)
    source = config.get('path')
    if not source or not os.path.isfile(source):
        raise StepError(f'소재 영상이 없다 — {source}')
    if config.get('body_kind') not in (None, '', 'openai_video', 'gemini_video'):
        raise StepError('서버의 영상 첨부 규약을 모릅니다 — 실행기를 갱신하세요.')
    if not config.get('shrink_argv'):
        raise StepError('서버가 shrink_argv 를 주지 않았다 — 실행기가 인코딩을 짓지 않는다')
    config['out'] = config.get('out') or os.path.splitext(source)[0] + '.ask.mp4'
    proxy_record = config['out'] + '.analysis-proxy.json'
    with review_receipt_lock(proxy_record):
        try: proxy = json.loads(Path(proxy_record).read_text(encoding='utf8'))
        except (OSError, ValueError): proxy = {}
        if config.get('prepared_proxy') is not None:
            proxy = config['prepared_proxy']
            if not video_proxy_valid(config, proxy):
                raise StepError('준비된 영상 proxy가 현재 원본·인코딩 명령·SHA와 다릅니다.')
        elif not video_proxy_valid(config, proxy):
            proxy = prepare_video_proxy(config)
        _photo_write_state(proxy_record, proxy)
    config['prepared_proxy'] = proxy
    expected = tuple(config.get('expect') or ())
    def valid(answer):
        return (isinstance(answer, dict) and bool(answer) and not answer.get('error')
                and all(answer.get(key) for key in expected))
    binding = dict(source_sha256=proxy['source_sha256'], proxy_sha256=proxy['sha256'],
                   body=_video_budget_identity_body(config, config.get('body')),
                   expect=expected, contract='video_analysis_v1')
    directory = str(Path(config['out']).parent/'video-analysis')
    key, output = _review_json_path({'out_dir':directory}, binding)
    if policy['provider'] == 'client':
        body = config.get('body') or {}
        messages = body.get('contents') if config.get('body_kind') == 'gemini_video' else body.get('messages')
        prompts = []
        for message in messages or []:
            parts = message.get('parts') if config.get('body_kind') == 'gemini_video' else message.get('content')
            text = parts if isinstance(parts, str) else '\n'.join(
                part.get('text', '') for part in parts or [] if isinstance(part, dict))
            prompts.append('[' + str(message.get('role') or 'user') + ']\n' + text)
        audio_record = output + '.audio.json'
        try: audio = json.loads(Path(audio_record).read_text(encoding='utf8'))
        except (OSError, ValueError): audio = {}
        if (audio.get('proxy_sha256') != proxy['sha256'] or
                (audio.get('audio') and (not os.path.isfile(audio['audio']) or
                 _image_file_sha(audio['audio']) != audio.get('audio_sha256')))):
            audio_directory = str(Path(output).parent/key)
            os.makedirs(audio_directory, exist_ok=True)
            audio = dict(client_video_audio(config, audio_directory), proxy_sha256=proxy['sha256'])
            if audio.get('audio'): audio['audio_sha256'] = _image_file_sha(audio['audio'])
            _photo_write_state(audio_record, audio)
        job = dict(out=output, prompt='\n'.join(prompts), qc_contract='video_analysis_v1',
            binding={'request_sha256':key, 'expect':expected}, video=config['out'],
            images=[dict(attachment) for attachment in config.get('attachments') or []],
            **{field:audio[field] for field in ('audio', 'audio_status') if field in audio})
        answer = client_review(job, validator=valid,
            replies=current_review_context().get('replies') or config.get('review_replies'),
            client=resolve_review_client(config.get('review_client') or config.get('client')))
    else:
        prepared_request = _video_request_body(config, config['out'])
        body = prepared_request[0]
        paid = dict(config, out=output, qc_contract='video_analysis_v1', review_policy=policy)
        body_binding = {'request':_video_budget_identity_body(config, body),
                        'expect':expected, 'source_sha256':proxy['source_sha256']}
        def request(resolved, selected_policy, attempts):
            return _ask_video_paid(dict(config, _review_policy=selected_policy,
                _review_budget=current_review_context().get('budget') or config.get('_review_budget'),
                _review_attempts=attempts), resolved, prepared_request=prepared_request)
        # Adapt only a new, proven never-sent request. Historical complete or
        # uncertain receipts are resolved inside _paid_review_json first.
        preflight_failed = False
        def preflight():
            nonlocal preflight_failed
            try:
                _video_size_preflight(config, config['out'])
            except StepError as exc:
                preflight_failed = getattr(exc, 'code', '') == 'video_preflight_size'
                raise
        def legacy_local_size(saved):
            if saved.get('outcome') != 'failed' or saved.get('code') != 'review_unknown_completion':
                return False
            # This exact old diagnostic was raised before the HTTP loop. Do
            # not infer non-submission from generic timeout/failure prose.
            match = re.match(r'서버 명령으로 압축한 뒤 영상 크기가 (\d+)바이트여서 '
                r'첨부 상한 (\d+)바이트를 넘습니다\. CRF 압축은 길이/장면에 따라 '
                r'파일 크기가 달라집니다\. API를 호출하지 않았습니다\.', str(saved.get('reason') or ''))
            return bool(match and int(match[1]) == os.path.getsize(config['out'])
                        and int(match[2]) == config.get('max_media_bytes')
                        and config.get('size_fit'))
        try:
            answer = _paid_review_json(paid, body_binding, headers, validator=valid,
                                      parse=lambda raw:raw, request=request, preflight=preflight,
                                      local_failure=legacy_local_size)
        except StepError:
            if not preflight_failed or not config.get('size_fit'):
                raise
            from video_proxy_fit import fit_proxy
            fitted = fit_proxy(config, runner=sys.modules[__name__])
            return ask_video(fitted, headers)
    if not video_proxy_valid(config, proxy):
        raise StepError('분석 중 원본 또는 영상 proxy가 바뀌었습니다. 이전 답을 적용하지 않습니다.')
    return answer


@review_dispatch()
def _ask_video_paid(item, headers=None, *, prepared_request=None):
    """서버가 선언한 영상 규약으로 보내고 완전한 답 객체를 받는다.

    2026-09-06 실물: 같은 영상/모델에서 OpenAI file 첨부는 400,
    기존 vision.py의 native inline_data는 영상·소리 모두 읽었다.
    주소·본문·읽을 자리·크기·출력 재시도 예산은 서버가 준다.
    body_kind 없는 옛 저장 job은 기존 규약 그대로 읽는다.
    """
    hdr = http_headers(headers)
    if not hdr:
        raise StepError("모델 키가 없다 — 서버가 알려준 자리에 키를 넣어라")
    native = item.get("body_kind") == "gemini_video"
    if item.get("body_kind") not in (None, "", "openai_video", "gemini_video"):
        raise StepError("서버의 영상 첨부 규약을 모릅니다 — 실행기를 갱신하세요.")
    src = item.get("path")
    if not src or not os.path.exists(src):
        raise StepError(f"소재 영상이 없다 — {src}")
    small = item.get("out") or (os.path.splitext(src)[0] + ".ask.mp4")
    argv = list(item.get("shrink_argv") or [])
    if not argv:
        raise StepError("서버가 shrink_argv 를 주지 않았다 — 실행기가 인코딩을 짓지 않는다")
    if item.get('prepared_proxy') is not None:
        if not video_proxy_valid(item, item['prepared_proxy']):
            raise StepError('준비된 영상 proxy가 현재 원본·인코딩 명령·SHA와 다릅니다. API를 호출하지 않았습니다.')
    else:
        run_argv(argv)
    if not os.path.exists(small):
        raise StepError(f"줄인 영상이 안 생겼다 — {small}")
    size = os.path.getsize(small)
    if not size:
        raise StepError("줄인 영상이 비었습니다 — 인코딩 결과를 확인하세요.")
    media_max = item.get("max_media_bytes")
    if media_max and size > int(media_max):
        raise StepError(f"서버 명령으로 압축한 뒤 영상 크기가 {size}바이트여서 "
                        f"첨부 상한 {media_max}바이트를 넘습니다. CRF 압축은 길이/장면에 따라 "
                        "파일 크기가 달라집니다. API를 호출하지 않았습니다. "
                        + str(item.get("size_recovery") or "원본을 보존하고 분석할 구간을 나누어 다시 요청하세요."))
    _progress(f"  [모델] 영상 {size / 1024 / 1024:.2f}MB 를 통째로 보냅니다 …")
    if prepared_request is None:
        _, media_size, request_size = _video_request_body(item, small, encode=False)
        body = None
    else:
        # These are the exact bytes whose semantic identity was recorded. Do
        # not reopen candidate attachments between receipt identity and send.
        import copy
        body, media_size, request_size = prepared_request
        body = copy.deepcopy(body)
    if media_max and media_size > int(media_max):
        raise StepError('영상과 후보 그림의 합계 크기가 첨부 상한을 넘습니다. API를 호출하지 않았습니다.')
    if item.get('max_request_bytes') and request_size > int(item['max_request_bytes']):
        raise StepError(f"영상·대본 요청 크기 {request_size}바이트가 상한 {item['max_request_bytes']}바이트를 넘습니다. API를 호출하지 않았습니다.")
    if body is None:
        body, _, _ = _video_request_body(item, small)
    hdr = {**hdr, "Content-Type": "application/json", "User-Agent": _UA}
    # 무한 재요청 대신 서버가 허용한 출력 확장 한 번만 쓴다. 옛 job은 재시도 없음.
    retry_max = int(item.get("retry_max_tokens") or 0)
    for attempt in range(2 if retry_max else 1):
        data = json.dumps(body).encode("utf-8")
        limit = item.get("max_request_bytes")
        if limit and len(data) > int(limit):
            raise StepError(f"영상·대본 요청 크기 {len(data)}바이트가 상한 {limit}바이트를 넘습니다. "
                            "분석할 구간을 나누거나 해상도를 줄여 다시 요청하세요.")
        req = urllib.request.Request(item["endpoint"], data=data, headers=hdr)
        observation = dict(request_sha256=hashlib.sha256(data).hexdigest(),
            service=item.get('service') or urllib.parse.urlsplit(item['endpoint']).hostname,
            model=body.get('model'))
        # A timeout/5xx does not prove the paid provider did not accept the POST.
        def before_video_request():
            if '_review_policy' in item:
                review_request_attempt(item['_review_policy'],item.get('_review_budget'),
                    hashlib.sha256(data).hexdigest(),attempts=item.get('_review_attempts'))
            check_review_running()
        check_review_running()
        stream = _open_retry(req, int(item.get("timeout") or 900), "모델", observation=observation,
                            retry_safe=False,before_request=before_video_request)
        out, json_received = None, False
        observation_outcome = 'read_error'
        try:
            out = json.load(stream)
            json_received = True
            observation_outcome = 'response_received'
        except ValueError as e:
            observation_outcome = 'json_error'
            raise StepError("모델 API가 JSON 응답을 끝까지 보내지 못했습니다 — "
                            f"{type(e).__name__}. 같은 요청을 자동 반복하지 않습니다.") from e
        finally:
            # Capture before metadata extraction, durable storage, export or close.
            started_ns = observation.get('started_ns')
            seconds = max(0, time.perf_counter_ns()-started_ns) / 1_000_000_000 if started_ns is not None else None
            from runtime_metrics import provider_response
            provider_response('video_review', observation['request_sha256'], stream, out,
                              service=observation['service'], model=observation['model'],
                              json_received=json_received, seconds=seconds, outcome=observation_outcome)
            close = getattr(stream, "close", None)
            if close:
                close()
        if not isinstance(out, dict):
            raise StepError("모델 API 응답이 객체가 아닙니다 — 서비스 응답 규약을 확인하세요.")
        _raise_provider_refusal(out)
        candidates = out.get("candidates" if native else "choices")
        if candidates and (not isinstance(candidates, list) or not isinstance(candidates[0], dict)):
            raise StepError("모델 API 응답의 후보 목록 모양이 잘못되었습니다 — 완성 대본으로 쓰지 않습니다.")
        cand = candidates[0] if candidates else {}
        if native:
            finish = str(cand.get("finishReason") or "")
            txt = _vision_text(out, item.get("pluck"))
            blocked = (out.get("promptFeedback") or {}).get("blockReason")
            if blocked or finish not in ("", "STOP", "MAX_TOKENS"):
                raise StepError(f"모델이 답을 완료하지 않았습니다 — finish_reason={finish}, "
                                f"blockReason={blocked}. 이 응답을 완성 대본으로 쓰지 않습니다.")
            usage = out.get("usageMetadata") or {}
            tokens, thoughts = usage.get("candidatesTokenCount"), usage.get("thoughtsTokenCount")
            message_keys = sorted((cand.get("content") or {}))
        else:
            finish = str(cand.get("finish_reason") or "")
            txt = _vision_text(out, item.get("pluck") or "choices[0].message.content")
            if not txt.strip():
                for alt in ("choices[0].message.reasoning_content", "choices[0].message.reasoning", "choices[0].text"):
                    txt = _vision_text(out, alt)
                    if txt.strip():
                        break
            if finish not in ("", "stop", "length"):
                raise StepError(f"모델이 답을 완료하지 않았습니다 — finish_reason={finish}.")
            usage = out.get("usage") or {}
            tokens = usage.get("completion_tokens")
            thoughts = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            message_keys = sorted(cand.get("message") or {})
        if txt.strip()[:20].startswith("영상없음"):
            raise StepError("모델이 영상을 못 받았다 — 첨부 형식이 어긋났다(서버에 보고됨)")
        obj = _json_object(txt)
        truncated = finish in ("MAX_TOKENS", "length")
        if obj and not truncated:
            if obj.get("error"):
                raise StepError("모델이 대본 대신 오류 객체를 보냈습니다 — "
                                + _request_error_text(obj["error"], req)
                                + ". 이 응답을 완성 대본으로 쓰지 않습니다.")
            missing = [k for k in (item.get("expect") or []) if not obj.get(k)]
            if missing:
                raise StepError(f"모델 답에 {missing} 가 빠졌다 — 완성 대본으로 쓰지 않습니다. "
                                "해당 항목을 확인한 뒤 다시 요청하세요.")
            return obj
        if attempt == 0 and retry_max and truncated:
            if native:
                body["generationConfig"]["maxOutputTokens"] = retry_max
            else:
                body["max_tokens"] = retry_max
            _progress("  [모델] 출력 예산에서 답이 잘렸습니다 — 서버가 정한 확장 예산으로 한 번 다시 받습니다.", flush=True)
            continue
        raise StepError("모델 답의 JSON 객체가 완성되지 않았습니다 — "
                        f"finish_reason={finish!r} · message 키={message_keys} · "
                        f"출력토큰={tokens} (추론 {thoughts}) · 답 {len(txt)}자. "
                        "잘린 대본을 채워 넣거나 성공으로 넘기지 않습니다. "
                        "소재 구간 또는 요청 대본 분량을 줄여 다시 요청하세요.")


def hardsub_probe(item):
    """원본에 **박힌 자막 띠**(하드섭)가 있는가 — 판단은 서버가 한다. 여기는 «어디에 얼마나» 만 잰다.

    ■ 왜 (2026-09-02, 명화관·린박스 제보) — 외국 소재의 박힌 자막이 우리 대사 자막과 같은 높이에 겹쳐
      둘 다 못 읽는데, 아무도 재지 않아 다 굽고 나서야 봤다. 재면 서버가 «띠가 있다 · 길은 둘» 이라 말한다.
    ■ 자 — 전부 일반 기술이다(PIL+numpy). 임계·표본 수는 **서버가 item 으로 준다**(여기 기본값은 폴백).
        · 자막 획 = 밝은 화소(≥bright)인데 반경 radius 안에 어두운 화소(≤dark)가 있는 것(외곽선 자막의 지문)
        · 행 프로필(획 비율 ≥row_frac)이 gap 안에서 이어진 띠, 높이 ≥min_h · 질량 ≥min_mass · 가로 퍼짐 ≥min_span ·
          **획 시작 밀도 ≥min_runs**(글자는 잘게 끊긴다 — 그래픽 덩어리를 거른다)
        · 레터박스 알맹이(`content`) = 자막 획을 지운 뒤 «어두운 화소 비율 ≥bar_frac» 인 가장자리 행·열. max 로 재면
          검은 띠 안에 구운 자막 한 줄에 무너진다(실측). 어두운 프레임(평균<dark_frame)은 빼고 **중앙값**.
    ■ 돌려주는 것 (원본 px)
        frames·with_text·share · size [W,H] · band [y0,y1]|None · band_pct · content [x,y,w,h]|None · runs
    item = {src, n, band_pct, probe_argv, frame_argv(@@T@@·@@OUT@@), suffix, 임계들}
    """
    import tempfile                                                # noqa: PLC0415
    import numpy as np
    from PIL import Image
    src = item["src"]
    p = _spawn(item["probe_argv"], capture_output=True, text=True)
    try:
        js = json.loads(p.stdout or "{}")
        st = (js.get("streams") or [{}])[0]
        W, H = int(st.get("width") or 0), int(st.get("height") or 0)
        dur = float((js.get("format") or {}).get("duration") or st.get("duration") or 0)
    except (ValueError, TypeError, AttributeError):
        W = H = 0; dur = 0.0
    if not (W and H and dur > 0):
        return {"frames": 0, "with_text": 0, "share": 0.0, "size": [W, H], "band": None, "content": None,
                "note": "ffprobe 로 크기·길이를 못 읽었다"}
    n = int(item.get("n") or 24)
    band_pct = float(item.get("band_pct") or 0.35)
    bright, dark = int(item.get("bright") or 200), int(item.get("dark") or 80)
    r = int(item.get("radius") or 2)
    row_frac, gap = float(item.get("row_frac") or 0.006), int(item.get("gap") or 3)
    min_h, min_mass, min_span = int(item.get("min_h") or 8), int(item.get("min_mass") or 120), float(item.get("min_span") or 0.15)
    bar_lum, dark_frame = int(item.get("bar_lum") or 32), int(item.get("dark_frame") or 24)
    bar_frac, min_runs = float(item.get("bar_frac") or 0.90), float(item.get("min_runs") or 0.008)
    times = [dur * (0.05 + 0.90 * i / max(1, n - 1)) for i in range(n)]
    found, boxes, frames, scale, size_s = [], [], 0, 1.0, None
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            out = os.path.join(td, f"hs{i:03d}{item.get('suffix') or '.png'}")
            argv = [a.replace("@@T@@", f"{t:.3f}").replace("@@OUT@@", out) for a in item["frame_argv"]]
            rr = _spawn(argv, capture_output=True)
            if rr.returncode != 0 or not os.path.exists(out):
                continue
            L = np.asarray(Image.open(out).convert("L")).astype(np.int16)
            h, w = L.shape
            frames += 1; size_s = [w, h]; scale = W / float(w)
            # ── 레터박스(검은 띠) — 소재의 성질이라 프레임마다 재고 중앙값을 쓴다 ──
            _bars_pending = float(L.mean()) > dark_frame
            # ── 자막 획: 밝은 화소인데 반경 r 안에 어두운 화소 — 아래 band_pct 만 본다 ──
            y_from = int(h * (1 - band_pct))
            R = L[y_from:]
            darkm = R <= dark
            near = np.zeros_like(darkm)
            hh, ww = darkm.shape
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dy == 0 and dx == 0:
                        continue
                    ys, ye = max(0, dy), hh + min(0, dy)
                    xs, xe = max(0, dx), ww + min(0, dx)
                    near[ys:ye, xs:xe] |= darkm[ys - dy:ye - dy, xs - dx:xe - dx]
            mask = (R >= bright) & near
            if _bars_pending:
                # 레터박스 — 자막 획을 지운 뒤 «어두운 화소 비율» 로 잰다(max 는 자막 한 줄에 무너진다)
                L2 = L.copy(); L2[y_from:][mask] = 0
                drow = (L2 < bar_lum).mean(axis=1); dcol = (L2 < bar_lum).mean(axis=0)
                top = 0
                while top < h and drow[top] >= bar_frac: top += 1
                bot = h
                while bot > top and drow[bot - 1] >= bar_frac: bot -= 1
                left = 0
                while left < w and dcol[left] >= bar_frac: left += 1
                right = w
                while right > left and dcol[right - 1] >= bar_frac: right -= 1
                boxes.append((left, top, right - left, bot - top))
            runs = (mask[:, 1:] & ~mask[:, :-1]).sum(axis=1)      # 행마다 «밝은 획 시작» 수 — 글자는 잘게 끊긴다
            rows = mask.sum(axis=1) / float(ww)
            on = rows >= row_frac
            best = None
            y = 0
            while y < hh:
                if not on[y]:
                    y += 1; continue
                y0 = y; last = y
                while y < hh and (on[y] or (y - last) <= gap):
                    if on[y]: last = y
                    y += 1
                y1 = last + 1
                if y1 - y0 >= min_h:
                    sub = mask[y0:y1]
                    mass = int(sub.sum())
                    cols = np.where(sub.any(axis=0))[0]
                    span = (cols[-1] - cols[0] + 1) / float(ww) if len(cols) else 0.0
                    rd = float(runs[y0:y1].mean()) / float(ww)
                    if mass >= min_mass and span >= min_span and rd >= min_runs and (best is None or mass > best[2]):
                        best = (y0 + y_from, y1 + y_from, mass, span, round(rd, 4))
            if best:
                found.append(best)
    out = {"frames": frames, "with_text": len(found), "share": round(len(found) / frames, 3) if frames else 0.0,
           "size": [W, H], "band": None, "band_pct": None, "content": None}
    if boxes:
        bx = sorted(b[0] for b in boxes); by = sorted(b[1] for b in boxes)
        bw = sorted(b[2] for b in boxes); bh = sorted(b[3] for b in boxes)
        m = len(boxes) // 2
        c = [int(round(bx[m] * scale)), int(round(by[m] * scale)), int(round(bw[m] * scale)), int(round(bh[m] * scale))]
        out["content"] = [max(0, c[0]), max(0, c[1]), min(W - max(0, c[0]), c[2]), min(H - max(0, c[1]), c[3])]
    if found:
        y0s = sorted(b[0] for b in found); y1s = sorted(b[1] for b in found)
        m = len(found) // 2
        out["band"] = [int(round(y0s[m] * scale)), int(round(y1s[m] * scale))]
        out["runs"] = round(sorted(b[4] for b in found)[m], 4)
        out["band_pct"] = [round(out["band"][0] / H, 3), round(out["band"][1] / H, 3)]
    return out


def cut_signature(item):
    """구운 조각의 **화면 서명** — 컷이 튀는지 서버가 판정할 재료.

    ★소재 원본이 아니라 **구운 조각**에서 잰다. 크롭이 다르면 같은 소재라도 화면이
      달라지므로, 원본에서 재면 실제보다 비슷하게 나와 정상 컷을 반려한다
      (실측: 컷1~2 가 원본 0.89 · 완성본 0.83).
    ★**어느 순간을 뜰지도 서버가 준다**(`item["grabs"]` 의 argv 에 이미 박혀 있다).
      여기서 고르면 자가 갈려서 서버가 들고 있는 실물 수치를 못 쓴다.
    ★판정은 서버가 한다 — 여기는 **작은 회색 썸네일을 정규화해서** 돌려줄 뿐이다.
    """
    import numpy as np
    from PIL import Image
    grabs = item.get("grabs")
    if not isinstance(grabs, list) or not grabs:
        raise StepError(f"서버가 뜰 순간(grabs)을 주지 않았다 — {item.get('src')}")
    from collections import Counter
    repeated = {}
    for argv, count in Counter(tuple(g["argv"]) for g in grabs).items():
        inputs = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == "-i"]
        if count > 1 and inputs and all(os.path.isfile(p) for p in inputs):
            repeated[argv] = inputs
    # Photo a/b/m jobs declare the same command. Reuse only within this call,
    # preserving all tags and verifying the actual inputs before and after use.
    # Distinct video seeks never hash their inputs or share a measurement.
    out, measured = {}, {}
    with _ArgvInputDigests() as input_digests:
        for g in grabs:
            tag = str(g.get("tag") or "")
            key = tuple(g["argv"])
            inputs = repeated.get(key)
            if inputs:
                for path in inputs:
                    input_digests.digest(path)
                if key in measured:
                    out[tag] = list(measured[key])
                    continue
            png = os.path.join(item["tmp"], f"sig_{tag}.png")
            # A successful exit without a fresh frame must not accept a previous
            # cut's image when the sequential caller reuses its temporary folder.
            if os.path.exists(png):
                os.remove(png)
            argv = [a.replace("@@OUT@@", png) for a in g["argv"]]
            r = _spawn(argv, capture_output=True)
            if r.returncode != 0 or not os.path.exists(png):
                # ★실패 사유(종료 코드·ffmpeg 오류 끝)를 버리지 않는다 (2026-10-17 · 신고 #150).
                _why = " ".join(err_gist(r.stderr, 200).split()) or "오류 출력 없음"
                if item.get("allow_missing"):
                    # ★배치 전 샷 서명(쇼핑 shop_shots)은 서버가 «절반 이상 재면 쓴다» 로 판정한다(render.shot_scan_ok) —
                    #   한 순간을 못 뜬 샷은 이 태그 없이 돌려주고(접기·판정이 그 샷을 뺀다) 단계 전체를 죽이지 않는다.
                    _progress(f"  [샷 서명] {item.get('card')} ({tag}) 를 못 떴다 — 그 샷은 닮음 판정에서 빠진다 "
                              f"(rc={r.returncode} · {_why})")
                    continue
                raise StepError(f"컷 서명을 못 떴다 — {item.get('src')} ({tag}) · rc={r.returncode} · {_why}")
            with Image.open(png) as image:
                a = np.asarray(image.convert("L")).astype(float)
            # ★작은 엡실론을 더해 나누지 않는다 — 그런 상수의 자릿수가 명세 잎값과 우연히
            #   겹쳐 검사 [20](명세 유출)에 걸린다(주석에 적어도 걸린다 — 날짜와 같은 부류다).
            #   단색 프레임이면 편차가 0 이라 나눌 수 없으니 **그때만** 가른다.
            sd = float(a.std())
            a = (a - a.mean()) / (sd if sd > 0 else 1.0)
            out[tag] = [round(float(v), 3) for v in a.reshape(-1)]
            if inputs:
                input_digests.check(inputs)
                measured[key] = out[tag]
        input_digests.check()
    return out


def _dig(obj, path):
    """서버가 준 자리를 따라 값 하나를 꺼낸다. 없으면 None.

    ★어느 자리를 읽을지 **서버가 준다**(`pick`). 여기서 API 모양을 알면 그 규격이
      실행기에 남고(§2), API 가 바뀌면 팩을 다시 배급해야 한다.
    """
    if path is None:
        return None
    cur = obj
    for k in path:
        if isinstance(k, int):
            if not isinstance(cur, (list, tuple)) or len(cur) <= k:
                return None
            cur = cur[k]
        else:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
    return cur


_PHOTO_TEXT_FIELDS = ('title', 'caption', 'description', 'page_url')
_PHOTO_RIGHTS_FIELDS = ('license', 'license_version', 'license_url', 'author',
                       'author_url', 'attribution', 'attribution_required', 'copyrighted')


def _metadata_text(value, markup=True):
    """Only explicit text is evidence; API objects/lists are never captions."""
    if not isinstance(value, str):
        return ''
    import html
    return html.unescape(re.sub(r'<[^>]*>', '', value) if markup else value).strip()


def _normalize_photo_metadata(metadata):
    out = dict(metadata) if isinstance(metadata, dict) else {}
    for key in (*_PHOTO_TEXT_FIELDS, *_PHOTO_RIGHTS_FIELDS):
        if key in out:
            # Flags retain their original scalar value; they are not evidence prose.
            if key in ('attribution_required', 'copyrighted') and type(out[key]) is bool:
                continue
            out[key] = _metadata_text(out[key], markup=not key.endswith('_url'))
    return out


def _project_photo_metadata(row, pick, url, origin):
    out = dict(scope='image_record', image_url=url,
               **{key: _dig(row, pick.get(key)) for key in _PHOTO_TEXT_FIELDS})
    out.update({key: value for key in _PHOTO_RIGHTS_FIELDS
                if (value := _dig(row, pick.get(key))) is not None})
    out = _normalize_photo_metadata(out)
    if any(out.get(key) for key in _PHOTO_RIGHTS_FIELDS):
        out.update(metadata_origin=origin, rights_status='provider_metadata')
    return out


def _photo_metadata(photo):
    out = _normalize_photo_metadata(photo.get('source_metadata'))
    for key in _PHOTO_RIGHTS_FIELDS:
        if out.get(key):
            continue
        value = _metadata_text(photo.get(key), markup=not key.endswith('_url'))
        if value:
            out[key] = value
    return out


#: 엔진 판정 결과를 **한 번만** 잰다(없다는 답도 캐싱한다).
#: ★왜: 프로브가 안 뜨는 기계에서는 후보마다 타임아웃(30초)을 물어, 컷마다 재면
#:   28컷이면 수십 분이 그냥 날아간다. 실측: 컷 2개에 65.7초 → 캐싱 뒤 30초 한 번.
#: ★기계는 실행 중에 바뀌지 않는다. 그래서 한 번이면 된다.
_ENGINE_CACHE = {}


def _browser_engine(spec, workdir):
    """이 기계에 **렌더할 수 있는 브라우저가 있는지 재서** 경로를 돌려준다. 없으면 None.

    ■ 왜 재나 (2026-08-18)
        구글 이미지는 **맨몸 HTTP 로 안 된다** — 200 이 오는데 본문이 자바스크립트
        껍데기다(실측 3/3: 92KB 고정 · 이미지 0개). 그래서 진짜 엔진이 필요하다.
        그런데 엔진이 **못 뜨는 기계도 있다** — 이 저장소 검사 환경에서는
        `about:blank` 에서도 30초 타임아웃이 난다(구글도 플래그도 아니다).
    ★그래서 **있는지 묻지 않고 돌려 본다.** 파일이 있어도 못 뜨는 경우가 실재한다 —
      존재가 아니라 **결과**를 본다(§"있는 것과 도는 것은 다르다").
    ★못 뜨면 조용히 None 이다. 부르는 쪽이 공개 API 로 간다 — 지어내지 않는다.
    """
    if "engine" in _ENGINE_CACHE:
        return _ENGINE_CACHE["engine"]
    prof = os.path.join(workdir or ".", "_chrome_probe")
    os.makedirs(prof, exist_ok=True)
    pr = spec.get("probe") or {}
    for cand in (spec.get("chrome_candidates") or []):
        if not os.path.exists(cand):
            continue
        argv = [x.replace("{chrome}", cand).replace("{profile}", prof)
                for x in (pr.get("argv") or [])]
        if not argv:
            _ENGINE_CACHE["engine"] = None
            return None
        try:
            r = _spawn(argv, capture_output=True, text=True,
                               timeout=float(pr.get("timeout") or 30))
        except Exception:  # noqa: BLE001
            continue      # 이 후보는 못 뜬다 — 다음 것을 본다
        if str(pr.get("want") or "") in (r.stdout or ""):
            _ENGINE_CACHE["engine"] = cand
            return cand
    _ENGINE_CACHE["engine"] = None
    return None


def _google_images(spec, query, engine, workdir, want, min_h, used):
    """렌더한 DOM 에서 원본 주소를 뽑는다. **어디를 읽을지는 서버가 준다.**"""
    import re as _re
    import urllib.parse
    prof = os.path.join(workdir or ".", "_chrome_run")
    os.makedirs(prof, exist_ok=True)
    url = str(spec.get("url") or "").replace("{q}", urllib.parse.quote(str(query)))
    rd = spec.get("render") or {}
    argv = [x.replace("{chrome}", engine).replace("{profile}", prof).replace("{url}", url)
            for x in (rd.get("argv") or [])]
    try:
        r = _spawn(argv, capture_output=True, text=True,
                           timeout=float(rd.get("timeout") or 60))
    except Exception:  # noqa: BLE001
        return []
    dom = r.stdout or ""
    _google_extract(dom)  # retain exact imgres→source-page links for photo evidence
    pat = (spec.get("pick_html") or {}).get("orig") or ""
    out = []
    for m in _re.findall(pat, dom) if pat else []:
        u = urllib.parse.unquote(str(m))
        if u.startswith("http") and u not in used:
            out.append(u)
        if len(out) >= want * 4:      # 하한 미달·내려받기 실패를 감당할 여유
            break
    return out


def photo_signature(path):
    """Decoded-image signature, reusing qc_output.py's dHash; RGB guards collisions.

    Dimensions/encoding are intentionally absent. A hash match alone is insufficient
    for flat pictures or different photographs with similar outlines.
    """
    from PIL import Image, ImageOps
    import numpy as np
    with Image.open(path) as raw:
        im = ImageOps.exif_transpose(raw).convert('RGB')
        g = np.asarray(im.convert('L').resize((9, 8), Image.Resampling.LANCZOS),
                       dtype=np.int16)
        value = 0
        for bit in (g[:, 1:] > g[:, :-1]).flatten():
            value = (value << 1) | int(bit)
        rgb = np.asarray(im.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.uint8)
    return {'dhash': f'{value:016x}', 'rgb': rgb.flatten().tolist()}


def same_photo(a, b):
    """Conservative resize/re-encoding duplicate comparison; not semantic identity."""
    import numpy as np
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    try:
        if bin(int(a['dhash'], 16) ^ int(b['dhash'], 16)).count('1') > 8:
            return False
        left = np.asarray(a['rgb'], dtype=np.int16)
        right = np.asarray(b['rgb'], dtype=np.int16)
        if left.shape != (3072,) or right.shape != left.shape:
            return False
        delta = np.abs(left - right)
        return float(delta.mean()) <= 8.0 and float(np.percentile(delta, 95)) <= 24.0
    except (KeyError, ValueError, TypeError):
        return False


def _photo_source_key(url):
    """Keep the original image identity exposed by Daum's thumbnail URL."""
    from urllib.parse import urlparse, parse_qs
    value = str(url or '')
    parsed = urlparse(value)
    if (parsed.hostname or '').endswith('.daumcdn.net') and parsed.path.startswith('/thumb/'):
        original = (parse_qs(parsed.query).get('fname') or [''])[0]
        if urlparse(original).scheme in ('http', 'https'):
            return original
    return value


def _photo_read_state(path):
    try:
        with open(path, encoding='utf-8') as fh:
            value = json.load(fh)
        if (isinstance(value, dict) and value.get('version') == 1
                and isinstance(value.get('requests'), dict)):
            return value
    except (OSError, ValueError):
        pass
    return {'version': 1, 'requests': {}}


# ★작업 폴더 파일 쓰기 — 한 자리 (2026-10-22 뇌전구 신고: images 수리 그림 img43/07.png 를 shutil.copyfile 로 제자리
#   덮어쓰다 PermissionError 13 · 같은 날 사용자 소재 자리(prepare_custom_media)는 따로 안내를 달았지만 그 안내가 이 자리를 안 덮었다).
#   쓰는 자리마다 제각각이던 «제자리 덮어쓰기 · 교체 다시 시도 · 실패 문구» 를 여기 하나로 모은다:
#   같은 폴더 임시 사본 → fsync → 교체(윈도우 공유 위반 5·32·33 만 합 약 10초 다시) → 그래도 안 되면 같은 안내 + 진단(쥔 프로그램·읽기 전용·폴더·동기화 폴더).
_WORK_REPLACE_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 3.0, 4.0)  # ★10-17: 1.5초로는 백신·OneDrive·미리보기 잠금이 안 풀렸다(뇌전구 render_plan) — 합 약 10초
_SYNC_FOLDER_NAMES = ('onedrive', 'dropbox', 'google drive', 'googledrive', 'icloud', 'icloud drive', 'mobile documents', 'naver mybox', 'mybox')


def _replace_retrying(tmp, path):
    """이미 다 쓴 사본(tmp)을 path 로 올린다. 윈도우 공유 위반만 짧게 다시 — 사본을 만든 일은 다시 하지 않는다.
    마지막 실패는 그 OSError 그대로 올린다(무엇을 보존·안내할지는 부른 자리가 정한다)."""
    for attempt in range(len(_WORK_REPLACE_DELAYS) + 1):
        try:
            os.replace(tmp, path)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == len(_WORK_REPLACE_DELAYS):
                raise
            time.sleep(_WORK_REPLACE_DELAYS[attempt])


def _file_holders(path):
    """윈도우 Restart Manager(rstrtmgr.dll)로 이 파일을 지금 쥔 프로그램을 잰다.
    윈도우가 아니면 None · 잰 결과는 [«이름(pid N)»…] (빈 목록 = 쥔 프로그램 없음). 잴 수 없으면 OSError."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes

    class _Unique(ctypes.Structure):
        _fields_ = [('pid', wintypes.DWORD), ('start', wintypes.FILETIME)]

    class _Info(ctypes.Structure):
        _fields_ = [('proc', _Unique), ('app', ctypes.c_wchar * 256), ('svc', ctypes.c_wchar * 64),
                    ('kind', ctypes.c_int), ('status', wintypes.ULONG), ('session', wintypes.DWORD),
                    ('restartable', wintypes.BOOL)]

    rm = ctypes.WinDLL('rstrtmgr')
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    rc = rm.RmStartSession(ctypes.byref(session), 0, key)
    if rc:
        raise OSError(f'RmStartSession {rc}')
    try:
        names = (wintypes.LPCWSTR * 1)(os.path.abspath(path))
        rc = rm.RmRegisterResources(session, 1, names, 0, None, 0, None)
        if rc:
            raise OSError(f'RmRegisterResources {rc}')
        need, have = wintypes.UINT(0), wintypes.UINT(16)
        info, reasons = (_Info * 16)(), wintypes.DWORD()
        rc = rm.RmGetList(session, ctypes.byref(need), ctypes.byref(have), info, ctypes.byref(reasons))
        if rc == 234:   # ERROR_MORE_DATA — 16개 넘게 쥐었다(이름은 못 받는다)
            return [f'프로그램 {need.value}개']
        if rc:
            raise OSError(f'RmGetList {rc}')
        return [f'{info[i].app or "?"}(pid {info[i].proc.pid})' for i in range(have.value)]
    finally:
        rm.RmEndSession(session)


def _work_write_diagnosis(path):
    """쓰기 실패한 작업 파일의 사실만 잰다(추측 없이) — 같은 이름 폴더 · 읽기 전용 · 쥔 프로그램 · 동기화 폴더."""
    import stat as _stat
    facts = []
    try:
        st = os.stat(path)
    except FileNotFoundError:
        facts.append('그 자리에 파일 없음')
    except OSError as exc:
        facts.append(f'파일 상태 확인 실패({type(exc).__name__})')
    else:
        if _stat.S_ISDIR(st.st_mode):
            facts.append('같은 이름의 폴더가 있음')
        elif getattr(st, 'st_file_attributes', 0) & 1 or not os.access(path, os.W_OK):   # 1 = FILE_ATTRIBUTE_READONLY
            facts.append('읽기 전용 파일')
    try:
        holders = _file_holders(path)
    except (OSError, AttributeError, ValueError) as exc:
        facts.append(f'쥔 프로그램 확인 실패({exc})')
    else:
        if holders:
            facts.append('이 파일을 쥔 프로그램: ' + ', '.join(holders))
        elif holders == []:
            facts.append('지금 쥔 프로그램 없음(백신 검사 등 잠깐 잠금이었을 수 있음)')
    parts = [p.lower() for p in re.split(r'[\\/]', os.path.abspath(path))]
    sync = next((p for p in parts for name in _SYNC_FOLDER_NAMES if p == name or p.startswith(name + ' -')), None)
    if sync:
        facts.append(f'동기화 폴더 안({sync})')
    return ' · '.join(facts) or '특이 사항 없음'


def _work_write_failure(path, exc, what, note=''):
    """작업 폴더 파일 쓰기 실패 하나의 안내 — 모든 쓰는 자리가 이 문구 하나를 쓴다."""
    diagnosis = _work_write_diagnosis(path)
    # 할 일을 앞에 둔다 — 여러 칸을 함께 돌린 묶음(_pool)은 칸마다 앞 200자만 모아 보여 준다.
    advice = '사진 보기·편집 프로그램을 닫고, 작업 폴더가 OneDrive 등 동기화 폴더면 동기화를 멈추거나 밖으로 옮긴 뒤 같은 명령을 다시 실행하세요'
    if '읽기 전용' in diagnosis:
        advice += ' · 그 파일 속성의 «읽기 전용»을 끄세요'
    if '같은 이름의 폴더' in diagnosis:
        advice += ' · 그 자리의 같은 이름 폴더를 옮기세요'
    failure = StepError(f"{what} 작업 폴더에 쓰지 못했습니다({type(exc).__name__}) — {advice}.\n"
                        f"  파일: {path} · 진단: {diagnosis}\n  {note}{exc}")
    failure.target_path = path
    return failure


def _publish_work_file(path, *, data=None, src=None, what='파일을', note=''):
    """작업 폴더 파일 하나를 원자적으로 쓴다 — data(바이트) 또는 src(복사할 파일). 실패하면 _work_write_failure 하나로."""
    folder = os.path.dirname(path) or '.'
    os.makedirs(folder, exist_ok=True)
    source = open(src, 'rb') if src is not None else None   # 원본 읽기 실패는 작업 파일 탓이 아니다 — 그대로 올린다
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.work-', dir=folder)
        with os.fdopen(fd, 'wb') as fh:
            if source is not None:
                shutil.copyfileobj(source, fh)
            else:
                fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        _replace_retrying(tmp, path)
        tmp = None
    except OSError as exc:
        raise _work_write_failure(path, exc, what, note) from exc
    finally:
        if source is not None:
            source.close()
        if tmp is not None and os.path.exists(tmp):
            os.remove(tmp)


def _photo_write_state(path, value):
    """Each accepted asset is durable before the next card starts."""
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='.photo-state-', dir=os.path.dirname(path))
    preserve = False
    try:
        # UTF-8 encodes every ordinary Unicode scalar unchanged. A historical
        # lone surrogate is escaped as JSON \\uXXXX instead of deleting a valid
        # recovery copy or changing the original string on readback.
        with os.fdopen(fd, 'w', encoding='utf-8', errors='backslashreplace') as fh:
            json.dump(value, fh, ensure_ascii=False, separators=(',', ':'))
            fh.flush()
            os.fsync(fh.fileno())
        # Windows readers can briefly deny delete-sharing on an existing file.
        # Retry only the atomic publication, never the work that made its data (_replace_retrying 한 자리).
        try:
            _replace_retrying(tmp, path)
        except OSError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33):
                raise
            preserve = True
            failure = StepError(
                f"저장 파일을 교체하지 못해 다음 작업을 중단했습니다: {path}\n"
                f"완료한 측정의 새 사본은 보존했습니다: {tmp}\n"
                f"진단: {_work_write_diagnosis(path)}\n"
                "파일 사용 또는 접근 권한 문제를 해결한 뒤 이 사본을 저장 경로로 "
                "복원해 이어가세요. 같은 생성·검수 요청부터 다시 실행하지 마세요.")
            failure.recovery_path = tmp
            failure.target_path = path
            raise failure from error
    finally:
        if not preserve and os.path.exists(tmp):
            os.remove(tmp)


_PHOTO_SOURCE_META = {}

_PHOTO_PAGE_CACHE = {}

def _photo_page_records(page_url):
    """Image alt text and the exact lead-photo metadata from an explicit source page."""
    from html.parser import HTMLParser
    if not str(page_url).startswith(('http://', 'https://')):
        return []
    if page_url in _PHOTO_PAGE_CACHE:
        return _PHOTO_PAGE_CACHE[page_url]
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__();self.meta={};self.title=[];self.in_title=False;self.images={}
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            if tag=='meta':self.meta[attrs.get('property') or attrs.get('name') or '']=attrs.get('content','')
            if tag=='title':self.in_title=True
            if tag=='img':
                src=urllib.parse.urljoin(page_url,attrs.get('data-src') or attrs.get('src') or '')
                if src.startswith(('http://','https://')) and attrs.get('alt'):
                    self.images[src]=attrs['alt']
        def handle_endtag(self, tag):
            if tag=='title':self.in_title=False
        def handle_data(self, text):
            if self.in_title:self.title.append(text)
    records=[]
    try:
        req=urllib.request.Request(page_url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=15) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('photo source page too large')
            charset=response.headers.get_content_charset() or 'utf-8'
        parser=Parser();parser.feed(raw.decode(charset,errors='replace'))
        if str(parser.meta.get('og:type') or '').startswith('video'):
            _PHOTO_PAGE_CACHE[page_url]=[]
            return []
        og=urllib.parse.urljoin(page_url,parser.meta.get('og:image') or '')
        urls=list(parser.images)
        if parser.meta.get('og:image') and og not in urls:urls.append(og)
        for url in urls:
            records.append({'scope':'linked_photo_page','image_url':url,'page_url':page_url,
                            'caption':parser.images.get(url) or '',
                            'title':(parser.meta.get('og:title') or ''.join(parser.title)) if url==og else '',
                            'description':(parser.meta.get('og:description') or parser.meta.get('description') or '') if url==og else ''})
    except (OSError,ValueError,TimeoutError):
        pass
    _PHOTO_PAGE_CACHE[page_url]=records
    return records


def _photo_page_evidence(page_url, image_url):
    """Never lend the page's headline to another image or a video frame."""
    def same_url(left,right):
        a,b=urllib.parse.urlsplit(left),urllib.parse.urlsplit(right)
        return (a.netloc.lower(),a.path,a.query)==(b.netloc.lower(),b.path,b.query)
    return next((r for r in _photo_page_records(page_url) if same_url(r['image_url'],image_url)),{})


def _photo_review_request(item, photos):
    import hashlib
    config = item['photo_review']
    prompt = str(config['prompt']) + (
        "\n후보 출처 정보(정답 증거로 단정하지 마라):\n"
        "권리 메타와 사용자 진술은 제공된 맥락이며 이용권의 법적 확인이 아니다. "
        "로고·채널명·얼굴만으로 저작권 침해나 자유이용을 추정하지 마라. "
        "user_selected는 소재 선택이며 소유권 인증이 아니다. 화면 적합성을 판정하라.\n") + json.dumps(
        [{'candidateNumber': i, 'title': (_photo_metadata(p).get('title') or _photo_metadata(p).get('caption')) if config.get('require_subject_evidence') else _metadata_text(p.get('title')), 'source': p.get('source'),
          'source_metadata': _photo_metadata(p), 'user_selected': p.get('user_selected') is True}
         for i, p in enumerate(photos, 1)], ensure_ascii=False)
    digest = hashlib.sha256(json.dumps(dict(config, prompt=prompt), sort_keys=True,
                                       ensure_ascii=False).encode())
    for photo in photos:
        with open(photo['path'], 'rb') as fh:
            digest.update(hashlib.sha256(fh.read()).digest())
    directory = os.path.join(os.path.abspath(item.get('out_dir') or 'photo'), '.photo-qc')
    os.makedirs(directory, exist_ok=True)
    return prompt, os.path.join(directory, digest.hexdigest() + '.json')


def review_photos(item, photos, headers=None):
    """Reuse existing candidate QC, keyed by actual bytes + question.

    Unavailable/unparsed review is unchecked. A selected photo gets a single-image
    cache entry too: the subsequent whole-film audit must not charge to rejudge it.
    """
    from pathlib import Path
    config = item.get('photo_review')
    if not config:
        return {'verdict': 'unchecked', 'reason': 'photo_review 설정 없음'}
    # A portrait's source title cannot identify one of several measured people.
    # Apply current measurements before even reading a prior VLM acceptance.
    conflicts = {i for i, photo in enumerate(photos, 1)
                 if config.get('require_subject_evidence') and
                 any(type(n) is int and n > 1 for n in photo.get('face_sample_counts') or [])}
    if conflicts:
        kept = [(i, photo) for i, photo in enumerate(photos, 1) if i not in conflicts]
        result = review_photos(item, [photo for _, photo in kept], headers=headers) if kept else {
            'verdict':'retry','selectedCandidateNumber':None,'decisions':[],
            'summary':'단독 인물 사진의 출처 설명과 여러 사람의 실제 측정이 충돌합니다. 다른 사진을 조달합니다.',
            'identity_verified':False}
        decisions = [dict(d, candidateNumber=kept[d['candidateNumber'] - 1][0])
                     for d in result.get('decisions') or [] if isinstance(d, dict) and
                     type(d.get('candidateNumber')) is int and 1 <= d['candidateNumber'] <= len(kept)]
        selected = result.get('selectedCandidateNumber')
        selected = kept[selected - 1][0] if type(selected) is int and 1 <= selected <= len(kept) else None
        decisions.extend({'candidateNumber':i,'source_supported':False,
                          'reason_code':'measured_subject_ambiguity',
                          'face_sample_counts':photos[i - 1]['face_sample_counts']} for i in sorted(conflicts))
        return dict(result, selectedCandidateNumber=selected, n_candidates=len(photos),
                    decisions=sorted(decisions,key=lambda d:d['candidateNumber']))
    prompt, path = _photo_review_request(item, photos)
    try:
        with open(path, encoding="utf-8") as fh:
            cached = json.load(fh)
        if _qc_selection_complete({'n_candidates': len(photos)}, cached):
            return cached
    except (OSError, ValueError):
        pass
    if config.get('require_subject_evidence') and not any(
            p.get('user_selected') is True or (
                (p.get('source_metadata') or {}).get('scope') in ('image_record', 'linked_photo_page') and
                any(_metadata_text((p.get('source_metadata') or {}).get(k))
                    for k in ('title', 'caption', 'description'))) for p in photos):
        result = {'verdict': 'retry', 'selectedCandidateNumber': None,
                  'summary': '요청 인물을 설명하는 사진별 출처 메타가 없습니다. 얼굴로 추측하지 않고 다른 출처 사진을 찾습니다.',
                  'identity_verified': False, 'source_context': 'missing_image_attribution',
                  'decisions': [{'candidateNumber': i, 'reason_code': 'subject_source_unverified',
                                 'source_supported': False} for i in range(1, len(photos) + 1)]}
        _photo_write_state(path, result)
        return result
    job = dict(config, prompt=prompt, index=int(item["card"]),
               source_records=[dict(_photo_metadata(p), user_selected=p.get('user_selected') is True) for p in photos],
               images=[{"url": _file_uri(p["path"]),
                        "mime": _photo_image_mime(p['path'])} for p in photos], n_candidates=len(photos),
               out=path + ".raw")
    result = image_qc([job], headers or {}, retry=1, claude=config.get("claude"), client=config.get("client") or item.get("review_client"))[
        str(item["card"])]
    selected = result.get("selectedCandidateNumber")
    if result.get("verdict") == "accepted" and not (
            type(selected) is int and 1 <= selected <= len(photos)):
        result = dict(result, verdict="unparsed", reason="선택 번호가 후보 범위를 벗어났습니다")
    # Only actual model verdicts are durable. Missing credentials can become available
    # later without changing the request; they must not be cached as a quality result.
    if result.get("verdict") in ("accepted", "retry"):
        _photo_write_state(path, result)
        if result['verdict'] == 'accepted' and len(photos) > 1:
            _prompt, single_path = _photo_review_request(item, [photos[selected - 1]])
            single = dict(result, selectedCandidateNumber=1, n_candidates=1,
                          decisions=[dict(d, candidateNumber=1) for d in result.get('decisions') or []
                                     if isinstance(d, dict) and d.get('candidateNumber') == selected])
            _photo_write_state(single_path, single)
    return result


def check_photo(item, headers=None, *, generation_headers=None):
    """Flatness is a suspicion; cached visual QC decides whether repair is needed.

    A server-authored repair has one durable attempt per output. Its normal raw
    cache permits interrupted work to resume without regenerating successful assets.
    """
    wanted = [f for f in item.get("files") or [] if f]
    present = [(f, os.path.isfile(f)) for f in wanted]
    files = [f for f, ok in present if ok]
    missing = [f for f, ok in present if not ok]
    if not files:
        # ★어느 파일이 없는지 말한다(2026-10-15) — 예전 문구는 경로가 한 글자도 없어 회원이 원인을 못 찾았다(4일 450건+ 한 사람).
        shown = " · ".join(missing[:5]) + (f" 외 {len(missing) - 5}개" if len(missing) > 5 else "")
        message = (f"그림체 검사를 한 장도 못 했다 — 검사할 그림 {len(missing)}개가 작업 폴더에 하나도 없다: {shown}\n"
                   "  그 칸 그림을 images 단계가 만들거나 놓은 적이 없다는 뜻이다. 본인 그림을 쓰는 칸이면 "
                   "customization.images.<칸>.path(또는 user_slots 의 {칸: 파일 경로})로 본인 파일을 지정하고 images 단계부터 "
                   "다시 돌리면 실행기가 그 자리에 놓는다. user_slots 를 번호 목록으로만 선언했다면 그 그림을 위 경로에 직접 두어야 한다.")
        if any('/img43/' in f.replace('\\', '/') for f in missing):
            # 그림 칸은 images 단계가 만드는 자리다 — 처방이 «images 다시» 하나뿐이라 구동기가 images 로 한 번 돌아간다(StepBack ·
            #   같은 빠진 칸에 한 번 · render_plan 의 빠진 칸과 같은 길). 2026-10-20 뇌전구 신고 290건: images 가 제공자 거절로 멈춘
            #   편을 밖에서 memes 로 불러 이 글만 되풀이됐다 — 돌아가면 images 가 진짜 원인(거절·할 일)을 말한다.
            raise StepBack(message + "\n  실행기는 images 로 한 번 돌아가 빠진 칸을 만든다 — 그 뒤에도 이 글이 나오면 images 의 그 칸 결과를 확인하라.",
                           'images', tuple(sorted(missing)))
        raise StepError(message)
    if missing:
        _progress("  ⚠ [그림체 검사] 없는 그림 " + str(len(missing)) + "개는 건너뛴다: " + " · ".join(missing[:5])
                  + (f" 외 {len(missing) - 5}개" if len(missing) > 5 else ""), flush=True)
    result = {"checked": len(files), "reviewed": [], "repaired": [], "unresolved": []}
    recovery = item.get("recovery") or {}
    jobs = {os.path.abspath(j["out"]): j for j in recovery.get("jobs") or []}
    for index, path in enumerate(files, 1):
        state_path = path + ".photo-repair.json"
        state = _photo_read_state(state_path)
        job = jobs.get(os.path.abspath(path))
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        recipe_key = hashlib.sha256(json.dumps(job, sort_keys=True, ensure_ascii=False,
                                               separators=(",", ":")).encode()).hexdigest()
        previous = state["requests"].get("completed")
        same_image = isinstance(previous, dict) and previous.get("output_sha256") == digest
        completed = same_image and previous.get("recipe_key") == recipe_key
        suspect = is_drawn(path, item.get("gate"))
        if not suspect and not same_image and previous is not True:
            continue
        metrics = dict(getattr(is_drawn, "last", {}) or {})
        request = {"card": index, "out_dir": os.path.dirname(path),
                   "photo_review": item.get("photo_review")}
        verdict = review_photos(request, [{"path": path}], headers=headers)
        detail = {"file": path, "metrics": metrics, "review": verdict}
        result["reviewed"].append(detail)
        if verdict.get("verdict") == "accepted":
            continue
        illustration = any(d.get("visual_kind") == "illustration" for d in verdict.get("decisions") or [] if isinstance(d, dict))
        if verdict.get("verdict") == "retry" and illustration and not job:
            # 생성 칸 복구 잡이 없는 편(플로우)의 «그림체로 확정된 칸» — 아래 정지 전에 auto_redo 가 그 칸을 images 로 한 번 되돌린다.
            detail["redo_sha256"] = digest
        if verdict.get("verdict") == "retry" and illustration and job and not completed:
            # The generator persists its submission before polling/downloading.
            # This separate receipt marks a completed visual repair only.
            repair_headers = generation_headers if generation_headers is not None else headers
            generate_images([job], recovery["poll"], (repair_headers() if callable(repair_headers) else repair_headers) or {}, recovery["retry"],
                            recovery["min_bytes"], parallel=1,
                            stagger=recovery.get("stagger_sec", 0),
                            retry_policy=recovery.get("retry_policy"))
            with open(path, "rb") as fh:
                output_digest = hashlib.sha256(fh.read()).hexdigest()
            state["requests"]["completed"] = {"recipe_key": recipe_key,
                                                "output_sha256": output_digest}
            _photo_write_state(state_path, state)
            verdict = review_photos(request, [{"path": path}], headers=headers)
            detail["after_review"] = verdict
            if verdict.get("verdict") == "accepted":
                result["repaired"].append(path)
                continue
        result["unresolved"].append(detail)
    redo = _photo_auto_redo(item, result["unresolved"])
    if redo is not None:
        raise redo
    if result["unresolved"]:
        detail = "\n".join(str(d["file"]) + ": " + str((d.get("after_review") or d["review"]).get("summary") or
                           (d.get("after_review") or d["review"]).get("reason") or "실사 여부 확인 불가")
                           for d in result["unresolved"])
        extra, resume = _photo_stop_lines(item, result["unresolved"])
        error = StepError("사진 실사 검수 미완료 — 해당 슬롯만 확인해야 합니다.\n" + detail +
                          "\n" + str(item.get("on_fail") or "") + extra)
        # 잇는 길을 이 정지가 스스로 싣는다 — 구동기의 일반 «같은 명령 그대로» 재개 안내를 내지 않게(그 명령은 같은 정지로 돌아온다).
        # 늘 한 줄 이상이다(채운 한 줄을 가리키거나 · 서버 알림을 가리킨다 — _photo_stop_lines).
        error.resume_lines = resume
        raise error
    return result


def _photo_auto_redo(item, unresolved):
    """플로우 편에서 그림체로 확정된 생성 칸을 사람에게 묻기 전에 images 로 **한 번** 되돌린다(2026-10-23 신고 · StepBack 또는 None).

    EvoLink 편은 위 recovery 잡이 그 칸을 그 자리에서 한 번 다시 만든다. 플로우 편은 잡이 없어(그 열쇠를 요구하지 않은 편) 그림체 칸
    하나로 작업 전체가 멈추고, 사용자가 같은 명령을 다시 돌리면 저장된 판정(.photo-qc)으로 같은 정지를 되풀이했다(10-23 7건·4명 중 5건).
    서버가 실은 `auto_redo`(다시 만들 수 있는 칸만 · 이미 실사 지시로 다시 만든 칸과 사용자 칸은 서버가 뺀다)에 든 칸을 payload 의
    `field`(flow_redo)에 더해 `back_to`(images)로 돌아간다 — images 가 그 칸만 실사 지시를 붙인 새 플로우 요청을 낸다.
    끝나는 조건 둘: 구동기가 같은 표지(칸·그림 지문)에 한 번만 돌아가고, 서버는 다시 만든 칸(flow_state.redo)을 auto_redo 에서 뺀다 —
    다시 만든 뒤에도 그림체면 아래 정지(그대로 쓰기·바꾸기)로 사람에게 묻는다. 기준은 EvoLink 복구와 같다(retry + illustration)."""
    plan = item.get("auto_redo")
    if not isinstance(plan, dict) or not isinstance(plan.get("slot_of"), dict) or not plan.get("back_to") or not plan.get("field"):
        return None
    picked = sorted(((str(plan["slot_of"][d["file"]]), d["file"], d["redo_sha256"]) for d in unresolved
                     if d.get("redo_sha256") and d["file"] in plan["slot_of"]), key=lambda x: int(x[0]))
    if not picked:
        return None
    slots = [int(s) for s, _f, _h in picked]
    back = StepBack("사진 실사 검수: 그림체로 판정된 플로우 칸 " + ", ".join(map(str, slots)) + " 을 실사 지시로 한 번 다시 만듭니다",
                    str(plan["back_to"]), tuple((f, h) for _s, f, h in picked))
    back.payload_add = {str(plan["field"]): slots}
    return back


#: 서버 volcano_photo_gate.FILLED_MARK 와 같은 글자 — 칸 번호를 채운 한 줄을 이 정지 글에 찍었다는 표지(검사가 두 글자를 대조한다).
#: 서버는 실패 보고 글에서 이 표지와 엔진 표지를 함께 보면 알림에서 명령 줄을 뺀다(같은 명령을 두 번 찍지 않는다 · 10-06 검토 3회차).
_PHOTO_FILLED_MARK = "▶ 멈춘 칸"
#: 채운 한 줄이 없을 때(서버 틀이 없는 옛 응답을 재생 · 채우기 실패) 잇는 길을 가리키는 한 줄 — 구동기의 일반 «같은 명령 그대로» 재개
#: 안내가 사진 정지에 나오지 않게 resume_lines 를 비우지 않는다(10-06 검토 3회차 · 서버 안내 «같은 명령을 다시 실행하지 마세요» 와 반대).
_PHOTO_STOP_POINTER = ("위 [알림] photo_stop 의 한 줄을 쓰세요 — 이 정지 보고에 서버가 칸 번호를 채운 한 줄로 답합니다. 알림이 없으면 판정 "
                       "근거를 사용자에게 보여 주고 칸마다 고른 뒤 그 칸을 payload.customization.images 에 지정해 같은 단계를 부르세요"
                       "(같은 명령을 그대로 다시 실행하면 저장된 판정으로 같은 정지가 납니다).")
#: 채운 한 줄을 이 정지 글에 찍었을 때 잇는 줄(resume_lines) — 그 줄들을 **가리킨다**. 구동기의 예외 뒤 재개 안내(B 묶음)가 resume_lines
#: 를 그대로 찍으므로 명령을 또 실으면 같은 명령이 두 벌이 된다(10-06 검토 3회차 — 그때 줄 하나 약 3.4K자 × 셸·길 6줄 ≈ 20K자.
#: 지금 줄은 짧지만(팩 안 도우미 파일을 부른다) 같은 명령 두 벌은 그대로 피한다).
_PHOTO_FILLED_POINTER = ("이 정지의 StepError 글 끝 «{mark}: {slots}» 바로 위에 칸 번호·도우미 위치를 채운 한 줄들이 있습니다 — "
                         "고른 길의 한 줄을 그대로 실행하세요.")
#: 사진 정지 한 줄이 부르는 도우미 — 실행기 팩에 든 파일(runner_files.STUDENT_FILES · tools/build_photo_fix.py 가 서버 본문으로 만든다).
#: 서버 volcano_photo_gate.HELPER_FILE 과 같은 이름(검사가 대조한다).
_PHOTO_FIX_FILE = "photo_fix.py"


def _photo_fix_path():
    """한 줄이 부를 도우미 — 이 실행기 폴더(volcano_run 옆)의 `_PHOTO_FIX_FILE` (2026-10-06 Q 도우미 파일화).

    팩에 든 파일이라 팩 sha 로 무결성이 보장되고 런타임에 코드 파일을 새로 쓰지 않는다. 그 도우미가 **자기 옆** volcano_drive.py 를
    다시 띄운다 — 작업 폴더 밖 공용 실행기도 제 자리를 안다(10-06 검토 3회차). 예전 한 줄은 도우미 코드를 통째로 품어 줄 하나가
    약 3.4K자였다(윈도우 정지 1칸 덧붙임 약 20.7K자 — 클로드 코드 명령 출력 3만 자 한도에서 가운데가 잘릴 수 있었다).
    없으면 FileNotFoundError — 부르는 쪽(`_photo_stop_lines`)이 채운 줄 없이 정지 보고 알림을 가리킨다(알림은 `-c` 모양 한 줄을 준다).
    윈도우는 `/` 표기로 적는다(서버 한 줄 규율 — 파이썬·PowerShell·Git Bash 가 다 받는다) · 긴 경로 머리(`\\\\?\\`)는 뗀다."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _PHOTO_FIX_FILE)
    if not os.path.isfile(path):
        raise FileNotFoundError("사진 정지 한 줄 도우미가 실행기 폴더에 없습니다: " + path)
    return _photo_line_path(path) if os.name == "nt" else path


def _photo_line_path(path):
    """윈도우 경로를 한 줄에 적는 모양으로 — 긴 경로 머리(`\\\\?\\` · `\\\\?\\UNC\\`)를 떼고 `/` 표기(서버 한 줄 규율)."""
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]
    return path.replace("\\", "/")


#: PowerShell 이 «작은따옴표» 로 읽는 글자 — ASCII ' 와 둥근 작은따옴표 넷(U+2018 ‘ · U+2019 ’ · U+201A ‚ · U+201B ‛). 작은따옴표
#: 글자('…') 안에서 이 가운데 하나가 나오면 글자가 끝나고 둘이 이어지면 글자 하나다(PowerShell 토크나이저 · about_Quoting_Rules) —
#: ' 만 겹치면 ’ 든 경로(예: «Kim’s Videos»)에서 줄이 깨진다(10-06 Q 검토 4회차 nit ⑦). 서버 volcano_photo_gate.PS_SINGLE_QUOTES 와
#: 같은 글자들이다(검사가 대조한다).
_PS_SINGLE_QUOTES = "'\u2018\u2019\u201a\u201b"


def _photo_quote(value, quote):
    """resolve 틀의 `quote` 대로 감싼다 — ps: PowerShell 작은따옴표(안의 작은따옴표 — ASCII·둥근 넷 — 는 같은 글자를 두 번),
    sh: POSIX 셸(shlex). 모르는 방식이면 멈춘다."""
    import shlex
    if quote == "ps":
        return "'" + "".join(c + c if c in _PS_SINGLE_QUOTES else c for c in value) + "'"
    if quote == "sh":
        return shlex.quote(value)
    raise ValueError("resolve 틀의 quote 를 모른다: %r" % (quote,))


def _photo_stop_lines(item, unresolved):
    """(정지 글 꼬리, 잇는 한 줄 목록) — 멈춘 칸 번호를 서버가 준 틀(`resolve`)에 채우고 같은 정지가 몇 번째인지 말한다 (2026-10-05 Q).

    검수 답은 그림 바이트+질문으로 저장돼(.photo-qc) 같은 명령을 다시 돌리면 같은 판정으로 또 멈춘다 — 실측 한 사람이 14분에 20번,
    서버 단계 호출 없이(응답 영수증 재생) 되풀이했다. 그래서 이 자리가 «N번째 같은 정지» 를 말한다(서버는 실패 보고로 따로 센다).
    틀의 자리: `{slots}` 멈춘 칸들 · `{one}` 바꾸기 칸(멈춘 칸이 하나면 그 칸, 여럿이면 «<칸>») · `{fix}` 이 실행기 폴더의 한 줄
    도우미 파일(`_photo_fix_path` · 줄의 `quote` 대로 감쌈 — 경로에 띄어쓰기·한글·작은따옴표가 있어도 그 셸의 규칙으로).
    ★예전 틀의 자리(`{runner}`·`{helper}`·`{tail}` — 줄마다 도우미 코드를 통째로 다시 채우던 모양)는 채우지 않는다 — 그런 틀이 오면
      서버와 실행기 판이 어긋난 것이라 채운 줄 없이 알림을 가리킨다(조용히 반쯤 채운 명령을 찍지 않는다).
    틀의 줄에 `only` 가 있으면 그 칸만 채운다(이미 다시 만든 칸에는 다시 만들기를 내지 않는다 — 서버 volcano_photo_gate).
    ★채운 줄들 **뒤** 엔진 표지 바로 앞에 `_PHOTO_FILLED_MARK` 줄을 둔다 — 실패 보고가 끝을 남기고 가운데를 자르므로 서버가 그 표지로
      «실행기가 이미 찍었다» 를 안다.
    ★이 함수는 정지 안내를 **가리지 않는다** — 세기·채우기가 실패하면 원래 안내는 그대로 두고 무엇을 못 했는지 한 줄 덧붙인다
      (예외가 정지 글 대신 올라가면 사람이 엉뚱한 트레이스백을 본다 · 10-06 검토 minor). 채운 줄이 없으면(틀 없는 옛 서버 응답 · 채우기
      실패) 잇는 줄로 `_PHOTO_STOP_POINTER` 를 돌려준다 — 정지 글 자체에는 덧붙이지 않는다(옛 글 끝의 엔진 판별 문장을 밀어내지 않게).
    ★잇는 줄(resume_lines)은 **가리킴 한 줄**이다 — 명령은 정지 글에만 한 벌(`_PHOTO_FILLED_POINTER` 주석).
    """
    resolve = item.get("resolve")
    if not isinstance(resolve, dict):
        return "", [_PHOTO_STOP_POINTER]
    out, lines, stopped = [], [], []     # stopped 는 lines 가 차야 쓰인다 — try 앞에서 정해 둔다(경계 검사 · 동작 동일)
    try:
        slot_of = resolve.get("slot_of") if isinstance(resolve.get("slot_of"), dict) else {}
        stopped = sorted({str(slot_of[d["file"]]) for d in unresolved if d.get("file") in slot_of},
                         key=lambda s: (not s.isdigit(), int(s) if s.isdigit() else 0, s))
        count = _photo_stop_count(unresolved)
        if count is None:
            out.append("■ 같은 정지가 몇 번째인지 세지 못했습니다(.photo-qc/stops.json 을 읽거나 쓰지 못함) — 다시 실행해도 결과는 같습니다.")
        elif count > 1:
            out.append(f"■ 같은 그림·같은 판정으로 {count}번째 멈춤입니다 — 다시 실행해도 결과는 같습니다. 아래에서 고르세요.")
        fix = None          # 이 실행기 폴더의 도우미 — 채울 줄이 있을 때 한 번만 찾는다(없으면 FileNotFoundError → 알림을 가리킨다)
        filled_lines = []
        for r in resolve.get("lines") or []:
            if not (isinstance(r, dict) and isinstance(r.get("command"), str)):
                continue
            only = r.get("only")
            mine = [s for s in stopped if s in {str(x) for x in only}] if isinstance(only, list) else stopped
            if not mine:
                continue
            old = sorted(set(re.findall(r"\{(runner|helper|tail)\}", r["command"])))
            if old:
                raise ValueError("이 실행기가 채우지 않는 resolve 틀 자리 " + ",".join("{" + x + "}" for x in old)
                                 + " — 서버와 실행기 판이 어긋났습니다")
            fix = _photo_fix_path() if fix is None else fix
            values = {"slots": ",".join(mine), "one": mine[0] if len(mine) == 1 else "<칸>",
                      "fix": _photo_quote(fix, r.get("quote"))}
            # 한 번에 바꾼다 — 넣은 글(도우미 경로) 안의 글자가 다른 자리로 다시 바뀌지 않게.
            filled = re.sub(r"\{(slots|one|fix)\}", lambda m, values=values: values[m.group(1)], r["command"])
            filled_lines.append(str(r.get("label") or "") + ": " + filled)
        lines = filled_lines
        if lines:
            out.append("고른 길의 한 줄을 그대로 실행하세요(칸 번호·도우미 위치는 이 실행기가 채웠습니다):")
            out.extend("  " + x for x in lines)
            out.append(f"{_PHOTO_FILLED_MARK}: {','.join(stopped)} — 위 한 줄 가운데 고른 길 하나를 실행하세요.")
    except Exception as e:  # noqa: BLE001 — 정지 글을 가리지 않는다(위). 못 한 것은 말한다.
        lines = []
        out.append(f"■ 멈춘 칸 한 줄을 짓지 못했습니다({type(e).__name__}: {e}) — 실패 보고 뒤 [알림] photo_stop 의 한 줄을 쓰세요.")
    # 서버가 준 그림 엔진 표지를 정지 글 **맨 끝**에 다시 붙인다 — 실패 보고는 끝을 남기고 가운데를 자르므로 서버가 이 표지로
    # 플로우 편인가를 가른다(volcano_photo_gate.ENGINE_TAG · 10-06 검토 major). 덧붙인 것이 없으면 on_fail 끝이 이미 그 표지다.
    tag = resolve.get("tag")
    if out and isinstance(tag, str) and tag:
        out.append(tag)
    resume = ([_PHOTO_FILLED_POINTER.format(mark=_PHOTO_FILLED_MARK, slots=",".join(stopped))] if lines else [_PHOTO_STOP_POINTER])
    return ("\n" + "\n".join(out) if out else ""), resume


def _photo_stop_count(unresolved):
    """같은 그림 묶음(경로+바이트)으로 몇 번째 멈췄는가 — img43/.photo-qc/stops.json. 못 세면 None(깨진 기록을 0 으로 치지 않는다)."""
    import hashlib
    marks = []
    for d in unresolved:
        with open(d["file"], "rb") as fh:
            marks.append([os.path.abspath(d["file"]), hashlib.sha256(fh.read()).hexdigest()])
    key = hashlib.sha256(json.dumps(sorted(marks)).encode()).hexdigest()
    path = os.path.join(os.path.dirname(os.path.abspath(unresolved[0]["file"])), ".photo-qc", "stops.json")
    try:
        with open(_review_receipt_io_path(path), encoding="utf-8") as fh:
            seen = json.load(fh)
    except FileNotFoundError:
        seen = {}
    except (OSError, ValueError):
        return None
    if not isinstance(seen, dict):
        return None
    prev = seen.get(key)
    count = (prev if type(prev) is int and prev > 0 else 0) + 1
    seen[key] = count
    try:
        os.makedirs(_review_receipt_io_path(os.path.dirname(path)), exist_ok=True)
        _photo_write_state(_review_receipt_io_path(path), seen)
    except OSError:
        return None
    return count


def _film_qc_complete(answer, metadata):
    """A film verdict selects only the measured IDs for every sampled frame."""
    if not isinstance(answer, dict):
        return False
    if answer.get('verdict') == 'retry':
        return True
    decisions = answer.get('decisions')
    if (answer.get('verdict') != 'accepted' or not isinstance(decisions, list)
            or len(decisions) != len(metadata)):
        return False
    candidates = {m.get('candidateNumber',i+1):m for i,m in enumerate(metadata)}
    if len(candidates) != len(metadata):
        return False
    seen = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            return False
        n, fid, tids = (decision.get(k) for k in ('candidateNumber', 'faceId', 'textIds'))
        if (type(n) is not int or n not in candidates or n in seen
                or not isinstance(tids, list)):
            return False
        seen.add(n)
        if fid is not None and (type(fid) is not int or not 0 <= fid < len(candidates[n]['faces'])):
            return False
        if any(type(t) is not int or not 0 <= t < len(candidates[n]['texts']) for t in tids):
            return False
    return True


def _film_context_text_complete(answer, metadata):
    """Every OCR candidate has one explicit role; missing IDs are not approval."""
    if not _film_qc_complete(answer, metadata):
        return False
    if answer.get('verdict') == 'retry':
        return True
    candidates = {m.get('candidateNumber',i+1):m for i,m in enumerate(metadata)}
    for decision in answer['decisions']:
        ids = []
        for field in ('textIds','preservedTextIds','falseTextIds'):
            selected = decision.get(field)
            if not isinstance(selected,list) or any(type(i) is not int for i in selected):
                return False
            ids.extend(selected)
        if (sorted(ids) != list(range(len(candidates[decision['candidateNumber']]['texts'])))
                or not isinstance(decision.get('reason'),str) or not decision['reason'].strip()):
            return False
        candidate=candidates[decision['candidateNumber']]
        if 'scene_views' in candidate:
            votes=decision.get('sceneViews')
            ids=[v['candidate_id'] for v in candidate['scene_views']]
            if (not isinstance(votes,list) or len(votes)!=len(ids)
                    or any(not isinstance(v,dict) or type(v.get('candidate_id')) is not int or type(v.get('accepted')) is not bool
                           or not isinstance(v.get('reason'),str) or not v['reason'].strip() for v in votes)
                    or [v.get('candidate_id') for v in votes]!=ids):return False
            for vote,view in zip(votes,candidate['scene_views']):
                if not vote['accepted']:continue
                x,y,w,h=view['view']
                for tid in decision['preservedTextIds']:
                    tx,ty,tw,th=candidate['texts'][tid]
                    if tx<x or ty<y or tx+tw>x+w or ty+th>y+h:return False
        elif 'scene_view' in candidate:
            # Historical replies remain parseable, but cannot authorize a v2 viewport.
            if type(decision.get('sceneViewAccepted')) is not bool:return False
            if decision['sceneViewAccepted']:
                x,y,w,h=candidate['scene_view']
                for tid in decision['preservedTextIds']:
                    tx,ty,tw,th=candidate['texts'][tid]
                    if tx<x or ty<y or tx+tw>x+w or ty+th>y+h:return False
    return True


def _photo_text_complete(answer, metadata):
    if not _film_qc_complete(answer, metadata):
        return False
    if answer.get('verdict') == 'retry':
        return True
    return all(isinstance(d.get('reason'), str) and d['reason'].strip()
               and len(d['textIds']) == len(set(d['textIds'])) and d.get('faceId') is None
               for d in answer['decisions'])


def _video_text_complete(answer, metadata):
    if not _photo_text_complete(answer,metadata):return False
    if answer.get('verdict')=='retry':return True
    frames={m['candidateNumber']:m for m in metadata}
    for d in answer['decisions']:
        false=d.get('falseTextIds')
        if (not isinstance(false,list) or any(type(i) is not int for i in false)
                or sorted(d['textIds']+false)!=list(range(len(frames[d['candidateNumber']]['texts'])))):
            return False
    return True


def _review_preserved_video_text(item, headers=None):
    """Classify only conflicting raw OCR on the original output grid, without detection."""
    import hashlib
    import subject_focus as F
    from PIL import Image,ImageDraw
    root=Path(item['out_dir']);root.mkdir(parents=True,exist_ok=True);out={}
    for request in item['cuts']:
        usage=str(request['card']);key=request['key'];binding=request['binding'];evidence=binding['evidence']
        receipt=dict(key=key,binding=evidence,status='unchecked',automatic_retry=False)
        try:
            actual=hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
            if key!=actual or review_semantic_config(item['photo_review'])!=review_semantic_config(binding['review']):
                raise StepError('video_text_binding_invalid')
            cut=binding['cut'];grid=evidence['frame_grid'];source=Path(cut['src'])
            indices=[f['frame_index'] for f in evidence['frames']]
            if (evidence.get('version')!=1 or F._sha(source)!=evidence['source_identity']
                    or grid!=dict(start=cut['start'],fps=cut['fps'],nframes=round(cut['duration']*cut['fps']))
                    or any(abs(f['t']-cut['start']-f['frame_index']/cut['fps'])>1e-6 for f in evidence['frames'])):
                raise StepError('video_text_source_or_grid_changed')
            directory=root/key;directory.mkdir(exist_ok=True)
            with review_receipt_lock(str(directory/'prepare')):
                frames_dir=directory/'frames';frames_dir.mkdir(exist_ok=True)
                paths,_,pts=F._frames(cut,frames_dir,binding['policy'],wanted_indices=indices)
                if len(pts)!=grid['nframes'] or len(paths)!=len(indices):raise StepError('video_text_frame_grid_invalid')
                metadata=[];units=[];cx,cy,cw,ch=evidence['content']
                for i,(frame,path) in enumerate(zip(evidence['frames'],paths),start=1):
                    with Image.open(path) as original:
                        if list(original.size)!=evidence['size'] or not F._box(evidence['content'],*original.size):
                            raise StepError('video_text_content_changed')
                        image=original.convert('RGB').crop((cx,cy,cx+cw,cy+ch))
                    if (not frame['texts'] or any(not F._box(b,cw,ch) for b in frame['texts'])
                            or len(frame['text_indices'])!=len(frame['texts'])):
                        raise StepError('video_text_candidates_invalid')
                    clean=Path(_frozen_png(image,directory))
                    draw=ImageDraw.Draw(image)
                    for tid,(x,y,w,h) in enumerate(frame['texts']):
                        draw.rectangle([x,y,x+w,y+h],outline='red',width=2)
                        draw.text((max(0,x),max(0,y-14)),f'T{tid}',fill='red',stroke_width=1,stroke_fill='black')
                    marked=Path(_frozen_png(image,directory))
                    meta=dict(candidateNumber=i,faces=[],texts=frame['texts'],frame_index=frame['frame_index'],source_time=frame['t'])
                    metadata.append(meta)
                    units.append(dict(metadata=meta,images=[dict(url=_file_uri(p),mime='image/png') for p in (clean,marked)],
                        labels=[f'candidateNumber={i} original pixels',f'candidateNumber={i} marked T IDs']))
                job=dict(item['photo_review'],index=0,out=str(directory/'review.json'),qc_contract='film_frames_v1')
                def prompt_for(selected):
                    return item['photo_review']['prompt']+'\n실측 후보 목록: '+json.dumps(selected,ensure_ascii=False)
                answer=image_qc_batches(job,units,headers or {},prompt_for=prompt_for,result_validator=_video_text_complete,
                    allow_provider=item.get('allow_provider',True),
                    client=item['review_client'],review_policy=item['review_policy'],
                    client_replies=item['focus_review_replies'],review_budget=item['_review_budget'])
                if answer.get('code')=='review_in_progress':
                    raise TranscriptionPending('이미지 검수',answer.get('reason') or '같은 검수가 실행 중입니다.',retry_after=2)
                if F._sha(source)!=evidence['source_identity']:raise StepError('video_text_source_changed')
                if answer.get('verdict')=='accepted' and _video_text_complete(answer,metadata):
                    receipt.update(status='accepted',decisions=answer['decisions'])
                else:
                    receipt.update(code=answer.get('code') or 'video_text_unresolved',
                        reason=answer.get('reason') or answer.get('summary') or '글자 후보 분류가 완전하지 않습니다.')
                    # 검수 묶음이 실행 예외로 끊겼다(image_qc_batches 의 unparsed) — 모델 판정이 아니다(예산 정지 제외).
                    if answer.get('verdict')=='unparsed' and not answer.get('review_budget_blocked'):receipt['stage']='execution'
        except ClientReviewPending as exc:
            if item.get('engine_failure_rows') is True and getattr(exc,'engine_failed',False):
                # 검수 엔진(구독 AGY 등)이 결과 없이 끝났다 — 사람이 손으로 쓸 답 대기가 아니라 실행 실패다(local_focus 가 opt-in ·
                #   막힌 컷의 «다시» 로 풀린다 · subject_focus.select_subjects 와 같은 규칙).
                receipt.update(code=getattr(exc,'engine_code',None) or 'client_review_no_result',stage='execution',
                               reason=(getattr(exc,'engine_reason','') or str(exc))[:1200])
            else:receipt.update(status='pending',code=exc.code,review_requests=[exc.request])
        except (StepError,OSError,ValueError,KeyError,TypeError) as exc:
            if getattr(exc,'code',None)=='review_in_progress':raise
            refused=isinstance(exc,ProviderRefusalError)
            receipt.update(code='provider_refused' if refused else getattr(exc,'code','video_text_execution_failed'),reason=str(exc)[:1200])
            if getattr(exc,'review_budget_blocked',None):receipt['review_budget_blocked']=exc.review_budget_blocked
            # 판정(모델 답)이 아니라 실행이 끊긴 것 — local_focus 가 «다시 재면 달라질 수 있는 막힘» 으로 말한다(거부·예산 정지는 제외).
            elif not refused:receipt['stage']='execution'
        out[usage]=receipt
    return out


def _review_preserved_photo_text(item, headers=None):
    """Review preserved OCR IDs on the same bytes without rerunning subject work."""
    import hashlib, io
    from pathlib import Path
    from PIL import Image, ImageDraw
    root = Path(item['out_dir']); root.mkdir(parents=True, exist_ok=True)
    out = {}
    for request in item['cuts']:
        usage = str(request['card']); key = request['key']; binding = request['binding']
        receipt = dict(key=key, status='unchecked', automatic_retry=False)
        try:
            actual_key = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False,
                                                   allow_nan=False).encode()).hexdigest()
            if actual_key != key or len(key) != 64:
                raise StepError('photo_text_binding_invalid')
            if review_semantic_config(item['photo_review']) != binding['review']:
                raise StepError('photo_text_review_changed')
            src = Path(binding['src'])
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != binding['source_identity']:
                raise StepError('photo_text_source_changed')
            directory = root/key; directory.mkdir(exist_ok=True)
            # Protect shared PNG preparation as well as the inner provider receipt.
            # Windows cannot replace a PNG while another review is reading it.
            with review_receipt_lock(str(directory/'prepare')):
                with Image.open(io.BytesIO(data)) as original:
                    if list(original.size) != binding['size']:
                        raise StepError('photo_text_size_changed')
                    x,y,w,h = binding['content']
                    im = original.convert('RGB').crop((x,y,x+w,y+h))
                clean = Path(_frozen_png(im,directory))
                draw = ImageDraw.Draw(im)
                for n,(x,y,w,h) in enumerate(binding['texts']):
                    draw.rectangle([x,y,x+w,y+h], outline='red', width=2)
                    draw.text((max(0,x),max(0,y-14)), f'T{n}', fill='red', stroke_width=1, stroke_fill='black')
                annotated = Path(_frozen_png(im,directory))
                metadata = [dict(candidateNumber=1, faces=[], texts=binding['texts'])]
                def prompt_for(selected):
                    return (item['photo_review']['prompt']+'\n원래 컷 문맥: '+str(binding.get('context') or '')+
                            '\n원본 보존 의도: '+json.dumps(binding['policy'],ensure_ascii=False)+
                            '\n실측 후보 목록: '+json.dumps(selected,ensure_ascii=False))
                job = dict(item['photo_review'], index=0, out=str(directory/'review.json'),
                           qc_contract='film_frames_v1')
                unit = dict(metadata=metadata[0], images=[dict(url=_file_uri(p),mime='image/png') for p in (clean,annotated)],
                            labels=['candidateNumber=1 original pixels','candidateNumber=1 marked T IDs'])
                answer = image_qc_batches(job, [unit], headers or {}, prompt_for=prompt_for,
                                          result_validator=_photo_text_complete, client=item['review_client'],
                                          allow_provider=item.get('allow_provider',True),
                                          review_policy=item['review_policy'],
                                          client_replies=item['focus_review_replies'],
                                          review_budget=item['_review_budget'])
                if answer.get('code') == 'review_in_progress':
                    raise TranscriptionPending('이미지 검수',answer.get('reason') or '같은 검수가 실행 중입니다.',retry_after=2)
                if hashlib.sha256(src.read_bytes()).hexdigest() != binding['source_identity']:
                    raise StepError('photo_text_source_changed')
                if answer.get('verdict') == 'accepted' and _photo_text_complete(answer, metadata):
                    decision = answer['decisions'][0]
                    receipt.update(status='accepted', text_ids=decision['textIds'], reason=decision['reason'])
                else:
                    receipt.update(code=answer.get('code') or 'photo_text_unresolved',
                                   reason=answer.get('reason') or answer.get('summary') or '글자 후보 판정 형식이 완전하지 않습니다.')
                    # 검수 묶음이 실행 예외로 끊겼다(image_qc_batches 의 unparsed) — 모델 판정이 아니다(예산 정지 제외).
                    if answer.get('verdict') == 'unparsed' and not answer.get('review_budget_blocked'):
                        receipt['stage'] = 'execution'
        except ClientReviewPending as exc:
            if item.get('engine_failure_rows') is True and getattr(exc, 'engine_failed', False):
                # ★검수 엔진(구독 AGY)이 결과 없이 끝났다(연결 끊김 등) — 사람이 손으로 쓸 답 대기가 아니라 실행 실패다.
                #   화면 글자 검수(_review_preserved_video_text)와 같은 규칙 · 막힌 컷의 «다시»(focus_retry)로 풀린다
                #   (2026-10-19 뇌전구 신고: render_plan 사진 글자 검수가 AGY 끊김 뒤 답 손쓰기로 멈췄다 — 이 opt-in 배선이 빠져 있었다).
                receipt.update(code=getattr(exc, 'engine_code', None) or 'client_review_no_result', stage='execution',
                               reason=(getattr(exc, 'engine_reason', '') or str(exc))[:1200])
            else:
                receipt.update(status='pending',code=exc.code,review_requests=[exc.request])
        except (StepError, OSError, ValueError, KeyError, TypeError) as exc:
            if getattr(exc,'code',None) == 'review_in_progress':
                raise TranscriptionPending('이미지 검수',str(exc),retry_after=2) from exc
            refused = isinstance(exc, ProviderRefusalError)
            receipt.update(code='provider_refused' if refused else getattr(exc,'code','photo_text_execution_failed'),
                           reason=str(exc)[:1200])
            if getattr(exc,'review_budget_blocked',None):
                receipt['review_budget_blocked'] = exc.review_budget_blocked
            # 판정(모델 답)이 아니라 실행이 끊긴 것 — 화면 글자 검수와 같은 규칙(거부·예산 정지는 제외).
            elif not refused:
                receipt['stage'] = 'execution'
        out[usage] = receipt
    return out


def _measure_selected_video_text(cut, item, directory):
    """Reinspect text on the selected source/grid/content, without choosing a face."""
    import subject_focus
    binding = cut['selected_text_measurement']
    if not isinstance(binding, dict) or subject_focus._sha(cut['src']) != binding.get('source_identity'):
        raise StepError('선택 이후 원본 바이트가 바뀌었습니다. 기존 글자 검수를 사용하지 않습니다.')
    policy = binding['policy']
    subject_focus._policy({'policy': policy})
    paths, _, _ = subject_focus._frames(cut, directory, policy)
    indices = binding['frame_indices']
    if (not isinstance(indices, list) or not indices
            or any(type(i) is not int or not 0 <= i < len(paths) for i in indices)
            or indices != sorted(set(indices))):
        raise StepError('글자 검수의 표본이 원래 선택한 영상 프레임 격자와 다릅니다.')
    measured, _, samples = subject_focus._measure(cut, paths, indices, directory, item,
                                                  content=binding['content'], annotate=False)
    if measured['size'] != binding['size'] or subject_focus._sha(cut['src']) != binding['source_identity']:
        raise StepError('글자 검수 중 선택된 원본 크기 또는 바이트가 바뀌었습니다.')
    measured['source_identity'] = binding['source_identity']
    view=binding.get('scene_view')
    if view is not None:
        if (not isinstance(view,dict) or view.get('version')!=2
                or any(view.get(k)!=binding[k] for k in ('source_identity','size','content','frame_indices'))
                or view.get('frame_grid')!=dict(start=cut['start'],fps=cut['fps'],nframes=len(paths))):
            raise StepError('장면 보기 검수가 선택된 원본·표본·crop과 다릅니다.')
        candidates=view.get('candidates')
        if (not isinstance(candidates,list) or not 1<=len(candidates)<=3
                or any(not isinstance(c,dict) for c in candidates)
                or [c.get('id') for c in candidates]!=list(range(len(candidates)))):
            raise StepError('장면 보기 후보 목록이 올바르지 않습니다.')
        bx,by,bw,bh=binding['content']
        for candidate in candidates:
            rect=candidate.get('view')
            if (not subject_focus._box(rect,*binding['size'])
                    or any(type(v) not in (int,float) or int(v)!=v for v in rect)):
                raise StepError('장면 보기 영역이 실제 원본 알맹이 밖입니다.')
            x,y,w,h=rect
            if x<bx or y<by or x+w>bx+bw or y+h>by+bh:
                raise StepError('장면 보기 영역이 실제 원본 알맹이 밖입니다.')
    return measured, [a['path'] for a in samples]


def review_film_frames(item, headers=None):
    """Use existing visual QC to select detector IDs, never model-invented coordinates."""
    item = review_execution_settings(item)
    if item.get('preserved_video_text_review') is True:
        return _review_preserved_video_text(item,headers)
    if item.get('preserved_text_review') is True:
        return _review_preserved_photo_text(item, headers)
    context_text = item.get('film_text_policy') == 'film_context_text_v1'
    complete = _film_context_text_complete if context_text else _film_qc_complete
    import hashlib,statistics
    from pathlib import Path
    from PIL import Image,ImageDraw
    root=Path(item['out_dir']);root.mkdir(parents=True,exist_ok=True)
    config=item['photo_review'];out={}
    for index,cut in enumerate(item['cuts']):
        directory=root/str(cut['card']).replace('#','_');directory.mkdir(exist_ok=True)
        measurement=dict(cut,tmp=str(directory),framevision=item['framevision'])
        if item.get('framevision_cache'):
            measurement['framevision_cache']=item['framevision_cache']
        selected_text = isinstance(cut.get('selected_text_measurement'), dict)
        if selected_text:
            m, samples = _measure_selected_video_text(cut, item, directory)
        else:
            m = measure_frame(measurement); samples = m.pop('sample_paths')
        scene_view=(cut.get('selected_text_measurement') or {}).get('scene_view')
        if scene_view and not context_text:raise StepError('장면 보기의 글자 분류 계약이 없습니다.')
        metadata=[];images=[];digest=hashlib.sha256(b'film-original-and-marked-pairs-v2')
        for j,(faces,texts) in enumerate(zip(m['face_candidates'],m['text_candidates'])):
            src=Path(samples[j])
            with Image.open(src) as original:
                im=original.convert('RGB')
            draw=ImageDraw.Draw(im)
            for kind,boxes,color in (('F',faces,'lime'),('T',texts,'red')):
                for n,(x,y,w,h) in enumerate(boxes):
                    draw.rectangle([x,y,x+w,y+h],outline=color,width=3)
                    draw.text((max(0,x),max(0,y-14)),f'{kind}{n}',fill=color,stroke_width=1,stroke_fill='black')
            annotated=Path(_frozen_png(im,directory))
            digest.update(src.read_bytes());digest.update(annotated.read_bytes())
            paths=[src,annotated];meta={'candidateNumber':j+1,'faces':faces,'texts':texts}
            if scene_view:
                cx,cy,_,_=m['content'];views=[]
                for candidate in scene_view['candidates']:
                    x,y,w,h=candidate['view']
                    with Image.open(src) as original:
                        proposed=Path(_frozen_png(original.crop((x-cx,y-cy,x-cx+w,y-cy+h)),directory))
                    paths.append(proposed);digest.update(proposed.read_bytes())
                    views.append(dict(candidate_id=candidate['id'],view=[x-cx,y-cy,w,h]))
                meta.update(scene_views=views,frame_index=scene_view['frame_indices'][j])
            images.append([{'url':_file_uri(p),'mime':'image/png'} for p in paths])
            metadata.append(meta)
        prompt=config['prompt']+'\n원래 컷 문맥: '+str(cut.get('context') or '')+'\n실측 후보 목록: '+json.dumps(metadata,ensure_ascii=False)
        digest.update(json.dumps(scene_view,sort_keys=True,ensure_ascii=False).encode())
        digest.update(json.dumps(dict(review_semantic_config(config),prompt=prompt,
            **({'film_text_policy':item['film_text_policy']} if context_text else {})),
            sort_keys=True,ensure_ascii=False).encode())
        cache=root/(digest.hexdigest()+'.json')
        try:result=json.loads(cache.read_text(encoding='utf-8'))
        except (OSError,ValueError):result=None
        if not complete(result,metadata):
            job=dict(config,prompt=prompt,index=index,out=str(cache)+'.raw',
                     qc_contract='film_frames_v1')
            units=[{'metadata':m,'images':pair, 'labels':[
                        'candidateNumber='+str(m['candidateNumber'])+' original pixels',
                        'candidateNumber='+str(m['candidateNumber'])+' marked F/T IDs']+
                        (['candidateNumber='+str(m['candidateNumber'])+' actual scene view candidate_id='+str(v['candidate_id']) for v in m['scene_views']] if scene_view else [])}
                   for m,pair in zip(metadata,images)]
            def prompt_for(selected):
                return (config['prompt']+'\n원래 컷 문맥: '+str(cut.get('context') or '')+
                        '\n실측 후보 목록: '+json.dumps(selected,ensure_ascii=False))
            try:
                result=image_qc_batches(job,units,headers or {},prompt_for=prompt_for,
                                        result_validator=complete,allow_provider=item.get('allow_provider',True),
                                        review_policy=item['review_policy'], client=item['review_client'],
                                        client_replies=item['focus_review_replies'],
                                        review_budget=item['_review_budget'])
            except ClientReviewPending as exc:
                out[str(cut['card'])]=dict(m,semantic_review={'status':'pending',
                    'code':exc.code,'review_requests':[exc.request],'automatic_retry':False})
                continue
            except StepError as exc:
                result={'verdict':'unparsed','reason':str(exc)[:1200],
                        'code':'provider_refused' if isinstance(exc,ProviderRefusalError) else getattr(exc,'code','review_execution_failed'),
                        **({'review_budget_blocked':exc.review_budget_blocked} if getattr(exc,'review_budget_blocked',None) else {})}
            if complete(result,metadata):_photo_write_state(str(cache),result)
        decisions=result.get('decisions') or []
        if result.get('verdict')!='accepted' or not complete(result,metadata):
            out[str(cut['card'])]=dict(m,semantic_review={'status':'unchecked','reason':result.get('reason') or result.get('summary'),
                'code':result.get('code') or 'film_review_unresolved','decisions':result.get('decisions') or [],
                'batches':result.get('batches') or [],'automatic_retry':False,
                **({'review_budget_blocked':result['review_budget_blocked']} if result.get('review_budget_blocked') else {})});continue
        track=[];times=[];texts=[]
        for decision in decisions:
            n=decision.get('candidateNumber');fid=decision.get('faceId');tids=decision.get('textIds')
            faces=m['face_candidates'][n-1];candidates=m['text_candidates'][n-1]
            if fid is not None:track.append((n-1,faces[fid]))
            texts.extend(candidates[t] for t in tids)
        track.sort();times=[m['sample_times'][n] for n,_ in track];faces=[f for _,f in track]
        face=[statistics.median(f[j] for f in faces) for j in range(4)] if faces else None
        m.update(face=face,face_samples=faces,face_sample_times=times,text_boxes=texts,
                 subject_sample_coverage=len(faces)/max(1,len(metadata)),subject_detected=bool(face),
                 by='face' if face else 'unresolved',semantic_review={'status':'accepted','summary':result.get('summary'),'decisions':decisions,'engine':result.get('_engine')})
        if context_text:m['semantic_review']['text_policy']=item['film_text_policy']
        if scene_view:
            checked=[];preserved=[];cx,cy,_,_=m['content']
            for decision in sorted(decisions,key=lambda d:d['candidateNumber']):
                j=decision['candidateNumber']-1
                checked.append(dict(frame_index=scene_view['frame_indices'][j],candidates=decision['sceneViews']))
                preserved.extend([x+cx,y+cy,w,h] for x,y,w,h in
                                 (m['text_candidates'][j][tid] for tid in decision['preservedTextIds']))
            # Candidate rectangles are server supplied. Choose the first with
            # complete approval whose pixels also exclude the classified overlay.
            def overlay_free(view):
                x,y,w,h=view
                return all(x+w<=tx+cx or tx+cx+tw<=x or y+h<=ty+cy or ty+cy+th<=y
                           for tx,ty,tw,th in m['text_boxes'])
            accepted=[c['id'] for c in scene_view['candidates']
                      if all(d['candidates'][c['id']]['accepted'] for d in checked)
                      and overlay_free(c['view'])]
            m['scene_view_review']=dict(binding=scene_view,status='accepted' if accepted else 'rejected',
                selected_candidate=accepted[0] if accepted else None,decisions=checked,preserved_text_boxes=preserved)
        if face:m['subject']=[(face[0]+face[2]/2)/m['content'][2],(face[1]+face[3]/2)/m['content'][3]]
        out[str(cut['card'])]=m
    return out


def _photo_selection_metadata(verdict):
    selected = verdict.get("selectedCandidateNumber")
    decision = next((d for d in verdict.get("decisions") or []
                     if isinstance(d, dict) and d.get("candidateNumber") == selected), {})
    return {"photo_review": {"verdict": verdict.get("verdict"),
                             "engine": verdict.get("_engine"),
                             "summary": verdict.get("summary"),
                             "decision": decision,
                             **({"identity_verified": False, "source_context": "provided_metadata_only"}
                                if "identity_verified" in verdict else {})},
            "preserve_text": decision.get("preserve_text") is True}


def _photo_retry_queries(item, verdict):
    """Only reuse words present in the supplied story; never invent affiliations."""
    context = str((item.get('photo_review') or {}).get('query_context') or '').casefold()
    hints = []
    for hint in (verdict or {}).get('retryQueryHints') or []:
        if not isinstance(hint, str) or not 1 <= len(hint) <= 100:
            continue
        terms = re.findall(r"[^\W_]+", hint.casefold(), flags=re.UNICODE)
        if terms and all(term in context for term in terms) and hint not in hints:
            hints.append(hint)
        if len(hints) == 3:
            break
    return hints + [q for q in item.get('queries') or [] if q not in hints]


def _photo_search_recipe(item):
    import hashlib
    request = {k: v for k, v in item.items() if k not in ('exclude', 'current', 'source_compatibility')}
    key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False,
                                   separators=(',', ':')).encode()).hexdigest()
    return request, key


def _photo_recipe_variants(item):
    """Only declared historical source transport may share a semantic receipt."""
    current = {k: v for k, v in item.items() if k != 'source_compatibility'}
    variants = [current]
    for transport in item.get('source_compatibility') or []:
        # 두 모양만 받는다: 9/11 이전 브라우저 판({sources, providers, google}) · 9/11~9/28 API 판({sources, source_policy}).
        #   2026-09-28 serper→agy 교체 때 API 판을 더했다 — 이미 고른 사진·검수 답변을 다시 찾거나 다시 검수하지 않게.
        if not isinstance(transport, dict) or set(transport) not in ({'sources', 'providers', 'google'},
                                                                    {'sources', 'source_policy'}):
            continue
        previous = {k: v for k, v in current.items()
                    if k not in ('sources', 'providers', 'google', 'source_policy')}
        variants.append(dict(previous, **transport))
    # The previous September 11 fix only disabled attended CAPTCHA waiting.
    for previous in list(variants):
        attended = copy.deepcopy(previous)
        for source in attended.get('sources') or []:
            if (str(source.get('kind') or '').lower() in ('cdp_google', 'google_cdp', 'google')
                    and source.get('block_action') == 'next_source' and source.get('attend_on_block') is False):
                source.pop('block_action')
                source['attend_on_block'] = True
        if attended != previous:
            variants.append(attended)
    return variants


def _photo_image_mime(path):
    """Read the downloaded bytes, including WebP and misleading URL suffixes."""
    from PIL import Image
    with Image.open(path) as image:
        mime = {'PNG':'image/png', 'JPEG':'image/jpeg', 'WEBP':'image/webp'}.get(image.format)
    if mime is None:
        raise StepError('사진 검수에서 지원하지 않는 이미지 형식입니다.')
    return mime



# ── 인물형 소재 탐색 — 공개 아카이브·유튜브에서 **동영상 후보**를 찾는다 (2026-09-16) ──
#
# ■ 왜 여기가 생겼나
#     인물형 새 경로(공통 편집기)의 1단계 «소재 탐색» 이 서버 스텁이었다 — 인물이 누구든
#     같은 NASA 주소 하나와 **존재하지 않는** archive.org 주소를 «후보» 라고 돌려줬다.
#     후보를 실제로 찾는 자리가 어디에도 없었다. 여기가 그 자리다.
# ■ 노하우 경계
#     어떤 소스를 어떤 순서로, 검색어 사다리를 무엇으로, 몇 개까지 — 전부 **서버가 준다**
#     (`sources`·`queries`·`want`). 실행기는 그 규약대로 공개 API 를 부르고 제목·길이·
#     출처·사용조건을 **적기만** 한다. 고르지 않는다(판정은 서버 `rank_source_candidates`
#     와 저자가 한다).
# ■ 소스 종류 (전부 열쇠 없음)
#     · ytsearch                 yt-dlp 의 유튜브 검색. 제목·길이·채널·조회수
#     · nasa_images              images-api.nasa.gov (퍼블릭 도메인). 자산 목록에서 mp4 를 고른다
#     · internet_archive         archive.org advancedsearch. yt-dlp 가 details 주소를 받는다
#     · wikimedia_commons_video  commons.wikimedia.org API (UA 정책 — 서버가 준 UA 로 부른다)
# ■ 같은 질의는 작업 폴더 `source-search.json` 에 남긴다 — 재개할 때 다시 안 부른다.
# ■ 한 소스가 죽어도 나머지는 돈다. 못 부른 소스는 `errors` 에 이름·사유를 남긴다 —
#   «0건» 과 «못 물었다» 를 같은 말로 쓰지 않는다(§«안 쟀다» 와 «재 봤더니 0개»).

def _runtime_seconds(value):
    """`HH:MM:SS`·`MM:SS`·초 문자열·숫자 → 초. 못 읽으면 None (0 이 아니다)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    try:
        if ":" in s:
            parts = [float(x) for x in s.split(":")]
            total = 0.0
            for part in parts:
                total = total * 60 + part
            return total
        return float(s)
    except ValueError:
        return None


def _video_candidate(provider, key, title, url, **extra):
    row = {"id": f"{provider}:{key}", "provider": provider, "kind": "video",
           "title": str(title or "").strip() or key, "url": url}
    row.update({k: v for k, v in extra.items() if v is not None})
    return row


def _ytsearch_candidates(src, query, per_source):
    """유튜브 검색 — `yt-dlp "ytsearchN:질의" --flat-playlist -j`. 열쇠도 로그인도 없다.

    ★flat 모드라 라이선스 칸이 비어 온다(유튜브는 CC 표시가 있을 때만 준다). «확인 안 됨»
      으로 적는다 — 없는 값을 «표준 라이선스» 로 지어내지 않는다.
    """
    count = int(src.get("count") or per_source or 8)
    argv = ["yt-dlp", f"ytsearch{count}:{query}", "--flat-playlist", "-j", "--no-warnings", "-q"]
    # yt-dlp 도 한 문(_spawn)으로 — 윈도우 .cmd/모듈 머리·EJS 런타임 환경·옛 판 403 의 최신 판 한 번 다시 받기가 여기서만 붙는다
    #   (날 것으로 부르면 yt-dlp 가 모듈로만 있는 PC 에서 검색이 FileNotFoundError 로 죽었다 · test_runner_win [8]).
    p = _spawn(argv, capture_output=True, text=True, encoding="utf-8",
               errors="replace", timeout=int(src.get("timeout") or 180))
    if p.returncode != 0 and not p.stdout.strip():
        raise RuntimeError(err_gist(p.stderr, 300) or f"yt-dlp exit {p.returncode}")
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        url = o.get("webpage_url") or o.get("url")
        if not url or not o.get("id"):
            continue
        out.append(_video_candidate(
            "youtube", o["id"], o.get("title"), url,
            page_url=url, duration=_runtime_seconds(o.get("duration")),
            author=o.get("channel") or o.get("uploader"), view_count=o.get("view_count"),
            license=o.get("license") or "확인 안 됨 — 유튜브 영상은 사용 조건을 저자가 확인한다",
            query=query))
    return out


def _nasa_video_candidates(src, query, ua, per_source, pace):
    """NASA 영상 도서관 — 검색 → 항목마다 자산 목록(collection.json)에서 mp4 하나."""
    import urllib.parse
    headers = {"User-Agent": ua}
    data = get_json(src["search"].replace("{q}", urllib.parse.quote(query)), headers, timeout=30)
    items = ((data.get("collection") or {}).get("items") or [])
    prefer = list(src.get("prefer") or ["~orig.mp4", "~large.mp4", "~medium.mp4", "~mobile.mp4"])
    out = []
    for it in items[:per_source]:
        rows = it.get("data") or []
        meta = rows[0] if rows and isinstance(rows[0], dict) else {}
        if meta.get("media_type") != "video" or not it.get("href"):
            continue
        time.sleep(pace)
        try:
            # ★자산 목록 주소에도 공백이 있다(`/video/katherine Johnson OBIT 1/collection.json`) —
            #   urllib 은 «control characters» 로 거부한다(실측 5/8 실패). 먼저 인코딩한다.
            href = urllib.parse.quote(str(it["href"]).replace("http://", "https://", 1), safe=":/?&=%~")
            assets = get_json(href, headers, timeout=30)
        except Exception as exc:                                  # noqa: BLE001
            _progress(f"    (NASA 자산 목록 실패 — {meta.get('nasa_id')}: {str(exc)[:80]})")
            continue
        chosen = None
        for suffix in prefer:
            chosen = next((a for a in assets if isinstance(a, str) and a.endswith(suffix)), None)
            if chosen:
                break
        if not chosen:
            continue
        # ★주소에 공백이 있다(«katherine Johnson OBIT 1~orig.mp4»). yt-dlp·urllib 이 그대로는 못 연다.
        chosen = urllib.parse.quote(chosen.replace("http://", "https://", 1), safe=":/?&=%~")
        out.append(_video_candidate(
            "nasa", meta.get("nasa_id") or chosen, meta.get("title"), chosen,
            page_url=f"https://images.nasa.gov/details/{urllib.parse.quote(str(meta.get('nasa_id') or ''))}",
            author=meta.get("center"), date=meta.get("date_created"),
            description=(meta.get("description") or "")[:300],
            license=src.get("license") or "Public Domain (NASA Media Usage Guidelines)",
            license_url=src.get("license_url") or "https://www.nasa.gov/nasa-brand-center/images-and-media/",
            query=query))
    return out


def _archive_video_candidates(src, query, ua, per_source):
    """인터넷 아카이브 — advancedsearch(JSON). 받는 주소는 details 페이지(yt-dlp 가 안다)."""
    import urllib.parse
    data = get_json(src["search"].replace("{q}", urllib.parse.quote(query)), {"User-Agent": ua}, timeout=30)
    docs = ((data.get("response") or {}).get("docs") or [])
    out = []
    for d in docs[:per_source]:
        ident = d.get("identifier")
        if not ident:
            continue
        page = (src.get("page") or "https://archive.org/details/{id}").replace("{id}", ident)
        creator = d.get("creator")
        if isinstance(creator, list):
            creator = ", ".join(str(x) for x in creator[:3])
        out.append(_video_candidate(
            "archive.org", ident, d.get("title"), page, page_url=page,
            duration=_runtime_seconds(d.get("runtime")), author=creator,
            downloads=d.get("downloads"),
            license=("아카이브 항목별 표기" + (f" — {d['licenseurl']}" if d.get("licenseurl") else " (라이선스 표기 없음 — 저자가 확인)")),
            license_url=d.get("licenseurl"), query=query))
    return out


def _commons_video_candidates(src, query, ua, per_source):
    """위키미디어 커먼즈 — 검색(list=search, 파일 이름공간) → imageinfo(주소·크기·라이선스)."""
    import urllib.parse
    headers = {"User-Agent": ua}
    data = get_json(src["search"].replace("{q}", urllib.parse.quote(query)), headers, timeout=30)
    titles = [r.get("title") for r in ((data.get("query") or {}).get("search") or []) if r.get("title")]
    titles = titles[:per_source]
    if not titles:
        return []
    info = get_json(src["info"].replace("{titles}", urllib.parse.quote("|".join(titles))), headers, timeout=30)
    out = []
    for page in ((info.get("query") or {}).get("pages") or {}).values():
        ii = (page.get("imageinfo") or [{}])[0]
        if not ii.get("url") or not str(ii.get("mime") or "").startswith("video/"):
            continue
        ext = ii.get("extmetadata") or {}
        lic = (ext.get("LicenseShortName") or {}).get("value")
        out.append(_video_candidate(
            "commons", page.get("title") or ii["url"], (page.get("title") or "").replace("File:", ""), ii["url"],
            page_url=ii.get("descriptionurl"), duration=_runtime_seconds(ii.get("duration")),
            width=ii.get("width"), height=ii.get("height"),
            author=(ext.get("Artist") or {}).get("value"),
            license=lic or "라이선스 표기 없음 — 저자가 확인", license_url=(ext.get("LicenseUrl") or {}).get("value"),
            query=query))
    return out


def search_videos(item):
    """서버가 준 소스·검색어 사다리로 **동영상 후보**를 모아 목록으로 돌려준다.

    돌려주는 것: {"candidates": [...], "errors": [{"source","query","error"}], "queries": [...],
                  "cache": 경로, "from_cache": bool}
    ★사다리는 위에서부터 — 한 소스가 1건이라도 내면 그 소스는 다음 칸으로 안 내려간다.
    ★같은 (소스·사다리) 질의는 캐시에서 읽는다. 지우면 다시 검색한다.
    """
    import hashlib
    subject = str(item.get("subject") or "").strip()
    queries = [str(q).strip() for q in (item.get("queries") or []) if str(q).strip()] or ([subject] if subject else [])
    sources = [s for s in (item.get("sources") or []) if isinstance(s, dict) and s.get("kind")]
    if not queries or not sources:
        raise StepError("소재 탐색 일감에 검색어(queries)나 소스(sources)가 없다 — 서버 응답을 확인하라")
    want = int(item.get("want") or 24)
    per_source = int(item.get("per_source") or 8)
    pace = float(item.get("pace") or 0.5)
    ua = item.get("ua") or _UA
    outdir = os.path.abspath(item.get("out_dir") or ".")
    os.makedirs(outdir, exist_ok=True)
    cache_path = os.path.join(outdir, "source-search.json")
    key = hashlib.sha256(json.dumps({"subject": subject, "queries": queries,
                                     "sources": [s.get("kind") for s in sources], "want": want},
                                    sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    try:
        with open(cache_path, encoding="utf-8") as fh:
            cached = json.load(fh)
        if isinstance(cached, dict) and cached.get("key") == key and isinstance(cached.get("candidates"), list):
            _progress(f"  [소재 탐색] 캐시에서 {len(cached['candidates'])}건 (다시 검색하지 않는다) — {cache_path}")
            return {**cached, "cache": cache_path, "from_cache": True}
    except (OSError, ValueError):
        pass
    found, errors, seen = [], [], set()
    for src in sources:
        kind = src["kind"]
        got_any = False
        for q in queries:
            try:
                if kind == "ytsearch":
                    rows = _ytsearch_candidates(src, q, per_source)
                elif kind == "nasa_images":
                    rows = _nasa_video_candidates(src, q, ua, per_source, pace)
                elif kind == "internet_archive":
                    rows = _archive_video_candidates(src, q, ua, per_source)
                elif kind == "wikimedia_commons_video":
                    rows = _commons_video_candidates(src, q, ua, per_source)
                else:
                    errors.append({"source": kind, "query": q, "error": "실행기가 모르는 소스 종류"})
                    break
            except Exception as exc:                              # noqa: BLE001
                errors.append({"source": kind, "query": q, "error": str(exc)[:200]})
                _progress(f"  [소재 탐색] {kind} «{q}» 실패 — {str(exc)[:120]}")
                continue
            fresh = [r for r in rows if r["url"] not in seen]
            for r in fresh:
                seen.add(r["url"])
            found.extend(fresh)
            _progress(f"  [소재 탐색] {kind} «{q}» → {len(fresh)}건")
            if rows:
                got_any = True
                break
        if not got_any and not any(e["source"] == kind for e in errors):
            errors.append({"source": kind, "query": queries[-1], "error": "0건"})
    result = {"key": key, "subject": subject, "queries": queries, "candidates": found[:want],
              "errors": errors, "searched_at": time.time()}
    try:
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return {**result, "cache": cache_path, "from_cache": False}


def search_images(item, seen=None, headers=None, active_recipe_keys=None):
    """Search with decoded-content exclusion and durable, request-specific results.

    Completed requests reuse verified local bytes; exhausted requests do not silently
    restart on resume. New queries/exclusions produce a new request, preserving old
    successful files. The local manifest never goes into the server payload.
    """
    import hashlib
    outdir = os.path.abspath(item.get('out_dir') or 'photo')
    os.makedirs(outdir, exist_ok=True)
    state_path = os.path.join(outdir, '.photo-search.json')
    state = _photo_read_state(state_path)
    excluded = []
    excluded_sources = {_photo_source_key(e.get('source')) for e in item.get('exclude') or [] if e.get('source')}
    for entry in item.get('exclude') or []:
        try:
            excluded.append(photo_signature(entry['path']))
        except (OSError, ValueError, KeyError):
            continue
    request, recipe_key = _photo_search_recipe(item)
    request['excluded_signatures'] = excluded
    key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()
    cached = state['requests'].get(key)
    recipe_keys = {_photo_search_recipe(previous)[1] for previous in _photo_recipe_variants(item)}
    # Earlier-slot recovery changes excludes, not this slot's successful recipe.
    # Reuse only a verified selection that remains distinct from the new excludes.
    candidates = ([cached] if isinstance(cached, dict) else []) + [
        r for r in state['requests'].values()
        if r is not cached and r.get('recipe_key') in recipe_keys]
    for record in candidates:
        # An empty network result has not completed selection. Only a completed
        # visual rejection retains its bounded-attempt receipt across resumes.
        rejected = isinstance(record.get('review'), dict) and record['review'].get('verdict') == 'retry'
        valid = bool(record.get('photos')) or rejected
        for row in record.get('photos', []):
            valid &= _photo_source_key(row.get('source')) not in excluded_sources
            try:
                with open(row['path'], 'rb') as fh:
                    valid &= hashlib.sha256(fh.read()).hexdigest() == row['_sha256']
                signature = row.get('_signature') or photo_signature(row['path'])
                valid &= not any(same_photo(signature, other) for other in excluded)
            except (OSError, KeyError):
                valid = False
        if valid:
            if record.get('recipe_key') != recipe_key or cached is not record:
                record = dict(record, recipe_key=recipe_key)
                state['requests'][key] = record
                _photo_write_state(state_path, state)
            photos = [{k: v for k, v in r.items() if not k.startswith('_')}
                      for r in record.get('photos', [])]
            if isinstance(seen, set):
                seen.update(r['source'] for r in photos)
            return photos
    if not isinstance(cached, dict):
        cached = next((record for record in candidates if record.get('candidate_batches')), None)
    used = seen if isinstance(seen, set) else set()
    used.update(str(r['source']) for r in item.get('exclude') or [] if r.get('source'))
    # Signatures of earlier cards survive execute()/process boundaries.
    for other_key, record in state['requests'].items():
        if other_key != key and (active_recipe_keys is None or record.get('recipe_key') in active_recipe_keys):
            used.update(str(r['source']) for r in record.get('photos', []) if r.get('source'))
            excluded.extend(r['_signature'] for r in record.get('photos', [])
                            if r.get('_signature'))
    working = dict(item, _photo_excluded=excluded)
    photos = []
    checked = None
    review = item.get('photo_review')
    if review:
        # Compare several candidates at once using the existing QC engine. At most
        # two rounds; all rejected pictures stay excluded during the second round.
        rounds = min(2, max(1, int(review.get('rounds') or 2)))
        budget = max(1, min(100, int(item.get('max_candidates') or 24)))
        rounds = min(rounds, budget)
        candidate_seen = set(used)
        batches = dict((cached or {}).get('candidate_batches') or {})
        empty_rounds = set((cached or {}).get('empty_rounds') or [])
        def save_batches():
            state['requests'][key] = dict(recipe_key=recipe_key, candidate_batches=batches,
                                          empty_rounds=sorted(empty_rounds))
            _photo_write_state(state_path, state)
        def valid_batch(batch):
            try:
                return bool(batch) and all(_image_file_sha(r['path']) == r['_sha256'] for r in batch)
            except (OSError, KeyError, TypeError):
                return False
        for _round in range(rounds):
            round_item = dict(working, want=4, max_candidates=max(1, budget // rounds))
            if (item.get('source_policy') or {}).get('rotate_review_sources'):
                sources = list(round_item.get('sources') or [])
                # ★agy 구글도 «두 번째 API» 자리다(2026-09-28 serper 자리 교체) — 2라운드가 실제로 그 출처를 먼저 쓴다.
                indices = [i for i, src in enumerate(sources) if src.get('kind') in ('json_api', 'agy_google')]
                if indices:
                    apis = [sources[i] for i in indices]
                    offset = _round % len(apis)
                    for i, src in zip(indices, apis[offset:] + apis[:offset]): sources[i] = src
                    round_item['sources'] = sources
            round_keys = [hashlib.sha256(json.dumps(dict(item=previous, seen=sorted(candidate_seen)),
                sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                for previous in _photo_recipe_variants(round_item)]
            round_key = round_keys[0]
            stored_batch = next((batches[k] for k in round_keys if batches.get(k)), [])
            # Resume the valid later batch without downloading the exhausted
            # first source again. Empty-only acquisition remains retryable after
            # credentials/source availability change; it is not a model verdict.
            if (any(k in empty_rounds for k in round_keys)
                    and any(valid_batch(value) for value in batches.values())):
                continue
            batch = []
            try:
                if stored_batch and all(_image_file_sha(row['path']) == row['_sha256'] for row in stored_batch):
                    batch = [{k:v for k,v in row.items() if not k.startswith('_')} for row in stored_batch]
                    candidate_seen.update(row['source'] for row in batch)
                    batches[round_key] = stored_batch
                    empty_rounds.difference_update(round_keys)
                    save_batches()
            except (OSError, KeyError, TypeError):
                pass  # Changed/missing bytes are new evidence, never an old completed review.
            if not batch:
                batch = _search_images_fetch(round_item, seen=candidate_seen)
                if batch:
                    batches[round_key] = [dict(row, _sha256=_image_file_sha(row['path'])) for row in batch]
                    empty_rounds.difference_update(round_keys)
                    # Commit acquired bytes before review can hand off or fail.
                    # A fresh CLI process must submit the same candidate IDs/SHA
                    # without repeating a search, CAPTCHA or download.
                    save_batches()
            if not batch:
                if (item.get('source_policy') or {}).get('rotate_review_sources'):
                    empty_rounds.add(round_key)
                    save_batches()
                    continue  # Next API uses the other existing half of the budget.
                break
            checked = review_photos(item, batch, headers=headers)
            if checked.get('verdict') == 'accepted':
                chosen = batch[checked['selectedCandidateNumber'] - 1]
                photos = [dict(chosen, **_photo_selection_metadata(checked))]
                used.add(chosen['source'])
                break
            working['_photo_excluded'].extend(photo_signature(p['path']) for p in batch)
            working['queries'] = _photo_retry_queries(working, checked)
            if checked.get('verdict') != 'retry':
                break
    else:
        photos = _search_images_fetch(working, seen=used)
    stored = []
    for row in photos:
        with open(row['path'], 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        stored.append(dict(row, _signature=photo_signature(row['path']), _sha256=digest))
    if stored or (isinstance(checked, dict) and checked.get('verdict') == 'retry'):
        state['requests'][key] = {'photos': stored, 'review': checked, 'recipe_key': recipe_key}
        _photo_write_state(state_path, state)
    return photos


def recover_photos(item, headers=None):
    """Whole-film A/B/C/A check and bounded acquisition for only failing shots.

    The server supplies the search recipe and explicit framing failures. Original
    assets are never overwritten. All original unique pictures are excluded before
    replacement starts, so a repair cannot steal a later successful shot's picture.
    """
    jobs = item.get('jobs') or []
    # The existing QC engine is used in a bounded pool, with identical questions
    # coalesced before scheduling so repeated shots do not repeat paid review.
    review_requests, review_keys = {}, {}
    for job in jobs:
        if not job.get('photo_review'):
            continue
        try:
            _prompt, key = _photo_review_request(job, [job.get('current') or {}])
        except (OSError, KeyError, ValueError):
            continue
        review_requests.setdefault(key, job)
        review_keys[int(job['card'])] = key
    verdicts = {}
    if review_requests:
        from concurrent.futures import ThreadPoolExecutor
        def inspect_one(pair):
            key, job = pair
            return key, review_photos(job, [job['current']], headers=headers)
        workers = max(1, min(6, int(item.get('review_parallel') or 1)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            verdicts.update(pool.map(review_context_worker(inspect_one), review_requests.items()))
    known, failed, checked, originals, reviewed = [], [], [], [], {}
    known_sources = set()

    for job in jobs:
        card = int(job['card'])
        current = job.get('current') or {}
        try:
            sig = photo_signature(current['path'])
        except (OSError, KeyError, ValueError):
            failed.append((job, 'missing_photo'))
            continue
        checked.append(card)
        source_key = _photo_source_key(current.get('source'))
        duplicate = bool(source_key and source_key in known_sources) or any(same_photo(sig, s) for s in known)
        if source_key:
            known_sources.add(source_key)
        if not duplicate:
            known.append(sig)
        originals.append(current)
        verdict = verdicts.get(review_keys.get(card))
        if verdict and verdict.get('verdict') == 'accepted':
            reviewed[str(card)] = _photo_selection_metadata(verdict)
        preserve_text = (reviewed.get(str(card)) or {}).get('preserve_text') is True
        replace = job.get('replace') and not (preserve_text and job.get('reason') == 'text_overlap')
        if verdict and verdict.get('verdict') not in ('accepted', 'retry'):
            failed.append((job, 'review_unchecked'))
        elif duplicate or replace or (verdict and verdict.get('verdict') == 'retry'):
            if verdict and verdict.get('verdict') == 'retry':
                job = dict(job, queries=_photo_retry_queries(job, verdict))
            source_missing = any(d.get('reason_code') == 'subject_source_unverified'
                                 for d in (verdict or {}).get('decisions') or [])
            failed.append((job, 'subject_source_unverified' if source_missing else
                           job.get('reason') or ('duplicate_photo' if duplicate else 'unrelated_photo')))
    replacements, unresolved = {}, []
    requests = {int(job['card']): {k: v for k, v in job.items()
                                  if k not in ('current', 'replace', 'reason')}
                for job, reason in failed if reason != 'review_unchecked'}
    active_recipes = {_photo_search_recipe(request)[1] for request in requests.values()}
    for job, reason in failed:
        card = int(job['card'])
        if reason == 'review_unchecked':
            unresolved.append({'card': card, 'reason': reason,
                               'why': '사진 검수 도구를 실행하지 못했습니다. 검수 통과로 처리하지 않았습니다.'})
            continue
        request = dict(requests[card], exclude=originals + list(replacements.values()))
        # Reserve successful pending slots from this recovery, while ignoring
        # historical selections belonging to superseded slots or search recipes.
        photos = search_images(request, headers=headers, active_recipe_keys=active_recipes)
        if photos:
            selected = dict(photos[0])
            metadata = selected.get('source_metadata') or {}
            # A cached photo can have a real caption but no HTML title. Use that
            # source text as its timeline name; never promote search words.
            if not str(selected.get('title') or '').strip():
                selected['title'] = str(metadata.get('caption') or metadata.get('title') or '').strip()
            replacements[str(card)] = dict(selected, id=f'photo_recovery_{card}',
                                            kind='image', card=card,
                                            clip_index=int(job.get('clip_index', card - 1)))
        else:
            unresolved.append({'card': card, 'reason': reason,
                               'candidate_limit': int(job.get('max_candidates') or 24),
                               'why': '다른 사진 후보를 소진했습니다. 이미 성공한 사진은 보존했습니다.'})
    return {'replacements': replacements, 'unresolved': unresolved, 'checked': checked,
            'reviewed': reviewed}


def _search_images_fetch(item, seen=None):
    """서버가 시킨 대로 **사진을 검색해서 받아온다.** 판정은 서버가 한다.

    ■ 이 함수에 채널 규격이 없다
        검색어(사다리)·어느 API·어디를 읽을지(`pick`)·몇 장·최소 높이·저장 경로 —
        **전부 서버가 준다.** 여기 있는 것은 HTTP GET · JSON 훑기 · 내려받기 ·
        크기 재기(일반 기술)뿐이다.

    ■ 왜 있나 (2026-08-17)
        서버는 예전부터 컷마다 **검색 사다리**를 만들어 줬는데(`plan_footage`)
        그것을 **실행하는 자가 없어서** 수강생이 손으로 찾았다. 실측: 소재 조달에
        중앙 18.8분 · p90 74.4분 · 최대 4066분(약 2.8일)이 들었다.

    ★못 찾으면 **비워서 돌려준다.** 아무 그림이나 채우면 자막과 무관한 화면이
      오류 없이 완성본까지 간다(이 채널이 반려당한 그 사고다).
    ★한 장이라도 받으면 그 컷은 성공이다 — 전체가 실패해도 나머지는 살린다.

    ★★**같은 그림을 두 컷에 쓰지 않는다** (`seen`). 검색 사다리의 마지막 칸은
      인물명이라, 앞칸이 0건이면 여러 컷이 **같은 사진**으로 떨어진다 —
      실측(2026-08-17): 컷 1과 컷 3이 바이트까지 같은 4096x3072 한 장을 받았다.
      그러면 그 다음에 **컷 튐 게이트가 반려한다**(같은 화면이 잇달아 붙는다).
      부르는 쪽이 `seen` 집합 하나를 넘겨 컷마다 이어 쓴다.
    """
    import urllib.parse
    from PIL import Image
    ua = str(item.get("ua") or "")
    lo = int(item.get("min_h") or 0)
    want = max(1, int(item.get("want") or 1))
    out_dir = item.get("out_dir") or "photo"
    os.makedirs(out_dir, exist_ok=True)
    got = []
    used = seen if isinstance(seen, set) else set()
    attempted = set()
    used_sources = {_photo_source_key(u) for u in used}
    candidate_limit = max(1, min(100, int(item.get('max_candidates') or 24)))
    signatures = list(item.get('_photo_excluded') or [])

    _deny = tuple(str(d).lower() for d in (item.get("deny_domains") or ()))

    def _take(src_url, provider, title, query, license_="", metadata=None):
        """주소 하나를 받아 **실물 크기를 재고** 통과하면 담는다. 실패는 조용히 넘긴다.

        ★**워터마크 도메인은 받기 전에 끊는다.** `min_h` 로는 절대 안 걸러진다 —
          해상도도 용량도 정상이기 때문이다(카드뉴스 실측: 오염 42.9% → 0%).
          목록은 서버가 준다(`deny_domains`) — 실행기에 박으면 서버가 고쳐도 안 따라온다.
        """
        metadata = _normalize_photo_metadata(metadata)
        source_key = _photo_source_key(src_url)
        if len(got) >= want or source_key in used_sources or source_key in attempted or len(attempted) >= candidate_limit:
            return
        if _deny:
            _h = urllib.parse.urlparse(str(src_url)).hostname or ""
            if any(_h == d or _h.endswith("." + d) for d in _deny):
                return
        if (item.get('photo_review') or {}).get('require_subject_evidence'):
            metadata = metadata or {}
            page = metadata.get('page_url') or (_PHOTO_SOURCE_META.get(str(src_url)) or {}).get('page_url')
            if page and not any(metadata.get(k) for k in ('title', 'caption', 'description')):
                metadata = dict(metadata, **_normalize_photo_metadata(_photo_page_evidence(page, str(src_url))))
            if metadata.get('scope') not in ('image_record', 'linked_photo_page') or not any(
                    _metadata_text(metadata.get(k)) for k in ('title', 'caption', 'description')):
                return  # Try the next source/provider; do not pay to guess identity.
        ext = os.path.splitext(urllib.parse.urlparse(source_key).path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = '.image'  # API URLs need not name a file; decoded bytes decide.
        import hashlib
        attempted.add(source_key)
        name = hashlib.sha256(str(src_url).encode()).hexdigest()[:16]
        dst = os.path.join(out_dir, f"c{int(item['card']):03d}_{name}{ext}")
        import tempfile
        fd, candidate = tempfile.mkstemp(prefix='.photo-candidate-', suffix=ext, dir=out_dir)
        os.close(fd)
        try:
            with review_dispatch():
                download(str(src_url), candidate, timeout=40,
                         headers={"User-Agent": ua} if ua else None)
            with Image.open(candidate) as im:
                actual_ext = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}.get(im.format)
                if actual_ext is None:
                    return
                im.load()  # Reject truncated images and HTML before publishing.
                w2, h2 = im.size
            if h2 < lo:
                return
            signature = photo_signature(candidate)
            if any(same_photo(signature, other) for other in signatures):
                return
            # A rejected download must never erase an earlier successful file.
            dst = os.path.join(out_dir, f"c{int(item['card']):03d}_{name}{actual_ext}")
            os.replace(candidate, dst)
        except ProviderRefusalError:
            raise
        except Exception:  # noqa: BLE001
            return
        finally:
            if os.path.exists(candidate):
                os.remove(candidate)
        signatures.append(signature)
        used.add(str(src_url))
        used_sources.add(source_key)
        got.append({"path": os.path.abspath(dst), "w": int(w2), "h": int(h2),
                    "source": str(src_url), "provider": provider,
                    "title": _metadata_text(title)[:120], "license": _metadata_text(license_) or metadata.get('license', ''),
                    "query": str(query), "source_metadata": metadata or {}})

    # ★★★그림 **소스 사다리**가 오면 그것을 쓴다 (2026-08-18 사장님 지시:
    #   *"구글 이미지 가져오는 방식은 지금 다른 탭의 쇼핑과 달빛부부에서 진행하고
    #    있는 방식을 쓰면 된다"*).
    #
    #   ■ 왜 갈아 끼우나 — **같은 실행기 안에 구글 크롤이 두 벌** 있었다
    #       ① 여기 있던 것   헤드리스 `--dump-dom` + `imgurl=` 정규식
    #       ② `fetch_images` 전용 프로필 크롬에 **CDP 로 붙는다**(`_GoogleCDP`)
    #     ②가 카드뉴스·강석주·꺄오옷에서 실제로 도는 검증된 길이다. 두 벌을 두면
    #     한쪽만 고쳐지고, 어느 쪽이 도는지 아무도 모른다(§"자가 두 벌이면 갈린다").
    #
    #   ★새로 짜지 않았다 — `_source_urls` 가 이미 `cdp_google`·`irasutoya`·`html`·
    #     `json` 을 **한 곳에서** 판정한다. 그 자를 그대로 부른다.
    #   ★옛 서버(`google`+`providers`)도 그대로 돈다 — 아래 갈래가 살아 있다.
    _srcs = item.get("sources")
    if _srcs:
        _pace = float(item.get("pace_sec") or 0.0)
        _bo = tuple(item.get("backoff_sec") or ())
        for _src in _srcs:
            if len(got) >= want or len(attempted) >= candidate_limit:
                break
            for q in (item.get("queries") or []):
                if len(got) >= want or len(attempted) >= candidate_limit:
                    break
                try:
                    _urls = _source_urls(_src, str(q), _bo, _pace)
                except (PhotoSourcePending, ProviderRefusalError):
                    raise
                except Exception as _e:                           # noqa: BLE001
                    _progress(f"  [사진] {_src.get('kind')} 실패 — 다음 소스로: "
                          f"{str(_e) if isinstance(_e, PhotoSourceError) else type(_e).__name__}")
                    break
                import itertools
                # Previously selected/rejected URLs consume no new candidate
                # attempt. Slice after excluding them so a second round can
                # reach the next result instead of revisiting only its prefix.
                fresh = (u for u in _urls if _photo_source_key(u) not in used_sources
                         and _photo_source_key(u) not in attempted)
                for u in itertools.islice(fresh, candidate_limit):
                    meta = _PHOTO_SOURCE_META.get(str(u)) or {}
                    _take(u, str(_src.get("kind") or "?"), meta.get('title') or "", q,
                          metadata=meta)
                    if len(got) >= want or len(attempted) >= candidate_limit:
                        break
        if len(got) >= want or len(attempted) >= candidate_limit:
            return got
        # ★★사다리가 못 채웠으면 **옛 갈래로 이어 간다** — 여기서 끊으면 그 컷이
        #   조용히 빈다(검사가 잡았다: 5컷 전부 0장). 사다리는 **더 나은 첫 시도**이지
        #   유일한 길이 아니다. 아래 `google`·`providers` 는 그대로 살아 있다.
        if not (item.get("source_policy") or {}).get("api_only"):
            _progress(f"  [사진] 사다리로 {len(got)}장 — 모자란 만큼 공개 API 로 이어 간다")

    if (item.get('source_policy') or {}).get('api_only'):
        return got  # This explicit policy has no legacy browser fallback.
    _g = item.get("google")
    modern_google = any(str(src.get('kind') or '').lower() in ('cdp_google','google_cdp','google')
                        for src in (_srcs or []))
    if _g and not modern_google:
        _eng = _browser_engine(_g, out_dir)
        if _eng:
            _progress(f"  [사진] 브라우저 엔진을 찾았다 — 구글도 본다: {os.path.basename(_eng)}")
            for q in (item.get("queries") or []):
                if len(got) >= want or len(attempted) >= candidate_limit:
                    break
                for u in _google_images(_g, q, _eng, out_dir, want, lo, used):
                    _take(u, "google", "", q)
                    if len(got) >= want or len(attempted) >= candidate_limit:
                        break
        else:
            _progress("  [사진] 이 기계에서는 브라우저 엔진이 안 뜬다 — 공개 API 로 간다")

    for prov in (item.get("providers") or []):
        for q in (item.get("queries") or []):
            if len(got) >= want or len(attempted) >= candidate_limit:
                break
            url = str(prov.get("url") or "").replace(
                "{q}", urllib.parse.quote(str(q))).replace(
                "{n}", "8").replace("{w}", str(max(lo, 1280)))
            try:
                with review_dispatch():
                    data = get_json(url, {"User-Agent": ua} if ua else {}, timeout=25)
            except ProviderRefusalError:
                raise
            except Exception:  # noqa: BLE001
                continue          # 이 제공처·이 검색어는 실패했다. 다음 것을 본다
            pick = prov.get("pick") or {}
            rows = _dig(data, pick.get("rows"))
            if pick.get("rows_are") == "map" and isinstance(rows, dict):
                rows = list(rows.values())
            if not isinstance(rows, list):
                continue
            for row in rows:
                if len(got) >= want or len(attempted) >= candidate_limit:
                    break
                src = _dig(row, pick.get("url"))
                h = _dig(row, pick.get("h"))
                if not src or not isinstance(h, int) or h < lo:
                    continue
                _take(src, str(prov.get("name") or ""),
                      _dig(row, pick.get("title")), q,
                      _dig(row, pick.get("license")),
                      metadata=_project_photo_metadata(row, pick, str(src), str(prov.get('name') or 'api')))
    return got


def _sig_cor(u, v):
    """정규화된 두 서명의 상관. **서버가 벡터를 받았을 때 쓰던 식 그대로다.**

    ★반올림한 값끼리 곱한다 — 서버가 받던 것이 반올림된 값이었으므로,
      여기서 원본으로 곱하면 같은 화면인데 **값이 미세하게 달라진다.**
      차동 검사가 이 동일성을 잰다(§"이식했으면 정본과 차동 비교").
    ★`np.multiply` 로 쓴다. 연산자(`u * v`)로 쓰면 numpy 가 임시배열로 오인해
      **살아 있는 배열을 덮어쓰는** 부류의 사고가 난다(§5, 실측된 것).
    """
    import numpy as np
    if not u or not v or len(u) != len(v):
        return None
    a = np.asarray(u, dtype=float)
    b = np.asarray(v, dtype=float)
    # ★반올림하지 않는다. 자릿수는 상수이고, 그 값이 명세 잎값과 우연히 겹치면
    #   반출 검사에 걸린다(실제로 걸렸다 — 날짜·엡실론과 같은 부류). 스칼라 두 개라
    #   짧게 만들 이유도 없다.
    return float(np.multiply(a, b).sum() / a.size)


def fold_scan_corr64(sig_by_card, order):
    """샷 서명(card→{a,b,m 벡터})을 **샷×샷 상관 행렬**로 접는다 (2026-08-24).

    ★서버 `render.fold_shot_scan` 과 **값이 같아야 한다** — 차동 검사가 잰다.
      행에 드는 샷 = a·b·m 셋 다 있는 샷 · 벡터 = m(없으면 a) · 반올림 4자리 ·
      위삼각(자기 자신 포함). 서버가 받은 원시로 접던 그 자 그대로다.
    ■ 왜 — 46샷 원시 벡터는 ≈4.2MB 라 **모델이 모는 MCP 호출에 실을 수 없다**
      (실물 2026-08-24: 수강생이 shop_place 앞에서 오도 가도 못 했다).
      행렬이면 십수 KB 다. 재는 자리에서 접는 것이 유일한 길이다.
    """
    ids, vecs = [], {}
    for card in order:
        sig = sig_by_card.get(card) or {}
        full = all(isinstance(sig.get(k), list) and sig.get(k)
                   for k in ("a", "b", "m"))
        v = sig.get("m") or sig.get("a")
        if full and v:
            ids.append(str(card))
            vecs[str(card)] = v
    corr = {}
    for i, a_ in enumerate(ids):
        row = {}
        for b_ in ids[i:]:
            r = _sig_cor(vecs[a_], vecs[b_])
            if r is not None:
                row[b_] = round(r, 4)
        corr[a_] = row
    return {"_fold": "corr64", "ids": ids, "corr": corr}


def cut_signatures(item):
    """컷 전체의 서명을 재고 **서버가 선언한 상관만** 돌려준다.

    ■ 왜 여기서 접나 (2026-08-17)
        예전에는 컷마다 서명 벡터 세 벌(`SIG_PX²` 개 실수 × 3 ≈ 88KB)을 그대로
        올려보냈다. 그런데 서버가 그것으로 하는 일은 **상관 두 개**뿐이다.
        실측: `person_render` 한 호출이 **3.76MB**(그중 99.5%가 이 벡터)였고
        그 크기 때문에 워커가 **메모리 한도 초과**로 죽었다 — 하루 553건.
        재는 자리에서 접으면 컷당 수십 바이트가 된다. **자는 그대로다.**

    ■ 무엇을 견줄지는 **서버가 정한다**
        `{"as": 이름, "within": [태그, 태그]}`(같은 컷의 두 순간) 또는
        `{"as": 이름, "across": 태그}`(앞 컷의 같은 태그)로 온다.
        여기서 짝을 지어내지 않는다 — 지어내면 자가 갈린다.

    ★★선언은 **`do` 항목에도, 컷 하나하나에도** 올 수 있다 — 둘 다 본다.
      2026-08-17 에 이것 때문에 고친 것이 **하나도 먹지 않았다**: 서버는
      `sig_jobs` 에서 **컷마다** 넣는데 여기서는 `item["correlate"]`(항목 수준)만
      봤다. 없으니 옛 계약으로 물러나 벡터를 그대로 올려보냈고, 새 팩·새 서버인데도
      한 호출이 **3.08MB** 였다(배급 뒤 실측으로 잡았다).
      ★검사는 통과하고 있었다 — 내가 항목 수준에 **손으로 먹여서** 불렀기 때문이다.
        그래서 지금 검사는 **서버 응답을 그대로** 먹인다(§"검사가 자기가 만든 값을 잰다").
    ★선언이 아무 데도 없으면 **옛 계약대로 벡터를 그대로** 돌려준다. 서버가 말하지
      않은 것을 실행기가 앞질러 하지 않는다(전파 중에는 옛 서버가 답할 수 있다).
    """
    import tempfile
    cuts = item.get("cuts") or []
    at_item = item.get("correlate")
    # ★측정(컷마다 ffmpeg 3회 + numpy)은 컷끼리 독립이라 **동시에** 재고,
    #   접기(상관)는 `across` 가 **앞 컷**을 보므로 순차를 유지한다 (2026-08-24).
    #   폭은 서버가 준다(`parallel`) — 없으면 지금까지처럼 순차다.
    #   ★임시폴더는 컷마다 가른다 — 한 폴더를 동시에 쓰면 프레임 파일이 충돌한다.
    try:
        _w = int(item.get("parallel") or 1)
    except (TypeError, ValueError):
        _w = 1
    _w = max(1, min(_w, len(cuts) or 1))
    out, prev = {}, None
    with tempfile.TemporaryDirectory() as td:
        _sigs = {}
        if _w > 1:
            from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

            def _sig_one(pair):
                _i, _it = pair
                _sub = os.path.join(td, f"c{_i:03d}")
                os.makedirs(_sub, exist_ok=True)
                return _i, cut_signature(dict(_it, tmp=_sub))

            with ThreadPoolExecutor(max_workers=_w) as _ex:
                for _i, _s in _ex.map(_sig_one, list(enumerate(cuts))):
                    _sigs[_i] = _s
        else:
            for _i, _it in enumerate(cuts):
                _sigs[_i] = cut_signature(dict(_it, tmp=td))
        # ★★서버가 `fold:"corr64"` 를 선언하면 **행렬로 접어** 돌려준다 (2026-08-24).
        #   쇼핑 shop_place 는 임의 샷쌍 상관이 필요해 스칼라(correlate)로는 못 섬긴다.
        #   선언이 없으면 아래 옛 계약 그대로다 — 실행기가 앞지르지 않는다.
        if str(item.get("fold") or "") == "corr64":
            return fold_scan_corr64({str(it["card"]): _sigs[_i]
                                     for _i, it in enumerate(cuts)},
                                    [str(it["card"]) for it in cuts])
        for _i, it in enumerate(cuts):
            sig = _sigs[_i]
            card = str(it["card"])
            spec = at_item if isinstance(at_item, list) and at_item else it.get("correlate")
            if not isinstance(spec, list) or not spec:
                out[card] = sig                      # 옛 계약 — 벡터 그대로
                continue
            row = {}
            for rule in spec:
                if not isinstance(rule, dict) or not rule.get("as"):
                    continue
                w = rule.get("within")
                if isinstance(w, (list, tuple)) and len(w) == 2:
                    row[rule["as"]] = _sig_cor(sig.get(w[0]), sig.get(w[1]))
                    continue
                a = rule.get("across")
                if a:
                    row[rule["as"]] = (None if prev is None
                                       else _sig_cor(prev.get(a), sig.get(a)))
            out[card] = row
            prev = sig
    return out


def find_subject(path):
    """피사체 중심(x, y 비율). 얼굴 우선, 없으면 엣지 무게중심.

    ★일반 OpenCV 기술이다. 이 좌표를 서버에 보내면 서버가 크롭 사각형을 정해 준다.
    """
    import cv2
    import numpy as np
    from PIL import Image
    g = cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2GRAY)
    h0, w0 = g.shape
    # ★부품이 없으면 여기서 **멈춘다**(`_face_cascade`). 예전에는 `except Exception: pass` 로
    #   삼켜 opencv 5.0 에서 엣지 중심이 얼굴 자리를 차지했다 — 오류 0줄로 틀린 크롭.
    #   산수는 정본 그대로다(실수 k 로 되돌린다 — 정수로 반올림하면 정본 JPEG 바이트가 갈린다).
    cas = _face_cascade()
    sc = 900 / max(w0, h0)
    gs = cv2.resize(g, (int(w0 * sc), int(h0 * sc))) if sc < 1 else g
    f = cas.detectMultiScale(gs, 1.08, 5, minSize=(40, 40))
    if len(f):
        x, y, w, h = max(f, key=lambda r: r[2] * r[3])
        k = 1 / sc if sc < 1 else 1.0
        return ((x + w / 2) * k / w0, (y + h / 2) * k / h0)
    small = cv2.resize(g, (w0 // 8 or 1, h0 // 8 or 1)).astype(float)
    gx = np.abs(np.diff(small, axis=1, prepend=small[:, :1]))
    gy = np.abs(np.diff(small, axis=0, prepend=small[:1, :]))
    e = gx + gy
    if e.sum() <= 0:
        return (0.5, 0.5)
    e = e / e.sum()
    ys, xs = np.mgrid[0:e.shape[0], 0:e.shape[1]]
    # ★`e * xs` 로 쓰지 마라. numpy 가 e 를 임시배열로 오인해 **제자리에서 덮어쓴다**
    #   (파이썬 최신 버전이 지역변수를 빌려온 참조로 올리는 것 + numpy 의 임시배열 재사용).
    #   그러면 두 번째 항이 이미 오염된 e 를 읽어 cy 가 비율이 아닌 큰 수가 되고,
    #   크롭이 슬롯 가장자리로 붙은 채 **오류 없이** 구도가 틀린 영상이 나온다.
    #   배열이 일정 크기를 넘을 때만 나타나서 작은 이미지로 시험하면 멀쩡해 보인다.
    #   np.multiply 는 연산자 슬롯을 거치지 않아 재사용이 없고, 곱셈·합산 결과는 원식과 같다.
    return (float(np.multiply(e, xs).sum()) / e.shape[1],
            float(np.multiply(e, ys).sum()) / e.shape[0])


def image_facts(paths):
    """서버에 보낼 이미지 사실 — 크기와 피사체 중심. **규격은 여기 없다.**"""
    from PIL import Image
    out = {}
    for rel in paths:
        im = Image.open(rel)
        cx, cy = find_subject(rel)
        out[rel] = {"w": im.size[0], "h": im.size[1], "cx": cx, "cy": cy}
    return out


def expand_frame_runs(frames):
    """run 서술자를 낱장으로 편다 — 식은 **성분별 선형 보간(lerp) 하나**뿐이다.

    ★서버가 `run` 키를 줄 때만 일이 있다 — 없으면 목록을 **그대로** 돌려준다
      (옛 서버 응답과 혼재 무해). 서술자 두 꼴:
        {"run": n, "src", "dstf", "dst0", "srcbox0", "srcbox1", "dst_size"}
            → k번째(0…n-1) 낱장: dst = dstf % (dst0+k) ·
              srcbox = srcbox0 + (srcbox1-srcbox0) · k/(n-1)  (성분별)
        {"run": n, "src", "dstf", "dst0", "resize", "crop"}
            → 같은 정수 상자를 n 장 반복
      끝점·이름·개수 전부 서버가 준다 — 여기에 채널 값은 하나도 없다.
    ★서버 쪽 같은 자(volcano_render.expand_frame_runs)와 **글자까지 같아야** 한다 —
      서버는 이 파일을 import 할 수 없어 두 벌이 불가피하고, 갈리면 서버가 검산한
      프레임과 실제로 구운 프레임이 다른 말을 한다(서버 게이트가 dict 완전 동일을
      잰다). 식을 고치려면 양쪽을 같이 고쳐라.
    """
    if not isinstance(frames, list) or not any(
            isinstance(f, dict) and "run" in f for f in frames):
        return frames
    out = []
    for f in frames:
        if not (isinstance(f, dict) and "run" in f):
            out.append(f)
            continue
        n, d0 = int(f["run"]), int(f["dst0"])
        if "srcbox0" in f:
            a, b = f["srcbox0"], f["srcbox1"]
            for k in range(n):
                t = k / (n - 1) if n > 1 else 0.0
                out.append({"src": f["src"], "dst": f["dstf"] % (d0 + k),
                            "srcbox": [a[j] + (b[j] - a[j]) * t
                                       for j in range(4)],
                            "dst_size": list(f["dst_size"]),
                            **{k:f[k] for k in ('order','placement','brightness','frame_canvas') if k in f}})
        else:
            for k in range(n):
                out.append({"src": f["src"], "dst": f["dstf"] % (d0 + k),
                            "resize": list(f["resize"]),
                            "crop": list(f["crop"]),
                            **{k:f[k] for k in ('order','placement','brightness','frame_canvas') if k in f}})
    return out


def bake_frames(frames, parallel=None, progress_every=60):
    """서버가 준 (resize, crop) 을 그대로 적용한다. 그 이상 아무것도 하지 않는다.

    ★★**모양이 아니면 아무 일도 하지 않는다** (2026-08-16, 수강생 7명이 여기서 죽었다).
      서버가 응답 최상위에 클라의 `payload.frames`(측정값 **dict**)를 같은 이름으로
      되돌려준 적이 있다. 그러면 여기로 dict 가 들어오고, 돌면 원소가 **문자열(키)** 라
      `f["src"]` 에서 `TypeError: string indices must be integers` 로 죽는다.
      서버는 고쳤지만(§`_RUNNER_RESERVED`), **다음에 다른 이름이 겹쳐도 죽지 않게**
      여기서도 막는다. 굽는 일은 목록일 때만 한다 — 아니면 **조용히 넘기지 않고 말한다.**

    ★LANCZOS · quality=100 · subsampling=0 은 **정본과 픽셀을 맞추기 위한 것**이다.
      바꾸면 결과가 달라진다.

    ■ ★폭(`parallel`)은 **서버가 준다.** 없으면 직렬이다 — 여기서 정하지 않는다
        예전에는 폭 인자조차 없어 **누구에게나 항상 직렬**이었다. 정본 242 프레임
        실측(M4 10코어): 직렬 6.82초 → 폭 5 에서 2.32초(**2.94배**).
        굽기가 이 단계에서 가장 큰 덩어리다(같은 workdir 의 video_raw 인코드가 4.51초).

    ■ ★바이트가 달라지면 안 된다 — 그래서 원본은 **먼저 다 연다**
        프레임들은 같은 그림을 여러 번 쓴다(정지·위글·반복 슬롯). 캐시가 곧 이득인데
        여러 갈래가 같은 캐시를 동시에 채우면 같은 파일을 여러 번 열게 되고, 최악에는
        반쯤 만든 객체를 남이 본다. 그래서 **① 원본을 순서대로 다 열고(가볍다)
        ② 무거운 resize/crop/save 만 나눈다.** PIL 의 그 두 일은 GIL 을 놓아서
        스레드로도 실측 2.94배가 나왔다.
    """
    from PIL import Image
    # ★목록이 아니면 굽지 않는다(위 주석). 조용히 통과시키면 프레임이 통째로
    #   안 구워진 채 다음 단계로 가서, 오류 없이 검은 화면이 나온다.
    if not isinstance(frames, list):
        raise StepError(
            "굽을 프레임 목록이 아니다 — 서버 응답의 `frames` 가 "
            f"{type(frames).__name__} 다. 실행기를 최신 팩으로 받으셨는지 확인하고, "
            "그래도 나면 관리자에게 알려주세요.")
    # ★run 서술자가 섞여 있으면 먼저 낱장으로 편다(2026-08-25 — 응답 크기 압축).
    #   서버가 그 키를 줄 때만 일이 있고, 없으면 목록이 그대로다(신구 혼재 무해).
    n_run = sum(1 for f in frames if isinstance(f, dict) and "run" in f)
    if n_run:
        frames = expand_frame_runs(frames)
        _progress(f"  [전개] 서술자 {n_run}건 → 낱장 {len(frames)}장(선형 보간)",
              flush=True)
    cache = {}

    def _load(src):
        if src.startswith("pepe"):
            s0 = Image.open(src).convert("RGBA")
            bg = Image.new("RGB", s0.size, (255, 255, 255))
            bg.paste(s0, mask=s0.split()[-1])
            return bg
        return Image.open(src).convert("RGB")

    # ① 원본 — **순서대로**, 한 번씩만. 여기는 나누지 않는다(그림 여는 건 싸다)
    for f in frames:
        if f["src"] not in cache:
            cache[f["src"]] = _load(f["src"])
        os.makedirs(os.path.dirname(f["dst"]) or ".", exist_ok=True)

    # ② 굽기 — 폭이 있으면 나눈다. 각 프레임은 **자기 dst 에만** 쓴다(겹치면 서버가 막는다)
    width = int(parallel or 1)
    if width > 1:
        from concurrent.futures import ThreadPoolExecutor
        done = [0]

        def _one(f):
            _bake_one(f, cache[f["src"]], Image)
            done[0] += 1
            if progress_every and done[0] % progress_every == 0:
                _progress(f"  프레임 {done[0]}/{len(frames)}", flush=True)

        with ThreadPoolExecutor(max_workers=width) as ex:
            for _ in ex.map(_one, frames):
                pass
        _progress(f"  프레임 {len(frames)}장 (폭 {width})", flush=True)
        return len(frames)

    for i, f in enumerate(frames):
        _bake_one(f, cache[f["src"]], Image)
        if progress_every and (i + 1) % progress_every == 0:
            _progress(f"  프레임 {i + 1}/{len(frames)}", flush=True)
    return len(frames)


def _bake_one(f, im, Image):
    """프레임 한 장. **직렬·병렬이 같은 코드를 쓴다** — 두 벌이면 한쪽만 고쳐진다.

    ★순서는 **서버가 정한다.** 기본은 resize→crop(뇌전구 정본과 픽셀을 맞춘 순서)이고,
      `order: "crop_first"` 면 자르고 나서 줄인다(원본이 큰 사진 슬라이드쇼는 그쪽이
      훨씬 가볍다). 실행기가 순서를 고르면 결과가 갈린다.

    ★`srcbox` — **소수점 상자**로 한 번에 줄인다 (2026-08-24). 느린 팬(초당 10px대)
      은 프레임당 1px 미만인데 정수 crop 은 5~6프레임 멈췄다 1px 튀는 계단이 된다.
      PIL 의 `crop` 은 실수를 줘도 부분 화소를 보간하지 않는다(실측) — 부분 화소는
      `resize(크기, LANCZOS, box=상자)` 만 한다. 상자·크기 전부 서버가 준다.
      서버가 이 키를 줄 때만 돈다 — 옛 서버 응답과 혼재 무해.
    """
    if f.get('placement'):
        import math
        p=f['placement']
        if p.get('mode')!='contain_selected':raise StepError('알 수 없는 사진 배치 방식입니다.')
        x,y,w,h=map(float,p['viewport']);bx,by,bw,bh=p['content']
        if (not all(math.isfinite(v) for v in (x,y,w,h,bx,by,bw,bh)) or min(w,h,bw,bh)<=0
                or bx<0 or by<0 or bx+bw>im.width or by+bh>im.height):
            raise StepError('사진 배치의 실제 원본 영역이 유효하지 않습니다.')
        # Extend only the declared solid canvas. Sample the real content once
        # with the existing Lanczos filter and its exact fractional viewport.
        left,top=math.floor(min(x,bx)),math.floor(min(y,by))
        right,bottom=math.ceil(max(x+w,bx+bw)),math.ceil(max(y+h,by+bh))
        padded=Image.new('RGB',(right-left,bottom-top),tuple(p['background']))
        padded.paste(im.crop((bx,by,bx+bw,by+bh)),(int(bx-left),int(by-top)))
        out=padded.resize(tuple(p['canvas']),Image.LANCZOS,
                          box=(x-left,y-top,x+w-left,y+h-top))
    elif f.get("srcbox"):
        out = im.resize(tuple(int(x) for x in f["dst_size"]), Image.LANCZOS,
                        box=tuple(float(x) for x in f["srcbox"]))
    elif f.get("order") == "crop_first":
        out = im.crop(tuple(f["crop"])).resize(tuple(f["resize"]), Image.LANCZOS)
    else:
        out = im.resize(tuple(f["resize"]), Image.LANCZOS).crop(tuple(f["crop"]))
    # Preserve the source compositor's JPEG round trips: crop is saved before
    # dim_intro, and the dimmed image is saved before frame_place. Keeping those
    # boundaries avoids silently changing measured texture/colors on this path.
    if f.get('brightness') is not None or f.get('frame_canvas'):
        import io
        def jpeg_roundtrip(img):
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=100, subsampling=0)
            buf.seek(0)
            return Image.open(buf).convert('RGB')
        out = jpeg_roundtrip(out)
        if f.get('brightness') is not None:
            import math
            import numpy as np
            gain = float(f['brightness'])
            if not math.isfinite(gain) or gain < 0:
                raise StepError('사진 밝기 변환값이 유효하지 않습니다.')
            pixels = np.asarray(out).astype(np.float32) * gain
            out = Image.fromarray(np.clip(pixels + .5, 0, 255).astype(np.uint8))
            if f.get('frame_canvas'):
                out = jpeg_roundtrip(out)
        if f.get('frame_canvas'):
            canvas = f['frame_canvas']
            size, xy = canvas['size'], canvas['xy']
            if len(size) != 2 or len(xy) != 2 or min(size) <= 0:
                raise StepError('사진 화면 배치값이 유효하지 않습니다.')
            background = Image.new('RGB', tuple(size), (0, 0, 0))
            background.paste(out, tuple(xy))
            out = background
    out.save(f["dst"], quality=100, subsampling=0)


def is_drawn(path, gate):
    """사진 슬롯에 **그림**이 들어왔는지. True 면 중단해야 한다.

    ■ ★임계는 **서버가 준다**(`gate`). 여기서 정하지 않는다
        예전에는 `white>0.35 and ncol<90` 이 이 함수에 박혀 있었다 — 서버가 값을
        바꿔도 실행기가 안 따라오는, 이 저장소가 금지한 그 모양이다.
        그리고 그 자는 **흰 배경 위 납작한 그림**만 잡았다. 배경이 채워진 그림은
        흰 화소가 적고 색이 많아 통째로 샜다.
    ■ 무엇을 재나
        flat      작은 블록의 표준편차가 거의 0 인 비율 = **평평한 면**이 얼마나 넓은가
        grad_med  이웃 화소 밝기차의 **중앙값** = 잔결(질감)이 있는가
        그림은 면이 평평하고 질감이 없다. 사진은 어디를 봐도 잔결이 있다.
    ■ ★`gate` 가 없으면 **막는다**
        판정할 수 없는 것을 통과로 읽지 않는다. 옛 서버 응답이면 여기서 멈추고
        사람이 새 배포본을 쓰게 한다 — 조용히 통과시키면 그게 §5 다.
    """
    import numpy as np
    from PIL import Image
    # ★기본값을 **하나도 두지 않는다.** 하나라도 두면 서버가 그 값을 바꿔도 안 따라오고,
    #   그 자리는 아무도 안 보는 채로 굳는다. 없으면 판정하지 말고 멈춘다.
    need = ("flat_max", "grad_med_min", "resize", "flat_block", "flat_std")
    if not isinstance(gate, dict) or any(k not in gate for k in need):
        raise StepError(
            "그림체 판정 기준(gate)을 서버가 다 주지 않았다 — 판정할 수 없다.\n"
            f"  필요: {list(need)}\n  받은 것: {sorted(gate) if isinstance(gate, dict) else gate}\n"
            "  서버가 옛 배포본이다. 검사를 건너뛰면 그림이 사진 자리로 그대로 나간다.")
    n = int(gate["resize"])
    blk, std_lim = int(gate["flat_block"]), float(gate["flat_std"])
    a = np.asarray(Image.open(path).convert("RGB").resize((n, n))).astype(float)
    g = a.mean(axis=2)
    # ★`g // k` 꼴로 쓰지 마라 — numpy 가 g 를 제자리에서 덮어쓴다(find_subject 와 같다).
    h, w = g.shape
    bl = g[:h // blk * blk, :w // blk * blk]
    bl = bl.reshape(h // blk, blk, w // blk, blk).transpose(0, 2, 1, 3).reshape(-1, blk * blk)
    flat = float((bl.std(axis=1) < std_lim).mean())
    grad = np.concatenate([np.abs(np.diff(g, axis=1)).ravel(),
                           np.abs(np.diff(g, axis=0)).ravel()])
    grad_med = float(np.median(grad))
    bad = flat > float(gate["flat_max"]) or grad_med < float(gate["grad_med_min"])
    # ★★**무엇이 걸렸는지 남긴다** (2026-08-26 · 실측 385회·61명).
    #   True/False 만 돌려주니 반려문이 「사진 슬롯에 그림이 들어왔다」뿐이었고,
    #   두 축(평평한 면 · 잔결) 중 **어느 쪽이 걸렸는지** 한 글자도 안 갔다.
    #   그러면 실사인데 걸린 사람이 화풍을 고치러 가고(고쳐도 안 통과한다) 같은
    #   자리를 되풀이한다 — 수강생 둘이 글로 이 값을 요청했다.
    #   ★임계는 **이미 클라 손에 있다**(서버가 `gate` 로 내려준다) — 여기서 값을
    #     찍는 것은 새로 반출하는 것이 아니다(§2 경계 그대로).
    #   ★반환값 계약은 안 바꾼다(bool) — 부르는 자리가 셋이고 검사도 bool 을 본다.
    is_drawn.last = {"file": path, "flat": round(flat, 4),
                     "grad_med": round(grad_med, 4),
                     "flat_max": float(gate["flat_max"]),
                     "grad_med_min": float(gate["grad_med_min"]),
                     "why": ("평평한 면이 넓다" if flat > float(gate["flat_max"])
                             else "잔결(질감)이 없다" if bad else "")}
    return bad


def _image_receipt_path(raw):
    # Let the actual filesystem resolve case/Unicode aliases, including APFS.
    # A mirrored basename also preserves distinct names on case-sensitive volumes.
    # Do not resolve the raw leaf: publishing replaces a symlink at that pathname.
    parent = os.path.realpath(os.path.dirname(raw) or '.')
    return os.path.join(parent, '.volcano-image', os.path.basename(raw), 'receipt.json')


def _retry_after_at(value, now):
    """`Retry-After` 머리글(RFC 9110 §10.2.3 — 초 또는 HTTP 날짜) → 다시 보내도 되는 시각(epoch). 없거나 읽을 수 없으면 None.

    시각을 지어내지 않는다(전역 규칙 6-2) — 머리글이 없으면 None 이고, 부르는 쪽은 사람이 풀 때까지 기다린다."""
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit():
        return now + int(text)
    import email.utils
    try:
        moment = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None
    if moment.tzinfo is None:
        import datetime
        moment = moment.replace(tzinfo=datetime.timezone.utc)  # RFC 9110 HTTP 날짜는 GMT 다.
    return moment.timestamp()


def _image_post_hold_path(endpoint, headers):
    """그림 접수 멈춤 기록 — **제공자 주소 + 자격증명 하나에 한 자리**(이 PC 의 모든 작업 폴더가 함께 본다 · 2026-10-20 저녁 신고).

    ■ 왜 작업 폴더가 아니라 키인가: 제공자 한도(429 · Retry-After)는 그 키에 걸린다. 10-20 15:25 판은 기록을 작업 폴더마다 두어,
      한 사람이 같은 키로 55편을 3편씩 돌리자 17:43:38 한 편이 429(→17:48:25) 를 받은 뒤에도 17:44:52 다른 편은 자기 폴더 기록만
      보고(17:43:06 에 풀림) 또 보내 429 를 받았다 — 편마다 창마다 한 번씩 제공자를 다시 때렸다. 키 하나에 기록 하나면 그 키로
      도는 어느 편이든 첫 429 뒤로는 제공자가 정한 시각까지 아무도 보내지 않는다.
    ■ 자격증명 값은 적지 않는다 — sha256 지문만 이름에 쓴다. 지문은 실행마다 주소 하나에 한 번만 잰다(generate_images 가 모아 넘긴다)."""
    import urllib.parse
    host = urllib.parse.urlsplit(str(endpoint)).netloc.lower()
    sent = sorted((str(k).lower(), v) for k, v in http_headers(headers).items())
    digest = hashlib.sha256(json.dumps([host, sent], ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    return os.path.join(os.path.expanduser('~'), '.volcano', 'image-holds', digest[:32] + '.json')


def _image_legacy_hold_path(receipt):
    """10-20 15:25 판이 작업 폴더에 남긴 멈춤 기록(`.volcano-image/post-hold.json`) — 같은 규칙으로 읽기만 한다(시각 없는 옛 기록이 표식 없이 풀리지 않게)."""
    return os.path.join(os.path.dirname(os.path.dirname(receipt)), 'post-hold.json')


def _image_post_hold_todo(hold, path, now):
    """멈춤 기록 하나 → 사람이 할 일 한 줄(다시 보낼 시각이 있으면 그 시각 · 없으면 표식 파일)."""
    if hold.get('http_status') == 402:
        # 잔액 부족은 시각으로 풀리지 않는다 — 충전했다는 사실은 사람만 안다(제공자가 «언제» 를 주지 않는다).
        return (" ▶ 그 서비스 계정의 크레딧(잔액)이 모자랍니다(HTTP 402). 그래서 이 PC 에서 같은 키로 도는 어느 편도 새 그림 접수를 보내지 않습니다 — "
                "같은 명령이나 다른 편을 다시 실행해도 보내지 않습니다(충전 전에는 다시 보내도 같은 402 입니다). "
                f"충전한 뒤 빈 파일 {path}.resume-once 를 만들고 같은 명령을 한 번 실행하세요(받아 둔 그림은 다시 사지 않습니다 · "
                f"새 계정·새 키로 돌리지 마세요). 기록: {path}")
    at = hold.get('retry_at')
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        local = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(at))
        return (f" ▶ 제공자가 Retry-After 로 {local}(이 PC 시각 · 약 {max(0, int(at - now + 0.999))}초 뒤) 이후에 다시 오라고 했습니다. "
                "그 전에는 이 PC 에서 같은 키로 도는 어느 편도 새 그림 접수를 보내지 않습니다(같은 명령을 그 전에 다시 실행해도 같은 멈춤입니다) — "
                f"그 시각이 지난 뒤 같은 명령을 한 번 실행하세요(새 계정·새 키로 돌리지 마세요). 기록: {path}")
    return (" ▶ 제공자가 다시 보낼 시각(Retry-After)을 알려 주지 않았습니다. 그래서 이 작업은 새 그림 접수를 자동으로 다시 보내지 않습니다 — "
            "같은 명령을 다시 실행해도 보내지 않습니다(다시 부를수록 한도만 더 걸립니다). 제공자 오류 문서는 기다릴 시간을 정하지 않고 "
            "«요청 간격을 늘리고 진행 중인 작업이 끝난 뒤 보내라» 고 합니다 — 같은 키로 동시에 도는 다른 편(이 PC·다른 PC)의 그림 생성을 "
            f"끝내거나 멈춘 뒤, 빈 파일 {path}.resume-once 를 만들고 같은 명령을 한 번 실행하세요(새 계정·새 키로 돌리지 마세요). 기록: {path}")


def _image_hold_read(path):
    """멈춤 기록 하나 → (바이트, 기록) · 없으면 (None, None) · 못 읽으면 StepError(새 유료 접수를 보내지 않는다)."""
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
        hold = json.loads(raw.decode('utf-8'))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as exc:
        raise StepError(f'그림 접수 멈춤 기록을 읽지 못했습니다 — 새 유료 접수를 보내지 않습니다. 기록: {path} ({type(exc).__name__})')
    if not isinstance(hold, dict):
        raise StepError(f'그림 접수 멈춤 기록 형식이 맞지 않습니다 — 새 유료 접수를 보내지 않습니다. 기록: {path}')
    return raw, hold


def _image_post_hold_gate(hold_path, receipt):
    """새 그림 접수(유료 POST) 직전 — 같은 키가 429 로 멈춰 있으면 보내지 않는다(2026-10-20 뇌전구 신고 · 한 사람 198건 → 같은 날 저녁 55편).

    ■ 왜: 429 는 한 실행 안에서만 멈췄다(run_stop). 같은 명령을 다시 실행하면 그 실행은 거절을 몰라 **안 보낸 다른 슬롯**을
      새로 보냈고, 또 429 를 받아 그 슬롯도 «접수 응답 미확인» 이 됐다 — 편마다 슬롯 수(10)만큼 제공자를 다시 때린 뒤
      «10/10 미확인» 으로 끝났다(20편 동시 · 78초 간격 재실행). 거절은 남겨 다음 실행도 본다.
    ■ 어디에: 키 단위 한 자리(`_image_post_hold_path`) — 같은 키로 도는 **다른 작업 폴더**의 429 도 본다(15:25 판은 작업 폴더마다
      두어 편끼리 서로의 429 를 몰랐다). 15:25 판이 작업 폴더에 남긴 옛 기록(`_image_legacy_hold_path`)도 같은 규칙으로 읽는다.
    ■ 언제 다시 보내나 — 제공자가 정한 것만: `Retry-After` 시각이 지났거나, 시각이 없으면 사람이 `<기록>.resume-once` 표식을
      만든 뒤(한 번 쓰고 지운다 · `_tts_resend_hint` 와 같은 꼴). EvoLink 공식 문서에는 기다릴 숫자가 없다(429 응답 예시
      «Too many requests, please try again later» — docs gpt-image-2-image-generation · task-management/error-codes.md
      quota_exceeded «Reduce request frequency … Wait for in-progress tasks to complete»).
    돌려주는 값: None(보내도 된다) · ProviderRefusalError·StepError(보내지 않는다 — 부르는 쪽이 멈춤을 알리고 던진다)."""
    for path in (hold_path, _image_legacy_hold_path(receipt)):
        try:
            raw, hold = _image_hold_read(path)
        except StepError as error:
            return error
        if hold is None:
            continue
        now = time.time()
        at = hold.get('retry_at')
        timed = isinstance(at, (int, float)) and not isinstance(at, bool)
        mark = path + '.resume-once'
        if (timed and now >= at) or (not timed and os.path.exists(mark)):
            # 같은 키의 다른 작업이 그사이 새 429 를 적었으면(바이트가 다르면) 그 기록은 지우지 않고 그 기록으로 멈춘다.
            try:
                fresh, newer = _image_hold_read(path)
            except StepError as error:
                return error
            if fresh == raw:
                for done in (path, mark):
                    try:
                        os.remove(done)
                    except FileNotFoundError:
                        pass
                _progress("  [이미지] 앞 실행의 HTTP %d 멈춤을 풀었다 — " % int(hold.get('http_status') or 429)
                          + ("제공자가 정한 시각이 지났다" if timed else "사람이 표식을 만들었다")
                          + " · 이번 실행이 새 접수를 보낸다", flush=True)
                continue
            if newer is None:
                continue
            hold = newer
        status = int(hold.get('http_status') or 429)
        what = '잔액 부족 거절' if status == 402 else '제공자 한도 거절'
        held = ProviderRefusalError('provider.image', 'HTTP_%d' % status,
                                    'HTTP %d — 같은 키가 받은 %s이 아직 풀리지 않아 이번 실행은 새 그림 접수를 보내지 않았습니다'
                                    % (status, what), todo=_image_post_hold_todo(hold, path, now))
        # ★이미 알린 거절을 기록에서 다시 보여 주는 정지다(묶음 사이 약속 `replayed` — 구동기 `_report_failure` 가 다시 알리지 않는다).
        #   거절은 제공자가 실제로 답한 실행이 그때 알렸다. 10-22 15:00~16:52 한 사람이 바깥 묶음으로 60편을 ~8분마다 다시 띄우자
        #   이 정지가 실행마다 신고 한 줄씩 577줄 쌓였다(제공자에는 한 건도 안 나감).
        held.replayed = True
        return held
    return None


def _image_post_hold_save(path, exc, slot, receipt):
    """첫 429·402 를 키 단위 기록(`_image_post_hold_path`)에 남긴다 — 429 는 제공자가 준 Retry-After 만 시각으로 쓴다(없으면 None · 지어내지 않는다).
    402(잔액 부족)는 시각이 없다 — 충전은 시간이 지나 저절로 되지 않으니 사람의 표식으로만 푼다."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = time.time()
    status = int(getattr(exc, 'code', 429))
    headers = getattr(exc, 'headers', None)
    value = headers.get('Retry-After') if headers is not None else getattr(exc, 'retry_after', None)
    hold = {'http_status': status, 'refused_at': now, 'slot': slot, 'receipt': receipt,
            'retry_at': None if status == 402 else _retry_after_at(value, now), 'retry_after_header': None if value is None else str(value)[:80]}
    _photo_write_state(path, hold)
    return hold, path, now

def _image_load_receipt(receipt):
    try:
        with open(receipt, encoding='utf-8') as fh:
            state = json.load(fh)
        if not (isinstance(state, dict) and type(state.get('version')) is int
                and state['version'] == 1 and isinstance(state.get('requests'), dict)
                and state['requests']):
            raise ValueError('bad receipt')
    except (ValueError, TypeError) as exc:
        raise StepError(f'이미지 접수 기록 손상 — 새 유료 접수를 보내지 않습니다. 기록: {receipt}') from exc
    return state


def _image_load_receipt_or_reset(receipt):
    """접수 기록 읽기 — 손상이면 멈추고, 사람이 `<기록>.reset-once` 를 만들었을 때만 새 기록으로 시작한다(10-21 뇌전구 신고).

    ■ 왜: «접수 기록 손상» 에는 빠져나갈 길이 없었다(같은 명령을 22번 되풀이해 같은 정지). 손상된 기록은 유료 접수를 했는지
      알 수 없으니 자동으로는 다시 보내지 않는다 — 사람이 «다시 사도 된다» 고 고를 때만(과금이 한 번 더 될 수 있다).
    ■ 원본은 지우지 않는다 — `<기록>.corrupt-<시각>` 으로 옮겨 보존한다(유료 요청 기록 삭제 금지). 표식은 한 번 쓰고 지운다."""
    mark = receipt + '.reset-once'
    try:
        return _image_load_receipt(receipt)
    except StepError as error:
        if not os.path.exists(mark):
            raise StepError(f'{error} · 기록을 확인했고 그 그림을 새로 접수해도 되면(과금이 한 번 더 될 수 있습니다) 빈 파일 {mark} '
                            '를 만든 뒤 같은 명령을 다시 실행하세요 — 지금 기록은 지우지 않고 옆에 옮겨 둡니다.') from error.__cause__
    kept = f'{receipt}.corrupt-{int(time.time())}'
    os.replace(receipt, kept)
    os.remove(mark)
    _progress(f"  [이미지] 사람이 손상된 접수 기록을 새로 시작하기로 골랐다 — 옛 기록은 {os.path.basename(kept)} 로 보존 · 이 슬롯은 새로 접수한다",
              flush=True)
    return {'version': 1, 'requests': {}}


def _image_legacy_receipt(raw, receipt, recipe):
    # The unreleased hash format did not store the output pathname. Adopt an
    # exact old pathname under both locks, retaining the old record unchanged.
    canonical = os.path.abspath(raw)
    for old in dict.fromkeys((canonical, os.path.normcase(canonical))):
        legacy = os.path.join(os.path.dirname(old), '.volcano-image',
                              hashlib.sha256(old.encode()).hexdigest() + '.json')
        if os.path.exists(legacy):
            with _asr_lock(legacy + '.lock'):
                state = _image_load_receipt(legacy)
                _asr_save(receipt, state)
                return state
    legacy_dir = os.path.dirname(os.path.dirname(receipt))
    for name in os.listdir(legacy_dir):
        if not re.fullmatch(r'[a-f0-9]{64}\.json', name):
            continue
        state = _image_load_receipt(os.path.join(legacy_dir, name))
        if recipe in state['requests']:
            # A case alias or moved old output cannot be safely distinguished
            # from another output using the same request. Other recipes are free
            # to proceed; an unattributed same-recipe receipt needs verification.
            raise StepError(f'이전 이미지 접수 기록의 출력 경로 확인이 필요합니다 — 새 유료 접수를 '
                            f'보내지 않습니다. 기록: {legacy_dir}')
    return {'version': 1, 'requests': {}}


#: 제공자가 «실패» 로 확정한 그림 작업 뒤 사람이 고를 길(2026-10-17 실행기 중단 보고 11건·7명 — 예전 글은 기록 경로뿐이라 같은 명령을
#: 되풀이해 같은 정지를 받았다). 자동 재접수는 하지 않는다(실패 작업의 과금 여부를 제공자 문서로 확인하지 못했다).
_IMAGE_FAILED_WAYS = ("\n  ▶ 그 칸(슬롯 {slot})은 본인 그림으로 이어 갈 수 있습니다: customization.images.{slot}.path 에 파일 경로를 넣고 "
                      "images 단계부터 다시 실행하세요. 같은 명령을 그대로 되풀이하면 같은 정지가 납니다(기록은 보존합니다).")


def _image_file_sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _image_generate_raw(j, poll, headers, retry, min_bytes, retry_policy, receipt, run_stop=None, hold_path=None):
    """One durable paid submission; only reads/downloads retry after acceptance."""
    raw = j['raw']
    if hold_path is None:
        hold_path = _image_post_hold_path(j['endpoint'], headers)
    recipe = hashlib.sha256(json.dumps([j['endpoint'], j['body']], sort_keys=True,
                                       ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    state = (_image_load_receipt_or_reset(receipt) if os.path.exists(receipt)
             else _image_legacy_receipt(raw, receipt, recipe))
    record = state['requests'].get(recipe)
    if recipe in state['requests']:
        stages = ('submitting', 'accepted', 'ready', 'downloaded', 'complete', 'rejected', 'failed', 'unsent')
        if (not isinstance(record, dict) or record.get('state') not in stages
                or (record['state'] in ('accepted', 'ready', 'downloaded', 'complete', 'failed')
                    and not (isinstance(record.get('task_id'), str) and record['task_id'].strip()))
                or (record['state'] in ('ready', 'downloaded', 'complete')
                    and not (isinstance(record.get('url'), str) and record['url'].startswith(('http://', 'https://'))))
                or (record['state'] in ('downloaded', 'complete')
                    and not re.fullmatch(r'[a-f0-9]{64}', str(record.get('raw_sha256') or '')))):
            raise StepError(f'이미지 접수 상태 손상 — 새 유료 접수를 보내지 않습니다. 기록: {receipt}')
    # Preserve legacy completed caches. Once receipts exist, the current request's
    # byte digest governs reuse, including when a caller reuses an output filename.
    if record is None and not state['requests'] and _have(j.get('skip_if')):
        try:
            with open(raw + '.url', encoding='utf-8') as fh:
                return fh.read().strip() or None
        except OSError:
            return None

    def save():
        state['requests'][recipe] = record
        _asr_save(receipt, state)  # Existing fsync + same-directory atomic replacement.

    def matches(path):
        return (record.get('raw_sha256') and os.path.isfile(path)
                and os.path.getsize(path) > min_bytes
                and _image_file_sha(path) == record['raw_sha256'])

    def check_run_stop():
        if run_stop is not None and run_stop['error'] is not None:
            raise run_stop['error']

    def stop_for_http(exc):
        code = getattr(exc, 'code', None)
        if not isinstance(exc, (urllib.error.HTTPError, ApiRefused)) or code not in (401, 402, 403, 429):
            return None
        error = ProviderRefusalError('provider.image', 'HTTP_%d' % code,
                                     'HTTP %d — 이 실행의 다른 이미지 요청도 중단했습니다' % code)
        if run_stop is not None:
            with run_stop['lock']:
                if run_stop['error'] is None:
                    run_stop['error'] = error
                return run_stop['error']
        return error

    def request_call(fn):
        # Serialize dispatch and the response classification for this image
        # batch. A concurrent worker cannot issue a new HTTP request in the
        # gap after a refusal response and before the stop is published.
        if run_stop is None:
            return fn()
        with run_stop['lock']:
            check_run_stop()
            try:
                return fn()
            except (urllib.error.HTTPError, ApiRefused) as exc:
                code = getattr(exc, 'code', None)
                if code in (401, 402, 403, 429) and run_stop['error'] is None:
                    run_stop['error'] = ProviderRefusalError(
                        'provider.image', 'HTTP_%d' % code,
                        'HTTP %d — 이 실행의 다른 이미지 요청도 중단했습니다' % code)
                raise

    if record and record['state'] in ('downloaded', 'complete'):
        if not matches(raw) and record['state'] == 'downloaded' and matches(raw + '.part'):
            _publish(raw + '.part', raw)
        if matches(raw):
            record['state'] = 'complete'
            save()
            from runtime_metrics import event
            event('image', 'reused', recipe)
            return record['url']
        record['state'] = 'ready'  # Lost/corrupt local file: reuse the accepted job's result.
        save()
    resend_mark = f'{receipt}.{recipe[:12]}.resend-once'
    if record and record['state'] == 'submitting' and os.path.exists(resend_mark):
        # 사람이 그 슬롯만 «한 번 더 보내기» 를 골랐다(신고 #313 · #208 음성과 같은 길) — 표식은 한 번 쓰고 지운다 · 아래 갈래가 새로 보낸다.
        os.remove(resend_mark)
        _progress(f"  [이미지] 슬롯 {j['slot']} — 사람이 다시 보내기를 골랐다(표식 {os.path.basename(resend_mark)}) · 이 슬롯만 새로 요청한다",
                  flush=True)
        record = None
    gated = False
    if record and record['state'] == 'submitting' and record.get('http_status') == 429:
        # 제공자가 429 로 답한 슬롯(작업 ID 없는 거절 응답) — 작업 폴더의 429 멈춤이 풀릴 때(제공자 시각·사람 표식)만 이 슬롯부터 다시 보낸다.
        with (run_stop['lock'] if run_stop is not None else contextlib.nullcontext()):
            check_run_stop()
            held = _image_post_hold_gate(hold_path, receipt)
            if held is not None:
                if run_stop is not None:
                    run_stop['error'] = held
                raise held
        gated, record = True, None
    if record and record['state'] == 'submitting':
        unconfirmed = StepError(f'이미지 접수 응답 미확인 (슬롯 {j["slot"]}) — 제공자 접수를 확인해야 합니다. '
                                f'새 유료 요청을 자동 재전송하지 않습니다. 기록: {receipt} · ' + _tts_resend_hint(resend_mark, "슬롯"))
        # 앞 실행이 응답을 잃은(또는 옛 판이 429 를 http_status 없이 남긴) 그 자리에서 알린 정지를 기록에서 다시 보여 주는 것이다 — 다시 알리지 않는다
        # (`replayed` · 10-22 한 사람 9편이 10-20 옛 429 기록으로 ~8분마다 다시 띄워 신고 ~80줄). 풀 길은 사람의 표식뿐이라 신고가 늘어도 바뀌는 것이 없다.
        unconfirmed.replayed = True
        raise unconfirmed
    if record and record['state'] == 'failed':
        raise StepError(f'이미지 제공자 작업 {record["task_id"]}이 실패로 끝났습니다. '
                        f'같은 요청을 자동 재접수하지 않습니다. 기록: {receipt}' + _IMAGE_FAILED_WAYS.format(slot=j['slot']))
    if record is None or record['state'] in ('rejected', 'unsent'):
        # Hold one request-local gate through the paid POST response. A peer
        # cannot start a new submission between the first refusal and its stop.
        with (run_stop['lock'] if run_stop is not None else contextlib.nullcontext()):
            check_run_stop()
            held = None if gated else _image_post_hold_gate(hold_path, receipt)
            if held is not None:
                # 앞 실행이 429 로 멈춘 작업 폴더 — 이 배치의 어느 슬롯도 새로 보내지 않는다(다른 일꾼은 run_stop 으로 멈춘다).
                if run_stop is not None:
                    run_stop['error'] = held
                raise held
            hdr = http_headers(headers)  # Credential/configuration failure precedes submission intent.
            record = {'state': 'submitting'}
            save()  # Must be durable BEFORE the paid POST, even if its response is lost.
            try:
                from runtime_metrics import event
                for _unsent_try in range(len(_UNSENT_RETRY_WAITS) + 1):
                    event('image', 'submitted', recipe)
                    try:
                        submitted = post_json(j['endpoint'], j['body'], hdr)
                        break
                    except Exception as exc:
                        # 요청이 제공자에 닿지 않았다(연결·본문 쓰기 단계 실패) — 접수 의도는 'submitting' 그대로 두고
                        # 상한 안에서 같은 본문을 다시 보낸다(첫 보냄이 처리될 수 없었으므로 중복 과금이 아니다).
                        if not _request_never_delivered(exc) or _unsent_try >= len(_UNSENT_RETRY_WAITS):
                            raise
                        _progress(f"  ⚠ [이미지] 슬롯 {j['slot']} 요청이 제공자에 닿지 않았다({type(exc.reason).__name__}) — "
                                  f"{_UNSENT_RETRY_WAITS[_unsent_try]}초 뒤 다시 보낸다", flush=True)
                        time.sleep(_UNSENT_RETRY_WAITS[_unsent_try])
                        check_run_stop()
                else:
                    # 마지막 회차는 닿지 않아도 위에서 다시 던진다 — 이 갈래는 «응답 아니면 예외» 계약이 깨졌을 때만 온다.
                    raise RuntimeError('이미지 접수 재시도가 응답도 예외도 없이 끝났다')
            except Exception as exc:
                code = getattr(exc, 'code', None)
                if isinstance(exc, (urllib.error.HTTPError, ApiRefused)) and code in (401, 402, 403, 429):
                    error = ProviderRefusalError('provider.image', 'HTTP_%d' % code,
                                                 'HTTP %d — 이 실행의 다른 이미지 요청도 중단했습니다' % code)
                    hold_error = None
                    if code in (402, 429):
                        # 다음 실행·같은 키의 다른 작업도 이 거절을 보게 키 단위 기록에 남긴다(_image_post_hold_gate) — 할 일(시각·표식)을 실은 거절로 바꿔 알린다.
                        # ★402(잔액 부족)도 키에 걸린다(10-21 뇌전구 신고: 한 사람 60편 · 402 를 편마다 다시 보내 44분에 142건 — 429 만 기록해
                        #   새 편·재실행이 거절을 몰랐다). 402 는 시각으로 풀리지 않으니 사람의 표식(충전 뒤)으로만 푼다.
                        try:
                            hold, _, now = _image_post_hold_save(hold_path, exc, j['slot'], receipt)
                            error = ProviderRefusalError('provider.image', 'HTTP_%d' % code, error.reason,
                                                         todo=_image_post_hold_todo(hold, hold_path, now))
                        except Exception as failure:
                            hold_error = failure
                    # Publish the stop before another receipt write can fail.
                    # The earlier submitting record then still protects paid intent.
                    if run_stop is not None:
                        run_stop['error'] = error
                    if code == 429:
                        # 슬롯은 «접수 응답 미확인» 그대로 두되 제공자가 429 로 답했다는 사실을 적는다 — 멈춤이 풀리면 이 슬롯부터 다시 보낸다.
                        try:
                            if hold_error is not None:
                                raise hold_error
                            record['http_status'] = 429
                            save()
                        except Exception as receipt_error:
                            error.receipt_error = str(receipt_error)[:300]
                            raise error from receipt_error
                    if _asr_definite_http_failure(exc):
                        record.update(state='rejected', http_status=code)
                        try:
                            save()
                        except Exception as receipt_error:
                            error.receipt_error = str(receipt_error)[:300]
                            raise error from receipt_error
                    if hold_error is not None:
                        # 402 멈춤 기록을 못 남겼다 — 다음 실행이 그 거절을 모른다는 사실을 함께 알린다(삼키지 않는다).
                        error.receipt_error = str(hold_error)[:300]
                        raise error from hold_error
                    raise error from exc
                if _asr_definite_http_failure(exc):
                    record.update(state='rejected', http_status=exc.code)
                    save()
                    raise StepError(f'이미지 접수가 HTTP {exc.code}로 거절됐습니다 (슬롯 {j["slot"]}). '
                                    '인증/요청을 수정한 뒤 같은 단계로 재개하세요.') from exc
                if _request_never_delivered(exc):
                    # 다시 보내도 닿지 않았다 — 접수된 적이 없으니 «unsent» 로 적어 다음 실행이 다시 보낸다(막다른 «미확인» 금지).
                    # ★지우지 않는다(10-21 뇌전구 신고): 예전에는 그 요청을 기록에서 빼서 빈 requests 를 저장했고, 읽는 쪽
                    #   (_image_load_receipt — «빈 기록 = 누가 지운 유료 기록» 이라 손상) 이 다음 실행부터 그 슬롯을 영영
                    #   «접수 기록 손상» 으로 막았다(한 편 12/12 · 10-20 20시부터 같은 정지 22번). 쓰는 쪽이 읽는 쪽 계약을 지킨다.
                    record.update(state='unsent')
                    save()
                    raise StepError(f'이미지 요청이 제공자에 닿지 않았습니다 (슬롯 {j["slot"]} · {type(exc.reason).__name__}: '
                                    f'{str(exc.reason)[:120]}) — {len(_UNSENT_RETRY_WAITS) + 1}번 보냈고 전부 연결 단계에서 '
                                    '끊겼습니다(접수·과금 없음). 인터넷 연결을 확인한 뒤 같은 명령을 다시 실행하면 이 슬롯부터 다시 보냅니다.') from exc
                raise StepError(f'이미지 접수 응답 미확인 (슬롯 {j["slot"]}) — 새 유료 요청을 '
                                f'자동 재전송하지 않습니다. 제공자 접수 확인 필요. 기록: {receipt} · '
                                + _tts_resend_hint(resend_mark, "슬롯")) from exc
            task_id = submitted.get('id') if isinstance(submitted, dict) else None
            if type(task_id) not in (str, int) or not str(task_id).strip():
                raise StepError(f'이미지 접수 응답에 작업 ID가 없습니다 — 새 유료 요청을 '
                                f'자동 재전송하지 않습니다. 기록: {receipt}')
            record.update(state='accepted', task_id=str(task_id))
            save()
    last = None
    for attempt in range(retry):
        try:
            if record['state'] == 'accepted':
                for _ in range(poll['max_tries']):
                    check_run_stop()
                    time.sleep(poll['interval_sec'])
                    check_run_stop()
                    result = request_call(lambda: get_json(
                        poll['endpoint_prefix'] + record['task_id'], http_headers(headers)))
                    status = result.get('status')
                    if status in poll['fail_status']:
                        record['state'] = 'failed'
                        save()
                        break
                    if status in poll['done_status']:
                        found = result.get('results') or [x['url'] for x in result.get('result_data', [])]
                        url = found[0] if found else None
                        if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
                            raise ValueError('완료 응답에 이미지 URL이 없습니다')
                        record.update(state='ready', url=url)
                        save()
                        break
                else:
                    raise TimeoutError(f'기존 작업 조회 {poll["max_tries"]}회 안에 완료되지 않았습니다')
            if record['state'] == 'failed':
                break
            try:
                check_run_stop()
                size = request_call(lambda: download(record['url'], raw + '.part'))
                if size <= min_bytes:
                    raise RuntimeError(f'내려받은 것이 {size}바이트 ≤ {min_bytes}')
            except ProviderRefusalError:
                raise
            except (urllib.error.HTTPError, ApiRefused) as exc:
                if getattr(exc, 'code', None) in (401, 402, 403, 429):
                    raise
                # Re-poll the SAME task to refresh an expired result URL next time.
                record['state'] = 'accepted'
                save()
                raise
            except Exception:
                # Re-poll the SAME task to refresh an expired result URL next time.
                record['state'] = 'accepted'
                save()
                raise
            record.update(state='downloaded', raw_sha256=_image_file_sha(raw + '.part'))
            save()
            _publish(raw + '.part', raw)
            record['state'] = 'complete'
            save()
            _progress(f"  {j['slot']:>3} ok {size // 1024}KB", flush=True)
            return record['url']
        except TranscriptionPending:
            raise  # Receipt write failure must never continue network activity.
        except Exception as exc:
            if isinstance(exc, ProviderRefusalError):
                raise
            refused = stop_for_http(exc)
            if refused is not None:
                raise refused from exc
            last = exc
            again, why = _retry_gate(exc, retry_policy)
            if not again:
                break
            if attempt + 1 < retry:
                check_run_stop()
                back = list((retry_policy or {}).get('backoff_s') or [])
                time.sleep(back[attempt] if attempt < len(back) else
                           (back[-1] if back else poll['interval_sec']))
    if record['state'] == 'failed':
        raise StepError(f'이미지 제공자 작업 {record["task_id"]}이 실패로 끝났습니다. '
                        f'같은 요청을 자동 재접수하지 않습니다. 기록: {receipt}' + _IMAGE_FAILED_WAYS.format(slot=j['slot']))
    raise StepError(f'이미지 작업 {record["task_id"]}의 조회/다운로드 미완료 (슬롯 {j["slot"]}). '
                    f'같은 단계로 재개하면 기존 접수만 확인합니다. 기록: {receipt}. '
                    f'마지막 오류: {type(last).__name__ if last else "pending"}') from last


def generate_images(jobs, poll, headers, retry, min_bytes, parallel=None, stagger=0.0,
                    retry_policy=None):
    """서버가 만든 요청 본문을 그대로 던지고 결과를 받아 저장한다.

    ★기본값을 두지 않는다. 재시도 횟수·최소 크기·대기 간격은 **전부 서버가 준 값**이다.
      기본값을 박아두면 서버가 값을 바꿔도 실행기가 안 따라간다 — 실제로 그 부류의
      하드코딩 사고가 세 번 있었다(보정 미반영 · 카드 종료시각 · 출력 파일명).

    ■ 결과 URL 을 돌려준다 (2026-08-25 — 소수정)
        지금까지는 결과 URL 로 내려받고 **버렸다.** 그런데 서버의 일관성 배선
        (같은 인물·배경을 잇는 참조 생성 — body.image_urls)은 **앞 칸 그림의
        URL** 이 필요하다(제공자 서버가 직접 받아갈 수 있는 주소여야 한다 —
        로컬 파일은 못 쓴다). 그래서 {슬롯: URL} 을 돌려주고, 캐시로 건너뛴
        슬롯도 지난 실행이 남긴 곁파일(raw+'.url')이 있으면 그 값을 준다.
        ★옛 서버는 이 반환값을 안 읽는다(measure 선언이 없으면 payload 에 안
          실린다) — 신구 혼재 무해.
    """
    import math
    backoff = (retry_policy or {}).get('backoff_s') or []
    if not isinstance(backoff, (list, tuple)):
        raise StepError('이미지 재시도 간격 형식이 유효하지 않습니다 — 접수 전에 서버 설정을 확인하세요.')
    waits = [poll.get('interval_sec'), stagger] + list(backoff)
    if (type(retry) is not int or retry < 1
            or type(poll.get('max_tries')) is not int or poll['max_tries'] < 1
            or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                   for value in waits)):
        raise StepError('이미지 재시도/조회 예산이 유효하지 않습니다 — 접수 전에 서버 설정을 확인하세요.')
    urls = {}
    import threading
    run_stop = {'lock': threading.Lock(), 'error': None}
    # 키 단위 429 멈춤 기록 자리 — 제공자 주소마다 지문 한 번(슬롯마다 다시 재지 않는다).
    hold_paths = {e: _image_post_hold_path(e, headers) for e in {j['endpoint'] for j in jobs}}

    def _one(j):
        raw = j["raw"]
        for pth in [raw, j.get("out")] + [st.get("out") for st in j.get("steps") or []]:
            if pth:
                os.makedirs(os.path.dirname(pth) or ".", exist_ok=True)
        receipt = _image_receipt_path(raw)
        os.makedirs(os.path.dirname(receipt), exist_ok=True)
        try:
            # Same OS lock used for ASR; process termination releases it on Windows/macOS.
            with _asr_lock(receipt + '.lock'):
                url = _image_generate_raw(j, poll, headers, retry, min_bytes, retry_policy, receipt, run_stop,
                                          hold_paths[j['endpoint']])
                if url:
                    urls[str(j['slot'])] = url
                    try:
                        with open(raw + '.url', 'w', encoding='utf-8') as fh:
                            fh.write(url)
                    except OSError:
                        pass  # URL also remains in the durable receipt.
                for step in j.get('steps') or []:
                    if 'copy' in step:
                        # 제자리 덮어쓰기(shutil.copyfile) 대신 작업 파일 쓰기 한 자리 — 사진 보기 프로그램이 쥔 칸도 교체를 다시 시도하고,
                        #   안 되면 무엇이 쥐었는지 말한다(2026-10-22 뇌전구 img43/07.png PermissionError 13).
                        src, dst = step['copy']
                        _publish_work_file(dst, src=src, what=f"그림 칸 {j.get('slot')} 을(를)")
                    else:
                        run_argv(step['argv'])
        except TranscriptionPending as exc:
            raise StepError(f'이미지 접수 기록 또는 실행 잠금을 확인해야 합니다. '
                            f'새 유료 접수를 보내지 않습니다. 기록: {receipt}') from exc

    _pool(jobs, parallel, _one, "이미지", stagger, stop_on_refusal=True)
    return urls


def _pluck(obj, expr):
    """JSON 에서 값을 꺼내는 **아주 작은 경로 평가기**. 서버가 준 `pick` 문자열을 읽는다.

    문법 (일반 기술이다 — 채널 지식이 아니다):
        a.b.c        점으로 내려간다
        a[]          리스트면 원소 전부, 딕셔너리면 값 전부로 갈라진다
        a[0]         리스트의 n번째
        x || y       왼쪽에서 못 찾으면 오른쪽
    ★실행기가 소스별 응답 모양을 알면 그게 규격이 된다. 그래서 **모양은 서버가 문자열로
      주고** 여기서는 그 문자열을 해석만 한다.
    """
    for alt in [e.strip() for e in expr.split("||")]:
        cur = [obj]
        ok = True
        for part in [p for p in alt.replace("[", ".[").split(".") if p]:
            nxt = []
            for c in cur:
                if part == "[]":
                    if isinstance(c, list):
                        nxt += c
                    elif isinstance(c, dict):
                        nxt += list(c.values())
                elif part.startswith("[") and part.endswith("]"):
                    i = int(part[1:-1])
                    if isinstance(c, list) and -len(c) <= i < len(c):
                        nxt.append(c[i])
                elif isinstance(c, dict) and part in c:
                    nxt.append(c[part])
            cur = nxt
            if not cur:
                ok = False
                break
        if ok:
            out = [c for c in cur if isinstance(c, str) and c]
            if out:
                return out
    return []


_QCACHE = {}
# ★파서가 알아낸 원본 크기. **받기 전에** 거르는 데 쓴다.
_SIZE_HINT = {}


def _api_json(url, headers, backoff, timeout=20):
    """Provider refusal ends this run; never retry it as a missing search result.

    First-refusal stop is the user's 2026-09-23 service policy. The backoff
    argument remains compatible with old plans but cannot authorize retries.
    """
    with review_dispatch():
        return get_json(url, headers, timeout)



# ── 구글 이미지 = 헤드풀 CDP ─────────────────────────────────────────────
#
# ■ 왜 urllib 으로 못 하나
#     구글 이미지는 **JS 가 돌아야** 결과가 나온다. 러너는 파이썬+urllib 이라 못 돈다.
#     그리고 **헤드리스는 차단된다** — 실측 6,195B(차단) vs 헤드풀 2,304,933B(정상).
#     그래서 수강생 PC 의 크롬을 **전용 프로필**로 띄워 CDP 로 붙는다.
#
# ■ 안 하는 것 — 오해를 미리 끊는다
#     ★사용자 프로필을 읽지 않는다. `--user-data-dir` 로 **빈 폴더**를 쓴다.
#       쿠키를 절취하지 않고, 로그인도 **필요 없다**.
#     ★CAPTCHA 를 풀지 않는다. 막히면 프로필을 갈고, 그래도 막히면 다음 소스로 간다.
#
# ■ 차단의 정체 (2026-08-16 실측)
#     차단 페이지가 답을 써 놨다: 「컴퓨터 네트워크에서 비정상적인 트래픽 … IP주소: …」
#     즉 예산은 **IP 단위**다. 다만 **갓 만든 프로필에는 유예분이 따로 붙어서**
#     프로필을 갈면 이어 갈 수 있다. 유예량은 고정이 아니다(아침 20회 → 오후 2회 → 0회)
#     — 그래서 차단을 맞을 때마다 한도를 **실측 통과값 아래로 내린다**.
#     완전히 소진되면 회복까지 **약 71분**이 걸린다(40분에도 여전히 차단이었다).
#
# ■ 수강생에게는 이 문제가 안 난다
#     한 편에 드는 질의는 20여 회이고 IP 도 사람마다 다르다. 더워지는 것은 대량 실행뿐이다.

_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
)
# ★★차단 표식·크기 문턱은 **서버가 준다**(`volcano_spec.BROWSER_POLICY`).
#   여기 목록을 두지 않는다 — §"실행기에 기본값을 두지 않는다": 서버가 값을 바꿔도
#   실행기가 안 따라간다. 실제로 그렇게 갈려 있었다(2026-08-18 실측):
#     서버 6개(`recaptcha` 포함) ↔ 실행기 4개(`recaptcha` **없음**)
#   그래서 reCAPTCHA 화면이 「차단 아님」으로 읽혀 **사람을 부르지도 않고
#   조용히 0장**이 될 수 있었다.


def _chrome_path():
    for p in _CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("google-chrome") or shutil.which("chromium") or None


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Chrome:
    """전용 프로필로 크롬을 띄우고 CDP 로 DOM 을 읽는다.

    ★`headless` 는 **서버가 정한다**(§BROWSER_POLICY). 실행기에 기본값을 두면
      서버가 바꿔도 안 따라온다 — 이 저장소가 세 번 겪은 부류다.
      기본을 `None` 으로 두어, 안 주면 부르는 쪽이 fail-closed 로 막는다.
    """

    def __init__(self, profile, headless=False):
        self.profile = profile
        self.port = _free_port()
        self.proc = None
        self.headless = bool(headless)

    def __enter__(self):
        exe = _chrome_path()
        if not exe:
            raise StepError(
                "크롬을 못 찾았다 — 구글 이미지 조달에는 크롬이 필요하다.\n"
                "  설치되어 있는데도 이 오류가 나면 설치 경로를 알려 달라.")
        os.makedirs(self.profile, exist_ok=True)
        args = [exe,
                f"--user-data-dir={self.profile}",
                f"--remote-debugging-port={self.port}",
                # ★크롬 111+ 는 이게 없으면 CDP 가 403 을 준다
                "--remote-allow-origins=*",
                "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking",
                "--disable-features=Translate,OptimizationHints",
                "--lang=ko-KR", "--window-size=1280,900"]
        if self.headless:
            # ★★창을 띄우지 않는다 (2026-08-18 사장님 지시). 수강생이 영상 만드는
            #   내내 크롬이 떴다 뜨면 안 된다. 막히면 그때만 창을 연다(유인 모드).
            #   `--headless=new` 다 — 옛 `--headless` 는 CDP 동작이 다르다.
            args.append("--headless=new")
        args.append("about:blank")
        # ★프로세스 **그룹의 장**으로 띄운다. 크롬은 렌더러·GPU 헬퍼를 따로 띄우는데
        #   부모만 죽이면 본체가 멈췄을 때 헬퍼가 남는다(실측: 61개가 쌓였다).
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL,
                                     start_new_session=True)
        try:
            for _ in range(120):
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{self.port}/json/version", timeout=1).read()
                    return self
                except Exception:                                  # noqa: BLE001, S112
                    if self.proc.poll() is not None:
                        err = (self.proc.stderr.read() or b"").decode("utf-8", "replace")
                        if "SingletonLock" in err or "ProcessSingleton" in err:
                            raise StepError(
                                "이 프로필을 쓰는 크롬 창이 이미 열려 있다.\n"
                                "  ★잠금은 프로필이 아니라 **폴더 단위**다 — "
                                "그 폴더를 쓰는 창을 닫고 다시 하라.")
                        raise StepError(f"크롬이 떴다가 죽었다: {err.strip()[:200]}")
                    time.sleep(0.25)
            raise StepError("CDP 포트가 30초 안에 안 열렸다")
        except BaseException:
            # ★`__enter__` 가 예외를 내면 파이썬은 `__exit__` 를 **안 부른다.**
            #   여기서 정리하지 않으면 크롬이 통째로 남는다.
            self._reap()
            raise

    def _reap(self):
        if not self.proc:
            return
        try:
            pgid = os.getpgid(self.proc.pid)
        except (ProcessLookupError, PermissionError, AttributeError):
            pgid = None
        if self.proc.poll() is None:
            try:
                if pgid is not None and hasattr(os, "killpg"):
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    self.proc.terminate()
            except (ProcessLookupError, PermissionError, OSError):  # noqa: S110
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    if pgid is not None and hasattr(os, "killpg"):
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        self.proc.kill()
                except (ProcessLookupError, PermissionError, OSError):  # noqa: S110
                    pass
        try:
            self.proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, ChildProcessError):      # noqa: S110
            pass
        if self.proc.stderr:
            try:
                self.proc.stderr.close()
            except OSError:                                         # noqa: S110
                pass
        self.proc = None

    def __exit__(self, *a):
        self._reap()

    def _post(self, path, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", method="PUT" if body else "GET")
        return json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

    def open_tab(self, url):
        """탭을 열고 **닫지 않는다.** 사람이 그 화면을 봐야 하는 자리에서 쓴다.

        ★`fetch_dom` 은 읽고 **탭을 닫는다.** 캡차를 사람이 푸는 동안 그것을 쓰면
          2초마다 탭이 열렸다 닫혀서 **사람이 캡차를 볼 수가 없다**(실제로 그렇게
          만들었다가 사장님 지적으로 잡았다 — 2026-08-18).
        ★그리고 매번 **새 구글 요청**이 나간다 = 예산을 더 먹고 차단을 더 부른다.
          열어 둔 탭의 DOM 을 읽으면 요청이 **한 번도 안 나간다.**
        """
        import urllib.parse as _up
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/json/new?{_up.quote(url, safe='')}",
            method="PUT")
        tab = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        return tab["webSocketDebuggerUrl"], tab["id"]

    def read_tab(self, ws):
        """열려 있는 탭의 **지금** DOM. 새 요청을 만들지 않는다."""
        return _cdp_outer_html(ws)

    def close_tab(self, tid):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/json/close/{tid}", timeout=5).read()
        except Exception:                                          # noqa: BLE001, S110
            pass

    def fetch_dom(self, url, settle=6.0):
        """새 탭에서 열고 JS 가 자리잡을 때까지 기다렸다가 DOM 전체를 돌려준다."""
        import urllib.parse as _up
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/json/new?{_up.quote(url, safe='')}",
            method="PUT")
        tab = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        ws = tab["webSocketDebuggerUrl"]
        tid = tab["id"]
        try:
            time.sleep(settle)
            return _cdp_outer_html(ws)
        finally:
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/close/{tid}", timeout=5).read()
            except Exception:                                       # noqa: BLE001, S110
                pass


def _cdp_outer_html(ws_url):
    """CDP 로 `document.documentElement.outerHTML` 을 읽는다(의존성 없이 websocket 직접)."""
    import base64
    import socket
    import struct
    import urllib.parse as _up
    u = _up.urlparse(ws_url)
    sock = socket.create_connection((u.hostname, u.port), timeout=20)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
                  "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                  "Origin: http://127.0.0.1\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise StepError("CDP 웹소켓 악수 실패")
        buf += chunk
    payload = json.dumps({"id": 1, "method": "Runtime.evaluate",
                          "params": {"expression":
                                     "document.documentElement.outerHTML",
                                     "returnByValue": True}}).encode()
    mask = os.urandom(4)
    n = len(payload)
    head = b"\x81"
    if n < 126:
        head += struct.pack("!B", 0x80 | n)
    elif n < 65536:
        head += struct.pack("!BH", 0x80 | 126, n)
    else:
        head += struct.pack("!BQ", 0x80 | 127, n)
    sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _read(k):
        out = b""
        while len(out) < k:
            c = sock.recv(k - len(out))
            if not c:
                raise StepError("CDP 웹소켓이 끊겼다")
            out += c
        return out

    frames = b""
    while True:
        b1, b2 = _read(2)
        ln = b2 & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", _read(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", _read(8))[0]
        data = _read(ln)
        frames += data
        if b1 & 0x80:
            break
    sock.close()
    try:
        msg = json.loads(frames.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return ""
    return (((msg.get("result") or {}).get("result") or {}).get("value")) or ""


def _google_classify(html, pol=None):
    """차단인가. **표식과 문턱은 서버가 준다** — 실행기가 정하지 않는다.

    ★대소문자를 접어서 본다. 예전 판은 원문 그대로 비교해서 `reCAPTCHA` 같은
      섞인 표기를 놓쳤다(표식을 소문자로 적어 두면 영영 안 맞는다).
    ★정책이 없으면 **막는다**(fail-closed). 판정할 수 없는데 「차단 아님」으로
      넘기면 조용히 0장이 되고, 「차단」으로 넘기면 멀쩡한 페이지에 사람을 부른다.
      둘 다 나쁘므로 **부르는 쪽에서** 정책을 요구한다(`_google_source` 축 ③).
    """
    pol = pol or {}
    marks = tuple(str(t).lower() for t in (pol.get("block_markers") or ()) if t)
    if not marks:
        raise RuntimeError(
            "구글 차단 표식(block_markers)이 없다 — 서버 정책 없이는 판정할 수 없다")
    cap = int(pol.get("block_max_bytes") or 0)
    if cap <= 0:
        raise RuntimeError("구글 차단 크기 문턱(block_max_bytes)이 없다 — 서버가 준다")
    low = (html or "")[:200000].lower()
    if any(t in low for t in marks) and len(html or "") < cap:
        return "차단"
    # ★`sorry/index` 로 판정하면 안 된다 — **정상 2.3MB 페이지에도 5번 나온다.**
    return "결과" if len(html or "") > cap else "빈결과"


# ── 구글 응답 파서 — **URL 과 크기를 함께** 뽑는다 ────────────────────────
#
# ■ 왜 바꿨나
#     옛 파서는 HTML 에서 이미지 URL 만 정규식으로 긁었다. 그래서 `min_px` 를
#     **받아 본 뒤에야** 알 수 있었고, 작은 그림도 일단 내려받았다.
#     구글은 스크립트 안에 **`["url", 가로, 세로]` 삼중항**을 실어 준다.
#     그걸 읽으면 **받기 전에** 거른다 — 헛다운로드가 사라진다.
#     실측(같은 페이지): 옛 파서 URL 63개(크기 모름) → 새 파서 **99개 전부 크기 있음**,
#     그중 짧은변 400px 미만이 11개였다. 그 11개를 안 받는다.
#
# ★출처: all-in-one-production `googleResponseParser.ts` 의 판단 절차를 옮긴 것이다.
_AF_INIT_RE = re.compile(r"AF_initDataCallback\(([\s\S]*?)\);")
_HTTP_DIM_RE = re.compile(r'\["((?:https?:)?//[^"]+)",(\d+),(\d+)\]')
_IMGRES_RE = re.compile(r"/imgres\?imgurl=[^\"'<>\\\s]+")
_IMG_RE = re.compile(r'https?://[^"\'\s\\<>]+?\.(?:jpg|jpeg|png|webp|gif)'
                     r'(?:\?[^"\'\s\\<>]*)?', re.I)


def _unescape_block(v):
    for a, b in ((r"\u003d", "="), (r"\u0026", "&"), (r"\u002f", "/"),
                 (r"\u003f", "?"), (r"\x3d", "="), (r"\x26", "&"), (r"\\/", "/")):
        v = v.replace(a, b).replace(a.upper(), b)
    return v


def _norm_url(v):
    if not v:
        return ""
    import html as _h
    v = _h.unescape(v.strip())
    try:
        v = urllib.parse.unquote(v)
    except (ValueError, UnicodeDecodeError):                     # noqa: S110
        pass
    if v.startswith("//"):
        return "https:" + v
    return v if v.startswith(("http://", "https://")) else ""


def _valid_img_url(u):
    """DOM 에서 뽑은 잘린 조각을 뺀다(`https://kor.png` 같은 것).

    호스트에 점이 있어야 하고, 호스트 자체가 이미지 확장자로 끝나면 안 되고,
    경로가 있어야 한다.
    """
    try:
        import urllib.parse as _up
        pr = _up.urlparse(u)
    except ValueError:
        return False
    host = (pr.hostname or "").lower()
    if "." not in host or len(host) < 4:
        return False
    if host.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return False
    return len(pr.path) > 1


def _google_extract(html):
    """후보를 `{url, w, h}` 로 돌려준다. **세 갈래를 순서대로** 쓴다.

    ① AF_initDataCallback 삼중항  — 크기가 함께 온다(가장 정확)
    ② /imgres?imgurl=…&w=&h=      — 링크에 크기가 박혀 있다
    ③ 맨 정규식                    — 위 둘이 빈손일 때만. **크기는 0(모름)** 이다
    ★`w`/`h` 가 0이면 「모른다」는 뜻이다. 0을 「작다」로 읽으면 안 된다.
    """
    text = html or ""
    # Source-page metadata belongs to the exact image URL, never to the query.
    for link in _IMGRES_RE.finditer(text):
        import html as _html
        params = urllib.parse.parse_qs(urllib.parse.urlparse(_html.unescape(link.group(0))).query)
        original = _norm_url((params.get('imgurl') or [''])[0])
        page = (params.get('imgrefurl') or [''])[0]
        if original and page:
            _PHOTO_SOURCE_META[original] = {'page_url': page}
    # ① 삼중항
    out, seen = [], set()
    blocks = [m.group(1) for m in _AF_INIT_RE.finditer(text)] or [text]
    for b in blocks:
        for m in _HTTP_DIM_RE.finditer(_unescape_block(b)):
            u = _norm_url(m.group(1))
            if not u or u in seen or not _valid_img_url(u) or "gstatic.com" in u:
                continue
            seen.add(u)
            out.append({"url": u, "w": int(m.group(2) or 0),
                        "h": int(m.group(3) or 0)})
    if out:
        return out
    # ② imgres
    for m in _IMGRES_RE.finditer(text):
        import html as _h
        q = urllib.parse.parse_qs(
            urllib.parse.urlparse(_h.unescape(m.group(0))).query)
        u = _norm_url((q.get("imgurl") or [""])[0])
        if not u or u in seen or not _valid_img_url(u):
            continue
        seen.add(u)

        def _n(k):
            try:
                return int((q.get(k) or ["0"])[0])
            except ValueError:
                return 0
        out.append({"url": u, "w": _n("w"), "h": _n("h")})
    if out:
        return out
    # ③ 마지막 그물
    for m in _IMG_RE.finditer(text):
        u = m.group(0)
        if u in seen or not _valid_img_url(u):
            continue
        if "gstatic.com" in u or "google.com/images/branding" in u:
            continue
        seen.add(u)
        out.append({"url": u, "w": 0, "h": 0})
    return out


class _GoogleCDP:
    """구글 소스. 프로필을 갈아 가며 쓰고, 차단을 맞으면 한도를 스스로 내린다."""

    def __init__(self, profile_base, rotate_at=18, max_profiles=200, policy=None):
        self.base = profile_base
        self.rotate_at = rotate_at
        self.max_profiles = max_profiles
        # ★정책은 **서버가 준다**(§BROWSER_POLICY). 없으면 부르는 쪽이 막는다.
        self.pol = dict(policy or {})
        self.slot = 0
        self.n_in_profile = 0
        self.ctx = None
        self.ch = None
        self.cur = None
        self.alive = True
        # ★★「이 기계에는 사람이 없다」 — `_attend` 가 상한까지 기다렸는데 아무도
        #   안 풀면 켜진다. 켜지면 다시 안 기다린다(자동 실행이 몇 시간 멎는다).
        #   실행 하나 동안만 산다 — 다음 실행에서는 다시 물어본다.
        self.attend_off = False

    def _open(self):
        self._close()
        if self.cur and os.path.isdir(self.cur):
            shutil.rmtree(self.cur, ignore_errors=True)
        # ★프로필은 **매번 새로 만든다.** 번호를 재사용하면(`_r00`, `_r01` …)
        #   다음 실행이 같은 폴더로 돌아와 누적이 쌓이고 로테이션이 무의미해진다.
        self.cur = f"{self.base}_{int(time.time())}_{os.getpid()}_{self.slot:03d}"
        self.ctx = _Chrome(self.cur, headless=bool(self.pol.get('headless')))
        self.ch = self.ctx.__enter__()
        self.n_in_profile = 0

    def _close(self):
        if self.ctx is not None:
            try:
                self.ctx.__exit__(None, None, None)
            except Exception:                                       # noqa: BLE001, S110
                pass
            self.ctx = self.ch = None

    def _rotate(self, why):
        if self.slot + 1 >= self.max_profiles:
            self._close()
            self.alive = False
            return False
        self.slot += 1
        _progress(f"    (구글 프로필 교체 #{self.slot:03d} — {why})", flush=True)
        self._open()
        return True

    def _adapt(self):
        """차단을 맞으면 한도를 **실제로 통과한 횟수 아래로** 내린다."""
        new = max(1, min(self.rotate_at, max(1, self.n_in_profile - 1)))
        if new < self.rotate_at:
            _progress(f"    (구글 한도 {self.rotate_at} → {new} 로 낮춘다)", flush=True)
            self.rotate_at = new

    def _reopen(self, headless):
        """**같은 프로필**로 크롬을 다시 띄운다. 쿠키가 이어져야 푼 것이 살아남는다.

        ★★`ctx` 와 `ch` 를 **둘 다** 바꾼다. 처음엔 `ch` 만 바꿨는데, `_close()` 는
          `ctx` 를 닫으므로 **옛 크롬을 닫고 새 것을 남겼다** — 실측에서 닫은 뒤에도
          프로세스 **8개**가 살아 있었다(§"61개가 쌓였다" 와 같은 부류).
          `_open()` 이 그 둘을 함께 세운다는 사실을 여기서도 지켜야 한다.
        ★크롬은 `--user-data-dir` 을 잠근다 — 완전히 닫힌 뒤에 열어야 한다.
        ★프로필 폴더를 **지우지 않는다**(`_open` 과 다른 점) — 캡차 면제가 쿠키에
          들어 있어서, 지우면 방금 푼 것이 날아간다.
        """
        if self.ctx is not None:
            try:
                self.ctx.__exit__(None, None, None)
            except Exception:                                      # noqa: BLE001, S110
                pass
            self.ctx = self.ch = None
        for _ in range(40):                       # 잠금이 풀릴 때까지(최대 4초)
            if not os.path.exists(os.path.join(self.cur, "SingletonLock")):
                break
            time.sleep(0.1)
        self.ctx = _Chrome(self.cur, headless=headless)
        self.ch = self.ctx.__enter__()

    def _attend(self, url, settle, html):
        """차단이면 **창을 열어** 사람이 캡차를 풀게 하고, 풀리면 **다시 헤드리스로** 간다.

        ■ 흐름 (사장님 지시 2026-08-18)
            (1) 헤드리스로 간다 — 창이 안 뜬다 · 빠르다
            (2) 막히면 **그때만** 창을 연다 — 같은 프로필로
            (3) 사람이 풀면 **바로 인식**한다 (차단 표식이 사라지는 것이 신호다)
            (4) **창을 닫고 다시 헤드리스로 이어 간다** — 그래야 빠르다
        ★(3)에서 (4)가 되는 이유: 캡차 면제는 **쿠키에 들어간다.** 같은 프로필을 그대로
          쓰므로 헤드리스로 돌아가도 면제가 살아 있다(쇼핑 실측: 재요청 차단 0).
        ★푼 뒤에는 **한 번 다시 받는다.** 그 판의 응답은 캡차 시점에 묶여 있다
          (쇼핑 실측: 본문이 None 으로 온다).
        ★상한이 있다 — 넘으면 다음 소스로 간다. **영원히 서지 않는다.**
        ★사람이 없는 기계(cron·CI)에서는 상한까지 기다렸다 나간다. 그래서
          `attend_on_block` 을 **서버가** 끌 수 있게 두었다.
        """
        wait_s = int(self.pol.get("solve_wait_sec") or 0)
        if wait_s <= 0:
            return html
        want_headless = bool(self.pol.get("headless"))
        try:
            self._reopen(headless=False)          # (2) 창을 연다 (같은 프로필)
        except Exception as e:                                     # noqa: BLE001
            _progress(f"    (창을 못 열었다 — {type(e).__name__}. 다음 소스로 간다)", flush=True)
            return html
        _progress("    [구글] 캡차가 떴습니다 — **방금 열린 크롬 창에서 풀어 주세요.**\n"
              f"           **풀 때까지 창을 닫지 않습니다.** 푸는 즉시(2초 안에) "
              f"알아채고 창을 닫은 뒤 헤드리스로 이어 갑니다.", flush=True)
        # ★★탭을 **열어 두고** 그 탭만 본다. `fetch_dom` 을 쓰면 읽고 나서 탭을 닫아
        #   2초마다 화면이 사라진다 — 사람이 캡차를 **볼 수가 없다**(그렇게 만들었다가
        #   사장님이 잡았다). 게다가 매번 새 구글 요청이라 예산을 더 먹는다.
        try:
            ws, tid = self.ch.open_tab(url)
        except Exception as e:                                     # noqa: BLE001
            _progress(f"    (캡차 화면을 못 띄웠다 — {type(e).__name__}. 다음 소스로 간다)",
                  flush=True)
            return html
        # ★★**풀 때까지 창을 닫지 않는다** (사장님 지시: *"못 풀면 바로 띄워야지"*).
        #   처음엔 240초에 포기하고 다음 소스로 갔는데, 그건 **사람이 잠깐 자리를 비운
        #   것**과 «못 푼다»를 같은 것으로 다룬 것이다. 캡차는 사람이 오면 풀린다.
        # ★조용히 기다리지 않는다 — `remind_every_sec` 마다 다시 알린다.
        #   안 알리면 멎은 줄 알고 수강생이 끈다.
        remind = int(self.pol.get("remind_every_sec") or 30)
        t0, solved, last = time.time(), False, time.time()
        try:
            while time.time() - t0 < wait_s:
                time.sleep(2.0)
                try:
                    probe = self.ch.read_tab(ws)                   # 요청이 안 나간다
                except Exception:                                  # noqa: BLE001
                    continue
                if _google_classify(probe, self.pol) != "차단":      # (3) 바로 인식
                    solved = True
                    break
                if remind and time.time() - last >= remind:
                    left = int(wait_s - (time.time() - t0))
                    _progress(f"    [구글] 아직 캡차가 떠 있습니다 — **크롬 창에서 풀어 주세요** "
                          f"(창은 그대로 둡니다 · 남은 {left // 60}분 {left % 60}초)",
                          flush=True)
                    last = time.time()
        finally:
            self.ch.close_tab(tid)                                 # 판정이 끝난 뒤에만 닫는다
        if not solved:
            # ★★여기까지 온 것은 «이 기계에 사람이 없다» 는 뜻이다(30분을 기다렸다).
            #   **그 사실을 기억한다.** 안 그러면 막힐 때마다 30분씩 또 서서
            #   자동 실행이 몇 시간 멎는다. 사람이 있는 기계에서는 여기 안 온다.
            self.attend_off = True
            _progress(f"    [구글] {wait_s // 60}분을 기다렸는데 안 풀렸습니다 — "
                  f"이 기계에는 사람이 없는 것으로 보고 다음 소스로 갑니다.\n"
                  f"           (사람이 있는데 이 줄을 보셨다면 알려 주세요 — "
                  f"기다리는 시간은 서버가 정합니다)", flush=True)
            return html
        _progress("    [구글] 캡차가 풀렸습니다 — 창을 닫고 **헤드리스로 이어 갑니다**", flush=True)
        # (4) 다시 헤드리스로. 쿠키(면제)는 같은 프로필에 남아 있다.
        if want_headless:
            try:
                self._reopen(headless=True)
            except Exception as e:                                 # noqa: BLE001
                _progress(f"    (헤드리스 복귀 실패 — {type(e).__name__}. 창을 켠 채로 간다)",
                      flush=True)
        try:
            out = self.ch.fetch_dom(url, settle=settle)
            self.n_in_profile += 1          # ★진짜 구글 요청이다 — 예산에 센다
            return out
        except Exception:                                          # noqa: BLE001
            return html

    def urls(self, query, gl="kr", hl="ko", settle=6.0):
        if not self.alive:
            return []
        if self.ch is None:
            self._open()
        if self.n_in_profile >= self.rotate_at and not self._rotate("한도 도달"):
            return []
        import urllib.parse as _up
        url = ("https://www.google.com/search?q=" + _up.quote(query) +
               f"&udm=2&hl={hl}&gl={gl}")
        html = self.ch.fetch_dom(url, settle=settle)
        self.n_in_profile += 1
        # ★★막히면 **사람을 부른다** (2026-08-18 사장님 지시: 헤드리스로 하고 캡차만 푼다).
        #   지금까지는 프로필만 갈고 안 되면 조용히 0장이었다 — 오늘 실측에서
        #   **헤드풀도 2번째 질의에서 막혔다**(6,258B). 즉 「헤드풀이면 안 막힌다」는
        #   전제가 이미 무너졌고, 남는 것은 «조용히 0장» 뿐이었다.
        tries = 0
        while _google_classify(html, self.pol) == "차단":
            if self.pol.get('block_action') == 'next_source':
                self._close()
                self.alive = False
                _progress('    [구글] 차단을 확인했습니다. 기다리거나 재요청하지 않고 다음 사진 출처로 이어 갑니다.', flush=True)
                return []
            # ★★부르는 자리가 **반복문 안**이다 (사장님 지시: *"못 풀면 바로 띄워야지"*).
            #   처음엔 반복문 **밖**에 한 번만 있었다 — 프로필을 갈고 또 막히면
            #   사람에게 **다시 물어보지도 않고** 조용히 다음 소스로 갔다.
            #   막혔는데 자동으로 못 뚫으면 **그때마다** 창을 띄우는 것이 맞다.
            if self.pol.get("attend_on_block") and not self.attend_off:
                html = self._attend(url, settle, html)
                if _google_classify(html, self.pol) != "차단":
                    break                       # 사람이 풀었다 — 그대로 이어 간다
            self._adapt()
            tries += 1
            if tries > 3:
                # ★새 프로필 3개가 연속으로 막히면 유예마저 없는 상태다(IP 소진).
                #   더 두드리지 않는다 — 두드리면 차단이 길어진다. 다음 소스로 간다.
                self._close()
                self.alive = False
                _progress("    (구글 소진 — 이 실행에서는 끈다. 회복까지 약 70분)",
                      flush=True)
                return []
            if not self._rotate(f"차단 @{self.n_in_profile}회"):
                return []
            html = self.ch.fetch_dom(url, settle=settle)
            self.n_in_profile += 1
        return _google_extract(html)

    def close(self):
        self._close()
        if self.cur and os.path.isdir(self.cur):
            shutil.rmtree(self.cur, ignore_errors=True)
        self.cur = None


_GOOGLE = None


def _google_source(src):
    global _GOOGLE
    if _GOOGLE is None:
        base = src.get("profile_base") or os.path.join(
            os.path.expanduser("~"), ".volcano", "gimg")
        os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
        # ★★정책이 없으면 **멈춘다.** 실행기에 기본값을 두면 서버가 바꿔도 안 따라온다
        #   (§retry_policy 와 같은 규율). 조용히 헤드풀로 도는 것이 오늘 지적된 것이다.
        if "headless" not in src:
            raise StepError(
                "구글 소스에 **브라우저 정책이 없다**(headless·attend_on_block …).\n"
                "  이 값은 서버가 준다(`volcano_spec.BROWSER_POLICY`). 없으면 창을\n"
                "  띄울지 말지를 실행기가 제멋대로 정하게 된다 — 그래서 멈춘다.\n"
                "  ★서버가 옛 판이면 `assets` 를 다시 불러 최신 배급을 받아라.")
        _GOOGLE = _GoogleCDP(base,
                             rotate_at=int(src.get("rotate_at") or 18),
                             max_profiles=int(src.get("max_profiles") or 200),
                             policy=src)
    return _GOOGLE



# ── 이라스토야 = **로컬 인덱스 조회** (검색이 아니다) ──────────────────────
#
# ■ 왜 검색이 아닌가
#     이라스토야 그림 **23,422건**의 인덱스가 이미 있다. 네트워크도 키도 필요 없다.
#     제목·태그가 **영어로 번역**돼 있고(`"Illustration of a torch"`),
#     한글 질의는 **한글→영어 매핑**으로 넓힌다.
#     ★그래서 구글 차단·속도 제한과 **아무 상관이 없다.** 군림보의
#       「상황에 맞게 이라스토야」가 이걸로 성립한다.
#
# ■ 점수 (제목 완전일치 10 · 제목 포함 5 · 태그 포함 3)
#
# ■ ★맞는 게 없으면 **빈손을 준다.** 「비슷한 것」을 억지로 주지 않는다 —
#     그림이 안 맞으면 그 컷만 조용히 틀린 화면이 된다.

_IRAS_CACHE = {}
_IRAS_WORD = re.compile(r"[a-zA-Z0-9]+")
_IRAS_HANGUL = re.compile(r"[가-힣]+")


def _iras_load(path):
    p = os.path.expanduser(path or "")
    if p in _IRAS_CACHE:
        return _IRAS_CACHE[p]
    if not p or not os.path.exists(p):
        raise StepError(
            f"이라스토야 인덱스가 없다: {p}\n"
            "  ★없는 채로 넘어가지 않는다 — 빈손이 조용히 통과하면 그 컷이 비고,\n"
            "    렌더가 나중에 죽는다. 인덱스를 배급에 실어라.")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    _IRAS_CACHE[p] = d
    return d


def _iras_expand(query, ko_en):
    """한글 질의를 영어 낱말로 넓힌다."""
    out = []
    for w in re.split(r"[\s,·/]+", (query or "").strip()):
        if not w:
            continue
        if _IRAS_WORD.fullmatch(w):
            out.append(w.lower())
            continue
        if w in ko_en:
            out += ko_en[w].split()
            continue
        for ko, en in ko_en.items():
            if _IRAS_HANGUL.fullmatch(ko) and (ko in w or w in ko):
                out += en.split()
                break
    seen, uniq = set(), []
    for w in out:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq


def _iras_scored(src, query):
    """색인 텍스트 점수 — [(항목번호, 점수)] 점수 내림차순(동점은 삽입 순서 안정).

    ★자는 **하나다** (2026-08-25): 조달 경로(`_iras_urls` — 꺄오옷·강석주
      IMAGE_SOURCES)와 몫 섞기 프로브(`iras_probe` — 군림보)가 같은 이 함수를
      쓴다. 두 벌이면 언젠가 답이 갈린다. 리팩터 전후 URL 목록이 바이트
      동일함은 채록(tools/verify_gunrimbo/fixtures/legacy_runner_iras_urls.json)
      이 증명한다 — 점수식(완전일치 10 · 포함 5 · 태그 3)·정렬 전부 그대로다.
    """
    d = _iras_load(src.get("index"))
    kws = _iras_expand(query, d.get("ko_en") or {})
    if not kws:
        return [], d
    score = {}
    items, index = d["items"], d["index"]
    for kw in kws:
        for n in index.get(kw, ()):
            it = items[n]
            tl = (it.get("t") or "").lower()
            add = 10 if tl == kw else (5 if kw in tl else 0)
            if any(kw in (t or "").lower() for t in it.get("g") or ()):
                add += 3
            if add:
                score[n] = score.get(n, 0) + add
    return sorted(score.items(), key=lambda kv: -kv[1]), d


def _iras_urls(src, query, limit=12):
    best, d = _iras_scored(src, query)
    return [d["items"][n]["u"] for n, _ in best[:limit]]


def iras_probe(item):
    """슬롯마다 색인 **최고 점수와 후보(URL·제목)** 를 잰다 — 로컬 조회(네트워크·
    키·비용 0). **판정(어느 칸이 이라스토야인가)은 서버가 한다.**

    ★색인 경로·질의·후보 수 전부 서버가 준다(`src`·`queries`·`want`) — 러너에
      채널 값 0. 색인 실물은 자산 팩(iras_gunrimbo)이 작업폴더에 푼 것이다.
    ★제목도 함께 올린다 — 컨택트시트 검수와 칸 기록(imgsource)이 「어느 그림을
      골랐는지」를 남기는 데 쓴다(주소만 주면 다시 놓을 수가 없다 — 실측 교훈).
    """
    src = item.get("src") or {}
    want = int(item.get("want") or 10)
    out = {}
    for k, qs in sorted((item.get("queries") or {}).items(), key=lambda x: int(x[0])):
        q = (qs[0] if isinstance(qs, list) and qs else str(qs or "")).strip()
        best, d = _iras_scored(src, q)
        if item.get('all_queries') and isinstance(qs,list):
            scores=dict(best)
            for alternate in qs[1:]:
                more,_=_iras_scored(src,str(alternate).strip())
                for index,score in more:
                    scores[index]=max(scores.get(index,0),score)
            best=sorted(scores.items(),key=lambda pair:-pair[1])
        items = d.get("items") or []
        top = best[:want]
        out[str(k)] = {"score": (float(top[0][1]) if top else None),
                       "urls": [items[n].get("u") for n, _ in top],
                       "titles": [items[n].get("t") for n, _ in top]}
    return out


def place_illust(item):
    """이라스토야 실물을 받아 **흰 판(슬롯 크기)에 실측 비율로** 놓는다.
    (tikitaka getimg.flatten_white 이관 · 2026-08-25 — 값은 전부 서버 params)

    ■ 왜 이렇게 놓나 (실측 — 사장님 「이라스토야를 왜 이렇게 확대시켜 놨어!」)
        실물 30편 실측: 흰 바탕은 슬롯을 **꽉** 채우고, 그림 자체는 그 안에서
        잉크 기준 세로/가로 비율·세로중심(`fit`)에 놓인다. 꽉 채워 늘리면 실물과
        다른 화면이 된다. 옆으로 긴 그림은 가로가 먼저 차 세로가 실물 한계 밖으로
        내려간다 — 실물 한계(`band`: 세로 아래끝·가로 위끝)까지 **키우기만** 한다
        (비율은 안 건드린다 — 늘리면 그림이 찌그러진다).
    ★값을 지어내지 않는다 — fit/band/slot 이 없으면 멈춘다(「쟀다」와 「안 쟀다」가
      화면에서 구별이 안 되게 하는 기본값 금지 · tikitaka 규율 그대로).
    """
    import io as _io
    from PIL import Image
    import numpy as np
    url, out = item.get("url"), item.get("out")
    if not url or not out:
        raise StepError("place_illust 에 url/out 이 없다 — 서버 응답이 이상하다")
    fit, slot = item.get("fit") or {}, item.get("slot") or []
    if len(slot) != 2 or any(fit.get(x) is None for x in ("h", "w", "cy")):
        raise StepError("place_illust 에 slot/fit(실측)이 없다 — 기본값을 박지 않는다. "
                        "서버 규격(ILLUST_PLACE)을 확인하라.")
    part = str(out) + ".part"
    n = download(url, part, timeout=60)
    if n < int(item.get("min_bytes") or 3000):
        raise StepError(f"이라스토야 실물이 {n}바이트 — 너무 작다: {str(url)[:80]}")
    with open(part, "rb") as fh:
        im = Image.open(_io.BytesIO(fh.read()))
        im.load()
    try:
        os.remove(part)
    except OSError:
        pass
    # 투명 그림은 흰 바탕에 얹는다 — 실물 일러스트가 그렇게 생겼다(격자무늬 방지)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, rgba).convert("RGB")
    else:
        im = im.convert("RGB")
    SW, SH = int(slot[0]), int(slot[1])
    hf, wf, cy = float(fit["h"]), float(fit["w"]), float(fit["cy"])
    band = item.get("band") or {}
    # 흰 여백을 잘라 **그림만** 남긴다(잉크 상자)
    a = np.asarray(im, np.float32)
    ink = a.min(axis=2) < 235
    ys, xs = np.nonzero(ink.any(1))[0], np.nonzero(ink.any(0))[0]
    if ys.size and xs.size:
        im = im.crop((int(xs.min()), int(ys.min()),
                      int(xs.max()) + 1, int(ys.max()) + 1))
    tw, th = SW * wf, SH * hf
    r = min(tw / max(im.width, 1), th / max(im.height, 1))
    if band.get("h_min") is not None and band.get("w_max") is not None:
        r_floor = (SH * float(band["h_min"])) / max(im.height, 1)
        r_ceil = (SW * float(band["w_max"])) / max(im.width, 1)
        r = min(max(r, r_floor), r_ceil)
    im = im.resize((max(1, int(im.width * r + 0.5)),
                    max(1, int(im.height * r + 0.5))), Image.LANCZOS)
    if im.width > SW or im.height > SH:               # 판을 넘지 않는다
        k = min(SW / im.width, SH / im.height)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))),
                       Image.LANCZOS)
    canvas = Image.new("RGB", (SW, SH), (255, 255, 255))
    canvas.paste(im, ((SW - im.width) // 2,
                      max(0, min(SH - im.height, int(SH * cy - im.height / 2)))))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    canvas.save(str(out) + ".part2", "PNG")
    _publish(str(out) + ".part2", out)
    return {"w": SW, "h": SH, "ink_w": im.width, "ink_h": im.height}


def _remember_photo_metadata(data, spec):
    """Preserve the existing JSON provider's image rows using server-declared paths."""
    rule = spec.get('photo_metadata') or {}
    rows = _dig(data, rule.get('rows')) if rule else []
    if isinstance(rows, dict):
        rows = list(rows.values())
    for row in rows if isinstance(rows, list) else []:
        for path in rule.get('urls') or []:
            url = _dig(row, path)
            if isinstance(url, str) and url.startswith(('http://', 'https://')):
                _PHOTO_SOURCE_META[url] = _project_photo_metadata(row, rule, url, str(spec.get('name') or 'api'))
                try:
                    _SIZE_HINT[url] = (int(_dig(row, rule.get('width')) or 0),
                                       int(_dig(row, rule.get('height')) or 0))
                except (ValueError, TypeError):
                    pass  # A size hint never replaces decoding the downloaded image.


class PhotoSourceError(StepError):
    """A safe API status, without provider response bodies or credential values."""


class PhotoSourcePending(PhotoSourceError):
    """An unknown POST outcome stops this acquisition before other paid calls."""


def _source_api_urls(src, query, pace, timeout):
    """Execute one declared API request and durably retain its outcome.

    The query receipt is shared by cards and fresh processes. Reserving its path
    before sending prevents duplicate paid POSTs after a lost response or crash.
    Credentials only enter the exact API request, never the image download.
    """
    check_review_running()
    import hashlib
    import http.client
    from volcano_drive import auth_headers
    import urllib.parse
    method = str(src.get('method') or 'GET').upper()
    if method not in ('GET', 'POST'):
        raise PhotoSourceError('사진 API 요청 방식이 GET/POST가 아닙니다.')
    if src.get('auth_services') and not src.get('auth'):
        raise PhotoSourceError('사진 API 인증 선언이 없습니다. 서버에서 수집 단계를 다시 받으세요.')
    try:
        headers = auth_headers({'auth': src.get('auth')}, src.get('headers'))
    except StepError as error:
        raise PhotoSourceError(str(error)) from None
    def fill(value):
        if isinstance(value, str): return value.replace('{q}', query)
        if isinstance(value, list): return [fill(v) for v in value]
        if isinstance(value, dict): return {k: fill(v) for k, v in value.items()}
        return value
    url = str(src['url']).replace('{q}', urllib.parse.quote(query))
    body = fill(src.get('body')) if method == 'POST' else None
    encoded = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8') if body is not None else None
    if encoded is not None: headers.setdefault('Content-Type', 'application/json')
    # Bind both receipts to the actual credential without storing its value.
    def fingerprint(value):
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
    key = fingerprint({'method': method, 'url': url, 'body': body, 'headers': headers})
    provider = fingerprint({'method': method, 'url': src['url'],
                            'body': src.get('body'), 'headers': headers})
    directory = src.get('cache_dir')
    if not directory:
        raise PhotoSourceError('사진 API 결과를 보존할 cache_dir가 없습니다.')
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, key + '.json')
    auth_path = os.path.join(directory, '_auth-' + provider + '.json')
    name = str(src.get('name') or 'image API')

    def read_receipt(filename):
        try:
            with open(filename, encoding='utf-8') as handle:
                value = json.load(handle)
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            raise PhotoSourceError(f'{name} 이전 검색 결과를 읽지 못했습니다. 중복 호출을 중단했습니다.') from None
        if not isinstance(value, dict):
            raise PhotoSourceError(f'{name} 이전 검색 기록이 손상됐습니다. 중복 호출을 중단했습니다.')
        return value

    def can_request(value):
        if value is None or value.get('status') == 'not_sent':
            return True
        retry_at = value.get('retry_at')
        return (method == 'GET' and value.get('status') == 'failed'
                and value.get('http_status') not in (401, 402, 403, 429)
                and isinstance(retry_at, (float, int)) and retry_at <= time.time())

    record = read_receipt(path)
    if record is None or record.get('status') != 'complete':
        auth_failure = read_receipt(auth_path)
        if auth_failure:
            raise remember_review_refusal(ProviderRefusalError(
                name, auth_failure.get('http_status'), 'saved API authentication refusal'))
    if can_request(record):
        # A short exclusive claim also serializes a permitted GET retry. The
        # durable pending receipt survives a crash after the claim is removed.
        claim = path + '.claim'
        try:
            fd = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            error = PhotoSourcePending if method == 'POST' else PhotoSourceError
            raise error(f'{name} 같은 검색이 이미 시작됐습니다. 결과를 받은 뒤 재개하세요.') from None
        os.close(fd)
        try:
            record = read_receipt(path)
            execute = can_request(record)
            if execute:
                record = {'status': 'pending', 'method': method, 'started_at': time.time()}
                _photo_write_state(path, record)
        finally:
            os.unlink(claim)
        if execute:
            request = urllib.request.Request(url, data=encoded, headers=headers, method=method)
            started = time.monotonic()
            try:
                with review_dispatch():
                    if pace: time.sleep(pace)
                    with urllib.request.urlopen(request, timeout=timeout) as response:
                        data = json.load(response)
                        status = response.status
                if not isinstance(data, (dict, list)):
                    raise ValueError('API JSON must be an object or array')
                record.update(status='complete', http_status=status, data=data)
            except (urllib.error.HTTPError, ProviderRefusalError) as refusal:
                error = refusal.__cause__ if isinstance(refusal, ProviderRefusalError) else refusal
                if not isinstance(error, urllib.error.HTTPError):
                    # The shared dispatch guard proves it never entered urlopen.
                    # Preserve the reservation, but do not label it accepted or
                    # uncertain. Only a new run can reach this source again.
                    if getattr(refusal, 'request_sent', None) is False:
                        record.update(status='not_sent', error_type=type(refusal).__name__)
                        _photo_write_state(path, record)
                    raise
                record.update(status='failed', http_status=error.code)
                if error.code in (401, 403):
                    _photo_write_state(auth_path, {'status': 'auth_failed', 'http_status': error.code})
                # Only an explicit server Retry-After authorizes a later GET.
                # POST outcomes never expire into an automatic billed retry.
                retry_after = error.headers.get('Retry-After') if error.headers else None
                if method == 'GET' and error.code not in (401, 402, 403, 429) and retry_after:
                    at = _retry_after_at(retry_after, time.time())
                    if at is not None:  # An invalid header grants no automatic retry.
                        record['retry_at'] = at
                error.close()
            except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as error:
                record.update(status='unknown', error_type=type(error).__name__)
            record['elapsed_sec'] = round(time.monotonic() - started, 3)
            _photo_write_state(path, record)
    if record.get('status') != 'complete':
        status = record.get('http_status')
        if status in (401, 402, 403, 429):
            raise remember_review_refusal(ProviderRefusalError(name, status, 'saved API refusal; no automatic retry'))
        why = f'HTTP {status}' if status is not None else '호출 결과를 확인하지 못했습니다'
        if method == 'POST' and record.get('status') in ('pending', 'unknown'):
            raise PhotoSourcePending(f'{name} 사진 검색: {why}. 이 수집을 멈췄습니다. '
                                     '같은 검색을 자동으로 다시 보내지 않습니다.')
        if record.get('retry_at') is not None:
            raise PhotoSourceError(f'{name} 사진 검색: {why}. API가 정한 Retry-After 이후에 재개할 수 있습니다.')
        raise PhotoSourceError(f'{name} 사진 검색: {why}. 같은 요청을 자동으로 다시 보내지 않습니다.')
    data = record['data']
    _remember_photo_metadata(data, src)
    return _pluck(data, src['pick'])


#: agy 점검 결과(한 실행에 한 번) — 설치·로그인이 안 됐으면 사람 말로 멈춘다.
_AGY_PROBE = {}
#: 한 실행(프로세스)이 함께 쓰는 agy·구글 멈춤 표시 (2026-09-28 규칙 6-2 수리).
#  ★거부(구글 401·403·429·sorry, agy 429·한도)가 **한 번이라도** 오면 이 실행에서는 이 출처를 다시 부르지 않는다.
#    전에는 부품이 부를 때마다 멈춤 표시를 새로 만들어, 컷 A 에서 구글이 거부해도 컷 B 가 다시 불렀다.
#  ★다음 실행에서 언제 다시 불러도 되는지는 구글·agy 공식 숫자가 없다 — 지어내지 않는다(사장님 결정 대기).
_AGY_STOP = {}


def _agy_run_stop():
    import agy_google
    if 'stop' not in _AGY_STOP:
        _AGY_STOP['stop'] = agy_google.Stop()
    return _AGY_STOP['stop']


def _agy_stop_reason(stop):
    if stop.google.is_set():
        return '구글이 요청을 거부했습니다'
    if stop.agy.is_set():
        return 'agy 가 한도·속도 제한을 알렸습니다'
    return ''


def _agy_google_path(src, query):
    """agy 구글 결과 영수증 자리. 같은 검색어·같은 조리법이면 같은 파일(이어 하기에서 다시 안 찾는다)."""
    import hashlib
    directory = src.get('cache_dir')
    if not directory:
        raise PhotoSourceError('구글 사진(agy) 결과를 보존할 cache_dir가 없습니다.')
    os.makedirs(directory, exist_ok=True)
    recipe = {'q': query, 'variants': src.get('variants'), 'max_body': src.get('max_body'),
              'skip': src.get('skip_domains'), 'v': 1}
    key = hashlib.sha256(json.dumps(recipe, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()
    return os.path.join(directory, 'agy-' + key + '.json')


def _agy_google_read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            value = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise PhotoSourceError('구글 사진(agy) 이전 결과를 읽지 못했습니다. 같은 검색을 다시 보내지 않았습니다.') from None
    return value if isinstance(value, dict) else None


def _agy_google_ready():
    """agy 가 있고 로그인돼 있는가 — 한 실행에 한 번 잰다. 아니면 **사람 말로** 멈춘다(조용히 건너뛰지 않는다)."""
    import agy_google
    if 'r' not in _AGY_PROBE:
        _progress("  [구글 사진·agy] agy 설치·로그인을 확인한다")
        try:
            _AGY_PROBE['r'] = agy_google.probe()
        except Exception as error:                               # noqa: BLE001 — 이유를 실어 사람 말로 바꾼다
            _AGY_PROBE['r'] = {'ok': False, 'why': 'probe_error',
                               'say': f'agy 점검 중 오류가 났습니다({type(error).__name__}: {error})'}
    r = _AGY_PROBE['r']
    if not r.get('ok'):
        raise PhotoSourceError(f"구글 사진(agy): {r.get('say') or r.get('why')}")
    return r['path']


def agy_google_prefetch(src, queries):
    """검색어 여러 개를 agy 로 **동시에** 찾아 영수증으로 남긴다. 이미 영수증이 있는 검색어는 건너뛴다.

    ■ 조리법(변형·동시 수·본문 사진 수·건너뛸 곳)은 **서버가 준다**(src). 여기는 부품(agy_google)을 돌리기만 한다.
    ★구글이 거부하면 부품이 그 실행의 구글 요청을 전부 멈춘다 — 그 사실을 영수증에 남기고 자동으로 다시 보내지 않는다.
    """
    import agy_google
    todo = []
    for q in dict.fromkeys(str(x or '').strip() for x in queries):
        if not q:
            continue
        record = _agy_google_read(_agy_google_path(src, q))
        if not (record and record.get('status') == 'complete'):
            todo.append(q)
    if not todo:
        return {}
    stop = _agy_run_stop()
    reason = _agy_stop_reason(stop)
    if reason:
        raise PhotoSourceError(f'구글 사진(agy): 이번 실행에서 {reason} — 이 실행에서는 다시 부르지 않습니다(규칙: 거부 한 번이면 멈춤).')
    # 검색 문구·건너뛸 곳은 서버 선언 그대로(§2) — 없으면 agy 를 부르기 전에 이유를 말하고 이 출처를 건너뛴다
    if not src.get('variants') or not isinstance(src.get('skip_domains'), list):
        raise PhotoSourceError('구글 사진(agy) 선언에 검색 문구(variants)·건너뛸 곳(skip_domains)이 없습니다 — 서버를 확인하세요.')
    agy = _agy_google_ready()
    variants, skip = src['variants'], tuple(src['skip_domains'])
    _progress(f"  [구글 사진·agy] 검색어 {len(todo)}개를 동시에 찾는다")
    try:
        result = agy_google.candidates(
            todo, os.path.join(src['cache_dir'], '_agy_work'), agy=agy, variants=variants,
            search_workers=max(1, min(16, int(src.get('search_workers') or 16))),
            page_workers=max(1, int(src.get('page_workers') or 24)),
            max_body=max(0, int(src.get('max_body') or 10)), skip_domains=skip,
            log=lambda s: _progress(f"    [agy] {s}"), stop=stop)
    except Exception as error:                                   # noqa: BLE001
        # 부품 안의 뜻밖의 오류(예: 윈도우 인코딩) — **숨기지 않고** 종류·내용을 실어 사진 사다리 규칙대로
        #   «이 출처 실패 → 다음 출처» 로 보낸다. 영수증은 남기지 않는다(다음 실행에서 다시 찾을 수 있게).
        raise PhotoSourceError(f"구글 사진(agy) 부품 오류: {type(error).__name__}: {error}") from error
    stats = result['stats']
    # 부품이 보고한 거부도 이 실행의 멈춤 표시에 옮긴다(부품이 같은 표시를 썼다면 이미 켜져 있다)
    if stats.get('google_stopped'):
        stop.google.set()
    if stats.get('agy_stopped'):
        stop.agy.set()
    errors = stats.get('search_errors') or {}
    cut = set(stats.get('cut_queries') or ())
    for q in todo:
        rows = result['by_query'].get(q) or []
        # ★거부로 끝까지 못 푼 검색어는 «완료»로 적지 않는다 — 적으면 다음 실행이 다시 찾지 않는다(빈 결과가 굳는다).
        status = 'failed' if ((q in errors and not rows) or q in cut) else 'complete'
        _photo_write_state(_agy_google_path(src, q), {
            'status': status, 'query': q, 'rows': rows, 'error': errors.get(q) or ('refused_cut' if q in cut else None),
            'google_stopped': stats.get('google_stopped'), 'at': time.time()})
    reason = _agy_stop_reason(stop)
    _progress(f"  [구글 사진·agy] 후보 {stats.get('candidates', 0)}개 · 검색 {stats.get('search_sec')}초 · "
              f"전체 {stats.get('sec')}초" + (f" · ★{reason} — 이번 실행의 구글 사진 검색을 멈췄다" if reason else ""))
    if reason:
        raise PhotoSourceError(f'구글 사진(agy): {reason}. 이번 실행에서는 다시 부르지 않습니다(규칙: 거부 한 번이면 멈춤).')
    return stats


def photo_search_started(item):
    """이 `search_images` 컷에 **이전 판을 포함한** 사진 검색 기록이 하나라도 있는가.

    ★미리 찾기는 처음 찾는 컷을 빠르게 하려는 것뿐이다(2026-09-28). 기록이 있는 컷 — 고른 사진·검수 탈락·
      검수 대기 — 은 `search_images` 가 그 기록으로 이어 가고 agy 는 정말 모자랄 때만 그 자리에서 부른다.
      이 판정이 없으면 serper 판(09-11~09-28)에서 이미 사진을 고른 옛 작업도 agy 영수증이 없어서
      컷마다 agy 검색(30~40초·요금제 한도)을 새로 돌렸다 — 결과는 옛 영수증 그대로인데.
    """
    state = _photo_read_state(os.path.join(os.path.abspath(item.get('out_dir') or 'photo'), '.photo-search.json'))
    keys = {_photo_search_recipe(previous)[1] for previous in _photo_recipe_variants(item)}
    return any(isinstance(record, dict) and record.get('recipe_key') in keys
               for record in state['requests'].values())


def agy_google_plan_prefetch(items, backoff=(), pace=0.0):
    """같은 응답의 사진 검색 컷들 중 **앞 출처(네이버 등)로 모자랄 컷**의 첫 검색어만 모아 agy 로 미리 찾는다.

    ★앞 출처 결과는 영수증으로 남는 API 라 여기서 먼저 불러도 두 번 나가지 않는다(`_source_api_urls`).
    ★모자람의 문턱(`prefetch_below`)은 서버가 준다. 여기서 못 채운 컷은 원래 순서에서 그 자리에서 찾는다.
    """
    groups = {}
    for item in items:
        sources = item.get('sources') or []
        agy_src = next((s for s in sources if (s.get('kind') or '').lower() == 'agy_google'), None)
        queries = [str(q or '').strip() for q in item.get('queries') or [] if str(q or '').strip()]
        if not agy_src or not queries:
            continue
        q = queries[0]
        found = 0
        for s in sources:
            if s is agy_src:
                break
            try:
                found = max(found, len(_source_urls(s, q, backoff, pace)))
            except PhotoSourceError:
                continue
        if found < int(agy_src.get('prefetch_below') or 8):
            groups.setdefault(json.dumps({k: agy_src.get(k) for k in ('cache_dir', 'variants', 'max_body', 'skip_domains',
                                                                      'search_workers', 'page_workers')},
                                         sort_keys=True, ensure_ascii=False), (agy_src, []))[1].append(q)
    for agy_src, qs in groups.values():
        agy_google_prefetch(agy_src, qs)


#: 공백·제어 문자가 든 글은 주소가 아니다 — 파이썬 http.client 가 받기 전에 InvalidURL(OSError 아님)로 실행기를 통째로 멈췄다
#: (10-20 강석주 images: 화면 틀 묶기 식 «:src="article.ar_image_optimized || article.ar_image"» · srcset 글이 src 칸에 든 것).
_NOT_URL_CHAR = re.compile(r'[\x00-\x20\x7f]')


def _one_http_url(u):
    u = str(u or '')
    if not u or _NOT_URL_CHAR.search(u):
        return False
    try:
        p = urllib.parse.urlsplit(u)
        p.port          # 숫자 아닌 포트(«a.com:abc») — http.client 가 같은 InvalidURL 로 멈춘다
    except ValueError:
        return False
    return p.scheme in ('http', 'https') and bool(p.hostname)


#: 주소 아닌 값을 이미 알린 (출처, 값) — 같은 검색 결과를 컷마다 다시 읽어도 한 번만 알린다.
_NOT_URL_TOLD = set()


def _http_urls_only(values, src):
    """사진 출처가 돌려준 값 가운데 «http(s) 주소 하나» 인 것만 후보로 낸다 — 모든 출처가 지나는 한 자리.

    10-20 강석주 images 신고 4건: 네이버 검색 `items[].link`·웹 페이지 `src` 칸에 주소가 아닌 글(화면 틀 묶기 식
    «article.ar_image_optimized || article.ar_image» · srcset 글 «a.png, b.png 2x»)이 그대로 실려 왔고, 그 글이
    후보가 되어 http.client.InvalidURL 로 실행기 전체가 멈췄다. 출처의 원문은 우리가 못 고치니 원문을 후보로
    읽는 이 자리에서 가른다(agy 구글은 영수증을 읽는 `_agy_google_urls` 가 같은 자로 이미 가른다 — 장편 imgsupply 가
    그 함수를 직접 부르기 때문). 뺀 것은 출처 이름과 함께 진행 기록에 한 번 남긴다(조용히 지우지 않는다)."""
    keep = []
    for u in values:
        if _one_http_url(u):
            keep.append(u)
            continue
        told = (str(src.get('name') or src.get('kind') or 'source'), str(u))
        if told not in _NOT_URL_TOLD:
            _NOT_URL_TOLD.add(told)
            _progress(f"  [사진 후보] {told[0]}: 주소가 아닌 값은 후보에서 뺀다 — {told[1][:120]!r}", flush=True)
    return keep


def _agy_google_urls(src, query):
    """agy 구글 후보 주소. 영수증이 있으면 그것을 쓰고, 없으면 이 검색어 하나를 찾는다."""
    path = _agy_google_path(src, query)
    record = _agy_google_read(path)
    if not (record and record.get('status') == 'complete'):
        agy_google_prefetch(src, [query])
        record = _agy_google_read(path) or {}
    if record.get('status') != 'complete':
        raise PhotoSourceError(f"구글 사진(agy) 검색이 끝나지 않았습니다: {record.get('error') or '원인 미상'}")
    # 후보는 «http(s) 주소 하나» 만 — 이 영수증을 읽는 곳이 여기 하나라 새 영수증·고치기 전 판이 남긴 영수증을 같은 자로 거른다
    rows = [r for r in record.get('rows') or [] if isinstance(r, dict) and _one_http_url(r.get('url'))]
    _remember_photo_metadata({'rows': rows}, src)
    return [r['url'] for r in rows]


def _source_urls(src, query, backoff, pace, timeout=20):
    """소스 하나에 질의해 이미지 URL 후보를 얻는다. 요청 모양은 **서버가 준다.**

    ★같은 질의를 컷마다 다시 던지지 않는다(캐시). 18컷이 같은 인물명으로 내려오면
      그대로 18번을 부르게 되고, 그게 속도 제한에 걸리는 첫 원인이다.
    ★후보는 «http(s) 주소 하나» 만 — 출처가 돌려준 값을 후보로 읽는 자리가 여기 하나다(`_http_urls_only`).
    """
    check_review_running()
    if src.get('kind') == 'agy_google':
        # 2026-09-28 사장님 결정 «네이버는 기존대로, 구글만 agy로» — serper 자리를 수강생 자기 agy 요금제가 맡는다.
        #   영수증을 읽는 그 자리(`_agy_google_urls`)가 같은 자로 이미 가른다.
        return _agy_google_urls(src, query)
    if src.get('kind') in ('json_api', 'photo_page'):
        # 검색 영수증·페이지 기록이 따로 있다 — 아래 표(_QCACHE)를 쓰지 않는다.
        return _http_urls_only(_source_urls_raw(src, query, backoff, pace, timeout), src)
    key = (src.get("url") or src.get("kind"), query,
           src.get("gl"), src.get("hl"), json.dumps(src.get('photo_metadata'), sort_keys=True))
    if key in _QCACHE:
        return _QCACHE[key]
    out = _QCACHE[key] = _http_urls_only(_source_urls_raw(src, query, backoff, pace, timeout), src)
    return out


def _source_urls_raw(src, query, backoff, pace, timeout):
    """출처가 돌려준 값 그대로(주소 검사·질의 표 없음) — `_source_urls` 만 부른다."""
    if src.get('kind') == 'json_api':
        return _source_api_urls(src, query, pace, timeout)
    if src.get('kind') == 'photo_page':
        subject = str(src.get('subject') or '').casefold().replace(' ', '')
        records = _photo_page_records(src.get('url') or '')
        out = []
        for record in records:
            text = ' '.join(str(record.get(k) or '') for k in ('caption','title','description')).casefold().replace(' ', '')
            if subject and subject not in text:
                continue
            original = _photo_source_key(record['image_url'])
            if original in out:
                continue
            if original != record['image_url']:
                record = dict(record, image_url=original, displayed_image_url=record['image_url'])
            _PHOTO_SOURCE_META[original] = record
            out.append(original)
        return out[:24]
    # ★구글 이미지는 JS 가 돌아야 결과가 나온다 — urllib 으로는 못 한다.
    #   전용 프로필 크롬을 CDP 로 몬다(위 `_GoogleCDP`). 로그인·키·비용 전부 0.
    if (src.get("kind") or "").lower() == "irasutoya":
        # ★로컬 조회다 — pace 도 backoff 도 걸지 않는다. 네트워크를 안 쓴다.
        out = _iras_urls(src, query)
        return out
    if (src.get("kind") or "").lower() in ("cdp_google", "google_cdp", "google"):
        g = _google_source(src)
        cands = g.urls(query, gl=src.get("gl") or "kr", hl=src.get("hl") or "ko",
                       settle=float(src.get("settle") or 6.0))
        # ★크기를 아는 후보는 **받기 전에** 거른다. 헛다운로드를 안 한다.
        #   `min_px` 는 job 이 갖고 있으므로 여기서는 캐시에 크기를 남겨 두고
        #   `fetch_images` 가 판정한다.
        out = []
        for c in cands:
            if isinstance(c, dict):
                _SIZE_HINT[c["url"]] = (c.get("w") or 0, c.get("h") or 0)
                out.append(c["url"])
            else:
                out.append(c)
        return out
    headers = dict(src.get("headers") or {})
    import urllib.parse
    tmpl = src["url"]
    if "{q}" in tmpl or "{lang}" in tmpl:
        out = []
        for lang in (src.get("langs") or [None]):
            u = tmpl.replace("{q}", urllib.parse.quote(query))
            if lang:
                u = u.replace("{lang}", lang)
            try:
                time.sleep(pace)
                data = _api_json(u, headers, backoff, timeout)
                _remember_photo_metadata(data, src)
                out += _pluck(data, src["pick"])
            except ProviderRefusalError:
                raise
            except Exception:                                     # noqa: BLE001, S110
                continue
            if out:
                break
        return out
    params = dict(src.get("params") or {})
    for k, v in params.items():
        if v == "{q}":
            params[k] = query
    params.setdefault("gsrsearch", query)
    u = tmpl + "?" + urllib.parse.urlencode(params)
    try:
        time.sleep(pace)
        data = _api_json(u, headers, backoff, timeout)
        _remember_photo_metadata(data, src)
        out = _pluck(data, src["pick"])
    except ProviderRefusalError:
        raise
    except Exception:                                             # noqa: BLE001
        out = []
    return out


def _sm_words(tr):
    """Speechmatics json-v2 → 단어열. `results[].alternatives[0].content` + start/end."""
    out = []
    for x in tr.get("results") or []:
        if x.get("type") != "word":
            continue
        alt = (x.get("alternatives") or [{}])[0]
        w = (alt.get("content") or "").strip()
        if w:
            out.append({"word": w, "start": float(x.get("start_time") or 0.0),
                        "end": float(x.get("end_time") or 0.0)})
    return out


def _groq_words(tr):
    """Groq verbose_json → `words[]` 에 word/start/end."""
    return [{"word": str(w.get("word") or "").strip(),
             "start": float(w.get("start") or 0.0), "end": float(w.get("end") or 0.0)}
            for w in (tr.get("words") or []) if str(w.get("word") or "").strip()]


def _gladia_words(tr):
    """Gladia v2의 완료 결과만 읽는다. 누락/잘못된 시각은 무음으로 바꾸지 않는다."""
    import math
    result = tr.get("result") if isinstance(tr, dict) else None
    transcript = result.get("transcription") if isinstance(result, dict) else None
    utterances = transcript.get("utterances") if isinstance(transcript, dict) else None
    if not isinstance(utterances, list):
        raise ValueError("Gladia 완료 응답에 utterances 목록이 없음")
    out = []
    for utterance in utterances:
        if not isinstance(utterance, dict) or not isinstance(utterance.get("words"), list):
            raise ValueError("Gladia 발화에 words 목록이 없음")
        for word in utterance["words"]:
            if not isinstance(word, dict) or not isinstance(word.get("word"), str):
                raise ValueError("Gladia 단어 응답 형식 오류")
            text = word["word"].strip()
            start, end = word.get("start"), word.get("end")
            if (type(start) not in (int, float) or type(end) not in (int, float)
                    or not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end):
                raise ValueError("Gladia 단어 시각이 누락되거나 유효하지 않음")
            if text:
                out.append({"word": text, "start": float(start), "end": float(end)})
    return out


def _whisper_words(tr):
    """OpenAI whisper CLI 의 `--output_format json` → segments[].words[].

    ★낱말 키가 `word` 다(앞에 공백이 붙어 온다). 시각은 초 단위 실수.
    """
    out = []
    for seg in tr.get("segments") or []:
        for w in seg.get("words") or []:
            t = str(w.get("word") or "").strip()
            if t:
                out.append({"word": t, "start": float(w.get("start") or 0.0),
                            "end": float(w.get("end") or 0.0)})
    return out


_WORD_READER = {"speechmatics": _sm_words, "groq": _groq_words, "gladia": _gladia_words,
                "local_whisper": _whisper_words}


class _FileBody:
    """Bounded, replayable body; caller owns its source guard with with/finally."""
    def __init__(self, path, before=b"", after=b"", source_check=None):
        self.path, self.before, self.after = path, before, after
        self._source_check = source_check
        self._closed = True
        self._readers = set()
        self._guard = _SourceReadGuard(path)
        self._guard.__enter__()
        try:
            st = os.stat(path)
            self.stat, self.changed_ns = self._stamp(st), st.st_ctime_ns
            self._check_stat(st)
        except BaseException:
            self._guard.__exit__(*sys.exc_info())
            raise
        self._closed = False

    def __enter__(self):
        if self._closed:
            raise ValueError("이미 닫힌 파일 본문입니다")
        return self  # The constructor acquired once; never re-enter its guard.

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.check()
        finally:
            self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                for handle in tuple(self._readers):
                    handle.close()
                self._readers.clear()
            finally:
                self._guard.__exit__(None, None, None)

    def __del__(self):
        # Compatibility safety net only; shipped consumers close explicitly.
        self.close()

    @staticmethod
    def _stamp(st):
        return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns

    def __len__(self):
        return len(self.before) + self.stat[2] + len(self.after)

    def _check_stat(self, st):
        # Windows stat/fstat ctime can mean birth/change time respectively.
        # Its mandatory source guard prevents writes; POSIX needs change time.
        if (self._stamp(st) != self.stat
                or (os.name != 'nt' and st.st_ctime_ns != self.changed_ns)):
            raise OSError("업로드 파일이 본문 준비 뒤 또는 전송 도중 바뀌었습니다")
        if self._source_check is not None:
            self._source_check()

    def check(self):
        if self._closed:
            raise ValueError("이미 닫힌 파일 본문입니다")
        self._check_stat(os.stat(self.path))

    def __iter__(self):
        # 재시도도 처음부터 읽는다. 같은 경로의 파일이 교체됐으면 다른 본문을 보내지 않는다.
        self.check()
        with open(self.path, "rb") as fh:
            self._readers.add(fh)
            try:
                self._check_stat(os.fstat(fh.fileno()))
                if self.before:
                    yield self.before
                remaining = self.stat[2]
                while remaining:
                    block = fh.read(min(1024 * 1024, remaining))
                    if not block:
                        raise OSError("업로드 파일이 전송 도중 짧아졌습니다")
                    # Check before yielding: do not send a detected changed chunk.
                    self._check_stat(os.fstat(fh.fileno()))
                    remaining -= len(block)
                    yield block
                self._check_stat(os.fstat(fh.fileno()))
                self.check()
                if self.after:
                    yield self.after
            finally:
                self._readers.discard(fh)


def _multipart(fields, file_field, path, source_check=None):
    """멀티파트의 작은 머리/꼬리만 구성한다. 파일은 전송 중 청크로 읽는다."""
    import mimetypes
    b = "----vol" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append((f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                      f"{v}\r\n").encode())
    ctype = mimetypes.guess_type(path)[0] or "audio/wav"
    parts.append((f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
                  f"filename=\"{os.path.basename(path)}\"\r\n"
                  f"Content-Type: {ctype}\r\n\r\n").encode())
    body = _FileBody(path, b"".join(parts), f"\r\n--{b}--\r\n".encode(), source_check=source_check)
    return body, f"multipart/form-data; boundary={b}"


def _post_multipart(url, body, ctype, headers, timeout):
    req = urllib.request.Request(url, data=body, headers=dict(
        headers, **{"Content-Type": ctype, "Content-Length": str(len(body)), "User-Agent": _UA}))
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace") or "{}")


class _AudioPreparationError(StepError):
    """로컬 전처리 실패는 제공자 장애나 불확실한 유료 접수가 아니다."""


@contextlib.contextmanager
def _asr_audio_input(path, plan):
    """원장은 원본에 묶고, 실제 신규 제출에만 서버가 지정한 음성을 한 번 만든다."""
    folder, prepared = None, None
    def ready():
        nonlocal folder, prepared
        spec = plan.get("audio")
        if spec is None:
            return path
        if prepared is not None:
            return prepared
        if not (isinstance(spec, dict) and isinstance(spec.get("suffix"), str)
                and re.fullmatch(r"\.[A-Za-z0-9]+", spec["suffix"])
                and isinstance(spec.get("argv"), list) and spec["argv"]
                and all(isinstance(a, str) for a in spec["argv"])
                and "@@IN@@" in spec["argv"] and "@@OUT@@" in spec["argv"]):
            raise _AudioPreparationError("서버의 전사 음성 추출 명령을 읽을 수 없습니다. API 호출 전 중단했습니다.")
        try:
            folder = tempfile.TemporaryDirectory(prefix="volcano-asr-")
            dest = os.path.join(folder.name, "source" + spec["suffix"])
            _spawn(_fill(spec["argv"], IN=path, OUT=dest), check=True, capture_output=True)
            if not os.path.isfile(dest) or os.path.getsize(dest) == 0:
                raise OSError("empty audio")
        except (OSError, subprocess.SubprocessError, StepError) as exc:
            raise _AudioPreparationError("전사 음성 추출에 실패했습니다. ffmpeg·원본 음성 트랙·임시 폴더 여유 공간을 확인하세요. "
                                         "API 호출 전 중단했습니다.") from exc
        prepared = dest
        _progress(f"    [전사] 전체 길이 음성 추출 · {os.path.getsize(dest):,}바이트", flush=True)
        return prepared
    try:
        yield ready
    finally:
        if folder is not None:
            folder.cleanup()


def _service_key_value(cfg):
    import os
    names = [cfg.get('env_var') or ''] + list(cfg.get('env_aliases') or [])
    for name in names:
        value = (os.environ.get(name) or '').strip()
        if value:
            return value, 'env'
    path = cfg.get('key_file')
    if not path:
        return '', None
    try:
        with open(os.path.expanduser(path), 'rb') as stream:
            raw = stream.read()
    except FileNotFoundError:
        return '', None
    value = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig').strip()
    return value, 'file'

def _read_service_key(cfg):
    """Read the declared environment aliases, then the canonical local file."""
    if not isinstance(cfg, dict):
        return ""
    return _service_key_value(cfg)[0]


class ASRSetupRequired(StepError):
    """No implicit local model download or execution when cloud keys are absent."""
    def __init__(self):
        super().__init__("전사 키 연결 또는 사용자의 명시적인 로컬 ASR 선택이 필요합니다. 모델을 실행하지 않았습니다.")


class TranscriptionPending(RuntimeError):
    """접수/조회가 아직 확정되지 않았다. 실패 fallback이나 완료 보고를 하면 안 된다."""

    def __init__(self, provider, reason, retry_after=0, state_file=None):
        self.provider = provider
        self.reason = reason
        self.retry_after = retry_after
        self.state_file = state_file
        super().__init__(f"{provider} 전사 대기: {reason}. 같은 단계로 다시 실행하면 "
                         "기존 접수를 확인합니다(새 유료 접수 없음)."
                         + (f" 기록: {state_file}" if state_file else ""))


class ReviewInProgress(StepError, TranscriptionPending):
    """같은 검수·실행 잠금을 살아 있는 다른 프로세스가 쥐고 있다(review_receipt_lock). StepError(code
    review_in_progress)로 잡던 자리는 그대로 잡고, 아무도 안 잡으면 구동기가 TranscriptionPending 으로 받아 대기로 끝낸다."""

    code = 'review_in_progress'

    def __init__(self):
        self.provider = '검수 잠금'
        self.reason = '이 작업의 다른 실행(앞서 띄운 실행기나 그 자식)이 같은 일을 아직 하고 있다'
        self.retry_after = 30
        self.state_file = None
        RuntimeError.__init__(self, '다른 실행기가 같은 검수 요청을 처리 중입니다. 완료 기록을 보존하며 새 유료 요청은 '
                              '보내지 않았습니다. 그 실행이 끝난 뒤 같은 단계로 다시 실행하면 그 결과를 이어 받습니다.')


@contextlib.contextmanager
def _asr_lock(path, *, blocking=False):
    """OS lock; paid work stays nonblocking, brief immutable-media writes may wait."""
    with open(path, "a+b") as fh:
        # Windows can lock a byte beyond EOF. Initializing that byte before
        # locking races with another handle that already owns the empty file.
        fh.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except OSError as exc:
            if blocking:
                raise StepError("검수 자료 저장 잠금을 얻지 못했습니다. 원본과 완료 검수는 보존합니다.") from exc
            raise TranscriptionPending("ASR", "다른 실행기가 같은 음성을 처리 중") from exc
        try:
            yield
        finally:
            fh.seek(0)
            if os.name == "nt":
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _asr_save(path, state):
    # 이 기록은 선택 캐시가 아니다. 먼저 저장하지 못하면 새 유료 요청을 보내지 않는다.
    tmp = None
    prepared = False
    preserve = False
    try:
        fd, tmp = tempfile.mkstemp(prefix=".receipt-", dir=os.path.dirname(path))
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        prepared = True
        # Same local Windows sharing policy as _photo_write_state (_replace_retrying 한 자리). This retries
        # only publication of these already-written bytes, never an API request.
        _replace_retrying(tmp, path)
    except Exception as exc:
        preserve = tmp is not None
        reason = "접수 기록 저장 실패 — 저장 공간/권한 확인 필요"
        if tmp:
            reason += (". 새 기록 사본 보존: " if prepared else ". 쓰기 미완료 사본 보존: ") + tmp
        failure = TranscriptionPending("ASR", reason, state_file=path)
        failure.target_path = path
        failure.recovery_path = tmp
        failure.recovery_ready = prepared
        raise failure from exc
    finally:
        if tmp and not preserve and os.path.exists(tmp):
            os.unlink(tmp)


def _asr_identity(path, plan):
    digest = hashlib.sha256()
    with _FileBody(path) as body:
        for chunk in body:
            digest.update(chunk)
    return digest.hexdigest()


def _asr_request_id(name, cfg):
    # 미사용 fallback 모델이나 순서가 바뀌어도 이미 접수한 작업은 같은 작업이다.
    # 키/키 위치/인증 헤더/대기 정책은 실제 전사 요청 내용이 아니다.
    request_keys = ("kind", "submit_url", "fields", "file_field", "bin", "argv", "reads")
    request = [name, {k: cfg[k] for k in request_keys if k in cfg}]
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def transcribe_words(path, plan, keys):
    """동일 음성/제공자 요청을 재개한다. 반환은 (words, provider), 미완료는 명시 대기."""
    try:
        with _FileBody(path) as source:
            return _transcribe_guarded(path, plan, keys, source)
    except OSError as exc:
        raise TranscriptionPending("ASR", "원본이 변경되었거나 읽기 보호를 설정할 수 없음 — 원본 확인 필요") from exc


def _asr_event(provider, outcome):
    """Observed provider operations only; metrics cannot change receipt/retry safety."""
    try:
        from runtime_metrics import event
        event("asr_" + provider, outcome)
    except Exception:  # noqa: BLE001
        pass


def _transcribe_guarded(path, plan, keys, source):
    if not any((cfg or {}).get("kind") in ("submit_poll", "upload_submit_poll")
               for cfg in plan["providers"].values()):
        return _transcribe_attempt(path, plan, keys, None, lambda: None, source.check)
    receipt = None
    try:
        identity = _asr_identity(path, plan)
        source.check()
        folder = os.path.join(os.path.dirname(os.path.abspath(path)), ".volcano-asr")
        os.makedirs(folder, exist_ok=True)
        receipt = os.path.join(folder, identity + ".json")
        with _asr_lock(receipt + ".lock"):
            state = {"version": 1, "identity": identity, "requests": {}}
            if os.path.exists(receipt):
                try:
                    with open(receipt, encoding="utf-8") as fh:
                        state = json.load(fh)
                    if not (isinstance(state, dict) and type(state.get("version")) is int
                            and state["version"] == 1 and state.get("identity") == identity
                            and isinstance(state.get("requests"), dict)):
                        raise ValueError("bad receipt")
                except (ValueError, TypeError) as exc:
                    raise TranscriptionPending("ASR", "접수 기록 손상 — 원본 기록 확인 필요",
                                               state_file=receipt) from exc
            ids = {name: _asr_request_id(name, plan["providers"].get(name) or {})
                   for name in plan["order"]}
            records = {name: state["requests"][rid] for name, rid in ids.items()
                       if rid in state["requests"]}
            valid_states = ("uploading", "uploaded", "submitting", "accepted",
                            "submitting_direct", "complete", "failed")
            for name, record in records.items():
                if not (isinstance(record, dict) and record.get("provider") == name
                        and record.get("state") in valid_states
                        and (record["state"] != "complete" or isinstance(record.get("words"), list))):
                    raise TranscriptionPending(name, "접수/완료 기록 손상 — 원본 기록 확인 필요",
                                               state_file=receipt)
            active = [name for name, r in records.items() if r["state"] not in ("failed", "complete")]
            if not active:
                for name in plan["order"]:
                    if (records.get(name) or {}).get("state") == "complete":
                        _progress("    [전사] 완료 기록 재사용 · 유료 호출 0", flush=True)
                        _asr_event(name, "reused")
                        return records[name]["words"], name
                # 명시적으로 실패한 시도는 키/잔액/서비스가 복구되면 재시도할 수 있다.
                # 미확인 접수가 하나라도 있으면 실패한 제공자부터 다시 제출하지 않는다.
                records = {}
            def save():
                for name, record in records.items():
                    record["provider"] = name
                    state["requests"][ids[name]] = record
                _asr_save(receipt, state)
            words, provider = _transcribe_attempt(path, plan, keys, records, save, source.check)
            source.check()
            record = records.setdefault(provider, {})
            record.update(state="complete", words=words)
            save()
            return words, provider
    except TranscriptionPending:
        raise
    except OSError as exc:
        raise TranscriptionPending("ASR", "음성 또는 접수 기록을 읽고 쓸 수 없음 — 경로/권한 확인 필요",
                                   state_file=receipt) from exc


#: 보내지 못한(제공자에 닿지 않은) 유료 요청을 다시 보내는 횟수 상한·간격(초) — 첫 시도 뒤 몇 번 더 보내는가.
#: 숫자는 이 저장소의 같은 부류 상한(volcano_run._open_retry «5xx 만 3회») 을 따른다 — 서비스 공식 숫자가 아니다
#: (Evolink·Typecast 문서에 연결 실패 재시도 규정 없음 · «공식 숫자 없음»). 거부(4xx·429)는 이 길을 타지 않는다(6-2).
_UNSENT_RETRY_WAITS = (2, 4)


def _tts_resend_hint(mark, unit="컷"):
    """완료 여부를 모르는 유료 요청 하나(음성 컷 · 그림 슬롯)를 사람이 다시 보내는 길(신고 #208·#313 · response_receipts.RESEND_MARKER 와
    같은 꼴 — 한 번 쓰고 지운다). 과금됐는지 공식 근거가 없어 자동으로는 보내지 않는다."""
    return (f"그 {unit}만 한 번 더 보내려면(과금이 한 번 더 될 수 있습니다) 빈 파일 " + str(mark)
            + f" 을 만든 뒤 같은 명령을 다시 실행하세요. 보내지 않으려면 그대로 두면 됩니다(다른 {unit}의 기록은 그대로입니다).")


def _request_never_delivered(exc):
    """이 예외가 «요청 본문이 제공자에 끝까지 닿지 않았다» 는 증거인가 (2026-10-17 · 실행기 중단 보고 51건·2명 + 음성 9건·5명).

    urllib 의 `do_open` 은 **요청을 보내는 단계**(`h.request` — 연결·헤더·본문 쓰기)의 OSError 만 `URLError` 로 감싼다.
    응답을 읽는 단계(`getresponse` 뒤)의 끊김·시간 초과는 감싸지 않고 그대로 올린다. 그래서 `HTTPError` 가 아닌 `URLError`
    (이유가 OSError — DNS·연결 거부·연결 시간 초과·본문 쓰기 중 끊김)는 서버가 온전한 요청을 받은 적이 없다는 뜻이다:
    본문이 다 가지 않은 HTTP 요청은 처리될 수 없다. 이때 예전에는 «접수 응답 미확인 — 새 유료 요청을 보내지 않습니다» 로
    접수 기록이 영구히 막혔다(한 사람 47건). 응답 단계 오류는 여전히 «모름» 이다(중복 과금 방지)."""
    return (isinstance(exc, urllib.error.URLError) and not isinstance(exc, urllib.error.HTTPError)
            and isinstance(getattr(exc, 'reason', None), OSError))


def _asr_definite_http_failure(exc):
    # timeout/429/5xx는 접수/처리 실패 증거가 아니다. 새 유료 작업으로 우회하지 않는다.
    return isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500 \
        and exc.code not in (408, 425, 429)


def _asr_find_submission(cfg, record, hdr):
    """접수 응답 유실 시 GET만으로 표지를 찾는다. 부재를 미접수 증거로 쓰지 않는다."""
    lookup = cfg.get("resume_lookup") or {}
    if lookup.get("kind") == "gladia_metadata" and record.get("tag"):
        return _asr_find_gladia_submission(cfg, record, hdr)
    if lookup.get("kind") != "speechmatics_tracking" or not record.get("tag"):
        return None
    cursor, found = None, set()
    for _ in range(lookup["max_pages"]):
        query = {"limit": lookup["page_size"], "include_deleted": "true"}
        if cursor:
            query["created_before"] = cursor
        url = lookup["list_url"] + ("&" if "?" in lookup["list_url"] else "?")
        data = get_json(url + urllib.parse.urlencode(query), hdr, cfg["timeout"])
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            return None
        for job in jobs:
            tracking = (job.get("config") or {}).get("tracking") or job.get("tracking") or {}
            if record["tag"] in (tracking.get("tags") or []) and job.get("id"):
                found.add(str(job["id"]))
        if found:
            # 복수 일치가 있으면 임의로 하나를 골라 버리지 않는다.
            return next(iter(found)) if len(found) == 1 else None
        if len(jobs) < lookup["page_size"]:
            break
        dates = [j.get("created_at") for j in jobs if isinstance(j.get("created_at"), str)]
        nxt = min(dates) if dates else None
        if not nxt or nxt == cursor:
            break
        cursor = nxt
    return None


def _asr_multipart(fields, file_field, path, source_check):
    # This is still before POST/state registration: a stale snapshot is a local
    # preparation failure. Later streaming errors keep the unknown-submit state.
    try:
        return _multipart(fields, file_field, path, source_check=source_check)
    except OSError as exc:
        raise _AudioPreparationError("전사 원본 또는 준비 음성이 바뀌었습니다. API 호출 전 중단했습니다.") from exc


def _asr_upload(path, name, cfg, hdr, record, records, save, source_check=None):
    """업로드는 전사 접수가 아니다. 응답을 보존한 뒤 실제 job POST를 따로 보낸다."""
    if record is not None and record["state"] != "uploading":
        return record
    upload = cfg["upload"]
    body, ctype = _asr_multipart(upload.get("fields") or {}, upload["file_field"], path, source_check)
    with body:
        if record is None:
            record = {"state": "uploading", "tag": "volcano-asr-" + uuid.uuid4().hex}
            records[name] = record
            save()
        try:
            result = _post_multipart(upload["url"], body, ctype, hdr, cfg["timeout"])
            audio_url = result.get(upload["url_key"])
            if not isinstance(audio_url, str) or not audio_url.startswith("https://"):
                raise ValueError("missing upload URL")
        except Exception as exc:
            if _asr_definite_http_failure(exc):
                record["state"] = "failed"
                save()
                raise
            raise TranscriptionPending(name, "파일 업로드 응답 미확인 — 아직 전사 접수 전이며 업로드부터 재개",
                                       cfg["poll_sec"]) from exc
        record.update(state="uploaded", audio_url=audio_url)
        save()
        return record


def _asr_find_gladia_submission(cfg, record, hdr):
    lookup = cfg["resume_lookup"]
    for page in range(lookup["max_pages"]):
        query = urllib.parse.urlencode({"offset": page * lookup["page_size"], "limit": lookup["page_size"]})
        url = lookup["list_url"] + ("&" if "?" in lookup["list_url"] else "?") + query
        data = get_json(url, hdr, cfg["timeout"])
        jobs = data.get("items")
        if not isinstance(jobs, list):
            return None
        found = {str(j["id"]) for j in jobs if isinstance(j, dict) and j.get("id")
                 and isinstance(j.get("custom_metadata"), dict)
                 and j["custom_metadata"].get(lookup["metadata_key"]) == record.get("tag")}
        if found:
            return next(iter(found)) if len(found) == 1 else None
        if len(jobs) < lookup["page_size"] or data.get("next") is None:
            break
        # next는 페이지 유무만 본다. 그 주소로 API 키를 전송하지 않는다.
    return None


def _asr_submit_poll(path, name, cfg, hdr, records, save, prepare=None, source_check=None):
    record = records.get(name)
    if isinstance(record, dict) and record.get("state") in ("uploading", "uploaded", "submitting", "accepted"):
        _asr_event(name, "resumed")
    if record is not None and (not isinstance(record, dict)
                              or record.get("state") not in ("uploading", "uploaded", "submitting", "accepted", "failed")):
        raise TranscriptionPending(name, "접수 기록 상태를 읽을 수 없어 확인 필요")
    if record and record["state"] == "failed":
        raise StepError("기존 접수가 명시적으로 실패하여 다음 제공자를 사용")
    if (record and record["state"] in ("uploading", "uploaded")
            and cfg["kind"] != "upload_submit_poll"):
        raise TranscriptionPending(name, "접수 기록의 업로드 상태와 제공자 규약이 달라 확인 필요")
    if cfg["kind"] == "upload_submit_poll":
        upload_path = (prepare() if prepare and (record is None or record["state"] == "uploading") else path)
        record = _asr_upload(upload_path, name, cfg, hdr, record, records, save, source_check)
    if record is None or record["state"] == "uploaded":
        fields = copy.deepcopy(cfg.get("fields") or {})
        lookup = cfg.get("resume_lookup") or {}
        if record is None:
            record = {"state": "submitting"}
            if lookup.get("kind") == "speechmatics_tracking":
                record["tag"] = "volcano-asr-" + uuid.uuid4().hex
                tracking = fields.setdefault("config", {}).setdefault("tracking", {})
                tracking["tags"] = list(tracking.get("tags") or []) + [record["tag"]]
            fields = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                      for k, v in fields.items()}
        else:
            fields["audio_url"] = record["audio_url"]
            fields.setdefault("custom_metadata", {})[lookup["metadata_key"]] = record["tag"]
            record["state"] = "submitting"
        with contextlib.ExitStack() as body_scope:
            if cfg["kind"] == "upload_submit_poll":
                submit = post_json
                submit_args = (cfg["submit_url"], fields, hdr, cfg["timeout"])
            else:
                body, ctype = _asr_multipart(fields, cfg["file_field"], prepare() if prepare else path, source_check)
                body_scope.enter_context(body)
                submit = _post_multipart
                submit_args = (cfg["submit_url"], body, ctype, hdr, cfg["timeout"])
            if source_check is not None:
                source_check()
            records[name] = record
            save()                         # 성공한 뒤에만 실제 전사 POST를 보낸다
            try:
                _asr_event(name, "submitted")
                result = submit(*submit_args)
                jid = result.get(cfg["id_key"])
                if not isinstance(jid, (str, int)) or isinstance(jid, bool) or not str(jid):
                    raise ValueError("missing job id")
            except Exception as exc:
                if _asr_definite_http_failure(exc):
                    record["state"] = "failed"
                    save()
                    raise
                raise TranscriptionPending(name, "접수 응답 미확인 — 다음 실행에서 접수 표지 조회",
                                           cfg["poll_sec"]) from exc
            record.update(state="accepted", job_id=str(jid))
            save()
    elif record["state"] == "submitting":
        try:
            jid = _asr_find_submission(cfg, record, hdr)
        except Exception as exc:
            raise TranscriptionPending(name, "접수 표지 조회 미완료 — 접수 여부 확인 필요",
                                       cfg["poll_sec"]) from exc
        if not jid:
            raise TranscriptionPending(name, "접수 번호 미확인 — 제공자 작업 목록에서 접수 표지를 확인해야 함 "
                                       + str(record.get("tag") or "(표지 없음)"), cfg["poll_sec"])
        record.update(state="accepted", job_id=jid)
        save()
    jid = record.get("job_id")
    if not isinstance(jid, str) or not jid:
        raise TranscriptionPending(name, "접수 번호가 손상되어 확인 필요")
    # ID는 URL 경로 값이다. 원문을 삽입해 쿼리/경로가 바뀌지 않게 한다.
    jid_path = urllib.parse.quote(jid, safe="")
    deadline = (time.monotonic() + cfg["poll_timeout"]
                if cfg.get("poll_timeout") is not None else None)
    def remaining_timeout():
        left = deadline - time.monotonic() if deadline is not None else cfg["timeout"]
        if left <= 0:
            raise TranscriptionPending(name, "이번 상태 조회 시간 한도 도달", cfg["poll_sec"])
        return min(cfg["timeout"], left)
    for _ in range(cfg["poll_max"]):
        time.sleep(min(cfg["poll_sec"], remaining_timeout()))
        try:
            st = get_json(cfg["status_url"].replace("{id}", jid_path), hdr, remaining_timeout())
            values = _pluck(st, cfg["status_pick"])
            status = str(values[0]).lower() if values else ""
        except TranscriptionPending:
            raise
        except Exception as exc:
            reason = ("기존 접수 상태 조회 HTTP " + str(exc.code) + " — 제공자 키/작업 접근 확인 필요"
                      if isinstance(exc, urllib.error.HTTPError) else "기존 접수 상태 조회 미완료")
            raise TranscriptionPending(name, reason, cfg["poll_sec"]) from exc
        if status in cfg["failed"]:
            record["state"] = "failed"
            save()
            raise StepError("전사 제공자가 작업 실패를 반환: " + status)
        if status in cfg["done"]:
            try:
                tr = (st if cfg.get("result_in_status") is True else
                      get_json(cfg["result_url"].replace("{id}", jid_path), hdr, remaining_timeout()))
                return _WORD_READER[name](tr)
            except TranscriptionPending:
                raise
            except Exception as exc:
                raise TranscriptionPending(name, "완료된 접수의 결과 읽기 미완료 — 제공자 접근/응답 확인 필요",
                                           cfg["poll_sec"]) from exc
    raise TranscriptionPending(name, "기존 접수의 완료/실패가 아직 확인되지 않음(이번 조회 한도 도달)", cfg["poll_sec"])


def _transcribe_attempt(path, plan, keys, records, save, source_check=None):
    with _asr_audio_input(path, plan) as prepare, contextlib.ExitStack() as scope:
        prepared_source = None
        def check_sources():
            if source_check is not None:
                source_check()
            if prepared_source is not None:
                prepared_source.check()
        def checked_prepare():
            nonlocal prepared_source
            try:
                check_sources()
                ready = prepare()
                check_sources()
                if prepared_source is None:
                    # Capture once, before handing its path to any provider. All
                    # fallback attempts share this snapshot and explicit lifetime.
                    prepared_source = scope.enter_context(_FileBody(ready))
                check_sources()
                return ready
            except OSError as exc:
                raise _AudioPreparationError("전사 원본 또는 준비 음성이 바뀌었습니다. API 호출 전 중단했습니다.") from exc
        return _transcribe_providers(path, plan, keys, records, save, checked_prepare, check_sources)


def _transcribe_providers(path, plan, keys, records, save, prepare, source_check=None):
    """오디오 → 단어 타임스탬프. **제공자 사다리·엔드포인트·본문은 전부 서버가 준다.**

    실행기가 아는 것은 "이 제공자의 응답에서 단어를 어떻게 읽는가" 뿐이다 —
    공개 API 문서에 있는 일반 지식이고 채널 규격이 아니다.
    ★언어를 자동감지로 두지 마라. 서버가 지정한 값을 그대로 보낸다.

    ★**"말이 없다" 와 "못 읽었다" 를 가른다** (2026-08-12).
      예전 코드는 `if w:` 하나로 봤다 — 전사가 **정상 완료됐는데 단어가 0개**면
      실패로 치고 다음 제공자로 넘어가다 끝내 `StepError` 로 죽었다.
      그래서 **말이 없는 원본은 아예 진행이 불가능**했다. 어랍숏은 재더빙 채널이라
      그런 소재(정비·공예·요리 현장음만 있는 외국 UGC)가 오히려 흔하다 —
      실제로 사장님이 주신 예제(오토바이 체인 정비 65초)가 말이 0초였다.
      지금은 **완료 여부**로 판정한다: 완료했으면 0개여도 그것이 측정값이다.
      전부 오류로 끝났을 때만 던진다 — 그때는 서버가 값을 못 받는다.
    """
    last = None
    active = [n for n in plan["order"] if (records or {}).get(n, {}).get("state")
              in ("uploading", "uploaded", "accepted", "submitting", "submitting_direct")]
    # 새 키가 생겼거나 우선순위가 바뀌어도 먼저 접수한 작업부터 이어 받는다.
    order = active + [n for n in plan["order"] if n not in active]
    resolved_keys, key_errors = {}, set()
    # ★키가 없거나(클라우드 제공자) 제공자가 키를 거부했으면(401/403 확정 응답) 그것은 «제공자 장애» 가 아니라 «사람이 키를
    #   고칠 일» 이다(#175 · 9명 · 한 사람이 15분에 같은 403 으로 23번). 끝까지 그것뿐이면 ASRSetupRequired 로 올려 서버의
    #   asr_setup(키 자리·원본 자막 지정)이 닿게 한다. 거부한 제공자는 이 실행에서 다시 부르지 않는다(자동 재시도 없음 · 6-2).
    keyless, refused, other = [], [], []
    def resolve_key(name):
        # Unused fallback credentials must not block the selected provider or
        # an accepted job's resume. A malformed cloud key is still configured:
        # it cannot silently authorize a local Whisper fallback.
        if name not in resolved_keys:
            try:
                resolved_keys[name] = (keys or {}).get(name) or _read_service_key(plan["providers"].get(name))
            except (OSError, UnicodeError):
                key_errors.add(name)
                resolved_keys[name] = None
        return resolved_keys[name]
    for name in order:
        cfg = plan["providers"].get(name)
        # ★★키를 **서버가 알려준 자리**에서 직접 읽는다 (2026-08-26).
        #   전에는 `keys`(=`headers['asr_keys']`)에서만 찾았는데 **그 통을 채우는
        #   코드가 저장소 어디에도 없었다** — 키를 실제로 가진 사람이 전사에서
        #   막혔다(08-25 12회·10명). 자리는 `auth_headers` 와 **같은 규약**으로
        #   서버가 준다(`key_file`·`env_var`) — 실행기가 경로를 지어내지 않는다.
        #   ★호출자가 직접 넘긴 `keys` 가 **우선**이다(수동 지정 우선 · 옛 계약 유지).
        key = resolve_key(name)
        if name in key_errors:
            if name in active:
                raise TranscriptionPending(name, "기존 접수를 조회할 키 파일의 접근 권한·인코딩 확인 필요")
            last = f"{name}: 키 파일의 접근 권한·인코딩을 확인하세요"
            continue
        # ★로컬 실행은 **키가 없는 것이 정상**이다. 여기서 걸러내면 사다리의
        #   바닥이 통째로 사라진다 — 키 없는 수강생이 이 자리에서 막혔던 그 결함이다.
        if name in active and cfg and cfg.get("kind") != "local_cmd" \
                and (not isinstance(key, str) or not key.strip()):
            raise TranscriptionPending(name, "기존 접수를 조회할 제공자 키가 없음 — 같은 제공자 키 설정 복구 필요")
        if not cfg or (not key and cfg.get("kind") != "local_cmd"):
            if cfg:
                keyless.append(name)
            continue
        if cfg.get("kind") == "local_cmd" and any(
                resolve_key(provider) or provider in key_errors for provider in order
                if (plan["providers"].get(provider) or {}).get("kind") != "local_cmd"):
            _progress("    [전사] 클라우드 키가 설정되어 로컬 전사는 실행하지 않습니다. 제공자 오류/키를 확인하세요.", flush=True)
            continue
        if cfg.get("kind") == "local_cmd" and plan.get("local_authorized") is not True:
            raise ASRSetupRequired()
        _asr_event(name, "selected")
        try:
            # ★로컬 실행에는 인증 헤더가 없다. 무조건 만들면 KeyError 로 죽고,
            #   그 예외를 위의 except 가 삼켜 **"제공자 장애" 처럼 보인다.**
            hdr = ({cfg["auth_header"]: cfg["auth_prefix"] + key}
                   if cfg.get("auth_header") else {})
            done, w = False, []
            if cfg["kind"] in ("submit_poll", "upload_submit_poll"):
                w = _asr_submit_poll(path, name, cfg, hdr, records, save, prepare=prepare, source_check=source_check)
                done = True
            elif cfg["kind"] == "local_cmd":
                # ★키가 없어도 되는 마지막 길. **argv 는 서버가 준다** — 실행기가
                #   모델·언어·옵션을 고르면 수강생마다 결과가 갈린다(§실행기 기본값 금지).
                exe = shutil.which(cfg["bin"])
                if not exe:
                    continue                      # 안 깔려 있다 = 이 제공자가 없는 것
                audio_path = prepare()
                outdir = os.path.join(os.path.dirname(os.path.abspath(audio_path)), "asr")
                os.makedirs(outdir, exist_ok=True)
                stem = os.path.splitext(os.path.basename(audio_path))[0]
                sub = {"{bin}": exe, "{in}": audio_path, "{outdir}": outdir, "{stem}": stem}
                argv = [sub.get(a, a) for a in cfg["argv"]]
                _spawn(argv, check=True, capture_output=True,
                               timeout=cfg.get("timeout") or 900)
                if source_check is not None:
                    source_check()
                rp = cfg["reads"]
                for k_, v_ in sub.items():
                    rp = rp.replace(k_, v_)
                with open(rp, encoding="utf-8") as f_:
                    tr = json.load(f_)
                done, w = True, _WORD_READER[name](tr)
            else:                                    # kind == "multipart_direct"
                body, ctype = _asr_multipart(cfg.get("fields") or {}, cfg["file_field"], prepare(), source_check)
                with body:
                    if records is not None:
                        old = records.get(name)
                        if old and old.get("state") != "failed":
                            raise TranscriptionPending(name, "직접 전사 응답 미확인 — 제공자 이력 확인 필요")
                        records[name] = {"state": "submitting_direct"}
                        save()
                    try:
                        _asr_event(name, "submitted")
                        tr = _post_multipart(cfg["submit_url"], body, ctype, hdr, cfg["timeout"])
                        done, w = True, _WORD_READER[name](tr)
                    except Exception as exc:
                        if records is None:
                            raise
                        if _asr_definite_http_failure(exc):
                            records[name] = {"state": "failed"}
                            save()
                            raise
                        raise TranscriptionPending(name, "직접 전사 응답 미확인 — 제공자 이력 확인 필요") from exc
            if done:
                _asr_event(name, "completed")
                _progress(f"    [전사] {name} · 단어 {len(w)}개"
                      + ("  ← 원본에 사람 말이 없다" if not w else ""), flush=True)
                return w, name
        except (TranscriptionPending, _AudioPreparationError):
            raise                       # 대기/로컬 전처리 실패는 다음 제공자로 넘기지 않는다.
        except Exception as e:                                    # noqa: BLE001
            if (records or {}).get(name, {}).get("state") in (
                    "uploading", "uploaded", "accepted", "submitting", "submitting_direct"):
                # A new accepted ID/upload URL is as durable as a resumed one.
                # Source validation after POST must not turn it into a retry.
                raise TranscriptionPending(name, "기존 접수 재개 중 확인 오류 — 접수 기록/제공자 설정 확인 필요") from e
            code = getattr(e, "code", None) if isinstance(e, urllib.error.HTTPError) else None
            if code in (401, 403):
                refused.append(f"{name}: HTTP {code}")
                _progress(f"    [전사] {name} 이 키를 거부했다(HTTP {code}) — 이 실행에서 다시 부르지 않는다", flush=True)
                continue
            detail = ""
            if code == 400:
                # 400 은 요청 내용 문제다 — 제공자가 준 본문을 실패 글에 남긴다(원인 추정 금지 · 본문이 근거).
                try:
                    detail = " · 응답 본문: " + e.read()[:300].decode("utf-8", "replace")
                except (OSError, ValueError, AttributeError) as read_error:
                    detail = f" · 응답 본문을 읽지 못함({type(read_error).__name__})"
            last = f"{name}: {type(e).__name__} {str(e)[:70]}{detail}"
            other.append(last)
            _progress(f"    [전사] {name} 실패 → 다음 제공자", flush=True)
            continue
    if (keyless or refused) and not other:
        setup = ASRSetupRequired()
        setup.args = ("전사 키가 " + " · ".join(
            [*(["없습니다(" + ", ".join(keyless) + ")"] if keyless else []),
             *(["제공자에게 거부됐습니다(" + ", ".join(refused) + " — 키 값·요금제·사용 한도를 확인하세요)"] if refused else [])])
            + ". 키를 연결하거나 고친 뒤 같은 단계를 재개하세요 — 원본 자막 파일이 있으면 subtitle_path 로 지정해도 됩니다. "
              "전사를 다시 요청하지 않았습니다.",)
        raise setup
    raise StepError("전사가 **한 번도 완료되지 않았다** — 키가 있는 제공자가 없거나 "
                    f"전부 오류로 끝났다. {last or ''}\n"
                    "★단어 0개는 이 오류가 아니다. 그건 '말이 없다' 로 정상 반환한다.")


def rise_edges(path, p):
    """오디오 → 상승엣지·소리구간 묶음. 규격 상수는 **서버가 준다.**

    ★numpy(rFFT)가 없으면 빈 목록들과 측정 불가 사유를 돌려준다. 근사를 넣으면 안 된다 —
      dB 스케일이 달라(중앙 −52 vs −25) 서버의 임계 보정이 통째로 무효가 되고,
      조용히 틀린 시각이 박힌다. 그때는 서버가 1단(단어)만 쓴다.
      너무 짧아 비교하지 못한 음성도 실제로 측정한 무음과 구별한다.
    """
    try:
        import numpy as np
    except ImportError:
        _progress("    [파형] numpy 가 없다 — 단어 타임스탬프만 쓴다", flush=True)
        return {"edges": [], "voiced": [], "unavailable": "numpy_missing"}
    # ★디코딩 argv 도 **서버가 준다.** 실행기가 ffmpeg 명령을 지으면 결과가 갈린다
    #   (`-vn` 하나가 빠지면 버릴 비디오까지 디코딩해 180배 느려진다 — 정본 실측).
    raw = path + ".16k.raw"
    run_argv([a.replace("{in}", path).replace("{out}", raw) for a in p["decode_argv"]])
    nw, nh = int(p["sr"] * p["win_s"]), int(p["sr"] * p["hop_s"])
    x = np.fromfile(raw, dtype="<i2").astype("f4") / 32768.0
    os.remove(raw)
    if len(x) < nw:
        return {"edges": [], "voiced": [], "unavailable": "audio_too_short"}
    nfr = 1 + (len(x) - nw) // nh
    win = np.hanning(nw).astype("f4")
    freqs = np.fft.rfftfreq(nw, 1.0 / p["sr"])
    band = (freqs >= p["band_lo_hz"]) & (freqs <= p["band_hi_hz"])
    out = np.empty(nfr, dtype="f4")
    ar = np.arange(nw)
    for s in range(0, nfr, 20000):
        e = min(nfr, s + 20000)
        idx = np.arange(s, e) * nh
        sp = np.fft.rfft(x[idx[:, None] + ar[None, :]] * win, axis=1)
        pw = (np.abs(sp[:, band]) ** 2).mean(axis=1)
        out[s:e] = 10.0 * np.log10(np.maximum(pw, 1e-20))
    n2 = max(1, int(round(p["db_span_s"] / p["hop_s"])))
    c = np.concatenate([[0.0], np.cumsum(out.astype("f8"))])
    r = np.full(nfr, p["db_floor"], dtype="f4")
    if nfr > 2 * n2:
        i = np.arange(n2, nfr - n2)
        r[i] = (c[i + n2] - c[i]) / n2 - (c[i] - c[i - n2]) / n2
    if nfr < 3:
        return {"edges": [], "voiced": [], "unavailable": "audio_too_short"}
    lm = (r[1:-1] >= r[:-2]) & (r[1:-1] > r[2:]) & (r[1:-1] >= p["rise_min_db"])
    edges = [round(float((i + 1) * p["hop_s"]), 3) for i in np.nonzero(lm)[0]]

    # ── 소리 나는 구간(호흡) — 임계는 **서버가 준다** ────────────────────
    #   원음 대사 자막은 단어가 아니라 이 경계에 놓인다(다른 언어라 단어 정렬 불가).
    base = float(np.percentile(out, p["voiced_pct"])) + p["voiced_over_db"]
    thr = max(base, p["voiced_floor_db"])
    on = out >= thr
    runs, i = [], 0
    n = len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and on[j]:
            j += 1
        if (j - i) * p["hop_s"] >= p["voiced_min_s"]:
            runs.append([round(i * p["hop_s"], 3), round(j * p["hop_s"], 3)])
        i = j
    return {"edges": edges, "voiced": runs}



# ── 후보 랭킹 ────────────────────────────────────────────────────────────
#
# ■ 왜 필요한가
#     지금까지는 구글이 준 **순서 그대로** 앞에서 4장을 받았다.
#     그 1위가 맞을 확률은 실측 **24%**(오답 44%)다 — 순서는 우리 기준이 아니다.
#
# ■ 점수 규칙 (all-in-one `ranking.ts:scoreReferenceResult` 를 옮긴 것)
#     ★우리가 **실제로 가진 신호만** 쓴다. 저쪽은 제목·스니펫·contextLink 가 있지만
#       우리 파서는 URL·가로·세로뿐이다. 없는 신호를 지어내지 않는다 —
#       그 자리는 점수 0 이고, 그 사실을 여기 적어 둔다.
#         못 쓰는 것: criticalPhrases/softPhrases 일치 · 제목 길이 · 기사/SNS 문구
#         쓰는 것  : 도메인 신호(선호/저신호/스톡) · 해상도 · 종횡비
#
#     선호 도메인      +6   (go.kr · or.kr · ac.kr · museum · heritage · unesco …)
#     저신호 도메인    −20  (facebook · instagram · youtube · pinterest …)
#     스톡 도메인      −100 (deny 목록. 이미 앞에서 끊지만 점수로도 눌러 둔다)
#     짧은변 < 300     −4
#     짧은변 ≥ 720     +2
#     종횡비 > 3       −3   (띠 배너·파노라마는 슬롯에 안 맞는다)
#     도메인 못 읽음   −3
#
# ■ 같은 점수면 **면적이 큰 것**을 앞에 둔다(저쪽과 같은 규칙).


def _host_of(url):
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _match_any(host, pats):
    return any(p and p in host for p in pats)


def _score_candidate(url, w, h, prefer, low_signal, deny):
    host = _host_of(url)
    score = 0
    if not host:
        score -= 3
    else:
        if _match_any(host, low_signal):
            score -= 20
        if _match_any(host, prefer):
            score += 6
        if any(d and d in url for d in deny):
            score -= 100
    if w > 0 and h > 0:
        lo, hi = min(w, h), max(w, h)
        if lo < 300:
            score -= 4
        if lo >= 720:
            score += 2
        if hi / max(1, lo) > 3:
            score -= 3
    return score


def _rank(urls, prefer, low_signal, deny):
    """★크기를 **모르는**(0,0) 후보는 점수로 불리해지지 않게 둔다.

    파서 ③갈래(맨 정규식)는 크기를 못 준다. 그걸 「작다」로 읽으면
    멀쩡한 후보가 뒤로 밀린다 — 「모른다」와 「작다」는 다르다.
    """
    rows = []
    for u in urls:
        w, h = _SIZE_HINT.get(u, (0, 0))
        rows.append((_score_candidate(u, w, h, prefer, low_signal, deny),
                     w * h, u))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    return [u for _, _, u in rows]


class CandidateHostRefused(OSError):
    """사진 후보를 담은 제3자 호스트가 그 주소를 HTTP 403 으로 막았다 — 우리 제공자의 거부가 아니라 «이 후보를 못 쓴다»(신고 #33 ·
    네이버 «Bad URL hash» · 서명 만료 · 핫링크 차단). 그 호스트에는 이 실행에서 더 묻지 않는다(호스트 단위 6-2)."""

    def __init__(self, host, code):
        super().__init__(f"{host} 가 HTTP {code} 로 막음")
        self.host, self.code = host, code


def _download_polite(url, out, headers, backoff, pace, candidate=False):
    """Keep the server pace, but propagate the first provider refusal.
    candidate=True(여러 후보 중 하나): 그 호스트의 403 은 후보 하나의 실패(CandidateHostRefused)로 돌려준다 — 429 는 그대로 거부."""
    hdr = {k: v for k, v in headers.items() if k.lower() != "accept"}
    with review_dispatch():
        time.sleep(pace)
        try:
            return download(url, out, headers=hdr)
        except urllib.error.HTTPError as error:
            if candidate and error.code == 403:
                raise CandidateHostRefused(urllib.parse.urlsplit(url).hostname or "?", error.code) from error
            raise


def fetch_images(jobs, retry, min_bytes, pace=0.0, backoff=(),
                 headers=None, retry_policy=None, candidates_out=None):
    """서버가 준 검색어·소스로 그림을 받아 out 에 저장한다.

    ★검색어도 소스도 **서버가 정한다.** 실행기는 던지고 받아 저장할 뿐이다.
    ★한 컷이라도 못 구하면 여기서 멈춘다 — 빈 컷을 다른 그림으로 메우면
      그 컷만 조용히 틀린 화면이 된다(뇌전구에서 겪은 §5 부류).

    ■ 2026-08-16 이관에서 고친 것
        ① `headers`·`retry_policy` 를 받는다 — `synthesize`·`generate_images` 와
           **같은 모양**이다. 429·403 에 되풀이하지 않는 정책이 이미지 경로에만
           안 걸려 있었다(2026-08-15 사고의 갈래가 살아 있었다).
        ② **검색 헤더를 다운로드에 재사용하지 않는다.** 그대로 두면 검색 키가
           임의의 이미지 CDN 으로 샌다.
        ③ **워터마크 도메인을 다운로드 전에 끊는다.** `min_px`·`min_bytes` 로는
           절대 안 걸러진다 — 해상도도 용량도 정상이기 때문이다.
           실측: 오염 42.9% → 0%, 못 쓰던 컷 6개 전량 회복.
           ★목록은 **서버가 준다**(`job["deny_domains"]`). 러너에 박으면 서버가
             고쳐도 안 따라온다.
        ④ DOM 에서 뽑은 **잘린 URL 조각**을 후보에서 뺀다.
    """
    from PIL import Image
    got, used = {}, set()
    # 다운로드 전용 헤더 — 검색 자격증명을 섞지 않는다
    dl_headers = {k: v for k, v in (headers or {}).items()
                  if k.lower() in ("user-agent", "accept-language", "referer")}
    # ★구글 사진(agy) 미리 찾기 (2026-09-28 «구글만 agy로») — 앞 출처(네이버)로 모자랄 칸의 첫 검색어만 모아
    #   동시에 먼저 찾는다. 칸마다 agy 한 번(30~40초)이 줄 서지 않게. 못 한 것은 아래 칸 순서에서 그 자리에서 찾는다.
    if candidates_out is not None:
        _agy_jobs = [j for j in jobs if 'candidates' not in j and any(
            str(s.get('kind') or '').lower() == 'agy_google' for s in (j.get('sources') or []))]
        if _agy_jobs:
            try:
                agy_google_plan_prefetch(_agy_jobs, backoff, pace)
            except PhotoSourceError as error:
                _progress(f"  [구글 사진·agy] 미리 찾기를 못 했다 — 칸마다 다시 시도한다: {error}")
    for j in jobs:
        if candidates_out is not None and 'candidates' not in j:
            candidates=[];seen=set();errors=[]
            limit=max(1,int(j.get('max_candidates') or 12))
            for query in j.get('queries') or []:
                for source in j.get('sources') or []:
                    try:
                        urls=_source_urls(source,query,backoff,pace)
                    except PhotoSourcePending:
                        raise
                    except PhotoSourceError as error:
                        errors.append(str(error));continue
                    for url in _rank(urls,j.get('prefer_domains') or (),
                                     j.get('low_signal_domains') or (),j.get('deny_domains') or ()):
                        if url in seen or any(d and d in url for d in j.get('deny_domains') or ()):continue
                        seen.add(url)
                        candidates.append({'url':url,'title':(_PHOTO_SOURCE_META.get(url) or {}).get('title') or ''})
                        if len(candidates)>=limit:break
                    if len(candidates)>=limit:break
                if len(candidates)>=limit:break
            if not candidates:
                detail=' / '.join(dict.fromkeys(errors)) or '검색 결과가 없습니다. 검색어를 수정하세요.'
                raise StepError(f"슬롯 {j['index']} 사진 후보 수집 실패: {detail}")
            j=dict(j,candidates=candidates)
        if 'candidates' in j and candidates_out is not None:
            directory=Path(j['out']);directory.mkdir(parents=True,exist_ok=True)
            found=[];why={};refused_hosts=set()
            for candidate in j['candidates']:
                url=candidate['url']
                host=urllib.parse.urlsplit(url).hostname or '?'
                name=hashlib.sha256(url.encode('utf-8')).hexdigest()
                path=directory/(name+'.png');receipt=directory/(name+'.json')
                cached=False;record={}
                try:
                    record=json.loads(receipt.read_text(encoding='utf-8'))
                    cached=record.get('sha256')==hashlib.sha256(path.read_bytes()).hexdigest()
                except (OSError,ValueError):pass
                if not cached and host in refused_hosts:
                    why[f'호스트가 앞서 막음({host})']=why.get(f'호스트가 앞서 막음({host})',0)+1;continue
                if not cached:
                    raw=directory/(name+'.download')
                    try:
                        n=_download_polite(url,str(raw),dl_headers,backoff,pace,candidate=True)
                        if n<int(min_bytes or 1):
                            why[f'파일이 너무 작음({int(min_bytes or 1)}바이트 미만)']=why.get(f'파일이 너무 작음({int(min_bytes or 1)}바이트 미만)',0)+1;continue
                        with Image.open(raw) as im:
                            if min(im.size)<j['min_px']:
                                why[f"그림이 작음(짧은 변 {j['min_px']}px 미만)"]=why.get(f"그림이 작음(짧은 변 {j['min_px']}px 미만)",0)+1;continue
                            rgba=im.convert('RGBA')
                            canvas=Image.new('RGB',rgba.size,'white');canvas.paste(rgba,mask=rgba.getchannel('A'))
                            temp=directory/(name+'.tmp.png');canvas.save(temp,'PNG');os.replace(temp,path)
                        record={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                        _photo_write_state(str(receipt),record)
                    except (OSError,ValueError,http.client.HTTPException) as error:
                        # HTTPException 도 후보 하나의 실패다 — download() 가 이어받기 끝에 IncompleteRead 를 그대로 올리고,
                        #   주소 모양이 틀린 InvalidURL 도 이 갈래다(OSError·ValueError 가 아니라 실행기 전체가 멈췄다 · 10-20 강석주).
                        if isinstance(error,CandidateHostRefused):refused_hosts.add(error.host)
                        # 어느 이유로 못 받았는지 센다(2026-10-17 강석주 images 5건 — 예전 정지 글은 이유가 한 글자도 없었다).
                        label=f"받기 실패({type(error).__name__}{' ' + str(getattr(error,'code','')) if getattr(error,'code',None) else ''})"
                        why[label]=why.get(label,0)+1
                        continue
                    finally:
                        try:raw.unlink()
                        except OSError:pass
                with Image.open(path) as im:w,h=im.size
                if min(w,h)<j['min_px']:
                    why[f"그림이 작음(짧은 변 {j['min_px']}px 미만)"]=why.get(f"그림이 작음(짧은 변 {j['min_px']}px 미만)",0)+1;continue
                found.append(dict(url=_file_uri(path),source_url=url,path=str(path.resolve()),
                                  sha256=record['sha256'],w=w,h=h,title=candidate.get('title') or ''))
            if not found:
                reasons=' · '.join(f'{k} {v}개' for k,v in why.items()) or '후보가 없습니다'
                raise StepError(f"슬롯 {j['index']}의 색인 후보 {len(j['candidates'])}개를 하나도 쓸 수 없었습니다 — {reasons}. "
                                "받기 실패가 많으면 인터넷 연결·차단(회사망 등)을 확인하고 같은 명령을 다시 실행하세요"
                                "(받아 둔 후보는 다시 받지 않습니다). 그림이 작다는 이유뿐이면 그 칸의 검색어를 바꾸세요.")
            candidates_out[str(j['index'])]=found
            _progress(f"  [후보] 슬롯 {j['index']}: {len(found)}장 — 아직 최종 그림으로 선택하지 않았습니다.",flush=True)
            continue
        # ★★직접 URL 갈래 (2026-09-01 이라스토야 마스코트) — 서버가 URL 을 지정한
        #   다운로드다. 검색 기전(queries·sources)을 안 탄다. 재배포 금지 자산이라
        #   서버가 파일을 못 주고 URL 만 준다 — sha 대조는 verify_meme 이 한다.
        if j.get("url"):
            os.makedirs(os.path.dirname(j["out"]) or ".", exist_ok=True)
            if j.get('sha256'):
                # Publish only the bytes the reviewer actually saw, atomically.
                expected=j['sha256']
                try:
                    if hashlib.sha256(Path(j['out']).read_bytes()).hexdigest()==expected:
                        got[j['out']]=os.path.getsize(j['out']);continue
                except OSError:pass
                temp=j['out']+'.selected.tmp'
                try:
                    n=_download_polite(j['url'],temp,dl_headers,backoff,pace)
                    if hashlib.sha256(Path(temp).read_bytes()).hexdigest()!=expected:
                        raise StepError('검수한 후보 파일이 변경됐습니다. 현재 그림을 다시 검수하세요.')
                    os.replace(temp,j['out']);got[j['out']]=n
                finally:
                    try:os.unlink(temp)
                    except OSError:pass
                continue
            n = _download_polite(j["url"], j["out"], dl_headers, backoff, pace)
            if not n or n < int(min_bytes or 1):
                raise StepError(
                    f"지정 URL 을 받지 못했다({n or 0}B): "
                    f"{j['url'][:80]} → {j['out']}")
            got[j["out"]] = n
            continue
        deny = tuple(j.get("deny_domains") or ())
        # 랭킹 신호 — **서버가 준다.** 러너에 박으면 서버가 고쳐도 안 따라온다.
        prefer = tuple(j.get("prefer_domains") or ())
        low_signal = tuple(j.get("low_signal_domains") or ())
        os.makedirs(os.path.dirname(j["out"]) or ".", exist_ok=True)
        done = False
        # ★같은 그림이 여러 컷에 깔리지 않게 이미 쓴 URL 을 건너뛴다. 다 썼으면
        #   재사용을 허용한다 — 컷을 비우는 것보다 낫다(빈 컷은 렌더가 죽는다).
        for allow_reuse in (False, True):
            if done:
                break
            for q in j["queries"]:
                if done:
                    break
                for src in j["sources"]:
                    if done:
                        break
                    # ★순서를 우리 기준으로 다시 세운다(도메인 신호 + 해상도).
                    cand = _rank(_source_urls(src, q, backoff, pace),
                                 prefer, low_signal, deny)[:40]
                    for url in cand:
                        if url in used and not allow_reuse:
                            continue
                        if not _valid_img_url(url):
                            continue
                        if any(dd and dd in url for dd in deny):
                            continue
                        # ★**받기 전에** 크기로 거른다. 파서가 알려 준 원본 크기다.
                        #   (0,0) 은 「모른다」이므로 그때는 받아 보고 판정한다.
                        hw, hh = _SIZE_HINT.get(url, (0, 0))
                        if hw and hh and min(hw, hh) < j["min_px"]:
                            continue
                        try:
                            # ★그림 서버도 속도 제한을 건다. API 만 물러나고 다운로드는
                            #   맨몸으로 던졌다가 6장째부터 전부 실패했다(2026-08-07).
                            #   헤더·간격·물러남을 **똑같이** 적용한다.
                            # ★검색 헤더(`src["headers"]`)를 여기 쓰지 않는다.
                            #   다운로드 전용 헤더만 넘긴다.
                            n = _download_polite(url, j["out"], dl_headers,
                                                 backoff, pace)
                            if n < min_bytes:
                                continue
                            with Image.open(j["out"]) as im:
                                w, h = im.size
                            if min(w, h) < j["min_px"]:
                                continue
                            # ★CMYK·팔레트·투명 PNG 가 섞여 온다. 렌더는 RGB 를 전제한다 —
                            #   여기서 맞춰 두지 않으면 PIL 이 프레임을 굽다가 죽는다.
                            with Image.open(j["out"]) as im:
                                im.convert("RGB").save(j["out"], "JPEG", quality=95)
                            with Image.open(j["out"]) as im:
                                w, h = im.size
                            got[j["index"]] = [w, h]
                            used.add(url)
                            _progress(f"  {j['index']:02d} {w}x{h}  {q}", flush=True)
                            done = True
                            break
                        except ProviderRefusalError:
                            raise
                        except Exception:                         # noqa: BLE001, S112
                            continue
        if not done:
            _close_google()
            raise StepError(
                f"컷 {j['index']} 의 그림을 못 구했다 — 검색어 {j['queries']!r}. "
                "빈 컷을 다른 그림으로 메우지 않는다. 검색어를 고쳐 다시 부르라.")
    # ★크롬을 반드시 닫는다. 안 닫으면 프로세스와 프로필 폴더가 쌓인다
    #   (실측: 죽인 실행들이 남긴 크롬이 61개였다).
    _close_google()
    return got


def _close_google():
    global _GOOGLE
    if _GOOGLE is not None:
        try:
            _GOOGLE.close()
        except Exception:                                           # noqa: BLE001, S110
            pass
        _GOOGLE = None


def _have(rule):
    """서버가 **키를 실어 준 경우에만** 건너뛴다. 규칙이 없으면 다시 만든다.

    ★예전에는 규칙이 없으면 `raw` 경로의 **존재**로 추측했다(fallback). 그래서 대본을
      고쳐도 `tts/_raw02.wav` 가 남아 있으면 새로 만들지 않았고, **옛 음성이 새 자막에
      붙었다** — 오류 0건. 판정은 '있느냐' 가 아니라 '**그 키의 것이냐**' 다.
    ★fallback 인자를 **시그니처에서 없앴다** — 호출부가 전달할 수 없어야 되살아나지 않는다.
    """
    r = rule or {}
    p, k = r.get("path"), r.get("key")
    if not p or not k:
        return False                       # ★fail-closed — 모르면 다시 만든다
    if k not in os.path.basename(p):
        raise StepError(f"캐시 경로가 키를 담고 있지 않다: {p} (키 {k})")
    return os.path.exists(p) and os.path.getsize(p) > r.get("min_bytes", 0)


def _publish(tmp, final):
    """이름이 존재하는 순간 **이미 완성본**이게 한다(같은 파일시스템 내 원자적 교체).

    ★중단된 실행이 남긴 잘린 파일을 캐시가 완성본으로 오인하면 조용히 틀린 결과가 남는다.
    """
    os.replace(tmp, final)


def _scene_provenance_qc(answer, job):
    """Keep typed scene observations; never persist face-derived name claims.

    The source context remains unverified identity metadata. Free model prose and
    biometric guesses cannot create or reject a candidate's identity.
    """
    count = int(job.get("n_candidates") or 0)
    kinds = {"person", "document", "diagram", "building", "artwork", "other"}
    decisions = []
    for raw in answer.get("decisions") or []:
        if not isinstance(raw, dict):
            continue
        modern = job.get("qc_contract") == "scene_provenance_v2"
        n, kind = raw.get("candidateNumber"), raw.get("visual_kind")
        match = raw.get("content_match" if modern else "scene_match")
        if modern and match == "match" and job.get("required_visuals"):
            match = ("match" if raw.get("requirements_met") is True else
                     "mismatch" if raw.get("requirements_met") is False else "uncertain")
        if type(n) is not int or not 1 <= n <= count or kind not in kinds or match not in {"match", "mismatch", "uncertain"}:
            continue
        document = raw.get("document_intended") is True and kind in {"document", "diagram", "building", "artwork"}
        suitable = kind == "person" or document
        code = ("insufficient_evidence" if match == "uncertain" else
                "wrong_content_type" if not suitable else
                "missing_required_visual" if match == "mismatch" else "relevant_scene")
        decision = dict(candidateNumber=n, visual_kind=kind, scene_match=match,
                        reason_code=code, preserve_text=document and raw.get("preserve_text") is True)
        if modern:
            preference = raw.get("preference_match")
            decision["preference_match"] = preference if preference in {"match", "mismatch", "uncertain"} else "uncertain"
        if job.get('require_subject_evidence') and kind == 'person':
            records = job.get('source_records') or []
            evidence = records[n - 1] if len(records) >= n else {}
            explicit = evidence.get('user_selected') is True
            bound = evidence.get('scope') in ('image_record', 'linked_photo_page') and any(
                _metadata_text(evidence.get(k)) for k in ('title', 'caption', 'description'))
            source_ok = explicit or (bound and raw.get('source_supported') is True and type(raw.get('subject_count')) is int and raw.get('subject_count') == 1)
            decision['source_supported'] = bool(source_ok)
            if not source_ok and decision['reason_code'] == 'relevant_scene':
                decision['reason_code'] = 'subject_source_unverified'
        decisions.append(decision)
    accepted = [d["candidateNumber"] for d in decisions if d["reason_code"] == "relevant_scene"]
    selected = answer.get("selectedCandidateNumber")
    selected = selected if selected in accepted else (accepted[0] if accepted else None)
    complete = {d["candidateNumber"] for d in decisions} == set(range(1, count + 1))
    verdict = "accepted" if selected is not None else "retry" if complete else "unchecked"
    summary = ("요청한 화면 유형과 장면에 부합합니다. 출처 메타는 인물 신원 인증이 아닙니다." if selected else
               "화면 유형 또는 요청 장면이 맞지 않거나 불확실합니다. 얼굴로 신원을 판정하지 않았습니다.")
    return dict(verdict=verdict, selectedCandidateNumber=selected, decisions=decisions,
                summary=summary, identity_verified=False, source_context="provided_metadata_only",
                retryQueryHints=_photo_retry_queries({"photo_review": job, "queries": []}, answer))


def _qc_selection_complete(job, answer):
    """Photo/contact-sheet acceptance needs a real candidate, not just a label."""
    if not isinstance(answer, dict):
        return False
    if answer.get('verdict') == 'retry':
        return True
    selected = answer.get('selectedCandidateNumber')
    count = job.get('n_candidates')
    return (answer.get('verdict') == 'accepted' and type(selected) is int
            and type(count) is int and 1 <= selected <= count)


def _review_binding_sha256(binding):
    """Hash legacy JSON bytes without a complete wide-Unicode/UTF-8 copy.

    Preserve sorting, separators, NaN and strict UTF-8 behavior: existing paid
    review receipts must keep the exact same cache identity across upgrades.
    """
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    for token in encoder.iterencode(binding):
        for offset in range(0, len(token), 16384):
            digest.update(token[offset:offset + 16384].encode('utf-8'))
    return digest.hexdigest()


def image_qc(jobs, headers, retry=3, retry_policy=None, parallel=None, claude=None,
             result_validator=None, allow_provider=True, review_policy=None, client_replies=None, review_budget=None, client=None):
    """조달 후보를 **한 번에 비교해** 고른다.

    ■ 왜 한 번에 보나
        장마다 따로 물으면 「이 장이 이 문단에 맞나」는 알아도
        「이 중에 무엇이 제일 맞나」는 못 고른다. 비교가 판단의 핵심이다.

    ■ ★키가 없으면 — **건너뛰되 「검수 못 했다」를 남긴다**
        `gemini` 는 선택 서비스다. 키가 없는 수강생을 막지 않는다.
        다만 결과에 `verdict:"unchecked"` 를 남긴다 —
        **「검수를 못 했다」와 「검수를 통과했다」는 다르다.**
        이걸 「통과」로 읽으면 자동 1위(정답률 24%)가 그대로 나간다.

    ■ ★전부 탈락하면
        `verdict:"retry"` 와 재검색어를 그대로 돌려준다. **그 자리는 비운다.**
        기본값으로 메우면 그 컷만 조용히 틀린 화면이 된다.
    """
    context = current_review_context()
    review_policy = resolve_review_policy(review_policy)
    selected_client = resolve_review_client(client, legacy=claude)
    client_replies = resolve_review_replies(client_replies)
    if context or review_budget is None: review_budget = context.get('budget')
    cache_claude = claude if client is None and _REVIEW_CONTEXT.get() is None else None
    validate = result_validator or _qc_selection_complete
    import threading
    stopped = threading.Event()
    failures = []

    def check_running(delay=0):
        if delay:
            stopped.wait(delay)
        if stopped.is_set():
            if isinstance(failures[0], (ProviderRefusalError, ClientReviewPending)):
                raise failures[0]
            raise StepError("다른 그림 검수가 중단되어 새 요청을 보내지 않았습니다. "
                            + str(failures[0])) from failures[0]

    def _one(j):
        check_running()
        try:
            with review_receipt_lock(_review_receipt_io_path(j['out'])):
                return _review(j)
        except Exception as exc:
            failures.append(exc)
            stopped.set()
            raise

    def _review(j):
        import base64
        os.makedirs(_review_receipt_io_path(os.path.dirname(j["out"]) or "."), exist_ok=True)
        imgs = j.get('_image_data')
        if imgs is None:
            imgs = []
            candidates = j.get('images') or []
            optional_remote = (j.get('candidate_acquisition') == 'optional_remote'
                and not j.get('qc_contract')
                and all(urllib.parse.urlsplit(im['url']).scheme.lower() in ('http', 'https')
                        for im in candidates))
            for number, im in enumerate(candidates, 1):
                try:
                    imgs.append((_fetch_b64(im['url']), im.get('mime') or 'image/jpeg'))
                except RemoteImageAcquisitionError:
                    if not optional_remote:
                        raise
                    # Keep this slot and its original candidate numbering. An
                    # incomplete contact sheet cannot be sent or called accepted.
                    return str(j['index']), dict(verdict='unchecked',
                        code='candidate_media_unavailable', failedCandidateNumbers=[number],
                        n_candidates=j.get('n_candidates'),
                        reason='외부 후보 그림을 받지 못해 이 칸은 검수하지 못했습니다.')
        semantic_key = j.get('qc_contract') in {'focus_selection_v1', 'focus_object_v1', 'film_frames_v1'}
        # Resume only a verdict for the same complete question, actual image
        # bytes, model/options and engine configuration. A path alone is not
        # evidence that its image still contains the same pixels.
        cache_keys = set()
        if semantic_key:
            cache_key = _image_review_key(j, imgs, cache_claude)
            if claude is not None and cache_claude is None:
                cache_keys.add(_image_review_key(j, imgs, claude))
        else:
            # Acquisition policy changes no question or image bytes. Existing
            # completed candidate reviews remain reusable when it is introduced.
            binding = dict(job={k: v for k, v in j.items() if k not in {"out", "_image_data", "candidate_acquisition"}},
                           images=imgs, claude=cache_claude, version=1)
            cache_key = _review_binding_sha256(binding)
            if claude is not None and cache_claude is None:
                old_binding = dict(binding, claude=claude)
                cache_keys.add(_review_binding_sha256(old_binding))
        cache_keys.add(cache_key)
        def save(raw, parsed, outcome=None):
            record = {'raw':raw, 'parsed':parsed, 'request_sha256':cache_key}
            record.update(outcome=outcome or {'status':'complete'}, parser_version=2)
            _review_receipt_save(os.path.abspath(j['out']), record)

        def stored_failure(outcome):
            if outcome.get('status') == 'refused':
                raise remember_review_refusal(ProviderRefusalError(outcome['origin'], outcome['reason_code'], outcome['reason']))
            exc = StepError(outcome.get('reason') or '앞선 검수 요청의 완료 여부를 확인할 수 없습니다. 같은 유료 요청은 자동 반복하지 않습니다.')
            exc.code = outcome.get('code') or 'review_unknown_completion'
            raise exc

        cached = _review_receipt_load(j['out'], [cache_key] + sorted(cache_keys - {cache_key}))
        if (isinstance(cached, dict) and cached.get('request_sha256') in cache_keys
                and release_unfinished_review(j['out'], cached['request_sha256'], cached, (
                    (cached.get('outcome') or {}).get('status') in UNFINISHED_REVIEW_OUTCOMES
                    or ((cached.get('parsed') or {}).get('verdict') == 'unparsed'
                        and not isinstance(cached.get('raw'), dict))))):
            # 사람이 «다시» 를 알린 컷(local_focus 화면 글자 검수의 review_retry_scope) — 결과 없이 끝났거나(started·failed)
            #   답 원문 없이 읽지 못한(unparsed) 이 요청을 한 번 다시 묻는다(옛 기록은 옆에 보존 · 범위 밖에서는 아무것도 놓지 않는다).
            #   답 원문(raw)이 있는 기록은 아래에서 먼저 다시 읽고, 그래도 못 읽을 때만 놓는다(값싼 재해석 먼저).
            #   예전에는 유료(evolink) 경로에 이 자리가 없어 «다시» 를 눌러도 저장된 실패가 그대로 돌아왔다(2026-10-15 검토).
            cached = {}
        try:
            prior = cached.get("parsed") or {}
            if (cached.get("request_sha256") in cache_keys
                    and prior.get("verdict") in ("accepted", "retry")
                    and prior.get("_engine") in ("claude", "gemini", "client")
                    and validate(j, prior)):
                return str(j["index"]), prior
        except (OSError, ValueError, AttributeError):
            pass
        if isinstance(cached, dict) and cached.get('request_sha256') in cache_keys:
            raw = cached.get('raw')
            if isinstance(raw, dict):
                engine = next((name for name in ('claude','client') if isinstance(raw.get(name),dict)), 'gemini')
                recovered = _qc_norm(raw[engine]) if engine in ('claude','client') else _qc_parse(raw, j.get('pluck'))
                if recovered.get('verdict') in ('accepted','retry') and not validate(j,recovered):
                    recovered = dict(recovered,verdict='unparsed',code='review_contract_invalid',
                                     reason='검수 후보 선택 또는 실측 ID가 누락되거나 범위를 벗어났습니다')
                recovered.update(n_candidates=j.get('n_candidates'), _engine=engine, request_sha256=cache_key)
                if not (recovered.get('verdict') == 'unparsed'
                        and release_unfinished_review(j['out'], cached['request_sha256'], cached, True)):
                    save(raw,recovered)
                    return str(j['index']), recovered
                # 다시 읽어도 못 읽는 답 — 사람이 «다시» 를 알린 범위에서만 한 번 새로 묻는다(아래 요청 경로로).
                cached = {}
        if isinstance(cached, dict) and cached.get('request_sha256') in cache_keys:
            outcome = cached.get('outcome') or {}
            if outcome.get('status') in {'started','failed','refused'}:
                stored_failure(outcome)
            prior = cached.get('parsed')
            if isinstance(prior,dict) and prior.get('verdict') == 'unparsed':
                return str(j['index']), prior
            blocked = outcome.get('review_budget_blocked') or {}
            # A matching receipt is evidence of an earlier attempt even when
            # its outcome is pending, missing or from a newer runner version.
            # Only an explicit never-sent budget block authorizes another try.
            if not (outcome.get('status') == 'budget_blocked'
                    and isinstance(blocked,dict)
                    and type(blocked.get('attempts_reserved')) is int and blocked['attempts_reserved'] == 0):
                stored_failure(outcome)
        if not allow_provider:
            # Execution policy is outside the semantic job/key. A local parser
            # repair may read a matching receipt, never start another question.
            return str(j['index']), {'verdict':'unparsed','code':'review_receipt_missing',
                'reason':'같은 질문의 저장된 그림 검수 답이 없습니다. 새 모델 요청은 보내지 않았습니다.',
                'n_candidates':j.get('n_candidates')}
        if review_policy.get('provider') == 'client':
            paths = []
            for n,(b64,mime) in enumerate(imgs):
                # A candidate that already lives here under its sha256 is found, not copied.
                target, _digest = _frozen_media_bytes(base64.b64decode(b64), os.path.dirname(j['out']),
                                                      _review_media_suffix(mime, image_only=True))
                paths.append(dict(path=target,mime=mime,
                    label=(j.get('image_labels') or [f'Candidate #{i+1}' for i in range(len(imgs))])[n]))
            import subject_stage_pool as ST
            if ST.active():
                imgs.clear()
                # The shared _image_data list is no longer needed after frozen
                # originals and the exact request key have been produced.
                if 'b64' in locals():del b64
            answer = client_review(dict(prompt=j['prompt'],qc_contract=j.get('qc_contract'),out=j['out'],
                images=paths,binding={'request_sha256':cache_key}),replies=client_replies,
                validator=lambda a:validate(j,a),claude=claude,
                **({'client':selected_client} if client is not None or _REVIEW_CONTEXT.get() is not None or not claude else {}))
            parsed = _qc_norm(answer)
            raw = {'client':answer}
            if j.get('qc_contract') in {'scene_provenance_v1','scene_provenance_v2'}:
                parsed = _scene_provenance_qc(parsed,j)
                raw = {'omitted':'Only typed scene observations are retained; unrestricted model prose is discarded.'}
            parsed.update(_engine='client',request_sha256=cache_key,n_candidates=j.get('n_candidates'))
            save(raw,parsed)
            return str(j['index']),parsed
        raw, parsed, engine = None, None, None
        check_running()
        body = None
        if j.get('max_request_bytes') is not None or j.get('max_media_bytes') is not None:
            body, media, size = _image_request_size(j, imgs)
            if not _image_request_fits(j, media, size):
                exc = StepError(f'그림 검수 요청 크기 상한을 넘었습니다: 본문 {size}바이트, 미디어 {media}바이트. 새 요청은 보내지 않았습니다.')
                exc.code = 'review_request_oversize'
                raise exc
        api_headers = headers() if callable(headers) else headers
        if not api_headers:
            return str(j['index']), {'verdict':'unchecked','code':'review_key_missing',
                'reason':'선택한 유료 검수의 키가 없어 검수하지 못했습니다.','n_candidates':j.get('n_candidates')}
        attempts = {'reserved':0}
        save(None, None, {'status':'started', 'code':'review_unknown_completion'})
        try:
            check_running()
            raw = _api_json_post(j["endpoint"], body if body is not None else _vision_body(j, imgs),
                # Paid image reviews have the same ambiguous-completion risk
                # as video reviews, even if an old job declares HTTP retries.
                api_headers, 1, {}, check_running=check_running,
                before_request=lambda:review_request_attempt(review_policy,review_budget,cache_key,attempts=attempts))
            parsed = _qc_parse(raw, j.get("pluck"))
            engine = "gemini"
        except Exception as exc:
            outcome = {'status':'failed','code':getattr(exc,'code','review_unknown_completion'),'reason':str(exc)[:1200]}
            if getattr(exc,'review_budget_blocked',None):
                outcome.update(status='budget_blocked',review_budget_blocked=exc.review_budget_blocked)
            if isinstance(exc,ProviderRefusalError):
                outcome = {'status':'refused','origin':exc.origin,'reason_code':exc.reason_code,'reason':exc.reason,
                           'request_sent':getattr(exc,'request_sent',True)}
            save(raw, None, outcome)
            raise
        if j.get("qc_contract") in {"scene_provenance_v1", "scene_provenance_v2"}:
            parsed = _scene_provenance_qc(parsed, j)
            raw = {"omitted": "Only typed scene observations are retained; unrestricted model prose is discarded."}
        if parsed.get('verdict') in ('accepted', 'retry') and not validate(j, parsed):
            parsed = dict(parsed, verdict='unparsed', code='review_contract_invalid', reason='검수 후보 선택 또는 실측 ID가 누락되거나 범위를 벗어났습니다')
        parsed["n_candidates"] = j.get("n_candidates")
        parsed["_engine"] = engine
        parsed['request_sha256'] = cache_key
        save(raw, parsed)
        pick = parsed.get("selectedCandidateNumber")
        _progress(f"  {int(j['index']):02d} {parsed.get('verdict')} "
              f"{('#' + str(pick)) if pick else '-'} "
              f"conf {parsed.get('confidence')} {(parsed.get('summary') or '')[:40]} "
              f"[{engine or '-'}]", flush=True)
        return str(j["index"]), parsed

    out = {}
    _w = max(1, min(int(parallel or 1), len(jobs) or 1))
    if _w > 1:
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        _progress(f"  [검수] {len(jobs)}장을 폭 {_w} 로 동시에 본다", flush=True)
        with ThreadPoolExecutor(max_workers=_w) as _ex:
            for k, v in _ex.map(review_context_worker(_one), jobs):
                out[k] = v
    else:
        for j in jobs:
            k, v = _one(j)
            out[k] = v
    n_retry = sum(1 for v in out.values() if v.get("verdict") == "retry")
    if n_retry:
        _progress(f"  [!] {n_retry}자리가 **재검색 필요**다 — 그 자리를 비워 두고 "
              "`retryQueryHints` 로 다시 조달하라. 기본값으로 메우지 마라.", flush=True)
    return out


def _fetch_b64(url):
    """후보 그림 한 장을 받아 base64 로. 실패는 호출부가 타입으로 처리한다.

    ★조용히 건너뛰지 않는다 — 후보가 빠지면 뒤 번호가 밀려서 모델이 고른 `#N` 이
      엉뚱한 그림을 가리킨다. 오류 없이 틀린 화면이 나가는 부류다.
    """
    import base64
    import http.client
    try:
        local = _file_uri_path(url)
        if local is not None:
            # ★로컬 그림은 URL 처리기를 거치지 않고 연다 — 윈도우 긴 경로(260자 넘음)도 `\\\\?\\` 로 열린다(W2-17).
            with open(local, 'rb') as stream:
                return base64.b64encode(stream.read()).decode()
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        for attempt in range(len(_UNSENT_RETRY_WAITS) + 1):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return base64.b64encode(r.read()).decode()
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
                # ★GET 한 장이라 연결이 끊긴 것은 상한 안에서 다시 받는다(2026-10-17 군림보 images 4건 — 한 번 끊기면 편 전체가
                #   멈췄다). HTTP 응답(403·429 등 거부)은 다시 보내지 않는다(전역 규칙 6-2).
                if isinstance(e, urllib.error.HTTPError) or attempt >= len(_UNSENT_RETRY_WAITS):
                    raise
                time.sleep(_UNSENT_RETRY_WAITS[attempt])
    except Exception as e:                                        # noqa: BLE001
        if (urllib.parse.urlsplit(str(url)).scheme.lower() in ('http', 'https')
                and isinstance(e, (urllib.error.URLError, OSError, http.client.HTTPException))):
            # URL queries, userinfo and provider/network exception text may hold
            # credentials. The typed failure needs no remote address or raw text.
            if isinstance(e, urllib.error.HTTPError):
                e.close()
            raise RemoteImageAcquisitionError('외부 후보 그림을 받지 못했습니다.') from e
        raise StepError(f"후보 그림을 못 받았다 — {str(url)[:80]} ({str(e)[:60]})") from e


def _qc_norm(obj):
    """판정 JSON(묶음)을 검수 결과 모양으로 — `_qc_parse` 와 **같은 규칙**(엔진이 달라도 자는 하나)."""
    v = str(obj.get("verdict") or "").lower()
    if v not in ("accepted", "retry"):
        v = "unparsed"
    result = {"verdict": v,
            "selectedCandidateNumber": obj.get("selectedCandidateNumber"),
            "confidence": obj.get("confidence"),
            "summary": obj.get("summary"),
            "decisions": obj.get("decisions") or [],
            "retryQueryHints": obj.get("retryQueryHints") or []}
    if isinstance(obj.get('reason'),str):
        result['reason'] = obj['reason'][:1200]
    if 'anchor_relations' in obj:
        result['anchor_relations'] = obj['anchor_relations']
    if 'refine_intervals' in obj:
        # Retain invalid shapes so the task validator rejects them; dropping an
        # invalid interval into [] would silently authorize missing evidence.
        result['refine_intervals'] = obj['refine_intervals']
    return result


def _qc_parse(raw, pluck=None):
    """모델 응답에서 판정 JSON 을 꺼낸다. **못 꺼내면 「모른다」로 둔다.**

    ★파싱 실패를 「통과」로 읽지 않는다 — 그게 가장 위험한 기본값이다.
    ★어디를 읽을지는 **서버가 준다**(`pluck`). 여기에 모양을 박으면 서버가
      경로를 바꿔도 안 따라온다 — 2026-08-22 에 그 자리가 실제로 갈려 있었다.
    """
    _raise_provider_refusal(raw)
    txt = _vision_text(raw, pluck) if pluck else ""
    obj = _json_object(txt)
    if not isinstance(obj, dict):
        return {"verdict": "unparsed",
                "reason": "판정 JSON 을 못 읽었다 — **통과로 읽지 마라**"}
    return _qc_norm(obj)


def _tts_identity(job):
    """Identify exactly the provider request; credentials are deliberately excluded."""
    request = [job["endpoint"], job["body"]]
    try:
        encoded = json.dumps(request, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StepError("음성 합성 요청 본문을 안정적으로 기록할 수 없습니다.") from exc
    return hashlib.sha256(encoded).hexdigest()


def _tts_paths(job):
    identity = _tts_identity(job)
    root = Path(job["raw"]).parent / ".volcano-tts"
    return (root / (identity + ".json"), root / (identity + ".audio"),
            root / (identity + ".lock"))


def _tts_raw_paths(job):
    receipt, _canonical, _lock = _tts_paths(job)
    raw_id = hashlib.sha256(os.path.abspath(job["raw"]).encode("utf-8")).hexdigest()
    return receipt.parent / ("raw-" + raw_id + ".json"), receipt.parent / ("raw-" + raw_id + ".lock")


def _tts_event(outcome, identity):
    """Metrics are evidence only; receipt safety never depends on their availability."""
    try:
        import runtime_metrics  # noqa: PLC0415
        runtime_metrics.event("tts", outcome, request_sha256=identity)
    except Exception:  # noqa: BLE001
        pass


def _tts_save(path, state):
    try:
        _asr_save(str(path), state)
        _tts_fsync_dir(str(path.parent))
    except (TranscriptionPending, OSError) as exc:
        message = ("음성 합성 접수 기록을 안전하게 저장하지 못했습니다. 기존 기록과 음성을 보존하고 "
                   "접수 상태를 확인하세요. 추가 요청은 자동으로 보내지 않습니다.")
        recovery = getattr(exc, 'recovery_path', None)
        if recovery:
            message += (" 새 기록 사본: " if getattr(exc, 'recovery_ready', False)
                        else " 쓰기 미완료 사본: ") + str(recovery)
        failure = StepError(message)
        for key in ('target_path', 'recovery_path', 'recovery_ready'):
            if hasattr(exc, key):
                setattr(failure, key, getattr(exc, key))
        raise failure from exc


def _tts_load(path, identity):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise StepError(f"음성 합성 접수 기록이 손상되었습니다. 재요청하지 않습니다: {path}") from exc
    if (not isinstance(state, dict) or state.get("version") != 1
            or state.get("request_sha256") != identity
            or state.get("status") not in ("intent", "rejected", "downloaded")):
        raise StepError(f"음성 합성 접수 기록 형식을 확인할 수 없습니다. 재요청하지 않습니다: {path}")
    if state["status"] == "downloaded":
        if (not isinstance(state.get("audio_sha256"), str)
                or len(state["audio_sha256"]) != 64
                or not isinstance(state.get("bytes"), int) or state["bytes"] < 0):
            raise StepError(f"음성 합성 완료 기록이 불완전합니다. 재요청하지 않습니다: {path}")
        staged = state.get("staged_audio")
        if staged is not None and (not isinstance(staged, str) or re.fullmatch(
                re.escape(identity + ".audio.part-") + r"[0-9a-f]{32}", staged) is None):
            raise StepError(f"음성 합성 임시 보존본 경로가 잘못되었습니다. 재요청하지 않습니다: {path}")
    return state


def _tts_load_raw(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise StepError(f"음성 원본 연결 기록이 손상되었습니다. 재요청하지 않습니다: {path}") from exc
    if (not isinstance(state, dict) or state.get("version") != 1
            or not isinstance(state.get("request_sha256"), str)
            or len(state["request_sha256"]) != 64):
        raise StepError(f"음성 원본 연결 기록 형식을 확인할 수 없습니다. 재요청하지 않습니다: {path}")
    return state["request_sha256"]


def _tts_file_sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tts_fsync(path):
    # Windows CRT _commit requires a writable descriptor; r+b never truncates.
    with open(path, "r+b") as fh:
        os.fsync(fh.fileno())


def _tts_fsync_dir(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _tts_ensure_directory(path):
    """Establish new receipt directories durably before sending any paid bytes."""
    missing = []
    parent = path
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Sync both the receipt directory and every newly created ancestor's
        # directory entry. On platforms without directory fsync, keep OS limits.
        directories = [path, path.parent]
        for created in missing:
            directories.extend((created, created.parent))
        for directory in dict.fromkeys(directories):
            _tts_fsync_dir(str(directory))
    except OSError as exc:
        raise StepError("음성 접수 기록 폴더를 안전하게 준비하지 못했습니다. 저장 공간과 권한을 확인하세요.") from exc


def _tts_publish_copy(source, destination):
    """Keep the canonical paid response while atomically repairing each declared raw path."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    fd, part = tempfile.mkstemp(prefix=".tts-publish-", dir=os.path.dirname(destination) or ".")
    try:
        with os.fdopen(fd, "wb") as out, open(source, "rb") as inp:
            shutil.copyfileobj(inp, out)
            out.flush()
            os.fsync(out.fileno())
        _publish(part, destination)
        _tts_fsync_dir(os.path.dirname(destination) or ".")
        part = None
    finally:
        if part and os.path.exists(part):
            os.unlink(part)


def _tts_restore_downloaded(canonical, state):
    """Recover only a recorded complete response, never arbitrary partial bytes."""
    def matches(path):
        try:
            return path.stat().st_size == state["bytes"] and _tts_file_sha(path) == state["audio_sha256"]
        except OSError:
            return False
    try:
        if not matches(canonical):
            staged = canonical.parent / state["staged_audio"] if state.get("staged_audio") else None
            if staged is None or not matches(staged):
                raise StepError(f"음성 합성 보존본이 없거나 완료 기록과 다릅니다. 재요청하지 않습니다: {canonical}")
            _tts_fsync(str(staged))
            _publish(str(staged), str(canonical))
        if state.get("staged_audio"):
            # Also complete a prior rename whose directory sync failed.
            _tts_fsync_dir(str(canonical.parent))
    except OSError as exc:
        raise StepError("완료한 음성 응답과 접수 기록을 보존했습니다. 저장 공간·권한 문제를 해결한 뒤 "
                        "같은 단계를 재개하면 새 합성 요청 없이 게시를 복구합니다.") from exc


@review_dispatch()
def _api_json_post(url, body, headers, retry, retry_policy, check_running=None, before_request=None):
    raw = _api_json_post_unlocked(url,body,headers,retry,retry_policy,check_running,before_request)
    _raise_provider_refusal(raw)
    return raw


def _api_json_post_unlocked(url, body, headers, retry, retry_policy, check_running=None, before_request=None):
    """Preserve provider evidence; retry only explicitly allowed server failures.

    A client error needs changed input/account state, even when a retry policy
    accidentally lists it. Unknown network completion is not proof of failure.
    """
    policy = retry_policy or {}
    retry_status = set(policy.get("retry_status") or [])
    no_retry = set(policy.get("no_retry_status") or [])
    backoff = list(policy.get("backoff_s") or [])
    stop_note = None
    data = json.dumps(body).encode("utf-8")
    hdr = dict(headers or {})
    hdr.setdefault("Content-Type", "application/json")
    last = None
    for i in range(max(1, retry)):
        # A peer can refuse while this job is in backoff. This is a new request,
        # so recheck the batch before sending; do not treat cancellation as a
        # network error eligible for another retry.
        if check_running:
            check_running()
        req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
        if before_request:
            before_request()
        check_review_running()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:                      # noqa: PERF203
            _http_error_detail(e, req)
            if e.code in (401,402,403,429):
                # 서버가 그 코드에 정한 «멈출 때 할 말»(volcano_spec.API_RETRY.stop_note — «새 계정을 만들지 마세요»
                # 등 계정 정지 사고 08-15 의 안내)이 거절 문구의 할 일이다. 94197b0f(10-02)가 거절을 즉시 멈춤으로
                # 바꾸며 이 안내를 버렸다 — 서버가 준 값을 실행기가 안 싣던 것.
                note = (policy.get("stop_note") or {}).get(str(e.code))
                raise ProviderRefusalError('provider.http',e.code,str(e),
                                           todo=(" ▶ " + note) if note else None) from e
            last = e
            if 400 <= e.code < 500 or e.code in no_retry or e.code not in retry_status:
                if str(e.code) in (policy.get("stop_note") or {}):
                    _, stop_note = _retry_gate(e, policy)
                break
        except Exception as e:                                   # noqa: BLE001
            last = e
            # A lost response may have been billed. Do not repeat an uncertain
            # request unless the server explicitly declared that network policy.
            if not policy.get("retry_network"):
                break
        if i + 1 < max(1, retry):
            delay = backoff[min(i, len(backoff) - 1)] if backoff else 2 * (i + 1)
            if check_running:
                check_running(delay)
            else:
                time.sleep(delay)
    error = StepError(f"검수 호출 실패: {str(last)[:600]} "
                      f"(요청 {len(data)}바이트). 완료한 검수는 보존했습니다."
                      + ("\n" + stop_note if stop_note else ""))
    error.code = 'review_unknown_completion'
    raise error


def synthesize(jobs, headers, retry, min_bytes, parallel=None, retry_policy=None):
    """서버가 만든 TTS 본문을 던지고, 서버가 준 **후처리 단계들**을 순서대로 적용한다.

    ★후처리가 몇 단계인지는 채널마다 다르다(한 단계도 있고 두 단계도 있다).
      여기서 "argv 하나" 를 가정하면 단계가 조용히 빠져 **그룹 길이가 달라지고
      자막이 통째로 밀린다.** 그래서 단계 수를 실행기가 정하지 않는다 — 목록을 받는다.
    ★옛 캐시는 서버가 준 규칙(`skip_if`)으로만 처음 채택한다. 새 요청부터는 endpoint/body
      전체를 묶은 내구 영수증으로만 재사용해, 응답을 잃은 유료 호출을 다시 보내지 않는다.
    """
    def _one(j):
        receipt, canonical, lock = _tts_paths(j)
        raw_receipt, raw_lock = _tts_raw_paths(j)
        identity = _tts_identity(j)
        _tts_ensure_directory(receipt.parent)
        # ★ffmpeg 은 폴더를 만들지 않는다. 서버가 선언한 산출 경로의 폴더를 먼저 만든다 —
        #   argv 를 뜯어 추측하지 않는다(실측: narr/ 가 없어 죽었다).
        for pth in [j.get("raw"), j.get("out")] + [st.get("out") for st in j["steps"]]:
            if pth:
                os.makedirs(os.path.dirname(pth) or ".", exist_ok=True)
        with _asr_lock(str(raw_lock), blocking=True):
            with _asr_lock(str(lock), blocking=True):
                bound = _tts_load_raw(raw_receipt) if raw_receipt.exists() else None
                state = _tts_load(receipt, identity) if receipt.exists() else None
                # Migrate each old server-keyed raw independently. Binding its
                # path to this full request prevents a later changed body from
                # adopting the same bytes, without invalidating sibling caches.
                if state is None and bound is None and _have(j.get("skip_if")):
                    _tts_publish_copy(j["raw"], str(canonical))
                    n = canonical.stat().st_size
                    audio_sha = _tts_file_sha(canonical)
                    _tts_save(receipt, {"version": 1, "request_sha256": identity,
                                        "status": "downloaded", "bytes": n,
                                        "audio_sha256": audio_sha})
                    _tts_save(raw_receipt, {"version": 1, "request_sha256": identity})
                    state = _tts_load(receipt, identity)
                resend_mark = str(receipt) + ".resend-once"
                if state and state["status"] == "intent" and os.path.exists(resend_mark):
                    # 사람이 그 컷만 «한 번 더 보내기» 를 골랐다(신고 #208 · 5xx 는 과금 여부 공식 근거 없음 — 자동으로는 보내지 않는다).
                    #   표식은 한 번 쓰고 지운다 · 이 실행이 이 컷을 새 요청으로 보낸다(아래 갈래).
                    os.remove(resend_mark)
                    _progress(f"  [음성] 컷 {j['index']} — 사람이 다시 보내기를 골랐다(표식 {os.path.basename(resend_mark)}) · 이 컷만 새로 요청한다",
                              flush=True)
                    state = None
                if state and state["status"] == "intent":
                    _tts_event("failed", identity)
                    raise StepError(
                        f"음성 합성 요청의 완료 여부를 알 수 없어 재요청하지 않습니다 (컷 {j['index']}). "
                        + _tts_resend_hint(resend_mark))
                if state and state["status"] == "downloaded":
                    _tts_restore_downloaded(canonical, state)
                    _tts_event("reused", identity)
                else:
                    # A definite 4xx rejection may be retried by a later invocation after
                    # credentials/input are corrected. Every other recorded intent is final.
                    _tts_save(raw_receipt, {"version": 1, "request_sha256": identity})
                    _tts_save(receipt, {"version": 1, "request_sha256": identity,
                                        "status": "intent"})
                    download = str(canonical) + ".part-" + uuid.uuid4().hex
                    _tts_event("submitted", identity)
                    try:
                        for _unsent_try in range(len(_UNSENT_RETRY_WAITS) + 1):
                            try:
                                post_bytes(j["endpoint"], j["body"], headers, download)
                                break
                            except Exception as exc:  # noqa: BLE001
                                # 요청이 제공자에 닿지 않았다(연결·본문 쓰기 단계) — 처리될 수 없었던 요청이라 상한 안에서 다시 보낸다.
                                if not _request_never_delivered(exc) or _unsent_try >= len(_UNSENT_RETRY_WAITS):
                                    raise
                                _progress(f"  ⚠ [음성] 컷 {j['index']} 요청이 서비스에 닿지 않았다({type(exc.reason).__name__}) — "
                                          f"{_UNSENT_RETRY_WAITS[_unsent_try]}초 뒤 다시 보낸다", flush=True)
                                time.sleep(_UNSENT_RETRY_WAITS[_unsent_try])
                    except ApiRefused as exc:
                        _tts_event("failed", identity)
                        # ★429 도 «확정 미처리» 다 (2026-10-05 · 원장 W2-26). 타입캐스트 공식 API 문서의 429 는
                        #   «Too Many Requests - Rate limit exceeded»(https://typecast.ai/docs/api-reference) — 한도로
                        #   받지 않은 요청이다(RFC 6585). 예전에는 intent 로 남아 그 컷이 «완료 여부를 알 수 없어
                        #   재요청하지 않습니다» 로 영구히 멈췄다(10-04 8건·7명 · 겹침 7/7). 이 실행은 지금처럼 즉시
                        #   멈추고(전역 규칙 6-2 — 자동 재시도 없음), 사람이 같은 명령을 다시 실행할 때만 다시 요청한다.
                        #   ★5xx 는 그대로 intent 다 — 같은 문서가 오류 때 과금 여부를 밝히지 않는다(«공식 숫자·규정 없음»).
                        if exc.code in (400, 401, 403, 404, 405, 413, 415, 422, 429):
                            _tts_save(receipt, {"version": 1, "request_sha256": identity,
                                                "status": "rejected"})
                        _, why = _retry_gate(exc, retry_policy)
                        if exc.code == 429:
                            # 일반 문구(«사람이 고쳐야 합니다»)는 429 에 틀린 말이다 — 기다렸다 다시 실행하면 된다.
                            server_note = ((retry_policy or {}).get("stop_note") or {}).get("429")
                            why = ("서비스 요청 한도(HTTP 429)에 걸렸습니다. 이 요청은 처리되지 않았습니다. 이번 실행의 "
                                   "음성 합성은 멈췄고, 잠시 뒤 같은 명령으로 다시 실행하면 이 컷부터 다시 요청합니다."
                                   + (f" (서비스가 {exc.retry_after}초 뒤에 다시 오라고 했습니다.)"
                                      if getattr(exc, "retry_after", None) else "")
                                   + (" " + server_note if server_note else ""))
                        elif not why:
                            # 서버 정책상 «다시 던져도 되는» 코드라 문구가 없다 — 예전에는 `None` 이 그대로 찍혔다.
                            why = (f"서비스가 HTTP {exc.code}(서버 오류)로 답했습니다. 공식 문서가 이때의 처리·과금 여부를 "
                                   "밝히지 않아 중복 과금을 막으려고 자동으로는 다시 보내지 않습니다. 접수 기록을 보존했습니다.")
                        if exc.code >= 500:
                            # 5xx 는 intent 로 남는다 — 서버 정책 문구(«사람이 고쳐야 합니다»)든 위 문구든 그 컷을 다시 보내는 길을 함께 말한다(#208).
                            why = f"{why} — " + _tts_resend_hint(str(receipt) + ".resend-once")
                        raise StepError(
                            f"음성 합성을 여기서 멈춥니다 (컷 {j['index']}).\n  {why}\n"
                            f"  서비스 응답: {str(exc)[:160]}") from exc
                    except Exception as exc:  # noqa: BLE001
                        _tts_event("failed", identity)
                        if _request_never_delivered(exc):
                            # 닿지 않은 요청은 처리·과금될 수 없다 — «완료 여부 모름»(intent) 으로 영구히 막지 않고 rejected 로 적어
                            # 다음 실행이 이 컷부터 다시 요청한다.
                            _tts_save(receipt, {"version": 1, "request_sha256": identity, "status": "rejected"})
                            raise StepError(
                                f"음성 합성 요청이 서비스에 닿지 않았습니다 (컷 {j['index']} · {type(exc.reason).__name__}: "
                                f"{str(exc.reason)[:120]}) — {len(_UNSENT_RETRY_WAITS) + 1}번 보냈고 전부 연결 단계에서 끊겼습니다"
                                "(접수·과금 없음). 인터넷 연결을 확인한 뒤 같은 명령을 다시 실행하면 이 컷부터 다시 요청합니다.") from exc
                        raise StepError(
                            f"음성 합성 요청의 완료 여부를 알 수 없어 재요청하지 않습니다 (컷 {j['index']}). "
                            f"{type(exc).__name__}: {str(exc)[:160]}") from exc
                    try:
                        n = os.path.getsize(download)
                        if n <= min_bytes:
                            raise StepError(
                                f"음성 응답이 비었다 (컷 {j['index']}, {n}바이트 ≤ {min_bytes}). "
                                "완료 여부가 불확실하므로 재요청하지 않습니다.")
                        audio_sha = _tts_file_sha(download)
                        # post_bytes returned after the complete HTTP body was
                        # written and closed. Record its exact bytes before local
                        # sync/rename, so those failures never require another POST.
                        state = {"version": 1, "request_sha256": identity,
                                 "status": "downloaded", "bytes": n,
                                 "audio_sha256": audio_sha,
                                 "staged_audio": Path(download).name}
                        _tts_save(receipt, state)
                        _tts_restore_downloaded(canonical, state)
                        _tts_event("succeeded", identity)
                    except OSError as exc:
                        raise StepError("받은 음성 응답을 보존했지만 로컬 저장을 완료하지 못했습니다. "
                                        "기존 접수 기록을 보존하고 저장 공간·권한을 확인하세요. "
                                        "추가 요청은 자동으로 보내지 않습니다.") from exc
                    # Never delete a response on persistence failure. Without a
                    # downloaded receipt it remains uncertain and cannot be adopted.
                try:
                    _tts_publish_copy(str(canonical), j["raw"])
                    _tts_save(raw_receipt, {"version": 1, "request_sha256": identity})
                except OSError as exc:
                    raise StepError(
                        f"음성 보존본은 완료했지만 산출 경로에 게시하지 못했습니다 (컷 {j['index']}). "
                        "같은 단계를 재개하면 새 요청 없이 복구합니다.") from exc
            # ★후처리에는 skip 이 없다 — 로컬·결정적이라 **언제나** 다시 돈다.
            #   여기에 skip 을 두면 필터 상수를 바꿔도 옛 정규화본이 남는다.
            for st in j["steps"]:
                run_argv(st["argv"])
            label = j.get("label") or ""
            _progress(f"  {j['index']:02d} {label:5s} {wav_seconds(j['out']):.2f}s", flush=True)

    _pool(jobs, parallel, _one, "음성", stop_on_error=True)

# ── 조교 채널 계측 (volcano_ref) — 손 ───────────────────────────────────────
#   tikitaka/shorts_analysis/grb/s1_probe.py + m_fps.py 이관 (2026-09-03).
#   ★이 갈래에는 채널 값·문턱이 0개이고 **ffprobe·ffmpeg 명령도 없다** — argv 까지 전부
#     서버 params 다(경계 검사 «실행기가 ffmpeg 명령을 짓지 않는다» · `measure_frame` 선례).
#     실행기는 `@@IN@@`·`@@OUT@@` 자리만 바꿔 넣는다. tests/test_ref.py [6] 이 AST 로 센다.
#     판정(해상도 경고·분포)은 서버 volcano_ref_steps.

def _fill(argv, **slots):
    """argv 템플릿의 `@@이름@@` 자리를 채운다. 서버가 지은 명령을 **그대로** 돌리기 위한 것."""
    out = []
    for a in argv:
        for k, v in slots.items():
            a = a.replace("@@" + k + "@@", v)
        out.append(a)
    return out


def ref_probe(item):
    """영상 묶음의 ffprobe 전수 + 오디오 추출 — 지침서 S1/S3. **값만** 돌려준다.

    item = {ids, src_dir, out_dir, probe_argv, audio:{이름:{suffix, argv}}, round, ext}
        probe_argv   `@@IN@@` 자리가 있는 ffprobe 템플릿 — 서버가 준다
        audio.*.argv `@@IN@@`·`@@OUT@@` 자리가 있는 ffmpeg 템플릿 — 서버가 준다
    돌려주는 것 {유튜브id: {w,h,fps,dur,vcodec,acodec,ach,asr,nb_frames,bitrate,
                          fps_num,fps_den,r_frame_rate,avg_frame_rate}}
    ★칸 이름·자릿수는 보존 `grb/probe.json` 과 같다(s1_probe 10칸 + m_fps 4칸) — 검사가 값 대조한다.
    ★한 번의 `-show_streams` 에 `r_frame_rate`·`avg_frame_rate` 가 같이 온다 —
      m_fps.py 처럼 두 번 부르지 않는다. 소수에서 분수를 되짚지 않는다(m_fps 머리말).
    """
    ids = [str(x) for x in item["ids"]]
    src_dir, out_dir = item["src_dir"], item.get("out_dir")
    rnd = int(item["round"])
    ext = item["ext"]
    probe_argv = item["probe_argv"]
    audio = item.get("audio") or {}
    if out_dir and audio:
        os.makedirs(out_dir, exist_ok=True)
    out = {}
    for vid in ids:
        mp4 = os.path.join(src_dir, vid + ext)
        if not os.path.exists(mp4):
            raise StepError(f"영상이 없다: {mp4}")
        r = _spawn(_fill(probe_argv, IN=mp4), capture_output=True, text=True)
        try:
            p = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            # ★자르지 않는다 — 손 팩에는 숫자를 두지 않는다(-v quiet 라 stderr 는 짧다)
            raise StepError(f"ffprobe 출력을 못 읽었다: {mp4}\n  {r.stderr.strip()}")
        v = next((s for s in p.get("streams") or [] if s.get("codec_type") == "video"), None)
        if v is None:
            raise StepError(f"영상 스트림이 없다: {mp4}")
        a = next((s for s in p.get("streams") or [] if s.get("codec_type") == "audio"), {})
        fr = v.get("avg_frame_rate") or "0/1"
        num, den = fr.split("/")
        fps = float(num) / float(den) if float(den) else 0
        rec = dict(w=v["width"], h=v["height"], fps=round(fps, rnd),
                   dur=round(float(p["format"]["duration"]), rnd),
                   vcodec=v["codec_name"], acodec=a.get("codec_name"),
                   ach=a.get("channels"), asr=a.get("sample_rate"),
                   nb_frames=v.get("nb_frames"), bitrate=p["format"].get("bit_rate"))
        rr = v.get("r_frame_rate")
        if rr and "/" in rr:
            n2, d2 = (int(x) for x in rr.split("/"))
            rec["fps_num"], rec["fps_den"] = n2, d2
            rec["r_frame_rate"], rec["avg_frame_rate"] = rr, v.get("avg_frame_rate")
        for spec in audio.values():
            dst = os.path.join(out_dir, vid + spec["suffix"])
            if not os.path.isfile(dst):
                _spawn(_fill(spec["argv"], IN=mp4, OUT=dst), check=True)
        out[vid] = rec
    return out


def probe_custom_media(item):
    """Read source/derivative identities without changing any asset or receipt."""
    results = {}
    for job in item.get('jobs') or []:
        row = {'source': job['source'], 'path': job['path']}
        for pathkey, hashkey in (('source', 'source_sha256'), ('path', 'sha256')):
            try:
                digest = hashlib.sha256()
                with open(job[pathkey], 'rb') as fh:
                    for chunk in iter(lambda: fh.read(1024*1024), b''):
                        digest.update(chunk)
                row[hashkey] = digest.hexdigest()
            except OSError as exc:
                row[hashkey] = None
                row[pathkey+'_error'] = type(exc).__name__
        results[job['key']] = row
    return {'key': item['key'], 'results': results}


def _custom_media_frame(source):
    """PIL 이 정지 그림으로 못 여는 원본(영상·움직이는 그림·HEIC/AVIF 등) → ffmpeg 이 뽑은 **한 장면** PNG 바이트 (2026-10-21).

    ★왜: 군림보 회원이 그림 칸(customization.images)에 .mp4 영상을 넣었다(진단 5건·4명). 서버는 파일을 못 보니 확장자로
      반려했고, 회원은 같은 요청을 되풀이했다. 그림 칸은 정지 그림 자리다 — 영상이면 ffmpeg `thumbnail` 필터(앞 100프레임 가운데
      가장 대표적인 장면 · 첫 프레임이 검은 화면인 영상을 피한다 · 공식 https://ffmpeg.org/ffmpeg-filters.html#thumbnail)로 한 장을
      골라 같은 변환에 넣는다. 결정적이라 verify 가 같은 바이트로 다시 만든다(ffmpeg 판이 바뀌면 verify 가 그렇다고 말한다).
    ★읽을 수 없으면 ffmpeg 의 말을 그대로 붙여 멈춘다(어느 칸·어느 파일인지는 부르는 쪽이 붙인다)."""
    done = _spawn(['ffmpeg', '-nostdin', '-v', 'error', '-i', source, '-map', '0:v:0', '-vf', 'thumbnail',
                   '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'],
                  stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    if done.returncode or not done.stdout:
        err = (done.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        raise ValueError('그림으로도 영상으로도 읽을 수 없습니다'
                         + (' — ffmpeg: ' + err[-1][:300] if err else f' (ffmpeg 종료 코드 {done.returncode})'))
    return done.stdout


def _custom_media_png(blob, slot, source=None):
    """사용자 원본 바이트 → 렌더 자산 PNG 바이트 (prepare·verify 의 복원이 **같은 자**로 만든다 · 결정적 변환).

    ★정지 그림은 PIL 로, PIL 이 못 열거나 여러 장면인 원본(영상·움직이는 GIF/WebP·HEIC 등)은 `_custom_media_frame` 이 원본
      파일(`source` · 부르는 쪽이 이 바이트와 같은지 해시로 확인한다)에서 한 장면을 뽑아 같은 길로 넣는다 (2026-10-21).
    돌려주는 값: (PNG 바이트, 원본 폭, 원본 높이, 결과 폭, 결과 높이)."""
    import io
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        decoded = Image.open(io.BytesIO(blob))
        still = getattr(decoded, 'n_frames', 1) == 1
    except UnidentifiedImageError:
        decoded, still = None, False
    if not still:
        if decoded is not None:
            decoded.close()
        if source is None:
            raise ValueError('정지 그림이 아닌 원본은 원본 파일 경로가 있어야 장면을 뽑습니다')
        decoded = Image.open(io.BytesIO(_custom_media_frame(source)))
    with decoded:
        decoded.load()
        im = ImageOps.exif_transpose(decoded).convert('RGBA')
    source_w, source_h = im.size
    # Keep all original pixels available for the measured subject crop.
    # Scaling is uniform; the renderer applies the actual slot crop later.
    if slot:
        ratio = max(int(slot[0])/im.width, int(slot[1])/im.height)
        im = im.resize((max(1, round(im.width*ratio)), max(1, round(im.height*ratio))), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', im.size, (255,255,255,255))
    canvas.alpha_composite(im)
    im = canvas.convert('RGB')
    encoded = io.BytesIO(); im.save(encoded, format='PNG')
    return encoded.getvalue(), source_w, source_h, im.width, im.height


def _custom_media_write(out, result, what='파생 자산을', note=''):
    """파생 자산을 원자적으로 쓴다(같은 바이트면 쓰지 않는다) — 쓰기는 작업 파일 쓰기 한 자리(_publish_work_file)."""
    old = None
    if os.path.isfile(out):
        with open(out, 'rb') as fh:
            old = fh.read()
    if old != result:
        _publish_work_file(out, data=result, what=what, note=note)


def prepare_custom_media(item):
    """Decode user originals into separate atomic assets and record actual identities."""
    from PIL import Image
    receipts = dict(item.get('receipts') or {})
    for job in item.get('jobs') or []:
        source, out = job['source'], job['path']
        try:
            if os.path.abspath(source) == os.path.abspath(out) or (os.path.exists(out) and os.path.samefile(source, out)):
                raise StepError('사용자 원본과 파생 파일 경로가 같습니다. 별도 원본을 지정하세요.')
            with open(source, 'rb') as fh:
                blob = fh.read()
            source_hash = hashlib.sha256(blob).hexdigest()
            slot = job.get('slot')
            result, source_w, source_h, width, height = _custom_media_png(blob, slot, source)
            with open(source, 'rb') as fh:
                if hashlib.sha256(fh.read()).hexdigest() != source_hash:
                    raise StepError('변환 중 사용자 원본이 바뀌었습니다. images/memes 단계를 다시 실행하세요.')
        except StepError:
            raise
        except (OSError, ValueError, Image.DecompressionBombError, subprocess.TimeoutExpired) as exc:
            raise StepError(f"사용자 소재 {job['key']} 파일을 열거나 변환할 수 없습니다: {source} ({type(exc).__name__}). 경로와 그 파일이 그림이나 영상인지 확인하세요 — {exc}") from exc
        # ★읽기·변환이 끝난 뒤의 쓰기 실패는 원본 탓이 아니다 — 작업 폴더의 파생 파일(img43/NN.png)을 다른 프로그램이 쥐고 있다
        #   (2026-10-21 뇌전구 신고: 윈도우 OneDrive 폴더에서 WinError 5 · 09-19~10-21 같은 자리 8건·6명). 예전에는 이 실패도 위
        #   «원본이 그림이나 영상인지 확인하세요» 로 나가 회원이 멀쩡한 원본을 고치러 갔다 → 실패한 자리와 할 일을 그대로 말한다.
        _custom_media_write(out, result, what=f"사용자 소재 {job['key']} 를",
                            note=f"원본({source})은 문제가 없습니다 — ")
        receipts[job['key']] = dict(source=source, source_sha256=source_hash,
            path=out, sha256=hashlib.sha256(result).hexdigest(), slot=slot,
            source_w=source_w, source_h=source_h, w=width, h=height)
    return receipts


class CustomMediaChanged(StepError):
    """사용자 원본 그림이 영수증 뒤에 바뀌었다 — 구동기(volcano_drive._drive_loop)가 그 칸을 같은 path 로 customize 에 다시
    보내 서버가 측정·피사체 근거를 다시 만들게 한다(2026-10-17 실행기 중단 보고 16건·9명 · 예전에는 사람이 patch 를 손으로 보냈다)."""

    def __init__(self, message, source):
        super().__init__(message)
        self.source = source


def verify_custom_media(item):
    """Recheck both original and derivative before any paid or render commands.

    ★원본(source)은 회원의 것이고 파생(path · img43/NN.png 등)은 **우리가 원본에서 만든 것**이다 (2026-10-15).
      예전에는 둘 중 무엇이 바뀌어도 «사용자 소재 파일이 변경되어…» 로 멈췄다 — 진단 원문은 그 상당수가 파생 파일
      (예: 렌더 계획의 «제거 대상 글자» 안내를 보고 img43/02.png 를 직접 고친 판)이었고, 회원 원본은 그대로였다.
      원본이 영수증 그대로면 파생은 같은 변환(`_custom_media_png` · 결정적)으로 **다시 만들어** 영수증 바이트와 같은지 보고
      되돌린다. 같은 바이트를 못 만들면(그림 부품 판이 바뀐 경우 등) 무엇이 바뀌었는지 말하고 멈춘다.
      원본이 바뀌었거나 없으면 예전처럼 멈춘다 — 그때는 측정·피사체 근거를 다시 만들어야 한다.
    """
    for rec in item.get('receipts') or []:
        source, out = rec['source'], rec['path']
        try:
            with open(source, 'rb') as fh:
                blob = fh.read()
        except OSError as exc:
            # ★무엇을 하라는지 말한다(2026-10-20 뇌전구 신고 6건 — 경로만 있어 같은 명령을 40초에 7번 되풀이했다). 원본은 회원이
            #   customization 으로 지정한 파일이다(플로우에서 받은 flow_downloads 파일을 지정한 경우 포함) — 우리가 대신 고르지 않는다.
            raise StepError(f"사용자 소재 원본 파일을 찾거나 읽을 수 없습니다: {source} ({type(exc).__name__} · 이 원본으로 만든 렌더 칸: {out}). "
                            "같은 명령을 다시 실행해도 같은 정지입니다. 셋 중 하나를 하세요: ① 그 파일을 그 경로에 되돌려 놓고 같은 명령을 실행 · "
                            "② customize 단계의 customization_patch 로 그 칸(images/memes)의 path 를 지금 있는 그림 파일로 바꿔 보내기"
                            "(그 칸의 변환·측정·검수를 새로 합니다) · ③ 그 칸을 본인 그림으로 쓰지 않으려면 customization_patch 의 그 칸에 "
                            "null 을 넣어 지정을 풀기(그 칸은 images 단계가 만듭니다).") from exc
        if hashlib.sha256(blob).hexdigest() != rec['source_sha256']:
            raise CustomMediaChanged('사용자 소재 원본 파일이 변경되어 기존 측정·피사체·렌더 근거를 사용할 수 없습니다. '
                'customize 단계의 customization_patch에 해당 images/memes 항목의 같은 path를 다시 보내 '
                '로컬 확인 후 바뀐 소재의 변환·검수를 이어가세요: ' + source, source)
        try:
            with open(out, 'rb') as fh:
                current = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            current = None
        if current == rec['sha256']:
            continue
        rebuilt = _custom_media_png(blob, rec.get('slot'), source)[0]
        if hashlib.sha256(rebuilt).hexdigest() != rec['sha256']:
            raise StepError('렌더용 파생 파일이 ' + ('없고' if current is None else '바뀌었고') + ' 원본에서 같은 바이트로 다시 만들 수 '
                '없습니다(그림 변환 부품 판이 달라졌을 수 있습니다). 원본은 그대로입니다 — custom_media_receipts 에서 이 칸('
                + out + ')을 지우고 같은 단계를 다시 실행하면 원본에서 새로 만듭니다. 그림을 바꾸려면 파생 파일을 고치지 말고 '
                '새 파일을 customization.images 의 그 칸 path 로 지정하세요.')
        _custom_media_write(out, rebuilt)
        _progress('  [사용자 소재] 렌더용 파생 파일이 ' + ('없어' if current is None else '원본과 달라져')
                  + ' 원본에서 다시 만들었습니다(원본은 그대로): ' + out
                  + ' — 그림을 바꾸려면 파생 파일 대신 customization.images 의 그 칸 path 에 새 파일을 지정하세요.', flush=True)
    return True
