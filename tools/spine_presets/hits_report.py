# 히트작 대본 지도 — 유형(훅) × 흐름(재료 조합) + 새 유형 후보 + 메종 분석 (2026-09-19)
# 사용:  py hits_report.py hits_cls.json maison42.json out.html
#   hits_cls.json = classify_hits.py 결과 / maison42.json = 메종 전사(조회수 포함)
# 흐름을 칸 순서 그대로 묶으면 유형당 42~57가지로 흩어진다(실측) → 재료 조합 4개로 묶는다.
import html, json, re, statistics as S, sys, collections

NEW = {  # 기존 분류에 흩어져 들어간 여는 방식 — 전체에서 문구로 센다
    "전문가지인형": (r"^.{0,60}(약사|의사|간호사|점장|조리장|셰프|피부과|치과|한의사|정리업체|인테리어 하는|커피 회사|업체 사장|사장님이|청소업체|미용사)",
                  "약사·의사·점장·셰프 같은 **직업인 지인**이 알려줬다 — 지인증언의 친근함 + 전문가 권위"),
    "업계충격형": (r"^.{0,40}(업계|망하게|멘탈을|박살낸|떼돈)", "이 물건 때문에 **업계가 망했다·사장님들 멘붕** — 발명품형의 센 버전"),
    "비밀폭로형": (r"^.{0,40}(가스라이팅|비밀|까발|숨겨|정체가 충격|영업비밀)", "다들 속고 있었다·업계 비밀 — **숨긴 걸 까발리는** 긴장 (⚠ 아직 표본이 적어 후보로만)"),
}
KNOWN = {"오용형", "제품정체형", "발명품형", "지인증언형", "권유지시형", "물건발견형", "금지경고형", "사회증거형", "정체의문형",
         "무지후회형", "목격담형", "가성비형", "만능템형", "다이소지목형", "내자랑형"}
MAISON_HOOKS = [
    ("오용(개발자도 놀란 활용)", r"^.{0,30}(개발자도|디자이너도|개발 의도랑은)"),
    ("금지·다이소지목(여러분 ~)", r"^(여러분|이제 욕실)"),
    ("지인증언(와이프·친구가 + 반응)", r"^.{0,40}(와이프|친구|엄마|형이|인플루언서|피아노 학원|부잣집)"),
    ("천재발명(천재·기장이 만든)", r"^.{0,25}(천재|기장이|엔지니어)"),
    ("권위·업계(미술관·장인·사장님들)", r"^.{0,30}(미술관|장인|사장님들|정리업체)"),
    ("사회증거(요즘 ~사이에서)", r"^요즘 .{0,15}사이에서"),
    ("내자랑(내가 샀더니 반응)", r"^(저희 집|서재방|이번 겨울|이거 하나 바꿨|저 작년|집주인)"),
    ("충격후기(평생 트라우마·오열)", r"^평생"),
]
TICS = [("체험 전달 '~더라고요'", r"더라[고구]요"), ("'진짜' 강조", r"진짜"), ("'심지어' 한 단계 더", r"심지어"),
        ("CTA '댓글에 ○○ 남겨주세요'", r"댓글에"), ("해외 출처(일본·미국·해외)", r"일본|미국|해외|영국"),
        ("숫자로 구체화", r"\d"), ("'근데 이건' 전환", r"근데 이(건|게)"), ("'~거든요' 사정 설명", r"거든요"),
        ("'얼마 전에' 계기", r"얼마 ?전에"), ("'난리' 화제", r"난리"), ("'미친·미쳤'", r"미[친쳤쳐]")]


def flow_key(f):
    f = [x.split("(")[0] for x in (f or [])]
    parts = ["계기 장면" if "계기" in f else "", "불편 먼저" if "기존불편" in f else "",
             "권위·사회증거" if ("유래·권위" in f or "사회증거" in f) else "", "'심지어' 한 단계 더" if "추가장점" in f else ""]
    return " + ".join(p for p in parts if p) or "바로 작동"


def med(v):
    return int(S.median(v)) if v else 0


def esc(s):
    return html.escape(str(s or ""))


def card(r, full=True):
    t = r["text"] if full else r["text"][:120] + ("…" if len(r["text"]) > 120 else "")
    who = ("메종 홈디노" if r.get("user") == "maison_homedino" else r.get("user") or "")
    why = f'<p class="why">잘 쓴 이유: {esc(r.get("strength"))}</p>' if r.get("strength") else ""
    return (f'<div class="card"><div class="meta"><b>{r["views"]:,}회</b> · {esc(r.get("platform"))} · {esc(who)}</div>'
            f'<p class="txt">{esc(t)}</p>{why}</div>')


