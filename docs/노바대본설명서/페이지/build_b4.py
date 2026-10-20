"""4차 판 대본 20편 페이지 — out/B4fix_*.json + 검사 결과 → 바탕화면/대본_4차_5개씩.html"""
import html, json, os, re, sys

AB = r"C:\Users\TheRose\Desktop\로또의 주식\.tracks\노바대본설명서\docs\노바대본설명서\ab"
CARDS = os.path.join(AB, "..", "cards_v4")
SIDE = sys.argv[1] if len(sys.argv) > 1 else "B4fix"
OUT = os.path.join(r"C:\Users\TheRose\Desktop", "대본_%s.html" % (sys.argv[2] if len(sys.argv) > 2 else "4차_5개씩"))
NAME = {"even": "이븐쇼핑", "jungche": "정체숨김", "hdn": "두유노홈디노"}
CIDS = os.environ.get("CIDS", "even,jungche").split(",")
SRC = {"glasspaint": "유리 페인트", "wrap": "밀착랩"}
A_FIRST = {("even", "glasspaint"): "A_even_glasspaint", ("even", "wrap"): "A_even_wrap",
           ("jungche", "glasspaint"): "A_55_glasspaint", ("jungche", "wrap"): "A_55_wrap", ("hdn", "glasspaint"): "A_hdn_glasspaint", ("hdn", "wrap"): "A_hdn_wrap"}

pts = json.load(open(os.path.join(AB, "points_%s.json" % SIDE), encoding="utf-8"))
awk = {x["key"]: x for x in json.load(open(os.path.join(AB, "awkward_%s.json" % SIDE), encoding="utf-8"))["flags"]}
fl = {(r["id"], r["src"], r["i"]): r for r in json.load(open(os.path.join(AB, "first_line_%s.json" % SIDE), encoding="utf-8"))["rows"]} \
    if os.path.exists(os.path.join(AB, "first_line_%s.json" % SIDE)) else {}
e = html.escape


def a_lines(cid, src):
    d = json.load(open(os.path.join(AB, "out", A_FIRST[(cid, src)] + ".json"), encoding="utf-8"))
    ls = d["lines"] if "lines" in d else d["drafts"][0]["lines"]
    return [l["text"] if isinstance(l, dict) else l for l in ls]


sections = []
for cid in CIDS:
    pm = json.load(open(os.path.join(CARDS, NAME[cid] + ".json"), encoding="utf-8"))["ing_wow"]["이 스타일 칸"]
    ing = set(pm["ing"]); wow = set(sum((k.split("|") for k in pm["wow"]), []))
    for src in ["glasspaint", "wrap"]:
        base = "%s_%s_%s" % (SIDE, cid, src)
        d = json.load(open(os.path.join(AB, "out", base + ".json"), encoding="utf-8"))
        cards = []
        for i, dd in enumerate(d["drafts"]):
            key = "%s#%d" % (base, i + 1)
            rows = []
            for j, l in enumerate(dd["lines"]):
                tags = []
                if l.get("slot") in ing and j < max(3, len(dd["lines"]) // 3 + 1):
                    tags.append('<span class="tag ing">잉</span>')
                if l.get("slot") in wow and re.match(r"(이게|심지어|근데|진짜|하지만)", l["text"]):
                    tags.append('<span class="tag wow">와우</span>')
                fix = ('<div class="fix">고침 전: %s</div>' % e(l["fixed_from"])) if l.get("fixed_from") else ""
                still = ('<div class="still">남은 어색함 → %s</div>' % e(awk[key]["fix"])) if key in awk and re.sub(r"\s", "", awk[key]["line"]) == re.sub(r"\s", "", l["text"]) else ""
                rows.append('<li class="%s"><span class="slot">%s</span>%s %s%s%s</li>' % ("fixed" if fix else "", e(l.get("slot", "")), "".join(tags), e(l["text"]), fix, still))
            probs = pts.get(key) or []
            f = fl.get((cid, src, i))
            if f and not f["keep"] and cid != "hdn":   # 두유노 틀은 문장형이라 낱말 일치로 못 잰다 — 사람이 읽는다
                probs = probs + ["첫 줄 틀 벗어남"]
            badge = ('<span class="bad">%s</span>' % e(" · ".join(probs))) if probs else '<span class="ok">잉·와우·첫 줄 통과</span>'
            cards.append('<article class="draft"><header><b>시안 %d</b> <span class="ht">%s</span> %s</header><ol>%s</ol></article>'
                         % (i + 1, e(dd.get("hook_type") or ""), badge, "".join(rows)))
        al = a_lines(cid, src)
        sections.append('<section><h2>%s · %s</h2><details class="a"><summary>비교: 지금 라이브(A) 대본</summary><ol>%s</ol></details><div class="grid">%s</div></section>'
                        % (NAME[cid], SRC[src], "".join("<li>%s</li>" % e(x) for x in al), "".join(cards)))

if len(sys.argv) > 3:   # 반복 측정 — 같은 입력 3번
    rows = []
    for r in sys.argv[3].split(","):
        d = json.load(open(os.path.join(AB, "out", r + "_even_wrap.json"), encoding="utf-8"))
        for i, dd in enumerate(d["drafts"]):
            ls = [l["text"] for l in dd["lines"]]
            rows.append("<tr><td>%s 시안%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (e(r), i + 1, e(ls[0]), e(ls[1]), e(ls[-1])))
    sections.append('<section><h2>같은 소재를 3번 따로 돌리면 (이븐쇼핑 · 밀착랩 · 15편)</h2><div class="tbl"><table><tr><th>회차</th><th>첫 줄</th><th>미끼</th><th>마무리</th></tr>%s</table></div></section>' % "".join(rows))
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.environ.get("TPL", "b4_tpl.html")), encoding="utf-8").read()
open(OUT, "w", encoding="utf-8").write(tpl.replace("@@BODY@@", "\n".join(sections)))
print(OUT)
