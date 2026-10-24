"""Preserve original Typecast PCM; level utterances and verify the encoded master."""
from pathlib import Path
import json
import math
import re
import wave
from film_editor import command
from longform_state import ProductionError, save, digest_file as file_digest

TARGET = -16.0
TOLERANCE = .2
TRUE_PEAK = -1.5
# Owner decision 2026-10-13 (same rule as volcano_stitch.TP_AAC_ALLOW, 2026-09-01):
# AAC encoding lifts true peak above the PCM master (reported +0.31/+0.57/+0.66 dB
# from three students). An encoded overshoot up to this many dB above TRUE_PEAK is
# accepted and recorded, not re-rendered. Larger overshoot still fails.
TP_AAC_ALLOW = 0.5
# 2026-10-23 report: master −1.73 dBTP → AAC −0.79 (+0.94 dB lift, more than the allowance above). Two causes:
# ① master() limited sample peaks only (alimiter), so the PCM true peak was not actually held at its −1.8 ceiling
#   (real narration + effect hits: −1.17..−1.56 dBTP); ② the encoder lifts the peak by an amount that depends on the
#   material and on the ffmpeg build (same PCM: +0.1 dB on one machine, +1.7 dB on another — docs/solutions/integration-issues/longform-aac-truepeak-measured-correction-2026-10-23.md),
#   so no fixed PCM headroom is right. Hence the limiter works on true peak (true_peak_limiter), and the delivery encode
#   is measured: master_for_delivery() encodes once and, only when the encoded true peak is above TRUE_PEAK, re-masters
#   once with the true-peak ceiling set from the lift it just measured, minus this margin. Still over after that one
#   correction → verify() fails as before (no loop, 6-00).
AAC_CORRECTION_MARGIN = 0.2
# The delivery codec, one place: the pre-picture check and the final assemble must encode the same way.
DELIVERY_AAC = ['-c:a','aac','-b:a','192k']
MAX_UTTERANCE_GAIN = 24.0

# One insertion-point test for the planner and the editor (6-00: the planner and sentence_pauses each carried
# their own copy of these thresholds). Conservative: rejects quiet syllable tails, breaths and any waveform step.
QUIET_RMS = 10**(-48/20)
QUIET_PEAK = 10**(-40/20)
QUIET_EDGE = 64/32768

def _quiet_at(pcm, at, guard):
    """pcm is float (-1..1). True when the ±guard window around sample `at` is safe to split."""
    import numpy as np
    window = pcm[max(0, at-guard):min(len(pcm), at+guard)]
    if len(window) < guard:
        return None
    rms = float(np.sqrt(np.mean(window*window)))
    edge = pcm[max(0, at-1):min(len(pcm), at+1)]
    ok = rms <= QUIET_RMS and float(np.max(np.abs(window))) <= QUIET_PEAK and float(np.max(np.abs(edge))) <= QUIET_EDGE
    return rms if ok else None


