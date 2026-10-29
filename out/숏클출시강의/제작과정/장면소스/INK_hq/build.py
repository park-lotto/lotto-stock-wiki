import sys, shutil, pathlib
root = pathlib.Path(__file__).parent
lib = root/'_lib'
DUR = {'P1':12,'P2':10,'P3':9,'P4':9,'P5':10}
HTML = '''<!doctype html>
<html lang="ko"><head><meta charset="UTF-8" /><meta name="viewport" content="width=1920, height=1080" />
<script src="brand/gsap.min.js"></script>
<style>
@font-face { font-family: "NP"; src: url("brand/NanumPenScript.ttf"); }
@font-face { font-family: "GG"; src: url("brand/Gaegu-Bold.ttf"); }
@font-face { font-family: "PB"; src: url("brand/Pretendard-ExtraBold.otf"); font-weight: 800; }
html, body { margin: 0; background: #FBF8F1; }
#stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #FBF8F1; }
#overlay { position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; z-index: 900; pointer-events: none;
  background: url("brand/paper.png"), radial-gradient(ellipse at center, rgba(0,0,0,0) 62%, rgba(60,45,20,0.09) 100%); background-size: 512px 512px, 100% 100%; opacity: 0.55; }
#pen { position: absolute; left: 0; top: 0; z-index: 1000; opacity: 0; overflow: visible; }
</style></head><body>
<div id="stage" data-composition-id="@@ID@@" data-start="0" data-duration="@@DUR@@" data-width="1920" data-height="1080">
  <div id="overlay"></div>
  <svg id="pen" width="90" height="90" viewBox="0 0 90 90"><g transform="rotate(-38 0 0)"><path d="M0 0 L14 -9 L84 -9 L84 9 L14 9 Z" fill="#1F1D1A"/><path d="M0 0 L14 -9 L14 9 Z" fill="#f2e6cf" stroke="#1F1D1A" stroke-width="2"/><path d="M0 0 L5 -3 L5 3 Z" fill="#1F1D1A"/><rect x="60" y="-9" width="6" height="18" fill="#F6A93B"/></g></svg>
</div>
<script src="brand/ink.js"></script><script src="brand/hero.js"></script>
<script>
document.fonts.load('40px "NP"').then(()=>document.fonts.load('40px "GG"')).then(()=>document.fonts.load('800 40px "PB"')).then(()=>document.fonts.ready).then(()=>{
  const ink = new INK.Ink(document.getElementById("stage"), @@DUR@@);
  window.__ink = ink;
  const { Ink, ell, P, rect, line, ORANGE } = INK;
@@SCENE@@
  ink.start("@@ID@@");
});
</script></body></html>
'''
for sc in sys.argv[1:]:
    d = root/sc/'template'; (d/'brand').mkdir(parents=True, exist_ok=True)
    for f in lib.iterdir(): shutil.copy(f, d/'brand'/f.name)
    scene = (root/sc/'scene.js').read_text(encoding='utf8')
    (d/'index.html').write_text(HTML.replace('@@ID@@',sc).replace('@@DUR@@',str(DUR[sc])).replace('@@SCENE@@',scene), encoding='utf8')
    print('built', sc)
