"""Conservative decoded-picture duplicate checks before paid work.

Hashes protect bytes. These comparisons additionally catch resized/re-encoded
pictures and identical sampled clip ranges. They do not prove semantic diversity.
"""
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image, ImageOps
from film_editor import command
from longform_state import ProductionError


def signature(image):
    image=ImageOps.exif_transpose(image).convert('RGB').resize((32,32),Image.Resampling.LANCZOS)
    return np.asarray(image,dtype=np.float32)


def similar(a,b):
    # Uniform backgrounds cannot establish identity: two white slides differ
    # precisely in their small foregrounds. Leave them to content review.
    if min(float(a.std()),float(b.std()))<12:return False
    delta=np.abs(a-b)
    return float(delta.mean())<=3 and float(np.quantile(delta,.95))<=10


def composition_signature(frame):
    image=Image.fromarray(np.clip(frame,0,255).astype('uint8')).convert('L')
    small=np.asarray(image.resize((9,8)),dtype=np.int16)
    bits=(small[:,1:]>small[:,:-1]).ravel()
    return np.asarray(image,dtype=np.float32),sum(int(bit)<<i for i,bit in enumerate(bits))


def composition_matches(left,right):
    # Authored triage thresholds, following the 2026-09-25 shot-family audit:
    # dHash<=4, grayscale MAE<=8, std>=12. These are NOT identity/approval gates.
    found=[]
    for i,(a,ah) in enumerate(left):
        if float(a.std())<12:continue
        for j,(b,bh) in enumerate(right):
            distance=(ah^bh).bit_count()
            if float(b.std())<12 or distance>4:continue
            error=float(np.abs(a-b).mean())
            if error<=8:found.append({'left_sample':i,'right_sample':j,
                                     'hash_distance':distance,'gray_mean_error':error})
    return found


# Candidate indexes so a new clip/image is compared only with earlier ones that can still pass (6-00: no
# comparison of every new picture against every earlier one). Each index only drops pairs that PROVABLY fail
# the unchanged test; every candidate is still decided by the same similar()/composition_matches() call, in
# the same (earlier-first) order, so the report is identical.
#
# similar(a,b) needs std>=12 on both and mean|a-b| <= 3 (float32 mean of exact integer differences; its
# rounding is < 1e-3 here). For any sign pattern s (s_i = +-1), the signed average f_s(x) = (1/N)*sum(s_i*x_i)
# obeys |f_s(a)-f_s(b)| <= (1/N)*sum|a_i-b_i| = mean|a-b| <= 3.001 < 4. Four such coordinates (plain mean,
# left-right, top-bottom, red-blue) in cells floor(f/4): a passing pair differs by at most one cell on every
# coordinate, so it is found among the 3^4 neighbouring cells.
FEATURE_CELL=4.0
# composition_matches needs a sample pair whose 64-bit dHashes differ in <= 4 bits. Split the 64 bits into
# 5 chunks: 4 differing bits cannot touch all 5, so a passing pair shares at least one whole chunk (pigeonhole).
HASH_CHUNKS=((0,13),(13,26),(26,39),(39,52),(52,64))