def sentence_pauses(root, source, characters, specification, *, original_source=None, editorial=False, verified=()):
    """Extend reviewed sentence silence without changing a single source sample.

    Timestamps describe the original PCM. Insertions must be in the whitespace
    after sentence punctuation and inside measured quiet audio. This is an
    explicit edit list, never punctuation-based automatic silence insertion.

    verified: (after_character, at_seconds) pairs that plan_sentence_pauses already proved quiet on this same
    PCM in this process. Only the caller passes it (never the plan JSON), so authored or merged entries are
    still tested here, and machine-chosen ones are not tested a second time.
    """
    import copy
    import numpy as np
    from film_editor import digest
    from longform_state import Stages
    original_source = original_source or source
    if (not isinstance(specification, dict)
            or specification.get('source_sha256') != file_digest(original_source)):
        raise ProductionError('pause_source_changed', '호흡 조정의 원본 음성 해시가 다릅니다.', action='review_audio')
    entries = specification.get('entries')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        raise ProductionError('pause_entries', '호흡 조정은 확인한 문장 경계 목록이 필요합니다.', action='review_audio')
    with wave.open(str(source), 'rb') as w:
        rate = w.getframerate()
        if (w.getnchannels(), w.getsampwidth()) != (1, 2) or not 8000 <= rate <= 192000:
            raise ProductionError('pause_pcm', '호흡 조정에는 모노 PCM16 음성이 필요합니다.')
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').copy()
    changes = []
    previous = -1
    used_characters = set()
    checked = {(e[0], e[1]) for e in verified}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProductionError('pause_entries', '호흡 조정 항목 형식이 잘못됐습니다.')
        index, at, extra = entry.get('after_character'), entry.get('at_seconds'), entry.get('add_seconds')
        if (type(index) is not int or not 0 <= index < len(characters)
                or index in used_characters or characters[index]['text'] not in '.!?。！？'
                or not all(type(v) in (int,float) and math.isfinite(v) for v in (at,extra))
                or not .02 <= extra <= (30.3 if editorial else .3)):
            raise ProductionError('pause_entries', '확인한 문장 끝과 20~300ms 추가 시간만 사용할 수 있습니다.', action='review_audio')
        following = index + 1
        while following < len(characters) and characters[following]['text'].isspace():
            following += 1
        tail=entry.get('terminal_tail') is True
        is_tail=tail and following==len(characters) and abs(at-len(pcm)/rate)<1/rate
        if (not is_tail and (tail or following == index + 1 or following >= len(characters)
                or not characters[index]['end'] <= at <= characters[following]['start'])):
            raise ProductionError('pause_not_sentence_gap', '호흡 삽입점이 문장 사이 공백 밖입니다.', action='review_audio')
        pos, count = round(at*rate), round(extra*rate)
        guard = max(1, round(.02*rate))
        if pos <= previous or pos-guard < 0 or (not is_tail and pos+guard >= len(pcm)):
            raise ProductionError('pause_order', '호흡 삽입점 순서/범위가 잘못됐습니다.', action='review_audio')
        # Conservative guard: includes quiet syllable tails and breaths instead
        # of trusting alignment timestamps alone. No automatic gate or fading.
        if ((index, at) not in checked
                and _quiet_at(pcm[max(0,pos-guard):pos+guard+1].astype(float)/32768, min(pos, guard), guard) is None):
            raise ProductionError('pause_not_quiet', '삽입점에 발화·여운 또는 파형 단절 가능성이 있습니다.', action='review_audio')
        changes.append({'after_character':index,'source_sample':pos,'added_samples':count,
                        'at_seconds':pos/rate,'add_seconds':count/rate,'terminal_tail':is_tail,
                        **({'editorial':True} if entry.get('editorial') else {})})
        previous = pos
        used_characters.add(index)
    # changes are strictly increasing in at_seconds (pause_order) → prefix sums + bisect, one pass (6-00 ④).
    from bisect import bisect_right
    marks = [x['at_seconds'] for x in changes]
    added = [0.0]
    for x in changes:
        added.append(added[-1] + x['add_seconds'])
    adjusted = copy.deepcopy(characters)
    for char in adjusted:
        for key in ('start','end'):
            old = char[key]
            char[key] = old + added[bisect_right(marks, old)]
    def produce(folder):
        parts=[];cursor=0
        for change in changes:
            pos=change['source_sample']
            parts.extend([pcm[cursor:pos], np.zeros(change['added_samples'],dtype='<i2')])
            cursor=pos
        parts.append(pcm[cursor:])
        joined=np.concatenate(parts)
        output=folder/'narration-paused.wav'
        with wave.open(str(output),'wb') as w:
            w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(joined.astype('<i2').tobytes())
        record={'source_sha256':file_digest(original_source),'prepared_sha256':file_digest(source),
                'output_sha256':file_digest(output),'sample_rate':rate,'original_samples':len(pcm),
                'output_samples':len(joined),'changes':changes,'characters':adjusted,
                'speed_changed':False,'source_samples_preserved':True,'direct_listening':False,
                'skipped_no_quiet_point':specification.get('skipped',[])}
        save(folder/'sentence-pauses.json',record)
        return {'path':str(output),'characters':adjusted,'timing_adjustments':changes,
                'report':str(folder/'sentence-pauses.json')},[output,folder/'sentence-pauses.json']
    import inspect
    return Stages(root).run('sentence-pauses',
        {'code':digest(inspect.getsource(sentence_pauses)),'specification':specification,'characters':characters,'editorial':editorial},
        [source,original_source],produce)


def merge_editorial_pauses(ordinary, editorial, source):
    """Add explicitly authored listening time; the approved breath stays separate."""
    import copy
    if not editorial:return ordinary
    if (not isinstance(editorial,dict) or editorial.get('source_sha256')!=file_digest(source)
            or not isinstance(editorial.get('reason'),str) or not editorial['reason'].strip()
            or not isinstance(editorial.get('reference'),str) or not editorial['reference'].strip()):
        raise ProductionError('editorial_pause_contract','원음 청취 쉼에는 원본 해시·사유·참고 구간이 필요합니다.',action='edit_plan')
    entries=editorial.get('entries')
    if not isinstance(entries,list) or not 1<=len(entries)<=10:
        raise ProductionError('editorial_pause_contract','원음 청취 쉼은 블록별 1~10개입니다.')
    result=copy.deepcopy(ordinary or {'source_sha256':file_digest(source),'entries':[]})
    if result.get('source_sha256')!=file_digest(source):
        raise ProductionError('pause_source_changed','호흡과 청취 쉼의 원본이 다릅니다.')
    used=set()
    for entry in entries:
        if (not isinstance(entry,dict) or type(entry.get('after_character')) is not int
                or type(entry.get('add_seconds')) not in (int,float)
                or not math.isfinite(entry['add_seconds']) or not .1<=entry['add_seconds']<=30
                or type(entry.get('at_seconds')) not in (int,float)
                or not math.isfinite(entry['at_seconds']) or entry['at_seconds']<0
                or entry['after_character'] in used):
            raise ProductionError('editorial_pause_contract','청취 쉼 항목에는 중복 없는 문장 경계와 0.1~30초가 필요합니다.')
        used.add(entry['after_character'])
        previous=next((e for e in result['entries'] if e['after_character']==entry['after_character']),None)
        if previous:
            if abs(previous['at_seconds']-entry['at_seconds'])>1e-7 or previous.get('terminal_tail',False)!=entry.get('terminal_tail',False):
                raise ProductionError('editorial_pause_position','같은 문장의 호흡과 청취 쉼은 같은 안전한 삽입점을 사용해야 합니다.')
            previous['add_seconds']+=entry['add_seconds'];previous['editorial']=True
        else:result['entries'].append({**entry,'editorial':True})
    result['entries'].sort(key=lambda e:e['at_seconds'])
    return result

