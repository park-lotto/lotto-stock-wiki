"""
make_video_screens.py — 영상 촬영용 화면 세트 생성

씬별로 필요한 화면을 준비합니다:
1. 24시간 타임스탬프 터미널 로그 (씬4 수집직원 데모)
2. 탑픽 스코어카드 HTML (씬4 탑픽직원 데모)
3. 아침 노트 HTML 열기 (씬4 브리핑직원 데모)

사용법:
    python make_video_screens.py
"""

import sys, json, subprocess
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

BASE   = Path(__file__).parent
OUT    = BASE / "out"
TODAY  = date.today().strftime("%Y-%m-%d")
TODAY8 = TODAY.replace("-", "")

OUT.mkdir(exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 24시간 터미널 로그 (영상용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VIDEO_LOG = """
==================================================
STOCK BRAIN NIGHT WATCH — 2026-05-30
==================================================

[14:23:11] [INFO] [수집직원] 증권사 리포트 신규 감지
[14:23:14] [INFO]   > 삼성전기 TP 상향 (한국투자 200만→220만) — 저장
[14:23:17] [INFO]   > SK하이닉스 실적 프리뷰 (NH투자) — 저장
[14:23:19] [INFO] [완료] 리포트 2건 수집

[15:04:33] [INFO] [수집직원] 텔레그램 채널 뉴스 감지
[15:04:35] [INFO]   > [반도체] TSMC 4월 매출 YoY +38% 확인
[15:04:36] [INFO]   > [방산] 폴란드 K2전차 3차 계약 협상 진행 중
[15:04:38] [INFO]   > [바이오] HLB PDUFA D-54일 — 임박 모니터링
[15:04:39] [INFO] [완료] 뉴스 3건 수집

[16:31:07] [INFO] [수집직원] 장마감 후 리포트 쏟아짐
[16:31:12] [INFO]   > 리포트 11건 일괄 수집
[16:31:15] [INFO]   > TP 상향: LG이노텍 한화 1.3M→1.6M, 현대차 KB 28만→32만
[16:31:18] [INFO] [완료] 리포트 11건 처리

[23:03:22] [INFO] [수집직원] 야간 텔레그램 모니터링 시작
[23:11:44] [INFO]   > [미국] 애플 WWDC 발표 예정 — AI 기능 확대 기대
[23:11:46] [INFO] [완료] 뉴스 1건

[23:32:01] [INFO] [미국장직원] 미국 정규장 오픈
[23:32:05] [INFO]   > 나스닥: 26,972 ▲0.20%
[23:32:05] [INFO]   > S&P500: 7,580 ▲0.22%
[23:32:05] [INFO]   > SOX(반도체ETF): 12,829 ▲0.00%
[23:32:05] [INFO]   > QQQ(AI·테크): 738 ▲0.37%
[23:32:05] [INFO]   > VIX: 15.32 ▼2.67% — 안전 구간
[23:32:07] [INFO]   > 원달러: 1,507 ▲0.27%

[01:14:39] [INFO] [미국장직원] 실적 발표 감지
[01:14:42] [INFO]   > 스노우플레이크 어닝서프 +23% — 클라우드 섹터 강세
[01:14:44] [INFO]   > 마이크론 목표주가 상향 (바클레이즈 675→1175)
[01:14:46] [INFO]   > 국내 SK하이닉스 커플링 예상 → 관련 섹터 주목

[03:00:01] [INFO] [수급직원] 수급 오실레이터 전 섹터 스캔 시작
[03:00:04] [INFO]   > 스캔 대상: 16개 섹터 / 500+ 종목
[03:00:31] [INFO]   > 반도체 — A등급 5종목 / B등급 8종목
[03:00:44] [INFO]   > 방산 — A등급 3종목 / B등급 6종목
[03:00:58] [INFO]   > 바이오 — A등급 7종목 / B등급 11종목
[03:01:09] [INFO]   > 조선 — A등급 2종목 / B등급 4종목
[03:01:12] [INFO] [완료] 전 섹터 스캔 완료 — A등급 총 29종목

[03:31:18] [INFO] [투경직원] 투자경고 모니터링
[03:31:22] [INFO]   > 활성 투경 12종목 확인
[03:31:24] [INFO]   > 해제 임박: 코리아써키트 (1조건 미해소)
[03:31:25] [INFO] [완료] 투경 분석 완료

[05:02:07] [INFO] [미국장직원] 미국 정규장 마감
[05:02:09] [INFO]   > 나스닥 종가 확정: 26,972 ▲0.20%
[05:02:10] [INFO]   > SOX 종가 확정: 12,829 ▲0.00%
[05:02:11] [INFO]   > 주요 반도체주: MU +2.1% / NVDA +0.8% / AMAT -0.3%

[05:33:01] [INFO] [분석직원] 탑픽 교차 분석 시작
[05:33:04] [INFO]   > 후보군: A등급 빈집 29종목 × 8개 기준 교차
[05:33:11] [INFO]   > 삼성전기: 7/9점 — 탑픽 후보 🔴
[05:33:14] [INFO]   > 피에스케이홀딩스: 6/9점 — 탑픽 후보 🔴
[05:33:17] [INFO]   > HLB: 5/9점 — 관심주 🟠
[05:33:19] [INFO] [완료] 탑픽 선정 완료

[06:31:44] [INFO] [브리핑직원] 아침 노트 HTML 생성
[06:31:47] [INFO]   > 섹터 온도 반영 완료
[06:31:49] [INFO]   > 탑픽 3종목 삽입 완료
[06:31:51] [INFO]   > 매크로 한 줄 삽입 완료
[06:31:53] [INFO]   > HTML 생성 완료: out/morning_dark_2026-05-30.html

[07:00:00] [INFO] [배포직원] 텔레그램 발송
[07:00:03] [INFO]   > 아침 브리핑 전송 완료
[07:00:04] [INFO]   > 수급 빈집 요약 전송 완료
[07:00:05] [INFO] [완료] 모든 배포 완료

==================================================
총 작업 시간: 8시간 37분 (23:00 ~ 07:00)
수집 건수: 뉴스 18건 / 리포트 13건 / 수급 500+종목
결과: 탑픽 3종목 선정 / 아침 노트 발송 완료
==================================================
"""

log_path = OUT / f"night_video_demo_{TODAY8}.log"
log_path.write_text(VIDEO_LOG.strip(), encoding="utf-8")
print(f"[1] 터미널 로그 생성: {log_path.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 탑픽 스코어카드 HTML
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCORECARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: #0a0e1a;
    color: #f0f4f8;
    font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    padding: 40px;
  }
  .card {
    width: 680px;
    background: #111827;
    border: 1px solid #1e2d45;
    border-radius: 20px;
    padding: 36px;
    box-shadow: 0 0 60px #00e5c320;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid #1e2d45;
  }
  .ticker { font-size: 28px; font-weight: 700; color: #00e5c3; }
  .name   { font-size: 14px; color: #6b7280; margin-top: 4px; }
  .score-badge {
    background: #00e5c320;
    border: 2px solid #00e5c3;
    border-radius: 50%;
    width: 80px; height: 80px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 30px #00e5c340;
  }
  .score-num  { font-size: 32px; font-weight: 900; color: #00e5c3; line-height: 1; }
  .score-deno { font-size: 12px; color: #4a5568; }
  .criteria   { display: flex; flex-direction: column; gap: 10px; }
  .row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    background: #0d1420;
    border-radius: 10px;
    border: 1px solid #1e2d45;
  }
  .row.pass { border-color: #00e5c340; background: #00e5c308; }
  .row.fail { border-color: #1e2d4580; opacity: 0.5; }
  .check { font-size: 18px; width: 24px; flex-shrink: 0; }
  .crit-name { font-size: 13px; font-weight: 600; flex: 1; }
  .crit-val  { font-size: 12px; color: #6b7280; }
  .pass .crit-val { color: #00e5c3; }
  .grade {
    margin-top: 24px;
    padding: 14px 20px;
    background: #ff475720;
    border: 1px solid #ff475760;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .grade-label { font-size: 18px; font-weight: 700; color: #ff4757; }
  .grade-desc  { font-size: 13px; color: #9ca3af; }
  .ts { font-size: 11px; color: #374151; margin-top: 16px; text-align: right; }
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div>
      <div class="ticker">삼성전기 (009150)</div>
      <div class="name">MLCC · FC-BGA · 반도체 소부장</div>
    </div>
    <div class="score-badge">
      <div class="score-num">7</div>
      <div class="score-deno">/ 9점</div>
    </div>
  </div>

  <div class="criteria">
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#0 수급 빈집</span>
      <span class="crit-val">B등급 (하위 18%) — 2점</span>
    </div>
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#1 수출 데이터 🔴</span>
      <span class="crit-val">전기전자 YoY +24.8% — 1점</span>
    </div>
    <div class="row fail">
      <span class="check">❌</span>
      <span class="crit-name">#2 판가 이슈</span>
      <span class="crit-val">MLCC 판가 횡보 — 미충족</span>
    </div>
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#3 어닝 서프라이즈</span>
      <span class="crit-val">1Q26 OP 3,120억 vs 컨센 2,800억 — 1점</span>
    </div>
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#4 리포트 컨센 신고가</span>
      <span class="crit-val">TP 200만→220만 (한국투자) — 1점</span>
    </div>
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#5 미국 유사기업 커플링</span>
      <span class="crit-val">Murata +3.2% / TDK +2.8% — 1점</span>
    </div>
    <div class="row fail">
      <span class="check">❌</span>
      <span class="crit-name">#6 정책 이슈</span>
      <span class="crit-val">해당 없음 — 미충족</span>
    </div>
    <div class="row pass">
      <span class="check">✅</span>
      <span class="crit-name">#7 일정 재료 D-30 이내</span>
      <span class="crit-val">MLCC CAPA 증설 완료 D-22 — 1점</span>
    </div>
  </div>

  <div class="grade">
    <div class="grade-label">🔴 오늘의 탑픽 후보</div>
    <div class="grade-desc">수급빈집 ✅ + 7/9점 = 탑픽 후보 등급</div>
  </div>

  <div class="ts">분석 시각: 2026-05-30 05:33 | STOCK BRAIN AI 직원팀</div>
</div>
</body>
</html>"""

scorecard_path = OUT / f"topick_scorecard_{TODAY8}.html"
scorecard_path.write_text(SCORECARD_HTML, encoding="utf-8")
print(f"[2] 탑픽 스코어카드 생성: {scorecard_path.name}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 화면 열기
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import subprocess, platform

def open_file(path: Path):
    if platform.system() == "Windows":
        subprocess.Popen(["start", str(path)], shell=True)

# 로그 파일 — VS Code로
subprocess.Popen(["code", str(log_path)], shell=True)

# 탑픽 스코어카드 — 브라우저로
open_file(scorecard_path)

# 아침 노트 — 브라우저로
morning_html = OUT / f"morning_dark_{TODAY}.html"
if morning_html.exists():
    open_file(morning_html)
    print(f"[3] 아침 노트 열기: {morning_html.name}")
else:
    print(f"[3] 아침 노트 없음 — python morning_briefing.py --save 먼저 실행")

print("\n화면 준비 완료.")
print("캡처 순서:")
print("  1. VS Code — 터미널 로그 (타임스탬프 보이게)")
print("  2. 브라우저 — 탑픽 스코어카드")
print("  3. 브라우저 — 아침 노트 HTML")
print("  4. 텔레그램 앱 — 실제 수신 메시지 (직접 캡처)")
