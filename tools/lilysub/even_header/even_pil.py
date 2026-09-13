# 이븐쇼핑(t11) 템플릿을 PIL 로 직접 그린다 — 볼케이노와 같은 방식(좌표 → 이미지 파일).
# 좌표·색·크기는 track/장면꾸미기UI코덱스 out/precision20-data.js  name=="이븐쇼핑" 그대로.
# 브라우저·스크린샷 없음.
import io, os, json, glob, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WORK = os.path.dirname(os.path.abspath(__file__))
OUT_FR = os.path.join(WORK, 'pil_frames')
SRC_MP4 = os.path.join(WORK, 'out', 'choiminsik-1980s-pay_v001.mp4')
OUT_MP4 = os.path.join(WORK, 'out', 'even_pil.mp4')
FONT = os.path.join(WORK, 'fonts', 'yg-jalnan.ttf')   # TmonMonsori 미설치 → 대체
W, H = 1080, 1920
FPS = 30

CHANNEL = '디씨썰극장'
HOOK1 = '최민식이 기억하는'
HOOK2 = '80년대 출연료'
BODYTITLE = '최민식 첫 출연료 150만원의 진실'

# ── 정의 파일(precision20-data.js) 값 그대로 ──────────────────────────
HOOK = dict(w=425, h=748, video_from=285,
    surfaces=[dict(x=0,y=0,w=425,h=285,grad=[('#202221',0),('#202020',.70),('#424441',1)]),
              dict(x=0,y=68,w=425,h=1,solid='#727772'),
              dict(x=5,y=225,w=415,h=51,grad=[('#FFFFFF',0),('#FFFFFF',.72),('#ECEEEC',1)],
                   glow=dict(blur=12,spread=7,color=(255,255,255,0xB0)),radius=2)],
    lines=[dict(bind='hook1',x0=15,x1=410,y0=103,y1=152,fs=43,color='#FFFFFF',stroke=2,shadow=2),
           dict(bind='hook2',x0=13,x1=412,y0=151,y1=213,fs=50,color='#00F9ED',stroke=2,shadow=2),
           dict(bind='bodyTitle',x0=19,x1=406,y0=231,y1=265,fs=25,color='#080808')],
    menu=dict(x=16,y=14,w=40,h=25,color='#E6E9E5'), search=dict(x=372,y=9,w=29,h=29,color='#D9DFDB'))
BODY = dict(w=420, h=746, video_from=229,
    surfaces=[dict(x=0,y=0,w=420,h=156,grad=[('#454545',0),('#3B3B3B',1)]),
              dict(x=0,y=67,w=420,h=1,solid='#949494'),
              dict(x=0,y=156,w=420,h=73,grad=[('#FFFFFF',0),('#FAFBFA',1)])],
    lines=[dict(bind='channel',x0=60,x1=360,y0=12,y1=58,fs=26,color='#FFFFFF'),
           dict(bind='bodyTitle',x0=15,x1=405,y0=82,y1=121,fs=27,color='#FFFFFF'),
           dict(bind='caption',x0=23,x1=397,y0=173,y1=213,fs=27,color='#090909')],
    menu=dict(x=16,y=14,w=40,h=25,color='#E6E9E5'), search=dict(x=367,y=9,w=29,h=29,color='#D9DFDB'))

POP_MS = 520 * 0.72          # 팝업 총 길이(빠름)
POP_STAGGER = 90 * 0.72      # 글자별 시차
# 얼굴 위치는 face_crop.py 가 YuNet 으로 실측해 둔 것(faces.json). 없으면 만들고 나서 렌더한다.
_fj = os.path.join(WORK, 'faces.json')
if not os.path.exists(_fj):
    raise SystemExit('faces.json 없음 — 먼저 face_crop.py 를 돌려 얼굴 위치를 실측하라')
FACES = json.load(io.open(_fj, encoding='utf-8'))

def hexrgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))

def vgrad(w, h, stops):
    ys = np.linspace(0, 1, h)[:, None]
    cols = np.array([hexrgb(c) for c,_ in stops], float); pos = np.array([p for _,p in stops])
    out = np.zeros((h, 1, 3))
    for i in range(3):
        out[:, 0, i] = np.interp(ys[:, 0], pos, cols[:, i])
    return Image.fromarray(np.repeat(out, w, axis=1).astype('uint8'), 'RGB')

def fit_font(draw, text, max_w, fs):
    while fs > 8:
        f = ImageFont.truetype(FONT, fs)
        bb = draw.textbbox((0,0), text, font=f)
        if bb[2]-bb[0] <= max_w: return f, bb
        fs -= 1
    return f, bb

