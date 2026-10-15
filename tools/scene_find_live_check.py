# -*- coding: utf-8 -*-
"""장면 보충(관제 209) 라이브 끝까지 시험 — 관리자 작업을 복제해서(원본·고객 작업은 안 건드린다)
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
        word = kw or pg.evaluate("document.getElementById('sfKw').value")
        pg.evaluate("w => sfSearch(w)", word)
        pg.wait_for_selector("#sfRes .sfit", timeout=120000)
        n_res = pg.evaluate("document.querySelectorAll('#sfRes .sfit').length")
        print("   검색어 %r 결과 %d개" % (word, n_res))
        pg.screenshot(path=str(OUT / "1_popup.png"))
        before = set(pg.evaluate("Object.keys(DATA.src_duration||{})"))
        pg.evaluate("sfUse(0)")
        t0 = time.time()
        while time.time() - t0 < 240:
            now = set(pg.evaluate("Object.keys(DATA.src_duration||{})"))
            if now - before:
                break
            pg.wait_for_timeout(2000)
        new = sorted(set(pg.evaluate("Object.keys(DATA.src_duration||{})")) - before)
        print("   받은 영상", new, "(%.0f초)" % (time.time() - t0), pg.evaluate("document.getElementById('sfMsg') && document.getElementById('sfMsg').textContent"))
        if not new:
            return 1
        vid = new[0]
        pg.wait_for_timeout(2500)
        boxes = pg.evaluate("ROLL && ROLL.inst && ROLL.inst.boxes ? JSON.stringify(ROLL.inst.boxes()) : null")
        print("② 필름 노란 박스", boxes)
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
