"""라이브러리 없이 효과음 후보 사건을 신호 모양으로 찾는다 (로컬).
 broad : 5~10.5kHz 에너지가 ±0.75초 중앙값보다 >= BR_DB 솟고(0.05~0.7초), 그 사이 유성 f0 없음 -> '휙·틱·뽁·딸깍' 류 (치찰음 /s/ 와 구분 약함 — 길이로 보조)
 tonal : 1~6kHz 에서 한 주파수 봉우리가 0.2초 이상 유지, 주변 대비 >= TN_DB, 유성 f0 없음 -> '띵·띠링' 류
 low   : 100~400Hz 에너지가 ±0.75초 중앙값보다 >= LO_DB 솟고(<=1.2초), 그 편 저역 최대 −LO_REL dB 안(큰 소리), 400~4kHz 보다 >= LO_MID dB 저역 쏠림
         -> '쿵·붐' 저역 타격(10-25 신박 rAt 8.6·11.15·bpj 14.73 정답 — broad·tonal 은 5kHz 위·1kHz 위라 못 잡았다). 저역 붐은 f0 추적이 '유성'으로
         읽어(rAt 11.17 유성 0.58) 유성 조건을 느슨히(<= LO_VOICED 0.65) 하고 크기·쏠림으로 가른다. 말소리 안 후보는 아래 받아쓰기 거름이 뺀다.
 python sfx_events.py <wav> -> json 줄 / 함수 detect(x) -> list
 python sfx_events.py <slug> [--detect] [--src 폴더] [--asr 낱말폴더] -> channel/<slug>/_kal/sfx_events.json (채널 신호표, 아래 channel())"""
import sys, os, json, glob, re
import numpy as np
from scipy.signal import stft, find_peaks
from scipy.ndimage import median_filter
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F, voice_fp as V
SR=F.SR; NF=1024; HOP=256; FPS=SR/HOP
BR_DB=18; TN_DB=22
LO_DB=12; LO_REL=6; LO_MID=4.5; LO_MAX=1.2; LO_VOICED=0.65
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
    # low (쿵·붐)
    m3=(f>=100)&(f<=400); lf=10*np.log10(P[m3].sum(0)); lmed=median_filter(lf,size=int(1.5*FPS)|1,mode='nearest'); lex=lf-lmed
    mid=10*np.log10(P[(f>400)&(f<=4000)].sum(0)); top=float(lf.max())
    pk,_=find_peaks(lex,height=LO_DB,distance=int(0.15*FPS))
    for p in pk:
        if lf[p]<top-LO_REL or lf[p]-mid[p]<LO_MID: continue
        a=p
        while a>0 and lex[a-1]>lex[p]*0.5: a-=1
        b=p
        while b<len(lex)-1 and lex[b+1]>lex[p]*0.5: b+=1
        dur=(b-a+1)/FPS
        vf=float(voiced[max(0,a-3):b+4].mean())
        if dur>LO_MAX or vf>LO_VOICED: continue      # 말소리 저역(키치잇 나레 유성 0.73~1.0)은 뺀다 — 붐은 f0 가 붙어도 0.62 이하(신박 정답 0.0~0.62)
        out.append({'t':round(float(t[p]),2),'kind':'low','dur':round(dur,2),'db':round(float(lex[p]),1),'rel_db':round(float(lf[p]-top),1),'low_mid_db':round(float(lf[p]-mid[p]),1),'voiced':round(vf,2)})
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


TONE_DEDUP = 0.15


