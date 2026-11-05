# -*- coding: utf-8 -*-
"""숏클 CS 보고서 HTML — 30분마다 다시 만든다(사장님 11-05 'html로 30분에 한 번씩 보고서').

  py -X utf8 tools/shortcl_cs/report_html.py <출력.html>

① 회원별 증상·결과·원인·해결 + Jev 숫자 + '주인 함수 한 곳에서 뿌리 수리했나' = handoff/숏클cs팀_보고서_상태.json(손 관리)
② 최근 24시간 회원 긴급 사건 = 서버 live events(감시와 같은 길 · 관리자 쿠키)
"""
from __future__ import annotations

import html
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / "handoff" / "숏클cs팀_보고서_상태.json"
KIND = {"stuck": "멈춤", "bug": "결함 신고", "code_fix": "엔진 손수정", "message": "보고", "done": "완성"}
ROOT_LABEL = {"뿌리": ("root", "뿌리 수리 · 함수 한 곳"), "부분": ("part", "뿌리 일부"), "증상": ("sym", "그 자리 수리"), "결정": ("dec", "사장님 결정 반영")}


def fetch_events(hours: float = 24.0) -> list[dict]:
    import requests
    from tools.live_admin import BASE, admin_cookie
    s, ck = requests.Session(), admin_cookie()
    head = {"Cookie": f"dash_auth={ck}", "Accept": "application/json"}
    first = s.get(f"{BASE}/api/admin/claude/live/events", params={"urgent": 1, "since_id": 0, "limit": 1}, headers=head, timeout=30).json()
    last = int(first.get("last_id") or 0)
    since, cut, out = max(0, last - 3000), time.time() - hours * 3600, []
    while True:
        d = s.get(f"{BASE}/api/admin/claude/live/events", params={"urgent": 1, "since_id": since, "limit": 200}, headers=head, timeout=30).json()
        ev = d.get("events") or []
        out += [e for e in ev if float(e.get("ts") or 0) >= cut]
        if len(ev) < 200:
            break
        since = int(ev[-1]["id"])
    return out


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def build(state: dict, events: list[dict]) -> str:
    now = time.strftime("%Y-%m-%d %H:%M")
    cases = state.get("cases") or []
    rc = Counter(c.get("root") for c in cases)
    kinds = Counter(e.get("kind") for e in events)
    by_member = defaultdict(list)
    for e in events:
        by_member[f"{e.get('member') or '회원'}({e.get('cid')})"].append(e)
    rows = []
    for c in cases:
        cls, lab = ROOT_LABEL.get(c.get("root"), ("sym", c.get("root") or ""))
        rows.append(f"""<tr><td class="who">{esc(c.get('member'))}</td><td>{esc(c.get('symptom'))}<div class="sub">{esc(c.get('result'))}</div></td>
<td>{esc(c.get('cause'))}</td><td>{esc(c.get('fix'))}<div class="sub mono">{esc(c.get('owner'))}</div></td>
<td class="num">{esc(c.get('jev'))}</td><td><span class="pill {cls}">{esc(lab)}</span></td>
<td class="sub">{esc(c.get('status'))}<div class="mono">{esc(c.get('commit'))}</div></td></tr>""")
    ev_rows = []
    for e in sorted(events, key=lambda x: -int(x.get("id") or 0))[:60]:
        t = time.strftime("%m-%d %H:%M", time.localtime(float(e.get("ts") or 0)))
        ev_rows.append(f"""<tr><td class="num">{t}</td><td class="who">{esc(e.get('member') or '회원')}<span class="sub"> {esc(e.get('cid'))}</span></td>
<td><span class="tag k-{esc(e.get('kind'))}">{esc(KIND.get(e.get('kind'), e.get('kind')))}</span></td>
<td>{esc(' '.join(str(e.get('text') or '').split())[:220])}</td></tr>""")
    mem = sorted(by_member.items(), key=lambda kv: -len(kv[1]))[:12]
    mem_html = "".join(f"<li><b>{esc(k)}</b> <span class='num'>{len(v)}</span><span class='sub'> · " +
                       esc(", ".join(f"{KIND.get(a, a)} {n}" for a, n in Counter(x.get('kind') for x in v).most_common())) + "</span></li>" for k, v in mem)
    dec = "".join(f"<li>{esc(d.get('what'))}<span class='sub'> — {esc(d.get('why'))}</span></li>" for d in state.get("decisions") or [])
    que = "".join(f"<li><b>{esc(q.get('member'))}</b> · {esc(q.get('what'))}</li>" for q in state.get("queue") or [])
    return f"""<title>숏클 CS 상황판</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* 상황판: 위에 숫자 한 줄 → 수리 표(회원별) → 결정 대기·조사 대기 → 최근 24시간 사건 */
:root {{ --bg:#f6f7f5; --panel:#ffffff; --fg:#1d2420; --mute:#5f6b64; --line:#dde3df; --accent:#1f6f5c;
  --ok:#1f7a4d; --okbg:#e3f3ea; --warn:#9a6300; --warnbg:#fbf0d9; --bad:#a3352b; --badbg:#f8e3e0; --info:#2f5f8f; --infobg:#e3edf7;
  --sans:"IBM Plex Sans KR",system-ui,"Malgun Gothic",sans-serif; --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#141816; --panel:#1b201d; --fg:#e4ebe7; --mute:#9aa8a0; --line:#2c3430; --accent:#5cc3a6;
  --ok:#7fd6a5; --okbg:#1d3328; --warn:#f0c26b; --warnbg:#3a2f17; --bad:#f19a90; --badbg:#3d2220; --info:#9cc3ea; --infobg:#1d2b3a; color-scheme:dark }} }}
:root[data-theme="dark"] {{ --bg:#141816; --panel:#1b201d; --fg:#e4ebe7; --mute:#9aa8a0; --line:#2c3430; --accent:#5cc3a6;
  --ok:#7fd6a5; --okbg:#1d3328; --warn:#f0c26b; --warnbg:#3a2f17; --bad:#f19a90; --badbg:#3d2220; --info:#9cc3ea; --infobg:#1d2b3a; color-scheme:dark }}
body {{ background:var(--bg); color:var(--fg); font-family:var(--sans); font-size:14px; line-height:1.55 }}
.wrap {{ max-width:1180px; margin:0 auto; padding-block:24px 48px; padding-left:max(16px, env(safe-area-inset-left,0px)); padding-right:max(16px, env(safe-area-inset-right,0px)); display:grid; gap:22px }}
h1 {{ font-size:22px; margin:0; text-wrap:balance }} h2 {{ font-size:16px; margin:0 0 10px }}
.meta {{ color:var(--mute); font-size:13px }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 14px; min-width:120px }}
.stat b {{ display:block; font-size:22px; font-variant-numeric:tabular-nums }} .stat span {{ color:var(--mute); font-size:12px; letter-spacing:.02em }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; min-width:0 }}
.scroll {{ overflow-x:auto }}
table {{ border-collapse:collapse; width:100%; min-width:900px }}
th,td {{ text-align:left; vertical-align:top; padding:9px 10px; border-bottom:1px solid var(--line) }}
th {{ font-size:12px; color:var(--mute); font-weight:600; letter-spacing:.03em; white-space:nowrap }}
.who {{ font-weight:600; white-space:nowrap }} .sub {{ color:var(--mute); font-size:12px; margin-top:3px }}
.mono {{ font-family:var(--mono); font-size:12px }} .num {{ font-variant-numeric:tabular-nums; white-space:nowrap }}
.pill {{ display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px; font-weight:600; white-space:nowrap }}
.root {{ background:var(--okbg); color:var(--ok) }} .part {{ background:var(--warnbg); color:var(--warn) }} .sym {{ background:var(--badbg); color:var(--bad) }} .dec {{ background:var(--infobg); color:var(--info) }}
.tag {{ font-size:12px; padding:1px 7px; border-radius:4px; background:var(--infobg); color:var(--info); white-space:nowrap }}
.k-stuck {{ background:var(--badbg); color:var(--bad) }} .k-code_fix {{ background:var(--warnbg); color:var(--warn) }} .k-bug {{ background:var(--badbg); color:var(--bad) }}
.cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:22px }}
ul {{ margin:0; padding-left:18px; display:grid; gap:6px }}
</style>
<div class="wrap">
<header><h1>숏클 CS 상황판</h1><div class="meta">갱신 {now} · 30분마다 다시 만듦 · 회원 사건 = 최근 24시간 긴급(서버 기록) · 수리·결정 = 숏클cs팀 상태 파일</div></header>
<div class="stats">
<div class="stat"><b>{len(events)}</b><span>24시간 긴급 사건</span></div>
<div class="stat"><b>{kinds.get('stuck', 0)}</b><span>멈춤</span></div>
<div class="stat"><b>{kinds.get('code_fix', 0)}</b><span>회원 엔진 손수정</span></div>
<div class="stat"><b>{len(cases)}</b><span>정리한 결함</span></div>
<div class="stat"><b>{rc.get('뿌리', 0)}</b><span>뿌리 수리(함수 한 곳)</span></div>
<div class="stat"><b>{rc.get('부분', 0) + rc.get('증상', 0)}</b><span>뿌리 아님·일부</span></div>
</div>
<section><h2>회원 증상 → 원인 → 해결</h2><div class="scroll"><table>
<thead><tr><th>회원</th><th>증상 · 결과</th><th>문제점(원인)</th><th>해결 · 주인 함수</th><th>Jev</th><th>뿌리?</th><th>상태</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>
<div class="cols">
<section><h2>사장님 결정 대기</h2><ul>{dec}</ul></section>
<section><h2>조사 대기 결함</h2><ul>{que}</ul></section>
<section><h2>24시간 회원별 사건</h2><ul>{mem_html}</ul></section>
</div>
<section><h2>최근 긴급 사건(최신 60건)</h2><div class="scroll"><table>
<thead><tr><th>시각</th><th>회원</th><th>종류</th><th>내용</th></tr></thead><tbody>{''.join(ev_rows)}</tbody></table></div></section>
</div>
"""


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = Path(sys.argv[1])
    state = json.loads(STATE.read_text(encoding="utf-8"))
    try:
        ev = fetch_events()
    except Exception as e:      # noqa: BLE001 — 서버가 안 되면 수리 표만이라도
        print("사건 못 읽음:", type(e).__name__, e)
        ev = []
    out.write_text(build(state, ev), encoding="utf-8")
    print("만듦", out, "사건", len(ev), "결함", len(state.get("cases") or []))


if __name__ == "__main__":
    main()
