"""Parameterized versions of the approved pilot's actual graphic layouts/textures."""
from pathlib import Path
import html
import json
import re
import shutil
from PIL import Image, ImageFont
from longform_state import ProductionError, native_path
from longform_contract import GRAPHIC_FONTS,TEMPLATE_THEMES,cue_ease,opened_motion,authored_value

def number_markup(value):
    match=re.fullmatch(r'([+-]?[0-9][0-9,.]*)([^0-9]*)',str(value))
    if not match:raise ProductionError('graphic_number_format','숫자와 단위를 확인하세요: '+str(value),action='edit_plan')
    number,unit=match.groups()
    return html.escape(number)+'<small>'+html.escape(unit)+'</small>'

def document(folder, visual, seconds, fonts, media, *, preview=False, handle_seconds=0, lang='ko'):
    render_seconds=seconds+handle_seconds
    folder=Path(folder);assets=folder/'assets';assets.mkdir(exist_ok=True)
    bank=Path(fonts).parent
    for name in ('gsap.min.js','charcoal-paper.png','brown-wallpaper.png'):
        shutil.copy2(bank/name,assets/name)
    (assets/'fonts').mkdir(exist_ok=True)
    families={'Hand','Paper','Body'} | {n.get('font','Hand') for n in visual.get('objects',[]) if n.get('kind')=='text'}
    for name in sorted({GRAPHIC_FONTS[f] for f in families}):
        shutil.copy2(Path(fonts)/name,assets/'fonts'/name)
    css=(bank/'approved-graphic.css').read_text(encoding='utf-8')
    for family in sorted(families):
        # Quote the alias: unquoted Serif is a CSS generic family and silently
        # falls back to a system font instead of loading our bundled font.
        css+=f"\n@font-face{{font-family:'{family}';src:url('assets/fonts/{GRAPHIC_FONTS[family]}')}}"
    css+='\n.big-num,.count{white-space:nowrap}'
    paths=[]
    for i,mid in enumerate(visual.get('media',[])):
        source=Path(media[mid]['path']);name=f'media-{i}'+source.suffix.lower()
        shutil.copy2(source,assets/name);paths.append('assets/'+name)
    esc=lambda value:html.escape(str(value),quote=True)
    def fit(value,font,maximum,width,minimum=28):
        for size in range(maximum,minimum-1,-1):
            face=ImageFont.truetype(str(Path(fonts)/font),size)
            if max(face.getlength(line) for line in str(value).split('\n'))<=width:return size
        raise ProductionError('graphic_text_overflow','그래픽 문구를 줄이세요: '+str(value),action='edit_plan')
    def number_sizes(value,maximum,unit_max,width,margin=0):
        match=re.fullmatch(r'([+-]?[0-9][0-9,.]*)([^0-9\n]*)',str(value))
        if not match:raise ProductionError('graphic_number_format','숫자와 단위를 확인하세요: '+str(value),action='edit_plan')
        for size in range(maximum,47,-1):
            unit=max(28,round(unit_max*size/maximum))
            main_font=ImageFont.truetype(str(Path(fonts)/'Paperlogy-8ExtraBold.ttf'),size)
            unit_font=ImageFont.truetype(str(Path(fonts)/'Paperlogy-8ExtraBold.ttf'),unit)
            if main_font.getlength(match[1])+unit_font.getlength(match[2])+(margin if match[2] else 0)<=width:return size,unit
        raise ProductionError('graphic_text_overflow','숫자 표기를 줄이거나 다른 단위로 설명하세요: '+str(value),action='edit_plan')
    labels=[esc(x) for x in visual['labels']];title=esc(visual['title'])
    # Fixed templates paint the theme from the contract's one table (B2): unique-v1 keys backgrounds by it.
    template=visual['template'];events=[];theme=TEMPLATE_THEMES.get(template,'charcoal')
    if template=='authored':
        body,extra_css=authored_body(visual,paths,folder,seconds,preview=preview,handle_seconds=handle_seconds,assets=Path(fonts).parent)
        css+=extra_css;theme=visual.get('theme','charcoal')
    elif template in ('document','debate','timeline','question','layers','balance','callout'):
        # Different editorial jobs have different geometry, not just a new colour
        # on the same three cards. All text is authored; no facts are invented here.
        css+='''
.editor-title{position:absolute;left:125px;top:200px;width:1670px;line-height:1.15}
.editor-note{font-family:Body;line-height:1.45;white-space:pre-line}
.editor-label{font-family:Paper;line-height:1.2;white-space:nowrap}
.editor-item{position:absolute;transform-origin:center}
.editor-svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.paper-leaf{background:#f0e7d3;color:#241f19;border:4px solid #211b17;box-shadow:14px 17px #140e1780}
.editor-caption{position:absolute;left:180px;right:180px;top:795px;text-align:center;color:#f2d774;font-size:30px}
'''
        title_size=fit(visual['title'],'BMYEONSUNG.ttf',86,1650)
        body=f'<div class="hand editor-title" style="font-size:{title_size}px">{title}</div>'
        def copy(index,width,label_max=66,note_max=40):
            label=visual['labels'][index];note=visual.get('notes',['']*len(labels))[index]
            if len(note.split('\n'))>3:raise ProductionError('graphic_text_overflow','도표 본문은 최대 3줄입니다.',action='edit_plan')
            return (f'<div class="editor-label" style="font-size:{fit(label,"Paperlogy-8ExtraBold.ttf",label_max,width)}px">{esc(label)}</div>'
                    + (f'<div class="editor-note" style="margin-top:22px;font-size:{fit(note,"ROKAFSansMedium.ttf",note_max,width)}px">{esc(note)}</div>' if note else ''))
        if template=='document':
            css+='''#source-leaf{left:165px;top:325px;width:1050px;height:485px;padding:42px 60px;transform:rotate(-2deg)}
.document-row{position:relative;padding:8px 0 17px;border-bottom:2px solid #95876e;margin-bottom:15px}
.document-row .editor-label{background:linear-gradient(transparent 55%,#e8c33490 55%);background-repeat:no-repeat;display:inline}
.document-row .editor-note{margin-top:5px!important}
#reading-note{left:1320px;top:410px;width:420px;font-size:77px;line-height:1.35}'''
            body+='<div id="source-leaf" class="editor-item paper-leaf">'+''.join(f'<div id="doc-{i}" class="document-row">{copy(i,910,45,29)}</div>' for i in range(3))+'</div>'
            from longform_render import screen_words
            body+='<div id="reading-note" class="editor-item hand">'+'<br>'.join(html.escape(x) for x in screen_words(lang)['reading_order'].split('\n'))+'</div>'
            events=[('#source-leaf',0),('#doc-0',.1),('#doc-1',1.2),('#doc-2',2.4),('#reading-note',.4)]
        elif template=='debate':
            css+='''.speech{width:700px;min-height:315px;border-radius:38px;padding:40px 48px;border:6px solid #21182b;color:#261a18;background:#f7efd9;box-shadow:13px 15px #1b0e28}
.speech:after{content:"";position:absolute;bottom:-44px;width:65px;height:48px;background:#f7efd9;clip-path:polygon(0 0,100% 0,0 100%)}
#argument-a{left:170px;top:335px;transform:rotate(-3deg)}#argument-b{left:1045px;top:470px;transform:rotate(3deg)}
#argument-b:after{right:30px;transform:scaleX(-1)}#versus{left:889px;top:435px;font-size:82px}'''
            body+=f'<div id="argument-a" class="editor-item speech">{copy(0,590)}</div><div id="argument-b" class="editor-item speech">{copy(1,590)}</div><div id="versus" class="editor-item hand">↔</div>'
            events=[('#argument-a',0),('#versus',.9),('#argument-b',1.45)]
        elif template=='timeline':
            body+='<svg class="editor-svg" viewBox="0 0 1920 1080"><path id="sequence-line" d="M397 406 C650 406 700 576 957 576 S1280 406 1517 406 H1650" fill="none" stroke="#efcf70" stroke-width="12" stroke-linecap="round"/><path d="M1620 375 L1660 406 L1620 437" fill="none" stroke="#efcf70" stroke-width="12"/></svg>'
            for i,left in enumerate((160,720,1280)):
                body+=f'<div id="step-{i}" class="editor-item" style="left:{left}px;top:{370 if i!=1 else 540}px;width:475px;text-align:center"><div style="width:72px;height:72px;border:5px solid #302619;background:#edce69;border-radius:50%;margin:0 auto 28px;color:#261b18;font-family:Paper;font-size:45px">{i+1}</div>{copy(i,475,64,37)}</div>'
            events=[('#sequence-line',0),('#step-0',.15),('#step-1',1.3),('#step-2',2.5)]
        elif template=='question':
            css+='''#question-mark{left:210px;top:370px;font-family:Hand;font-size:435px;line-height:1;color:#fac02d;transform:rotate(-12deg)}
#question-first{left:670px;top:380px;width:1070px}#question-second{left:760px;top:600px;width:950px;color:#fff5de}
#question-stroke{position:absolute;left:680px;top:545px;width:990px;height:10px;background:#efcc63;transform:rotate(-2deg)}'''
            body+=f'<div id="question-mark" class="editor-item ink">?</div><div id="question-first" class="editor-item hand" style="font-size:{fit(visual["labels"][0],"BMYEONSUNG.ttf",112,1050)}px">{labels[0]}</div><div id="question-stroke"></div><div id="question-second" class="editor-item" style="font-size:{fit(visual["labels"][1],"ROKAFSansMedium.ttf",59,950)}px">{labels[1]}</div>'
            events=[('#question-mark',0),('#question-first',.2),('#question-stroke',.7),('#question-second',1.6)]
        elif template=='layers':
            # Rotated paper needs room around both text and neighbouring sheets.
            # A long label formerly reached the index's rotated bounding box.
            for i,(left,top) in enumerate(((110,330),(710,380),(1310,430))):
                body+=f'<div id="layer-{i}" class="editor-item paper-leaf" style="left:{left}px;top:{top}px;width:520px;height:390px;padding:30px 36px;transform:rotate({(-4,2,-2)[i]}deg)"><div style="font-family:Body;color:#7c6746;font-size:27px;margin-bottom:40px">{i+1:02d}</div>{copy(i,440,59,34)}</div>'
            events=[('#layer-0',0),('#layer-1',1.25),('#layer-2',2.6)]
        elif template=='balance':
            body+='<svg class="editor-svg" viewBox="0 0 1920 1080">'
            for shape,ident in [('M960 350 V815 M825 815 H1095','balance-base'),('M460 425 H1460 M460 425 L320 650 H600 Z M1460 425 L1320 650 H1600 Z','balance-arm')]:
                body+=f'<g id="{ident}">'+''.join(f'<path d="{shape}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" fill="none"/>' for color,width in [('#21192a',22),('#efcf70',10)])+'</g>'
            body+='</svg>'
            for i,left in enumerate((145,1145)):
                body+=f'<div id="weigh-{i}" class="editor-item" style="left:{left}px;top:695px;width:630px;text-align:center">{copy(i,630,58,33)}</div>'
            events=[('#weigh-0',.1),('#weigh-1',1.4)]
        elif template=='callout':
            from PIL import Image
            with Image.open(media[visual['media'][0]]['path']) as original:
                ratio=min(1420/original.width,620/original.height);iw=original.width*ratio;ih=original.height*ratio
            ix=(1920-iw)/2;iy=235+(620-ih)/2
            body=f'<img id="annotated-source" class="editor-item" src="{paths[0]}" style="left:{ix}px;top:{iy}px;width:{iw}px;height:{ih}px;object-fit:contain" alt="출처 자료">'
            body+=f'<div class="hand editor-title" style="font-size:{title_size}px">{title}</div>'
            for i,(mx,my) in enumerate(visual['markers']):
                x=ix+mx*iw;y=iy+my*ih;lx=100 if i==0 else 1330;ly=390 if i==0 else 670
                body+=f'<svg id="pointer-{i}" class="editor-svg" viewBox="0 0 1920 1080"><path d="M{lx+240} {ly+75} Q{(lx+240+x)/2} {ly+150} {x} {y}" stroke="#f5d336" stroke-width="7" fill="none"/><circle cx="{x}" cy="{y}" r="58" stroke="#f5d336" stroke-width="7" fill="none"/></svg><div id="annotation-{i}" class="editor-item label-tag" style="left:{lx}px;top:{ly}px;font-size:{fit(visual["labels"][i],"Paperlogy-8ExtraBold.ttf",48,440)}px">{labels[i]}</div>'
            events=[('#annotated-source',0),('#pointer-0',.6),('#annotation-0',.6),('#pointer-1',2),('#annotation-1',2)]
    elif template=='story':
        css+=f'\n#cow-note{{font-size:{fit(visual["title"],"BMYEONSUNG.ttf",86,1160)}px}}'
        css+=f'\n#cow-money{{font-size:{fit(visual["labels"][0],"BMYEONSUNG.ttf",160,1030)}px}}'
        body=f'<img class="story" src="{paths[0]}" alt="설명용 삽화"><div id="cow-note" class="hand yellow">{title}</div><div id="cow-money" class="hand yellow">{labels[0]}</div>'
        events=[('#cow-note',.13),('#cow-money',1.83)]
    elif template=='context':
        for suffix,value,width in zip('abc',visual['labels'],(800,830,1100)):
            css+=f'\n#context-{suffix}{{font-size:{fit(value,"BMYEONSUNG.ttf",92,width)}px}}'
        body=f'<img class="story" src="{paths[0]}" alt="설명용 삽화">'+''.join(f'<div id="context-{c}" class="hand context">{v}</div>' for c,v in zip('abc',labels))
        events=[('#context-a',.05),('#context-b',1.35),('#context-c',3.05)]
    elif template=='comparison':
        dates=[esc(x) for x in visual['dates']]
        for sid,value in zip(('june','oct'),visual['dates']):
            css+=f'\n#{sid} .date{{font-size:{fit(value,"Paperlogy-8ExtraBold.ttf",40,790)}px}}'
        for sid,value in zip(('june','oct'),visual['labels']):
            main_size,unit_size=number_sizes(value,138,47,820,18)
            css+=f'\n#{sid} .count{{font-size:{main_size}px}}#{sid} .count small{{font-size:{unit_size}px}}'
        body=''.join(f'<div id="{sid}" class="split-card"><img src="{path}" alt="기록 사진"><div class="shade"></div><div class="date">{date}</div><div class="count ink yellow">{number_markup(html.unescape(label))}</div></div>' for sid,path,date,label in zip(('june','oct'),paths,dates,labels))
        events=[('#oct .count',.25)]
    elif template=='numbers':
        dates=[esc(x) for x in visual['dates']]
        css+=f'\n#sum-title{{font-size:{fit(visual["title"],"BMYEONSUNG.ttf",65,1460)}px}}'
        for sid,date,value in zip(('left-num','right-num'),visual['dates'],visual['labels']):
            main_size,unit_size=number_sizes(value,170,52,590)
            css+=f'\n#{sid} .num-date{{font-size:{fit(date,"ROKAFSansMedium.ttf",38,590)}px}}#{sid} .big-num{{font-size:{main_size}px}}#{sid} .big-num small{{font-size:{unit_size}px}}'
        for total_size in range(99,27,-1):
            label_size=max(28,round(39*total_size/99))
            total_font=ImageFont.truetype(str(Path(fonts)/'Paperlogy-8ExtraBold.ttf'),total_size)
            label_font=ImageFont.truetype(str(Path(fonts)/'Paperlogy-8ExtraBold.ttf'),label_size)
            if total_font.getlength(visual['total'])+label_font.getlength(visual['total_label'])+32<=1200:break
        else:raise ProductionError('graphic_text_overflow','합계 문구가 화면 폭을 넘습니다.',action='edit_plan')
        css+=f'\n#total{{font-size:{total_size}px}}#total small{{font-size:{label_size}px}}'
        body=f'<div id="sum-title" class="hand">{title}</div>'
        for sid,date,label in zip(('left-num','right-num'),dates,labels):
            body+=f'<div id="{sid}" class="num-group"><div class="num-date">{date}</div><div class="big-num ink">{number_markup(html.unescape(label))}</div></div>'
        total=re.fullmatch(r'([+-]?[0-9][0-9,.]*)([^0-9]*)',str(visual['total']))
        if not total:raise ProductionError('graphic_number_format','합계 숫자와 단위를 확인하세요.',action='edit_plan')
        total_html='<span class="yellow">'+esc(total[1])+'</span>'+esc(total[2])
        body+=f'<div id="sum-plus" class="sum-plus ink">+</div><div id="sum-line"></div><div id="total" class="ink"><small>{esc(visual["total_label"])}</small>{total_html}</div>'
        events=[('#left-num',0),('#sum-plus',.7),('#right-num',1.1),('#total',2.95)]
    elif template=='explanation':
        title_size=fit(visual['title'],'BMYEONSUNG.ttf',70,1600)
        body=f'<div id="three-heading" class="hand" style="font-size:{title_size}px">{title}</div>'
        for sid,label,note in zip(('meaning-a','meaning-b','meaning-c'),visual['labels'],visual['notes']):
            if len(note.split('\n'))>4:raise ProductionError('graphic_text_overflow','설명 카드 본문은 최대 4줄입니다.',action='edit_plan')
            label_size=fit(label,'Paperlogy-8ExtraBold.ttf',76,400)
            note_size=fit(note,'ROKAFSansMedium.ttf',35,400)
            body+=f'<div id="{sid}" class="meaning-card"><div class="meaning-title" style="font-size:{label_size}px">{esc(label)}</div><div class="meaning-rule"></div><div class="meaning-copy" style="font-size:{note_size}px;white-space:pre-line">{esc(note)}</div></div>'
        events=[('#meaning-a',.05),('#meaning-b',1.35),('#meaning-c',3.05)]
    elif template=='identity':
        if visual.get('face'):
            face=visual['face']
            portrait=f'<div id="hybrid"><img id="suit" src="{paths[0]}" alt="설명용 몸체"><svg id="real-head" viewBox="{esc(face["view_box"])}" xmlns="http://www.w3.org/2000/svg"><defs><clipPath id="face-mask"><path d="{esc(face["path"])}"/></clipPath></defs><image data-layout-allow-overflow="true" href="{paths[1]}" width="{face["width"]}" height="{face["height"]}" clip-path="url(#face-mask)"/></svg></div>'
            selector='#hybrid'
        else:
            portrait=f'<img id="portrait" src="{paths[0]}" alt="인물 누끼">';selector='#portrait'
            css+='\n#portrait{left:90px;top:195px;width:780px;height:805px;object-fit:contain}'
        body=portrait+f'<div id="intro-copy"><div class="label-tag" id="intro-tag">{labels[0]}</div><div id="intro-name" class="ink">{title}</div><div id="intro-role" class="hand yellow">{labels[1]}</div></div>'
        css+=f'\n#intro-name{{font-size:{fit(visual["title"],"BMYEONSUNG.ttf",165,850)}px}}'
        css+=f'\n#intro-role{{font-size:{fit(visual["labels"][1],"BMYEONSUNG.ttf",75,800)}px}}'
        css+=f'\n#intro-tag{{font-size:{fit(visual["labels"][0],"Paperlogy-8ExtraBold.ttf",40,720)}px}}'
        events=[(selector,0),('#intro-tag',.2),('#intro-name',.45),('#intro-role',.9)]
    else:raise ProductionError('unknown_graphic_template',template)
    script, motion = authored_motion(visual,seconds) if template=='authored' else choreography(template, events, seconds, visual)
    # Standalone documents and the renderer share the same registration path.
    # Keep any timelines already installed by the composition host.
    script='window.__timelines=window.__timelines||{};'+script
    (folder/'motion.json').write_text(json.dumps(motion,ensure_ascii=False,indent=2),encoding='utf-8')
    scene_timing='' if any(n.get('kind')=='video' for n in visual.get('objects',[])) else f' data-start="0" data-duration="{render_seconds}"'
    # Keep the composition root before bundled JS: HyperFrames 0.8.80's
    # WebGPU tag scan can overflow on '<' operators in an inlined GSAP script.
    # GSAP still loads synchronously before the authored timeline script.
    result=f'<!doctype html><html lang="{html.escape(lang)}"><head><meta charset="utf-8"><style>{css}</style></head><body><div id="root" data-composition-id="graphic" data-width="1920" data-height="1080" data-duration="{render_seconds}"><section id="graphic-scene" class="clip {theme}"{scene_timing}><div class="grain"></div>{body}</section></div><script src="assets/gsap.min.js"></script><script>{script}</script></body></html>'
    (folder/'index.html').write_text(result,encoding='utf-8')
    return folder/'index.html'


