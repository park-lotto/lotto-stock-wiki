import json, html, sys
R = json.load(open(sys.argv[1], encoding="utf-8"))
e = lambda s: html.escape(str(s or ""))
b = []
for r in R:
    ok = "".join('<div class="card"><div class="ph">%s</div><ol>%s</ol></div>'
                 % (e(o["name"]), "".join("<li>%s</li>" % e(x) for x in o["script"].split("\n") if x.strip()))
                 for o in r["ok"])
    sk = "".join('<li><b>%s</b> — %s</li>' % (e(t["spine"]), e(t["why"])) for t in (r.get("skipped") or []))
    b.append('<section><h2>%s <span class="sub">통과 %d편</span></h2>%s'
             '<details class="skip"><summary>안 쓴 스파인 %d개 — 왜 뺐나</summary><ul>%s</ul></details></section>'
             % (e(r["product"]), len(r["ok"]), ok, len(r.get("skipped") or []), sk))
open(sys.argv[2], "w", encoding="utf-8").write("""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>통과본만 고르기</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#b4540a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:900px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:26px 0 8px}
.sub{color:var(--sub);font-size:14px;font-weight:400}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:8px 0}
.ph{color:var(--acc);font-weight:600;font-size:14px}ol{margin:6px 0;padding-left:20px}li{margin:3px 0}
.skip{margin:6px 0 0;color:var(--sub);font-size:14px}.skip b{color:var(--ink)}
</style></head><body><main><h1>대본 — 스파인 6개를 돌려 통과본만</h1>
<p class="sub">인물·상황 검사를 통과한 대본만 싣습니다. 통과 못 한 스파인은 이유와 함께 접혀 있습니다.</p>
""" + "\n".join(b) + "</main></body></html>")
print("ok")
