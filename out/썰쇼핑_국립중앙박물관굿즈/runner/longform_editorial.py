"""Deterministic editorial evidence, never an automatic style approval.

Preserve every occurrence instead of collapsing a block into a set. Source
regions and visibility cues let reviewers distinguish sprites/document details
from a subject-photo carousel. Similar geometry is a candidate, not a verdict.
"""
from collections import defaultdict
from itertools import accumulate, combinations
from longform_state import digest


def overlap(a,b):
    x=max(a[0],b[0]);y=max(a[1],b[1])
    w=max(0,min(a[0]+a[2],b[0]+b[2])-x)
    h=max(0,min(a[1]+a[3],b[1]+b[3])-y)
    intersection=w*h;union=a[2]*a[3]+b[2]*b[3]-intersection
    return intersection/union if union>0 else 0


def similar(a,b):
    # Reordered objects, names, words and tiny position changes are not a
    # different composition. A different spatial arrangement remains distinct.
    if not a or len(a)!=len(b):return False
    remaining=list(b)
    for role,box in sorted(a,key=lambda x:x[1][2]*x[1][3],reverse=True):
        scores=[overlap(box,other) if kind==role else 0 for kind,other in remaining]
        score=max(scores,default=0)
        if score<.8:return False
        remaining.pop(scores.index(score))
    return True


_AREA_SLACK=1e-9   # relative float slack on the .8 overlap bound (rounding is ~1e-15; never loosens a verdict)


def _area_key(geometry):
    """(bucket, total area, per-kind area sums) or None when a box is not a finite positive-area rectangle."""
    from collections import Counter
    from math import isfinite
    try:
        bucket=(len(geometry),frozenset(Counter(kind for kind,_ in geometry).items()))
    except TypeError:
        return None
    sums={}
    for kind,box in geometry:
        if not (isinstance(box,(list,tuple)) and len(box)==4
                and all(type(v) in (int,float) and isfinite(v) for v in box) and box[2]>0 and box[3]>0):
            return None
        sums[kind]=sums.get(kind,0)+box[2]*box[3]
    return bucket,sum(sums.values()),sums


def _ratio_ok(a,b):
    # min/max >= .8 for positive a,b, with the same float slack as the window.
    return min(a,b)*1.25*(1+_AREA_SLACK)>=max(a,b)


def similar_pairs(compositions):
    """Index pairs (i,j), i<j, with similar(compositions[i]['geometry'], compositions[j]['geometry']) True.

    Same pairs in the same order as «for a,b in combinations(compositions,2): if similar(a,b)», without
    comparing every pair of the episode (6-00).

    Why no similar pair is skipped. similar(a,b) is True only if the greedy matcher pairs EVERY element of a
    with a distinct element of b of the same kind (other kinds score 0) whose overlap() is >= .8, and a and b
    have the same length. So a and b share length and kind multiset (= one bucket). For a matched pair of
    positive-area boxes, overlap = I/U with I <= min(Aa,Ab) and U >= max(Aa,Ab), so min/max >= .8: each matched
    area ratio lies in [.8,1.25], hence so does the ratio of the per-kind area sums and of the total area. Within
    a bucket, compositions are sorted by total area and only pairs inside the 1.25 window (plus float slack) are
    candidates, then filtered by the per-kind sums. A composition with a box that is not a finite positive-area
    rectangle makes no such guarantee: it is compared with every other composition, exactly as before. Every
    candidate is decided by similar() itself. Cost O(n log n + W), W = pairs inside an area window (quadratic
    only when a bucket holds many near-equal-area compositions — then the output itself can be that large).
    """
    keys=[_area_key(row['geometry']) for row in compositions]
    buckets=defaultdict(list);loose=[]
    for i,key in enumerate(keys):
        if key is None:loose.append(i)
        else:buckets[key[0]].append(i)
    candidates=set()
    for members in buckets.values():
        members.sort(key=lambda i:(keys[i][1],i))
        for p,i in enumerate(members):
            limit=keys[i][1]*1.25*(1+_AREA_SLACK);q=p+1   # walk by index: a slice would copy the tail per p
            while q<len(members) and keys[members[q]][1]<=limit:
                j=members[q];q+=1
                if all(_ratio_ok(area,keys[j][2][kind]) for kind,area in keys[i][2].items()):
                    candidates.add((min(i,j),max(i,j)))
    for i in loose:
        for j in range(len(compositions)):
            if j!=i:candidates.add((min(i,j),max(i,j)))
    return [(i,j) for i,j in sorted(candidates)
            if similar(compositions[i]['geometry'],compositions[j]['geometry'])]


