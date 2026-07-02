"""daily_gemini_report.py — 오늘 크롤링·인제스트·Gemini 사용량 보고서 (1회성, 21시 스케줄).

사용법:
    python scripts\\daily_gemini_report.py
"""
import os
import sys
import json
import sqlite3
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")

_FIXED_BUGS_TODAY = """## 오늘(07-02) 고친 버그 목록

1. **vector_db.py 인코딩 크래시** — 임베딩 폴백 키 로딩이 `.env`를 cp949로 읽어 UnicodeDecodeError → utf-8 지정으로 수정
2. **report/PDF 인제스트 키 로테이션 누락** — `questionnaire.py`가 고정 1개 키만 써서 소진 시 그대로 포기 → telegram과 동일한 로테이션 패턴 적용
3. **블로그/뉴스 D등급 오분류** — `taxonomy.py`의 `"blog":"D"`,`"news":"D"` 하드코딩으로 정식 질문지 경로(post_ingest.py) 안 타면 무조건 최하 신뢰도. 오늘분(07-01/07-02) 89개 재처리, 과거분(6/21~6/30, 727개)은 보류
4. **인제스트 경로 침범** — `ingest_pending.py`(범용)가 report/telegram/blog/news/yt까지 훑어서 전용 파이프라인보다 먼저 잘못 처리 → EXCLUDED_TYPES로 스코프 분리, `sync_crawling.py`도 동일 수정
5. **원자 ID 충돌로 조용한 데이터 유실** — `telegram_questionnaire.py::_mk_id`가 raw_file을 안 섞어서 같은 채널+날짜에 여러 파일 있으면(특히 뉴스=공용출처명) ID 겹쳐서 INSERT OR REPLACE로 무음 덮어쓰기. raw_file 포함하도록 수정 + 유실분 재처리
6. **채널명 변경 시 매칭 실패** — 소스 편집페이지에서 표시명 줄이면(예: 독학주식첵터정리→독학주식) 크롤 파일명과 안 맞아 원자 0개 → 접두매칭 폴백
7. **Gemini 키소진 알림 스팸** — 매 프로세스마다 이미 소진된 키 재시도+반복알림 → 당일 소진 상태 파일 기록해서 스킵
8. **브리핑 목록 dedup 버그** — "같은 라벨+날짜"면 최신 1개만 남기고 숨김 → 오늘 만든 여러 "텔레 오늘" 워크스페이스 중 3개가 목록에서 사라짐 → id 기준으로만 dedup하도록 수정
9. **인포그래픽 생성 중 화면 이탈 시 영구 프리징** — 생성 중(스피너) 상태를 그대로 스냅샷 저장해서, 재방문 시 죽은 "생성 중..." 화면이 영원히 표시됨 → 스피너 상태는 저장 안 하도록 수정 + 폴링 타임아웃 4분→10분으로 연장
10. **브리핑 리포트 섹션(④) 부실** — 프롬프트가 ③과 겹치는 내용을 지시해서 AI가 게으르게 "자료 없음"으로 얼버무림(실제 데이터는 있었음) → 프롬프트 명확화
"""


def _env_vals():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def section_ingest_counts():
    db = ROOT / "pipeline" / "atoms" / "atoms.db"
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    lines = ["## 1. 오늘 크롤링·인제스트 실행량\n"]
    cur.execute("""
        SELECT source_type, COUNT(*), COUNT(DISTINCT raw_file)
        FROM atoms WHERE created_at LIKE ?
        GROUP BY source_type ORDER BY 2 DESC
    """, (f"{TODAY}%",))
    rows = cur.fetchall()
    total_atoms = sum(r[1] for r in rows)
    total_files = sum(r[2] for r in rows)
    lines.append("| 유형 | 원자 수 | 처리 파일 수 |")
    lines.append("|---|---|---|")
    for st, acnt, fcnt in rows:
        lines.append(f"| {st} | {acnt} | {fcnt} |")
    lines.append(f"| **합계** | **{total_atoms}** | **{total_files}** |\n")
    conn.close()
    return "\n".join(lines), total_atoms, total_files