def _feature_cell(frame):
    """Cell of the four signed averages of one (H, W, 3) signature (see FEATURE_CELL)."""
    import math
    x=np.asarray(frame,dtype=np.float64);h,w,c=x.shape;n=x.size
    left=x[:,:w//2].sum();top=x[:h//2].sum();red=x[:,:,0].sum();total=x.sum()
    sums=(total,2*left-total,2*top-total,2*red-total)   # sum(s_i*x_i) with s=+1 inside the part, -1 outside
    return tuple(math.floor(v/n/FEATURE_CELL) for v in sums)


def _neighbour_cells(cell):
    from itertools import product
    return [tuple(c+d for c,d in zip(cell,step)) for step in product((-1,0,1),repeat=len(cell))]


def _hash_chunks(value):
    return [(c,(value>>a)&((1<<(b-a))-1)) for c,(a,b) in enumerate(HASH_CHUNKS)]


class _Candidates:
    """Earlier entries by key: add(index, keys) then near(keys) -> set of earlier indices sharing any key."""
    def __init__(self):self.rows={}
    def add(self,index,keys):
        for key in keys:self.rows.setdefault(key,[]).append(index)
    def near(self,keys):
        found=set()
        for key in keys:found.update(self.rows.get(key,()))
        return found


def picture(asset,crop=None):
    with Image.open(asset['path']) as image:
        if crop is not None:
            a,b,c,d=crop
            if not (0<=a<c<=image.width and 0<=b<d<=image.height):
                raise ProductionError('photo_crop','사진 자르기 범위가 원본 밖입니다.',action='edit_plan')
            image=image.crop(tuple(crop))
        return signature(image)


def inspect(plan,folder,*,reject_duplicates=True):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    images=[];clips=[];cache={};matches=[];compositions=[];composition_candidates=[]
    image_keys=_Candidates();image_cells=_Candidates();clip_cells=_Candidates();empty_clips=[];sample_chunks=_Candidates()
    expanded=[]
    for block in plan['blocks']:
        if block['visual']['kind']=='montage':
            for i,part in enumerate(block['visual']['shots']):
                expanded.append({'id':block['id']+'-shot-'+str(i),'visual':{**part,'media':[part['media']],'repeat_reason':block['visual'].get('repeat_reason')}})
                if part.get('paired_photo'):
                    expanded.append({'id':block['id']+'-shot-'+str(i)+'-paired','visual':{'kind':'photo','media':[part['paired_photo']['media']],'repeat_reason':block['visual'].get('repeat_reason')}})
        elif block['visual']['kind']=='graphic' and block['visual'].get('template')=='authored':
            seen=set()
            for node in block['visual']['objects']:
                if node['kind'] not in ('image','video'):continue
                key=(node['kind'],node['media'],tuple(node.get('crop',[])),node.get('in'),node.get('out'))
                if key in seen:continue
                seen.add(key)
                expanded.append({'id':block['id']+'-object-'+node['id'],'visual':{
                    **node,'kind':'video' if node['kind']=='video' else 'photo',
                    'media':[node['media']],'repeat_reason':block['visual'].get('repeat_reason')}})
        else:expanded.append(block)
    for block in expanded:
        shot=block['visual'];bid=block['id'];reason=shot.get('repeat_reason')
        if shot['kind']=='video':
            asset=plan['media'][shot['media'][0]]
            key=(asset['sha256'],shot['in'],shot['out'])
            if key not in cache:
                frames=[]
                for i,fraction in enumerate((.1,.3,.5,.7,.9)):
                    when=shot['in']+(shot['out']-shot['in'])*fraction
                    raw=command(folder,['ffmpeg','-v','error','-ss',when,'-i',asset['path'],'-frames:v','1','-vf','scale=64:64','-f','image2pipe','-vcodec','png','-'],f'duplicate-{bid}-{i}',timeout=60)
                    with Image.open(BytesIO(raw)) as image:frames.append(signature(image))
                cache[key]=frames
            frames=cache[key]
            signatures=[composition_signature(frame) for frame in frames]
            times=[shot['in']+(shot['out']-shot['in'])*f for f in (.1,.3,.5,.7,.9)]
            # Only samples with std>=12 can match (composition_matches skips the others on both sides).
            chunks=[chunk for a,ah in signatures if float(a.std())>=12 for chunk in _hash_chunks(ah)]
            for index in sorted(sample_chunks.near(chunks)):
                previous,old,old_times,old_sha=compositions[index]
                pairs=composition_matches(old,signatures)
                if pairs:
                    for pair in pairs:
                        pair['left_source_seconds']=old_times[pair['left_sample']]
                        pair['right_source_seconds']=times[pair['right_sample']]
                    composition_candidates.append({'previous':previous,'block':bid,
                        'left_source_sha256':old_sha,'right_source_sha256':asset['sha256'],
                        'sample_pairs':pairs,'reason':reason,'status':'review_required'})
            sample_chunks.add(len(compositions),chunks)
            compositions.append((bid,signatures,times,asset['sha256']))
            # A match needs similar() on the first sample pair (std>=12 both, features within one cell). An empty
            # sample list (all() of nothing is True) stays a candidate of everything, as before.
            cell=_feature_cell(frames[0]) if frames and float(frames[0].std())>=12 else None
            if not frames:near=set(range(len(clips)))
            else:
                near=set(empty_clips)
                if cell is not None:near|=clip_cells.near(_neighbour_cells(cell))
            for index in sorted(near):
                previous,old=clips[index]
                if all(similar(a,b) for a,b in zip(frames,old)):
                    matches.append({'block':bid,'previous':previous,'kind':'sampled_video','reason':reason})
            if not frames:empty_clips.append(len(clips))
            elif cell is not None:clip_cells.add(len(clips),[cell])
            clips.append((bid,frames))
        else:
            for mid in shot['media']:
                asset=plan['media'][mid];crop=shot.get('crop') if shot['kind']=='photo' else None
                key=(asset['sha256'],tuple(crop) if crop else None)
                if key not in cache:cache[key]=picture(asset,crop)
                frame=cache[key]
                # Same key (exact reuse) or a similar() candidate: std>=12 and features within one cell.
                textured=float(frame.std())>=12
                near=image_keys.near([key])
                cell=_feature_cell(frame) if textured else None
                if textured:near|=image_cells.near(_neighbour_cells(cell))
                for index in sorted(near):
                    previous,old_key,old=images[index]
                    # The flat-picture heuristic cannot establish similarity,
                    # but identical source bytes and crop already establish reuse.
                    if key==old_key or similar(frame,old):
                        matches.append({'block':bid,'previous':previous,'kind':'decoded_image','reason':reason})
                image_keys.add(len(images),[key])
                if textured:image_cells.add(len(images),[cell])
                images.append((bid,key,frame))
    unreviewed=[row for row in matches if not row['reason']]
    report={'image_occurrences':len(images),'video_ranges':len(clips),'matches':matches,
            'similar_video_compositions':composition_candidates,
            'composition_review':{'status':'review_required','sample_fractions':[.1,.3,.5,.7,.9],
                'method':'dHash<=4 and grayscale MAE<=8; std<12 excluded; authored triage thresholds',
                'scope':'Five uncomposited samples per declared source interval. May include unused handles. Similar framing candidates, not proof of identity, uniqueness, or approval. Repeat reasons do not approve candidates.'},
            'scope':'resizing/JPEG and five matching clip samples; not exhaustive crop or semantic similarity'}
    from longform_state import save,digest
    report['plan_id']=digest(plan)
    save(folder/'duplicates.json',report)
    if unreviewed and reject_duplicates:
        row=unreviewed[0]
        raise ProductionError('duplicate_media',f"{row['block']}의 화면이 {row['previous']}과 거의 같습니다. 소재를 교체하거나 의도한 회상의 이유를 기록하세요.",action='edit_plan')
    return report


def inspect_timed(plan, voices, folder):
    """Review displayed source time, separately from pre-voice handle checks.

    Reuse the product's montage boundaries and authored positive-opacity
    windows. This does not infer that a layer is unobscured by other layers.
    New findings require review; the existing preflight duplicate gate remains.
    """
    from longform_editorial import video_audio_assignments
    from longform_timing import conform_plan
    from longform_state import save, digest
    if len(plan['blocks']) != len(voices) or any(
            type(v.get('frames')) is not int or v['frames'] <= 0 for v in voices):
        raise ProductionError('review_voice_clock', '모든 장면의 확정 음성 프레임 수가 필요합니다.')
    plan = conform_plan(plan, voices)
    blocks = {b['id']: b for b in plan['blocks']}
    expanded = []; windows = []
    for row in video_audio_assignments(plan, voices):
        block = blocks[row['block']]; visual = block['visual']; location = row['location']
        if location.startswith('objects['):
            node = visual['objects'][int(location[8:-1])]
            label = block['id']+'-object-'+node['id']
        elif location.startswith('shots['):
            index = int(location[6:-1]); node = visual['shots'][index]
            label = block['id']+'-shot-'+str(index)
        else:
            node = visual; label = block['id']
        for i, (start, end) in enumerate(row['visible']):
            source_start = row['source_in']+start-row['timeline_start']
            source_end = row['source_in']+end-row['timeline_start']
            if source_start < node['in']-1e-6 or source_end > node['out']+1e-6:
                raise ProductionError('review_source_window',
                                      label+'의 실제 표시 길이가 확보한 원본 구간 밖입니다.', action='edit_plan')
            identity = label if len(row['visible']) == 1 else label+'-window-'+str(i)
            expanded.append({'id': identity, 'visual': {
                'kind': 'video', 'media': [row['media']], 'in': source_start,
                'out': source_end, 'repeat_reason': visual.get('repeat_reason')}})
            windows.append({'id': identity, 'block': block['id'], 'location': location,
                            'source_in': source_start, 'source_out': source_end,
                            'timeline_start': start, 'timeline_end': end})
    report = inspect({'media': plan['media'], 'blocks': expanded}, folder,
                     reject_duplicates=False)
    report['sample_plan_id'] = report['plan_id']
    report['plan_id'] = digest(plan)
    report['voice_clock_id'] = digest(voices)
    report['source_windows'] = windows
    report['status'] = 'review_required'
    report['composition_review']['scope'] = (
        'Five source samples per narration-timed positive-opacity window, including visible '
        'transition handles. Excludes unused acquired footage. Does not model occlusion, '
        'crop/zoom, final compositing, every frame, or perceptual approval.')
    report['scope'] = 'Timed video review only. Pre-voice image/video duplicate gate is separate.'
    save(Path(folder)/'duplicates.json', report)
    return report