def plan_sentence_pauses(source,characters,*,original_source=None,extra=.3):
    """Resolve the approved extra silence using alignment AND actual quiet PCM.

    No deletion, silence removal, paid retries, or insertion into spoken tails.
    A clip-final sentence receives the same extra time before the next clip.

    A sentence gap without a provably safe point (breath, room noise, or a gap shorter than the guards —
    measured on this Mac's real Typecast output: 5 of 524 sentence boundaries, i.e. a 15-minute script
    almost always has one) gets NO added time: its paid PCM stays exactly as delivered and the skip is
    recorded in `skipped`. 2026-10-14: this used to block the whole job (sentence_gap_review_required
    63회/24h), but the narration is cached by receipt, so rerunning hit the same sentence forever — the
    only exits were rewriting the script (a new paid TTS) or nothing.
    """
    import numpy as np
    with wave.open(str(source)) as w:
        rate=w.getframerate()
        if w.getnchannels()!=1 or w.getsampwidth()!=2:
            raise ProductionError('pause_pcm','호흡 검사에는 모노 PCM16 음성이 필요합니다.')
        pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
    if not .02<=extra<=.3:raise ProductionError('pause_entries','호흡 추가 시간은 20~300ms입니다.')
    entries=[];skipped=[];guard=round(.02*rate)
    for i,char in enumerate(characters):
        if char['text'] not in '.!?。！？':continue
        following=i+1
        while following<len(characters) and characters[following]['text'].isspace():following+=1
        tail=following==len(characters)
        if not tail and following==i+1:continue  # e.g. decimal points, not sentence gaps
        if tail:
            points=[len(pcm)]
        else:
            lo=round(char['end']*rate)+guard;hi=round(characters[following]['start']*rate)-guard
            points=range(max(guard,lo),min(len(pcm)-guard,hi)+1,max(1,round(.005*rate)))
        candidates=[(q,at) for at in points for q in (_quiet_at(pcm,at,guard),) if q is not None]
        if not candidates:
            skipped.append({'after_character':i,'terminal_tail':tail,'reason':'no_quiet_point'})
            continue
        _,at=min(candidates)
        entries.append({'after_character':i,'at_seconds':at/rate,'add_seconds':extra,**({'terminal_tail':True} if tail else {})})
    if not entries:return None
    spec={'source_sha256':file_digest(original_source or source),'reason':'사용자 승인: 필재 1.05 / 문장 사이 원본 대비 300ms 추가; 파형 검증','entries':entries}
    if skipped:spec['skipped']=skipped
    return spec

def measure(root, path, label='loudness', filters=None):
    norm = 'loudnorm=I=-16:TP=-2:LRA=7:print_format=json'
    command(root, ['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-af',
                  (filters + ',' if filters else '') + norm, '-f', 'null', '-'], label, timeout=1800)
    log = (Path(root) / 'logs' / (label + '.log')).read_text(encoding='utf-8', errors='replace')
    stats = json.loads(re.findall(r'\{[^{}]+\}', log)[-1])
    if not all(math.isfinite(float(stats[k])) for k in ('input_i','input_tp','input_lra','input_thresh','target_offset')):
        raise ProductionError('audio_not_measurable', '음성에서 유효한 음량을 측정할 수 없습니다. 무음/손상 여부를 확인하세요.')
    return stats

def tail_clicks(samples, rate=48000):
    """Conservative QC candidates, not a claim that every transient is non-speech."""
    import numpy as np
    x = np.asarray(samples, dtype=float)
    if len(x) < rate // 2:
        return []
    first = max(0, len(x)-int(.15*rate))
    loud = np.flatnonzero(np.abs(x[first:]) > .02)
    if not len(loud):
        return []
    a,b = first+int(loud[0]),first+int(loud[-1])+1
    if b-a > .06*rate or len(x)-b < .015*rate:
        return []
    before = x[a-int(.15*rate):a-int(.015*rate)]
    after = x[b+int(.005*rate):]
    if (not len(before) or not len(after) or np.max(np.abs(before))>.008
            or np.sqrt(np.mean(before**2))>.002 or np.max(np.abs(after))>.008):
        return []
    return [{'start_seconds':a/rate,'end_seconds':b/rate,
             'peak':float(np.max(np.abs(x[a:b]))),'preceding_rms':float(np.sqrt(np.mean(before**2)))}]

