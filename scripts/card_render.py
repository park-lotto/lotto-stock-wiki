"""브리핑 카드 HTML 합성 — 다크+골드, Instrument Serif, 캡처요소 .card(420px)."""
import html
from pathlib import Path

GOLD = "#d4af37"
BG   = "#1a1a1e"


def render_briefing_card(data: dict, hero_path: Path = None) -> str:
    hero_html = f'<img class="hero" src="{Path(hero_path).as_uri()}" alt="">' if hero_path else ""
    sectors = " · ".join(html.escape(s) for s in data.get("lead_sectors", [])[:4])
    sectors_html = f'<div class="sectors">🔴 강세 — {sectors}</div>' if sectors else ""
    lines_html = "".join(
        f'<li>{html.escape(ln)}</li>' for ln in data.get("lines", [])[:5]
    )
    date_s = html.escape(data.get('date', ''))
    headline_s = html.escape(data.get('headline', ''))
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#000; }}
  .card {{ width:420px; background:{BG}; color:#fff; font-family:'Noto Sans KR',sans-serif;
           border-radius:24px; overflow:hidden; }}
  .hero {{ width:100%; height:240px; object-fit:cover; }}
  .body {{ padding:28px 26px 34px; }}
  .date {{ color:{GOLD}; font-size:14px; letter-spacing:2px; }}
  .headline {{ font-family:'Instrument Serif',serif; font-size:34px; line-height:1.2;
               margin:10px 0 6px; }}
  .sectors {{ color:{GOLD}; font-size:15px; font-weight:700; margin-bottom:18px; }}
  ul {{ list-style:none; }}
  li {{ font-size:16px; line-height:1.7; padding-left:18px; position:relative; color:#e8e8ea; }}
  li::before {{ content:"›"; color:{GOLD}; position:absolute; left:0; }}
  .foot {{ margin-top:22px; font-size:12px; color:#888; }}
</style></head><body>
  <div class="card">
    {hero_html}
    <div class="body">
      <div class="date">{date_s}  ·  아침 브리핑</div>
      <div class="headline">{headline_s}</div>
      {sectors_html}
      <ul>{lines_html}</ul>
      <div class="foot">로또의 주식 · STOCK BRAIN</div>
    </div>
  </div>
</body></html>"""


def save_card_html(html: str, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
