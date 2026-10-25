"""Durable local TTS geometry/OCR planning; only compact receipts leave this PC."""
import copy
import hashlib
import json


#: 계약 지문에서 빼는 «실행 보조» 칸 — 서버 volcano_local_render.EXECUTION_ONLY_SELECTION 에 «다시» 표식 칸을 더한 것
#:   (그 칸은 서버가 지문을 정한 뒤 싣는다). local_source_plan 도 이것을 쓴다. framevision_cache = 측정 캐시 자리(2026-10-22).
EXECUTION_ONLY_SELECTION = ('focus_review_replies', 'review_budget', 'parallel', 'agy_parallel', 'framevision_cache',
                            'focus_retry_cards')


def _bytes(value):
    # Keep ordinary UTF-8 output byte-identical; escape a historical unpaired
    # surrogate as valid JSON so preserved accepted evidence can be read back.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8', 'backslashreplace')


def _semantic(task):
    value = copy.deepcopy(task)
    for key in ('out_dir', 'files', 'contract_key'):
        value.pop(key, None)
    selection = value['selection']
    # focus_retry_cards — 사람이 «다시» 를 알린 한 번 실행 지시(서버 volcano_local_render.consume 이 계약 지문을 정한 뒤 싣는다).
    for key in EXECUTION_ONLY_SELECTION:
        selection.pop(key, None)
    selection['review_policy'].pop('max_requests', None)
    return value


def _read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _absolute(value, wd):
    import local_photo_plan as P
    return P.norm_abs(value if P.is_abs_path(value) else wd+'/'+value)


def _build(task, rows, payload):
    import render_kernel as K
    from local_photo_plan import PhotoPlan
    images = {}
    for usage, source, _ in task['uses']:
        row = rows[str(usage)]
        box = row['framing_subject']['bbox']
        entry = images.setdefault(source, dict(task['metadata'][str(usage)], focus_by_usage={}))
        entry.update(w=row['size'][0], h=row['size'][1],
                     cx=(box[0]+box[2]/2)/row['size'][0], cy=(box[1]+box[3]/2)/row['size'][1])
        entry['focus_by_usage'][str(usage)] = row
    selection = task['selection']
    settings = {k:selection[k] for k in ('review_policy','focus_review_replies','review_budget') if k in selection}
    plan = PhotoPlan(payload, task['cuts'], rows, task['metadata'], task['workdir'],
                     task['text_review']['photo_review'], settings)
    spec = task['spec']; fps = float(spec.get('FPS') or 30)
    kb = bool(spec.get('KB_MOVE_FRAME_PCT')) and bool(spec.get('KB_PAN_PX_S'))
    memes = {int(k):v for k,v in task['memes'].items()}
    args = (task['timing'], task['imgdir'], memes, images, task['meme_geom'], spec)
    try:
        parts = K.build_parts_kb(*args, card_bg_image=task['card_bg'], text_review=plan.callback) if kb else K.build_parts(*args, text_review=plan.callback)
    except KeyError as error:
        import volcano_run as R
        key = str(error.args[0] if error.args else '')
        if key == 'img':
            raise R.StepError(
                '어떤 그룹에 `img`(이미지 슬롯번호)도 배정된 밈도 없습니다. '
                '모든 그룹에 `img` 를 주거나, 밈 자리는 `memes` 단계의 기존 배정을 '
                '그대로 넣어 주세요. 기존 결과물과 검수 증거는 보존되어 있습니다.') from error
        raise R.StepError(
            f'로컬 렌더 계획에서 원본 {key!r}의 측정 정보를 찾지 못했습니다. '
            '기존 원본 파일과 timing.groups·memes의 파일 연결을 확인하고 '
            '같은 render_plan 단계에서 해당 원본을 다시 측정하세요. '
            'payload.images에 크기나 좌표를 지어 넣지 마세요. '
            '기존 이미지·밈·음성·검수 증거를 삭제하거나 다시 생성할 필요는 없습니다.') from error
    state = plan.finish()
    if state['status'] != 'complete':
        # diagnostics 는 «컷 → 진단» 지도다(서버가 컷마다 code·reason 을 읽고 photo_text_diagnostics 로 보인다). 고칠 안내는 그 지도에
        #   섞지 않는다 — 제 칸(local_photo_plan.PHOTO_TEXT_GUIDANCE_KEYS)으로 서버까지 간다(prepare_local_render_plan).
        return plan, state, None
    grid = bool(spec.get('FRAME_GRID'))
    frames = K.pack_frame_runs(K.seq_frames(parts, fps, task['timing']['total']), frame_guard=plan.frame_guard) if grid else [dict(src=p['src'],dst=p['dst'],**K.frame_transform(p)) for p in parts]
    warnings = ['피사체 중심 배치가 원본 경계에서 조정되었습니다: '+str(f['_anchor_clamped']) for f in frames if isinstance(f.get('_anchor_clamped'),dict)]
    # 주피사체를 정하지 못했거나 거부된 컷 — 판정을 다시 묻지 않고 확대 없이 전체 화면으로 넣었다(local_focus.full_frame_row).
    #   영수증 행에서 유도한다 — 계획을 다시 검증할 때(verify_local_render_plan)도 같은 글이 나온다.
    from local_focus import full_frame_cause
    fallen = sorted((str(card), cause) for card, row in rows.items() if (cause := full_frame_cause(row)))
    if fallen:
        warnings.append('주피사체를 확정하지 못한 컷은 확대 없이 전체 화면으로 넣었습니다(판정을 다시 묻지 않음): '
                        + ', '.join(f'{card}({cause})' for card, cause in fallen))
    for row in parts+frames:
        row.pop('_photo_usage', None)
    for frame in frames:
        for key in ('src','dst','dstf'):
            if key in frame:
                frame[key] = _absolute(frame[key], task['workdir'])
        if frame.get('src') == task['workdir']+'/black.png' and 'black' in task['files']:
            frame['src'] = task['files']['black']
    concat_parts = copy.deepcopy(parts)
    # Grid concat is informational, but remains usable from its immutable folder.
    if grid:
        for part in concat_parts:
            part['dst'] = _absolute(part['dst'], task['workdir'])
    blobs = {'frames':json.dumps(frames,ensure_ascii=False,allow_nan=False).encode(),
             'concat':K.vconcat_text(concat_parts,task['workdir'],fps=fps if grid else None).encode()}
    if 'black' in task['files']:
        blobs['black'] = K.black_png(*K.black_intro_geometry(spec)['resize'])
    return plan, state, dict(blobs=blobs, counts={'frames':int(round(float(task['timing']['total'])*fps)) if grid else len(frames),
        'parts':len(parts),'runs':len(frames)},warnings=warnings)


