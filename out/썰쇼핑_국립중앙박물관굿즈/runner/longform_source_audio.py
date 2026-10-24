"""Explicit original-clip audio roles; never discard or mute narration implicitly."""
from pathlib import Path
import math, wave
from film_editor import command, file_digest, probe
from longform_state import ProductionError, save

RATE=48000

def fail(code, message):
    raise ProductionError(code,message,action='edit_plan')

def validate(blocks, media):
    for block in blocks:
        cues=block.get('source_audio',[])
        if not isinstance(cues,list) or len(cues)>32:fail('source_audio_contract','원음 큐는 블록별 최대32개 목록입니다.')
        for cue in cues:
            if not isinstance(cue,dict) or cue.get('media') not in media:fail('source_audio_contract','원음의 등록된 media ID가 필요합니다.')
            if cue.get('mode') not in ('foreground','background','mute'):fail('source_audio_contract','원음 역할은 foreground/background/mute입니다.')
            for key,lo,hi in [('in',0,86400),('out',0,86400),('at',0,2400),('gain_db',-60,6),('fade_in',.005,10),('fade_out',.005,10)]:
                value=cue.get(key)
                if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:fail('source_audio_contract','원음 숫자 범위 오류: '+key)
            if 'gap_after_character' in cue and (type(cue['gap_after_character']) is not int or cue['gap_after_character']<0 or cue['mode']!='foreground'):
                fail('source_audio_contract','청취 쉼 기준은 전면 원음의 문장 끝 인덱스여야 합니다.')
            if 'gap_after_character' in cue:
                entries=(block.get('editorial_pauses') or {}).get('entries',[])
                if not any(e.get('after_character')==cue['gap_after_character'] for e in entries):
                    fail('source_audio_contract','원음에 지정한 청취 쉼이 제작표에 없습니다.')
            duration=cue['out']-cue['in']
            if not 0<duration<=120 or cue['fade_in']+cue['fade_out']>duration:fail('source_audio_contract','원음 구간은 120초 이내, 페이드는 구간 안이어야 합니다.')
            for key in ('reason','reference'):
                if not isinstance(cue.get(key),str) or not cue[key].strip():fail('source_audio_contract','원음 역할 사유와 확인한 참고 구간이 필요합니다.')

def preflight(root, blocks, media):
    """Decode exact audible source windows before paid speech; no optional audio map."""
    validate(blocks,media);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    seen=set()
    for block in blocks:
        for cue in block.get('source_audio',[]):
            if cue['mode']=='mute':continue
            asset=media[cue['media']];source=Path(asset['path']);key=(asset['sha256'],cue['in'],cue['out'])
            if not source.is_file() or file_digest(source)!=asset['sha256']:fail('source_audio_changed','원음 자료 지문이 다릅니다: '+cue['media'])
            if key in seen:continue
            seen.add(key)
            info=probe(root,source)
            if not any(s['codec_type']=='audio' for s in info['streams']):fail('source_audio_missing','선택한 자료에 오디오 스트림이 없습니다: '+cue['media'])
            if float(info['format']['duration'])+1/RATE<cue['out']:fail('source_audio_short','원음 끝이 실제 자료 길이를 넘습니다.')
            command(root,['ffmpeg','-v','error','-xerror','-ss',cue['in'],'-i',source,'-t',cue['out']-cue['in'],'-map','0:a:0','-vn','-f','null','-'],'source-audio-preflight-'+str(len(seen)))

def dependencies(plan):
    ids=sorted({c['media'] for b in plan['blocks'] for c in b.get('source_audio',[]) if c['mode']!='mute'})
    return [plan['media'][mid]['path'] for mid in ids]

