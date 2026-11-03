"""P6~P10 빌드 (Opus, 2026-10-29) — _lib_p/build.py 셸 그대로 + _assets/assets.js + helpers.js 를 끼운다.
공용 파일(_lib_p, _assets)은 읽기만 한다(복사). usage: py build.py P6 P7 ...
"""
import sys, os, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__)); HQ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HQ, '_lib_p'))
src = open(os.path.join(HQ, '_lib_p', 'build.py'), encoding='utf8').read()
SHELL = re.search(r"SHELL='''(.*?)'''", src, re.S).group(1)
SHELL = SHELL.replace('<script src="brand/hq.js"></script>', '<script src="brand/hq.js"></script><script src="brand/assets.js"></script><script src="brand/helpers.js"></script>')
assert 'assets.js' in SHELL
LIB = os.path.join(HQ, '_lib_p')
for name in sys.argv[1:]:
    d = os.path.join(HQ, name); t = os.path.join(d, 'template'); b = os.path.join(t, 'brand')
    os.makedirs(b, exist_ok=True)
    for fn in ['gsap.min.js', 'hq.js', 'NanumPenScript.ttf', 'Gaegu-Bold.ttf', 'Pretendard-ExtraBold.otf']:
        shutil.copy(os.path.join(LIB, fn), os.path.join(b, fn))
    shutil.copy(os.path.join(HQ, '_assets', 'assets.js'), os.path.join(b, 'assets.js'))
    shutil.copy(os.path.join(HERE, 'helpers.js'), os.path.join(b, 'helpers.js'))
    sc = open(os.path.join(d, 'scene.js'), encoding='utf8').read()
    dur = open(os.path.join(d, 'dur.txt')).read().strip()
    pen = open(os.path.join(LIB, 'pen.svg'), encoding='utf8').read()
    open(os.path.join(t, 'index.html'), 'w', encoding='utf8').write(SHELL.replace('__DUR__', dur).replace('__SCENE__', sc).replace('__PEN__', pen))
    print('built', name)