def tone_profile(slug):
    """readline_tools/tone 문턱 — 채널 프로필(profiles/<slug>.json 의 tone)을 잰 채널만(None = 이 채널은 순음 검출을 안 쓴다).
    10-25 실측: 프로필 없는 채널에 기본값을 쓰면 말소리·배경음 선율이 순음으로 쏟아진다(샤크탱크 161·키치잇 36·굿레터 32 — 이븐쇼핑 20발 중 정답 16)."""
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'calcopy', 'engine', 'readline_tools'))
    import tone as TN
    pf = os.path.join(ROOT, 'tools', 'calcopy', 'engine', 'readline_tools', 'profiles', f'{slug}.json')
    prof = (json.load(open(pf, encoding='utf-8')).get('tone') if slug and os.path.exists(pf) else None)
    if not prof:
        return TN, None
    return TN, {**TN.DEFAULTS, **prof}


def tone_cands(path, slug, ev=()):
    """말 위 순음 → kind 'tone' 후보(같은 자리 tonal 이 이미 있으면 뺀다). 판단 주인 = readline_tools/tone.tone_events(두 벌 금지 — 부르기만)."""
    TN, P = tone_profile(slug)
    if P is None:
        return []
    out = []
    for e in TN.tone_events(path, P['lo'], P['hi'], P['prom'], P['min_dur'], P['merge']):
        if any(o['kind'] == 'tonal' and abs(o['t'] - e['t']) <= TONE_DEDUP for o in ev):
            continue
        out.append({'t': e['t'], 'kind': 'tone', 'dur': e['dur'], 'db': e['prom_db'], 'hz': e['hz']})
    return out


BEAT_TOL = 0.03           # ㉞①: BGM 박자 주기와 ±30ms
BEAT_RUN = 3              # 3연속(간격 둘)이 박자 배수면 배경음 박자


def mark_bgm_beats(cand, x):
    """(판단 주인 ㉞①) 신호 솟음이 BGM 박자(bgm_fp.tempo)와 주기 일치(±30ms·3연속)면 kind_class 'bgm_beat' = 효과음 아님.
    간격이 박자 주기 T 의 정수배(1~4)에서 ±30ms 안이면 '박자 간격' — 그런 간격이 이어진 3개 이상 묶음을 표시."""
    import bgm_fp as B
    if len(cand) < BEAT_RUN:
        return None
    tp = B.tempo(x)
    lo, al = float(tp.get('low') or 0), float(tp.get('all') or 0)
    if lo and al and abs(max(lo, al) / min(lo, al) - 2) <= 0.06:      # 두 대역이 옥타브(2배) 관계면 빠른 쪽 — 느린 쪽 배수는 빠른 쪽 배수에 들어간다(신박 edT 저역 139.7·전대역 69.8)
        bpm = max(lo, al)
    else:
        bpm = tp.get('low') if tp.get('low_ac', 0) >= tp.get('all_ac', 0) else tp.get('all')
    if not bpm:
        return None
    T = 60.0 / bpm
    ts = sorted(range(len(cand)), key=lambda i: cand[i]['t'])

    def on_beat(d):
        m = round(d / T)
        return 1 <= m <= 4 and abs(d - m * T) <= BEAT_TOL
    run = [ts[0]]
    for a, b in zip(ts, ts[1:]):
        if on_beat(cand[b]['t'] - cand[a]['t']):
            run.append(b)
        else:
            if len(run) >= BEAT_RUN:
                for i in run:
                    cand[i]['kind_class'] = 'bgm_beat'; cand[i]['beat'] = {'bpm': bpm, 'T': round(T, 3)}
            run = [b]
    if len(run) >= BEAT_RUN:
        for i in run:
            cand[i]['kind_class'] = 'bgm_beat'; cand[i]['beat'] = {'bpm': bpm, 'T': round(T, 3)}
    return bpm


