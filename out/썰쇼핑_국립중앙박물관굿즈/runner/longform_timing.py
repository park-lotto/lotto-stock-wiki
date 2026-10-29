"""Conform authored picture/sound cues to explicitly inserted sentence pauses."""
import copy
from longform_state import ProductionError


def voice_time(voice, value):
    """Map original scene seconds to the derived narration clock, including padding."""
    changes=voice.get('timing_adjustments',[])
    if not changes:return float(value)
    old=voice['original_frames']/60;new=voice['frames']/60
    if abs(value-old)<1e-7:return new
    return float(value)+sum(x['add_seconds'] for x in changes if x['at_seconds']<=value)


def validate_source_capacity(plan, voices):
    """Check source placement after voice timing, before media review and mixing.

    2026-10-20 실기(헵번 5분 판): 첫 블록 하나만 알려 h05 → 고침 → 한 바퀴 → h13 … 처럼 블록마다 한 바퀴(재개·검사)를 돌았다.
    모든 블록을 한 번 훑어 걸린 것을 전부 모아 한 번에 알린다(longform_contract.gathered — 하나면 예전과 같은 예외·같은 글)."""
    from longform_contract import gathered
    found=[]
    for block,voice in zip(plan['blocks'],voices):
        # Match the 48kHz mixer clock exactly, including explicitly muted cues.
        # Removed pictures can leave stale cues even without inserted pauses.
        for cue in block.get('source_audio',[]):
            start=round(cue['at']*48000)
            count=round((cue['out']-cue['in'])*48000)
            if start<0 or start+count>voice['frames']*800:
                found.append(ProductionError('source_audio_outside_shot','원음이 장면 범위를 넘습니다: '+block.get('id','?'),action='edit_plan'))
                break
        if not voice.get('timing_adjustments'):continue
        error=short_window(block,voice)
        if error:found.append(error)
    if found:raise gathered(found)


def short_window(block, voice):
    """The first picture window shorter than its timeline span on this voice clock, as the ProductionError the
    gate raises — or None. One measurement for validate_source_capacity and fit_pauses (no second formula)."""
    visual=block['visual'];seconds=voice['frames']/60;windows=[]
    if visual['kind']=='video':windows.append((visual,seconds))
    if visual['kind']=='montage':
        shots=visual['shots'];total=sum(float(s['weight']) for s in shots)
        edges=[0]+[round(voice['frames']*sum(float(s['weight']) for s in shots[:i])/total) for i in range(1,len(shots))]+[voice['frames']]
        for i,shot in enumerate(shots):
            if shot['kind']=='video':
                transition=shot.get('transition',{})
                handle=transition.get('frames',0) if transition.get('kind','cut')!='cut' else 0
                windows.append((shot,(edges[i+1]-edges[i]+handle)/60))
    windows.extend((node,node.get('duration',1)*seconds) for node in visual.get('objects',[]) if node.get('kind')=='video')
    for source,required in windows:
        span=source['out']-source['in']
        if span+1e-7<required:
            # Say the exact in/out and shortfall: the author re-picks the range once instead of guessing again.
            return ProductionError('pause_source_handles',
                f"호흡 조정 뒤 {block.get('id','?')} 영상 구간이 {required:.3f}초보다 짧습니다"
                f"(지금 in {source['in']:.3f} → out {source['out']:.3f} = {span:.3f}초 · {required-span:.3f}초 모자람). "
                "원본 앞뒤 컷을 확인해 다시 선정하세요.",action='edit_plan')
    return None


def paused_voice(entries, *, samples, rate, characters):
    """The voice clock a pause edit list produces — the same sample arithmetic as longform_audio.sentence_pauses
    (round(at·rate), round(add·rate)) and timed_voice (60fps frames, editorial gap = position after earlier pauses).
    Used to try a pause set against the footage BEFORE the audio is cut (fit_pauses)."""
    changes=[];gaps=[];offset=0.;added=0
    for entry in sorted(entries,key=lambda e:e['at_seconds']):
        pos,count=round(entry['at_seconds']*rate),round(entry['add_seconds']*rate)
        change={'after_character':entry['after_character'],'at_seconds':pos/rate,'add_seconds':count/rate}
        if entry.get('editorial'):
            change['editorial']=True
            gaps.append({'start':pos/rate+offset,'end':pos/rate+offset+count/rate,'after_character':entry['after_character']})
        changes.append(change);offset+=count/rate;added+=count
    voice={'original_frames':(samples*60+rate-1)//rate,'frames':((samples+added)*60+rate-1)//rate,
           'timing_adjustments':changes,'source_characters':characters}
    if gaps:voice['editorial_gaps']=gaps
    return voice


