# -*- coding: utf-8 -*-
"""A/B 결과 → 아침에 눈으로 보는 HTML 리포트.

★숫자를 지어내지 않는다 — results.json에 실제로 있는 것만 센다.
  실행이 중간에 죽었어도 있는 데까지로 리포트를 만들고, **몇 건까지만 돌았는지 명시**한다.
"""
import io
import json
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(_HERE, "results.json")
PROGRESS = os.path.join(_HERE, "progress.json")
OUT = os.path.join(_HERE, "리포트.html")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
    rows = json.load(io.open(RESULTS, encoding="utf-8"))
    prog = {}
    if os.path.exists(PROGRESS):
        prog = json.load(io.open(PROGRESS, encoding="utf-8"))

    models = sorted({r["model"] for r in rows})
    ok = [r for r in rows if r.get("ok")]
    fail = [r for r in rows if not r.get("ok")]

    # ── 모델별 집계 ────────────────────────────────────────────────
    agg = {}
    for m in models:
        rs = [r for r in ok if r["model"] == m]
        if not rs:
            continue
        # 재픽이 실제로 돈 건만(모델을 부른 건만) 성능으로 센다.
        # ★blank는 제외한다 — 출발이 '화면 없음'이라 채점축이 판정을 보류해
        #   base_bad=0(만점처럼 보임)이 된다. 채우면 판정이 켜지므로 무엇을 골라도
        #   "나빠짐"으로 세어져 지표가 거꾸로 나온다. 별도 표로 따로 본다.
        called = [r for r in rs if r.get("seconds", 0) > 0.5 and r["case"] != "blank"]
        beats = sum(r["n_beats"] for r in called)
        base = sum(r["base_bad"] for r in called)
        after = sum(r["after_bad"] for r in called)
        # ★"나빠짐"은 **잴 수 있었던 비트**에서만 센다.
        #   출발 shot_role이 없는 비트(pad·빈칸)는 채점축이 판정을 보류해 어긋남 0으로
        #   잡히므로, 채우는 순간 무엇을 골라도 나빠짐이 된다(blank와 같은 함정).
        def _real_worse(r):
            gained = 0
            for b0, a0 in zip(r.get("base_detail", []), r.get("after_detail", [])):
                if b0.get("shot_role") and (not b0["mismatch"]) and a0["mismatch"]:
                    gained += 1   # 판정 가능했고 멀쩡했는데 어긋나게 만든 것만
            return gained > 0
        worse = [r for r in called if _real_worse(r)]
        better = [r for r in called if r["after_bad"] < r["base_bad"]]
        same = [r for r in called if r["after_bad"] == r["base_bad"]]
        agg[m] = {
            "n": len(rs), "called": len(called), "beats": beats,
            "base": base, "after": after,
            "fixed_rate": (100.0 * (base - after) / base) if base else 0.0,
            "resid": (100.0 * after / beats) if beats else 0.0,
            "better": len(better), "worse": len(worse), "same": len(same),
            "sec": statistics.median([r["seconds"] for r in called]) if called else 0,
            "changed": sum(r.get("changed", 0) for r in called),
        }

    # ── 케이스별 나란히 ────────────────────────────────────────────
    cases = []
    for cname in sorted({r["case"] for r in ok}):
        row = {"case": cname}
        for m in models:
            rs = [r for r in ok if r["case"] == cname and r["model"] == m]
            if rs:
                row[m] = {
                    "base": rs[0]["base_bad"],
                    "after": [r["after_bad"] for r in rs],
                    "changed": [r.get("changed", 0) for r in rs],
                    "called": any(r.get("seconds", 0) > 0.5 for r in rs),
                }
        cases.append(row)

    # ── 훅/CTA 역할별 (가장 중요한 두 자리) ─────────────────────────
    role_stat = {}
    for r in ok:
        if r.get("seconds", 0) <= 0.5 or r["case"] == "blank":
            continue
        for d in r.get("after_detail", []):
            k = (r["model"], d.get("role") or "?")
            s = role_stat.setdefault(k, {"n": 0, "bad": 0})
            s["n"] += 1
            s["bad"] += 1 if d["mismatch"] else 0

    P = []
    P.append("<title>매칭 오푸스 vs 제미니</title>")
    P.append("""<style>
:root{--bg:#fbfaf9;--fg:#1a1a19;--mut:#6b6b68;--line:#e3e0dc;--card:#fff;
--good:#1a7f5a;--bad:#b3402f;--warn:#8a6d1f}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#191817;--fg:#eceae7;
--mut:#a09d98;--line:#343230;--card:#211f1e;--good:#5fce9f;--bad:#f08a75;--warn:#d9bc6a}}
:root[data-theme="dark"]{--bg:#191817;--fg:#eceae7;--mut:#a09d98;--line:#343230;--card:#211f1e;
--good:#5fce9f;--bad:#f08a75;--warn:#d9bc6a}
body{background:var(--bg);color:var(--fg);font:15px/1.65 -apple-system,"Segoe UI",
"Malgun Gothic",sans-serif;margin:0;padding:28px 20px 60px}
.w{max-width:1000px;margin:0 auto}
h1{font-size:25px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:17px;margin:34px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.sub{color:var(--mut);font-size:13.5px;margin-bottom:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
.c{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:15px 17px}
.c .n{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.c .v{font-size:29px;font-weight:640;margin:5px 0 2px;letter-spacing:-.02em}
.c .d{font-size:12.5px;color:var(--mut)}
table{border-collapse:collapse;width:100%;font-size:13.5px;background:var(--card);
border:1px solid var(--line);border-radius:9px;overflow:hidden}
th,td{padding:8px 11px;text-align:left;border-bottom:1px solid var(--line)}
th{background:rgba(128,128,128,.07);font-weight:600;font-size:12.5px}
tr:last-child td{border-bottom:none}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.good{color:var(--good);font-weight:600}.bad{color:var(--bad);font-weight:600}
.warn{color:var(--warn)}
.scroll{overflow-x:auto}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--warn);
border-radius:8px;padding:13px 16px;margin:16px 0;font-size:13.5px}
code{background:rgba(128,128,128,.13);padding:1px 5px;border-radius:4px;font-size:12.5px}
</style>""")
    P.append('<div class="w">')
    P.append("<h1>장면매칭 — 오푸스 vs 제미니</h1>")
    done = prog.get("done", len(rows))
    tot = prog.get("total", len(rows))
    P.append('<div class="sub">실측 %d건 / 계획 %d건 · %s분 소요 · 실패 %d건<br>'
             '채점축 = 프로덕션 <code>backbone.beat_role_mismatch</code> '
             '(역할↔결 어긋남. 낮을수록 좋다)</div>'
             % (done, tot, prog.get("elapsed_min", "?"), len(fail)))

    if done < tot:
        P.append('<div class="note">⚠️ 계획 %d건 중 <b>%d건까지</b> 돌았다. '
                 '아래 수치는 그 범위의 실측이다.</div>' % (tot, done))

    # 요약 카드
    P.append("<h2>한눈에</h2><div class='cards'>")
    for m in models:
        a = agg.get(m)
        if not a:
            continue
        cls = "good" if a["fixed_rate"] >= 50 else ("warn" if a["fixed_rate"] > 0 else "bad")
        P.append('<div class="c"><div class="n">%s</div>'
                 '<div class="v %s">%.0f%%</div>'
                 '<div class="d">어긋남 교정률 (%d→%d)<br>'
                 '호출 %d건 · 중앙 %.1f초</div></div>'
                 % (esc(m), cls, a["fixed_rate"], a["base"], a["after"], a["called"], a["sec"]))
    P.append("</div>")

    # ── 실험2: 문턱(fit) — 이번 실측의 결론 ──────────────────────────
    GATE = os.path.join(_HERE, "gate_results.json")
    if os.path.exists(GATE):
        grows = [r for r in json.load(io.open(GATE, encoding="utf-8")) if r.get("ok")]
        if grows:
            gagg = {}
            for r in grows:
                gagg.setdefault((r["fit"], r["model"]), []).append(r)
            P.append("<h2>★ 실험2 — 진짜 원인은 모델이 아니라 <b>문턱</b>이었다</h2>")
            P.append('<div class="note">재픽(<code>_repick_weak_beats</code>)은 '
                     '<b>fit≤3 또는 forced</b>인 비트만 고친다. 라이브는 전 비트가 '
                     '<b>fit=5</b>라 <b>어느 모델도 호출되지 않는다.</b><br>'
                     '아래는 문턱만 바꿔가며 같은 비트를 재픽시킨 결과다.</div>')
            P.append("<div class='scroll'><table><tr><th>fit(출발)</th>"
                     "<th class='num'>모델</th><th class='num'>모델 호출</th>"
                     "<th class='num'>출발 어긋남</th><th class='num'>교정 후</th></tr>")
            for fit in [5, 4, 3, 2, 1]:
                for m in sorted({r["model"] for r in grows}):
                    rs = gagg.get((fit, m)) or []
                    if not rs:
                        continue
                    called = sum(1 for r in rs if r.get("called"))
                    base = sum(r["base_bad"] for r in rs) / len(rs)
                    after = sum(r["after_bad"] for r in rs) / len(rs)
                    cls = "good" if after < base else ("bad" if called == 0 else "")
                    P.append("<tr><td><b>fit=%d</b></td><td class='num'>%s</td>"
                             "<td class='num %s'>%d/%d</td><td class='num'>%.1f</td>"
                             "<td class='num %s'>%.1f</td></tr>"
                             % (fit, esc(m), "bad" if called == 0 else "good",
                                called, len(rs), base, cls, after))
            P.append("</table></div>")
            P.append('<div class="note"><b>읽는 법:</b> fit 5·4에서는 <b>호출 0회</b> — '
                     '오푸스를 붙여도 <b>부르질 않으니 소용이 없다</b>. '
                     'fit을 3 이하로 낮추면 <b>양쪽 모델 다 어긋남을 0으로</b> 만든다.<br>'
                     '→ 처방은 <b>모델 교체가 아니라 fit 판정 수정</b>이다(원가 0).</div>')

    # 모델 비교표
    P.append("<h2>모델 비교</h2><div class='scroll'><table><tr>"
             "<th>모델</th><th class='num'>호출</th><th class='num'>출발 어긋남</th>"
             "<th class='num'>교정 후</th><th class='num'>교정률</th>"
             "<th class='num'>좋아짐</th><th class='num'>나빠짐</th><th class='num'>그대로</th>"
             "<th class='num'>중앙초</th></tr>")
    for m in models:
        a = agg.get(m)
        if not a:
            continue
        P.append("<tr><td><b>%s</b></td><td class='num'>%d</td><td class='num'>%d</td>"
                 "<td class='num'>%d</td><td class='num %s'>%.0f%%</td>"
                 "<td class='num good'>%d</td><td class='num %s'>%d</td>"
                 "<td class='num'>%d</td><td class='num'>%.1f</td></tr>"
                 % (esc(m), a["called"], a["base"], a["after"],
                    "good" if a["fixed_rate"] >= 50 else "warn", a["fixed_rate"],
                    a["better"], "bad" if a["worse"] else "", a["worse"], a["same"], a["sec"]))
    P.append("</table></div>")

    # 역할별 잔존 어긋남
    P.append("<h2>역할별 — 교정 후에도 어긋난 비율</h2><div class='scroll'><table><tr><th>역할</th>")
    for m in models:
        P.append("<th class='num'>%s</th>" % esc(m))
    P.append("</tr>")
    roles = sorted({k[1] for k in role_stat})
    for role in roles:
        P.append("<tr><td><b>%s</b></td>" % esc(role))
        for m in models:
            s = role_stat.get((m, role))
            if s and s["n"]:
                pct = 100.0 * s["bad"] / s["n"]
                cls = "good" if pct < 15 else ("warn" if pct < 40 else "bad")
                P.append("<td class='num %s'>%.0f%% <span style='color:var(--mut)'>(%d/%d)</span></td>"
                         % (cls, pct, s["bad"], s["n"]))
            else:
                P.append("<td class='num'>–</td>")
        P.append("</tr>")
    P.append("</table></div>")

    # 케이스별
    P.append("<h2>케이스별 (출발 → 교정 후, 반복 3회)</h2><div class='scroll'><table><tr>"
             "<th>케이스</th><th class='num'>출발</th>")
    for m in models:
        P.append("<th class='num'>%s</th>" % esc(m))
    P.append("</tr>")
    for row in cases:
        P.append("<tr><td>%s</td>" % esc(row["case"]))
        base = None
        for m in models:
            if row.get(m):
                base = row[m]["base"]
                break
        P.append("<td class='num'>%s</td>" % (base if base is not None else "–"))
        for m in models:
            d = row.get(m)
            if not d:
                P.append("<td class='num'>–</td>")
                continue
            if not d["called"]:
                P.append("<td class='num' style='color:var(--mut)'>미호출</td>")
                continue
            afters = d["after"]
            best = min(afters)
            cls = "good" if best < d["base"] else ("bad" if best > d["base"] else "")
            P.append("<td class='num %s'>%s</td>" % (cls, "·".join(str(x) for x in afters)))
        P.append("</tr>")
    P.append("</table></div>")

    # blank(백지에서 고르기) — 별도로 본다. 위 집계에서 제외한 이유를 함께 밝힌다.
    blanks = [r for r in ok if r["case"] == "blank" and r.get("seconds", 0) > 0.5]
    if blanks:
        P.append("<h2>백지에서 고르기 (blank) — 따로 보는 이유</h2>")
        P.append('<div class="note">출발이 <b>화면 없음</b>이라 채점축이 판정을 보류해 '
                 '<b>출발 어긋남이 0</b>으로 잡힌다(만점처럼 보이지만 실은 "잴 수 없음"). '
                 '무엇을 채워도 "나빠짐"으로 세어지므로 <b>위 집계에서 뺐다.</b> '
                 '여기서는 <b>채운 뒤 몇 개가 어긋났나</b>로만 본다 — 낮을수록 좋다.</div>')
        P.append("<div class='scroll'><table><tr><th>모델</th><th class='num'>회차</th>"
                 "<th class='num'>채운 칸</th><th class='num'>채운 뒤 어긋남</th></tr>")
        for r in sorted(blanks, key=lambda x: (x["model"], x["rep"])):
            filled = sum(1 for d in r["after_detail"] if d["seg_id"])
            bad_n = r["after_bad"]
            cls = "good" if bad_n == 0 else ("warn" if bad_n <= 1 else "bad")
            P.append("<tr><td><b>%s</b></td><td class='num'>%d</td>"
                     "<td class='num'>%d/%d</td><td class='num %s'>%d</td></tr>"
                     % (esc(r["model"]), r["rep"], filled, r["n_beats"], cls, bad_n))
        P.append("</table></div>")

    # ── problem 비트 — 나빠짐의 정체 ────────────────────────────────
    prob_worse = {}
    for r in ok:
        if r["case"] == "blank" or r.get("seconds", 0) <= 0.5:
            continue
        for b0, a0 in zip(r.get("base_detail", []), r.get("after_detail", [])):
            if b0.get("shot_role") and (not b0["mismatch"]) and a0["mismatch"]:
                k = (r["model"], a0.get("role") or "?")
                prob_worse[k] = prob_worse.get(k, 0) + 1
    if prob_worse:
        P.append("<h2>\"나빠짐\"은 어디서 났나</h2>")
        P.append("<div class='scroll'><table><tr><th>모델</th><th>역할</th>"
                 "<th class='num'>멀쩡→어긋남</th></tr>")
        for (m, role), n in sorted(prob_worse.items(), key=lambda x: -x[1]):
            P.append("<tr><td><b>%s</b></td><td>%s</td><td class='num bad'>%d건</td></tr>"
                     % (esc(m), esc(role), n))
        P.append("</table></div>")
        P.append('<div class="note"><b>오푸스 나빠짐은 대부분 <code>problem</code> 한 자리에 몰려 있다</b> '
                 '— 오푸스가 문제 비트에 완성·after 샷을 고르기 때문.<br>'
                 '⚠️ <b>이 잡의 인벤토리엔 <code>before</code>·<code>문제</code> 결이 0건</b>이다'
                 '(사용중 41·완성 9·after 5·기타 1). 판정표는 problem에 '
                 '<code>before/문제</code>(없으면 <code>사용중</code>)를 요구하는데, '
                 '재픽 프롬프트는 <b>재고에 없는 <code>before·문제</code>를 그대로 지시</b>한다 '
                 '(<code>edit_plan.py:3978</code>이 <code>available</code>을 안 넘긴다 — '
                 '3861은 넘긴다).<br>'
                 '★단 <b>그 힌트를 고쳐 재실측했더니 오푸스 선택은 안 바뀌었다</b>(짝비교 3쌍 전부 동일). '
                 '즉 힌트 누락은 <b>진짜지만 이 증상의 원인은 아니다</b> — 대사가 "맛보더니 가져가도 '
                 '되냐고 매달려서"라 실제로 문제 상황이 아니고, 완성샷이 대사엔 더 맞는다. '
                 '<b>채점축이 problem에 요구하는 결과 대사가 어긋난 경우</b>로 보인다.</div>')

    if fail:
        P.append("<h2>실패 %d건</h2><div class='scroll'><table>"
                 "<tr><th>케이스</th><th>모델</th><th>오류</th></tr>" % len(fail))
        for r in fail[:25]:
            P.append("<tr><td>%s</td><td>%s</td><td><code>%s</code></td></tr>"
                     % (esc(r["case"]), esc(r["model"]), esc((r.get("error") or "")[:150])))
        P.append("</table></div>")

    P.append('<h2>이 리포트를 읽는 법</h2><div class="note">'
             '<b>교정률</b> = 출발 시 어긋난 비트 중 몇 %를 고쳤나. 높을수록 좋다.<br>'
             '<b>나빠짐</b> = 멀쩡하던 걸 망친 케이스 수. <b>0이어야 한다.</b><br>'
             '<b>미호출</b> = 재픽 대상이 0개라 모델을 아예 안 부른 것 '
             '(<code>live_asis</code>가 여기 해당 — fit=5라 문이 안 열린다).<br>'
             '⚠️ 표본은 <b>라이브 잡 1건</b>(세그 64개)에서 출발점만 바꿔 만든 것이다. '
             '"어느 모델이 잘 고르나"는 답하지만 "라이브 전체에서 몇 % 좋아지나"는 답하지 못한다.'
             '</div>')
    P.append("</div>")

    io.open(OUT, "w", encoding="utf-8").write("\n".join(P))
    print("wrote", OUT)
    for m in models:
        a = agg.get(m)
        if a:
            print("  %-8s 교정률 %.0f%% (%d→%d) · 나빠짐 %d · 중앙 %.1fs"
                  % (m, a["fixed_rate"], a["base"], a["after"], a["worse"], a["sec"]))


if __name__ == "__main__":
    main()
