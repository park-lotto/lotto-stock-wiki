"""Isolated proposed production contracts. No deployment or HTTP registration.

Original reads grant only current-account data access. Existing server gates
remain authoritative for preset, review and TA execution after local recovery.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from original_import import SHA, owner, digest, _read_checked

DENSE = frozenset(('frames','focus_frames','focus_measurements','focus_recovery',
    'focus_state','video_text_state','video_text_results','_focus_pack','_focus_recovery_pack',
    'photo_text_state','photo_text_results','focus_render_key','film_frame_state',
    'film_recovery_state','film_semantic_state','film_semantic_frames','film_recovery_frames',
    'film_recovery_text_results'))


def require_local_capability(caps, preset, step):
    if type(caps.get('local_original_import_version')) is not int or caps['local_original_import_version'] != 1:
        raise ValueError('original import capability unavailable; no expanded upload fallback')
    if step in ('person_frame','person_render','person_deliver'):
        name, presets = 'local_person_version','local_person_presets'
    elif step in ('stitch_narr','stitch_blocks','stitch_master','deliver') and preset in caps.get('local_source_presets',[]):
        name, presets = 'local_source_version','local_source_presets'
    elif preset == '쇼핑' and step in ('shop_frame','shop_cuts','shop_render','shop_deliver'):
        name,presets = 'local_shop_version',None
    elif preset == '어랍숏' and step in ('redub_master','deliver'):
        name,presets = 'local_redub_version',None
    elif step in ('render_plan','render_mix','deliver'):
        name,presets = 'local_render_version','local_render_presets'
    elif preset == '인물형 롱폼' and step in ('longform_seed','longform_run','longform_status','longform_deliver'):
        name,presets = 'local_focus_version',None
    else:
        raise ValueError('this step has no negotiated local original consumer')
    if type(caps.get(name)) is not int or caps[name] != 1 or (presets and preset not in caps.get(presets, [])):
        raise ValueError('local compute capability unavailable; no dense fallback')
    return name




def durable_raw_import(root, metadata, chunks, *, expected_owner, preset, max_bytes):
    """Use shipped OS lock and Windows publication policy, preserving raw bytes."""
    from longform_state import native_path
    import volcano_run as R
    sha=metadata.get('sha')
    if (type(metadata.get('version')) is not int or metadata['version'] != 1
            or metadata.get('owner')!=expected_owner or metadata.get('preset')!=preset
            or not isinstance(sha,str) or not SHA.fullmatch(sha)
            or type(metadata.get('size')) is not int or type(max_bytes) is not int
            or not 0<metadata['size']<=max_bytes):raise ValueError('authenticated original metadata mismatch')
    root=native_path(root);root.mkdir(parents=True,exist_ok=True)
    final=root/(sha+'.json')
    with R.review_receipt_lock(root/(sha+'.publication')):
        if final.exists():return _read_checked(final,sha,max_bytes)
        fd,name=tempfile.mkstemp(prefix=sha+'.',suffix='.part',dir=root)
        temp=Path(name);keep=False
        try:
            total=0
            with os.fdopen(fd,'wb') as out:
                for part in chunks:
                    if not isinstance(part,bytes):raise ValueError('invalid original stream')
                    total+=len(part)
                    if total>metadata['size']:raise ValueError('original stream exceeds declared size')
                    out.write(part)
                if total!=metadata['size']:raise ValueError('truncated original stream')
                out.flush();os.fsync(out.fileno())
            value=_read_checked(temp,sha,max_bytes)
            # Same existing publication retry policy as _photo_write_state;
            # retries only Windows filesystem sharing, NEVER download/execution.
            delays=(0.05,0.1,0.2,0.4,0.8)
            for attempt in range(len(delays)+1):
                try:
                    os.replace(temp,final);break
                except OSError as error:
                    if getattr(error,'winerror',None) not in (5,32,33) or attempt==len(delays):
                        keep=True
                        failure=OSError('verified raw original publication failed; preserve '+str(temp))
                        failure.recovery_path=str(temp);failure.target_path=str(final)
                        raise failure from error
                    time.sleep(delays[attempt])
            return value
        finally:
            if not keep:temp.unlink(missing_ok=True)


def original_refs(value):
    """Read child references locally from hash-verified parent bytes only."""
    from local_resolver import _marker,_wire
    found=set();stack=[value]
    while stack:
        item=stack.pop()
        if isinstance(item,dict):
            if '_blob' in item:
                _marker(item);found.add(item['sha']);continue
            if '_wire_blob' in item:
                plain,entries=_wire(item,review_refs=True)
                found.update(sha for _,sha in entries);stack.append(plain);continue
            stack.extend(item.values())
        elif isinstance(item,list):stack.extend(item)
    return found


def fetch_original_graph(root, compact, *, fetch, expected_owner, preset, max_bytes):
    """Each child is owner-authorized separately; parent linkage is SHA-verified.

    fetch is a single authenticated streaming operation with no retry policy.
    Returned graph edges are provenance, not server execution authority.
    """
    from local_resolver import _unwrap
    args=copy.deepcopy(compact);args['payload']=_unwrap(args.get('payload',{}))
    pending=sorted(original_refs(args));loaded={};edges={}
    while pending:
        sha=pending.pop()
        if sha in loaded:continue
        metadata=fetch(sha)
        if metadata.get('sha')!=sha:raise ValueError('server original identity differs')
        try:
            value=durable_raw_import(root,metadata,metadata['body'],expected_owner=expected_owner,preset=preset,max_bytes=max_bytes)
        finally:
            close=metadata.get('close')
            if callable(close):close()
        loaded[sha]=value
        children=original_refs(value);edges[sha]=sorted(children)
        pending.extend(sorted(children-set(loaded)))
    return dict(version=1,compact_request_sha=digest(compact),original_shas=sorted(loaded),edges=edges)


def compact_for_import(payload, preset, step, caps):
    """Archive through existing durable paths, then deny any residual dense RPC."""
    require_local_capability(caps,preset,step)
    if step in ('stitch_narr','stitch_blocks','stitch_master','deliver') and preset in caps.get('local_source_presets',[]):
        from local_source_plan import preserve_wire_evidence
        wire=preserve_wire_evidence(payload)
    else:
        from local_focus import preserve_wire_evidence
        family=('person' if step.startswith('person_') else 'shop' if step.startswith('shop_') else
                'redub' if step=='redub_master' or preset=='어랍숏' else 'render' if step in ('render_plan','render_mix','deliver') else 'focus')
        wire=preserve_wire_evidence(payload,out_dir=str(payload['workdir']).rstrip('/\\')+'/local-'+family+'/evidence')
    if DENSE.intersection(wire):raise ValueError('unhandled dense field; preserve locally, do not upload')
    if step in ('person_frame','person_render','person_deliver'):wire=dict(wire,local_person_version=1)
    if step in ('render_plan','render_mix','deliver') and preset in caps.get('local_render_presets',[]):wire=dict(wire,local_render_version=1)
    return wire




def imported_client_class():
    """One live capability read per imported step; never a dense fallback.

    Existing Client owns RPC pacing, refusal handling and paid uncertainty. The
    temporary cache only deduplicates caps reads within this one step, never
    persists across requests or masks a server rollback on the next step.
    """
    import volcano_run as R
    class ImportedClient(R.Client):
        def _prepare_imported_payload(self,name,payload,source,tool):
            actual_tool=tool or self.tool
            if actual_tool!='volcano_video' or not isinstance(payload,dict) or not DENSE.intersection(payload):
                return payload
            caps=getattr(self,'_receipt_step_caps',None)
            if not isinstance(caps,dict):caps=self._wire_rpc({'op':'caps'})
            self._receipt_step_caps=caps
            return compact_for_import(payload,self.preset,name,caps)
    return ImportedClient


def prepare_imported_request(root, compact, *, caps, fetch, expected_owner,
                             max_bytes, admit, review_defaults=None):
    """Prepare only. No driver/setup/provider action occurs before admission."""
    from local_resolver import resolve_request,_unwrap,_wire
    preset,step=compact.get('preset'),compact.get('step')
    require_local_capability(caps,preset,step)
    inline,_=_wire(_unwrap(compact.get('payload',{})),review_refs=True)
    workdir=inline.get('workdir')
    if not isinstance(workdir,str) or not workdir.strip():
        raise ValueError('workdir must be inline; no inferred storage location')
    graph=fetch_original_graph(root,compact,fetch=fetch,expected_owner=expected_owner,preset=preset,max_bytes=max_bytes)
    restored,receipt=resolve_request(root,compact,allowed_shas=set(graph['original_shas']),expected_workdir=workdir,
                                    max_original_bytes=max_bytes,focus_refs=True,review_refs=True)
    defaults=review_defaults or {}
    if not isinstance(defaults,dict) or set(defaults)-{'review_policy','review_client','mcp_host'}:
        raise ValueError('invalid captured review defaults')
    for key,value in defaults.items():restored['payload'].setdefault(key,copy.deepcopy(value))
    receipt['restored_request_sha']=digest(restored)
    outbound=dict(restored,payload=compact_for_import(restored['payload'],preset,step,caps))
    admission=admit(outbound)
    if not isinstance(admission,dict) or admission.get('status')!='admitted':
        raise ValueError('server did not admit restored request; nothing executed')
    # Preserve exact local preparation/provenance before handing control to the
    # existing checkpointed driver. Immutable raw publication avoids rewriting
    # the prior checkpoint or any provider receipt as recovery.
    state=dict(version=1,compact=compact,restored=restored,graph=graph,receipt=receipt,admission=admission)
    raw=json.dumps(state,ensure_ascii=True,separators=(',',':')).encode('utf-8')
    sha=digest(state)
    durable_raw_import(root,dict(version=1,owner=expected_owner,preset=preset,sha=sha,size=len(raw)),[raw],
                       expected_owner=expected_owner,preset=preset,max_bytes=len(raw))
    return dict(args=restored,wire_args=outbound,state_path=str(Path(root)/(sha+'.json')),receipt=receipt)
