# -*- coding: utf-8 -*-
"""지금 라이브가 실제로 어떤 상태인가 — **말하기 전에 이걸 먼저 본다** (2026-09-09).

## 왜 만들었나 (사장님: "왜 놓치는 구조를 만드나")

2026-09-09 하루에 놓친 것들의 공통점은 하나였다 — **재보기 전에 결론을 말했다.**

    "정답지가 없다"          -> scene_swaps에 2,233건 있었다
    "사장님 한 시간이 필요"   -> 필요 없었다(그 2,233건이 라벨이다)
    B1을 켜고 하루           -> 좋아졌는지 **아무도 안 쟀다** (실측하니 교체 30% 감소)
    길이 하한을 올림         -> 게이트가 "문장을 더 쪼개라"고 시키는 걸 못 봤다

규칙으로는 안 막힌다(이 프로젝트가 이미 배운 것: "안 지켜지는 규칙은 없는 규칙").
그래서 **도구**로 만든다. `find_work.py`와 같은 원리 — 목록을 안 만들고 매번 직접 잰다.
갱신이 필요 없다 = 썩지 않는다.

## 언제 쓰나 — 세 번

    세션 시작할 때        지금 상태가 어떤지 모르고 시작하지 않는다
    무언가 바꾸기 **전**   지금 숫자를 먼저 박아둔다(기준선)
    바꾼 **뒤**           정말 좋아졌는지 같은 잣대로 다시 잰다

    py tools/현황.py             # 서버 실측
    py tools/현황.py --기준선     # 지금 숫자를 파일에 박아둔다
    py tools/현황.py --대조       # 박아둔 것과 지금을 나란히
"""
import datetime as dt
import json
import pathlib
import subprocess
import sys

for _st in ("stdout", "stderr"):
    try:
        getattr(sys, _st).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE = pathlib.Path(__file__).resolve().parent.parent
SNAP = BASE / ".현황기준선.json"
KEY = r"C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"

# ★서버에서 돌릴 측정. 여기 한 곳에만 적는다 — 재는 잣대가 두 벌이면
#   "좋아졌다/나빠졌다"가 서로 다른 답을 낸다(0순위-B).
PROBE = r'''
import sqlite3, json, datetime as dt, re
from collections import Counter, defaultdict
c = sqlite3.connect('shopping_shorts/data/reference.db')
out = {}

# ① 장면 교체 — 사장님이 손으로 바꾼 횟수. 낮을수록 배치가 맞는 것이다.
day = defaultdict(set); cnt = Counter()
for ts, j in c.execute('select created_at, job_id from scene_swaps'):
    try: d = dt.datetime.fromtimestamp(float(ts)).strftime('%Y-%m-%d')
    except Exception: continue
    cnt[d] += 1; day[d].add(j)
recent = sorted(cnt)[-5:]
out['교체'] = [{'날짜': d, '건수': cnt[d], 'job': len(day[d]),
                'job당': round(cnt[d]/max(len(day[d]), 1), 1)} for d in recent]
out['정답지'] = c.execute('select count(*) from scene_swaps').fetchone()[0]

# ② 대본 재료 — 이게 비면 모델이 지어낸다(2026-09-09 실사고)
n = has = short = 0
for (s,) in c.execute("select state_json from produce_works where created_at>=date('now','-3 day')"):
    try: m = (json.loads(s).get('s2') or {}).get('materials') or {}
    except Exception: continue
    if not m: continue
    n += 1
    if m.get('product_facts'): has += 1
    if sum((x or {}).get('chars') or 0 for x in (m.get('sources') or [])) < 200: short += 1
out['재료'] = {'job': n, '제품재료있음': has, '자막200자미만': short}

# ③ 대본 길이 — 목표를 채우는가
try:
    from shopping_shorts import script_gate as g
    cps = g._speech_cps()
    lens = []
    for (s,) in c.execute("select state_json from produce_works where created_at>=date('now','-3 day')"):
        try: ds = (json.loads(s).get('s2') or {}).get('drafts') or []
        except Exception: continue
        for d in ds:
            t = ' '.join(b.get('narration') or b.get('text') or '' for b in (d.get('beats') or []))
            L = len(g.norm(t))
            if L: lens.append((L, len(d.get('beats') or [])))
    if lens:
        lens.sort()
        mid = lens[len(lens)//2]
        out['대본'] = {'편수': len(lens), '중앙글자': mid[0],
                       '중앙초': round(mid[0]/cps, 1), '중앙칸': mid[1],
                       '칸당초': round(mid[0]/cps/max(mid[1], 1), 1)}
    lo, hi = g.density_range({}, 25)
    out['게이트'] = {'25초허용': '%d~%d자' % (lo, hi)}
except Exception as e:
    out['대본'] = {'오류': str(e)[:80]}

# ④ 스위치 — 켜져 있다고 착각하기 쉽다
sw = {}
for k in ('frame_extract_enabled', 'screen_verify_enabled', 'scene_library_auto_enabled'):
    r = c.execute('select value from settings where key=?', (k,)).fetchone()
    sw[k] = (r[0] if r else '(꺼짐)')
out['스위치'] = sw

# ⑤ 레퍼런스 기준선 — 우리가 따라가야 할 수
out['레퍼런스'] = {'대본추출': c.execute('select count(*) from script_extracts').fetchone()[0]}
print(json.dumps(out, ensure_ascii=False))
'''


