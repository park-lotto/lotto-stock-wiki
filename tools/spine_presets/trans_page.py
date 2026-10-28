# transpose_hit.py 결과 → 히트작 원문 vs 새 대본 칸별 나란히 (2026-09-19)
import json, html, sys, re
R = json.load(open(sys.argv[1], encoding="utf-8"))
PROD = {"68dc7e13dc23": "카드형 접이식 볼펜", "26698eb0a362": "고단백 팬케이크", "bbb6bcbbbeb8": "벽걸이 수납함"}
e = lambda s: html.escape(str(s or ""))
body = []
for jid in dict.fromkeys(r["job"] for r in R):
    body.append(f'<h2>{e(PROD.get(jid, jid))}</h2>')
    for r in [r for r in R if r["job"] == jid]:
        who = "메종 홈디노" if r["hit_user"] == "maison_homedino" else r["hit_user"]
        dup = [c["role"] for c in r["cells"] if re.search(r"(.{6,})\s*\1", c["text"])]
        flags = r["flags"] + (["같은 말 반복: " + ",".join(dup)] if dup else [])
        fl = "".join(f'<span class="bad">{e(f)}</span>' for f in flags) or '<span class="ok">코드 검사 통과</span>'
        rows = "".join(f'<tr><td class="r">{e(h["role"])}</td><td class="h">{e(h["text"])}</td><td class="n">{e(n["text"] if n else "")}</td></tr>'
                       for h, n in zip(r["hit_cells"], r["cells"] + [None] * 9))
        body.append(f'<details class="sec" open><summary>틀: <b>{e(who)}</b> {r["hit_views"]:,}회 {fl}</summary>'
                    f'<div class="tw"><table><tr><th>칸</th><th>히트작 원문</th><th>새 대본</th></tr>{rows}</table></div></details>')
PAGE = open(sys.argv[3], encoding="utf-8").read() if len(sys.argv) > 3 else ""
open(sys.argv[2], "w", encoding="utf-8").write("""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>지인증언형 대본 시험</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--ok:#1a7f37;--bad:#c2410c;--hit:#f1efe9;--new:#fff6e8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--ok:#4ade80;--bad:#fb923c;--hit:#26262a;--new:#2a2116}}
:root[data-theme="dark"]{--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--ok:#4ade80;--bad:#fb923c;--hit:#26262a;--new:#2a2116}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"Malgun Gothic",sans-serif}main{max-width:1100px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 6px}.lead{color:var(--sub)}h2{margin:30px 0 8px;font-size:20px}.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:10px 0;padding:10px 14px}
summary{cursor:pointer}.ok,.bad{font-size:13px;border:1px solid;border-radius:99px;padding:0 8px;margin-left:6px}.ok{color:var(--ok)}.bad{color:var(--bad)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;margin-top:8px}td,th{padding:6px 10px;vertical-align:top;border-bottom:1px solid var(--line);text-align:left}th{color:var(--sub);font-weight:500}
td.r{white-space:nowrap;font-weight:600;width:60px}td.h{background:var(--hit);width:46%}td.n{background:var(--new)}
@media (max-width:640px){td.h,td.n{min-width:240px}}
</style></head><body><main><h1>지인증언형 — 히트작 한 편을 틀로 옮긴 대본</h1>
<p class="lead">방식: 히트작 한 편의 칸 순서·말투·연결어는 그대로, 제품 이야기만 새 제품 재료로 바꿔 씀. 제품 3개 × 히트작 3편(채이홈 631만 · 메종 58만 · 메종 52만). 왼쪽이 원문, 오른쪽이 새 대본. 렌더 없음.</p>
""" + "\n".join(body) + "</main></body></html>")
print("ok")
