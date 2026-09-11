"""Pure HTML rendering for the daily project dashboard."""
from datetime import date, timedelta
import html

from dashboard_common import DEFAULT_TRACK, entry_track


def tracks_for(log, category):
    """해당 카테고리에 기록이 있는 트랙명을 최근 활동 순으로 반환."""
    latest = {}
    for e in log:
        if e["category"] != category:
            continue
        t = entry_track(e)
        if t not in latest or e["date"] > latest[t]:
            latest[t] = e["date"]
    return sorted(latest, key=lambda t: (latest[t], t), reverse=True)


def _mini_log(log, category, track, days=7):
    today = date.today()
    marks = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        has_entry = any(
            e["date"] == d and e["category"] == category and entry_track(e) == track
            for e in log
        )
        marks.append("●" if has_entry else "○")
    return "".join(marks)


def _latest_entry(log, category, track):
    matches = [
        e for e in log
        if e["category"] == category and entry_track(e) == track
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda e: e["date"])[-1]


def _track_block(log, category, track):
    latest = _latest_entry(log, category, track)
    summary = html.escape(latest["summary"]) if latest else "(기록 없음)"
    next_step = html.escape(latest["next"]) if latest else "(기록 없음)"
    mini = _mini_log(log, category, track)
    label = ""
    if track != DEFAULT_TRACK:
        label = f'<h3 class="track">{html.escape(track)}</h3>'
    return f"""
  <div class="trackblock">
    {label}
    <p class="summary"><strong>현재:</strong> {summary}</p>
    <p class="next"><strong>다음:</strong> {next_step}</p>
    <p class="minilog">{mini}</p>
  </div>"""


def build_html(config, log):
    cards = []
    for cat in config["categories"]:
        name = cat["name"]
        tracks = tracks_for(log, name)
        if not tracks:
            body = _track_block(log, name, DEFAULT_TRACK)
        else:
            body = "".join(_track_block(log, name, t) for t in tracks)
        cards.append(f"""
<section class="card">
  <h2>{html.escape(name)}</h2>{body}
</section>""")
    body = "\n".join(cards)
    return f"""<title>프로젝트 대시보드</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #fff; color: #111; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #111; color: #eee; }} }}
:root[data-theme="dark"] body {{ background: #111; color: #eee; }}
:root[data-theme="light"] body {{ background: #fff; color: #111; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; max-width: 100%; }}
.card {{ border: 1px solid #8888; border-radius: 8px; padding: 1rem; overflow-x: auto; }}
.card h2 {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
.trackblock {{ border-top: 1px dashed #8886; padding-top: 0.6rem; margin-top: 0.6rem; }}
.trackblock:first-of-type {{ border-top: 0; padding-top: 0; margin-top: 0; }}
.track {{ margin: 0 0 0.3rem; font-size: 0.95rem; opacity: 0.85; }}
.minilog {{ font-size: 1.2rem; letter-spacing: 0.2rem; }}
</style>
<div class="grid">
{body}
</div>
"""