def choreography(template, events, seconds, visual):
    """Seekable, finite motion with an inspectable schedule, not an entrance loop.

    Timing is authored relative to a shot, unless narration-aligned beat_seconds
    are supplied. These are editorial choices, not measurements of the source.
    """
    duration=float(seconds)
    if duration<=0:raise ProductionError('motion_duration','장면 길이는 양수여야 합니다.')
    cues=[];script=['const tl=gsap.timeline({paused:true});']
    def tween(target, start, end, at, length, technique):
        at=max(0.,min(float(at),duration-.001));length=max(.001,min(float(length),duration-at))
        end={**end,'duration':round(length,6),'ease':end.get('ease','power2.out')}
        script.append('tl.fromTo('+json.dumps(target)+','+json.dumps(start)+','+json.dumps(end)+','+str(round(at,6))+');')
        cues.append({'target':target,'start':round(at,6),'end':round(at+length,6),'technique':technique})
    # Keep the title still and legible. Different explanatory structures get
    # different action: read, connect, compare, question, stack, or locate.
    beat=visual.get('beat_seconds')
    def when(i,n):
        return float(beat[i]) if beat and i<len(beat) else duration*(.04+.66*i/max(1,n-1))
    if template=='timeline':
        tween('#sequence-line',{'strokeDasharray':1800,'strokeDashoffset':1800},
              {'strokeDashoffset':0,'ease':'none'},0,duration*.78,'trim-path')
        for i in range(3):
            at=when(i,3)
            tween('#step-'+str(i),{'opacity':0,'y':35},{'opacity':1,'y':0},at,.55,'stagger-rise')
            tween('#step-'+str(i)+' .editor-label',{'color':'#ffffff'},
                  {'color':'#fac02d','ease':'none'},at+.55,duration*.18,'reading-focus')
    elif template=='document':
        tween('#source-leaf',{'opacity':0,'x':-95},{'opacity':1,'x':0},0,.6,'paper-slide')
        for i in range(3):
            at=when(i,3)
            tween('#doc-'+str(i),{'opacity':0,'x':30},{'opacity':1,'x':0},at,.55,'read-line')
            tween('#doc-'+str(i)+' .editor-label',{'backgroundSize':'0% 100%'},
                  {'backgroundSize':'100% 100%','ease':'none'},at+.55,duration*.2,'highlight-wipe')
        tween('#reading-note',{'opacity':0,'y':30},{'opacity':1,'y':0},duration*.52,.5,'margin-note')
    elif template=='debate':
        for i,target in enumerate(('#argument-a','#argument-b')):
            at=when(i,2)
            tween(target,{'opacity':0,'x':(-85 if i==0 else 85)},
                  {'opacity':1,'x':0},at,.55,'opposed-slide')
            tween(target,{'y':0},{'y':(-14 if i==0 else 14),'ease':'sine.inOut'},at+.55,duration-at-.55,'conversation-depth')
        tween('#versus',{'opacity':0,'scaleX':0},{'opacity':1,'scaleX':1},duration*.42,.6,'connection')
    elif template=='question':
        tween('#question-mark',{'opacity':0,'scale':.5},{'opacity':1,'scale':1,'ease':'back.out(1.3)'},0,.65,'overshoot')
        tween('#question-mark',{'y':0},{'y':-22,'ease':'sine.inOut'},.65,duration-.65,'question-rise')
        tween('#question-first',{'opacity':0,'x':65},{'opacity':1,'x':0},duration*.08,.6,'question-reveal')
        tween('#question-stroke',{'scaleX':0,'transformOrigin':'left center'},
              {'scaleX':1,'ease':'none'},duration*.28,duration*.3,'underline-write')
        tween('#question-second',{'opacity':0,'y':38},{'opacity':1,'y':0},when(1,2),.6,'answer-reveal')
    elif template=='layers':
        for i in range(3):
            at=when(i,3)
            tween('#layer-'+str(i),{'opacity':0,'y':90},{'opacity':1,'y':0},at,.7,'paper-follow-through')
            tween('#layer-'+str(i),{'x':0},{'x':(-10+i*10),'ease':'sine.inOut'},at+.7,duration-at-.7,'layer-parallax')
    elif template=='balance':
        for i in range(2):
            at=when(i,2)
            tween('#weigh-'+str(i),{'opacity':0,'y':30},{'opacity':1,'y':0},at,.6,'comparison-label')
        # The illustration rocks then comes level: it does not claim one side
        # has a numerically greater weight. The base remains fixed.
        tween('#balance-arm',{'rotation':-5,'svgOrigin':'960 425'},
              {'rotation':4,'ease':'sine.inOut'},0,duration*.42,'balance-question')
        tween('#balance-arm',{'rotation':4,'svgOrigin':'960 425'},
              {'rotation':0,'ease':'sine.inOut','immediateRender':False},duration*.42,duration*.55,'balance-settle')
    elif template=='callout':
        tween('#annotated-source',{'opacity':0},{'opacity':1},0,.3,'source-reveal')
        for i in range(2):
            at=when(i,2)
            tween('#pointer-'+str(i)+' path',{'strokeDasharray':1800,'strokeDashoffset':1800},
                  {'strokeDashoffset':0,'ease':'none'},at,duration*.23,'pointer-write')
            tween('#pointer-'+str(i)+' circle',{'opacity':0},{'opacity':1},at+duration*.13,.5,'locate-detail')
            tween('#annotation-'+str(i),{'opacity':0,'x':(-30 if i==0 else 30)},
                  {'opacity':1,'x':0},at+duration*.16,.6,'detail-label')
    else:
        last=max(t+.18 for _,t in events)
        for target,original in events:
            at=(original/last)*duration*.65
            tween(target,{'opacity':0,'y':25},{'opacity':1,'y':0},at,.5,'stagger-reveal')
        if template=='identity':
            target='#hybrid' if visual.get('face') else '#portrait'
            tween(target,{'x':-35,'scale':.96},{'x':24,'scale':1.035,'ease':'none'},0,duration,'portrait-parallax')
        if template in ('story','context'):
            tween('.story',{'scale':1},{'scale':1.035,'ease':'none'},0,duration,'illustration-push')
        if template=='numbers':
            tween('#sum-line',{'scaleX':0,'transformOrigin':'left center'},{'scaleX':1},duration*.58,.5,'sum-rule')
    script.append('window.__timelines["graphic"]=tl;')
    return ''.join(script),{'schema':'geumbit-motion-v1','template':template,'duration':duration,
        'basis':'authored editorial choreography; not measured original timings','cues':cues}


