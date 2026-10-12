"""실제 라이브 작업 1건으로 숏템메이커 제작소를 로컬(8769)에 띄운다.

seed_live_demo.py가 만든 .tmp/live-demo/demo.db 를 쓴다. 로컬 확인 전용이며
라이브 DB·서버는 건드리지 않는다.

  http://127.0.0.1:8769/꾸미기  →  장면꾸미기가 바로 열린다(작업 자동 지정)

★"/"는 못 쓴다 — app.mount("/", ...)가 정적 파일로 먼저 잡아가서 라우트가 안 걸린다
  (실측: / 를 요청하면 랭킹 index.html이 온다). 그래서 별도 경로를 쓴다.

★produce.html(제품 코드)은 건드리지 않는다. 자동 열기는 이 로컬 서버가 껍데기
  페이지에서 주입할 뿐이라, 배포되는 화면에는 아무 영향이 없다.
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

WORK = BASE / '.tmp/live-demo'
DB = WORK / 'demo.db'
if not DB.exists():
    raise SystemExit('먼저 tools/seed_live_demo.py 를 실행하세요')

from shopping_shorts import app as module          # noqa: E402
from fastapi.responses import HTMLResponse         # noqa: E402
import sqlite3                                     # noqa: E402
import uvicorn                                     # noqa: E402

module.DB_PATH = str(DB)
module._MIX_WORK_DIR = WORK / 'mix_jobs'
module._AUTH_ON = False                             # 로컬 확인용 — 로그인 없이 연다

_con = sqlite3.connect(DB)
JOB = _con.execute('select job_id from mix_jobs order by created_at desc limit 1').fetchone()[0]
_con.close()

# ── 로컬 전용 자동 열기 ────────────────────────────────────────────────
# produce.html을 iframe으로 띄우고, 로드된 뒤 그 안에서 작업을 지정해 6단계를
# 펼친 다음 장면꾸미기를 연다. 콘솔에 손으로 치던 두 줄을 대신한다.
_SHELL = """<!doctype html><meta charset="utf-8">
<title>장면꾸미기 · 로컬 확인</title>
<style>html,body{margin:0;height:100%;background:#0b0f14}
iframe{width:100%;height:100%;border:0}
#msg{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);
color:#9fe8c8;font:15px system-ui;z-index:9}</style>
<div id="msg">장면꾸미기를 여는 중…</div>
<iframe id="f" src="/produce.html"></iframe>
<script>
const JOB = %JOB%;
const f = document.getElementById('f');
f.addEventListener('load', () => {
  const w = f.contentWindow, d = f.contentDocument;
  let tries = 0;
  const tick = setInterval(() => {
    tries++;
    const step = d.querySelector('[data-step="3"]');
    const btn  = d.querySelector('[onclick="openSceneStyleEditor()"]');
    if (step && btn && typeof w.openSceneStyleEditor === 'function') {
      clearInterval(tick);
      // ★produce.html의 MIX_JOB은 `let` 이라 **window 속성이 아니다**.
      //   w.MIX_JOB=... 로 넣으면 동명의 딴 속성만 생기고 진짜 변수는 null로 남아
      //   편집기가 "음성·장면을 먼저 준비해 주세요"로 조용히 되돌아간다(실측).
      //   그래서 그 스코프 안에서 실행시켜 렉시컬 변수에 직접 대입한다.
      const s = d.createElement('script');
      s.textContent = 'MIX_JOB=' + JSON.stringify(JOB) + ';';
      d.body.appendChild(s);
      s.remove();
      step.style.display = 'block';
      btn.scrollIntoView();
      w.openSceneStyleEditor();
      document.getElementById('msg').remove();
    } else if (tries > 100) {
      clearInterval(tick);
      document.getElementById('msg').textContent =
        '자동 열기 실패 — produce.html 에서 직접 열어주세요';
    }
  }, 100);
});
</script>"""


def _local_home():
    """로컬 확인 전용 진입점 — 장면꾸미기를 바로 연다."""
    import json
    return HTMLResponse(_SHELL.replace("%JOB%", json.dumps(JOB)))


# ★라우트를 **마운트 앞에** 끼워넣는다. app.mount("/", ...)가 import 시점에 이미
#   등록돼 있어서, 그냥 @app.get 으로 붙이면 뒤에 달려 영영 안 걸린다(실측 404).
module.app.add_api_route("/꾸미기", _local_home, methods=["GET"],
                         response_class=HTMLResponse)
_added = module.app.router.routes.pop()
_mount_at = next(i for i, r in enumerate(module.app.router.routes)
                 if getattr(r, "path", None) == "" or getattr(r, "name", "") == "static")
module.app.router.routes.insert(_mount_at, _added)


if __name__ == '__main__':
    print(f'작업 {JOB} · http://127.0.0.1:8769/꾸미기 에서 장면꾸미기가 바로 열립니다')
    uvicorn.run(module.app, host='127.0.0.1', port=8769, log_level='warning')
