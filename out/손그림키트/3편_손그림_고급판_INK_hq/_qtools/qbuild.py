# Q 장면 빌드 — _lib_p/build.py 의 SHELL 을 그대로 읽어 쓰고(엔진 하나, R7), _assets/assets.js + qkit.js 를 붙인다.
# 종이결(R8③): 노이즈 0.07→0.10, 비네트 58%→55%. 공용 파일은 읽기만 한다.
# usage: py qbuild.py Q1 [Q2 ...]
import sys, os, re, shutil
HQ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(HQ, '_lib_p'); AS = os.path.join(HQ, '_assets'); QT = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(LIB, 'build.py'), encoding='utf8').read()
SHELL = re.search(r"SHELL='''(.*?)'''", src, re.S).group(1)
SHELL = SHELL.replace('<script src="brand/hq.js"></script>', '<script src="brand/hq.js"></script>\n<script src="brand/assets.js"></script>\n<script src="brand/qkit.js"></script>')
SHELL = SHELL.replace('filter="url(#nz)" opacity="0.07"', 'filter="url(#nz)" opacity="0.10"').replace('rgba(120,90,40,0) 58%', 'rgba(120,90,40,0) 55%')
assert 'assets.js' in SHELL and 'opacity="0.10"' in SHELL and '55%' in SHELL
for name in sys.argv[1:]:
    d = os.path.join(HQ, name); t = os.path.join(d, 'template'); b = os.path.join(t, 'brand')
    os.makedirs(b, exist_ok=True)
    for fn in ['gsap.min.js', 'hq.js', 'NanumPenScript.ttf', 'Gaegu-Bold.ttf', 'Pretendard-ExtraBold.otf']:
        shutil.copy(os.path.join(LIB, fn), os.path.join(b, fn))
    shutil.copy(os.path.join(AS, 'assets.js'), os.path.join(b, 'assets.js'))
    shutil.copy(os.path.join(QT, 'qkit.js'), os.path.join(b, 'qkit.js'))
    sc = open(os.path.join(d, 'scene.js'), encoding='utf8').read()
    dur = open(os.path.join(d, 'dur.txt')).read().strip()
    pen = open(os.path.join(LIB, 'pen.svg'), encoding='utf8').read()
    open(os.path.join(t, 'index.html'), 'w', encoding='utf8').write(SHELL.replace('__DUR__', dur).replace('__SCENE__', sc).replace('__PEN__', pen))
    import subprocess; subprocess.run([sys.executable, os.path.join(HQ, '_hero_draft', 'hero_install.py'), t], check=True)
    print('built', name)
