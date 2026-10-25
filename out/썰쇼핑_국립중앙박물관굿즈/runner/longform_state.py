"""Durable incremental stages for longform; shared locks/publication, no API calls."""
from pathlib import Path
import json
import os
import platform
import time
from film_editor import digest, file_digest, file_lock
from volcano_run import _photo_write_state

VERSION = 'geumbit-longform-v1'

class ProductionError(ValueError):
    def __init__(self, code, message, *, action='repair', retryable=False):
        super().__init__(message)
        self.code, self.action, self.retryable = code, action, retryable
    def record(self):
        row = dict(code=self.code, message=str(self), action=self.action, retryable=self.retryable)
        # longform_contract.gathered: every violation of one validate() pass (2026-10-17 #117). Single errors are unchanged.
        if getattr(self, 'violations', None): row['violations'] = self.violations
        return row

def native_path(value):
    """Use Windows extended-length paths without changing global OS settings.

    Stages contain full content hashes. Even normal user-selected work folders
    can exceed MAX_PATH after nesting, so normalize before producing any file.
    """
    path=Path(value).resolve()
    if os.name=='nt':
        name=str(path)
        prefix=chr(92)*2+'?'+chr(92)
        if not name.startswith(prefix):
            name=prefix+'UNC'+chr(92)+name[2:] if name.startswith(chr(92)*2) else prefix+name
        return Path(name)
    return path

def save(path, value):
    path = native_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _photo_write_state(str(path), value)

# Windows: while another process publishes this file with os.replace (save → _photo_write_state), the old
# file is briefly «delete pending» and opening it fails with ERROR_ACCESS_DENIED / sharing violation
# (errno 13 · winerror 5/32/33). The publisher already retries its side with these delays; the reader had
# none, so `status` polling every 0.5 s against a running job turned one unlucky read into a blocked job
# (2026-10-14 운영: runtime_failed «[Errno 13] Permission denied: …status.json» 5건 · 전부 윈도우).
# Same bounded delays as the publisher (total 1.55 s); a real permission problem still raises after them.
_READ_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)
_ON_WINDOWS = os.name == 'nt'

def _lock_retry(action):
    """Run `action()` with the bounded Windows «file briefly held» delays above (winerror 5/32/33 · total 1.55 s).
    One loop for every reader/publisher here — read() and replace() share it. Other systems and other errors raise at
    once; after the last delay the error is raised for the caller to report against that one file."""
    for attempt in range(len(_READ_RETRY_DELAYS) + 1):
        try:
            return action()
        except PermissionError as error:
            if not _ON_WINDOWS or attempt == len(_READ_RETRY_DELAYS) or (
                    getattr(error, 'winerror', None) not in (None, 5, 32, 33)):
                raise
            time.sleep(_READ_RETRY_DELAYS[attempt])

def replace(temp, target):
    """os.replace that survives an antivirus / indexer briefly holding a just-written file on Windows (2026-10-17 신고
    #131: `os.replace(part, final)` raised WinError 5 and stopped the whole runner). Every longform_* publisher uses this.
    (volcano_drive._replace_retry and volcano_run._photo_write_state keep their own copies of these delays — owned by the
    runner-core bundle; they can call this one.)"""
    return _lock_retry(lambda: os.replace(temp, target))

def read(path):
    target = native_path(path)
    return _lock_retry(lambda: json.loads(target.read_text(encoding='utf-8-sig')))

# Per-process sha256 memo for files() (6-00: the same fonts/CSS/media were re-hashed for every block and stage).
# Key = (resolved path, size, mtime_ns, ctime_ns, inode, device): any write changes size or mtime/ctime, so a
# changed key re-hashes. Coarse timestamps (FAT 2 s, exFAT 10 ms) could hide a same-size rewrite inside one tick,
# so — like git's «racy clean» rule — a hash is remembered only when the file's mtime was already at least
# RACY_SECONDS older than the moment hashing started, and only when the stat is unchanged after hashing. A later
# write then necessarily carries a newer mtime (a different key). Not covered: deliberately resetting mtime to its
# old value after a same-size rewrite on Windows (st_ctime is the creation time there) — the same limit as
# git/make. Receipts are unchanged: same sha256, and 'bytes' is still the size stat()ed after hashing.
RACY_SECONDS = 2
_DIGESTS = {}

def file_sha256(path):
    """sha256 of the file at path (a native_path), remembered per process while its identity is unchanged."""
    before = os.stat(path)
    key = (str(path), before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_ino, before.st_dev)
    if key in _DIGESTS:
        return _DIGESTS[key], before.st_size
    started = time.time_ns()
    value = file_digest(path)
    after = os.stat(path)
    same = (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino, after.st_dev) == key[1:]
    settled = before.st_mtime_ns <= started - RACY_SECONDS * 10**9
    if same and settled:
        _DIGESTS[key] = value
    return value, after.st_size

def digest_file(path):
    """sha256 of a file, through the identity-checked per-process memo (6-00: one audio file was hashed
    5~6 times per narration block — engine, prepare_voice, plan/apply pauses, editorial merge, report)."""
    return file_sha256(native_path(path))[0]

def files(paths):
    result = []
    for value in paths:
        p = native_path(value)
        if not p.is_file():
            raise ProductionError('asset_missing', '파일이 없습니다: '+str(p), action='restore_asset')
        sha, size = file_sha256(p)
        result.append({'path':str(p), 'sha256':sha, 'bytes':size})
    return result

class Stages:
    """Caller holds workdir lock. A successful receipt binds exact inputs AND outputs."""
    def __init__(self, root):
        self.root = native_path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = []
        # stage -> receipt outputs [{path,sha256,bytes}] of this run (B3 · 그래픽 실화면 검수가 그림 sha256 을
        # 다시 해시하지 않고 여기서 꺼낸다 — 6-00 중복 지문 금지).
        self.outputs = {}
    def run(self, stage, inputs, sources, produce):
        key = digest({'engine':VERSION, 'stage':stage, 'inputs':inputs, 'sources':files(sources)})
        folder = self.root/'stages'/stage/key
        receipt = folder/'receipt.json'
        if receipt.exists():
            prior = read(receipt)
            if prior.get('key') != key:
                raise ProductionError('receipt_mismatch','작업 기록과 요청이 다릅니다. 기록을 보존합니다.')
            try:
                valid = files([x['path'] for x in prior['outputs']]) == prior['outputs']
            except ProductionError:
                valid = False
            if valid:
                self.events.append({'stage':stage,'key':key,'reused':True})
                self.outputs[stage] = prior['outputs']
                return prior['result']
        folder.mkdir(parents=True, exist_ok=True)
        save(self.root/'status.json',{'engine':VERSION,'state':'running','stage':stage,'key':key})
        start = time.monotonic()
        # Only local work belongs here. Paid requests have their own durable ledger.
        result, paths = produce(folder)
        outputs = files(paths)
        if not outputs:
            raise ProductionError('empty_stage','작업 결과 파일이 없습니다: '+stage)
        save(receipt,{'key':key,'inputs':inputs,'outputs':outputs,'result':result,
                      'seconds':time.monotonic()-start,'os':platform.platform()})
        self.events.append({'stage':stage,'key':key,'reused':False})
        self.outputs[stage] = outputs
        return result
