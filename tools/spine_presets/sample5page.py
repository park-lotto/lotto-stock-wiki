import json, html, sys
R = json.load(open(sys.argv[1], encoding="utf-8"))
e = lambda s: html.escape(str(s or ""))
b = []
for r in R:
    cards = ""
    for o in r["ok"]:
        orig = "".join("<tr><td class='r'>%s</td><td>%s</td></tr>" % (e(c.get("role")), e(c.get("text")))
                       for c in (o.get("origin") or []))
        cards += ('<div class="card"><div class="ph">%s</div>'
                  '<div class="grid"><div><h4>이 스파인이 담은 히트작 원문</h4><table>%s</table></div>'
                  '<div><h4>이 제품으로 쓴 대본</h4><ol>%s</ol></div></div></div>'
                  % (e(o["name"]), orig, "".join("<li>%s</li>" % e(x) for x in o["script"].split("\n") if x.strip())))
    sk = "".join("<li><b>%s</b> — %s</li>" % (e(t.get("spine")), e(t.get("why"))) for t in (r.get("skipped") or []))
    b.append('<section><h2>%s <span class="sub">씨앗 유형 %s · 후보 %d개 중 통과 %d편</span></h2>%s'
             '<details class="skip"><summary>안 쓴 스파인 %d개 — 왜 뺐나</summary><ul>%s</ul></details></section>'
             % (e(r["product"]), e(r["type"] or "판정 실패"), r["tried"], len(r["ok"]), cards,
                len(r.get("skipped") or []), sk))
open(sys.argv[2], "w", encoding="utf-8").write("""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>대본 샘플 — 원문형 스파인</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#b4540a;--hit:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c;--hit:#26262a}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:1150px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:26px 0 8px}
h4{font-size:13px;color:var(--sub);margin:0 0 4px}.sub{color:var(--sub);font-size:14px;font-weight:400}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:8px 0}
.ph{color:var(--acc);font-weight:600;font-size:14px;margin-bottom:6px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}table{border-collapse:collapse;width:100%;background:var(--hit);border-radius:8px}
td{padding:4px 8px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}td.r{white-space:nowrap;color:var(--sub);width:48px}
ol{margin:4px 0;padding-left:20px}li{margin:3px 0}.skip{color:var(--sub);font-size:14px;margin-top:4px}.skip b{color:var(--ink)}
@media (max-width:760px){.grid{grid-template-columns:1fr}}
</style></head><body><main><h1>대본 샘플 — 씨앗 유형 자동 배정</h1>
<p class="sub">스파인 374개 중 씨앗 유형에 맞는 것만 후보로 쓰고, 인물·상황 검사를 통과한 대본만 실었습니다. 버릴 스파인을 알려주시면 뺍니다.</p>
""" + "\n".join(b) + "</main></body></html>")
print("ok")