def _validate_task(task):
    import local_compute_identity as I
    import focus_kernel as F
    import volcano_run as R
    I.verify()
    if task.get('version') != 1 or task.get('mode') != 'tts' or task.get('kernel_id') != I.LOCAL_COMPUTE_ID or task.get('focus_kernel_id') != F.KERNEL_ID:
        raise R.StepError('로컬 렌더 규격과 설치된 계산 코드가 다릅니다. 기존 증거를 보존하고 실행기를 갱신하세요.')
    if hashlib.sha256(_bytes(_semantic(task))).hexdigest() != task.get('contract_key'):
        raise R.StepError('로컬 렌더 규격 내용과 식별자가 다릅니다.')
    root = task['workdir']+'/local-render/'+task['contract_key']
    expected = {'frames':root+'/render_frames.json','concat':root+'/vconcat.txt','receipt':root+'/planner_receipt.json'}
    if task['card_bg'] is False:expected['black']=root+'/black.png'
    if task.get('out_dir') != root or task.get('files') != expected:
        raise R.StepError('로컬 렌더 결과 경로가 규격과 다릅니다.')



def _legacy_photo(task):
    from longform_state import native_path
    from film_editor import file_digest
    import volcano_run as R
    root = native_path(task['workdir']+'/local-render/evidence')
    index = root/'legacy-index.json'
    results = {}; missing = False
    if index.exists():
        for entry in _read(index).get('records', []):
            path = root/entry['file']
            if file_digest(path) != entry['sha256']:
                raise R.StepError('보존한 이전 사진 검수 기록의 지문이 다릅니다.')
            prior = R.unfold_payload(_read(path))
            state = prior.get('photo_text_state') or {}
            if R._blob_is_marker(state):
                missing = True
                state = {}
            for value in (state.get('results') or {}, prior.get('photo_text_results') or {}):
                if R._blob_is_marker(value):
                    missing = True
                    continue
                for card, receipt in value.items():
                    if R._blob_is_marker(receipt):missing = True
                    elif isinstance(receipt,dict):results[str(card)] = receipt
    return results,missing

