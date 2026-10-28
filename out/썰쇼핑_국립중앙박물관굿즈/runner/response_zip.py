"""Verify and restore a negotiated gzip JSON-RPC response without reposting."""

import base64
import binascii
import hashlib
import json
import re
import sys
import zlib


class ResponseZipError(ValueError):
    """The server's compressed reply cannot be trusted as a complete result."""


_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_CHUNK = 1 << 20
_INPUT_CHUNK = 1 << 16


def _decode_gzip(data, declared):
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    plain = bytearray()
    digest = hashlib.sha256()

    def take(part):
        if len(part) > declared - len(plain):
            raise ResponseZipError("압축 응답이 선언된 크기를 넘었습니다")
        plain.extend(part)
        digest.update(part)

    try:
        for start in range(0, len(data), _INPUT_CHUNK):
            pending = data[start:start + _INPUT_CHUNK]
            if decoder.eof:
                raise ResponseZipError("압축 응답 뒤에 추가 데이터가 있습니다")
            while pending:
                remaining = declared - len(plain)
                part = decoder.decompress(pending, min(_OUTPUT_CHUNK, remaining + 1))
                take(part)
                new_pending = decoder.unconsumed_tail
                if decoder.unused_data or (new_pending and len(new_pending) == len(pending) and not part):
                    raise ResponseZipError("압축 응답 뒤에 추가 데이터가 있습니다")
                pending = new_pending
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ResponseZipError("압축 응답이 끝까지 도착하지 않았습니다")
    except zlib.error as exc:
        raise ResponseZipError("압축 응답이 손상되었습니다") from exc
    if len(plain) != declared:
        raise ResponseZipError("압축 응답 크기가 다릅니다")
    return plain, digest.hexdigest()


def restore_response_zip(rpc):
    """Return the verified inner RPC, or the untouched legacy RPC."""
    if not isinstance(rpc, dict):
        return rpc
    result = rpc.get("result")
    if not isinstance(result, dict):
        return rpc
    content = result.get("content")
    compressed_marker = content == [{"type": "text", "text": "(실행기 압축 응답)"}]
    meta = result.get("_meta") if isinstance(result, dict) else None
    if not isinstance(meta, dict) or "response_gzip" not in meta:
        if compressed_marker:
            raise ResponseZipError("압축 응답 명세가 없습니다")
        return rpc
    if not compressed_marker:
        raise ResponseZipError("압축 응답 표지가 다릅니다")
    manifest = meta["response_gzip"]
    if not isinstance(manifest, dict):
        raise ResponseZipError("압축 응답 명세가 없습니다")
    declared = manifest.get("bytes")
    sha = manifest.get("sha256")
    if (type(manifest.get("version")) is not int or manifest["version"] != 1
            or manifest.get("encoding") != "gzip-base64"
            or type(declared) is not int or not 0 < declared <= sys.maxsize
            or not isinstance(sha, str) or _HEX_SHA256.fullmatch(sha) is None):
        raise ResponseZipError("압축 응답 명세가 잘못되었습니다")
    structured = result.get("structuredContent")
    data = structured.get("data") if isinstance(structured, dict) else None
    if not isinstance(data, str):
        raise ResponseZipError("압축 응답 데이터가 없습니다")
    try:
        compressed = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ResponseZipError("압축 응답 데이터가 손상되었습니다") from exc
    plain, actual_sha = _decode_gzip(compressed, declared)
    del compressed
    if actual_sha != sha:
        raise ResponseZipError("압축 응답 지문이 다릅니다")
    try:
        inner = json.loads(plain.decode("utf-8", "surrogatepass"))
    except (UnicodeError, ValueError) as exc:
        raise ResponseZipError("압축 응답 JSON이 손상되었습니다") from exc
    if (not isinstance(inner, dict) or inner.get("jsonrpc") != "2.0"
            or rpc.get("jsonrpc") != "2.0" or "id" not in inner or "id" not in rpc
            or type(inner["id"]) is not type(rpc["id"]) or inner["id"] != rpc["id"]):
        raise ResponseZipError("압축 응답 요청 식별자가 다릅니다")
    return inner
