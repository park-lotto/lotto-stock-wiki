"""한 유형의 세부 갈래 페이지 — <out>/<name>_subtypes.json({갈래: [id…]}) + tags.jsonl + transcripts.json → HTML.
갈래마다 성적(편수·10만+·중앙·최고)과 편마다 첫 줄 · 줄별 칸 · 원문을 펼쳐 볼 수 있게 보여 준다(버텍스 0).
사용: py subtype_page.py --slug homedesignnote --name question --title "질문도발 세부 갈래" --out <html>"""
import argparse, html, json, os, statistics

from script_calcopy import load_json, out_dir

CSS = """:root{--bg:#f3f2ee;--paper:#fff;--ink:#1d1b18;--muted:#6a655c;--line:#dcd8cf;--frost:#ece9e1;--acc:#0f6e5d;--acc-soft:#e1f1ec;--hot:#b4401a;--hot-soft:#fbe8df;
--fd:"Black Han Sans","IBM Plex Sans KR",sans-serif;--fb:"IBM Plex Sans KR","Malgun Gothic",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141310;--paper:#1d1b18;--ink:#ebe7df;--muted:#a49e93;--line:#38342d;--frost:#26231e;--acc:#5cc4ab;--acc-soft:#1b3530;--hot:#f39a72;--hot-soft:#3d2219;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--fb);font-size:14.5px;line-height:1.6}
.wrap{max-width:1100px;margin:0 auto;padding:20px 16px 60px}h1{font-family:var(--fd);font-weight:400;font-size:28px;margin:0 0 4px}
h2{font-family:var(--fd);font-weight:400;font-size:22px;margin:0 0 4px}.mut{color:var(--muted);font-size:12.5px}
section{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:18px}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}th{background:var(--frost)}
.lead{background:var(--acc-soft);border-radius:10px;padding:10px 14px;margin-top:12px}
details{border-top:1px solid var(--line);padding:6px 0}summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}
.v{display:inline-block;min-width:58px;font-variant-numeric:tabular-nums;color:var(--muted)}.hit .v{color:var(--hot);font-weight:700}
.hit summary{background:var(--hot-soft);border-radius:6px;padding:2px 6px}
ol{margin:6px 0 4px;padding-left:22px}li{margin:2px 0}.beat{font-size:11px;color:var(--acc);background:var(--acc-soft);border-radius:4px;padding:0 5px;margin-right:4px}
.raw{font-size:12.5px;color:var(--muted);margin:4px 0 0}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--lead", default="")
    ap.add_argument("--hit", type=int, default=100000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = out_dir(a.slug)
    subs = load_json(os.path.join(d, a.name + "_subtypes.json"), {})
    tags = {}
    for l in open(os.path.join(d, "tags.jsonl"), encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            tags[r["id"]] = r
    tr = load_json(os.path.join(d, "transcripts.json"), {})
    e = html.escape
    rows, secs = [], []
    order = sorted(subs.items(), key=lambda kv: -statistics.median([tags[i]["views"] for i in kv[1]]))
    for k, ids in order:
        rs = sorted((tags[i] for i in ids), key=lambda r: -r["views"])
        vv = [r["views"] for r in rs]
        nh = sum(v >= a.hit for v in vv)
        rows.append("<tr><td><a href='#s%d'>%s</a></td><td>%d</td><td>%d</td><td>%.1f만</td><td>%d만</td></tr>" % (
            len(rows), e(k), len(rs), nh, statistics.median(vv) / 10000, max(vv) // 10000))
        items = []
        for r in rs:
            body = "".join("<li><span class='beat'>%s</span>%s</li>" % (e(l["beat"]), e(l["text"])) for l in r["lines"])
            items.append("<details class='%s'><summary><span class='v'>%s만</span> %s</summary><ol>%s</ol><p class='raw'>스토리: %s · 화자: %s · CTA: %s</p></details>" % (
                "hit" if r["views"] >= a.hit else "", format(r["views"] // 10000, ","), e(r["lines"][0]["text"]), body,
                e(r["story"].get("arc", "")), e(r["narrator"].get("persona", "")), e(r["cta"].get("kind", ""))))
        secs.append("<section id='s%d'><h2>%s</h2><p class='mut'>%d편 · 10만+ %d편 · 조회 중앙 %.1f만 · 최고 %d만 — 줄을 누르면 대본 전체</p>%s</section>" % (
            len(secs), e(k), len(rs), nh, statistics.median(vv) / 10000, max(vv) // 10000, "".join(items)))
    page = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;700&family=Black+Han+Sans&display=swap"><style>%s</style></head>
<body><div class="wrap"><h1>%s</h1><p class="mut">%s · 첫 줄 모양(원문 규칙)으로 나눈 갈래 · 빨간 줄 = 조회 %d만 이상</p>%s
<section><h2>갈래별 성적</h2><div class="tbl"><table><tr><th>갈래</th><th>편수</th><th>10만+</th><th>조회 중앙</th><th>최고</th></tr>%s</table></div></section>%s</div></body></html>""" % (
        e(a.title), CSS, e(a.title), e(a.slug), a.hit // 10000, ("<div class='lead'>%s</div>" % a.lead) if a.lead else "", "".join(rows), "".join(secs))
    open(a.out, "w", encoding="utf-8").write(page)
    print(a.out)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
