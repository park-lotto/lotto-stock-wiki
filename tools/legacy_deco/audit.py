"""옛 피팅룸(6단계 패널, produce.html data-step=3) 걷어내기 감사 — 관제 058 C단계.
패널 안 id가 JS 어디서 쓰이나 / 함수가 패널 밖에서 불리나를 센다. 지울 것은 '패널 안에서만 쓰이는 것'뿐."""
import re, sys, json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / "shopping_shorts/static/produce.html"
s = P.read_text(encoding="utf-8")
lines = s.splitlines()
a = next(i for i,l in enumerate(lines) if '<section class="panel" data-step="3">' in l)
b = next(i for i,l in enumerate(lines) if '<section class="panel" data-step="4">' in l)
panel = "\n".join(lines[a:b]); rest = "\n".join(lines[:a] + lines[b:])
ids = re.findall(r'id="([^"]+)"', panel)
# 패널 안 onclick 등에 적힌 함수
panel_calls = set(re.findall(r'\b([A-Za-z_$][\w$]*)\s*\(', panel))
# JS 함수 정의 전체
defs = re.findall(r'^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(', rest, re.M)
def_set = set(defs)
js_only = rest
def refs(name):  # 정의 줄 제외한 참조 수
    return len(re.findall(r'(?<![\w$.])' + re.escape(name) + r'(?![\w$])', js_only)) - len(re.findall(r'function\s+' + re.escape(name) + r'\s*\(', js_only))
id_use = {i: len(re.findall(r"getElementById\(['\"]" + re.escape(i) + r"['\"]\)|#" + re.escape(i) + r"\b|querySelector\(['\"]#" + re.escape(i), rest)) for i in ids}
report = {
  "panel_lines": b - a, "ids": len(ids),
  "ids_unused_in_js": sorted(i for i,n in id_use.items() if n == 0),
  "ids_used_in_js": {i:n for i,n in id_use.items() if n},
  "panel_only_funcs": sorted(f for f in panel_calls if f in def_set and refs(f) == 0),
  "panel_funcs_also_used_elsewhere": sorted(f for f in panel_calls if f in def_set and refs(f) > 0),
}
if "--json" in sys.argv:
    print(json.dumps(report, ensure_ascii=False, indent=1))
else:
    print(f"패널 {report['panel_lines']}줄 · id {report['ids']}개 · JS가 안 쓰는 id {len(report['ids_unused_in_js'])}개 · JS가 쓰는 id {len(report['ids_used_in_js'])}개")
    print(f"패널 onclick 함수 중 패널 밖에서 안 불리는 것 {len(report['panel_only_funcs'])}개 / 밖에서도 불리는 것 {len(report['panel_funcs_also_used_elsewhere'])}개")
    print("밖에서도 불림:", ", ".join(report["panel_funcs_also_used_elsewhere"]))

# ── 연쇄 참조: 함수 본문을 떼어내 "누가 누구를 부르나" 그물을 만들고, 옛 패널 밖의 뿌리에서 닿는 함수만 산 것으로 센다 ──
def _func_bodies(js):
    out = {}
    for m in re.finditer(r'^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(', js, re.M):
        name, start = m.group(1), m.start()
        i = js.index('{', m.end()); depth = 0
        for k in range(i, len(js)):
            if js[k] == '{': depth += 1
            elif js[k] == '}':
                depth -= 1
                if depth == 0: break
        out[name] = (start, k + 1, js[start:k + 1])
    return out
bodies = _func_bodies(rest)
spans = sorted((v[0], v[1]) for v in bodies.values())
# 간단히: 최상위 코드 = rest에서 함수 본문을 전부 뺀 것
tl = rest
for st,en in sorted(spans, reverse=True):
    tl = tl[:st] + tl[en:]
def calls_in(text):
    # ★괄호 없는 참조(setTimeout(fn)·{k:fn}·addEventListener('x',fn))도 산 것으로 센다 — 놓치면 ReferenceError
    return {n for n in re.findall(r'(?<![\w$.])([A-Za-z_$][\w$]*)(?![\w$])', text) if n in bodies}
graph = {k: calls_in(v[2]) for k,v in bodies.items()}
# 뿌리: 최상위 코드에서 부르는 함수 + 다른 단계 패널(HTML, 패널3 제외)의 onclick + 외부 JS(scene-style-produce.js 등)가 부르는 window 함수
html_other = "\n".join(lines[:a] + lines[b:])
html_other_nojs = re.sub(r'<script[\s\S]*?</script>', '', html_other)
roots = calls_in(tl) | calls_in(html_other_nojs)
for extra in (ROOT/"shopping_shorts/static/scene-style-produce.js",):
    roots |= calls_in(extra.read_text(encoding="utf-8"))
roots -= set(report["panel_only_funcs"])
live = set(); stack = list(roots)
while stack:
    f = stack.pop()
    if f in live: continue
    live.add(f); stack.extend(graph.get(f, ()))
dead = sorted(set(bodies) - live)
dead_panel = sorted(f for f in dead if f in panel_calls or any(f in graph.get(g, ()) for g in panel_calls))
print(f"\n함수 전체 {len(bodies)}개 · 뿌리에서 닿는 함수 {len(live)}개 · 안 닿는(죽은) 함수 {len(dead)}개")
print(f"  그중 옛 패널과 엮인 죽은 함수 {len(dead_panel)}개 · 줄수 합 {sum(bodies[f][2].count(chr(10))+1 for f in dead_panel)}")
if "--list" in sys.argv:
    print("\n".join(dead))
