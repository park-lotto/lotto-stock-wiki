"""Pure production-plan checks; no truth claims, file I/O, model calls or rendering."""
import math
import re
import json
import hashlib
from urllib.parse import urlsplit
from longform_state import ProductionError
import longform_floor

KINDS = {'photo','video','split','cutout','graphic','montage'}
FONT_NAMES = ('ROKAFSansMedium.ttf','JalnanGothic.ttf','Paperlogy-8ExtraBold.ttf','BMYEONSUNG.ttf','Paperlogy-3Light.ttf','SBAggroB.ttf','NanumMyeongjo-ExtraBold.ttf','DNFForgedBlade-Bold.otf')
GRAPHIC_FONTS = {'Hand':'BMYEONSUNG.ttf','Paper':'Paperlogy-8ExtraBold.ttf','Body':'ROKAFSansMedium.ttf','Serif':'NanumMyeongjo-ExtraBold.ttf'}
CAPTION_FIELDS={'font','font_file','font_size','color','outline_color','outline_width','background_color','background_opacity','x','y'}
GRAPHIC_LABEL_COUNTS={'numbers':2,'comparison':2,'identity':2,'story':1,'context':3,'explanation':3,
                      'document':3,'debate':2,'timeline':3,'question':2,'layers':3,'balance':2,'callout':2,'authored':1}
# 2026-10-09 B2 (docs/2026-10-09_롱폼-그래픽-다양성/B2-unique-v1.md). One table for the fixed templates'
# background theme: longform_graphic.document paints from it and unique-v1 keys backgrounds by it.
TEMPLATE_THEMES={'identity':'charcoal','story':'brown','context':'purple','comparison':'brown','numbers':'charcoal',
                 'explanation':'brown','document':'brown','debate':'purple','timeline':'brown','question':'charcoal',
                 'layers':'charcoal','balance':'brown','callout':'charcoal'}
# One ease list read by both the contract and the renderer. Every name is a GSAP 3 core ease present in the
# bundled assets/stage_geumbit/geumbit-assets/gsap.min.js (3.14.2: Power0-4 loop, Expo, Circ, Sine, Back,
# Elastic and Bounce registrations, SteppedEase as «steps» — checked in the file 2026-10-09).
# LEGACY_EASES is the pre-B2 list: plans without unique-v1 (no visual.variety) keep exactly it.
LEGACY_EASES=('power2.out','power2.in','power2.inOut','power3.out','sine.inOut','none','back.out(1.4)','back.out(1.3)')
AUTHORED_EASES=LEGACY_EASES+('power1.out','power1.inOut','power3.inOut','power4.out','expo.out','expo.inOut','circ.out','circ.inOut',
                'sine.out','back.out(1.7)','back.out(2.2)','back.inOut(1.4)','elastic.out(1,0.5)','elastic.out(1,0.3)',
                'bounce.out','steps(4)','steps(8)','steps(12)')
# Entrance values when a cue omits them, and the only values a pre-B2 (old) graphic ever renders.
MOTION_DEFAULTS={'rise_distance':55,'slide_distance':90,'pop_from_scale':.6,'pop_ease':'back.out(1.4)'}
MOTION_VALUE_KEYS=('distance','from_scale','scale','from','to','x','y','from_x','from_y','axis','direction','strength','feather')
GRAPHIC_VARIETY='unique-v1'
# Vocabulary from the 966 reference graphics (ref-distribution.json).
VARIETY_VOCAB={'expression':('cutout_composite','reenactment_illustration','document_highlight','numbers_chart',
                             'map_route','typography','comparison_split','symbolic_metaphor'),
               'texture':('paper_card','material_pattern','flat_gradient','live_footage','painted_scene','geometric_pattern'),
               'motion':('slow_zoom','pan','pop_in','slide_in','draw_reveal','shake_glitch','rotate_flip','still')}
VARIETY_AXIS_NAMES={'expression':'표현','texture':'질감','motion':'모션'}
VARIETY_CHOICES=' / '.join(axis+'('+VARIETY_AXIS_NAMES[axis]+'): '+'·'.join(words) for axis,words in VARIETY_VOCAB.items())
# 2026-10-09 B3: the motion axis is derived, not judged by agy. Lead measurement on 10 real graphic clips
# (two agy passes, scratchpad revacc/rows.json): the passes disagreed on motion 4/10 (expression 1/10, texture 1/10),
# so the program reads the motion families the graphic itself contains and visual.variety.motion must be one of them.
# ONE table: authored motion_cues effect, scene-level effect, and fixed-template choreography technique
# (longform_graphic.choreography cues[].technique) → motion families. () = not one of the families (fade, colour,
# count-up, small floating drift). A graphic with no family at all is 'still'.
MOTION_FAMILY={
    'cue':{'zoom':('slow_zoom',),'pan':('pan',),'pattern_pan':('pan',),'pop':('pop_in',),'slide':('slide_in',),'rise':('slide_in',),
           'draw':('draw_reveal',),'paper_reveal':('draw_reveal',),'brush_reveal':('draw_reveal',),'text_wipe':('draw_reveal',),
           'polygon_wipe':('draw_reveal',),'object_glitch':('shake_glitch',),'rotate':('rotate_flip',),'gear_spin':('rotate_flip',),
           'fade':(),'focus':(),'grayscale':(),'brightness':(),'count':(),'round_frame':()},
    'scene':{'glitch':('shake_glitch',),'edge_strobe':('shake_glitch',)},
    'technique':{'trim-path':('draw_reveal',),'stagger-rise':('slide_in',),'reading-focus':(),'paper-slide':('slide_in',),
                 'read-line':('slide_in',),'highlight-wipe':('draw_reveal',),'margin-note':('slide_in',),'opposed-slide':('slide_in',),
                 'conversation-depth':(),'connection':('draw_reveal',),'overshoot':('pop_in',),'question-rise':(),
                 'question-reveal':('slide_in',),'underline-write':('draw_reveal',),'answer-reveal':('slide_in',),
                 'paper-follow-through':('slide_in',),'layer-parallax':(),'comparison-label':('slide_in',),
                 'balance-question':('rotate_flip',),'balance-settle':('rotate_flip',),'source-reveal':(),'pointer-write':('draw_reveal',),
                 'locate-detail':(),'detail-label':('slide_in',),'stagger-reveal':('slide_in',),'portrait-parallax':('slow_zoom','pan'),
                 'illustration-push':('slow_zoom',),'sum-rule':('draw_reveal',)}}

def motion_families(visual):
    """The set of visual.variety.motion values this graphic actually contains (MOTION_FAMILY). Fixed templates read
    their technique names from longform_graphic.choreography itself (lazy import: longform_graphic imports this module)."""
    if visual['template']=='authored':
        found={f for cue in visual['motion_cues'] for f in MOTION_FAMILY['cue'][cue['effect']]}
    else:
        from longform_graphic import choreography
        # Techniques do not depend on timing; one placeholder event feeds the generic stagger branch.
        _script,report=choreography(visual['template'],[('#graphic',0.0)],10.0,visual)
        found={f for cue in report['cues'] for f in MOTION_FAMILY['technique'][cue['technique']]}
    for name,families in MOTION_FAMILY['scene'].items():
        spec=visual.get(name)
        # A content-scope glitch only shakes the labels/captions layer; it still moves on screen.
        if spec is not None:found.update(families)
    return sorted(found) or ['still']

def render_key_visual(visual):
    """렌더 단계 열쇠용 visual — variety 의 «값» 은 렌더에 쓰이지 않고 «있음» 만 쓰인다(opened_motion). 값까지 열쇠에 넣으면 선언만 고쳐도
    그래픽을 다시 굽고(실측 장면당 236초) hyperframes 출력이 바이트가 달라 agy 검수까지 다시 묻는다(2026-10-09 실 E2E). 있음만 남긴다.
    variety 가 없는 옛 visual 은 그대로(같은 객체) — 옛 작업의 열쇠는 바뀌지 않는다.

    영상 노드의 video_treatment.local_focus.contract_key 도 열쇠에서 뺀다(2026-10-21 인물형 롱폼 신고 — 한 컷의 in 만 고쳐
    다시 seed 했더니 b02~b30 그림을 전부 다시 구웠다 · 약 1시간 45분). 그 값은 «편 전체» 피사체 일감의 지문이라 컷 하나만
    바뀌어도 모든 영상 노드에서 같이 바뀐다. 렌더가 쓰는 것은 컷마다의 focus_key·영수증 sha256(그대로 열쇠에 남는다)이고,
    contract_key 는 굽기 직전 검사(local_focus.verify_render_receipt)가 계약 파일을 찾는 자리일 뿐이다 — 단계를 다시 쓸 때는
    그 검사가 돌 일이 없고, 새로 구울 때는 원래 visual(값 그대로)이 검사를 받는다. 영상 노드의 자리는 서버
    longform/treatment.video_cuts 와 같다(video 는 visual 자신 · montage 는 shots · graphic 은 objects)."""
    keyed = visual if 'variety' not in visual else {**visual, 'variety': True}
    kind = visual.get('kind')
    if kind == 'video':
        node = _focus_key_node(visual)
        if node is not visual:
            keyed = {**keyed, 'video_treatment': node['video_treatment']}
    elif kind in ('montage', 'graphic'):
        field = 'shots' if kind == 'montage' else 'objects'
        nodes = visual.get(field)
        if isinstance(nodes, list):
            stripped = [_focus_key_node(n) for n in nodes]
            if any(a is not b for a, b in zip(stripped, nodes)):
                keyed = {**keyed, field: stripped}
    return keyed


def _focus_key_node(node):
    """영상 노드 하나 — local_focus 에 contract_key 가 있으면 그것만 뺀 사본, 없으면 같은 객체(render_key_visual)."""
    if not isinstance(node, dict):
        return node
    treatment = node.get('video_treatment')
    proof = treatment.get('local_focus') if isinstance(treatment, dict) else None
    if not isinstance(proof, dict) or 'contract_key' not in proof:
        return node
    return {**node, 'video_treatment': {**treatment, 'local_focus': {k: v for k, v in proof.items() if k != 'contract_key'}}}


def opened_motion(visual):
    """B2 marker: the authored entrance values (distance, pop from_scale/ease, the wider ease list) are read only
    when the graphic carries visual.variety. unique-v1 makes it mandatory on every graphic and validate() refuses it
    without unique-v1, so the marker equals the plan's graphic_variety and travels with the visual itself (the
    renderer and the layout cache see only the visual). Without it the pre-B2 behaviour is kept exactly."""
    return 'variety' in visual

def authored_value(cue,key,opened):
    """rise/slide distance and pop from_scale: the cue's own value when opened, else the pre-B2 constant."""
    default=MOTION_DEFAULTS[cue['effect']+'_'+key]
    return cue.get(key,default) if opened else default

def cue_ease(cue,opened=True):
    """The ease the renderer actually applies to an authored cue (None: the effect draws its own curve)."""
    effect=cue['effect']
    if effect in ('draw','pattern_pan'):return 'none'
    if effect in ('count','brush_reveal','paper_reveal','object_glitch'):return None
    if effect=='pop':return cue.get('ease',MOTION_DEFAULTS['pop_ease']) if opened else MOTION_DEFAULTS['pop_ease']
    if effect in ('pan','zoom','text_wipe','gear_spin'):return cue.get('ease','none')
    return cue.get('ease','power2.out')

def entrance_value(cue):
    """The main entrance value with the renderer default filled in (B2 §3-6)."""
    effect=cue['effect']
    if effect=='rise':return authored_value(cue,'distance',True)
    if effect=='slide':return cue.get('direction',1)*authored_value(cue,'distance',True)
    if effect=='pop':return authored_value(cue,'from_scale',True)
    if effect=='fade':return cue.get('from',0)
    if effect=='text_wipe':return cue.get('axis','y')
    if effect=='polygon_wipe':return len(cue['from_points'])
    return None

def motion_values(cue):
    """MOTION_VALUE_KEYS of a cue, with the entrance defaults the renderer applies filled in."""
    values={key:cue.get(key) for key in MOTION_VALUE_KEYS}
    if cue['effect'] in ('rise','slide'):values['distance']=authored_value(cue,'distance',True)
    if cue['effect']=='pop':values['from_scale']=authored_value(cue,'from_scale',True)
    return [values[key] for key in MOTION_VALUE_KEYS]

class SourceIntervals:
    """Earlier source ranges per media sha256: «does the open range (start,end) overlap any earlier one?» by bisection.

    Ranges that strictly overlap are merged (touching ones are not), so the stored ranges stay disjoint and
    sorted. For positive-length ranges (every caller checks end>start first) an open range meets the union
    iff it meets one member — the same answer as the former any(start<b and end>a for a,b in ranges) scan
    over every earlier range, without rescanning the episode list per shot (6-00).
    """
    def __init__(self):self.rows={}
    def add(self,sha,start,end):
        """Record the range; return whether it overlapped an earlier range of the same source."""
        from bisect import bisect_left,bisect_right
        starts,ends=self.rows.setdefault(sha,([],[]))
        # Stored j strictly overlaps iff starts[j]<end and ends[j]>start; both lists are sorted.
        lo=bisect_right(ends,start);hi=bisect_left(starts,end)
        if lo<hi:starts[lo:hi]=[min(start,starts[lo])];ends[lo:hi]=[max(end,ends[hi-1])]
        else:starts.insert(lo,start);ends.insert(lo,end)
        return lo<hi

def validate_brand_position(position):
    need(isinstance(position,list) and len(position)==2,'브랜드 위치는 [x,y] 좌표입니다.')
    for value,limit in zip(position,(1919,1079)):
        need(type(value) is int and 0<=value<=limit,'브랜드 좌표는 화면 안의 정수입니다.')
    return position

def validate_styles(styles):
    need(isinstance(styles,dict) and set(styles)<= {'caption','overlay_lock'},'새 엔진 스타일은 caption과 overlay_lock으로 지정하세요.')
    if 'overlay_lock' in styles:
        need(type(styles['overlay_lock']) is bool,'overlay_lock은 참/거짓이어야 합니다.')
    caption=styles.get('caption',{})
    need(isinstance(caption,dict) and set(caption)<=CAPTION_FIELDS,'지원되지 않은 자막 스타일 필드가 있습니다.')
    for key,value in caption.items():
        if key in ('font','font_file'):text(value,'자막 글꼴',2000)
        elif key.endswith('color'):need(bool(re.fullmatch('#[0-9a-fA-F]{6}',str(value))),'자막 색은 #RRGGBB 형식입니다.')
        else:
            lo,hi={'font_size':(1,500),'outline_width':(0,40),'background_opacity':(0,1),'x':(0,1920),'y':(0,1080)}[key]
            numeric(value,'자막 '+key,lo,hi)
    return styles

