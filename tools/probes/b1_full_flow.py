# -*- coding: utf-8 -*-
"""[프로브] 1단계 분석 결과 → 2단계 대본(grounded) → 3단계 장면 배치(상속)를 **끝까지** 돌려
    "어느 대사에 어느 구간이 붙는지"를 그림과 함께 보여준다.

왜: 지금까지 잰 건 전부 정확도 숫자(AI가 AI를 채점)뿐이고, **이 흐름이 실제로 도는 걸 본 적이 없다**.
    2·3단계 스위치는 라이브에서 꺼져 있다.

사용: py tools/probes/b1_full_flow.py <b1_eye 결과폴더>
      예) py tools/probes/b1_full_flow.py out/probes/b1_eye/tmp_src
      → 그 폴더에 flow.html (대사 ↔ 붙은 구간 ↔ 띠 그림)

★호출 형태는 라이브 그대로다(하네스가 계약을 발명하면 0% 동작도 초록이 된다):
  · sources = [{name, full_text, segments, structure}]        ← _sources_for_generate가 만드는 모양
  · beat_sources = [{role, seg, segs}]                        ← produce.html s2Confirm이 만드는 모양
  · style = 서버 /api/script/styles의 id 57 원문(_style57.py)"""
import sys, os, json, html, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from shopping_shorts import keyroute, comment_gen

if comment_gen._current_key_and_idx()[0] is None:
    _KEYS = keyroute.gemini_keys("general")
    _N = {"i": 0}

    def _rr():
        k = _KEYS[_N["i"] % len(_KEYS)]
        _N["i"] += 1
        return (k, 0)

    comment_gen._current_key_and_idx = _rr
    print("(SHORTS 풀 0개 → 예비풀 키 %d개 돌려쓰기로 우회)" % len(_KEYS))

from shopping_shorts import script_generate, edit_plan
sys.path.insert(0, os.path.join(ROOT, "tools", "probes"))
# 스타일은 두 번째 인자로 고른다(기본 57 다이소축). 60=유튜브 발명품형(단일 제품·히트작 23편).
_SID = sys.argv[2] if len(sys.argv) > 2 else "57"
STYLE = __import__("_style%s" % _SID, fromlist=["STYLE"]).STYLE

SRC_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "out/probes/b1_eye/tmp_src")
res = json.loads((SRC_DIR / "result.json").read_text(encoding="utf-8"))
segs = res.get("segments") or []
brief = res.get("source_brief") or {}
print("1단계 결과: 구간 %d개 / 제품 %s" % (len(segs), brief.get("product") or "-"))

# --- 2단계: 본 것만 쓰기(grounded) ---
sources = [{
    "name": brief.get("product") or "소스 영상",
    "full_text": res.get("full_text_ko") or res.get("full_text") or "",
    "segments": segs,
    "structure": {},
    "product_benefits": res.get("product_benefits") or [],
}]
t0 = time.time()
note = {}
draft = script_generate.generate_one_style(sources, STYLE, target_seconds=30,
                                           seed="probe", note=note, grounded=True)
if not draft:
    print("2단계 실패 — note:", note)
    raise SystemExit(1)
beats = draft.get("beats") or []
print("2단계: 칸 %d개 / 게이트 통과 %s / 시도 %d회 / %.0f초"
      % (len(beats), draft.get("passed"), len(draft.get("tries") or []), time.time() - t0))
for b in beats:
    print("   [%s] src_seg=%-8s %s" % (b.get("role"), b.get("src_seg") or "-", (b.get("text") or "")[:44]))

# --- 3단계: 붙어 온 장면 그대로(상속) ---
#   produce.html s2Confirm과 같은 모양으로 beat_sources를 만든다.
beat_sources = [{"role": (b.get("role") or ""), "seg": (b.get("src_seg") or ""),
                 "segs": [x for x in (b.get("src_segs") or []) if x]} for b in beats]
# 칸을 **줄**로 잇는다 — produce.html s2ScriptLines와 같은 단위(2026-09-03).
#   draft["script"]는 공백 통짜라 마침표로 쪼개지면 줄 수가 칸 수와 어긋나
#   build_inherit_plan이 None(옛 경로 폴백)이 된다 — 실측: 9줄 vs 칸 8개.
given_script = "\n".join(t for t in ((b.get("text") or "").strip() for b in beats) if t)
# source_scripts는 **리스트**이고 각 원소에 video_id가 있어야 한다(_build_inventory가 그렇게 읽는다).
_src_scripts = [dict(res, video_id="s0")]
plan = edit_plan.build_inherit_plan(_src_scripts, given_script, beat_sources)
print("3단계 상속:", "성공 — 비트 %d개" % len(plan.get("beats") or []) if plan else "None(옛 경로로 폴백)")

