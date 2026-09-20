# 원문형 스파인 검수 페이지 — 368개를 유형별로 펼쳐 버릴 것을 고른다 (2026-09-21)
#
# 왜 별도 도구인가: spinepage.py는 4유형만·생성 대본이 있어야 돌고,
# sample5page.py는 씨앗 제품별 묶음이다. 핸드오프 ⏭1번("버릴 스파인 고르기")은
# **스파인 전수**를 유형별로 봐야 해서 입력이 다르다(덤프 JSON 한 개).
#
# 쓰기: python tools/spine_presets/reviewpage.py <덤프.json> <출력.html>
import json, html, sys, collections

e = lambda s: html.escape(str(s or ""))
rows = json.load(open(sys.argv[1], encoding="utf-8"))


def origin(r):
    """원문형 표식 — backbone_assemble.spine_origin과 같은 판정(0순위-B: 같은 판단 두 벌 금지)."""
    try:
        t = json.loads(r.get("templates_json") or "{}")
    except Exception:                      # noqa: BLE001
        return None
    o = t.get("_origin")
    return o if isinstance(o, dict) and o.get("cells") else None


def tone(r):
    try:
        return json.loads(r.get("voice_json") or "{}").get("tone") or ""
    except Exception:                      # noqa: BLE001
        return ""


def fits(r):
    try:
        return json.loads(r.get("fit_categories_json") or "[]")
    except Exception:                      # noqa: BLE001
        return []


og = [r for r in rows if origin(r)]
by = collections.OrderedDict()
for r in og:
    for f in (fits(r) or ["(유형없음)"]):
        by.setdefault(f, []).append(r)
# 많은 유형부터 — 약한 유형(정체의문 6개)이 끝에 모여 보강 대상이 눈에 띈다
by = collections.OrderedDict(sorted(by.items(), key=lambda kv: -len(kv[1])))

nav = " · ".join('<a href="#t%d">%s <b>%d</b></a>' % (i, e(k), len(v))
                 for i, (k, v) in enumerate(by.items()))
secs = []
for i, (typ, lst) in enumerate(by.items()):
    lst = sorted(lst, key=lambda r: -(origin(r).get("views") or 0))
    cards = []
    for r in lst:
        o = origin(r)
        cells = "".join('<tr><td class="r">%s</td><td>%s</td></tr>' % (e(c.get("role")), e(c.get("text")))
                        for c in o.get("cells", []))
        cards.append(
            '<details class="sp" id="s%d"><summary>'
            '<span class="id">#%d</span> <b>%s</b>'
            '<span class="sub">%s · 조회 %s · @%s · %d칸</span></summary>'
            '<div class="body"><div class="hk">훅 고정틀: <code>%s</code></div>'
            '<table>%s</table></div></details>'
            % (r["id"], r["id"], e(r.get("name")), e(tone(r)),
               format(o.get("views") or 0, ","), e(o.get("user")), len(o.get("cells") or []),
               e(o.get("hook_tpl")), cells))
    secs.append('<section id="t%d"><h2>%s <span class="sub">%d개</span></h2>%s</section>'
                % (i, e(typ), len(lst), "".join(cards)))

open(sys.argv[2], "w", encoding="utf-8").write("""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>원문형 스파인 검수</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#b4540a;--hit:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c;--hit:#26262a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}
h2{font-size:20px;margin:30px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--acc)}
.sub{color:var(--sub);font-size:13px;font-weight:400;margin-left:8px}
nav{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:14px 0 8px;font-size:14px;line-height:2}
nav a{color:var(--acc);text-decoration:none}nav a:hover{text-decoration:underline}
.sp{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:6px 0}
.sp summary{padding:9px 13px;cursor:pointer;font-size:15px}.sp summary::marker{color:var(--sub)}
.id{color:var(--sub);font-variant-numeric:tabular-nums;margin-right:6px;font-size:13px}
.body{padding:0 13px 12px}.hk{font-size:13px;color:var(--sub);margin:2px 0 8px}
code{background:var(--hit);padding:1px 6px;border-radius:5px;font-size:13px;color:var(--acc)}
table{border-collapse:collapse;width:100%;background:var(--hit);border-radius:8px;overflow:hidden}
td{padding:5px 9px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
td.r{white-space:nowrap;color:var(--sub);width:58px;font-size:13px}
.lead{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;padding:12px 14px;margin:12px 0;font-size:14.5px}
</style></head><body><main>
<h1>원문형 스파인 검수 — 368개</h1>
<p class="sub">히트작 원문 한 편 = 스파인 한 개. 버릴 것의 <b>#번호</b>를 알려주시면 뺍니다. 남는 것만 approved로 올립니다.</p>
<div class="lead">지금 전부 <b>pending</b>(대기)이라 고객에게는 안 나갑니다. 유형을 눌러 펼치고, 원문이 어색하거나
제품을 못 갈아끼울 것 같은 스파인의 번호를 적어 주세요.</div>
<nav>""" + nav + "</nav>" + "\n".join(secs) + "</main></body></html>")
print("ok")
