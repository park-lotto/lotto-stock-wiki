"""One-line captions from immutable source timing; no rendering or paid calls.

Integration API:
  canonical_table(rows, source_id=..., timing_kind='word'|'cue', ...)
    Word timing additionally requires provider, request_id, receipt_sha256.
    Persist this returned object locally; never accept its timestamps from the
    host's editable caption payload. Cue timing is explicitly not word timing.
  layout_captions(clip, table, measure_width, max_width, preferred_width=None)
    clip has source_in, duration and captions. Captions may be local [a,b,text]
    rows or {'word_ids': [...], 'text': corrected_display_text} cards. Returns
    local [a,b,text] rows. measure_width must measure at the fixed render size,
    with any render scaling already included. This module never shrinks fonts.
    preferred_width is a soft group target; single words and corrected authored
    cards that fit max_width remain valid. It never triggers extra ASR by itself.
  completed_speechmatics_words(source_path, source_id, request_id)
    Read-only durable-cache lookup: returns a word table or None if absent.
    Corrupt, pending or mismatched records raise CaptionTimingError. No directory
    creation, lock-file writes, provider calls, imports of ASR engines, or retry.

An oversized unmatched cue requires measured words. Corrected long display text
requires author-supplied word-ID cards that each fit; proportional text timing
and multiline fallback are deliberately not provided.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata


class CaptionTimingError(ValueError):
    def __init__(self, message, code="invalid_caption_timing"):
        self.code = code
        super().__init__(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _sha(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise CaptionTimingError(name + " must be a SHA256 fingerprint")
    return value


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise CaptionTimingError("Timing must contain finite, nonnegative seconds")
    return float(value)


def _clean(value):
    return "".join(c for c in unicodedata.normalize("NFC", value) if c.isalnum())


def _line(value):
    if not isinstance(value, str) or not value.strip():
        raise CaptionTimingError("Caption display text must be nonempty")
    return " ".join(unicodedata.normalize("NFC", value).split())


def canonical_table(rows, *, source_id, timing_kind, provider=None, request_id=None, receipt_sha256=None):
    """Create persisted timing/ID bindings from trusted measured data."""
    _sha(source_id, "source_id")
    if timing_kind not in ("word", "cue") or not isinstance(rows, list):
        raise CaptionTimingError("Specify a list and explicit word or cue timing provenance")
    provenance = {}
    if timing_kind == "word":
        if not isinstance(provider, str) or not provider:
            raise CaptionTimingError("Measured word timing requires provider provenance")
        provenance = {"provider": provider, "request_id": _sha(request_id, "request_id"),
                      "receipt_sha256": _sha(receipt_sha256, "receipt_sha256")}
    result = {"version": 1, "source_id": source_id, "timing_kind": timing_kind, "provenance": provenance}
    entries, seen_ids = [], set()
    for index, row in enumerate(rows):
        if isinstance(row, dict):
            a, b, text = row.get("start"), row.get("end"), row.get("text", row.get("word"))
        elif isinstance(row, (list, tuple)) and len(row) == 3:
            a, b, text = row
        else:
            raise CaptionTimingError("Each timing entry needs start, end and text")
        a, b, text = _seconds(a), _seconds(b), _line(text)
        if timing_kind == "word" and not _clean(text):
            raise CaptionTimingError("Measured word entries must contain spoken text, not punctuation alone")
        if b <= a or (entries and a < entries[-1]["start"]):
            raise CaptionTimingError("Timing entries must be nonempty and ordered by measured start")
        entry = {"index": index, "start": a, "end": b, "text": text}
        origin = row.get("origin") if isinstance(row, dict) else None
        if origin is not None:
            if timing_kind != "word" or not isinstance(origin, dict) or set(origin) != {"batch_id", "word_index", "record_sha256"}:
                raise CaptionTimingError("Invalid selected-audio word origin")
            if type(origin["word_index"]) is not int or origin["word_index"] < 0:
                raise CaptionTimingError("Word origin needs its original nonnegative index")
            _sha(origin["batch_id"], "batch_id"); _sha(origin["record_sha256"], "record_sha256")
            entry["origin"] = dict(origin)
            # Coverage may grow before this word. Neither its global index nor
            # the aggregate receipt/table digest is part of its immutable ID.
            identity = {"source_id": source_id, "provider": provider, "request_id": request_id,
                        "origin": origin, "start": a, "end": b, "text": text}
        else:
            identity = {**result, **entry}
        entry["id"] = ("w_" if timing_kind == "word" else "c_") + _digest(identity)
        if entry["id"] in seen_ids:
            raise CaptionTimingError("A measured word origin was included more than once")
        seen_ids.add(entry["id"])
        entries.append(entry)
    result["words" if timing_kind == "word" else "cues"] = entries
    return {**result, "table_id": _digest(result)}


def _validated(table):
    if table is None:
        return None
    if not isinstance(table, dict):
        raise CaptionTimingError("Load the canonical timing table from its local artifact")
    kind = table.get("timing_kind")
    rows = table.get("words" if kind == "word" else "cues")
    provenance = table.get("provenance") or {}
    if not isinstance(provenance, dict):
        raise CaptionTimingError("Invalid timing provenance")
    expected = canonical_table(rows, source_id=table.get("source_id"), timing_kind=kind,
        provider=provenance.get("provider"), request_id=provenance.get("request_id"),
        receipt_sha256=provenance.get("receipt_sha256"))
    if expected != table:
        raise CaptionTimingError("Canonical word IDs or times changed; reload the saved source timing table")
    return table


def layout_captions(clip, table, measure_width, max_width, *, preferred_width=None):
    """Resolve local caption times without inventing per-character timing."""
    table = _validated(table)
    source, duration = _seconds(clip.get("source_in")), _seconds(clip.get("duration"))
    if not duration or not callable(measure_width) or _seconds(max_width) <= 0:
        raise CaptionTimingError("Provide clip duration and a fixed-size font width measurement")
    preferred=max_width if preferred_width is None else min(max_width,_seconds(preferred_width))
    if preferred<=0:
        raise CaptionTimingError("Preferred caption width must be positive")
    if clip.get("source_id") and (not table or table["source_id"] != clip["source_id"]):
        raise CaptionTimingError("Caption word table belongs to a different source")
    words = table.get("words", []) if table and table["timing_kind"] == "word" else []
    by_id = {word["id"]: word for word in words}
    width_cache={}
    def width(text):
        if text in width_cache:return width_cache[text]
        measured = measure_width(text)
        if isinstance(measured, bool) or not isinstance(measured, (int, float)) or not math.isfinite(measured) or measured < 0:
            raise CaptionTimingError("Font measurement did not return a finite width")
        width_cache[text]=measured
        return measured
    def fits(text):
        return width(text)<=max_width
    def ordered(selected):
        if any(right["index"] != left["index"] + 1 or right["start"] < left["end"]
               for left, right in zip(selected, selected[1:])):
            raise CaptionTimingError("Word IDs must select consecutive, nonoverlapping measured words in order")
    output = []
    for caption in clip.get("captions", []):
        if isinstance(caption, str):
            text = _line(caption)
            target = _clean(text)
            cursor = source + (output[-1][1] if output else 0)
            rows = words or (table.get("cues", []) if table else [])
            candidates = [w for w in rows if w["start"] >= cursor - 1e-8
                          and w["end"] <= source + duration + 1e-8]
            selected = None
            for index in range(len(candidates)):
                phrase = ""
                for end in range(index, len(candidates)):
                    phrase += _clean(candidates[end]["text"])
                    if phrase == target and target:
                        selected = candidates[index:end+1]
                        break
                    if not target.startswith(phrase):
                        break
                if selected:
                    break
            if not selected:
                raise CaptionTimingError("Caption phrase does not match complete measured words inside this clip: "
                    + repr(text) + "; copy the source phrase or bind corrected text to word_ids", "word_timing_required")
            if words:
                caption = {"word_ids": [w["id"] for w in selected], "text": text}
            else:
                caption = [selected[0]["start"] - source, selected[-1]["end"] - source, text]
        if isinstance(caption, dict):
            ids = caption.get("word_ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in by_id for i in ids):
                raise CaptionTimingError("Use word_ids from this source's saved measured word table")
            selected = [by_id[i] for i in ids]; ordered(selected)
            text = _line(caption.get("text"))
            if selected[0]["start"] < source or selected[-1]["end"] > source + duration:
                raise CaptionTimingError("Authored word IDs must be inside the selected source interval")
            measured_text = _clean("".join(w["text"] for w in selected))
            if width(text) <= preferred or _clean(text) != measured_text:
                if not fits(text):
                    raise CaptionTimingError("Corrected display text exceeds one line: " + repr(text) + "; split its consecutive word_ids cards while keeping measured times", "caption_card_too_wide")
                output.append([selected[0]["start"] - source, selected[-1]["end"] - source, text])
                continue
            # Matching text already has trustworthy word boundaries. Use the
            # same deterministic layout as a timed cue, without a host retry.
            caption = [selected[0]["start"] - source, selected[-1]["end"] - source, text]
        if not isinstance(caption, (list, tuple)) or len(caption) != 3:
            raise CaptionTimingError("Use [local_start, local_end, text] or a word_ids display card")
        a, b, text = _seconds(caption[0]), _seconds(caption[1]), _line(caption[2])
        if not a < b <= duration + 1e-8:
            raise CaptionTimingError("Caption times must be inside the selected clip")
        if fits(text) and (width(text)<=preferred or not words):
            output.append([a, b, text]); continue
        selected = [w for w in words if w["end"] > source + a and w["start"] < source + b]
        if not selected or _clean("".join(w["text"] for w in selected)) != _clean(text):
            if fits(text):
                output.append([a,b,text]);continue
            raise CaptionTimingError("Long caption requires matching measured word timing. Load completed Speechmatics words or measure only the selected original-dialogue interval; for corrected text submit word_ids cards", "word_timing_required")
        ordered(selected)
        positions = [i for i, char in enumerate(text) if char.isalnum()]
        # A line is always a slice of the authored text, so its own spacing is
        # kept (report #217: '나하고' became '나 하고' when words were re-joined
        # with ' '). group_raw is where the current line starts in `text`.
        offset, raw_start, group_raw, current, group_start = 0, 0, 0, "", a
        for word in selected:
            offset += len(_clean(word["text"]))
            raw_end = positions[offset] if offset < len(positions) else len(text)
            fragment = text[raw_start:raw_end].strip()
            if not fits(fragment):
                raise CaptionTimingError("One measured word exceeds the fixed one-line width. Supply a shorter display text bound to its word_id; do not invent subword times", "single_word_too_wide")
            joined = text[group_raw:raw_end].strip()
            boundary = word["start"] - source
            if current and width(joined)>preferred:
                if not group_start < boundary < b:
                    raise CaptionTimingError("No usable measured boundary inside this caption interval")
                output.append([group_start, boundary, current])
                group_start, current, group_raw = boundary, fragment, raw_start
            else:
                current = joined
            raw_start = raw_end
        output.append([group_start, b, current])
    if any(right[0] < left[1] - 1e-8 for left, right in zip(output, output[1:])):
        raise CaptionTimingError("Caption cards overlap or are out of order; select each measured word range once")
    return output


def _read_snapshot(path):
    """Atomic-replace writers permit a complete old or new read; reject in-place mutation."""
    with Path(path).open("rb") as stream:
        import os
        before = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if stamp(before) != stamp(after) or len(raw) != before.st_size:
        raise CaptionTimingError("Source timing cache changed while reading; retry the same read")
    return raw


def completed_speechmatics_words(source_path, source_id, request_id):
    """Inspect only the exact completed durable record; never start ASR."""
    _sha(source_id, "source_id"); _sha(request_id, "request_id")
    source = Path(source_path).expanduser().resolve()
    # Validate source bytes without retaining a potentially large movie in RAM.
    import os
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = source.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if stamp(before) != stamp(after) or stamp(after) != stamp(current) or digest.hexdigest() != source_id:
        raise CaptionTimingError("Original source changed; do not reuse its word timing")
    path = source.parent / ".volcano-asr" / (source_id + ".json")
    if not path.is_file():
        return None
    try:
        ledger = json.loads(_read_snapshot(path))
    except (ValueError, UnicodeError) as exc:
        raise CaptionTimingError("ASR receipt is corrupt; preserve it and do not automatically submit") from exc
    if not isinstance(ledger, dict) or ledger.get("version") != 1 or ledger.get("identity") != source_id or not isinstance(ledger.get("requests"), dict):
        raise CaptionTimingError("ASR receipt identity or schema does not match this source")
    record = ledger["requests"].get(request_id)
    if record is None:
        return None
    if not isinstance(record, dict) or record.get("provider") != "speechmatics":
        raise CaptionTimingError("ASR provider record is corrupt; preserve existing requests")
    if record.get("state") != "complete":
        raise CaptionTimingError("ASR request is pending or failed; resume its existing durable record, never create a replacement request", "asr_pending")
    if not isinstance(record.get("words"), list):
        raise CaptionTimingError("Completed ASR record has no word list")
    return canonical_table(record["words"], source_id=source_id, timing_kind="word", provider="speechmatics",
                           request_id=request_id, receipt_sha256=_digest(record))
