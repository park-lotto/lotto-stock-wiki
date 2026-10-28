"""Preserved sample identity with NEW local tracking, never full-frame equivalence.

Only the global cache-only selection entry may use this reader. It never changes
an original manifest/PNG, never adds a review attachment, and never certifies the
unobserved historical pictures. Missing/new questions stay unresolved.
"""
import hashlib
import json
from pathlib import Path
import tempfile
from subject_frame_stream import SampledFrames, PixelPipe

NAME='stored-sample-local-measurement-v1.json'

def candidate(previous,current):
    if (not isinstance(previous,dict) or type(previous.get('version')) is not int or previous.get('version')!=1
            or not isinstance(current,dict) or type(current.get('version')) is not int or current.get('version')!=2):return False
    old=dict(previous);old.pop('tools',None);old['version']=2
    now=dict(current);now.pop('tools',None)
    return now.pop('extraction_algorithm',None)=='legacy-seek-fps-v1' and old==now

class PreservedSamples(SampledFrames):
    def __init__(self,F,cut,directory,policy,digest,timeline):
        super().__init__(F,cut,directory,policy,digest,timeline)
        self.raw=self.manifest.read_bytes()
        self.saved=json.loads(self.raw)
        self.saved_content=json.dumps(self.saved,sort_keys=True,ensure_ascii=False)
        self.measurement_origin='current-local-tracking-not-historical-unsampled-equivalence'

    def check_source(self):
        super().check_source()
        if json.dumps(self.saved,sort_keys=True,ensure_ascii=False)!=self.saved_content:self.fail('보존 표본의 메모리 내용이 바뀌었습니다.')
        if self.manifest.read_bytes()!=self.raw:self.fail('복구 중 원래 표본 영수증이 바뀌었습니다.')
        if hasattr(self,'proof_sha') and self.F._sha(self.directory/NAME)!=self.proof_sha:
            self.fail('복구 중 로컬 측정 증거가 바뀌었습니다.')

    def validate(self,saved,*,files=True):
        if (not isinstance(saved,dict) or not candidate(saved.get('recipe'),self.recipe)
                or saved.get('storage')!='sampled-png-v1' or type(saved.get('nframes')) is not int
                or saved['nframes']!=self.count):self.fail('기존 표본만 보존하는 복구 조건이 아닙니다.')
        pts,cuts,samples=saved.get('pts'),saved.get('cuts'),saved.get('samples')
        if (not isinstance(pts,list) or len(pts)!=self.count
                or any(p is not None and not self.F._number(p) for p in pts)
                or not isinstance(cuts,list) or any(type(i) is not int or not 0<i<self.count for i in cuts)
                or cuts!=sorted(set(cuts)) or not isinstance(samples,dict) or not samples
                or any(not isinstance(k,str) or not k.isascii() or not k.isdigit()
                    or str(int(k))!=k or not 0<=int(k)<self.count for k in samples)
                or any(not isinstance(v,str) or not self.F.re.fullmatch('[0-9a-f]{64}',v) for v in samples.values())):
            self.fail('원래 표본 번호·SHA·시간축이 잘못되었습니다.')
        self.F._check_source_pts(pts,self.cut,self.timeline)
        if files:
            for index,sha in self.hashes(saved).items():
                if not self[index].is_file() or self.F._sha(self[index])!=sha:
                    self.fail('원래 질문 표본이 없거나 바이트가 바뀌었습니다.')
            if self.cut.get('video_timing') is not None:
                timing=self.directory/'video-timing.json'
                if not timing.is_file() or self.F._sha(timing)!=saved.get('timing_sha256'):
                    self.fail('원래 질문 시간축 증거가 바뀌었습니다.')

    def initialize(self,before_decode=None):
        with self.F.R.review_receipt_lock(str(self.manifest)):
            if any((self.directory/name).exists() for name in ('sample-transaction.json','frame-transaction.json')):
                self.fail('원래 프레임 게시가 끝나지 않았습니다.')
            # This fallback is reached only after normal identity validation
            # failed. Never bypass an existing contradictory/corrupted identity
            # attestation by minting a different kind of proof.
            if (self.directory/'decoder-identity-v1.json').exists() or (self.directory/'decoder-output-equivalence-v1.json').exists():
                self.fail('기존 디코더 정체성 증거와 충돌합니다. 원래 증거를 보존합니다.')
            self.validate(self.saved);self.check_source()
            proof=dict(version=1,scope=self.measurement_origin,
                original_manifest_sha256=hashlib.sha256(self.raw).hexdigest(),
                current_recipe=self.recipe,stored_samples=self.saved['samples'])
            path=self.directory/NAME
            if path.exists():
                try:matches=json.loads(path.read_text(encoding='utf-8'))==proof
                except (OSError,ValueError):matches=False
                if not matches:self.fail('기존 로컬 측정 복구 증거가 바뀌었습니다.')
            else:
                self.verify_current_samples_and_clock()
                self.validate(self.saved);self.check_source()
                self.F.R._photo_write_state(str(path),proof)
            self.proof_sha=self.F._sha(path)
        self.observed_hashes.clear() # Future tracking records its own measured PNGs.
        step=max(1,round(self.policy['sample_interval']*float(self.cut['fps'])))
        self.prepare(sorted(set(range(0,self.count,step))|{self.count-1}|{i for c in self.saved['cuts'] for i in (c-1,c)}))

    def verify_current_samples_and_clock(self):
        # Decode to a bounded PNG pipe. PixelPipe checks only the saved samples;
        # all other outputs are new local measurements, not historical equality.
        stage=Path(tempfile.mkdtemp(prefix='.sample-local-proof-',dir=self.directory.parent))/self.directory.name
        stage.mkdir()
        args=self.F._decode_frames(self.cut,stage,self.policy,timeline=self.timeline,_command_only=True)
        pipe=PixelPipe(self,args[:-1]+['-c:v','png','-f','image2pipe','pipe:1']);failed=False
        try:
            for index in range(self.count):pipe.at(index)
            pipe.log.seek(0);log=pipe.log.read().decode('utf-8','replace')
            # The parser only uses the sequence length and metadata; images
            # are read from the pipe, never emitted as a dense disk cache.
            paths=[self[i] for i in range(self.count)]
            _,cuts,pts=self.F._decoded_frame_evidence(self.cut,stage,self.policy,log,paths)
            if cuts!=self.saved['cuts'] or pts!=self.saved['pts']:
                self.fail('현재 로컬 측정 시간축이 원래 질문 시간축과 다릅니다.')
            if self.cut.get('video_timing') is not None and self.F._sha(stage/'video-timing.json')!=self.saved['timing_sha256']:
                self.fail('현재 로컬 측정의 질문 시간축 증거가 다릅니다.')
        except BaseException as error:
            failed=True;error.frame_evidence_staging=str(stage.parent);raise
        finally:
            try:pipe.close()
            except BaseException:
                if not failed:raise

    def local_measurement(self):
        self.check_source()
        from subject_decoder_identity import recipe_sha
        return dict(scope=self.measurement_origin,
            original_manifest_sha256=hashlib.sha256(self.raw).hexdigest(),
            current_recipe_sha256=recipe_sha(self.recipe),
            proof_sha256=self.proof_sha,saved_reviews_only=True)

    def prepare(self,indices):
        self.check_source();self.validate(self.saved)
        if any(type(i) is not int or not 0<=i<self.count for i in indices):
            self.fail('요청 표본이 원래 영상 격자와 다릅니다.')
        known=self.hashes()
        if any(i not in known for i in indices):
            error=self.F.R.StepError('저장된 질문에 없는 표본이 필요합니다. 원문을 보존하고 새 판독을 자동 요청하지 않습니다.')
            error.code='saved_sample_question_missing'
            raise error

    def recover(self):
        self.fail('로컬 복구 reader는 원래 프레임 게시를 변경하지 않습니다.')

def frames(F,cut,directory,policy,digest,timeline):
    reader=PreservedSamples(F,cut,directory,policy,digest,timeline)
    reader.initialize()
    return reader,reader.saved['cuts'],reader.saved['pts']
