# -*- coding: utf-8 -*-
"""error_help.js(정본)를 읽어 '고객이 보게 될 모양' 미리보기 HTML을 만든다.

★손으로 문구를 옮겨 적지 않는다 — 정본에서 뽑는다. 그래야 문구를 고칠 때
   미리보기가 저절로 따라오고, 둘이 어긋나지 않는다(CLAUDE.md 0순위-B).

사용: py tools/error_help_preview.py   → out/에러문구_미리보기.html (+ 바탕화면 복사)
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "shopping_shorts" / "static" / "error_help.js"

GROUPS = [
    ("통신·서버", ["network", "server_500", "login_expired", "not_approved"]),
    ("대본 만들기(AI)", ["gen_no_keys", "gen_exhausted", "gen_rate_limit",
                     "gen_api_error", "gen_empty", "gen_style_mismatch"]),
    ("영상 담기·분석", ["src_login_required", "src_private", "src_download",
                   "src_timeout", "src_ai_busy", "yt_blocked"]),
    ("미리보기", ["preview_black", "preview_frozen", "preview_stale"]),
    ("제작·내보내기", ["render_fail", "tts_silent", "caption_remove_fail",
                  "capcut_bat", "save_fail"]),
]


def load():
    """node로 정본을 실행해 항목 표를 그대로 받는다(파싱 흉내 금지)."""
    code = ("global.window={};require(%s);"
            "process.stdout.write(JSON.stringify(window.ErrorHelp.map));"
            % json.dumps(str(SRC).replace("\\", "/")))
    out = subprocess.run([_node(), "-e", code], capture_output=True)
    if out.returncode != 0:
        sys.exit("정본을 읽지 못했습니다: " + out.stderr.decode("utf-8", "replace"))
    return json.loads(out.stdout.decode("utf-8"))


def _node():
    return shutil.which("node") or "node"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build(m):
    seen = set()
    body = []
    for title, keys in GROUPS:
        rows = []
        for k in keys:
            e = m.get(k)
            if not e:
                continue
            seen.add(k)
            src = e.get("src", "")
            rows.append(
                '<div class="item"><div class="key">%s</div>'
                '<div class="errHelp"><b>%s</b>'
                '<div class="errWhy">%s</div>'
                '<div class="errTodo">&#128073; %s</div></div>%s</div>'
                % (esc(k), esc(e["title"]), esc(e["why"]), esc(e["todo"]),
                   ('<div class="src">근거: %s</div>' % esc(src)) if src else ""))
        if rows:
            body.append('<h2>%s <span class="cnt">%d</span></h2>%s'
                        % (esc(title), len(rows), "".join(rows)))
    left = [k for k in m if k not in seen]
    if left:
        body.append('<h2>분류 안 됨 <span class="cnt">%d</span></h2><div class="src">%s</div>'
                    % (len(left), esc(", ".join(left))))
    return TPL % {"n": len(m), "body": "".join(body)}


TPL = u"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>에러 설명 문구 미리보기</title>
<style>
:root{--fire:#e5484d;--sub:#8b8b8b}
body{font-family:'Malgun Gothic',system-ui,sans-serif;max-width:820px;margin:0 auto;
  padding:28px 18px 60px;background:#fafafa;color:#1a1a1a;line-height:1.6}
h1{font-size:22px;margin:0 0 6px}
.lead{color:#666;font-size:14px;margin-bottom:24px}
h2{font-size:16px;margin:30px 0 10px;padding-bottom:6px;border-bottom:2px solid #e3e3e3}
.cnt{font-size:12px;color:#999;font-weight:400}
.item{margin:0 0 14px}
.key{font-family:Consolas,monospace;font-size:11px;color:#aaa;margin-bottom:3px}
.errHelp{border-left:3px solid var(--fire);background:rgba(229,72,77,.07);
  padding:9px 11px;border-radius:6px;line-height:1.55}
.errHelp b{color:var(--fire);font-size:14px}
.errHelp .errWhy{color:var(--sub);font-size:13px;margin-top:3px}
.errHelp .errTodo{font-size:13px;margin-top:4px}
.src{font-size:11px;color:#b0b0b0;margin-top:4px;padding-left:3px}
</style></head><body>
<h1>고객이 에러를 만났을 때 뜨는 설명 &mdash; 문구 검수</h1>
<div class="lead">아래 빨간 상자가 <b>화면에 실제로 그려지는 모양</b>입니다.
정본 <code>shopping_shorts/static/error_help.js</code>에서 그대로 뽑았습니다 (총 %(n)d개).<br>
고칠 문구를 말씀해 주시면 정본만 고치면 됩니다 &mdash; 4개 화면에 저절로 반영됩니다.</div>
%(body)s
</body></html>"""


if __name__ == "__main__":
    m = load()
    out = BASE / "out" / "에러문구_미리보기.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(m), encoding="utf-8")
    print("만들었습니다:", out)
    desk = Path.home() / "Desktop" / "에러문구_미리보기.html"
    try:
        shutil.copy2(out, desk)
        print("바탕화면:", desk)
    except Exception as e:
        print("바탕화면 복사 실패:", e)