def table_of(x, mk, path=None, slug=None):
    """한 편 소리 x + 표식 → 옛 sfx_rules 와 같은 꼴 {strong_n, strong_hits, dur, n_events_all, cand[{…,near}], markers, chance}.
    path(원본 파일)를 주면 말 위 순음(tone — 주인 readline_tools/tone.tone_events, 채널 문턱 profiles/<slug>.json)을 더한다:
    detect 의 tonal 은 유성(말) 구간을 빼서 말과 겹친 띵을 0발로 냈다(이븐쇼핑 줄판독 띵 17발 중 0)."""
    ev = detect(x)
    if path:
        ev = sorted(ev + tone_cands(path, slug, ev), key=lambda e: e['t'])
    dur = len(x) / F.SR
    cand = [{**e, 'near': {k: round(_near(e['t'], v), 2) for k, v in mk.items() if v}} for e in ev if e['kind'] in ('tonal', 'low', 'tone') or e.get('isolated', 0) >= 0.8]
    mark_bgm_beats(cand, x)
    rng = np.random.default_rng(0); rt = rng.uniform(0, dur, 2000)
    chance = {k: round(float(np.mean([_near(t, v) <= TOL for t in rt])), 2) for k, v in mk.items() if v}
    strong = [e for e in ev if e['db'] >= 25]
    hits = {k: [round(e['t'], 2) for e in strong if _near(e['t'], v) <= TOL] for k, v in mk.items() if v}
    return {'strong_n': len(strong), 'strong_hits': hits, 'dur': round(dur, 1), 'n_events_all': len(ev), 'cand': cand,
            'markers': {k: [round(a, 2) for a in v] for k, v in mk.items()}, 'chance': chance}


# ── 받아쓰기 낱말 거름(10-25 06 워커 붙임 스크립트를 도구 안으로) ─────────────────────
# 후보 시각이 받아쓰기 낱말 구간 [t0−PAD, t1+PAD] 안이면 cand_in_words(치찰음·파열음 오탐), 나머지 cand_kept.
# 예외: 화면 전환(cut)·스티커 등장 ±KEEP_NEAR 초 안 후보는 낱말 안이어도 남긴다(샤크탱크 QMJ 7.26·7.36 '띠링' = 번쩍 7.067 직후인데 지워졌다).
# 무음 환각 받아쓰기(위스퍼가 말 없는 영상에 'Thanks for watching'·'구독과 좋아요' 를 지어냄)는 낱말 0 으로 본다(신박 5편).
ASR_PAD = 0.05
KEEP_NEAR = 0.3
HALLU = re.compile(r"thanks?\s*(you\s*)?for\s*watching|please\s*subscribe|subscribe|like\s*button|구독\s*(과|하고|와)?\s*좋아요|시청\s*해\s*주셔서|시청해주셔서|"
                   r"^\W*music\W*$|♪|자막\s*(제공|by)|mbc\s*뉴스", re.I)
ZERO_LEN = 0.02          # 길이 0 낱말(끝=시작) — 환각 받아쓰기에 몰린다(신박 rAt 8/11·bpj 36/65)
ZERO_FRAC = 0.4


def asr_dirs(slug):
    base = os.path.join(os.environ.get('CALCOPY_PACK_ROOT_DATA') or 'C:/숏템_칼카피', slug, 'work')
    return [os.path.join(base, d) for d in ('asrw_auto', 'asrw')]


