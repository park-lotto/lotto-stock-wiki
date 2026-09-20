# -*- coding: utf-8 -*-
"""[프로브] 소스 **2편 이상**을 섞으면 장면 중복이 사라지는가 (핸드오프 남은 것 3번).

왜: 18차에서 중복을 지시+판정으로 막았지만, 장면 재고가 빠듯한 소재는 여전히 아슬아슬하다.
    라이브는 담긴 영상을 최대 8편까지 넣는다(_sources_for_generate) — 재고가 몇 배로 늘면
    중복 압력 자체가 사라지는지, 그리고 3단계 상속이 **여러 소스에 걸쳐** 제대로 도는지 본다.

사용: py tools/probes/b1_two_sources.py <폴더1> <폴더2> [스타일id]
      예) py tools/probes/b1_two_sources.py out/probes/b1_eye/tmp_src14 out/probes/b1_eye/tmp_src40

★라이브 형태 그대로 부른다(하네스가 계약을 발명하면 0% 동작도 초록이 된다):
  · seg_id는 **소스마다 다른 video_id**로 다시 매긴다 — 라이브는 _assign_seg_ids(video_id, …)가
    "s0-0"/"s1-0"처럼 붙인다. 프로브가 둘 다 s0으로 두면 번호가 충돌해 엉뚱한 소스의 장면을 집는다.
  · sources = [{name, full_text, segments, structure, product_benefits}]  ← _sources_for_generate 모양
  · beat_sources = [{role, seg, segs}]                                    ← produce.html s2Confirm 모양
"""
import sys, os, json, time
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

from shopping_shorts import script_generate, edit_plan, script_gate
sys.path.insert(0, os.path.join(ROOT, "tools", "probes"))
_SID = sys.argv[3] if len(sys.argv) > 3 else "57"
STYLE = __import__("_style%s" % _SID, fromlist=["STYLE"]).STYLE

DIRS = [Path(sys.argv[1]), Path(sys.argv[2])]


def _load(d, vid):
    """result.json을 읽어 **video_id를 다시 매긴** 소스 하나로 만든다(라이브 형태)."""
    res = json.loads((d / "result.json").read_text(encoding="utf-8"))
    segs = []
    for n, s in enumerate(res.get("segments") or []):
        s = dict(s)
        s["seg_id"] = "%s-%d" % (vid, n)
        segs.append(s)
    res = dict(res, segments=segs, video_id=vid)
    brief = res.get("source_brief") or {}
    src = {
        "name": brief.get("product") or d.name,
        "full_text": res.get("full_text_ko") or res.get("full_text") or "",
        "segments": segs,
        "structure": {},
        "product_benefits": res.get("product_benefits") or [],
    }
    return res, src


srcs, raws = [], []
for i, d in enumerate(DIRS):
    res, src = _load(d, "s%d" % i)
    raws.append(res)
    srcs.append(src)
    print("소스 %d: %-22s 구간 %d개  (%s)" % (i, d.name, len(src["segments"]), src["name"]))

total_segs = sum(len(s["segments"]) for s in srcs)
print("합계 재고 %d구간\n" % total_segs)

t0 = time.time()
note = {}
draft = script_generate.generate_one_style(srcs, STYLE, target_seconds=30,
                                           seed="two", note=note, grounded=True)
if not draft:
    print("2단계 실패 — note:", note)
    raise SystemExit(1)
beats = draft.get("beats") or []
print("2단계: 칸 %d개 / 게이트 통과 %s / 시도 %d회 / %.0f초"
      % (len(beats), draft.get("passed"), len(draft.get("tries") or []), time.time() - t0))

# --- 중복·소스 분산 판정 ---
prim, used_src = [], {}
for b in beats:
    ids = script_gate.parse_src_segs(b.get("src_seg"))
    head = ids[0] if ids else ""
    print("   [%-9s] src_seg=%-10s %s" % (b.get("role"), b.get("src_seg") or "-", (b.get("text") or "")[:40]))
    if head:
        prim.append(head)
        used_src[head.split("-")[0]] = used_src.get(head.split("-")[0], 0) + 1
dups = len(prim) - len(set(prim))
print("\n대표 장면 %d개 · 중복 %d개 · 소스별 사용 %s" % (len(prim), dups, used_src))

# --- 3단계 상속 ---
beat_sources = [{"role": (b.get("role") or ""), "seg": (b.get("src_seg") or ""),
                 "segs": [x for x in (b.get("src_segs") or []) if x]} for b in beats]
given_script = "\n".join(t for t in ((b.get("text") or "").strip() for b in beats) if t)
plan = edit_plan.build_inherit_plan(raws, given_script, beat_sources)
if not plan:
    print("3단계 상속: None(옛 경로 폴백) ★2편에선 상속이 안 된다는 뜻")
else:
    pb = plan.get("beats") or []
    inh = sum(1 for b in pb if b.get("inherited"))
    pids = [ (b.get("primary") or {}).get("seg_id") for b in pb ]
    pset = [x for x in pids if x]
    by_src = {}
    for x in pset:
        by_src[x.split("-")[0]] = by_src.get(x.split("-")[0], 0) + 1
    print("3단계 상속: 성공 — 비트 %d개 · 2단계가 정한 것 %d개 · 자동 b-roll %d개"
          % (len(pb), inh, len(pb) - inh))
    print("            배치된 장면 %d개 · 중복 %d개 · 소스별 %s"
          % (len(pset), len(pset) - len(set(pset)), by_src))

out = DIRS[0].parent / "two_src_result.json"
json.dump({"draft": draft, "plan": plan, "sources": [d.name for d in DIRS],
           "dups_stage2": dups, "used_src": used_src},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", out)
