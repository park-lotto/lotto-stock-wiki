import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for r in d['runs']:
    print(r['model'], r['why'])
    for c in (r['clips'] or []): print('   ', c.get('i'), c.get('speakers'), c.get('text'))