def prepare_voice(root, source, repair=None):
    """Repair only a hash-bound non-speech tail (authored audio_repair, else the automatic one below); never rewrite the paid source."""
    import numpy as np
    root=Path(root)
    with wave.open(str(source),'rb') as w:
        rate=w.getframerate()
        if (w.getnchannels(),w.getsampwidth())!=(1,2) or not 8000<=rate<=192000:
            raise ProductionError('unsupported_voice_pcm','음성은 유효한 표본율의 16bit/mono PCM이어야 합니다.')
        pcm=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').copy()
    x=pcm.astype(float)/32768.;candidates=tail_clicks(x,rate);sha=file_digest(source)
    report={'source_sha256':sha,'samples':len(pcm),'sample_rate':rate,'tail_click_candidates':candidates,'repair':repair}
    save(root/'voice-quality.json',report)
    if repair is None:
        if not candidates:return Path(source)
        # 2026-10-17 신고 #128(2명): one block at a time, every run stopped here and asked the author for a «reviewed» tail
        # start and a reason — values this code already decides. tail_clicks only reports a burst that is isolated by
        # its own measurement (≤0.06 s inside the last 0.15 s, the 0.135 s before it peak ≤0.008 · rms ≤0.002, silence
        # after), so the repair below is bound to this exact file hash and starts 0.025 s before the burst: the whole
        # 0.01 s fade then lies inside that measured quiet span (the fade check below still guards it), and the range
        # rule (len−0.25 … burst−0.015) holds because the burst starts within the last 0.15 s. The paid source is never
        # rewritten; voice-quality.json records the repair as automatic, and an authored audio_repair still wins.
        repair={'source_sha256':sha,'tail_start_seconds':round(candidates[0]['start_seconds']-.025,6),'automatic':True,
                'reason':'자동: 고립 꼬리 충격음(끝 0.15초 안 0.06초 이하 · 앞 0.135초 정숙 · 뒤 무음) — 원본 해시 고정, 길이 유지'}
        report['repair']=repair
    if (not isinstance(repair,dict) or repair.get('source_sha256')!=sha or not candidates
            or not isinstance(repair.get('reason'),str) or not repair['reason'].strip()):
        raise ProductionError('invalid_audio_repair','음성 보정의 원본 해시/검토 사유/잡음 후보가 일치하지 않습니다.')
    start=repair.get('tail_start_seconds')
    if (type(start) not in (int,float) or not math.isfinite(start)
            or not len(x)/rate-.25<=start<=candidates[0]['start_seconds']-.015):
        raise ProductionError('invalid_audio_repair','보정 시작점이 확인된 꼬리 잡음의 정숙 구간 밖입니다.')
    a=round(start*rate);fade=round(rate*.01)
    if np.max(np.abs(x[max(0,a-fade):a+fade]))>.008:
        raise ProductionError('invalid_audio_repair','발화일 수 있는 구간을 자동 삭제하지 않습니다.')
    pcm[a:a+fade]=np.rint(pcm[a:a+fade]*(.5+.5*np.cos(np.linspace(0,math.pi,fade)))).astype('<i2')
    pcm[a+fade:]=0
    destination=root/'voice-clean.wav'
    with wave.open(str(destination),'wb') as w:
        w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(pcm.tobytes())
    report['output_sha256']=file_digest(destination)
    report['remaining_candidates']=tail_clicks(pcm.astype(float)/32768.,rate)
    save(root/'voice-quality.json',report)
    return destination

def level_voice(root, source, destination, repair=None):
    """Match utterance loudness; control brief peaks without quieting all speech.

    Re-render only local PCM from the untouched source. Limiter lookahead is
    delay-compensated, and exact duration remains a hard gate.
    """
    root = Path(root); destination = Path(destination)
    original_source=source
    source=prepare_voice(root,source,repair)
    stats = measure(root, source, 'voice-before')
    # Limiting constant gain by the single loudest peak left an actual Typecast
    # utterance at -23.68 LUFS. Keep its body at -20 and limit only those peaks.
    gain = max(-MAX_UTTERANCE_GAIN, min(MAX_UTTERANCE_GAIN, -20. - float(stats['input_i'])))
    attempts=[]
    for attempt in range(3):
        limited=float(stats['input_tp'])+gain>-3.
        filters=f'volume={gain:.6f}dB'
        if limited:filters+=',alimiter=limit=0.707945784:level=false:attack=5:release=100:latency=true'
        command(root, ['ffmpeg','-y','-v','error','-i',source,'-af',filters,
                      '-ar','48000','-ac','1','-c:a','pcm_s16le',destination], f'voice-level-{attempt}')
        after=measure(root,destination,f'voice-after-{attempt}')
        attempts.append({'gain_db':gain,'peak_limited':limited,'filter':filters,'measurement':after})
        if abs(float(after['input_i'])+20.)<=.5:break
        adjusted=max(-MAX_UTTERANCE_GAIN,min(MAX_UTTERANCE_GAIN,gain-20.-float(after['input_i'])))
        if abs(adjusted-gain)<.01:break
        gain=adjusted
    with wave.open(str(source),'rb') as a, wave.open(str(destination),'rb') as b:
        expected=round(a.getnframes()*48000/a.getframerate())
        if b.getframerate()!=48000 or abs(expected-b.getnframes())>1:
            raise ProductionError('audio_timing_changed','음량 처리 중 음성 길이가 달라졌습니다.')
    record = {'source_sha256':file_digest(original_source),'prepared_sha256':file_digest(source),'output_sha256':file_digest(destination),
              'gain_db':attempts[-1]['gain_db'],'before':stats,'after':after,'attempts':attempts}
    save(root/'voice-level.json',record)
    if abs(float(after['input_i'])+20.)>1. or float(after['input_tp'])>-.5:
        raise ProductionError('audio_level_out_of_spec', '문장 음량을 안전하게 균일화하지 못했습니다. 원본과 측정 기록을 보존하고 출력을 중단합니다.')
    return record

