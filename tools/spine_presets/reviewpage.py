# 원문형 스파인 검수 페이지 — 368개를 유형별로 펼쳐 버릴 것을 고른다 (2026-09-21)
#
# 왜 별도 도구인가: spinepage.py는 4유형만·생성 대본이 있어야 돌고,
# sample5page.py는 씨앗 제품별 묶음이다. 핸드오프 ⏭1번("버릴 스파인 고르기")은
# **스파인 전수**를 유형별로 봐야 해서 입력이 다르다(덤프 JSON 한 개).
#
# 쓰기: python tools/spine_presets/reviewpage.py <덤프.json> <출력.html>
import json, html, re, sys, collections

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


# ── 유튜브형 3유형의 인스타 혼입 거르기 (2026-09-21 사장님) ──────────────────
# 사장님: "발명품이랑 오용형 제품정체형 이건 cta없고 유튜브 스타일이야 인스타형태있는것 걸러내"
#
# ★두 종류를 함께 거른다 — 재보니 불량이 하나가 아니었다(실측 90개 중 39개):
#   ① 인스타 CTA 13개 — "댓글에 'OO' 남겨주세요"·"저장해두시고". 유튜브형엔 CTA가 없어야 한다.
#   ② 마지막 문장이 중간에 잘린 것 26개 — "근데"/"올해 장맞철 오기"처럼 종결어미 없이 끊긴 칸이
#      CTA 역할로 붙어 있다. 원문 자체가 깨진 것이라 대본 끝이 무너진다.
# 지우지 않고 **표시만** 한다(사장님 확정) — 전부 pending이라 고객에겐 안 나간다.
YT_TYPES = {"발명품형", "오용형", "제품정체형"}
_INSTA_CTA = re.compile(r"댓글|남겨|저장해|팔로우|프로필|링크|디엠|DM")
# 한국어 종결어미 또는 문장부호로 끝나면 완결로 본다
_ENDS = re.compile(r"(다|요|임|음|죠|네|야|함|거|까|래|워|해|고요|든요)[.!?~]*$|[.!?]$")


# ── 원문 자체가 망가진 것 (2026-09-21 사장님 "좋은 백본 많은데 이런건 걸러야되네") ──
# 실사고: 스파인 387로 뽑은 대본이 ①존대·반말 혼재 ②`[음악]` 박힘 ③끝이 '진짜 미친'에서 잘림.
# 백본은 제대로 돌았다 — **원문이 그 모양이라 그대로 베낀 것**이다. 그래서 원문에서 막는다.
_NOISE = re.compile(r"\[(음악|박수|웃음|Music|Applause)\]", re.I)
# 존댓말 종결 vs 반말 종결 — 한 대본에 섞이면 읽을 때 튄다.
# ★연결어미(`~는데`·`~니까`·`~고`)는 **판정에서 뺀다**(2026-09-21 실측으로 정정).
#   칸이 문장 중간에서 끊기면 연결어미로 끝나는데, 이걸 반말로 세면
#   멀쩡한 존댓말 대본이 '섞임'으로 잡힌다(#125·#127·#130 전부 오탐이었다).
#   실측: 연결어미를 넣으면 133개가 걸렸는데, 빼면 진짜 혼재만 남는다.
_HONOR = re.compile(r"(어요|예요|에요|습니다|세요|해요|거예요|입니다|시죠|잖아요|더라고요|거죠)[.!?~]*$")
_PLAIN = re.compile(r"(임|음|함|거임|했음|됨|았어|었어|거야|든다|한다|이다)[.!?~]*$")


def _tone_mixed(cells):
    """존대 칸과 반말 칸이 **둘 다** 있나. CTA는 코드가 갈아끼우므로 제외한다."""
    hon = pla = 0
    for c in cells:
        t = (c.get("text") or "").strip()
        if not t or c.get("role") == "CTA":
            continue
        if _HONOR.search(t):
            hon += 1
        elif _PLAIN.search(t):
            pla += 1
    return hon and pla


