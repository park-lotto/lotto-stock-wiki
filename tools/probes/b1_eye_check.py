# -*- coding: utf-8 -*-
"""[프로브] 영상 한 편을 B1으로 분석해 **띠 그림 + 그 구간 묘사**를 나란히 놓은 눈검사 HTML을 만든다.

왜: 정확도 숫자는 AI(판정기)가 AI를 채점한 것이라 관대하다(2026-09-05 실측: 빈 묘사를 '맞음'으로
세어 100%가 찍힌 적이 있다). **사람이 그림을 보고 설명이 맞는지 직접 판정**하는 화면이 필요하다.

사용: py tools/probes/b1_eye_check.py <video.mp4> [out_dir]
     → <out_dir>/index.html (기본 out/probes/b1_eye/<영상이름>)
키: SHORTS 풀이 0개인 PC는 예비풀 키로 우회. GROQ 키가 있으면 말(전사)도 함께 나온다.
경로: 저장소 루트로 chdir 후 상대경로 사용(한글 절대경로는 로컬 ffmpeg stderr cp949 크래시)."""
import sys, os, json, time, shutil, html
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from shopping_shorts import keyroute, comment_gen, frame_script

if comment_gen._current_key_and_idx()[0] is None:
    # ★키를 하나로 고정하면 429로 태깅이 통째로 실패한다(2026-09-05 실측: 23구간 전부 빈 묘사).
    #   B1은 묶음마다 키를 새로 고르도록 짜여 있으니, 우회도 **돌려 써야** 한다.
    _KEYS = keyroute.gemini_keys("general")
    _N = {"i": 0}

    def _rr():
        k = _KEYS[_N["i"] % len(_KEYS)]
        _N["i"] += 1
        return (k, 0)

    comment_gen._current_key_and_idx = _rr
    print("(SHORTS 풀 0개 → 예비풀 키 %d개 돌려쓰기로 우회)" % len(_KEYS))

VIDEO = sys.argv[1] if len(sys.argv) > 1 else None
if not VIDEO or not os.path.exists(VIDEO):
    print("사용: py tools/probes/b1_eye_check.py <video.mp4> [out_dir]")
    raise SystemExit(2)
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else
           os.path.join("out", "probes", "b1_eye", Path(VIDEO).stem))
(OUT / "img").mkdir(parents=True, exist_ok=True)

# 띠 그림은 B1이 임시폴더에 만들고 끝나면 지운다 → tag_frames를 감싸 **넘어온 순간 복사**한다.
_kept = {}
_real_tag = frame_script._gemini_tag_frames


def _tag_and_keep(frame_groups, caption, segs, brief=None):
    for i, grp in enumerate(frame_groups or []):
        if grp and grp[0] and os.path.exists(grp[0]):
            dst = OUT / "img" / ("seg%03d.jpg" % i)
            try:
                shutil.copyfile(grp[0], dst)
                _kept[i] = dst.name
            except OSError:
                pass
    return _real_tag(frame_groups, caption, segs, brief)


t0 = time.time()
res = frame_script.extract_script_frames(VIDEO, "s0", caption="", _no_classic=True,
                                         tag_frames=_tag_and_keep)
secs = time.time() - t0
segs = res.get("segments") or []
brief = res.get("source_brief") or {}
print(f"구간 {len(segs)}개 / {secs:.0f}초 / 전사 {res.get('transcript_status')}")

rows = []
for i, s in enumerate(segs):
    img = _kept.get(i)
    say = (s.get("text_ko") or s.get("text") or "").strip()
    rows.append(
        '<tr><td class="n">#%d<br><span class="t">%.1f~%.1fs</span></td>'
        '<td class="im">%s</td><td class="d"><div class="sd">%s</div>%s'
        '<div class="meta">결: %s · 쓰임: %s</div>%s</td></tr>' % (
            i + 1, float(s.get("start") or 0), float(s.get("end") or 0),
            ('<img src="img/%s">' % img) if img else '<span class="no">(그림 없음)</span>',
            html.escape(s.get("scene_desc") or "(묘사 없음)"),
            ('<div class="say">말: %s</div>' % html.escape(say)) if say else "",
            html.escape(s.get("shot_role") or "-"), html.escape(s.get("label") or "-"),
            ('<div class="up">%s</div>' % html.escape(s.get("use_point") or "")) if s.get("use_point") else ""))

doc = """<!doctype html><meta charset="utf-8"><title>B1 눈검사 — %s</title>
<style>
body{font:15px/1.6 system-ui,'Malgun Gothic',sans-serif;margin:0;background:#f6f7f9;color:#1a1a1a}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px} .sub{color:#666;font-size:13px;margin-bottom:18px}
.brief{background:#fff;border:1px solid #e3e5e9;border-radius:10px;padding:14px 16px;margin-bottom:18px}
.brief b{color:#0b62d0} .brief div{margin:3px 0}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid #e3e5e9;border-radius:10px;overflow:hidden}
td{border-top:1px solid #eceef1;padding:12px;vertical-align:top}
tr:first-child td{border-top:0}
.n{width:74px;color:#0b62d0;font-weight:700;white-space:nowrap} .n .t{color:#888;font-weight:400;font-size:12px}
.im{width:420px} .im img{width:100%%;border-radius:6px;display:block} .no{color:#bbb;font-size:13px}
.sd{font-size:16px;font-weight:600;margin-bottom:4px}
.say{color:#2a7d3f;font-size:13px;margin:3px 0}
.meta{color:#777;font-size:13px;margin-top:5px}
.up{color:#555;font-size:13px;margin-top:5px;padding-left:9px;border-left:3px solid #dfe3e8}
@media(max-width:820px){.im{width:220px}}
</style>
<div class="wrap"><h1>B1 눈검사 — %s</h1>
<div class="sub">구간 %d개 · 분석 %.0f초 · 전사 %s · <b>그림과 설명이 맞는지 직접 보십시오</b></div>
<div class="brief"><b>영상 전체 흐름(AI가 먼저 파악한 것)</b>
<div>%s</div><div>제품: %s · 역할: %s</div><div>%s</div></div>
<table>%s</table></div>""" % (
    html.escape(Path(VIDEO).name), html.escape(Path(VIDEO).name), len(segs), secs,
    html.escape(str(res.get("transcript_status"))),
    html.escape(brief.get("flow") or "(없음)"), html.escape(brief.get("product") or "-"),
    html.escape(brief.get("role") or "-"), html.escape(brief.get("core") or ""), "".join(rows))

(OUT / "index.html").write_text(doc, encoding="utf-8")
json.dump(res, open(OUT / "result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", (OUT / "index.html").resolve())