def true_peak_limiter(ceiling_db):
    """Peak limiter on true peak: alimiter only sees samples (a −1.8 dB sample ceiling left real masters near
    −1.0 dBTP). At 4× rate — the oversampling ITU-R BS.1770 true peak uses — it bounds the peaks a meter and a
    decoder reconstruct; 48 kHz is restored afterwards."""
    return (f'aresample=192000,alimiter=limit={10**(ceiling_db/20):.9f}:level=false:attack=5:release=100:latency=true,'
            'aresample=48000')

def master(root, source, destination, ceiling=None):
    """The existing editor's measured two-pass algorithm, with gentle speech compression.

    `ceiling` (dBTP) is given only by master_for_delivery's one measured AAC correction: the same master, then every
    loudness pass runs the true-peak limiter at that ceiling, with the gain scaled by what the previous pass actually
    gained (the limiter takes some loudness back)."""
    root = Path(root)
    # Preserve the measured channel layout; downmixing after loudnorm changes LUFS.
    compressor = 'acompressor=threshold=0.1:ratio=2:attack=20:release=250:knee=2.828:makeup=1:detection=rms'
    stats = measure(root, source, 'master-analysis', compressor)
    norm = 'loudnorm=I=-16:TP=-2:LRA=7:linear=true:' + ':'.join(
        f'{key}={stats[value]}' for key,value in (
            ('measured_I','input_i'),('measured_TP','input_tp'),('measured_LRA','input_lra'),
            ('measured_thresh','input_thresh'),('offset','target_offset')))
    command(root, ['ffmpeg','-y','-v','error','-i',source,'-af',compressor+','+norm,
                  '-ar','48000','-c:a','pcm_s24le',destination], 'master-render',timeout=1800)
    # loudnorm's two-pass request is not proof of its output: a real 11-second
    # utterance measured -16.22 after it. Close small residual errors using the
    # measured PCM; constrain gain with a latency-compensated limiter when
    # peaks leave too little headroom. The encoded output still must pass.
    # Never change the provider original or weaken the final AAC acceptance gate.
    destination=Path(destination);after=measure(root,destination,'master-output-0');feedback=[];yield_=1.
    for attempt in range(2 if ceiling is None else 3):
        delta=TARGET-float(after['input_i'])
        if ceiling is None:
            if abs(delta)<=.08:break
            limited=float(after['input_tp'])+delta>TRUE_PEAK-.2;limiter=true_peak_limiter(TRUE_PEAK-.3);gain=delta
        else:
            if abs(delta)<=.08 and float(after['input_tp'])<=ceiling+.1:break
            limited=True;limiter=true_peak_limiter(ceiling);gain=max(-3.,min(3.,delta/yield_))
        if abs(delta)>1:break
        correction=f'volume={gain:.6f}dB'+(','+limiter if limited else '')
        adjusted=destination.with_name(destination.stem+f'-feedback-{attempt}.wav')
        command(root,['ffmpeg','-y','-v','error','-i',destination,'-af',correction,
                      '-ar','48000','-c:a','pcm_s24le',adjusted],f'master-feedback-{attempt}')
        before=after;after=measure(root,adjusted,f'master-output-{attempt+1}')
        destination.replace(destination.with_name(destination.stem+f'-before-feedback-{attempt}.wav'))
        adjusted.replace(destination)
        gained=float(after['input_i'])-float(before['input_i'])
        if abs(gain)>.05 and 0<gained/gain:yield_=max(.25,min(1.,gained/gain))
        feedback.append({'gain_db':gain,'needed_db':delta,'peak_limited':limited,'filter':correction,'before':before,'after':after})
    save(root/'master-analysis.json',{'input':stats,'target_lufs':TARGET,'true_peak_target':-2.,'true_peak_ceiling':ceiling,
                                      'filter':compressor+','+norm,'measured_output':after,'feedback':feedback})
    return after

def master_for_delivery(root, source, destination, preview):
    """Master, encode the delivery AAC and measure it; one measured correction when AAC lifted the peak over TRUE_PEAK.

    The correction re-masters from the same mix with a true-peak ceiling set from the measured AAC lift (+margin) — it
    does not change the encoder settings or touch any paid voice. Returns verify()'s report — still the gate."""
    root=Path(root);destination=Path(destination);preview=Path(preview)
    pcm=master(root,source,destination)
    command(root,['ffmpeg','-y','-v','error','-i',destination,*DELIVERY_AAC,preview],'audio-preview',timeout=1800)
    encoded=measure(root,preview,'encoded-loudness-first')
    over=float(encoded['input_tp'])-TRUE_PEAK
    record={'true_peak_ceiling_dbtp':TRUE_PEAK,'first':{'pcm':pcm,'encoded':encoded},'corrected':None}
    if over>0:
        # Ceiling that lands the encode at TRUE_PEAK − margin given the lift this encoder just showed on this mix.
        lift=float(encoded['input_tp'])-float(pcm['input_tp'])
        corrected=round(min(TRUE_PEAK-.3,TRUE_PEAK-lift-AAC_CORRECTION_MARGIN),3)
        destination.replace(destination.with_name(destination.stem+'-before-aac-correction.wav'))
        preview.replace(preview.with_name(preview.stem+'-before-aac-correction'+preview.suffix))
        pcm=master(root,source,destination,corrected)
        command(root,['ffmpeg','-y','-v','error','-i',destination,*DELIVERY_AAC,preview],'audio-preview-corrected',timeout=1800)
        record['corrected']={'pcm_ceiling':corrected,'encoded_overshoot_db':round(over,3),'aac_lift_db':round(lift,3),'pcm':pcm}
    save(root/'aac-peak-correction.json',record)
    # The uncorrected preview was just measured: hand that measurement to the gate instead of measuring it again.
    return verify(root,preview,measured=None if record['corrected'] else encoded)