def overlapping_video_uses(uses):
    """Pairs (i,j), i<j, whose source windows strictly overlap — the same pairs, in the same order, as
    «for a,b in combinations(uses,2)» with the None/overlap test (6-00: no pairwise scan of one source's uses).

    max(in) < min(out) holds iff both windows are non-empty (in < out) and each starts before the other ends.
    Uses with a None limit or an empty/unordered window can never overlap and are left out. Sorted by source_in,
    a use p overlaps exactly the later-sorted uses q with in_q < out_p (in_q >= in_p and in_q < out_q already
    give the other two inequalities), so the inner walk stops at the first q that does not overlap:
    O(n log n + pairs found).
    """
    valid=[i for i,u in enumerate(uses)
           if u['source_in'] is not None and u['source_out'] is not None and u['source_in']<u['source_out']]
    valid.sort(key=lambda i:(uses[i]['source_in'],i))
    found=[]
    for p,i in enumerate(valid):
        end=uses[i]['source_out'];q=p+1   # walk by index: a slice would copy the tail per p
        while q<len(valid) and uses[valid[q]]['source_in']<end:
            j=valid[q];q+=1
            found.append((min(i,j),max(i,j)))
    return sorted(found)


def layout_family(geometry):
    """Broad photo-and-copy patterns, independent of text node count or IDs.

    These are review candidates, not prohibited layouts. A clothing credit and
    a field report can repeat the same presentation despite different geometry.
    """
    pictures=[box for kind,box in geometry if kind in ('image','video')]
    words=[box for kind,box in geometry if kind=='text']
    if not pictures or not words:return None
    def side(box):
        centre=box[0]+box[2]/2
        return 'left' if centre<864 else 'right' if centre>1056 else 'centre'
    picture_sides={side(box) for box in pictures}
    word_sides={side(box) for box in words}
    if len(picture_sides)==len(word_sides)==1:
        a=next(iter(picture_sides));b=next(iter(word_sides))
        if (a,b) in (('left','right'),('right','left')):
            return f'picture_{a}_copy_{b}'
    return None


