"""피사체 AGY 판독의 제품 배선 — AGY 전송 · 격리 작업 폴더 · 진행/재개 · 거부 처리 · 옛 영수증 이어 쓰기.

■ 무엇을 하나
    산수·질문·영수증 모양은 subject_agy(순수 모듈)가 한다. 이 파일은 그것을 «실제로 돌리는» 자리다:
      컷마다  ① ffmpeg 한 번으로 작은 사본(+장면 전환 점수)  ② AGY 가 그 사본을 view_file 로 읽는다(컷마다 AGY 호출 1번)
              ③ 답을 산수로 크롭 영역으로 옮긴다  ④ 뒤 단계가 읽는 영수증을 쓴다.
      (v4 · 사장님 결정 2026-10-06 밤 «medium 한 번만»: v3 의 크롭 재확인 — 자른 사본을 AGY 가 다시 보고 잘렸으면 넓혀 다시 — 은 없다.)
    로컬 추론(얼굴·글자 검출·광류)은 없다. cv2·onnxruntime·numpy·PIL 을 import 하지 않는다(tests/test_subject_agy_run.py).

■ 실측으로 정한 것 (docs/2026-10-05_피사체-AGY-판독/README.md)
    · 사본을 **임시 작업 폴더**로 옮겨 그 폴더를 cwd 로 AGY 를 부른다. 수강생 작업 폴더의 상위에 CLAUDE.md·AGENTS.md 가
      있으면 AGY 가 영상을 본 뒤 그 파일을 열려다 자동 거부당하고 답이 빈다(저장소 아래 자리 40건 중 9건).
      상위에 규칙 파일이 없는 폴더에서는 35건 중 0건이었고, 작업 폴더 안 읽기는 설정 파일을 고치지 않아도 허용됐다.
    · 질문 첫머리에 «이 파일 하나만 봐라 · 다른 파일은 열지 마라» 를 둔다(저장소 아래 자리에서도 12건 중 0건).
    · AGY 는 기존 전송 한 자리(agy_transport_client.invoke)로만 부른다 — 기계 전체 16칸 · 거부 표식 · 최소 환경.
      거부(한도·로그인·속도 제한·도구 거부)는 그 전송이 RunServiceRefused 로 올리고 거부 표식을 남긴다 — 그 순간부터 이 실행의 AGY
      요청은 0 이다(전역 규칙 6-2 · 다른 컷도 곧바로 멈춤). ★사장님 결정(2026-10-06 16:4x «멈추면 안된다니까»): 거절 종류가
      한도·속도·로그인(GATE_REFUSAL_CODES)이면 작업은 멈추지 않는다 — 남은 컷(묻던 중 거부된 컷 · 아직 안 물은 컷 · 시작할 때 이미
      거부 표식이 걸린 실행의 컷 · 관문의 한도·로그인)은 그 컷만 확대 없는 전체 화면(cause agy_refused · 거부 종류 refused_as 를
      사실로)으로 끝내고 complete 로 제작에 간다. 그 밖의 거절(도구 거부 · 모델 이름 등 «이 PC 의 AGY 설정을 고칠 것» · 종류를
      모르는 거부 표식)은 예전처럼 막는다(provider_refused · not_started/not_continued_after_refusal + 거절 종류 · 검토 10-06 ①).
      거부 종류는 전송이 표식을 남길 때 이 프로세스에 적어 두므로(agy_transport_refusal.refusal_kind) 시작할 때 걸린 표식도 가른다.
    · status ERROR 는 사장님 결정(2026-10-05 5-1)대로 «그 컷만 실패, 나머지 계속» — 전송을 status_error='per_request_evidence' 로
      불러 한도·속도·로그인의 «증거»(오류 글의 낱말 · /usage 가 소진·로그인 풀림이라고 함)가 있을 때만 거부(전부 멈춤 · 거부 표식)이고,
      증거가 없으면(/usage 를 확인 못 한 것 포함 · 10-06) 그 컷의 실패다. 다른 엔진은 기본값('refuse')·검수 다리는 'per_request' 그대로.
    · ★한 컷의 실패 가운데 사람이 고칠 것이 없는 것(subject_agy.CUT_FAILURE_TEXT — status ERROR · 답 없이 끝난 호출 · 증명 실패 ·
      답 형식 · 주인공 못 정함 · 작은 사본/그 사본의 ffprobe 실패 · 영수증 검사 실패)은 그 컷을 확대하지 않는 전체 화면 영수증(«까닭_full_frame» ·
      자동 재시도 없음)으로 끝내고 작업은 complete 로 다음 단계(제작)로 간다(10-06 · 결정 5-1 을 넓힘). 그 컷의 알림은 diagnostics 에
      fallback 으로 남는다. 막는 것은 사람이 고칠 수 있거나 컷 탓이 아닌 것뿐이다 — 관문의 설치·시험 영상 실패 ·
      이 PC 의 AGY 설치·호출 모양·모델·네트워크(agy_environment) · ffmpeg/ffprobe 실행 불가 · 디스크 가득 참 ·
      원본 파일(원본 크기 ffprobe 실패 = source_probe_failed · 10-07 · 원본마다 한 번 잰다) · 실행기 규격.

■ 숫자
    동시 수·제한 시간·모델은 서버(item['agy'])가 준다. 답을 바꾸는 숫자(표본 간격·장수·사본 높이·장면 문턱·재확인 횟수 0)는
    알고리즘 이름(subject_agy.ALGORITHM)이 묶는다 — 서버가 다른 값을 보내면 고쳐 쓰지 않고 멈춘다(check_policy).
■ 옛 판 영수증
    서버가 prior_keys 로 알려 준 옛 AGY 판(v3 = high + 크롭 재확인)의 끝난 영수증은 그대로 쓴다 — AGY 에 다시 묻지 않는다
    (prepare_agy_focus · 서버 agy_focus.PRIOR_POLICIES 의 까닭).
■ 돈·시간 전 관문
    잴 컷이 하나라도 있으면 사본을 만들기 전에 agy_gate(설치·로그인·한도 + 2초 시험 영상 실제 판독). 계약당 한 번 기록.
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = 1
# 사람이 «고쳐서 다시»(서버 focus_retry)를 누른 컷 가운데, 막힌 까닭이 «저장된 AGY 답 자체» 인 것 — 같은 답을 다시 읽으면
# 같은 막힘이 난다(옛 구조 M11: selection_invalid 컷이 재전송해도 같은 답만 돌아옴). 그 컷의 저장된 답은 지우지 않고
# retry-<n>/ 으로 옮겨 두고 AGY 에 새로 묻는다. 그 밖의 까닭(장면 전환·사본 실패·AGY 오류·거부 뒤 멈춤)은 저장된 답이 없거나
# 답과 무관하므로 옮기지 않는다(멀쩡한 첫 판독을 다시 묻지 않는다).
# 10-06 부터 이 까닭들은 막지 않고 그 컷만 전체 화면으로 끝난다(CUT_FAILURE_TEXT) — 이 목록은 옛 실행기가 남긴 막힌 결과에서
# 사람이 «다시» 를 누른 컷에 쓰인다(그때는 저장된 답을 옮겨 두고 새로 묻는다 · 사람이 고른 다시 묻기라 자동 재시도가 아니다).
ANSWER_DERIVED = ('subject_not_determined', 'agy_answer_invalid', 'selection_invalid')
POLICY_KEYS = ('algorithm', 'model', 'timeout_s', 'parallel', 'step', 'cap', 'height',
               'scene_threshold', 'max_checks', 'guard')
# 답을 바꾸는 설정만 영수증 열쇠에 넣는다. 동시 수·제한 시간은 답을 바꾸지 않는다.
SEMANTIC_KEYS = ('algorithm', 'model', 'step', 'cap', 'height', 'scene_threshold', 'max_checks', 'guard')
SCENE_TAIL_SECONDS = .5     # 사본 입력에 붙이는 꼬리(장면 점수는 컷 안 프레임만 쓴다 — subject_agy.scene_scores)


class SubjectAgyError(RuntimeError):
    """한 컷의 판독을 끝내지 못한 사유(코드 + 사람 말). 실행 전체를 멈추는 «거부» 와 다르다."""
    def __init__(self, code, message, **detail):
        super().__init__(message)
        self.code, self.detail = code, detail


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8', 'surrogatepass')).hexdigest()


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _save(path, value):
    from longform_state import save
    save(path, value)


def _file_sha(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def check_policy(policy):
    """서버가 준 설정의 모양을 본다 — 값을 고치거나 채우지 않는다(없으면 멈춘다).

    답을 바꾸는 숫자(표본 간격·장수·사본 높이·장면 문턱·재확인 횟수 — v4 는 0)는 알고리즘 이름(subject_agy.ALGORITHM)이 묶는다.
    서버가 다른 숫자를 보내면 그 알고리즘이 아니다 → 고쳐 쓰지 않고 «실행기를 갱신하라» 로 멈춘다.
    """
    import subject_agy as S
    if not isinstance(policy, dict) or any(k not in policy for k in POLICY_KEYS):
        raise SubjectAgyError('agy_policy_invalid', 'AGY 피사체 판독 설정이 덜 왔습니다. 서버의 새 계획을 받으세요.')
    ok = (policy['algorithm'] == S.ALGORITHM
          and isinstance(policy['model'], str) and policy['model']
          and _number(policy['timeout_s']) and policy['timeout_s'] > 0
          and type(policy['parallel']) is int and policy['parallel'] >= 1
          and policy['step'] == S.STEP_SECONDS and policy['cap'] == S.MAX_PICTURES
          and policy['height'] == S.PROXY_HEIGHT and policy['scene_threshold'] == S.SCENE_THRESHOLD
          and policy['max_checks'] == S.MAX_CHECKS
          and isinstance(policy['guard'], str) and policy['guard'].strip())
    if not ok:
        raise SubjectAgyError('agy_policy_invalid', 'AGY 피사체 판독 설정이 이 실행기와 맞지 않습니다. 실행기를 갱신하거나 서버의 새 계획을 받으세요.')
    return policy


# ── ffmpeg: 작은 사본(그림 파일로 풀지 않는다) ─────────────────────────────────────
def _ffprobe_stream(argv, timeout, what, code='probe_failed', hint=''):
    """ffprobe 한 번 → 첫 영상 스트림. 실패·시간 초과·이상한 출력은 SubjectAgyError(code) 로 바꾼다 —
    한 컷의 ffprobe 문제가 ThreadPoolExecutor.map 밖으로 새어 다른 컷까지 멈추지 않게(검토 2026-10-05). 사유는 남긴다.

    code: 작은 사본(_frames_in)은 'probe_failed'(그 컷 탓 — CUT_FAILURE_TEXT · 그 컷만 전체 화면), 원본(source_size)은
    'source_probe_failed'(원본 파일 탓 — 막고 사람이 원본을 고친다 · 10-07). 두 실패가 같은 이름을 쓰던 동안 서버가 원본 실패에도
    «고칠 것 없음 · 다시» 를 안내해 학생이 다시 부르고 또 막히는 고리가 났다. failure_kind: timeout · exit · no_stream(사실 그대로).
    hint: 사람이 할 일 한 줄(원본 쪽만)."""
    try:
        raw = subprocess.check_output(argv, stderr=subprocess.PIPE, timeout=timeout)
        return json.loads(raw)['streams'][0]
    except subprocess.TimeoutExpired as error:
        raise SubjectAgyError(code, f'{what}: ffprobe 가 {timeout}초 안에 끝나지 않았습니다.' + hint,
                              failure_kind='timeout') from error
    except subprocess.CalledProcessError as error:
        said = (error.stderr or b'').decode('utf-8', 'replace')[-300:]
        raise SubjectAgyError(code, f'{what}: ffprobe 실패(종료 {error.returncode}) {said}' + hint, failure_kind='exit') from error
    except OSError as error:             # 이 PC 에서 ffprobe 를 띄우지 못함 — 컷 탓이 아니다(막는다 · 10-06)
        raise SubjectAgyError('ffmpeg_unavailable', f'{what}: ffprobe 를 실행하지 못했습니다: {type(error).__name__}: {error}') from error
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise SubjectAgyError(code, f'{what}: ffprobe 출력에 영상 스트림이 없습니다: {type(error).__name__}' + hint,
                              failure_kind='no_stream') from error


def _frames_in(path):
    stream = _ffprobe_stream(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                              '-show_entries', 'stream=nb_read_frames,width,height', '-of', 'json', str(path)], 300, '작은 사본 화면 수')
    try:
        return int(stream['nb_read_frames']), [int(stream['width']), int(stream['height'])]
    except (KeyError, TypeError, ValueError) as error:
        raise SubjectAgyError('probe_failed', f'작은 사본 화면 수: ffprobe 가 화면 수·크기를 주지 않았습니다: {type(error).__name__}',
                              failure_kind='no_stream') from error


# 원본 크기 탐침(source_size)이 실패하면 그 원본의 컷은 «확대 없는 전체 화면» 영수증조차 만들 수 없다(영수증에 원본 크기가 든다).
# 그래서 막는다(source_probe_failed) — 컷 탓이 아니라 원본 파일 탓이고, 같은 원본의 모든 컷에 같은 일이 난다.
# 실측(2026-10-07 이 맥 · 같은 argv): 정상 원본 0.5~1.4GB · moov 가 앞/끝 어느 쪽이든 0.02~0.08초 · 받다 만 파일·빈 파일·영상 아닌
# 파일은 0.04초 안에 종료 1(«moov atom not found» · «Invalid data»). 원본은 바로 앞에서 file_digest 로 끝까지 읽혔으므로 «없음» 이
# 아니다. 60초 시간 초과는 정상의 수백 배라 원본이 클라우드 동기화·네트워크 폴더에 있어 그때그때 받아 오거나, 다른 프로그램(백신 등)이
# 잡고 있거나, PC 가 매우 바쁜 경우다 — 같은 실행 안에서 곧바로 다시 재도 같은 까닭이 남아 있으므로 자동으로 다시 재지 않고 막아
# 사람이 확인한 뒤 «다시» 를 누른다(그때 이 탐침부터 다시 한다 · 끝난 컷은 다시 묻지 않는다).
SOURCE_PROBE_HINT = (' 원본 영상 파일이 끝까지 받아졌는지, 영상이 맞는지(손상·소리만 있는 파일이 아닌지) 확인하세요. '
                     '시간 초과면 원본이 클라우드 동기화·네트워크 폴더에 있거나 다른 프로그램이 잡고 있지 않은지 확인하세요.')


def source_size(path):
    stream = _ffprobe_stream(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                              'stream=width,height', '-of', 'json', str(path)], 60, '원본 크기', 'source_probe_failed',
                             SOURCE_PROBE_HINT)
    try:
        return [int(stream['width']), int(stream['height'])]
    except (KeyError, TypeError, ValueError) as error:
        raise SubjectAgyError('source_probe_failed', f'원본 크기: ffprobe 가 크기를 주지 않았습니다: {type(error).__name__}'
                              + SOURCE_PROBE_HINT, failure_kind='no_stream') from error


PROXY_TIMEOUT_S = 1800     # 사본 하나 만들기 상한(전과 같은 값) — 넘으면 그 컷만 proxy_timeout


def make_proxy(cut, out, vf, expected, warmup=0.):
    """컷 구간(+꼬리)을 subject_agy 가 지은 필터로 작은 사본 하나로. 그림 파일로 풀지 않는다. 돌려주는 값: 사실 dict.

    warmup: 장면 점수용으로 컷보다 그만큼 앞에서 디코드를 시작한다(필터가 그림 갈래에서는 잘라 낸다 · subject_agy.proxy_filter).
    """
    import subject_agy as S
    warmup = float(warmup)
    argv = S.proxy_argv('ffmpeg', str(cut['src']), str(out), vf,
                        input_options=['-ss', f"{float(cut['start']) - warmup:.6f}",
                                       '-t', f"{float(cut['duration']) + SCENE_TAIL_SECONDS + warmup:.6f}"])
    started = time.monotonic()
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=PROXY_TIMEOUT_S)
    except subprocess.TimeoutExpired as error:     # 그 컷만 실패 — 다른 컷은 계속(검토 2026-10-05)
        raise SubjectAgyError('proxy_timeout', f'컷의 작은 사본 만들기가 {PROXY_TIMEOUT_S}초 안에 끝나지 않았습니다.') from error
    except OSError as error:             # 이 PC 에서 ffmpeg 를 띄우지 못함 — 컷 탓이 아니다(막는다 · 10-06)
        raise SubjectAgyError('ffmpeg_unavailable', f'ffmpeg 를 실행하지 못했습니다: {type(error).__name__}: {error}') from error
    if done.returncode or not Path(out).is_file():
        if 'No space left on device' in (done.stderr or ''):
            # 디스크가 가득 참(ENOSPC 의 strerror 글) — 컷 탓이 아니라 이 PC 환경이다. 그 컷을 전체 화면으로 굳히면 비운 뒤에도 확대가
            # 영영 빠지므로 막는다(사람이 비우고 «다시» · 10-06).
            raise SubjectAgyError('disk_full', '작업 폴더 디스크가 가득 차 컷의 작은 사본을 쓰지 못했습니다: ' + (done.stderr or '')[-200:])
        raise SubjectAgyError('proxy_failed', '컷의 작은 사본을 만들지 못했습니다: ' + (done.stderr or '')[-300:])
    count, size = _frames_in(out)
    if count != expected:
        raise SubjectAgyError('proxy_frames_short',
            f'작은 사본의 화면 수가 다릅니다(요청 {expected} · 실제 {count}). 원본 구간이 영상 끝을 넘는지 확인하세요.')
    return {'sha256': _file_sha(out), 'bytes': Path(out).stat().st_size, 'pictures': count, 'size': size,
            'seconds': round(time.monotonic() - started, 2), 'log': done.stderr}


# ── AGY 호출 (기존 전송 한 자리) ────────────────────────────────────────────────
def _viewed_exactly(result, paths):
    """모델의 말이 아니라 도구 기록으로 본다: 파일 읽기 도구로 «그 파일만» 실제로 열었는가.

    판정은 전송 한 자리(agy_transport_client.opened_exactly — agy 1.4.2 view_file · 1.4.3 read_file 을 같은 표로 읽는다).
    인정 = 그 파일(들)을 **성공적으로** 연 기록이 있고, 그 밖의 도구가 **성공한** 기록이 없다. 실패·거부된 시도는 세지 않는다(10-06 —
    권한 거부된 시도 하나로 멀쩡한 답을 버렸다 · 학생 실측 agy_view_unproven 12명). 10-20 agy 1.4.3 자동 갱신 뒤에는 이 자리가
    view_file 이름만 알아 정상 답을 전부 agy_view_unproven 으로 버렸다(인물형 롱폼·인스타형 신고).
    """
    import agy_transport_client as AGY
    why, _used = AGY.opened_exactly(result.get('tools'), paths)
    return why is None


def _environment_failure(result):
    """이 PC 의 AGY 설치·호출 모양·모델·네트워크 문제인가 — 그렇다면 컷마다 같은 실패가 되풀이되고 사람이 고칠 수 있으므로 막는다
    (전체 화면으로 굳히면 고친 뒤에도 그 영수증이 남아 확대가 영영 빠진다). 새 목록을 짓지 않는다: 기존 코드 표(agy_transport_codes)의
    «advice: fix_env» 코드 + 전송이 가른 DNS 실패(failure_kind 'dns_lookup' · 네트워크). 그 밖의 «답 없이 끝난 호출»(시간 초과·빈 답·
    결과 사건 없음 등)은 그 요청 하나의 실패다."""
    import agy_transport_client as AGY
    if result.get('failure_kind') in ('dns_lookup', 'network'):   # network: DNS 밖 Go 네트워크 오류(전송이 가른다 · 10-06 검토 major)
        return True
    row = ((AGY.table().get('codes') or {}).get(result.get('code')) or {})
    return row.get('advice') == 'fix_env'


def _json_answer(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', str(text or '').strip())
    try:
        return json.loads(text)
    except ValueError:
        return None


def ask(question, clip, policy, env, purpose):
    """작은 사본 하나를 AGY 에게 보여 주고 JSON 답을 받는다. question(사본 경로) → 질문 글.

    돌려주는 값: (답 dict, 사실 dict). 거부는 전송이 RunServiceRefused 로 올린다 — 여기서 삼키지 않는다.
    """
    import agy_transport_client as AGY
    workspace = Path(tempfile.mkdtemp(prefix='volcano-agy-'))
    try:
        local = workspace/Path(clip).name
        shutil.copyfile(clip, local)
        prompt = policy['guard'].strip() + '\n' + question(str(local))
        started = time.monotonic()
        # status_error='per_request_evidence'(10-06): 한도·속도·로그인의 증거가 있을 때만 거부(전부 멈춤 · 거부 표식) — /usage 를
        # 확인하지 못한 오류(학생 실측: 길어서 잘린 답)는 그 요청 하나의 실패로 돌아온다(agy_transport_client._status_error_refusal).
        result = AGY.invoke(prompt, kind=None, files=[str(local)], model=policy['model'],
                            timeout_s=policy['timeout_s'], cwd=str(workspace), env=env, tries=1,
                            owner={'purpose': purpose}, status_error='per_request_evidence')
        facts = {'code': result.get('code'), 'seconds': round(time.monotonic() - started, 2),
                 'usage': result.get('usage'), 'model': result.get('model'), 'waited_slot_s': result.get('waitedSlotS'),
                 'question_sha256': hashlib.sha256(question('{path}').encode('utf-8')).hexdigest()}
        if result.get('failure_kind') == 'status_error':
            facts['usage_after_error'] = result.get('usage_after_error')
            known = (result.get('usage_after_error') or {}).get('known')
            raise SubjectAgyError('agy_status_error', 'AGY 가 이 컷 판독을 오류(status ERROR)로 끝냈습니다 — '
                                  + ('한도·로그인은 남아 있어' if known else '한도·속도·로그인 거부라는 증거가 없어')
                                  + ' 이 컷만 실패로 두고 다른 컷은 계속합니다(자동으로 다시 묻지 않음): '
                                  + str(result.get('error') or result.get('message') or '')[:160], facts=facts)
        if not result.get('ok'):
            code = 'agy_environment' if _environment_failure(result) else 'agy_call_failed'
            said = result.get('error') if isinstance(result.get('error'), str) and result.get('error') else result.get('message')
            raise SubjectAgyError(code, 'AGY 판독이 끝나지 않았습니다(' + str(result.get('code')) + '): ' + str(said or '')[:200],
                                  facts=facts, agy_code=result.get('code'),
                                  **({'failure_kind': result['failure_kind']} if result.get('failure_kind') else {}))
        if not _viewed_exactly(result, [str(local)]):
            raise SubjectAgyError('agy_view_unproven', 'AGY 가 이 영상만 직접 열었다는 도구 기록이 없습니다. 그 답은 쓰지 않습니다.', facts=facts)
        answer = _json_answer(result.get('text'))
        if not isinstance(answer, dict):
            raise SubjectAgyError('agy_answer_invalid', 'AGY 답이 JSON 객체가 아닙니다.', facts=facts)
        facts['answer_sha256'] = _hash(answer)
        return answer, facts
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


# ── 컷 하나 ──────────────────────────────────────────────────────────────────
def _pictures(vf):
    """필터가 고른 프레임 수(select 의 eq(n,…) 개수) — 사본 화면 수 대조용."""
    return len(re.findall(r'eq\(n,\d+\)', vf.split("select='", 2)[-1].split("'", 1)[0]))


def measure_cut(cut, policy, folder, source_sha, env, tally, halt=None, on_refused=None, size_of=None):
    """subject_agy.run_cut 을 실제 ffmpeg·AGY 로 돌린다. 단계마다 파일로 남겨, 끊겨도 같은 사본·같은 질문은 다시 만들거나 묻지 않는다.

    folder/<단계>.mp4 + <단계>.proxy.json(필터 지문·사본 sha·ffmpeg 로그) · <단계>.answer.json(질문 지문·사본 sha·답·사실).
    halt(): 참(첫 거부의 사실 dict)이면 새 AGY 요청을 보내지 않는다(같은 실행의 다른 컷이 거부를 받았다 — 전송의 거부 표식에만
    기대지 않는다). on_refused(사실): 이 컷이 거부를 받은 순간 부른다(다른 컷을 멈추게). 거부 뒤 이 컷은 막지 않고 전체 화면이다
    (사장님 결정 10-06 16:4x «멈추면 안된다» · 그 뒤 AGY 요청 0 — 전역 규칙 6-2).
    size_of(원본 경로): 원본 크기(prepare_agy_focus 가 원본마다 한 번만 재 둔 것 · 실패도 그대로 다시 낸다). 없으면 여기서 잰다.
    """
    import subject_agy as S
    import agy_transport_refusal as refusal
    def count(name, amount=1):
        tally[name] = tally.get(name, 0) + amount
    folder.mkdir(parents=True, exist_ok=True)
    fps = float(cut['fps'])
    nframes = max(1, round(float(cut['duration']) * fps))
    from longform_state import native_path
    size = (size_of or source_size)(native_path(cut['src']))      # 실패면 source_probe_failed — 막는다(AGY 를 부르기 전)
    proxies = {}

    asked = {'at': 'reading'}       # 마지막으로 다룬 판독 이름 — 답 모양 오류(ValueError)가 어느 판독에서 났는지 적는다

    def proxy(name, vf, warmup=0.):
        out, facts_path = folder/(name + '.mp4'), folder/(name + '.proxy.json')
        bound = _hash({'vf': vf, 'source': source_sha, 'start': cut['start'], 'duration': cut['duration'], 'warmup': warmup})
        saved = _read(facts_path) if facts_path.is_file() and out.is_file() else None
        if not (isinstance(saved, dict) and saved.get('bound') == bound and saved.get('sha256') == _file_sha(out)):
            try:
                made = make_proxy(cut, out, vf, _pictures(vf), warmup)
            except SubjectAgyError as error:
                error.detail.setdefault('at', name)     # 어느 사본에서 났는지 — 전체 화면 영수증이 적는다
                raise
            count('proxy_seconds', made['seconds']); count('proxies')
            saved = dict(made, bound=bound)
            _save(facts_path, saved)
        proxies[str(out)] = saved['sha256']
        return str(out), saved['log']

    def reader(name, question, path):
        asked['at'] = name
        answer_path = folder/(name + '.answer.json')
        template = question.replace(path, '{path}')
        # 묶음(bound)은 질문 본문만 — 답 길이 한 줄(S.ANSWER_BREVITY)은 답의 칸·뜻을 바꾸지 않아 넣지 않는다(넣으면 진행 중 작업이
        # 이미 받은 답을 버리고 다시 묻는다 · 6-2). 보내는 글에는 붙인다(사실 question_sha256 은 보낸 글 그대로를 잰다).
        bound = _hash({'question': template, 'proxy': proxies[path], 'model': policy['model']})
        saved = _read(answer_path) if answer_path.is_file() else None
        if isinstance(saved, dict) and saved.get('bound') == bound and isinstance(saved.get('answer'), dict):
            count('agy_reused')
            return saved['answer']
        first = halt() if halt is not None else None
        if first:
            first = first if isinstance(first, dict) else {}
            raise SubjectAgyError('not_continued_after_refusal',
                                  '같은 실행의 다른 컷에서 AGY 가 거부해 이 컷은 새 요청을 보내지 않았습니다(자동 재시도 없음). 받은 답은 남아 있습니다.',
                                  at=name, refusal=first, refused_as=first.get('refused_as'), refusal_seen='other_cut')
        try:
            answer, facts = ask(lambda local: template.replace('{path}', local) + S.ANSWER_BREVITY, path, policy, env,
                                'volcano-subject-' + name)
        except SubjectAgyError as error:
            error.detail.setdefault('at', name)     # 어느 판독에서 났는지 — 전체 화면 영수증이 적는다
            raise
        count('agy_calls'); count('agy_seconds', facts['seconds'])
        _save(answer_path, {'bound': bound, 'answer': answer, 'facts': facts})
        return answer

    try:
        receipt, report = S.run_cut(cut, source_sha, size, nframes, _recipe(cut, policy, source_sha),
                                    make_proxy=proxy, ask=reader, grid=f'fps={fps:g}', origin=0.)
    except S.Unresolved as error:
        detail = {k: v for k, v in error.detail.items() if k in ('frames', 'seconds')}
        if error.code in S.CUT_FAILURE_TEXT:         # 주인공 못 정함 — 그 컷만 전체 화면(10-06)
            return cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally,
                                       error.code, error.reason, asked['at'])
        raise SubjectAgyError(error.code, error.reason, **detail) from error
    except refusal.RunServiceRefused as error:
        # 거부(전송이 거부 표식을 남겼다 · 이 실행의 AGY 요청은 이제 0 — 6-2). 다른 컷을 곧바로 멈추게 알린다(on_refused · 종류와 무관).
        seen = refusal_facts(error, 'request', env)
        if on_refused is not None:
            on_refused(seen)
        if not refusal_continues(seen.get('refused_as')):
            # 한도·속도·로그인이 아닌 거절(도구 거부·모델 이름 등 «이 PC 의 AGY 설정을 고칠 것» · 종류 모름) — 예전처럼 막는다(검토 10-06 ①).
            raise SubjectAgyError('provider_refused', 'AGY 가 요청을 거절했습니다(' + str(seen.get('refused_as') or '종류 모름') + '): '
                                  + seen['reason'], provider_code=seen.get('refused_as'), refused_as=seen.get('refused_as'),
                                  refusal_seen='request', at=asked['at']) from error
        # 한도·속도·로그인 — 사장님 결정(10-06 16:4x «멈추면 안된다»): 막지 않고 이 컷은 받은 데까지로 확대 없이 전체 화면.
        return cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally, 'agy_refused',
                                   'AGY 거절(' + str(seen.get('refused_as')) + '): ' + seen['reason'], asked['at'], facts=seen)
    except ValueError as error:          # 답 모양이 규격과 다름 — 그 컷만 전체 화면(10-06)
        return cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally,
                                   'agy_answer_invalid', 'AGY 답이 규격과 다릅니다: ' + str(error), asked['at'])
    except SubjectAgyError as error:
        if error.code == 'not_continued_after_refusal':
            # 같은 실행의 다른 컷이 거부를 받아 이 컷은 다음 요청을 보내지 않았다 — 한도·속도·로그인이면 막지 않고 그 컷만 전체 화면
            # (10-06 16:4x) · 그 밖의 거절이면 예전처럼 막는다(검토 10-06 ① · 진단에 거절 종류).
            seen = {'refused_as': error.detail.get('refused_as'), 'refusal_seen': 'other_cut'}
            if not refusal_continues(seen['refused_as']):
                raise
            return cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally, 'agy_refused',
                                       str(error), str(error.detail.get('at') or asked['at']), facts=seen)
        if error.code not in S.CUT_FAILURE_TEXT:
            raise                        # 이 PC 환경(AGY 설치·네트워크·ffmpeg·디스크) — 막는다
        return cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally,
                                   error.code, str(error), str(error.detail.get('at') or asked['at']))
    selection = receipt['framing_subject']['selection_evidence']
    selection['agy'] = {'model': policy['model'], 'policy': {k: policy[k] for k in SEMANTIC_KEYS}}
    if receipt['framing_subject']['kind'] == 'scene':
        reason = '확대하지 않고 전체 화면을 지킨다(' + str(report['exception']) + ') — AGY 영상 판독: ' + report['who']
        for row in selection['decisions']:
            row['reason'] = reason[:400]
    tally['local_inference_frames'] = 0
    return receipt, report


def cut_failure_receipt(cut, policy, folder, source_sha, size, nframes, tally, code, message, at, facts=None):
    """사람이 고칠 것이 없는 한 컷의 실패(code ∈ subject_agy.CUT_FAILURE_TEXT) → 그 컷만 확대하지 않는 전체 화면 영수증 · 제작은 이어 간다.

    사장님 결정 5-1(«그 컷만 실패, 나머지 계속» · 10-05 status ERROR)을 10-06 에 이 실패들로 넓혔다. AGY 에 다시 묻지 않는다
    (전역 규칙 6-2) — 영수증이 남아 이어 할 때도 그대로 쓰인다(재사용 · 알림은 status_error_notice 가 계속 낸다). 첫 판독 답이
    이미 왔으면(판독 뒤 영수증 검사에서 난 실패 · at='validate') 그 주인공 상자로 16:9 아닌 원본의 창 자리만 정한다(확대는 안 한다).
    at='not_started'(거부 뒤 시작하지 않은 컷)은 이 실행에서 판독이 없었으므로 저장된 답을 읽지 않는다. facts: 실패의 사실(거부 종류 등).
    돌려주는 값: measure_cut 과 같은 (영수증, 보고).
    """
    import subject_agy as S
    at = str(at or 'reading')
    answer_path = folder/'reading.answer.json'
    saved = _read(answer_path) if at not in ('reading', 'not_started') and answer_path.is_file() else None
    reply = saved.get('answer') if isinstance(saved, dict) else None
    receipt = S.status_error_receipt(cut, source_sha, size, nframes, _recipe(cut, policy, source_sha), reply,
                                     message=str(message), at=at, code=code, facts=facts)
    receipt['framing_subject']['selection_evidence']['agy'] = {'model': policy['model'],
                                                               'policy': {k: policy[k] for k in SEMANTIC_KEYS}}
    tally['local_inference_frames'] = 0
    tally['cut_failure_full_frame'] = tally.get('cut_failure_full_frame', 0) + 1
    if code == 'agy_status_error':
        tally['status_error_full_frame'] = tally.get('status_error_full_frame', 0) + 1
    if code == 'agy_refused':
        tally['refused_full_frame'] = tally.get('refused_full_frame', 0) + 1
    exception = receipt['framing_subject']['selection_evidence']['exception']
    report = {'exception': exception, 'tier': 'scene', 'fit': 1.,
              'cut_failure': {'code': code, 'at': at, 'reason': str(message)[:300]}}
    if code == 'agy_status_error':
        report['status_error'] = {'at': at, 'reason': str(message)[:300]}
    return receipt, report


def _recipe(cut, policy, source_sha):
    return _hash({'cut': cut, 'policy': {k: policy[k] for k in SEMANTIC_KEYS}, 'source_identity': source_sha,
                  'version': VERSION})


def set_aside_answers(folder):
    """저장된 AGY 답(*.answer.json)을 folder/retry-<n>/ 로 옮긴다(지우지 않는다 — 막힌 까닭의 증거). 사본은 그대로 둔다."""
    folder = Path(folder)
    answers = sorted(folder.glob('*.answer.json')) if folder.is_dir() else []
    if not answers:
        return []
    number = 1 + sum(1 for p in folder.glob('retry-*') if p.is_dir())
    target = folder/f'retry-{number}'
    target.mkdir()
    for path in answers:
        os.replace(path, target/path.name)
    return [target/path.name for path in answers]


def status_error_notice(row):
    """한 컷의 실패로 확대 없이 전체 화면이 된 컷(cut_failure_receipt · 10-05 status ERROR 영수증 포함)이면 그 알림(진단 칸 한 줄),
    아니면 None. 막는 진단이 아니다(fallback) — 서버 consume 이 완료 결과에서도 그대로 받는다.
    code = 영수증 예외 이름의 뿌리(«까닭_full_frame» · status ERROR 는 agy_status_error_full_frame) · cause = 까닭."""
    import subject_agy as S
    selection = (((row or {}).get('framing_subject') or {}).get('selection_evidence') or {}) if isinstance(row, dict) else {}
    failure = selection.get('cut_failure')
    if isinstance(failure, dict) and failure.get('code') in S.CUT_FAILURE_TEXT:
        cause, said = failure['code'], failure
    elif str(selection.get('exception') or '').startswith(S.STATUS_ERROR_EXCEPTION):     # 10-05 판이 쓴 status ERROR 영수증
        cause, said = 'agy_status_error', selection.get('agy_status_error') or {}
    else:
        return None
    notice = {'code': S.failure_exception(cause), 'cause': cause, 'fallback': 'full_frame', 'exception': selection['exception'],
              'at': said.get('at'), 'reason': str(said.get('message') or '')[:300], 'automatic_retry': False}
    for key in ('refused_as', 'refusal_seen'):           # 거부로 전체 화면이 된 컷 — 거부 종류·본 자리(사실 그대로)
        if key in said:
            notice[key] = said[key]
    return notice


def refusal_facts(error, seen, env=None):
    """거부의 사실 — 종류와 어디서 보았나(request 판독 요청 · marker 실행 시작 때 이미 걸린 거부 표식 · gate 관문 · other_cut 같은 실행의
    다른 컷). 종류 = 전송이 가른 이름(agy_transport_client.refusal_kind — 증거 refused_as → 도구 거부 → 코드). 결과 없이 표식만 보았으면
    (실행 시작 때 표식 · 다른 스레드가 막 남긴 표식) 이 프로세스가 적어 둔 그 실행의 첫 거부 종류 · 그것도 없으면 None(종류 모름 — 막는다)."""
    import agy_transport_client as AGY
    import agy_transport_refusal as refusal
    evidence = getattr(error, 'provider_result', None) or {}
    kind = AGY.refusal_kind(evidence)
    if kind is None and env is not None:
        try:
            kind = refusal.refusal_kind(env)
        except ValueError:                          # 실행 ID 모양이 틀림 — 표식 확인도 같은 이유로 거부했다(종류 모름)
            kind = None
    return {'refused_as': kind, 'refusal_seen': seen, 'reason': str(evidence.get('message') or error)[:200]}


# 거절 뒤에도 피사체 단계를 멈추지 않는 거절 종류 — 한도·속도·로그인(사장님 결정 10-06 16:4x «멈추면 안된다니까» · 검토 10-06 ①:
# 기다리거나 다시 로그인하면 풀려 그 작업에서 사람이 고칠 것이 없다). 그 밖(도구 사용 거부 AGY_TOOL_DENIED · 모델 이름 AGY_MODEL_INVALID 등
# «이 PC 의 AGY 설정을 고칠 것» · 종류를 모르는 거부 표식)은 예전처럼 막는다. 어느 쪽이든 거절 뒤 AGY 요청은 0(6-2 · 거부 표식 유지).
def refusal_continues(kind):
    return kind in GATE_REFUSAL_CODES


# ── 옛 구조가 끝낸 컷 ─────────────────────────────────────────────────────────
def legacy_receipt(old_cut, path, source_sha):
    """옛 구조(얼굴·글자 검출 + 검수)가 이미 끝낸 영수증이면 그대로 쓴다. 못 쓰면 사유를 돌려준다(버리지 않는다)."""
    import focus_kernel as K
    import local_focus
    import volcano_run as R
    try:
        row = _read(path)
    except (OSError, ValueError) as error:
        return None, 'unreadable: ' + type(error).__name__
    errors = K.validate(old_cut, row)
    if errors or row.get('source_identity') != source_sha:
        return None, 'invalid: ' + ', '.join(errors or ['source_file_changed'])
    try:
        local_focus.verify_selection_runtime([row])
    except (R.StepError, OSError, KeyError, TypeError, ValueError) as error:
        return None, 'detector_environment_changed: ' + str(error)[:120]
    return row, None


# ── 옛 AGY 판이 끝낸 컷 ──────────────────────────────────────────────────────
# 서버가 prior_keys 로 주는 옛 판 열쇠 한 줄의 칸 — 컷 내용은 요청 컷과 같고 이 두 칸만 다르다(서버 agy_focus.prior_keys).
PRIOR_KEY_FIELDS = ('selection_recipe', 'focus_key')


def prior_cut_of(cut, key):
    """요청 컷 + 옛 판 열쇠 한 줄 → 옛 판 컷(그 판이 영수증을 만들 때 받은 컷과 같은 모양)."""
    return dict(cut, **{k: key[k] for k in PRIOR_KEY_FIELDS})


def prior_receipt(prior_cut, path, source_sha):
    """옛 AGY 판(subject_agy.PRIOR_ALGORITHMS · v3 = high + 크롭 재확인)이 끝낸 영수증이면 그대로 쓴다. 못 쓰면 사유(버리지 않는다).

    판정은 셋 다: 그 옛 판 열쇠로 지은 컷과 영수증이 맞는다(focus_kernel.validate · 열쇠 = 그 판 POLICY 지문) · 원본이 같다 ·
    영수증을 만든 엔진 이름이 그 옛 판이다(같은 열쇠 자리에 다른 판 파일이 있으면 쓰지 않는다)."""
    import focus_kernel as K
    import subject_agy as S
    try:
        row = _read(path)
    except (OSError, ValueError) as error:
        return None, 'unreadable: ' + type(error).__name__
    if not isinstance(row, dict):
        return None, 'invalid: not_a_receipt'
    errors = K.validate(prior_cut, row)
    if errors or row.get('source_identity') != source_sha:
        return None, 'invalid: ' + ', '.join(errors or ['source_file_changed'])
    engine = (((row.get('framing_subject') or {}).get('selection_evidence') or {}).get('engine'))
    if engine not in S.PRIOR_ALGORITHMS:
        return None, 'engine: ' + str(engine)[:60]
    return row, None


def _prior_cuts(prior, cuts):
    """서버가 준 prior_keys → {card: [옛 판 컷, …]}. 카드는 요청 컷 안 · 줄마다 두 칸(PRIOR_KEY_FIELDS)만 · 다시 지은 옛 판 컷의 열쇠가
    맞고 요청 컷의 열쇠와 다르다. 하나라도 어긋나면 일감을 거절한다(엉뚱한 파일을 그 컷의 영수증으로 쓰지 않게)."""
    import focus_kernel as K
    by_card = {str(c['card']): c for c in cuts}
    if not isinstance(prior, dict) or set(prior) - set(by_card):
        raise SubjectAgyError('agy_contract_invalid', '옛 AGY 판 열쇠 목록(prior_keys)이 요청과 다릅니다.')
    out = {}
    for card, rows in prior.items():
        if not isinstance(rows, list):
            raise SubjectAgyError('agy_contract_invalid', '옛 AGY 판 열쇠 목록(prior_keys)이 요청과 다릅니다.')
        out[card] = []
        for row in rows:
            if (not isinstance(row, dict) or set(row) != set(PRIOR_KEY_FIELDS)
                    or not all(isinstance(row[k], str) and re.fullmatch('[0-9a-f]{64}', row[k]) for k in PRIOR_KEY_FIELDS)):
                raise SubjectAgyError('agy_contract_invalid', '옛 AGY 판 열쇠 줄의 모양이 다릅니다.')
            old = prior_cut_of(by_card[card], row)
            if old['focus_key'] == by_card[card].get('focus_key') or K.cut_key(old) != old['focus_key']:
                raise SubjectAgyError('agy_contract_invalid', '옛 AGY 판 열쇠가 요청 컷과 맞지 않습니다.')
            out[card].append(old)
    return out


# ── 실행기 명령 ───────────────────────────────────────────────────────────────
def prepare_agy_focus(item, tally=None):
    """서버 일감(prepare_agy_focus) → 컷마다 영수증. 결과 모양은 옛 prepare_local_focus 와 같다.

    {version, contract_key, status: complete|blocked, receipts:{card:{focus_key,path,sha256,source_identity}},
     review_requests: [], diagnostics:{card:{code,…}}}  — 서버 consume() 이 그대로 받는다.
    tally: 재는 쪽이 주는 dict(호출 수·초·재사용 수). 결과에는 싣지 않는다(서버 계약에 없는 칸).
    """
    import focus_kernel as K
    import agy_review_bridge as bridge
    import agy_transport_refusal as refusal
    from film_editor import file_digest, file_lock, stamped_digest
    from longform_state import native_path
    tally = tally if tally is not None else {}
    if (item.get('version') != VERSION or not isinstance(item.get('contract_key'), str)
            or not re.fullmatch('[0-9a-f]{64}', item['contract_key'])):
        raise SubjectAgyError('agy_contract_invalid', 'AGY 피사체 작업 규격이 올바르지 않습니다.')
    if item.get('kernel_id') != K.KERNEL_ID:
        raise SubjectAgyError('agy_contract_invalid', '서버와 로컬 피사체 검증 코드 버전이 다릅니다. 기존 증거를 보존하고 실행기를 갱신하세요.')
    policy = check_policy(item.get('agy'))
    cuts = item['cuts']
    if len({str(c['card']) for c in cuts}) != len(cuts):
        raise SubjectAgyError('agy_contract_invalid', '피사체 컷 번호가 중복되었습니다.')
    legacy = item.get('legacy_cuts') or {}
    if not isinstance(legacy, dict) or set(legacy) - {str(c['card']) for c in cuts}:
        raise SubjectAgyError('agy_contract_invalid', '옛 규격 컷 목록이 요청과 다릅니다.')
    prior = _prior_cuts(item.get('prior_keys') or {}, cuts)
    retry = item.get('retry') or {}
    if (not isinstance(retry, dict) or set(retry) - {str(c['card']) for c in cuts}
            or any(not isinstance(v, str) for v in retry.values())):
        raise SubjectAgyError('agy_contract_invalid', '다시 잴 컷 목록(retry)이 요청과 다릅니다.')
    root = native_path(item['out_dir'])
    root.mkdir(parents=True, exist_ok=True)
    key = item['contract_key']
    out = {'version': VERSION, 'contract_key': key, 'status': 'complete', 'receipts': {}, 'review_requests': [], 'diagnostics': {}}
    env = bridge._environment({'run_id': item.get('run_id'), 'run_root': item.get('run_root')})
    prefix = item['out_dir'].rstrip('/') + '/'
    try:
        lock = file_lock(root/'agy-focus-execution.lock', '피사체 AGY 판독 ' + key[:12])
        lock.__enter__()
    except ValueError as error:
        raise SubjectAgyError('agy_in_progress', '다른 실행기가 같은 피사체 작업을 하고 있습니다.'
                              + getattr(error, 'owner_text', '')) from error
    try:
        # 렌더 직전 검증(local_focus.verify_render_receipt)이 이 파일에서 «그 영수증의 컷» 을 찾는다 — 옛 규격 컷·옛 AGY 판 컷도 같이 적는다.
        contract = {'version': 1, 'kernel_id': K.KERNEL_ID, 'contract_key': key,
                    'cuts': list(cuts) + [legacy[card] for card in sorted(legacy)]
                            + [row for card in sorted(prior) for row in prior[card]]}
        contract_path = root/(key + '.contract.json')
        if contract_path.exists():
            if _read(contract_path) != contract:
                raise SubjectAgyError('agy_contract_invalid', '피사체 규격 파일이 변경됐습니다. 덮어쓰지 않습니다.')
        else:
            _save(contract_path, contract)
        digests, todo, notes = {}, [], {}
        for cut in cuts:
            card = str(cut['card'])
            if K.cut_key(cut) != cut.get('focus_key'):
                raise SubjectAgyError('agy_contract_invalid', '피사체 컷과 서버 규격 지문이 다릅니다.')
            if cut['src'] not in digests:
                digests[cut['src']] = stamped_digest(native_path(cut['src']), root)
            source_sha = digests[cut['src']]
            old = legacy.get(card)
            if old is not None:
                if K.cut_key(old) != old.get('focus_key'):
                    raise SubjectAgyError('agy_contract_invalid', '옛 규격 컷의 지문이 다릅니다.')
                name = old['focus_key'] + '.' + source_sha + '.json'
                if (root/name).is_file():
                    row, why = legacy_receipt(old, root/name, source_sha)
                    if row is not None:
                        out['receipts'][card] = {'focus_key': old['focus_key'], 'source_identity': source_sha,
                                                 'path': prefix + name, 'sha256': file_digest(root/name)}
                        tally['legacy_reused'] = tally.get('legacy_reused', 0) + 1
                        continue
                    notes[card] = why           # 옛 영수증은 그대로 두고 AGY 로 새로 잰다
            name = cut['focus_key'] + '.' + source_sha + '.json'
            if (root/name).is_file():
                try:
                    row = _read(root/name)
                except (OSError, ValueError):
                    row = None
                if row is not None and not K.validate(cut, row) and row.get('source_identity') == source_sha:
                    out['receipts'][card] = {'focus_key': cut['focus_key'], 'source_identity': source_sha,
                                             'path': prefix + name, 'sha256': file_digest(root/name)}
                    tally['reused'] = tally.get('reused', 0) + 1
                    notice = status_error_notice(row)       # 이어 할 때도 «이 컷은 오류로 전체 화면» 을 계속 알린다(다시 묻지는 않는다)
                    if notice:
                        out['diagnostics'][card] = notice
                    continue
            # 옛 AGY 판(v3)이 끝낸 영수증 — 그대로 쓴다(AGY 에 다시 묻지 않는다 · 서버 agy_focus.PRIOR_POLICIES). 새 판 영수증이 있으면
            # 위에서 그것을 썼다(새 판으로 이미 잰 컷). 못 쓰면 사유를 남기고 새 판으로 잰다(옛 파일은 지우지 않는다).
            reused = False
            for old in prior.get(card) or []:
                old_name = old['focus_key'] + '.' + source_sha + '.json'
                if not (root/old_name).is_file():
                    continue
                row, why = prior_receipt(old, root/old_name, source_sha)
                if row is None:
                    # 같은 컷의 옛 규격(legacy) 영수증을 못 쓴 사유가 이미 있으면 덮지 않고 이어 적는다(10-07 검토 nit — 두 사유 다 남긴다).
                    notes[card] = (notes[card] + ' | ' if card in notes else '') + 'prior ' + why
                    continue
                out['receipts'][card] = {'focus_key': old['focus_key'], 'source_identity': source_sha,
                                         'path': prefix + old_name, 'sha256': file_digest(root/old_name)}
                tally['prior_reused'] = tally.get('prior_reused', 0) + 1
                notice = status_error_notice(row)           # 옛 판이 전체 화면으로 끝낸 컷이면 그 알림도 그대로
                if notice:
                    out['diagnostics'][card] = notice
                reused = True
                break
            if reused:
                continue
            todo.append((cut, source_sha, name))
        if notes:
            _save(root/'agy'/(key + '.legacy-notes.json'), notes)
        # 거부의 사실(첫 거부 하나) — 비어 있지 않으면 이 실행에서 AGY 요청은 0 이다(전역 규칙 6-2 — 거부 뒤 요청 0 · 거부 표식·다른
        # 스레드 즉시 멈춤 그대로). 남은 컷은 거절 종류로 가른다(refusal_continues): 한도·속도·로그인이면 확대 없이 전체 화면으로 끝내고
        # 작업은 제작으로(사장님 결정 10-06 16:4x «멈추면 안된다니까») · 그 밖이면 예전처럼 막는다(검토 10-06 ①).
        stopped = []
        try:
            refusal.assert_allowed(env)          # 실행을 시작할 때 이미 거부 표식이 걸려 있으면 AGY 를 한 번도 부르지 않는다
        except refusal.RunServiceRefused as error:
            stopped.append(refusal_facts(error, 'marker', env))
        if todo and not stopped:
            # 돈·시간을 쓰기 전에: AGY 가 이 PC 에서 설치·로그인·한도·«영상을 실제로 읽는가» 까지 통과해야 컷을 잰다.
            # 통과는 이 계약에 한 번만 기록한다(같은 작업을 이어 할 때 다시 시험 영상을 묻지 않는다).
            gate_path = root/'agy'/(key + '.gate.json')
            passed = _read(gate_path) if gate_path.is_file() else None
            if not (isinstance(passed, dict) and passed.get('ok') is True and passed.get('model') == policy['model']):
                gate = agy_gate(dict(item, model=policy['model']))
                tally['gate'] = gate
                if not gate.get('ok') and gate_continues(gate):
                    # 관문에서 본 한도·속도·로그인 거부 — 위와 같다(막지 않고 남은 컷 전체 화면 · AGY 요청 0).
                    stopped.append({'refused_as': gate.get('refused_as') or gate.get('code'), 'refusal_seen': 'gate',
                                    'reason': str(gate.get('message') or '')[:200]})
                elif not gate.get('ok'):
                    # 설치·시험 영상 판독 실패, 시험 영상 판독의 한도·속도·로그인 밖 거절(도구 거부 등) 같은 «AGY 를 이 PC 에서 쓸 수 없음» 은
                    # 사람이 고칠 수 있어 지금처럼 막는다(AGY 필수 · 10-05 · 검토 10-06 ①).
                    for cut, _sha, _name in todo:
                        out['diagnostics'][str(cut['card'])] = {
                            'code': 'agy_unavailable', 'agy_code': gate.get('code'),
                            'reason': (gate.get('message') or 'AGY 를 쓸 수 없습니다.')[:300], 'automatic_retry': False}
                    out['status'] = 'blocked'
                    return out
                else:
                    _save(gate_path, {'ok': True, 'model': policy['model'], 'version': gate.get('version'),
                                      'view_seconds': (gate.get('view') or {}).get('seconds')})

        def finish(card, cut, source_sha, name, row, started):
            """잰(또는 전체 화면으로 끝낸) 영수증 → 검사 · 원본 대조 · 저장 · (컷 기록, 알림)."""
            errors = K.validate(cut, row)
            size = row.get('size') if isinstance(row, dict) else None
            if errors and isinstance(size, list) and len(size) == 2:
                # 판독으로 만든 영수증이 검사를 통과하지 못했다 — 사람이 고칠 것이 없다 → 그 컷만 전체 화면(10-06 · 이유에 검사 결과)
                nframes = max(1, round(float(cut['duration']) * float(cut['fps'])))
                row, _report = cut_failure_receipt(cut, policy, folder_of(cut, source_sha), source_sha, size, nframes, tally,
                                                   'selection_invalid', '영수증 검사 실패: ' + ', '.join(errors), 'validate')
                still = K.validate(cut, row)
                errors = errors + still if still else []     # 전체 화면 영수증마저 못 통과하면 지금처럼 막는다(두 결과를 같이 남긴다)
            if errors:
                return card, None, {'code': 'selection_invalid', 'errors': errors, 'automatic_retry': False}
            try:
                # 원본이 그사이 바뀌었나 — 표지(크기·수정 시각)가 처음과 같으면 처음 지문 그대로, 다르면 그때만 다시 읽는다.
                # 예전에는 컷마다 원본 전체를 다시 읽었다(컷 N 개 = N+1 번 · 16 병렬 · #183 MemoryError 신고).
                now = stamped_digest(native_path(cut['src']), root)
            except OSError as error:
                return card, None, {'code': 'source_file_changed', 'reason': f'원본을 다시 읽지 못했습니다: {type(error).__name__}'[:300],
                                    'automatic_retry': False}
            if now != source_sha:
                return card, None, {'code': 'source_file_changed', 'automatic_retry': False}
            _save(root/name, row)
            tally.setdefault('cut_seconds', {})[card] = round(time.monotonic() - started, 2)
            return card, {'focus_key': cut['focus_key'], 'source_identity': source_sha, 'path': prefix + name,
                          'sha256': file_digest(root/name)}, status_error_notice(row)

        sizes, sizes_lock = {}, threading.Lock()

        def size_of(path):
            """원본마다 크기를 한 번만 잰다(같은 원본의 컷이 100개면 ffprobe 100번 · 시간 초과면 그만큼 기다림이 쌓였다).
            실패도 기억해 같은 원본의 다른 컷에 같은 사유로 다시 낸다 — 원본 파일 탓이라 컷마다 다시 재도 같다(사람이 고친 뒤 «다시»
            를 누르면 새 실행이 처음부터 잰다). 원본 지문(digests)을 원본마다 한 번 재는 것과 같은 모양이다."""
            key = str(path)
            with sizes_lock:
                slot = sizes.setdefault(key, {'lock': threading.Lock()})
            with slot['lock']:
                if 'size' not in slot and 'error' not in slot:
                    try:
                        slot['size'] = source_size(path)
                    except SubjectAgyError as error:
                        slot['error'] = (error.code, str(error), dict(error.detail))
            if 'error' in slot:
                code, message, detail = slot['error']
                raise SubjectAgyError(code, message, **detail)      # 컷마다 새 오류(부르는 쪽이 detail 을 고쳐 쓴다)
            return list(slot['size'])

        def folder_of(cut, source_sha):
            return root/'agy'/_hash({'focus_key': cut['focus_key'], 'source': source_sha,
                                     'policy': {k: policy[k] for k in SEMANTIC_KEYS}})

        def refused_cut(card, cut, source_sha, name, facts, started):
            """거부 뒤 이 실행에서 시작하지 않은 컷 — AGY 요청 없이(원본 크기만 ffprobe 로 · 로컬) 확대 없는 전체 화면 영수증."""
            size = size_of(native_path(cut['src']))
            nframes = max(1, round(float(cut['duration']) * float(cut['fps'])))
            row, _report = cut_failure_receipt(cut, policy, folder_of(cut, source_sha), source_sha, size, nframes, tally,
                                               'agy_refused', 'AGY 거절(' + str(facts.get('refused_as') or '종류 모름')
                                               + ') 뒤라 이 컷은 AGY 에 묻지 않았다', 'not_started', facts=facts)
            return finish(card, cut, source_sha, name, row, started)

        def not_started_facts():
            first = stopped[0]
            seen = first.get('refusal_seen') if first.get('refusal_seen') in ('marker', 'gate') else 'other_cut'
            return {'refused_as': first.get('refused_as'), 'refusal_seen': seen}

        def diagnostic_of(card, error):
            return card, None, dict({'code': error.code, 'reason': str(error)[:600], 'automatic_retry': False},
                                    **{k: v for k, v in error.detail.items()
                                       if k in ('frames', 'seconds', 'agy_code', 'failure_kind', 'provider_code', 'refused_as',
                                                'refusal_seen')})

        def blocked_after_refusal(card, facts):
            """한도·속도·로그인 밖 거절 뒤 시작하지 않은 컷 — 예전처럼 막는다(AGY 요청 0 · 거절 종류를 진단에 · 검토 10-06 ①)."""
            return card, None, {'code': 'not_started_after_refusal', 'refused_as': facts.get('refused_as'),
                                'refusal_seen': facts.get('refusal_seen'), 'automatic_retry': False}

        def work(job):
            cut, source_sha, name = job
            card = str(cut['card'])
            started = time.monotonic()
            facts = not_started_facts() if stopped else None
            if facts is not None and not refusal_continues(facts.get('refused_as')):
                return blocked_after_refusal(card, facts)
            if facts is None:
                try:
                    folder = folder_of(cut, source_sha)
                    if retry.get(card) in ANSWER_DERIVED:
                        moved = set_aside_answers(folder)
                        tally['answers_set_aside'] = tally.get('answers_set_aside', 0) + len(moved)
                    row, _report = measure_cut(cut, policy, folder, source_sha, env, tally,
                                               halt=lambda: stopped[0] if stopped else None, on_refused=stopped.append,
                                               size_of=size_of)
                    return finish(card, cut, source_sha, name, row, started)
                except refusal.RunServiceRefused as error:
                    # measure_cut 밖에서 올라온 거부(안전망) — 같은 처리: 다른 컷을 멈추고 이 컷은 AGY 요청 없이 전체 화면
                    # (한도·속도·로그인) 또는 막음(그 밖).
                    stopped.append(refusal_facts(error, 'request', env))
                    facts = dict(stopped[-1])
                    if not refusal_continues(facts.get('refused_as')):
                        return card, None, {'code': 'provider_refused', 'provider_code': facts.get('refused_as'),
                                            'refused_as': facts.get('refused_as'), 'refusal_seen': 'request',
                                            'reason': facts['reason'], 'automatic_retry': False}
                except SubjectAgyError as error:
                    return diagnostic_of(card, error)
            try:
                return refused_cut(card, cut, source_sha, name, facts, started)
            except SubjectAgyError as error:          # 원본 크기를 못 읽음(source_probe_failed) 등 — 전체 화면 영수증도 못 만든다(막는다)
                return diagnostic_of(card, error)
        with ThreadPoolExecutor(max_workers=min(policy['parallel'], max(1, len(todo)))) as pool:
            for card, receipt, diagnostic in pool.map(work, todo):
                if receipt:
                    out['receipts'][card] = receipt
                if diagnostic:
                    out['diagnostics'][card] = diagnostic
    finally:
        lock.__exit__(None, None, None)
    # 막힘 = 영수증이 없는 컷이 있다. 한 컷의 실패·거부로 전체 화면이 된 컷(fallback)은 영수증이 있어 막지 않는다(결정 5-1 · 10-06
    # 넓힘 · 10-06 16:4x 거부 뒤에도 멈추지 않음) — 그 컷의 알림은 diagnostics 에 남아 서버 consume 이 그대로 받는다.
    if any(not d.get('fallback') for d in out['diagnostics'].values()):
        out['status'] = 'blocked'
    refused = sorted(card for card, d in out['diagnostics'].items() if d.get('fallback') and d.get('cause') == 'agy_refused')
    fallen = sorted(card for card, d in out['diagnostics'].items() if d.get('fallback') and d.get('cause') != 'agy_refused')
    if refused:
        kinds = sorted({str(out['diagnostics'][card].get('refused_as') or '종류 모름') for card in refused})
        print('피사체 AGY: ' + refused_notice([out['diagnostics'][card] for card in refused]) + '(거절: ' + ', '.join(kinds)
              + ' · 컷: ' + ', '.join(refused)[:200] + ')', file=sys.stderr, flush=True)
    if fallen:
        causes = sorted({str(out['diagnostics'][card].get('cause') or 'agy_status_error') for card in fallen})
        print('피사체 AGY: 컷 ' + str(len(fallen)) + '개(' + ', '.join(fallen)[:200] + ')는 판독을 끝내지 못해(' + ', '.join(causes)
              + ') 확대하지 않고 전체 화면으로 둡니다(사장님 결정 5-1 · 나머지 컷은 그대로 · 그 컷은 AGY 에 다시 묻지 않음).',
              file=sys.stderr, flush=True)
    if stopped:
        tally['refusal'] = dict(stopped[0])
    tally['cuts'] = len(cuts)
    tally['local_inference_frames'] = 0
    return out


# ── 돈·시간이 나가기 전의 관문 ────────────────────────────────────────────────
# 관문(agy_gate)이 본 «거부» — 한도·속도·로그인(상태 확인의 /usage·models 판정) 또는 시험 영상 판독이 전송 거부를 받음.
# 이런 관문 실패는 막지 않고 거부 뒤와 같이 남은 컷을 전체 화면으로 끝낸다(사장님 결정 10-06 16:4x). 설치·시험 영상 판독 실패
# 같은 «이 PC 에서 AGY 를 쓸 수 없음» 은 사람이 고칠 수 있어 지금처럼 막는다(AGY 필수 · 10-05).
GATE_REFUSAL_CODES = ('AGY_QUOTA', 'AGY_RATE_LIMIT', 'AGY_NOT_SIGNED_IN')


def gate_continues(gate):
    """관문 실패가 «한도·속도·로그인» 이라 멈추지 않는 거절인가 — 상태 확인의 코드 또는 시험 영상 판독이 받은 거절의 종류(refused_as).
    시험 영상 판독의 도구 거부 같은 그 밖의 거절은 막는다(검토 10-06 ①)."""
    return refusal_continues(gate.get('refused_as') or gate.get('code'))


# 확대 없이 넣은 컷의 학생 알림(사장님 결정 10-06 16:4x · 검토 10-06 ②③). 서버 agy_focus.REFUSED_FALLBACK_TEXT·
# LOGIN_REFUSED_FALLBACK_TEXT 와 같은 글이어야 한다(검사 tests/test_subject_agy_refusal_kinds.py 가 대조한다). {n} = 그 컷 수.
# ② «새 작업 폴더에서» — 같은 작업 폴더에서 다시 돌리면 거절로 넣은 컷의 영수증을 그대로 다시 쓴다(AGY 에 다시 묻지 않는다 · 6-2).
REFUSED_NOTICE = ('AGY 가 한도/속도/로그인 이유로 거절해 {n}컷은 확대 없이 넣었습니다(자동으로 다시 묻지 않음). 확대가 필요하면 한도가 '
                  '풀린 뒤 새 작업 폴더에서 다시 만드세요(같은 작업 폴더에서 다시 돌리면 확대 없이 넣은 컷을 그대로 씁니다). ')
LOGIN_REFUSED_NOTICE = ('AGY 로그인이 풀려 {n}컷은 확대 없이 넣었습니다(자동으로 다시 묻지 않음). 확대가 필요하면 이 컴퓨터 화면에서 '
                        'agy 를 한 번 실행해 구글 로그인을 마친 뒤 새 작업 폴더에서 다시 만드세요(같은 작업 폴더에서 다시 돌리면 확대 '
                        '없이 넣은 컷을 그대로 씁니다). ')


def refused_notice(diagnostics):
    """거절로 확대 없이 넣은 컷들의 알림 — 로그인 풀림(AGY_NOT_SIGNED_IN)과 한도·속도를 갈라 그 수를 말한다."""
    login = sum(1 for d in diagnostics if d.get('refused_as') == 'AGY_NOT_SIGNED_IN')
    other = len(diagnostics) - login
    return ((LOGIN_REFUSED_NOTICE.replace('{n}', str(login)) if login else '')
            + (REFUSED_NOTICE.replace('{n}', str(other)) if other else ''))


def _private_masked(text):
    """상태 판정의 확인 기록에서 홈 폴더(사용자 이름이 든다)를 ~ 로, 계정 이메일을 <계정> 으로 — 나머지 사실(경로 끝·종료 코드·시간 초과)은 그대로.
    윈도우는 경로 대소문자를 가리지 않고 / 와 \\ 를 둘 다 쓴다."""
    out = str(text or '')
    home = os.path.expanduser('~')
    if home and home not in ('~', os.sep, '/'):
        for h in sorted({home, home.replace('\\', '/'), home.replace('/', '\\')}, key=len, reverse=True):
            # 이름 경계까지만(홈이 C:\\Users\\kim 일 때 C:\\Users\\kimchi 를 «~chi» 로 만들지 않는다).
            out = re.sub(re.escape(h) + r'''(?![^\\/\s:;'"])''', '~', out, flags=re.IGNORECASE if os.name == 'nt' else 0)
    return re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', '<계정>', out)


def _status(item, env):
    """설치·로그인·모델·한도 — 기존 판정 한 자리(agy_transport_pc_env.agy_status · 맥·윈도우 같은 코드). 홈 경로·계정은 내보내지 않는다."""
    import agy_transport_pc_env as PC
    status = PC.agy_status(env=env, model=item['model'], usage=True)
    quota = status.get('quota') or {}
    # 코드 표 글은 이 판독이 실제로 쓰는 모델(서버가 준 item['model'])로 짓는다(PC.code_text model= · 표에 적힌 모델 이름을 그대로 말하지 않는다).
    # AGY_MODEL_UNAVAILABLE 은 상태 판정 글이 이미 그 모델 이름과 보이는 모델 수를 말하므로 그 글만 쓴다(같은 말을 두 번 붙이지 않는다).
    # 그 밖의 코드는 코드 표 글을 머리말로 두고 상태 판정이 남긴 확인 기록(후보 경로마다 --version 종료 코드·시간 초과 · models 출력 끝 · 한도 묶음)을
    # 그대로 붙인다(신고 #174 — 예전에는 코드 표 글로 덮어 원인이 지워졌다). 한도처럼 판정 글이 이미 코드 표 글로 시작하면 두 번 적지 않는다.
    code = status.get('code')
    head = PC.code_text(code, model=item['model'], env=env) if code else ''
    said = _private_masked(status.get('message')).strip()
    # AGY_UNRESPONSIVE 도 같다 — 코드 표 글은 «agy models 가 …» 인데 같은 코드가 --version 시간 초과에도 난다(10-21 cb86d7) ·
    #   상태 판정의 글이 어느 호출이 몇 초에 늦었는지 스스로 말하므로 그것만 쓴다(틀린 호출 이름을 머리말로 붙이지 않는다).
    if code not in ('AGY_MODEL_UNAVAILABLE', 'AGY_UNRESPONSIVE') and head and not said.startswith(head):
        said = head + (' — 확인한 것: ' + (said if len(said) <= 300 else '…' + said[-300:]) if said else '')
    message = said
    return {'ok': bool(status.get('ok')), 'code': code,
            'message': message,
            'version': status.get('version'), 'source': status.get('source'), 'signed_in': status.get('signedIn'),
            'model': status.get('model'), 'quota_known': quota.get('known'), 'reset_at': status.get('resetAt'), 'view': None}


def agy_preflight(item):
    """env 단계(제작표·원본·유료 단계 전)의 이른 관문 — 영상 없이 설치·로그인·모델·한도만 잰다(수 초).

    실제 판독(2초 시험 영상)은 피사체 일감 맨 앞의 agy_gate 가 계약당 한 번 한다. 돌려주는 값은 agy_gate 와 같은 모양.
    """
    import agy_review_bridge as bridge
    if not isinstance(item.get('model'), str) or not item['model']:
        raise SubjectAgyError('agy_policy_invalid', 'AGY 사전 확인 지시에 모델 이름이 없습니다. 실행기·서버를 갱신하세요.')
    started = time.monotonic()
    out = _status(item, bridge._environment({'run_id': None, 'run_root': None}))
    return dict(out, seconds=round(time.monotonic() - started, 2), stage='env')


def agy_gate(item):
    """AGY 가 이 PC 에서 «영상을 실제로 읽는가» 까지 확인한다. 값·계정은 내보내지 않는다.

    ① 설치·로그인·모델·한도 — 기존 판정 한 자리(agy_transport_pc_env.agy_status)
    ② 실제 판독 — 서버가 준 명령으로 만든 2초짜리 시험 영상을 view_file 로 읽히고 답을 대조한다.
    돌려주는 값: {ok, code, message, version, source, signed_in, model, quota_known, reset_at, view{ok, seconds}}
    """
    import agy_review_bridge as bridge
    import agy_transport_pc_env as PC
    import agy_transport_refusal as refusal
    env = bridge._environment({'run_id': item.get('run_id'), 'run_root': item.get('run_root')})
    out = _status(item, env)
    probe = item.get('view_probe')
    if not out['ok']:
        return out
    if not probe:
        return dict(out, ok=False, code='AGY_VIEW_PROBE_MISSING', message='서버가 AGY 시험 영상 지시를 보내지 않았습니다. 실행기·서버를 갱신하세요.')
    workspace = Path(tempfile.mkdtemp(prefix='volcano-agy-probe-'))
    try:
        clip = workspace/'probe.mp4'
        argv = [str(clip) if part == '@@OUT@@' else part for part in probe['argv']]
        try:
            done = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        except (subprocess.TimeoutExpired, OSError) as error:
            return dict(out, ok=False, code='AGY_VIEW_PROBE_FAILED', message=f'시험 영상을 만들지 못했습니다(ffmpeg · {type(error).__name__}).')
        if done.returncode or not clip.is_file():
            return dict(out, ok=False, code='AGY_VIEW_PROBE_FAILED', message='시험 영상을 만들지 못했습니다(ffmpeg).')
        policy = {'guard': probe['guard'], 'model': item['model'], 'timeout_s': probe['timeout_s']}
        try:
            answer, facts = ask(lambda path: probe['question'].replace('{path}', path), clip, policy, env, 'volcano-subject-gate')
        except refusal.RunServiceRefused as error:
            evidence = getattr(error, 'provider_result', None) or {}
            kind = refusal_facts(error, 'gate', env)['refused_as']        # 판독 컷과 같은 한 규칙(전송 refusal_kind · 그 실행의 첫 거부)
            return dict(out, ok=False, code=kind or 'AGY_REFUSED', refused=True, refused_as=kind,
                        message=PC.code_text(evidence.get('code'), model=item['model'], env=env) or 'AGY 가 시험 영상 판독을 거부했습니다.')
        except SubjectAgyError as error:
            return dict(out, ok=False, code='AGY_VIEW_PROBE_FAILED', message=str(error)[:300])
        passed = answer.get('answer') == probe['expect']
        if not passed:
            facts['answer'] = answer
        return dict(out, ok=passed, code=None if passed else 'AGY_VIEW_PROBE_WRONG',
                    message=out['message'] if passed else 'AGY 가 시험 영상을 읽었지만 답이 달랐습니다.',
                    view={'ok': passed, 'seconds': facts['seconds']})
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
