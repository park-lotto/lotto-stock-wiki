"""Seekable lens-ring and curved-blade handoff, below persistent captions.

Geometry is authored. Reference landmarks: Nolan 1675.3667–1676.75,
180 native frames documented in 2026-09-25-nolan-iris-native.json.
No recovered plugin/easing or audio identity claim.
"""
import json
import math


def blade_path(radius, count=8):
    angle=2*math.pi/count; twist=.72; outer=560
    def polar(r,a):return (r*math.cos(a),r*math.sin(a))
    def xy(p):return f'{p[0]:.6f} {p[1]:.6f}'
    # Neighbouring blades share the same curved radial seam, rotated by one
    # sector. Only the aperture radius changes; equal topology permits seeking.
    a=polar(radius,0);b=polar(radius,angle)
    c1=polar(radius+(outer-radius)*.40,angle+twist*.25)
    c2=polar(outer*.9,angle+twist*.8);c=polar(outer,angle+twist)
    d=polar(outer,twist);e1=polar(outer*.9,twist*.8)
    e2=polar(radius+(outer-radius)*.40,twist*.25)
    bend=.12+.88*radius/450
    return (f'M {xy(a)} Q {radius*bend:.6f} {radius*math.tan(angle/2)*bend:.6f} {xy(b)} '
            f'C {xy(c1)} {xy(c2)} {xy(c)} A {outer} {outer} 0 0 0 {xy(d)} '
            f'C {xy(e1)} {xy(e2)} {xy(a)} Z')



def backing_path(radius):
    # An opaque backing with the same curved aperture prevents subpixel cracks
    # between antialiased blades from revealing the hidden source at closure.
    angle=math.pi/4;bend=.12+.88*radius/450
    path='M -2000 -2000 H 2000 V 2000 H -2000 Z'
    path+=f' M {radius:.6f} 0'
    for i in range(8):
        a=i*angle;x=radius*bend;y=radius*math.tan(angle/2)*bend
        cx=x*math.cos(a)-y*math.sin(a);cy=x*math.sin(a)+y*math.cos(a)
        ex=radius*math.cos(a+angle);ey=radius*math.sin(a+angle)
        path+=f' Q {cx:.6f} {cy:.6f} {ex:.6f} {ey:.6f}'
    return path+' Z'


def body():
    blades=''.join(f'<path id="iris-blade-{i}" d="{blade_path(450)}" transform="rotate({i*45})" fill="url(#iris-metal)" stroke="#222" stroke-width=".7"/>' for i in range(8))
    return ('<div id="iris-overlay" style="position:absolute;inset:0;pointer-events:none;visibility:hidden">'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-960 -540 1920 1080" width="1920" height="1080">'
            '<defs><clipPath id="iris-blade-circle"><circle r="450"/></clipPath><linearGradient id="iris-metal" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0a0a0a"/><stop offset="1" stop-color="#454545"/></linearGradient></defs>'
            '<g id="iris-lens">'
            f'<path id="iris-backing" d="{backing_path(450)}" fill="#171717" fill-rule="evenodd"/>'
            +'<g clip-path="url(#iris-blade-circle)">'+blades+'</g><circle r="477" fill="none" stroke="#080808" stroke-width="52"/>'
            '<circle r="477" fill="none" stroke="#444" stroke-width="3"/><circle r="499" fill="none" stroke="#282828" stroke-width="7"/>'
            '</g></svg></div>')


def motion(spec, seconds):
    time={k:spec[k]*seconds for k in ('at','ring_in','close','closed','swap','opened','end')}
    j=json.dumps;result=[]
    def set_(target,state,at=None):
        result.append(('gsap.set' if at is None else 'tl.set')+'('+j(target)+','+j(state)+(('') if at is None else ','+str(at))+');')
    def tween(target,start,end,at,duration):
        result.append('tl.fromTo('+j(target)+','+j(start)+','+j(dict(end,duration=duration,ease='none',immediateRender=False))+','+str(at)+');')
    outgoing='#obj-'+spec['outgoing'];incoming='#obj-'+spec['incoming']
    set_(outgoing,{'opacity':1});set_(incoming,{'opacity':0})
    set_('#iris-overlay',{'visibility':'hidden'});set_('#iris-lens',{'attr':{'transform':'scale(3)'}})
    set_('#iris-overlay',{'visibility':'visible','immediateRender':False},time['at'])
    tween('#iris-lens',{'attr':{'transform':'scale(3)'}},{'attr':{'transform':'scale(1)'}},time['at'],time['ring_in']-time['at'])
    for i in range(9):
        target=f'#iris-blade-{i}' if i<8 else '#iris-backing'
        shape=blade_path if i<8 else backing_path
        open_={'attr':{'d':shape(450)}}
        set_(target,open_)
        # Interpolating only the open and closed paths produces a round hole
        # throughout. Intermediate geometry retains each blade's curved edge.
        for at,end,a,b in ((time['close'],time['closed'],450,0),(time['swap'],time['opened'],0,450)):
            for step in range(16):
                first={'attr':{'d':shape(a+(b-a)*step/16)}}
                last={'attr':{'d':shape(a+(b-a)*(step+1)/16)}}
                tween(target,first,last,at+(end-at)*step/16,(end-at)/16)
    set_(outgoing,{'opacity':0,'immediateRender':False},time['swap'])
    set_(incoming,{'opacity':1,'immediateRender':False},time['swap'])
    tween('#iris-lens',{'attr':{'transform':'scale(1)'}},{'attr':{'transform':'scale(3)'}},time['opened'],time['end']-time['opened'])
    set_('#iris-overlay',{'visibility':'hidden','immediateRender':False},time['end'])
    return ''.join(result)
