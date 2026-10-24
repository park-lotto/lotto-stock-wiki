"""Run source-bound focus verification locally and publish only receipt metadata.

The exact server validation kernel is generated at build time. Dense originals,
OCR bindings, and review results never form this command's network result.
"""
import copy
import hashlib
import json
from pathlib import Path


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8', 'surrogatepass')).hexdigest()


def _read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _legacy_object(value, field):
    """Decode one documented JSON-object envelope without rewriting its archive."""
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as error:
            raise ValueError('payload.'+field+'의 JSON 값을 읽을 수 없습니다.') from error
    if not isinstance(value, dict):
        raise ValueError('payload.'+field+'가 객체여야 합니다.')
    return value


def _refused(row):
    evidence = ((row.get('framing_subject') or {}).get('selection_evidence') or {}) if isinstance(row,dict) else {}
    return _receipt_refused(evidence)


def _receipt_refused(receipt):
    code = receipt.get('code') if isinstance(receipt,dict) else None
    return code == 'provider_refused' or (type(code) is int and code in (401,402,403,429))


def runtime_stale(row, identities):
    """이 선택 행이 지금과 다른 검출 모델·환경(framevision 파일·패키지 판·설정)·알고리즘에서 나왔나.
    identities = {뿌리: 지금 지문} — 부르는 쪽이 한 번 만들어 넘긴다(뿌리마다 지문 한 번)."""
    import subject_focus as F
    runtime = row.get('selection_runtime') if isinstance(row,dict) else None
    if not runtime:
        return False  # Historical rows without a runtime stamp had no such gate.
    root = runtime['root']
    if root not in identities:
        current = F._detector_identity(root)
        identities[root] = hashlib.sha256(json.dumps(current, sort_keys=True,
            ensure_ascii=False).encode()).hexdigest()
    return identities[root] != runtime['identity'] or runtime['algorithm'] != F.ALGORITHM_VERSION


def verify_selection_runtime(rows, identities=None):
    """Preserve the former renderer's detector/model/algorithm equality gate.
    identities — 같은 실행에서 이미 잰 지금 지문(runtime_stale 과 같은 dict)을 넘기면 다시 재지 않는다."""
    import volcano_run as R
    identities = {} if identities is None else identities
    if any(runtime_stale(row, identities) for row in rows):
        raise R.StepError('피사체 선택 뒤 검출 모델·환경이 바뀌었습니다. 이전 원본·검수 기록을 보존하고 현재 환경에서 재확인해야 합니다.')


# 사람이 «고쳤으니 다시» 를 알린 컷 목록을 싣는 선택 칸(서버 volcano_local_render.RETRY_SELECTION_KEY 와 같은 이름).
# 계약 지문에는 들지 않는다(local_render_plan._semantic · local_source_plan 이 뺀다) — 같은 계약의 한 번 실행 지시일 뿐이다.
RETRY_SELECTION_KEY = 'focus_retry_cards'
_REASON_CHARS = 300


def _execution_failure(row):
    """선택 단계가 **판정 없이** 끝난 행인가 — 예외로 멈춘 실행 실패(subject_focus.select_subjects 의 execution 행).

    판정(주인공 못 정함·물체 확인 실패 같은 모델 답)과 다르다: 원본·크기·지문을 재기 전에 끊겼으므로 K.validate 에
    태우면 «크기 없음·원본 바뀜» 같은 거짓 사유가 붙는다(2026-10-15 쇼핑 신고 — 원본을 안 바꿨는데 source_file_changed).
    거부(provider_refused·401/402/403/429)와 예산 정지(review_budget_blocked — 예산 재개 경로가 따로 있다)는 여기 넣지 않는다."""
    if not isinstance(row, dict) or row.get('review_budget_blocked') or _refused(row):
        return False
    recovery = row.get('focus_recovery')
    return isinstance(recovery, dict) and recovery.get('stage') == 'execution'


#: 실행이 판정 없이 끝났지만 **같은 입력으로 다시 재도 같은 실패** 인 코드 — 판독 파일이 구독 AGY view_file 한도를 넘음 ·
#:   검수 요청이 크기 상한을 넘음(실행기 subject_focus·image_qc 가 붙이는 코드). «다시» 표식을 주면 사람이 아무리 눌러도 같은
#:   실패만 돌아온다(헛도는 고리 · 2026-10-15 검토) — 그래서 다시 잴 막힘이 아니라 «이 컷의 입력이 검수에 맞지 않음» 으로
#:   말하고, 컷 지문·원본 지문을 실어 쇼핑이 그 컷만 다른 소재로 바꾸게 한다(volcano_shop_recovery).
_INPUT_UNUSABLE_CODES = ('AGY_FILE_TOO_LARGE', 'review_request_oversize')


def _bound(diagnostic, focus_key, cut, source_sha):
    """진단에 컷 지문·원본 지문을 싣는다 — 쇼핑은 이 둘로 «이 컷만 다른 소재로 교체» 를 이 원본에 묶는다."""
    return dict(diagnostic, focus_key=focus_key, source=cut['src'], source_identity=source_sha)


def _execution_diagnostic(row, focus_key, cut, source_sha):
    evidence = ((row.get('framing_subject') or {}).get('selection_evidence') or {})
    reason = evidence.get('reason') if isinstance(evidence.get('reason'), str) else ''
    code = (row.get('focus_recovery') or {}).get('code')
    code = code if isinstance(code, str) else str(code)
    if code in _INPUT_UNUSABLE_CODES:
        return _bound({'code': 'selection_invalid', 'errors': ['review_input_unusable'], 'failure_code': code,
                       'reason': reason[:_REASON_CHARS], 'automatic_retry': False}, focus_key, cut, source_sha)
    return {'code': 'selection_execution_failed', 'stage': 'execution', 'failure_code': code,
            'reason': reason[:_REASON_CHARS], 'automatic_retry': False}