def reject(r, typ):
    """이 스파인을 걸러낼 이유 — 없으면 None.

    ★①②③은 **모든 유형**에 건다(원문 품질이라 유형과 무관하다).
      ④ 인스타 CTA만 유튜브형 3유형 전용이다(그 유형엔 CTA가 없어야 하므로)."""
    o = origin(r)
    cells = [c for c in (o.get("cells") or []) if (c.get("text") or "").strip()]
    if not cells:
        return "칸이 비었음"
    # ① 끝이 잘림 — 마지막 칸이 종결어미로 안 끝난다(유튜브 자동자막이 멈춘 자리)
    if not _ENDS.search(cells[-1]["text"].strip()):
        return "마지막 문장이 잘림 — 원문 불량"
    # ② 자막 잡음이 원문에 박힘
    if any(_NOISE.search(c["text"]) for c in cells):
        return "[음악] 등 자막 잡음이 원문에 박힘"
    # ③ 존대·반말 혼재
    if _tone_mixed(cells):
        return "존대·반말 섞임 — 대본이 튄다"
    # ④ 유튜브형인데 인스타 CTA
    if typ in YT_TYPES:
        cta = [c["text"].strip() for c in cells if c.get("role") == "CTA"]
        if cta and _INSTA_CTA.search(cta[0]):
            return "인스타 CTA — 유튜브형엔 CTA가 없어야 함"
    return None


og = [r for r in rows if origin(r)]
by = collections.OrderedDict()
for r in og:
    for f in (fits(r) or ["(유형없음)"]):
        by.setdefault(f, []).append(r)
# 많은 유형부터 — 약한 유형(정체의문 6개)이 끝에 모여 보강 대상이 눈에 띈다
by = collections.OrderedDict(sorted(by.items(), key=lambda kv: -len(kv[1])))

def _n_ok(k, v):
    return sum(1 for r in v if not reject(r, k))


nav = " · ".join('<a href="#t%d">%s <b>%d</b>%s</a>'
                 % (i, e(k), _n_ok(k, v),
                    ('<s>%d</s>' % (len(v) - _n_ok(k, v))) if len(v) - _n_ok(k, v) else "")
                 for i, (k, v) in enumerate(by.items()))
secs = []
for i, (typ, lst) in enumerate(by.items()):
    lst = sorted(lst, key=lambda r: -(origin(r).get("views") or 0))
    cards = []
    for r in lst:
        o = origin(r)
        why = reject(r, typ)
        cells = "".join('<tr><td class="r">%s</td><td>%s</td></tr>' % (e(c.get("role")), e(c.get("text")))
                        for c in o.get("cells", []))
        cards.append(
            '<details class="sp%s" id="s%d"><summary>'
            '<span class="id">#%d</span> <b>%s</b>%s'
            '<span class="sub">%s · 조회 %s · @%s · %d칸</span></summary>'
            '<div class="body"><div class="hk">훅 고정틀: <code>%s</code></div>'
            '<table>%s</table></div></details>'
            % (" cut" if why else "", r["id"], r["id"], e(r.get("name")),
               ('<span class="tag">걸러냄 · %s</span>' % e(why)) if why else "",
               e(tone(r)), format(o.get("views") or 0, ","), e(o.get("user")),
               len(o.get("cells") or []), e(o.get("hook_tpl")), cells))
    nout = sum(1 for r in lst if reject(r, typ))
    head = ('%d개 — <b>%d개 걸러냄</b>, 남는 것 %d개' % (len(lst), nout, len(lst) - nout)) if nout else ('%d개' % len(lst))
    secs.append('<section id="t%d"><h2>%s <span class="sub">%s</span></h2>%s</section>'
                % (i, e(typ), head, "".join(cards)))

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
.sp.cut{opacity:.5;border-style:dashed}
.sp.cut summary{text-decoration:line-through;text-decoration-color:var(--sub)}
.tag{background:#c0392b;color:#fff;font-size:11.5px;padding:1px 7px;border-radius:20px;margin-left:7px;white-space:nowrap;text-decoration:none;display:inline-block}
nav s{color:#c0392b;margin-left:3px;font-size:12px}
.lead{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;padding:12px 14px;margin:12px 0;font-size:14.5px}
</style></head><body><main>
<h1>원문형 스파인 검수 — 368개</h1>
<p class="sub">히트작 원문 한 편 = 스파인 한 개. 버릴 것의 <b>#번호</b>를 알려주시면 뺍니다. 남는 것만 approved로 올립니다.</p>
<div class="lead">지금 전부 <b>pending</b>(대기)이라 고객에게는 안 나갑니다. 유형을 눌러 펼치고, 원문이 어색하거나
제품을 못 갈아끼울 것 같은 스파인의 번호를 적어 주세요.</div>
<nav>""" + nav + "</nav>" + "\n".join(secs) + "</main></body></html>")
print("ok")
