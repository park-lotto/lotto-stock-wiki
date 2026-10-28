"""옛 피팅룸 삭제 전/후 대조(관제 058 C1). 로컬 서버의 작업을 열어 단계 0→6→7(썸네일)→8→9(완성본)까지 jump 하며
① 콘솔 오류 ② /api/produce/mix/settings 로 나가는 설정 본문(제목·자막·꾸미기)을 기록한다. 전/후 파일을 diff 하면 끝.
사용: py tools/legacy_deco/smoke.py http://127.0.0.1:8854 4a3099bb7159 out.json"""
import sys, json, time
from playwright.sync_api import sync_playwright
base, work, out = sys.argv[1], sys.argv[2], sys.argv[3]
rec = {"errors": [], "settings_posts": [], "steps": []}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1500, "height": 1000})
    pg.on("pageerror", lambda e: rec["errors"].append(str(e)[:200]))
    pg.on("console", lambda m: rec["errors"].append("console.error: " + m.text[:200]) if m.type == "error" and "favicon" not in m.text else None)
    def on_req(r):
        if "/api/produce/mix/settings" in r.url and r.method == "POST":
            try: rec["settings_posts"].append(json.loads(r.post_data or "{}"))
            except Exception: rec["settings_posts"].append({"raw": (r.post_data or "")[:300]})
    pg.on("request", on_req)
    pg.goto(f"{base}/produce?work={work}", wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(6000)
    for o in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
        try:
            pg.evaluate(f"() => {{ try {{ jump({o}); }} catch(e) {{ console.error('jump {o}: '+e); }} }}")
            pg.wait_for_timeout(2500)
            rec["steps"].append({"orb": o, "cur": pg.evaluate("() => typeof cur!=='undefined'?cur:null"),
                                 "visible_panel": pg.evaluate("() => document.querySelector('.panel.show')?.dataset.step")})
        except Exception as e:
            rec["errors"].append(f"jump {o}: {e!s:.150}")
    # 렌더 직전 설정 저장 본문(saveHeadcopy)만 따로 한 번 더
    pg.evaluate("() => typeof saveHeadcopy==='function' && saveHeadcopy()"); pg.wait_for_timeout(1500)
    rec["state"] = pg.evaluate("() => ({headcopy: STATE.headcopy, captionStyle: STATE.captionStyle, deco: STATE.deco})")
    b.close()
json.dump(rec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("errors", len(rec["errors"]), "settings_posts", len(rec["settings_posts"]), "steps", [(s["orb"], s["visible_panel"]) for s in rec["steps"]])
for e in rec["errors"][:8]: print("  ", e)
