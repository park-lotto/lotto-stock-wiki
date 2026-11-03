"""Source/film geometry, recovery, OCR and plan persistence on this PC."""
import copy
import hashlib
import json
import local_render_plan as T
import local_source_context as C
import source_kernel as K
import focus_kernel as F


def _focus(task,pl,cuts,preset,step,wd,headers=None):
    import local_focus as L
    from longform_state import native_path
    prepared=[]
    recipe=task['context']['focus_settings'][1]
    for cut in cuts:
        c=dict(cut,selection_recipe=recipe)
        c.setdefault('band',dict(task['context']['focus_settings'][0]['band']));c.setdefault('probe',[]);c.setdefault('suffix','.ppm');c.setdefault('samples',[float(c.get('start',0))])
        c.setdefault('frame_argv',['ffmpeg','-y','-v','error','-ss','@@T@@','-i',c['src'],'-frames:v','1','@@OUT@@'])
        c['focus_key']=F.cut_key(c)
        prepared.append(c)
    group=hashlib.sha256(T._bytes({'kernel_id':F.KERNEL_ID,'cuts':prepared})).hexdigest()
    selection=dict(task['selection'],**({'saved_reviews_only':True} if task['payload'].get('local_source_resume') else {}))
    focus=L.prepare_local_focus(dict(version=1,kernel_id=F.KERNEL_ID,contract_key=group,cuts=prepared,selection=selection,text_review=task['text_review'],out_dir=task['workdir']+'/local-source/focus/'+group,legacy_dir=task['workdir']+'/local-source/evidence'),headers=headers)
    if focus['status']!='complete':
        return {},dict(status='need_input',next_step=step,focus_review_requests=focus.get('review_requests',[]),diagnostics=focus.get('diagnostics',{}),message='원본 피사체 검수 결과를 기다립니다.')
    rows={card:T._read(native_path(meta['path'])) for card,meta in focus['receipts'].items()}
    # Canonical film recovery consumes accepted secondary OCR/view receipts.
    # Preserve those derived fields separately instead of replacing the raw
    # accepted measurement file or silently reverting to its pre-review state.
    from longform_state import save
    from film_editor import file_digest
    allowed={'text_boxes','semantic_review','scene_view_review','preserved_text_boxes'}
    for card,old in F.normalize_focus_rows(pl.get('focus_measurements'), 'focus_measurements').items():
        base=rows.get(str(card))
        if not isinstance(old,dict) or base is None:continue
        if ({k:v for k,v in old.items() if k not in allowed}!={k:v for k,v in base.items() if k not in allowed}
                or (old.get('semantic_review') or {}).get('status')!='accepted'):continue
        merged=dict(base,**{k:copy.deepcopy(v) for k,v in old.items() if k in allowed})
        if merged==base:continue
        digest=hashlib.sha256(T._bytes(merged)).hexdigest()
        meta=focus['receipts'][str(card)]
        path=native_path(meta['path']).parent/(meta['focus_key']+'.secondary.'+digest+'.json')
        if path.exists() and T._read(path)!=merged:raise ValueError('secondary film evidence changed')
        if not path.exists():save(path,merged)
        rows[str(card)]=merged
        focus['receipts'][str(card)]=dict(meta,path=str(path).replace('\\','/'),sha256=file_digest(path))
    pl.update(focus_measurements=rows,focus_state=focus,frames=rows)
    return rows,None


