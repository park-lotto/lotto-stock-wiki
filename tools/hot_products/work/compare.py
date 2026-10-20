import json,sys,statistics as S; sys.stdout.reconfigure(encoding='utf-8')
SP='C:/Users/TheRose/AppData/Local/Temp/claude/C--Users-TheRose-Desktop-------/5bcd84e0-da56-4bff-98ee-acb52102d898/scratchpad/'
import os
sets={'터진 상품':(json.load(open('hits/enrich.json',encoding='utf-8')),json.load(open('hits/season.json',encoding='utf-8'))),
      '베스트셀러 후보':(json.load(open('enrich.json',encoding='utf-8')),json.load(open(SP+'season.json',encoding='utf-8')))}
def med(v): v=[x for x in v if x is not None]; return round(S.median(v)) if v else None
def pct(v,f): v=[x for x in v if x is not None]; return f'{round(100*sum(1 for x in v if f(x))/len(v))}%' if v else '-'
rows=[]
for name,(e,s) in sets.items():
    sm=[x.get('search_month') for x in e.values()]; tr=[x.get('trend_up') for x in e.values()]; yt=[x.get('yt_views_med') for x in e.values()]; vp=[x.get('vs_peak') for x in e.values()]
    su=[x.get('season_up') for x in s.values()]; nl=[x.get('now_vs_ly') for x in s.values()]
    rows.append((name,len(e),len(s),med(sm),pct(sm,lambda x:x>=1000),pct(sm,lambda x:x>=10000),med(tr),pct(tr,lambda x:x>0),med(vp),med(yt),med(su),pct(su,lambda x:x>20),med(nl),pct(nl,lambda x:x>0)))
lab=['','키워드 수','시즌분석 수','월검색 중앙','월검색 1천+','월검색 1만+','4주추세 중앙%','4주추세 상승 비율','1년 최고 대비 지금%','유튜브 조회 중앙','앞8주 시즌상승 중앙%','앞8주 +20%↑ 비율','작년 대비 지금 중앙%','작년보다 높음 비율']
for i in range(1,len(lab)): print(f'{lab[i]:<16} | {rows[0][i]!s:>8} | {rows[1][i]!s:>8}')
