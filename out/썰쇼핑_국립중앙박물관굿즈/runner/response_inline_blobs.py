"""Negotiated lossless inline units for newly produced response evidence.

Requires blob-v1, structured-only and response-inline-blobs-v1. Preserve
storage ASCII bytes independently from canonical cache SHA. The response
size contract matches response_zip: exact declared sizes bounded by sys.maxsize.
Fresh units have at most the existing top-level and same-slot carry copies.
"""
import base64
import hashlib
import io
import json
import re
import sys
import zlib
CAP = 'response-inline-blobs-v1'
HEX = re.compile('[0-9a-f]{64}\\Z')
PAIR = re.compile('\\\\ud[89abAB][0-9a-fA-F]{2}\\\\ud[c-fC-F][0-9a-fA-F]{2}')
INPUT_CHUNK = 1 << 16
OUTPUT_CHUNK = 1 << 20

def eligible(key):
    """Use the existing blob field eligibility rule; frames have their own references."""
    return isinstance(key, str) and (not key.startswith('_')) and (key not in ('frames', 'focus_frames'))

def marker(v):
    return isinstance(v, dict) and set(v) == {'_blob', 'sha'} and (type(v['_blob']) is int) and (v['_blob'] == 1) and isinstance(v['sha'], str) and HEX.fullmatch(v['sha'])

