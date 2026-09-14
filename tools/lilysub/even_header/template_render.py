# 썰쇼핑 템플릿 20종 범용 렌더러 — precision20-data.js 좌표를 PIL 로 그대로 그린다(브라우저 없음).
#
# 쓰는 법
#   python template_render.py --sheet                 # 20종 × (훅·본문) 참조이미지 vs 렌더 격자 → sheet_hook.jpg / sheet_body.jpg
#   python template_render.py --name 이븐쇼핑 --kind hook --out x.png [--photo 사진.jpg] [--text hook1=... hook2=... ...]
#   (모듈로) render(tpl, 'hook', texts, photo=PIL.Image|None, W=1080) -> RGBA
#
# 좌표 어휘(정의 파일 실측, 2026-09-15): surfaces{x,y,width,height,background,border,borderTop,borderBottom,shadow,radius}
#   lines{bind,x0,x1,y0,y1,h,font_size,font_family,font_weight,color,accent,accent_words,max_lines,scale_x,lpct,rpct,
#         stroke,shadow_y,letter_spacing,background,patch_top,patch_bottom,no_patch,skip_patch,role}
#   ornaments{type=menu|search}, channel_box, white_box{y0,y1,background,text}, boxes[]
# 정답 렌더러는 out/precision20-ui.js — 의미가 갈리면 그쪽이 맞다.
import io, os, re, sys, json, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))          # 트랙 루트
STATIC_FONTS = os.path.join(ROOT, 'shopping_shorts', 'static', 'fonts')
DATA = os.path.join(HERE, 'precision20-data.js')
REFS = os.path.join(HERE, 'template_refs')

# 글꼴 가족 → 파일. ★없는 3종(JalnanGothic·Jalnan2·GothicA1Black)은 대체 — 격자에서 표시한다
FONT_FILES = {
    'TmonMonsori':    os.path.join(STATIC_FONTS, 'TmonMonsori.ttf'),
    'PretendardXBold': os.path.join(STATIC_FONTS, 'Pretendard-ExtraBold.otf'),
    'Pretendard':      os.path.join(STATIC_FONTS, 'Pretendard-Bold.otf'),
    'PretendardBold':  os.path.join(STATIC_FONTS, 'Pretendard-Bold.otf'),
    'GmarketSansBold': os.path.join(STATIC_FONTS, 'GmarketSansBold.otf'),
    'BinggraeBold':   os.path.join(STATIC_FONTS, 'Binggrae-Bold.otf'),
    'BlackHanSans':   os.path.join(STATIC_FONTS, 'BlackHanSans.ttf'),
    'Cafe24Ohsquare': os.path.join(STATIC_FONTS, 'Cafe24Ohsquare.ttf'),
    'SBAggroB':       os.path.join(HERE, 'fonts', 'SBAggroB.ttf'),
    'YgJalnan':       os.path.join(HERE, 'fonts', 'yg-jalnan.ttf'),
    'JalnanGothic':   os.path.join(HERE, 'fonts', 'yg-jalnan.ttf'),      # 대체
    'Jalnan2':        os.path.join(HERE, 'fonts', 'yg-jalnan.ttf'),      # 대체
    'GothicA1Black':  os.path.join(STATIC_FONTS, 'BlackHanSans.ttf'),    # 대체
}
FONT_FALLBACK = {'JalnanGothic', 'Jalnan2', 'GothicA1Black'}
GAPS = []   # 못 그린 것 기록(radial 그라데이션·대체 글꼴 등)

# ───────────────────────── 데이터 ─────────────────────────
def load_templates(path=DATA):
    s = io.open(path, encoding='utf-8').read()
    body = s[s.find('['):s.rfind(';')] if s.rstrip().endswith(';') else s[s.find('['):]
    return json.loads(body)

def by_name(name, tpls=None):
    tpls = tpls or load_templates()
    for t in tpls:
        if t['name'] == name or t.get('id') == name: return t
    raise KeyError(f'템플릿 없음: {name} (있는 것: {[t["name"] for t in tpls]})')

