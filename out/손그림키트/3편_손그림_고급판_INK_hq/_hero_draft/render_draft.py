# 새 주인공 시안 시트 — py render_draft.py → sheet.png(1600 폭, 4안 × hope/tired/폰포즈) + big_<who>.png(960)
import pathlib, sys
from playwright.sync_api import sync_playwright
D = pathlib.Path(__file__).parent
JS = (D.parent / "_assets" / "assets.js").read_text(encoding="utf-8") + "\n" + (D / "hero_draft.js").read_text(encoding="utf-8")
LABEL = {"mA": "A안 남 · 단정·현실적", "fA": "A안 여 · 단정·현실적", "mB": "B안 남 · 귀엽고 둥근", "fB": "B안 여 · 귀엽고 둥근"}
HTML = """<!doctype html><meta charset=utf-8><style>
body{margin:0;background:#FBF8F1;font-family:sans-serif}
#g{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:10px;width:1600px;box-sizing:border-box}
h4{margin:0;text-align:center;font-size:18px;color:#333;height:26px}
.c{background:#fff;border:1px solid #ddd;display:flex;align-items:center;justify-content:center;height:%(ch)dpx;overflow:hidden}
.c svg{max-width:100%%;max-height:100%%;width:auto;height:auto}
</style><body><div id=g></div><script>%(js)s</script><script>
const g=document.getElementById('g'), W=HERODRAFT.who;
W.forEach(w=>{const h=document.createElement('h4');h.textContent=%(labels)s[w];g.appendChild(h);});
const rows=[w=>HERODRAFT.face(w,'hope'), w=>HERODRAFT.face(w,'tired'), w=>HERODRAFT.bustPhone(w,'hope')];
for(const r of rows) for(const w of W){const c=document.createElement('div');c.className='c';
 try{c.innerHTML=INKASSETS.toSVG(r(w),{bg:false,pad:10});}catch(e){c.innerHTML='<b style="color:red">'+w+' '+e.message+'</b>';} g.appendChild(c);}
</script>"""

def main():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome"); pg = b.new_page()
        pg.set_viewport_size({"width": 1600, "height": 100})
        pg.set_content(HTML % dict(ch=330, js=JS, labels=str(LABEL).replace("'", '"')))
        pg.wait_for_timeout(200)
        pg.locator("#g").screenshot(path=str(D / "sheet.png"))
        for w in (sys.argv[1:] or ["mA", "fA", "mB", "fB"]):
            pg.set_viewport_size({"width": 960, "height": 960})
            pg.set_content("<style>body{margin:0;background:#FBF8F1}svg{width:960px;height:960px}</style><script>%s</script><div id=s></div><script>document.getElementById('s').innerHTML=INKASSETS.toSVG(HERODRAFT.face('%s','hope'),{paper:true,pad:40})</script>" % (JS, w))
            pg.wait_for_timeout(150)
            pg.screenshot(path=str(D / ("big_" + w + ".png")))
        b.close()
    print("sheet", D / "sheet.png")

if __name__ == "__main__":
    main()
