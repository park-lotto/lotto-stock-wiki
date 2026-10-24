"""Local transport-reference restoration without server expansion or execution.

Transport semantics mirror volcano_blob.wire_marks/wire_restore and the optional
volcano_focus_record.request_marks extension. Download authority is established
separately; allowed_shas must come from authenticated, locally verified original imports.
"""
import copy
import json
from pathlib import Path
from original_import import SHA, _read_checked, digest


def _sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError('invalid original SHA')
    return value


def _marker(value):
    if not isinstance(value, dict) or '_blob' not in value:
        return False
    if set(value) != {'_blob', 'sha'} or type(value['_blob']) is not int or value['_blob'] != 1:
        raise ValueError('invalid blob marker version or shape')
    _sha(value['sha'])
    return True


def _unwrap(value, *, source=False):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        if not (text.startswith('{') and text.endswith('}')):
            if source:
                return value
            raise ValueError('payload JSON text must contain an object')
        value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('payload/source JSON wrapper must contain an object')
    return value


def _wire(value, *, review_refs):
    if '_wire_blob' not in value:
        return value, []
    if (set(value) != {'_wire_blob', 'value', 'blobs'}
            or type(value['_wire_blob']) is not int or value['_wire_blob'] != 1
            or not isinstance(value['value'], dict)
            or not isinstance(value['blobs'], list) or not value['blobs']):
        raise ValueError('invalid wire envelope version or shape')
    entries, seen, prefixes = [], set(), set()
    for entry in value['blobs']:
        if not isinstance(entry, dict) or set(entry) not in ({'path', 'sha'}, {'path', 'sha', 'review'}):
            raise ValueError('invalid wire reference shape')
        if 'review' in entry and (not review_refs or type(entry['review']) is not int or entry['review'] != 1):
            raise ValueError('review original reference not negotiated')
        path = entry['path']
        if not isinstance(path, list) or not path or any(type(k) not in (str, int) for k in path):
            raise ValueError('invalid wire path')
        path = tuple(path)
        if path in prefixes or any(path[:i] in seen for i in range(1, len(path)+1)):
            raise ValueError('duplicate or ancestor-overlapping wire paths')
        seen.add(path)
        prefixes.update(path[:i] for i in range(1, len(path)+1))
        parent = value['value']
        for index, key in enumerate(path):
            if not ((isinstance(parent, dict) and type(key) is str and key in parent)
                    or (isinstance(parent, list) and type(key) is int and 0 <= key < len(parent))):
                raise ValueError('invalid wire path target')
            if index == len(path) - 1:
                if parent[key] is not None:
                    raise ValueError('wire target must be None placeholder')
            else:
                parent = parent[key]
        entries.append((path, _sha(entry['sha'])))
    return value['value'], entries


def _marks(payload, *, focus_refs):
    # Exact legacy two-level contract, then negotiated focus extension.
    marks = []
    for key, value in payload.items():
        eligible = isinstance(key, str) and not key.startswith('_') and key not in ('frames', 'focus_frames')
        if not eligible and not (focus_refs and key in ('frames', 'focus_frames', 'focus_measurements')):
            continue
        if _marker(value):
            marks.append(((key,), value['sha']))
        elif isinstance(value, dict):
            for sub, child in value.items():
                if _marker(child):
                    marks.append(((key, sub), child['sha']))
    recovery = payload.get('focus_recovery')
    held = recovery.get('unrepaired_frames') if isinstance(recovery, dict) else None
    if focus_refs and isinstance(held, dict) and not _marker(held):
        for key, value in held.items():
            if isinstance(key, str) and _marker(value):
                marks.append((('focus_recovery', 'unrepaired_frames', key), value['sha']))
    return marks


def _set(target, path, value):
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def _no_refs(value):
    # Refuse unnegotiated or unsupported nested transport rather than guess an
    # expansion loop. Ordinary text is data, including scripts quoting markers.
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if '_blob' in item or '_wire_blob' in item:
                raise ValueError('unresolved or unsupported nested transport reference')
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def resolve_request(root, args, *, allowed_shas, expected_workdir, max_original_bytes,
                    focus_refs=False, review_refs=False):
    """Restore exact originals locally; return copy plus immutable provenance.

    Workdir must be inline in the compact request and match a separately trusted
    handoff. This function never chooses a directory from unresolved contents.
    Two restoration phases match existing server order: wire envelope then blob
    markers. No recursive fetching, paid replay, proof rewriting or projection.
    """
    if not isinstance(args, dict):
        raise ValueError('arguments must be an object')
    if not isinstance(expected_workdir, str) or not expected_workdir.strip():
        raise ValueError('trusted explicit workdir required')
    if type(max_original_bytes) is not int or max_original_bytes <= 0:
        raise ValueError('negotiated original limit required')
    allowed = frozenset(_sha(sha) for sha in allowed_shas)
    compact_sha = digest(args)
    payload, entries = _wire(_unwrap(args.get('payload', {})), review_refs=review_refs)
    workdir = payload.get('workdir')
    if not isinstance(workdir, str) or not workdir.strip() or workdir != expected_workdir:
        raise ValueError('workdir must be explicit inline and match handoff; cannot infer from originals')
    if any(path[0] == 'workdir' for path, _ in entries):
        raise ValueError('workdir cannot be restored from a reference')
    out = copy.deepcopy(args)
    out['payload'] = copy.deepcopy(payload)
    if 'source' in out:
        out['source'] = _unwrap(out['source'], source=True)
    loaded, references = {}, []

    def load(sha, path, kind):
        if sha not in allowed:
            raise PermissionError('original is not authorized by this handoff')
        if sha not in loaded:
            loaded[sha] = _read_checked(Path(root)/(sha+'.json'), sha, max_original_bytes)
        references.append(dict(path=list(path), sha=sha, transport=kind))
        # Same SHA at distinct paths is valid; avoid mutation aliasing.
        return copy.deepcopy(loaded[sha])

    for path, sha in entries:
        _set(out['payload'], path, load(sha, path, 'wire-v1'))
    for path, sha in _marks(out['payload'], focus_refs=focus_refs):
        _set(out['payload'], path, load(sha, path, 'blob-v1'))
    _no_refs(out)
    receipt = dict(version=1, compact_request_sha=compact_sha,
                   restored_request_sha=digest(out), originals=references,
                   original_shas=sorted(loaded), workdir=workdir)
    return out, receipt
