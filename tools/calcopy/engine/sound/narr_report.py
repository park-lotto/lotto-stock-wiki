"""나레 판정 + 닮은 우리 목소리. python narr_report.py <wav폴더> <출력json>
wav 이름 = <slug>__<영상id>.wav. 나레·원음 구간 = **그 채널 줄판독** `channel/<slug>/줄판독/*.json`(화자 '나레'·'원음/연예인/본인') — 어느 채널이든(10-20 범용화, kal.py 소리 단계).
줄판독이 없는 옛 두 채널만 아래 NARR 표(손으로 적은 구간)를 쓴다."""
import sys, os, json, glob, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import voice_fp as V
SR=V.SR
def load(path):
    o=subprocess.run(['ffmpeg','-v','error','-i',path,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True).stdout
    return np.frombuffer(o,np.float32)
NARR={
 'kitchit':{'Cs-Ka_S8nDM':[(0,1.6),(6.8,8.0),(11.2,12.6)],'BRa5Iv4A3Y8':[(0,3.2),(18.5,20.9)],'Ks5kYYKAUlQ':[(0,2.2),(4.3,5.8)],
   'Nv99RyxmrfU':[(0,1.4),(8.3,10.0)],'oTi41R74WIY':[(0,10.1)],'cNo91ddBwB8':[(0,1.3),(3.4,5.1)],'vSEaZ-BCELY':[(2.1,6.0),(10.1,12.8)],'_Wa4IehA6yE':[(0,1.3),(5.7,6.8)]},
 'kkultemnote':{'2wJTffElmjk':[(2.4,4.9),(14.4,15.6)],'653bTRm8p6E':[(1.4,5.1),(6.8,13.1)],'BpUOIUwkoG4':[(1.8,4.2),(5.5,6.6),(8.8,10.0),(11.6,12.9),(14.6,15.2)],
   'KCxJ5qJft38':[(1.0,4.0),(9.6,12.3),(13.5,15.8)],'_dzncUms1yQ':[(0,4.9),(11.4,15.4)],'cLk6fJly6OY':[(1.0,2.8),(9.7,10.9),(11.9,13.5)],
   'm0Ex0y1DN5s':[(1.8,4.5),(17.3,18.5)],'znHaConczpE':[(2.3,6.1),(7.5,9.3),(15.3,16.4)]}}
def line_segs(slug):
    """채널 줄판독 → {'narr':{vid:[(a,b)]}, 'orig':{…}}. 없으면 빈 것."""
    out={'narr':{}, 'orig':{}}
    for p in glob.glob(f'channel/{slug}/줄판독/*.json'):
        d=json.load(open(p,encoding='utf-8')); i=d['id']
        for l in d['lines']:
            sp=l.get('speaker') or ''
            if sp.startswith('\ub098\ub808'): out['narr'].setdefault(i,[]).append((l['t0'],l['t1']))
            elif sp.startswith('\uc6d0\uc74c') or sp.startswith('\uc5f0\uc608\uc778') or sp.startswith('\ubcf8\uc778'):
                out['orig'].setdefault(i,[]).append((l['t0'],l['t1']))
    return out
def cat(x,segs):
    return np.concatenate([x[int(a*SR):int(b*SR)] for a,b in segs if b-a>=0.5]) if segs else np.zeros(0)
def vec(d):
    m=np.array(d['mfcc'][1:13]) ; return m
def main(wavdir,out):
    samples=json.load(open('shopping_shorts/assets/voice_presets.json',encoding='utf-8'))
    lib={}
    for s in samples:
        p='shopping_shorts/assets/voice_samples/'+s['sample_file']
        if not os.path.exists(p): continue
        d=V.feats(load(p)); 
        if 'mfcc' in d: lib[s['preset_id']]={'f':d,'group':s['group_id']}
    ids=list(lib); M=np.array([vec(lib[i]['f']) for i in ids]); mu=M.mean(0); sd=M.std(0)+1e-6
    def rank(d,k=5):
        z=(vec(d)-mu)/sd; Z=(M-mu)/sd; dist=np.linalg.norm(Z-z,axis=1)
        st=12*np.log2(d['f0_med']/np.array([lib[i]['f']['f0_med'] for i in ids])); dist=dist+0.6*np.abs(st)
        o=np.argsort(dist)[:k]; return [(ids[j],round(float(dist[j]),2)) for j in o]
    # 보정: 견본에 BGM 섞기(SNR 8dB) 후 같은 group 1~3위 회수율
    bg=load(sorted(glob.glob('shopping_shorts/assets/bgm_lib/*.mp3'))[3]); hit1=hit3=n=0
    rng=np.random.default_rng(0)
    for i in ids[::3]:
        x=load('shopping_shorts/assets/voice_samples/'+[s for s in samples if s['preset_id']==i][0]['sample_file'])
        b=bg[int(rng.integers(0,max(1,len(bg)-len(x)))):][:len(x)]
        if len(b)<len(x): continue
        y=x/np.sqrt((x**2).mean()+1e-9)+ b/np.sqrt((b**2).mean()+1e-9)*10**(-8/20)
        d=V.feats(y)
        if 'mfcc' not in d: continue
        r=rank(d,3); g=lib[i]['group']; n+=1; hit1+= lib[r[0][0]]['group']==g; hit3+= any(lib[a]['group']==g for a,_ in r)
    calib={'n':n,'top1_group':round(hit1/max(n,1),2),'top3_group':round(hit3/max(n,1),2),'note':'BGM SNR 8dB 섞은 견본의 같은 목소리(group) 회수율'}
    print('보정',calib,flush=True)
    res={'calib':calib,'tts_lib_stats':{}, 'videos':{}}
    keys=['st_std','micro_dst','micro_p90','shim','pause_cv','voiced_ratio']
    for k in keys:
        v=[lib[i]['f'][k] for i in ids if lib[i]['f'].get(k) is not None]; res['tts_lib_stats'][k]=[round(float(np.percentile(v,q)),3) for q in (10,50,90)]
    segs_of={}
    for w in sorted(glob.glob(os.path.join(wavdir,'*.wav'))):
        ch,vid=os.path.basename(w)[:-4].split('__'); x=load(w)
        if ch not in segs_of: segs_of[ch]=line_segs(ch)
        L=segs_of[ch]
        if vid in L['narr'] or vid in L['orig']: nar=L['narr'].get(vid,[]); org=L['orig'].get(vid,[])
        else: nar=NARR.get(ch,{}).get(vid,[]); org=[]
        r={}
        for tag,segs in (('narr',nar),('orig',org)):
            y=cat(x,segs)
            if len(y)>SR*1.0:
                d=V.feats(y); 
                if 'mfcc' in d: d['rank']=rank(d)
                d.pop('mfcc',None); r[tag]=d; r[tag]['segs']=segs
        res['videos'][ch+'/'+vid]=r
        print(ch,vid,{k:{kk:vv for kk,vv in v.items() if kk in ('f0_med','st_std','micro_dst','shim','pause_cv','rank')} for k,v in r.items()},flush=True)
    json.dump(res,open(out,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
