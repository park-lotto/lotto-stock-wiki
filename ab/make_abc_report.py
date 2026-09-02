# -*- coding: utf-8 -*-
"""A/B/C 비교표 — 같은 비트에 세 방식이 각각 고른 **화면을 나란히** 놓는다.

★왜 눈으로 보게 하나:
  B·C는 역할축을 안 준 답이다. 그걸 축(`beat_role_mismatch`)으로 채점하면 이번
  problem 사고가 그대로 재현된다(축이 요구하는 결과 대사가 어긋난 경우가 있다).
  기계 채점은 참고로만 싣고, **사장님이 화면을 보고 판단**하시는 게 맞다.
"""
import base64
import io
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(_HERE, "frames")
OUT = os.path.join(_HERE, "비교표.html")

MODE_LABEL = {
    "prod": "A · 현재 방식",
    "free": "B · 자유 판단",
    "image": "C · 이미지 보고",
}
MODE_DESC = {
    "prod": "텍스트 캡션 + 역할축 강제 (지금 라이브)",
    "free": "텍스트 캡션만, 축 없이 “대본에 맞는 걸 골라라”",
    "image": "실제 프레임 이미지 + 캡션을 보고",
}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def img_tag(sid, cls=""):
    p = os.path.join(FRAMES, "%s.jpg" % sid) if sid else None
    if not p or not os.path.exists(p):
        return '<div class="noimg">%s</div>' % esc(sid or "—")
    b = base64.b64encode(io.open(p, "rb").read()).decode()
    return '<img class="%s" src="data:image/jpeg;base64,%s" alt="%s">' % (cls, b, esc(sid or ""))


