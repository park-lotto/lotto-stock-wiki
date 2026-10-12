# -*- coding: utf-8 -*-
import re, json, html, collections, sys
OUT = sys.argv[1]
def words(t): return re.sub(r"[^\w\uac00-\ud7a3\s]", " ", t).split()
def grams(ws, n=6): return {" ".join(ws[i:i+n]) for i in range(max(0, len(ws)-n+1))}
WORKS = [("7f7d2393eb0b", "7f7d", "두피 액체빗", "반말 소개체 · 발명품형 · 끝을 끊어 반복재생"),
         ("667ffd60408e", "667f", "기차 케이크", "엄마 1인칭 존댓말 · 사연형 · 댓글 CTA"),
         ("dbddcce899bb", "dbdd", "빈티지 미니 카메라", "질문형 과장 · 수치(3만원·수천만 조회) 있는 씨앗")]
MODELS = [("31lite", "gemini-3.1-flash-lite", "★지금 필자(무료) 3.1 Flash-Lite", (0.25, 1.5)),
          ("35flash", "gemini-3.5-flash", "Gemini 3.5 Flash", (1.5, 9.0)),
          ("36flash", "gemini-3.6-flash", "Gemini 3.6 Flash", (0.75, 3.75)),
          ("37flash", "gemini-3.7-flash", "Gemini 3.7 Flash", (0.75, 3.75))]
usage = collections.defaultdict(dict)
for r in json.load(open("usage.json")):
    usage[(r["model"], r["work"])][r["run"]] = r
def mark(line, sgrams):
    """씨앗과 6어절 넘게 같은 구간을 노랗게."""
    ws = line.split(); hit = [False]*len(ws); norm = [re.sub(r"[^\w\uac00-\ud7a3]", "", w) for w in ws]
    for i in range(len(ws)-5):
        if " ".join(norm[i:i+6]) in sgrams:
            for k in range(i, i+6): hit[k] = True
    out, i = [], 0
    while i < len(ws):
        j = i
        while j < len(ws) and hit[j] == hit[i]: j += 1
        seg = html.escape(" ".join(ws[i:j]))
        out.append('<mark>%s</mark>' % seg if hit[i] else seg); i = j
    return " ".join(out)
secs = []; summ = collections.defaultdict(lambda: collections.defaultdict(list))
for full, short, name, kind in WORKS:
    p = open("prompt_%s.txt" % full, encoding="utf-8").read()
    seed = p[p.index("[씨앗]\n")+5:p.index("[이 제품]")].strip()
    srows = [re.match(r"^\[([^\]]+)\]\s*(.*)$", l).groups() for l in seed.split("\n") if l.strip()]
    sg = grams(words(" ".join(t for _, t in srows[1:])))
    cards = ['<div class="card seed"><h3>씨앗 원문 <small>(터진 영상이 실제로 한 말)</small></h3>'
             + "".join('<p><b class="role">%s</b>%s</p>' % (html.escape(r), html.escape(t)) for r, t in srows) + '</div>']
    for mk, mid, mname, (pi, po) in MODELS:
        for run in (1, 2):
            ls = [l for l in open("o_%s_%s_%d.txt" % (mk, short, run), encoding="utf-8").read().strip().split("\n") if l.strip()]
            og = grams(words(" ".join(ls[1:]))); ov = 100*len(og & sg)/max(1, len(og))
            u = usage[(mid, full)][run]; cost = u["in"]*pi/1e6 + (u["out"]+u["think"])*po/1e6
            summ[mid]["ov"].append(ov); summ[mid]["sec"].append(u["sec"]); summ[mid]["cost"].append(cost); summ[mid]["think"].append(u["think"])
            body = "".join("<p>%s</p>" % (html.escape(l) if k == 0 else mark(l, sg)) for k, l in enumerate(ls))
            warn = ' class="bad"' if ov >= 10 else ""
            cards.append('<div class="card m%s"><h3>%s <small>%d회차</small></h3>%s'
                         '<div class="meta"><span>%.0f초</span><span>생각 %s토큰</span><span>$%.4f</span><span%s>씨앗 베낌 %.1f%%</span><span>%d줄 / 씨앗 %d줄</span></div></div>'
                         % (mk[:2], mname, run, body, u["sec"], format(u["think"], ","), cost, warn, ov, len(ls), len(srows)))
    secs.append('<section><h2>%s</h2><div class="kind">%s</div><div class="grid">%s</div></section>' % (html.escape(name), html.escape(kind), "".join(cards)))
