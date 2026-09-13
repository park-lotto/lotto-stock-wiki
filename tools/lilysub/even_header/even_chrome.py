# B안: video_raw.mp4(볼케이노 판, 사진 y469~1254) 위에 얹을 이븐쇼핑 **헤더 층**만 만든다.
# 투명 PNG 시퀀스 → chrome.mov(ProRes4444). 사진·밈·움직임은 video_raw 그대로.
# 좌표는 even_pil.py 의 HOOK/BODY 스펙(precision20-data.js 이븐쇼핑) 그대로, 높이만 469 에 맞춰 축소.
import io, os, json, math, subprocess, glob
from PIL import Image
import even_pil as E   # 스펙·그리기 함수 재사용 (같은 판단을 두 군데 적지 않는다)

WORK = os.path.dirname(os.path.abspath(__file__))
OUT_FR = os.path.join(WORK, 'chrome_frames')
CHROME_MOV = os.path.join(WORK, 'chrome.mov')
PHOTO_TOP = 469           # video_raw 실측: 사진 띠 시작 y
FPS = 30

def header_layer(spec, texts, pop_ms=None):
    """스펙 헤더(0~video_from)를 폭 1080 기준으로 그린 뒤, 높이를 PHOTO_TOP 으로 축소한 투명 레이어."""
    S = E.W / spec['w']
    full_h = int(round(spec['video_from'] * S))
    img = Image.new('RGBA', (E.W, full_h + 40), (0, 0, 0, 0))
    E.draw_surfaces(img, spec, S)
    E.draw_ornaments(img, spec, S)
    for i, ln in enumerate(spec['lines']):
        txt = texts.get(ln['bind'])
        if not txt: continue
        pop = None
        if pop_ms is not None:
            t = pop_ms - i * E.POP_STAGGER
            if t < 0: pop = (0.25, 0.0)
            else:
                p = min(1.0, t / E.POP_MS)
                if p < .68: sc = .25 + (1.14 - .25) * (p / .68); al = p / .68
                else:       sc = 1.14 - .14 * ((p - .68) / .32); al = 1.0
                pop = (sc, al)
        E.draw_text(img, txt, ln, S, pop)
    # 본문 헤더는 흰 자막띠(spec y156~229)를 뺀다 — B안에서 자막은 릴리 층이 맡으므로 비어 보인다
    cut_h = full_h if spec is E.HOOK else int(round(156 * S))
    hdr = img.crop((0, 0, E.W, cut_h))
    layer = Image.new('RGBA', (E.W, E.H), (0, 0, 0, 0))
    if spec is E.HOOK:
        # 훅: 비율 유지하고 세로만 사진 위 검정 띠(469)에 맞춘다
        layer.paste(hdr.resize((E.W, PHOTO_TOP), Image.LANCZOS), (0, 0))
    else:
        # 본문: 회색 헤더(401px)를 그대로 두고 남는 아래(401~469)는 헤더 끝색으로 채워 사진과 붙인다
        layer.paste(hdr, (0, 0))
        fill = Image.new('RGBA', (E.W, PHOTO_TOP - cut_h), E.hexrgb('#3B3B3B') + (255,))
        layer.paste(fill, (0, cut_h))
    return layer

def main():
    tm = json.load(io.open(os.path.join(WORK, 'timing.json'), encoding='utf-8'))
    groups = tm['groups']; total = float(tm['total'])
    hook_end = float(groups[1]['t'])
    for f in glob.glob(os.path.join(OUT_FR, '*')): os.remove(f)
    os.makedirs(OUT_FR, exist_ok=True)
    hook_texts = dict(hook1=E.HOOK1, hook2=E.HOOK2, bodyTitle=E.BODYTITLE)
    body_texts = dict(channel=E.CHANNEL, bodyTitle=E.BODYTITLE)   # caption 은 릴리 자막이 맡는다
    shots = []
    n_pop = int(math.ceil((E.POP_MS + 2 * E.POP_STAGGER) / 1000 * FPS)) + 1
    for i in range(n_pop):
        fn = f'pop_{i:03d}.png'
        header_layer(E.HOOK, hook_texts, pop_ms=i / FPS * 1000).save(os.path.join(OUT_FR, fn))
        shots.append((fn, 1 / FPS))
    fn = 'hook_hold.png'
    header_layer(E.HOOK, hook_texts, pop_ms=E.POP_MS + 2 * E.POP_STAGGER + 1).save(os.path.join(OUT_FR, fn))
    shots.append((fn, max(0.02, hook_end - n_pop / FPS)))
    fn = 'body.png'
    header_layer(E.BODY, body_texts).save(os.path.join(OUT_FR, fn))
    shots.append((fn, total - hook_end))

    lst = os.path.join(OUT_FR, 'concat.txt')
    with io.open(lst, 'w', encoding='utf-8', newline='\n') as f:
        for fn, d in shots:
            f.write(f"file '{os.path.join(OUT_FR, fn).replace(os.sep, '/')}'\nduration {d:.4f}\n")
        f.write(f"file '{os.path.join(OUT_FR, shots[-1][0]).replace(os.sep, '/')}'\n")
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
           '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-r', str(FPS), CHROME_MOV]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print('chrome.mov rc', r.returncode, (r.stderr or '')[-300:])
    print('shots', len(shots), 'sum', round(sum(d for _, d in shots), 2), 'timing', total)

if __name__ == '__main__':
    main()