def asr_words(path):
    """낱말 [{w,t0,t1,p}] → (쓸 낱말, 판정). 환각 문구에 걸린 낱말은 빼고, 그게 절반 이상이거나 남은 게 2개 이하, 또는 길이 0 낱말이 ZERO_FRAC 이상이면 편 전체 무음(0)."""
    if not path or not os.path.exists(path):
        return None, 'no_asr'
    d = json.load(open(path, encoding='utf-8'))
    raw = (d.get('words') if isinstance(d, dict) else d) or []
    raw = [{'t0': w[0], 't1': w[1], 'w': w[2]} if isinstance(w, (list, tuple)) and len(w) >= 3 else w for w in raw]   # 유튜브 자동자막 낱말 꼴 [t0,t1,낱말](만템 vttw)
    ws = [w for w in raw if isinstance(w, dict) and 't0' in w and 't1' in w]
    if not ws:
        return [], 'empty'
    text = ''; spans = []
    for w in ws:
        a = len(text); text += str(w.get('w', '')).strip() + ' '; spans.append((a, len(text) - 1))
    hit = [False] * len(ws)
    for m in HALLU.finditer(text):
        for i, (a, b) in enumerate(spans):
            if a < m.end() and b > m.start():
                hit[i] = True
    for i, w in enumerate(ws):           # 한 낱말짜리 'Music' 같은 것
        if HALLU.search(str(w.get('w', '')).strip()):
            hit[i] = True
    zero = sum(1 for w in ws if float(w['t1']) - float(w['t0']) < ZERO_LEN) / len(ws)
    left = [w for w, h in zip(ws, hit) if not h]
    if sum(hit) and (len(left) <= 2 or sum(hit) >= len(ws) / 2):      # 환각 문구가 절반 넘거나 남는 게 거의 없으면 편 전체가 환각
        return [], f'hallucination(문구 {sum(hit)}/{len(ws)})'
    if zero >= ZERO_FRAC:
        return [], f'hallucination(길이0 낱말 {zero:.0%})'
    return [w for w in left if float(w['t1']) > float(w['t0'])], ('ok' if not sum(hit) else f'ok(환각 문구 {sum(hit)}낱말 뺌)')


KEEP_WINDOWS = (0.3, 0.2, 0.15, 0.1, 0.05)
KEEP_CHANCE = 0.1         # 예외 창 안에 임의 시각이 들 확률(우연 기대)이 이 아래일 때만 '전환·스티커 곁' 예외가 뜻이 있다


def keep_window(row):
    """(판단 주인 ② 10-25) 전환·스티커 곁 예외 창 = 그 편 표식 밀도로 우연 기대를 재서 KEEP_CHANCE 아래인 가장 넓은 창.
    방구석처럼 컷이 촘촘하면(±0.3초 우연 0.25~0.3) 창을 줄이고, 0.05초로도 우연이 크면 예외 없음(0)."""
    mk = row.get('markers') or {}
    pts = sorted(float(a) for k in ('cut', 'sticker') for a in mk.get(k) or [])
    dur = float(row.get('dur') or (max(pts) + 1 if pts else 0))
    if not pts or dur <= 0:
        return 0.0, 0.0
    grid = np.arange(0, dur, 0.01)
    P = np.array(pts)
    dist = np.min(np.abs(grid[:, None] - P[None, :]), axis=1)
    for w in KEEP_WINDOWS:
        ch = float(np.mean(dist <= w))
        if ch <= KEEP_CHANCE:
            return w, round(ch, 3)
    return 0.0, round(float(np.mean(dist <= KEEP_WINDOWS[-1])), 3)


READ_TOL = 0.15


def read_sfx_times(read):
    """줄판독(눈) sfx 시각 — 벤치가 얹은 소리만(sfx_key 가 None 인 '원본 동작음' 류는 뺀다). t 가 없으면 그 줄 t0."""
    out = []
    for l in (read or {}).get('lines') or []:
        s = l.get('sfx')
        if not s:
            continue
        kind = s.get('kind') if isinstance(s, dict) else s
        if re.search(r'원본|원음', str(kind)):
            continue
        t = s.get('t') if isinstance(s, dict) else None
        t = t if isinstance(t, (int, float)) else l.get('t0')
        if isinstance(t, (int, float)):
            out.append(float(t))
    return out


