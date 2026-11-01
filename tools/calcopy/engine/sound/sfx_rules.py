"""효과음 후보 사건 x 자막/스티커/나레전환/컷 표식 대조 + 우연 일치율. python sfx_rules.py <wav폴더> <출력json>"""
import sys, os, glob, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import sfx_fp as F, sfx_events as E, narr_report as N
TOL=0.15
def markers(ch,vid):
    m={'cap':[],'sticker':[],'switch':[],'cut':[]}
    if ch=='starpickroom':
        d=json.load(open('channel/starpickroom/줄판독/%s.json'%vid,encoding='utf-8'))
        for l in d['lines']:
            m['cap'].append(l['t0'])
            for s in l.get('sticker') or []:
                if s.get('t_in') is not None: m['sticker'].append(s['t_in'])
        m['cut']=[c if not isinstance(c,list) else c[0] for c in d.get('cuts_approx',[]) if isinstance(c,(int,float,list))]
        nar=N.spr_lines()['narr'].get(vid,[])
    else:
        d=json.load(open(glob.glob('channel/%s/뜯기/%s/뜯기.json'%(ch,vid))[0],encoding='utf-8'))
        m['cap']=d['captions'].get('changes',[]); m['cut']=d['cuts'].get('times',[])
        for a in (d.get('overlay_rules') or {}).get('appearances',[]): m['sticker'].append(a['t'][0])
        nar=N.NARR[ch].get(vid,[])
    for a,b in nar: m['switch']+= [a,b]
    m['switch']=[t for t in m['switch'] if t>0.05]
    m={k:[float(a) for a in v if isinstance(a,(int,float))] for k,v in m.items()}
    return m
def near(t,arr): 
    return min((abs(t-a) for a in arr),default=9)
def main(wavdir,out):
    res={}
    for w in sorted(glob.glob(os.path.join(wavdir,'*.wav'))):
        ch,vid=os.path.basename(w)[:-4].split('__'); x=F.load(w); ev=E.detect(x); mk=markers(ch,vid)
        dur=len(x)/F.SR
        cand=[e for e in ev if e['kind']=='tonal' or e.get('isolated',0)>=0.8]
        rows=[]
        for e in cand:
            rows.append({**e,'near':{k:round(near(e['t'],v),2) for k,v in mk.items() if v}})
        # 우연: 임의 시각이 표식 +-TOL 에 들 확률
        rng=np.random.default_rng(0); rt=rng.uniform(0,dur,2000); chance={k:float(np.mean([near(t,v)<=TOL for t in rt])) for k,v in mk.items() if v}
        strong=[e for e in ev if e['db']>=25]
        sc={k:[round(e['t'],2) for e in strong if near(e['t'],v)<=TOL] for k,v in mk.items() if v}
        res[ch+'/'+vid]={'strong_n':len(strong),'strong_hits':sc,'dur':round(dur,1),'n_events_all':len(ev),'cand':rows,'markers':{k:[round(a,2) for a in v] for k,v in mk.items()},'chance':{k:round(v,2) for k,v in chance.items()}}
        print(ch,vid,'후보',len(rows),'전체',len(ev),[(r['t'],r['kind'],r.get('isolated')) for r in rows],flush=True)
    json.dump(res,open(out,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