# ───────────────────────── 색·그라데이션 ─────────────────────────
def hexrgba(h):
    h = h.strip()
    if not h.startswith('#'): return None
    h = h[1:]
    if len(h) == 3: h = ''.join(c*2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) if len(h) >= 8 else 255
    return (r, g, b, a)

def _split_top(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == ',' and depth == 0: out.append(cur.strip()); cur = ''
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out

def _parse_stops(parts):
    stops = []
    for p in parts:
        m = re.match(r'(#[0-9a-fA-F]{3,8}|transparent)\s*([\d.]+)?%?', p.strip())
        if not m: continue
        col = (0, 0, 0, 0) if m.group(1) == 'transparent' else hexrgba(m.group(1))
        pos = float(m.group(2))/100 if m.group(2) else None
        stops.append([col, pos])
    if not stops: return []
    if stops[0][1] is None: stops[0][1] = 0.0
    if stops[-1][1] is None: stops[-1][1] = 1.0
    # 빈 위치는 선형 보간
    i = 0
    while i < len(stops):
        if stops[i][1] is None:
            j = i
            while stops[j][1] is None: j += 1
            a, b = stops[i-1][1], stops[j][1]
            for k in range(i, j): stops[k][1] = a + (b-a)*(k-i+1)/(j-i+1)
            i = j
        i += 1
    return stops

def gradient_layer(w, h, spec):
    """CSS linear-gradient(angle, stops) → RGBA 이미지. radial 은 None(건너뜀)."""
    m = re.match(r'(linear|radial)-gradient\((.*)\)\s*$', spec.strip(), re.S)
    if not m: return None
    kind, inner = m.group(1), m.group(2)
    parts = _split_top(inner)
    if kind == 'radial':
        GAPS.append(f'radial-gradient 건너뜀: {spec[:60]}')
        return None
    angle = 180.0
    if parts and re.match(r'^-?[\d.]+deg$', parts[0].strip()):
        angle = float(parts[0].strip()[:-3]); parts = parts[1:]
    elif parts and parts[0].strip().startswith('to '):
        d = parts[0].strip()[3:]; parts = parts[1:]
        angle = {'top':0,'right':90,'bottom':180,'left':270}.get(d, 180)
    stops = _parse_stops(parts)
    if not stops: return None
    # CSS: 0deg=위로, 90deg=오른쪽. 진행 방향 벡터
    th = np.deg2rad(angle)
    dx, dy = np.sin(th), -np.cos(th)
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = (w-1)/2, (h-1)/2
    L = abs(w*dx) + abs(h*dy)          # 그라데이션 선 길이(CSS 정의)
    tt = ((xs-cx)*dx + (ys-cy)*dy)/L + 0.5
    tt = np.clip(tt, 0, 1)
    pos = np.array([p for _, p in stops]); cols = np.array([c for c, _ in stops], float)
    out = np.zeros((h, w, 4))
    for i in range(4): out[..., i] = np.interp(tt, pos, cols[:, i])
    return Image.fromarray(out.astype('uint8'), 'RGBA')

def paint_background(w, h, spec):
    """배경 문자열(단색 / 그라데이션 / 여러 층 콤마) → RGBA. 층 순서는 CSS 대로 앞이 위."""
    w, h = max(1, w), max(1, h)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if not spec: return img
    layers = _split_top(spec)
    for lay in reversed(layers):
        lay = lay.strip()
        if lay.startswith('#'):
            c = hexrgba(lay); tile = Image.new('RGBA', (w, h), c)
        elif lay == 'transparent': continue
        else:
            tile = gradient_layer(w, h, lay)
            if tile is None: continue
        img.alpha_composite(tile)
    return img

def rounded_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w-1, h-1], radius=int(r), fill=255)
    return m