#: 검수 엔진 실패(구독 AGY 가 결과 없이 끝남 등)를 «사람 답 대기» 가 아니라 실행 실패 행으로 받는 판(subject_focus.select_subjects
#:   · volcano_run._review_preserved_video_text 의 engine_failure_rows). 상태 파일의 컷 기록에 이 판 번호를 적는다 — 이 판보다
#:   먼저(옛 실행기) 저장된 «대기» 행·화면 글자 영수증은 그 구분이 없으므로 한 번만 다시 읽어 지금 규칙으로 가른다
#:   (영수증이 있으면 모델을 다시 띄우지 않는다 — client_review 의 attempted 영수증 · 새 요청 0).
ENGINE_ROWS = 1
#: 옛 화면 글자 영수증(stage 칸이 없던 판)에서 «실행이 끊김» 을 뜻하던 코드.
_TEXT_EXECUTION_CODES = ('video_text_execution_failed', 'review_execution_failed')


def _text_execution_failure(receipt):
    """화면 글자 검수가 판정 없이 끝났고 **다시 재면 달라질 수 있는가**(실행 끊김·엔진 결과 없음) — 모델 판정·거부·
    예산 정지·같은 입력이면 같은 실패(_INPUT_UNUSABLE_CODES)는 아니다."""
    return (isinstance(receipt, dict) and receipt.get('status') not in ('pending', 'accepted')
            and not _receipt_refused(receipt) and not receipt.get('review_budget_blocked')
            and receipt.get('code') not in _INPUT_UNUSABLE_CODES
            and (receipt.get('stage') == 'execution' or receipt.get('code') in _TEXT_EXECUTION_CODES))


def _text_diagnostic(receipt, focus_key, cut, source_sha):
    reason = receipt.get('reason') if isinstance(receipt.get('reason'), str) else ''
    if _text_execution_failure(receipt):
        return {'code': 'selection_execution_failed', 'stage': 'text_review', 'failure_code': str(receipt.get('code')),
                'reason': reason[:_REASON_CHARS], 'automatic_retry': False}
    if _receipt_refused(receipt):
        # 제공자 거부(401·402·403·429) — 소재를 바꿔도 같은 거부다(6-2: 거부면 멈춘다). 교체 묶음 칸을 싣지 않는다.
        return {'code': 'provider_refused', 'automatic_retry': False}
    if receipt.get('review_budget_blocked'):
        # 예산 정지 — 예산을 늘리면 이어진다(예산 재개 경로). 교체 대상이 아니라 예전 모양 그대로 둔다.
        return {'code': 'text_review_unresolved', 'automatic_retry': False}
    # 판정(글자 후보 분류가 끝나지 않음)·같은 입력이면 같은 실패 — 다시 재도 같다. 컷 지문·원본 지문을 실어 쇼핑이 그 컷만
    #   다른 소재로 바꾸게 한다(예전에는 묶음 칸이 없어 쇼핑도 «소재를 바꾸라» 는 말뿐이었다 · 2026-10-15 검토).
    return _bound({'code': 'text_review_unresolved', 'failure_code': str(receipt.get('code')),
                   'reason': reason[:_REASON_CHARS], 'automatic_retry': False}, focus_key, cut, source_sha)


def _block_diagnostic(K, cut, row, focus_key, source_sha):
    """선택 행 하나의 막힘 진단 — 없으면 None(유효한 행). 새로 잰 행과 저장된 옛 막힘(옛 실행기 기록 포함)을 **같은 규칙**으로 말한다."""
    if _execution_failure(row):
        # 판정이 아니라 «결과 없음» — 거짓 사유(크기 없음·원본 바뀜)를 만들지 않고 그대로 말한다.
        return _execution_diagnostic(row, focus_key, cut, source_sha)
    errors = K.validate(cut, row)
    # 원본이 바뀐 것은 행이 **다른** 원본 지문을 들고 있을 때만이다 — 지문 없는 행을 «바뀜» 으로 세던 것이 거짓 사유였다
    #   (지문 없음 자체는 validate 가 판정한다: 끝난 판정 행은 source_identity_missing · 미확정 행은 selection_unresolved).
    if isinstance(row.get('source_identity'), str) and row['source_identity'] != source_sha:
        errors.append('source_file_changed')
    if not errors:
        return None
    diagnostic = _bound({'code': 'selection_invalid', 'errors': errors, 'automatic_retry': False}, focus_key, cut, source_sha)
    blocked = row.get('review_budget_blocked')
    if isinstance(blocked, dict):
        diagnostic['review_budget_blocked'] = dict(blocked)
    return diagnostic


def _rowless_diagnostic(diagnostic):
    """원본 행(.original.json)이 없는 저장된 막힘 — 판정을 뒷받침할 행이 없으니 «판정» 으로 두지 않는다.

    옛 실행기는 결과 없는 실행 실패도 selection_invalid(거짓 사유)로 적었다. 행이 남아 있으면 _block_diagnostic 이 지금
    규칙으로 다시 말하지만, 행이 없으면 그 진단을 그대로 돌려줘 «다시» 표식도 교체도 없는 막다른 길이었다(2026-10-15 검토).
    행이 없는 selection_invalid 는 «결과 빠짐» 이다 — 사람이 «다시» 를 알리면 그 컷을 새로 잰다(행이 없으면 다시 묻는다).
    예산 정지(예산 재개 경로)·거부·그 밖의 진단은 그대로다."""
    if (isinstance(diagnostic, dict) and diagnostic.get('code') == 'selection_invalid'
            and not diagnostic.get('review_budget_blocked')):
        return {'code': 'local_focus_results_missing', 'automatic_retry': False}
    return diagnostic


