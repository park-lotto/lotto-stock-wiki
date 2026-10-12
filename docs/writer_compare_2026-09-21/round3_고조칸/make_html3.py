# -*- coding: utf-8 -*-
import re, html, sys
OUT = sys.argv[1]
def words(t): return re.sub(r"[^\w\uac00-\ud7a3\s]", " ", t).split()
def grams(ws, n=6): return {" ".join(ws[i:i+n]) for i in range(max(0, len(ws)-n+1))}
CLIMAX = re.compile(r"^\s*(심지어|근데 진짜 미친 포인트는|진짜 충격적인\s?건)|심지어 ")
WORKS = [("7f7d2393eb0b", "7f7d", "두피 액체빗", "씨앗의 고조 = 남편 선물 → 재료엔 없는 이야기"),
         ("667ffd60408e", "667f", "기차 케이크", "씨앗의 고조 = 장난감으로 써도 됨·퀄리티"),
         ("dbddcce899bb", "dbdd", "빈티지 미니 카메라", "씨앗의 고조 = 셔터 쾌감 · 필름값 0원")]
NOTES = {("667f", "o2", 2): "마지막 CTA 칸이 빠짐(8칸→7칸)", ("dbdd", "o2", 1): "오타 '카메리'",
         ("dbdd", "o2", 2): "둘째 줄을 씨앗에서 통째로 복사 — 재료에 없는 수치(3만원·수천만 조회)까지 따라옴"}
def mark(line, sg):
    ws = line.split(); hit = [False]*len(ws); norm = [re.sub(r"[^\w\uac00-\ud7a3]", "", w) for w in ws]
    for i in range(len(ws)-5):
        if " ".join(norm[i:i+6]) in sg:
            for k in range(i, i+6): hit[k] = True
    out, i = [], 0
    while i < len(ws):
        j = i
        while j < len(ws) and hit[j] == hit[i]: j += 1
        seg = html.escape(" ".join(ws[i:j])); out.append('<mark>%s</mark>' % seg if hit[i] else seg); i = j
    return " ".join(out)
secs = []
for full, short, name, kind in WORKS:
    p = open("prompt_%s.txt" % full, encoding="utf-8").read()
    seed = p[p.index("[씨앗]\n")+5:p.index("[이 제품]")].strip()
    srows = [re.match(r"^\[([^\]]+)\]\s*(.*)$", l).groups() for l in seed.split("\n") if l.strip()]
    sg = grams(words(" ".join(t for _, t in srows[1:])))
    cards = ['<div class="card seed"><h3>씨앗 원문</h3>' + "".join(
        '<p class="%s"><b class="role">%s</b>%s</p>' % ("cx" if CLIMAX.search(t) else "", html.escape(r), html.escape(t)) for r, t in srows) + '</div>']
    for pref, label, cls in (("o", "고치기 전 지시문", "old"), ("o2", "★새 지시문 — 씨앗에 없는 특징을 고조 칸에", "new")):
        for run in (1, 2):
            ls = [l for l in open("%s_36flash_%s_%d.txt" % (pref, short, run), encoding="utf-8").read().strip().split("\n") if l.strip()]
            og = grams(words(" ".join(ls[1:]))); ov = 100*len(og & sg)/max(1, len(og))
            body = "".join('<p class="%s">%s</p>' % ("cx" if (k and CLIMAX.search(l)) else "", html.escape(l) if k == 0 else mark(l, sg)) for k, l in enumerate(ls))
            note = NOTES.get((short, pref, run))
            cards.append('<div class="card %s"><h3>%s <small>%d회차</small></h3>%s<div class="meta"><span%s>씨앗 베낌 %.1f%%</span><span>%d줄 / 씨앗 %d줄</span>%s</div></div>'
                         % (cls, label, run, body, ' class="bad"' if ov >= 10 else "", ov, len(ls), len(srows),
                            ('<span class="bad">⚠ %s</span>' % html.escape(note)) if note else ""))
    secs.append('<section><h2>%s</h2><div class="kind">%s</div><div class="grid">%s</div></section>' % (html.escape(name), html.escape(kind), "".join(cards)))
page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>고조 칸 시험 — Gemini 3.6 Flash</title><style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#1c1b19;--sub:#6b675f;--line:#e2ded4;--seed:#efe9da;--mark:#ffe08a;--cx:#dff3ea;--cxb:#1f6f5c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.8 "Pretendard","Malgun Gothic",sans-serif}
header,main{max-width:1500px;margin:0 auto;padding:0 20px}header{padding-top:28px}h1{font-size:28px;margin:0 0 6px}header p{margin:4px 0;color:var(--sub)}
.how{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:14px 0}.how b{color:var(--cxb)}
.legend span{display:inline-block;margin-right:14px}.sw{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:5px}
section{margin-top:40px}h2{font-size:24px;margin:0;border-left:6px solid var(--ink);padding-left:12px}.kind{color:var(--sub);margin:4px 0 14px 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;border-top:6px solid #b9b3a4}
.card h3{margin:0 0 8px;font-size:17px}.card p{margin:0 0 9px;padding:2px 6px;border-radius:6px}small{color:var(--sub);font-weight:400}
.seed{background:var(--seed);grid-column:1/-1}.new{border-top-color:var(--cxb)}.old{opacity:.92}
.role{display:inline-block;min-width:3.6em;color:var(--sub);font-weight:600;font-size:14px}
p.cx{background:var(--cx);border-left:4px solid var(--cxb)}mark{background:var(--mark);padding:0 2px;border-radius:3px}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);font-size:14px;color:var(--sub)}
.meta span{background:#f1eee6;border-radius:999px;padding:2px 10px}.meta .bad{background:#ffd9d2;color:#8a1c0c;font-weight:700}
main{padding-bottom:60px}</style></head><body><header><h1>고조 칸 시험 — 씨앗에 없는 특징을 '심지어·미친 포인트' 자리에</h1>
<p>2026-09-21 · Gemini 3.6 Flash(Vertex) · 재료 3건 × 지시문 2종 × 2회 = 12편</p>
<div class="how">새 지시문: 쓰기 전에 <b>① 씨앗이 이미 말한 특징</b>과 <b>② 재료 영상엔 나오는데 씨앗은 말하지 않은 특징</b>을 가르고, 앞 칸은 씨앗 흐름대로, <b>고조 칸에는 ②에서 가장 센 것</b>을 넣는다(뒤로 갈수록 더 센 것).
<div class="legend" style="margin-top:8px"><span><i class="sw" style="background:var(--cx);border-left:4px solid var(--cxb)"></i>고조 칸</span><span><i class="sw" style="background:var(--mark)"></i>씨앗과 6어절 넘게 글자 그대로 같은 곳(베낌)</span></div></div></header>
<main>%s</main></body></html>""" % "".join(secs)
open(OUT, "w", encoding="utf-8", newline="\n").write(page); print("written", len(page))
