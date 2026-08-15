"""대본 스타일 실험실 — 결과 보기 페이지 생성.

gen.py가 서버에서 만든 out/*.json을 읽어 한 장짜리 HTML로 만든다(외부 의존 0).
scene_lab과 같은 방식: 라이브를 안 건드리고 로컬에서 눈으로 확정한다.

    py tools/script_lab/build.py            # 가장 최근 결과
    py tools/script_lab/build.py 1786774879 # 특정 결과
"""
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def _esc(s):
    return html.escape(str(s or ""))


def _draft_html(d):
    checks = d.get("checks") or []
    passed = d.get("passed")
    badge = ('<span class="badge ok">구조 통과</span>' if passed
             else '<span class="badge no">재작성 대상</span>')
    views = d.get("evidence_views") or []
    ev = (" · ".join(f"{v // 10000}만" for v in views[:4])) if views else "실적 없음(가설)"
    rows = "".join(
        f'<li class="{"ok" if c["ok"] else "no"}">'
        f'<b>{"O" if c["ok"] else "X"}</b> {_esc(c["name"])}'
        f'<span class="detail">{_esc(c["detail"])}</span></li>'
        for c in checks)
    beats = "".join(
        f'<div class="beat"><span class="role">{_esc(b.get("role"))}</span>'
        f'<p>{_esc(b.get("text"))}</p></div>'
        for b in (d.get("beats") or []))
    err = f'<p class="err">{_esc(d["error"])}</p>' if d.get("error") else ""
    return f"""
<section class="card">
  <header>
    <h2>{_esc(d.get("style_name"))} {badge}</h2>
    <p class="meta">출처 {_esc(d.get("source"))} · 실적 {_esc(ev)} · 생성 {_esc(d.get("sec"))}초</p>
  </header>
  {err}
  <div class="beats">{beats}</div>
  <h3>게이트</h3>
  <ul class="checks">{rows}</ul>
  <details><summary>보낸 지시문 보기</summary><pre>{_esc(d.get("prompt"))}</pre></details>
</section>"""


def build(stamp=None):
    files = sorted(OUT.glob("*.json"))
    if not files:
        print("결과가 없다. 먼저 서버에서 gen.py를 돌려라.")
        return 1
    path = (OUT / f"{stamp}.json") if stamp else files[-1]
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = "".join(_draft_html(d) for d in data.get("drafts") or [])
    out = HERE / "index.html"
    out.write_text(f"""<!doctype html><meta charset="utf-8">
<title>대본 스타일 실험실</title>
<style>
:root {{ color-scheme: light dark; --bg:#fff; --fg:#111; --mut:#666; --line:#ddd;
        --ok:#0a7d3f; --no:#b3261e; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#14161a; --fg:#e8eaed; --mut:#9aa3af; --line:#333; --ok:#5ddc9a; --no:#ff8a80; }} }}
body {{ margin:0; padding:24px; background:var(--bg); color:var(--fg);
       font:16px/1.65 system-ui,'Malgun Gothic',sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; }}
.topic {{ color:var(--mut); margin:0 0 20px; }}
.wrap {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(380px,1fr)); gap:18px; }}
.card {{ border:1px solid var(--line); border-radius:12px; padding:18px; }}
.card h2 {{ font-size:18px; margin:0 0 2px; }}
.meta {{ color:var(--mut); font-size:13.5px; margin:0 0 14px; }}
.badge {{ font-size:12.5px; padding:2px 8px; border-radius:999px; vertical-align:middle; }}
.badge.ok {{ background:var(--ok); color:#fff; }}
.badge.no {{ background:var(--no); color:#fff; }}
.beat {{ border-left:3px solid var(--line); padding:2px 0 2px 12px; margin:0 0 10px; }}
.role {{ font-size:12px; color:var(--mut); letter-spacing:.04em; text-transform:uppercase; }}
.beat p {{ margin:2px 0 0; }}
h3 {{ font-size:14px; color:var(--mut); margin:18px 0 6px; }}
.checks {{ list-style:none; padding:0; margin:0; font-size:14px; }}
.checks li {{ padding:4px 0; border-bottom:1px dashed var(--line); }}
.checks li.ok b {{ color:var(--ok); }}
.checks li.no b {{ color:var(--no); }}
.detail {{ display:block; color:var(--mut); font-size:13px; }}
.err {{ color:var(--no); }}
pre {{ white-space:pre-wrap; font-size:13px; color:var(--mut); }}
</style>
<h1>대본 스타일 실험실</h1>
<p class="topic">소재: {_esc(data.get("topic"))} · 사실재료: {_esc(data.get("facts"))}
 · 목표 {_esc(data.get("seconds"))}초</p>
<div class="wrap">{cards}</div>
""", encoding="utf-8")
    print("만듦:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(build(sys.argv[1] if len(sys.argv) > 1 else None))