def section_key_status():
    lines = ["## 2. Gemini API 키 상태 (21시 시점)\n"]
    ev = _env_vals()
    names = ["GEMINI_INGEST_KEY", "GEMINI_INGEST_KEY_2", "GEMINI_INGEST_KEY_3", "GEMINI_INGEST_KEY_4",
             "GEMINI_API_KEY", "GEMINI_API_KEY_2"]
    roles = ["인제스트전용"] * 4 + ["대화형(공유위험)"] * 2

    state_path = ROOT / "pipeline" / "atoms" / ".gemini_key_state.json"
    persisted_exhausted = set()
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
            if st.get("date") == TODAY:
                persisted_exhausted = set(st.get("exhausted", []))
        except Exception:
            pass

    lines.append("| # | 역할 | 당일 소진 기록(무비용 확인) | 실시간 재확인 |")
    lines.append("|---|---|---|---|")
    try:
        from google import genai
    except Exception:
        genai = None
    for i, (name, role) in enumerate(zip(names, roles)):
        key = ev.get(name, "")
        if not key:
            lines.append(f"| {i} {name} | {role} | (미설정) | - |")
            continue
        marked = "🔴 소진" if i in persisted_exhausted else "🟢 정상"
        live = "-"
        if genai:
            try:
                client = genai.Client(api_key=key)
                resp = client.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
                live = "🟢 OK" if (resp.text or "").strip() else "⚠️빈응답"
            except Exception as e:
                m = str(e)
                live = "🔴 429소진" if ("429" in m or "RESOURCE_EXHAUSTED" in m) else f"⚠️{m[:40]}"
        lines.append(f"| {i} {name} | {role} | {marked} | {live} |")

    if len(persisted_exhausted & {0, 1, 2, 3}) == 4:
        lines.append("\n⚠️ **인제스트전용 4개 키 전부 소진 상태** — 이후 인제스트는 대화형 키(4,5)로 자동 폴백됨.")
    return "\n".join(lines)


def section_scheduler_impact():
    lines = ["## 3. 18:10·21:10 자동 인제스트가 대화형 작업에 영향 줬는지\n"]
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ScheduledTaskInfo -TaskName 'LottoStock_SlotIngest_Main' | "
             "Select-Object LastRunTime,LastTaskResult,NextRunTime | Format-List"],
            capture_output=True, text=True, timeout=20,
        )
        lines.append("```")
        lines.append((out.stdout or out.stderr or "(조회 실패)").strip())
        lines.append("```")
    except Exception as e:
        lines.append(f"(작업스케줄러 조회 실패: {e})")
    lines.append(
        "\n참고: 인제스트전용 키 4개가 소진되면 스크립트는 자동으로 대화형 키(GEMINI_API_KEY·_2)로 "
        "넘어가 계속 작동하도록 설계돼 있습니다 — 즉 실패는 안 하지만, 그 시간대엔 인사이트허브 "
        "채팅/인포그래픽 생성이 같은 쿼터를 나눠 쓰게 됩니다. 위 섹션2에서 대화형 키(4,5)가 "
        "🔴로 뜨면 오늘 밤 인사이트허브 사용 중 쿼터 오류를 만났을 가능성이 있습니다."
    )
    return "\n".join(lines)


def send_telegram(text):
    ev = _env_vals()
    token = os.environ.get("BOT_TOKEN") or ev.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID") or ev.get("CHAT_ID", "")
    if not token or not chat_id:
        print("[WARN] BOT_TOKEN/CHAT_ID 없음 — 텔레 전송 스킵")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15)
    except Exception as e:
        print(f"[WARN] 텔레 전송 실패: {e}")


def main():
    ingest_section, total_atoms, total_files = section_ingest_counts()
    key_section = section_key_status()
    sched_section = section_scheduler_impact()

    report = (
        f"# 📊 오늘의 크롤링·인제스트·Gemini 사용량 보고서 ({TODAY} 21:00)\n\n"
        f"{ingest_section}\n\n{key_section}\n\n{sched_section}\n\n{_FIXED_BUGS_TODAY}"
    )

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"gemini_daily_report_{TODAY}.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"저장됨: {out_path}")

    tg_summary = (
        f"📊 <b>오늘({TODAY}) 크롤링·인제스트 보고서</b>\n"
        f"원자 {total_atoms}개 · 파일 {total_files}개 처리\n"
        f"전체 리포트: out/{out_path.name}"
    )
    send_telegram(tg_summary)
    print("완료")


if __name__ == "__main__":
    main()
