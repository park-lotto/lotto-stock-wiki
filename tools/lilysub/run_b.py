"""B안 한 명령 — 볼케이노 뇌전구 결과물에 우리 템플릿 헤더 + 릴리 자막을 입힌다.

    python tools/lilysub/run_b.py <볼케이노 작업폴더> --template 이븐쇼핑 [--plan 계획.json] [--channel 디씨썰극장]
                                  [--hook1 ..] [--hook2 ..] [--title ..] [--out x.mp4] [--skip-overlay] [--no-gate]

전제: 작업폴더에 video_raw.mp4 · audio_sfx.wav · timing.json (볼케이노 render_mix 까지 돌린 상태).
문구는 next_payload.json 의 title(h1·h2·card)에서 자동으로 읽고, 인자로 덮어쓸 수 있다.

흐름  ① video_raw 에서 사진 띠(위/아래 y) 실측 → 헤더 높이·자막 위치 계산
      ② 헤더 층 chrome.mov (template_render.header_layer, 훅 팝업 포함)
      ③ cuts.json (build_cuts) → Remotion SsulOverlay → overlay.mov
      ④ 게이트: 컷마다 자막이 띠 안(react/stamp 는 사진 위)에 있는지 실측 — 아니면 멈추고 컷 번호를 말한다
      ⑤ ffmpeg 합성 → out/<slug>_B.mp4
볼케이노처럼 "안 되면 멈추고 말한다". 되풀이하지 않는다.
"""
import os, sys, io, json, math, argparse, subprocess, shutil
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'even_header'))
import template_render as TR
import build_cuts

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MOTION = os.path.join(ROOT, 'shopping_shorts', 'motion')
FF = 'ffmpeg'
FPS = 30
W, H = 1080, 1920

def sh(cmd, cwd=None, timeout=1800):
    # ★윈도우 기본 cp949 로 npx 출력을 읽으면 UnicodeDecodeError 가 스레드에서 터진다 → utf-8 고정
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=timeout, shell=isinstance(cmd, str))
    if r.returncode != 0:
        raise SystemExit(f'[중단] 명령 실패 rc={r.returncode}: {cmd if isinstance(cmd,str) else " ".join(cmd)}\n{(r.stderr or r.stdout)[-800:]}')
    return r

def probe_duration(p):
    r = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',p],capture_output=True,text=True)
    return float(r.stdout.strip())

def frame_at(video, t, out):
    sh([FF,'-v','error','-y','-ss',f'{t:.3f}','-i',video,'-frames:v','1','-q:v','2',out])
    return Image.open(out).convert('RGB')

def measure_photo_band(video, total):
    """자막 없는 원본에서 사진 띠 위/아래 y — 릴리 핸드오프 방식(행 평균 밝기 > 12)."""
    tops, bots = [], []
    for frac in (0.3, 0.5, 0.7):
        im = frame_at(video, total*frac, os.path.join(os.path.dirname(video), '_band_probe.jpg'))
        rows = np.array(im.convert('L')).mean(axis=1)
        lit = np.where(rows > 12)[0]
        if len(lit): tops.append(int(lit[0])); bots.append(int(lit[-1]))
    if not tops: raise SystemExit('[중단] video_raw 에서 사진 띠를 못 찾았다 — 프레임이 전부 검정')
    return int(np.median(tops)), int(np.median(bots))

def auto_texts(work, a):
    texts = {}
    p = os.path.join(work, 'next_payload.json')
    if os.path.exists(p):
        title = json.load(io.open(p, encoding='utf-8')).get('title') or {}
        texts = dict(hook1=title.get('h1',''), hook2=title.get('h2',''), bodyTitle=title.get('card') or title.get('youtube',''))
    for k in ('hook1','hook2'):
        if getattr(a, k): texts[k] = getattr(a, k)
    if a.title: texts['bodyTitle'] = a.title
    texts['channel'] = a.channel
    missing = [k for k in ('hook1','hook2','bodyTitle') if not texts.get(k)]
    if missing: raise SystemExit(f'[중단] 헤더 문구가 비었다: {missing} — next_payload.json 의 title 이 없으면 --hook1/--hook2/--title 로 줘라')
    return texts

def build_chrome(work, tpl, texts, photo_top, hook_end, total):
    fr = os.path.join(work, 'chrome_frames'); shutil.rmtree(fr, ignore_errors=True); os.makedirs(fr)
    shots = []
    n_pop = int(math.ceil((TR.POP_MS + 2*TR.POP_STAGGER)/1000*FPS)) + 1
    for i in range(n_pop):
        fn = f'pop_{i:03d}.png'
        TR.header_layer(tpl, 'hook', texts, photo_top, pop_ms=i/FPS*1000).save(os.path.join(fr, fn)); shots.append((fn, 1/FPS))
    TR.header_layer(tpl, 'hook', texts, photo_top, pop_ms=TR.POP_MS+2*TR.POP_STAGGER+1).save(os.path.join(fr, 'hook_hold.png'))
    shots.append(('hook_hold.png', max(0.02, hook_end - n_pop/FPS)))
    TR.header_layer(tpl, 'body', texts, photo_top).save(os.path.join(fr, 'body.png'))
    shots.append(('body.png', total - hook_end))
    lst = os.path.join(fr, 'concat.txt')
    with io.open(lst, 'w', encoding='utf-8', newline='\n') as f:
        for fn, d in shots: f.write(f"file '{os.path.join(fr, fn).replace(os.sep,'/')}'\nduration {d:.4f}\n")
        f.write(f"file '{os.path.join(fr, shots[-1][0]).replace(os.sep,'/')}'\n")
    out = os.path.join(work, 'chrome.mov')
    sh([FF,'-v','error','-y','-f','concat','-safe','0','-i',lst,'-c:v','prores_ks','-profile:v','4444','-pix_fmt','yuva444p10le','-r',str(FPS),out])
    return out, sorted(set(TR.GAPS))

