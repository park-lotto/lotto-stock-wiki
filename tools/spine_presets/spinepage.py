# 원문형 스파인 보기 — 스파인(히트작 원문) + 그 스파인으로 뽑은 대본 (2026-09-20)
import json, html, sys, collections
R = json.load(open(sys.argv[1], encoding="utf-8"))
e = lambda s: html.escape(str(s or ""))
by = collections.OrderedDict()
for r in R:
    by.setdefault(r["spine_id"], []).append(r)
sec = []
for t in ["지인증언형", "제품정체형", "오용형", "발명품형"]:
    ids = [i for i, L in by.items() if L[0]["type"] == t]
    sec.append('<h2>%s <span class="sub">스파인 %d개</span></h2>' % (e(t), len(ids)))
    for i in ids:
        L = by[i]
        o = L[0]["origin"]
        orig = "".join('<tr><td class="r">%s</td><td>%s</td></tr>' % (e(c["role"]), e(c["text"])) for c in o.get("cells", []))
        outs = ""
        for r in L:
            lines = "".join("<li>%s</li>" % e(x) for x in (r["script"] or "").split("\n") if x.strip())
            outs += ('<div class="out"><div class="ph">%s</div>%s</div>'
                     % (e(r["product"]), ("<ol>%s</ol>" % lines) if lines else '<p class="bad">실패: %s</p>' % e(r["why"])))
        sec.append('<details class="sp"><summary><b>%s</b> <span class="sub">%s · %s회 · %s</span></summary>'
                   '<div class="grid"><div><h3>원문 (이 스파인의 틀)</h3><table>%s</table></div>'
                   '<div><h3>이 스파인으로 쓴 대본</h3>%s</div></div></details>'
                   % (e(L[0]["name"]), e(L[0]["tone"]), format(o.get("views", 0), ","), e(o.get("user")), orig, outs))
open(sys.argv[2], "w", encoding="utf-8").write("""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>원문형 스파인</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#b4540a;--hit:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c;--hit:#26262a}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:1150px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:20px;margin:28px 0 8px}h3{font-size:15px;margin:0 0 6px;color:var(--sub)}
.sub{color:var(--sub);font-size:14px;font-weight:400}.sp{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:10px 14px}
summary{cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:10px}
table{border-collapse:collapse;width:100%;background:var(--hit);border-radius:8px}td{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.r{white-space:nowrap;color:var(--sub);width:54px}.out{margin-bottom:12px}.ph{font-weight:600;color:var(--acc)}ol{margin:4px 0;padding-left:20px}li{margin:3px 0}
.bad{color:var(--acc);font-size:14px}.ok,.warn{font-size:13px;border:1px solid;border-radius:99px;padding:0 8px;margin-left:6px}.ok{color:#1a7f37}.warn{color:var(--acc)}@media (max-width:760px){.grid{grid-template-columns:1fr}}
</style></head><body><main><h1>원문형 스파인 — 히트작 한 편 = 스파인 한 개</h1>
<p class="sub">왼쪽이 스파인이 담은 히트작 원문(칸 표시), 오른쪽이 그 스파인으로 제품 2개에 쓴 대본. 전부 pending이라 고객에게는 안 나갑니다. 인물·상황 검사(같이 사는 사람에게 '놀러 왔다', 안 쓰는 사람에게 선물, 화자 바뀜)를 통과한 대본에 초록 표시가 붙습니다.</p>
""" + "\n".join(sec) + "</main></body></html>")
print("ok")
