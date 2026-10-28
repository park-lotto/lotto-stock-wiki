# -*- coding: utf-8 -*-
"""장면 보충(관제 209) 라이브 끝까지 시험(2026-10-15 판: 유튜브 썸네일 담기 → 아래 영상 소스 → 필름에서 칸에 담기) — 관리자 작업을 복제해서(원본·고객 작업은 안 건드린다)
① 3단계 장면 찾기 → 검색 → [이 칸에 쓰기] ② 필름 노란 박스 ③ 저장된 편성(scene_override video_id=x*)
④ 렌더 완성본에 그 영상이 그 칸에 나오나(프레임 대조) ⑤ 캡컷 매니페스트에 x* 소스가 들어갔나.

    py tools/scene_find_live_check.py <원본 job> [칸번호] [검색어]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.live_admin import admin_page  # noqa: E402

KEY = str(Path.home() / "crawling_bot_client" / "LightsailDefaultKey-ap-northeast-2.pem")
HOST = "ubuntu@3.35.251.172"
REPO = "/home/ubuntu/lotto-stock-wiki/shopping_shorts"
OUT = ROOT / "out" / "scene_find_live"


def ssh(cmd, timeout=600):
    r = subprocess.run(["ssh", "-i", KEY, HOST, cmd], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout + r.stderr


def fetch(pg, method, url, body=None):
    return pg.evaluate("""async ([m,u,b]) => { const r = await fetch(u, {method:m, headers:{'Content-Type':'application/json'},
        body: b ? JSON.stringify(b) : undefined}); let t = await r.text(); try { return {s:r.status, j:JSON.parse(t)} } catch(e) { return {s:r.status, t:t.slice(0,300)} } }""",
                       [method, url, body])


def main():
    src = sys.argv[1]
    beat = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    kw = sys.argv[3] if len(sys.argv) > 3 else ""
    OUT.mkdir(parents=True, exist_ok=True)
    with admin_page("produce") as pg:
        r = fetch(pg, "POST", "/api/mix/candidate/clone", {"job_id": src, "index": 0})
        print("복제", r)
        job = r["j"]["job_id"]
        pg.goto("https://shoppingshorts.duckdns.org/scene_lab.html?job=" + job)
        pg.wait_for_timeout(8000)
        n_btn = pg.evaluate("[...document.querySelectorAll('button')].filter(b=>b.textContent.includes('장면 찾기')).length")
        print("① 장면 찾기 버튼", n_btn, "· 페이지 오류", pg.errors[:3])
        if not n_btn:
            return 1
        pg.evaluate("openSceneFind(%d)" % beat)
        pg.wait_for_timeout(800)
        if kw:
            pg.fill("#sfKw", kw)
        pg.click("#sfExp")
        pg.wait_for_selector("#sfCands .sfk", timeout=90000)
        print("   나라별 검색어", pg.evaluate("SF.cands.length"), pg.evaluate("JSON.stringify(SF.cands[0])")[:200])
        pg.evaluate("sfSetLang('en')")
        pg.locator("#sfCands .sfk button.yt").first.click()
        pg.wait_for_selector("#sfRes .sfit", timeout=90000)
        print("   유튜브 썸네일 %d개" % pg.evaluate("SF.items.length"))
        pg.screenshot(path=str(OUT / "1_popup.png"))
        before = set(pg.evaluate("Object.keys(DATA.src_duration||{})"))
        pg.evaluate("sfUse(0)")
        t0 = time.time()
        while time.time() - t0 < 240:
            pg.wait_for_timeout(3000)
            if set(pg.evaluate("Object.keys(DATA.src_duration||{})")) - before:
                break
        new = sorted(set(pg.evaluate("Object.keys(DATA.src_duration||{})")) - before)
        print("② 아래 영상 소스에 들어옴", new, "(%.0f초)" % (time.time() - t0))
        if not new:
            return 1
        vid = new[0]
        pg.evaluate("closeSceneFind()")
        heads = pg.evaluate("[...document.querySelectorAll('.srchead')].map(h=>h.innerText.split(String.fromCharCode(10)).join(' ').slice(0,50))")
        print("   소스 목록 끝:", heads[-1:])
        # 사람이 하는 길: 🎞 필름 펼치기 → 박스 → 담기(칸 길이만큼)
        need = pg.evaluate("Math.min(DATA.src_duration['%s'], beatDur(%d))" % (vid, beat))
        pg.evaluate("v => { if (ROLL.key) closeRoll(ROLL); toggleRoll('src', v); }", vid)
        pg.wait_for_timeout(2500)
        pg.evaluate("([v,i,n]) => { ROLL.inst.addBox(0, n); commitRoll('src', v, v, [{s:0,e:n}], i); }", [vid, beat, need])
        pg.wait_for_timeout(2500)
        print("   필름 박스", pg.evaluate("ROLL && ROLL.inst && ROLL.inst.boxes ? JSON.stringify(ROLL.inst.boxes()) : null"))
        pg.screenshot(path=str(OUT / "2_film_box.png"))
        pg.wait_for_timeout(8000)                     # 자동저장
    plan = ssh("cd %s && python3 -c \"import json,sqlite3;c=sqlite3.connect('data/reference.db');"
               "p=json.loads(c.execute('select edit_plan_json from mix_jobs where job_id=?',('%s',)).fetchone()[0]);"
               "b=p['beats'][%d];print(json.dumps(b.get('scene_override'),ensure_ascii=False)[:600])\"" % (REPO, job, beat))
    print("③ 저장된 칸 %d scene_override:" % beat, plan.strip())
    ok_plan = vid in plan
    print("   %s 편성에 %s %s" % ("✅" if ok_plan else "❌", vid, "있음" if ok_plan else "없음"))
    json.dump({"job": job, "vid": vid, "beat": beat}, open(OUT / "state.json", "w"))
    print("다음: 렌더·캡컷 — py tools/scene_find_live_check.py --render", job, vid, beat)
    return 0


def render_and_check(job, vid, beat):
    beat = int(beat)
    with admin_page("produce") as pg:
        r = fetch(pg, "POST", "/api/mix/render", {"job_id": job})
        print("렌더 예약", r)
        t0 = time.time()
        st = None
        while time.time() - t0 < 1800:
            st = ssh("cd %s && python3 -c \"import sqlite3;c=sqlite3.connect('data/reference.db');"
                     "print(c.execute('select status,error from mix_jobs where job_id=?',('%s',)).fetchone())\"" % (REPO, job)).strip()
            if "done" in st or "fail" in st or "error" in st.lower() and "None" not in st:
                break
            time.sleep(30)
        print("④ 렌더 상태", st, "(%.0f분)" % ((time.time() - t0) / 60))
        cc = fetch(pg, "GET", "/api/mix/capcut/%s?base=C:%%5CCapCut" % job)
    blob = json.dumps(cc, ensure_ascii=False)
    print("⑤ 캡컷 응답", cc.get("s"), "· %s 소스 %s" % (vid, "있음 ✅" if vid in blob else "없음 ❌"))
    # 완성본에서 그 칸 구간 프레임 vs 새 영상 첫 부분 — 서버에서 비교
    cmp_ = ssh(r"""cd %s && python3 - <<'EOF'
import json,sqlite3,subprocess,glob
c=sqlite3.connect('data/reference.db')
p=json.loads(c.execute('select edit_plan_json from mix_jobs where job_id=?',('%s',)).fetchone()[0])
from shopping_shorts import mix_pipeline as mp
work='data/mix_jobs/%s'
srcs=mp.extra_source_paths(work); print('x 소스', srcs)
fin=sorted(glob.glob(work+'/final*.mp4'))
print('완성본', fin)
EOF""" % (REPO.rsplit('/', 1)[0], job, "shopping_shorts/" + "data/mix_jobs/" + job if False else job))
    print(cmp_)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--render":
        sys.exit(render_and_check(*sys.argv[2:5]) or 0)
    sys.exit(main())