def _source_versions(task):
    from film_editor import file_digest
    from longform_state import native_path
    # ★없는 원본은 파이썬 FileNotFoundError(윈도우 긴 경로 머리 `\\?\` 가 붙은 글자) 대신 어느 칸인지 말한다 (2026-10-17 실행기 중단
    #   보고 · 뇌전구 render_plan img43 11건·3명). 그림 칸은 images 단계가 만든 자리다 — images 를 다시 부르면 이미 있는 칸은
    #   그대로 두고 빠진 칸만 만든다. 팩 파일(밈·페페)은 서버가 이 단계 앞에 «없을 때만 다시 확보» 를 싣는다(_attach_render_packs).
    gone = sorted({cut['src'] for cut in task['cuts'] if not native_path(cut['src']).exists()})
    if gone:
        import volcano_run as R
        shown = ' · '.join(gone[:5]) + (f' 외 {len(gone) - 5}개' if len(gone) > 5 else '')
        slots = [g for g in gone if '/img43/' in g.replace('\\', '/')]
        if slots:
            # 처방이 «images 다시» 하나뿐이다 — 사람에게 시키지 않고 구동기가 images 로 한 번 돌아간다(같은 빠진 칸에 한 번 · StepBack).
            #   (10-19 0시 한 사람이 같은 칸 01 로 15초에 6번 멈춤 보고 — 사람 차례로 되풀이했다.) 다시 만든 뒤에도 없으면 이 글로 멈춘다.
            raise R.StepBack(f'굽기에 쓸 원본 {len(gone)}개가 작업 폴더에 없습니다: {shown}\n  '
                             '그림 칸은 images 단계가 만드는 자리입니다 — 실행기는 images 로 한 번 돌아가 이미 있는 칸은 두고 빠진 칸만 만듭니다. '
                             '그 뒤에도 이 글이 나오면 images 가 그 칸을 실패로 끝냈거나 그 그림을 옮기거나 지운 것입니다 — images 의 그 칸 결과를 확인하세요.',
                             'images', tuple(gone))
        raise R.StepError(f'굽기에 쓸 원본 {len(gone)}개가 작업 폴더에 없습니다: {shown}\n  '
                          '같은 작업 폴더에서 assets 단계부터 다시 실행하면 팩 파일을 다시 풉니다.')
    return {cut['src']:file_digest(native_path(cut['src'])) for cut in task['cuts']}


def _source_changed(current):
    import volcano_run as R
    error = R.StepError('원본 파일 바이트가 변경됐습니다. 이전 계획·검수·음성은 보존하고 새 원본 버전의 로컬 계획부터 준비합니다.')
    error.code = 'local_source_changed'
    error.execution_recovery = {'local_render_plan_result': None, 'local_source_versions': current}
    error.execution_next_step = 'render_plan'
    return error


def _import_legacy_plan(task, current, identities):
    """Copy a verified pre-source-version plan without any provider work.
    옛 계획의 피사체 행이 지금과 다른 검출 모델·환경에서 골라졌으면 옮기지 않는다(None) — 아래 local_focus 가
    그 컷을 «selection_runtime_changed» 로 돌려주고 사람이 «다시» 를 알리면 지금 환경에서 다시 고른다."""
    from longform_state import native_path, save
    from film_editor import atomic_bytes, file_digest
    old = copy.deepcopy(task)
    old.pop('source_versions', None)
    old['contract_key'] = hashlib.sha256(_bytes(_semantic(old))).hexdigest()
    old['out_dir'] = old['workdir']+'/local-render/'+old['contract_key']
    old['files'] = {k:old['out_dir']+'/'+v.rsplit('/',1)[-1] for k,v in old['files'].items()}
    path = native_path(old['files']['receipt'])
    if not path.exists():return None
    receipt = _read(path)
    if receipt.get('sources') != current:return None
    if _receipt_runtime_stale(path, identities):return None
    verify_local_render_plan(old, identities=identities)
    rows = {str(c['card']):_read(native_path(receipt['focus']['receipts'][str(c['card'])]['path'])) for c in task['cuts']}
    _, state, built = _build(task, rows, copy.deepcopy(receipt['photo']))
    if built is None:
        import volcano_run as R
        raise R.StepError('보존된 이전 계획의 검수 답으로 새 원본 버전 계약을 복원하지 못했습니다.')
    latest = _source_versions(task)
    if latest != current:raise _source_changed(latest)
    focus = copy.deepcopy(receipt['focus']);focus['contract_key']=task['contract_key']
    for card,meta in focus['receipts'].items():
        target=task['out_dir']+'/focus/'+meta['focus_key']+'.'+meta['source_identity']+'.json'
        atomic_bytes(native_path(target),native_path(meta['path']).read_bytes())
        meta.update(path=target,sha256=file_digest(native_path(target)))
    result=copy.deepcopy(receipt['result']);result['contract_key']=task['contract_key']
    result['files']={};result.update(counts=built['counts'],warnings=built['warnings'])
    for name,blob in built['blobs'].items():
        atomic_bytes(native_path(task['files'][name]),blob)
        result['files'][name]=dict(path=task['files'][name],sha256=hashlib.sha256(blob).hexdigest())
    updated=dict(receipt,task=task,focus=focus,result=result)
    save(native_path(task['files']['receipt']),updated)
    result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
    return result