def need(ok, message, code='invalid_plan'):
    if not ok:raise ProductionError(code,message,action='edit_plan')

def text(value, label, maximum=2000):
    need(isinstance(value,str) and value.strip() and len(value)<=maximum,label+'가 비었거나 너무 깁니다.')
    return value

def numeric(value,label,low=0,high=86400):
    need(type(value) in (int,float) and math.isfinite(value) and low<=value<=high,label+' 범위 오류')
    return value

def validate_music(music, sounds):
    need(isinstance(music,dict),'배경음악 설정은 사전이어야 합니다.')
    segmented='segments' in music
    if segmented:
        need('asset' not in music,'단일 음악과 구간 음악을 동시에 지정하지 마세요.')
        cues=music['segments']
        need(isinstance(cues,list) and 1<=len(cues)<=32,'배경음악 구간은 1–32개입니다.')
    else:cues=[music]
    for cue in cues:
        need(isinstance(cue,dict) and cue.get('asset') in sounds,'배경음악은 등록된 sound_assets를 사용하세요.')
        numeric(cue.get('in'),'배경음악 원본 시작',0,86400)
        numeric(cue.get('gain_db'),'배경음악 게인',-60,0)
        fin=numeric(cue.get('fade_in'),'배경음악 시작 페이드',.01,60)
        fout=numeric(cue.get('fade_out'),'배경음악 끝 페이드',.01,60)
        text(cue.get('reason'),'배경음악 배정 이유');text(cue.get('reference'),'배경음악 편집 판단 근거')
        if segmented:
            start=numeric(cue.get('start'),'배경음악 타임라인 시작')
            end=numeric(cue.get('end'),'배경음악 타임라인 끝')
            need(end>start and fin+fout<=end-start,'배경음악 구간 길이/페이드가 잘못됐습니다.')
    return music

def validate_requested_duration(plan,requested):
    # Older local projects without a request field retain their explicit plan.
    if requested is None:return
    numeric(requested,'요청한 전체 목표 길이',300,2400)
    need(abs(plan['target_seconds']-requested)<=.001,
         f"요청한 목표 {requested:g}초와 제작표 목표 {plan['target_seconds']:g}초가 다릅니다. 대본·제작표를 수정하고 기존 음성을 보존하세요.",
         'requested_duration_mismatch')


def caption_display(value):
    # Narration keeps its punctuation and paid identity. Screen captions omit
    # sentence periods; decimal points remain part of the displayed number.
    return re.sub(r'(?<!\d)\.|\.(?!\d)', '', value).strip()

def display_highlights(highlights):
    """Caption highlight terms in the form the screen shows (2026-10-17 신고 #119): the same caption_display rule the
    caption text goes through, so «S.M.기획» finds the displayed «SM기획». The one rule for both the contract
    (checked_captions) and the drawing (longform_render.Layout.caption). Non-string terms pass through untouched for
    the contract to report."""
    out=[]
    for item in highlights if isinstance(highlights,list) else ():
        term=item.get('text') if isinstance(item,dict) else item
        if isinstance(term,str):
            shown=caption_display(term)
            item={**item,'text':shown} if isinstance(item,dict) else shown
        out.append(item)
    return out

def caption_ranges(narration,cards):
    """Narration character range of every authored caption card, computed by code (2026-10-17 신고 #118).

    start is always the previous card's end (the first is 0) and the last card always ends at len(narration) — they
    carry no choice, so an author's off-by-one never stops a job. A card whose authored start/end already satisfy the
    contract (start == previous end, end on a word boundary, room left for the following cards) keeps them exactly,
    so plans that ran before keep byte-identical timings. Otherwise the end is the narration word where the card's
    display text ends (letters and digits compared in order, spaces and punctuation ignored); if the display text is
    written differently from the narration (1992년 / 천구백구십이년), the authored end snapped to the nearest word end
    (the later on a tie), and with no usable end, the share of the remaining narration in proportion to the remaining
    cards' display length. One forward pass over the words (suffix sums for the shares). → [(start, end, how)]; how is
    'authored', 'matched', 'snapped', 'shared' or 'last' (the last card takes the rest). Fewer narration words than cards is the only violation left."""
    from bisect import bisect_right
    words=[m.span() for m in re.finditer(r'\S+',narration)]
    ends=[b for _,b in words]
    need(len(words)>=len(cards),f'자막 카드 {len(cards)}개가 대본 낱말 {len(words)}개보다 많습니다. 카드를 합치세요.','caption_card_count')
    def keys(value):return [c.lower() for c in value if c.isalnum()]
    shown=[keys(card.get('text')) if isinstance(card,dict) and isinstance(card.get('text'),str) else [] for card in cards]
    weights=[max(1,len(k)) for k in shown];rest=[0]*(len(cards)+1)
    for i in range(len(cards)-1,-1,-1):rest[i]=rest[i+1]+weights[i]
    cursor=0;taken=0;out=[]
    for i,card in enumerate(cards):
        start=cursor;last=i==len(cards)-1
        highest=len(words)-(len(cards)-i)          # the last word index this card may end on
        a=card.get('start') if isinstance(card,dict) else None;z=card.get('end') if isinstance(card,dict) else None
        if (type(a) is int and type(z) is int and a==cursor and cursor<z<=len(narration)
                and (z==len(narration) or narration[z-1].isspace() or narration[z].isspace())
                and (z==len(narration) if last else bisect_right(ends,z)-1<=highest)
                and narration[start:z].strip()):
            end,how=z,'authored'
        elif last:end,how=len(narration),'last'
        else:
            word=None;want=shown[i];at=0
            if want:
                for index in range(taken,len(words)):
                    for ch in narration[words[index][0]:words[index][1]]:
                        if not ch.isalnum():continue
                        if ch.lower()!=want[at]:break
                        at+=1
                        if at==len(want):break
                    else:continue
                    if at==len(want):word=index
                    break
            how='matched'
            if word is None:
                if type(z) is int and cursor<z<=len(narration):
                    target,how=z,'snapped'
                else:
                    target,how=cursor+(len(narration)-cursor)*weights[i]/rest[i],'shared'
                k=bisect_right(ends,target)
                below=k-1 if k>0 else None
                word=k if below is None or (k<len(ends) and ends[k]-target<=target-ends[below]) else below
            word=min(max(word,taken),highest);end=words[word][1]
        out.append((start,end,how))
        taken=bisect_right(ends,end);cursor=end
    return out

def checked_captions(block):
    narration=block['text'];cards=block.get('captions')
    need(isinstance(cards,list) and cards,
         '의미 단위로 작성한 captions가 필요합니다. 화면 폭으로 문장을 자동 분할하지 않습니다: '+block.get('id',''),
         'caption_plan_missing')
    for card in cards:need(isinstance(card,dict),'자막 카드 형식 오류')
    result=[]
    for card,(start,end,how) in zip(cards,caption_ranges(narration,cards)):
        if 'style' in card:
            validate_styles({'caption':card['style']})
            if 'font_file' in card['style']:
                need(card['style']['font_file'] in FONT_NAMES,'카드별 자막은 배포 글꼴을 지정하세요.','caption_font_missing')
        if 'motion' in card:
            motion=card['motion']
            need(isinstance(motion,dict) and set(motion)=={'kind','duration','blur_px','reference'},'자막 진입 모션 필드를 확인하세요.')
            need(motion['kind']=='horizontal_reveal','지원하지 않는 자막 진입 모션입니다.')
            numeric(motion['duration'],'자막 진입 길이',1/60,2)
            numeric(motion['blur_px'],'자막 수평 번짐',0,120)
            text(motion['reference'],'자막 모션 관찰 근거')
        raw=text(card.get('text'),'표시 자막',200)
        # A range the code placed by share/snap is not the author's; judge the sentence mix on what the author wrote.
        source=narration[start:end].strip() if how in ('authored','matched') else raw
        need(not re.search(r'[.!?。！？][”’\"\']?\s+\S',source),
             '끝난 문장과 다음 문장을 같은 자막에 섞지 마세요: '+source, 'caption_sentence_merge')
        display=caption_display(raw)
        need(display and '\n' not in display and '\r' not in display,
             '자막은 의미 단위 한 줄로 작성하세요.', 'caption_multiline')
        row={**card,'start':start,'end':end,'text':display}
        if (card.get('start'),card.get('end'))!=(start,end):
            row['range_note']=f'자막 «{display}» 의 대본 범위를 문자 {start}–{end}로 맞췄습니다('+{'matched':'표시 글로 찾음','snapped':'가까운 낱말 끝','shared':'남은 대본을 표시 길이로 나눔','last':'끝 카드가 남은 대본을 맡음'}[how]+').'
        result.append(row)
    highlights=block.get('highlights',[])
    need(isinstance(highlights,list),'자막 강조는 목록이어야 합니다.','caption_highlight')
    assigned={}
    for item in display_highlights(highlights):
        term=item.get('text') if isinstance(item,dict) else item
        text(term,'자막 강조 단어',80)
        color=item.get('color','#00FCA6') if isinstance(item,dict) else '#00FCA6'
        need(isinstance(color,str) and bool(re.fullmatch('#[0-9a-fA-F]{6}',color)),
             '자막 강조색은 #RRGGBB여야 합니다.','caption_highlight')
        size=item.get('font_size') if isinstance(item,dict) else None
        if size is not None:
            need(type(size) is int and 1<=size<=500,'강조 글자 크기는 1~500 정수여야 합니다.','caption_highlight')
        signature=(color.lower(),size)
        matches=0
        for index,card in enumerate(result):
            start=0
            while (at:=card['text'].find(term,start))>=0:
                for pos in range(at,at+len(term)):
                    key=(index,pos)
                    need(key not in assigned or assigned[key]==signature,
                         '같은 자막 글자에 다른 강조색 또는 크기가 겹칩니다.','caption_highlight')
                    assigned[key]=signature
                matches+=1;start=at+len(term)
        need(matches>0,'강조 단어가 실제 표시 자막에 없습니다: '+term,'caption_highlight_unused')
    return result

def validate_atlas(asset):
    """Only declared, disjoint drawn panels can have separate identities."""
    regions=asset.get('atlas_regions')
    if regions is None:return
    need(asset.get('origin')=='illustration','실제 기록 사진을 삽화 아틀라스로 분할할 수 없습니다.')
    need(isinstance(regions,dict) and 2<=len(regions)<=32,'삽화 아틀라스 영역은 2~32개여야 합니다.')
    prior=[]
    for name,box in regions.items():
        text(name,'삽화 영역 이름',80);validate_crop(box)
        x1,y1,x2,y2=box
        need(all(x2<=a or c<=x1 or y2<=b or d<=y1 for a,b,c,d in prior),
             '삽화 아틀라스 영역이 서로 겹칩니다.')
        prior.append(box)

def image_identity(media,node):
    asset=media[node['media']];sha=asset['sha256'];region=node.get('atlas_region')
    if region is None:return sha
    validate_atlas(asset)
    regions=asset.get('atlas_regions',{})
    need(region in regions,'등록되지 않은 삽화 아틀라스 영역입니다.')
    crop=node.get('crop');need(crop is not None,'삽화 영역에는 실제 crop이 필요합니다.');validate_crop(crop)
    x1,y1,x2,y2=regions[region];a,b,c,d=crop
    need(x1<=a<c<=x2 and y1<=b<d<=y2,'삽화 crop이 선언한 영역을 벗어납니다.')
    # Two crops of one panel stay the same source, even at different zooms.
    return sha+':panel:'+region

def graphic_visibility(visual, target):
    """Positive-opacity spans in the authored timeline, including parent groups.

    Use the same initial/from/to semantics as authored_motion. This describes
    visibility, not a claim that an object is unobstructed in the final frame.
    """
    # Scene-local: scans one scene's objects (<= 30) and cues (<= 80) — validate_authored caps.
    node=next((n for n in visual.get('objects',[]) if n['id']==target),{})
    from longform_groups import chain
    groups=visual.get('groups',[])
    targets=chain(groups,target) if any(g['id']==target for g in groups) else [target]+chain(groups,node.get('group'))
    tracks=[];bounds={0,1}
    for name in targets:
        cues=sorted((c for c in visual['motion_cues'] if c['target']==name
                     and c['effect'] in ('fade','rise','slide','pop')),key=lambda c:c['at'])
        for c in cues:bounds.update((c['at'],c['at']+c['duration']))
        tracks.append(cues)
    def opacity(cues,t):
        value=(cues[0].get('from',0) if cues[0]['effect']=='fade' else 0) if cues else 1
        for c in cues:
            if t<c['at']:break
            a=c.get('from',0) if c['effect']=='fade' else 0
            b=c.get('to',1) if c['effect']=='fade' else 1
            progress=min(1,(t-c['at'])/c['duration'])
            value=a+(b-a)*progress
        return value
    points=sorted(bounds);spans=[]
    for a,b in zip(points,points[1:]):
        if a<b and all(opacity(track,(a+b)/2)>0 for track in tracks):
            if spans and spans[-1][1]==a:spans[-1][1]=b
            else:spans.append([a,b])
    iris=visual.get('iris_handoff')
    if iris:
        # The renderer owns these group opacity changes outside motion_cues.
        # Preserve child fades while intersecting with the covered source swap.
        lo=iris['swap'] if iris['incoming'] in targets else 0
        hi=iris['swap'] if iris['outgoing'] in targets else 1
        spans=[[max(a,lo),min(b,hi)] for a,b in spans if max(a,lo)<min(b,hi)]
    return spans


def validate_graphic_continuity(visual, media):
    """Do not disguise repeated sentence panels as distinct image objects."""
    from itertools import combinations
    from math import isclose
    rows=[]
    for index,node in enumerate(visual['objects']):
        if node['kind']!='image':continue
        # Verified decorative paper may paint both canvas and a clipped scene.
        # Content photographs and atlases still use the strict reentry check.
        if background_texture(media,node,index,visual):continue
        identity=(image_identity(media,node),tuple(node.get('crop') or []))
        rows.append((identity,node,graphic_visibility(visual,node['id'])))
    # Pairwise over one scene's image objects (<= 30, validate_authored), not the episode.
    for (identity,a,left),(other,b,right) in combinations(rows,2):
        if identity!=other or not left or not right:continue
        concurrent=any(max(x,u)<min(y,v) for x,y in left for u,v in right)
        same_frame=a['box']==b['box'] and a.get('fit','cover' if a.get('crop') else 'contain')==b.get('fit','cover' if b.get('crop') else 'contain')
        need(concurrent and (not same_frame or left==right),
             f"같은 그림을 문장별 객체로 다시 등장시키지 마세요: {a['id']} → {b['id']}. "
             '한 객체의 연속 움직임으로 유지하거나 실제로 다른 자료/장면을 배정하세요.',
             'graphic_image_reentry')
    zooms={}
    for cue in visual['motion_cues']:
        if cue['effect']=='zoom':zooms.setdefault(cue['target'],[]).append(cue)
    for target,cues in zooms.items():
        spans=graphic_visibility(visual,target)
        ordered=sorted(cues,key=lambda c:c['at'])
        for prior,cue in zip(ordered,ordered[1:]):
            if not any(a<cue['at']<b for a,b in spans):continue
            need(prior['at']+prior['duration']<=cue['at']
                 and isclose(prior['scale'],cue.get('from_scale',1)),
                 f'{target}: 보이는 그림의 확대가 중간에 되돌아가거나 겹칩니다. 끝 배율에서 이어 주세요.',
                 'graphic_motion_discontinuity')