#: Gates a single automatic breath can trip on its own (2026-10-15). Dropping that breath clears them; every other
#: conform/validate stop is not caused by a breath and is left to the gate exactly as before.
BREATH_LIMITS=('pause_source_handles','source_audio_pause_inside')


def fit_pauses(block, spec, *, samples, rate, characters, timing_basis='original_voice'):
    """Keep only the automatic sentence breaths this block's plan can carry (2026-10-15).

    The approved breath (+0.3s per sentence end, plan_sentence_pauses) lengthens the block after the footage and the
    original-sound cues were chosen against the bought voice. A picture window could then come up short
    (pause_source_handles) or a breath could land inside a playing original-sound cue (source_audio_pause_inside)
    purely because of the breath — and the job stopped, the author re-picked and ran again (a full round each time).
    The breath is a nicety on top of the bought voice: like a sentence gap with no quiet point (plan_sentence_pauses
    `skipped`), a breath the plan cannot carry is simply not inserted and is recorded in `skipped`.

    Judged with the gate's own code (conform_plan + short_window on this one block) — no second formula, so the gate
    can never disagree with the choice. Authored listening gaps (editorial) are never dropped. If the plan fails even
    with no automatic breath, the spec is returned unchanged so the gate reports exactly as before (re-picking footage
    is the only fix there). An authored adjusted_voice clock is never changed (its cues were placed on the breaths).
    Cost: one measurement when everything fits (the usual case); otherwise one pass in time order — each breath is
    tried once, at most 100 per block (sentence_pauses limit). Returns None when no pause is left."""
    entries=(spec or {}).get('entries') or []
    auto=[e for e in entries if not e.get('editorial')]
    # A block with no picture plan cannot be conformed (the contract requires one — longform_contract kind check);
    # there is nothing to fit against, so it is left exactly as before.
    if not auto or timing_basis=='adjusted_voice' or not isinstance(block.get('visual'),dict):return spec
    local={'blocks':[block],'timing_basis':timing_basis}
    def blocked(chosen):
        voice=paused_voice(chosen,samples=samples,rate=rate,characters=characters)
        try:conformed=conform_plan(local,[voice])['blocks'][0]
        except ProductionError as error:
            if error.code in BREATH_LIMITS:return True
            raise
        return short_window(conformed,voice) is not None
    if not blocked(entries):return spec
    kept=[e for e in entries if e.get('editorial')]
    if blocked(kept):return spec
    dropped=[]
    for entry in sorted(auto,key=lambda e:e['at_seconds']):
        (dropped if blocked(kept+[entry]) else kept).append(entry)
    if not kept:return None
    result=dict(spec)
    result['entries']=sorted(kept,key=lambda e:e['at_seconds'])
    result['skipped']=list(spec.get('skipped',[]))+[
        {'after_character':e['after_character'],'terminal_tail':bool(e.get('terminal_tail')),'reason':'plan_cannot_carry'}
        for e in dropped]
    return result