def video_audio_assignments(plan, voices):
    """Expose silent-by-omission source windows, never infer audible quality.

    Uses the renderer's 60fps montage boundaries and authored video clock.
    Visibility is positive opacity, not proof that another layer does not cover
    the video. A sound from a different source instant is not synchronous audio.
    """
    from longform_contract import graphic_visibility
    from longform_graphic import aligned_visual
    rows=[]
    for block,voice in zip(plan['blocks'],voices):
        v=block['visual'];duration=voice['frames']/60;uses=[]
        if v['kind']=='video':
            uses=[('visual',v['media'][0],v['in'],0,[[0,duration]])]
        elif v['kind']=='montage':
            shots=v['shots'];weights=[float(s['weight']) for s in shots];total=sum(weights)
            # Running prefix sums: the same left-to-right additions as sum(weights[:i]) (exact floats), once.
            prefix=list(accumulate(weights))
            edges=[0]+[round(voice['frames']*prefix[i-1]/total)/60 for i in range(1,len(shots))]+[duration]
            for i,s in enumerate(shots):
                if s['kind']!='video':continue
                tr=s.get('transition',{});handle=tr.get('frames',0)/60 if tr.get('kind','cut')!='cut' else 0
                uses.append((f'shots[{i}]',s['media'],s['in'],edges[i],[[edges[i],min(duration,edges[i+1]+handle)]]))
        elif v['kind']=='graphic' and v.get('template')=='authored':
            visual=aligned_visual(v,voice)
            for i,n in enumerate(visual['objects']):
                if n['kind']!='video':continue
                start=n.get('at',0)*duration;end=min(duration,start+n.get('duration',1)*duration)
                spans=[]
                for a,b in graphic_visibility(visual,n['id']):
                    a=max(start,a*duration);b=min(end,b*duration)
                    if b>a:spans.append([a,b])
                uses.append((f'objects[{i}]',n['media'],n['in'],start,spans))
        # One pass over this block's source_audio cues, indexed by source sha (cue order kept), instead of
        # rescanning every cue for every visual use (block-local; uses <= shots/objects of one scene).
        cues_by_sha=defaultdict(list)
        if uses:
            for ci,cue in enumerate(block.get('source_audio',[])):
                cues_by_sha[plan['media'][cue['media']]['sha256']].append((ci,cue))
        for location,mid,source_in,start,visible in uses:
            assignments=[];remaining=[];sha=plan['media'][mid]['sha256']
            for ci,cue in cues_by_sha.get(sha,()):
                if abs((source_in-start)-(cue['in']-cue['at']))>1/48000:continue
                for a,b in visible:
                    left=max(a,cue['at']);right=min(b,cue['at']+cue['out']-cue['in'])
                    if right>left:assignments.append({'cue_index':ci,'mode':cue['mode'],'start':left,'end':right,'reason':cue['reason']})
            ordered=sorted(assignments,key=lambda c:c['start'])   # once per use, not once per visible span
            for a,b in visible:
                edge=a
                for cue in ordered:
                    left=max(a,cue['start']);right=min(b,cue['end'])
                    if right<=left:continue
                    if left>edge+1e-7:remaining.append([edge,left])
                    edge=max(edge,right)
                if b>edge+1e-7:remaining.append([edge,b])
            rows.append({'block':block['id'],'location':location,'media':mid,'source_sha256':sha,
                         'source_in':source_in,'timeline_start':start,'visible':visible,
                         'assignments':assignments,'unassigned':remaining,'status':'review_required'})
    return rows


def source_audio_picture_mismatches(plan, assignments):
    """Reverse the picture-to-audio lookup, preserving intentional offscreen sound.

    These are review candidates, not invalid audio: a dialogue or ambience bed
    can deliberately continue after a cut. Mute decisions can also become stale
    when a picture is replaced or shortened. Report the exact uncovered clock.
    """
    spans=defaultdict(list)
    for row in assignments:
        for cue in row['assignments']:
            spans[(row['block'],cue['cue_index'])].append((cue['start'],cue['end']))
    findings=[]
    for block in plan['blocks']:
        for index,cue in enumerate(block.get('source_audio',[])):
            start=cue['at'];end=start+cue['out']-cue['in'];edge=start;gaps=[]
            matched=sorted(spans[(block['id'],index)])
            for left,right in matched:
                left=max(start,left);right=min(end,right)
                if right<=left:continue
                if left>edge+1e-7:gaps.append([edge,left])
                edge=max(edge,right)
            if end>edge+1e-7:gaps.append([edge,end])
            if gaps:
                findings.append({'block':block['id'],'cue_index':index,
                                 'media':cue['media'],'mode':cue['mode'],
                                 'cue_interval':[start,end],
                                 'matching_video_intervals':[list(p) for p in matched],
                                 'without_matching_video':gaps,
                                 'status':'review_required'})
    return findings