def _retry_cards(selection, cards):
    """서버가 사람의 «다시» 표식을 확인하고 실은 컷 목록 — {컷: 막힌 까닭 코드} 중 이 일감의 컷만. 없으면 빈 묶음.

    이 일감 밖 컷(쇼핑의 전체 화면 컷처럼 피사체를 재지 않는 컷)은 여기서 다시 잴 것이 없으니 뺀다."""
    import volcano_run as R
    retry = selection.pop(RETRY_SELECTION_KEY, None)
    if retry is None:
        return {}
    if not isinstance(retry, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in retry.items()):
        raise R.StepError('다시 잴 컷 목록(focus_retry_cards)의 형식이 다릅니다. 서버의 새 응답을 받으세요.')
    return {card: code for card, code in retry.items() if card in cards}


def _budget_can_resume(blocked, policy):
    """Only an explicitly increased limit releases a proven never-sent attempt."""
    return (isinstance(blocked, dict) and type(blocked.get('attempts_reserved')) is int
            and blocked['attempts_reserved'] == 0 and type(blocked.get('max_requests')) is int
            and blocked['max_requests'] > 0 and policy.get('provider') == 'evolink'
            and type(policy.get('max_requests')) is int
            and policy['max_requests'] > blocked['max_requests'])


#: 같은 입력으로 다시 물어도 같은 답인 막힘 — 판정이 피사체를 정하지 못함(selection_invalid · 검수에 맞지 않는 입력 포함) ·
#:   구독 AGY/제공자 거부(provider_refused). 부르는 쪽이 full_frame(출력 비율)을 주면 그 컷은 판정을 다시 묻지 않고
#:   확대 없이 전체 화면 영수증으로 끝낸다(뇌전구 TTS 렌더 계획 · 2026-10-17 사장님 원칙 «멈춤 대신 정상 실행»).
#:   예산 정지(review_budget_blocked)는 예산을 늘리면 이어지는 길이 따로 있어 넣지 않는다.
FULL_FRAME_CODES = ('selection_invalid', 'provider_refused')
#: 거부를 본 실행에서 아직 판정하지 않은 컷의 까닭 — 거부 뒤에는 그 실행의 요청을 더 보내지 않는다(전역 규칙 6-2).
NOT_STARTED_AFTER_REFUSAL = 'not_started_after_refusal'


def _full_frame_eligible(diagnostic):
    return (isinstance(diagnostic, dict) and diagnostic.get('code') in FULL_FRAME_CODES
            and not diagnostic.get('review_budget_blocked'))


def full_frame_row(cut, focus_key, source_sha, aspect, cause, row=None):
    """확대하지 않는 전체 화면 영수증(배율 1.0) — 인물형 롱폼 subject_agy.full_frame 과 같은 자.

    지키는 영역 = 원본 알맹이 안에 들어가는 가장 큰 출력 비율 창(subject_agy.window)을 알맹이 한가운데에 둔 것.
    렌더(center_plan)는 그 창보다 작게 자를 수 없으므로 채널 줌이 걸리지 않고 cover 맞춤 그대로 나간다.
    판정(AGY)을 다시 묻지 않는다 — 원본 크기·알맹이는 판정 행에 잰 값이 있으면 그것을, 없으면(거부·실행 실패 행) 그림에서
    판정과 같은 알맹이 자(volcano_run._content_rect_over · cut['band'])로 잰다. 정지 그림 컷만 받는다(TTS 렌더 계획)."""
    import subject_agy as S
    import volcano_run as R
    from longform_state import native_path
    if cut.get('kind') != 'image':
        raise R.StepError('전체 화면 영수증은 정지 그림 컷에서만 만듭니다: ' + str(cut.get('card')))
    measured = row if isinstance(row, dict) else {}
    size, content = measured.get('size'), measured.get('content')
    if not (isinstance(size, list) and len(size) == 2 and all(type(v) is int and v > 0 for v in size)
            and isinstance(content, list) and len(content) == 4 and all(type(v) is int for v in content)
            and content[2] > 0 and content[3] > 0 and content[0] >= 0 and content[1] >= 0
            and content[0] + content[2] <= size[0] and content[1] + content[3] <= size[1]):
        from PIL import Image
        import numpy as np
        band = cut['band']
        with Image.open(native_path(cut['src'])) as image:
            size = [int(image.width), int(image.height)]
            gray = np.asarray(image.convert('L'))
        content = [int(v) for v in R._content_rect_over([gray], band['dark_max'], band['black_frac'], band['frame_dark_min'])]
    x, y, w, h = content
    base_w, base_h = S.window((w, h), aspect)
    box = [x + (w - base_w) / 2, y + (h - base_h) / 2, base_w, base_h]
    start = float(cut.get('start', 0))
    reason = '판정을 다시 묻지 않고 확대 없이 전체 화면으로 둔다(' + str(cause) + ' · 자동 재시도 없음)'
    subject = dict(bbox=list(box), track=[dict(frame_index=0, t=start, bbox=list(box), cut=False)], origin=start,
                   complete=True, kind='scene',
                   selection_evidence=dict(decisions=[dict(sample=0, kind='scene', face_ids=[], speaker='silent',
                                                           reason=reason, engine='full-frame-fallback', frame_index=0)],
                                           engine='full-frame-fallback', automatic_retry=False,
                                           full_frame=dict(cause=str(cause), exception=str(cause) + '_full_frame')))
    return dict(focus_key=focus_key, focus_status='accepted', size=list(size), content=list(content),
                source_identity=source_sha, framing_subject=subject, by='scene', face=None, face_samples=[],
                subject=[.5, .5], subject_detected=False, measurement_version=3)