def main():
    R = json.load(open(sys.argv[1], encoding="utf-8"))
    M = json.load(open(sys.argv[2], encoding="utf-8"))
    out = sys.argv[3]
    R = [r for r in R if sum(1 for c in r["text"][:80] if "가" <= c <= "힣") >= 15]      # 외국어·노래 제외
    R = [r for r in R if not str(r.get("type") or "").startswith("new_type")]
    for r in R:
        for k, (p, _) in NEW.items():
            if re.search(p, r["text"]):
                r["new_cand"] = k
                break
    by = collections.defaultdict(list)
    for r in R:
        t = str(r.get("type") or "")
        by[t if t in KNOWN else "새유형(단발)"].append(r)
    h = []
    total = len(R)
    h.append(f'<p class="lead">터진 대본 <b>{total}편</b>(조회수 10만 회 이상 + 메종 홈디노 전부, 한국어만) · '
             f'인스타 {sum(r["platform"]=="instagram" for r in R)} · 유튜브 {sum(r["platform"]=="youtube" for r in R)}. '
             '유형 = 첫 문장이 어떻게 여는가 / 흐름 = 뒤에 무슨 재료를 붙였나.</p>')
    # 1. 유형 순위
    rows = []
    for t, L in sorted(by.items(), key=lambda a: -len(a[1])):
        if t == "새유형(단발)":
            continue
        rows.append(f'<tr><td><a href="#t-{esc(t)}">{esc(t)}</a></td><td>{len(L)}</td><td>{med([x["views"] for x in L]):,}</td>'
                    f'<td>{sum(x["platform"]=="instagram" for x in L)}</td><td>{sum(x["platform"]=="youtube" for x in L)}</td>'
                    f'<td>{sum(x.get("user")=="maison_homedino" for x in L)}</td></tr>')
    h.append('<h2>1. 유형 순위</h2><div class="tw"><table><tr><th>유형</th><th>편수</th><th>조회수 중앙</th><th>인스타</th><th>유튜브</th><th>메종</th></tr>'
             + "".join(rows) + "</table></div>")
    # 2. 새 유형 후보
    h.append('<h2>2. 새 유형 후보 <small>기존 유형에 흩어져 들어가 있던 여는 방식</small></h2>')
    for k, (p, desc) in NEW.items():
        L = sorted([r for r in R if r.get("new_cand") == k], key=lambda r: -r["views"])
        where = collections.Counter(r["type"] for r in L).most_common(4)
        h.append(f'<details class="sec" open><summary><b>{k}</b> — {len(L)}편 · 조회수 중앙 {med([r["views"] for r in L]):,}</summary>'
                 f'<p>{desc.replace("**", "")}</p><p class="sub">지금은 {", ".join("%s %d" % w for w in where)}로 흩어져 분류됨</p>'
                 + "".join(card(r) for r in L[:4]) + "</details>")
    solo = sorted(by.get("새유형(단발)", []), key=lambda r: -r["views"])
    if solo:
        h.append('<details class="sec"><summary>모델이 새 유형이라 한 단발 %d편 (아직 유형으로 묶기엔 1편씩)</summary>' % len(solo)
                 + "".join(f'<p class="sub"><b>{esc(str(r["type"]).split(":")[-1])}</b> · {r["views"]:,}회 — {esc(r["text"][:90])}…</p>' for r in solo) + "</details>")
    # 3. 메종
    M.sort(key=lambda x: -(x["views"] or 0))
    MT = [(x["full_text"] or "").strip() for x in M]
    mrows = []
    first = {}
    for x in M:
        first[id(x)] = next((n for n, p in MAISON_HOOKS if re.search(p, (x["full_text"] or "").strip())), "기타")
    for name, p in MAISON_HOOKS:
        L = [x for x in M if first[id(x)] == name]
        if L:
            mrows.append((med([x["views"] or 0 for x in L]), f'<tr><td>{esc(name)}</td><td>{len(L)}</td><td>{med([x["views"] or 0 for x in L]):,}</td><td>{max(x["views"] or 0 for x in L):,}</td></tr>'))
    tics = "".join(f'<tr><td>{esc(k)}</td><td>{sum(1 for t in MT if re.search(p, t))}/{len(MT)}</td></tr>' for k, p in TICS)
    seen, MU = set(), []
    for x, t in zip(M, MT):          # 같은 대본 재업로드는 한 번만(상위 5편·CTA 셈)
        k = re.sub(r"\s", "", t)[:25]
        if k not in seen:
            seen.add(k); MU.append((x, t))
    top10_cta = sum("댓글에" in t for _, t in MU[:10])
    nj = sum(1 for x in M if first[id(x)].startswith("지인증언"))
    h.append(f'''<h2 id="maison">3. 메종 홈디노 분석 <small>전사 {len(M)}편(게시물 기록 384편 중)</small></h2>
<div class="box"><b>한 줄 요약</b> — 메종은 <b>“내가 겪은 일”을 말하듯 전한다</b>. 42편 중 40편이 “~더라고요”로 끝나는 체험 전달체이고,
훅은 <b>사람(와이프·친구·엄마) + 반응(소리질렀어요·혼났어요·깜짝 놀랐어요)</b>이 가장 많다({nj}편). 단일 최고는 오용형(158만), 편수 대비 고르게 잘 되는 건 천재발명·지인증언이다.
흐름은 거의 고정: <b>훅 → 계기(얼마 전에 ○○ 갔는데) → 기존 불편(~거든요/~잖아요) → 근데 이건(작동) → 심지어(한 단계 더) → 결과·감정</b>.
길이 중앙 {med([len(t) for t in MT])}자(140~336). 조회수 상위 10편(재업로드 제외) 중 CTA를 단 건 {top10_cta}편뿐 — <b>잘 된 대본일수록 CTA가 없다</b>.
같은 대본을 다시 올려도 터진다(게임방 145만→79만, 숯 27만→16만).</div>
<div class="grid2"><div><h3>훅별 조회수</h3><div class="tw"><table><tr><th>훅</th><th>편</th><th>중앙</th><th>최고</th></tr>{"".join(r for _, r in sorted(mrows, reverse=True))}</table></div></div>
<div><h3>말버릇 빈도</h3><div class="tw"><table><tr><th>꼴</th><th>편</th></tr>{tics}</table></div></div></div>
<h3>메종 상위 5편</h3>''' + "".join(card(dict(text=t, views=x["views"] or 0, platform="instagram", user="maison_homedino")) for x, t in MU[:5]))
    # 4. 유형별 흐름 + 대표 대본
    h.append('<h2>4. 유형별 흐름과 대표 대본 <small>흐름 = 뒤에 붙인 재료 조합, 편수 많은 순 최대 5개</small></h2>')
    for t, L in sorted(by.items(), key=lambda a: -len(a[1])):
        if t == "새유형(단발)" or len(L) < 3:
            continue
        fl = collections.defaultdict(list)
        for r in L:
            fl[flow_key(r.get("flow"))].append(r)
        top = sorted(fl.items(), key=lambda a: (-len(a[1]), -med([x["views"] for x in a[1]])))[:5]
        parts = []
        for i, (k, FL) in enumerate(top, 1):
            best = max(FL, key=lambda r: r["views"])
            parts.append(f'<div class="flow"><div class="fh">흐름 {i}. <b>훅 → {esc(k)}</b> <small>{len(FL)}편 · 중앙 {med([x["views"] for x in FL]):,}회</small></div>{card(best)}</div>')
        h.append(f'<details class="sec" id="t-{esc(t)}"><summary><b>{esc(t)}</b> — {len(L)}편 · 조회수 중앙 {med([x["views"] for x in L]):,} · 흐름 {len(fl)}가지 중 상위 {len(top)}</summary>'
                 + "".join(parts) + "</details>")
    h.append('<h2>5. 다음</h2><p class="sub">① 사장님이 새 유형 후보 3개 확정 → ② 유형마다 위 흐름 5개를 스타일 5개로(문장은 이 대본들의 원문에서) → '
             '③ 우리 스타일로 뽑은 대본을 같은 흐름의 히트작 옆에 나란히 놓고 판정.</p>')
    open(out, "w", encoding="utf-8").write(PAGE.replace("%BODY%", "\n".join(h)))
    print("wrote", out, total)


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>히트작 대본 지도</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--sub:#6e6e73;--line:#e3e3e0;--acc:#b4540a;--box:#fff6e8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c;--box:#2a2116}}
:root[data-theme="dark"]{--bg:#141416;--card:#1f1f22;--ink:#f2f2f2;--sub:#a1a1a6;--line:#333;--acc:#fb923c;--box:#2a2116}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"Malgun Gothic",sans-serif}
main{max-width:900px;margin:0 auto;padding:24px 16px 80px}h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:36px 0 10px}h2 small,summary small,.fh small{color:var(--sub);font-weight:400;font-size:14px}
h3{font-size:16px;margin:16px 0 6px}.lead,.sub{color:var(--sub)}a{color:var(--acc)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);font-size:15px}td,th{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;white-space:nowrap}th{color:var(--sub);font-weight:500}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:10px 0;padding:12px 16px}summary{cursor:pointer}
.card{border-left:3px solid var(--acc);padding:6px 12px;margin:10px 0;background:var(--bg);border-radius:0 8px 8px 0}.meta{font-size:13px;color:var(--sub)}.txt{margin:4px 0}.why{font-size:14px;color:var(--acc);margin:4px 0}
.flow{margin:14px 0}.fh{font-size:15px}.box{background:var(--box);border-radius:12px;padding:14px 16px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:640px){.grid2{grid-template-columns:1fr}td,th{white-space:normal}}
</style></head><body><main><h1>히트작 대본 지도</h1>%BODY%</main></body></html>"""

if __name__ == "__main__":
    main()