def build_overlay(work, plan, shift_y):
    cuts_path = build_cuts.build(work, plan)
    cuts = json.load(io.open(cuts_path, encoding='utf-8'))['cuts']
    props = os.path.join(MOTION, 'cuts.json')
    json.dump({'cuts': cuts, 'shiftY': shift_y}, io.open(props, 'w', encoding='utf-8'), ensure_ascii=False)
    out = os.path.join(work, 'overlay.mov')
    sh(f'npx remotion render src/index.ts SsulOverlay "{out}" --props=./cuts.json --codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png', cwd=MOTION, timeout=3600)
    return out, cuts

def gate_overlay(work, overlay, cuts, photo_top, photo_bot):
    """컷마다 자막 픽셀의 y 범위를 실측. 띠 밖이면 실패 목록을 돌려준다."""
    bad = []
    probe = os.path.join(work, '_ov_probe.png')
    for i, c in enumerate(cuts, 1):
        t = c['t'] + c['d']*0.6
        sh([FF,'-v','error','-y','-ss',f'{t:.3f}','-i',overlay,'-frames:v','1','-pix_fmt','rgba',probe])
        a = np.array(Image.open(probe).convert('RGBA'))[..., 3]
        rows = np.where(a.max(axis=1) > 30)[0]
        if not len(rows): bad.append((i, c['kind'], '픽셀 0 — 화면 밖이거나 안 그려짐')); continue
        y0, y1 = int(rows.min()), int(rows.max())
        on_photo = c['kind'] in ('react', 'stamp')
        ok = (photo_top <= y0 and y1 <= photo_bot) if on_photo else (y0 >= photo_bot - 4)
        if not ok: bad.append((i, c['kind'], f'y={y0}~{y1} (사진 {photo_top}~{photo_bot})'))
    return bad

def composite(work, chrome, overlay, total, out):
    sh([FF,'-y','-v','error','-i',os.path.join(work,'video_raw.mp4'),'-i',chrome,'-i',overlay,'-i',os.path.join(work,'audio_sfx.wav'),
        '-filter_complex','[0:v][1:v]overlay=0:0:format=auto[a];[a][2:v]overlay=0:0:format=auto,format=yuv420p[v]',
        '-map','[v]','-map','3:a','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p',
        '-color_range','tv','-colorspace','bt709','-c:a','aac','-b:a','192k','-t',f'{total:.3f}','-movflags','+faststart',out], timeout=1800)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('work'); ap.add_argument('--template', required=True); ap.add_argument('--plan')
    ap.add_argument('--channel', default='디씨썰극장'); ap.add_argument('--hook1'); ap.add_argument('--hook2'); ap.add_argument('--title')
    ap.add_argument('--out'); ap.add_argument('--skip-overlay', action='store_true'); ap.add_argument('--no-gate', action='store_true')
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    for f in ('video_raw.mp4', 'audio_sfx.wav', 'timing.json'):
        if not os.path.exists(os.path.join(work, f)): raise SystemExit(f'[중단] {f} 없음 — 볼케이노 render_mix 까지 돌린 폴더여야 한다')
    tm = json.load(io.open(os.path.join(work, 'timing.json'), encoding='utf-8'))
    total = float(tm['total']); groups = tm['groups']
    hook_end = float(groups[1]['t']) if len(groups) > 1 else total*0.1
    tpl = TR.by_name(a.template)
    texts = auto_texts(work, a)
    print(f'[문구] hook1={texts["hook1"]} | hook2={texts["hook2"]} | title={texts["bodyTitle"]} | channel={texts["channel"]}')

    top, bot = measure_photo_band(os.path.join(work, 'video_raw.mp4'), total)
    band_center = (bot + H)//2
    shift_y = band_center - 834          # SsulOverlay 실측: shiftY 753 ↔ 띠 중심 1587
    print(f'[실측] 사진 띠 y={top}~{bot} → 헤더 높이 {top}, 자막 중심 {band_center}, shiftY={shift_y}')

    chrome, gaps = build_chrome(work, tpl, texts, top, hook_end, total)
    print(f'[헤더] {a.template} chrome.mov OK' + (f' | 갭: {gaps}' if gaps else ''))

    overlay = os.path.join(work, 'overlay.mov')
    if a.skip_overlay and os.path.exists(overlay):
        cuts = json.load(io.open(os.path.join(work, 'cuts.json'), encoding='utf-8'))['cuts']; print('[자막] 기존 overlay.mov 재사용')
    else:
        overlay, cuts = build_overlay(work, a.plan, shift_y); print(f'[자막] overlay.mov OK ({len(cuts)}컷)')

    if not a.no_gate:
        bad = gate_overlay(work, overlay, cuts, top, bot)
        if bad:
            print('[중단] 자막 위치 게이트 실패 — 다음 컷을 고쳐라(되풀이하지 않는다):')
            for i, k, why in bad: print(f'   컷{i:2d} {k:7s} {why}')
            raise SystemExit(2)
        print(f'[게이트] {len(cuts)}컷 자막 위치 통과')

    slug = tm.get('slug') or 'video'
    out = a.out or os.path.join(work, 'out', f'{slug}_B_{a.template}.mp4')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    composite(work, chrome, overlay, total, out)
    dur = probe_duration(out)
    if abs(dur - total) > 0.15: raise SystemExit(f'[중단] 길이 불일치 {dur:.2f} vs timing {total:.2f}')
    print(f'[완료] {out} ({dur:.2f}s)')

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