# ───────────────────────── 글꼴·글자 ─────────────────────────
_fcache = {}
def font(family, size):
    fam = family or 'PretendardXBold'
    path = FONT_FILES.get(fam)
    if fam in FONT_FALLBACK: GAPS.append(f'글꼴 대체: {fam}')
    if not path or not os.path.exists(path):
        GAPS.append(f'글꼴 없음: {fam} → Pretendard'); path = FONT_FILES['PretendardXBold']
    key = (path, int(size))
    if key not in _fcache: _fcache[key] = ImageFont.truetype(path, max(6, int(size)))
    return _fcache[key]

def text_size(f, s, spacing=0):
    d = ImageDraw.Draw(Image.new('L', (4, 4)))
    bb = d.textbbox((0, 0), s, font=f)
    w = bb[2]-bb[0] + (spacing*(len(s)-1) if spacing else 0)
    return w, bb[3]-bb[1], bb

def luminance(rgba):
    if not rgba: return None
    def ch(v):
        v = v/255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    r, g, b = rgba[:3]
    return ch(r)*.2126 + ch(g)*.7152 + ch(b)*.0722

def contrast_stroke(text_rgba, bg_rgba, S):
    """정답 렌더러 contrastOutline: 대비비 <3 이면 1.2px(미리보기 기준) 외곽선. 밝은 배경엔 #151515, 어두우면 흰색."""
    fg, bg = luminance(text_rgba), luminance(bg_rgba)
    if fg is None or bg is None: return 0, None
    ratio = (max(fg, bg)+.05)/(min(fg, bg)+.05)
    if ratio >= 3: return 0, None
    return max(2, int(round(1.4*S))), ((21,21,21,255) if bg > .179 else (255,255,255,255))

def draw_runs(layer, x, y, runs, f, stroke_w=0, shadow=0, spacing=0, stroke_col=(8,8,8,255), bg_rgba=None, S=1.0):
    """runs=[(text,color)] 를 왼쪽 x 부터 이어 그린다. 그림자·외곽선 포함. 런마다 대비 판정."""
    d = ImageDraw.Draw(layer)
    cx = x
    for text, col in runs:
        sw, sc = stroke_w, stroke_col
        if not sw and bg_rgba is not None:
            sw, sc2 = contrast_stroke(col, bg_rgba, S)
            if sc2: sc = sc2
        if spacing:
            for ch in text:
                if ch.isspace():                      # ★공백을 글리프로 그리면 □(두부)가 찍힌다(다있슈 실측)
                    cx += text_size(f, 'a')[0]*0.6 + spacing; continue
                if shadow: d.text((cx, y+shadow), ch, font=f, fill=(8,8,8,255), stroke_width=sw, stroke_fill=(8,8,8,255))
                d.text((cx, y), ch, font=f, fill=col, stroke_width=sw, stroke_fill=sc)
                cx += text_size(f, ch)[0] + spacing
        else:
            # ★공백 글리프가 없는 글꼴(Binggrae 등)은 통짜로 그리면 □가 찍힌다(다있슈 실측) → 어절마다 그리고 공백은 건너뛴다
            space_w = text_size(f, '가')[0]*0.32
            parts = text.split(' ')
            for k, word in enumerate(parts):
                if word:
                    if shadow: d.text((cx, y+shadow), word, font=f, fill=(8,8,8,255), stroke_width=sw, stroke_fill=(8,8,8,255))
                    d.text((cx, y), word, font=f, fill=col, stroke_width=sw, stroke_fill=sc)
                    cx += text_size(f, word)[0]
                if k < len(parts)-1: cx += space_w

def wrap_words(f, text, max_w, max_lines):
    words = text.split(); lines = []; cur = ''
    for w in words:
        cand = (cur + ' ' + w).strip()
        if text_size(f, cand)[0] <= max_w or not cur: cur = cand
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines[:max_lines], len(lines) <= max_lines

