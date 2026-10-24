"""Author-supplied narration for 인물형 롱폼 (existing_voice.format = external-wav-v1).

2026-10-16: a student narrated every block with Gemini speech and declared it as existing_voice
{format: external-wav-v1, path, sha256}. verify_import() only knew Typecast records, read item['metadata'] and stopped the
whole job with KeyError 'metadata' (runtime_failed) before the first block. The customization decision (2026-09-15) is
that an author's request is produced as asked, so the engine must accept the author's own voice.

What Typecast gave us for free and an outside voice does not: per-character speech times. Captions, sentence breaths,
motion cues and cuts are all placed on those times, so they are measured — never spread by character count (that was
measured at 0.149 s mean / 0.276 s max error and is forbidden by the caption rule). The measurement is the runner's
existing word-timing ladder (`volcano_run.transcribe_words` with the server's `asr_plan`: Speechmatics → … → local
whisper, which needs no key). Its own receipts make a rerun resume the same request instead of buying a second one.
The word list is stored once per audio fingerprint; the text→character mapping is recomputed from it (it is cheap and
follows script edits without a new transcription).
"""
import difflib
import json
import os
import wave
from pathlib import Path

from film_editor import command
from longform_state import ProductionError, native_path, digest_file as file_digest, replace as publish

FORMAT = 'external-wav-v1'
# Same lower bound the caption aligner uses for "this speech is that text" (MIN_TOKEN_MATCH_RATIO 0.5): below it the
# recording says something else and no honest caption time exists for the script.
MIN_MATCH = 0.5


def is_external(item):
    return isinstance(item, dict) and item.get('format') == FORMAT


def _folder(root, sha):
    folder = Path(native_path(Path(root) / 'external-voice' / sha[:32]))
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _pcm16_mono(path):
    try:
        with wave.open(str(path), 'rb') as stream:
            return (stream.getnchannels(), stream.getsampwidth(), stream.getcomptype()) == (1, 2, 'NONE') \
                and 8000 <= stream.getframerate() <= 192000
    except (wave.Error, EOFError, OSError):
        return False


def pcm(item, root):
    """The author's file as mono PCM16 WAV (the format every timing/breath stage reads). Verified once by fingerprint;
    any other container/codec ffmpeg can decode is converted once, next to the work, and reused."""
    if not isinstance(item.get('path'), str) or not isinstance(item.get('sha256'), str):
        raise ProductionError('external_voice_contract', '외부 음성은 existing_voice {format:"external-wav-v1", path, sha256} 로 지정하세요.',
                              action='edit_plan')
    source = Path(native_path(item['path']))
    if not source.is_file():
        raise ProductionError('external_voice_missing', '외부 음성 파일이 없습니다: ' + item['path'], action='restore_asset')
    sha = file_digest(source)
    if sha != item['sha256']:
        raise ProductionError('voice_import_changed', '외부 음성 파일의 지문이 제작표와 다릅니다: ' + item['path'], action='restore_asset')
    if _pcm16_mono(source):
        return source, sha
    folder = _folder(root, sha)
    out = folder / 'voice.wav'
    if not _pcm16_mono(out):
        part = folder / 'voice.part.wav'
        # Keep the author's sample rate when it is a normal one; 48 kHz otherwise (the master rate).
        command(folder, ['ffmpeg', '-y', '-v', 'error', '-i', source, '-vn', '-ac', '1', '-c:a', 'pcm_s16le', part],
                'external-voice-pcm')
        if not _pcm16_mono(part):
            raise ProductionError('external_voice_format', '외부 음성을 PCM16 WAV 로 바꾸지 못했습니다: ' + item['path'], action='restore_asset')
        publish(part, out)
    return out, sha


