"""Torn media aperture and a shaded paper flap, driven by seekable CSS tweens."""
import json
import random


def brush_paths(seed=23, strokes=5):
    """Overlapping, seeded bristle ribbons in a normalized media aperture."""
    rng = random.Random(seed)
    ribbons = []
    for row in range(strokes):
        centre = (row + .5) * 100 / strokes
        half = 70 / strokes
        upper = [(x, centre-half+rng.uniform(-2, 2)) for x in range(-4, 105, 4)]
        lower = [(x, centre+half+rng.uniform(-2, 2)) for x in range(104, -5, -4)]
        ribbons.append('M ' + ' L '.join(f'{x},{y:.4f}' for x,y in upper+lower) + ' Z')
    return ribbons


def wrap_brush(markup, node):
    nid = 'obj-' + node['id']; spec = node['brush_reveal']
    initial = 1 if spec.get('phase', 'in') == 'out' else 0
    opening, content = markup.split('>', 1)
    content = content.rsplit('</div>', 1)[0]
    strips = []
    for i, path in enumerate(brush_paths(spec.get('seed',23),spec.get('strokes',5))):
        strips.append(f'<clipPath id="brush-edge-{nid}-{i}"><path d="{path}"/></clipPath>'
                      f'<rect id="brush-progress-{nid}-{i}" width="100" height="100" fill="white" '
                      f'clip-path="url(#brush-edge-{nid}-{i})" style="--brush-progress:{initial};transform:scaleX(var(--brush-progress));transform-origin:0 0"/>')
    # A luminance mask reveals the existing child once, so video time is never
    # duplicated or restarted. All motion is seekable, without frame callbacks.
    mask = (f'<svg width="0" height="0" aria-hidden="true" style="position:absolute"><defs>'
            f'<mask id="brush-mask-{nid}" maskUnits="objectBoundingBox" maskContentUnits="objectBoundingBox" '
            f'x="0" y="0" width="1" height="1" style="mask-type:luminance">'
            f'<g transform="scale(.01)">{"".join(strips)}</g></mask></defs></svg>')
    return opening + '>' + mask + f'<div style="position:absolute;inset:0;mask:url(#brush-mask-{nid});-webkit-mask:url(#brush-mask-{nid})">' + content + '</div></div>'


def brush_motion(node, at, length):
    count = node['brush_reveal'].get('strokes',5)
    # Animate a CSS variable: GSAP SVG transform attributes must not compete
    # with the initial CSS transform (which otherwise wins and freezes the mask).
    first, last = (1, 0) if node['brush_reveal'].get('phase', 'in') == 'out' else (0, 1)
    calls = []
    span = length / (1 + .65 * (count-1))
    for i in range(count):
        selector = '#brush-progress-obj-' + node['id'] + '-' + str(i)
        calls.append('tl.fromTo(' + ','.join(json.dumps(x) for x in (
            selector, {'--brush-progress':first}, {'--brush-progress':last,'duration':span,'ease':'none','immediateRender':False}, at+i*.65*span)) + ');')
    return ''.join(calls)


def aperture(seed=23):
    rng = random.Random(seed)
    left = [(rng.uniform(1, 3), i * 100 / 32) for i in range(33)]
    right = [(100 - rng.uniform(1, 3), i * 100 / 32) for i in range(32, -1, -1)]
    return 'polygon(' + ','.join(f'{x:.4f}% {y:.4f}%' for x, y in left + right) + ')'


def wrap_media(markup, node):
    """Keep the original outer transform and timed video; reveal inside it."""
    spec = node['paper_reveal']; nid = 'obj-' + node['id']
    w, h = node['box'][2:]; flap = min(150, h * .22)
    opening, content = markup.split('>', 1)
    content = content.rsplit('</div>', 1)[0]
    color = spec.get('color', '#F0EEE8'); seed = spec.get('seed', 23)
    # No per-frame randomness or JS callbacks: backwards seeks restore exactly.
    paint = f'''<svg id="paper-fold-{nid}" viewBox="0 0 {w} {flap}"
      style="position:absolute;left:0;top:0;width:100%;height:{flap}px;opacity:0;pointer-events:none">
      <defs><linearGradient id="paper-shade-{nid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#777777"/><stop offset=".12" stop-color="{color}"/>
        <stop offset=".75" stop-color="#FFFFFF"/><stop offset="1" stop-color="#AAA79F"/>
      </linearGradient><filter id="paper-grain-{nid}" x="0" y="0" width="100%" height="100%">
        <feTurbulence type="fractalNoise" baseFrequency=".035 .16" numOctaves="2" seed="{seed}"/>
        <feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".16"/></feComponentTransfer>
        <feBlend in="SourceGraphic" mode="multiply"/>
      </filter></defs>
      <path d="M {w*.02} 0 Q {w*.52} {flap*.34} {w*.98} 0 L {w*.92} {flap*.88}
        Q {w*.49} {flap*.55} {w*.07} {flap} Z" fill="url(#paper-shade-{nid})" filter="url(#paper-grain-{nid})"/>
    </svg>'''
    return (opening + '><div id="paper-open-' + nid + '" style="position:absolute;inset:0;clip-path:inset(0% 0% 100% 0%)">'
            + '<div style="position:absolute;inset:0;clip-path:' + aperture(seed) + '">' + content
            + '</div></div>' + paint + '</div>')


def motion(node, at, length):
    nid = 'obj-' + node['id']; h = node['box'][3]; flap = min(150, h * .22)
    calls = []
    def tween(target, start, end, t, span):
        end.update(duration=span, ease='none', immediateRender=False)
        calls.append('tl.fromTo(' + ','.join(json.dumps(x) for x in (target, start, end, t)) + ');')
    tween('#paper-open-' + nid, {'clipPath':'inset(0% 0% 100% 0%)'}, {'clipPath':'inset(0% 0% 0% 0%)'}, at, length)
    tween('#paper-fold-' + nid, {'y':-flap}, {'y':h}, at, length)
    tween('#paper-fold-' + nid, {'opacity':0}, {'opacity':1}, at, length*.12)
    tween('#paper-fold-' + nid, {'opacity':1}, {'opacity':0}, at+length*.82, length*.18)
    return ''.join(calls)
