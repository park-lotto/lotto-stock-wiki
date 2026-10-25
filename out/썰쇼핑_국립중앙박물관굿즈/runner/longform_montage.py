"""Narration-length montage with real outgoing picture handles and no audio retiming."""
from pathlib import Path
import json,math
from film_editor import command
from longform_photo import encoder_slot
from longform_state import ProductionError,save

FPS=60

def video_filter(shot):
    """Preserve the complete foreground; optional blurred overscan fills its matte."""
    crop=shot.get('crop');prefix=''
    if crop:prefix=f'crop={crop[2]-crop[0]}:{crop[3]-crop[1]}:{crop[0]}:{crop[1]},'
    top=shot.get('inset_top',0);bottom=shot.get('inset_bottom',0)
    if not all(isinstance(n,(int,float)) and 0<=n<=400 for n in (top,bottom)):
        raise ProductionError('montage_inset_range','몽타주 영상 여백은 0~400px입니다.',action='edit_plan')
    background=shot.get('background','black')
    if background not in ('black','blur'):
        raise ProductionError('montage_background','몽타주 영상 배경은 black 또는 blur입니다.',action='edit_plan')
    height=1080-top-bottom
    fit=shot.get('fit','contain')
    if fit not in ('contain','cover') or (fit=='cover' and (top or bottom)):
        raise ProductionError('video_fit','영상 cover는 여백 없이 지정하세요. fit은 contain 또는 cover입니다.',action='edit_plan')
    if fit=='cover':
        return prefix+'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=60'
    if background=='black':
        return prefix+f'scale=1920:{height}:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:{top}+({height}-ih)/2,setsar=1,fps=60'
    # Only the backdrop is overscanned 2x. Foreground retains source logos/text.
    return (prefix+'setsar=1,fps=60,split[matte][picture];'
            '[matte]scale=3840:2160:force_original_aspect_ratio=increase,crop=1920:1080,gblur=sigma=45,eq=brightness=-0.16[bg];'
            f'[picture]scale=1920:{height}:force_original_aspect_ratio=decrease[fg];'
            f'[bg][fg]overlay=(W-w)/2:{top}+({height}-h)/2,setsar=1')

def camera_frame(image,index,frames,camera):
    """Seek-independent subpixel crop; no rounded zoompan crop offsets."""
    from PIL import Image
    t=index/max(1,frames-1)
    t=max(0,min(1,(t-camera.get('at',0))/camera.get('duration',1)))
    if camera.get('ease','linear')=='ease_out':t=1-(1-t)**3
    scale=camera['from_scale']+(camera['to_scale']-camera['from_scale'])*t
    a=1/scale;w,h=image.size;cx=w*camera.get('anchor_x',.5);cy=h*camera.get('anchor_y',.5)
    return image.transform(image.size,Image.Transform.AFFINE,(a,0,cx*(1-a),0,a,cy*(1-a)),Image.Resampling.BICUBIC)