rows = ""
for mk, mid, mname, _ in MODELS:
    s = summ[mid]; n = len(s["ov"]); ss = sorted(s["sec"]); c = sum(s["cost"])/n
    rows += "<tr><td>%s</td><td>%.0f초 <small>(최대 %.0f초)</small></td><td>%s</td><td>$%.4f</td><td>$%.0f</td><td>%.1f%% <small>(최대 %.1f%%)</small></td></tr>" % (
        mname, ss[n//2], ss[-1], format(int(sum(s["think"])/n), ","), c, c*429*30, sum(s["ov"])/n, max(s["ov"]))
page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>대본 필자 비교</title><style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#1c1b19;--sub:#6b675f;--line:#e2ded4;--a35:#b4532a;--a36:#1f6f5c;--a37:#2a4fb4;--seed:#efe9da;--mark:#ffe08a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.75 "Pretendard","Malgun Gothic",sans-serif}
header{padding:28px 20px 8px;max-width:1500px;margin:0 auto}h1{font-size:28px;margin:0 0 6px}header p{margin:4px 0;color:var(--sub)}
main{max-width:1500px;margin:0 auto;padding:0 20px 60px}
table{border-collapse:collapse;width:100%%;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:14px 0 8px}
th,td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line)}th{background:#ece7da;font-size:15px}tr:last-child td{border-bottom:0}small{color:var(--sub);font-weight:400}
section{margin-top:40px}h2{font-size:24px;margin:0;border-left:6px solid var(--ink);padding-left:12px}.kind{color:var(--sub);margin:4px 0 14px 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;border-top:6px solid var(--line)}
.card h3{margin:0 0 8px;font-size:18px}.card p{margin:0 0 9px}.seed{background:var(--seed);grid-column:1/-1}.seed p{margin:0 0 5px}
.role{display:inline-block;min-width:3.6em;color:var(--sub);font-weight:600;font-size:14px}
.m31{border-top-color:#8a1c0c;background:#fff6f4}.m35{border-top-color:var(--a35)}.m36{border-top-color:var(--a36)}.m37{border-top-color:var(--a37)}
mark{background:var(--mark);padding:0 2px;border-radius:3px}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);font-size:14px;color:var(--sub)}
.meta span{background:#f1eee6;border-radius:999px;padding:2px 10px}.meta .bad{background:#ffd9d2;color:#8a1c0c;font-weight:700}
.note{background:#fff8e1;border:1px solid #ecd98a;border-radius:12px;padding:12px 16px;margin-top:12px}
</style></head><body><header><h1>대본 필자 비교 — 지금 필자(무료) vs Gemini 3.5 · 3.6 · 3.7 Flash</h1>
<p>2026-09-21 · Vertex AI(사장님 구글 클라우드) · 같은 지시문 · 재료 3건 × 모델 4개 × 2회 = 24편</p>
<p>지시문은 "자료를 다 읽고 한 편 써라 / 훅은 씨앗 그대로 / 관용구만 남기고 나머지는 새로 써라 / 재료에 없는 건 지어내지 마라".</p></header><main>
<table><tr><th>모델</th><th>걸린 시간(중간값)</th><th>생각 토큰 평균</th><th>1편 비용</th><th>한 달(하루 429편)</th><th>씨앗 베낌 평균</th></tr>%s</table>
<div class="note"><b>노란 형광</b> = 씨앗 원문과 6어절 넘게 글자 그대로 같은 구간(베낀 곳). 비용은 구글 AI Studio 공식 단가 기준 어림이고 Vertex 단가와 같은지는 확인 전입니다. 3.6·3.7 단가는 2026-12-31까지의 할인가(이후 2배).</div>
%s</main></body></html>""" % (rows, "".join(secs))
open(OUT, "w", encoding="utf-8", newline="\n").write(page)
print("written", OUT, len(page))
