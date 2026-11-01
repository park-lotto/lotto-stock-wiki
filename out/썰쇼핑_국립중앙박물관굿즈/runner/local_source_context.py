"""Local adapters for the canonical source/film recovery state machine."""
import copy
import hashlib
import json
import math
import types
import source_kernel as K
import source_state_kernel as S


def bind(task, focus):
    """Settings are a server-issued snapshot, never an embedded preset registry."""
    snapshot=task['context']
    if snapshot['preset_spec'].get('timing_origin')!='source':raise ValueError('source-only context required')
    specmod=types.ModuleType('volcano_spec')
    specmod.PRESETS={task['preset']:copy.deepcopy(snapshot['preset_spec'])}
    specmod.CLAUDE_CLI=copy.deepcopy(snapshot['claude'])
    specmod.channel_rhythm=lambda preset:copy.deepcopy(snapshot['rhythm'])
    specmod.person_spec=lambda preset:copy.deepcopy(snapshot['person'])
    specmod.stitch_spec=lambda preset:copy.deepcopy(snapshot['render'])
    specmod.vision_call=lambda prompt:dict(snapshot['vision'],prompt=prompt)
    exec(compile(S.ADDITIONAL['volcano_spec'],'<source-spec-pure>','exec'),dict(specmod.__dict__,hashlib=hashlib,json=json),out:={})
    specmod.job_sig=out['job_sig']
    pure=K.build_modules(copy.deepcopy(snapshot['policy']))
    modules={name:pure[name] for name in S.MODULE_NAMES if name in pure}
    modules['volcano_spec']=specmod
    focusmod=modules['volcano_focus'];focusmod.__dict__.update(modules)
    exec(compile(S.ADDITIONAL['volcano_focus'],'<source-render-key>','exec'),focusmod.__dict__)
    deliver=types.ModuleType('volcano_deliver');modules['volcano_deliver']=deliver
    deliver.__dict__.update(pure);deliver.__dict__.update(modules,json=json,copy=copy,math=math)
    deliver.__dict__.update(snapshot['export_policy']['volcano_deliver'])
    exec(compile(S.ADDITIONAL['volcano_deliver'],'<source-deliver-pure>','exec'),deliver.__dict__)
    def workdir(pl):
        if pl.get('workdir')!=task['workdir']:raise ValueError('local source workdir changed')
        return task['workdir']
    def settings(pl,wd):
        return {key:copy.deepcopy(task['selection'][key]) for key in ('review_policy','focus_review_replies','review_budget')}
    def spec(pl,preset=None):
        # Only canonical local cut compilation/recovery mutates BLOCKS.
        value=copy.deepcopy(snapshot['spec']);value['BLOCKS']=copy.deepcopy(pl['BLOCKS']);return value
    def preflight(*args):
        if snapshot.get('preflight')!='source-timeline-bounds-ctc-v1':raise ValueError('unverified source preflight')
        return None
    skipped=[]
    adapters=dict(_require_preset=lambda args,principal:task['preset'],_stitch_S=lambda *args:copy.deepcopy(snapshot['render']),
        _stitch_spec=spec,_stitch_timeline_prepare=preflight,_stitch_check_source_bounds=preflight,_stitch_ctc_prepare=preflight,
        _focus_prepare=focus,_focus_selection_settings=lambda preset:copy.deepcopy(snapshot['focus_settings']),
        _narration_options=lambda *args:copy.deepcopy(snapshot['narration_options']),
        _review_execution_settings=settings,_rules_off=lambda pl:snapshot['rules_off'],_note_skipped=lambda items:skipped.extend(str(item) for item in items if item),_stitch_workdir=workdir,
        _bucket_of=lambda preset:snapshot['bucket'],parallel_width=lambda pl:snapshot['parallel'])
    machine=S.bind(adapters,modules);machine['_local_skipped_rules']=skipped
    return machine