def line_background(ln, frame, bind):
    """대비 판정용 배경색 — 정답 렌더러 순서: channel→줄배경 / white_box / cleanup_region / 줄배경 / title_bg"""
    y = ln['y0'] + (ln.get('h') or (ln['y1']-ln['y0']))/2
    if bind == 'channel': return hexrgba(ln.get('background') or '#000000')
    wb = frame.get('white_box')
    if wb and wb['y0'] <= y <= wb['y1']: return hexrgba(wb.get('background') or '#FFFFFF')
    for r in frame.get('cleanup_regions') or []:
        if r['y'] <= y < r['y']+r['height'] and r.get('background'): return hexrgba(r['background'])
    return hexrgba(ln.get('background') or frame.get('title_bg') or '#101010')

def draw_line(img, ln, text, frame, tpl, S, role_default_color, bind=None):
    """정의 한 줄(line)을 그린다. 반환: 실제 그린 상자(px) 또는 None."""
    if not text: return None
    bg_rgba = line_background(ln, frame, bind)
    x0, x1 = ln['x0']*S, ln['x1']*S
    y0 = ln['y0']*S; h = (ln.get('h') or (ln['y1']-ln['y0']))*S
    box_w = max(4, x1-x0)
    fam = ln.get('font_family') or frame.get('font_family') or tpl.get('font_family')
    fs = (ln.get('font_size') or 24)*S
    color = hexrgba(ln.get('color') or role_default_color or '#FFFFFF')
    accent = hexrgba(ln['accent']) if ln.get('accent') else None
    n_acc = int(ln.get('accent_words') or 0)
    max_lines = int(ln.get('max_lines') or 1)
    scale_x_cap = float(ln.get('scale_x') or 1)
    lp, rp = ln.get('lpct', 50), ln.get('rpct', 50)
    align = 'left' if (lp < 4 and rp > 10) else 'center'
    spacing = (ln['letter_spacing']*S) if ln.get('letter_spacing') not in (None, 0) and ln.get('letter_spacing') > 0 else 0
    stroke_w = int(round((ln.get('stroke') or 0)*S))
    shadow = int(round((ln.get('shadow_y') or 0)*S))

    # 글자 뒤 배경(patch) — 새로 그리는 판이므로 배경색이 있을 때만 칠한다
    if ln.get('background') and not ln.get('no_patch') and not ln.get('skip_patch'):
        pt = (ln.get('patch_top', 2))*S; pb = (ln.get('patch_bottom', 2))*S
        bg = paint_background(int(box_w), int(h+pt+pb), ln['background'])
        img.alpha_composite(bg, (int(x0), int(y0-pt)))

    f = font(fam, fs)
    # 줄바꿈 / 축소
    lines = [text]; xscale = 1.0
    if max_lines > 1:
        lines, ok = wrap_words(f, text, box_w, max_lines)
        while not ok and fs > 8:
            fs *= 0.94; f = font(fam, fs); lines, ok = wrap_words(f, text, box_w, max_lines)
    else:
        tw = text_size(f, text, spacing)[0]
        if tw > box_w:
            xscale = max(0.5, min(scale_x_cap if scale_x_cap < 1 else 1.0, box_w/tw))
            if scale_x_cap >= 1: xscale = box_w/tw          # 정답 렌더러: min(scale_x, overflow) → 필요한 만큼 압축
            xscale = max(0.55, xscale)
            if xscale < 0.55:  # 그래도 넘치면 글자 줄임
                pass
    # ★배치는 폭 계산이 아니라 **실제로 그린 글리프의 경계(getbbox)** 로 한다 — 계산식은 외곽선·자간·
    #   강조 런에서 어긋나 오른쪽이 잘렸다(숏템·활용정점 격자 실측). 그려서 재고, 넓으면 가로만 줄인다.
    lh = fs*1.05
    total_h = lh*len(lines)
    for i, line in enumerate(lines):
        if n_acc > 0 and accent:
            ws = line.split(); runs = [(' '.join(ws[:n_acc]), accent)]
            rest = ' '.join(ws[n_acc:])
            if rest: runs.append((' ' + rest, color))
        else:
            runs = [(line, color)]
        pad = stroke_w + shadow + 8
        tmp = Image.new('RGBA', (img.width*2, int(lh*2 + pad*2)), (0,0,0,0))
        draw_runs(tmp, pad, pad, runs, f, stroke_w, shadow, spacing, bg_rgba=bg_rgba, S=S)
        bb = tmp.getbbox()
        if not bb: continue
        glyph = tmp.crop(bb)
        gw, gh = glyph.size
        if gw > box_w:
            cap = scale_x_cap if scale_x_cap < 1 else 1.0
            xs = max(0.5, min(cap, box_w/gw)) if cap < 1 else max(0.5, box_w/gw)
            glyph = glyph.resize((max(1, int(gw*xs)), gh), Image.LANCZOS); gw = glyph.width
        cy = y0 + (h - total_h)/2 + i*lh + lh/2
        ty = int(cy - gh/2)
        tx = int(x0) if align == 'left' else int(x0 + (box_w - gw)/2)
        img.alpha_composite(glyph, (max(0, tx), max(0, ty)))
    return (x0, y0, x1, y0+h)

