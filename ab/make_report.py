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
        called = [r for r in rs if r.get("seconds", 0) > 0.5]
        beats = sum(r["n_beats"] for r in called)
        base = sum(r["base_bad"] for r in called)
        after = sum(r["after_bad"] for r in called)
        worse = [r for r in called if r["after_bad"] > r["base_bad"]]
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
        if r.get("seconds", 0) <= 0.5:
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
