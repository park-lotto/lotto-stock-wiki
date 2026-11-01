"""Durable repair admission transaction. Never retries an uncertain dispatch."""
import hashlib
from pathlib import Path
from repair_state_stage import stage, physical, matching, resolved

RELEASES={'reader-resume-20261002':'repair_release.json','content-batching-20261003':'repair_content_batching.json','numeric-parts-20261003':'repair_numeric_parts.json'}

def path_for(wd, job):return wd/'.volcano-engine-jobs'/(job+'.repair.json')

def recover(cfg, read, validate):
    from longform_state import save
    wd=resolved(cfg['workdir']);job_id=cfg['jobId'];path=path_for(wd,job_id)
    if not physical(path).exists():return None
    tx=read(path)
    if tx.get('phase')=='admitted' and not cfg.get('repairRelease'):
        if cfg.get('runId')==tx.get('old_run'):cfg['runId']=tx['run_id']
        return None
    different=bool(cfg.get('repairRelease') and cfg['repairRelease']!=tx.get('release'))
    root=resolved(tx['root'])
    expected=wd/'.volcano-engine-repairs'/job_id/tx['descriptor_sha256']/'info3d'
    if root!=expected or not root.is_relative_to(wd):raise ValueError('Invalid repair transaction root')
    job=read(root/'work/_episode_jobs'/job_id/'job.json')
    admitted=any(h.get('releaseId')==tx['release'] and h.get('previous',{}).get('runId')==tx['old_run'] for h in job.get('repairHistory',[]))
    if admitted:
        if job.get('runId')==tx['old_run'] or job.get('requestSha256')!=tx['request_sha256']:
            raise ValueError('Repair admission identity mismatch')
        job,stats=validate(root,job_id)
        save(wd/'.volcano-engine-jobs'/(job_id+'.json'),dict(version=1,root=str(root),file_stats=stats,engine_runtime_root=tx.get('runtime_root',tx['source_root']),
            **{k:job[k] for k in ('jobId','requestSha256','codeIdentity')}))
        save(path,dict(tx,phase='admitted',run_id=job['runId']))
        if different and not any(h.get('releaseId')==cfg['repairRelease'] for h in job.get('repairHistory',[])):
            # A later explicitly selected release is a new admission, not a
            # poll of this earlier release. Its own signed engine gate decides.
            return None
        if cfg.get('runId')==tx['old_run']:cfg['runId']=job['runId']
        # Retried repair request observes the already-admitted attempt, even if
        # that attempt failed meanwhile. It never dispatches it a second time.
        return dict(cfg,root=str(root),fonts_dir=str(root/'fonts'),engine_runtime_root=tx.get('runtime_root',tx['source_root']),mode='status',runId=job['runId'],repairRelease=None) if cfg.get('repairRelease') else None
    if different:
        if tx['phase']=='denied':return None
        raise ValueError('Previous repair admission is unresolved; no different release dispatched')
    if tx['phase']=='inflight':
        raise ValueError('Repair admission outcome is uncertain; original receipts preserved; inspect existing job, do not resend')
    if cfg.get('repairRelease') and tx['phase']=='denied':
        raise ValueError('Signed repair admission was denied; original pin and receipts preserved')
    return None


def execute(cfg, selected, invoke, read, validate):
    from longform_state import save
    from volcano_run import review_receipt_lock
    wd=resolved(cfg['workdir']);job_id=cfg['jobId'];release=cfg.get('repairRelease')
    if release not in RELEASES or cfg.get('mode')!='resume':raise ValueError('Unsupported repair command')
    with review_receipt_lock(str(physical(wd/'.volcano-engine-jobs'/'launch'))):
        recovered=recover(cfg,read,validate)
        if recovered:return invoke(recovered)
        for entry in matching(wd,'.volcano-engines/*/info3d/work/_episode_jobs/j_*/job.json'):
            other=read(entry)
            if other.get('jobId')!=job_id and other.get('state') in ('accepted','running','cancelling'):
                raise ValueError('Another accepted job is active; repair did not dispatch')
        for pattern in ('info3d/work/_episode_jobs/j_*/job.json','.volcano-engine-repairs/j_*/*/info3d/work/_episode_jobs/j_*/job.json'):
            for entry in matching(wd,pattern):
                other=read(entry)
                if other.get('jobId')!=job_id and other.get('state') in ('accepted','running','cancelling'):
                    raise ValueError('Another accepted job is active; repair did not dispatch')
        old=resolved(selected['root'])
        runtime=resolved(selected.get('engine_runtime_root') or old)
        if not runtime.is_relative_to(wd):raise ValueError('Repair runtime root is outside this workspace')
        new=wd/'.volcano-engines'/cfg['pack_revision']/'info3d'
        descriptor=hashlib.sha256(physical(new/RELEASES[release]).read_bytes()).hexdigest()
        root=wd/'.volcano-engine-repairs'/job_id/descriptor/'info3d'
        path=path_for(wd,job_id)
        tx=read(path) if physical(path).exists() else None
        if tx and tx.get('release')!=release:
            if tx.get('phase') not in ('admitted','denied'):
                raise ValueError('Previous repair admission is unresolved')
            # Preserve exact previous transaction bytes before publishing its
            # successor. A crash between these writes leaves the old transaction
            # recoverable; an uncertain dispatch is never archived or resent.
            from film_editor import atomic_bytes
            raw=physical(path).read_bytes()
            history=path.with_name(path.name+'.'+hashlib.sha256(raw).hexdigest()+'.history')
            if physical(history).exists():
                if physical(history).read_bytes()!=raw:raise ValueError('Repair transaction archive changed')
            else:atomic_bytes(physical(history),raw)
            tx=None
        if tx:
            if tx['phase']!='prepared':raise ValueError('Repair transaction is not ready')
        else:
            job=read(old/'work/_episode_jobs'/job_id/'job.json')
            stage(old,new,root,job_id)
            tx={'version':1,'root':str(root),'source_root':str(old),'runtime_root':str(runtime),'descriptor_sha256':descriptor,
                'release':release,'old_run':job['runId'],'request_sha256':job['requestSha256'],'phase':'prepared'}
            save(path,tx)
        # Persist before entering a controller that may start a worker. A crash
        # after admission is recovered from durable engine repairHistory.
        save(path,dict(tx,phase='inflight'))
        result=invoke(dict(cfg,root=str(root),fonts_dir=str(root/'fonts'),engine_runtime_root=tx.get('runtime_root',tx['source_root'])))
        current=read(root/'work/_episode_jobs'/job_id/'job.json')
        admitted=any(h.get('releaseId')==release and h.get('previous',{}).get('runId')==tx['old_run'] for h in current.get('repairHistory',[]))
        recovered=recover(cfg,read,validate) if admitted else None
        if recovered:return result
        if isinstance(result,dict) and result.get('ok') is False:
            save(path,dict(tx,phase='denied'))
        return result
