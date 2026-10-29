"""Prospective engine roots and durable accepted-job selection (no model calls)."""
import hashlib
import json
import re
from pathlib import Path
from repair_state_stage import physical, children, matching, resolved


def _json(path):
    return json.loads(physical(path).read_text(encoding='utf-8-sig'))


def _sha(path):
    h=hashlib.sha256()
    with physical(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def version_parent(workdir, revision):
    if not re.fullmatch('[a-f0-9]{64}',str(revision)):
        raise ValueError('Engine pack SHA is required')
    return resolved(workdir)/'.volcano-engines'/revision


def _job_id(cfg):
    selected=cfg.get('jobId')
    request=cfg.get('request') or {}
    from_request=('j_'+hashlib.sha256(request['requestId'].encode()).hexdigest()) if request.get('requestId') else None
    if selected and from_request and selected!=from_request:
        raise ValueError('Engine job and request identities disagree')
    selected=selected or from_request
    if selected is not None and not re.fullmatch('j_[a-f0-9]{64}',str(selected)):
        raise ValueError('Engine job identity is invalid')
    return selected


def _validate(root, job_id, known_stats=None, *, verify_files=True):
    # 파일 경로는 실제 경로로 풀어(resolved) 뿌리 안인지 본다 — 뿌리도 같은 자로 푼다(링크 걸린 작업 폴더 · 맥 /var→/private/var).
    root=resolved(root)
    folder=root/'work'/'_episode_jobs'/job_id
    job=_json(folder/'job.json');manifest=job.get('repairManifest') or _json(folder/'code_manifest.json')
    if (job.get('jobId')!=job_id or manifest.get('version')!=1
            or not re.fullmatch('[a-f0-9]{64}',str(job.get('requestSha256')))
            or manifest.get('codeIdentity')!=job.get('codeIdentity')):
        raise ValueError('Accepted engine job manifest is inconsistent')
    files=manifest.get('files')
    if not isinstance(files,list) or not files:
        raise ValueError('Accepted engine manifest has no files')
    canonical=json.dumps(files,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(canonical).hexdigest()!=job.get('codeIdentity'):
        raise ValueError('Accepted engine manifest identity changed')
    import file_witness as W
    measured = {}
    for entry in (files if verify_files else []):
        relative=str(entry['path']).replace('\\','/')
        raw=root/relative
        path=resolved(raw)
        if not path.is_relative_to(root) or physical(raw).is_symlink() or not physical(path).is_file():
            raise ValueError('Accepted engine files changed; original job and paid receipts preserved')
        fingerprint=W.stamp(physical(path))
        previous=(known_stats or {}).get(entry['path'])
        # settled: 잴 때 이미 가라앉은 증거였나(file_witness.memoizable) — 앞의 기록도 가라앉았을 때만 같은 증거로 해시를 건너뛴다.
        measured[entry['path']]={'stat':fingerprint,'sha256':entry['sha256'],'settled':W.memoizable(fingerprint)}
        # Polling uses reliable metadata without re-reading large references.
        # Windows creation time is insufficient. Unknown change witnesses force
        # fresh hashing; old five-field memo rows naturally invalidate once.
        if fingerprint[0]!=entry['bytes']:
            raise ValueError('Accepted engine files changed; original job and paid receipts preserved')
        if not measured[entry['path']]['settled'] or previous!=measured[entry['path']]:
            actual=_sha(path)
            if W.stamp(physical(path))!=fingerprint or actual!=entry['sha256']:
                raise ValueError('Accepted engine files changed; original job and paid receipts preserved')
    # The engine rechecks its complete production manifest (including additions)
    # before resuming. This selector never changes codeIdentity or reader SHA.
    module=resolved(job.get('engineModule',''))
    if not module.is_relative_to(root) or not physical(module).is_file():
        raise ValueError('Accepted engine entry path changed')
    return job,measured


def resolve(cfg):
    from longform_state import save
    from volcano_run import review_receipt_lock
    wd=resolved(cfg['workdir'])
    newest=version_parent(wd,cfg['pack_revision'])/'info3d'
    job_id=_job_id(cfg)
    if job_id:
        cfg=dict(cfg,jobId=job_id)
        from repair_transition import recover
        recovered=recover(cfg,_json,_validate)
        if recovered:return recovered
    root=newest
    pins=wd/'.volcano-engine-jobs';physical(pins).mkdir(parents=True,exist_ok=True)
    with review_receipt_lock(str(physical(pins/'selection'))):
        record_path=pins/(job_id+'.json') if job_id else None
        if record_path and physical(record_path).exists():
            record=_json(record_path);root=resolved(record['root'])
            permitted=(root==wd/'info3d' or root.parent.parent==wd/'.volcano-engines'
                or (root.parent.parent.parent==wd/'.volcano-engine-repairs' and root.parent.parent.name==job_id))
            if not permitted:raise ValueError('Pinned engine root is outside this workspace')
            if record.get('engine_runtime_root'):cfg=dict(cfg,engine_runtime_root=record['engine_runtime_root'])
            job,stats=_validate(root,job_id,record.get('file_stats'),verify_files=not bool(cfg.get('repairRelease')))
            if any(record.get(k)!=job.get(k) for k in ('jobId','requestSha256','codeIdentity')):
                raise ValueError('Pinned accepted job identity changed')
            if not cfg.get('repairRelease') and record.get('file_stats')!=stats:save(record_path,dict(record,file_stats=stats))
        elif job_id:
            candidates=[wd/'info3d']
            parent=wd/'.volcano-engines'
            if physical(parent).exists():
                candidates.extend(p/'info3d' for p in children(parent) if physical(p).is_dir() and re.fullmatch('[a-f0-9]{64}',p.name))
            found=[resolved(p) for p in candidates if physical(p/'work'/'_episode_jobs'/job_id/'job.json').exists()]
            if len(found)>1:raise ValueError('Accepted job exists in multiple engine roots; preserve both')
            if found:
                root=found[0]
                if not root.is_relative_to(wd):raise ValueError('Accepted engine root resolves outside this workspace')
                job,stats=_validate(root,job_id,verify_files=not bool(cfg.get('repairRelease')))
                save(record_path,dict(version=1,root=str(root),file_stats=stats,**{k:job[k] for k in ('jobId','requestSha256','codeIdentity')}))
            elif cfg.get('mode') in ('status','resume','result','cancel'):
                raise ValueError('Accepted job original root is unavailable; no new order was created')
        selected=dict(cfg,root=str(root),fonts_dir=str(root/'fonts'))
        return selected


LIVE_STATES=('accepted','running','cancelling')
#: 상태 물음에 실을 수 없는 칸 — 이어 하기·새 주문 전용(연장·수리판·다시 뽑을 컷·주문서)과 지금 판의 실행 뿌리(다른 판 뿌리는 제 것을 쓴다).
_STATUS_DROP=('deadlineExtension','repairRelease','redoCuts','request','engine_runtime_root')


def _engine_state(selected, root, job, execute_call):
    """다른 판 뿌리에 «받은 상태»로 적힌 주문이 지금 정말 도는가 — 그 판 엔진의 status(episode_jobs.publicState) 한 정의로 본다.
    ★10-21 회원 신고: 실행기가 강제 종료된 회차는 엔진 status 가 interrupted(WORKER_INTERRUPTED — worker 가 기록 없이 끝남)로 알리지만
      job.json 의 state 는 'running' 그대로다(엔진은 기록을 해석할 뿐 고쳐 쓰지 않는다 · cancel 도 살아 있는 회차만 바꾼다). 종전에는 기록의
      글자만 보고 «다른 판이 도는 중»으로 새 판 접수를 영영 막았다. 돌려줌 = 엔진이 알린 상태 · 알 수 없으면(물음 실패·다른 주문의 답)
      None — 부르는 쪽은 그때 막는다(도는 주문 위에 새 주문을 얹지 않는다)."""
    root=resolved(root)
    probe={k:v for k,v in selected.items() if k not in _STATUS_DROP}
    probe.update(mode='status',root=str(root),fonts_dir=str(root/'fonts'),jobId=job.get('jobId'),runId=job.get('runId'),waitSeconds=0)
    try:
        out=execute_call(probe)
    except Exception as exc:                       # 엔진 물음이 실패 — 모른다(막는다 · 까닭은 막는 글에 싣는다)
        return None,f'{type(exc).__name__}: {exc}'[:300]
    if not (isinstance(out,dict) and out.get('ok') is True and out.get('jobId')==job.get('jobId') and isinstance(out.get('state'),str)):
        return None,json.dumps(out,ensure_ascii=False)[:300] if isinstance(out,dict) else repr(out)[:300]
    return out['state'],None


def dispatch(cfg, execute_call):
    """Serialize new launches across versions; status/cancel remain responsive."""
    from volcano_run import review_receipt_lock
    selected=resolve(cfg)
    if selected.get('repairRelease') is not None:
        from repair_transition import execute
        return execute(dict(cfg,jobId=_job_id(cfg)),selected,execute_call,_json,_validate)
    if selected.get('mode') not in ('start','resume'):
        return execute_call(selected)
    wd=resolved(selected['workdir']);current=resolved(selected['root'])
    with review_receipt_lock(str(physical(wd/'.volcano-engine-jobs'/'launch'))):
        roots=[wd/'info3d']
        versions=wd/'.volcano-engines'
        if physical(versions).exists():roots.extend(p/'info3d' for p in children(versions) if physical(p).is_dir() and re.fullmatch('[a-f0-9]{64}',p.name))
        repairs=wd/'.volcano-engine-repairs'
        if physical(repairs).exists():roots.extend(matching(repairs,'j_*/*/info3d'))
        for root in roots:
            if resolved(root)==current:continue
            directory=root/'work/_episode_jobs'
            if not physical(directory).exists():continue
            for path in matching(directory,'j_*/job.json'):
                job=_json(path)
                if job.get('state') not in LIVE_STATES:
                    continue
                state,why=_engine_state(selected,root,job,execute_call)
                if state is None or state in LIVE_STATES:
                    raise ValueError('Another engine version has an active job; preserve it and inspect its status before launching'
                                     f' (job {job.get("jobId")} · engine status: {state or why})')
        return execute_call(selected)
