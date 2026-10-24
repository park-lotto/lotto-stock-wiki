"""라이브러리 없이 효과음 후보 사건을 신호 모양으로 찾는다 (로컬).
 broad : 5~10.5kHz 에너지가 ±0.75초 중앙값보다 >= BR_DB 솟고(0.05~0.7초), 그 사이 유성 f0 없음 -> '휙·틱·뽁·딸깍' 류 (치찰음 /s/ 와 구분 약함 — 길이로 보조)
 tonal : 1~6kHz 에서 한 주파수 봉우리가 0.2초 이상 유지, 주변 대비 >= TN_DB, 유성 f0 없음 -> '띵·띠링' 류
 python sfx_events.py <wav> -> json 줄 / 함수 detect(x) -> list
 python sfx_events.py <slug> [--detect] [--src 폴더] -> channel/<slug>/_kal/sfx_events.json (채널 신호표, 아래 channel())"""
import sys, os, json, glob
import numpy as np
from scipy.signal import stft, find_peaks
from scipy.ndimage import median_filter
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F, voice_fp as V
SR=F.SR; NF=1024; HOP=256; FPS=SR/HOP
BR_DB=18; TN_DB=22
def detect(x):
    f,t,Z=stft(x,SR,nperseg=NF,noverlap=NF-HOP,boundary=None,padded=False); P=np.abs(Z)**2+1e-12
    L=10*np.log10(P)
    # 유성 마스크 (f0 트랙 10ms -> 프레임 격자)
    f0,_=V.f0_track(x.astype(np.float32)); vt=np.arange(len(f0))*0.01+0.02
    voiced=np.interp(t,vt,(f0>0).astype(float))>0.5
    out=[]
    # broad
    m=(f>=5000)&(f<=10500); hf=10*np.log10(P[m].sum(0)); med=median_filter(hf,size=int(1.5*FPS)|1,mode='nearest'); ex=hf-med
    pk,_=find_peaks(ex,height=BR_DB,distance=int(0.15*FPS))
    for p in pk:
        a=p
        while a>0 and ex[a-1]>BR_DB*0.5: a-=1
        b=p
        while b<len(ex)-1 and ex[b+1]>BR_DB*0.5: b+=1
        dur=(b-a+1)/FPS
        if not (0.05<=dur<=0.7): continue
        vf=voiced[max(0,a-3):b+4].mean()
        w=int(0.12*FPS); iso=1.0-float(np.concatenate([voiced[max(0,a-w):a],voiced[b+1:b+1+w]]).mean()) if (a>0 or b<len(voiced)-1) else 1.0
        cen=float((f[m]*P[m][:,p]).sum()/P[m][:,p].sum())
        out.append({'t':round(float(t[a]),2),'kind':'broad','dur':round(dur,2),'db':round(float(ex[p]),1),'voiced':round(float(vf),2),'isolated':round(iso,2),'cen_hz':round(cen)})
    # tonal
    m2=(f>=1000)&(f<=6000); S=L[m2]; ff=f[m2]; k=S.argmax(0); prom=S.max(0)-np.median(S,axis=0)
    ok=(prom>=TN_DB)&(~voiced)
    i=0
    while i<len(ok):
        if ok[i]:
            j=i
            while j+1<len(ok) and ok[j+1] and abs(k[j+1]-k[j])<=3: j+=1
            dur=(j-i+1)/FPS
            if dur>=0.2: out.append({'t':round(float(t[i]),2),'kind':'tonal','dur':round(dur,2),'db':round(float(prom[i:j+1].max()),1),'cen_hz':round(float(ff[int(np.median(k[i:j+1]))]))}); 
            i=j+1
        else: i+=1
    out.sort(key=lambda e:e['t']); return out


# ── 채널 신호표(표준 §3-3 A2, 관제 263 지시서 03) ─────────────────────────────
# 채널마다 자기 파일 channel/<slug>/_kal/sfx_events.json (키 = 편 id). placement.count 가 bench.sfx_events 대신 이 파일을 먼저 읽는다.
#   python sfx_events.py <slug>              옛 공유 파일(LEGACY)에 그 채널 키가 있으면 1회 변환(값 그대로 · 키 접두만 뗌), 없으면 검출
#   python sfx_events.py <slug> --detect [--src <폴더>]   벤치 원본(<폴더>/<id>.mp4|wav, 기본 C:/숏템_칼카피/<slug>/src)에서 다시 잰다
# 표식(자막교체·스티커·화자 전환·컷)은 뜯기.json 이 있으면 그것(옛 sfx_rules 와 같은 출처), 없으면 줄판독. 우연 기대 = 임의 시각이 표식 ±TOL 안에 들 비율.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
LEGACY = os.path.join(ROOT, 'channel', 'starpickroom', '_tools', '결과', 'sfx_events_rules.json')
TOL = 0.15


def out_path(slug):
    return os.path.join(ROOT, 'channel', slug, '_kal', 'sfx_events.json')


def _reads(slug):
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'channel', slug, '줄판독', '*.json'))):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except Exception as e:          # 깨진 줄판독은 건너뛰되 알린다
            print('[sfx_events] 줄판독 읽기 실패', p, e, file=sys.stderr); continue
        out[d.get('id') or os.path.basename(p)[:-5]] = d
    return out