def mix(root, mixed, narration, destination, voices, blocks, media):
    """Keep source stereo. Foreground requires actual quiet narration PCM.

    Music key contains narration plus foreground source, never background source
    or effects. Background source is ducked by narration only. Source in/out are
    fixed; no looping, stretching, hidden narration deletion or paid requests.
    """
    import numpy as np
    validate(blocks,media)
    if len(blocks)!=len(voices):fail('source_audio_timing','원음 제작표와 음성 개수가 다릅니다.')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with wave.open(str(narration),'rb') as reader:
        if (reader.getframerate(),reader.getnchannels(),reader.getsampwidth())!=(RATE,1,2):fail('source_audio_pcm','원음 키는 48kHz 16bit mono 나레이션이어야 합니다.')
        length=reader.getnframes();voice=np.frombuffer(reader.readframes(length),'<i2').astype(np.float32)/32768
    from longform_audio import sum_pcm_windows,duck_pcm
    roles={'foreground':[],'background':[]};events=[];cursor=0;windows=[]
    for block,timing in zip(blocks,voices):
        block_samples=timing['frames']*800
        for cue in block.get('source_audio',[]):
            start=cursor+round(cue['at']*RATE);count=round((cue['out']-cue['in'])*RATE)
            if start<cursor or start+count>cursor+block_samples or start+count>length:fail('source_audio_outside_shot','원음이 장면 범위를 넘습니다: '+block['id'])
            if cue['mode']=='foreground':
                if any(start<b and start+count>a for a,b in windows):fail('source_audio_dialogue_overlap','전면 원음끼리 겹칩니다.')
                windows.append((start,start+count))
                # A 20ms RMS gate rejects speech instead of cutting it away.
                samples=voice[start:start+count];padded=np.pad(samples,(0,(-len(samples))%960))
                if np.max(np.sqrt(np.mean(padded.reshape(-1,960)**2,axis=1)))>10**(-45/20):fail('source_audio_narration_overlap','전면 원음 구간에 나레이션이 남아 있습니다. 실제 편집 쉼을 배정하세요: '+block['id'])
            asset=media[cue['media']]
            events.append({**cue,'block':block['id'],'sample_start':start,'sample_count':count,'source_sha256':asset['sha256']})
            if cue['mode']=='mute':continue
            source=Path(asset['path'])
            if not source.is_file() or file_digest(source)!=asset['sha256']:fail('source_audio_changed','원음 자료 지문이 변경됐습니다.')
            index=sum(len(x) for x in roles.values());decoded=root/f'source-audio-{index}.f32'
            offset=round(cue['in']*RATE)
            command(root,['ffmpeg','-y','-v','error','-copyts','-start_at_zero','-i',source,'-map','0:a:0','-vn','-af',f'aresample=48000:first_pts=0,atrim=start_sample={offset}:end_sample={offset+count},asetpts=PTS-STARTPTS','-ac','2','-f','f32le',decoded],'source-audio-decode-'+str(index))
            if decoded.stat().st_size!=count*8:fail('source_audio_short','원음 디코딩 길이가 선택한 구간과 다릅니다. 무음으로 채우지 않습니다.')
            probe_samples=np.fromfile(decoded,dtype='<f4')
            if not np.isfinite(probe_samples).all() or np.max(np.abs(probe_samples))<1e-6:fail('source_audio_silent','원음 구간이 무음이거나 잘못된 PCM입니다.')
            # Gain and short fades affect only this derived PCM, never its source.
            data=np.memmap(decoded,dtype='<f4',mode='r+',shape=(count,2))
            try:
                data*=10**(cue['gain_db']/20)
                fin=min(count,round(cue['fade_in']*RATE));fout=min(count,round(cue['fade_out']*RATE))
                data[:fin]*=np.linspace(0,1,fin)[:,None]
                data[-fout:]*=np.linspace(1,0,fout)[:,None]
                data.flush()
            finally:data._mmap.close()
            roles[cue['mode']].append((decoded,start,count))
        cursor+=block_samples
    foreground=root/'source-foreground.f32';background=root/'source-background.f32'
    sum_pcm_windows(foreground,length,roles['foreground']);sum_pcm_windows(background,length,roles['background'])
    base=root/'source-base.f32';narr=root/'source-narration.f32'
    for source,out,label in [(mixed,base,'source-base-decode'),(narration,narr,'source-key-decode')]:
        command(root,['ffmpeg','-y','-v','error','-i',source,'-ar',RATE,'-ac','2','-f','f32le',out],label,timeout=1800)
    ducked=root/'source-background-ducked.f32';duck_pcm(background,narr,ducked,length)
    final=root/'source-final.f32';control=root/'source-control.f32'
    sum_pcm_windows(final,length,[(base,0,length),(foreground,0,length),(ducked,0,length)])
    sum_pcm_windows(control,length,[(narr,0,length),(foreground,0,length)])
    key=root/'source-dialogue-key.wav'
    for source,out,label in [(final,destination,'source-audio-mix'),(control,key,'source-control-write')]:
        command(root,['ffmpeg','-y','-v','error','-f','f32le','-ar',RATE,'-ac','2','-i',source,'-c:a','pcm_f32le',out],label,timeout=1800)
    save(root/'source-audio-mix.json',{'schema':'geumbit-source-audio-v1','events':events,'samples':length,'narration_unchanged':True,'music_key':'narration + foreground original audio','background_key':'narration only','ducking_detector':'10ms RMS; continuous gain; sample-addressed PCM','exact_reference_compressor_settings':False})
    return Path(destination),key