def gear_clip(group):
    """An independently animated aperture; media descendants keep their pose.

    Geometry is authored, not recovered editor parameters. Even-odd clipping
    exposes the background through both the teeth gaps and central hole.
    """
    import math
    config=group.get('gear',{});teeth=config.get('teeth',16)
    root=config.get('root_radius',.42);hole=config.get('hole_radius',.1)
    points=[]
    for tooth in range(teeth):
        for phase,radius in ((0,root),(.18,.5),(.62,.5),(.8,root)):
            angle=2*math.pi*(tooth+phase)/teeth
            points.append((.5+radius*math.cos(angle),.5+radius*math.sin(angle)))
    path='M '+' L '.join(f'{x:.8f} {y:.8f}' for x,y in points)+' Z'
    if hole:
        path+=f' M {.5-hole} .5 A {hole} {hole} 0 1 0 {.5+hole} .5 A {hole} {hole} 0 1 0 {.5-hole} .5 Z'
    gid=html.escape(group['id'],quote=True)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position:absolute" aria-hidden="true"><defs><clipPath id="gear-clip-{gid}" clipPathUnits="objectBoundingBox"><path id="gear-mask-{gid}" d="{path}" clip-rule="evenodd" fill-rule="evenodd"/></clipPath></defs></svg>'


