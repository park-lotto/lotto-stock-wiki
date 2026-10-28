"""Object-scoped chromatic displacement; independent of scene transforms.

Reference: Nolan wJacNPyhlXU 520.6s, 120-frame inspection recorded in
nolan-gap-480-544-708-724-direct-observations.json. Shader values are authored
parameters, not a claim of recovered original editing settings.
"""
import json
import math


def wrap(markup, target):
    # Image wrappers are divs; nested crops/outlines remain inside the effect.
    opening, content = markup.split('>', 1)
    assert content.endswith('</div>')
    return opening + '><div id="fx-obj-' + target + '" style="position:absolute;inset:0">' + content[:-6] + '</div></div>'


def definitions(target, seed):
    name='object-glitch-'+target
    channels=[]
    for label,index in [('r',0),('g',1),('b',2)]:
        matrix=[0]*20
        matrix[index*5+index]=1;matrix[18]=1
        channels.append(f'<feColorMatrix in="warped" type="matrix" values="{" ".join(map(str,matrix))}" result="{label}"/>')
    return (f'<svg width="0" height="0" aria-hidden="true" style="position:absolute"><defs>'
            f'<filter id="{name}" x="-20%" y="-20%" width="140%" height="140%" color-interpolation-filters="sRGB">'
            f'<feTurbulence type="fractalNoise" baseFrequency=".035 .23" numOctaves="1" seed="{seed}" result="noise"/>'
            f'<feDisplacementMap id="{name}-noise" in="SourceGraphic" in2="noise" scale="0" xChannelSelector="R" yChannelSelector="G" result="warped"/>'
            + ''.join(channels) +
            f'<feOffset id="{name}-r" in="r" dx="0" result="red"/>'
            f'<feOffset id="{name}-b" in="b" dx="0" result="blue"/>'
            '<feComposite in="red" in2="g" operator="arithmetic" k2="1" k3="1" result="rg"/>'
            '<feComposite in="rg" in2="blue" operator="arithmetic" k2="1" k3="1"/>'
            '</filter></defs></svg>')


def motion(cue, at, length):
    target=cue['target'];name='object-glitch-'+target
    inner='#fx-obj-'+target
    # Explicit fromTo endpoints restore exact neutral state on reverse seeks.
    out=['gsap.set('+json.dumps(inner)+',{"filter":"none"});']
    strength=cue.get('strength',6)
    steps=max(1,math.ceil(length*60))
    for n in range(steps):
        t=n/steps
        envelope=(1-t)**2
        sign=-1 if n%2 else 1
        phase=at+length*n/steps;span=length/steps
        for selector,attr,value in [(name+'-r','dx',strength*envelope*sign),
                                     (name+'-b','dx',-strength*envelope*sign),
                                     (name+'-noise','scale',strength*2*envelope)]:
            state={'attr':{attr:round(value,5)}}
            end={**state,'duration':span,'ease':'none','immediateRender':False}
            out.append('tl.fromTo('+','.join(json.dumps(v) for v in ('#'+selector,state,end,phase))+');')
    out.append('tl.fromTo('+','.join(json.dumps(v) for v in (inner,{'filter':'none'},
        {'filter':f'url(#{name})','duration':min(length/1000,.0001),'immediateRender':False},at))+');')
    out.append('tl.set('+','.join(json.dumps(v) for v in (inner,{'filter':'none'},at+length))+');')
    return ''.join(out)
