"""Seekable brush coverage and light leaks below the caption/brand layers."""
from pathlib import Path
import numpy as np
from PIL import Image
from longform_photo import encode_frames


def splatter_field(size=(480,270),seed=17,islands=None):
    """Seeded expanding ragged islands, with detached small droplets."""
    w,h=size;yy,xx=np.mgrid[0:h,0:w].astype(np.float32);xx/=w;yy/=h
    rng=np.random.default_rng(seed);field=np.full((h,w),100.,np.float32)
    for i in range(30 if islands is None else len(islands)):
        cx,cy=rng.uniform(0,1,2);radius=rng.uniform(.10,.24) if i<10 else rng.uniform(.025,.07)
        dx=(xx-cx)*w/h;dy=yy-cy;angle=np.arctan2(dy,dx)
        # Keep the established island positions/onsets when refining contours.
        rng.uniform(0,6.28,2)
        onset=rng.uniform(0,.7)
        edge_rng=np.random.default_rng(np.random.SeedSequence([seed,i,1]))
        # Periodic 11/23-lobed sines made every island look like a star icon.
        # A wrapped, seeded contour has uneven lobes and fine ink fingers,
        # while the fixed arrival field still expands monotonically on seek.
        phase=(angle+np.pi)/(2*np.pi)
        def contour(knots):
            values=edge_rng.uniform(-1,1,knots)
            return np.interp(phase,np.linspace(0,1,knots+1),np.r_[values,values[0]])
        rough=1+.22*contour(13)+.13*contour(47)+.09*contour(139)
        if islands is not None:
            island=islands[i];cx,cy,radius,onset=(island[k] for k in ('x','y','radius','onset'))
            dx=(xx-cx)*w/h;dy=yy-cy;angle=np.arctan2(dy,dx)
            phase=(angle+np.pi)/(2*np.pi)
            edge_rng=np.random.default_rng(np.random.SeedSequence([seed,i,1]))
            rough=1+.22*contour(13)+.13*contour(47)+.09*contour(139)
        arrival=np.sqrt(dx*dx+dy*dy)/(radius*rough)+onset
        field=np.minimum(field,arrival)
    return (field-field.min())/(field.max()-field.min())


def grain_field(size=(480,270),seed=17):
    w,h=size;yy,xx=np.mgrid[0:h,0:w].astype(np.float32);xx/=w;yy/=h
    rng=np.random.default_rng(seed)
    # Staggered fibres and grain disturb a diagonal front; not an iris or tear.
    fibre=.025*np.sin(xx*w*.83+np.floor(yy*h/2)*1.7)
    field=(.6*(1-xx)+yy)/1.6+fibre+rng.uniform(-.065,.065,(h,w))
    return (field-field.min())/(field.max()-field.min())


def field_alpha(field,progress):
    if progress<=0:return np.zeros(field.shape,np.uint8)
    if progress>=1:return np.full(field.shape,255,np.uint8)
    return np.round(np.clip((progress-field)/.025+.5,0,1)*255).astype(np.uint8)


def render_splatter(folder,frames,spec):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True)
    field=splatter_field(seed=spec.get('seed',17),islands=spec.get('islands'))
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
    def pixels():
        for i in range(frames):
            q=(i-first)/span
            # End is exclusive: a following cut must not inherit one negative frame.
            # Compare timeline positions, not q: at an exact end frame the
            # subtraction/division can yield 0.9999999999999999 and leak the
            # effect into the incoming shot (actual f14 frame 530).
            # Optional authored growth controls threshold speed, not exposed area.
            # The default preserves existing masks; power<1 reveals islands earlier.
            mask=field_alpha(field,q**spec.get('growth_power',1.)*spec.get('reveal_limit',1.)) if first<=i<first+span else np.full(field.shape,255,np.uint8)
            yield np.repeat(mask[:,:,None],3,axis=2).tobytes()
    path=root/'splatter-mask.mp4';encode_frames(pixels(),path,size=(480,270));return path


def splatter_filter(index):
    return ('[splatterbase]split[splatteroriginal][splatterinverse];'
            '[splatteroriginal]format=gbrp[splattercolor];'
            '[splatterinverse]negate,format=gbrp[splatternegative];'
            f'[{index}:v]scale=1920:1080,format=gbrp[splattermask];'
            '[splatternegative][splattercolor][splattermask]maskedmerge,format=yuv420p[v0];')