def audio_coverage(plan, voices):
    """Report actual-clock assignments, not perceived sound or mandatory BGM.

    Short effects never count as a continuous bed. Unassigned intervals remain
    visible even when original audio plays; a reviewer decides intentional quiet.
    """
    if len(voices) != len(plan['blocks']):
        raise ValueError('Audio coverage requires one measured voice per block')
    clock=[];cursor=0
    for block,voice in zip(plan['blocks'],voices):
        end=cursor+voice['frames']/60
        clock.append({'block':block['id'],'start':cursor,'end':end,
                      'source_audio':[dict(c, start=cursor+c['at'], end=cursor+c['at']+c['out']-c['in']) for c in block.get('source_audio',[])],
                      'sfx':[dict(c, start=cursor+c['at']) for c in block.get('sfx',[])]})
        cursor=end
    # The assembly and audio mixer append the same nine-second endcard.
    total=cursor+9
    music=plan.get('music') or {}
    segments=music.get('segments',[])
    if music and 'segments' not in music:
        segments=[dict(music,start=0,end=total)]
    spans=sorted((max(0,c['start']),min(total,c['end'])) for c in segments if c['end']>0 and c['start']<total)
    gaps=[];edge=0
    for start,end in spans:
        if start>edge+1e-7:gaps.append((edge,start))
        edge=max(edge,end)
    if edge<total-1e-7:gaps.append((edge,total))
    missing=[]
    # clock is contiguous (each block starts where the previous ends, frames >= 0), so its starts and ends are
    # non-decreasing: the blocks overlapping a gap form one slice, found by bisection instead of a rescan per gap.
    # The exact overlap test still filters the slice. If the clock were ever not monotone, scan it as before.
    from bisect import bisect_left,bisect_right
    starts=[r['start'] for r in clock];ends=[r['end'] for r in clock]
    monotone=all(a<=b for a,b in zip(starts,starts[1:])) and all(a<=b for a,b in zip(ends,ends[1:]))
    for start,end in gaps:
        window=clock[bisect_right(ends,start):bisect_left(starts,end)] if monotone else clock
        rows=[r for r in window if r['start']<end and r['end']>start]
        missing.append({'start':start,'end':end,'seconds':end-start,
                        'blocks':[r['block'] for r in rows],
                        'original_audio':[dict(c, block=r['block']) for r in rows for c in r['source_audio'] if c['mode']!='mute' and c['start']<end and c['end']>start],
                        'includes_endcard':end>cursor})
    assignments=video_audio_assignments(plan,voices)
    return {'status':'review_required','actual_seconds':total,'blocks':clock,
            'music_segments':segments,'music_unassigned_intervals':missing,
            'video_source_audio_assignments':assignments,
            'source_audio_picture_mismatches':source_audio_picture_mismatches(plan,assignments),
            'limitations':['Assignments are not proof of audible sound or style fidelity',
                           'Unassigned video audio is a review candidate, not a command to unmute; source streams and sound must be checked',
                           'A music gap may be intentional; no automatic music insertion or looping',
                           'SFX and muted source cues do not establish continuous audio coverage',
                           'Source audio without matching video can be intentional offscreen sound; review before changing or removing it']}


def pose_motion_restarts(visual, media):
    """Flag endpoint resets between adjacent atlas poses, without approving style.

    Limited to equal image boxes, the same source hash, distinct crops, and
    direct pan/zoom cues covering each visible phase. Parent transforms and
    arbitrary easing samples require browser inspection; never auto-rewrite.
    """
    from math import isclose
    from longform_contract import graphic_visibility
    nodes=[n for n in visual.get('objects',[]) if n['kind']=='image']
    rows=[];spans={}
    def visibility(node):
        # Each node's spans once per scene (the pair loop asked again for every pair and direction).
        if node['id'] not in spans:spans[node['id']]=graphic_visibility(visual,node['id'])
        return spans[node['id']]
    # Pairwise over one scene's image objects only: objects <= 30 (longform_contract validate_authored).
    for a,b in combinations(nodes,2):
        if (a['box']!=b['box'] or a.get('crop')==b.get('crop')
                or media[a['media']]['sha256']!=media[b['media']]['sha256']):continue
        for left,right in ((a,b),(b,a)):
            ls=visibility(left);rs=visibility(right)
            # Only one unambiguous, consecutive visibility span per pose.
            if len(ls)!=1 or len(rs)!=1 or not isclose(ls[0][1],rs[0][0],abs_tol=1e-7):continue
            changes=[]
            for effect,axes in (('pan',(('x','from_x',0),('y','from_y',0))),
                                ('zoom',(('scale','from_scale',1),))):
                def phase_cue(node,span):
                    # Scans one scene's cues (<= 80, validate_authored).
                    candidates=[c for c in visual.get('motion_cues',[]) if c['target']==node['id'] and c['effect']==effect]
                    if len(candidates)!=1:return None
                    c=candidates[0]
                    return c if isclose(c['at'],span[0],abs_tol=1e-7) and isclose(c['at']+c['duration'],span[1],abs_tol=1e-7) else None
                previous=phase_cue(left,ls[0]);following=phase_cue(right,rs[0])
                if previous is None or following is None:continue
                for key,start,default in axes:
                    before=previous.get(key,default);after=following.get(start,default)
                    if not isclose(before,after,abs_tol=1e-7):changes.append({'property':key,'before':before,'after':after})
            if changes:rows.append({'left':left['id'],'right':right['id'],'at':rs[0][0],
                                   'changes':changes,'status':'review_required'})
    return rows