def words(item, root, asr):
    """Measured word times for the author's audio (one transcription per audio fingerprint, resumable)."""
    audio, sha = pcm(item, root)
    folder = _folder(root, sha)
    stored = folder / 'words.json'
    if stored.is_file():
        data = json.loads(stored.read_text('utf-8'))
        if data.get('audio_sha256') == sha and isinstance(data.get('words'), list):
            return audio, data['words']
    if not isinstance(asr, dict) or not isinstance(asr.get('providers'), dict) or not asr.get('order'):
        raise ProductionError('external_voice_timing_plan',
                              '외부 음성의 발화 시각을 재는 서버 설정이 이 작업 설정에 없습니다. longform_seed 를 다시 부르면 서버가 넣습니다.',
                              action='resume', retryable=True)
    from volcano_run import transcribe_words, TranscriptionPending
    try:
        measured, provider = transcribe_words(str(audio), asr, {})
    except TranscriptionPending as pending:
        raise ProductionError('external_voice_timing_pending', str(pending), action='resume', retryable=True) from pending
    rows = [{'word': str(w.get('word') or ''), 'start': float(w['start']), 'end': float(w['end'])}
            for w in measured if isinstance(w, dict) and w.get('start') is not None and w.get('end') is not None]
    part = folder / 'words.part.json'
    part.write_text(json.dumps({'audio_sha256': sha, 'provider': provider, 'words': rows}, ensure_ascii=False), 'utf-8')
    publish(part, stored)
    return audio, rows


def characters_from_words(text, rows, duration):
    """Per-character times for `text` from measured words, in one pass over the matching blocks.

    Letters/digits are matched to the spoken letters (case-folded) by SequenceMatcher on the two letter lists of one
    block (bounded by the block's length). A matched letter takes its share of its word's span; an unmatched run is
    spread inside the gap its matched neighbours leave (it is between two measured points, not guessed from the whole
    text). Spaces and punctuation take the previous letter's end, so a sentence gap stays exactly the measured silence
    between the last word of one sentence and the first word of the next (what the breath stage inserts into)."""
    letters = [(i, c.casefold()) for i, c in enumerate(text) if c.isalnum()]
    if not letters:
        raise ProductionError('external_voice_text', '외부 음성 블록의 대본에 글자가 없습니다.', action='edit_plan')
    spoken, spans = [], []
    for row in rows:
        s, e = max(0.0, row['start']), max(row['start'], row['end'])
        chars = [c.casefold() for c in row['word'] if c.isalnum()]
        for k, c in enumerate(chars):
            spoken.append(c)
            spans.append((s + (e - s) * k / len(chars), s + (e - s) * (k + 1) / len(chars)))
    times = [None] * len(letters)
    matcher = difflib.SequenceMatcher(None, [c for _, c in letters], spoken, autojunk=False)
    for a, b, size in matcher.get_matching_blocks():
        for j in range(size):
            times[a + j] = spans[b + j]
    matched = sum(t is not None for t in times)
    if matched < MIN_MATCH * len(letters):
        raise ProductionError('external_voice_mismatch',
                              f'외부 음성이 이 블록 대본과 다르게 들립니다(대본 글자 {len(letters)}개 중 {matched}개만 음성에서 확인). '
                              f'블록 앞부분: {text[:40]!r}. 이 블록의 음성 파일이 맞는지 확인하세요.', action='review_audio')
    # Fill unmatched runs between their measured neighbours (one pass).
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(times) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i else (times[j][0] if j < len(times) else 0.0)
        hi = times[j][0] if j < len(times) else max(lo, duration)
        step = (hi - lo) / (j - i)
        for k in range(i, j):
            times[k] = (lo + step * (k - i), lo + step * (k - i + 1))
        i = j
    at = dict(zip((i for i, _ in letters), times))
    characters, last = [], times[0][0]
    for i, c in enumerate(text):
        if i in at:
            s, e = at[i]
            s = max(s, last)
            e = min(max(e, s), duration)
            s = min(s, e)
            last = e
            characters.append({'text': c, 'start': s, 'end': e})
        else:
            characters.append({'text': c, 'start': last, 'end': last})
    return characters


def load(item, text, root, asr):
    """(mono PCM16 path, characters) for one block's author-supplied narration."""
    audio, rows = words(item, root, asr)
    with wave.open(str(audio), 'rb') as stream:
        duration = stream.getnframes() / stream.getframerate()
    return audio, characters_from_words(text, rows, duration)