def main():
    rows = [r for r in json.load(io.open(os.path.join(_HERE, "abc_results.json"),
                                        encoding="utf-8")) if r.get("ok")]
    job = json.load(io.open(os.path.join(_HERE, "job_409f894230c6.json"), encoding="utf-8"))
    beats = job["edit_plan"]["beats"]
    seg = {}
    for _s, v in job["extract"].items():
        for x in (v or {}).get("segments") or []:
            seg[x["seg_id"]] = x

    models = sorted({r["model"] for r in rows})
    modes = ["prod", "free", "image"]

    P = ["<title>매칭 방식 비교 A/B/C</title>"]
    P.append("""<style>
:root{--bg:#fbfaf9;--fg:#1a1a19;--mut:#6b6b68;--line:#e3e0dc;--card:#fff;
--good:#1a7f5a;--bad:#b3402f;--warn:#8a6d1f;--accent:#2b5f8f}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#191817;--fg:#eceae7;
--mut:#a09d98;--line:#343230;--card:#211f1e;--good:#5fce9f;--bad:#f08a75;--warn:#d9bc6a;
--accent:#7fb2de}}
:root[data-theme="dark"]{--bg:#191817;--fg:#eceae7;--mut:#a09d98;--line:#343230;--card:#211f1e;
--good:#5fce9f;--bad:#f08a75;--warn:#d9bc6a;--accent:#7fb2de}
body{background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Segoe UI",
"Malgun Gothic",sans-serif;margin:0;padding:26px 18px 70px}
.w{max-width:1180px;margin:0 auto}
h1{font-size:25px;margin:0 0 5px;letter-spacing:-.02em}
h2{font-size:17px;margin:36px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.sub{color:var(--mut);font-size:13.5px;margin-bottom:20px}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--warn);
border-radius:8px;padding:13px 16px;margin:16px 0;font-size:13.5px}
.beat{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:16px 18px;margin:18px 0}
.blabel{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.narr{font-size:15.5px;font-weight:600;margin:5px 0 14px;line-height:1.45}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:13px}
.cell{border:1px solid var(--line);border-radius:9px;overflow:hidden;background:var(--bg)}
.cell .hd{padding:7px 10px;font-size:12px;font-weight:600;border-bottom:1px solid var(--line);
display:flex;justify-content:space-between;gap:6px;align-items:center}
.cell img{width:100%;display:block;aspect-ratio:9/16;object-fit:cover}
.noimg{aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;
color:var(--mut);font-size:12px;background:rgba(128,128,128,.08)}
.cell .ft{padding:7px 10px;font-size:11.5px;color:var(--mut);line-height:1.45}
.tag{font-size:10.5px;padding:1px 6px;border-radius:99px;border:1px solid var(--line);
color:var(--mut);white-space:nowrap}
.same{outline:2px solid var(--accent);outline-offset:-2px}
table{border-collapse:collapse;width:100%;font-size:13.5px;background:var(--card);
border:1px solid var(--line);border-radius:9px;overflow:hidden}
th,td{padding:8px 11px;text-align:left;border-bottom:1px solid var(--line)}
th{background:rgba(128,128,128,.07);font-weight:600;font-size:12.5px}
tr:last-child td{border-bottom:none}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.good{color:var(--good);font-weight:600}.bad{color:var(--bad);font-weight:600}
.scroll{overflow-x:auto}
code{background:rgba(128,128,128,.13);padding:1px 5px;border-radius:4px;font-size:12.5px}
</style>""")
    P.append('<div class="w">')
    P.append("<h1>매칭 방식 비교 — A / B / C</h1>")
    P.append('<div class="sub">같은 대본·같은 후보(56개)에 <b>물어보는 방식만</b> 바꿔 '
             '고르게 한 결과. 실측 %d건.</div>' % len(rows))

    P.append('<div class="note"><b>세 방식이 무엇이 다른가</b><br>'
             '<b>A · 현재 방식</b> — 1단계가 만든 <b>텍스트 캡션만</b> 읽고, '
             '<code>역할:problem → 결 before·문제 우선</code> 같은 <b>정해진 축을 강제</b>. '
             '<b>이미지는 한 장도 안 본다.</b><br>'
             '<b>B · 자유 판단</b> — 같은 텍스트 캡션이지만 <b>축 없이</b> '
             '“대본에 맞는 걸 골라라”.<br>'
             '<b>C · 이미지 보고</b> — <b>실제 프레임 이미지</b>를 보고 고른다(사장님이 말씀하신 방식).</div>')

    # ── 비트별 화면 나란히 ────────────────────────────────────────
    P.append("<h2>비트별 — 무엇을 골랐나 (화면으로)</h2>")
    P.append('<div class="note">같은 칸에 <b>같은 화면</b>이 나오면 방식이 달라도 결론이 같다는 뜻이다. '
             '테두리가 표시된 것은 <b>세 방식이 모두 같은 것을 고른</b> 경우.</div>')

    for b in beats:
        bi = b["beat_idx"]
        P.append('<div class="beat">')
        P.append('<div class="blabel">비트 %d · %s</div>' % (bi, esc(b.get("role") or "")))
        P.append('<div class="narr">%s</div>' % esc(b.get("narration") or ""))
        P.append('<div class="grid">')
        # 원본(라이브)
        live = (b.get("primary") or {}).get("seg_id")
        P.append('<div class="cell"><div class="hd"><span>라이브 원본</span>'
                 '<span class="tag">%s</span></div>%s'
                 '<div class="ft">%s</div></div>'
                 % (esc(live or "—"), img_tag(live),
                    esc((seg.get(live, {}).get("scene_desc") or "")[:60])))
        # 방식 × 모델
        for mode in modes:
            for m in models:
                rs = [r for r in rows if r["mode"] == mode and r["model"] == m]
                if not rs:
                    continue
                picked = [r.get("picks", {}).get(str(bi)) or r.get("picks", {}).get(bi)
                          for r in rs]
                picked = [p for p in picked if p]
                if not picked:
                    continue
                # 최빈값(여러 회 돌렸으므로)
                top = max(set(picked), key=picked.count)
                stable = picked.count(top)
                P.append('<div class="cell"><div class="hd"><span>%s<br><span class="tag">%s</span></span>'
                         '<span class="tag">%d/%d</span></div>%s'
                         '<div class="ft">%s<br><b>%s</b></div></div>'
                         % (esc(MODE_LABEL[mode].split(" · ")[0]), esc(m), stable, len(picked),
                            img_tag(top), esc(top),
                            esc((seg.get(top, {}).get("scene_desc") or "")[:55])))
        P.append("</div></div>")

    # ── 방식별 요약 ───────────────────────────────────────────────
    P.append("<h2>방식별 요약 (기계 채점 — 참고용)</h2>")
    P.append('<div class="note">⚠️ 채점축 <code>beat_role_mismatch</code>는 <b>A의 축</b>이다. '
             'B·C는 그 축을 안 받고 고른 답이라 <b>이 표에서 불리하다.</b> '
             '숫자가 낮다고 좋은 게 아니라 <b>축과 얼마나 같은 답을 냈나</b>로 읽어라. '
             '진짜 판단은 위 화면이다.</div>')
    P.append("<div class='scroll'><table><tr><th>방식</th><th>모델</th>"
             "<th class='num'>채운 칸</th><th class='num'>축 기준 어긋남</th>"
             "<th class='num'>중앙 초</th><th>설명</th></tr>")
    import statistics
    for mode in modes:
        for m in models:
            rs = [r for r in rows if r["mode"] == mode and r["model"] == m]
            if not rs:
                continue
            filled = statistics.mean([r.get("filled", 0) for r in rs])
            bad = statistics.mean([r.get("axis_bad", 0) for r in rs])
            sec = statistics.median([r.get("seconds", 0) for r in rs])
            P.append("<tr><td><b>%s</b></td><td>%s</td><td class='num'>%.1f/5</td>"
                     "<td class='num'>%.1f</td><td class='num'>%.1f</td>"
                     "<td style='color:var(--mut);font-size:12.5px'>%s</td></tr>"
                     % (esc(MODE_LABEL[mode]), esc(m), filled, bad, sec, esc(MODE_DESC[mode])))
    P.append("</table></div>")

    P.append('<div class="note"><b>보실 때</b><br>'
             '① 같은 비트에서 A와 C가 <b>다른 화면</b>을 골랐다면 — 이미지를 본 효과가 있다는 뜻.<br>'
             '② A와 B가 다르면 — <b>역할축</b>이 결과를 바꾸고 있다는 뜻.<br>'
             '③ 셋이 같으면 — 그 자리는 어떻게 물어봐도 같으니 <b>지금 방식으로 충분</b>하다.<br>'
             '⚠️ 표본은 <b>라이브 잡 1건</b>(쿠키 레시피)이다.</div>')
    P.append("</div>")

    io.open(OUT, "w", encoding="utf-8").write("\n".join(P))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
