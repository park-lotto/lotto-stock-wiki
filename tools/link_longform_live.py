"""구매링크용 롱폼 — 라이브 실측(관제 132). 관리자로 제작소를 열어 「롱폼으로 렌더」를 실제로 누르고,
받은 파일을 그 작업의 완성본과 영상으로 대조한다.

  py tools/link_longform_live.py <job_id> <저장폴더> [--wait-until HH:MM]

--wait-until: 배포가 아직이면 그 시각까지 1분마다 다시 본다(서버가 새 경로를 알 때까지).
⚠️ 제작소 9단계까지 단계를 밟아 들어가지는 않는다 — 제작소를 연 뒤 그 작업을 완성본 있는 상태로 지정
   (MIX_JOB + renderExport)하고, 버튼·서버 굽기·받기는 전부 라이브 실물로 돈다.
"""
import datetime
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import live_admin  # noqa: E402
from tools import link_longform_check as chk  # noqa: E402

_KEY_HERE = Path.home() / "crawling_bot_client" / "LightsailDefaultKey-ap-northeast-2.pem"
if not Path(live_admin.KEY).exists() and _KEY_HERE.exists():
    live_admin.KEY = str(_KEY_HERE).replace("\\", "/")      # PC 마다 사용자 폴더가 다르다
live_admin.HOST = "ubuntu@shoppingshorts.duckdns.org"       # IP 는 바뀐다 — 도메인으로


def _deployed(pg, job):
    return pg.evaluate("""async (j) => { const r = await fetch('/api/mix/longform_link/' + j);
        const d = await r.json().catch(() => ({})); return [r.status, d.state || '', typeof renderLongform]; }""", job)


def run(job, out_dir, wait_until=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    while True:
        with live_admin.admin_page("produce") as pg:
            st = _deployed(pg, job)
            print(datetime.datetime.now().strftime("%H:%M:%S"), "서버 응답·상태·화면 함수:", st, flush=True)
            if st[0] == 200 and st[1] and st[2] == "function":
                return _press(pg, job, out_dir)
        if not wait_until or datetime.datetime.now().strftime("%H:%M") >= wait_until:
            print("❌ 라이브에 아직 안 올라왔다(경로 또는 화면 함수 없음)")
            return 2
        time.sleep(60)


def _press(pg, job, out_dir):
    src = out_dir / "live_final.mp4"
    with pg.expect_download(timeout=120000) as dl:
        pg.evaluate("j => { const a=document.createElement('a'); a.href='/api/mix/video/'+j+'?dl=1'; a.download=''; document.body.appendChild(a); a.click(); }", job)
    dl.value.save_as(str(src))
    pg.evaluate("""j => { MIX_JOB = j;
        document.querySelectorAll('section.panel').forEach(s => { if (s.querySelector('#longformBox')) s.style.display = 'block'; });
        renderExport({rendered: true}); }""", job)
    pg.wait_for_timeout(2500)
    print("버튼(누르기 전):", pg.evaluate("[_lfState.phase, document.getElementById('btnLongform').disabled, document.getElementById('btnLongform').textContent]"))
    if pg.evaluate("_lfState.phase") == "ready":
        # 이미 만든 것이 있으면 다른 문구로 바꿔 **새로 굽는 길**을 탄다
        pg.select_option("#lfWhere", "desc")
        pg.wait_for_timeout(2500)
    if pg.evaluate("_lfState.phase") != "ready":
        pg.click("#btnLongform")
        t0 = time.time()
        pg.wait_for_timeout(1500)
        print("누른 직후:", pg.evaluate("[_lfState.phase, document.getElementById('btnLongform').textContent]"))
        while time.time() - t0 < 600 and pg.evaluate("_lfState.phase") == "running":
            pg.wait_for_timeout(2000)
        print("굽기 끝: %s · %.0f초" % (pg.evaluate("[_lfState.phase, _lfState.msg]"), time.time() - t0))
    if pg.evaluate("_lfState.phase") != "ready":
        pg.locator("#longformBox").screenshot(path=str(out_dir / "live_fail.png"))
        print("❌ 완료 상태가 아니다")
        return 1
    pg.wait_for_timeout(3000)
    print("미리보기 영상(가로·세로·길이):", pg.evaluate("(()=>{const v=document.querySelector('#longformBox video');return v?[v.videoWidth,v.videoHeight,v.duration]:null})()"))
    pg.locator("section.panel:has(#longformBox)").screenshot(path=str(out_dir / "live_ready.png"))
    with pg.expect_download(timeout=120000) as dl:
        pg.click("#longformBox a[download]")
    got = out_dir / "live_longform.mp4"
    dl.value.save_as(str(got))
    print("받은 파일명:", dl.value.suggested_filename, "| 페이지 오류:", pg.errors)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "3", "-i", str(got), "-frames:v", "1", str(out_dir / "live_frame.png")],
                   stdin=subprocess.DEVNULL)
    bad = 0
    for name, ok, detail in chk.check(str(src), str(got)):
        print(("✅" if ok else "❌"), name, "—", detail)
        bad += 0 if ok else 1
    print("라이브 결과: %s" % ("전부 통과" if not bad else "%d개 실패" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    wu = a[a.index("--wait-until") + 1] if "--wait-until" in a else None
    sys.exit(run(a[0], a[1], wu))