def render_grain(folder,frames,spec,texture_path):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True)
    field=grain_field(seed=spec.get('seed',17))
    from PIL import ImageOps
    with Image.open(texture_path) as image:texture=np.asarray(ImageOps.fit(image.convert('RGB'),(480,270)))
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
    paths=[]
    for channel,name in enumerate(('grain-keep','grain-paper')):
        def pixels():
            for i in range(frames):
                q=np.clip((i-first)/span,0,1)
                if spec['phase']=='in':q=1-q
                alpha=field_alpha(field,q)
                layer=np.repeat((255-alpha)[:,:,None],3,axis=2) if channel==0 else np.round(texture.astype(float)*alpha[:,:,None]/255).astype(np.uint8)
                yield layer.tobytes()
        path=root/(name+'.mp4');encode_frames(pixels(),path,size=(480,270));paths.append(path)
    return paths


def glitch_filter(frames,spec,size,input_label='glitchbase',output_label='v0'):
    """Displace strips of the actual moving picture; keep the original clock.

    Authored frames and seed determine every jump, so resume/seek do not choose
    a new animation. render_scene chooses picture or picture+caption scope;
    fixed branding is composited afterwards.
    This is a native FFmpeg treatment, not a claim of the reference's plugin.
    """
    if spec.get('profile')=='staged_strips':
        return staged_strips_filter(frames,spec,size,input_label,output_label)
    canvas_w,canvas_h=size
    rng=np.random.default_rng(spec.get('seed',17));blocks=spec.get('profile','strips')=='blocks';count=64 if blocks else 12
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
    phase=spec.get('phase','full');strength=spec.get('strength',1.)
    progress=f'max(0,min(1,(n-{first:.9f})/{span:.9f}))'
    u={'full':progress,'out':f'({progress})/2','in':f'.5+({progress})/2'}[phase]
    pulse=f'sin(PI*({u}))'
    enabled=f'gte(n,{first:.9f})*lte(n,{first+span:.9f})'
    labels=''.join(f'[gs{i}]' for i in range(count))
    graph=f'[{input_label}]split={count+1}[gb0]{labels};'
    for i in range(count):
        # Reference elliott-58-glitch native source frame1755 shows localized rectangular
        # damage plus thin bands, not only full-width strips. Geometry below is
        # an authored approximation; original mask/plugin parameters are unknown.
        origin=0;width=canvas_w
        y=int(rng.integers(0,max(1,canvas_h//2-25)))*2;height=min(canvas_h-y,int(rng.integers(8,57))*2)
        if blocks:
            height=min(canvas_h-y,int(rng.integers(2,12 if i<8 else 32))*2)
            if i>=8:
                width=int(rng.integers(12,300))*2
                origin=int(rng.integers(0,(canvas_w-width)//2+1))*2
        amplitude=float(rng.uniform(70,250))*strength;offset=float(rng.uniform(0,6.28))
        x=f'{amplitude:.6f}*({pulse})*sin(floor(({u})*24)*2.399963+{offset:.6f})'
        graph+=f'[gs{i}]crop={width}:{height}:{origin}:{y}[gc{i}];'
        graph+=f"[gb{i}][gc{i}]overlay=x='{origin}+({x})':y={y}:enable='{enabled}'[gb{i+1}];"
    graph+=f'[gb{count}]null[{output_label}];'
    return graph


def brush_material(size=(480,270),seed=17,strokes=5,color='#163968'):
    w,h=size;yy,xx=np.mgrid[0:h,0:w].astype(np.float32);xx/=max(1,w-1);yy/=max(1,h-1)
    rng=np.random.default_rng(seed);field=np.full((h,w),10.,dtype=np.float32)
    for i in range(strokes):
        centre=(i+.5)/strokes
        bristles=np.interp(np.arange(w),np.linspace(0,w-1,60),rng.uniform(-.02,.02,60))[None,:]
        distance=np.abs(yy-centre+bristles)
        fringe=np.clip(distance*strokes-.42,0,1)
        arrival=i*.68+xx*.95+fringe*.28
        field=np.minimum(field,np.where(distance<.78/strokes,arrival,10.))
    # Overlapping strokes cover the entire canvas; no last-frame hole filling.
    assert np.max(field)<10
    field=(field-field.min())/(field.max()-field.min())
    cloud=np.asarray(Image.fromarray(rng.integers(0,256,(14,24),dtype=np.uint8)).resize(size,Image.Resampling.BICUBIC),dtype=float)/255
    grain=rng.normal(0,2.0,(h,w))
    shading=.68+.48*cloud-.15*np.minimum(1,((xx-.5)**2+(yy-.5)**2)*2)
    rgb=np.array([int(color[j:j+2],16) for j in (1,3,5)])
    texture=np.clip(shading[:,:,None]*rgb+grain[:,:,None],0,255).astype(np.uint8)
    return field,texture


def brush_at(field,texture,progress):
    if progress<=0:alpha=np.zeros(field.shape)
    elif progress>=1:alpha=np.ones(field.shape)
    else:
        alpha=np.clip((progress-field)/.018+.5,0,1);alpha=alpha*alpha*(3-2*alpha)
    keep=np.round((1-alpha)*255).astype(np.uint8)
    paint=np.round(texture*alpha[:,:,None]).astype(np.uint8)
    return keep,paint


def light_at(progress,phase='full',size=(480,270),strength=1.,seed=17,profile='smooth'):
    w,h=size
    if progress<0 or progress>1:return np.zeros((h,w,3),np.uint8)
    u={'full':progress,'out':progress/2,'in':.5+progress/2}[phase]
    if profile=='white_flash':
        # Elliott 0opgOhMJ2Ks 330.0-332.0 native-frame inspection:
        # docs/.../2026-09-25-reference-fast-transition-326-459.json.
        # Neutral flash without a warm rebound. Linear opacity is authored,
        # not a recovered reference curve; duration is set by the plan.
        value=round(255*strength*max(0.,1-abs(2*u-1)))
        return np.full((h,w,3),min(255,max(0,value)),np.uint8)
    pulse=np.sin(np.pi*u)**2
    yy,xx=np.mgrid[0:h,0:w].astype(np.float32);xx/=max(1,w-1);yy/=max(1,h-1)
    rng=np.random.default_rng(seed);cy=.35+float(rng.uniform(-.1,.1));cx=-.35+u*1.7
    hot=np.exp(-((xx-cx)/.42)**2-((yy-cy)/.85)**2)
    wash=np.exp(-((xx-(1-cx))/.75)**2-((yy-.5)/1.1)**2)
    warm=np.array([255.,171.,77.]);violet=np.array([134.,75.,166.])
    rgb=(hot[:,:,None]*warm*1.8+wash[:,:,None]*violet*.8)*pulse*strength
    if profile=='flash_rebound':
        # Nolan wJacNPyhlXU 333.1–333.8833: consecutive48-frame evidence:
        # docs/.../2026-09-25-awards-light-flash-gap.json. Authored envelope,
        # not a recovered LUT. Full-white peak hides the cut below text layers.
        amplitude=np.interp(u,[0,.08,.36,.44,.48,.565,.62,.75,1],
                              [0,.1,.9,1,.7,0,.25,.4,0])
        flash=np.interp(u,[0,.46,.49,.525,.565,1],[0,0,1,1,0,0])
        rgb=(hot[:,:,None]*warm*.85+wash[:,:,None]*violet*.45)*amplitude*strength
        rgb=np.clip(rgb,0,255)*(1-flash*strength)+255*flash*strength
    elif profile!='smooth':
        raise ValueError('Unknown light profile: '+str(profile))
    return np.clip(np.round(rgb),0,255).astype(np.uint8)


def render_brush(folder,frames,spec):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True)
    field,texture=brush_material(seed=spec.get('seed',17),strokes=spec.get('strokes',5),color=spec.get('color','#163968'))
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1);outputs=[]
    for channel,name in enumerate(('brush-keep','brush-paint')):
        def pixels():
            for i in range(frames):
                layer=brush_at(field,texture,(i-first)/span)[channel]
                if channel==0:layer=np.repeat(layer[:,:,None],3,axis=2)
                yield layer.tobytes()
        path=root/(name+'.mp4');encode_frames(pixels(),path,size=(480,270));outputs.append(path)
    return outputs


def render_light(folder,frames,spec):
    root=Path(folder);root.mkdir(parents=True,exist_ok=True)
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
    def pixels():
        for i in range(frames):
            # Normalized endpoints such as 1-23/1430 accumulate tiny error.
            # Keep the mathematically included last frame at u=1, rather than
            # flashing back to the unmodified picture just before the cut.
            q=min(1.,max(0.,(i-first)/span)) if first-1e-9<=i<=first+span+1e-9 else -1.
            yield light_at(q,spec.get('phase','full'),strength=spec.get('strength',1.),seed=spec.get('seed',17),profile=spec.get('profile','smooth')).tobytes()
    path=root/'light-leak.mp4';encode_frames(pixels(),path,size=(480,270));return path


def edge_strobe_filter(frames,spec,input_label='edgebase',output_label='v0'):
    """Explicit half-open windows on the 60fps production timeline.

    Reference evidence: haaland-edge-strobe-direct-observations.json,
    MvtomDV0RWA 1013–1013.6. Sobel is an authored approximation, not a
    recovered source plugin. FFmpeg local `-h filter=sobel`: planes mask,
    scale=1, delta=0. RGB planes retain colored fine edges on black.
    frame_offset carries the same window clock across separately rendered cuts.
    """
    from longform_state import ProductionError
    offset=spec.get('frame_offset',0)
    windows=spec['windows']
    if not any(a<offset+frames and b>offset for a,b in windows):
        raise ProductionError('edge_strobe_range','윤곽선 전환 구간이 이 장면과 겹치지 않습니다.',action='edit_plan')
    enabled='+'.join(f'gte(n+{offset},{a})*lt(n+{offset},{b})' for a,b in windows)
    return (f'[{input_label}]split[edgeoriginal][edgecopy];'
            '[edgecopy]format=gbrp,sobel=planes=7:scale=1:delta=0,format=yuv420p[edgepicture];'
            f"[edgeoriginal][edgepicture]overlay=0:0:format=yuv420:enable='{enabled}'[{output_label}];")


def group_zoom_filter(input_label, output_label, spec, boundary, *, canvas):
    """Picture+chip zoom handoff, before fixed brand/caption composition.

    Authored radial exposure samples; not a recovered reference plugin/curve.
    Integrate a dense logarithmic exposure by repeated two-tap doubling.
    Only the short moving branch is resampled; fixed overlays remain separate.
    """
    width,height,fps=canvas
    before=spec['out_frames'];after=spec['in_frames'];first=boundary-before
    last=boundary+after-1
    # perspective increments its output counter before evaluating coordinates.
    # Actual boundary decode regression catches an uncorrected one-frame jump.
    q=f'((on-1)/{before-1})';u=f'((on-1-{before})/{after-1})'
    scale=f'if(lt(on-1,{before}),1+({spec["out_scale"]}-1)*pow({q},3),1-(1-{spec["in_scale"]})*pow(1-{u},3))'
    blur=f'if(lt(on-1,{before}),{spec["blur"]}*pow({q},2),{spec["blur"]}*pow(1-{u},3))'
    # Incoming scales below 1 need real overscan; perspective alone repeats
    # outermost pixels into long stripes (found on actual Sabrina footage).
    import math
    px=2*math.ceil(width*(1/spec['in_scale']-1)/4)
    py=2*math.ceil(height*(1/spec['in_scale']-1)/4)
    overscan=f'pad=iw+{2*px}:ih+{2*py}:{px}:{py},fillborders=left={px}:right={px}:top={py}:bottom={py}:mode=reflect,' if px or py else ''
    prefix=output_label+'z'
    # Each doubling pass generates twice as many log-spaced exposure taps.
    # Keep the worst-case corner displacement between taps below two pixels.
    distance=math.hypot(width/2,height/2)*spec['out_scale']*(1+spec['blur'])*math.log1p(spec['blur'])
    passes=max(0,math.ceil(math.log2(1+distance/2)))
    def perspective(source,target,z):
        x=f'W*(1-({z}))/2';y=f'H*(1-({z}))/2'
        return f"[{source}]perspective=x0='{x}':y0='{y}':x1='W-({x})':y1='{y}':x2='{x}':y2='H-({y})':x3='W-({x})':y3='H-({y})':sense=destination:eval=frame[{target}];"
    g=f'[{input_label}]split[{prefix}base][{prefix}region];[{prefix}region]trim=start_frame={first}:end_frame={last+1},setpts=PTS-STARTPTS,{overscan}null[{prefix}padded];'
    label=f'{prefix}scaled';g+=perspective(f'{prefix}padded',label,scale)
    for i in range(passes):
        g+=f'[{label}]split[{prefix}keep{i}][{prefix}sample{i}];'
        exponent=2**i/(2**passes-1)
        g+=perspective(f'{prefix}sample{i}',f'{prefix}tap{i}',f'pow(1+({blur}),{exponent})')
        label=f'{prefix}mix{i}'
        g+=f'[{prefix}keep{i}][{prefix}tap{i}]blend=all_expr=\'A*0.5+B*0.5\'[{label}];'
    g+=f'[{label}]crop={width}:{height}[{prefix}cropped];';label=f'{prefix}cropped'
    g+=f'[{label}]settb=expr=1/{fps},setpts=N+{first}[{prefix}clock];'
    g+=f"[{prefix}base][{prefix}clock]overlay=0:0:enable='between(n,{first},{last})':eof_action=pass[{output_label}];"
    return g


def reveal_field(size,seed=17):
    """Authored irregular reveal islands with fine vertical bristle edges.

    Reference: elliott-1492-cut/observations.json, native1493.2–1493.6667.
    This is a deterministic approximation, not the recovered original mask.
    """
    rng=np.random.default_rng(seed);w,h=size
    def noise(columns,rows):
        values=rng.random((rows,columns)).astype(np.float32)
        return np.asarray(Image.fromarray(values).resize((w,h),Image.Resampling.BICUBIC))
    # Long vertical bristles break the round low-frequency islands.
    # .12 was selected by native-frame comparison; .22 produced deep drips.
    # Evidence: brush-reveal-bristles/experiments.jpg, not a source metric.
    field=noise(9,6)+.16*noise(37,13)+.12*noise(151,5)
    return (field-field.min())/(field.max()-field.min())


def reveal_mask(field,progress):
    if progress<=0:return Image.new('L',(field.shape[1],field.shape[0]),0)
    if progress>=1:return Image.new('L',(field.shape[1],field.shape[0]),255)
    alpha=np.clip((progress-field)/.015+.5,0,1)
    return Image.fromarray(np.round(alpha*255).astype(np.uint8))


def render_reveal(outgoing,incoming,dest,start,count,seed=17,size=None):
    """Read both moving pictures at their actual clocks, only for the overlap."""
    from longform_shatter import decoded
    if size is None:
        from longform_render import W,H
        size=(W,H)
    field=reveal_field(size,seed)
    with decoded(outgoing,start,count,size) as a,decoded(incoming,0,count,size) as b:
        def pixels():
            for i in range(count):
                old,new=a(),b()
                yield Image.composite(new,old,reveal_mask(field,i/max(1,count-1))).tobytes()
        encode_frames(pixels(),dest,size=size)
    return dest


def staged_strips_filter(frames,spec,size,input_label,output_label):
    """Transfer the approved v12's 30 bands / eight held poses to live pixels.

    v12 HTML: sin(i*127.1+f*31.7)*100*sin(pi*f/7), f=0..7.
    These are our approved authored values, not recovered source-plugin values.
    Overlay's n starts at one: use n-1 for the production zero-based clock.
    """
    width,height=size;count=30
    first=spec['at']*max(1,frames-1);span=spec['duration']*max(1,frames-1)
    step=f'max(0,min(7,floor(((n-1)-{first:.9f})/({span:.9f}/8))))'
    enabled=f'gte(n-1,{first:.9f})*lt(n-1,{first+span:.9f})'
    labels=''.join(f'[ss{i}]' for i in range(count))
    graph=f'[{input_label}]split={count+1}[sb0]{labels};'
    for i in range(count):
        y=(height*i//count)//2*2;end=(height*(i+1)//count)//2*2
        band=end-y
        if band<=0:raise ValueError('staged strips require at least 60 source rows')
        x=f'{100*width/1280:.9f}*sin(PI*({step})/7)*sin({i}*127.1+({step})*31.7)'
        graph+=f'[ss{i}]crop={width}:{band}:0:{y}[sc{i}];'
        graph+=f"[sb{i}][sc{i}]overlay=x='{x}':y={y}:enable='{enabled}'[sb{i+1}];"
    return graph+f'[sb{count}]null[{output_label}];'
