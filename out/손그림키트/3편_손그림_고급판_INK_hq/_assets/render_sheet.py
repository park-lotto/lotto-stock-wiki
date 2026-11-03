# 자산 전수 검수 시트 — py render_sheet.py  → sheet.png(긴 변 1600) + big_*.png(960)
import pathlib, sys
from playwright.sync_api import sync_playwright
D = pathlib.Path(__file__).parent
JS = (D / "assets.js").read_text(encoding="utf-8")
HTML = """<!doctype html><meta charset=utf-8><style>
body{margin:0;background:#FBF8F1;font-family:sans-serif}
#g{display:grid;grid-template-columns:repeat(%(cols)d,1fr);gap:6px;padding:8px;width:%(w)dpx;box-sizing:border-box}
.c{background:#fff;border:1px solid #ddd;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:%(ch)dpx;overflow:hidden;position:relative}
.c svg{max-width:100%%;max-height:%(sh)dpx;width:auto;height:auto}
.c b{font-size:11px;color:#555;position:absolute;left:4px;top:3px;font-weight:normal}
</style><body><div id=g></div><script>%(js)s</script><script>
const g=document.getElementById('g');
const names=%(names)s;
for(const n of names){const c=document.createElement('div');c.className='c';
 try{c.innerHTML=INKASSETS.toSVG(n,{bg:false,pad:10})+'<b>'+n+'</b>';}catch(e){c.innerHTML='<b style="color:red">'+n+' '+e.message+'</b>';}
 g.appendChild(c);} </script>"""

def main():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome"); pg = b.new_page()
        pg.set_content("<script>%s</script>" % JS)
        names = pg.evaluate("INKASSETS.list()")
        bigs = sys.argv[1:] or ["face.hope.front", "face.tired.front"]
        # 전체 시트: 8열, 셀 190px → 폭 1600
        cols = 8; w = 1600; ch = 230; sh = 200
        pg.set_viewport_size({"width": w, "height": 100})
        pg.set_content(HTML % dict(cols=cols, w=w, ch=ch, sh=sh, js=JS, names=str(names).replace("'", '"')))
        pg.wait_for_timeout(200)
        pg.locator("#g").screenshot(path=str(D / "sheet.png"))
        for n in bigs:
            pg.set_viewport_size({"width": 960, "height": 960})
            pg.set_content("<style>body{margin:0;background:#FBF8F1}svg{width:960px;height:960px}</style><script>%s</script><div id=s></div><script>document.getElementById('s').innerHTML=INKASSETS.toSVG('%s',{paper:true,pad:40})</script>" % (JS, n))
            pg.wait_for_timeout(150)
            pg.screenshot(path=str(D / ("big_" + n.replace(".", "_") + ".png")))
        b.close()
    print("assets", len(names), "sheet", D / "sheet.png")

if __name__ == "__main__":
    main()