def _photo_text_execution_failed(receipt):
    """사진 글자 검수가 판정 없이 끝났고 다시 재면 달라질 수 있는가 — 화면 글자 검수와 같은 자(local_focus._text_execution_failure)."""
    from local_focus import _text_execution_failure
    return _text_execution_failure(receipt)


def _photo_text_retry(task, payload):
    """서버가 실은 «다시» 컷(focus_retry_cards) 중 사진 글자 검수가 실행 실패로 끝난 것 → 그 영수증을 payload 에서 뺀다(다시 검수할 차례).
    돌려주는 값: 뺀 사용 번호 목록(없으면 빈 목록 — 아무것도 바꾸지 않는다)."""
    from local_focus import RETRY_SELECTION_KEY
    retry = task['selection'].get(RETRY_SELECTION_KEY)
    results = payload.get('photo_text_results')
    if not isinstance(retry, dict) or not isinstance(results, dict):
        return []
    again = sorted(u for u in retry if _photo_text_execution_failed(results.get(u)))
    if again:
        payload['photo_text_results'] = {u: r for u, r in results.items() if u not in again}
    return again


def _photo_text_diagnostics(diagnostics, payload):
    """막힌 사진 글자 검수 진단 — 실행 실패 컷은 «결과 없음»(selection_execution_failed · 다시 잴 수 있음)으로 말한다.
    서버는 이 코드에만 «다시» 표식(focus_retry)을 준다(volcano_local_render._retryable). 판정·거부 진단은 그대로 둔다."""
    from local_focus import _REASON_CHARS
    results = payload.get('photo_text_results') or {}
    out = {}
    for usage, value in (diagnostics or {}).items():
        receipt = results.get(usage)
        if _photo_text_execution_failed(receipt):
            reason = receipt.get('reason') if isinstance(receipt.get('reason'), str) else ''
            out[usage] = {'code': 'selection_execution_failed', 'stage': 'photo_text_review',
                          'failure_code': str(receipt.get('code')), 'reason': reason[:_REASON_CHARS], 'automatic_retry': False}
        else:
            out[usage] = value
    return out


def _full_frame_aspect(task):
    """TTS 렌더 계획(정지 그림 컷)의 출력 비율 = 그림 슬롯(SLOT_W×SLOT_H · render_kernel._image_box 가 쓰는 그 값).
    주피사체 판정이 같은 답만 내는 막힘(판정 불가·거부)은 그 컷만 이 비율의 전체 화면으로 끝낸다 — 소재를 바꿀 길이 없는
    채널이라 «소재를 바꾸라» 는 막다른 길이었다(2026-10-17). 비율이 없거나 그림이 아닌 컷이 있으면 예전대로 막는다."""
    spec = task.get('spec') or {}
    slot = (spec.get('SLOT_W'), spec.get('SLOT_H'))
    if (any(type(v) not in (int, float) or v <= 0 for v in slot)
            or any(cut.get('kind') != 'image' for cut in task['cuts'])):
        return None
    return slot



def _receipt_runtime_stale(receipt_path, identities):
    """저장된 계획의 피사체 행이 지금과 다른 검출 모델·환경에서 골라졌나(local_focus.runtime_stale · 뿌리마다 지문 한 번).
    기록을 못 읽으면 False — 그때는 verify_local_render_plan 이 제 사유로 멈춘다(여기서 삼키지 않는다)."""
    import local_focus as F
    from longform_state import native_path
    try:
        receipts = _read(receipt_path)['focus']['receipts']
        rows = [_read(native_path(meta['path'])) for meta in receipts.values()]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    return any(F.runtime_stale(row, identities) for row in rows)


def reusable_receipt(receipt_path, identities):
    """저장된 계획 영수증을 그대로 확인해 쓸 수 있나 — 없으면 False · 지금과 다른 검출 환경의 피사체 행을 품었으면 옆 이름으로 남기고
    False(부르는 쪽이 바뀐 컷만 지금 환경에서 다시 고른다 · local_focus.prepare_local_focus). 뇌전구·쇼핑·재더빙 로컬 계획이 함께 쓴다."""
    if not receipt_path.exists():return False
    if not _receipt_runtime_stale(receipt_path, identities):return True
    _set_aside(receipt_path)
    return False


