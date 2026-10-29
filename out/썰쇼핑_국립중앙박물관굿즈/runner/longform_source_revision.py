"""Re-probe changed local originals before review or narration, preserving history."""
import copy
import hashlib
import json
import math


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def sources(plan,native_path):
    """media id → local path for every registered source, or None when the plan's media cannot be bound here.

    The production-plan contract is judged in ONE place — the engine preflight, in the Python the env step verified
    (longform_engine.preflight → every violation back to the author through longform_run). This check runs inside the
    runner driver's own Python (no Pillow there · 2026-10-17 #117: rid 479672 died with «No module named 'PIL'»), and
    used to raise the first contract violation as a runner crash. A plan whose media is malformed or missing is left to
    that preflight, which reports it with every other violation; nothing is bound, and nothing paid runs before it."""
    media=plan.get('media')
    if not isinstance(media,dict) or not media:return None
    paths={}
    for mid,asset in media.items():
        if not isinstance(asset,dict) or not isinstance(asset.get('path'),str) or not asset['path'].strip() or not isinstance(asset.get('sha256'),str):
            return None
        path=native_path(asset['path'])
        if not path.is_file():return None
        paths[mid]=path
    return paths


def check(res):
    from film_editor import file_digest,probe,file_lock
    from longform_state import native_path,save
    from volcano_run import StepError
    contract=res.get('longform_source_check')
    if contract is None:return []
    plan=res.get('longform_project')
    if not isinstance(contract,dict) or not isinstance(plan,dict) or contract.get('plan_id')!=identity(plan):
        raise StepError('롱폼 원본 확인 계약이 제작표와 다릅니다.')
    paths=sources(plan,native_path)
    if paths is None:return []
    assets=plan['media'];current={mid:file_digest(path) for mid,path in paths.items()}
    changed={mid for mid,a in assets.items() if current[mid]!=a['sha256']}
    if not changed:return [dict(path=a['path'],sha256=current[mid]) for mid,a in assets.items()]
    root=native_path(contract['workdir'])/'geumbit'/'source-revisions'
    proposed=copy.deepcopy(plan)
    def walk(value):
        if isinstance(value,list):
            for child in value:yield from walk(child)
        elif isinstance(value,dict):
            yield value
            for key,child in value.items():
                if key!='video_treatment':yield from walk(child)
    # Old treatment receipts must be intact even when their original is replaced.
    for node in walk(plan.get('blocks')):
        treatment=node.get('video_treatment')
        if not treatment:continue
        proof=treatment.get('local_focus') or {};path=native_path(treatment['focus_receipt'])
        if not proof.get('sha256') or file_digest(path)!=proof['sha256']:
            raise StepError('보존된 롱폼 검수 증거가 변경되었습니다. 원본 교체로 우회하지 않습니다.')
        row=json.loads(path.read_text(encoding='utf-8'))
        mids=node.get('media');mid=mids[0] if isinstance(mids,list) and mids else mids
        if row.get('source_identity')!=(assets.get(mid) or {}).get('sha256') or row.get('focus_key')!=treatment['focus_key']:
            raise StepError('보존된 롱폼 검수 증거와 제작표가 다릅니다.')
    with file_lock(root/'revision.lock'):
        reports={}
        for mid in sorted(changed):
            attempt=root/current[mid];attempt.mkdir(parents=True,exist_ok=True)
            report=probe(attempt,str(native_path(assets[mid]['path'])))
            streams=report.get('streams',[])
            visual=[s for s in streams if s.get('codec_type')=='video']
            if not visual or any(int(visual[0].get(k,0))<=0 for k in ('width','height')):
                raise StepError('교체 소재의 영상·이미지 크기를 확인하지 못했습니다: '+mid)
            for node in walk(plan.get('blocks')):
                mids=node.get('media');ids=mids if isinstance(mids,list) else [mids]
                if mid not in ids or node.get('kind')!='video':continue
                # A malformed in/out is a contract violation: the preflight that follows this re-seed reports it.
                if not all(type(node.get(k)) in (int,float) for k in ('in','out')):continue
                duration=float(report.get('format',{}).get('duration') or visual[0].get('duration') or 0)
                start,end=float(node['in']),float(node['out'])
                if not math.isfinite(duration) or not 0<=start<end<=duration:
                    raise StepError('교체 영상이 기존 사용 구간을 포함하지 않습니다: '+mid)
            reports[mid]=report
            proposed['media'][mid]['sha256']=current[mid]
        if {mid:file_digest(path) for mid,path in paths.items()}!=current:
            raise StepError('소재 확인 중 파일이 변경됐습니다. 기존 기록을 보존하고 멈춥니다.')
        # The proposed plan re-enters longform_seed; its preflight judges the contract (one place · see sources()).
        # Content-addressed history is never replaced with different bytes.
        for value in (plan,proposed):
            path=root/(identity(value)+'.plan.json')
            if path.exists():
                if json.loads(path.read_text(encoding='utf-8'))!=value:
                    raise StepError('보존된 제작표 이력이 손상됐습니다.')
            else:save(path,value)
        report_path=root/(identity(proposed)+'.'+identity(reports)+'.probe.json')
        if not report_path.exists():save(report_path,reports)
    error=StepError('교체 소재를 로컬에서 확인했습니다. 기존 음성·검수 기록을 보존하고 피사체 검수를 연결합니다.')
    error.code='longform_source_changed';error.execution_next_step='longform_seed'
    error.execution_recovery={'longform_project':proposed,'local_focus_result':None,'longform_preflight':None}
    raise error
