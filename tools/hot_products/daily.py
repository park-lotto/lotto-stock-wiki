"""매일 수집 한 번에 — 사장님 PC 작업 스케줄러 '숏템_인기상품_수집'(매일 08:00)이 부른다.
 1) snap.py            네이버·1688·테무·아마존(PC, 테무 로그인 프로필)
 2) coupang_snap.py    쿠팡(서버 쿠팡파트너스 키 — ssh 로 실행, 키는 서버 밖으로 안 나옴)
 3) build_day.py       어제 대비 하루 변화 + 처음 보는 상품 분류(classify.py)
 4) enrich.py · season.py   새 키워드 월검색·추세·유튜브·시즌
 5) build4.py → build_html4.py → check4.py   시안 v4 다시 굽고 브라우저 점검
단계가 실패하면 로그에 ★ 로 남기고 다음 단계는 가능한 데까지 간다(조용한 실패 금지). 로그: work/daily/YYYYMMDD.log"""
import datetime, os, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "work")
os.makedirs(os.path.join(W, "daily"), exist_ok=True)
LOG = open(os.path.join(W, "daily", datetime.date.today().strftime("%Y%m%d") + ".log"), "a", encoding="utf-8")
KEY = r"C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
SERVER = "ubuntu@3.35.251.172"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

def log(msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"; print(line, flush=True); LOG.write(line + "\n"); LOG.flush()

def step(name, cmd, cwd=W, timeout=3600, stdout=None):
    t = time.time(); log(f"▶ {name}")
    try:
        p = subprocess.run(cmd, cwd=cwd, env=ENV, timeout=timeout, text=True, encoding="utf-8", errors="replace",
                           stdout=stdout or subprocess.PIPE, stderr=subprocess.PIPE)
        tail = ((p.stdout or "") if stdout is None else "")[-600:] + (p.stderr or "")[-400:]
        log(f"{'✔' if p.returncode == 0 else '★실패'} {name} rc={p.returncode} {round(time.time() - t)}초\n{tail.strip()}")
        return p.returncode == 0
    except Exception as e:
        log(f"★실패 {name} {type(e).__name__}: {e}"); return False

PY = [sys.executable, "-I"]
step("1 스냅샷(네이버·1688·테무·아마존)", PY + [os.path.join(HERE, "snap.py")], timeout=2400)
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
with open(os.path.join(W, "snaps", f"cp_{ts}.json"), "w", encoding="utf-8") as f:
    ok = step("2 쿠팡(서버)", ["ssh", "-o", "ConnectTimeout=15", "-i", KEY, SERVER,
              'cd ~/hot_research/hot_products && sudo -E bash -c "set -a; . /etc/shopping-shorts.env; set +a; '
              'PYTHONPATH=/home/ubuntu/lotto-stock-wiki python3 coupang_snap.py"'], timeout=600, stdout=f)
if not ok or os.path.getsize(os.path.join(W, "snaps", f"cp_{ts}.json")) < 100:
    os.remove(os.path.join(W, "snaps", f"cp_{ts}.json")); log("★쿠팡 스냅샷 비어서 지움")
step("3 하루 비교·새 상품 분류", PY + [os.path.join(HERE, "build_day.py")], timeout=3600)
step("4a 새 키워드 검색수·추세·유튜브", PY + [os.path.join(HERE, "enrich.py")], timeout=5400)
step("4b 시즌", PY + [os.path.join(HERE, "season.py")], timeout=1800)
step("5a 시안 데이터", PY + [os.path.join(HERE, "build4.py")], cwd=HERE, timeout=1800)
step("5b 시안 HTML", PY + [os.path.join(HERE, "build_html4.py")], cwd=HERE)
step("5c 브라우저 점검", PY + [os.path.join(HERE, "check4.py")], cwd=HERE, timeout=600)
log("끝")