def conform_plan(plan, voices):
    """No holds, video time stretching, source-range extension, or asset substitution.

    Only timeline positions change. Source handles are rechecked by the normal
    video renderer; insufficient footage must be reselected, never freeze-filled.
    An already adjusted plan is explicitly marked to prevent double conforming.
    """
    result=copy.deepcopy(plan)
    basis=plan.get('timing_basis','original_voice')
    if basis not in ('original_voice','adjusted_voice'):
        raise ProductionError('timing_basis','편집 시간 기준은 original_voice 또는 adjusted_voice여야 합니다.')
    if len(plan['blocks'])!=len(voices):
        raise ProductionError('timing_voice_count','편집표와 음성 개수가 다릅니다.')
    # Gap-anchored original audio uses an explicit new timeline interval.
    anchored=set()
    for bi,(block,voice) in enumerate(zip(result['blocks'],voices)):
        for ci,cue in enumerate(block.get('source_audio',[])):
            if 'gap_after_character' not in cue:continue
            gap=next((g for g in voice.get('editorial_gaps',[]) if g['after_character']==cue['gap_after_character']),None)
            if gap is None or cue['at']+cue['out']-cue['in']>gap['end']-gap['start']+1e-7:
                raise ProductionError('source_audio_gap','전면 원음은 확인한 청취 쉼 안에 들어가야 합니다.',action='edit_plan')
            cue['at']+=gap['start'];cue.pop('gap_after_character');anchored.add((bi,ci))
    if basis=='adjusted_voice' or not any(v.get('timing_adjustments') for v in voices):return result
    for bi,(block,voice) in enumerate(zip(result['blocks'],voices)):
        if not voice.get('timing_adjustments'):continue
        old=voice['original_frames']/60;new=voice['frames']/60
        warp=lambda t:voice_time(voice,t)
        visual=block['visual']
        for name in ('ink_cover','tear_cover','brush_cover','light_leak','glitch','negative_splatter','grain_wipe'):
            if name in visual:
                cue=visual[name];start=cue['at']*old;end=start+cue['duration']*old
                cue['at']=warp(start)/new;cue['duration']=(warp(end)-warp(start))/new
        if 'beat_seconds' in visual:visual['beat_seconds']=[warp(t) for t in visual['beat_seconds']]
        for cue in visual.get('motion_cues',[]):
            if 'start_char' in cue:
                start=voice['source_characters'][cue['start_char']]['start']
                if 'end_char' in cue:end=voice['source_characters'][cue['end_char']]['end']
                else:end=start+cue['duration']*old
            else:start=cue['at']*old;end=start+cue['duration']*old
            cue['at']=warp(start)/new;cue['duration']=(warp(end)-warp(start))/new
        for node in visual.get('objects',[]):
            if node.get('kind')=='video':
                start=node.get('at',0)*old;end=start+node.get('duration',1)*old
                node['at']=warp(start)/new;node['duration']=(warp(end)-warp(start))/new
        if visual.get('kind')=='montage':
            shots=visual['shots'];total=sum(float(s['weight']) for s in shots)
            edges=[0]+[round(voice['original_frames']*sum(float(s['weight']) for s in shots[:i])/total) for i in range(1,len(shots))]+[voice['original_frames']]
            mapped=[round(warp(t/60)*60) for t in edges]
            for index,(shot,a,b) in enumerate(zip(shots,mapped,mapped[1:])):
                if b<=a:raise ProductionError('timing_empty_shot','호흡 조정 뒤 자료 컷 길이가 비었습니다.')
                for entry in shot.get('paired_photo',{}).get('entrances',[]):
                    span=max(1,edges[index+1]-edges[index]-1)
                    first=(edges[index]+entry['at']*span)/60
                    last=first+entry['duration']*span/60
                    entry['at']=(warp(first)*60-a)/max(1,b-a-1)
                    entry['duration']=(warp(last)-warp(first))*60/max(1,b-a-1)
                shot['weight']=b-a
        for cue in block.get('sfx',[]):cue['at']=warp(cue['at'])
        for ci,cue in enumerate(block.get('source_audio',[])):
            if (bi,ci) in anchored:continue
            a=cue['at'];b=a+cue['out']-cue['in']
            if abs((warp(b)-warp(a))-(b-a))>1e-7:
                raise ProductionError('source_audio_pause_inside','원음 재생 도중 호흡 삽입은 동기화를 깨뜨립니다. 원음 구간을 다시 배정하세요.',action='edit_plan')
            cue['at']=warp(a)
    def global_time(t):
        original=adjusted=0.
        for voice in voices:
            old=voice.get('original_frames',voice['frames'])/60
            if t<original+old-1e-7:return adjusted+voice_time(voice,t-original)
            original+=old;adjusted+=voice['frames']/60
        return adjusted+(t-original)
    music=result.get('music') or {}
    for cue in music.get('segments',[]):
        cue['start']=global_time(cue['start']);cue['end']=global_time(cue['end'])
    result['timing_basis']='adjusted_voice'
    return result
