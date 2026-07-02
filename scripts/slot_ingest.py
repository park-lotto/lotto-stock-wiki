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


def _atoms_count_today(source_type: str, date: str) -> int:
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE source_type=? AND date=?",
            (source_type, date)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _atoms_count_since(source_type: str, since_iso: str) -> int:
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM atoms WHERE source_type=? AND created_at>=?",
            (source_type, since_iso)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def _trailing_avg(source_type: str, before_date: str, days: int = 7) -> float:
    """before_date 이전 최근 N일간 source_type 일평균 원자 수. 데이터 없으면 0.0."""
    from pipeline.atoms.db import get_conn
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT date, COUNT(*) c FROM atoms WHERE source_type=? AND date<? "
            "GROUP BY date ORDER BY date DESC LIMIT ?",
            (source_type, before_date, days)).fetchall()
        if not rows:
            return 0.0
        return sum(r[1] for r in rows) / len(rows)
    finally:
        conn.close()


def diagnose(cat: str, date: str, extra_date: str, since_iso: str, output: str) -> dict:
    """카테고리 1개 진단. 문제로 판정되면 ingest_cat()을 1회만 재호출해 재시도한다."""
    source_type = cat
    pending = _extract_pending(output)
    error = _extract_error(output)
    delta = _atoms_count_since(source_type, since_iso)
    retried = False

    if error or (pending > 0 and delta == 0):
        retried = True
        retry_output = ingest_cat(cat, date, extra_date)
        retry_error = _extract_error(retry_output)
        delta = _atoms_count_since(source_type, since_iso)
        if delta > 0 and not retry_error:
            icon, note = "✅", "재시도로 해결"
        else:
            summary = retry_error or error or "원인 미상"
            icon, note = "🔴", f"확인필요 — {summary}"
    else:
        avg = _trailing_avg(source_type, date)
        if delta > 0 and avg > 0 and delta < avg * 0.3:
            icon, note = "⚠️", f"급감(평균 {avg:.0f} 대비 {delta})"
        else:
            icon, note = "✅", "정상"

    total_today = _atoms_count_today(source_type, date)
    return {"cat": cat, "delta": delta, "total_today": total_today,
            "icon": icon, "note": note, "retried": retried}


CAT_LABEL = {"telegram": "텔레그램", "youtube": "유튜브", "blog": "블로그", "report": "리포트"}


def build_report(cats: list[str], date: str, results: list[dict]) -> str:
    """오늘누적(+이번슬롯신규) 표 + 문제/경고 섹션을 텔레그램 HTML 메시지로 조립."""
    hhmm = datetime.now().strftime("%H:%M")
    lines = [f"{_pad('카테고리', 10)}{_pad('오늘누적', 10)}상태", "─" * 28]
    issues = []
    for r in results:
        label = CAT_LABEL.get(r["cat"], r["cat"])
        value = f"{r['total_today']}(+{r['delta']})"
        lines.append(f"{_pad(label, 10)}{_pad(value, 10)}{r['icon']} {r['note']}")
        if r["icon"] in ("🔴", "⚠️"):
            issues.append(f"· {label}: {r['note']}")

    table = "\n".join(lines)
    msg = f"📥 크롤 인제스트  {date[5:]} {hhmm}\n<pre>{table}</pre>"
    if issues:
        head = "🔴 확인 필요" if any(r["icon"] == "🔴" for r in results) else "⚠️ 참고"
        msg += f"\n\n{head} {len(issues)}건\n" + "\n".join(issues)
    return msg


def run(cmd: list[str], label: str) -> tuple[int, str]:
    """서브프로세스 실행. 출력은 화면에 그대로 찍고(기존 가시성 유지), 진단용으로도 반환.
    subprocess 자체 실행 실패(예: 인터프리터 경로 문제)도 예외를 던지지 않고
    에러 텍스트로 반환해 파이프라인이 죽지 않게 한다."""
    print(f"\n{'='*50}\n[{label}] {' '.join(str(c) for c in cmd)}\n{'='*50}")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
        output = (r.stdout or "") + (r.stderr or "")
        code = r.returncode
    except Exception as e:
        output = f"[run 오류] {e}"
        code = -1
    print(output)
    print(f"[{label}] 완료 (exit={code})")
    return code, output


def ingest_cat(cat: str, date: str, extra_date: str | None = None) -> str:
    """카테고리별 인제스트.
    - 텔레는 날짜 단위 파일이라 date + extra_date(전날) 모두 --force-date 처리
    - 유튜브/블로그는 sync 후 파일 목록 기반이라 자동으로 전날분 포함
    반환값: 이번 호출에서 실행된 서브프로세스 출력을 모두 이어붙인 문자열(진단용).
    """
    parts: list[str] = []
    if cat == "telegram":
        if extra_date:
            _, out = run([PY, "-m", "pipeline.atoms.telegram_ingest",
                          "--all", "--force-date", extra_date, "--limit", "40"],
                         f"telegram-{extra_date[5:]}")
            parts.append(out)
        _, out = run([PY, "-m", "pipeline.atoms.telegram_ingest",
                      "--all", "--force-date", date, "--limit", "40"],
                     f"telegram-{date[5:]}")
        parts.append(out)
    elif cat == "youtube":
        _, out = run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "youtube",
                      "--all", "--limit", "60"], "youtube")
        parts.append(out)
    elif cat == "blog":
        _, out = run([PY, "-m", "pipeline.atoms.post_ingest", "--source", "blog",
                      "--all", "--limit", "60"], "blog")
        parts.append(out)
    elif cat == "report":
        _, out = run([PY, "-m", "pipeline.atoms.report_ingest",
                      "--all", "--limit", "40"], "report")
        parts.append(out)
    else:
        print(f"[skip] 알 수 없는 카테고리: {cat}")
    return "\n".join(parts)


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


def _send_ops_tg(text: str) -> None:
    """업무보고 전용 봇으로 발송 (.env OPS_BOT_TOKEN/OPS_CHAT_ID, t.me/parklotto13bot).
    기존 _send_tg()(BOT_TOKEN/CHAT_ID)는 다른 스크립트 브리핑용이라 건드리지 않는다."""
    import urllib.request
    import urllib.parse
    cfg = {}
    envp = ROOT / ".env"
    if envp.exists():
        for line in envp.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    token, chat = cfg.get("OPS_BOT_TOKEN", ""), cfg.get("OPS_CHAT_ID", "")
    if not token or not chat:
        print("[report] 업무보고 봇 설정 없음 (.env OPS_BOT_TOKEN/OPS_CHAT_ID)")
        return
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=10) as r:
            ok = json.loads(r.read()).get("ok")
        print("[report] 업무보고 텔레 전송 " + ("완료" if ok else "실패"))
    except Exception as e:
        print(f"[report] 업무보고 텔레 전송 오류: {e}")


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