def text_layer(size, fs, text, box, color, S, stroke=0, shadow=0):
    """글자를 투명 레이어에 그린다(팝업 변형용). box=(x0,x1,y0,y1) 정의좌표, fs=정의 글자크기."""
    layer = Image.new('RGBA', size, (0,0,0,0)); d = ImageDraw.Draw(layer)
    x0,x1,y0,y1 = [v*S for v in box]
    f, bb = fit_font(d, text, (x1-x0)*0.98, int(round(fs*S)))
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    x = x0 + ((x1-x0)-tw)/2 - bb[0]; y = y0 + ((y1-y0)-th)/2 - bb[1]
    sw = int(round(stroke*S)) if stroke else 0
    if shadow:
        d.text((x, y+shadow*S), text, font=f, fill=(0,0,0,255), stroke_width=sw, stroke_fill=(0,0,0,255))
    d.text((x, y), text, font=f, fill=hexrgb(color)+(255,), stroke_width=sw, stroke_fill=(0,0,0,255))
    return layer

def draw_text(img, text, ln, S, pop=None):
    """pop=None 이면 그대로, 아니면 (scale, alpha) 로 중심 확대·투명 적용."""
    layer = text_layer((img.width, img.height), ln['fs'], text,
                       (ln['x0'],ln['x1'],ln['y0'],ln['y1']), ln['color'], S,
                       ln.get('stroke',0), ln.get('shadow',0))
    if pop:
        sc, al = pop
        if al <= 0: return
        cx = (ln['x0']+ln['x1'])/2*S; cy = (ln['y0']+ln['y1'])/2*S
        if abs(sc-1) > 1e-3:
            nw, nh = max(1,int(layer.width*sc)), max(1,int(layer.height*sc))
            big = layer.resize((nw, nh), Image.LANCZOS)
            canvas = Image.new('RGBA', layer.size, (0,0,0,0))
            canvas.paste(big, (int(cx - cx*sc), int(cy - cy*sc)), big)
            layer = canvas
        if al < 1:
            a = layer.split()[3].point(lambda v: int(v*al)); layer.putalpha(a)
    img.alpha_composite(layer)

def draw_ornaments(img, spec, S):
    d = ImageDraw.Draw(img)
    m = spec['menu']; x,y,w,h = m['x']*S, m['y']*S, m['w']*S, m['h']*S
    t = max(2, int(2.2*S))
    for k in (0, .5, 1):
        yy = y + k*h; d.line([(x, yy), (x+w, yy)], fill=hexrgb(m['color']), width=t)
    s = spec['search']; x,y,w,h = s['x']*S, s['y']*S, s['w']*S, s['h']*S
    r = w*0.36; cx, cy = x+w*0.42, y+h*0.42
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=hexrgb(s['color']), width=t)
    d.line([(cx+r*0.7, cy+r*0.7), (x+w, y+h)], fill=hexrgb(s['color']), width=t)

def draw_surfaces(img, spec, S):
    for sf in spec['surfaces']:
        x,y,w,h = [int(round(v*S)) for v in (sf['x'],sf['y'],sf['w'],sf['h'])]
        h = max(h, 2)
        if sf.get('glow'):
            g = sf['glow']; pad = int((g['blur']+g['spread'])*S*2)
            gl = Image.new('RGBA', img.size, (0,0,0,0)); gd = ImageDraw.Draw(gl)
            sp = int(g['spread']*S)
            gd.rounded_rectangle([x-sp, y-sp, x+w+sp, y+h+sp], radius=int(6*S), fill=g['color'])
            gl = gl.filter(ImageFilter.GaussianBlur(int(g['blur']*S)))
            img.alpha_composite(gl)
        if 'grad' in sf: tile = vgrad(w, h, sf['grad'])
        else: tile = Image.new('RGB', (w, h), hexrgb(sf['solid']))
        if sf.get('radius'):
            mask = Image.new('L', (w, h), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0,0,w-1,h-1], radius=int(sf['radius']*S*2), fill=255)
            img.paste(tile, (x, y), mask)
        else:
            img.paste(tile, (x, y))

