# -*- coding: utf-8 -*-
"""전수조사 결과(out/*.json)에서 채널별 '평소 대비 터진 영상'을 뽑아 JSON·HTML로 만든다."""
import json, glob, io, statistics as st

M = "C:/Users/CH/Desktop/로또의 주식/out/"
sul = set(l.strip() for l in open("sul_final.txt") if l.strip())
home = set(l.strip() for l in open("home87.txt") if l.strip())
rows, skipped, tot = [], [], 0
for f in glob.glob("out/*.json"):
    d = json.load(open(f, encoding="utf-8")); v = d["videos"]; tot += len(v)
    name = v[0]["ch"] if v else d["cid"]
    if d["cid"] not in sul and d["cid"] not in home:
        continue      # 사장님이 관리자 화면에서 다른 탭으로 옮긴 채널
    if len(v) < 10:
        skipped.append((name, len(v))); continue
    med = st.median(x["views"] for x in v) or 1
    top = sorted(v, key=lambda x: -x["views"])[:3]
    picks = [{"id": x["id"], "t": x["title"], "v": x["views"], "r": round(x["views"] / med, 1), "d": x["at"][:10]}
             for x in top if x["views"] >= med * 5 and x["views"] >= 10000]
    rows.append({"id": d["cid"], "name": name, "g": "썰쇼핑" if d["cid"] in sul else "홈템", "n": len(v), "med": int(med), "p": picks})
json.dump({"made": "2026-10-06", "rule": "60초 이하 쇼츠 전수, 채널 중앙값의 5배 이상이면서 1만 이상, 채널당 조회수 상위 3편", "channels": rows},
          io.open(M + "채널별_터진영상_2026-10-06.json", "w", encoding="utf-8"), ensure_ascii=False)
print("채널", len(rows), "뽑힌 영상", sum(len(r["p"]) for r in rows), "| 뽑힌 게 없는 채널", [r["name"] for r in rows if not r["p"]],
      "| 10편 미만이라 뺀 채널", skipped)
print("썰쇼핑", sum(len(r["p"]) for r in rows if r["g"] == "썰쇼핑"), "편 /", sum(1 for r in rows if r["g"] == "썰쇼핑" and r["p"]), "채널",
      "| 홈템", sum(len(r["p"]) for r in rows if r["g"] == "홈템"), "편 /", sum(1 for r in rows if r["g"] == "홈템" and r["p"]), "채널")

