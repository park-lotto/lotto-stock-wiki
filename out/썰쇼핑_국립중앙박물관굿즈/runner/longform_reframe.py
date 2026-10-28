"""Source-space subject-safe landscape framing, independent of providers and OS.

Input boxes must describe the narrated subject/action, not inferred identity.
All boxes at a timestamp are mandatory (including both people in a two-shot).
This module only solves geometry; it does not claim to detect or track subjects.
"""
import hashlib
import math

VERSION = 1


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def union(boxes, width, height):
    if not isinstance(boxes, list) or not boxes:
        raise ValueError('subject boxes are required; no implicit center fallback')
    for b in boxes:
        if (not isinstance(b, (list, tuple)) or len(b) != 4 or not all(number(v) for v in b)
                or not 0 <= b[0] < b[2] <= width or not 0 <= b[1] < b[3] <= height):
            raise ValueError('subject box must be finite source-space left/top/right/bottom')
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


# 렌더 배율 구간. 상한 190% 는 사장님 결정(2026-10-07 «135~190%»). LEGACY_MAX_ZOOM = zoom_range 칸이 없는 옛 피사체 영수증(AGY v3·v4
# · 로컬 판독)이 주변 사람 머리 잘림을 확인한 상한 — 그 영수증은 그 안에서만 푼다(from_focus_receipt).
MIN_ZOOM, MAX_ZOOM, LEGACY_MAX_ZOOM = 1.35, 1.90, 1.70


