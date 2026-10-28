"""Exact person audit/camera/filter planning on the student's PC."""
import copy
import hashlib
import json
import local_render_plan as T


def _validate(task):
    import person_kernel as K
    import focus_kernel as F
    from pathlib import Path
    import volcano_run as R
    if hashlib.sha256(Path(K.__file__).read_bytes()).hexdigest()!=task.get('person_kernel_sha256'):
        raise R.StepError('인물형 계산 코드 파일이 서버 규격과 다릅니다.')
    if task.get('kernel_id')!=K.KERNEL_ID or task.get('focus_kernel_id')!=F.KERNEL_ID:
        raise R.StepError('인물형 로컬 계산 코드와 서버 규격 버전이 다릅니다.')
    if hashlib.sha256(T._bytes(T._semantic(task))).hexdigest()!=task.get('contract_key'):
        raise R.StepError('인물형 계산 계약이 변경됐습니다.')
    if task.get('mode') not in ('person','person_delivery'):
        raise R.StepError('인물형 계산 단계가 올바르지 않습니다.')
    cards={str(c['card']) for c in task['cuts']}
    intent=task.get('photo_text_intent',{})
    if not isinstance(intent,dict) or not set(intent)<=cards or any(type(v) is not bool for v in intent.values()):
        raise R.StepError('사진 검수의 글자 보존 의도가 올바르지 않습니다.')
    if task['mode']=='person_delivery' and (not isinstance(task.get('delivery_frames'),list)
        or len(task['delivery_frames'])!=len(task['cuts'])
        or any(type(n) is not int or n<=0 for n in task['delivery_frames'])):
        raise R.StepError('편집본 프레임 수가 원본 컷과 다릅니다.')
    folder=task['workdir']+'/local-person/'+task['contract_key']
    if task['out_dir']!=folder or task['files']!={'plan':folder+'/frame_plan.json','receipt':folder+'/planner_receipt.json'}:
        raise R.StepError('인물형 계획 파일 위치가 계약과 다릅니다.')


def _changed(current):
    error=T._source_changed(current);error.execution_next_step='person_frame';return error


def _build(task,rows):
    import person_kernel as K
    cards,clips,ids,S=task['cards'],task['clips'],task['ids'],task['spec']
    rows={card:dict(row,**({'preserve_text':task['photo_text_intent'][card]} if card in task.get('photo_text_intent',{}) else {})) for card,row in rows.items()}
    audit=K.audit_frames(cards,clips,ids,rows,S)
    shots=K.shots_of(cards,clips)
    plan=audit['plan']
    # A failed audit preserves its measurements and produces no render jobs.
    jobs=K.cut_jobs(cards,clips,ids,task['workdir'],S,plan=plan) if not audit['reject'] else []
    pre=K.presig_plan(shots,ids,plan) if not audit['reject'] else []
    return dict(audit=audit,jobs=jobs,presig=pre,
        presig_jobs=K.sig_jobs(shots,task['workdir'],S,plan=pre) if pre else [],
        frame_key=K.frame_identity(shots,ids,plan,S),rows=rows)


def _summary(packet):
    audit=packet['audit']
    allowed={'card','crop','zoom','by','motion','needs_replacement','framing_reason','framing_status','subject_detected'}
    summary=dict(audit=dict(reject=audit['reject'],warn=audit['warn'],
        plan=[{k:v for k,v in row.items() if k in allowed} for row in audit['plan']]),
        frame_key=packet['frame_key'],presig=packet['presig'],
        jobs=[{k:j[k] for k in ('index','out','seconds')} for j in packet['jobs']],
        frames={card:{k:row[k] for k in ('source_identity','size','measurement_version') if k in row} for card,row in packet['rows'].items()})
    return json.loads(T._bytes(summary))