seg_by_id = {s.get("seg_id"): s for s in segs}
idx_by_id = {s.get("seg_id"): i for i, s in enumerate(segs)}
rows = []
for i, b in enumerate(beats):
    pb = ((plan or {}).get("beats") or [])
    pbi = pb[i] if i < len(pb) else {}
    # 비트의 장면은 primary(대표) + alternates(나머지)에 실린다 — 실제 키를 확인하고 쓴다.
    _cl = ([pbi["primary"]] if pbi.get("primary") else []) + list(pbi.get("alternates") or [])
    ids = [c.get("seg_id") for c in _cl if isinstance(c, dict) and c.get("seg_id")] or \
          ([b.get("src_seg")] if b.get("src_seg") else [])
    ims, labs = [], []
    for sid in ids[:3]:
        s = seg_by_id.get(sid)
        n = idx_by_id.get(sid)
        if s is None:
            continue
        p = SRC_DIR / "img" / ("seg%03d.jpg" % n)
        if p.exists():
            ims.append('<figure><img src="img/seg%03d.jpg"><figcaption>#%d %.1f~%.1fs · %s</figcaption></figure>'
                       % (n, n + 1, float(s.get("start") or 0), float(s.get("end") or 0),
                          html.escape((s.get("scene_desc") or "")[:44])))
        labs.append(sid)
    inh = pbi.get("inherited")
    tag = ('<span class="b inh">📎 2단계가 정함</span>' if inh
           else ('<span class="b br">🎞 자동(b-roll)</span>' if ids else '<span class="b no">장면 없음</span>'))
    rows.append('<tr><td class="r">%s</td><td class="tx">%s%s<div class="ids">%s</div></td>'
                '<td class="ims">%s</td></tr>' % (
                    html.escape(b.get("role") or ""), html.escape(b.get("text") or ""),
                    "<br>" + tag, html.escape(", ".join(labs) or "—"),
                    "".join(ims) or '<span class="none">(그림 없음)</span>'))

doc = """<!doctype html><meta charset="utf-8"><title>대본 ↔ 장면 배치</title><style>
body{font:15px/1.65 system-ui,'Malgun Gothic',sans-serif;margin:0;background:#f6f7f9;color:#191919}
.wrap{max-width:1180px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:#666;font-size:13px;margin-bottom:16px}
.box{background:#fff;border:1px solid #e3e5e9;border-radius:10px;padding:14px 16px;margin-bottom:16px}
table{width:100%%;border-collapse:collapse;background:#fff;border:1px solid #e3e5e9;border-radius:10px;overflow:hidden}
td{border-top:1px solid #eceef1;padding:13px;vertical-align:top}tr:first-child td{border-top:0}
.r{width:88px;color:#0b62d0;font-weight:700}
.tx{width:44%%;font-size:15px}.ids{color:#999;font-size:12px;margin-top:5px}
.b{display:inline-block;font-size:12px;padding:2px 8px;border-radius:99px;margin-top:6px}
.inh{background:#e6f0fd;color:#0b52b0}.br{background:#f0eee6;color:#8a6d1f}.no{background:#fbe9e9;color:#a33}
.ims{display:flex;gap:8px;flex-wrap:wrap}figure{margin:0;width:250px}
figure img{width:100%%;border-radius:6px;display:block}
figcaption{font-size:11px;color:#777;margin-top:3px;line-height:1.35}
.none{color:#bbb;font-size:13px}
</style><div class="wrap"><h1>대본 ↔ 장면 배치 (1→2→3단계 전 구간)</h1>
<div class="sub">스타일 <b>%s</b> · 칸 %d개 · 게이트 통과 %s · 3단계 상속 %s</div>
<div class="box"><b>소스 영상 흐름(1단계)</b><div>%s</div><div>제품: %s</div></div>
<table>%s</table></div>""" % (
    html.escape(STYLE["name"]), len(beats), draft.get("passed"),
    "성공" if plan else "실패(옛 경로 폴백)",
    html.escape(brief.get("flow") or "-"), html.escape(brief.get("product") or "-"), "".join(rows))

(SRC_DIR / "flow.html").write_text(doc, encoding="utf-8")
json.dump({"draft": draft, "plan": plan, "beat_sources": beat_sources},
          open(SRC_DIR / "flow.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", (SRC_DIR / "flow.html").resolve())