# Authored smooth scallops, based on inspected Haaland 1081.5–1083.
# This is not a claim of recovering the source editor's exact Bezier path.
THOUGHT_PATH = ('M .12 .27 C .10 .08 .29 .02 .37 .15 '
                'C .44 -.01 .63 .015 .68 .16 C .81 .075 .91 .18 .9 .30 '
                'C 1.03 .32 1.015 .55 .92 .61 C 1 .76 .88 .91 .77 .86 '
                'C .71 1.025 .50 1.015 .46 .91 C .31 1.005 .18 .925 .18 .85 '
                'C .04 .875 .02 .72 .065 .65 C -.025 .575 .01 .345 .12 .32 Z')


def thought_frame(nid, width, height, stroke_width=6, stroke_color='#FFFFFF'):
    """Shared normalized geometry for timed media clip and its visible outline."""
    esc=lambda value:html.escape(str(value),quote=True)
    clip_id='thought-clip-'+nid
    defs=f'<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><clipPath id="{esc(clip_id)}" clipPathUnits="objectBoundingBox"><path d="{THOUGHT_PATH}"/></clipPath></defs></svg>'
    # Use scene-pixel coordinates for stroke width, independent of aspect ratio.
    outline=f'<svg data-thought-outline="true" viewBox="0 0 {width} {height}" style="position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none" aria-hidden="true"><path d="{THOUGHT_PATH}" transform="scale({width} {height})" fill="none" stroke="{esc(stroke_color)}" stroke-width="{stroke_width}" vector-effect="non-scaling-stroke"/></svg>'
    return defs,'url(#'+clip_id+')',outline


def _first_by(rows,key):
    """{key(row): first row with that key} — one pass; replaces next(...) scans inside per-object/per-cue loops
    (6-00). First match wins, exactly like next() over the same list."""
    table={}
    for row in rows:table.setdefault(key(row),row)
    return table


def _first(table,key):
    # next(...) without a default raised StopIteration when nothing matched; keep that.
    try:return table[key]
    except KeyError:raise StopIteration from None