# ───────────────────────── 표면·장식 ─────────────────────────
def draw_surface(img, sf, S):
    x, y = int(round(sf['x']*S)), int(round(sf['y']*S))
    w, h = max(1, int(round(sf['width']*S))), max(1, int(round(sf['height']*S)))
    # shadow: "0 0 12px 7px #FFFFFFB0" / "inset ..." / "0 3px 9px #111111"
    sh = sf.get('shadow')
    if sh and not sh.startswith('inset'):
        m = re.match(r'(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px(?:\s+([\d.]+)px)?\s+(#[0-9a-fA-F]{3,8})', sh.strip())
        if m:
            ox, oy, blur = float(m.group(1))*S, float(m.group(2))*S, float(m.group(3))*S
            spread = float(m.group(4) or 0)*S; col = hexrgba(m.group(5))
            gl = Image.new('RGBA', img.size, (0,0,0,0))
            ImageDraw.Draw(gl).rounded_rectangle([x-spread+ox, y-spread+oy, x+w+spread+ox, y+h+spread+oy],
                                                 radius=int((sf.get('radius') or 0)*S), fill=col)
            if blur > 0: gl = gl.filter(ImageFilter.GaussianBlur(blur))
            img.alpha_composite(gl)
    tile = paint_background(w, h, sf.get('background'))
    if sf.get('radius'):
        img.paste(tile, (x, y), rounded_mask(w, h, sf['radius']*S))
    else:
        img.alpha_composite(tile, (x, y))
    d = ImageDraw.Draw(img)
    bw = max(1, int(round(1*S*0.6)))
    for key in ('border', 'borderTop', 'borderBottom'):
        c = sf.get(key)
        if not c: continue
        col = hexrgba(c)
        if key == 'border': d.rounded_rectangle([x, y, x+w-1, y+h-1], radius=int((sf.get('radius') or 0)*S), outline=col, width=bw)
        elif key == 'borderTop': d.line([(x, y), (x+w, y)], fill=col, width=bw)
        else: d.line([(x, y+h-1), (x+w, y+h-1)], fill=col, width=bw)

def draw_box(img, b, S):
    x, y = int(b['x']*S), int(b['y']*S); w, h = int(b['width']*S), int(b['height']*S)
    sh = b.get('shadow')
    if sh:
        m = re.match(r'(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px\s+(#[0-9a-fA-F]{3,8})', sh.strip())
        if m:
            gl = Image.new('RGBA', img.size, (0,0,0,0))
            ImageDraw.Draw(gl).rectangle([x+float(m.group(1))*S, y+float(m.group(2))*S, x+w+float(m.group(1))*S, y+h+float(m.group(2))*S], fill=hexrgba(m.group(4)))
            img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(float(m.group(3))*S)))
    img.alpha_composite(paint_background(w, h, b.get('background') or '#FFFFFF'), (x, y))
    if b.get('border'):
        ImageDraw.Draw(img).rectangle([x, y, x+w-1, y+h-1], outline=hexrgba(b['border']), width=max(1, int((b.get('border_width') or 1)*S)))

