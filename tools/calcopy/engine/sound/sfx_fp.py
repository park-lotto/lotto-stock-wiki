"""벤치 영상 소리에서 우리 효과음을 찾는 스펙트럼 지문 대조 (제미나이·외부 전송 없음, 로컬 numpy/scipy).
사용: python sfx_fp.py <wav폴더> <출력json> [--inject]   (wav = 22.05kHz mono)
방법: 로그멜(48밴드 0.8~10.5kHz, hop 11.6ms) -> 벤치는 밴드별 ±0.5초 중앙값을 뺀 '초과 에너지', 효과음은 자기 바닥을 뺀 초과 에너지
     -> 효과음 길이(최대 0.9초) 창을 슬라이딩하며 코사인 유사도. 같은 파일(md5) 중복은 한 번만.
--inject: 양성 대조 — 벤치 음성에 효과음을 알려진 자리에 -12dB 로 섞어 되찾는지 잰다."""
import sys, os, glob, json, hashlib, subprocess
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
from scipy.ndimage import median_filter
SR = 22050; NF = 1024; HOP = 256
def melbank(n=48, lo=800., hi=10500.):
    f = np.fft.rfftfreq(NF, 1/SR)
    mel = lambda x: 2595*np.log10(1+x/700); inv = lambda m: 700*(10**(m/2595)-1)
    pts = inv(np.linspace(mel(lo), mel(hi), n+2)); B = np.zeros((n, len(f)))
    for i in range(n):
        a, b, c = pts[i], pts[i+1], pts[i+2]
        B[i] = np.clip(np.minimum((f-a)/(b-a), (c-f)/(c-b)), 0, None)
    return B
B = melbank()
def load(path):
    if path.lower().endswith('.wav'):
        try:
            sr, x = wavfile.read(path)
            x = x.astype(np.float32); x = x/ (np.abs(x).max() if x.dtype!=np.float32 or np.abs(x).max()>1 else 1)
            if x.ndim > 1: x = x.mean(1)
            if sr != SR:
                raise ValueError
            return x
        except Exception: pass
    out = subprocess.run(['ffmpeg','-v','error','-i',path,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True).stdout
    return np.frombuffer(out, np.float32)
def logmel(x):
    if len(x) < NF*2: x = np.pad(x, (0, NF*2-len(x)))
    _,_,Z = stft(x, SR, nperseg=NF, noverlap=NF-HOP, boundary=None, padded=False)
    P = (np.abs(Z)**2); M = B@P
    return 10*np.log10(M+1e-10)   # (48, T)
def bench_feat(x):
    L = logmel(x); w = int(0.5*SR/HOP)*2+1
    med = median_filter(L, size=(1, w), mode='nearest')
    return np.clip(L-med, 0, None), L
def tmpl_feat(x, maxlen=0.9):
    x = x/ (np.abs(x).max()+1e-9)
    L = logmel(x); e = L.max(0); thr = e.max()-35
    idx = np.where(e > thr)[0]
    if len(idx)==0: return None
    a = idx[0]; b = min(idx[-1]+1, a+int(maxlen*SR/HOP))
    L = L[:, a:b]
    F = np.clip(L - np.percentile(L, 10, axis=1, keepdims=True), 0, None)
    return F
def library():
    roots = [('sfx_packs','shopping_shorts/assets/sfx_packs/*/*.wav'),
             ('remotion_sfx','remotion-stock/public/sfx/*'),
             ('meme_sfx','research/sfx_census/meme_sfx/*/*')]
    lib, seen = {}, {}
    for tag, pat in roots:
        for p in sorted(glob.glob(pat)):
            if not p.lower().endswith(('.wav','.mp3')): continue
            h = hashlib.md5(open(p,'rb').read()).hexdigest()
            if h in seen: lib[seen[h]]['also'].append(p.replace(os.sep,'/')); continue
            seen[h] = tag+':'+p.replace(os.sep,'/'); lib[seen[h]] = {'path':p,'also':[]}
    return lib
def match(Bf, T):
    n = T.shape[1]; t = T.flatten(); t = t - t.mean(); tn = np.linalg.norm(t)+1e-9
    T_ = Bf.shape[1]
    if T_ < n: return np.zeros(0)
    from numpy.lib.stride_tricks import sliding_window_view
    W = sliding_window_view(Bf, n, axis=1)            # (48, T-n+1, n)
    W = W.transpose(1,0,2).reshape(W.shape[1], -1)
    W = W - W.mean(1, keepdims=True)
    num = W@t; den = np.linalg.norm(W,axis=1)+1e-9
    return num/(den*tn)
def run(wavdir, out, inject=False):
    lib = library(); T = {}
    for k,v in lib.items():
        x = load(v['path']); f = tmpl_feat(x)
        if f is not None and f.shape[1] >= 4: T[k] = (f, x)
    print('라이브러리 고유', len(T), '/', len(lib), flush=True)
    res = {}
    rng = np.random.default_rng(0)
    for w in sorted(glob.glob(os.path.join(wavdir,'*.wav'))):
        name = os.path.basename(w)[:-4]; x = load(w); planted = []
        if inject:
            ks = list(T); 
            for t0 in (3.0, 7.0, 11.0):
                k = ks[rng.integers(len(ks))]; s = T[k][1]; s = s/(np.abs(s).max()+1e-9)*0.25*np.abs(x).max()
                i = int(t0*SR)
                if i+len(s) < len(x): x[i:i+len(s)] += s
                planted.append((t0,k))
        Bf, _ = bench_feat(x); hits = []
        for k,(f,_x) in T.items():
            c = match(Bf, f)
            if len(c)==0: continue
            # 국소 최대 + 문턱
            for i in np.where((c>0.5)&(c==np.maximum.reduce([np.roll(c,s) for s in range(-8,9)])))[0]:
                seg = Bf[:, i:i+f.shape[1]]
                hits.append({'t': round(float(i*HOP/SR),2), 'file': k, 'cos': round(float(c[i]),3), 'excess_db': round(float(seg.max()),1)})
        hits.sort(key=lambda h:-h['cos'])
        res[name] = {'hits': hits[:40], 'planted': planted, 'dur': round(len(x)/SR,2)}
        print(name, len(hits), '상위:', [(h['t'],h['file'].split('/')[-1],h['cos']) for h in hits[:4]], 'planted', [(a,b.split('/')[-1]) for a,b in planted], flush=True)
    json.dump({'lib_also': {k:v['also'] for k,v in lib.items()}, 'res':res}, open(out,'w',encoding='utf-8'), ensure_ascii=False, indent=1)
if __name__=='__main__':
    run(sys.argv[1], sys.argv[2], '--inject' in sys.argv)
