"""수급빈집 탑픽 카드 HTML — 시장판단 + 주도섹터 + 탑픽(점수·RS·신호·왜).

card_render(브리핑)와 별개. 캡처요소 .card(420px), 다크+골드, Instrument Serif.
"""
import html
from pathlib import Path

GOLD = "#d4af37"
BG   = "#1a1a1e"


def _verdict_badge(v: str) -> str:
    color = {"GO": "#27c93f", "CAUTION": "#ffbd2e", "STOP": "#ff5f56",
             "NO-GO": "#ff5f56"}.get(v, "#888")
    return f'<span style="color:{color};font-weight:700">● {html.escape(v or "-")}</span>'


def render_picks_card(data: dict) -> str:
    date_s = html.escape(data.get("date", ""))
    mk = data.get("market", {})
    vix = mk.get("vix")
    vix_s = f"VIX {vix}" if vix is not None else ""
    lead = " · ".join(html.escape(s["name"]) for s in data.get("lead_sectors", [])[:4])
    us = " · ".join(html.escape(s) for s in (mk.get("us_strong_sectors") or [])[:4])
    checks = "".join(
        f'<span class="ck {"ok" if r.get("ok") else "no"}">{html.escape(r.get("label",""))}'
        f'{"✓" if r.get("ok") else "✗"}</span>'
        for r in (mk.get("reasons") or [])
    )

    rows = []
    for i, p in enumerate(data.get("picks", [])[:4], 1):
        signals = " · ".join(html.escape(s) for s in p.get("signals", [])[:3])
        atom = p.get("atom") or {}
        why = html.escape((atom.get("why") or "")[:62])
        src = html.escape(atom.get("source") or "")
        why_line = (f'<div class="why">↳ {why}<span class="src"> · {src}</span></div>'
                    if why else "")
        rs = p.get("rs", 0)
        rs_s = f"RS {rs:.0f}" if rs else ""
        rows.append(f"""
      <div class="pick">
        <div class="rk">{i}</div>
        <div class="pm">
          <div class="pn">{html.escape(p.get('name',''))}
            <span class="ps">{html.escape(p.get('sector',''))}</span></div>
          <div class="chips"><b>{p.get('score',0)}점</b> · 빈집{html.escape(p.get('vacancy',''))} {('· '+rs_s) if rs_s else ''}</div>
          <div class="sig">{signals}</div>
          {why_line}
        </div>
      </div>""")
    rows_html = "".join(rows)

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Noto+Sans+KR:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#000; }}
  .card {{ width:420px; background:{BG}; color:#fff; font-family:'Noto Sans KR',sans-serif; }}
  .top {{ padding:26px 26px 18px; background:linear-gradient(135deg,#2a2410,{BG}); border-bottom:1px solid #2c2c34; }}
  .kicker {{ color:{GOLD}; font-size:13px; letter-spacing:2px; font-weight:700; }}
  .title {{ font-family:'Instrument Serif',serif; font-size:32px; line-height:1.15; margin:6px 0 12px; }}
  .meta {{ font-size:13px; color:#bbb; }}
  .checks {{ margin-top:8px; display:flex; gap:6px; flex-wrap:wrap; }}
  .ck {{ font-size:11px; padding:2px 8px; border-radius:10px; background:#222; }}
  .ck.ok {{ color:#27c93f; }}
  .ck.no {{ color:#ff7b72; }}
  .lead {{ margin-top:10px; font-size:13px; color:{GOLD}; font-weight:700; }}
  .us {{ margin-top:4px; font-size:12px; color:#9a9aa2; }}
  .picks {{ padding:8px 22px 20px; }}
  .pick {{ display:flex; gap:12px; padding:14px 4px; border-bottom:1px solid #26262e; }}
  .pick:last-child {{ border-bottom:none; }}
  .rk {{ flex:0 0 26px; height:26px; border-radius:50%; background:{GOLD}; color:#000;
         font-weight:800; font-size:14px; display:flex; align-items:center; justify-content:center; }}
  .pm {{ flex:1; }}
  .pn {{ font-size:18px; font-weight:800; }}
  .ps {{ font-size:12px; color:#999; font-weight:400; margin-left:6px; }}
  .chips {{ font-size:13px; color:#ddd; margin-top:2px; }}
  .chips b {{ color:{GOLD}; }}
  .sig {{ font-size:12px; color:{GOLD}; margin-top:3px; }}
  .why {{ font-size:12px; color:#9a9aa2; margin-top:4px; line-height:1.4; }}
  .why .src {{ color:#666; }}
  .foot {{ padding:14px 26px 22px; font-size:11px; color:#777; border-top:1px solid #26262e; }}
</style></head><body>
  <div class="card">
    <div class="top">
      <div class="kicker">🌅 오늘의 시황 + 수급빈집 탑픽</div>
      <div class="title">주도섹터 × 빈집 × 다중신호</div>
      <div class="meta">{date_s} · 시장 {_verdict_badge(mk.get('verdict',''))} · {html.escape(vix_s)}</div>
      <div class="checks">{checks}</div>
      <div class="lead">주도섹터 — {lead}</div>
      {f'<div class="us">美강세 — {us}</div>' if us else ''}
    </div>
    <div class="picks">{rows_html}</div>
    <div class="foot">로또의 주식 · STOCK BRAIN — 9점표·수급빈집·소르티노 교집합 + 원자DB 근거</div>
  </div>
</body></html>"""


def save_card_html(html_str: str, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_str, encoding="utf-8")
    return out_path
