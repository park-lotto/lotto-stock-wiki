"""Legacy redub focus/OCR/scene and exact filter calculation on this PC."""
import copy
import hashlib
import json
import local_render_plan as T


def _validate(task):
    import redub_kernel as K
    import focus_kernel as F
    import volcano_run as R
    from pathlib import Path
    if hashlib.sha256(Path(K.__file__).read_bytes()).hexdigest()!=task.get('redub_kernel_sha256'):
        raise R.StepError('재더빙 로컬 계산 파일이 서버의 정확한 코드와 다릅니다.')
    if task.get('kernel_id')!=K.KERNEL_ID or task.get('focus_kernel_id')!=F.KERNEL_ID:
        raise R.StepError('재더빙 로컬 계산 코드 버전이 서버 계약과 다릅니다.')
    if hashlib.sha256(T._bytes(T._semantic(task))).hexdigest()!=task.get('contract_key'):
        raise R.StepError('재더빙 계획 계약이 변경됐습니다.')
    folder=task['workdir']+'/local-redub/'+task['contract_key']
    if task['out_dir']!=folder or task['files']!={'filter':folder+'/master.filter','receipt':folder+'/planner_receipt.json'}:
        raise R.StepError('재더빙 계획 경로가 계약과 다릅니다.')


def _changed(current):
    error=T._source_changed(current);error.execution_next_step='redub_master';return error


def _build(task,rows):
    import redub_kernel as K
    import volcano_run as R
    if any(row.get('size')!=task['size'] for row in rows.values()):
        raise R.StepError('재더빙 실제 원본 크기가 측정된 source_size와 다릅니다. 검수 증거를 보존합니다.')
    vparts=[];aparts=[];warnings=[];zoomed=[]
    subjects=K.subjects_of(rows);width,height=task['canvas'];sw,sh=task['size'];fps=task['cuts'][0]['fps']
    for k,segment in enumerate(task['segments']):
        a,b=segment;plan=[]
        chain=K.seg_video_chain(k,a,b,sw,sh,task['zoom'],subject=subjects.get(k),measurement=rows[str(k)],output_size=[width,height],fps=fps,matte=task['matte'],collect=plan)
        vparts.append('[0:v]'+chain+f'[cv{k}]')
        aparts.append(f'[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[ca{k}]')
        if plan[0].get('zoom_applied'):zoomed.append(k)
        elif plan[0].get('zoom_suppressed'):warnings.append(f'구간 {k}: 선택 피사체 전체를 보존하기 위해 확대를 생략했습니다.')
    pre=vparts+aparts+K.concat_av(len(task['segments']),fps,video_prefix='cv',audio_prefix='ca',video_out='jv',audio_out='ja')
    return ';'.join(pre+task['tail']).encode('utf-8'),warnings,zoomed


def prepare(task,headers=None):
    import local_focus as F
    import volcano_run as R
    from longform_state import native_path,save
    from film_editor import atomic_bytes,file_digest
    _validate(task);current=T._source_versions(task)
    if task.get('source_versions') is None or task['source_versions']!=current:raise _changed(current)
    root=native_path(task['out_dir']);root.mkdir(parents=True,exist_ok=True)
    with R.review_receipt_lock(str(root/'execution')):
        identities={}   # 뿌리마다 지금 검출 환경 지문 한 번(local_focus.runtime_stale)
        if T.reusable_receipt(native_path(task['files']['receipt']),identities):return verify(task,identities)
        focus=F.prepare_local_focus(dict(version=1,kernel_id=task['focus_kernel_id'],contract_key=task['contract_key'],cuts=task['cuts'],selection=task['selection'],text_review=task['text_review'],out_dir=task['out_dir']+'/focus',legacy_dir=task['workdir']+'/local-redub/evidence'),headers=headers)
        result=dict(version=1,contract_key=task['contract_key'],status=focus['status'],files={},counts={},warnings=[],source_sizes={},review_requests=focus.get('review_requests',[]),diagnostics=focus.get('diagnostics',{}))
        if focus['status']!='complete':return result
        rows={card:T._read(native_path(meta['path'])) for card,meta in focus['receipts'].items()}
        blob,warnings,zoomed=_build(task,rows)
        latest=T._source_versions(task)
        if latest!=current:raise _changed(latest)
        atomic_bytes(native_path(task['files']['filter']),blob)
        result.update(status='complete',files={'filter':dict(path=task['files']['filter'],sha256=hashlib.sha256(blob).hexdigest())},counts={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts']),'runs':len(zoomed)},warnings=warnings,source_sizes={card:row['size'] for card,row in rows.items()})
        save(native_path(task['files']['receipt']),dict(task=task,focus=focus,sources=current,result=result))
        result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
        return result


def verify(task,identities=None):
    import local_focus as F
    import volcano_run as R
    from film_editor import file_digest
    from longform_state import native_path
    _validate(task);saved=T._read(native_path(task['files']['receipt']))
    if T._semantic(saved['task'])!=T._semantic(task) or saved['sources']!=task['source_versions']:
        raise R.StepError('재더빙 저장 계약 또는 원본 목록이 변경됐습니다.')
    current=T._source_versions(task);rows={}
    for cut in task['cuts']:
        meta=saved['focus']['receipts'][str(cut['card'])];path=native_path(meta['path'])
        if meta['path']!=task['out_dir']+'/focus/'+cut['focus_key']+'.'+saved['sources'][cut['src']]+'.json' or file_digest(path)!=meta['sha256']:
            raise R.StepError('재더빙 검수 증거가 변경됐습니다.')
        row=T._read(path)
        import focus_kernel as K
        if K.validate(cut,row) or row['source_identity']!=saved['sources'][cut['src']]:raise R.StepError('재더빙 검수 증거가 현재 계약과 다릅니다.')
        rows[str(cut['card'])]=row
    F.verify_selection_runtime(rows.values(),identities)
    blob,warnings,zoomed=_build(task,rows);result=copy.deepcopy(saved['result'])
    if native_path(task['files']['filter']).read_bytes()!=blob or result['files']['filter']!={'path':task['files']['filter'],'sha256':hashlib.sha256(blob).hexdigest()} or result['warnings']!=warnings or result['counts']!={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts']),'runs':len(zoomed)} or result['source_sizes']!={card:row['size'] for card,row in rows.items()}:
        raise R.StepError('재더빙 필터 또는 요약이 변경됐습니다.')
    latest=T._source_versions(task)
    if latest!=current:raise _changed(latest)
    if current!=saved['sources']:raise _changed(current)
    result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
    return result


def verify_proof(proof):
    from longform_state import native_path
    from film_editor import file_digest
    import volcano_run as R
    path=native_path(proof['files']['receipt']['path'])
    if file_digest(path)!=proof['files']['receipt']['sha256']:raise R.StepError('재더빙 실행 증명이 변경됐습니다.')
    identities=T.runtime_checked(path,proof['files']['receipt'],'redub_master')
    saved=T._read(path);task=saved['task'];result=verify(task,identities)
    if proof!={'version':1,'kernel_id':task['kernel_id'],'contract_key':task['contract_key'],'files':result['files']}:raise R.StepError('재더빙 실행 증명과 로컬 파일이 다릅니다.')
    return [dict(path=path,sha256=sha) for path,sha in saved['sources'].items()]