def asr_filter(row, words, read=None):
    """신호표 한 편에 cand_kept·cand_in_words·asr_words(+ cand_bgm·confidence·ear_pending)를 붙인다.
    거름: 받아쓰기 낱말 안 = cand_in_words — 단 (a) 전환·스티커 곁(keep_window, 우연 유의할 때만) (b) 말 위 순음 tone (c) 판독(눈) sfx 자리(㉞② 판독 우선)는 남긴다.
    배경음 박자(kind_class bgm_beat, ㉞①) = cand_bgm(효과음 아님). 남은 후보: 판독 sfx ±0.15초 = confidence '눈', 아니면 '신호' + ear_pending(㉞③)."""
    w_keep, ch = keep_window(row)
    mk = row.get('markers') or {}
    near_pts = [float(a) for k in ('cut', 'sticker') for a in mk.get(k) or []]
    eye = read_sfx_times(read)
    kept, inw, bgm = [], [], []
    for c in row.get('cand') or []:
        by_eye = any(abs(c['t'] - e) <= READ_TOL for e in eye)
        if c.get('kind_class') == 'bgm_beat':
            if not by_eye:
                bgm.append(c); continue
            c = {**c, 'keep_why': '배경음 박자 위지만 판독(눈) sfx 자리 — 귀 확인(㉞②)'}      # 판독 우선: 숨기지 않고 대기로
        c = {k: v for k, v in c.items() if k not in ('word', 'confidence', 'ear_pending') and not (k == 'keep_why' and not str(v).startswith('배경음'))}
        hit = next((w for w in words if float(w['t0']) - ASR_PAD <= c['t'] <= float(w['t1']) + ASR_PAD), None)
        if hit and not c.get('keep_why'):
            nb = min((abs(c['t'] - a) for a in near_pts), default=9)
            if by_eye:
                c.update(word=hit.get('w'), keep_why='낱말 안이지만 판독(눈) sfx 자리 — 판독 우선(㉞②)')
            elif c['kind'] == 'tone':
                c.update(word=hit.get('w'), keep_why='낱말 안이지만 말 위 순음(tone)')
            elif w_keep and nb <= w_keep:
                c.update(word=hit.get('w'), keep_why=f'낱말 안이지만 전환·스티커 {nb:.2f}초 안(창 ±{w_keep} · 우연 {ch})')
            else:
                inw.append({**c, 'word': hit.get('w')}); continue
        c['confidence'] = '눈' if by_eye else '신호'
        if not by_eye or c.get('keep_why', '').startswith(('낱말 안이지만 판독', '배경음 박자')):
            c['ear_pending'] = True
        kept.append(c)
    row['asr_words'] = len(words); row['cand_in_words'] = inw; row['cand_kept'] = kept; row['cand_bgm'] = bgm
    row['keep_window'] = {'w': w_keep, 'chance': ch}
    row['sfx_count'] = {'sure': sum(1 for c in kept if not c.get('ear_pending')), 'pending': sum(1 for c in kept if c.get('ear_pending'))}
    return row


def meta_asr_dir(meta):
    """저장된 신호표 _meta.asr_filter.asr 글에서 위스퍼 낱말 폴더(…/<id>.json)를 꺼낸다. 다른 꼴(유튜브 vtt·스피치매틱스)이면 None."""
    a = (meta or {}).get('asr_filter')
    raw = str(a.get('asr') if isinstance(a, dict) else a or '').strip()
    if raw and os.path.isdir(raw):          # 이 도구가 쓴 꼴 = 폴더 경로만(10-25 06: 자기가 쓴 걸 못 읽어 다시 잴 때 거름이 빠졌다)
        return raw
    m = re.search(r"([A-Za-z]:[/\\][^\s]+?)[/\\]<id>\.json",str(a.get('asr') if isinstance(a, dict) else a or ''))
    return m.group(1) if m and os.path.isdir(m.group(1)) else None


