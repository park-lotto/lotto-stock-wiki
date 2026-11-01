"""Validate and restore negotiated response references before runner handling."""

from __future__ import annotations

import json
import io


def _bytes(value):
    return b''.join(_fragments(value))


def _fragments(value):
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'))
    pending = []
    size = 0
    for token in encoder.iterencode(value):
        length = len(token)
        if size + length > io.DEFAULT_BUFFER_SIZE:
            if pending:
                yield _encoded_fragment(''.join(pending))
                pending.clear()
                size = 0
            if length >= io.DEFAULT_BUFFER_SIZE:
                yield _encoded_fragment(token)
                continue
        pending.append(token)
        size += length
    if pending:
        yield _encoded_fragment(''.join(pending))


def _encoded_fragment(fragment):
    try:
        return fragment.encode('utf-8')
    except UnicodeEncodeError:
        return (fragment.encode('utf-16-le', 'surrogatepass')
                .decode('utf-16-le', 'surrogatepass').encode('utf-8', 'surrogatepass'))


def _wire_size(value):
    return sum(len(fragment) for fragment in _fragments(value))


def _at(root, path):
    value = root
    for part in path:
        if isinstance(part, bool):
            raise ValueError('response reference path has a boolean index')
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
            value = value[part]
        else:
            raise ValueError('response reference path is absent')
    return value


def _target_branch(path):
    if (len(path) == 4 and path[:3] == ['next_payload', 'focus_frames', '_focus_delta']
            and type(path[3]) is str):
        return 'focus_row'
    if path == ['next_payload', 'focus_measurements']:
        return 'measurements'
    if (len(path) == 4 and path[0] == 'focus_frames' and isinstance(path[1], str)
            and path[2] == 'review_requests' and type(path[3]) is int):
        return 'focus_frames'
    if (len(path) == 6 and path[:3] == ['next_payload', 'focus_frames', '_focus_delta']
            and isinstance(path[3], str) and path[4] == 'review_requests'
            and type(path[5]) is int):
        return 'next_delta'
    raise ValueError('response reference target is outside eligible evidence')


def _clone_json(value):
    """Clone a decoded JSON tree without deepcopy's shallow recursion ceiling."""
    if isinstance(value, dict):
        clone = {}
    elif isinstance(value, list):
        clone = [None] * len(value)
    else:
        return value
    pending = [(value, clone)]
    while pending:
        source, target = pending.pop()
        items = source.items() if isinstance(source, dict) else enumerate(source)
        for key, child in items:
            if isinstance(child, dict):
                copied = {}
                pending.append((child, copied))
            elif isinstance(child, list):
                copied = [None] * len(child)
                pending.append((child, copied))
            else:
                copied = child
            target[key] = copied
    return clone


def restore_response_refs(result, manifest):
    """Restore exact JSON values after validating the entire reference map.

    Sources are top-level review requests (at most once per eligible branch)
    or the single top-level measurements object (at most once). Version 2 also
    permits each top-level focus row exactly once at its same-key carry path,
    without any nested reference touching that source or target. Encoded data
    cannot fan out without bound. No fixed byte limit excludes responses
    previously accepted by the runner. Invalid metadata leaves input unchanged.
    """
    # Call this function only when the MCP metadata key exists. A present
    # null manifest is malformed; treating it as "no negotiation" would let
    # null placeholders escape as a successful, incomplete result.
    if manifest is None:
        raise ValueError('response reference manifest is null')
    if not isinstance(result, dict):
        raise ValueError('response reference payload must be an object')
    if (not isinstance(manifest, dict) or set(manifest) !=
            {'version', 'refs', 'total_bytes'} or
            type(manifest['version']) is not int or manifest['version'] not in (1, 2) or
            not isinstance(manifest['refs'], list) or not manifest['refs'] or
            type(manifest['total_bytes']) is not int or manifest['total_bytes'] < 0):
        raise ValueError('invalid response reference manifest')
    originals = result.get('focus_review_requests')
    originals = originals if isinstance(originals, list) else []
    rows = result.get('focus_frames')
    rows = rows if isinstance(rows, dict) else {}
    max_refs = 2 * len(originals) + 1 + (len(rows) if manifest['version'] == 2 else 0)
    if len(manifest['refs']) > max_refs:
        raise ValueError('response reference expansion exceeds eligible copies')
    targets = set()
    uses = set()
    plan = []
    total = 0
    for ref in manifest['refs']:
        if not isinstance(ref, dict) or set(ref) != {'path', 'source', 'bytes'}:
            raise ValueError('invalid response reference entry')
        path, source = ref['path'], ref['source']
        if (not isinstance(path, list) or not isinstance(source, list)
                or type(ref['bytes']) is not int or ref['bytes'] <= 0):
            raise ValueError('invalid response reference source or size')
        branch = _target_branch(path)
        if branch == 'focus_row':
            if manifest['version'] != 2 or source != ['focus_frames', path[3]]:
                raise ValueError('invalid focus row reference source')
            value = rows.get(path[3])
            source_use = ('focus_row', path[3])
        elif branch == 'measurements':
            if source != ['focus_measurements']:
                raise ValueError('invalid measurements reference source')
            value = result.get('focus_measurements')
            source_use = ('measurements',)
        else:
            if (len(source) != 2 or source[0] != 'focus_review_requests'
                    or type(source[1]) is not int or not 0 <= source[1] < len(originals)):
                raise ValueError('invalid review reference source')
            value = originals[source[1]]
            source_use = (branch, source[1])
        target = tuple(path)
        if target in targets or source_use in uses or _at(result, path) is not None:
            raise ValueError('duplicate or occupied response reference target')
        try:
            exact_size = _wire_size(value) if isinstance(value, dict) else -1
        except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
            raise ValueError('response reference source is not JSON') from exc
        if exact_size != ref['bytes']:
            raise ValueError('response reference source size mismatch')
        targets.add(target)
        uses.add(source_use)
        total += ref['bytes']
        plan.append((path, value))
    row_cuts = {use[1] for use in uses if use[0] == 'focus_row'}
    for path, _ in plan:
        branch = _target_branch(path)
        if ((branch == 'focus_frames' and path[1] in row_cuts)
                or (branch == 'next_delta' and path[3] in row_cuts)):
            raise ValueError('focus row reference overlaps a nested review reference')
    if total != manifest['total_bytes'] or len(plan) > max_refs:
        raise ValueError('response reference expansion mismatch')
    # Prepare every copy before the first mutation. Even an unexpectedly
    # uncloneable source cannot leave a partly restored result behind.
    copies = [(path, _clone_json(value)) for path, value in plan]
    for path, value in copies:
        parent = _at(result, path[:-1])
        parent[path[-1]] = value
    return result
