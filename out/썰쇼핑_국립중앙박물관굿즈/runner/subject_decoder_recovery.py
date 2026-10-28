"""Local full-output equivalence; never infer historical decoder bytes."""
import hashlib
import json
from pathlib import Path
import tempfile

NAME='decoder-output-equivalence-v1.json'

def expected(saved,current,raw):
    return dict(version=1,mode='all-frame-png-pts-v1',original_manifest_sha256=hashlib.sha256(raw).hexdigest(),
                content_recipe=current,frames=len(saved['sha256']))

def valid(directory,current):
    directory=Path(directory)
    try:
        raw=(directory/'frame-evidence.json').read_bytes();saved=json.loads(raw)
        proof=json.loads((directory/NAME).read_text(encoding='utf-8'))
        return ('storage' not in saved and isinstance(saved.get('sha256'),list)
                and proof==expected(saved,current,raw))
    except (OSError,ValueError,TypeError,KeyError):return False

def recover(F,cut,policy,directory,current,timeline,source_digest):
    from subject_frame_stream import PixelPipe
    directory=Path(directory)
    with F.R.review_receipt_lock(str(directory/'frame-evidence.json')):
        raw=(directory/'frame-evidence.json').read_bytes();saved=json.loads(raw)
        if valid(directory,current):return True
        if (directory/NAME).exists():raise F.R.StepError('기존 출력 동등성 증거가 달라졌습니다. 원문을 보존합니다.')
        old=saved.get('recipe');old_shape=dict(old) if isinstance(old,dict) else {}
        old_shape.pop('tools',None);old_shape['version']=2
        shape=dict(current);shape.pop('tools',None)
        if shape.pop('extraction_algorithm',None)!='legacy-seek-fps-v1' or old_shape!=shape:return False
        n=round(float(cut['duration'])*float(cut['fps']))
        hashes=saved.get('sha256');pts=saved.get('pts');cuts=saved.get('cuts')
        if ('storage' in saved or 'frame_indices' in old or not isinstance(hashes,list) or len(hashes)!=n
                or not isinstance(pts,list) or len(pts)!=n or not isinstance(cuts,list)):
            return False # Sampled evidence cannot certify unobserved pictures.
        if source_digest(cut['src'])!=current['source_identity']:raise F.R.StepError('원본 바이트가 달라졌습니다.')
        paths=[directory/f'frame_{i:06d}.png' for i in range(n)]
        for path,sha in zip(paths,hashes):
            if not path.is_file() or F._sha(path)!=sha:raise F.R.StepError('기존 전체 프레임 SHA를 확인하지 못했습니다. 원문을 보존합니다.')
        F._check_source_pts(pts,cut,timeline)
        # Only bounded PNG bytes and a metadata log are generated. Never create
        # another full PNG cache, even for a many-gigabyte original directory.
        stage=Path(tempfile.mkdtemp(prefix='.decoder-equivalence-',dir=directory.parent))/directory.name
        stage.mkdir()
        def fail(message):raise F.R.StepError(message+' 기존 검수 원문을 보존합니다.')
        class Frames:
            observed_hashes={}
            def __len__(self):return n
            def hashes(self):return dict(enumerate(hashes))
        frames=Frames();frames.fail=fail
        args=F._decode_frames(cut,stage,policy,timeline=timeline,_command_only=True)
        pipe=PixelPipe(frames,args[:-1]+['-c:v','png','-f','image2pipe','pipe:1'])
        failed=False
        try:
            for index in range(n):pipe.at(index)
            pipe.log.seek(0);log=pipe.log.read().decode('utf-8','replace')
            _,actual_cuts,actual_pts=F._decoded_frame_evidence(cut,stage,policy,log,paths)
            if actual_cuts!=cuts or actual_pts!=pts:fail('전체 프레임의 PTS 또는 장면 경계가 다릅니다.')
            if cut.get('video_timing') is not None:
                if (F._sha(directory/'video-timing.json')!=saved.get('timing_sha256')
                        or F._sha(stage/'video-timing.json')!=saved.get('timing_sha256')):
                    fail('영상 시간축 영수증이 다릅니다.')
            if (source_digest(cut['src'])!=current['source_identity']
                    or F._frame_recipe(cut,policy,current['source_identity'])!=current
                    or (directory/'frame-evidence.json').read_bytes()!=raw):fail('동등성 확인 중 원본 조건이 바뀌었습니다.')
            F.R._photo_write_state(str(directory/NAME),expected(saved,current,raw))
            return True
        except BaseException as error:
            failed=True
            error.frame_evidence_staging=str(stage.parent)
            raise
        finally:
            try:pipe.close()
            except BaseException as error:
                if not failed:
                    error.frame_evidence_staging=str(stage.parent)
                    raise