def prepare(task,headers=None):
    import local_focus as F
    import person_kernel as K
    import volcano_run as R
    from subject_focus import measure_source_motions
    from longform_state import native_path,save
    from film_editor import atomic_bytes,file_digest
    task=copy.deepcopy(task);_validate(task);current=T._source_versions(task)
    if task.get('source_versions')!=current:raise _changed(current)
    root=native_path(task['out_dir']);root.mkdir(parents=True,exist_ok=True)
    with R.review_receipt_lock(str(root/'execution')):
        if native_path(task['files']['receipt']).exists():return verify(task)
        focus=F.prepare_local_focus(dict(version=1,kernel_id=task['focus_kernel_id'],contract_key=task['contract_key'],cuts=task['cuts'],selection=task['selection'],text_review=task['text_review'],out_dir=task['out_dir']+'/focus',legacy_dir=task['workdir']+'/local-person/evidence'),headers=headers)
        result=dict(version=1,contract_key=task['contract_key'],status=focus['status'],files={},counts={},warnings=[],source_sizes={},review_requests=focus.get('review_requests',[]),diagnostics=focus.get('diagnostics',{}))
        if focus['status']!='complete':return result
        rows={card:T._read(native_path(meta['path'])) for card,meta in focus['receipts'].items()}
        missing=[dict(c,content=rows[str(c['card'])]['content'],source_identity=rows[str(c['card'])]['source_identity'],selection_recipe_key=rows[str(c['card'])].get('_recipe')) for c in task['cuts'] if c['kind']!='image' and not K.source_motion_valid(c,rows[str(c['card'])])]
        if missing:
            motion_path=root/'source-motion.json'
            state={'results':{},'observations':[]}
            if motion_path.exists():
                raw=motion_path.read_bytes()
                try:
                    parsed=json.loads(raw.decode('utf-8-sig'))
                    if not isinstance(parsed,dict) or not isinstance(parsed.get('results'),dict) or not isinstance(parsed.get('observations'),list):raise ValueError('invalid local metric state')
                    state=parsed
                except (ValueError,UnicodeError):
                    # Preserve corrupt local bytes for diagnosis, then rebuild
                    # only missing metrics from immutable original media.
                    atomic_bytes(root/('source-motion.corrupt.'+hashlib.sha256(raw).hexdigest()+'.json'),raw)

            valid={}
            for cut in missing:
                card=str(cut['card']);record=state.get('results',{}).get(card)
                if isinstance(record,dict) and K.source_motion_valid(cut,dict(rows[card],motion=record.get('value'),source_motion=record)):
                    valid[card]=record
            pending=[c for c in missing if str(c['card']) not in valid]
            if pending:
                # This is a deterministic local pixel calculation, never a paid
                # provider request. Interrupted/partial attempts may resume only
                # their missing invalid cells; verified peers are never repeated.
                state.update(status='requested',results=valid,pending=[str(c['card']) for c in pending])
                save(motion_path,state)
                measured=measure_source_motions(dict(cuts=pending,out_dir=task['workdir']+'/probe/subject-focus'))
                state.setdefault('observations',[]).append(measured)
                if isinstance(measured,dict):
                    for cut in pending:
                        card=str(cut['card']);record=measured.get(card)
                        if isinstance(record,dict) and K.source_motion_valid(cut,dict(rows[card],motion=record.get('value'),source_motion=record)):
                            valid[card]=record
                state.update(status='complete' if len(valid)==len(missing) else 'incomplete',results=valid,
                    pending=[str(c['card']) for c in missing if str(c['card']) not in valid])
                save(motion_path,state)
            if len(valid)!=len(missing):
                raise R.StepError('원본 움직임 측정이 일부 완료되지 않았습니다. 정상 결과와 검수 증거는 보존했습니다. 재개하면 빠진 로컬 측정만 복구합니다.')
            for card,measurement in valid.items():rows[card]=dict(rows[card],motion=measurement['value'],source_motion=measurement)
        F.preserve_wire_evidence({'frames':rows},out_dir=task['workdir']+'/local-person/evidence')
        packet=_build(task,rows)
        latest=T._source_versions(task)
        if latest!=current:raise _changed(latest)
        blob=T._bytes(packet);atomic_bytes(native_path(task['files']['plan']),blob)
        result.update(status='complete',files={'plan':dict(path=task['files']['plan'],sha256=hashlib.sha256(blob).hexdigest())},counts={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts'])},source_sizes={card:row['size'] for card,row in rows.items()},diagnostics={'person':_summary(packet)})
        save(native_path(task['files']['receipt']),dict(task=task,focus=focus,sources=current,result=result,motion={card:row.get('source_motion') for card,row in rows.items()}))
        result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
        return result


def verify(task):
    import local_focus as F
    import person_kernel as K
    import volcano_run as R
    from longform_state import native_path
    from film_editor import file_digest
    _validate(task);saved=T._read(native_path(task['files']['receipt']))
    if T._semantic(saved['task'])!=T._semantic(task) or saved['sources']!=task['source_versions']:
        raise R.StepError('인물형 저장 계약 또는 원본이 변경됐습니다.')
    rows={}
    import focus_kernel as FK
    for cut in task['cuts']:
        card=str(cut['card']);meta=saved['focus']['receipts'][card];path=native_path(meta['path'])
        expected=task['out_dir']+'/focus/'+cut['focus_key']+'.'+saved['sources'][cut['src']]+'.json'
        if meta['path']!=expected or file_digest(path)!=meta['sha256']:
            raise R.StepError('인물형 피사체 검수 증거가 변경됐습니다.')
        row=T._read(path)
        if FK.validate(cut,row) or row['source_identity']!=saved['sources'][cut['src']]:
            raise R.StepError('인물형 피사체 검수 증거가 요청과 다릅니다.')
        motion=saved['motion'].get(card)
        if motion is not None:row=dict(row,motion=motion['value'],source_motion=motion)
        if cut['kind']!='image' and not K.source_motion_valid(cut,row):
            raise R.StepError('인물형 원본 움직임 증거가 요청과 다릅니다.')
        rows[card]=row
    F.verify_selection_runtime(rows.values())
    packet=_build(task,rows);blob=T._bytes(packet);result=copy.deepcopy(saved['result'])
    if (native_path(task['files']['plan']).read_bytes()!=blob
        or result['files']['plan']!={'path':task['files']['plan'],'sha256':hashlib.sha256(blob).hexdigest()}
        or result['diagnostics']!={'person':_summary(packet)}
        or result['source_sizes']!={card:row['size'] for card,row in rows.items()}
        or result['counts']!={'frames':sum(round(c['duration']*c['fps']) for c in task['cuts']),'parts':len(task['cuts'])}
        or result['version']!=1 or result['contract_key']!=task['contract_key'] or result['status']!='complete'
        or result['warnings']!=[] or result['review_requests']!=[]):
        raise R.StepError('인물형 로컬 계산 결과 또는 요약이 변경됐습니다.')
    current=T._source_versions(task)
    if current!=saved['sources']:raise _changed(current)
    result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
    return result


def verify_proof(proof):
    from longform_state import native_path
    from film_editor import file_digest
    import volcano_run as R
    path=native_path(proof['files']['receipt']['path'])
    if file_digest(path)!=proof['files']['receipt']['sha256']:raise R.StepError('인물형 실행 증명이 변경됐습니다.')
    saved=T._read(path);task=saved['task'];result=verify_delivery(task) if task.get('mode')=='person_delivery' else verify(task)
    if proof!={'version':1,'kernel_id':task['kernel_id'],'contract_key':task['contract_key'],'files':result['files']}:
        raise R.StepError('인물형 실행 증명과 로컬 파일이 다릅니다.')
    return T._read(native_path(task['files']['plan'])),[dict(path=p,sha256=h) for p,h in saved['sources'].items()]


def expand_response(response):
    """Verify first, then materialize exact native work before any execution."""
    import sys
    import person_kernel as K
    import volcano_run as R
    packet,checks=verify_proof(response['local_person_plan'])
    expected=packet['summary'] if response.get('local_person_stage')=='delivery' else _summary(packet)
    if T._bytes(response.get('local_person_summary'))!=T._bytes(expected):raise R.StepError('인물형 실행 요약이 검증된 원본 계산과 다릅니다.')
    out=copy.deepcopy(response)
    out['source_checks']=[*(out.get('source_checks') or []),*checks]
    if out.get('local_person_stage')=='bake':
        def wf(path,content):
            blob=content.encode('utf-8')
            return dict(path=path,content=content,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob))
        from longform_state import native_path
        saved=T._read(native_path(response['local_person_plan']['files']['receipt']['path']))
        prepared=K.prepare(packet['jobs'],{'python':sys.executable},saved['task']['workdir'],wf=wf,next_step='person_frame',error=R.StepError)
        if prepared['probe']:raise R.StepError('로컬 실행 파이썬 경로를 확정하지 못했습니다.')
        out['jobs']=prepared['jobs'];out['write_files']=[*(out.get('write_files') or []),*prepared['write_files']]
    elif out.get('local_person_stage')=='presig':
        for task in out.get('do',[]):
            if task.get('cmd')=='cut_signature':task['cuts']=packet['presig_jobs']
    elif out.get('local_person_stage')=='delivery':
        options=out['local_person_delivery_inputs']
        from longform_state import native_path
        saved=T._read(native_path(response['local_person_plan']['files']['receipt']['path']))
        task=saved['task'];S=task['spec'];dd=options['directory']
        xml=K.fcp7_xml(options['title']+' 원본 편집',packet['raw_cuts'],options['audio'],options['total_frames'],options['markers'],S,S['FPS'],frame={'path':dd+'/프레임.png'})
        if options.get('text_records'):xml=K.editable_text_xml(xml,options['text_records'],S['FPS'],S['W'],S['H'])
        for item in out.get('write_files',[]):
            if item['path']==dd+'/프리미어_원본편집.xml':item['content']=xml
            elif item['path']==dd+'/원본소재.json':item['content']=json.dumps(packet['raw_cuts'],ensure_ascii=False,indent=2)
            else:continue
            blob=item['content'].encode('utf-8');item.update(sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob))
    else:raise R.StepError('인물형 로컬 실행 단계가 올바르지 않습니다.')
    return out


