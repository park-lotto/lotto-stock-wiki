"""Authenticated original integrity and local preservation primitives.

Authority is a freshly authorized app principal, never a client-supplied tail.
R2 JSON is decoded only in the local importer, not in the server body endpoint.
"""
import hashlib
import hmac
import json
import os
import re
import tempfile
from pathlib import Path

SHA = re.compile(r'[0-9a-f]{64}\Z')
DOMAIN = b'volcano-local-original-import-v1\0'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8', 'surrogatepass')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def owner(principal, preset):
    # Integration must call volcano_tools.authorize for EVERY download request.
    email = str(principal.get('name') or '').strip().lower()
    identity = hashlib.sha256(email.encode('utf-8')).hexdigest()
    if (principal.get('status') != 'active' or not principal.get('grant_source')
            or '@' not in email or principal.get('token_tail') != '@' + identity[:12]
            or preset not in principal.get('presets', [])):
        raise PermissionError('active app owner and current preset grant required')
    return identity, '@' + identity[:12]


def issue(secret, principal, *, preset, request_sha, sha, expires, now):
    if not isinstance(secret, bytes) or not secret:
        raise ValueError('server signing key required')
    identity, tail = owner(principal, preset)
    if (not isinstance(request_sha, str) or not SHA.fullmatch(request_sha)
            or not isinstance(sha, str) or not SHA.fullmatch(sha)
            or type(expires) is not int or type(now) is not int or expires <= now):
        raise ValueError('invalid import binding')
    claims = dict(version=1, owner=identity, tail=tail, preset=preset,
                  request_sha=request_sha, sha=sha, expires=expires)
    return dict(claims=claims, signature=hmac.new(secret, DOMAIN + canonical(claims), hashlib.sha256).hexdigest())


def verify(secret, principal, permit, *, preset, request_sha, sha, now):
    if not isinstance(permit, dict) or set(permit) != {'claims', 'signature'}:
        raise PermissionError('invalid import permit')
    c = permit['claims']
    if not isinstance(c, dict) or set(c) != {'version', 'owner', 'tail', 'preset', 'request_sha', 'sha', 'expires'}:
        raise PermissionError('invalid import claims')
    expected = hmac.new(secret, DOMAIN + canonical(c), hashlib.sha256).hexdigest()
    signature = permit['signature']
    if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
        raise PermissionError('invalid import signature')
    identity, tail = owner(principal, preset)
    if (type(c['version']) is not int or c['version'] != 1
            or type(c['expires']) is not int or type(now) is not int or c['expires'] <= now
            or c['owner'] != identity or c['tail'] != tail or c['preset'] != preset
            or c['request_sha'] != request_sha or c['sha'] != sha
            or not isinstance(sha, str) or not SHA.fullmatch(sha)):
        raise PermissionError('import authority mismatch or expired')
    return c


async def stream_original(bucket, secret, principal, permit, *, preset, request_sha, sha, now):
    """Returns a raw body handle, with no text/read/JSON inflation on the server."""
    c = verify(secret, principal, permit, preset=preset, request_sha=request_sha, sha=sha, now=now)
    obj = await bucket.get('blob/' + c['tail'] + '/' + sha)
    if obj is None:
        raise FileNotFoundError('original unavailable; preserve local state')
    return {'body': obj.body, 'size': obj.size, 'sha': sha,
            'request_sha': request_sha, 'version': 1}


def _read_checked(path, sha, max_bytes):
    if path.stat().st_size > max_bytes:
        raise ValueError('local original exceeds negotiated size')
    value = json.loads(path.read_bytes())
    if digest(value) != sha:
        raise ValueError('original canonical hash mismatch')
    return value


def import_original(root, *, sha, chunks, size, max_bytes):
    """chunks is a single authenticated response stream; no retry/provider invocation.

    Exact raw original bytes stay on disk. Canonical hash differs from HTTP/raw
    hash for stored ASCII-escaped Unicode. Invalid existing cache is preserved.
    Caller must authenticate metadata and negotiate max_bytes; no invented limit.
    """
    if (not isinstance(sha, str) or not SHA.fullmatch(sha) or type(size) is not int
            or type(max_bytes) is not int or not 0 < size <= max_bytes):
        raise ValueError('invalid original metadata')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    final = root / (sha + '.json')
    if final.exists():
        return _read_checked(final, sha, max_bytes)
    fd, tmp = tempfile.mkstemp(prefix=sha + '.', suffix='.part', dir=root)
    tmp = Path(tmp)
    try:
        total = 0
        with os.fdopen(fd, 'wb') as out:
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ValueError('invalid byte stream')
                total += len(chunk)
                if total > size or total > max_bytes:
                    raise ValueError('original exceeds declared size')
                out.write(chunk)
            if total != size:
                raise ValueError('truncated original stream')
            out.flush()
            os.fsync(out.fileno())
        value = _read_checked(tmp, sha, max_bytes)
        # A concurrent importer may have published the same immutable SHA.
        # A malformed existing file is never replaced as a recovery shortcut.
        if final.exists():
            return _read_checked(final, sha, max_bytes)
        # Atomic no-clobber publication on macOS and Windows. Hard-link failure
        # (unsupported filesystem / permissions) leaves originals unchanged;
        # do not silently downgrade to an overwrite-prone rename.
        try:
            os.link(tmp, final)
        except FileExistsError:
            return _read_checked(final, sha, max_bytes)
        return value
    finally:
        tmp.unlink(missing_ok=True)