def authored_body(visual, paths, folder=None, seconds=None, *, preview=False, handle_seconds=0, assets=None):
    """Narrative-specific objects, independent of the small stock diagram set."""
    esc=lambda x:html.escape(str(x),quote=True)
    body=[];css='\n.scene-object{position:absolute;transform-origin:center;white-space:pre-line;line-height:1.2}\n'
    # Per-object lookups built once (first match, as the former next()/list.index() scans per object).
    wipes=_first_by((c for c in visual.get('motion_cues',[]) if c['effect']=='text_wipe'),lambda c:c['target'])
    paints={}
    for paint in visual.get('text_paints',[]):
        paints.setdefault(paint['front'],paint);paints.setdefault(paint['depth'],paint)
    media_index={}
    for i,mid in enumerate(visual['media']):media_index.setdefault(mid,i)
    def source_of(mid):
        if mid not in media_index:raise ValueError(f'{mid!r} is not in list')
        return paths[media_index[mid]]
    # Per-target color and focus channels compose instead of overwriting filter.
    gray_targets={c['target'] for c in visual.get('motion_cues',[]) if c['effect'] in ('grayscale','brightness')}
    for target in sorted(gray_targets):
        css+='#obj-'+target+'{--object-gray:0;--object-blur:0px;filter:grayscale(var(--object-gray,0)) blur(var(--object-blur,0px)) brightness(var(--object-bright,1))}\n'
    if visual.get('theme')=='blue':
        # Reuse the installed paper texture; no network asset or animated noise.
        # Separate dot, vignette, and paper layers keep the texture behind objects.
        css+='''.blue{background-color:#183c75;background-image:radial-gradient(ellipse at center,transparent 25%,#020b1ee8 100%),radial-gradient(circle,#78a8e526 .7px,transparent .9px),url('assets/charcoal-paper.png');background-size:100% 100%,4px 4px,100% 100%;background-blend-mode:normal,normal,soft-light}\n'''
    from longform_groups import members as group_members
    group_bounds={}
    for group in visual.get('groups',[]):
        # groups <= 8 x objects <= 30 x depth <= 8 (validate_authored caps) — scene-local.
        members=[n['box'] for n in group_members(visual,group['id'])]
        left=min(b[0] for b in members);top=min(b[1] for b in members)
        group_bounds[group['id']]=(left,top,max(b[0]+b[2] for b in members)-left,max(b[1]+b[3] for b in members)-top)
    for node in visual['objects']:
        x,y,w,h=node['box'];nid='obj-'+node['id']
        texture_id=f' id="texture-{nid}"' if 'texture_cadence' in node else ''
        if node.get('group'):
            gx,gy,_,_=group_bounds[node['group']];x-=gx;y-=gy
        style=f'left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
        if 'line_height' in node:style+=f'line-height:{node["line_height"]};'
        if 'shadow' in node and node['kind']!='image':
            shadow=node['shadow'];style+=f'filter:drop-shadow({shadow["x"]}px {shadow["y"]}px {shadow["blur"]}px {shadow["color"]});'
        if 'transform_origin' in node:
            ox,oy=node['transform_origin'];style+=f'transform-origin:{ox*100}% {oy*100}%;'
        if node['kind']=='text':
            style+=f'font-family:\'{node.get("font","Hand")}\';font-size:{node["size"]}px;color:{node["color"]};'
            # Keep text on a stable layer during opacity-based ink inspection.
            # Without this, Chromium can rerasterize scaled gold/depth glyphs
            # after hide/restore and invalidate the before/after evidence.
            style+='will-change:opacity;'
            if 'align' in node:style+=f'text-align:{node["align"]};'
            cls=' hand' if node.get('font','Hand')=='Hand' else ''
            if 'outline_width' in node:
                # Paint the stroke behind the fill so a readability outline does
                # not eat thin glyph strokes. The animated wrapper stays intact.
                style+=f'-webkit-text-stroke:{node["outline_width"]}px {node.get("outline_color","#141020")};paint-order:stroke fill;text-shadow:none;'
            content=esc(node['text'])
            if 'gradient' in node or 'skew_x' in node:
                # Keep glyph styling inside the independently animated wrapper.
                # GSAP zoom/rotation must not overwrite the authored italic angle.
                ink='display:inline-block;max-width:100%;will-change:opacity;'
                if 'gradient' in node:
                    gradient=node['gradient'];direction='to bottom' if gradient.get('direction')=='vertical' else 'to right'
                    ink+=f'background-image:linear-gradient({direction},{",".join(gradient["colors"])});background-clip:text;-webkit-background-clip:text;color:transparent;-webkit-text-fill-color:transparent;text-shadow:none;'
                if 'skew_x' in node:ink+=f'transform:skewX({node["skew_x"]}deg);'
                content=f'<span class="authored-text-ink" style="{ink}">{content}</span>'
            wipe=wipes.get(node['id'])
            if wipe is not None:
                # Haaland reference 932–936: stationary glyphs, descending soft
                # reveal. Feather is an authored percentage, not a recovered
                # source-editor parameter. Keep masking inside pose transforms.
                feather=wipe.get('feather',8)
                horizontal=wipe.get('axis','y')=='x'
                direction='right' if horizontal else 'bottom'
                display='inline-block;max-width:100%' if horizontal else 'block'
                mask=f'linear-gradient(to {direction},#000 var(--wipe-edge),transparent calc(var(--wipe-edge) + {feather}%))'
                content=f'<span id="wipe-{nid}" style="display:{display};--wipe-edge:-{feather}%;mask-image:{mask};-webkit-mask-image:{mask}">{content}</span>'
            paint=paints.get(node['id'])
            annotation=''
            if paint and node['id']==paint['depth']:
                annotation=f' data-text-paint-owner="obj-{esc(paint["front"])}" data-text-paint-dx="{paint["offset"][0]}" data-text-paint-dy="{paint["offset"][1]}"'
            body.append(f'<div id="{nid}" class="scene-object{cls}"{annotation} style="{style}">{content}</div>')
        elif node['kind']=='video':
            import subprocess
            source=source_of(node['media'])
            if seconds is None or folder is None:
                raise ProductionError('graphic_video_clock','영상 객체에 장면 시간과 작업 폴더가 필요합니다.',action='edit_plan')
            start=node.get('at',0)*seconds;length=node.get('duration',1)*seconds
            visible_length=length
            if abs(start+length-seconds)<1e-6:length+=handle_seconds
            # Five-second layout probes are not the delivered narration clock.
            # Preview only the declared source window; delivery must fit exactly.
            if preview:length=min(length,node['out']-node['in'])
            # Verify the actual source, not its filename or author-supplied metadata.
            raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration,width,height:format=duration','-of','json',str(Path(folder)/source)],timeout=30)
            probe=json.loads(raw);streams=probe.get('streams',[])
            duration=streams[0].get('duration',probe.get('format',{}).get('duration')) if streams else None
            if duration is None or node['out']>float(duration)+1/60 or node['in']+length>node['out']+1/60:
                raise ProductionError('graphic_video_range','영상 객체의 원본 재생 구간이 부족합니다.',action='edit_plan')
            if not preview:
                from longform_video import inspect_cuts
                inspect_cuts(Path(folder)/('cut-check-'+node['id']),Path(folder)/source,node['in'],length,visible_seconds=visible_length,cut_review=node.get('cut_review'))
            media_start=node['in']
            if node.get('video_treatment') and not preview:
                from longform_video_treatment import prepare,place_in
                # 처리 결과는 공용 캐시에 있다 — 장면 문서는 장면 폴더 안 상대 경로만 쓸 수 있으므로 폴더 안으로 둔다(하드링크·안 되면 복사).
                treated=place_in(prepare(Path(folder)/('treatment-'+node['id']),Path(folder)/source,node['in'],round(length*60),node['video_treatment'],assets),
                                 Path(folder)/('treatment-'+node['id']))
                source=native_path(treated['path']).relative_to(native_path(folder)).as_posix();media_start=0
            frame_defs=frame_outline=''
            if node.get('mask')=='thought':
                frame_defs,mask,frame_outline=thought_frame(nid,w,h,node.get('outline_width',6),node.get('outline_color','#FFFFFF'))
            else:
                mask={'rectangle':'none','rounded':'inset(0 round 6%)','ellipse':'ellipse(50% 50% at 50% 50%)'}[node.get('mask','rectangle')]
            # The wrapper is animated; only the child media owns clip timing.
            # Sound remains in the existing narration/music/SFX mixer.
            video_style=f'width:100%;height:100%;object-fit:{node.get("fit","contain")}'
            crop_open=crop_close=''
            if node.get('crop') is not None and not (node.get('video_treatment') and not preview):
                from longform_contract import validate_crop
                validate_crop(node['crop'])
                x0,y0,x1,y1=node['crop'];iw=streams[0]['width'];ih=streams[0]['height']
                if x1>iw or y1>ih:raise ProductionError('graphic_crop_bounds','원본 영상 밖의 자르기 영역입니다.',action='edit_plan')
                cw,ch=x1-x0,y1-y0
                ratio=(min if node.get('fit','contain')=='contain' else max)(w/cw,h/ch)
                vw,vh=cw*ratio,ch*ratio
                # Isolate the selected source rectangle before fitting it in the
                # animated wrapper. The original timed video stays seekable.
                crop_open=f'<div data-source-crop="{x0},{y0},{x1},{y1}" style="position:absolute;left:{(w-vw)/2:.6f}px;top:{(h-vh)/2:.6f}px;width:{vw}px;height:{vh}px;overflow:hidden">'
                crop_close='</div>'
                video_style=f'position:absolute;left:{-x0*ratio:.6f}px;top:{-y0*ratio:.6f}px;width:{iw*ratio:.6f}px;height:{ih*ratio:.6f}px;max-width:none;object-fit:fill'
            media_html=f'{crop_open}<video id="{nid}-video" class="clip" src="{esc(source)}" data-start="{start}" data-duration="{length}" data-media-start="{media_start}" muted playsinline style="{video_style}" aria-label="{esc(node["alt"])}"></video>{crop_close}'
            if frame_outline:
                body.append(f'{frame_defs}<div id="{nid}" class="scene-object" style="{style}"><div style="position:absolute;inset:0;overflow:hidden;clip-path:{mask}">{media_html}</div>{frame_outline}</div>')
            else:
                body.append(f'<div id="{nid}" class="scene-object" style="{style};overflow:hidden;clip-path:{mask}">{media_html}</div>')
        elif node['kind']=='image':
            source=source_of(node['media'])
            stroke=node.get('outline_width',0);color=node.get('outline_color','#FFFFFF')
            # Apply the silhouette outline to the inner bitmap so outer focus
            # animation does not replace it. Atlas crops keep independent poses.
            outline=' '.join(f'drop-shadow({dx*stroke}px {dy*stroke}px 0 {color})' for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) if stroke else 'none'
            if 'shadow' in node:
                shadow=node['shadow']
                extra=f'drop-shadow({shadow["x"]}px {shadow["y"]}px {shadow["blur"]}px {shadow["color"]})'
                outline=(outline+' '+extra) if outline!='none' else extra
            if node.get('crop') is not None:
                with Image.open(Path(folder)/source) as image:iw,ih=image.size
                x0,y0,x1,y1=node['crop']
                if x1>iw or y1>ih:raise ProductionError('graphic_crop_bounds','원본 이미지 밖의 자르기 영역입니다.',action='edit_plan')
                # Isolate source pixels before resampling, tiling or outlining.
                # SVG viewBox/meet reveals neighbours; even clipPath can leave
                # a sampled edge from adjacent pixels that drop-shadow amplifies.
                # This local render derivative never changes the original asset.
                cropped=Path(source).parent/('crop-'+nid+'.png')
                with Image.open(Path(folder)/source) as image:
                    image.crop((x0,y0,x1,y1)).save(Path(folder)/cropped)
                if node.get('tile_scale') is not None:
                    tw=(x1-x0)*node['tile_scale'];th=(y1-y0)*node['tile_scale']
                    body.append(f'<svg id="{nid}" class="scene-object" style="{style}" viewBox="0 0 {w} {h}"><defs><pattern id="tile-{nid}" width="{tw}" height="{th}" patternUnits="userSpaceOnUse"><image href="{cropped.as_posix()}" width="{tw}" height="{th}"/></pattern></defs><rect width="100%" height="100%" fill="url(#tile-{nid})"/></svg>')
                    continue
                fit=node.get('fit','cover')
                body.append(f'<div id="{nid}" class="scene-object" style="{style};overflow:hidden"><img{texture_id} src="{cropped.as_posix()}" style="width:100%;height:100%;object-fit:{fit};filter:{outline}" alt="{esc(node["alt"])}"></div>')
            else:
                # Honor the authored frame even without an explicit source crop.
                # Keep contain for older plans that omitted fit entirely.
                fit=node.get('fit','contain')
                clip=';overflow:hidden' if fit=='cover' else ''
                body.append(f'<div id="{nid}" class="scene-object" style="{style}{clip}"><img{texture_id} src="{source}" style="width:100%;height:100%;object-fit:{fit};filter:{outline}" alt="{esc(node["alt"])}"></div>')
        else:
            # Gradients contain validated colours only, never arbitrary SVG/HTML.
            paint=node.get('fill','none');defs=''
            if node.get('gradient'):
                gradient=node['gradient'];colors=gradient['colors'];vertical=gradient.get('direction')=='vertical'
                stops=''.join(f'<stop offset="{i/(len(colors)-1):.6f}" stop-color="{color}"/>' for i,color in enumerate(colors))
                defs=f'<defs><linearGradient id="paint-{nid}" x1="0%" y1="0%" x2="{0 if vertical else 100}%" y2="{100 if vertical else 0}%">{stops}</linearGradient></defs>'
                paint=f'url(#paint-{nid})'
            path=f'<path pathLength="1" d="{node["path"]}" fill="{paint}" stroke="{node.get("stroke","#FAC02D")}" stroke-width="{node.get("stroke_width",6)}" stroke-linecap="round" stroke-linejoin="round"/>'
            if 'pattern_height' in node:
                # Move the repeating field, not its viewport: every edge stays filled.
                content=f'<defs><pattern id="flow-{nid}" x="0" y="0" width="{w}" height="{node["pattern_height"]}" patternUnits="userSpaceOnUse">{path}</pattern></defs><rect width="{w}" height="{h}" fill="url(#flow-{nid})"/>'
            else:content=defs+path
            body.append(f'<svg id="{nid}" class="scene-object" style="{style}" viewBox="0 0 {w} {h}">{content}</svg>')
    for index,node in enumerate(visual['objects']):
        if 'brush_reveal' in node:
            from longform_paper_reveal import wrap_brush
            body[index]=wrap_brush(body[index],node)
        if 'paper_reveal' in node:
            from longform_paper_reveal import wrap_media
            body[index]=wrap_media(body[index],node)
    local_glitches=[c for c in visual.get('motion_cues',[]) if c['effect']=='object_glitch']
    if local_glitches:
        from longform_object_glitch import wrap
        glitch_targets={c['target'] for c in local_glitches}
        for index,node in enumerate(visual['objects']):
            if node['id'] in glitch_targets:
                body[index]=wrap(body[index],node['id'])
    if visual.get('groups'):
        from longform_groups import wrap
        body=wrap(visual,body,group_bounds)
        body.extend(gear_clip(g) for g in visual['groups'] if g.get('clip')=='gear')
    if local_glitches:
        from longform_object_glitch import definitions as glitch_definitions
        body.extend(glitch_definitions(c['target'],c.get('seed',17)) for c in local_glitches)
    if visual.get('iris_handoff'):
        from longform_iris import body as iris_body
        body.append(iris_body())
    return ''.join(body),css


