# 스파인(대본 스타일) 보기 페이지 — 유형 → 스타일 → 칸별 문장틀 + 점검 결과
# 사용:  py spine_viewer.py <spines.json> <audit_out.txt> <out.html>
#   spines.json = 서버 spine 테이블 덤프(select * ... ) / audit_out.txt = audit_spines.py 출력
import sys, json, re, html

ROLE_KO = {"title": "제목(첫 3초)", "bait": "떡밥", "fame": "화제성", "reveal": "제품 공개", "limit": "기존 불편",
           "solve": "해결", "more": "추가 장점", "twist": "반전 포인트", "land": "마무리", "hook": "훅",
           "origin": "원래 용도", "misuse": "뜻밖의 사용", "result": "결과", "benefit": "장점", "good": "좋은 점",
           "howto": "사용법", "vs": "비교", "price": "가격", "pain": "불편함", "cta": "행동 유도",
           "situation": "상황", "escalation": "한 단계 더(고수)", "cases": "사용 사례(초보)", "notice": "눈치챔",
           "spread": "입소문", "scale": "화제 규모", "targets": "누구에게", "limit": "기존 불편", "proof": "증거", "feature": "특징"}


def load(sp, au):
    spines = json.load(open(sp, encoding="utf-8"))
    txt = open(au, encoding="utf-8").read()
    stat, defects = {}, {}
    for m in re.finditer(r"^\s*(\d+) .*?\|\s*(\d+) \|\s*(\d+) \|\s*(\d+) \|\s*(\d+)", txt, re.M):
        stat[int(m.group(1))] = dict(combos=int(m.group(2)), first_kinds=int(m.group(4)), first_top=int(m.group(5)))
    for m in re.finditer(r"^\s*\[(\d+)\] (.+)$", txt, re.M):
        defects.setdefault(int(m.group(1)), []).append(m.group(2))
    return spines, stat, defects