def reference_entries(value, path='style_reference'):
    """Keep every nested observation and its location; never infer verification.

    Authoring can attach distinct return/comparison references under a primary
    reference. Traverse dictionaries and lists, including malformed candidates,
    so a correction cannot leave an earlier review digest valid.
    """
    from math import isfinite
    pending=[(path,value)];valid=[];invalid=[]
    while pending:
        location,node=pending.pop()
        if isinstance(node,dict):
            if any(k in node for k in ('source','start','end')):
                source=node.get('source');start=node.get('start');end=node.get('end');observed=node.get('observed')
                numbers=all(type(x) in (int,float) and 0<=x<=10**12 and isfinite(x) for x in (start,end))
                if (isinstance(source,str) and source.strip() and numbers and end>start
                        and isinstance(observed,str) and observed.strip()):
                    valid.append((location,node))
                else:
                    invalid.append({'reference_path':location,'value':node,
                                    'reason':'Reference needs a source, finite increasing times and an observation',
                                    'status':'review_required'})
            for key in sorted(node,reverse=True):
                if isinstance(node[key],(dict,list)):pending.append((location+'.'+key,node[key]))
        elif isinstance(node,list):
            for i in range(len(node)-1,-1,-1):pending.append((f'{location}[{i}]',node[i]))
    return valid,invalid


def effect_reference_notes(visual):
    """Expose authored effect citations without promoting them to verified evidence."""
    rows=[]
    def visit(value,path):
        if isinstance(value,dict):
            for key,child in value.items():
                if key=='style_reference':continue
                location=f'{path}.{key}'
                if key=='reference' and isinstance(child,str) and child.strip():
                    rows.append({'reference_path':location,'note':child,'status':'unverified_author_note'})
                else:visit(child,location)
        elif isinstance(value,list):
            for i,child in enumerate(value):visit(child,f'{path}[{i}]')
    visit(visual,'visual')
    return rows


def photo_treatment_groups(plan):
    """Declared single-photo treatments, not a judgement of visible repetition.

    Scale amplitudes/crops remain evidence, not new treatment families. Encoded
    interiors and paired-photo animations require their own rendered review.
    """
    groups=defaultdict(list)
    for block in plan['blocks']:
        visual=block['visual'];kind=visual['kind']
        if kind=='photo':
            nodes=[('media[0]',visual,visual['media'][0])]
        elif kind=='montage':
            nodes=[(f'shots[{i}]',n,n['media']) for i,n in enumerate(visual['shots'])
                   if n['kind']=='photo' and not n.get('paired_photo')]
        else:continue
        for location,node,mid in nodes:
            fit=node.get('fit','auto');motion=node.get('motion','in')
            # Direct still/auto uses FFmpeg cover; montage auto uses prepare().
            if kind=='photo' and fit=='auto' and motion=='still':fit='cover'
            camera=node.get('camera') if kind=='montage' else None
            key=(fit,motion,digest(camera))
            groups[key].append({'block':block['id'],'location':location,'media':mid,
                'source_sha256':plan['media'][mid]['sha256'],'fit':fit,'motion':motion,
                'max_scale':node.get('max_scale'),'min_scale':node.get('min_scale',1),
                'crop':node.get('crop'),'camera':camera,'reason':node.get('reason')})
    return [{'fit':key[0],'motion':key[1],'uses':uses,
             'scope':'Same declared framing/motion family, ignoring scale amplitude and crop differences. Auto fit depends on source aspect ratio; contain does not prove exposed blur. Compare actual frames and narrative purpose; this is not an automatic rejection.'}
            for key,uses in groups.items() if len(uses)>1]