def aligned_visual(visual,voice):
    """Resolve authored character anchors using the preserved provider alignment."""
    import copy
    result=copy.deepcopy(visual);seconds=voice['frames']/60
    for cue in result.get('motion_cues',[]):
        if 'start_char' not in cue:continue
        chars=voice.get('characters',[]);index=cue['start_char']
        if type(index) is not int or not 0<=index<len(chars):
            raise ProductionError('motion_alignment_missing','모션 기준 문자의 실제 음성 시간이 없습니다.',action='edit_plan')
        cue['at']=chars[index]['start']/seconds
        if 'end_char' in cue:
            end=cue['end_char']
            if type(end) is not int or not index<=end<len(chars):
                raise ProductionError('motion_alignment_missing','모션 종료 문자 범위를 확인하세요.',action='edit_plan')
            cue['duration']=(chars[end]['end']-chars[index]['start'])/seconds
        if cue['duration']<=0 or cue['at']+cue['duration']>1.000001:
            raise ProductionError('motion_alignment_overflow','발화에 맞춘 모션이 장면 범위를 벗어났습니다.',action='edit_plan')
    return result


def special_motion_checks(visual,cues,seconds):
    """Expose effect-specific browser states without changing animation code."""
    import math
    def check(target,start,end,first,last):
        return dict(target=target,start=start,end=end,expected_start=first,expected_end=last)
    nodes_by_selector=_first_by(visual['objects'],lambda n:'#obj-'+n['id'])
    cue_by_effect=_first_by(visual['motion_cues'],lambda c:(c['effect'],c['target']))
    for row in cues:
        effect=row['technique'];at=row['start'];end=row['end'];length=end-at
        if effect=='text_wipe':
            row.update(expected_start={'--wipe-edge':f'-{row["feather"]}%'},expected_end={'--wipe-edge':'100%'})
        elif effect in ('brush_reveal','paper_reveal','object_glitch'):
            node=_first(nodes_by_selector,row['target']);nid='obj-'+node['id']
            if effect=='brush_reveal':
                spec=node['brush_reveal'];count=spec.get('strokes',5);span=length/(1+.65*(count-1));first,last=(1,0) if spec.get('phase','in')=='out' else (0,1)
                row['checks']=[check('#brush-progress-'+nid+'-'+str(i),at+i*.65*span,at+i*.65*span+span,{'--brush-progress':first},{'--brush-progress':last}) for i in range(count)]
            elif effect=='paper_reveal':
                h=node['box'][3];flap=min(150,h*.22)
                row['checks']=[check('#paper-open-'+nid,at,end,{'clipPath':'inset(0% 0% 100% 0%)'},{'clipPath':'inset(0% 0% 0% 0%)'}),check('#paper-fold-'+nid,at,end,{'y':-flap},{'y':h}),check('#paper-fold-'+nid,at,at+length*.12,{'opacity':0},{'opacity':1}),check('#paper-fold-'+nid,at+length*.82,end,{'opacity':1},{'opacity':0})]
            else:
                cue=_first(cue_by_effect,(effect,node['id']));strength=cue.get('strength',6);exact_length=cue['duration']*seconds;steps=max(1,math.ceil(exact_length*60));span=exact_length/steps
                def value(n,factor):return round(strength*(1-n/steps)**2*factor,5)
                sign=-1 if (steps-1)%2 else 1
                row['checks']=[check('#object-glitch-'+node['id']+suffix,at+span*.25,end-span*.25,{'attr':{attr:value(0,factor)}},{'attr':{attr:value(steps-1,factor*(sign if attr=='dx' else 1))}}) for suffix,attr,factor in [('-r','dx',1),('-b','dx',-1),('-noise','scale',2)]]
                row['checks'].append(check('#fx-'+nid,max(0,at-1/60),end,{'filter':'none'},{'filter':'none'}))
        elif effect=='iris_handoff':
            from longform_iris import blade_path,backing_path
            spec=visual['iris_handoff'];t={k:spec[k]*seconds for k in ('at','ring_in','close','closed','swap','opened','end')}
            checks=[check('#iris-lens',t['at'],t['ring_in'],{'attr':{'transform':'scale(3)'}},{'attr':{'transform':'scale(1)'}}),check('#iris-lens',t['opened'],t['end'],{'attr':{'transform':'scale(1)'}},{'attr':{'transform':'scale(3)'}})]
            for i in range(9):
                target='#iris-blade-'+str(i) if i<8 else '#iris-backing';shape=blade_path if i<8 else backing_path
                checks.extend([check(target,t['close'],t['closed'],{'attr':{'d':shape(450)}},{'attr':{'d':shape(0)}}),check(target,t['swap'],t['opened'],{'attr':{'d':shape(0)}},{'attr':{'d':shape(450)}})])
            checks.extend([check('#obj-'+spec['outgoing'],t['closed'],t['opened'],{'opacity':1},{'opacity':0}),check('#obj-'+spec['incoming'],t['closed'],t['opened'],{'opacity':0},{'opacity':1}),check('#iris-overlay',t['ring_in'],t['end'],{'visibility':'visible'},{'visibility':'hidden'})]);row['checks']=checks


