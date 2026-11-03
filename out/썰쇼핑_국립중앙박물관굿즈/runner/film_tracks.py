"""Independent authored picture, reaction, source-audio and local sound tracks."""
from copy import deepcopy
from pathlib import Path
import math
import re

def migrate(item):
    import film_editor as E
    import os
    old=Path(item['legacy_workdir']).resolve();root=Path(item['workdir']).resolve()
    if not old.is_dir() or root!=old/'.common-editor':raise ValueError('Migration must preserve the existing folder')
    root.mkdir(exist_ok=True)
    with E.file_lock(root/'migration.lock'):
        payload=item.get('payload') or {};snapshot=root/('legacy-payload-'+E.digest(payload)+'.json')
        if not snapshot.exists():E.atomic_json(snapshot,payload)
        # The stable pointer is itself a saved payload, not an executable plan.
        E.atomic_json(root/'legacy-payload.json',payload)
        files=[]
        for folder,dirs,names in os.walk(old,followlinks=False):
            dirs[:]=[d for d in dirs if d not in ('.common-editor','.git','node_modules','.venv','venv','fonts')]
            for name in names:
                path=Path(folder)/name
                if path.suffix.lower() not in ('.wav','.mp3','.m4a','.json','.srt','.vtt'):continue
                if path.is_symlink():continue
                files.append({'path':str(path),'bytes':path.stat().st_size,'sha256':E.file_digest(path)})
        result={'legacy_workdir':str(old),'reuse_only_narration':True,'inventory_path':str(root/'legacy-inventory.json'),
                'payload_path':str(snapshot),'files':files,'paid_requests':0}
        E.atomic_json(root/'legacy-inventory.json',result)
        return {k:v for k,v in result.items() if k!='files'}

def number(value,label,low=0,high=float('inf')):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('Invalid '+label)
    return value

def frame(value,label,low,high):
    if type(value) is not int:raise ValueError(label+' must be an integer frame')
    return number(value,label,low,high)

def validate(edit,config,duration):
    """Before paid narration: verify local assets and all authored field shapes."""
    music=edit.get('music')
    if music:
        # A continuous music bed (person shorts: the whole soundtrack). The file must exist and
        # carry an audio stream now, not after the picture has been rendered (2026-09-16).
        import subprocess
        path=music.get('path') if isinstance(music,dict) else music
        if not isinstance(path,str) or not Path(path).expanduser().is_file():
            raise ValueError('Music file is missing: '+str(path))
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_type',
                              '-of','csv=p=0',str(Path(path).expanduser())],capture_output=True,text=True)
        if 'audio' not in (probe.stdout or ''):
            raise ValueError('Music file has no audio stream: '+str(path))
        if isinstance(music,dict) and 'gain_db' in music:number(music['gain_db'],'music gain',-96,12)
    for row in edit['sequence']:
        if 'pictures' in row:
            if not isinstance(row['pictures'],list) or not row['pictures']:
                raise ValueError('pictures must be a nonempty list')
            for p in row['pictures']:
                number(p.get('source_in'),'picture source',0,duration)
                number(p.get('weight',1),'picture weight',1e-9)
                if 'source_audio_gain_db' in p:
                    number(p['source_audio_gain_db'],'source gain',-96,12)
                    if not row.get('narration') and p['source_audio_gain_db']!=row.get('source_audio_gain_db',config.get('audio',{}).get('dialogue_gain_db',0)):
                        raise ValueError('Dialogue audio stays continuous; set source_audio_gain_db on its parent sequence, not individual pictures')
                reason=p.get('intentional_jumpback_reason')
                if reason is not None and (not isinstance(reason,str) or not reason.strip()):
                    raise ValueError('Picture jumpback needs an authored reason')
        if 'source_audio_gain_db' in row:number(row['source_audio_gain_db'],'source gain',-96,12)
        if row.get('effects') and config.get('effect',{}).get('enabled') is False:
            raise ValueError('This profile disables reaction effects')
        for e in row.get('effects',[]):
            frame(e.get('start_frame'),'effect start',0,2**31)
            frame(e.get('end_frame'),'effect end',e['start_frame']+1,2**31)
            if not isinstance(e.get('text'),str) or not e['text'].strip() or any(c in e['text'] for c in '\r\n'):
                raise ValueError('Reaction text must be one nonempty line')
            for k in ('color','outline_color'):
                if k in e and not re.fullmatch(r'#[0-9a-fA-F]{6}',e[k]):raise ValueError('Invalid reaction color')
            if 'position' in e:
                if not isinstance(e['position'],list) or len(e['position'])!=2:raise ValueError('Invalid reaction position')
                for value,limit in zip(e['position'],(config['width'],config['height'])):number(value,'reaction position',0,limit)
        for cue in row.get('sounds',[]):
            frame(cue.get('at_frame'),'sound onset',0,2**31)
            number(cue.get('gain_db',0),'sound gain',-96,12)
            asset=(config.get('sfx') or {}).get(cue.get('asset'))
            if not asset:raise ValueError('Unknown sound asset')
            import film_editor as E
            if not Path(asset['path']).is_file() or E.file_digest(asset['path'])!=asset['sha256']:
                raise ValueError('Sound file is missing or changed; restore the declared asset before narration')

