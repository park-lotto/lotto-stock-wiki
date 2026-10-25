"""HyperFrames graphics: pinned CLI, retained attempts, verified atomic output.

CLI flags are from `hyperframes@0.8.80 render --help` (2026-09-28; `--gpu` checked 2026-10-20).
One local browser worker is our resource policy, not an external API limit.
"""
from pathlib import Path
from fractions import Fraction
import json
import os
import tempfile

from film_editor import command, file_digest
from longform_state import ProductionError, save, replace as publish

VERSION = '0.8.80'


def launcher():
    from longform_render import hyperframes_launcher
    return [*hyperframes_launcher(), '--yes', 'hyperframes@' + VERSION]


def runtime(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = command(folder, [*launcher(), '--version'], 'hyperframes-version')
    version = result.decode('utf-8', 'replace').strip()
    if VERSION not in version:
        raise ProductionError('hyperframes_version', version, action='repair_environment')
    return {'renderer': 'hyperframes', 'version': VERSION}


def _render(folder, args, label, frames, width, height, fps):
    """Run the render with this PC's encoder pick (runner/video_encoder.py — the one picker).

    HyperFrames encodes the mp4 itself; `--gpu` (`hyperframes render --help`: «Use GPU encoding»,
    default off) lets it use the GPU encoder it detects, and it falls back to libx264 on its own when
    none is usable. We pass `--gpu` only when video_encoder judged a GPU usable on this PC, and if that
    render fails we mark the GPU broken for this process and render once more without it (at most two
    tries — the same contract as film_editor.command). Returns the encoder name we asked for."""
    import video_encoder
    slot = video_encoder.x264('fast', 18, width, height, fps, program='ffmpeg', color=False)
    timeout = max(300, frames * 2)
    for gpu, _ in video_encoder.attempts(slot):
        try:
            command(folder, [*args, *(['--gpu'] if gpu else [])], label + ('-gpu' if gpu else ''),
                    timeout=timeout)
            return gpu or video_encoder.cpu_name(slot)
        except ValueError as error:
            if gpu is None or 'time limit' in str(error):
                raise
            video_encoder.failed(gpu, str(error))


def render_document(folder, frames, *, fps=60, width=1920, height=1080):
    if type(frames) is not int or frames <= 0:
        raise ValueError('frames must be a positive integer')
    folder = Path(folder).resolve()
    if not (folder / 'index.html').is_file():
        raise ProductionError('graphic_document_missing', str(folder), action='edit_plan')
    attempt = Path(tempfile.mkdtemp(prefix='hyperframes-render-', dir=folder))
    candidate = attempt / 'graphic.mp4'
    # Relative paths remain valid inside film_editor.process_directory's Windows
    # long-path alias. Never pass a \\?\ Node entry path or invoke a shell.
    output = candidate.relative_to(folder).as_posix()
    args = [*launcher(), 'render', '.', '--output', output, '--fps', str(fps),
            '--quality', 'delivery', '--workers', '1', '--frames-cache-dir', 'off']
    proof = {'renderer': 'hyperframes', 'version': VERSION, 'frames': frames,
             'fps': fps, 'success': False, 'actualOS': os.name}
    try:
        proof['encoder'] = _render(folder, args, attempt.name, frames, width, height, fps)
        raw = command(folder, ['ffprobe', '-v', 'error', '-show_streams',
                              '-of', 'json', output], attempt.name + '-probe')
        streams = json.loads(raw)['streams']
        video = [s for s in streams if s.get('codec_type') == 'video']
        if len(video) != 1:
            raise ValueError('expected exactly one video stream')
        stream = video[0]
        if (int(stream.get('nb_frames', 0)) != frames
                or Fraction(stream['avg_frame_rate']) != fps
                or (stream['width'], stream['height']) != (width, height)):
            raise ValueError('rendered frame clock or dimensions differ from plan')
        if any(s.get('codec_type') == 'audio' for s in streams):
            raise ValueError('picture stage must not introduce a second audio mix')
        command(folder, ['ffmpeg', '-v', 'error', '-xerror', '-i', output,
                         '-f', 'null', '-'], attempt.name + '-decode',
                timeout=max(300, frames))
        proof.update(sha256=file_digest(candidate), stream=stream)
        with candidate.open('r+b') as file:
            os.fsync(file.fileno())
        publish(candidate, folder / 'graphic.mp4')
        proof['success'] = True
        return folder / 'graphic.mp4'
    except (OSError, ValueError) as error:
        proof['error'] = str(error)
        raise ProductionError('hyperframes_render_failed', str(error),
                              action='repair_environment') from error
    finally:
        save(attempt / 'result.json', proof)