def validate_scene_handoffs(blocks,voices=None):
    for i,block in enumerate(blocks):
        visual=block.get('visual',{});spec=visual.get('scene_handoff')
        if spec is None:continue
        need(isinstance(spec,dict) and spec.get('kind')=='shatter','장면 사이 전환은 shatter 명세가 필요합니다.')
        need(visual.get('kind')=='graphic' and visual.get('template')=='authored','장면 사이 파편 퇴장은 맞춤 그래픽에 지정하세요.')
        need(i+1<len(blocks),'마지막 장면에는 다음 장면 파편 전환을 지정할 수 없습니다.')
        n=spec.get('frames');need(type(n) is int and 2<=n<=180,'장면 파편 전환은 2~180프레임입니다.')
        seed=spec.get('seed',17);need(type(seed) is int and 0<=seed<=99999,'장면 파편 seed 범위 오류')
        text(spec.get('reference'),'장면 파편 직접 관찰 근거',1000)
        if voices is not None:
            need(n<voices[i]['frames'] and n<voices[i+1]['frames'],'장면 파편은 양쪽 장면보다 짧아야 합니다.')


def background_texture(media,node,index,visual=None):
    """Explicit decorative canvas, never an exemption for a content image."""
    asset=media[node['media']]
    declared=asset.get('role')=='background_texture' or node.get('role')=='background_texture'
    if not declared:return False
    scope=node.get('texture_scope','canvas')
    need(scope in ('canvas','panel'),'장식 질감 범위는 canvas 또는 panel입니다.','background_texture_role')
    first_layer=index==0
    panel=False
    if visual and node.get('group'):
        gid=node['group']
        # Scene-local: groups <= 8, objects <= 30 (validate_authored caps).
        group=next((g for g in visual.get('groups',[]) if g['id']==gid),{})
        members=[n for n in visual['objects'] if n.get('group')==gid]
        first_layer=first_layer or (group.get('clip')=='rounded' and bool(members) and members[0] is node)
        # A panel is an explicitly declared decorative surface, not a content
        # photo exemption. Keep its source-role and reuse evidence intact.
        box=node.get('box',[])
        if scope=='panel' and group and members and members[0] is node and len(box)==4:
            x,y,w,h=box
            panel=(all(isinstance(n,(int,float)) and not isinstance(n,bool) for n in box)
                   and 0<=x<1920 and 0<=y<1080 and w>0 and h>0
                   and x+w<=1920 and y+h<=1080)
    need(asset.get('role')==node.get('role')=='background_texture'
         and asset.get('origin')=='illustration' and node.get('kind')=='image'
         and ((scope=='canvas' and first_layer and node.get('box')==[0,0,1920,1080]) or panel)
         and node.get('fit','cover')=='cover'
         and not any(k in node for k in ('crop','atlas_region','tile_scale'))
         and not asset.get('atlas_regions'),
         '질감은 삽화 소재와 이미지에 함께 선언하세요. canvas는 첫 전체 화면 배경, panel은 화면 안에 있는 묶음의 첫 장식 이미지입니다. 사진·크롭·아틀라스에는 사용할 수 없습니다.',
         'background_texture_role')
    return True