def draw_channel_box(img, cb, text, tpl, S):
    x, y = cb['x']*S, cb['y']*S; w, h = cb['width']*S, cb['height']*S
    if cb.get('background'):
        tile = paint_background(int(w), int(h), cb['background'])
        if cb.get('radius'): img.paste(tile, (int(x), int(y)), rounded_mask(int(w), int(h), cb['radius']*S))
        else: img.alpha_composite(tile, (int(x), int(y)))
    if cb.get('border'):
        ImageDraw.Draw(img).rectangle([x, y, x+w, y+h], outline=hexrgba(cb['border']), width=max(1, int(S)))
    ln = dict(bind='channel', x0=cb['x'], x1=cb['x']+cb['width'], y0=cb['y'], h=cb['height'],
              font_size=cb.get('font_size', 22), font_family=cb.get('font_family'), color=cb.get('color', '#FFFFFF'),
              letter_spacing=cb.get('letter_spacing'), no_patch=True, background=cb.get('background'))
    draw_line(img, ln, text, {}, tpl, S, cb.get('color', '#FFFFFF'), bind='channel')

def draw_ornaments(img, frame, S):
    d = ImageDraw.Draw(img)
    for o in frame.get('ornaments', []):
        x, y, w, h = o['x']*S, o['y']*S, o['width']*S, o['height']*S
        col = hexrgba(o.get('color', '#E6E9E5')); t = max(2, int(2.2*S/2.5))
        if o['type'] == 'menu':
            for k in (0, .5, 1): d.line([(x, y+k*h), (x+w, y+k*h)], fill=col, width=t)
        elif o['type'] == 'search':
            r = w*0.36; cx, cy = x+w*0.42, y+h*0.42
            d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=col, width=t)
            d.line([(cx+r*0.7, cy+r*0.7), (x+w, y+h)], fill=col, width=t)

# ───────────────────────── 프레임 렌더 ─────────────────────────
def bind_lines(frame, kind):
    """bind 없는 줄에 순서대로 역할을 붙인다(정답 렌더러 규칙)."""
    lines = frame.get('lines', [])
    order = ['hook1', 'hook2', 'bodyTitle'] if kind == 'hook' else ['bodyTitle', 'caption']
    out, i = [], 0
    for ln in lines:
        b = ln.get('bind')
        if not b:
            b = order[i] if i < len(order) else f'line{i}'
        i += 1
        out.append((b, ln))
    return out

POP_MS = 520 * 0.72          # 훅 '팝업' 모션(장면꾸미기 UI hookMotion=pop, 속도 빠름) 총 길이
POP_STAGGER = 90 * 0.72      # 글자 줄마다 시차

def pop_state(pop_ms, index):
    """팝업 키프레임: 0.25배·투명 → 68%에서 1.14배·불투명 → 1배. 줄마다 index*시차."""
    t = pop_ms - index*POP_STAGGER
    if t < 0: return (0.25, 0.0)
    p = min(1.0, t/POP_MS)
    if p < .68: return (.25 + (1.14-.25)*(p/.68), p/.68)
    return (1.14 - .14*((p-.68)/.32), 1.0)