def _set_aside(receipt_path):
    """옛 환경의 계획 영수증을 지우지 않고 옆 이름(<이름>.stale-<지문>)으로 옮긴다 — 아래가 지금 환경에서 다시 고르고 다시 짓는다.
    (10-21 뇌전구 render_plan 신고: 영수증이 있으면 검증만 해서 «검출 모델·환경이 바뀌었습니다» 로 멈추고 다시 지을 길이 없었다.)"""
    import os
    from film_editor import file_digest
    os.replace(receipt_path, receipt_path.with_name(receipt_path.name + '.stale-' + file_digest(receipt_path)[:16]))

def prepare_local_render_plan(task, headers=None):
    import local_focus as F
    import volcano_run as R
    from longform_state import native_path, save
    from film_editor import atomic_bytes, file_digest
    _validate_task(task)
    current = _source_versions(task)
    if task.get('source_versions') is None or task['source_versions'] != current:
        raise _source_changed(current)
    root = native_path(task['out_dir']); root.mkdir(parents=True,exist_ok=True)
    result = dict(version=1,contract_key=task['contract_key'],status='pending',files={},counts={},source_sizes={},warnings=[],review_requests=[],diagnostics={})
    with R.review_receipt_lock(str(root/'local-render-execution')):
        receipt_path = native_path(task['files']['receipt'])
        identities = {}   # 뿌리마다 지금 검출 환경 지문 한 번(local_focus.runtime_stale) — 영수증·옛 계획 확인이 함께 쓴다
        if reusable_receipt(receipt_path, identities):
            return verify_local_render_plan(task, identities=identities)
        restored = _import_legacy_plan(task, current, identities)
        if restored is not None:return restored
        focus = F.prepare_local_focus(dict(version=1,kernel_id=task['focus_kernel_id'],contract_key=task['contract_key'],
            cuts=task['cuts'],selection=task['selection'],text_review=task['text_review'],out_dir=task['out_dir']+'/focus',legacy_dir=task['workdir']+'/local-render/evidence'),headers=headers,
            full_frame=_full_frame_aspect(task))
        if focus['status'] != 'complete':
            result.update(status=focus['status'],review_requests=focus.get('review_requests',[]),diagnostics=focus.get('diagnostics',{}))
            return result
        rows = {key:_read(native_path(meta['path'])) for key,meta in focus['receipts'].items()}
        path = root/'photo-state.json'
        legacy, legacy_missing = _legacy_photo(task)
        state = _read(path) if path.exists() else {'phase':'ready','payload':{'photo_text_results':legacy}}
        if state.get('phase') == 'inflight':
            result.update(status='blocked',diagnostics={'review':{'code':'unknown_acceptance','automatic_retry':False}})
            return result
        payload = dict(state.get('payload') or {},timing=task['timing'],imgdir=task['imgdir'],
                       images={source:task['metadata'][str(usage)] for usage,source,_ in task['uses']})
        # 사람이 «다시»(focus_retry)를 알린 컷 중 사진 글자 검수가 **실행 실패**(구독 AGY 결과 없음·끊김)로 끝난 것만 그 영수증을
        #   놓아 다시 검수한다 — 판정·거부·예산 정지는 다시 묻지 않는다(_photo_text_execution_failed · 자동 재시도 없음).
        again = _photo_text_retry(task, payload)
        plan, pending, built = _build(task, rows, payload)
        save(path,dict(phase='ready',payload=payload))
        if built is None and plan.pending and focus.get('full_frame_refusal'):
            # 이 실행의 피사체 판정에서 거부를 봤다 — 사진 글자 검수 요청도 보내지 않는다(전역 규칙 6-2 · 자동 재시도 없음).
            result.update(status='blocked',diagnostics={'review':{'code':'provider_refused','automatic_retry':False}})
            return result
        if built is None and plan.pending:
            if legacy_missing:
                result.update(status='blocked',diagnostics={'review':{'code':'legacy_photo_receipt_unavailable','automatic_retry':False}})
                return result
            requests = pending.get('review_requests',[])
            from local_photo_plan import _review_needs_reply
            if any(_review_needs_reply(r,task['selection']['focus_review_replies']) for r in requests):
                result.update({k:pending[k] for k in ('status','review_requests','diagnostics')})
                return result
            save(path,dict(phase='inflight',payload=payload))
            settings = {k:task['selection'][k] for k in ('review_policy','focus_review_replies','review_budget') if k in task['selection']}
            # engine_failure_rows: 검수 엔진(구독 AGY)이 결과 없이 끝나면 사람 답 대기가 아니라 실행 실패 행으로 받는다(화면 글자
            #   검수와 같은 opt-in · 전역 규칙 6-1 — 사람에게 판독 답을 손으로 쓰게 하지 않는다). «다시» 컷은 끝나지 않은 영수증을 한 번 놓는다.
            with R.review_retry_scope(bool(again), R.review_retry_registry() if again else None):
                reviewed = R.review_film_frames(dict(settings,preserved_text_review=True,cuts=plan.pending,engine_failure_rows=True,
                    photo_review=task['text_review']['photo_review'],out_dir=task['workdir']+'/probe/photo-text'),headers=headers)
            payload['photo_text_results'] = reviewed
            save(path,dict(phase='ready',payload=payload))
            if any(F._receipt_refused(r) for r in reviewed.values()):
                result.update(status='blocked',diagnostics={'review':{'code':'provider_refused','automatic_retry':False}})
                return result
            plan,pending,built = _build(task,rows,payload)
            save(path,dict(phase='ready',payload=payload))
        if built is None:
            # 사진 글자 막힘의 고칠 안내(author·message·then_call_with — local_photo_plan.PHOTO_TEXT_GUIDANCE_KEYS 한 자리)도 함께 넘긴다.
            from local_photo_plan import PHOTO_TEXT_GUIDANCE_KEYS
            result.update({k:pending[k] for k in ('status','review_requests','diagnostics',*PHOTO_TEXT_GUIDANCE_KEYS) if k in pending})
            result['diagnostics'] = _photo_text_diagnostics(result['diagnostics'], payload)
            return result
        sources = {c['src']:file_digest(native_path(c['src'])) for c in task['cuts']}
        if sources != current:raise _source_changed(sources)
        if any(rows[str(c['card'])]['source_identity'] != sources[c['src']] for c in task['cuts']):
            raise R.StepError('계획 작성 중 원본이 바뀌었습니다. 기존 검수 기록을 보존합니다.')
        for name,blob in built['blobs'].items():
            atomic_bytes(native_path(task['files'][name]),blob)
            result['files'][name] = dict(path=task['files'][name],sha256=hashlib.sha256(blob).hexdigest())
        result.update(status='complete',counts=built['counts'],warnings=built['warnings'],
                      source_sizes={str(c['card']):list(rows[str(c['card'])]['size']) for c in task['cuts']})
        receipt = dict(version=1,task=task,focus=focus,photo=payload,sources=sources,result=result)
        save(receipt_path,receipt)
        result['files']['receipt'] = dict(path=task['files']['receipt'],sha256=file_digest(receipt_path))
        return result