def visual_diversity(plan,*,execution=False):
    """Editorial release policy, not a measured statistic of the reference channel.

    A free-text repeat reason cannot authorize a source carousel or an episode
    built from one infographic layout. This does not replace semantic review.
    """
    from collections import Counter
    assets=Counter();graphics=[]
    previous=None
    for block in plan['blocks']:
        shot=block['visual']
        continued=set()
        if 'continues_photo_from' in shot:
            need(previous is not None and shot['continues_photo_from']==previous['id'],
                 '사진 연속 표시는 바로 앞 블록을 가리켜야 합니다.','photo_continuity')
            prior=previous['visual']
            need(shot['kind']=='photo' and prior['kind'] in ('photo','montage'),
                 '사진 연속 표시는 사진 또는 몽타주 끝 사진에서 이어야 합니다.','photo_continuity')
            sha=plan['media'][shot['media'][0]]['sha256']
            if prior['kind']=='photo':
                need(prior.get('motion','in') in ('in','out') and shot.get('motion','in') in ('in','out')
                     and 'max_scale' in prior and 'max_scale' in shot,
                     '연속 사진은 양쪽 배율 범위를 명시하세요.','photo_continuity')
                end_scale=prior['max_scale'] if prior.get('motion','in')=='in' else prior.get('min_scale',1)
                start_scale=shot.get('min_scale',1) if shot.get('motion','in')=='in' else shot['max_scale']
                need(abs(end_scale-start_scale)<1e-9 and prior.get('fit','auto')==shot.get('fit','auto'),
                     '연속 사진의 끝/시작 배율과 채움 방식이 다릅니다.','photo_continuity')
                source_id=prior['media'][0];crop=prior.get('crop')
            else:
                tail=prior['shots'][-1]
                need(tail['kind']=='photo' and tail.get('motion','in')=='still' and not tail.get('camera')
                     and not tail.get('paired_photo')
                     and tail.get('transition',{}).get('kind','cut')=='cut'
                     and shot.get('motion','in')=='in' and shot.get('fit','auto')=='auto'
                     and shot.get('min_scale',1)==1,
                     '연속 사진은 같은 크기의 정지 끝에서 확대 시작으로 이어져야 합니다.','photo_continuity')
                source_id=tail['media'];crop=tail.get('crop')
            need(sha==plan['media'][source_id]['sha256'] and shot.get('crop')==crop,
                 '연속 사진의 원본과 자르기 영역이 다릅니다.','photo_continuity')
            continued.add(sha)
        if shot['kind']=='montage':
            photo_ids={item['media'] for item in shot['shots'] if item['kind']=='photo'}
            photo_ids.update(item['paired_photo']['media'] for item in shot['shots']
                             if item['kind']=='photo' and item.get('paired_photo'))
            assets.update({plan['media'][mid]['sha256'] for mid in photo_ids})
        elif shot['kind']=='graphic' and shot.get('template')=='authored':
            validate_graphic_continuity(shot,plan['media'])
            # Moving archive intervals are checked separately in validate().
            # Count only visible still images here, as with video/montage.
            assets.update({image_identity(plan['media'],node)
                           for index,node in enumerate(shot['objects']) if node['kind']=='image'
                           and not background_texture(plan['media'],node,index,shot)})
        elif shot['kind']!='video':
            assets.update({plan['media'][mid]['sha256'] for mid in shot.get('media',[])}-continued)
        if shot['kind']=='graphic':
            if shot['template']=='authored':
                # Changing a label, source filename or layout ID is not a new
                # composition. Compare geometry and action roles instead.
                nodes=shot['objects'];indices={n['id']:i for i,n in enumerate(nodes)}
                groups=shot.get('groups',[]);indices.update({g['id']:len(nodes)+i for i,g in enumerate(groups)})
                geometry=[(n['kind'],n['box'],indices.get(n.get('group'))) for n in nodes]
                geometry.extend(('group',g.get('origin',[.5,.5])) for g in groups)
                geometry.extend(('parent',indices[g['id']],indices[g['parent']]) for g in groups if g.get('parent'))
                actions=[(indices[c['target']],c['effect']) for c in shot['motion_cues']]
                graphics.append('authored:'+json.dumps([geometry,actions],sort_keys=True))
            else:graphics.append(shot['template'])
        previous=block
    overused=[sha for sha,count in assets.items() if count>2]
    need(not overused,'같은 자료를 세 장면 이상 순환 사용하지 마세요. 다른 자료/구도로 제작표를 다시 구성하세요.', 'media_overused')
    counts=Counter(graphics)
    if plan.get('graphic_variety')==GRAPHIC_VARIETY:
        # The stronger one-pass uniqueness checks replace the distribution check (no second check of the same thing).
        # They run once, on the authored plan before paid voice. The execution plan (conform_plan recomputes at/
        # duration from the real voice) is not re-judged: a duplicate check that could flip the verdict after TTS.
        if not execution:graphic_variety_unique(plan)
    elif len(graphics)>=6:
        needed=min(6,max(3,len(graphics)//6))
        need(len(counts)>=needed and max(counts.values())*2<=len(graphics),
             '인포그래픽이 한 형태에 몰려 있습니다. 내용에 맞는 서로 다른 구도를 설계하세요.', 'graphic_monotony')
        need(not any(a==b==c for a,b,c in zip(graphics,graphics[1:],graphics[2:])),
             '사진을 끼워 넣어도 같은 인포그래픽 형태를 세 번 연속 반복할 수 없습니다.', 'graphic_monotony')
    return {'media_uses':dict(assets),'graphic_templates':dict(counts),
            'scope':'exact source identity and structural layout distribution; semantic/editorial review still required'}

SCENE_EFFECTS=('light_leak','glitch','ink_cover','tear_cover','brush_cover','grain_wipe','negative_splatter','edge_strobe','scene_handoff','iris_handoff')
SCENE_EFFECT_DEFAULTS={'light_leak':'smooth','glitch':'strips'}
PAIRED_SCENE_EFFECTS=('light_leak','glitch','grain_wipe')
ENTRANCE_EFFECTS=('rise','slide','pop','fade','draw','paper_reveal','brush_reveal','text_wipe','polygon_wipe','count')

def graphic_variety_unique(plan):
    """unique-v1 (B2 §3): every graphic differs from every other one on eight axes.

    One pass over the graphic blocks with dict lookups — no pairwise comparison (6-00). Each table maps a
    fingerprint to the first block that used it, so a collision names both blocks.
    """
    media=plan['media']
    tables={}
    def once(table,key,bid,what):
        other=tables.setdefault(table,{}).setdefault(key,bid)
        need(other==bid,f'그래픽 {other} 와(과) {bid} 의 {what}이(가) 같습니다. unique-v1 제작표는 영상 전체에서 그래픽마다 서로 다르게 만드세요.',
             'graphic_variety_unique')
    def rounded(value,digits=3):
        return round(value,digits) if isinstance(value,(int,float)) and not isinstance(value,bool) else value
    def fingerprint(rows):
        # Cues may hold None beside numbers; compare canonical JSON strings, not mixed tuples.
        return tuple(sorted(json.dumps(row,ensure_ascii=False) for row in rows))
    previous=None;prior_block=None;motion_miss=None
    for block in plan['blocks']:
        visual=block['visual']
        if visual['kind']!='graphic':
            prior_block=block;continue
        bid=block['id'];variety=visual.get('variety')
        need(isinstance(variety,dict) and set(variety)==set(VARIETY_VOCAB)
             and all(variety[axis] in VARIETY_VOCAB[axis] for axis in VARIETY_VOCAB),
             f'{bid}: unique-v1 그래픽은 visual.variety={{expression,texture,motion}} 세 칸을 정해진 어휘로 지정하세요. '+VARIETY_CHOICES,
             'graphic_variety_unique')
        # 1. expression·texture·motion combination
        once('combo',(variety['expression'],variety['texture'],variety['motion']),bid,'표현·질감·모션 조합')
        # 2. adjacent graphics differ on all three axes
        if previous is not None:
            same=[VARIETY_AXIS_NAMES[axis] for axis in VARIETY_AXIS_NAMES if previous[1][axis]==variety[axis]]
            need(not same,f'이웃한 그래픽 {previous[0]} 와(과) {bid} 의 {"·".join(same)}이(가) 같습니다. 바로 이웃한 그래픽은 표현·질감·모션이 모두 달라야 합니다.',
                 'graphic_variety_unique')
        previous=(bid,variety)
        template=visual['template']
        if template=='authored':
            objects=visual['objects'];first=objects[0]
            if first['kind'] in ('image','video') and first['box']==[0,0,1920,1080]:
                background=media[first['media']]['sha256']+(':'+str(int(first['in'])) if first['kind']=='video' else '')
                foreground=objects[1:]
            else:
                background='theme:'+visual.get('theme','charcoal');foreground=objects
            kinds={node['id']:node['kind'] for node in objects}
            cues=visual['motion_cues']
            motion=(fingerprint([cue['effect'],cue_ease(cue),[rounded(v) for v in motion_values(cue)],
                                 rounded(cue['at'],2),rounded(cue['duration'],2),kinds.get(cue['target'],'group')] for cue in cues),
                    any('texture_cadence' in node for node in objects),'iris_handoff' in visual)
            entrance=fingerprint({(cue['effect'],cue_ease(cue) or '-',rounded(entrance_value(cue)))
                                  for cue in cues if cue['effect'] in ENTRANCE_EFFECTS}) or ('none',)
            layout=tuple(sorted((node['kind'],tuple(round(v/48) for v in node['box'])) for node in foreground))
        else:
            # 4. each fixed template once
            once('template',template,bid,'고정 틀('+template+')')
            background='theme:'+TEMPLATE_THEMES[template]
            motion=entrance=layout=('template',template)
        # 3. background asset or theme
        once('background',background,bid,'바탕(질감·배경 자산)')
        # 5–7. motion, entrance and layout fingerprints
        once('motion',motion,bid,'모션 지문(효과·이징·값·시점)')
        once('entrance',entrance,bid,'등장 방식(효과·이징·주 값)')
        once('layout',layout,bid,'배치(48px 격자 위 객체 종류·위치·크기)')
        # 8. scene effects; an «in» that completes the previous block's «out» (any kind — a video→graphic light
        # leak is one transition) is the same transition and is not counted again.
        for name in SCENE_EFFECTS:
            spec=visual.get(name)
            if spec is None:continue
            if (name in PAIRED_SCENE_EFFECTS and prior_block is not None and spec.get('phase')=='in'
                    and prior_block['visual'].get(name,{}).get('phase')=='out'):continue
            profile=spec.get('profile',spec.get('kind',SCENE_EFFECT_DEFAULTS.get(name))) if isinstance(spec,dict) else None
            once('scene',(name,profile),bid,f'장면 효과({name}·{profile})')
        # 9. declared motion is one the graphic contains (MOTION_FAMILY) — reported after rules 1–8 so a collision
        # between two blocks is named first.
        derived=motion_families(visual)
        if variety['motion'] not in derived and motion_miss is None:motion_miss=(bid,variety['motion'],derived)
        prior_block=block
    if motion_miss is not None:
        bid,declared,derived=motion_miss
        need(False,f'{bid}: 선언한 모션 {declared} 이(가) 이 그래픽의 실제 움직임(motion_cues·장면 효과·고정 틀 안무)에서 나오지 않습니다. '
                   f'이 그래픽에서 나오는 모션 값: {"·".join(derived)} — visual.variety.motion 을 그중 하나로 고치거나 그 움직임을 실제로 넣으세요.',
             'graphic_variety_motion')

def gathered(found):
    """One ProductionError carrying every distinct violation found by one validate() pass (2026-10-17 신고 #117 · 23명).

    The first violation keeps its code and action, so callers and tests that branch on the code are unchanged; a single
    violation is returned as-is (same exception, same text). Several are listed in one message and in .violations —
    the author fixes them all at once instead of learning one rule per failed run."""
    unique=[];keys=set()
    for error in found:
        key=(error.code,str(error))
        if key not in keys:keys.add(key);unique.append(error)
    if len(unique)==1:return unique[0]
    first=unique[0]
    error=ProductionError(first.code,f'제작표에서 고칠 곳이 {len(unique)}곳입니다 — 한 번에 모두 고친 뒤 다시 보내세요: '
                          +' / '.join(f'{index}) {item}' for index,item in enumerate(unique,1)),
                          action=first.action,retryable=first.retryable)
    error.violations=[item.record() for item in unique]
    return error

def validate(plan,*,execution=False):
    """execution=True: the conformed execution plan (longform_engine after paid voice). It skips only the unique-v1
    judgement, which ran once on the authored plan; every structural check still runs.

    2026-10-17 신고 #117: every independent part (each reference, media, sound, block identity / picture / voice /
    captions, and each episode-level check) is checked even after an earlier part failed, and all violations are raised
    together (gathered). Within one part the first violation stops that part only. Parts the rest depends on (schema,
    reference list, media/sound dictionaries, block list) stop the pass. A non-contract exception in a later part that
    reads a value already reported as malformed raises the gathered report (that report explains it); with nothing
    reported it propagates unchanged."""
    from longform_video_treatment import validate_tree
    found=[]
    def part(step,*args,essential=False):
        try:
            step(*args);return True
        except ProductionError as error:
            found.append(error)
            if essential:raise gathered(found) from None
            return False
        except Exception as error:
            if found:raise gathered(found) from error
            raise
    def core():
        validate_tree(plan)
        need(isinstance(plan,dict) and plan.get('schema')=='geumbit-plan-v1','geumbit-plan-v1 제작표가 필요합니다.')
        if 'graphic_variety' in plan:
            need(plan['graphic_variety']==GRAPHIC_VARIETY,'graphic_variety는 "unique-v1"만 지정할 수 있습니다.','graphic_variety_unique')
        if 'composition_floor' in plan:
            need(plan['composition_floor']==longform_floor.MARK,'composition_floor는 "'+longform_floor.MARK+'"만 지정할 수 있습니다.','composition_floor')
        if 'footage_unavailable' in plan:
            need(isinstance(plan['footage_unavailable'],str) and 10<=len(plan['footage_unavailable'].strip())<=1000,
                 'footage_unavailable은 영상 자료가 없는 이유·찾아본 곳(10~1000자)입니다.','composition_floor')
        need(plan.get('timing_basis','original_voice') in ('original_voice','adjusted_voice'),'편집 시간 기준은 original_voice 또는 adjusted_voice여야 합니다.')
        if 'narration' in plan:
            need(plan['narration']=={'tempo':1.05,'sentence_gap_add_seconds':.3},'승인된 나레이션은 필재 1.05 / 문장 사이 300ms 추가입니다.')
            need(isinstance(plan.get('blocks'),list) and all(isinstance(b,dict) for b in plan['blocks']),'제작표 blocks 목록이 필요합니다.')
            need(not any(b.get('sentence_pauses') for b in plan['blocks']),'자동 호흡 프로필과 수동 호흡 목록은 동시에 사용하지 마세요.')
    part(core,essential=True)
    part(validate_styles,plan.get('styles',{}))
    subject=plan.get('subject',{})
    def person():
        text(subject.get('name'),'인물 이름',100)
        text(subject.get('headline'),'이 인물/이야기에 맞는 상단 문구',60)
        need('\n' not in subject['headline'],'상단 문구는 한 줄로 지정하세요.')
        need(subject.get('kind') in ('actor','entrepreneur','thinker','other'),'인물 종류를 지정하세요.')
        text(subject.get('context'),'시대·장소·사건',1000)
    part(person)
    part(numeric,plan.get('target_seconds'),'목표 길이',1,2400)
    refs=plan.get('references');part(need,isinstance(refs,list) and refs,'확인한 사실 출처가 필요합니다.',essential=True)
    ref_ids=set()
    def reference(ref):
        rid=text(ref.get('id'),'출처 ID',100);need(rid not in ref_ids,'출처 ID 중복');ref_ids.add(rid)
        url=urlsplit(text(ref.get('url'),'출처 URL'))
        need(url.scheme in ('http','https') and url.hostname and not url.username,'출처는 HTTP(S) URL이어야 합니다.')
        text(ref.get('title'),'출처 제목');text(ref.get('evidence'),'해당 출처에서 확인한 내용',6000)
    for ref in refs:part(reference,ref)
    media=plan.get('media');part(need,isinstance(media,dict),'media 사전이 필요합니다.',essential=True)
    def medium(mid,asset):
        text(mid,'소재 ID',100);text(asset.get('path'),'로컬 소재 경로')
        need(bool(re.fullmatch('[a-f0-9]{64}',str(asset.get('sha256','')))),'소재 SHA256 필요: '+mid)
        need(asset.get('origin') in ('record','illustration'),'기록/설명용 삽화를 구분하세요: '+mid)
        need(asset.get('role') in (None,'background_texture'),'소재 역할 오류: '+mid)
        if asset.get('role')=='background_texture':
            need(asset['origin']=='illustration' and not asset.get('atlas_regions'),
                 '기록 사진이나 상황 삽화 아틀라스는 배경 질감으로 지정할 수 없습니다.','background_texture_role')
        text(asset.get('source'),'소재 출처');text(asset.get('description'),'소재 내용')
        validate_atlas(asset)
    for mid,asset in media.items():part(medium,mid,asset)
    sounds=plan.get('sound_assets',{})
    part(need,isinstance(sounds,dict),'sound_assets는 효과음 사전이어야 합니다.',essential=True)
    def sound(sid,asset):
        text(sid,'효과음 ID',100);text(asset.get('path'),'효과음 경로')
        need(bool(re.fullmatch('[a-f0-9]{64}',str(asset.get('sha256','')))),'효과음 SHA256 필요')
        text(asset.get('source'),'효과음 출처');text(asset.get('license'),'효과음 사용 근거')
    for sid,asset in sounds.items():part(sound,sid,asset)
    if plan.get('music') is not None:part(validate_music,plan['music'],sounds)
    blocks=plan.get('blocks');part(need,isinstance(blocks,list) and blocks,'대본 블록이 필요합니다.',essential=True)
    part(validate_scene_handoffs,blocks)
    seen=set();photo_ids=set();intervals=SourceIntervals()
    def block_identity(block_index,block):
        bid=text(block.get('id'),'블록 ID',80)
        need(bool(re.fullmatch('[A-Za-z0-9_-]+',bid)) and bid not in seen,'블록 ID 형식/중복');seen.add(bid)
        narration=text(block.get('text'),'나레이션',1000)
        if 'visual_text_sha256' in block:
            binding=block['visual_text_sha256']
            need(isinstance(binding,str) and bool(re.fullmatch('[a-f0-9]{64}',binding)),
                 '화면 연출의 대본 지문은 SHA256이어야 합니다.','visual_text_binding')
            need(binding==hashlib.sha256(narration.encode('utf-8')).hexdigest(),
                 '대본이 변경됐습니다. 장면 전환·모션·효과음의 발화 기준을 다시 맞춘 뒤 화면 연출의 대본 지문을 갱신하세요: '+bid,
                 'visual_text_changed')
        citations=block.get('references');need(isinstance(citations,list) and citations and all(x in ref_ids for x in citations),'블록별 근거를 연결하세요: '+bid)
    def block_picture(block_index,block):
        # The identity part reports a bad id/text; here they only label messages and bound character indexes.
        bid=str(block.get('id',''));narration=block.get('text') if isinstance(block.get('text'),str) else ''
        shot=block.get('visual',{});kind=shot.get('kind');need(kind in KINDS,'지원하지 않는 화면 종류: '+str(kind))
        if 'renderer' in shot:
            need(kind=='graphic' and shot['renderer'] in ('native','hyperframes'),'그래픽 렌더러는 native 또는 hyperframes입니다.')
        need(sum(key in shot for key in ('ink_cover','tear_cover','brush_cover','grain_wipe'))<=1,'한 장면에 잉크·찢김·붓칠·입자 덮기를 동시에 지정하지 마세요.')
        if 'edge_strobe' in shot:
            effect=shot['edge_strobe']
            need(isinstance(effect,dict) and set(effect)<={'windows','frame_offset','reason','reference'},'윤곽선 전환 설정 오류')
            offset=effect.get('frame_offset',0)
            need(type(offset) is int and offset>=0,'윤곽선 전환 프레임 오프셋 오류')
            windows=effect.get('windows')
            need(isinstance(windows,list) and 1<=len(windows)<=80,'윤곽선 전환 프레임 구간이 필요합니다.')
            last=0
            for pair in windows:
                need(isinstance(pair,list) and len(pair)==2 and all(type(n) is int for n in pair),'윤곽선 전환은 정수 프레임 구간입니다.')
                a,b=pair;need(0<=a<b and a>=last,'윤곽선 구간은 겹치지 않는 시작·끝 순서여야 합니다.');last=b
            text(effect.get('reason'),'전환의 문맥',300);text(effect.get('reference'),'직접 확인한 전환 근거',1000)
        for name in ('brush_cover','light_leak','glitch','negative_splatter','grain_wipe'):
            if name not in shot:continue
            effect=shot[name];need(isinstance(effect,dict),'화면 전환 설정 오류')
            if name in ('negative_splatter','grain_wipe'):
                fields={'at','duration','seed','reason','reference','phase'}|({'media'} if name=='grain_wipe' else {'reveal_limit','growth_power','islands'})
                need(set(effect)<=fields,'지원하지 않는 재질 전환 설정입니다.')
            at=numeric(effect.get('at'),'전환 시작 비율',0,1)
            length=numeric(effect.get('duration'),'전환 지속 비율',.001,1)
            need(at+length<=1.000001,'전환이 장면 끝을 넘습니다.')
            seed=effect.get('seed',17);need(type(seed) is int and 0<=seed<=4294967295,'전환 seed는 양의 정수입니다.')
            text(effect.get('reason'),'전환의 문맥',300);text(effect.get('reference'),'직접 확인한 전환 근거',1000)
            if name=='glitch':
                need(effect.get('scope','picture') in ('picture','content'),'글리치 scope는 picture/content입니다.')
                need(effect.get('profile','strips') in ('strips','blocks','staged_strips'),'글리치 profile은 strips/blocks/staged_strips입니다.')
                if effect.get('profile')=='staged_strips':
                    need(effect.get('phase','full')=='full','staged_strips는 장면 내부 full 전환입니다.')
                    need(not any(k in effect for k in ('seed','strength')),'staged_strips는 승인된 고정 패턴입니다. seed/strength를 지정하지 마세요.')
            if name=='brush_cover':
                need(type(effect.get('strokes',5)) is int and 3<=effect.get('strokes',5)<=8,'붓 횟수는 3~8입니다.')
                need(bool(re.fullmatch(r'#[0-9a-fA-F]{6}',str(effect.get('color','#163968')))),'붓칠 색은 #RRGGBB입니다.')
            elif name=='negative_splatter':
                need(effect.get('phase','full')=='full','음화 스플래터는 full 구간으로 지정하세요.')
                numeric(effect.get('reveal_limit',1),'음화 원색 노출 진행 한도',.01,1)
                numeric(effect.get('growth_power',1),'음화 얼룩 성장 지수',.1,4)
                if 'islands' in effect:
                    islands=effect['islands'];need(isinstance(islands,list) and 1<=len(islands)<=64,'얼룩은 1~64개 좌표로 지정하세요.')
                    for island in islands:
                        need(isinstance(island,dict) and set(island)=={'x','y','radius','onset'},'얼룩은 x/y/radius/onset을 모두 지정하세요.')
                        for key in ('x','y','onset'):numeric(island[key],'얼룩 '+key,0,1)
                        numeric(island['radius'],'얼룩 반경',.005,1)
            else:
                need(effect.get('phase','full') in ('full','out','in'),'전환은 full/out/in 중 지정하세요.')
                numeric(effect.get('strength',1),'전환 세기',.1,1)
                if effect.get('phase')=='out':need(abs(at+length-1)<1e-6,'나가는 전환은 장면 끝에서 이어집니다.')
                if effect.get('phase')=='in':need(at==0,'들어오는 전환은 장면 시작에서 이어집니다.')
                if name=='light_leak':need(effect.get('profile','smooth') in ('smooth','flash_rebound','white_flash'),'빛 전환 profile은 smooth/flash_rebound/white_flash입니다.')
                if name=='grain_wipe':
                    need(effect.get('phase') in ('out','in'),'입자 전환은 인접 장면 out/in 한 쌍으로 지정하세요.')
                    mid=effect.get('media');need(isinstance(mid,str) and mid in media,'입자 전환의 종이 질감을 plan.media에 등록하세요.')
                    need(media[mid].get('role')=='background_texture' and media[mid].get('origin')=='illustration','입자 전환에는 설명용 배경 질감을 사용하세요.')
        if 'ink_cover' in shot or 'tear_cover' in shot:
            ink=shot.get('ink_cover',shot.get('tear_cover'));need(isinstance(ink,dict),'화면 덮기 설정 오류')
            at=numeric(ink.get('at'),'잉크 시작 비율',0,1)
            length=numeric(ink.get('duration'),'잉크 진행 비율',.01,1)
            need(at+length<=1,'잉크 효과가 장면 끝을 넘습니다.')
            seed=ink.get('seed',17);need(type(seed) is int and 0<=seed<=4294967295,'잉크 seed는 양의 정수입니다.')
            text(ink.get('reason'),'내용을 잉크로 덮는 이유',300)
        if 'group_zoom' in shot:
            gz=shot['group_zoom']
            need(not shot.get('work'),'공동 확대의 작품칩은 전체 visual.work 대신 컷별 work로 지정하세요.')
            need(kind=='montage','공동 확대 전환은 몽타주에서 지정하세요.')
            need(isinstance(gz,dict) and set(gz)=={'after_shot','out_frames','in_frames','out_scale','in_scale','blur','reference'},'공동 확대 전환 설정 오류')
            parts=shot.get('shots',[]);at=gz['after_shot']
            need(type(at) is int and 0<=at<len(parts)-1,'공동 확대 전환 뒤에 다음 컷이 필요합니다.')
            for key in ('out_frames','in_frames'):
                need(type(gz[key]) is int and 2<=gz[key]<=60,'공동 확대 전환 프레임은 2~60입니다.')
            numeric(gz['out_scale'],'퇴장 확대',1,3);numeric(gz['in_scale'],'입장 시작 배율',.5,1)
            numeric(gz['blur'],'방사 흐림',0,.3);text(gz['reference'],'공동 확대 직접 관찰 근거',1000)
            need(all(p.get('transition',{}).get('kind','cut')=='cut' for p in parts[max(0,at-1):at+2]),'공동 확대 주변 컷은 다른 전환과 겹칠 수 없습니다.')
        if 'work_motion' in shot:
            wm=shot['work_motion']
            need(kind=='montage','작품칩 모션은 몽타주에서 지정하세요.')
            need(isinstance(wm,dict) and set(wm)<={'kind','delay','duration','reference'},'작품칩 모션 설정 오류')
            need(wm.get('kind')=='squash_y','작품칩 모션은 squash_y입니다.')
            numeric(wm.get('delay',0),'작품칩 등장 지연',0,2)
            numeric(wm.get('duration'),'작품칩 등장 길이',.05,2)
            text(wm.get('reference'),'작품칩 직접 관찰 근거',1000)
            need(any(p.get('work') for p in shot.get('shots',[])),'작품칩 모션에는 컷별 work가 필요합니다.')
        if 'brand_position' in shot:validate_brand_position(shot['brand_position'])
        if 'headline' in shot:
            text(shot['headline'],'장면별 상단 문구',60)
            need('\n' not in shot['headline'],'장면별 상단 문구는 한 줄로 지정하세요.')
        ids=shot.get('media',[]);need(isinstance(ids,list) and all(x in media for x in ids),'등록된 소재 ID를 사용하세요.')
        count={'photo':1,'video':1,'split':2,'cutout':2}.get(kind,{'story':1,'context':1,'comparison':2,'identity':2 if shot.get('face') else 1,'callout':1}.get(shot.get('template'),0))
        if kind=='graphic' and shot.get('template')=='authored':count=len(ids);need(count<=6,'맞춤 그래픽 소재는 최대 6개입니다.')
        if kind=='montage':count=len(set(ids));need(1<=count<=8,'몽타주 소재는 1~8개입니다.')
        need(len(ids)==count,'화면 종류에 맞는 소재 수가 필요합니다: '+bid)
        if any(media[mid].get('role')=='background_texture' for mid in ids):
            need(kind=='graphic' and shot.get('template')=='authored',
                 '배경 질감은 맞춤 그래픽의 전체 화면 배경에만 사용하세요.','background_texture_role')
        if kind not in ('video','montage'):
            picture_ids={n['media'] for n in shot.get('objects',[]) if n.get('kind')=='image'} if kind=='graphic' and shot.get('template')=='authored' else ids
            fingerprints=[media[mid]['sha256'] for mid in picture_ids]
            need((not any(h in photo_ids for h in fingerprints) and len(set(fingerprints))==len(fingerprints)) or bool(shot.get('repeat_reason')),'같은 사진 재사용 사유가 필요합니다: '+bid)
            photo_ids.update(fingerprints)
        if kind in ('photo','split') and 'max_scale' in shot:numeric(shot['max_scale'],'사진 최대 확대',1,1.5)
        if 'min_scale' in shot:
            need(kind=='photo' and 'max_scale' in shot and shot.get('motion','in') in ('in','out'),'사진 시작 배율은 확대/축소와 최대 배율을 함께 지정하세요.')
            numeric(shot['min_scale'],'사진 최소 확대',1,shot['max_scale'])
        if kind=='split' and 'panels' in shot:
            panels=shot['panels'];need(isinstance(panels,list) and len(panels)==2,'분할 화면은 두 패널 설정이 필요합니다.')
            for panel in panels:
                need(isinstance(panel,dict),'패널 설정은 사전이어야 합니다.')
                need(panel.get('fit','cover') in ('cover','contain'),'분할 사진 채움 방식 오류')
                if 'crop' in panel:validate_crop(panel['crop'])
                numeric(panel.get('inset_top',0),'분할 사진 상단 여백',0,400)
                need(not panel.get('inset_top') or panel.get('fit')=='contain','상단 여백은 contain 패널에 적용하세요.')
        if kind=='video':
            if 'crop' in shot:validate_crop(shot['crop'])
            for side in ('inset_top','inset_bottom'):numeric(shot.get(side,0),'영상 여백',0,400)
            need(shot.get('fit','contain') in ('contain','cover'),'영상 채움 방식 오류')
            need(shot.get('fit')!='cover' or not (shot.get('inset_top',0) or shot.get('inset_bottom',0)),'전체 화면 cover에는 여백을 지정하지 마세요.')
        if kind=='photo':
            need(shot.get('fit','auto') in ('auto','cover','contain'),'사진 채움 방식 오류')
            need(shot.get('motion','in') in ('in','out','still'),'사진 움직임 형식 오류')
            if shot.get('crop') is not None:
                crop=shot['crop'];need(isinstance(crop,list) and len(crop)==4,'사진 crop은 원본 좌표 4개입니다.')
                for value in crop:numeric(value,'사진 자르기 좌표',0,100000)
                need(crop[2]>crop[0] and crop[3]>crop[1],'사진 자르기 영역이 비었습니다.')
        if kind=='cutout':
            need(shot.get('entrance','left') in ('left','right','rise'),'누끼 등장 방향은 left/right/rise입니다.')
            numeric(shot.get('background_blur',45),'누끼 배경 흐림',0,90)
        if shot.get('source_label') is not None:text(shot['source_label'],'화면 자료 설명',120)
        if 'source_style' in shot:
            st=shot['source_style'];need(isinstance(st,dict),'출처 서식 오류')
            name=st.get('font_file','ROKAFSansMedium.ttf')
            need(isinstance(name,str) and bool(re.fullmatch(r'[A-Za-z0-9_-]+\.ttf',name)),'출처 글꼴은 로컬 TTF 파일명이어야 합니다.')
            numeric(st.get('font_size',29),'출처 크기',16,36)
            need(type(st.get('font_size',29)) is int,'출처 크기는 정수입니다.')
            numeric(st.get('background_alpha',170),'출처 배경 투명도',0,255)
        if kind=='video':
            start=numeric(shot.get('in'),'영상 시작');end=numeric(shot.get('out'),'영상 끝');need(end>start,'영상 구간이 비었습니다.')
            overlapped=intervals.add(media[ids[0]]['sha256'],start,end)
            need(not overlapped or bool(shot.get('repeat_reason')),'같은 영상 구간 재사용 사유가 필요합니다.'+' — 같은 원본 구간을 다시 쓰려면 visual.repeat_reason에 사유를 적고, 아니면 겹치지 않는 구간을 고르세요: '+bid)
        if kind=='montage':
            parts=shot.get('shots');need(isinstance(parts,list) and 2<=len(parts)<=12,'몽타주는 2~12개 컷이 필요합니다.')
            used=set()
            for i,part in enumerate(parts):
                need(isinstance(part,dict) and part.get('kind') in ('photo','video'),'몽타주 컷 종류 오류')
                need(part.get('media') in ids,'몽타주 소재 ID 오류');used.add(part['media'])
                if any(key in part for key in ('max_scale','min_scale')) or ('fit' in part and part['kind']=='photo'):
                    need(part['kind']=='photo' and not part.get('paired_photo'),'사진 채움·확대 설정은 단일 사진 컷에 적용하세요.')
                    need(part.get('fit','auto') in ('auto','cover','contain'),'몽타주 사진 채움 방식 오류')
                    if 'max_scale' in part:numeric(part['max_scale'],'몽타주 사진 최대 확대',1,1.5)
                    if 'min_scale' in part:
                        need('max_scale' in part,'최소 확대에는 최대 확대도 필요합니다.')
                        numeric(part['min_scale'],'몽타주 사진 최소 확대',1,part['max_scale'])
                if 'paired_photo' in part:
                    pair=part['paired_photo'];need(part['kind']=='photo' and isinstance(pair,dict),'쌍사진은 사진 컷에 지정하세요.')
                    need(pair.get('media') in ids and pair['media']!=part['media'],'쌍사진의 두 번째 소재 ID 오류');used.add(pair['media'])
                    need('crop' not in part and part.get('motion','still')=='still','쌍사진은 개별 crop/줌 대신 독립 등장을 사용합니다.')
                    entries=pair.get('entrances');need(isinstance(entries,list) and len(entries)==2,'쌍사진 등장 설정은 좌우 두 개입니다.')
                    for entry in entries:
                        need(isinstance(entry,dict) and entry.get('from') in ('top','bottom'),'사진 등장 방향 오류')
                        a=numeric(entry.get('at'),'사진 등장 시작',0,1);z=numeric(entry.get('duration'),'사진 등장 길이',.000001,1)
                        need(a+z<=1,'사진 등장이 컷을 벗어납니다.')
                    text(pair.get('reference'),'쌍사진 연출 근거')
                numeric(part.get('weight'),'몽타주 길이 비중',.001,10000)
                text(part.get('reason'),'몽타주 컷 선택 이유')
                if 'background' in part:
                    need(part['kind']=='video' and part['background'] in ('black','blur'),'몽타주 background는 영상 컷의 black 또는 blur입니다.')
                if 'brand_position' in part:validate_brand_position(part['brand_position'])
                if 'source_label' in part:text(part['source_label'],'컷별 자료 설명',120)
                if 'work' in part:
                    need(subject['kind']=='actor','비배우에게 영화 작품칩을 강제하지 않습니다.')
                    work=part['work'];need(isinstance(work,dict),'몽타주 작품칩 형식 오류')
                    text(work.get('title'),'작품 제목',60)
                    need(type(work.get('year')) is int,'작품 연도는 정수입니다.')
                    numeric(work['year'],'작품 연도',1800,2200)
                    need(not shot.get('work'),'몽타주 전체 작품칩과 컷별 작품칩을 동시에 지정하지 마세요.')
                for side in ('inset_top','inset_bottom'):
                    if side in part:
                        need(part['kind']=='video','몽타주 여백은 영상 컷에 적용하세요.')
                        numeric(part[side],'몽타주 영상 여백',0,400)
                if part['kind']=='video':
                    need(part.get('fit','contain') in ('contain','cover'),'몽타주 영상 채움 방식 오류')
                    need(part.get('fit')!='cover' or not (part.get('inset_top',0) or part.get('inset_bottom',0)),'전체 화면 cover에는 여백을 지정하지 마세요.')
                    a=numeric(part.get('in'),'몽타주 원본 시작');z=numeric(part.get('out'),'몽타주 원본 끝');need(z>a,'몽타주 원본 구간이 비었습니다.')
                    overlapped=intervals.add(media[part['media']]['sha256'],a,z)
                    need(not overlapped or bool(shot.get('repeat_reason')),'몽타주 원본 구간이 반복됩니다.'+' — 같은 원본 구간을 다시 쓰려면 visual.repeat_reason에 사유를 적고, 아니면 겹치지 않는 구간을 고르세요: '+bid)
                else:need(part.get('motion','in') in ('in','out','still'),'몽타주 사진 모션 오류')
                if part.get('crop') is not None:
                    crop=part['crop'];need(isinstance(crop,list) and len(crop)==4,'몽타주 사진/영상 crop 형식 오류')
                    for x in crop:numeric(x,'몽타주 crop',0,100000)
                    need(crop[2]>crop[0] and crop[3]>crop[1],'몽타주 crop 범위 오류')
                if 'camera' in part:
                    camera=part['camera'];need(isinstance(camera,dict),'카메라 모션 오류')
                    for key in ('from_scale','to_scale'):numeric(camera.get(key),'카메라 배율',1,1.5)
                    for key in ('anchor_x','anchor_y'):numeric(camera.get(key,.5),'카메라 기준점',0,1)
                    numeric(camera.get('at',0),'카메라 시작',0,1)
                    numeric(camera.get('duration',1),'카메라 길이',.000001,1)
                    need(camera.get('at',0)+camera.get('duration',1)<=1+1e-9,'카메라 모션이 컷을 벗어납니다')
                    need(camera.get('ease','linear') in ('linear','ease_out'),'카메라 easing 오류')
                tr=part.get('transition',{'kind':'cut','frames':0})
                need(isinstance(tr,dict) and tr.get('kind') in ('cut','dissolve','wipe_left','wipe_right','horizontal_blur','shatter','brush_reveal'),'몽타주 전환 종류 오류')
                n=tr.get('frames',0);need(type(n) is int,'몽타주 전환은 정수 프레임입니다.')
                # Authored product range: shattered fragments can outlast1s,
                # unlike existing xfade treatments. Reference2016.833–2018.4.
                need((n==0) if tr['kind']=='cut' else (2<=n<=180 if tr['kind']=='shatter' else 2<=n<=60 if tr['kind']=='brush_reveal' else 1<=n<=60),'몽타주 전환 프레임 범위 오류')
                if tr['kind'] in ('shatter','brush_reveal'):
                    need(type(tr.get('seed',17)) is int and 0<=tr.get('seed',17)<=99999,'질감 전환 seed 오류')
                    text(tr.get('reference'),'질감 전환 관찰 근거')
                if i==len(parts)-1:need(tr['kind']=='cut','마지막 컷 뒤에는 전환을 배정하지 않습니다.')
            need(used==set(ids),'등록하고 사용하지 않은 몽타주 소재가 있습니다.')
        if kind=='graphic':
            need(shot.get('template') in GRAPHIC_LABEL_COUNTS,'등록된 그래픽 부품을 고르세요.')
            # visual.variety is the renderer's marker for the opened motion values (opened_motion): it must mean unique-v1.
            need(not opened_motion(shot) or plan.get('graphic_variety')==GRAPHIC_VARIETY,
                 f'{bid}: visual.variety는 graphic_variety:"unique-v1" 제작표에서만 지정합니다.','graphic_variety_unique')
            if shot['template']=='authored':
                validate_authored(shot)
                for index,node in enumerate(shot['objects']):
                    if node['kind'] in ('image','video'):background_texture(media,node,index,shot)
                for node in shot['objects']:
                    if node['kind']!='video':continue
                    overlapped=intervals.add(media[node['media']]['sha256'],node['in'],node['out'])
                    need(not overlapped or bool(shot.get('repeat_reason')),'같은 영상 객체 구간 재사용 사유가 필요합니다.'+' — 같은 원본 구간을 다시 쓰려면 visual.repeat_reason에 사유를 적고, 아니면 겹치지 않는 구간을 고르세요: '+bid)
                for cue in shot['motion_cues']:
                    for key in ('start_char','end_char'):
                        if key in cue:need(type(cue[key]) is int and 0<=cue[key]<len(narration),'모션 기준 문자가 대본 밖입니다.')
                    if 'end_char' in cue:need('start_char' in cue and cue['end_char']>=cue['start_char'],'모션 문자 범위 오류')
            labels=shot.get('labels');need(isinstance(labels,list) and 1<=len(labels)<=3,'그래픽 항목 1~3개 필요')
            for label in labels:
                text(label,'그래픽 문구',60);need('\n' not in label,'그래픽 항목 제목은 한 줄로 지정하세요. 여러 줄 설명은 notes를 사용하세요.')
            text(shot.get('title'),'그래픽 제목',100);need('\n' not in shot['title'],'그래픽 제목은 한 줄로 지정하세요.')
            expected=GRAPHIC_LABEL_COUNTS[shot['template']]
            need(len(labels)==expected,'그래픽 종류별 문구 수가 다릅니다.')
            if shot['template'] in ('explanation','document','debate','timeline','layers','balance'):
                need(isinstance(shot.get('notes'),list) and len(shot['notes'])==expected,'그래픽 항목마다 본문이 필요합니다.')
                for note in shot['notes']:text(note,'설명 카드 본문',80)
            if shot['template']=='callout':
                marks=shot.get('markers')
                need(isinstance(marks,list) and len(marks)==2,'주석은 원본 이미지의 상대 좌표 두 개가 필요합니다.')
                for mark in marks:
                    need(isinstance(mark,list) and len(mark)==2,'주석 좌표는 [x, y]입니다.')
                    for coordinate in mark:numeric(coordinate,'주석 상대 좌표',0,1)
            if shot['template'] in ('numbers','comparison'):
                need(isinstance(shot.get('dates'),list) and len(shot['dates'])==2,'비교 항목 이름 2개가 필요합니다.')
                for date in shot['dates']:
                    text(date,'비교 항목 이름',40);need('\n' not in date,'비교 항목 이름은 한 줄로 지정하세요.')
            if shot.get('face'):
                face=shot['face'];need(shot['template']=='identity' and isinstance(face,dict),'얼굴 마스크 형식 오류')
                need(bool(re.fullmatch(r'[0-9.eE+ ,\-]+',str(face.get('view_box','')))),'SVG viewBox 형식 오류')
                need(bool(re.fullmatch(r'[MmLlHhVvCcSsQqTtAaZz0-9.eE+ ,\-]+',str(face.get('path','')))),'얼굴 마스크 경로 형식 오류')
                numeric(face.get('width'),'원본 얼굴 이미지 폭',1,20000);numeric(face.get('height'),'원본 얼굴 이미지 높이',1,20000)
            if shot['template']=='numbers':
                text(shot.get('total'),'합계 표시',40);text(shot.get('total_label'),'합계 설명',40)
                need('\n' not in shot['total'] and '\n' not in shot['total_label'],'합계 표시는 한 줄로 지정하세요.')
        if shot.get('work'):
            need(subject['kind']=='actor','비배우에게 영화 작품칩을 강제하지 않습니다.')
            text(shot['work'].get('title'),'작품 제목',60);numeric(shot['work'].get('year'),'작품 연도',1800,2200)
    def block_voice(block_index,block):
        shot=block.get('visual',{})
        editorial=block.get('editorial_pauses')
        if editorial is not None:
            need(bool(block.get('existing_voice')),'원음 청취 쉼은 이미 보존된 음성에 지정하세요.')
            need(isinstance(editorial,dict),'원음 청취 쉼 기록 형식 오류')
            need(bool(re.fullmatch('[a-f0-9]{64}',str(editorial.get('source_sha256','')))),'청취 쉼 원본 SHA256 필요')
            text(editorial.get('reason'),'청취 쉼 사유',2000);text(editorial.get('reference'),'청취 쉼 참고 구간',2000)
            entries=editorial.get('entries')
            need(isinstance(entries,list) and 1<=len(entries)<=10,'청취 쉼 항목은 1~10개입니다.')
            seen=set();previous=-1
            for entry in entries:
                need(isinstance(entry,dict),'청취 쉼 항목 형식 오류')
                idx=entry.get('after_character')
                need(type(idx) is int and 0<=idx<len(block['text']) and block['text'][idx] in '.!?。！？' and idx not in seen,'중복 없는 문장 끝 인덱스가 필요합니다.')
                numeric(entry.get('at_seconds'),'청취 쉼 삽입 시각',0,2400);numeric(entry.get('add_seconds'),'청취 쉼 추가 시간',.1,30)
                need(type(entry.get('terminal_tail',False)) is bool,'문장 꼬리 표시는 불리언이어야 합니다.')
                need(entry['at_seconds']>previous,'청취 쉼은 시간 순서여야 합니다.')
                seen.add(idx);previous=entry['at_seconds']
        repair=block.get('audio_repair')
        pauses=block.get('sentence_pauses')
        if pauses is not None:
            need(isinstance(pauses,dict),'호흡 조정은 원본 해시와 문장 경계 목록이 필요합니다.')
            need(bool(re.fullmatch('[a-f0-9]{64}',str(pauses.get('source_sha256','')))),'호흡 조정 원본 SHA256 필요')
            text(pauses.get('reason'),'호흡 조정 사유',2000)
            entries=pauses.get('entries')
            need(isinstance(entries,list) and 1<=len(entries)<=100,'호흡 조정 항목은 1~100개입니다.')
            last_pause=-1
            for entry in entries:
                need(isinstance(entry,dict),'호흡 조정 항목 형식 오류')
                idx=entry.get('after_character')
                need(type(idx) is int and 0<=idx<len(block['text']) and block['text'][idx] in '.!?。！？','문장 끝 문자 인덱스가 필요합니다.')
                numeric(entry.get('at_seconds'),'호흡 삽입 시각',0,2400)
                numeric(entry.get('add_seconds'),'호흡 추가 시간',.02,.3)
                need(type(entry.get('terminal_tail',False)) is bool,'문장 꼬리 표시는 불리언이어야 합니다.')
                need(entry['at_seconds']>last_pause,'호흡 조정은 시간 순서여야 합니다.')
                last_pause=entry['at_seconds']
        if repair is not None:
            need(isinstance(repair,dict),'음성 보정 기록 형식 오류')
            need(bool(re.fullmatch('[a-f0-9]{64}',str(repair.get('source_sha256','')))),'음성 보정 원본 SHA256 필요')
            numeric(repair.get('tail_start_seconds'),'음성 꼬리 보정 시작')
            text(repair.get('reason'),'음성 보정 검토 사유',2000)
        cues=block.get('sfx',[])
        need(isinstance(cues,list),'sfx는 명시적인 효과음 배정 목록이어야 합니다.')
        for cue in cues:
            need(isinstance(cue,dict) and cue.get('asset') in sounds,'등록된 효과음 ID가 필요합니다.')
            if 'tail_into_next' in cue:
                need(block_index+1<len(blocks) and cue['tail_into_next']==blocks[block_index+1].get('id'),'효과음 여운은 바로 다음 장면 ID로 연결하세요.')
            numeric(cue.get('at'),'효과음 시각',0,2400)
            numeric(cue.get('gain_db'),'효과음 게인',-60,6)
            text(cue.get('reason'),'효과음 배정 이유')
            text(cue.get('reference'),'대조한 원본 효과음 위치')
        if 'beat_seconds' in shot:
            beat=shot['beat_seconds']
            need(isinstance(beat,list) and beat and len(beat)<=10,'모션 비트 시각 목록 오류')
            for t in beat:numeric(t,'모션 비트 시각',0,2400)
            need(all(a<b for a,b in zip(beat,beat[1:])),'모션 비트는 시간 순서여야 합니다.')
    for block_index,block in enumerate(blocks):
        for check in (block_identity,block_picture,block_voice):part(check,block_index,block)
        part(checked_captions,block)
    from longform_source_audio import validate as validate_source_audio
    part(validate_source_audio,blocks,media)
    part(lambda:visual_diversity(plan,execution=execution))
    # 2026-10-20 최소 구성(오드리 헵번 편 바닥 · runner/longform_floor.py). 작성한 제작표에서 한 번만 잰다 — 실행 제작표
    # (conform_plan)는 블록 종류를 바꾸지 않으니 다시 재지 않는다. 표시가 없는 시작한 작업은 예전 규칙 그대로.
    if plan.get('composition_floor')==longform_floor.MARK and not execution:
        def floor():
            fixes=longform_floor.check(plan)[1]
            need(not fixes,longform_floor.message(fixes) if fixes else '','composition_floor')
        part(floor)
    def upload_part():
        upload=plan.get('upload',{});text(upload.get('title'),'업로드 제목',100);text(upload.get('description'),'영상 설명',10000)
        need(isinstance(upload.get('hashtags'),list) and all(isinstance(t,str) and re.fullmatch(r'#[\w가-힣]+',t) for t in upload['hashtags']),'해시태그 형식 오류')
        from longform_upload import upload_fields
        upload_fields(plan)  # Validate final music credits and tags before paid work (Korean credit header is the longest one, so this bound also holds for English episodes).
    part(upload_part)
    def endcard_part():
        endcard=plan.get('endcard',{})
        need(isinstance(endcard,dict),'엔딩 설정은 객체입니다.')
        need(type(endcard.get('recommendation_arrow',True)) is bool,'엔딩 화살표 설정은 true 또는 false입니다.')
        need(endcard.get('title_treatment','classic') in ('classic','gold_depth'),'엔딩 제목 처리는 classic 또는 gold_depth입니다.')
        need(endcard.get('title_font','BMYEONSUNG.ttf') in FONT_NAMES,'엔딩 제목은 배포 글꼴을 지정하세요.')
        reveal=endcard.get('title_reveal')
        if reveal is not None:
            need(isinstance(reveal,list) and len(reveal)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in reveal) and reveal[0]>=0 and reveal[1]>0 and sum(reveal)<=9,'엔딩 제목 등장은 [시작초, 진행초]이며 9초 안에 끝나야 합니다.')
        credits=endcard.get('credits',[])
        need(isinstance(credits,list) and len(credits)<=2,'엔딩 출처 문구는 최대 2줄입니다.')
        for line in credits:text(line,'엔딩 출처 문구',100)
    part(endcard_part)
    def thumbnail_part():
        thumb=plan.get('thumbnail',{});need(thumb.get('media') in media,'썸네일 소재가 필요합니다.')
        need(isinstance(thumb.get('lines'),list) and 1<=len(thumb['lines'])<=2,'썸네일 문구는 1~2줄')
        for line in thumb['lines']:text(line,'썸네일 문구',30)
        if 'elements' in thumb:
            elements=thumb['elements']
            need(isinstance(elements,list) and 1<=len(elements)<=12,'썸네일 요소는 1~12개입니다.')
            text(thumb.get('reference'),'썸네일 구도 대조 원본')
            for el in elements:
                need(isinstance(el,dict) and el.get('kind') in ('image','text'),'썸네일 요소 형식 오류')
                box=el.get('box')
                need(isinstance(box,list) and len(box)==4 and all(type(v) is int for v in box),'썸네일 box는 정수 4개입니다.')
                x,y,w,h=box;need(0<=x<x+w<=1280 and 0<=y<y+h<=720,'썸네일 요소가 화면 밖입니다.')
                if el['kind']=='image':
                    need(el.get('media') in media,'썸네일 이미지가 없습니다.')
                    if 'crop' in el:
                        need(isinstance(el['crop'],list) and len(el['crop'])==4,'썸네일 crop 좌표 4개 필요')
                        for v in el['crop']:numeric(v,'썸네일 crop 좌표',0,20000)
                else:
                    text(el.get('text'),'썸네일 문구',40);numeric(el.get('size'),'썸네일 글자 크기',12,250)
                    numeric(el.get('stroke',7),'썸네일 외곽선',0,20)
                    numeric(el.get('shear',0),'썸네일 글자 기울기',-.35,.35)
                    need(el.get('font','Paperlogy-8ExtraBold.ttf') in FONT_NAMES,'배포 글꼴만 사용하세요.')
                    need(bool(re.fullmatch('#[0-9a-fA-F]{6}',str(el.get('color','')))),'썸네일 글자색 오류')
                    if 'gradient' in el:
                        gradient=el['gradient']
                        need(isinstance(gradient,dict) and set(gradient)<= {'direction','colors'},'썸네일 그라디언트 형식 오류')
                        need(gradient.get('direction','vertical') in ('horizontal','vertical'),'썸네일 그라디언트 방향 오류')
                        colors=gradient.get('colors')
                        need(isinstance(colors,list) and 2<=len(colors)<=6,'썸네일 그라디언트 색상은 2~6개입니다.')
                        for color in colors:need(bool(re.fullmatch('#[0-9a-fA-F]{6}',str(color))),'썸네일 그라디언트 색상 오류')
        if thumb.get('secondary_media'):need(thumb['secondary_media'] in media,'썸네일 보조 소재가 없습니다.')
        if thumb.get('crop') is not None:
            need(isinstance(thumb['crop'],list) and len(thumb['crop'])==4,'썸네일 crop은 좌표 4개입니다.')
            for coordinate in thumb['crop']:numeric(coordinate,'썸네일 좌표',0,20000)
    part(thumbnail_part)
    for effect in ('light_leak','glitch','grain_wipe'):part(validate_light_sequence,blocks,effect)
    if found:raise gathered(found)
    return plan


def validate_light_sequence(blocks,effect_name='light_leak'):
    for index,block in enumerate(blocks):
        effect=block['visual'].get(effect_name,{})
        phase=effect.get('phase','full')
        if phase=='full':continue
        other=index+1 if phase=='out' else index-1
        need(0<=other<len(blocks),effect_name+' 전환의 앞뒤 장면이 없습니다.')
        pair=blocks[other]['visual'].get(effect_name,{})
        need(pair.get('phase')==('in' if phase=='out' else 'out'),effect_name+' out/in을 인접 장면에 함께 지정하세요.')
        need(effect.get('seed',17)==pair.get('seed',17) and effect.get('strength',1)==pair.get('strength',1),effect_name+' 앞뒤 seed와 strength가 다릅니다.')
        if effect_name=='glitch':
            need(effect.get('scope','picture')==pair.get('scope','picture'),'글리치 앞뒤 scope가 다릅니다.')
            need(effect.get('profile','strips')==pair.get('profile','strips'),'글리치 앞뒤 profile이 다릅니다.')
        if effect_name=='light_leak':need(effect.get('profile','smooth')==pair.get('profile','smooth'),'빛 전환 앞뒤 profile이 다릅니다.')
        if effect_name=='grain_wipe':need(effect.get('media')==pair.get('media'),'입자 전환의 앞뒤 종이 질감이 다릅니다.')


def validate_authored(shot):
    opened=opened_motion(shot)
    text(shot.get('layout_id'),'장면 고유 구도 ID',100)
    text(shot.get('design_reason'),'이 장면에서 이 구도가 필요한 이유',2000)
    reference=shot.get('style_reference')
    need(isinstance(reference,dict),'맞춤 장면은 직접 확인한 원본 위치가 필요합니다.')
    text(reference.get('source'),'원본 영상/파일')
    a=numeric(reference.get('start'),'원본 시작');b=numeric(reference.get('end'),'원본 끝')
    need(b>a,'원본 대조 구간이 비었습니다.')
    text(reference.get('observed'),'직접 관찰한 표현')
    need(shot.get('theme','charcoal') in ('charcoal','brown','purple','blue'),'맞춤 그래픽 배경 오류')
    objects=shot.get('objects');need(isinstance(objects,list) and 1<=len(objects)<=30,'맞춤 그래픽은 객체 1~30개입니다.')
    groups=shot.get('groups',[]);need(isinstance(groups,list) and len(groups)<=8,'모션 묶음은 최대 8개입니다.')
    ids=set();group_ids=set()
    for group in groups:
        need(isinstance(group,dict),'모션 묶음은 사전이어야 합니다.')
        gid=group.get('id');need(isinstance(gid,str) and bool(re.fullmatch('[a-zA-Z][a-zA-Z0-9_-]*',gid)) and gid not in ids,'모션 묶음 ID 형식/중복')
        need(group.get('clip','none') in ('none','rounded','gear'),'묶음 마스크는 none, rounded 또는 gear입니다.')
        if group.get('clip')=='gear':
            gear=group.get('gear',{});need(isinstance(gear,dict),'톱니 설정은 사전이어야 합니다.')
            need(not set(gear)-{'teeth','root_radius','hole_radius'},'알 수 없는 톱니 설정입니다.')
            need(type(gear.get('teeth',16)) is int and 6<=gear.get('teeth',16)<=64,'톱니 개수는 6~64 정수입니다.')
            root=numeric(gear.get('root_radius',.42),'톱니 뿌리 반경',.25,.49)
            hole=numeric(gear.get('hole_radius',.1),'톱니 중앙 구멍 반경',0,.4)
            need(hole<root,'톱니 중앙 구멍은 뿌리 반경보다 작아야 합니다.')
        else:need('gear' not in group,'톱니 설정은 gear 마스크에만 지정하세요.')
        origin=group.get('origin',[.5,.5]);need(isinstance(origin,list) and len(origin)==2,'묶음 중심은 화면 비율 2개입니다.')
        for value in origin:numeric(value,'묶음 중심 비율',0,1)
        ids.add(gid);group_ids.add(gid)
    if 'iris_handoff' in shot:
        iris=shot['iris_handoff']
        need(isinstance(iris,dict),'조리개 전환 설정은 사전이어야 합니다.')
        keys={'outgoing','incoming','at','ring_in','close','closed','swap','opened','end','reference'}
        need(set(iris)==keys,'조리개 전환의 두 묶음·7개 시점·근거를 모두 지정하세요.')
        need(isinstance(iris['outgoing'],str) and isinstance(iris['incoming'],str) and iris['outgoing'] in group_ids and iris['incoming'] in group_ids and iris['outgoing']!=iris['incoming'],'조리개 전환에는 서로 다른 등록 묶음 두 개가 필요합니다.')
        times=[numeric(iris[k],'조리개 전환 시점',0,1) for k in ('at','ring_in','close','closed','swap','opened','end')]
        need(all(a<b for a,b in zip(times,times[1:])),'조리개 등장→유지→닫힘→교체→열림→퇴장 순서가 필요합니다.')
        text(iris['reference'],'조리개 원본 관찰 근거')
    from longform_groups import validate_order, members as group_members
    need(all(isinstance(n,dict) for n in objects),'객체는 사전이어야 합니다.')
    validate_order(shot)
    def color(v):need(v=='none' or bool(re.fullmatch('#[a-fA-F0-9]{6}',str(v))),'맞춤 그래픽 색상 오류')
    for node in objects:
        need(isinstance(node,dict),'객체는 사전이어야 합니다.')
        nid=node.get('id');need(isinstance(nid,str) and bool(re.fullmatch('[a-zA-Z][a-zA-Z0-9_-]*',nid)) and nid not in ids,'객체 ID 형식/중복');ids.add(nid)
        kind=node.get('kind');need(kind in ('image','video','text','path'),'맞춤 그래픽 객체 종류 오류')
        if 'brush_reveal' in node:
            brush=node['brush_reveal']
            need(kind in ('image','video'),'붓 노출은 이미지 또는 영상 객체에 지정하세요.')
            need(isinstance(brush,dict) and set(brush)<= {'seed','strokes','phase'},'붓 노출 설정 오류')
            need(brush.get('phase','in') in ('in','out'),'붓 노출 방향은 in 또는 out입니다.')
            need(type(brush.get('seed',23)) is int and 0<=brush.get('seed',23)<=99999,'붓 질감 seed 오류')
            need(type(brush.get('strokes',5)) is int and 2<=brush.get('strokes',5)<=8,'붓 획 개수는 2~8입니다.')
            need('paper_reveal' not in node and node.get('tile_scale') is None and node.get('mask','rectangle')=='rectangle','붓 노출은 다른 노출·반복 질감·마스크와 병용하지 마세요.')
        if 'paper_reveal' in node:
            paper=node['paper_reveal']
            need(kind in ('image','video'),'종이 노출은 이미지 또는 영상 객체에 지정하세요.')
            need(isinstance(paper,dict) and set(paper)<= {'seed','color'},'종이 노출 설정 오류')
            need(type(paper.get('seed',23)) is int and 0<=paper.get('seed',23)<=99999,'종이 질감 seed 오류')
            need(bool(re.fullmatch('#[a-fA-F0-9]{6}',str(paper.get('color','#F0EEE8')))),'종이 색상 오류')
            need(node.get('tile_scale') is None and node.get('mask','rectangle')=='rectangle','종이 노출은 반복 질감·다른 마스크와 병용하지 마세요.')
        if 'gradient' in node:
            need(kind in ('text','path'),'그라디언트는 글자 또는 path에만 지정하세요.')
            gradient=node['gradient'];need(isinstance(gradient,dict),'그라디언트 형식 오류')
            need(gradient.get('direction','horizontal') in ('horizontal','vertical'),'그라디언트 방향 오류')
            colors=gradient.get('colors');need(isinstance(colors,list) and 2<=len(colors)<=6,'그라디언트 색상 2~6개가 필요합니다.')
            for value in colors:
                color(value);need(value!='none','그라디언트 색상은 불투명 색으로 지정하세요.')
        if 'skew_x' in node:
            need(kind=='text','글자 기울기는 text에만 지정하세요.')
            numeric(node['skew_x'],'글자 기울기 각도',-20,20)
        if 'pattern_height' in node:
            need(kind=='path' and 'gradient' not in node,'반복 필드는 그라디언트 없는 path에만 지정하세요.')
            numeric(node['pattern_height'],'반복 필드 높이',1,1080)
        need(node.get('role') in (None,'background_texture'),'객체 역할 오류')
        if node.get('role')=='background_texture':
            need(kind=='image','배경 질감 역할은 이미지에만 지정하세요.','background_texture_role')
        box=node.get('box');need(isinstance(box,list) and len(box)==4,'객체 box는 좌표 4개입니다.')
        for v in box:numeric(v,'객체 위치/크기',0,1920)
        x,y,w,h=box
        if 'frame_crop' in node:
            text(node['frame_crop'],'의도한 프레임 잘림의 근거',500)
            need(kind=='image' and w>0 and h>0 and x<1920 and y<1080,'프레임 잘림은 화면과 교차하는 이미지에만 지정하세요.')
        else:need(w>0 and h>0 and x+w<=1920 and y+h<=1080,'객체가 화면 밖입니다.')
        if 'shadow' in node:
            shadow=node['shadow'];need(isinstance(shadow,dict) and set(shadow)=={'x','y','blur','color'},'그림자 설정 오류')
            for axis in ('x','y'):numeric(shadow[axis],'그림자 위치',-60,60)
            numeric(shadow['blur'],'그림자 흐림',0,60);color(shadow['color'])
        if 'line_height' in node:
            need(kind=='text','줄높이는 텍스트에 지정하세요.');numeric(node['line_height'],'줄높이',.8,2)

        if 'transform_origin' in node:
            origin=node['transform_origin'];need(isinstance(origin,list) and len(origin)==2,'모션 중심은 비율 2개입니다.')
            for value in origin:numeric(value,'모션 중심 비율',0,1)
        if 'texture_cadence' in node:
            from longform_texture import validate as validate_texture
            validate_texture(node)
        if kind=='image':
            need(node.get('media') in shot['media'],'객체 이미지 ID 오류');text(node.get('alt'),'이미지 설명')
            need(node.get('fit','cover') in ('contain','cover'),'객체 채움 방식 오류')
            numeric(node.get('outline_width',0),'누끼 테두리 두께',0,20)
            color(node.get('outline_color','#FFFFFF'))
            if node.get('tile_scale') is not None:
                need(node.get('crop') is not None,'반복 질감에는 원본 영역이 필요합니다.')
                numeric(node['tile_scale'],'질감 배율',.25,4)
            if node.get('crop') is not None:
                crop=node['crop'];need(isinstance(crop,list) and len(crop)==4,'객체 crop은 원본 좌표 4개입니다.')
                for value in crop:numeric(value,'객체 crop',0,100000)
                need(crop[2]>crop[0] and crop[3]>crop[1],'객체 crop이 비었습니다.')
        elif kind=='video':
            need(node.get('media') in shot['media'],'객체 영상 ID 오류');text(node.get('alt'),'영상 설명')
            start=numeric(node.get('in'),'영상 시작',0,100000)
            end=numeric(node.get('out'),'영상 끝',0,100000);need(end>start,'영상 객체의 원본 구간이 비었습니다.')
            at=numeric(node.get('at',0),'영상 등장 비율',0,1)
            length=numeric(node.get('duration',1),'영상 재생 비율',.001,1)
            need(at+length<=1.000001,'영상이 장면 끝을 넘습니다.')
            need(node.get('fit','contain') in ('contain','cover'),'영상 채움 방식 오류')
            need(node.get('mask','rectangle') in ('rectangle','rounded','ellipse','thought'),'영상 마스크 오류')
            if 'outline_width' in node or 'outline_color' in node:
                need(node.get('mask')=='thought','영상 윤곽선은 thought 마스크에만 지정하세요.')
            if node.get('mask')=='thought':
                numeric(node.get('outline_width',6),'생각창 윤곽선 두께',0,20)
                color(node.get('outline_color','#FFFFFF'))
            if node.get('crop') is not None:validate_crop(node['crop'])
        elif kind=='text':
            text(node.get('text'),'객체 문구',150);numeric(node.get('size'),'객체 글자 크기',20,200);color(node.get('color'))
            need(node.get('font','Hand') in GRAPHIC_FONTS,'객체 글꼴 오류')
            need(node.get('align','left') in ('left','center','right'),'객체 글자 정렬 오류')
            if 'outline_width' in node or 'outline_color' in node:
                numeric(node.get('outline_width'),'글자 윤곽선 두께',0,20)
                color(node.get('outline_color','#141020'))
                need(node.get('outline_color','#141020')!='none','글자 윤곽선은 불투명 색으로 지정하세요.')
        else:
            need(bool(re.fullmatch(r'[MmLlHhVvCcSsQqTtAaZz0-9.eE+ ,\-]+',str(node.get('path','')))),'SVG 경로 형식 오류')
            color(node.get('fill','none'));color(node.get('stroke','#FAC02D'));numeric(node.get('stroke_width',6),'선 두께',0,30)
    cues=shot.get('motion_cues');need(isinstance(cues,list) and 1<=len(cues)<=80,'맞춤 모션 큐가 필요합니다.')
    paints=shot.get('text_paints',[]);need(isinstance(paints,list),'입체 글자 관계는 목록이어야 합니다.')
    # Object ids are unique (checked above), so id lookups replace scans of the objects list in the loops below.
    lookup={n['id']:n for n in objects};position={n['id']:i for i,n in enumerate(objects)};owned=set()
    group_lookup={g['id']:g for g in groups}
    for paint in paints:
        need(isinstance(paint,dict) and set(paint)=={'front','depth','offset','reason'},'입체 글자의 앞면·깊이·위치차·근거를 지정하세요.')
        a,z=paint['front'],paint['depth']
        need(isinstance(a,str) and isinstance(z,str) and a!=z and a in lookup and z in lookup,'입체 글자 대상 오류')
        need(not ({a,z}&owned),'입체 글자 관계 중복');owned.update((a,z))
        front,depth=lookup[a],lookup[z]
        need(front['kind']==depth['kind']=='text','입체 글자는 text 객체끼리 지정하세요.')
        need(all(front.get(k,default)==depth.get(k,default) for k,default in [('text',None),('font','Hand'),('size',None),('align','left'),('skew_x',0),('group',None)]),'입체 글자 내용·서체·크기·묶음이 다릅니다.')
        need(front['box'][2:]==depth['box'][2:] and position[z]<position[a],'입체 글자 크기 또는 앞뒤 순서 오류')
        off=paint['offset'];need(isinstance(off,list) and len(off)==2,'입체 글자 위치차 오류')
        for value in off:need(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value),'입체 글자 위치차는 유한한 숫자여야 합니다.')
        need(all(abs(depth['box'][i]-front['box'][i]-off[i])<1e-6 for i in range(2)),'선언한 입체 글자 위치차와 실제 배치가 다릅니다.')
        need(not any(c.get('target') in (a,z) for c in cues),'입체 글자 모션은 공통 묶음에 지정하세요.')  # paints x cues: <= 15 x 80
        text(paint['reason'],'입체 글자 중첩 근거')
    for cue in cues:
        need(isinstance(cue,dict),'모션 큐는 사전이어야 합니다.')
        need(cue.get('target') in ids,'모션 대상이 없습니다.')
        iris=shot.get('iris_handoff')
        if iris and cue.get('target') in (iris['outgoing'],iris['incoming']):
            need(cue.get('effect') not in ('fade','rise','slide','pop'),'조리개가 제어하는 두 묶음의 불투명도를 별도 등장 모션으로 덮어쓰지 마세요. 자식 객체에 적용하세요.')
        need(cue.get('effect') in ('draw','rise','slide','pop','pan','pattern_pan','paper_reveal','brush_reveal','count','zoom','fade','focus','grayscale','rotate','object_glitch','text_wipe','round_frame','gear_spin','polygon_wipe','brightness'),'모션 기법 오류')
        if 'focus_transition' in cue:
            spec=cue['focus_transition']
            need(cue['effect']=='focus' and cue['target'] in group_ids,'흐림 전환은 focus 묶음에만 지정하세요.')
            need(isinstance(spec,dict) and set(spec)=={'phase','reason'} and spec['phase']=='enter','흐림 전환 선언 형식 오류')
            text(spec['reason'],'흐림 전환 근거',500)
            need(isinstance(cue.get('from'),(int,float)) and cue['from']>0 and cue.get('to')==0,'흐림 전환은 양수에서 0으로 선명해져야 합니다.')
        if 'viewport_transition' in cue:
            spec=cue['viewport_transition']
            need(cue['effect'] in ('pan','zoom') and cue['target'] in group_ids,'화면 출입은 pan 또는 zoom 묶음에만 지정하세요.')
            need(isinstance(spec,dict) and set(spec)=={'phase','reason'},'화면 출입 선언 형식 오류')
            need(spec['phase'] in ('enter','exit'),'화면 출입 방향 오류')
            text(spec['reason'],'화면 출입 근거',500)
            need(any(axis in cue and 'from_'+axis in cue and cue[axis]!=cue['from_'+axis] for axis in (('x','y') if cue['effect']=='pan' else ('scale',))),'화면 출입의 시작·끝 이동값이 필요합니다.')
        if cue['effect']=='polygon_wipe':
            for key in ('from_points','to_points'):
                points=cue.get(key);need(isinstance(points,list) and 3<=len(points)<=16,'노출 다각형은 점3~16개입니다.')
                for point in points:
                    need(isinstance(point,list) and len(point)==2,'노출 다각형 좌표 오류')
                    for value in point:numeric(value,'노출 다각형 비율',0,100)
            need(len(cue['from_points'])==len(cue['to_points']),'노출 다각형의 점 개수가 다릅니다.')
        if cue['effect']=='grayscale':
            need('from' in cue and 'to' in cue,'흑백 전환의 시작과 끝 비율을 지정하세요.')
        if cue['effect']=='rotate':
            need(cue.get('axis','z') in ('x','y','z'),'회전 축은 x, y 또는 z입니다.')
            if cue.get('axis','z')!='z':
                need('from' in cue and 'to' in cue,'입체 회전의 시작과 끝 각도를 지정하세요.')
        if cue['effect']=='gear_spin':
            need(cue['target'] in group_lookup and group_lookup[cue['target']].get('clip')=='gear','톱니 회전은 gear 묶음에만 지정하세요.')
            need('from' in cue and 'to' in cue,'톱니 회전 시작과 끝 각도를 지정하세요.')
        if cue['effect']=='round_frame':
            need(cue['target'] in group_lookup and group_lookup[cue['target']].get('clip')=='rounded','둥근 프레임 변화는 rounded 묶음에만 지정하세요.')
            need('from' in cue and 'to' in cue,'프레임 모서리의 시작과 끝 비율을 지정하세요.')
        if cue['effect']=='count':
            node=lookup.get(cue['target']);node=node if node is not None and node['kind']=='text' else None
            need(node is not None,'숫자 변화는 글자 객체에만 지정하세요.')
            for key in ('from_value','to_value'):
                need(type(cue.get(key)) is int and abs(cue[key])<=10**12,'숫자 변화 값은 범위 안의 정수여야 합니다.')
            for key in ('prefix','suffix'):
                value=cue.get(key,'')
                need(isinstance(value,str) and len(value)<=24 and not any(ch in value for ch in '<>"\'\\\n\r\t'),'숫자 앞뒤 문구 형식 오류')
            need(type(cue.get('grouping',True)) is bool,'숫자 자릿수 구분 설정 오류')
            final=format(cue['to_value'],',d' if cue.get('grouping',True) else 'd')
            need(node['text']==cue.get('prefix','')+final+cue.get('suffix',''),'숫자 변화 최종값은 표시 문구와 같아야 합니다.')
            # Scans this scene's cues (<= 80); later cues are not validated yet, so no precomputed index.
            need(sum(c.get('effect')=='count' and c.get('target')==cue['target'] for c in cues)==1,'한 숫자 객체에는 변화 모션 하나만 지정하세요.')
        numeric(cue.get('at'),'모션 시작 비율',0,1);numeric(cue.get('duration'),'모션 지속 비율',.001,1)
        need(cue['at']+cue['duration']<=1.000001,'모션이 장면 끝을 넘습니다.')
        need(cue.get('ease','power2.out') in (AUTHORED_EASES if opened else LEGACY_EASES),'이징 오류')
        # Old (pre-B2) graphics: distance is not read and pop keeps .6/back.out(1.4) — exactly as before.
        if opened and 'distance' in cue:
            need(cue['effect'] in ('rise','slide'),'distance는 rise 또는 slide 등장에만 지정합니다.')
            if cue['effect']=='rise':
                numeric(cue['distance'],'rise 시작 거리',-600,600)
                need(cue['distance']!=0,'rise 시작 거리 0은 움직임이 없습니다. 생략하면 기본 55px입니다.')
            else:numeric(cue['distance'],'slide 시작 거리',20,1920)
        for key in ('x','y','from_x','from_y'):numeric(cue.get(key,0),'모션 이동',-1920,1920)
        # A vector-only group can move from a whole object to its detail without
        # magnifying raster pixels. Keep image/video and standalone limits intact.
        # group_members walks objects (<= 30) x group depth (<= 8) for a zoom cue only.
        vector_camera=(cue['effect']=='zoom' and cue['target'] in group_ids and
                       all(n['kind'] in ('path','text') for n in group_members(shot,cue['target'])))
        max_scale=4 if vector_camera else 1.5
        if opened and cue['effect']=='pop' and 'from_scale' in cue:
            # pop's opening scale has its own range: below 1 grows in, above 1 «stamps» down to 1.
            numeric(cue['from_scale'],'pop 시작 배율',.05,3)
            need(cue['from_scale']!=1,'pop 시작 배율 1은 움직임이 없습니다. 생략하면 기본 0.6입니다.')
        else:numeric(cue.get('from_scale',1),'시작 모션 배율',.5,max_scale)
        numeric(cue.get('scale',1),'모션 배율',.5,max_scale)
        bounds={'focus':(0,90),'rotate':(-180,180),'round_frame':(0,.5),'gear_spin':(-3600,3600)}.get(cue['effect'],(0,1))
        if cue['effect']=='rotate' and cue.get('axis','z')!='z':bounds=(-3600,3600)
        for key in ('from','to'):numeric(cue.get(key,0 if key=='from' else 1),'모션 상태',*bounds)
        if cue['effect']=='zoom':need('scale' in cue,'확대 배율을 지정하세요.')
        need(cue.get('direction',1) in (-1,1),'등장 방향 오류')
        if cue['effect']=='text_wipe':
            need(cue['target'] in lookup and lookup[cue['target']]['kind']=='text','문구 노출은 글자 객체에만 적용합니다.')
            # Scans this scene's cues (<= 80); later cues are not validated yet, so no precomputed index.
            need(sum(c['target']==cue['target'] and c['effect']=='text_wipe' for c in cues)==1,'문구 노출은 한 객체당 하나만 지정하세요.')
            numeric(cue.get('feather',8),'문구 노출 경계 비율',0,30)
            need(cue.get('axis','y') in ('x','y'),'문구 노출 축은 x 또는 y입니다.')
            if cue.get('axis','y')=='x':
                node=lookup[cue['target']]
                need('\n' not in node['text'],'가로 문구 노출은 줄마다 별도 객체와 시점을 지정하세요.')
            need(not any(c['target']==cue['target'] and c['effect']=='count' for c in cues),'숫자 변화와 문구 노출은 별도 객체로 분리하세요.')
        if cue['effect']=='object_glitch':
            n=lookup.get(cue['target'])
            need(n is not None and n['kind']=='image' and n.get('role')!='background_texture' and 'tile_scale' not in n,'국소 글리치는 배경 질감이 아닌 이미지 객체에만 적용합니다.')
            # Scans this scene's cues (<= 80); later cues are not validated yet, so no precomputed index.
            need(sum(c['target']==cue['target'] and c['effect']=='object_glitch' for c in cues)==1,'국소 글리치는 한 객체당 하나만 지정하세요.')
            numeric(cue.get('strength',6),'국소 글리치 강도',0,30)
            need(type(cue.get('seed',17)) is int and 0<=cue.get('seed',17)<=65535,'국소 글리치 seed 범위 오류')
        if cue['effect']=='pattern_pan':need(cue['target'] in lookup and lookup[cue['target']]['kind']=='path' and 'pattern_height' in lookup[cue['target']],'반복 필드 이동은 pattern_height가 있는 path에만 적용합니다.')
        if cue['effect']=='paper_reveal':need(cue['target'] in lookup and 'paper_reveal' in lookup[cue['target']],'종이 노출 모션은 paper_reveal이 있는 객체에만 지정하세요.')
        if cue['effect']=='brush_reveal':need(cue['target'] in lookup and 'brush_reveal' in lookup[cue['target']],'붓 노출 모션은 brush_reveal이 있는 객체에만 지정하세요.')
        if cue['effect']=='draw':need(cue['target'] in lookup and lookup[cue['target']]['kind']=='path' and 'pattern_height' not in lookup[cue['target']],'선 그리기는 반복 필드가 아닌 path 객체에만 적용합니다.')
    opacity_cues=[c for c in cues if c['effect'] in ('fade','rise','slide','pop')]
    # Only same-target pairs can conflict: walk each cue against the later cues of its own target, in the
    # same (earlier, later) order as the former all-pairs scan, so the first conflict reported is the same.
    by_target={};rank=[]
    for c in opacity_cues:
        same=by_target.setdefault(c['target'],[]);rank.append(len(same));same.append(c)
    for index,a in enumerate(opacity_cues):
        for b in by_target[a['target']][rank[index]+1:]:
            if a==b:continue
            overlap=min(a['at']+a['duration'],b['at']+b['duration'])-max(a['at'],b['at'])
            need(overlap<=1e-7,'같은 객체의 등장·불투명도 모션 시간을 겹치지 마세요: '+a['target'])
    # Every cue is validated by now: index them once by (target, effect), in cue order.
    reveal_cues={}
    for c in cues:reveal_cues.setdefault((c['target'],c['effect']),[]).append(c)
    for node in objects:
        if 'brush_reveal' in node:
            reveals=reveal_cues.get((node['id'],'brush_reveal'),[])
            need(len(reveals)==1,'붓 노출 객체에는 노출 모션 하나가 필요합니다.')
            if node['kind']=='video':
                cue=reveals[0];start=node.get('at',0);end=start+node.get('duration',1)
                need(start<=cue['at'] and cue['at']+cue['duration']<=end+1e-7,'붓 노출은 실제 영상 재생 구간 안에 있어야 합니다.')
        if 'paper_reveal' in node:
            reveals=reveal_cues.get((node['id'],'paper_reveal'),[])
            need(len(reveals)==1,'종이 노출 객체에는 노출 모션 하나가 필요합니다.')
            if node['kind']=='video':
                cue=reveals[0];start=node.get('at',0);end=start+node.get('duration',1)
                need(start<=cue['at'] and cue['at']+cue['duration']<=end+1e-7,'종이 노출은 실제 영상 재생 구간 안에 있어야 합니다.')


