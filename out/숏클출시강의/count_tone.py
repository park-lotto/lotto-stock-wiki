import re,sys
t=open(sys.argv[1],encoding='utf-8').read()
main=t.split('# 쇼츠 4편')[0] if '# 쇼츠 4편' in t else t
lines=[l[2:] for l in main.splitlines() if l.startswith('> ')]
txt='\n'.join(lines)
keys=['그냥','보시면','보세요','굉장히','잖아요','예를 들어서','근데','쭉','진짜','아시겠죠','딱','솔직히','습니다','거예요','겁니다','거든요']
print("chars:",len(re.sub(r'\s','',txt)))
for k in keys: print(f"{k}\t{txt.count(k)}")
