# -*- coding: utf-8 -*-
"""숏클 CS 기록 — 가벼운 한 장(사장님 11-05 '가벼운 페이지 · CS 기록 계속 올려 · 다른 PC 에서도').

  py -X utf8 tools/shortcl_cs/cs_log_page.py <출력.html> [--hours 72]

글꼴·라이브러리 없음(시스템 글꼴) · 검색 칸 하나. 내용:
  ① 결함 처리 표 = handoff/숏클cs팀_보고서_상태.json(증상·원인·해결·Jev·뿌리)
  ② 사건 장부 = handoff/숏클cs팀_사건장부.md 표
  ③ 최근 N시간 회원 긴급 사건 = 서버 live events(감시와 같은 길)
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.shortcl_cs.report_html import KIND, ROOT_LABEL, fetch_events  # noqa: E402

STATE = ROOT / "handoff" / "숏클cs팀_보고서_상태.json"
LEDGER = ROOT / "handoff" / "숏클cs팀_사건장부.md"


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def ledger_rows() -> list[list[str]]:
    rows = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if ln.startswith("| ") and not ln.startswith("| 사건") and not re.match(r"^\|[-| ]+\|$", ln):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 6:
                rows.append(cells[:7])
    return rows


def build(state: dict, events: list[dict], hours: float) -> str:
    now = time.strftime("%Y-%m-%d %H:%M")
    fx = "".join(
        f"<tr><td><b>{esc(c.get('member'))}</b></td><td>{esc(c.get('symptom'))}<br><small>{esc(c.get('result'))}</small></td>"
        f"<td>{esc(c.get('cause'))}</td><td>{esc(c.get('fix'))}<br><small><code>{esc(c.get('owner'))}</code></small></td>"
        f"<td class=n>{esc(c.get('jev'))}</td><td><span class='p {ROOT_LABEL.get(c.get('root'), ('sym', ''))[0]}'>{esc(ROOT_LABEL.get(c.get('root'), ('', c.get('root')))[1])}</span></td>"
        f"<td><small>{esc(c.get('status'))}<br><code>{esc(c.get('commit'))}</code></small></td></tr>" for c in state.get("cases") or [])
    led = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>" for r in reversed(ledger_rows()))
    ev = "".join(
        f"<tr><td class=n>{time.strftime('%m-%d %H:%M', time.localtime(float(e.get('ts') or 0)))}</td><td class=n>#{esc(e.get('id'))}</td>"
        f"<td><b>{esc(e.get('member') or '회원')}</b> <small>{esc(e.get('cid'))}</small></td><td><span class='k k-{esc(e.get('kind'))}'>{esc(KIND.get(e.get('kind'), e.get('kind')))}</span></td>"
        f"<td>{esc(' '.join(str(e.get('text') or '').split())[:400])}</td></tr>" for e in sorted(events, key=lambda x: -int(x.get("id") or 0)))
    dec = "".join(f"<li>{esc(d.get('what'))} <small>— {esc(d.get('why'))}</small></li>" for d in state.get("decisions") or [])
    que = "".join(f"<li><b>{esc(q.get('member'))}</b> · {esc(q.get('what'))}</li>" for q in state.get("queue") or [])
    return f"""<title>숏클 CS 기록</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* 가벼운 기록장: 시스템 글꼴, 검색 한 칸, 표 넷 */
