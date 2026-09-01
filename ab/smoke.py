# -*- coding: utf-8 -*-
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'C:/Users/CH/Desktop/로또의 주식'); sys.path.insert(0, _HERE)
from run_ab import load_job, build_cases, score
b, sm = load_job()
print('비트', len(b), '세그', len(sm))
cs = build_cases(b, sm)
print('케이스', len(cs), [c[0] for c in cs])
for name, cb in cs:
    bad, det = score(cb, sm)
    print('  %-14s 출발 어긋남 %d/%d' % (name, bad, len(cb)))
bad, det = score(b, sm)
print('--- 원본 상세 ---')
for d in det:
    print('  %-9s %-6s mismatch=%s  %s' % (d['role'], d['shot_role'], d['mismatch'], d['scene_desc'][:40]))
