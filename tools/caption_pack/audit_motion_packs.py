"""등장 효과팩 측정(관제 144) — "회원 100명이 돌려쓰면 몇 가지가 나오나". 편집기 판단 함수(motionPlan)를 실제로 돌려 잰다.

  py tools/caption_pack/audit_motion_packs.py <출력폴더>

  ① 배정: 회원 1~100 → 20팩에 몇 명씩(scene_style.caption_motion_pack_for — 회원 번호 나머지)
     (라이브 실제 작업 회원 90명은 번호가 띄엄띄엄이라 팩당 1~8명 — 2026-10-06 서버 실측)
  ② 팩마다 같은 대본(20장면: 첫·일반·가격·문제·공개·영상 위 강조·마지막)으로 장면 계획 → 같은 등장 연속 0, 쓰인 효과 수
  ③ 회원 100명이 같은 대본을 만들면 서로 다른 장면 계획이 몇 가지인가
  ④ 두 팩 사이 다른 칸(만들기 도구 make_motion_packs 와 같은 셈)
  ⑤ 자동: 서버 회원 번호를 받으면 그 번호 팩으로 움직이고 저장값에 그 번호가 실린다
"""
import collections, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from shopping_shorts import scene_style, video_assemble as va

out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
fails = []
def need(ok, msg):
    print(("  통과  " if ok else "★ 실패  ") + msg)
    if not ok: fails.append(msg)

n = scene_style.caption_motion_pack_count()
assign = collections.Counter(scene_style.caption_motion_pack_for(c) for c in range(1, 101))
need(len(assign) == n, f"① 회원 100명 → {len(assign)}/{n}팩에 배정 (팩당 최소 {min(assign.values())}명 · 최대 {max(assign.values())}명)")

tts = out / "v.wav"
if not tts.exists():
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2", str(tts)])
ROLES = [("훅", "주부들도 감탄한 천재 아이디어")] + [("", "그냥 일반 설명 줄입니다")] * 3 + [("문제", "옷 태그 달기 너무 귀찮죠"), ("", "매번 가위를 찾게 돼요"),
         ("공개", "이거 하나면 끝나요"), ("", "누르기만 하면 돼요"), ("", "손에 딱 맞아요"), ("", "단돈 9,900원이에요"), ("", "설치도 쉬워요"),
         ("고조1", "무게도 버티고 설치도"), ("", "한 번 쓰면 못 끊어요"), ("", "집집마다 하나씩"), ("", "주방에도 좋아요"),
         ("", "선물로도 딱"), ("", "후기도 좋아요"), ("", "재구매율 최고"), ("", "지금 바로"), ("마무리", "링크는 댓글에 있어요")]
tl = [{"beat_idx": i, "t0": i * 2, "dur": 2, "narration": c, "caption_lines": [c], "tts_path": str(tts), "target_seconds": 2, "role": r,
       "primary": {"video_id": "s0", "start": i * 2, "end": i * 2 + 2}} for i, (r, c) in enumerate(ROLES)]
TEXT = {"channel": "숏템메이커", "hook1": "주부들도 감탄한", "hook2": "천재 아이디어", "bodyTitle": "주부들도 감탄한 천재 아이디어?"}
base = {"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "hook", "text": TEXT,
        "effects": {"11": {"dim": {"level": .32, "sec": 0}}}}
ctx = scene_style.context_for(tl, {"text": "x"}, base, None)
url = (ROOT / "out/scene-style-ui-showcase.html").as_uri()
plans = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url + "?qa=1"); pg.wait_for_timeout(1200)
    for k in range(1, n + 1):
        pg.evaluate("([c,s])=>window.sceneStyle.load(c,s)", [ctx, {**base, "motionPack": str(k)}]); pg.wait_for_timeout(50)
        plans[k] = pg.evaluate("()=>window.sceneStyle.motionPlan()")
    # ⑤ 자동: 서버가 회원 번호(context.motionPackAuto)를 주면 저장값 없이도 그 번호로 움직이고, 저장할 때 그 번호가 실린다
    pg.evaluate("([c,s])=>window.sceneStyle.load(c,s)", [{**ctx, "motionPackAuto": 9}, base]); pg.wait_for_timeout(50)
    auto_plan = pg.evaluate("()=>window.sceneStyle.motionPlan()"); auto_saved = pg.evaluate("()=>window.sceneStyle.snapshot().motionPack")
    b.close()
need(auto_plan == plans[9] and auto_saved == "9", f"⑤ 자동(서버 회원 번호 9) → 9번 팩 계획과 같음 {auto_plan == plans[9]} · 저장값 motionPack={auto_saved}")
need(not errs, f"페이지 오류 {len(errs)}건 {errs[:1]}")
worst = 0
for k, plan in plans.items():
    live = [x for x in plan if x]
    rep = sum(1 for a, c in zip(live, live[1:]) if a == c)
    worst = max(worst, rep)
    if rep: need(False, f"② {k}번 팩: 같은 등장 연속 {rep}회 {plan}")
need(worst == 0, f"② 20팩 모두 한 영상(20장면) 안 같은 등장 연속 0회 · 팩별 쓰인 효과 수 {sorted(len(set(x for x in pl if x)) for pl in plans.values())}")
uniq = len({tuple(plans[scene_style.caption_motion_pack_for(c)]) for c in range(1, 101)})
need(uniq >= 15, f"③ 회원 100명이 같은 대본 → 서로 다른 장면 계획 {uniq}가지 (자막팩 이전: 1가지)")
sys.path.insert(0, str(ROOT / "tools/caption_pack"))
import make_motion_packs as mm
packs = mm.read(); pair = min(mm.diff(a, c) for i, a in enumerate(packs) for c in packs[i + 1:])
need(pair >= mm.MIN_DIFF, f"④ 두 팩 사이 최소 다른 칸 {pair}/7")
(out / "plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}건")
sys.exit(1 if fails else 0)