def verify_local_render_plan(task, expected=None, identities=None):
    """Verify originals, canonical selections and deterministic plan before baking."""
    import focus_kernel as K
    import volcano_run as R
    from film_editor import file_digest
    from longform_state import native_path
    _validate_task(task)
    receipt_path=native_path(task['files']['receipt']); receipt=_read(receipt_path)
    if _bytes(_semantic(receipt['task'])) != _bytes(_semantic(task)):
        raise R.StepError('저장된 로컬 계획의 규격이 바뀌었습니다.')
    current = _source_versions(task)
    if task.get('source_versions') is not None and receipt['sources'] != task['source_versions']:
        raise R.StepError('저장된 원본 버전 목록이 계약과 다릅니다.')
    rows={}
    for cut in task['cuts']:
        meta=receipt['focus']['receipts'][str(cut['card'])];path=native_path(meta['path'])
        if meta['path'] != task['out_dir']+'/focus/'+cut['focus_key']+'.'+str(meta.get('source_identity'))+'.json':
            raise R.StepError('로컬 피사체 기록의 경로가 바뀌었습니다.')
        if file_digest(path)!=meta['sha256']:
            raise R.StepError('로컬 피사체 검수 기록이 변경되었습니다.')
        row=_read(path)
        if K.validate(cut,row):
            raise R.StepError('원본 또는 피사체 검수 기록이 규격과 다릅니다.')
        rows[str(cut['card'])]=row
    from local_focus import verify_selection_runtime
    verify_selection_runtime(rows.values(), identities)
    if receipt['sources'] != {c['src']:rows[str(c['card'])]['source_identity'] for c in task['cuts']}:
        raise R.StepError('로컬 원본 확인 목록이 바뀌었습니다.')
    _,_,built=_build(task,rows,copy.deepcopy(receipt['photo']))
    if built is None:raise R.StepError('저장된 로컬 계획의 검수가 완료되지 않았습니다.')
    result=copy.deepcopy(receipt['result'])
    for name,blob in built['blobs'].items():
        path=native_path(task['files'][name]);meta=result['files'][name];rebuilt=hashlib.sha256(blob).hexdigest()
        # ★두 사실을 가른다(2026-10-23 뇌전구 신고 · 5명 · 맥·윈도우): 예전 한 문구는 «무엇이·어느 쪽이» 를 안 말해 원인을 못 가렸다.
        #   같은 재료(피사체 기록 지문·원본 지문·영수증의 사진 글자 답)로 다시 지은 계획은 실행기 갱신(제자리 다시 읽기)·새
        #   프로세스·실행 전용 칸 변화에도 바이트가 같다(맥·윈도우 실측). 그래서 ① 영수증 지문 ≠ 다시 지은 지문 = 계획 계산이
        #   달라진 것 · ② 영수증 = 다시 지은 것인데 디스크만 다름 = 계획을 지은 뒤 이 실행기 밖에서 파일을 고친 것.
        if meta!={'path':task['files'][name],'sha256':rebuilt}:
            raise R.StepError(f'로컬 프레임 계획({path.name})을 같은 재료로 다시 지은 결과가 계획 영수증과 다릅니다(영수증 '
                              f'{str(meta.get("sha256"))[:12]} · 다시 지음 {rebuilt[:12]}). 계획을 지은 실행기와 지금 실행기의 계산이 '
                              '갈렸습니다 — 결과물·검수 기록은 그대로 두고 이 신고를 보내 주세요(같은 명령을 되풀이해도 같은 결과입니다).')
        disk=path.read_bytes() if path.is_file() else None
        if disk!=blob:
            found='없음' if disk is None else hashlib.sha256(disk).hexdigest()[:12]
            raise R.StepError(f'로컬 프레임 계획 파일 {path.name} 이 계획을 지은 뒤 바뀌었습니다(영수증 {rebuilt[:12]} · 지금 파일 '
                              f'{found}). 이 실행기는 그 파일을 다시 쓰지 않습니다 — 같은 작업 폴더를 다른 실행기 창·편집기·동기화 '
                              '프로그램이 함께 쓰고 있습니다. 그 창(같은 폴더의 다른 volcano_drive 실행)을 끝내고 파일은 고치지 말고 '
                              '같은 명령을 다시 실행하세요.')
    if (result['counts']!=built['counts'] or result['warnings']!=built['warnings']
            or result.get('source_sizes')!={str(c['card']):list(rows[str(c['card'])]['size']) for c in task['cuts']}):
        raise R.StepError('로컬 프레임 계획 요약이 변경되었습니다.')
    latest = _source_versions(task)
    if latest != current:raise _source_changed(latest)
    if receipt['sources'] != current:
        raise _source_changed(current)
    result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(receipt_path))
    if expected is not None and result!=expected:
        raise R.StepError('서버에 보낸 로컬 계획 식별자와 현재 파일이 다릅니다.')
    return result