def audit(plan, voices=None, *, plan_id=None):
    """plan_id: the caller's digest(plan) of this same plan object, so it is not hashed twice (6-00)."""
    stills=defaultdict(list);videos=defaultdict(list);compositions=[]
    reference_uses=defaultdict(list);unreferenced=[];motion_restarts=[];invalid_references=[];effect_notes=[];without_any=[]
    for block in plan['blocks']:
        v=block['visual'];bid=block['id'];nodes=[]
        reference=v.get('style_reference')
        entries,invalid=reference_entries(reference)
        invalid_references.extend(dict(row,block=bid) for row in invalid)
        if not entries:unreferenced.append(bid)
        notes=effect_reference_notes(v)
        effect_notes.extend(dict(row,block=bid) for row in notes)
        if not entries and not notes:without_any.append(bid)
        for location,entry in entries:
            key=(entry['source'],entry['start'],entry['end'])
            reference_uses[key].append({'block':bid,'reference_path':location,'observed':entry['observed']})
        if v['kind']=='montage':
            for i,n in enumerate(v['shots']):
                nodes.append((f'shots[{i}]',n))
                if n.get('paired_photo'):
                    nodes.append((f'shots[{i}].paired_photo',
                                  {'kind':'photo','media':n['paired_photo']['media']}))
        elif v['kind']=='graphic' and v.get('template')=='authored':
            nodes=[(f'objects[{i}]',n) for i,n in enumerate(v['objects']) if n['kind'] in ('image','video')]
            motion_restarts.extend(dict(row,block=bid) for row in pose_motion_restarts(v,plan['media']))
            # A decorative animated group must not hide the persistent base board.
            # One pass groups the objects (first-seen group order, object order inside) — no rescan per group.
            grouped=defaultdict(list)
            for n in v['objects']:grouped[n.get('group')].append(n)
            for group,members in grouped.items():
                geometry=[(n['kind'],n['box']) for n in members if n['kind'] in ('image','video','text','path')]
                if geometry:compositions.append({'block':bid,'group':group,'geometry':geometry})
        else:
            nodes=[(f'media[{i}]',{'kind':v['kind'],'media':mid,'crop':v.get('crop'),'in':v.get('in'),'out':v.get('out')}) for i,mid in enumerate(v.get('media',[]))]
        # Cues per target, in motion_cues order (looked up per node instead of rescanning every cue per node).
        # Built only when there are nodes, as the old per-node scan touched the cues only then.
        cues_by_target=defaultdict(list)
        if nodes:
            for index,c in enumerate(v.get('motion_cues',[])):cues_by_target[c.get('target')].append((index,c))
        for location,n in nodes:
            mid=n['media'];asset=plan['media'][mid]
            row={'block':bid,'location':location,'media':mid,'crop':n.get('crop'),'object_id':n.get('id'),'group':n.get('group')}
            # Keep decorative repeats visible to reviewers, including their
            # declaration. The contract alone determines whether it is valid.
            if n.get('role') or asset.get('role'):
                row.update(object_role=n.get('role'),asset_role=asset.get('role'))
            targets={x for x in (n.get('id'),n.get('group')) if x is not None}
            row['visibility_cues']=[c for _,c in sorted((pair for t in targets for pair in cues_by_target.get(t,())),key=lambda pair:pair[0])
                                    if c['effect'] in ('fade','rise','slide','pop')]
            if n['kind']=='video':
                row.update(source_in=n.get('in'),source_out=n.get('out'));videos[asset['sha256']].append(row)
            else:stills[asset['sha256']].append(row)
    repeated=[{'source_sha256':sha,'uses':uses} for sha,uses in stills.items() if len(uses)>1]
    repeated_video=[]
    for sha,uses in videos.items():
        for i,j in overlapping_video_uses(uses):
            a,b=uses[i],uses[j]
            start=max(a['source_in'],b['source_in']);end=min(a['source_out'],b['source_out'])
            repeated_video.append({'source_sha256':sha,'left':a,'right':b,
                                   'overlap_seconds':end-start,'source_interval':[start,end]})
    matches=[]
    for i,j in similar_pairs(compositions):
        a,b=compositions[i],compositions[j]
        matches.append({'left':{'block':a['block'],'group':a['group']},'right':{'block':b['block'],'group':b['group']},'reason':'same object-role geometry within 80% IoU; inspect real content and motion'})
    families=defaultdict(list)
    for row in compositions:
        family=layout_family(row['geometry'])
        if family:families[family].append({'block':row['block'],'group':row['group']})
    recurring=[{'family':name,'uses':uses} for name,uses in families.items() if len(uses)>1]
    references=[{'source':key[0],'start':key[1],'end':key[2],'uses':uses}
                for key,uses in reference_uses.items()]
    # An encoded clip may itself contain a montage or authored graphic. Its
    # outer SHA/window says nothing about the identity of sources inside it.
    # Do not infer trusted provenance from a neighbouring visual.json file.
    coverage={'authored_graphic_blocks':[b['id'] for b in plan['blocks'] if b['visual']['kind']=='graphic' and b['visual'].get('template')=='authored'],
              'video_container_uses':[{'block':r['block'],'location':r['location'],'media':r['media'],'source_sha256':sha}
                                      for sha,uses in videos.items() for r in uses],
              'video_interiors_inspected':False,
              'scope':'Explicit plan objects and outer source identities/windows only. Photos, textures and edits baked inside video files are not expanded. Preserve composition/source evidence and review the rendered footage; no duplicate candidates is not complete coverage.'}
    photo_treatments=photo_treatment_groups(plan)
    result={'schema':'geumbit-editorial-audit-v1','plan_id':digest(plan) if plan_id is None else plan_id,'status':'review_required',
            'repeated_sources':repeated,'video_sources':[{'source_sha256':s,'uses':u} for s,u in videos.items()],
            'repeated_video_intervals':repeated_video,
            'recurring_layout_families':recurring,'recurring_photo_treatments':photo_treatments,'pose_motion_restarts':motion_restarts,
            'style_reference_uses':references,'invalid_style_references':invalid_references,
            'repeated_style_references':[row for row in references if len(row['uses'])>1],
            'blocks_without_style_reference':unreferenced,
            'effect_reference_notes':effect_notes,'blocks_without_any_reference_notes':without_any,
            'similar_compositions':matches,'composition_count':len(compositions),'inspection_coverage':coverage,
            'limitations':['Pose restart candidates cover adjacent atlas crops with direct full-phase pan/zoom only; absence is not continuity approval',
                           'Occurrence count is not visible reentry count; inspect visibility cues and final frames',
                           'Different encodings of the same footage require visual comparison',
                           'Geometry candidates do not establish semantic variety or reference fidelity',
                           'A reference citation is not proof of observation or implementation; repeated citations require scene-specific comparison']}
    if voices is not None:result['audio_coverage']=audio_coverage(plan,voices)
    result['findings_id']=digest({'inspection_coverage':coverage,'effect_reference_notes':effect_notes,'blocks_without_any_reference_notes':without_any,'repeated_sources':repeated,'repeated_video_intervals':repeated_video,'similar_compositions':matches,'recurring_layout_families':recurring,'recurring_photo_treatments':photo_treatments,'pose_motion_restarts':motion_restarts,
                                 'style_reference_uses':references,'invalid_style_references':invalid_references,'blocks_without_style_reference':unreferenced,'audio_coverage':result.get('audio_coverage')})
    return result