def filter_channel(rows, slug, asr_dir=None):
    """편마다 받아쓰기 파일을 찾아 거른다. 반환 _meta.asr_filter. 받아쓰기 없는 편은 거르지 않고(cand_kept = cand) 목록에 적는다."""
    dirs = [asr_dir] if asr_dir else asr_dirs(slug)
    reads = _reads(slug)
    no_speech, no_asr, nk, ni, used = {}, [], 0, 0, None
    for vid, row in rows.items():
        if vid == '_meta' or not isinstance(row, dict):
            continue
        f = next((os.path.join(d, vid + '.json') for d in dirs if d and os.path.exists(os.path.join(d, vid + '.json'))), None)
        words, why = asr_words(f)
        if words is None:
            no_asr.append(vid); asr_filter(row, [], reads.get(vid)); row['asr_words'] = None
            continue
        used = used or os.path.dirname(f)
        if why.startswith('hallucination'):
            no_speech[vid] = why
        asr_filter(row, words, reads.get(vid))
        nk += len(row['cand_kept']); ni += len(row['cand_in_words'])
    return {'how': f'후보 시각이 받아쓰기 낱말 구간[t0−{ASR_PAD}, t1+{ASR_PAD}] 안이면 cand_in_words(치찰음·파열음 오탐) — 단 전환·스티커 곁(편마다 우연 기대 ≤ {KEEP_CHANCE} 인 창 {KEEP_WINDOWS})·말 위 순음 tone·판독 sfx 자리는 남김(keep_why). 배경음 박자 = cand_bgm. 남은 것 = cand_kept(confidence 눈/신호, ear_pending)',
            'asr': (used or '').replace(os.sep, '/') or None, 'no_speech': no_speech, 'no_asr': no_asr, 'n_kept': nk, 'n_in_words': ni,
            'note': '귀 확인 아님(신호). 무음 환각 = 환각 문구(Thanks for watching·구독과 좋아요·Music…)가 절반 이상이거나 빼고 2낱말 이하, 또는 길이0 낱말 40% 이상'}


def convert(slug):
    """옛 공유 파일의 <slug>/<id> 항목 → {id: 값}(값은 한 글자도 안 바꾼다 — placement.count 결과가 변환 전과 같아야 한다)."""
    if not os.path.exists(LEGACY):
        return {}
    d = json.load(open(LEGACY, encoding='utf-8'))
    return {k.split('/', 1)[1]: v for k, v in d.items() if k.startswith(slug + '/')}


def channel(slug, detect_mode=False, src=None, asr_dir=None):
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
            rows[vid] = table_of(F.load(f), markers(slug, vid, rd), f, slug)
            print(slug, vid, '후보', len(rows[vid]['cand']), [(c['t'], c['kind']) for c in rows[vid]['cand']], flush=True)
        if miss:
            print(f'[sfx_events] 원본 없음 {len(miss)}편(재지 않음): {miss} — 폴더 {src}', file=sys.stderr)
        if not rows:
            raise SystemExit(f'잴 원본이 하나도 없다: {src}')
    if how == 'detect' and not asr_dir and os.path.exists(out_path(slug)):     # 다시 잴 때는 저장본이 쓰던 낱말 폴더를 그대로
        asr_dir = meta_asr_dir(json.load(open(out_path(slug), encoding='utf-8')).get('_meta'))
    asr = filter_channel(rows, slug, asr_dir) if how == 'detect' else None     # 변환(옛 값 그대로)은 거르지 않는다
    meta = {'made_by': 'tools/calcopy/engine/sound/sfx_events.py ' + slug + (' --detect' if detect_mode else ''), 'how': how, 'asr_filter': asr,
            'from': os.path.relpath(LEGACY, ROOT).replace(os.sep, '/') if how == 'convert' else src, 'n_videos': len(rows),
            'n_cand': sum(len(v.get('cand') or []) for v in rows.values())}
    p = out_path(slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'_meta': meta, **rows}, fh, ensure_ascii=False, indent=1)
    print(json.dumps({'out': os.path.relpath(p, ROOT).replace(os.sep, '/'), **meta}, ensure_ascii=False))
    return p


