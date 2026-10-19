"""sfx_rules.py 결과(json) -> 후보 사건 표(마크다운). 사건이 난 줄(화자·글·스티커)과 박자 역할을 붙인다. python sfx_table.py <rules.json> <채널>"""
import sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
import narr_report as N
r=json.load(open(sys.argv[1],encoding='utf-8')); ch0=sys.argv[2]
print('| 편 | 초 | 종류 | 세기(dB) | 박자 역할 | 같이 난 것(±0.3초) |'); print('|---|---|---|---|---|---|')
for k,v in r.items():
    ch,vid=k.split('/')
    if ch!=ch0: continue
    lines=None
    if ch=='starpickroom': lines=json.load(open('channel/starpickroom/줄판독/%s.json'%vid,encoding='utf-8'))['lines']
    nar=N.spr_lines()['narr'].get(vid,[]) if ch=='starpickroom' else N.NARR[ch].get(vid,[])
    seen=set()
    for c in v['cand']:
        t=c['t']
        if round(t,1) in seen: continue
        seen.add(round(t,1))
        role='나레 구간' if any(a-0.05<=t<=b+0.05 for a,b in nar) else '원음 구간'
        near=[n+' %.2f초'%d for n,d in {'자막교체':c['near'].get('cap',9),'스티커':c['near'].get('sticker',9),'나레↔원음 전환':c['near'].get('switch',9),'컷':c['near'].get('cut',9)}.items() if d<=0.3]
        txt=''
        if lines:
            for l in lines:
                if l['t0']-0.05<=t<=l['t1']+0.05:
                    st=','.join((s.get('what') or '') for s in (l.get('sticker') or []) if s.get('t_in') is not None and abs(s['t_in']-t)<=0.6)
                    txt='줄 "%s"%s'%((l.get('text') or '')[:18], (' · 스티커 '+st) if st else ''); break
        print('| %s | %.2f | %s | %.0f | %s | %s |'%(vid[:6],t,'띵류(음정 있는 울림)' if c['kind']=='tonal' else '짧은 광대역 솟음',c['db'],role,'; '.join(near+([txt] if txt else [])) or '표식 없음'))