def full_frame_cause(row):
    """전체 화면 영수증이면 그 까닭(full_frame_row 의 cause), 아니면 None — 렌더 계획의 알림이 이것을 읽는다."""
    evidence = (((row or {}).get('framing_subject') or {}).get('selection_evidence') or {}) if isinstance(row, dict) else {}
    marker = evidence.get('full_frame')
    return marker.get('cause') if isinstance(marker, dict) and evidence.get('engine') == 'full-frame-fallback' else None


def prepare_local_focus(item, headers=None, full_frame=None):
    """full_frame — 출력 비율 (가로, 세로). 주면 FULL_FRAME_CODES 막힘과 거부 뒤 판정하지 않은 컷을 전체 화면 영수증으로 끝낸다
    (부르는 쪽의 선택 · 계약 지문에 들지 않는다 — 같은 계약의 막힌 컷을 «다시 묻지 않고» 끝내는 실행 방식일 뿐이다).
    그 컷과 까닭은 결과의 full_frame 칸 {컷: 까닭} 에 싣는다(full_frame 을 준 경우만 · 다른 부르는 쪽 결과는 그대로)."""
    import focus_kernel as K
    import subject_focus as F
    import volcano_run as R
    from longform_state import native_path, save
    from film_editor import file_digest
    if item.get('version') != 1 or not isinstance(item.get('contract_key'), str):
        raise R.StepError('로컬 피사체 작업 규격이 올바르지 않습니다.')
    if item.get('kernel_id') != K.KERNEL_ID:
        raise R.StepError('서버와 로컬 피사체 검증 코드 버전이 다릅니다. 기존 증거를 보존하고 실행기를 갱신하세요.')
    cuts = item['cuts']
    if len({str(c['card']) for c in cuts}) != len(cuts):
        raise R.StepError('로컬 피사체 컷 번호가 중복되었습니다.')
    root = native_path(item['out_dir']); root.mkdir(parents=True, exist_ok=True)
    key = item['contract_key']
    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        raise R.StepError('로컬 피사체 규격 지문이 올바르지 않습니다.')
    state_path = root / (key + '.state.json')
    with R.review_receipt_lock(str(root / 'local-focus-execution')):
        contract_path = root / (key + '.contract.json')
        contract = {'version': 1, 'kernel_id': K.KERNEL_ID, 'contract_key': key, 'cuts': cuts}
        if contract_path.exists():
            if _read(contract_path) != contract:
                raise R.StepError('로컬 피사체 규격 파일이 변경됐습니다. 덮어쓰지 않습니다.')
        else:
            save(contract_path, contract)
        state = _read(state_path) if state_path.exists() else {'version': 1, 'contract_key': key, 'cuts': {}}
        if state.get('version') != 1 or state.get('contract_key') != key:
            raise R.StepError('로컬 피사체 작업 기록과 규격이 다릅니다. 기존 기록은 보존합니다.')
        selection = dict(item['selection'])
        retry = _retry_cards(selection, {str(c['card']) for c in cuts})
        # 검수 엔진이 결과 없이 끝나면 실행 실패 행으로 받는다(사람에게 영상·음성 판독 답을 손으로 쓰게 하지 않는다 — 전역 규칙 6-1).
        selection['engine_failure_rows'] = True
        # 사람이 «다시» 를 알린 컷의 검수 영수증을 한 번 놓아 주는 한 실행의 장부(화면 글자 검수용 · 선택은 select_subjects 가 만든다).
        retry_registry = R.review_retry_registry() if retry else None
        replies = selection.get('focus_review_replies') or {}
        reply_key = _hash(replies)
        out = {'version': 1, 'contract_key': key, 'status': 'complete',
               'receipts': {}, 'review_requests': [], 'diagnostics': {}}
        fallen = {}       # 전체 화면으로 끝낼 컷 {컷: (cut, 판정 행 또는 None, 까닭)} — full_frame 을 준 경우만 채운다
        refusal = False   # 이 실행에서 거부를 봤다 — 그 뒤로는 새 판정 요청을 보내지 않는다(6-2)
        by_card = {str(c['card']): c for c in cuts}
        legacy = {}; legacy_missing = set(); legacy_all_missing = False; legacy_text = {}
        legacy_root = native_path(item.get('legacy_dir') or root)
        legacy_path = legacy_root / 'legacy-index.json'
        if legacy_path.exists():
            for record in _read(legacy_path).get('records', []):
                evidence_path = legacy_root / record['file']
                if file_digest(evidence_path) != record['sha256']:
                    raise R.StepError('보존한 이전 피사체 기록의 지문이 다릅니다.')
                prior = R.unfold_payload(_read(evidence_path))
                try:
                    candidates = [prior.get(field) if R._blob_is_marker(prior.get(field))
                        else K.normalize_focus_rows(prior.get(field), field)
                        for field in ('frames', 'focus_measurements', 'focus_frames')]
                    text_state = _legacy_object(prior.get('video_text_state'), 'video_text_state')
                    text_results = _legacy_object(text_state.get('results'), 'video_text_state.results')
                    text_results = dict(text_results)
                    text_results.update(_legacy_object(prior.get('video_text_results'), 'video_text_results'))
                except ValueError as error:
                    raise R.StepError(str(error)) from error
                recovery = prior.get('focus_recovery')
                if R._blob_is_marker(recovery):
                    legacy_all_missing = True
                    recovery = {}
                try:
                    recovery = K.normalize_focus_recovery(recovery)
                except ValueError as error:
                    raise R.StepError(str(error)) from error
                candidates.append(recovery.get('unrepaired_frames') or {})
                for rows in candidates:
                    if R._blob_is_marker(rows):
                        legacy_all_missing = True
                        continue
                    for card, row in rows.items():
                        if R._blob_is_marker(row):legacy_missing.add(str(card))
                        elif isinstance(row, dict) and isinstance(row.get('focus_key'), str):
                            legacy[row['focus_key']] = row
                legacy_text.update(text_results)
        source_hashes = {}; loaded = {}; missing = []; cache_only = set()
        waiting = set()   # 검수 답을 기다리는 컷(결과 빠짐 판정에서 뺀다)
        checked = set()   # 저장된 막힘을 다시 말하며 이미 검사한 유효 행(두 번 검사하지 않는다)
        runtime_now = {}  # 뿌리마다 지금 검출 환경 지문 한 번(runtime_stale)
        for cut in cuts:
            card = str(cut['card']); focus_key = K.cut_key(cut)
            if cut.get('focus_key') != focus_key:
                raise R.StepError('로컬 피사체 컷과 서버 규격 지문이 다릅니다.')
            if cut['src'] not in source_hashes:
                source_hashes[cut['src']] = file_digest(native_path(cut['src']))
            source_sha = source_hashes[cut['src']]
            saved = state['cuts'].get(card) or {}
            if saved and saved.get('focus_key') != focus_key:
                raise R.StepError('컷 규격이 기존 기록과 다릅니다. 이전 검수 기록은 보존합니다.')
            if saved and saved.get('source_identity') != source_sha:
                history = state.setdefault('source_history', {}).setdefault(card, {})
                history[saved['source_identity']] = copy.deepcopy(saved)
                saved = copy.deepcopy(history.get(source_sha) or {})
                state['cuts'][card] = saved
                save(state_path, state)
            stem = focus_key + '.' + source_sha
            text_path = root / (stem + '.text.json')
            raw_path = root / (stem + '.original.json')
            # Upgrade fixed-name local evidence only when its own source bytes
            # match. Never move/delete the old receipt or reuse it for new bytes.
            old_raw = root / (focus_key + '.original.json')
            if not raw_path.exists() and old_raw.exists():
                old_row = _read(old_raw)
                if old_row.get('source_identity') == source_sha:
                    if saved.get('original_sha256') and file_digest(old_raw) != saved['original_sha256']:
                        raise R.StepError('이전 로컬 피사체 원본 기록이 변경됐습니다.')
                    save(raw_path, old_row)
                    saved = dict(saved, focus_key=focus_key, source_identity=source_sha,
                                 original_sha256=file_digest(raw_path), phase=saved.get('phase') or 'selected')
                    state['cuts'][card] = saved
                    save(state_path, state)
                    old_text = root / (focus_key + '.text.json')
                    if not text_path.exists() and old_text.exists():
                        old_receipt = _read(old_text)
                        if (old_receipt.get('binding') or {}).get('source_identity') == source_sha:
                            save(text_path, old_receipt)
            if text_path.exists() and _receipt_refused(_read(text_path)):
                out['status'] = 'blocked'
                out['diagnostics'][card] = {'code':'provider_refused','automatic_retry':False}
                return out
            if saved.get('phase') == 'selection_inflight':
                cache_only.add(card)
            # 끊긴 컷도 사람이 «다시» 를 알리면 이어 잰다(아래에서 원본 행이 없으면 다시 묻고, 있으면 화면 글자 검수부터).
            if card not in retry and (saved.get('phase') == 'inflight'
                                      or (saved.get('phase') == 'text_inflight' and not text_path.exists())):
                out['diagnostics'][card] = {'code': 'local_focus_interrupted', 'automatic_retry': False}
                continue
            row = None
            if raw_path.exists() and saved.get('original_sha256'):
                if file_digest(raw_path) != saved['original_sha256']:
                    raise R.StepError('로컬 피사체 원본 기록이 변경됐습니다. 덮어쓰지 않습니다.')
                row = _read(raw_path)
            if row is None and focus_key in legacy and not legacy[focus_key].get('source_identity'):
                cache_only.add(card)
            if row is None and focus_key in legacy and legacy[focus_key].get('source_identity') == source_sha:
                row = legacy[focus_key]
                save(raw_path, row)
                saved = dict(saved, focus_key=focus_key, source_identity=source_sha,
                             original_sha256=file_digest(raw_path), phase='selected', reply_key='')
                state['cuts'][card] = saved; save(state_path, state)
            # 막힌 컷은 사람이 «다시» 를 알린 경우(retry)에만 다시 잰다 — 아니면 저장된 진단을 돌려준다(자동 재시도 금지).
            #   저장된 진단은 지금 규칙으로 다시 말한다(_block_diagnostic): 옛 실행기는 결과 없이 끝난 실행 실패도
            #   «selection_invalid · source_size_invalid·source_file_changed» 로 적었다(2026-10-15 쇼핑 신고) — 그대로 돌려주면
            #   서버가 «다시» 표식을 주지 않아 신고자가 영영 못 푼다. 다시 말한 진단이 다르면 상태 파일도 고쳐 적는다.
            #   다시 잴 때 옛 원본 행은 지우지 않는다: 새 행을 쓸 때 original-<지문>.json 으로 옮겨 둔다(아래 missing 처리).
            #   full_frame 을 준 경우: 다시 재도 같은 판정인 막힘(FULL_FRAME_CODES)은 «다시» 를 알렸어도 다시 묻지 않고 전체 화면으로 끝낸다.
            if saved.get('phase') == 'blocked' and not _budget_can_resume(
                    saved.get('diagnostic', {}).get('review_budget_blocked'), selection['review_policy']) and (
                    card not in retry or (full_frame is not None and _full_frame_eligible(saved.get('diagnostic')))):
                diagnostic = (_block_diagnostic(K, cut, row, focus_key, source_sha) if row is not None
                              else _rowless_diagnostic(saved['diagnostic']))
                if diagnostic is not None:
                    if diagnostic != saved['diagnostic']:
                        saved['diagnostic'] = diagnostic; save(state_path, state)
                    if full_frame is not None and _full_frame_eligible(diagnostic):
                        fallen[card] = (cut, row, diagnostic['code'])
                        continue
                    if card not in retry:
                        out['diagnostics'][card] = diagnostic
                        continue
                    # «다시» 를 알린 컷의 진단이 지금 규칙으로는 다시 잴 막힘이다 — 상태는 blocked 그대로, 아래에서 다시 묻는다.
                else:
                    # 저장된 막힘이 거짓 사유뿐이었다(행은 유효) — 이미 검사했으니 아래에서 다시 검사하지 않는다.
                    saved['phase'] = 'selected'; saved.pop('diagnostic', None); save(state_path, state)
                    checked.add(card)
            # 다시 묻는 경우: 행이 없다 · 사람이 «다시» 를 알린 컷의 결과 없는 행(실행 실패·끊김·대기·결과 빠짐) · 예산이 늘었다 ·
            #   답이 바뀐 대기 · 엔진 실패를 가르기 전(옛 실행기)에 저장된 대기 행(한 번만 — 새 행에는 ENGINE_ROWS 가 적힌다).
            # 선택 뒤 검출 모델·환경이 바뀐 행(실행기 갱신으로 framevision 이 바뀜) — 지금 환경에서 그 컷을 다시 고른다(옛 원본 행은 아래에서
            #   original-<지문>.json 으로 남는다 · 새 행은 지금 지문을 적어 다음 실행에는 바뀐 것이 아니다 — 실행마다 많아야 한 번).
            #   예전에는 아래 verify_selection_runtime 이 «재확인해야 합니다» 로 멈추기만 해 다시 고를 길이 없었다
            #   (10-21 뇌전구 render_plan 신고 · 한 주 9건·4명 · 사장님 «반려가 아니라 정상 실행»).
            if (row is None or runtime_stale(row, runtime_now)
                    or (card in retry and (saved.get('phase') in ('blocked', 'inflight', 'queued', 'selection_inflight')
                                           or _execution_failure(row) or row.get('focus_status') == 'pending'))
                    or _budget_can_resume(row.get('review_budget_blocked'), selection['review_policy'])
                    or (row.get('focus_status') == 'pending'
                        and (saved.get('reply_key') != reply_key or saved.get('engine_rows') != ENGINE_ROWS))):
                state['cuts'][card] = dict(saved, focus_key=focus_key, source_identity=source_sha,
                                          phase='queued', reply_key=reply_key)
                missing.append(cut)
            elif row.get('focus_status') == 'pending':
                out['review_requests'].extend(row.get('review_requests') or [])
                waiting.add(card)
            else:
                loaded[card] = row
        denied = [card for card,row in loaded.items() if _refused(row)]
        if denied and full_frame is None:
            out['status'] = 'blocked'
            out['diagnostics'].update({card:{'code':'provider_refused','automatic_retry':False} for card in denied})
            save(state_path,state)
            return out
        for card in denied:
            # 지난 실행에 거부된 컷(저장된 거부 행) — 그 컷만 다시 묻지 않고 전체 화면으로 끝낸다. 그 거부는 이 실행에서 본 것이
            #   아니므로 다른 컷의 판정은 막지 않는다(거부가 이어지면 그 요청이 이 실행의 거부가 되어 아래에서 멈춘다).
            fallen[card] = (by_card[card], loaded.pop(card), 'provider_refused')
        verify_selection_runtime(loaded.values(), runtime_now)
        if missing:
            for cut in missing:state['cuts'][str(cut['card'])]['phase'] = 'selection_inflight'
            # Use the existing batch scheduler, rate guards, and paid receipts.
            # Never create a second per-cut scheduling loop around this call.
            save(state_path, state)
            # 사람이 «다시» 를 알린 컷은 저장된 기록만 읽는 복구(recover)로 보내지 않는다 — 다시 묻는 것이 그 지시다.
            recover = [c for c in missing if str(c['card']) not in retry and (
                legacy_all_missing or str(c['card']) in legacy_missing or str(c['card']) in cache_only)]
            fresh = [c for c in missing if c not in recover]
            selected = {}
            if recover:
                # A server reference is not permission to repeat a model call.
                # Existing selector cache/receipt recovery runs without new calls.
                selected.update(F.select_subjects(dict(selection, cuts=recover, saved_reviews_only=True), headers=headers))
            if fresh and not any(_refused(row) for row in selected.values()):
                # retry_cards — 그 컷의 작업 동안만 끝나지 않은 검수 영수증(보냈는데 끝 모름·결과 없이 끝남·모델을 띄웠다가 결과
                #   없음)을 한 번 놓아 주고 새로 묻게 한다(volcano_run.review_retry_scope). 사람이 «다시» 를 안 알린 컷은 자동 반복하지 않는다.
                again = sorted(str(c['card']) for c in fresh if str(c['card']) in retry)
                selected.update(F.select_subjects(dict(selection, cuts=fresh, **({'retry_cards': again} if again else {})),
                                                  headers=headers))
            for cut in missing:
                card = str(cut['card']); saved = state['cuts'][card]
                if card not in selected:
                    saved['phase'] = 'queued'
                    save(state_path,state)
                    continue
                row = selected[card]; raw_path = root / (saved['focus_key'] + '.' + saved['source_identity'] + '.original.json')
                if raw_path.exists():
                    prior = _read(raw_path)
                    if prior != row:
                        save(root / (saved['focus_key'] + '.' + saved['source_identity'] + '.original-' + _hash(prior) + '.json'), prior)
                save(raw_path, row)
                saved.update(original_sha256=file_digest(raw_path), phase='selected', engine_rows=ENGINE_ROWS)
                save(state_path, state); loaded[card] = row
        denied = [card for card,row in loaded.items() if _refused(row)]
        if denied and full_frame is None:
            out['status'] = 'blocked'
            out['diagnostics'].update({card:{'code':'provider_refused','automatic_retry':False} for card in denied})
            return out
        for card in denied:
            # 이 실행의 판정 중 거부 — 그 컷은 전체 화면, 아직 판정하지 않은 컷도 다시 묻지 않고 전체 화면으로 끝낸다(6-2).
            fallen[card] = (by_card[card], loaded.pop(card), 'provider_refused'); refusal = True
        verify_selection_runtime(loaded.values(), runtime_now)
        for cut in cuts:
            card = str(cut['card'])
            if card not in loaded:continue
            focus_key = K.cut_key(cut); source_sha = source_hashes[cut['src']]
            row = loaded.pop(card); saved = state['cuts'][card]
            stem = focus_key + '.' + source_sha
            final_path = root / (stem + '.json')
            if row.get('focus_status') == 'pending':
                out['review_requests'].extend(row.get('review_requests') or [])
                waiting.add(card)
                continue
            diagnostic = None if card in checked else _block_diagnostic(K, cut, row, focus_key, source_sha)
            if diagnostic is not None:
                saved.update(phase='blocked', diagnostic=diagnostic); save(state_path, state)
                if full_frame is not None and _full_frame_eligible(diagnostic):
                    fallen[card] = (cut, row, diagnostic['code'])
                else:
                    out['diagnostics'][card] = diagnostic
                continue
            protected = row
            evidence = None
            if cut['kind'] != 'image':
                count = K.frame_count(cut)
                plan = K.plan_cut(cut['start'], count, cut['fps'], row['scene_evidence'],
                                  preserve_audio=True,
                                  source_duration=cut.get('source_duration') or cut['start'] + count / cut['fps'])
                K.plan_filter(plan)
                protected = K.protected_measurement(row, plan)
                evidence = K.video_text_binding(protected)
            if evidence:
                config = item['text_review']['photo_review']
                binding = {'evidence': evidence,
                           'cut': {k: cut[k] for k in ('src', 'kind', 'start', 'duration', 'fps',
                                   'seek_mode', 'video_timing', 'frame_argv', 'tracking_probe_argv') if k in cut},
                           'review': config, 'policy': item['text_review']['policy']}
                request_key = _hash(binding)
                text_path = root / (stem + '.text.json')
                receipt = _read(text_path) if text_path.exists() else None
                prior_text = legacy_text.get(card)
                if receipt is None and isinstance(prior_text,dict) and prior_text.get('key') == request_key:
                    receipt = prior_text
                    save(text_path, receipt)
                if not K.video_text_receipt(receipt, evidence):
                    # 다시 묻는 경우: 영수증이 없다 · 사람이 «다시» 를 알린 컷의 실행 실패 영수증 · 답이 바뀐 대기 ·
                    #   엔진 실패를 가르기 전(옛 실행기)에 저장된 대기 영수증(한 번만 — 새 영수증에는 ENGINE_ROWS 가 적힌다).
                    rerun = (not receipt or (card in retry and _text_execution_failure(receipt))
                             or (receipt.get('status') == 'pending'
                                 and (saved.get('text_reply_key') != reply_key
                                      or saved.get('text_engine_rows') != ENGINE_ROWS)))
                    if not rerun:
                        if receipt.get('status') == 'pending':
                            out['review_requests'].extend(receipt.get('review_requests') or [])
                            waiting.add(card)
                        else:
                            out['diagnostics'][card] = _text_diagnostic(receipt, focus_key, cut, source_sha)
                        continue
                    saved.update(phase='text_inflight', text_reply_key=reply_key); save(state_path, state)
                    settings = {k: selection[k] for k in ('review_policy', 'focus_review_replies', 'review_budget') if k in selection}
                    with R.review_retry_scope(card in retry, retry_registry):
                        reviewed = R.review_film_frames(dict(settings, preserved_video_text_review=True,
                            cuts=[dict(card=card, key=request_key, binding=binding)], photo_review=config,
                            allow_provider=not selection.get('saved_reviews_only',False), engine_failure_rows=True,
                            out_dir=str(native_path(selection['out_dir']).parent / 'video-text')), headers=headers)
                    receipt = reviewed[card]; save(text_path, receipt)
                    saved.update(phase='selected', text_engine_rows=ENGINE_ROWS); save(state_path, state)
                    if _receipt_refused(receipt):
                        out['status'] = 'blocked'
                        out['diagnostics'][card] = {'code':'provider_refused','automatic_retry':False}
                        return out
                    if not K.video_text_receipt(receipt, evidence):
                        if receipt.get('status') == 'pending':
                            out['review_requests'].extend(receipt.get('review_requests') or [])
                            waiting.add(card)
                        else:out['diagnostics'][card] = _text_diagnostic(receipt, focus_key, cut, source_sha)
                        continue
                protected = dict(protected, video_text_review=receipt)
            # Detect replacement during processing before publishing an accepted
            # receipt. It is not permission to reuse an old model response.
            if file_digest(native_path(cut['src'])) != source_sha:
                raise R.StepError('검수 도중 원본 파일이 변경됐습니다. 기존 기록은 보존합니다.')
            save(final_path, protected)
            meta = dict(focus_key=focus_key, path=item['out_dir'].rstrip('/')+'/'+stem+'.json', sha256=file_digest(final_path), source_identity=source_sha)
            saved.update(phase='complete', receipt=meta); save(state_path, state)
            out['receipts'][card] = meta
        if full_frame is not None:
            if refusal:
                # 거부 뒤 이 실행에서 판정하지 않은 컷 — 다시 묻지 않고 전체 화면으로 끝낸다(인물형 롱폼과 같은 규칙).
                for cut in cuts:
                    card = str(cut['card'])
                    if (card not in out['receipts'] and card not in out['diagnostics'] and card not in waiting
                            and card not in fallen):
                        fallen[card] = (cut, None, NOT_STARTED_AFTER_REFUSAL)
            for card, (cut, row, cause) in fallen.items():
                focus_key = K.cut_key(cut); source_sha = source_hashes[cut['src']]
                stem = focus_key + '.' + source_sha
                final_path = root / (stem + '.json')
                receipt = full_frame_row(cut, focus_key, source_sha, full_frame, cause, row)
                errors = K.validate(cut, receipt)
                if errors:
                    raise R.StepError('전체 화면 영수증이 검사를 통과하지 못했습니다(' + ', '.join(errors) + '). 실행기 판을 확인하세요.')
                # 원본 지문은 위에서 잰 것을 쓴다(다시 재지 않는다) — 계획 끝에 렌더 계획이 원본 전체를 한 번 다시 재서 바뀜을 막는다.
                # 판정 원본 행(.original.json)·상태 기록은 그대로 둔다 — 이 파일은 그 행에서 매번 같은 값으로 다시 만들어진다.
                save(final_path, receipt)
                out['receipts'][card] = dict(focus_key=focus_key, path=item['out_dir'].rstrip('/')+'/'+stem+'.json',
                                             sha256=file_digest(final_path), source_identity=source_sha)
            out['full_frame'] = {card: cause for card, (_, _, cause) in sorted(fallen.items())}
            # 이 실행에서 거부를 봤다 — 부르는 쪽(렌더 계획)도 이 실행에서는 새 검수 요청을 보내지 않는다(6-2).
            out['full_frame_refusal'] = refusal
        # 영수증·진단·검수 대기 어느 것도 없이 빠진 컷(선택 결과가 오지 않아 queued 로 남은 컷) — 그 컷 번호로 말한다.
        #   컷 번호가 있어야 서버의 «다시» 표식이 그 컷을 다시 잰다('_contract' 같은 이름 없는 진단은 다시 잴 대상이 없어
        #   같은 막힘만 되풀이했다 · 2026-10-15 검토).
        for cut in cuts:
            card = str(cut['card'])
            if card not in out['receipts'] and card not in out['diagnostics'] and card not in waiting:
                out['diagnostics'][card] = {'code': 'local_focus_results_missing', 'automatic_retry': False}
        if out['diagnostics']:out['status'] = 'blocked'
        elif out['review_requests']:out['status'] = 'pending'
        return out