def render(spines, stat, defects, title="유튜브 대본 스타일", samples=None):
    samples = samples or {}
    groups = {}
    for s in spines:
        for c in [c for c in json.loads(s.get("fit_categories_json") or "[]") if c.endswith("형")] or ["미분류"]:
            groups.setdefault(c, []).append(s)
    n_ok = sum(1 for s in spines if not defects.get(s["id"]))
    out = []
    for cat in sorted(groups, key=lambda c: -len(groups[c])):
        out.append('<section><h2>%s <span class="cnt">스타일 %d개</span></h2>' % (html.escape(cat), len(groups[cat])))
        for s in groups[cat]:
            d = defects.get(s["id"], [])
            st = stat.get(s["id"], {})
            tpl = json.loads(s.get("templates_json") or "{}")
            roles = json.loads(s.get("beat_roles_json") or "[]")
            badge = '<span class="ok">틀 점검 통과</span>' if not d else '<span class="bad">보완 필요 %d건</span>' % len(d)
            sm = samples.get(str(s["id"]))
            if sm is not None:
                flags = [x for x in [("근거 없는 숫자 " + ",".join(sm.get("fake_num") or [])) if sm.get("fake_num") else "",
                                     ("재료에 없는 나라 " + ",".join(sm.get("country") or [])) if sm.get("country") else "",
                                     ("지어낸 사실 의심 " + ",".join(sm.get("claim") or [])) if sm.get("claim") else "",
                                     ("빈칸 새어나옴 %d줄" % sm["leak"]) if sm.get("leak") else "",
                                     ("장면 없는 줄 %d" % sm["empty_lines"]) if sm.get("empty_lines") else ""] if x]
                badge += ('<span class="bad">실제 뽑기 실패</span>' if not sm.get("ok") else
                          '<span class="bad">뽑았지만 걸림 %d</span>' % len(flags) if flags else '<span class="ok">실제 뽑기 OK</span>')
            out.append('<details class="sp"><summary><b>%d</b> %s %s <small>회원 100명 → %s가지 · 첫 줄 %s종</small></summary>' % (
                s["id"], html.escape(s["name"]) + ("" if s.get("status") == "approved" else ' <span class="bad">미승인(%s)</span>' % html.escape(str(s.get("status")))), badge, st.get("combos", "?"), st.get("first_kinds", "?")))
            if d:
                out.append('<ul class="def">' + "".join("<li>%s</li>" % html.escape(x) for x in d) + "</ul>")
            if sm is not None:
                out.append('<div class="smp"><div class="role">실제로 뽑아 본 대본 <small>같은 재료(%s)·렌더 없음</small></div>' % html.escape(samples.get("_job", "")))
                if sm.get("switched"):
                    out.append('<p class="ap">재료에 딴 용도 장면이 없어 「%s」로 바꿔 씀</p>' % html.escape(str((sm["switched"] or {}).get("to"))))
                if not sm.get("ok"):
                    out.append('<p class="def">실패: %s</p>' % html.escape(str(sm.get("why"))))
                else:
                    out.append("<ol class='lines'>" + "".join("<li>%s</li>" % html.escape(l) for l in sm["lines"]) + "</ol>")
                    out.append('<p class="ap">%d줄 · 장면 %d컷 지정%s</p>' % (len(sm["lines"]), sm.get("cuts", 0),
                               "".join(" · <span class='bad'>%s</span>" % html.escape(f) for f in flags)))
                out.append('</div><div class="role">칸별 문장틀</div>')
            if s.get("appeal"):
                out.append('<p class="ap">%s</p>' % html.escape(s["appeal"]))
            out.append("<ol>")
            for r in roles:
                items = tpl.get(r) or []
                out.append('<li><div class="role">%s <small>%d개</small></div><ul>%s</ul></li>' % (
                    ROLE_KO.get(r, r), len(items),
                    "".join("<li>%s</li>" % re.sub(r"\{([^{}]+)\}", r'<mark>\1</mark>', html.escape(t)) for t in items)))
            out.append("</ol></details>")
        out.append("</section>")
    sm_all = [samples.get(str(x["id"])) for x in spines if samples.get(str(x["id"])) is not None]
    smp_line = (" 실제로 뽑아 보니 %d개 중 <b>%d개 대본 나옴</b>." % (
        len(sm_all), sum(1 for v in sm_all if v.get("ok")))) if sm_all else ""
    return PAGE % dict(title=title, n=len(spines), ok=n_ok, smp=smp_line, body="\n".join(out))


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--ok:#1a7f37;--bad:#c2410c;--mark:#fff1a8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--ok:#4ade80;--bad:#fb923c;--mark:#5c4b00}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}.lead{color:var(--sub);margin:0 0 24px}
h2{font-size:19px;margin:28px 0 10px}.cnt{font-size:14px;color:var(--sub);font-weight:400}
.sp{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:8px 0;padding:12px 16px}
summary{cursor:pointer;font-size:16px}summary small{display:block;color:var(--sub);margin-top:2px}
.ok,.bad{font-size:13px;padding:1px 8px;border-radius:99px;margin-left:6px;border:1px solid}.ok{color:var(--ok)}.bad{color:var(--bad)}
.smp{background:var(--bg);border-radius:10px;padding:8px 12px;margin:10px 0}.lines li{margin:3px 0}.def{color:var(--bad);font-size:14px}.ap{color:var(--sub);font-size:14px}.role{font-weight:600;margin-top:10px}.role small{color:var(--sub);font-weight:400}
ol{padding-left:22px}ol ul{padding-left:18px;margin:4px 0}ol ul li{margin:2px 0}mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}
</style></head><body><main><h1>%(title)s</h1>
<p class="lead">스타일 %(n)d개 중 %(ok)d개 틀 점검 통과.%(smp)s 스타일을 누르면 칸별 문장틀이 펼쳐집니다. 노란 글자는 제품마다 바뀌는 빈칸입니다.</p>
%(body)s</main></body></html>"""

if __name__ == "__main__":
    sp, au, out = sys.argv[1:4]
    a, b, c = load(sp, au)
    insta = len(sys.argv) > 4 and sys.argv[4] == "insta"      # 인스타 = 이름이 '유튜브'로 시작하지 않는 스파인 중 인스타 유형
    mode = sys.argv[4] if len(sys.argv) > 4 else "yt"
    smp = {}
    if len(sys.argv) > 5:
        j = json.load(open(sys.argv[5], encoding="utf-8"))
        smp = dict(j.get("spines") or {}, _job=j.get("job", ""))
    if mode != "all":
        a = [s for s in a if (not s["name"].startswith("유튜브")) == insta]
    a = [s for s in a if (str(s["id"]) in smp or not smp) and s.get("status") == "approved"]      # 라이브에서 쓰는 것만
    title = {"all": "대본 스타일 전체 점검", "insta": "인스타 대본 스타일"}.get(mode, "유튜브 대본 스타일")
    open(out, "w", encoding="utf-8").write(render(a, b, c, title, smp))
    print("wrote", out, len(a))
