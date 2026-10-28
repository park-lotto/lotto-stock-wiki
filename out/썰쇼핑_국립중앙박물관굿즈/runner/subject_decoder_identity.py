"""Content identity for decoders; legacy proof never replaces paid/frame receipts."""
import functools
import hashlib
import json
from pathlib import Path


def signature(path):
    from volcano_run import _ArgvInputDigests, _FileBody, _review_receipt_io_path
    # Windows st_ctime may mean creation time. Reuse the existing actual open
    # handle ChangeTime guard, including path-replacement detection.
    with open(_review_receipt_io_path(path),'rb') as handle:
        stamp=_ArgvInputDigests._stamp(handle)
        if stamp[:4]!=_FileBody._stamp(path.stat()):raise OSError('decoder path changed')
        return stamp


@functools.lru_cache(maxsize=8)
def _digest(path,stamp):
    digest=hashlib.sha256()
    from volcano_run import _review_receipt_io_path
    with open(_review_receipt_io_path(path),'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    if signature(Path(path))!=stamp:raise OSError('decoder changed while hashing')
    return digest.hexdigest()


def binary_identity(path):
    stamp=signature(path)
    value=_digest(str(path),stamp)
    if signature(path)!=stamp:raise OSError('decoder changed while identifying')
    return dict(path=str(path),sha256=value)


def recipe_sha(recipe):
    return hashlib.sha256(json.dumps(recipe,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _proof(directory):
    path=Path(directory)/'decoder-identity-v1.json'
    if not path.exists():return None
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return False


def compatible(F,previous,current,cut,policy,directory):
    if previous==current:return True
    if (not isinstance(previous,dict) or previous.get('version')!=1
            or not isinstance(current,dict) or current.get('version')!=2):return False
    old_shape=dict(previous);old_shape.pop('tools',None);old_shape['version']=2
    new_shape=dict(current);new_shape.pop('tools',None)
    # This is the audited, unchanged deployed extraction algorithm. A new
    # source clock/filter algorithm cannot inherit any legacy compatibility.
    if new_shape.pop('extraction_algorithm',None)!='legacy-seek-fps-v1':return False
    if old_shape!=new_shape:return False
    from subject_decoder_recovery import valid
    if valid(directory,current):return True
    proof=_proof(directory)
    expected=dict(version=1,legacy_recipe_sha256=recipe_sha(previous),content_recipe=current)
    if proof is not None:return proof==expected
    # A metadata-mismatched old receipt has no historical binary digest. Never
    # infer equivalence merely because today's executable hashes successfully.
    legacy=F._legacy_frame_recipe(cut,policy,current['source_identity'])
    if legacy is not None and 'frame_indices' in current:legacy=dict(legacy,frame_indices=current['frame_indices'])
    return legacy==previous


def record_verified(F,saved,current,cut,policy,directory,source_digest=None):
    previous=saved.get('recipe')
    if previous==current:return
    if not compatible(F,previous,current,cut,policy,directory):
        raise F.R.StepError('기존 디코더의 원래 바이트를 확인할 수 없습니다. 검수 영수증을 보존합니다.')
    from subject_decoder_recovery import valid
    if valid(directory,current):return
    proof=dict(version=1,legacy_recipe_sha256=recipe_sha(previous),content_recipe=current)
    existing=_proof(directory)
    if existing==proof:return
    if existing is not None:raise F.R.StepError('디코더 정체성 증거가 달라졌습니다. 기존 영수증을 보존합니다.')
    if (source_digest or F._sha)(cut['src'])!=current['source_identity']:
        raise F.R.StepError('검증 중 원본 바이트가 바뀌었습니다. 기존 영수증을 보존합니다.')
    checked=F._frame_recipe(cut,policy,current['source_identity'])
    if checked is not None and 'frame_indices' in current:checked=dict(checked,frame_indices=current['frame_indices'])
    if checked!=current:
        raise F.R.StepError('검증 중 디코더 바이트가 바뀌었습니다. 기존 영수증을 보존합니다.')
    # Caller holds the frame receipt OS lock and has verified source, every
    # recorded PNG and the complete PTS contract before writing this sidecar.
    F.R._photo_write_state(str(Path(directory)/'decoder-identity-v1.json'),proof)