def render(tpl, kind, texts, photo=None, W=1080, H_out=None, pop_ms=None):
    frame = tpl[kind]
    S = W / frame['width']
    H = int(round(frame['height']*S))
    img = Image.new('RGBA', (W, H), hexrgba(tpl.get('title_bg') or frame.get('title_bg') or '#101010'))
    vf = int(round(frame['video_from']['y']*S))
    # 사진
    if photo is not None:
        ph = photo.convert('RGB'); pw, phh = ph.size
        want = W/(H-vf) if H > vf else 1
        if pw/phh > want:
            nw = int(phh*want); ph = ph.crop(((pw-nw)//2, 0, (pw+nw)//2, phh))
        else:
            nh = int(pw/want); ph = ph.crop((0, 0, pw, nh))
        img.paste(ph.resize((W, H-vf), Image.LANCZOS), (0, vf))
    for sf in frame.get('surfaces', []): draw_surface(img, sf, S)
    for b in frame.get('boxes', []) or []: draw_box(img, b, S)
    wb = frame.get('white_box')
    if wb:
        y0, y1 = int(wb['y0']*S), int(wb['y1']*S)
        img.alpha_composite(paint_background(W, y1-y0, wb.get('background') or '#FFFFFF'), (0, y0))
        if wb.get('text') and isinstance(wb['text'], dict):
            t_ = dict(wb['text']); t_.setdefault('no_patch', True)
            draw_line(img, t_, texts.get('bodyTitle') or texts.get('caption'), frame, tpl, S, '#111111', bind='bodyTitle')
    cb = frame.get('channel_box') or (frame.get('channel_boxes') or [None])[0]
    # ★sample 에 channel 이 없는 템플릿이 대부분 → 빈 박스가 뜬다(격자 실측). 없으면 템플릿 이름
    if cb: draw_channel_box(img, cb, texts.get('channel') or tpl['name'], tpl, S)
    accent_default = tpl.get('accent') or tpl.get('accent_color') or '#FFE500'
    for i, (b, ln) in enumerate(bind_lines(frame, kind)):
        role_col = {'hook1': '#FFFFFF', 'hook2': accent_default, 'bodyTitle': '#FFFFFF', 'caption': '#111111'}.get(b, '#FFFFFF')
        if pop_ms is None:
            draw_line(img, ln, texts.get(b, ''), frame, tpl, S, role_col, bind=b)
        else:
            # 팝업: 줄을 따로 그려 상자 중심 기준 확대·투명 적용
            sc, al = pop_state(pop_ms, i)
            if al <= 0: continue
            layer = Image.new('RGBA', img.size, (0,0,0,0))
            draw_line(layer, ln, texts.get(b, ''), frame, tpl, S, role_col, bind=b)
            cx = (ln['x0']+ln['x1'])/2*S; cy = (ln['y0'] + (ln.get('h') or (ln['y1']-ln['y0']))/2)*S
            if abs(sc-1) > 1e-3:
                big = layer.resize((max(1,int(layer.width*sc)), max(1,int(layer.height*sc))), Image.LANCZOS)
                canvas = Image.new('RGBA', layer.size, (0,0,0,0))
                canvas.paste(big, (int(cx-cx*sc), int(cy-cy*sc)), big); layer = canvas
            if al < 1: layer.putalpha(layer.split()[3].point(lambda v: int(v*al)))
            img.alpha_composite(layer)
    draw_ornaments(img, frame, S)
    if H_out and H_out != H:
        canvas = Image.new('RGBA', (W, H_out), (0,0,0,255)); canvas.paste(img, (0, 0)); img = canvas
    return img

# ───────────────────────── B안 헤더 층 ─────────────────────────
def body_cut_y(tpl, S):
    """본문 헤더를 어디까지 쓸지 — 자막띠(릴리가 맡는다)는 뺀다: white_box 위 / caption 줄 위 / 없으면 video_from."""
    frame = tpl['body']
    wb = frame.get('white_box')
    if wb: return int(wb['y0']*S)
    for b, ln in bind_lines(frame, 'body'):
        if b == 'caption':
            return int((ln['y0'] - (ln.get('patch_top', 2) or 0) - 2)*S)
    return int(frame['video_from']['y']*S)

def header_layer(tpl, kind, texts, photo_top, W=1080, H=1920, pop_ms=None):
    """video_raw(사진 y=photo_top 부터) 위에 얹을 헤더만 투명 레이어로. 훅은 세로 축소, 본문은 아래를 헤더 끝색으로 채운다."""
    frame = tpl[kind]; S = W/frame['width']
    full = render(tpl, kind, texts, photo=None, W=W, pop_ms=pop_ms)
    cut = int(round(frame['video_from']['y']*S)) if kind == 'hook' else body_cut_y(tpl, S)
    hdr = full.crop((0, 0, W, max(2, cut)))
    layer = Image.new('RGBA', (W, H), (0,0,0,0))
    if hdr.height > photo_top:
        layer.paste(hdr.resize((W, photo_top), Image.LANCZOS), (0, 0))
    else:
        layer.paste(hdr, (0, 0))
        if hdr.height < photo_top:
            row = np.array(hdr.convert('RGB'))[-2:].reshape(-1, 3).mean(axis=0).astype(int)
            fill = Image.new('RGBA', (W, photo_top-hdr.height), (int(row[0]), int(row[1]), int(row[2]), 255))
            layer.paste(fill, (0, hdr.height))
    return layer

# ───────────────────────── 격자(검증) ─────────────────────────
def sheet(tpls, kind, out_path, tile_h=420):
    tiles = []
    for t in tpls:
        frame = t[kind]
        refp = os.path.join(REFS, t.get(f'{kind}_image', ''))
        ref = Image.open(refp).convert('RGB') if os.path.exists(refp) else None
        W = 1080; S = W/frame['width']; H = int(round(frame['height']*S))
        vf = int(round(frame['video_from']['y']*S))
        photo = None
        if ref is not None:
            r2 = ref.resize((W, H), Image.LANCZOS); photo = r2.crop((0, vf, W, H))
        GAPS.clear()
        ours = render(t, kind, t.get('sample', {}), photo=photo, W=W).convert('RGB')
        gaps = sorted(set(GAPS))
        def th(im):
            return im.resize((int(im.width*tile_h/im.height), tile_h), Image.LANCZOS)
        a = th(ref.resize((W, H))) if ref is not None else Image.new('RGB', (int(W*tile_h/H), tile_h), (40,0,0))
        b = th(ours)
        pair = Image.new('RGB', (a.width+b.width+6, tile_h+28), (18,18,18))
        pair.paste(a, (0, 28)); pair.paste(b, (a.width+6, 28))
        d = ImageDraw.Draw(pair)
        label = f"{t['name']}  " + ('  '.join(gaps) if gaps else '')
        d.text((4, 6), label[:80], fill=(255, 230, 0) if gaps else (200, 255, 200), font=font('PretendardXBold', 16))
        tiles.append(pair)
    cols = 4; rows = (len(tiles)+cols-1)//cols
    cw = max(t.width for t in tiles); ch = max(t.height for t in tiles)
    out = Image.new('RGB', (cw*cols, ch*rows), (10,10,10))
    for i, tl in enumerate(tiles): out.paste(tl, ((i%cols)*cw, (i//cols)*ch))
    out.save(out_path, quality=88)
    return out_path

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', action='store_true')
    ap.add_argument('--name'); ap.add_argument('--kind', default='hook'); ap.add_argument('--out')
    ap.add_argument('--photo'); ap.add_argument('--text', nargs='*', default=[])
    a = ap.parse_args()
    tpls = load_templates()
    if a.sheet:
        for k in ('hook', 'body'):
            p = sheet(tpls, k, os.path.join(HERE, f'sheet_{k}.jpg'))
            print('sheet', p)
        sys.exit(0)
    t = by_name(a.name, tpls)
    texts = dict(t.get('sample', {}))
    for kv in a.text:
        k, v = kv.split('=', 1); texts[k] = v
    photo = Image.open(a.photo) if a.photo else None
    im = render(t, a.kind, texts, photo=photo, W=1080, H_out=1920)
    im.convert('RGB').save(a.out or f'{t["name"]}_{a.kind}.png')
    print('saved', a.out, '| gaps:', sorted(set(GAPS)))
