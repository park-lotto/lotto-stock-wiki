"""Copy a terminal job into a private repair root without dispatch or receipt edits.

The caller must run the existing signed engine repair admission before switching
any job pin. A prepared copy is not permission to resume or resend requests.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def physical(path):
    """Native file I/O only; job identity and serialized paths remain logical."""
    value = os.path.abspath(os.fspath(path))
    if os.name == "nt":
        prefix = chr(92) * 2 + "?" + chr(92)
        if not value.startswith(prefix):
            value = prefix + "UNC" + chr(92) + value[2:] if value.startswith(chr(92) * 2) else prefix + value
    return Path(value)


def resolved(path, *, strict=False):
    """Resolve physical links, then keep the ordinary path in all identities."""
    value = str(physical(path).resolve(strict=strict))
    prefix = chr(92) * 2 + "?" + chr(92)
    if value.startswith(prefix + "UNC" + chr(92)):
        value = chr(92) * 2 + value[len(prefix) + 4:]
    elif value.startswith(prefix):
        value = value[len(prefix):]
    return Path(value)


def children(path):
    path = Path(path)
    return (path / child.name for child in physical(path).iterdir())


def matching(path, pattern):
    path = Path(path)
    native = physical(path)
    return (path / child.relative_to(native) for child in native.glob(pattern))


def digest_file(path):
    h = hashlib.sha256()
    with physical(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""): h.update(part)
    return h.hexdigest()


def stage(old, approved, destination, job_id):
    old, approved, destination = map(resolved, (old, approved, destination))
    if not re.fullmatch(r'j_[a-f0-9]{64}', job_id):
        raise ValueError('Invalid job identity')
    if destination == old or destination == approved or physical(destination).exists():
        raise ValueError('Repair root must be a fresh private directory')
    folder = old / 'work/_episode_jobs' / job_id
    original = physical(folder / 'job.json').read_bytes()
    job = json.loads(original)
    if job.get('jobId') != job_id or job.get('state') != 'failed' or not job.get('endedAt'):
        raise ValueError('Only a stopped failed job may be copied for signed repair admission')
    project = job.get('request', {}).get('project')
    if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', project):
        raise ValueError('Invalid project identity')
    if resolved(job.get('engineModule', '')) != old / 'tools/make_episode.mjs':
        raise ValueError('Original job does not use the canonical engine entry')
    # Project configuration is executable input. Never let a copied script/audio
    # path silently point back at the original workspace. Provenance journals
    # remain byte-identical and are not rewritten to manufacture a new hash.
    def check_paths(value):
        if isinstance(value, dict):
            for child in value.values(): check_paths(child)
        elif isinstance(value, list):
            for child in value: check_paths(child)
        elif isinstance(value, str):
            normalized = value.replace('\\', '/')
            if normalized == old.as_posix() or normalized.startswith(old.as_posix() + '/'):
                raise ValueError('Project contains an absolute original-root path; safe relocation is not proven')
    check_paths(json.loads(physical(old / 'project' / (project + '.json')).read_text(encoding='utf-8-sig')))
    physical(destination.parent).mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / Path(tempfile.mkdtemp(prefix='.repair-stage-', dir=physical(destination.parent))).name
    evidence = []
    def copy(source, target, preserve=False):
        if physical(source).is_symlink():
            raise ValueError('Repair migration refuses symlinks')
        if physical(source).is_dir():
            physical(target).mkdir(parents=True, exist_ok=True)
            for child in children(source): copy(child, target / child.name, preserve)
            return
        if not physical(source).is_file(): raise ValueError('Missing repair input')
        physical(target.parent).mkdir(parents=True, exist_ok=True)
        # Never hardlink: an engine can rewrite files after admission.
        # Windows fsync requires a writable descriptor. Flush the copy before
        # applying source permissions, including a read-only original.
        with physical(source).open("rb") as original_stream, physical(target).open("wb") as durable:
            shutil.copyfileobj(original_stream, durable)
            durable.flush()
            os.fsync(durable.fileno())
        shutil.copymode(physical(source), physical(target))
        digest = digest_file(source)
        if digest_file(target) != digest:
            raise ValueError('Repair copy verification failed')
        if preserve: evidence.append({'path': str(source.relative_to(old)), 'sha256': digest})
    try:
        for source in children(approved):
            if source.name not in ('work', 'project', '.venv', '.node', '.config'):
                copy(source, temporary / source.name)
        copy(folder, temporary / 'work/_episode_jobs' / job_id, True)
        copy(old / 'work' / project, temporary / 'work' / project, True)
        copy(old / 'project' / (project + '.json'), temporary / 'project' / (project + '.json'), True)
        for relative in ('.config', 'flow/flow_config.local.json'):
            source = old / relative
            if physical(source).exists(): copy(source, temporary / relative, True)
        health = old / 'work/_provider_health'
        if physical(health).exists(): copy(health, temporary / 'work/_provider_health', True)
        claim = old / 'work/_episode_jobs/projects' / (project + '.json')
        if physical(claim).exists(): copy(claim, temporary / 'work/_episode_jobs/projects' / claim.name, True)
        if physical(folder / 'job.json').read_bytes() != original:
            raise ValueError('Original job changed while staging')
        for item in evidence:
            if digest_file(old / item['path']) != item['sha256']:
                raise ValueError('Original evidence changed while staging')
        from longform_state import save
        save(temporary / 'repair_staging.json', {'version': 1, 'source_root': str(old),
            'approved_root': str(approved), 'job_id': job_id, 'evidence': evidence,
            'original_job_sha256': hashlib.sha256(original).hexdigest()})
        with physical(temporary / 'original_job.json').open('wb') as durable:
            durable.write(original)
            durable.flush()
            os.fsync(durable.fileno())
        job['engineModule'] = str(destination / 'tools/make_episode.mjs')
        save(temporary / 'work/_episode_jobs' / job_id / 'job.json', job)
        # Same filesystem rename works on Windows and POSIX with closed handles.
        if os.name != "nt":
            for directory in [p for p in temporary.rglob("*") if p.is_dir()] + [temporary]:
                fd=os.open(directory, os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
        os.rename(physical(temporary), physical(destination))
        if os.name != "nt":
            fd=os.open(destination.parent, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        return destination
    except BaseException as error:
        try:
            shutil.rmtree(physical(temporary))
        except OSError as cleanup_error:
            error.add_note("Repair staging cleanup failed; staging evidence preserved: " + str(cleanup_error))
        raise