def regress(slug, src=None, asr_dir=None):
    """(점검 — 쓰지 않음) 지금 코드로 다시 잰 후보·거름 ↔ 저장된 channel/<slug>/_kal/sfx_events.json. 편마다 더해진/빠진 후보와 까닭.
    python sfx_events.py <slug> --regress [--src 폴더] [--asr 낱말폴더]"""
    old = json.load(open(out_path(slug), encoding='utf-8'))
    src = src or os.path.join(os.environ.get('CALCOPY_PACK_ROOT_DATA') or 'C:/숏템_칼카피', slug, 'src')
    reads = _reads(slug); rows = {}
    for vid in [k for k in old if k != '_meta']:
        f = next((p for p in (os.path.join(src, vid + e) for e in ('.wav', '.mp4', '.webm', '.mkv')) if os.path.exists(p)), None)
        if f:
            rows[vid] = table_of(F.load(f), markers(slug, vid, reads.get(vid)), f, slug)
    old_filter = isinstance((old.get('_meta') or {}).get('asr_filter'), (dict, str))
    asr_dir = asr_dir or meta_asr_dir(old.get('_meta'))
    meta = filter_channel(rows, slug, asr_dir)
    same_source = not old_filter or bool(asr_dir) or bool(meta.get('asr'))
    key = lambda c: (round(c['t'], 2), c['kind'])
    rep = {'slug': slug, 'old_how': (old.get('_meta') or {}).get('how'), 'missing_src': [k for k in old if k != '_meta' and k not in rows], 'videos': {}}
    for vid, new in rows.items():
        o = old[vid]
        oc, nc = {key(c) for c in o.get('cand') or []}, {key(c) for c in new.get('cand') or []}
        has_old_filter = 'cand_kept' in o
        if has_old_filter and not same_source:     # 옛 거름이 다른 받아쓰기(vtt·스피치매틱스)라 이 도구로 재현 못 함 — 거름은 옛 것 + 새 후보만 비교
            new['cand_kept'] = [c for c in o['cand_kept']] + [c for c in new['cand'] if key(c) not in oc]
        ok_, nk = ({key(c) for c in o.get('cand_kept') or []} if has_old_filter else oc), {key(c) for c in new['cand_kept']}
        d = {'cand_added': sorted(nc - oc), 'cand_removed': sorted(oc - nc), 'kept_added': sorted(nk - ok_), 'kept_removed': sorted(ok_ - nk)}
        why = []
        for t, k in d['kept_added']:
            c = next(c for c in new['cand_kept'] if key(c) == (t, k))
            why.append(f"{t} {k}: " + ('새 저역(low) 후보' if k == 'low' and (t, k) not in oc else c.get('keep_why') or ('받아쓰기 무음 환각 → 낱말 0' if new.get('asr_words') == 0 and o.get('asr_words') else '거름 없던 편(옛 파일에 cand_kept 없음)' if not has_old_filter else '낱말 밖')))
        for t, k in d['kept_removed']:
            c = next((c for c in new['cand_in_words'] if key(c) == (t, k)), None)
            why.append(f"{t} {k}: " + (f"낱말 '{c.get('word')}' 안" if c else '후보에서 빠짐'))
        if any(d.values()):
            rep['videos'][vid] = {**d, 'why': why, 'asr_words': [o.get('asr_words'), new.get('asr_words')]}
    rep['asr'] = {**meta, 'old_filter_reproduced': same_source}
    return rep


if __name__=='__main__':
    a = sys.argv[1:]
    if a and (a[0].lower().endswith(('.wav', '.mp4', '.webm', '.m4a')) or os.path.isfile(a[0])):
        x=F.load(a[0]); print(json.dumps(detect(x),ensure_ascii=False))
    elif a and '--regress' in a:
        print(json.dumps(regress(a[0], a[a.index('--src') + 1] if '--src' in a else None, a[a.index('--asr') + 1] if '--asr' in a else None), ensure_ascii=False, indent=1))
    elif a:
        src = a[a.index('--src') + 1] if '--src' in a else None
        channel(a[0], detect_mode='--detect' in a, src=src, asr_dir=a[a.index('--asr') + 1] if '--asr' in a else None)
    else:
        print(__doc__)
