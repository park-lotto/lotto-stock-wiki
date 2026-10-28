"""Selected dialogue word timing with durable batch identity and source mapping.

The caller holds its edit-root lock. Submitted batches survive edit changes;
existing paid ledgers and source files are never removed or rewritten.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import wave

from film_caption import canonical_table


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _request_identity(plan):
    if plan.get('order') != ['speechmatics'] or set(plan.get('providers',{})) != {'speechmatics'} or plan.get('local_authorized'):
        raise ValueError('Selected timing requires the explicit cloud-only Speechmatics plan')
    cfg=plan['providers']['speechmatics']
    request_keys=('kind','submit_url','fields','file_field','bin','argv','reads')
    return _digest(['speechmatics',{k:cfg[k] for k in request_keys if k in cfg}])


def selected_coverage(root, source_id, plan):
    """Read measured source intervals, including completed intervals with zero words.

    An existing word table does not imply full-film coverage. The caller can use
    missing_ranges(requested, selected_coverage(...)) to decide whether another
    selected measurement is needed, rather than treating missing words as text
    correction. This function never creates files or submits/resumes a request.
    """
    request_id=_request_identity(plan);rate=16000
    namespace=_digest([source_id,request_id,rate])
    path=Path(root)/'word-audio'/namespace/'coverage.json'
    if not path.is_file():return []
    state=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(state,dict) or state.get('source_id')!=source_id or state.get('request_id')!=request_id or not isinstance(state.get('batches'),list):
        raise ValueError('Word timing coverage identity changed; preserve records')
    coverage=[]
    for batch in state['batches']:
        if not isinstance(batch,dict) or type(batch.get('complete')) is not bool or not isinstance(batch.get('coverage'),list):
            raise ValueError('Word timing coverage record is corrupt')
        samples=missing_ranges(batch['coverage'],[],rate)
        if batch.get('id')!=_digest([namespace,samples]):
            raise ValueError('Word timing coverage identity changed')
        if batch['complete']:
            if not isinstance(batch.get('words'),list) or (batch.get('words_sha256') and batch['words_sha256']!=_digest(batch['words'])):
                raise ValueError('Completed word timing data changed')
            coverage.extend(batch['coverage'])
    return coverage


def missing_ranges(ranges, coverage, rate=16000):
    if type(rate) is not int or rate <= 0:
        raise ValueError('Word timing sample rate must be a positive integer')
    for a,b in list(ranges)+list(coverage):
        if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (a,b)) or a<0 or b<=a:
            raise ValueError('Selected word timing needs finite ordered source intervals')
    requested = sorted((max(0, math.floor(a*rate)), math.ceil(b*rate)) for a,b in ranges)
    merged = []
    for a,b in requested:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b,merged[-1][1])
        else:
            merged.append([a,b])
    for ca,cb in coverage:
        ca,cb = round(ca*rate),round(cb*rate)
        merged = [piece for a,b in merged for piece in
                  ([[a,b]] if cb<=a or ca>=b else [[a,min(b,ca)],[max(a,cb),b]]) if piece[1]>piece[0]]
    return merged


#: 새 묶음에서 떨어진 원음 조각 사이에 끼우는 무음(샘플 수 = rate × 이 초) — 낱말이 이음매를 넘지 않게 한다(#176).
#: 공식 숫자가 아니라 이 편집기의 값이다(전사기가 0.5초 무음을 넘어 한 낱말로 잇지 않는다는 실측은 없다 — 남는 경우는
#: 아래 map_words 의 «겹침이 큰 조각» 규칙이 받는다).
GAP_SECONDS = 0.5


def map_words(words, chunks, rate):
    """묶음 시각 낱말 → 원본 시각. 이음매에 걸친 낱말은 **겹친 길이가 가장 큰 조각**에 넣고 그 조각 안으로 자른다(#176).

    예전에는 걸친 낱말을 오류로만 처리해, 이미 받은 유료 전사 결과가 «미완료» 로 남고 다음 실행이 같은 결과를 같은
    규칙으로 다시 매핑해 같은 실패를 되풀이했다(빠져나갈 수 없는 고리 · 3명). 결정적 규칙이라 같은 결과는 같은 표가 된다.
    """
    mapped = []
    for word in words:
        a,b = float(word['start']),float(word['end'])
        if not math.isfinite(a) or not math.isfinite(b) or not 0<=a<b:
            raise ValueError('Measured words have invalid start/end times; preserve the completed request')
        best, overlap = None, 0.0
        for c in chunks:
            o = min(b, c['batch_end']/rate) - max(a, c['batch_start']/rate)
            if o > overlap:
                best, overlap = c, o
        if best is None:
            raise ValueError('A measured word lies outside every selected audio interval; preserve the receipt and review this source interval')
        c = best
        shift = (c['source_start']-c['batch_start'])/rate
        start,end=max(c['source_start']/rate,a+shift),min(c['source_end']/rate,b+shift)
        if end<=start:
            raise ValueError('A measured word has no duration inside the selected source interval')
        mapped.append({'start':start, 'end':end,
                       'word':word.get('word',word.get('text'))})
    return mapped


def _provider_finished(batch, request_id, read_json):
    """다른 설정(언어)의 미완료 묶음이 **제공자 쪽에서는 끝났나** — 결과를 이미 받아(접수 원장 state 'complete') 제공자에게
    걸린 일이 없으면, 그 묶음을 두고 새 설정으로 넘어가도 접수된 유료 작업을 버리는 것이 아니다(#176 · 옛 판이 출력 언어로
    전사해 매핑에 실패한 묶음). 접수만 되고 결과가 없는 묶음은 예전처럼 지킨다. 원장 파일 이름은 실행기가 정한 규칙
    (`<wav 폴더>/.volcano-asr/<wav sha256>.json`) 그대로다."""
    sha = batch.get('wav_sha256')
    if not isinstance(sha, str) or not batch.get('wav'):
        return False
    ledger = Path(batch['wav']).parent / '.volcano-asr' / (sha + '.json')
    if not ledger.is_file():
        return False
    try:
        record = (read_json(ledger).get('requests') or {}).get(request_id) or {}
    except (OSError, ValueError, AttributeError):
        return False
    return record.get('state') == 'complete'


def selected_word_table(root, source, source_id, ranges, plan, *, command, atomic_json, read_json, file_digest, transcribe):
    """Return canonical measured words; resume pending batch before new coverage."""
    root = Path(root)
    rate = 16000
    if file_digest(source)!=source_id:
        raise ValueError('Source hash changed; preserve all existing word timing requests')
    request_id = _request_identity(plan)
    namespace = _digest([source_id,request_id,rate])
    folder = root / 'word-audio' / namespace
    # A changed language/configuration must not silently abandon an accepted
    # billable batch in another namespace and create a replacement request.
    for other in (root/'word-audio').glob('*/coverage.json'):
        if other.parent==folder:
            continue
        previous=read_json(other)
        if not isinstance(previous,dict) or not isinstance(previous.get('batches'),list):
            raise ValueError('Existing word timing coverage is corrupt; preserve its records')
        if any(not b.get('complete') and not _provider_finished(b, previous.get('request_id'), read_json)
               for b in previous['batches']):
            raise ValueError('Another word timing configuration has a pending batch; resume its original source and plan before changing configuration')
    folder.mkdir(parents=True,exist_ok=True)
    state_path = folder / 'coverage.json'
    state = read_json(state_path) if state_path.exists() else {'source_id':source_id,'request_id':request_id,'batches':[]}
    if not isinstance(state,dict) or state.get('source_id') != source_id or state.get('request_id') != request_id or not isinstance(state.get('batches'),list):
        raise ValueError('Word timing coverage identity changed; preserve records')
    for batch in state['batches']:
        if not isinstance(batch,dict) or type(batch.get('complete')) is not bool or not isinstance(batch.get('coverage'),list) or not isinstance(batch.get('chunks'),list):
            raise ValueError('Word timing batch record is corrupt; preserve existing requests')
        samples=missing_ranges(batch['coverage'],[],rate)
        if batch.get('id')!=_digest([namespace,samples]) or Path(batch.get('wav','')).resolve()!=(folder/(batch['id']+'.wav')).resolve():
            raise ValueError('Word timing batch source coverage or file identity changed')
        gap=batch.get('gap',0)
        if type(gap) is not int or gap<0:
            raise ValueError('Word timing batch gap is corrupt; preserve existing requests')
        chunks=[];cursor=0
        for a,b in samples:
            chunks.append({'source_start':a,'source_end':b,'batch_start':cursor,'batch_end':cursor+b-a});cursor+=b-a+gap
        if chunks!=batch['chunks']:
            raise ValueError('Word timing source mapping changed; preserve its receipt')
        if batch['complete'] and (not isinstance(batch.get('words'),list) or
                (batch.get('words_sha256') and batch['words_sha256']!=_digest(batch['words']))):
            raise ValueError('Completed word timing data changed; restore its completed receipt')
    if sum(not b['complete'] for b in state['batches'])>1:
        raise ValueError('Multiple pending word timing batches require existing-receipt recovery')
    missing = missing_ranges(ranges,[r for b in state['batches'] if b.get('complete') for r in b['coverage']],rate)
    pending = next((b for b in state['batches'] if not b.get('complete')),None)
    if pending is None and missing:
        batch_id = _digest([namespace,missing])
        gap = round(GAP_SECONDS*rate)
        pending = {'id':batch_id,'coverage':[[a/rate,b/rate] for a,b in missing],
                   'chunks':[],'wav':str(folder/(batch_id+'.wav')),'complete':False,'gap':gap}
        wav = Path(pending['wav'])
        if wav.exists() and (wav.parent/'.volcano-asr'/(file_digest(wav)+'.json')).exists():
            raise ValueError('Existing selected audio has a paid receipt but missing coverage; restore the original coverage record before reuse')
        pieces = []
        cursor = 0
        for index,(a,b) in enumerate(missing):
            piece = folder/(batch_id+f'-{index}.wav')
            command(folder,['ffmpeg','-v','error','-ss',a/rate,'-i',source,'-map','0:a:0','-vn',
                '-af',f'aresample={rate},atrim=end_sample={b-a},asetpts=PTS-STARTPTS',
                '-ac',1,'-ar',rate,'-c:a','pcm_s16le','-y',piece],f'word-extract-{index}')
            with wave.open(str(piece),'rb') as handle:
                if handle.getnchannels()!=1 or handle.getsampwidth()!=2 or handle.getframerate()!=rate or handle.getnframes()!=b-a:
                    raise ValueError('Selected dialogue WAV sample count does not match source mapping')
                pieces.append(handle.readframes(handle.getnframes()))
            pending['chunks'].append({'source_start':a,'source_end':b,'batch_start':cursor,'batch_end':cursor+b-a})
            cursor += b-a+gap
        descriptor,tmp=tempfile.mkstemp(prefix=batch_id+'-',suffix='.pending.wav',dir=folder)
        try:
            with os.fdopen(descriptor,'w+b') as stream:
                with wave.open(stream,'wb') as handle:
                    handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(rate)
                    silence=b'\0\0'*gap
                    for index,data in enumerate(pieces):
                        if index:handle.writeframes(silence)
                        handle.writeframes(data)
                stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,wav)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        pending['wav_sha256'] = file_digest(wav)
        state['batches'].append(pending)
        atomic_json(state_path,state)
    if pending:
        wav=Path(pending['wav'])
        if file_digest(wav)!=pending['wav_sha256']:
            raise ValueError('Pending selected audio changed; do not submit another file')
        # Do not retry an explicitly failed billable batch automatically either.
        ledger=wav.parent/'.volcano-asr'/(pending['wav_sha256']+'.json')
        if ledger.exists() and (read_json(ledger).get('requests',{}).get(request_id) or {}).get('state')=='failed':
            raise ValueError('Selected audio request failed; preserve its receipt and resolve provider failure before any new request')
        selected_plan={k:v for k,v in plan.items() if k!='audio'}
        words,provider=transcribe(str(wav),selected_plan,{})
        if provider!='speechmatics':raise ValueError('Unexpected word timing provider')
        pending['words']=map_words(words,pending['chunks'],rate)
        pending['words_sha256']=_digest(pending['words'])
        pending['complete']=True
        atomic_json(state_path,state)
        # A changed edit may have needed different coverage while a batch was pending.
        missing=missing_ranges(ranges,[r for b in state['batches'] if b.get('complete') for r in b['coverage']],rate)
        if missing:
            return selected_word_table(root,source,source_id,ranges,plan,command=command,
                atomic_json=atomic_json,read_json=read_json,file_digest=file_digest,transcribe=transcribe)
    rows=[]
    for batch in state['batches']:
        result_sha=_digest(batch.get('words',[]))
        rows.extend({**word,'origin':{'batch_id':batch['id'],'word_index':index,'record_sha256':result_sha}}
                    for index,word in enumerate(batch.get('words',[])))
    rows.sort(key=lambda word:word['start'])
    return canonical_table(rows,source_id=source_id,timing_kind='word',provider='speechmatics',
        request_id=request_id,receipt_sha256=_digest(state))
