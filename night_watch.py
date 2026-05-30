"""
night_watch.py — 밤새 AI 직원 오케스트레이터

내가 잠든 순간부터 깨는 순간까지 밤새 수집·분석·배포.

타임라인:
  23:00~     수집 직원: 텔레그램 뉴스 + 미국 시장 모니터링 시작
  23:30~     미국 정규장 오픈 → 나스닥/섹터 ETF 30분마다 체크
  03:00      분석 직원: 수급 오실레이터 전 섹터 스캔
  05:30      미국 장 마감 → 종가 확정 → 브리핑 생성
  06:00      브리핑 직원: 아침 노트 HTML 생성
  07:00      배포 직원: 텔레그램 전송

사용법:
  python night_watch.py           # 지금 즉시 시작 (밤새 대기)
  python night_watch.py --now     # 테스트: 지금 바로 전체 파이프라인 1회 실행
  python night_watch.py --step 수급   # 특정 단계만 실행
"""

import sys, os, time, subprocess, argparse, json
from datetime import datetime, date
from pathlib import Path
import urllib.request, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).parent
LOG_DIR = BASE / "out" / "night_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── .env 로드 ────────────────────────────────────────────────────────
def load_env():
    env = {}
    ep = BASE / ".env"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
BOT_TOKEN = ENV.get("BOT_TOKEN", "")
CHAT_ID   = ENV.get("CHAT_ID", "")


# ── 로거 ─────────────────────────────────────────────────────────────
log_file = LOG_DIR / f"night_{date.today().strftime('%Y%m%d')}.log"

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── 텔레그램 ─────────────────────────────────────────────────────────
def tg(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        log("텔레그램 설정 없음 — 콘솔만 출력", "WARN")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }).encode()
    try:
        urllib.request.urlopen(url, data, timeout=10)
        log("텔레그램 전송 완료")
    except Exception as e:
        log(f"텔레그램 전송 실패: {e}", "ERROR")


# ── 서브프로세스 실행 ─────────────────────────────────────────────────
def run(script: str, args: list = [], label: str = ""):
    label = label or script
    log(f"[실행 시작] {label}")
    cmd = [sys.executable, str(BASE / script)] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", cwd=str(BASE), timeout=300
        )
        if result.stdout:
            for line in result.stdout.strip().splitlines()[-10:]:
                log(f"  > {line}")
        if result.returncode != 0 and result.stderr:
            log(f"  [오류] {result.stderr.strip()[:200]}", "ERROR")
            return False
        log(f"[완료] {label}")
        return True
    except subprocess.TimeoutExpired:
        log(f"[타임아웃] {label}", "ERROR")
        return False
    except Exception as e:
        log(f"[예외] {label}: {e}", "ERROR")
        return False


