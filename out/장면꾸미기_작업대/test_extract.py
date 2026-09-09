import io,sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
WB=__file__.replace('test_extract.py','')
src=open(WB+'index.html',encoding='utf-8').read().split('\n')

def take(name):
    """중괄호 균형으로 함수 하나를 통째로 떼어낸다(줄 수 고정 금지 — 늘면 잘린다)."""
    for i,l in enumerate(src):
        if l.strip().startswith(name):
            depth=0; started=False; out=[]
            for j in range(i,len(src)):
                ln=src[j]; out.append(ln)
                for ch in ln:
                    if ch=='{': depth+=1; started=True
                    elif ch=='}': depth-=1
                if started and depth==0:
                    return '\n'.join(out)
    raise AssertionError(name)

names=['function _restoreBody(','function _healDefaults(','function _isBody(','function _touchBody(','function setBig(','function bumpBig(',
       'function setSub(','function bumpSub(','function _mirrorHc(','function setHc(',
       'function bumpHc(','function set(','function bump(','function applyLayout(','function toggleSame(',
       'function setCh(','function _chanReset(','function _chanFor(']
# 함수들이 쓰는 상수도 원본에서 그대로 떼어온다(손으로 베끼면 원본과 어긋난다)
consts=[l for l in src if l.strip().startswith('const _BODY_KEEP_KEYS=') or l.strip().startswith('let CH_MINE=')]
assert consts, '_BODY_KEEP_KEYS 를 못 찾았다'
parts=[c.strip() for c in consts]+[take(n) for n in names]
open(sys.argv[1],'w',encoding='utf-8').write('\n'.join(parts))
print('추출 함수:',len(parts))
