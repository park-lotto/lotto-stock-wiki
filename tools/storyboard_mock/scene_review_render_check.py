"""장면 점검(관제 257) 결과물 확인 — 라이브(관리자)에서 [이 장면으로 바꾸기] → 확정 → 3단계 job → 렌더까지 실제로 돌려
그 줄 구간에 제안 조각이 나오는지 본다. 원본 작업은 건드리지 않는다(복사본 '[시험] 장면점검 렌더대조'를 만들어 거기서).

    py tools/storyboard_mock/scene_review_render_check.py prep <원본 work_id> [--row 7]     # 복사·점검·바꾸기·확정·3단계 시작 → work·job 출력
    py tools/storyboard_mock/scene_review_render_check.py plan <job_id> <줄> <조각,조각>      # 3단계 계획의 그 칸 장면 = 바꾼 조각인가

★자막 제거(유료 VMake)는 이 시험 job 에서 끈다 — 확인 대상이 장면이라 돈을 쓰지 않는다.
"""
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.live_admin import BASE, admin_page, KEY, HOST   # noqa: E402


def prep(src, row, reuse=None):
    with admin_page("produce?work=" + src, viewport=(1750, 1000)) as pg:
        pg.wait_for_timeout(4000)
        # ★복사본을 단계 7로 처음 열면 화면이 3단계 매칭을 자동으로 시작한다(10-23 실측 681bd5b69cfa) — 그 뒤엔 --work 로 그 복사본을 다시 쓴다
        wid = reuse or pg.evaluate("""async (src) => { const w=await (await fetch('/api/produce/works/'+src)).json();
            const st=Object.assign({}, (w.work||w).state||{}); st.title_manual='[시험] 장면점검 렌더대조 '+new Date().toISOString().slice(5,16);
            delete st.work_id;
            const post=b=>fetch('/api/produce/works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json());
            const d=await post({state:st, step:7}); if(!d.work_id) return JSON.stringify(d);
            // 스토리보드 저장본은 작업 열쇠('w:<작업>')로 되살아난다 — 복사본 열쇠로 바꿔 다시 저장
            if(st.sb){ st.sb=Object.assign({}, st.sb, {jid:'w:'+d.work_id, work_id:d.work_id}); }
            st.work_id=d.work_id; await post({work_id:d.work_id, state:st});
            return d.work_id; }""", src)
        print("복사본 work", wid)
        pg.goto(BASE + "/produce?work=" + wid, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        ok = pg.evaluate("""async () => { const w=ms=>new Promise(r=>setTimeout(r,ms));
            for(let k=0;k<60&&!(window.STORYBOARD_ON&&SB.data&&Object.keys(SB.made||{}).length);k++) await w(500);
            if(!Object.keys(SB.made||{}).length) return false; if(!SB.made[SB.view]) SB.view=Object.keys(SB.made)[0];
            cur=8; showPanel(); sbRender(); return window.SCRIPT_CHAT_ON; }""")
        if not ok:
            raise SystemExit("스토리보드·대본 AI 스위치가 안 열렸다: %r" % ok)
        before = pg.evaluate("(i) => sbLiveIds(SB.view,i,SB.made[SB.view].slots[i])", row)
        pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="장면 점검").click()
        pg.wait_for_function("(i) => SB.rev[SB.view+'#'+i] && !Object.keys(SB.revBusy).length", arg=row, timeout=200000)
        v = pg.evaluate("(i) => SB.rev[SB.view+'#'+i]", row)
        print("판정", v["verdict"], "|", v["why"])
        if v["verdict"] != "swap":
            raise SystemExit("이 줄은 교체 판정이 아니다 — 다른 --row 로")
        pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="이 장면으로 바꾸기").click()
        pg.wait_for_timeout(3000)
        after = pg.evaluate("(i) => sbLiveIds(SB.view,i,SB.made[SB.view].slots[i])", row)
        print("장면 전", before, "→ 후", after)
        pg.evaluate("() => { sbConfirm(); }")
        pg.wait_for_timeout(3000)
        pg.evaluate("() => { try{ STATE.subtitleRemoval=false; }catch(e){} }")
        pg.evaluate("() => startProduceMix()")
        jid = None
        for _ in range(60):
            pg.wait_for_timeout(2000)
            jid = pg.evaluate("() => (typeof MIX_JOB!=='undefined' && MIX_JOB) || null")
            if jid:
                break
        pg.wait_for_timeout(4000)    # saveWork 가 job_id 를 작업에 적을 시간
        print("3단계 job", jid)
        row_line = pg.evaluate("(i) => sbLine(SB.view,i,SB.made[SB.view].slots[i])", row)
        # 확정 대본의 몇 번째 줄인가(빈 줄은 빠진다) — 3단계 칸 번호
        k = pg.evaluate("(i) => SB.made[SB.view].slots.slice(0,i).filter((sl,k)=>String(sbLine(SB.view,k,sl)).trim()).length", row)
        print(json.dumps({"work": wid, "job": jid, "beat": k, "line": row_line, "ids": after}, ensure_ascii=False))


_PLAN = r"""
import sys, json; sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.store import Store
from shopping_shorts import config
j = Store(config.DB_PATH).get_mix_job(sys.argv[1]) or {}
ep = j.get("edit_plan") or {}
bs = ep.get("beats") or []
b = bs[int(sys.argv[2])] if int(sys.argv[2]) < len(bs) else {}
segs = [{k: c.get(k) for k in ("seg_id", "seg_key", "src", "start", "end", "source_idx", "video_idx") if k in c} for c in (b.get("clips") or b.get("segs") or [])]
print(json.dumps({"status": j.get("status"), "beats": len(bs), "text": b.get("text"), "keys": sorted(b.keys()), "clips": segs,
                  "src_seg": b.get("src_seg"), "src_segs": b.get("src_segs"), "video_path": j.get("video_path")}, ensure_ascii=False))
"""


def plan(jid, beat):
    r = subprocess.run(["ssh", "-i", KEY, HOST, "cd /home/ubuntu/lotto-stock-wiki && python3 - %s %s" % (jid, beat)],
                       input=_PLAN.encode(), capture_output=True)
    print(r.stdout.decode("utf-8", "replace") or r.stderr.decode("utf-8", "replace")[-800:])


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "prep":
        prep(a[1], int(a[a.index("--row") + 1]) - 1 if "--row" in a else 6, a[a.index("--work") + 1] if "--work" in a else None)
    elif a[0] == "plan":
        plan(a[1], a[2])