def _delivery_build(task):
    import person_kernel as K
    packet,checks=verify_proof(task['framing_proof'])
    from longform_state import native_path
    import volcano_run as R
    parent=T._read(native_path(task['framing_proof']['files']['receipt']['path']))['task']
    for key in ('cards','clips','ids','spec','workdir','cuts','source_versions','photo_text_intent'):
        if task.get(key)!=parent.get(key):raise R.StepError('편집본 계약과 확정된 프레이밍의 원본이 다릅니다.')
    if packet['audit']['reject']:raise ValueError('Rejected framing cannot be delivered')
    S=task['spec'];shots=K.shots_of(task['cards'],task['clips']);plan=packet['audit']['plan']
    raw=K.deliver_cuts(shots,task['ids'],task['delivery_frames'],S,S['FPS'],plan=plan)
    cuts=K.rendered_delivery_cuts(raw,plan,task['workdir'],S)
    def compact(row):
        value={k:v for k,v in row.items() if k not in ('motion_keys','scene_guard_plan')}
        if 'original_source' in value:value['original_source']={k:v for k,v in value['original_source'].items() if k!='scene_guard_plan'}
        return value
    return dict(raw_cuts=raw,cuts=cuts,summary={'raw_cuts':[compact(c) for c in raw],'cuts':[compact(c) for c in cuts]})