def verify(root, video, measured=None):
    stats = measured or measure(root, video, 'encoded-loudness')
    over = float(stats['input_tp'])-TRUE_PEAK
    ok = abs(float(stats['input_i'])-TARGET)<=TOLERANCE and over<=TP_AAC_ALLOW+1e-9
    report = {'passed':ok,'target_lufs':TARGET,'tolerance_lu':TOLERANCE,
              'true_peak_ceiling_dbtp':TRUE_PEAK,'aac_true_peak_allowance_db':TP_AAC_ALLOW,
              'aac_true_peak_overshoot_db':round(max(0.,over),3),
              'encoded_measurement':stats,'sha256':file_digest(video)}
    save(Path(root)/'audio-verification.json',report)
    if not ok:
        raise ProductionError('audio_master_out_of_spec',f"최종 음량 검사 실패: {stats['input_i']} LUFS / {stats['input_tp']} dBTP. 자동 통과시키지 않습니다.")
    return report


def mix_effects(root, narration, destination, voices, blocks, assets):
    """Mix hash-bound, explicitly scheduled effects before final loudness mastering.

    No inference from cuts, no random selection, and no external requests. A cue
    outside its authored shot/tail span fails rather than being clipped or repeated.
    """
    import numpy as np
    root=Path(root)
    with wave.open(str(narration),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,48000):
            raise ProductionError('sfx_pcm','믹스 입력은 48kHz 16bit mono여야 합니다.')
        mix=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)/32768
    cursor=0;report=[];decoded={}
    for block_index,(block,voice) in enumerate(zip(blocks,voices)):
        shot_samples=voice['frames']*800
        for cue in block.get('sfx',[]):
            asset=assets[cue['asset']];source=Path(asset['path'])
            if not source.is_file() or file_digest(source)!=asset['sha256']:
                raise ProductionError('sfx_source_changed','효과음 원본/해시가 다릅니다: '+cue['asset'],action='repair_media')
            if cue['asset'] not in decoded:
                # Float sources and resampling can exceed 0 dBFS before gain.
                # Integer decoding would clip them irreversibly even when the
                # explicitly authored gain makes the mixed effect safely quiet.
                out=root/('effect-'+str(len(decoded))+'.f32')
                command(root,['ffmpeg','-y','-v','error','-i',source,'-vn','-ar','48000','-ac','1','-f','f32le',out],out.stem)
                samples=np.frombuffer(out.read_bytes(),dtype='<f4').astype(np.float64)
                if not np.all(np.isfinite(samples)):
                    raise ProductionError('sfx_nonfinite','효과음에 유효하지 않은 파형 값이 있습니다.',action='repair_media')
                decoded[cue['asset']]=samples
            samples=decoded[cue['asset']].copy();start=round(cue['at']*48000)
            allowed_samples=shot_samples
            tail=cue.get('tail_into_next')
            if tail is not None:
                if block_index+1>=len(blocks) or tail!=blocks[block_index+1]['id']:
                    raise ProductionError('sfx_tail_target','효과음 여운은 명시한 바로 다음 장면으로만 연결할 수 있습니다.',action='edit_plan')
                allowed_samples+=voices[block_index+1]['frames']*800
            if start<0 or start>=shot_samples or start+len(samples)>allowed_samples or cursor+start+len(samples)>len(mix):
                raise ProductionError('sfx_outside_shot','효과음이 장면 경계를 넘습니다: '+block['id'],action='edit_plan')
            if not len(samples) or np.max(np.abs(samples))<1e-6:
                raise ProductionError('sfx_silent','효과음 파일이 비었거나 무음입니다.')
            # 5ms endpoint ramps prevent waveform discontinuities at splice points.
            n=min(240,len(samples)//2)
            if n:
                samples[:n]*=np.linspace(0,1,n);samples[-n:]*=np.linspace(1,0,n)
            gain=10**(cue['gain_db']/20);mix[cursor+start:cursor+start+len(samples)]+=samples*gain
            report.append({'block':block['id'],'asset':cue['asset'],'source_sha256':asset['sha256'],
                           'sample_start':cursor+start,'sample_count':len(samples),'gain_db':cue['gain_db'],'tail_into_next':tail,
                           'tail_samples':max(0,start+len(samples)-shot_samples),
                           'reason':cue['reason'],'reference':cue['reference']})
        cursor+=shot_samples
    peak=float(np.max(np.abs(mix))) if len(mix) else 0
    # Floating-point output preserves peaks for the subsequent loudness limiter;
    # an int16 intermediate would irreversibly clip before mastering.
    raw=root/'mix-float.f32';raw.write_bytes(mix.astype('<f4').tobytes())
    command(root,['ffmpeg','-y','-v','error','-f','f32le','-ar','48000','-ac','1','-i',raw,
                  '-c:a','pcm_f32le',destination],'sfx-mix')
    raw.unlink()
    save(root/'sfx-mix.json',{'schema':'geumbit-sfx-v1','events':report,'premaster_peak':peak,
                            'samples':len(mix),'mastering':'applied after this mix'})
    return Path(destination)



def sum_pcm_windows(destination, samples, windows):
    """Sample-addressed float stereo sum; no stream-EOF driven amix truncation.

    Fixed-size chunks bound RAM. Close every mapping before FFmpeg opens it,
    including on Windows. Missing decoded samples are errors, never zero fill.
    """
    import numpy as np
    for source,start,count in windows:
        if not 0<=start<samples or start+count>samples or Path(source).stat().st_size!=count*8:
            raise ProductionError('music_pcm_length','음악 PCM 길이가 실제 배정과 다릅니다. 부족한 음원을 무음으로 채우지 않습니다.')
    target=np.memmap(destination,dtype='<f4',mode='w+',shape=(samples,2))
    try:
        target[:]=0
        for source,start,count in windows:
            data=np.memmap(source,dtype='<f4',mode='r',shape=(count,2))
            try:
                for a in range(0,count,480000):
                    b=min(a+480000,count);chunk=data[a:b]
                    if not np.isfinite(chunk).all():raise ProductionError('music_pcm_invalid','음악 PCM에 유효하지 않은 값이 있습니다.')
                    target[start+a:start+b]+=chunk
                    del chunk
            finally:data._mmap.close()
        target.flush()
    finally:target._mmap.close()


def duck_pcm(source, key, destination, samples):
    """Deterministic 10ms RMS detector with a continuous gain envelope.

    Unlike stream-driven sidechains, control EOF means silence, not program EOF.
    Only the control signal may be absent; the audible bed must have every sample.
    """
    import numpy as np
    if Path(source).stat().st_size!=samples*8 or Path(key).stat().st_size%8:
        raise ProductionError('music_pcm_length','덕킹 입력 PCM 길이가 잘못됐습니다.')
    count=Path(key).stat().st_size//8
    if not count:raise ProductionError('music_pcm_length','덕킹 제어 신호가 비었습니다.')
    bed=np.memmap(source,dtype='<f4',mode='r',shape=(samples,2))
    control=np.memmap(key,dtype='<f4',mode='r',shape=(count,2))
    output=np.memmap(destination,dtype='<f4',mode='w+',shape=(samples,2))
    gain=1.
    try:
        for a in range(0,samples,480):
            b=min(a+480,samples);c=min(b,count)
            if a<c:
                signal=control[a:c]
                if not np.isfinite(signal).all():raise ProductionError('music_pcm_invalid','덕킹 신호에 유효하지 않은 값이 있습니다.')
                rms=float(np.sqrt(np.sum(signal.astype('float64')**2)/((b-a)*2)))
                del signal
            else:rms=0.
            desired=(rms/.03)**(1/8-1) if rms>.03 else 1.
            alpha=math.exp(-(b-a)/48000/(.02 if desired<gain else .25))
            end=alpha*gain+(1-alpha)*desired
            envelope=np.linspace(gain,end,b-a+1,dtype='float64')[1:]
            chunk=bed[a:b]
            if not np.isfinite(chunk).all():raise ProductionError('music_pcm_invalid','덕킹 대상에 유효하지 않은 값이 있습니다.')
            output[a:b]=chunk*envelope[:,None];del chunk
            gain=end
        output.flush()
    finally:
        output._mmap.close();control._mmap.close();bed._mmap.close()

def mix_music(root, narration, destination, music, assets, sidechain=None, sidechain_role='narration only'):
    """Hash-bound music with narration-driven ducking, before the final LUFS master."""
    from film_editor import probe
    if 'segments' in music:return mix_music_segments(root,narration,destination,music,assets,sidechain,sidechain_role)
    root=Path(root);asset=assets[music['asset']];source=Path(asset['path'])
    if not source.is_file() or file_digest(source)!=asset['sha256']:
        raise ProductionError('music_source_changed','배경음악 원본/해시가 다릅니다.',action='repair_media')
    voice_info=probe(root,narration);seconds=float(voice_info['format']['duration']);start=music['in']
    source_info=probe(root,source)
    if float(source_info['format']['duration'])+1e-5<start+seconds:
        raise ProductionError('music_too_short','선택한 배경음악 구간이 영상보다 짧습니다. 임의로 반복하지 않습니다.',action='edit_plan')
    fin=music['fade_in'];fout=music['fade_out']
    if fin+fout>seconds:raise ProductionError('music_fade_overlap','배경음악 페이드가 서로 겹칩니다.',action='edit_plan')
    fades=(f',afade=t=in:st=0:d={fin}' if fin else '')+(f',afade=t=out:st={seconds-fout}:d={fout}' if fout else '')
    samples=round(seconds*48000)
    dry=root/'music-dry.f32';bed=root/'music-bed.f32';key=root/'music-key.f32';ducked=root/'music-ducked.f32'
    for source_file,output,label in [(narration,dry,'music-dry-decode'),(sidechain or narration,key,'music-key-decode')]:
        command(root,['ffmpeg','-y','-v','error','-i',source_file,'-ar','48000','-ac','2','-f','f32le',output],label)
    filters=(f'atrim=start={start}:duration={seconds},asetpts=PTS-STARTPTS,aresample=48000,'
             f'volume={music["gain_db"]}dB{fades}')
    command(root,['ffmpeg','-y','-v','error','-i',source,'-af',filters,'-ar','48000','-ac','2','-f','f32le',bed],'music-bed-decode',timeout=1800)
    duck_pcm(bed,key,ducked,samples)
    pcm=root/'music-summed.f32'
    sum_pcm_windows(pcm,samples,[(dry,0,samples),(ducked,0,samples)])
    command(root,['ffmpeg','-y','-v','error','-f','f32le','-ar','48000','-ac','2','-i',pcm,'-c:a','pcm_f32le',destination],'music-mix',timeout=1800)
    actual=float(probe(root,destination)['format']['duration'])
    if abs(actual-seconds)>1/48000+1e-6:raise ProductionError('music_timing_changed','배경음악 믹싱 뒤 타임라인 길이가 변했습니다.')
    save(root/'music-mix.json',{'schema':'geumbit-music-v1','asset':music['asset'],'source_sha256':asset['sha256'],
         'source_in':start,'duration':seconds,'gain_db':music['gain_db'],'fade_in':fin,'fade_out':fout,
         'ducking':{'key':sidechain_role,'threshold':.03,'ratio':8,'attack_ms':20,'release_ms':250,'detector':'10ms RMS; continuous gain; sample-addressed PCM'},
         'reason':music['reason'],'reference':music['reference'],'license':asset['license'],
         'looped':False,'mastering':'applied after music and effects'})
    return Path(destination)


def mix_music_segments(root, narration, destination, music, assets, sidechain=None, sidechain_role='narration only'):
    """Place source excerpts at sample boundaries; duck the combined bed only once."""
    from film_editor import probe
    from longform_contract import validate_music
    validate_music(music,assets)
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    seconds=float(probe(root,narration)['format']['duration']);samples=round(seconds*48000)
    windows=[];reports=[]
    for i,cue in enumerate(music['segments']):
        asset=assets[cue['asset']];source=Path(asset['path'])
        if not source.is_file() or file_digest(source)!=asset['sha256']:
            raise ProductionError('music_source_changed','배경음악 원본/해시가 다릅니다.',action='repair_media')
        start=round(cue['start']*48000);end=round(cue['end']*48000);offset=round(cue['in']*48000)
        if end>samples or end<=start:
            raise ProductionError('music_outside_timeline','배경음악 구간이 실제 영상 길이를 벗어납니다.',action='edit_plan')
        if float(probe(root,source)['format']['duration'])*48000+0.5<offset+end-start:
            raise ProductionError('music_too_short','음악 원본 구간이 부족합니다. 임의 반복하지 않습니다.',action='edit_plan')
        duration=(end-start)/48000;decoded=root/f'music-segment-{i}.f32'
        filters=(f'aresample=48000,atrim=start_sample={offset}:end_sample={offset+end-start},'
                 f'asetpts=PTS-STARTPTS,volume={cue["gain_db"]}dB,'
                 f'afade=t=in:st=0:d={cue["fade_in"]},afade=t=out:st={duration-cue["fade_out"]}:d={cue["fade_out"]}')
        command(root,['ffmpeg','-y','-v','error','-i',source,'-af',filters,'-ar','48000','-ac','2','-f','f32le',decoded],f'music-segment-{i}',timeout=1800)
        windows.append((decoded,start,end-start))
        reports.append({**cue,'source_sha256':asset['sha256'],'sample_start':start,'sample_end':end,'source_sample_start':offset,'license':asset['license']})
    pcm=root/'music-sequence.f32';sum_pcm_windows(pcm,samples,windows)
    bed=root/'music-sequence.wav'
    command(root,['ffmpeg','-y','-v','error','-f','f32le','-ar','48000','-ac','2','-i',pcm,'-c:a','pcm_f32le',bed],'music-sequence',timeout=1800)
    internal={'asset':'sequence','in':0,'gain_db':0,'fade_in':0,'fade_out':0,'reason':'validated timeline segments','reference':'music.segments'}
    mix_music(root,narration,destination,internal,{'sequence':{'path':str(bed),'sha256':file_digest(bed),'license':'see segments'}},sidechain,sidechain_role)
    save(root/'music-mix.json',{'schema':'geumbit-music-v2','segments':reports,'samples':samples,'looped':False,
         'ducking':{'key':sidechain_role,'threshold':.03,'ratio':8,'attack_ms':20,'release_ms':250,'detector':'10ms RMS; continuous gain; sample-addressed PCM'},
         'mastering':'applied after music and effects'})
    return Path(destination)