def preserve_wire_evidence(payload, *, out_dir=None):
    """Durably preserve legacy dense fields before omitting them from an RPC copy.

    Caller negotiates local_focus_version=1 first. The original checkpoint object
    is never modified. Failure to publish stops before transmitting anything.
    """
    from longform_state import native_path, save
    from film_editor import file_digest
    import volcano_run as R
    fields = ('frames', 'focus_frames', 'focus_measurements', 'focus_recovery',
              'focus_state', 'video_text_state', 'video_text_results', '_focus_pack', '_focus_recovery_pack',
              'photo_text_state', 'photo_text_results', 'focus_render_key')
    evidence = {k:payload[k] for k in fields if k in payload}
    if not evidence:return payload
    root = native_path(out_dir or Path(payload['workdir']) / 'geumbit' / 'focus')
    root.mkdir(parents=True, exist_ok=True)
    with R.review_receipt_lock(str(root / 'local-focus-execution')):
        name = 'legacy-' + _hash(evidence) + '.json'
        path = root / name
        if path.exists():
            if _read(path) != evidence:raise R.StepError('이전 피사체 기록이 변경됐습니다. 덮어쓰지 않습니다.')
        else:save(path, evidence)
        index_path = root / 'legacy-index.json'
        index = _read(index_path) if index_path.exists() else {'records': []}
        record = {'file': name, 'sha256': file_digest(path)}
        if record not in index['records']:
            index['records'].append(record);save(index_path, index)
    return {k:v for k,v in payload.items() if k not in fields}