def _probe():
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", KEY, HOST,
         "cd /home/ubuntu/lotto-stock-wiki && python3 -c \"%s\"" % PROBE.replace('"', '\\"')],
        capture_output=True, timeout=180)
    txt = (r.stdout or b"").decode("utf-8", "replace").strip()
    for line in reversed(txt.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError("측정 실패: %s" % ((r.stderr or b"").decode("utf-8", "replace")[-300:]))


def _show(d, prev=None):
    def _d(cur, old, lower_is_better=True):
        if old is None or cur == old:
            return ""
        good = (cur < old) if lower_is_better else (cur > old)
        return "  (%s%+.1f %s)" % ("", cur - old, "좋아짐" if good else "나빠짐")

    print("\n■ 장면 교체 — 사장님이 손으로 바꾼 횟수 (낮을수록 배치가 맞다)")
    for x in d["교체"]:
        print("   %s  job당 %.1f건  (교체 %d · job %d)" % (x["날짜"], x["job당"], x["건수"], x["job"]))
    print("   ★정답지 %d건 — 사장님이 바꾼 기록. 판정기 채점에 그대로 쓴다" % d["정답지"])

    m = d.get("재료") or {}
    if m.get("job"):
        print("\n■ 대본 재료 (최근 3일 %d job)" % m["job"])
        print("   제품 재료 있음   %d건 (%.0f%%)" % (m["제품재료있음"], 100*m["제품재료있음"]/m["job"]))
        print("   자막 200자 미만  %d건 (%.0f%%)  ← 이러면 화면에서 뽑아야 한다"
              % (m["자막200자미만"], 100*m["자막200자미만"]/m["job"]))

    s = d.get("대본") or {}
    if s.get("편수"):
        print("\n■ 대본 (최근 3일 %d편)" % s["편수"])
        print("   중앙값 %d자 = %.1f초 · %d칸 · 칸당 %.1f초" %
              (s["중앙글자"], s["중앙초"], s["중앙칸"], s["칸당초"]))
        print("   ※히트작 기준: 25초 · 4칸 · 칸당 6.3초 (레퍼런스 4,915편 실측)")
    if d.get("게이트"):
        print("   게이트 25초 허용: %s" % d["게이트"]["25초허용"])

    print("\n■ 스위치 (켜진 줄 알았는데 꺼져 있는 일이 잦다)")
    for k, v in (d.get("스위치") or {}).items():
        print("   %-28s %s" % (k, v))

    if prev:
        print("\n■ 기준선 대조 (%s에 박아둔 것)" % prev.get("_잰시각", "?"))
        try:
            a = d["교체"][-1]["job당"]; b = prev["교체"][-1]["job당"]
            print("   교체 job당  %.1f → %.1f%s" % (b, a, _d(a, b)))
        except Exception:
            pass
        try:
            print("   대본 칸당초 %.1f → %.1f%s" %
                  (prev["대본"]["칸당초"], d["대본"]["칸당초"],
                   _d(d["대본"]["칸당초"], prev["대본"]["칸당초"], lower_is_better=False)))
        except Exception:
            pass


def main():
    args = sys.argv[1:]
    d = _probe()
    d["_잰시각"] = dt.datetime.now().strftime("%m-%d %H:%M")
    prev = None
    if "--대조" in args and SNAP.exists():
        prev = json.loads(SNAP.read_text(encoding="utf-8"))
    _show(d, prev)
    if "--기준선" in args:
        SNAP.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n[기준선 박음] %s — 바꾼 뒤 `--대조`로 다시 재라" % SNAP.name)


if __name__ == "__main__":
    main()
