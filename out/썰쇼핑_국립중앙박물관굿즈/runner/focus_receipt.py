"""Materialize one server-bound focus receipt without touching paid execution state."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def _encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')


def _apply(row,changes):
    if not isinstance(changes,list):raise ValueError('invalid focus receipt changes')
    for change in changes:
        if not isinstance(change,dict) or set(change) not in ({'path','value'},{'path','delete'}):raise ValueError('invalid focus receipt change')
        path=change['path']
        if not isinstance(path,list) or any(type(k) is not str for k in path):raise ValueError('invalid focus receipt path')
        if not path:row=change['value'];continue
        root=dict(row);target=root;source=row
        for key in path[:-1]:
            source=source[key]
            if not isinstance(source,dict):raise ValueError('invalid focus receipt parent')
            child=dict(source);target[key]=child;target=child
        if 'delete' in change:
            if change['delete'] is not True or path[-1] not in target:raise ValueError('invalid focus receipt deletion')
            del target[path[-1]]
        else:target[path[-1]]=change['value']
        row=root
    return row


def write_focus_receipt(spec,*,unpack=None):
    if (not isinstance(spec,dict) or set(spec)!={'cmd','version','path','packed','packed_sha256','changes','sha256'}
            or spec['cmd']!='write_focus_receipt' or type(spec['version']) is not int or spec['version']!=1
            or not isinstance(spec['path'],str) or not spec['path']
            or any(not isinstance(spec[k],str) or re.fullmatch('[0-9a-f]{64}',spec[k]) is None
                   for k in ('packed_sha256','sha256'))):
        raise ValueError('invalid focus receipt contract')
    if hashlib.sha256(_encode(spec['packed'])).hexdigest()!=spec['packed_sha256']:
        raise ValueError('focus original digest mismatch')
    if unpack is None:
        from volcano_run import _focus_unpack
        unpack=_focus_unpack
    row=_apply(unpack(spec['packed']),unpack(spec['changes']))
    raw=_encode(row)
    if hashlib.sha256(raw).hexdigest()!=spec['sha256']:raise ValueError('focus final digest mismatch')
    from volcano_run import _review_receipt_io_path
    path=Path(_review_receipt_io_path(spec['path']));path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
        from volcano_run import _tts_fsync_dir
        _tts_fsync_dir(path.parent)
    finally:
        try:os.unlink(tmp)
        except FileNotFoundError:pass
    return {'path':spec['path'],'sha256':spec['sha256'],'bytes':len(raw)}
