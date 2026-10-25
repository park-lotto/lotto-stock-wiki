"""노하우카드.md → 분류 필터·검색되는 HTML (개인 열람용, 게시 금지)."""
import re, sys, html, json
src, out = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
cards = []
for blk in re.split(r"\n(?=### )", text):
    m = re.match(r"### \[([\d:]+)\]\s*(.+)", blk)
    if not m: continue
    c = {"t": m.group(1), "title": m.group(2).strip()}
    for k, key in (("무엇", "what"), ("왜/근거", "why"), ("어떻게", "how"), ("분류", "cat")):
        mm = re.search(rf"^- {re.escape(k)}:\s*(.*?)(?=^- (?:무엇|왜/근거|어떻게|분류):|^## |\Z)", blk, re.S | re.M)
        c[key] = mm.group(1).strip() if mm else ""
    c["cats"] = [x.strip() for x in c["cat"].split("/") if x.strip()]
    cards.append(c)
CATS = ["대본", "장면·편집", "음성", "소재수집", "저작권·정책", "도구·비용", "채널운영", "기타"]
page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>3주차 노하우 카드</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1a1a1a;--sub:#666;--line:#e4e4e0;--acc:#2f6fed}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--card:#1e1e1e;--ink:#eee;--sub:#aaa;--line:#333;--acc:#6c9bff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 "Pretendard","Malgun Gothic",sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px;z-index:1}
h1{font-size:19px;margin:0 0 4px}.note{color:var(--sub);font-size:12.5px}
.bar{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:5px 12px;font:inherit;font-size:13px;cursor:pointer;transition:transform .12s ease-out}
button:active{transform:scale(.97)}button.on{background:var(--acc);border-color:var(--acc);color:#fff}
input{flex:1;min-width:180px;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 10px;font:inherit}
main{max-width:920px;margin:0 auto;padding:16px}
.c{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:12px}
.h{display:flex;gap:10px;align-items:baseline}.t{font-family:Consolas,monospace;color:var(--acc);font-size:13px;white-space:nowrap}
.ti{font-weight:700;font-size:16px}.tags{margin:6px 0}.tag{display:inline-block;font-size:11.5px;color:var(--sub);border:1px solid var(--line);border-radius:4px;padding:0 6px;margin-right:4px}
dl{margin:6px 0 0;display:grid;grid-template-columns:62px 1fr;gap:4px 10px}dt{color:var(--sub);font-size:13px}dd{margin:0;white-space:pre-wrap;word-break:break-word}
.none{color:var(--sub)}#cnt{color:var(--sub);font-size:13px;margin-bottom:8px}
</style></head><body><header><h1>AI스위칭쇼츠 3주차 · 노하우 카드</h1>
<div class="note">개인 학습용 · 외부 공유 금지 · 제미니 판독 기반이라 도구명·숫자 오인식 가능</div>
<div class="bar" id="bar"></div><div class="bar"><input id="q" placeholder="검색 (예: 누끼, 타입캐스트, 프롬프트)"></div></header>
<main><div id="cnt"></div><div id="list"></div></main><script>
const C=__CARDS__,CATS=__CATS__;let cur="전체";
const esc=s=>s.replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));
const bar=document.getElementById("bar");
["전체",...CATS].forEach(k=>{const b=document.createElement("button");const n=k=="전체"?C.length:C.filter(c=>c.cats.includes(k)).length;
b.textContent=k+" "+n;b.onclick=()=>{cur=k;draw()};b.dataset.k=k;bar.appendChild(b)});
function draw(){const q=document.getElementById("q").value.trim().toLowerCase();
[...bar.children].forEach(b=>b.classList.toggle("on",b.dataset.k==cur));
const f=C.filter(c=>(cur=="전체"||c.cats.includes(cur))&&(!q||JSON.stringify(c).toLowerCase().includes(q)));
document.getElementById("cnt").textContent=f.length+"장";
const row=(k,v)=>`<dt>${k}</dt><dd class="${/기록에 없음/.test(v)&&v.length<40?'none':''}">${esc(v||"-")}</dd>`;
document.getElementById("list").innerHTML=f.map(c=>`<div class="c"><div class="h"><span class="t">${c.t}</span><span class="ti">${esc(c.title)}</span></div>
<div class="tags">${c.cats.map(x=>`<span class="tag">${x}</span>`).join("")}</div><dl>${row("무엇",c.what)}${row("왜/근거",c.why)}${row("어떻게",c.how)}</dl></div>`).join("")}
document.getElementById("q").oninput=draw;draw();
</script></body></html>"""
page = page.replace("__CARDS__", json.dumps(cards, ensure_ascii=False)).replace("__CATS__", json.dumps(CATS, ensure_ascii=False))
open(out, "w", encoding="utf-8").write(page)
print(len(cards), "장")