def camera_video(source,dest,frames,camera):
    import subprocess
    from PIL import Image
    from longform_photo import encode_frames
    size=1920*1080*3
    with open(str(dest)+'.decode.log','wb') as log:
        proc=subprocess.Popen(['ffmpeg','-v','error','-i',str(source),'-an','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE,stderr=log)
        def pixels():
            for i in range(frames):
                raw=bytearray()
                while len(raw)<size:
                    chunk=proc.stdout.read(size-len(raw))
                    if not chunk:raise RuntimeError('Camera input ended before expected frame count')
                    raw.extend(chunk)
                yield camera_frame(Image.frombytes('RGB',(1920,1080),bytes(raw)),i,frames,camera).tobytes()
            if proc.stdout.read(1):raise RuntimeError('Camera input has unexpected extra frames')
        try:
            encode_frames(pixels(),dest)
            if proc.wait():raise RuntimeError('Camera decode failed')
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
            proc.stdout.close()

def build(folder,visual,media,frames,*,assets=None):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True)
    shots=visual['shots'];weights=[float(s['weight']) for s in shots];total=sum(weights)
    boundaries=[0]+[round(frames*sum(weights[:i])/total) for i in range(1,len(shots))]+[frames]
    lengths=[b-a for a,b in zip(boundaries,boundaries[1:])]
    if min(lengths)<30:raise ProductionError('montage_short_shot','각 몽타주 컷은 최소 0.5초여야 합니다.',action='edit_plan')
    transitions=[s.get('transition',{'kind':'cut','frames':0}) for s in shots]
    if transitions[-1].get('kind','cut')!='cut':raise ProductionError('montage_last_transition','마지막 컷 뒤 전환은 다음 컷이 필요합니다.',action='edit_plan')
    # 2026-10-17 #128: inspect every video shot's source cuts before building any shot, and report all short spans at
    # once (one author round instead of one per shot). Same inspect_cuts call per shot as before — not a second pass.
    from longform_video import inspect_cuts
    from longform_contract import gathered
    found=[]
    for i,(shot,count,tr) in enumerate(zip(shots,lengths,transitions)):
        if shot['kind']!='video':continue
        handle=int(tr.get('frames',0)) if tr.get('kind','cut')!='cut' else 0
        try:inspect_cuts(root/f'cut-check-{i}',Path(media[shot['media']]['path']),float(shot['in']),(count+handle)/FPS,
                         visible_seconds=count/FPS,cut_review=shot.get('cut_review'))
        except ProductionError as error:
            if error.code!='short_source_shot':raise
            found.append(ProductionError(error.code,f'몽타주 컷 {i}: {error}',action=error.action))
    if found:raise gathered(found)
    clips=[];proof=[]
    for i,(shot,count,tr) in enumerate(zip(shots,lengths,transitions)):
        kind=tr.get('kind','cut');handle=int(tr.get('frames',0)) if kind!='cut' else 0
        if handle and (handle>=count or handle>=lengths[i+1]):raise ProductionError('montage_transition_length','전환은 양쪽 컷보다 짧아야 합니다.',action='edit_plan')
        wanted=count+handle;source=Path(media[shot['media']]['path']);dest=root/f'picture-{i:03d}.mp4'
        if shot['kind']=='video':
            start=float(shot['in']);end=float(shot['out'])
            if end-start+1e-7<wanted/FPS:raise ProductionError('montage_source_handles','전환에 쓸 실제 뒷부분 영상이 부족합니다. 정지 프레임으로 채우지 않습니다.',action='edit_plan')
            # Use a declared crop only when selected by the author; no watermark removal inference.
            applied=shot
            if shot.get('video_treatment'):
                from longform_video_treatment import prepare
                if assets is None:raise ProductionError('video_treatment_assets','영상처리 자산 위치가 없습니다.',action='repair_environment')
                treated=prepare(root/f'treatment-{i}',source,start,wanted,shot['video_treatment'],assets)
                source=Path(treated['path']);start=0
                applied={**shot,'fit':'cover','inset_top':0,'inset_bottom':0};applied.pop('crop',None)
            vf=video_filter(applied)
            command(root,['ffmpeg','-y','-v','error','-ss',start,'-i',source,'-vf',vf,'-an','-frames:v',wanted,*encoder_slot(19),'-pix_fmt','yuv420p',dest],f'shot-{i}')
        elif shot['kind']=='photo':
            from longform_render import photo_render,photo_source
            if shot.get('paired_photo'):
                from longform_photo import paired_frames,encode_frames,Frames
                pair=shot['paired_photo']
                encode_frames(Frames(lambda:paired_frames(source,media[pair['media']]['path'],wanted,count,pair['entrances'])),dest)
            elif shot.get('crop') is not None:
                crop_folder=root/f'photo-source-{i:03d}';crop_folder.mkdir(exist_ok=True)
                source=photo_source({'media':[shot['media']],'crop':shot['crop']},media,crop_folder)
                photo_render(source,dest,wanted,shot.get('motion','in'),fit=shot.get('fit','auto'),max_scale=shot.get('max_scale'),min_scale=shot.get('min_scale',1))
            else:photo_render(source,dest,wanted,shot.get('motion','in'),fit=shot.get('fit','auto'),max_scale=shot.get('max_scale'),min_scale=shot.get('min_scale',1))
        else:raise ProductionError('montage_shot_kind','몽타주 컷은 photo 또는 video여야 합니다.',action='edit_plan')
        if shot.get('camera'):
            moved=root/f'camera-{i:03d}.mp4';camera_video(dest,moved,wanted,shot['camera']);dest=moved
        clips.append(dest);proof.append({'index':i,'media':shot['media'],'source_sha256':media[shot['media']]['sha256'],
            'source_in':shot.get('in'),'visible_frames':count,'outgoing_handle_frames':handle,'timeline_start_frame':boundaries[i],'transition':tr,'crop':shot.get('crop'),'camera':shot.get('camera'),'background':shot.get('background','black'),'fit':shot.get('fit','auto'),'max_scale':shot.get('max_scale'),'min_scale':shot.get('min_scale',1)})
        if shot.get('paired_photo'):
            pair=shot['paired_photo'];proof[-1]['paired_photo']={**pair,'source_sha256':media[pair['media']]['sha256']}
    shatters={}
    for i,tr in enumerate(transitions[:-1]):
        if tr.get('kind') in ('shatter','brush_reveal'):
            if tr['kind']=='shatter':
                from longform_shatter import render
            else:
                from longform_transitions import render_reveal as render
            path=root/f'{tr["kind"]}-{i:03d}.mp4'
            render(clips[i],clips[i+1],path,lengths[i],tr['frames'],tr.get('seed',17))
            shatters[i]=(len(clips)+len(shatters),path)
    args=['ffmpeg','-y','-v','error','-filter_complex_threads','1']
    for p in clips:args+=['-i',p]
    for _,p in shatters.values():args+=['-i',p]
    chains=[f'[{i}:v]settb=1/60,setpts=PTS-STARTPTS,format=yuv420p[v{i}]' for i in range(len(clips))]
    label='v0'
    for i in range(1,len(clips)):
        tr=transitions[i-1];out=f'm{i}'
        if tr.get('kind','cut')=='cut':chains.append(f'[{label}][v{i}]concat=n=2:v=1:a=0[{out}]')
        elif tr['kind'] in ('shatter','brush_reveal'):
            index,_=shatters[i-1]
            chains.append(f'[{label}]trim=end_frame={boundaries[i]},setpts=PTS-STARTPTS[prior{i}]')
            chains.append(f'[v{i}]trim=start_frame={tr["frames"]},setpts=PTS-STARTPTS[tail{i}]')
            chains.append(f'[{index}:v]settb=1/60,setpts=PTS-STARTPTS[shards{i}]')
            chains.append(f'[prior{i}][shards{i}][tail{i}]concat=n=3:v=1:a=0[{out}]')
        else:
            kind={'dissolve':'fade','wipe_left':'wipeleft','wipe_right':'wiperight','horizontal_blur':'hblur'}[tr['kind']]
            chains.append(f'[{label}][v{i}]xfade=transition={kind}:duration={tr["frames"]/FPS:.9f}:offset={boundaries[i]/FPS:.9f}[{out}]')
        # concat resets its output clock to microseconds. Normalize after every
        # boundary so a later xfade sees the same60fps clock on both inputs.
        normalized=f'clock{i}'
        chains.append(f'[{out}]settb=1/60,setpts=PTS-STARTPTS[{normalized}]')
        label=normalized
    dest=root/'montage.mp4'
    args+=['-filter_complex',';'.join(chains),'-map',f'[{label}]','-an','-frames:v',frames,'-r',FPS,*encoder_slot(19),'-pix_fmt','yuv420p',dest]
    command(root,args,'montage',timeout=1800)
    from film_editor import probe
    info=probe(root,dest)
    video=next(x for x in info['streams'] if x['codec_type']=='video')
    if int(video.get('nb_frames',-1))!=frames:raise ProductionError('montage_frames','몽타주 프레임 수가 나레이션 타임라인과 다릅니다.')
    # Full decoding remains the final delivery gate; preserve exact requested frame contract here.
    save(root/'montage.json',{'schema':'geumbit-montage-v1','frames':frames,'fps':FPS,'duration':frames/FPS,'shots':proof,'audio_retimed':False,'source_info':info})
    return dest