:root {{ --bg:#fafaf8; --fg:#1e2321; --mute:#68716c; --line:#e1e5e2; --head:#f0f2f0; --ok:#1d7448; --okb:#e2f2e8; --wa:#946000; --wab:#faefd6; --bad:#a1342a; --badb:#f7e2df; --in:#2c5c8c; --inb:#e2ecf6 }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#151817; --fg:#e3e9e6; --mute:#9aa6a0; --line:#2b3330; --head:#1d2220; --ok:#82d6a7; --okb:#1c3227; --wa:#efc26c; --wab:#382e16; --bad:#f09b91; --badb:#3b2220; --in:#9dc3ea; --inb:#1c2a39; color-scheme:dark }} }}
:root[data-theme="dark"] {{ --bg:#151817; --fg:#e3e9e6; --mute:#9aa6a0; --line:#2b3330; --head:#1d2220; --ok:#82d6a7; --okb:#1c3227; --wa:#efc26c; --wab:#382e16; --bad:#f09b91; --badb:#3b2220; --in:#9dc3ea; --inb:#1c2a39; color-scheme:dark }}
body {{ background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,"Malgun Gothic","Apple SD Gothic Neo",sans-serif }}
.w {{ max-width:1200px; margin:0 auto; padding-block:18px 40px; padding-left:max(16px, env(safe-area-inset-left,0px)); padding-right:max(16px, env(safe-area-inset-right,0px)); display:grid; gap:18px }}
h1 {{ font-size:20px; margin:0 }} h2 {{ font-size:15px; margin:0 0 8px }} small,.m {{ color:var(--mute) }}
input {{ width:100%; max-width:420px; padding:8px 10px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); font:inherit }}
input:focus-visible {{ outline:2px solid var(--in); outline-offset:1px }}
.s {{ overflow-x:auto; border:1px solid var(--line); border-radius:6px }}
table {{ border-collapse:collapse; width:100%; min-width:860px }}
th,td {{ text-align:left; vertical-align:top; padding:7px 9px; border-bottom:1px solid var(--line) }}
th {{ background:var(--head); font-size:12px; color:var(--mute); white-space:nowrap }}
.n {{ white-space:nowrap; font-variant-numeric:tabular-nums }} code {{ font-size:12px }}
.p,.k {{ font-size:12px; padding:1px 7px; border-radius:999px; white-space:nowrap; background:var(--inb); color:var(--in) }}
.root {{ background:var(--okb); color:var(--ok) }} .part,.k-code_fix {{ background:var(--wab); color:var(--wa) }} .sym,.k-stuck,.k-bug {{ background:var(--badb); color:var(--bad) }}
.c {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:18px }} ul {{ margin:0; padding-left:18px }}
</style>
<div class="w">
<div><h1>숏클 CS 기록</h1><div class="m">갱신 {now} · 30분마다 · 회원 사건 = 최근 {int(hours)}시간 긴급(서버 기록 {len(events)}건)</div></div>
<input id="q" type="search" placeholder="회원 이름·편 번호·낱말로 찾기" aria-label="기록 찾기">
<section><h2>결함 처리(증상 → 원인 → 해결 · Jev · 함수 한 곳 뿌리 수리인가)</h2><div class="s"><table>
<thead><tr><th>회원</th><th>증상·결과</th><th>원인</th><th>해결·주인 함수</th><th>Jev</th><th>뿌리?</th><th>상태</th></tr></thead><tbody>{fx}</tbody></table></div></section>
<div class="c"><section><h2>사장님 결정 대기</h2><ul>{dec}</ul></section><section><h2>조사 대기 결함</h2><ul>{que}</ul></section></div>
<section><h2>회원 긴급 사건(최신순)</h2><div class="s"><table>
<thead><tr><th>시각</th><th>번호</th><th>회원</th><th>종류</th><th>내용</th></tr></thead><tbody>{ev}</tbody></table></div></section>
<section><h2>사건 장부(최신순)</h2><div class="s"><table>
<thead><tr><th>사건</th><th>시각</th><th>회원</th><th>종류</th><th>요지</th><th>상태</th><th>근거</th></tr></thead><tbody>{led}</tbody></table></div></section>
</div>
<script>
(function(){{var q=document.getElementById('q');q.addEventListener('input',function(){{var v=q.value.trim().toLowerCase();
document.querySelectorAll('tbody tr').forEach(function(r){{r.hidden=!!v&&r.textContent.toLowerCase().indexOf(v)<0}});
document.querySelectorAll('ul li').forEach(function(r){{r.hidden=!!v&&r.textContent.toLowerCase().indexOf(v)<0}});}});}})();
</script>
"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = Path(sys.argv[1])
    hours = float(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 72.0
    state = json.loads(STATE.read_text(encoding="utf-8"))
    try:
        ev = fetch_events(hours)
    except Exception as e:      # noqa: BLE001
        print("사건 못 읽음:", type(e).__name__, e)
        ev = []
    out.write_text(build(state, ev, hours), encoding="utf-8")
    print("만듦", out, "사건", len(ev), "장부", len(ledger_rows()))


if __name__ == "__main__":
    main()
