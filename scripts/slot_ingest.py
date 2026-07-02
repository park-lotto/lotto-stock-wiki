"""
slot_ingest.py — 슬롯별 크롤 데이터 인제스트 (서버크롤 독립 + 로컬 인제스트)

서버(crawlingbot.service)가 config.yaml 스케줄대로 크롤 → client.py가 로컬
crawling_bot_data 로 자동 다운로드 → 이 스크립트가 raw/ 동기화 후 원자화한다.

크롤 스케줄 (서버 config.yaml):
  telegram/youtube/blog : 08,12,15,18,21시
  reports               : 08,11시
→ Windows 작업스케줄러가 각 크롤 +10분 뒤 이 스크립트를 카테고리별로 실행.

사용법:
    python scripts/slot_ingest.py --cats telegram,youtube,blog
    python scripts/slot_ingest.py --cats report
    python scripts/slot_ingest.py --cats telegram,youtube,blog --date 2026-07-01
"""
import sys
import re
import json
import unicodedata
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
PY = sys.executable


def _disp_width(s: str) -> int:
    """동아시아 넓은 문자(한글 등)를 폭 2로 계산 — 텔레그램 모노스페이스 표 정렬용."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    """오른쪽 공백 패딩(한글 폭 보정). 이미 목표폭 이상이면 그대로 반환."""
    return s + " " * max(0, width - _disp_width(s))


def _extract_pending(text: str) -> int:
    """서브프로세스 출력에서 '미처리 {라벨}: N개' 패턴의 N을 추출. 못 찾으면 0."""
    m = re.search(r"미처리[^:：]*[:：]\s*(\d+)개", text)
    return int(m.group(1)) if m else 0


_ERROR_SIGNS = ("Traceback", "RESOURCE_EXHAUSTED", "429", "quota",
                "Authentication", "invalid_api_key", "invalid api key",
                "ConnectionError", "run 오류")


def _extract_error(text: str) -> str | None:
    """서브프로세스 출력에서 에러 시그니처가 포함된 첫 줄을 찾아 반환. 없으면 None."""
    for line in text.splitlines():
        if any(sign in line for sign in _ERROR_SIGNS):
            return line.strip()[:200]
    return None


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'='*50}\n[{label}] {' '.join(str(c) for c in cmd)}\n{'='*50}")
    r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"[{label}] 완료 (exit={r.returncode})")
    return r.returncode


def ingest_cat(cat: str, date: str, extra_date: str | None = None) -> None:
    """카테고리별 인제스트.
    - 텔레는 날짜 단위 파일이라 date + extra_date(전날) 모두 --force-date 처리
    - 유튜브/블로그는 sync 후 파일 목록 기반이라 자동으로 전날분 포함
    """
    if cat == "telegram":
        # 전날 먼저 처리(공백 보완) → 당일 처리
        if extra_date:
            run([PY, "-m", "pipeline.atoms.telegram_ingest",
                 "--all", "--force-date", extra_date, "--limit", "40"], f"telegram-{extra_date[5:]}")
        run([PY, "-m", "pipeline.atoms.telegram_ingest",
             "--all", "--force-date", date, "--limit", "40"], f"telegram-{date[5:]}")
    elif cat == "youtube":
        run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "youtube",
             "--all", "--limit", "60"], "youtube")
    elif cat == "blog":
        run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "blog",
             "--all", "--limit", "60"], "blog")
    elif cat == "report":
        run([PY, "-m", "pipeline.atoms.report_ingest",
             "--all", "--limit", "40"], "report")
    else:
        print(f"[skip] 알 수 없는 카테고리: {cat}")


def _send_tg(text: str) -> None:
    """자급식 텔레 발송 (.env BOT_TOKEN/CHAT_ID)."""
    import urllib.request
    import urllib.parse
    cfg = {}
    envp = ROOT / ".env"
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    token, chat = cfg.get("BOT_TOKEN", ""), cfg.get("CHAT_ID", "")
    if not token or not chat:
        print("[report] 텔레 설정 없음 (.env BOT_TOKEN/CHAT_ID)")
        return
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=10) as r:
            ok = json.loads(r.read()).get("ok")
        print("[report] 텔레 전송 " + ("완료" if ok else "실패"))
    except Exception as e:
        print(f"[report] 텔레 전송 오류: {e}")


def send_report(cats: list[str], since_iso: str, date: str) -> None:
    """이번 슬롯에서 새로 적재된 원자를 요약해 텔레로 보고."""
    try:
        from pipeline.atoms.db import get_conn
        conn = get_conn()
        by_src = conn.execute(
            "SELECT source_type, COUNT(*) FROM atoms WHERE created_at >= ? "
            "GROUP BY source_type ORDER BY 2 DESC", (since_iso,)).fetchall()
        secs = conn.execute(
            "SELECT sector, COUNT(*) FROM atoms WHERE created_at >= ? "
            "AND sector IS NOT NULL AND sector NOT IN ('기타','') "
            "GROUP BY sector ORDER BY 2 DESC LIMIT 5", (since_iso,)).fetchall()
        assets = conn.execute(
            "SELECT asset, COUNT(*) FROM atoms WHERE created_at >= ? "
            "AND asset_level='stock' AND asset IS NOT NULL AND asset != '' "
            "GROUP BY asset ORDER BY 2 DESC LIMIT 6", (since_iso,)).fetchall()
        conn.close()
    except Exception as e:
        print(f"[report] DB 조회 실패: {e}")
        return

    total = sum(n for _, n in by_src)
    hhmm = datetime.now().strftime("%H:%M")
    lines = [f"📥 <b>크롤 인제스트 완료</b> {date[5:]} {hhmm}",
             f"카테고리: {', '.join(cats)}", ""]
    if total == 0:
        lines.append("신규 원자 없음")
    else:
        lines.append(f"<b>신규 원자 {total}개</b>")
        lines += [f"• {st} {n}" for st, n in by_src]
        if secs:
            lines.append("")
            lines.append("🏭 섹터: " + " ".join(f"{s}({n})" for s, n in secs))
        if assets:
            lines.append("📈 종목: " + " ".join(f"{a}({n})" for a, n in assets))
    _send_tg("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="슬롯별 크롤 인제스트")
    ap.add_argument("--cats", required=True,
                    help="쉼표구분: telegram,youtube,blog,report")
    ap.add_argument("--date", default=None, help="날짜 YYYY-MM-DD (기본=오늘)")
    ap.add_argument("--no-report", action="store_true", help="텔레 보고 생략")
    args = ap.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    since_iso = datetime.now().isoformat()  # 이번 실행 이후 생성된 원자만 집계
    print(f"[slot_ingest] {date} (전날보완: {yesterday}) | cats={cats}")

    # 1) 동기화: 전날 + 오늘 모두 overwrite
    #    → 전날 21시처럼 슬롯 사이 공백이 생겨도 다음 슬롯에서 자동 회수
    run([PY, "scripts/sync_crawling.py", "--date", yesterday, "--overwrite"], "sync-yesterday")
    run([PY, "scripts/sync_crawling.py", "--date", date, "--overwrite"], "sync-today")

    # 2) 카테고리별 원자화 (텔레는 전날 날짜도 함께 처리)
    for c in cats:
        ingest_cat(c, date, extra_date=yesterday)

    # 3) 텔레 보고
    if not args.no_report:
        send_report(cats, since_iso, date)

    print(f"\n[slot_ingest] 완료 — {date} {cats}")


if __name__ == "__main__":
    main()