def _validate(task):
    import volcano_run as R
    from pathlib import Path
    names={'source_export_kernel.py','source_kernel.py','source_state_kernel.py','local_source_context.py','local_source_plan.py'}
    if set(task.get('source_runtime',{}))!=names or hashlib.sha256(json.dumps(task['source_runtime'],sort_keys=True).encode()).hexdigest()!=task['kernel_id']:
        raise R.StepError('로컬 영화 계산 파일 목록이 서버 계약과 다릅니다.')
    for name,digest in task['source_runtime'].items():
        if name not in {'source_export_kernel.py','source_kernel.py','source_state_kernel.py','local_source_context.py','local_source_plan.py'} or hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()!=digest:
            raise R.StepError('로컬 영화 계산 코드가 서버 계약의 정확한 버전과 다릅니다.')
    semantic=copy.deepcopy(task)
    for key in ('contract_key','out_dir','files'):semantic.pop(key,None)
    for key in T.EXECUTION_ONLY_SELECTION:semantic['selection'].pop(key,None)
    semantic['selection']['review_policy'].pop('max_requests',None)
    semantic['payload'].pop('focus_review_replies',None)
    if isinstance(semantic['payload'].get('review_policy'),dict):semantic['payload']['review_policy'].pop('max_requests',None)
    if hashlib.sha256(json.dumps(semantic,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()!=task['contract_key']:
        raise R.StepError('로컬 영화 규격 계약이 변경됐습니다.')
    expected=task['workdir']+'/local-source/'+task['contract_key']
    if task['out_dir']!=expected or task['files']!={'plan':expected+'/block_plan.json','receipt':expected+'/planner_receipt.json'}:
        raise R.StepError('로컬 영화 증거 경로가 계약과 다릅니다.')
    return T._source_versions(task)


def _source_changed(task,current):
    error=T._source_changed(current)
    error.execution_next_step='stitch_blocks'
    error.execution_recovery['local_source_plan']=None
    if task.get('source_versions') is not None and task['source_versions']!=current:
        error.execution_recovery['local_source_resume']=None
    return error


def _legacy_film_state(task, current):
    import local_focus as L
    from longform_state import native_path,read
    from film_editor import file_digest
    import volcano_run as R
    root=native_path(task['workdir']+'/local-source/evidence')
    index=root/'film-index.json'
    if not index.exists():return {}
    restored={}
    expected={key:task['payload'].get(key) for key in ('SRC','SRC_SIZE','SRC_CROP','BLOCKS','wav_secs','scene_cuts')}
    for record in read(index)['records']:
        path=root/record['file']
        if path.parent!=root or file_digest(path)!=record['sha256']:raise R.StepError('보존된 영화 검수 상태의 파일 또는 해시가 다릅니다.')
        data=read(path);binding=data.get('_source_binding') or {}
        if binding.get('inputs')!=expected:continue
        if binding.get('source_sha256') not in current.values():continue
        if binding.get('verified_rows') is not True:
            raise R.StepError('이전 영화 검수의 원본 연결을 확인할 수 없습니다. 접수 기록을 보존하며 새 검수를 보내지 않습니다.')
        for key,value in data.items():
            if key=='_source_binding':continue
            try:
                normalized=(F.normalize_focus_rows(value, 'frames') if key in ('film_semantic_frames','film_recovery_frames')
                    else L._legacy_object(value,key))
            except ValueError as error:
                raise R.StepError(str(error).replace('payload.frames', 'payload.'+key, 1)) from error
            restored[key]=normalized
    return restored


def _legacy_render(task,current):
    from longform_state import native_path,read
    from film_editor import file_digest
    import volcano_run as R
    root=native_path(task['workdir']+'/local-source/evidence');index=root/'legacy-index.json'
    if not index.exists():raise R.StepError('기존 렌더와 연결된 원본 검수 기록이 없습니다. 기존 영상과 음성은 보존합니다.')
    for record in reversed(read(index)['records']):
        path=root/record['file']
        if path.parent!=root or file_digest(path)!=record['sha256']:raise R.StepError('기존 렌더 검수 파일의 지문이 다릅니다.')
        prior=R.unfold_payload(read(path))
        field='focus_measurements' if prior.get('focus_measurements') else 'frames'
        rows=F.normalize_focus_rows(prior.get(field), field)
        if ((prior.get('focus_render_key') or task['payload'].get('local_source_resume')=='stitch_narr') and rows and all(isinstance(row,dict) and row.get('source_identity') in current.values() for row in rows.values())):
            return dict(focus_measurements=rows,frames=rows,focus_render_key=prior.get('focus_render_key'))
    raise R.StepError('현재 원본과 연결된 기존 렌더 검수 기록을 확인하지 못했습니다. 새 유료 요청 없이 기존 결과를 보존합니다.')


def prepare(task,headers=None):
    import volcano_run as R
    import volcano_drive as D
    from longform_state import native_path,read,save
    from film_editor import atomic_bytes,file_digest
    current=_validate(task)
    if task.get('source_versions') is None or task['source_versions']!=current:
        raise _source_changed(task,current)
    root=native_path(task['out_dir']);root.mkdir(parents=True,exist_ok=True)
    with R.review_receipt_lock(str(root/'execution')):
        receipt_path=native_path(task['files']['receipt'])
        if receipt_path.exists():
            saved=read(receipt_path)
            proof=dict(version=1,kernel_id=task['kernel_id'],contract_key=task['contract_key'],files=dict(saved['result']['files'],receipt=dict(path=task['files']['receipt'],sha256=file_digest(receipt_path))))
            verify_proof(proof)
            return dict(saved['result'],files=proof['files'])
        state_path=root/'state.json'
        state=read(state_path) if state_path.exists() else {'payload':dict(copy.deepcopy(task['payload']),**_legacy_film_state(task,current)),'history':[]}
        pl=state['payload']
        if task['payload'].get('local_source_resume') and not state.get('legacy_selection_loaded'):
            prior=_legacy_render(task,current);pl.update(prior);state['legacy_render_key']=prior['focus_render_key'];state['legacy_selection_loaded']=True;save(state_path,state)
        machine=C.bind(task,lambda *args:_focus(task,*args,headers=headers))
        seen=set()
        while True:
            try:
                response=machine['_step_stitch_blocks']({'preset':task['preset'],'payload':pl},None)
            except machine['ToolError'] as exc:
                state['diagnostic']=str(exc);save(state_path,state)
                raise R.StepError(str(exc)) from exc
            state['response']=response;save(state_path,state)
            latest=T._source_versions(task)
            if latest!=current:raise _source_changed(task,latest)
            if response.get('jobs'):
                camera_rebuild=False
                if state.get('legacy_render_key') and machine['volcano_focus'].render_key(task['preset'],pl)!=state['legacy_render_key']:
                    # 고른 장면·편집 규격이 같고 카메라 판만 바뀐 옛 렌더인가 — 옛 렌더가 구워진 카메라 판(작업의 stitch_camera_revision)으로
                    # 열쇠를 다시 잰다. 같으면 블록(화면)만 다시 굽는다(고른 장면·검수·나레이션 WAV 재사용 · 새 유료 요청 없음).
                    # 다르면 장면 또는 규격이 바뀐 것이다 — 기존 렌더를 덮어쓰지 않고 멈춘다.
                    old=machine['volcano_deliver'].stitch_camera_parts(task['payload'].get('stitch_camera_revision'))
                    if not old or machine['volcano_focus'].render_key(task['preset'],pl,camera=old)!=state['legacy_render_key']:
                        raise R.StepError('현재 규격의 계획이 기존 렌더와 다릅니다(고른 장면 또는 편집 규격이 바뀜). 기존 영상·음성·검수를 보존했습니다. 블록 재렌더가 필요하며 자동 덮어쓰기는 하지 않습니다.')
                    camera_rebuild=True
                if any(row['size']!=task['context']['spec']['SRC_SIZE'] for row in pl['focus_measurements'].values()):raise R.StepError('영화 원본의 실제 크기가 서버 측정 규격과 다릅니다.')
                blob=T._bytes(response);atomic_bytes(native_path(task['files']['plan']),blob)
                result=dict(version=1,contract_key=task['contract_key'],status='complete',files={'plan':dict(path=task['files']['plan'],sha256=hashlib.sha256(blob).hexdigest())},counts={'frames':sum(row['scene_evidence']['nframes'] for row in pl['focus_measurements'].values()),'parts':len(pl['focus_measurements']),'runs':len(response['jobs'])},warnings=[*response.get('warnings',[]),*['요청에 따라 생략한 규격: '+note for note in dict.fromkeys(machine['_local_skipped_rules'])]],source_sizes={str(c['card']):next(iter(pl['focus_measurements'].values()))['size'] for c in task['cuts']},review_requests=[],diagnostics={'selection_verified':True,'reuse_render':bool(state.get('legacy_render_key')),'camera_rebuild':camera_rebuild,'render_state':{k:response[k] for k in ('BLOCKS','narr_cut_state','stitch_audio_revision','stitch_camera_revision','stitch_camera_rebuild','master_audio_state','ln_probe','peaks') if k in response}})
                save(native_path(task['files']['receipt']),dict(task=task,sources=current,payload=pl,response=response,result=result))
                result['files']['receipt']=dict(path=task['files']['receipt'],sha256=file_digest(native_path(task['files']['receipt'])))
                return result
            if response.get('status')=='need_input':
                return dict(version=1,contract_key=task['contract_key'],status='pending',files={},counts={},source_sizes={},warnings=response.get('warnings',[]),review_requests=response.get('focus_review_requests',[]),diagnostics={'message':response.get('message'),'author':response.get('author')})
            identity=hashlib.sha256(T._bytes(response)).hexdigest()
            if identity in seen:raise R.StepError('동일한 로컬 복구 요청이 진전 없이 반복됩니다. 기존 증거를 보존합니다.')
            seen.add(identity)
            recovering=state.get('inflight')==identity
            if recovering and (not response.get('do') or any(item.get('cmd')!='review_film_frames' for item in response['do'])):
                raise R.StepError('접수 결과가 확인되지 않은 로컬 검수 요청을 보존합니다. 자동 재전송하지 않습니다.')
            state['inflight']=identity;save(state_path,state)
            execution=copy.deepcopy(response)
            if isinstance(execution.get('frames'),dict):
                execution.pop('frames');execution['carry']=[k for k in execution.get('carry',[]) if k!='frames']
            # 측정 캐시 자리 — 공개 입구의 _attach_framevision 이 화면 측정 명령에 붙이던 실행 보조를 이 고리에서 같은 값으로 붙인다
            # (고르기는 task['selection'] 에서 이미 받는다). 요청 지문(identity)은 위에서 이미 쟀다 — 실행 보조는 지문에 들지 않는다.
            if task['selection'].get('framevision_cache'):
                for item in execution.get('do',[]):
                    if item.get('cmd')=='review_film_frames':item.setdefault('framevision_cache',task['selection']['framevision_cache'])
            if recovering or task['payload'].get('local_source_resume'):
                for item in execution.get('do',[]):
                    if item.get('cmd')=='review_film_frames':item['allow_provider']=False
            updates=D.execute(execution,headers=headers)
            if recovering:
                for item in execution['do']:
                    values=updates.get(item['as']) or {}
                    if not values or any((row.get('semantic_review') or row).get('status')!='accepted' for row in values.values()):
                        raise R.StepError('완료된 검수 증거가 아직 없습니다. 기존 접수 기록을 보존하며 새 요청을 보내지 않습니다.')
            state['history'].append({'request':identity,'updates':updates})
            pl.update({key:response[key] for key in response.get('carry',[]) if key in response});pl.update(updates)
            state.pop('inflight',None);save(state_path,state)


def verify_proof(proof):
    import local_focus as L
    import volcano_run as R
    from longform_state import native_path,read
    from film_editor import file_digest
    files=proof['files']
    for entry in files.values():
        if file_digest(native_path(entry['path']))!=entry['sha256']:raise R.StepError('로컬 영화 계획 증거 파일이 변경됐습니다.')
    receipt=read(native_path(files['receipt']['path']));task=receipt['task']
    if set(files)!=set(task['files']) or any(files[k]['path']!=v for k,v in task['files'].items()):raise R.StepError('로컬 영화 실행 증거 경로가 다릅니다.')
    if task['contract_key']!=proof['contract_key'] or task['kernel_id']!=proof['kernel_id']:
        raise R.StepError('로컬 영화 계획의 계약이 다릅니다.')
    current=_validate(task)
    if receipt['sources']!=current:
        raise _source_changed(task,current)
    plan=read(native_path(files['plan']['path']))
    if plan!=receipt['response']:raise R.StepError('로컬 영화 실행 계획과 보존된 증거가 다릅니다.')
    pl=copy.deepcopy(receipt['payload'])
    def verified(scope,cuts,preset,step,wd):
        rows=scope.get('focus_measurements') or {};saved=scope.get('focus_state') or {}
        for cut in cuts:
            card=str(cut['card']);meta=saved.get('receipts',{}).get(card)
            if not meta:raise R.StepError('영화 계획에 연결된 원본 검수 증거가 없습니다.')
            L.verify_render_receipt(dict(focus_receipt=meta['path'],focus_key=meta['focus_key'],local_focus=dict(version=1,kernel_id=F.KERNEL_ID,contract_key=saved['contract_key'],sha256=meta['sha256'])),rows[card])
            expected=dict(cut,selection_recipe=task['context']['focus_settings'][1])
            if F.cut_key(expected)!=meta['focus_key']:raise R.StepError('영화 계획의 컷과 원본 검수 범위가 다릅니다.')
        return rows,None
    machine=C.bind(task,verified)
    actual=machine['_step_stitch_blocks']({'preset':task['preset'],'payload':pl},None)
    if actual!=plan:raise R.StepError('보존된 영화 계획이 정본 계산 결과와 다릅니다.')
    return plan


def _input_value(key,value):
    """확정된 계획과 실행 입력을 «뜻» 으로 견준다. 언어는 계산하는 모든 자리(서버 volcano_tools._lang_of · 정본 stitch_kit ·
    volcano_stitch)가 같은 자로 읽는다 — 없음·'ko'·'ko-KR'·'KO' 는 같은 한국어다. 글자 그대로 견주면 같은 언어를 다르게 적은
    인계·마스터가 «입력이 다릅니다» 로 멈췄다(2026-10-21 · test_film_ctc_contract 로캘 ko-KR/KO). 다른 언어(en 등)는 여전히 다르다."""
    if key=='lang':return str(value or 'ko').lower().split('-')[0]
    return value


def delivery_packet(proof,payload,*,directory,text_records,custom_files):
    """Compute the original editor keyframes using the exact canonical stitch kit."""
    import types
    from longform_state import native_path,read
    import volcano_run as R
    verify_proof(proof)
    saved=read(native_path(proof['files']['receipt']['path']));task=saved['task']
    pl=copy.deepcopy(saved['payload'])
    for key in ('SRC','SRC_SIZE','SRC_CROP','BLOCKS','wav_secs','HEADLINE','scene_cuts','lang'):
        if key in payload and _input_value(key,payload[key])!=_input_value(key,pl.get(key)):raise R.StepError('편집 인계와 검증된 영화 계획의 입력이 다릅니다: '+key)
    pl.update({key:copy.deepcopy(value) for key,value in payload.items() if key not in ('frames','focus_measurements','focus_state')})
    machine=C.bind(task,lambda *args:(_ for _ in ()).throw(R.StepError('편집 인계에서 추가 피사체 검수를 요청하지 않습니다.')))
    module=machine['volcano_deliver']
    module.volcano_custom_native=types.SimpleNamespace(editor_files=lambda *args:(text_records,custom_files))
    module.build_kit=lambda *args,**kwargs:[{'args':list(args),'kwargs':kwargs}]
    return module.stitch_kit(task['preset'],pl,task['context']['render'],directory)


def checked_execution(plan):
    """Separate preserved measurements from executable frame render instructions."""
    value=copy.deepcopy(plan)
    dense={'frames','focus_measurements','focus_state','film_frame_state','film_recovery_state','film_semantic_state'}
    for key in dense:value.pop(key,None)
    value['carry']=[k for k in value.get('carry',[]) if k not in dense]
    return value


def verify_inputs(proof,inputs):
    import volcano_run as R
    from longform_state import native_path,read
    verify_proof(proof)
    saved=read(native_path(proof['files']['receipt']['path']))
    for key,value in inputs.items():
        if T._bytes(_input_value(key,value))!=T._bytes(_input_value(key,saved['payload'].get(key))):
            raise R.StepError('확정된 영화 계획과 실행 입력이 다릅니다: '+key)
    return [{'path':path,'sha256':digest} for path,digest in saved['sources'].items()]


def preserve_wire_evidence(payload):
    """Archive legacy dense source state before creating the compact RPC copy."""
    import local_focus as L
    import volcano_run as R
    from longform_state import native_path,read,save
    from film_editor import file_digest
    directory=str(payload['workdir']).rstrip('/')+'/local-source/evidence'
    root=native_path(directory);root.mkdir(parents=True,exist_ok=True)
    fields={'film_frame_state','film_recovery_state','film_semantic_state','film_semantic_frames','film_recovery_frames','film_recovery_text_results'}
    evidence={key:payload[key] for key in fields if key in payload}
    if evidence:
        source=native_path(payload.get('SRC') or payload.get('source') or '')
        if source.is_file():
            source_sha=file_digest(source)
            rows=[]
            for key in ('frames','focus_measurements','film_semantic_frames','film_recovery_frames'):
                # Examine decoded local copies only; evidence below retains the
                # exact submitted JSON strings and never rewrites paid receipts.
                value=payload.get(key)
                try:
                    normalized=F.normalize_focus_rows(value, key if key in ('frames','focus_measurements') else 'frames')
                except ValueError as error:
                    raise R.StepError(str(error).replace('payload.frames', 'payload.'+key, 1)) from error
                rows.extend(row for row in normalized.values() if isinstance(row,dict))
            verified=bool(rows) and all((row.get('source_identity') or (row.get('scene_evidence') or {}).get('source_identity'))==source_sha for row in rows)
            evidence['_source_binding']=dict(inputs={key:payload.get(key) for key in ('SRC','SRC_SIZE','SRC_CROP','BLOCKS','wav_secs','scene_cuts')},source_sha256=source_sha,verified_rows=verified)
        with R.review_receipt_lock(str(root/'film-evidence')):
            digest=hashlib.sha256(T._bytes(evidence)).hexdigest();path=root/('film-'+digest+'.json')
            if path.exists() and read(path)!=evidence:raise R.StepError('보존된 영화 검수 상태가 변경됐습니다.')
            if not path.exists():save(path,evidence)
            indexpath=root/'film-index.json';index=read(indexpath) if indexpath.exists() else {'records':[]}
            record={'file':path.name,'sha256':file_digest(path)}
            if record not in index['records']:index['records'].append(record);save(indexpath,index)
    wire={key:value for key,value in L.preserve_wire_evidence(payload,out_dir=directory).items() if key not in fields}
    if payload.get('focus_measurements') or payload.get('frames') or payload.get('_focus_pack'):wire['local_source_cached_focus']=True
    return wire


def export_files(item):
    import source_export_kernel as E
    from longform_state import native_path,read
    import volcano_run as R
    proof=item['proof']
    packet=delivery_packet(proof,item['payload'],directory=item['directory'],text_records=item['text_records'],custom_files=item['custom_files'])
    saved=read(native_path(proof['files']['receipt']['path']));task=saved['task']
    exporter=E.build_modules(copy.deepcopy(task['context']['export_policy']))['volcano_deliver']
    exporter.volcano_spec.person_spec=lambda preset:copy.deepcopy(task['context']['person'])
    files=exporter.build_kit(*packet[0]['args'],**packet[0]['kwargs'])+packet[1:]
    for entry in files:
        blob=entry['content'].encode('utf-8');entry.update(bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest())
        if not native_path(entry['path']).resolve().is_relative_to(native_path(item['directory']).resolve()):
            raise R.StepError('편집 인계 결과 경로가 지정한 폴더 밖입니다.')
    return files