def solve(width, height, samples, identity, *, min_zoom=MIN_ZOOM, max_zoom=MAX_ZOOM, margin=.025, aspect=(16, 9)):
    """Choose reproducible zoom and project smooth centers onto safe intervals.

    samples: ordered {time, boxes:[[left,top,right,bottom], ...]} on local cut clock.
    Temporal sampling/tracking coverage is the caller's responsibility. Explicit
    preservation fallback below 135% is recorded; impossible 16:9 framing raises.
    No source bytes, receipts, audio, or existing renders are mutated here.
    """
    if not all(number(v) and v > 0 for v in (width, height, min_zoom, max_zoom)):
        raise ValueError('invalid dimensions or zoom')
    if not 1 <= min_zoom <= max_zoom or not number(margin) or not 0 <= margin < .25:
        raise ValueError('invalid framing bounds')
    if not isinstance(identity, str) or not identity or not samples:
        raise ValueError('source-bound identity and samples required')
    # aspect = 출력 창 가로:세로(롱폼 16:9 · 숏폼은 영상 창 비율 — 사장님 결정 2026-10-07).
    if not (isinstance(aspect,(list,tuple)) and len(aspect)==2 and all(type(v) is int and v>0 for v in aspect)):
        raise ValueError('aspect must be [width, height] positive integers')
    ratio=aspect[0]/aspect[1]
    base_w=min(float(width), float(height)*ratio);base_h=base_w/ratio
    rows=[];last=-1.;upper=max_zoom
    for sample in samples:
        t=sample.get('time')
        if not number(t) or t < 0 or t <= last:
            raise ValueError('sample times must be finite and strictly increasing')
        last=t;b=union(sample.get('boxes'),width,height)
        # A fraction of the ROI size, clamped only at the physical source edge.
        px=(b[2]-b[0])*margin;py=(b[3]-b[1])*margin
        safe=[max(0,b[0]-px),max(0,b[1]-py),min(width,b[2]+px),min(height,b[3]+py)]
        upper=min(upper,base_w/(safe[2]-safe[0]),base_h/(safe[3]-safe[1]))
        rows.append({'time':t,'required':b,'safe':safe})
    if upper < 1-1e-9:
        raise ValueError(f'required subjects do not fit a full-frame {aspect[0]}:{aspect[1]} crop; choose another shot or explicit contain')
    fallback=upper < min_zoom
    if fallback:
        zoom=max(1.,upper)
    else:
        # Stable across machines/restarts; never Python hash() or per-frame randomness.
        fraction=int(hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16],16)/(2**64-1)
        zoom=min_zoom+(upper-min_zoom)*fraction
    # ★한 샷 = 한 창 (2026-10-23 회원 신고 «컷 없는 한 샷 안에서 창이 흔들린다» · 멕 라이언 241블록 중 48블록 150px 이상 이동).
    #   samples 는 한 원본 샷이다(from_focus_receipt 가 scene_evidence.cuts 있는 영수증을 받지 않는다). 모든 표본의 지킬 영역(safe)을 함께
    #   품는 창이 있으면 그 창 하나로 고정한다 — 창 너비가 합친 영역 폭 이상이면 된다(닫힌 식 · 표본 한 번 훑기). 고른 배율이 그보다 크면
    #   요청 구간 [min_zoom, 고른 배율] 안에서 고정이 되는 가장 큰 배율로 낮춘다. 요청 최소 배율에서도 못 품으면(피사체가 화면을 가로지름)
    #   예전처럼 표본마다 지킬 영역 안으로 따라간다 — 배율을 요청 구간 밖으로 내리지 않는다(주변 사람 판정 subject_agy.bystander_cuts 가 본 구간).
    span_x=max(r['safe'][2] for r in rows)-min(r['safe'][0] for r in rows)
    span_y=max(r['safe'][3] for r in rows)-min(r['safe'][1] for r in rows)
    hold_zoom=min(base_w/span_x if span_x>0 else math.inf,base_h/span_y if span_y>0 else math.inf)
    held=hold_zoom>=zoom-1e-9 or (not fallback and hold_zoom>=min_zoom-1e-9)
    if held:zoom=min(zoom,hold_zoom)
    cw=base_w/zoom;ch=base_h/zoom
    def median(values):
        values=sorted(values);n=len(values)
        return (values[(n-1)//2]+values[n//2])/2
    if held:
        # 창 하나: 전체 표본 중심의 중앙값을 모든 표본이 허락하는 구간에 넣는다.
        lo_x=max(0,max(r['safe'][2] for r in rows)-cw);hi_x=min(width-cw,min(r['safe'][0] for r in rows))
        lo_y=max(0,max(r['safe'][3] for r in rows)-ch);hi_y=min(height-ch,min(r['safe'][1] for r in rows))
        if lo_x > hi_x+1e-7 or lo_y > hi_y+1e-7:
            raise ValueError('no safe source-space crop')
        cx=median([(r['safe'][0]+r['safe'][2])/2 for r in rows]);cy=median([(r['safe'][1]+r['safe'][3])/2 for r in rows])
        x=max(lo_x,min(hi_x,cx-cw/2));y=max(lo_y,min(hi_y,cy-ch/2))
        for row in rows:row['crop']=[x,y,cw,ch]
        return {'version':VERSION,'zoom':zoom,'requested_zoom':[min_zoom,max_zoom],'aspect':list(aspect),
                'fallback':'preserve_required_region_below_minimum' if fallback else None,'hold':'shot',
                'source_size':[width,height],'samples':rows,
                'scope':'geometry only; supplied sample coverage is not a semantic or continuous-video approval'}
    # Rolling median (±0.5 s) reduces detector jitter without dropping either two-shot subject. Times strictly increase,
    # so the window is two moving indices (one pass — the old per-row rescan of every row was O(n²)).
    a=z=0
    for row in rows:
        while rows[a]['time'] < row['time']-.5-1e-9:a+=1
        while z < len(rows) and rows[z]['time'] <= row['time']+.5+1e-9:z+=1
        local=rows[a:z]
        cx=median([(r['safe'][0]+r['safe'][2])/2 for r in local])
        cy=median([(r['safe'][1]+r['safe'][3])/2 for r in local])
        b=row['safe']
        lo_x=max(0,b[2]-cw);hi_x=min(width-cw,b[0])
        lo_y=max(0,b[3]-ch);hi_y=min(height-ch,b[1])
        if lo_x > hi_x+1e-7 or lo_y > hi_y+1e-7:
            raise ValueError('no safe source-space crop')
        x=max(lo_x,min(hi_x,cx-cw/2));y=max(lo_y,min(hi_y,cy-ch/2))
        row['crop']=[x,y,cw,ch]
    return {'version':VERSION,'zoom':zoom,'requested_zoom':[min_zoom,max_zoom],'aspect':list(aspect),
            'fallback':'preserve_required_region_below_minimum' if fallback else None,'hold':None,
            'source_size':[width,height],'samples':rows,
            'scope':'geometry only; supplied sample coverage is not a semantic or continuous-video approval'}


AUTHOR_CROP_WINDOW='author_crop_largest_window_unzoomed'
MARGIN=.025


def _largest_window(box,width,height,margin=MARGIN,aspect=(16,9)):
    """W2-21 검토(10-05): 작성자 crop 이 16:9 가 아닐 때(4:3 필러박스 제거) 지킬 영역이 그 안의 16:9 창에 안 들어가면 그 창.

    왜: 지금 피사체 영수증(C · subject_agy)은 **원본 전체** 좌표에서 계획한다 — 전체 화면 영수증(scene_full_frame ·
    agy_status_error_full_frame)은 원본의 가장 큰 16:9 창(16:9 원본이면 원본 전부)을, 큰 클로즈업은 그 창에 맞는 영역을
    준다. 작성자가 4:3 만 남기면 그 영역이 crop 안의 16:9 창(crop 폭 × 그 폭의 9/16 높이)에 높이로 안 들어가 solve 가
    «16:9 창에 안 들어간다» 로 사전 검사를 막았다(재현: 검토 probe/fullframe_bounds·closeup_bounds).
    정의 — C 가 16:9 가 아닌 원본에 쓰는 규칙(subject_agy.full_frame: «4:3 원본은 16:9 출력이 어차피 위아래를 자른다 —
    창은 판독이 본 영역의 한가운데») 을 작성자 crop 에 그대로: 확대 없이(배율 1.0) crop 안의 가장 큰 16:9 창을
    지킬 영역의 한가운데에 둔다. 들어가는 영역(None)은 그대로 둔다 — 그 컷의 구도는 바뀌지 않는다.
    solve 의 ROI 여유(margin)를 더해도 창 하나에 들어가게 안쪽으로 들인다(subject_agy.full_frame 과 같은 산수).
    이 창은 AGY 가 crop 좌표에서 따로 재확인하지 않았다 — 그래서 plan['fallback'] 에 이름(AUTHOR_CROP_WINDOW)을 남긴다.
    """
    ratio=aspect[0]/aspect[1]
    base_w=min(float(width),float(height)*ratio);base_h=base_w/ratio
    px=(box[2]-box[0])*margin;py=(box[3]-box[1])*margin
    safe=[max(0,box[0]-px),max(0,box[1]-py),min(width,box[2]+px),min(height,box[3]+py)]
    if safe[2]-safe[0]<=base_w+1e-9 and safe[3]-safe[1]<=base_h+1e-9:
        return None
    cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
    x=max(0.,min(width-base_w,cx-base_w/2));y=max(0.,min(height-base_h,cy-base_h/2))
    ix=base_w*margin/(1+2*margin);iy=base_h*margin/(1+2*margin)
    return [x+ix,y+iy,x+base_w-ix,y+base_h-iy]


def from_focus_receipt(receipt, source_sha256, start, frames, fps, size, identity, *, bounds=None, aspect=(16, 9)):
    """Consume the existing subject_focus accepted dense track, without new calls.

    A sparse set of authored centers is deliberately not accepted. The exact
    selected source, output clock, all frames and object verification must match.

    bounds (W2-21 · 2026-10-05): the author's source crop [left,top,right,bottom] — the part of the source that
    exists for this shot (pillarbox/UI removed). Framing is solved inside it (zoom is relative to that region)
    and subject boxes are clipped to it: the author explicitly excluded the rest. A subject wholly outside is an error.
    """
    from subject_focus import _cached_complete
    if (type(frames) is not int or frames < 1 or not number(fps) or fps <= 0
            or not number(start) or start < 0 or not isinstance(receipt, dict)):
        raise ValueError('invalid framing evidence clock')
    scene=receipt.get('scene_evidence') or {}
    origin=scene.get('start');available=scene.get('nframes')
    if not number(origin) or type(available) is not int or available<frames or scene.get('fps')!=fps:
        raise ValueError('subject evidence does not cover the requested clock')
    offset=(start-origin)*fps;first=round(offset)
    if abs(offset-first)>1e-6 or first<0 or first+frames>available:
        raise ValueError('requested source window is outside the measured frame grid')
    cut={'kind':'video','start':float(origin),'duration':available/fps,'fps':fps,
         'focus_key':receipt.get('focus_key')}
    key=receipt.get('_recipe')
    if (not isinstance(key,str) or len(key)!=64
            or receipt.get('size')!=list(size)
            or not _cached_complete(receipt,cut,key,source_sha256)):
        raise ValueError('accepted subject track differs from source, dimensions, clock or dense coverage')
    if receipt['scene_evidence'].get('cuts'):
        raise ValueError('framing must be planned per source shot; split detected scene boundaries first')
    left,top,right,bottom=0,0,size[0],size[1]
    if bounds is not None:
        if (not isinstance(bounds,(list,tuple)) or len(bounds)!=4 or not all(number(v) for v in bounds)
                or not 0<=bounds[0]<bounds[2]<=size[0] or not 0<=bounds[1]<bounds[3]<=size[1]):
            raise ValueError('author crop must be [left,top,right,bottom] inside the source')
        left,top,right,bottom=bounds
    samples=[];widened=0
    for i,point in enumerate(receipt['framing_subject']['track'][first:first+frames]):
        x,y,w,h=point['bbox']
        box=[x,y,x+w,y+h]
        if bounds is not None:
            box=[max(box[0],left),max(box[1],top),min(box[2],right),min(box[3],bottom)]
            if box[0]>=box[2] or box[1]>=box[3]:
                raise ValueError('the measured subject is outside the author crop')
            local=[box[0]-left,box[1]-top,box[2]-left,box[3]-top]
            window=_largest_window(local,right-left,bottom-top,aspect=aspect)
            if window is not None:
                local=window;widened+=1
        else:
            local=box
        samples.append({'time':i/fps,'boxes':[local]})
    evidence=receipt['framing_subject'].get('selection_evidence') or {}
    # 판독이 계획한 창 비율(숏폼 영수증의 window_aspect · 없으면 16:9)과 렌더 창이 다르면 그 영수증의 주변 사람 판정이 맞지 않는다.
    if tuple(evidence.get('window_aspect') or (16, 9))!=tuple(aspect):
        raise ValueError('subject receipt was planned for a different window aspect')
    zrange=evidence.get('zoom_range')
    if zrange is None:
        zmin,zmax=MIN_ZOOM,LEGACY_MAX_ZOOM
    elif (isinstance(zrange,list) and len(zrange)==2 and all(number(v) for v in zrange)
            and MIN_ZOOM-1e-9<=zrange[0]<=zrange[1]<=MAX_ZOOM+1e-9):
        zmin,zmax=zrange
    else:
        raise ValueError('subject receipt zoom_range is outside the renderer zoom range')
    plan=solve(right-left,bottom-top,samples,identity,min_zoom=zmin,max_zoom=zmax,aspect=aspect)
    if widened:
        plan['fallback']=AUTHOR_CROP_WINDOW;plan['author_crop_window_frames']=widened
    if bounds is not None:
        for row in plan['samples']:
            row['crop'][0]+=left;row['crop'][1]+=top
            row['required']=[row['required'][0]+left,row['required'][1]+top,row['required'][2]+left,row['required'][3]+top]
            row['safe']=[row['safe'][0]+left,row['safe'][1]+top,row['safe'][2]+left,row['safe'][3]+top]
        plan.update(source_size=list(size),bounds=list(bounds))
    plan.update(focus_recipe=key,source_sha256=source_sha256,source_start=start,fps=fps,
                frames=frames,focus_kind=receipt['framing_subject']['kind'])
    return plan


def fixed_framing(source_sha256, start, frames, fps, size, bounds=None, *, aspect=(16, 9)):
    """확대·추적을 끈 컷(2026-10-23 · 사용자 요청 «블록별 video_treatment 끄기»): 배율 1.0 · 모든 프레임 같은 창.
    창 = 작성자 crop(없으면 원본 전체) 안의 가장 큰 aspect 창, 그 영역의 한가운데. 피사체 기록을 읽지 않는다."""
    if type(frames) is not int or frames < 1 or not number(fps) or fps <= 0 or not number(start) or start < 0:
        raise ValueError('invalid framing clock')
    left,top,right,bottom=(0,0,size[0],size[1]) if bounds is None else bounds
    if not (0<=left<right<=size[0] and 0<=top<bottom<=size[1]):
        raise ValueError('author crop must be [left,top,right,bottom] inside the source')
    ratio=aspect[0]/aspect[1];w=right-left;h=bottom-top
    cw=min(float(w),float(h)*ratio);ch=cw/ratio
    crop=[left+(w-cw)/2,top+(h-ch)/2,cw,ch]
    rows=[{'time':i/fps,'crop':list(crop)} for i in range(frames)]
    return {'version':VERSION,'zoom':1.0,'requested_zoom':[1.0,1.0],'aspect':list(aspect),'fallback':None,'hold':'shot',
            'reframe':False,'source_size':list(size),'samples':rows,
            **({'bounds':list(bounds)} if bounds is not None else {}),
            'source_sha256':source_sha256,'source_start':start,'fps':fps,'frames':frames,
            'scope':'user turned subject reframing off for this cut; geometry only'}