def verify_render_receipt(settings, selected):
    """Verify local receipt bytes and full rules immediately before rendering.

    Historical server-issued receipts keep their historical consumer checks.
    Newly local-issued receipts must carry this contract; no boolean approval
    substitutes for the preserved measurements or source-bound validation.
    """
    proof = settings.get('local_focus')
    if proof is None:return
    import focus_kernel as K
    from longform_state import native_path
    from film_editor import file_digest
    if (not isinstance(proof, dict) or set(proof) != {'version', 'kernel_id', 'contract_key', 'sha256'}
            or type(proof.get('version')) is not int or proof['version'] != 1
            or proof.get('kernel_id') != K.KERNEL_ID
            or any(not isinstance(proof.get(k),str) or len(proof[k]) != 64
                   or any(c not in '0123456789abcdef' for c in proof[k]) for k in ('contract_key','sha256'))):
        raise ValueError('local focus renderer contract differs from installed kernel')
    path = native_path(settings['focus_receipt'])
    if file_digest(path) != proof['sha256'] or _read(path) != selected:
        raise ValueError('local focus receipt bytes changed before rendering')
    contract = _read(path.parent / (proof['contract_key'] + '.contract.json'))
    if (contract.get('version') != 1 or contract.get('kernel_id') != K.KERNEL_ID
            or contract.get('contract_key') != proof['contract_key']):
        raise ValueError('local focus recipe differs from renderer contract')
    cuts = [c for c in contract['cuts'] if c.get('focus_key') == settings['focus_key']]
    if len(cuts) != 1:raise ValueError('local focus receipt has no unique bound cut')
    errors = K.validate(cuts[0], selected)
    if errors:raise ValueError('local focus receipt validation: '+', '.join(errors))
    verify_selection_runtime([selected])
    evidence = K.video_text_binding(selected)
    if evidence and not K.video_text_receipt(selected.get('video_text_review'), evidence):
        raise ValueError('local focus OCR review is incomplete')