def _proof_stale(meta):
    """서버가 보낸 계획 증명(planner_receipt 지문)이 지금 작업 폴더의 기록과 다르다 → 옛 증명을 버리고 render_plan 의 로컬 계획부터.

    ★왜 (2026-10-22 뇌전구 신고 2건 · 한 사람): 영상을 끝낸 뒤 같은 작업 폴더에서 편집을 다시 돌리자 서버가 이전 판의
      local_render_plan_result(같은 계약 · 기록 지문 8ab3d7cb…)로 곧장 굽기 증명을 다시 냈고, 그 사이 작업 폴더의 기록이 달라져 있어
      여기서 «기록이 변경되었습니다» 로 멈췄다. 사람은 같은 명령을 다시 돌렸고 payload 에 옛 결과가 그대로 있어 같은 자리에서 또 멈췄다
      (17초 뒤). 그 결과를 빼고 부르자 로컬 계획(검증만)부터 다시 해 완주했다 — 그 길을 구동기가 한 번 스스로 간다.
      기록이 무엇 때문에 달라졌는지는 못 가렸다(그 사이 render_plan 로컬 계획 호출 없음 · 같은 폴더의 다른 실행기 프로세스는 추측).
    ★굽기·유료 일은 이 검사 뒤에만 시작하므로 아무것도 쓰기 전이다. 같은 옛 증명이 또 오면 구동기가 다시 돌지 않고 이 글로 멈춘다."""
    import volcano_run as R
    error = R.StepError('로컬 렌더 계획 기록이 변경되었습니다 — 서버가 보낸 계획 증명이 지금 작업 폴더의 기록보다 옛것입니다. '
                        '옛 증명을 버리고 render_plan 의 로컬 계획부터 다시 확인합니다(검수·음성 기록은 보존).')
    error.code = 'local_plan_proof_stale'
    error.execution_recovery = {'local_render_plan_result': None}
    error.execution_next_step = 'render_plan'
    error.stale_proof = str(meta.get('sha256') or '')
    return error


