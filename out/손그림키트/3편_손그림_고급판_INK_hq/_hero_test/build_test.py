# 새 주인공 시험 빌드 — P1 빌드(_tool/build_p.py)와 같은 껍데기 + hero_strokes.js·hero_put.js·컬러판(brand/hero/)
# 다른 장면에 꽂을 때도 이 네 줄(스크립트 2개 싣기 + flat 복사)만 build_p.py 에 더하면 된다.
# usage: py build_test.py P1  → P1/template/index.html
import sys, os, shutil, glob
T = os.path.dirname(os.path.abspath(__file__)); HQ = os.path.dirname(T)
LIB = os.path.join(HQ, '_lib_p'); AS = os.path.join(HQ, '_assets'); HD = os.path.join(HQ, '_hero_draft')
SHELL = open(os.path.join(LIB, 'build.py'), encoding='utf8').read().split("SHELL='''")[1].split("'''")[0]
SHELL = SHELL.replace('<script src="brand/hq.js"></script>',
    '<script src="brand/hq.js"></script><script src="brand/assets.js"></script><script src="brand/hero_strokes.js"></script><script src="brand/hero_put.js"></script>')
for name in sys.argv[1:]:
    d = os.path.join(T, name); t = os.path.join(d, 'template'); b = os.path.join(t, 'brand'); hb = os.path.join(b, 'hero')
    os.makedirs(hb, exist_ok=True)
    for fn in ['gsap.min.js', 'hq.js', 'NanumPenScript.ttf', 'Gaegu-Bold.ttf', 'Pretendard-ExtraBold.otf']:
        shutil.copy(os.path.join(LIB, fn), os.path.join(b, fn))
    shutil.copy(os.path.join(AS, 'assets.js'), os.path.join(b, 'assets.js'))
    for fn in ['hero_strokes.js', 'hero_put.js']: shutil.copy(os.path.join(HD, fn), os.path.join(b, fn))
    for f in glob.glob(os.path.join(HD, "c_*_flat.png")) + glob.glob(os.path.join(HD, "l_*.png")): shutil.copy(f, os.path.join(hb, os.path.basename(f)))
    kit = open(os.path.join(d, '_tool', 'kit.js'), encoding='utf8').read()
    sc = open(os.path.join(d, 'scene.js'), encoding='utf8').read()
    dur = open(os.path.join(d, 'dur.txt')).read().strip()
    pen = open(os.path.join(LIB, 'pen.svg'), encoding='utf8').read()
    open(os.path.join(t, 'index.html'), 'w', encoding='utf8').write(SHELL.replace('__DUR__', dur).replace('__SCENE__', kit + '\n' + sc).replace('__PEN__', pen))
    print('built', name, dur)