def canonical(value):
    """Match the existing blob canonical encoding, including lone surrogates."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf8', 'surrogatepass')

def string_keys_only(value, depth=0):
    """Eligibility fallback only. Non-string or custom container keys keep legacy JSON semantics; deep containers are not rejected."""
    t = type(value)
    if t not in (dict, list, tuple):
        return not isinstance(value, (dict, list, tuple))
    if depth >= 64:
        return False
    if t is dict and any((type(k) is not str for k in value)):
        return False
    for child in value.values() if t is dict else value:
        if isinstance(child, (dict, list, tuple)) and (not string_keys_only(child, depth + 1)):
            return False
    return True

def pack_stored(sha, text):
    """Compress one already-created ASCII storage string in existing 64KiB chunks. Valid surrogate-pair escapes fall back because JSON parsing can change canonical identity."""
    if not isinstance(sha, str) or not HEX.fullmatch(sha):
        raise ValueError('unit SHA')
    if PAIR.search(text):
        return None
    c = zlib.compressobj(wbits=31)
    zipped = io.BytesIO()
    digest = hashlib.sha256()
    for start in range(0, len(text), INPUT_CHUNK):
        fragment = text[start:start + INPUT_CHUNK].encode('ascii')
        digest.update(fragment)
        zipped.write(c.compress(fragment))
    zipped.write(c.flush())
    return dict(sha=sha, storage_bytes=len(text), storage_sha=digest.hexdigest(), gzip=base64.b64encode(zipped.getbuffer()).decode('ascii'))

def envelope(packets):
    """Build exact aggregate sizes from server-created canonical base64 padding without decoding copies."""
    total_bytes = sum(packet['storage_bytes'] for packet in packets)
    compressed_bytes = 0
    for packet in packets:
        text = packet['gzip']
        padding = len(text) - len(text.rstrip('='))
        compressed_bytes += len(text) // 4 * 3 - padding
    return {'version': 1, 'units': packets, 'total_bytes': total_bytes,
            'compressed_bytes': compressed_bytes}

def eligible_markers(result):
    """Enumerate only existing top-level/child and next_payload blob slots."""
    found = []
    for prefix, obj in (((), result), (('next_payload',), result.get('next_payload'))):
        if not isinstance(obj, dict):
            continue
        for key, value in obj.items():
            if key == 'next_payload' or not eligible(key):
                continue
            if marker(value):
                found.append((prefix + (key,), value['sha']))
            elif isinstance(value, dict):
                found.extend(((prefix + (key, sub), child['sha']) for sub, child in value.items() if marker(child)))
    return found

def _pairs(items):
    """Reject duplicate keys inside a compressed storage JSON unit."""
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out

def _decode_cache(result, manifest, local):
    """Return a new local cache, only after validating every unit. Never POST.

    The caller must reject errors without invoking Client.step again, then use
    its existing marker resolver (a fresh JSON parse per occurrence) atomically.
    Do not update persisted known-server ACKs here.
    """
    if not isinstance(result, dict) or not isinstance(manifest, dict) or set(manifest) != {'version', 'units', 'total_bytes', 'compressed_bytes'}:
        raise ValueError('manifest')
    if type(manifest['version']) is not int or manifest['version'] != 1:
        raise ValueError('version')
    units = manifest['units']
    total = manifest['total_bytes']
    compressed = manifest['compressed_bytes']
    if not isinstance(units, list) or not units or any((type(v) is not int or not 0 < v <= sys.maxsize for v in (total, compressed))):
        raise ValueError('aggregate')
    targets = eligible_markers(result)
    allowed = {sha for _, sha in targets}
    if len(units) > len(allowed):
        raise ValueError('unit count')
    slots = {}
    for path, sha in targets:
        normalized = path[1:] if path[:1] == ('next_payload',) else path
        slots.setdefault(sha, []).append((path[:1] == ('next_payload',), normalized))
    used = set()
    plans = []
    count = 0
    zcount = 0
    for item in units:
        if not isinstance(item, dict) or set(item) != {'sha', 'storage_bytes', 'storage_sha', 'gzip'}:
            raise ValueError('unit')
        sha = item['sha']
        n = item['storage_bytes']
        sh = item['storage_sha']
        data = item['gzip']
        if not isinstance(sha, str) or not HEX.fullmatch(sha) or sha in used or (sha not in allowed):
            raise ValueError('duplicate/unused SHA')
        if not isinstance(sh, str) or not HEX.fullmatch(sh) or type(n) is not int or (not 0 < n <= total) or (not isinstance(data, str)):
            raise ValueError('unit bounds')
        count += n
        if count > total or len(data) > 4 * ((compressed + 2) // 3):
            raise ValueError('aggregate bounds')
        raw = base64.b64decode(data, validate=True)
        zcount += len(raw)
        if zcount > compressed:
            raise ValueError('compressed aggregate')
        plans.append((sha, n, sh, raw))
        used.add(sha)
    if count != total or zcount != compressed:
        raise ValueError('aggregate mismatch')
    for sha in used:
        locations = slots[sha]
        if len(locations) > 2 or len({slot for _, slot in locations}) != 1 or len(set(locations)) != len(locations):
            raise ValueError('fresh unit fanout')
    target_paths = {path for path, sha in targets if sha in used}
    # Iterator frames retain depth only, not one tuple for every inline item.
    stack = [((), iter(result.items()))]
    while stack:
        parent_path, children = stack[-1]
        try:
            key, value = next(children)
        except StopIteration:
            stack.pop()
            continue
        path = parent_path + (key,)
        if marker(value) and value['sha'] in used and path not in target_paths:
            raise ValueError('unexpected marker path')
        if isinstance(value, dict):
            stack.append((path, iter(value.items())))
        elif isinstance(value, list):
            stack.append((path, enumerate(value)))
    prepared = {}
    for sha, n, sh, data in plans:
        d = zlib.decompressobj(31)
        out = bytearray()
        digest = hashlib.sha256()
        for start in range(0, len(data), INPUT_CHUNK):
            remaining = data[start:start + INPUT_CHUNK]
            while remaining:
                part = d.decompress(remaining, min(OUTPUT_CHUNK, n - len(out) + 1))
                out.extend(part)
                digest.update(part)
                if len(out) > n or d.unused_data:
                    raise ValueError('gzip trailing/size')
                remaining = d.unconsumed_tail
        if not d.eof or len(out) != n or digest.hexdigest() != sh:
            raise ValueError('gzip truncated/SHA')
        value = json.loads(out.decode('ascii'), object_pairs_hook=_pairs)
        encoded = canonical(value)
        if hashlib.sha256(encoded).hexdigest() != sha:
            raise ValueError('canonical SHA')
        if sha in local and local[sha] != encoded:
            raise ValueError('known cache conflict')
        prepared[sha] = encoded
    merged = dict(local)
    merged.update(prepared)
    return merged

class Saved(list):

    def __init__(self):
        super().__init__()
        self.packets = []

async def store_units(env, tail, inline_texts, fresh_values, B, *, enabled=False, original_store=None):
    """Store originals and compress new response units only after negotiation. A failed put does not acknowledge the SHA; complete inline evidence can still be returned. Cancellation propagates."""
    if not enabled:
        return await original_store(env, tail, inline_texts, fresh_values)
    saved = Saved()
    pending = {sha: (value, False) for sha, value in (inline_texts or {}).items()}
    pending.update(((sha, (value, True)) for sha, value in (fresh_values or {}).items()))
    for sha, (value, fresh) in pending.items():
        if not isinstance(sha, str) or not HEX.fullmatch(sha) or (not fresh and (not isinstance(value, str))):
            continue
        text = B._stored_text(value) if fresh else value
        if fresh and string_keys_only(value):
            packet = pack_stored(sha, text)
            if packet is not None:
                saved.packets.append(packet)
        try:
            if env is not None:
                await env.DIAG.put(B.key_of(tail, sha), text)
                saved.append(sha)
        except Exception:
            pass
        finally:
            text = None
    return saved

def safe_slot_keys(mapping):
    """Only stable JSON object slot names may carry new unit references."""
    return (type(mapping) is dict and all(
        type(key) is str and not any(0xD800 <= ord(char) <= 0xDFFF for char in key)
        for key in mapping))

def shape_fresh(payload, fresh, packets, B):
    """Copy response container paths only. Units shared across different slots stay inline instead of expanding client reference permissions."""
    if not safe_slot_keys(payload):
        return payload, []
    if isinstance(payload.get('next_payload'), dict) and not safe_slot_keys(payload['next_payload']):
        return payload, []
    included = {p['sha'] for p in packets}
    by_id = {id(v): sha for sha, v in fresh.items() if sha in included}

    def fields(obj):
        out = dict(obj)
        for field, value in obj.items():
            if field == 'next_payload' or not B.eligible(field):
                continue
            sha = by_id.get(id(value))
            if sha:
                out[field] = B.marker(sha)
            elif isinstance(value, dict):
                # JSON coerces parent keys too. Keep the whole field inline
                # when slot names are not exact strings (1 and '1' can collide).
                if not safe_slot_keys(value):
                    continue
                changes = {k: B.marker(by_id[id(v)]) for k, v in value.items() if id(v) in by_id}
                if changes:
                    out[field] = dict(value, **changes)
        return out
    out = fields(payload)
    if isinstance(payload.get('next_payload'), dict):
        out['next_payload'] = fields(payload['next_payload'])
    targets = eligible_markers(out)
    valid = set()
    for sha in included:
        locations = [p for p, s in targets if s == sha]
        normalized = [p[1:] if p[:1] == ('next_payload',) else p for p in locations]
        if 0 < len(locations) <= 2 and len(set(normalized)) == 1:
            valid.add(sha)
    if valid != included:
        return shape_fresh(payload, fresh, [p for p in packets if p['sha'] in valid], B)
    return (out, [p for p in packets if p['sha'] in valid])

def decode_cache(result, manifest, local):
    """Normalize corrupt gzip to the same no-retry validation error as other malformed units. No requests or persistent cache updates occur here."""
    try:
        return _decode_cache(result, manifest, local)
    except zlib.error as exc:
        raise ValueError('invalid gzip stream') from exc