def prepare_delivery(task):
    import volcano_run as R
    from longform_state import native_path,save
    from film_editor import atomic_bytes,file_digest
    _validate(task);root=native_path(task['out_dir']);root.mkdir(parents=True,exist_ok=True)
    with R.review_receipt_lock(str(root/'execution')):
        if native_path(task['files']['receipt']).exists():return verify_delivery(task)
        current=T._source_versions(task)
        if current!=task['source_versions']:raise _changed(current)
        packet=_delivery_build(task);blob=T._bytes(packet)
        if T._source_versions(task)!=current:raise _changed(T._source_versions(task))
        atomic_bytes(native_path(task['files']['plan']),blob)
        result=dict(version=1,contract_key=task['contract_key'],status='complete',
            files={'plan':dict(path=task['files']['plan'],sha256=hashlib.sha256(blob).hexdigest())},
            counts={'frames':sum(task['delivery_frames']),'parts':len(task['cuts'])},warnings=[],review_requests=[],
            source_sizes=T._read(native_path(task['framing_proof']['files']['receipt']['path']))['result']['source_sizes'],
            diagnostics={'person_delivery':json.loads(T._bytes(packet['summary']))})
        save(native_path(task['files']['receipt']),dict(task=task,sources=current,result=result))
        result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
        return result


def verify_delivery(task):
    import volcano_run as R
    from longform_state import native_path
    from film_editor import file_digest
    _validate(task);saved=T._read(native_path(task['files']['receipt']))
    if T._semantic(saved['task'])!=T._semantic(task) or saved['sources']!=task['source_versions']:raise R.StepError('편집본의 원본 또는 계약이 변경됐습니다.')
    packet=_delivery_build(task);blob=T._bytes(packet);result=copy.deepcopy(saved['result'])
    if (native_path(task['files']['plan']).read_bytes()!=blob or result['diagnostics']!={'person_delivery':json.loads(T._bytes(packet['summary']))}
        or result['files']['plan']!={'path':task['files']['plan'],'sha256':hashlib.sha256(blob).hexdigest()}
        or result['version']!=1 or result['contract_key']!=task['contract_key'] or result['status']!='complete'
        or result['counts']!={'frames':sum(task['delivery_frames']),'parts':len(task['cuts'])}
        or result['warnings']!=[] or result['review_requests']!=[]
        or result['source_sizes']!=T._read(native_path(task['framing_proof']['files']['receipt']['path']))['result']['source_sizes']):raise R.StepError('편집본 계산 증거가 변경됐습니다.')
    current=T._source_versions(task)
    if current!=saved['sources']:raise _changed(current)
    result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
    return result