HTML = r'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>채널별 터진 영상</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2330;--sub:#5d6778;--line:#e3e7ee;--accent:#2563eb;--hot:#c2410c;--hotbg:#ffedd5}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1b2029;--ink:#e8ecf3;--sub:#9aa5b8;--line:#2c3442;--accent:#7aa7ff;--hot:#fdba74;--hotbg:#43240f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Pretendard","Malgun Gothic",system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.wrap,main{max-width:1900px;margin:0 auto}
h1{font-size:20px;margin:0 0 2px}
.meta{color:var(--sub);font-size:13px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px}
input[type=search],select{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
input[type=search]{flex:1;min-width:160px}
.seg button{font:inherit;padding:7px 14px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.seg button:first-child{border-radius:8px 0 0 8px}.seg button:last-child{border-radius:0 8px 8px 0}
.seg button.on{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700}
main{padding:12px 16px 80px}
#list{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}
.row{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px}
.top{display:flex;gap:10px;align-items:baseline;margin-bottom:10px}
.name{font-weight:700;font-size:17px;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.name a{color:inherit;text-decoration:none}.name a:hover{text-decoration:underline}
.small{color:var(--sub);font-size:12px;flex:none}
.thumbs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.th{color:inherit;text-decoration:none;min-width:0}
.th .img{position:relative;aspect-ratio:9/16;border-radius:8px;overflow:hidden;background:var(--line)}
.th img{width:100%;height:100%;object-fit:cover;display:block}
.th .x{position:absolute;left:6px;top:6px;background:var(--hotbg);color:var(--hot);font-weight:800;font-size:13px;padding:2px 7px;border-radius:999px}
.th .vw{position:absolute;left:0;right:0;bottom:0;padding:14px 6px 4px;color:#fff;font-size:13px;font-weight:700;background:linear-gradient(transparent,rgba(0,0,0,.75))}
.th .t{font-size:12px;margin-top:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.th .d{font-size:11px;color:var(--sub)}
.th{position:relative}.del{position:absolute;right:6px;top:6px;z-index:2;width:28px;height:28px;border-radius:50%;border:0;background:rgba(0,0,0,.7);color:#fff;font-size:15px;cursor:pointer}
.del:hover{background:#dc2626}.th.gone .img{opacity:.25}.th.gone .t{text-decoration:line-through}
.acts{display:flex;gap:6px;flex:none}.acts button,.bar button{font:inherit;font-size:12px;padding:4px 9px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--ink);cursor:pointer}
.acts button.on{background:var(--accent);border-color:var(--accent);color:#fff}.row.out{opacity:.45}
.bar button.main{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:700;font-size:14px;padding:7px 12px}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111;color:#fff;padding:10px 16px;border-radius:8px;display:none;z-index:9}
textarea{width:100%;height:90px;margin-top:8px;display:none;font:13px monospace}
@media (max-width:520px){#list{grid-template-columns:1fr}}
</style></head><body>
<header><div class="wrap">
<h1>채널별 터진 영상</h1>
<div class="meta">고른 205채널의 60초 이하 쇼츠 __NV__편 전수조사(2026-10-06) · 그 채널 평소(중앙) 조회수의 5배 이상이면서 1만 이상인 영상 중 채널당 상위 3편 · 지금 보이는 영상 <b id="cnt"></b>편</div>
<div class="bar">
<span class="seg"><button data-g="썰쇼핑" class="on">썰쇼핑</button><button data-g="홈템">홈템</button><button data-g="">전체</button></span>
<input type="search" id="q" placeholder="채널명 검색">
<select id="sort"><option value="r">평소 대비 배수 순</option><option value="v">최고 조회수 순</option><option value="d">최근에 터진 순</option><option value="name">이름 순</option></select>
<label style="font-size:13px;color:var(--sub)"><input type="checkbox" id="showGone"> 뺀 것도 보기</label>
<span style="font-size:13px">고친 것 <b id="chg">0</b>건</span>
<button id="undo">전부 되돌리기</button><button class="main" id="copy">고친 내용 복사</button>
</div><textarea id="outbox" readonly></textarea></div></header>
<main><div id="list"></div></main>
<div id="toast"></div>
<script>
const DATA = __DATA__;
let G = "썰쇼핑";
const KEY = "hit_edit_v1";
let ED = {move:{}, delV:{}};   // move: 채널ID → "썰쇼핑"|"홈템"|"빼기" / delV: 영상ID → 1
try{ ED = Object.assign(ED, JSON.parse(localStorage.getItem(KEY) || "{}")); }catch(e){}
const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(ED)); }catch(e){} };
const grp = c => ED.move[c.id] || c.g;
const n = v => v >= 100000000 ? (v/100000000).toFixed(1) + "억" : v >= 10000 ? (v/10000).toFixed(v >= 100000 ? 0 : 1) + "만" : v.toLocaleString();
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const $ = id => document.getElementById(id);
function render(){
  const q = $("q").value.trim().toLowerCase(), s = $("sort").value;
  const sg = $("showGone").checked;
  let rows = DATA.filter(c => c.p.length && (!q || c.name.toLowerCase().includes(q)) &&
    (grp(c) === "빼기" ? sg && (!G || c.g === G) : (!G || grp(c) === G)) && (sg || c.p.some(v => !ED.delV[v.id])));
  const key = {r: c => Math.max(...c.p.map(x => x.r)), v: c => c.p[0].v, d: c => c.p.map(x => x.d).sort().pop()};
  rows.sort((a,b) => s === "name" ? a.name.localeCompare(b.name, "ko") : s === "d" ? key.d(b).localeCompare(key.d(a)) : key[s](b) - key[s](a));
  $("cnt").textContent = rows.reduce((a,c) => a + (grp(c) === "빼기" ? 0 : c.p.filter(v => !ED.delV[v.id]).length), 0).toLocaleString();
  $("chg").textContent = Object.keys(ED.move).length + Object.keys(ED.delV).length;
  $("list").innerHTML = rows.map(c => `<div class="row ${grp(c) === "빼기" ? "out" : ""}" data-id="${c.id}"><div class="top">
    <div class="name"><a href="https://www.youtube.com/channel/${c.id}/shorts" target="_blank" rel="noopener">${esc(c.name)}</a></div>
    <div class="small">쇼츠 ${c.n.toLocaleString()}편 · 평소 ${n(c.med)}</div>
    <div class="acts">${["썰쇼핑","홈템","빼기"].map(g => `<button data-mv="${g}" class="${grp(c) === g ? "on" : ""}">${g === "빼기" ? "채널 빼기" : g}</button>`).join("")}</div></div>
    <div class="thumbs">${c.p.filter(v => sg || !ED.delV[v.id]).map(v => `<a class="th ${ED.delV[v.id] ? "gone" : ""}" data-v="${v.id}" href="https://www.youtube.com/shorts/${v.id}" target="_blank" rel="noopener">
      <button class="del" title="이 영상 빼기/되살리기">${ED.delV[v.id] ? "↺" : "✕"}</button><div class="img"><img loading="lazy" src="https://i.ytimg.com/vi/${v.id}/oardefault.jpg" alt=""><span class="x">${v.r >= 100 ? Math.round(v.r) : v.r}배</span><span class="vw">${n(v.v)}</span></div>
      <div class="t">${esc(v.t || "")}</div><div class="d">${v.d}</div></a>`).join("")}</div></div>`).join("");
}
document.querySelectorAll(".seg button").forEach(b => b.onclick = () => { G = b.dataset.g; document.querySelectorAll(".seg button").forEach(x => x.classList.toggle("on", x === b)); render(); });
["q","sort","showGone"].forEach(id => $(id).addEventListener("input", render));
$("list").addEventListener("click", e => {
  const d = e.target.closest(".del"), m = e.target.closest("[data-mv]");
  if(d){ e.preventDefault(); const id = d.closest(".th").dataset.v; if(ED.delV[id]) delete ED.delV[id]; else ED.delV[id] = 1; save(); render(); return; }
  if(m){ const id = m.closest(".row").dataset.id, c = DATA.find(x => x.id === id); if(m.dataset.mv === c.g) delete ED.move[id]; else ED.move[id] = m.dataset.mv; save(); render(); }
});
$("undo").onclick = () => { const b = $("undo"); if(!b.dataset.arm){ b.dataset.arm = 1; b.textContent = "한 번 더 누르면 되돌림"; setTimeout(() => { delete b.dataset.arm; b.textContent = "전부 되돌리기"; }, 3000); return; }
  ED = {move:{}, delV:{}}; save(); delete b.dataset.arm; b.textContent = "전부 되돌리기"; render(); };
$("copy").onclick = async () => {
  const nm = id => (DATA.find(c => c.id === id) || {}).name || "";
  const vn = id => { for(const c of DATA){ const v = c.p.find(x => x.id === id); if(v) return c.name + " / " + (v.t || "").slice(0, 30); } return ""; };
  const mv = Object.entries(ED.move), dv = Object.keys(ED.delV);
  const txt = "터진 영상 수정 — 채널 " + mv.length + "건, 영상 삭제 " + dv.length + "건\n" +
    mv.map(([id, g]) => "채널\t" + g + "\t" + id + "\t" + nm(id)).join("\n") + (mv.length ? "\n" : "") +
    dv.map(id => "영상삭제\t" + id + "\t" + vn(id)).join("\n");
  const t = $("toast"), o = $("outbox");
  try{ await navigator.clipboard.writeText(txt); t.textContent = "복사됨 — 대화창에 붙여 넣어 주세요"; }
  catch(e){ o.style.display = "block"; o.value = txt; o.select(); t.textContent = "아래 칸 내용을 복사해 주세요"; }
  t.style.display = "block"; setTimeout(() => t.style.display = "none", 2500);
};
render();
</script></body></html>'''
HTML = HTML.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")).replace("__NV__", format(tot, ","))
io.open(M + "채널별_터진영상.html", "w", encoding="utf-8").write(HTML)