def validate_crop(crop):
    need(isinstance(crop,list) and len(crop)==4,'자르기 영역은 원본 좌표 4개입니다.')
    for value in crop:numeric(value,'자르기 좌표',0,100000)
    need(crop[2]>crop[0] and crop[3]>crop[1],'자르기 영역이 비었습니다.')


def opening_review(plan, voices):
    """Advisory only: source images delayed by their own or parent entrance."""
    candidates=[]
    for block,voice in zip(plan['blocks'],voices):
        visual=block['visual']
        if visual.get('kind')!='graphic' or visual.get('template')!='authored':continue
        seconds=voice['frames']/60;entrances={}
        for cue in visual.get('motion_cues',[]):
            if cue['effect'] not in ('rise','slide','pop','fade'):continue
            at=cue['at']*seconds
            if 'start_char' in cue:
                chars=voice.get('characters',[]);i=cue['start_char']
                if not 0<=i<len(chars):continue  # Rendering's alignment gate owns invalid anchors.
                at=chars[i]['start']
            initial=cue.get('from',0) if cue['effect']=='fade' else 0
            target=cue['target']
            if target not in entrances or at<entrances[target][0]:entrances[target]=(at,initial)
        for obj in visual.get('objects',[]):
            if obj['kind'] not in ('image','video'):continue
            visible=obj.get('at',0)*seconds if obj['kind']=='video' else 0
            for target in [obj['id'],obj.get('group')]:
                at,initial=entrances.get(target,(0,1))
                if initial<=0:visible=max(visible,at)
            if visible>=2:
                candidates.append({'block':block['id'],'object':obj['id'],'first_visible_seconds':round(visible,6),
                                   'reason':'자료가 늦게 등장합니다. 앞 구도가 충분한지 확인하고, 의도된 순차 설명이면 유지하세요.'})
    return {'schema':'geumbit-opening-review-v1','automatic_failure':False,
            'scope':'계획과 실제 발화 시간의 검토 후보이며, 화면 면적·연출 품질 판정이나 직접 시청을 대신하지 않습니다.',
            'candidates':candidates}