def compile_tracks(tl,edit):
    fps=tl['fps'];pictures=[];effects=[];sounds=[]
    authored=any('pictures' in row for row in edit['sequence'])
    for row,clip in zip(edit['sequence'],tl['clips']):
        base=round(clip['timeline_in']*fps);count=clip['frames']
        if 'source_audio_gain_db' in row:clip['source_audio_gain_db']=row['source_audio_gain_db']
        if authored:
            choices=row.get('pictures') or [{'source_in':clip['source_in'],'weight':1}]
            weights=[number(p.get('weight',1),'picture weight',1e-9) for p in choices]
            previous=0;weight=0
            for p,w in zip(choices,weights):
                weight+=w;end=round(count*weight/sum(weights));n=end-previous
                if n<1:raise ValueError('Every picture needs at least one measured output frame')
                value={**deepcopy(clip),'index':len(pictures),'origin_index':clip['index'],
                    'source_in':p['source_in'],'frames':n,'duration':n/fps,
                    'timeline_in':(base+previous)/fps,'timeline_out':(base+end)/fps}
                for key in ('intentional_jumpback_reason','source_audio_gain_db'):
                    if key in p:value[key]=p[key]
                pictures.append(value);previous=end
        for e in row.get('effects',[]):
            a=frame(e.get('start_frame'),'effect start',0,count-1)
            b=frame(e.get('end_frame'),'effect end',a+1,count)
            effects.append({**deepcopy(e),'start_frame':base+a,'end_frame':base+b})
        for cue in row.get('sounds',[]):
            t=frame(cue.get('at_frame'),'sound onset',0,count-1)
            sounds.append({**deepcopy(cue),'at_frame':base+t})
    if authored:tl['picture_clips']=pictures
    if effects:tl['effects']=effects
    if sounds:tl['sounds']=sounds
    return tl

def bind_assets(tl,config):
    import film_editor as E
    for cue in tl.get('sounds',[]):
        asset=config['sfx'][cue['asset']]
        if E.file_digest(asset['path'])!=asset['sha256']:raise ValueError('Sound asset changed; preserve existing render')
    return {cue['asset']:config['sfx'][cue['asset']]['sha256'] for cue in tl.get('sounds',[])}

def existing_narration(contract,text,root):
    """Import an explicit measured artifact without inventing a paid receipt."""
    import film_editor as E
    verify_existing(contract)
    data=E.read_json(contract['alignment']['path']);chars=data.get('characters',[])
    if data.get('text')!=text or ''.join(c.get('text','') for c in chars)!=text:
        raise ValueError('Existing narration alignment does not cover the exact requested text')
    duration=float(E.probe(root,contract['audio']['path'])['format']['duration'])
    previous=0
    for c in chars:
        a=number(c.get('start'),'existing character start',0,duration)
        number(c.get('end'),'existing character end',a,duration)
        if len(c['text'])!=1 or a<previous:raise ValueError('Existing character timing must be ordered')
        previous=a
    if not isinstance(contract.get('provenance'),str) or not contract['provenance'].strip():
        raise ValueError('Existing narration requires its source/provenance description')
    record={'kind':'existing_narration','audio':contract['audio'],'alignment':contract['alignment'],
            'provenance':contract['provenance'],'reused':True,'requests':0}
    E.atomic_json(root/('imported-narration-'+E.digest(record)+'.json'),record)
    return {'characters':chars,'audio_duration':duration},Path(contract['audio']['path']),record

def verify_existing(contract):
    import film_editor as E
    for key in ('audio','alignment'):
        value=contract.get(key) or {};path=Path(value.get('path',''))
        if not path.is_file() or E.file_digest(path)!=value.get('sha256'):
            raise ValueError('Existing narration '+key+' is missing or changed')

def mix_extra(work,source,tl,config,pcm):
    """Mix by exact samples without repeating the continuous narration track."""
    import film_editor as E
    import numpy as np
    import wave
    rate=config['audio']['sample_rate'];spf=rate//tl['fps']
    with wave.open(str(pcm),'rb') as f:data=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).astype(float)/32767
    def add(path,start,at,count,gain,label):
        raw=E.command(work,['ffmpeg','-v','error','-ss',start,'-i',path,'-map','0:a:0','-t',count/rate,
                           '-f','f32le','-ar',rate,'-ac',2,'pipe:1'],label)
        samples=np.frombuffer(raw,dtype='<f4').reshape(-1,2);n=min(count,len(samples),len(data)-at)
        if n>0:
            samples=samples[:n].copy()
            if label.startswith('source-bed-'):
                fade=min(round(.005*rate),n//2)
                if fade:
                    samples[:fade]*=np.linspace(0,1,fade)[:,None]
                    samples[-fade:]*=np.linspace(1,0,fade)[:,None]
            data[at:at+n]+=samples*10**(gain/20)
    for i,p in enumerate(tl.get('picture_clips',tl['clips'])):
        gain=p.get('source_audio_gain_db')
        if p['kind']=='N' and gain is not None:
            add(source,p.get('picture_in',p['source_in']),round(p['timeline_in']*tl['fps'])*spf,
                p['frames']*spf,gain,'source-bed-'+str(i))
    bind_assets(tl,config)
    for i,cue in enumerate(tl.get('sounds',[])):
        at=cue['at_frame']*spf
        add(config['sfx'][cue['asset']]['path'],0,at,len(data)-at,cue.get('gain_db',0),'sfx-'+str(i))
    # Fixed headroom preserves every track without clipping before mastering.
    peak=float(np.max(np.abs(data))) if data.size else 0
    gain=min(1,.98/peak) if peak else 1
    with wave.open(str(pcm),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes((data*gain*32767).astype('<i2').tobytes())
    E.atomic_json(work/'mix-tracks.json',{'sounds':tl.get('sounds',[]),'asset_hashes':bind_assets(tl,config),
        'pre_master_gain':gain,'samples':len(data)})