# ── 미국 시장 스냅샷 (yfinance) ──────────────────────────────────────
def us_market_snapshot():
    try:
        import yfinance as yf
        symbols = {
            "나스닥": "^IXIC", "S&P500": "^GSPC", "VIX": "^VIX",
            "반도체ETF(SOX)": "^SOX", "AI·테크(QQQ)": "QQQ",
            "달러인덱스": "DX-Y.NYB", "원달러": "KRW=X", "WTI": "CL=F"
        }
        lines = []
        for name, sym in symbols.items():
            h = yf.Ticker(sym).history(period="2d", interval="1d")
            if len(h) >= 2:
                prev, cur = h["Close"].iloc[-2], h["Close"].iloc[-1]
                chg = (cur / prev - 1) * 100
                arrow = "▲" if chg >= 0 else "▼"
                lines.append(f"{name}: {cur:,.2f} {arrow}{abs(chg):.2f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"시장 데이터 조회 실패: {e}"


# ══════════════════════════════════════════════════════════════════════
# 직원별 작업 함수
# ══════════════════════════════════════════════════════════════════════

def job_us_market_check():
    """직원2: 미국 시장 스냅샷 (30분마다 호출)"""
    log("── 미국 시장 체크 ──")
    snapshot = us_market_snapshot()
    log(snapshot)
    # 주요 변동 있으면 텔레그램 알림 (VIX 25 이상 등 위험 신호)
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        if vix >= 25:
            tg(f"⚠️ <b>VIX 경고</b>\nVIX {vix:.1f} — 공포 구간\n\n{snapshot}")
            log(f"VIX {vix:.1f} 경고 발송", "WARN")
    except Exception:
        pass


def job_news_collect():
    """직원1: 크롤링 뉴스 수집 브리핑"""
    log("── 뉴스 수집 직원 실행 ──")
    run("send_crawl_brief.py", ["--dry"], label="뉴스 수집 확인")


def job_oscillator():
    """직원3: 수급 오실레이터 전 섹터 스캔"""
    log("── 수급 오실레이터 스캔 (전 섹터) ──")
    ok = run("calc_oscillator.py", ["--all", "--tg"], label="수급 오실레이터")
    if ok:
        tg("🔍 <b>수급 스캔 완료</b>\n빈집 종목 분석 완료\n자세한 내용은 아침 브리핑 확인")
    return ok


def job_투경():
    """직원4: 투자경고 모니터링"""
    log("── 투자경고 모니터링 ──")
    run("fetch_투경.py", ["--daily", "--tg"], label="투경 모니터링")


def job_morning_briefing():
    """직원5: 미국 시장 브리핑 생성"""
    log("── 아침 브리핑 생성 ──")
    ok = run("morning_briefing.py", ["--tg", "--save"], label="아침 브리핑")
    return ok


def job_html_generate():
    """직원6: 아침 노트 HTML 생성"""
    log("── 아침 노트 HTML 생성 ──")
    ok = run("generate_morning_html.py", [], label="HTML 생성")
    return ok


def job_final_send():
    """직원7: 최종 아침 브리핑 텔레그램 전송"""
    log("── 최종 배포 ──")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 밤새 로그 요약
    log_lines = []
    if log_file.exists():
        all_lines = log_file.read_text(encoding="utf-8").splitlines()
        # 완료 라인만 뽑기
        done_lines = [l for l in all_lines if "[완료]" in l or "[오류]" in l]
        log_lines = done_lines[-10:]

    summary = "\n".join(log_lines) if log_lines else "밤새 작업 완료"

    msg = f"""🌅 <b>STOCK BRAIN 아침 브리핑</b>
{now}

직원들이 밤새 일했습니다.

<b>작업 완료 내역</b>
{summary}

📊 아침 노트 및 탑픽은 대시보드에서 확인하세요."""

    tg(msg)
    log("최종 아침 브리핑 전송 완료")


# ══════════════════════════════════════════════════════════════════════
# 스케줄 테이블
# ══════════════════════════════════════════════════════════════════════

SCHEDULE = [
    # (실행 시각 "HH:MM", 함수, 이름)
    ("23:35", job_us_market_check,  "미국 장 오픈 체크"),
    ("00:30", job_us_market_check,  "미국 장 중간 체크 1"),
    ("01:30", job_news_collect,     "뉴스 수집"),
    ("02:30", job_us_market_check,  "미국 장 중간 체크 2"),
    ("03:00", job_oscillator,       "수급 오실레이터 스캔"),
    ("03:30", job_투경,             "투자경고 모니터링"),
    ("05:10", job_us_market_check,  "미국 장 마감 체크"),
    ("05:30", job_morning_briefing, "아침 브리핑 생성"),
    ("06:00", job_html_generate,    "HTML 생성"),
    ("07:00", job_final_send,       "최종 텔레그램 발송"),
]


def minutes_from_midnight(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


# ══════════════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════════════

def run_all_now():
    """--now: 전체 파이프라인 즉시 1회 실행 (테스트용)"""
    log("=" * 50)
    log("테스트 모드: 전체 파이프라인 즉시 실행")
    log("=" * 50)
    job_us_market_check()
    job_oscillator()
    job_morning_briefing()
    job_html_generate()
    job_final_send()
    log("테스트 완료")


def run_step(step: str):
    """--step: 특정 단계만 실행"""
    steps = {
        "미국": job_us_market_check,
        "수급": job_oscillator,
        "투경": job_투경,
        "브리핑": job_morning_briefing,
        "html": job_html_generate,
        "배포": job_final_send,
        "뉴스": job_news_collect,
    }
    fn = steps.get(step)
    if fn:
        log(f"단계 실행: {step}")
        fn()
    else:
        log(f"알 수 없는 단계: {step} (선택: {list(steps.keys())})", "ERROR")


def run_schedule():
    """밤새 스케줄 대기 모드"""
    log("=" * 50)
    log("STOCK BRAIN 나이트 워치 시작")
    log(f"로그 파일: {log_file}")
    log("=" * 50)

    done_jobs = set()

    while True:
        now = datetime.now()
        current_min = now.hour * 60 + now.minute
        current_time = now.strftime("%H:%M")

        for time_str, fn, name in SCHEDULE:
            job_key = time_str
            target_min = minutes_from_midnight(time_str)

            # 해당 분에 한 번만 실행
            if current_min == target_min and job_key not in done_jobs:
                log(f"\n{'='*40}")
                log(f"스케줄 실행: {name} ({time_str})")
                log(f"{'='*40}")
                try:
                    fn()
                except Exception as e:
                    log(f"오류: {e}", "ERROR")
                done_jobs.add(job_key)

        # 오전 8시 이후 종료
        if now.hour >= 8 and len(done_jobs) >= len(SCHEDULE):
            log("모든 작업 완료. 나이트 워치 종료.")
            break

        # 자정 넘으면 done_jobs 리셋
        if now.hour == 0 and now.minute == 0:
            done_jobs = set()

        time.sleep(30)  # 30초마다 체크


def main():
    ap = argparse.ArgumentParser(description="STOCK BRAIN 나이트 워치")
    ap.add_argument("--now",  action="store_true", help="즉시 전체 파이프라인 실행 (테스트)")
    ap.add_argument("--step", help="특정 단계만 실행 (미국/수급/투경/브리핑/html/배포/뉴스)")
    args = ap.parse_args()

    if args.now:
        run_all_now()
    elif args.step:
        run_step(args.step)
    else:
        run_schedule()


if __name__ == "__main__":
    main()