def runtime_changed(meta, next_step):
    """굽기 증명의 계획이 지금과 다른 검출 모델·환경에서 고른 피사체 행을 품었다 → 증명을 버리고 render_plan 의 로컬 계획부터
    한 번 다시 간다 — 거기서 prepare_local_render_plan 이 옛 영수증을 옆 이름으로 남기고(_set_aside) 바뀐 컷만 지금 환경에서 다시 고른다.

    ★왜 (2026-10-20~22 뇌전구 render_mix 신고 · 윈도우 3명): 윈도우 env 단계가 onnxruntime 을 onnxruntime-directml 로 바꿔 깐 뒤
      (10-19 결정 · 10-20 배포) 검출 환경 지문이 달라졌는데, render_plan 은 10-21 에 «다시 고르기» 길이 생겼지만 굽기 증명 확인
      (verify_render_plan)은 그대로 «재확인해야 합니다» 로 멈췄다. 굽기·유료 일은 이 검사 뒤에만 시작하므로 아무것도 쓰기 전이다.
      다시 고른 행은 지금 지문을 적으므로 같은 증명이 또 오면(진전 없음) 구동기가 다시 돌지 않고 멈춘다."""
    import volcano_run as R
    error = R.StepError('피사체 선택 뒤 검출 모델·환경이 바뀌었습니다 — 옛 계획 증명을 버리고 ' + next_step + ' 의 로컬 계획에서 '
                        '바뀐 컷을 현재 환경으로 다시 확인합니다(이전 원본·검수 기록 보존).')
    error.code = 'local_plan_runtime_changed'
    error.execution_recovery = {'local_render_plan_result': None}
    error.execution_next_step = next_step
    error.stale_proof = str(meta.get('sha256') or '')
    return error


def runtime_checked(path, meta, next_step):
    """굽기 증명 확인 앞: 영수증의 피사체 행이 지금 검출 환경과 같으면 그 지문 묶음(뒤 확인이 다시 재지 않게)을, 다르면
    runtime_changed 로 계획 단계(next_step)에 한 번 돌려보낸다 — 뇌전구(render_plan)·쇼핑(shop_cuts)·재더빙(redub_master) 한 자리."""
    identities = {}
    if _receipt_runtime_stale(path, identities):raise runtime_changed(meta, next_step)
    return identities


def verify_render_plan(proof):
    """Phase-two entry: verify receipt before any writes, bake, or paid jobs."""
    import volcano_run as R
    from film_editor import file_digest
    from longform_state import native_path
    if not isinstance(proof,dict) or set(proof)!={'version','kernel_id','contract_key','files'} or proof.get('version')!=1:
        raise R.StepError('로컬 렌더 실행 증명이 올바르지 않습니다.')
    if not isinstance(proof.get('files'),dict):
        raise R.StepError('로컬 렌더 파일 식별자가 올바르지 않습니다.')
    meta=proof['files'].get('receipt',{})
    if not isinstance(meta,dict):
        raise R.StepError('로컬 렌더 계획 기록 식별자가 올바르지 않습니다.')
    path=native_path(meta.get('path',''))
    if not path.is_file() or file_digest(path)!=meta.get('sha256'):
        raise _proof_stale(meta)
    task=_read(path)['task']
    if task['kernel_id']!=proof['kernel_id'] or task['contract_key']!=proof['contract_key'] or task['files']['receipt']!=meta['path']:
        raise R.StepError('로컬 렌더 실행 증명과 계획이 다릅니다.')
    identities=runtime_checked(path, meta, 'render_plan')   # 뿌리마다 지금 검출 환경 지문 한 번 — 아래 확인도 이것을 쓴다
    result=verify_local_render_plan(task, identities=identities)
    if result['files']!=proof['files']:
        raise R.StepError('로컬 렌더 출력 파일과 실행 증명이 다릅니다.')
    receipt=_read(path)
    return [dict(path=p,sha256=sha) for p,sha in sorted(receipt['sources'].items())]