def markers(slug, vid, read=None):
    """표식 {cap, sticker, switch, cut} 초 목록 — 뜯기.json(captions.changes·cuts.times·overlay appearances) 우선, 없으면 줄판독."""
    m = {'cap': [], 'sticker': [], 'switch': [], 'cut': []}
    tg = glob.glob(os.path.join(ROOT, 'channel', slug, '뜯기', vid, '뜯기.json'))
    if tg:
        d = json.load(open(tg[0], encoding='utf-8'))
        m['cap'] = list((d.get('captions') or {}).get('changes') or [])
        m['cut'] = list((d.get('cuts') or {}).get('times') or [])
        m['sticker'] = [a['t'][0] for a in (d.get('overlay_rules') or {}).get('appearances', []) if a.get('t')]
    lines = (read or {}).get('lines') or []
    if lines and not tg:
        m['cap'] = [l['t0'] for l in lines if isinstance(l.get('t0'), (int, float))]
        for l in lines:
            for s in l.get('sticker') or []:
                if isinstance(s, dict) and isinstance(s.get('t_in'), (int, float)):
                    m['sticker'].append(s['t_in'])
            if isinstance(l.get('cut_at'), (int, float)):
                m['cut'].append(l['cut_at'])
        m['cut'] += [c if not isinstance(c, list) else c[0] for c in (read or {}).get('cuts_approx', []) if isinstance(c, (int, float, list))]
    prev = None
    for l in lines:                      # 나레↔원음 전환 = 화자 바뀐 줄 시작
        sp = 'narr' if str(l.get('speaker', '')).startswith('나레') else 'orig'
        if prev is not None and sp != prev and isinstance(l.get('t0'), (int, float)):
            m['switch'].append(l['t0'])
        prev = sp
    return {k: sorted(float(a) for a in v if isinstance(a, (int, float)) and a > 0.05) for k, v in m.items()}


def _near(t, arr):
    return min((abs(t - a) for a in arr), default=9)


def table_of(x, mk):
    """한 편 소리 x + 표식 → 옛 sfx_rules 와 같은 꼴 {strong_n, strong_hits, dur, n_events_all, cand[{…,near}], markers, chance}."""
    ev = detect(x)
    dur = len(x) / F.SR
    cand = [{**e, 'near': {k: round(_near(e['t'], v), 2) for k, v in mk.items() if v}} for e in ev if e['kind'] == 'tonal' or e.get('isolated', 0) >= 0.8]
    rng = np.random.default_rng(0); rt = rng.uniform(0, dur, 2000)
    chance = {k: round(float(np.mean([_near(t, v) <= TOL for t in rt])), 2) for k, v in mk.items() if v}
    strong = [e for e in ev if e['db'] >= 25]
    hits = {k: [round(e['t'], 2) for e in strong if _near(e['t'], v) <= TOL] for k, v in mk.items() if v}
    return {'strong_n': len(strong), 'strong_hits': hits, 'dur': round(dur, 1), 'n_events_all': len(ev), 'cand': cand,
            'markers': {k: [round(a, 2) for a in v] for k, v in mk.items()}, 'chance': chance}


def convert(slug):
    """옛 공유 파일의 <slug>/<id> 항목 → {id: 값}(값은 한 글자도 안 바꾼다 — placement.count 결과가 변환 전과 같아야 한다)."""
    if not os.path.exists(LEGACY):
        return {}
    d = json.load(open(LEGACY, encoding='utf-8'))
    return {k.split('/', 1)[1]: v for k, v in d.items() if k.startswith(slug + '/')}


def channel(slug, detect_mode=False, src=None):
    rows = {} if detect_mode else convert(slug)
    how = 'convert'
    if not rows:
        how = 'detect'
        src = src or os.path.join(os.environ.get('CALCOPY_PACK_ROOT_DATA') or 'C:/숏템_칼카피', slug, 'src')
        reads = _reads(slug)
        if not reads:
            raise SystemExit(f'줄판독이 없다: channel/{slug}/줄판독 — 편 목록을 모른다')
        miss = []
        for vid, rd in reads.items():
            f = next((p for p in (os.path.join(src, vid + e) for e in ('.wav', '.mp4', '.webm', '.mkv')) if os.path.exists(p)), None)
            if not f:
                miss.append(vid); continue
            rows[vid] = table_of(F.load(f), markers(slug, vid, rd))
            print(slug, vid, '후보', len(rows[vid]['cand']), [(c['t'], c['kind']) for c in rows[vid]['cand']], flush=True)
        if miss:
            print(f'[sfx_events] 원본 없음 {len(miss)}편(재지 않음): {miss} — 폴더 {src}', file=sys.stderr)
        if not rows:
            raise SystemExit(f'잴 원본이 하나도 없다: {src}')
    meta = {'made_by': 'tools/calcopy/engine/sound/sfx_events.py ' + slug + (' --detect' if detect_mode else ''), 'how': how,
            'from': os.path.relpath(LEGACY, ROOT).replace(os.sep, '/') if how == 'convert' else src, 'n_videos': len(rows),
            'n_cand': sum(len(v.get('cand') or []) for v in rows.values())}
    p = out_path(slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'_meta': meta, **rows}, fh, ensure_ascii=False, indent=1)
    print(json.dumps({'out': os.path.relpath(p, ROOT).replace(os.sep, '/'), **meta}, ensure_ascii=False))
    return p


if __name__=='__main__':
    a = sys.argv[1:]
    if a and (a[0].lower().endswith(('.wav', '.mp4', '.webm', '.m4a')) or os.path.isfile(a[0])):
        x=F.load(a[0]); print(json.dumps(detect(x),ensure_ascii=False))
    elif a:
        src = a[a.index('--src') + 1] if '--src' in a else None
        channel(a[0], detect_mode='--detect' in a, src=src)
    else:
        print(__doc__)