def photo_for(g, slot_ratio):
    """컷의 사진(또는 밈)을 슬롯 비율로 만든다."""
    if g.get('img'):
        n = g['img']; im = Image.open(os.path.join(WORK, 'img_clean', f'{n:02d}.jpg')).convert('RGB')
        w, h = im.size; nw = min(w, int(h*slot_ratio))
        # ★규칙(중앙/0.72)이 아니라 faces.json(YuNet 실측 얼굴 위치) 기준 — 분할컷 11번에서 규칙이 얼굴을 다 잘랐다
        cx = FACES.get(str(n), {}).get('cx', 0.5) * w
        x0 = int(max(0, min(w-nw, cx-nw/2)))
        return im.crop((x0, 0, x0+nw, h))
    # 밈: 흰 배경 + contain (볼케이노 _load 와 동일)
    p = os.path.join(WORK, g['meme'].replace('/', os.sep))
    s0 = Image.open(p).convert('RGBA')
    bg = Image.new('RGB', s0.size, (255,255,255)); bg.paste(s0, mask=s0.split()[-1])
    w, h = bg.size; tw, th = (w, int(w/slot_ratio)) if w/h < slot_ratio else (int(h*slot_ratio), h)
    canvas = Image.new('RGB', (tw, th), (255,255,255))
    canvas.paste(bg, ((tw-w)//2, (th-h)//2))
    return canvas

def render(spec, texts, g, pop_ms=None):
    S = W / spec['w']
    vf = int(round(spec['video_from']*S))
    img = Image.new('RGBA', (W, H), (11,11,11,255))
    # 사진
    slot_ratio = W / (H - vf)
    ph = photo_for(g, slot_ratio).resize((W, H-vf), Image.LANCZOS)
    img.paste(ph, (0, vf))
    draw_surfaces(img, spec, S)
    draw_ornaments(img, spec, S)
    for i, ln in enumerate(spec['lines']):
        txt = texts.get(ln['bind'])
        if not txt: continue
        pop = None
        if pop_ms is not None:
            t = pop_ms - i*POP_STAGGER
            if t < 0: pop = (0.25, 0.0)
            else:
                p = min(1.0, t/POP_MS)
                if p < .68: sc = .25 + (1.14-.25)*(p/.68); al = p/.68
                else:       sc = 1.14 - .14*((p-.68)/.32); al = 1.0
                pop = (sc, al)
        draw_text(img, txt, ln, S, pop)
    return img.convert('RGB')

def main():
    tm = json.load(io.open(os.path.join(WORK, 'timing.json'), encoding='utf-8'))
    groups = tm['groups']; total = float(tm['total'])
    hook_end = float(groups[1]['t'])   # 훅 = 1장(카드+첫 컷)만. 앞 3판을 훅으로 묶은 건 근거 없는 임의 설정이었다
    for f in glob.glob(os.path.join(OUT_FR, '*')): os.remove(f)
    os.makedirs(OUT_FR, exist_ok=True)
    shots = []
    hook_texts = dict(hook1=HOOK1, hook2=HOOK2, bodyTitle=BODYTITLE)
    g0 = dict(groups[0], img=5)   # 훅 표지는 최민식 단독 클로즈업(캡처05). 1번은 이동진+포스터라 주인공이 안 보인다

    # 훅 팝업 — 30fps 로 0.55초
    n_pop = int(math.ceil((POP_MS + 2*POP_STAGGER)/1000*FPS)) + 1
    for i in range(n_pop):
        ms = i/FPS*1000
        fn = f'pop_{i:03d}.png'
        render(HOOK, hook_texts, g0, pop_ms=ms).save(os.path.join(OUT_FR, fn))
        shots.append((fn, 1/FPS))
    spent = n_pop/FPS
    fn = 'hook_hold.png'
    render(HOOK, hook_texts, g0, pop_ms=POP_MS+2*POP_STAGGER+1).save(os.path.join(OUT_FR, fn))
    shots.append((fn, max(0.02, hook_end-spent)))

    # 본문 — 컷마다 1장, 자막은 컷 대사
    for g in groups:
        st, en = float(g['t']), float(g['t'])+float(g['d'])
        if en <= hook_end: continue
        dur = en - max(st, hook_end)
        fn = f"cut_{g['i']:02d}.png"
        render(BODY, dict(channel=CHANNEL, bodyTitle=BODYTITLE, caption=g['text']), g).save(os.path.join(OUT_FR, fn))
        shots.append((fn, dur))
        print('cut', g['i'], 'img'+str(g['img']) if g.get('img') else 'MEME', round(dur,2), g['text'][:18])

    # concat + 원본 오디오
    lst = os.path.join(OUT_FR, 'concat.txt')
    with io.open(lst, 'w', encoding='utf-8', newline='\n') as f:
        for fn, d in shots:
            f.write(f"file '{os.path.join(OUT_FR, fn).replace(os.sep,'/')}'\nduration {d:.4f}\n")
        f.write(f"file '{os.path.join(OUT_FR, shots[-1][0]).replace(os.sep,'/')}'\n")
    cmd = ['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',lst,'-i',SRC_MP4,
           '-map','0:v','-map','1:a','-c:v','libx264','-preset','medium','-crf','18',
           '-pix_fmt','yuv420p','-r',str(FPS),'-c:a','copy','-shortest',OUT_MP4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print('ffmpeg rc', r.returncode, (r.stderr or '')[-300:])
    print('frames', len(shots), 'sum', round(sum(d for _,d in shots),2), 'timing', total)
    print('OUT', OUT_MP4, os.path.getsize(OUT_MP4) if os.path.exists(OUT_MP4) else 'MISSING')

if __name__ == '__main__':
    main()
