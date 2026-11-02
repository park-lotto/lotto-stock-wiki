import json,glob,sys
d=sys.argv[1]; bad=0; n=0
for p in glob.glob(d+'/*.json'):
    for l in json.load(open(p,encoding='utf-8'))['lines']:
        n+=1; bad+=sum(1 for k in ('transition','fit','confidence') if l.get(k) is None)
print('줄',n,'null',bad); sys.exit(1 if bad else 0)