def authored_motion(visual,seconds):
    script=['const tl=gsap.timeline({paused:true});'];cues=[]
    paper_targets=set()
    for node in visual['objects']:
        if 'paper_reveal' in node or 'brush_reveal' in node:
            paper_targets.add(node['id'])
            if node.get('group'):paper_targets.add(node['group'])
    for target in sorted(paper_targets):
        # Nested jagged clip paths otherwise acquire different GPU edge pixels
        # after a forward/backwards seek through a fractional-scale tween.
        script.append('gsap.set('+json.dumps('#obj-'+target)+',{"force3D":false});')
    # Establish entrances once. Future fromTo tweens must not immediately
    # overwrite earlier states when the timeline is created or scrubbed.
    initial_opacity={}
    for cue in sorted(visual['motion_cues'],key=lambda c:c['at']):
        if cue['effect'] in ('rise','slide','pop','fade'):
            initial_opacity.setdefault(cue['target'],cue.get('from',0) if cue['effect']=='fade' else 0)
    for target,opacity in initial_opacity.items():
        script.append('gsap.set('+json.dumps('#obj-'+target)+','+json.dumps({'opacity':opacity})+');')
    gray_targets={c['target'] for c in visual['motion_cues'] if c['effect'] in ('grayscale','brightness')}
    # B2: authored entrance values are read only for unique-v1 graphics (visual.variety); old graphics keep the
    # pre-B2 constants even if their cues happen to carry such keys (byte-identical old renders).
    opened=opened_motion(visual)
    nodes_by_id=_first_by(visual['objects'],lambda n:n['id'])
    for cue in visual['motion_cues']:
        at=cue['at']*seconds;length=cue['duration']*seconds
        if cue['effect']=='text_wipe':
            target='#wipe-obj-'+cue['target'];feather=cue.get('feather',8)
            start={'--wipe-edge':f'-{feather}%'}
            script.append('gsap.set('+json.dumps(target)+','+json.dumps(start)+');')
            end={'--wipe-edge':'100%','duration':length,'ease':cue_ease(cue,opened),'immediateRender':False}
            script.append('tl.fromTo('+json.dumps(target)+','+json.dumps(start)+','+json.dumps(end)+','+str(at)+');')
            cues.append({'target':target,'start':at,'end':at+length,'technique':'text_wipe','feather':feather})
            continue
        if cue['effect']=='object_glitch':
            from longform_object_glitch import motion
            script.append(motion(cue,at,length))
            cues.append({'target':'#obj-'+cue['target'],'start':at,'end':at+length,'technique':'object_glitch'})
            continue
        if cue['effect']=='count':
            import math
            target='#obj-'+cue['target'];first=cue['from_value'];last=cue['to_value']
            node=_first(nodes_by_id,cue['target'])
            text_target=target+(' .authored-text-ink' if 'gradient' in node or 'skew_x' in node else '')
            steps=max(1,min(abs(last-first),600,math.ceil(length*60)))
            def label(value):
                return cue.get('prefix','')+format(value,',d' if cue.get('grouping',True) else 'd')+cue.get('suffix','')
            script.append('gsap.set('+json.dumps(text_target)+','+json.dumps({'textContent':label(first),'fontVariantNumeric':'tabular-nums'})+');')
            # Explicit text states avoid elapsed-time callbacks and HTML insertion.
            # Seeking backwards restores the same integer and its unit.
            for step in range(steps+1):
                value=round(first+(last-first)*step/steps)
                state={'textContent':label(value),'immediateRender':False}
                script.append('tl.set('+','.join(json.dumps(x) for x in (text_target,state,at+length*step/steps))+');')
            cues.append({'target':target,'start':at,'end':at+length,'technique':'count','from_value':first,'to_value':last,'expected_start':{'textContent':label(first)},'expected_end':{'textContent':label(last)}})
            continue
        if cue['effect']=='brush_reveal':
            from longform_paper_reveal import brush_motion
            node=_first(nodes_by_id,cue['target'])
            script.append(brush_motion(node,at,length))
            cues.append({'target':'#obj-'+cue['target'],'start':at,'end':at+length,'technique':'brush_reveal'})
            continue
        if cue['effect']=='paper_reveal':
            from longform_paper_reveal import motion
            node=_first(nodes_by_id,cue['target'])
            script.append(motion(node,at,length))
            cues.append({'target':'#obj-'+cue['target'],'start':at,'end':at+length,'technique':'paper_reveal'})
            continue
        target='#obj-'+cue['target']+(' path' if cue['effect']=='draw' else '')
        effect=cue['effect'];direction=cue.get('direction',1)
        if effect=='pattern_pan':target='#flow-obj-'+cue['target']
        if effect=='round_frame':target='#frame-'+cue['target']
        if effect=='gear_spin':target='#gear-mask-'+cue['target']
        # cue_ease (contract) is the one ease rule; the per-effect branches below no longer restate it.
        start,end={},{'duration':length,'ease':cue_ease(cue,opened),'immediateRender':False}
        if effect=='draw':
            # CSSPlugin rounds pixel-valued properties by default. With
            # pathLength=1 that turns a continuous reveal into a 1→0 switch.
            start={'strokeDasharray':1,'strokeDashoffset':1}
            end.update(strokeDashoffset=0,autoRound=False)
        # Opened entrance values (B2 §4) for unique-v1 graphics; omitted fields and old graphics use the former constants.
        elif effect=='rise':start={'opacity':0,'y':authored_value(cue,'distance',opened)};end.update(opacity=1,y=0)
        elif effect=='slide':start={'opacity':0,'x':direction*authored_value(cue,'distance',opened)};end.update(opacity=1,x=0)
        elif effect=='pop':start={'opacity':0,'scale':authored_value(cue,'from_scale',opened)};end.update(opacity=1,scale=1)
        elif effect=='pan':
            # A horizontal drift must not overwrite a simultaneous rise's y.
            # Keep the legacy zero-axis fallback only for cues with no axes.
            axes=[axis for axis in ('x','y') if axis in cue or 'from_'+axis in cue] or ['x','y']
            start={axis:cue.get('from_'+axis,0) for axis in axes}
            end.update({axis:cue.get(axis,0) for axis in axes})
        elif effect=='pattern_pan':
            start={'attr':{'x':cue.get('from_x',0),'y':cue.get('from_y',0)}}
            end.update(attr={'x':cue.get('x',0),'y':cue.get('y',0)})
        elif effect=='zoom':start={'scale':cue.get('from_scale',1)};end.update(scale=cue['scale'])
        elif effect=='fade':start={'opacity':cue.get('from',0)};end.update(opacity=cue.get('to',1))
        elif effect=='polygon_wipe':
            polygon=lambda points:'polygon('+','.join(str(x)+'% '+str(y)+'%' for x,y in points)+')'
            start={'clipPath':polygon(cue['from_points'])};end.update(clipPath=polygon(cue['to_points']))
        elif effect=='brightness':
            start={'--object-bright':cue['from']};end.update({'--object-bright':cue['to']})
        elif effect=='grayscale':
            start={'--object-gray':cue['from']};end.update({'--object-gray':cue['to']})
        elif effect=='focus' and cue['target'] in gray_targets:
            start={'--object-blur':f'{cue.get("from",0)}px'};end.update({'--object-blur':f'{cue.get("to",0)}px'})
        elif effect=='focus':start={'filter':f'blur({cue.get("from",0)}px)'};end.update(filter=f'blur({cue.get("to",0)}px)')
        elif effect=='rotate':
            # An orthographic object turn narrows only its chosen axis; no
            # whole-scene camera rotation or inferred source-editor curve.
            prop={'x':'rotationX','y':'rotationY','z':'rotation'}[cue.get('axis','z')]
            start={prop:cue.get('from',0)};end[prop]=cue.get('to',0)
        elif effect=='gear_spin':
            start={'attr':{'transform':f'rotate({cue["from"]} .5 .5)'}}
            end.update(attr={'transform':f'rotate({cue["to"]} .5 .5)'})
        elif effect=='round_frame':start={'borderRadius':f'{cue["from"]*100}%'};end.update(borderRadius=f'{cue["to"]*100}%')
        # A paused timeline already at zero may not render a lazy fromTo when
        # the renderer first seeks to zero. Establish only zero-time starts
        # immediately; future cues must not overwrite this opening pose.
        if at==0:
            script.append('gsap.set('+json.dumps(target)+','+json.dumps(start)+');')
        if effect=='draw':
            # A paused timeline's zero-time set is not guaranteed to render on
            # its initial seek(0). Hide the full path before that first frame;
            # keep the timeline set as well for backwards seeks.
            script.append('gsap.set('+json.dumps(target)+','+json.dumps(start)+');')
            script.append('tl.set('+json.dumps(target)+','+json.dumps(start)+',0);')
        script.append('tl.fromTo('+json.dumps(target)+','+json.dumps(start)+','+json.dumps(end)+','+str(at)+');')
        cues.append({'target':target,'start':at,'end':at+length,'technique':effect,
                     'expected_start':start,'expected_end':{k:v for k,v in end.items() if k not in ('duration','ease','immediateRender','autoRound')},
                     **({'viewport_transition':cue['viewport_transition'],'ease':end.get('ease','none')} if 'viewport_transition' in cue else {}),
                     **({'focus_transition':cue['focus_transition'],'ease':end.get('ease','none')} if 'focus_transition' in cue else {}),
                     **({'axis':cue['axis']} if effect=='rotate' and cue.get('axis','z')!='z' else {}),
                     **({k:cue[k] for k in ('start_char','end_char') if k in cue})})
    if visual.get('iris_handoff'):
        from longform_iris import motion as iris_motion
        spec=visual['iris_handoff'];script.append(iris_motion(spec,seconds))
        cues.append({'technique':'iris_handoff','start':spec['at']*seconds,'end':spec['end']*seconds,'swap':spec['swap']*seconds})
    for node in visual['objects']:
        if 'texture_cadence' in node:
            from longform_texture import motion as texture_motion
            animation,checks=texture_motion(node,seconds);script.append(animation);cues.extend(checks)
    special_motion_checks(visual,cues,seconds)
    script.append('window.__timelines["graphic"]=tl;')
    return ''.join(script),{'schema':'geumbit-motion-v1','template':'authored','layout_id':visual['layout_id'],
        'duration':seconds,'basis':visual['design_reason'],'cues':cues}
