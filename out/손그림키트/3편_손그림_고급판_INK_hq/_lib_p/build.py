import sys,os,shutil
HQ=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB=os.path.join(HQ,'_lib_p')
SHELL='''<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="brand/gsap.min.js"></script>
<style>
@font-face { font-family: "NP"; src: url("brand/NanumPenScript.ttf"); }
@font-face { font-family: "GB"; src: url("brand/Gaegu-Bold.ttf"); }
@font-face { font-family: "PB"; src: url("brand/Pretendard-ExtraBold.otf"); font-weight: 800; }
html, body { margin: 0; background: #FBF8F1; }
#stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #FBF8F1; }
#svg, #bgn { position: absolute; left: 0; top: 0; }
#tdiv { position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; }
#vig { position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; background: radial-gradient(ellipse at center, rgba(120,90,40,0) 58%, rgba(120,90,40,0.07) 100%); pointer-events: none; }
</style></head><body>
<div id="stage" data-composition-id="promo" data-start="0" data-duration="__DUR__" data-width="1920" data-height="1080">
<svg id="bgn" width="1920" height="1080" viewBox="0 0 1920 1080"><filter id="nz" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/><feColorMatrix type="matrix" values="0 0 0 0 0.35  0 0 0 0 0.28  0 0 0 0 0.18  0 0 0 0.9 0"/></filter><rect width="1920" height="1080" filter="url(#nz)" opacity="0.07"/></svg>
<svg id="svg" width="1920" height="1080" viewBox="0 0 1920 1080"></svg>
<div id="tdiv"></div>
<div id="vig"></div>
__PEN__
</div>
<script src="brand/hq.js"></script>
<script>
const {Scene,person,robot,smooth,ell,cloud,poly,rr,ln,pl,tube,mk,INK,ORG,SKIN,SHIRT,HAIR,BEIGE,SKY,PINK,eo,seg,clamp,qo,J,f} = HQ;
document.fonts.load('40px "NP"').then(()=>document.fonts.load('40px "GB"')).then(()=>document.fonts.load('800 40px "PB"')).then(()=>document.fonts.ready).then(()=>{
const S = new Scene(__DUR__);
__SCENE__
S.start();
});
</script></body></html>
'''
for name in sys.argv[1:]:
    d=os.path.join(HQ,name); t=os.path.join(d,'template'); b=os.path.join(t,'brand')
    os.makedirs(b,exist_ok=True)
    for fn in ['gsap.min.js','hq.js','NanumPenScript.ttf','Gaegu-Bold.ttf','Pretendard-ExtraBold.otf']:
        shutil.copy(os.path.join(LIB,fn),os.path.join(b,fn))
    sc=open(os.path.join(d,'scene.js'),encoding='utf8').read()
    dur=open(os.path.join(d,'dur.txt')).read().strip()
    pen=open(os.path.join(LIB,'pen.svg'),encoding='utf8').read()
    open(os.path.join(t,'index.html'),'w',encoding='utf8').write(SHELL.replace('__DUR__',dur).replace('__SCENE__',sc).replace('__PEN__',pen))
    print('built',name)
