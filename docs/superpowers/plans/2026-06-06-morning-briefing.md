# 아침 브리핑 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 07:30 텔레그램 봇이 운영자에게 2단계 질문을 던지고, 답변을 받아 운영자 판단이 담긴 브리핑 카드를 자동 생성·PNG 캡처·텔레그램 채널 전송하는 시스템 구축

**Architecture:** collect.py가 wiki에서 오늘 핵심 이슈를 추출 → bot.py가 텔레그램 양방향 대화로 운영자 판단을 수집 → card_gen.py가 판단이 담긴 HTML 카드 생성 → publish.py가 Playwright로 PNG 캡처 후 채널 전송. 각 모듈은 `pipeline/briefing_state.json`을 통해 상태를 공유한다.

**Tech Stack:** Python 3.11, python-telegram-bot 21.x, anthropic SDK (claude-haiku-4-5), playwright (chromium), Google Genai SDK (기존 코드와 동일 패턴)

---

## 사전 준비 (코드 작성 전)

- [ ] **BotFather에서 신규 봇 생성**
  - 텔레그램에서 @BotFather → `/newbot` → 이름: `StockBrainBriefing` → 토큰 복사
  - `.env` 파일에 추가:
    ```
    BRIEFING_BOT_TOKEN=<발급받은 토큰>
    BRIEFING_OPERATOR_CHAT_ID=<운영자 본인 chat_id>
    BRIEFING_CHANNEL_ID=<배포할 채널 ID, 예: @lotto_stockbrain>
    ```
  - chat_id 확인법: 봇에게 아무 메시지 보낸 후 `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속

- [ ] **패키지 설치 확인**
  ```bash
  pip install python-telegram-bot==21.6 playwright
  python -m playwright install chromium
  ```

---

## 파일 구조

```
scripts/briefing/
  __init__.py       — 빈 파일 (패키지 선언)
  collect.py        — wiki에서 오늘 핵심 이슈 3~5개 추출
  bot.py            — 텔레그램 양방향 봇 (질문 전송 + 답변 수신 + 타임아웃)
  card_gen.py       — 운영자 판단이 담긴 HTML 카드 생성
  publish.py        — Playwright PNG 캡처 + 텔레그램 채널 전송

pipeline/
  briefing_state.json   — 오늘 이슈·운영자 답변·카드 경로 공유 상태

out/
  briefing_아침_YYYYMMDD.html   — 생성된 카드
  briefing_아침_YYYYMMDD.png    — 캡처된 PNG
```

---

## Task 1: 상태 파일 + collect.py (이슈 추출)

**Files:**
- Create: `scripts/briefing/__init__.py`
- Create: `scripts/briefing/collect.py`
- Create: `pipeline/briefing_state.json` (초기값)

- [ ] **Step 1: `__init__.py` 생성**

  ```python
  # scripts/briefing/__init__.py
  ```

- [ ] **Step 2: 초기 상태 파일 생성**

  `pipeline/briefing_state.json`:
  ```json
  {
    "date": "",
    "issues": [],
    "selected_index": null,
    "verdict": "",
    "reason": "",
    "card_html": "",
    "card_png": "",
    "stage": "idle"
  }
  ```
  `stage` 값: `idle` → `collected` → `q1_sent` → `q2_sent` → `answered` → `card_done` → `published`

- [ ] **Step 3: `collect.py` 작성**

  ```python
  """
  collect.py — wiki L5_섹터에서 오늘 핵심 이슈 3~5개 추출
  
  사용:
    python scripts/briefing/collect.py
    python scripts/briefing/collect.py --date 2026-06-06
  """
  import sys, io, json, argparse
  from datetime import date, timedelta
  from pathlib import Path
  import anthropic
  
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
  
  ROOT       = Path(__file__).parent.parent.parent
  WIKI_L5    = ROOT / 'wiki' / 'L5_섹터'
  STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
  
  def load_state() -> dict:
      return json.loads(STATE_PATH.read_text(encoding='utf-8'))
  
  def save_state(s: dict):
      STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
  
  def gather_recent_wiki(target_date: str) -> str:
      """오늘 날짜가 포함된 섹터 index 파일들의 최근 100줄 수집"""
      chunks = []
      for sector_dir in sorted(WIKI_L5.iterdir()):
          idx = sector_dir / f'sector_{sector_dir.name}.md'
          if not idx.exists():
              idx_candidates = list(sector_dir.glob('sector_*.md'))
              if not idx_candidates:
                  continue
              idx = idx_candidates[0]
          lines = idx.read_text(encoding='utf-8').splitlines()
          # 오늘 날짜 포함 줄 주변 50줄만
          relevant = []
          for i, line in enumerate(lines):
              if target_date in line:
                  start = max(0, i - 2)
                  end = min(len(lines), i + 50)
                  relevant.extend(lines[start:end])
                  break
          if relevant:
              chunks.append(f"### {sector_dir.name}\n" + '\n'.join(relevant[:80]))
      return '\n\n'.join(chunks[:8])  # 최대 8섹터
  
  def extract_issues(wiki_text: str, target_date: str) -> list[dict]:
      """Haiku로 오늘 핵심 이슈 3~5개 추출"""
      client = anthropic.Anthropic()
      prompt = f"""아래는 {target_date} 기준 주식 섹터 위키 내용이다.

  {wiki_text}

  위 내용에서 오늘({target_date}) 가장 중요한 핵심 이슈 3~5개를 추출하라.
  각 이슈는 반드시 JSON 배열로 반환하라:
  [
    {{
      "sector": "반도체",
      "headline": "브로드컴 쇼크 여파 + 피에스케이 상한가",
      "pivot_a": "일시 조정 — AI 가이던스 상향, 곧 반등",
      "pivot_b": "추세 전환 — 네트워크 부진이 구조적 문제"
    }}
  ]
  - headline: 이슈 핵심 1줄 (30자 이내)
  - pivot_a: 강세/낙관 판단 시나리오 (20자 이내)
  - pivot_b: 약세/주의 판단 시나리오 (20자 이내)
  JSON만 반환, 다른 텍스트 없이."""
  
      resp = client.messages.create(
          model='claude-haiku-4-5-20251001',
          max_tokens=800,
          messages=[{'role': 'user', 'content': prompt}]
      )
      text = resp.content[0].text.strip()
      # JSON 파싱
      if text.startswith('```'):
          text = text.split('```')[1]
          if text.startswith('json'):
              text = text[4:]
      return json.loads(text)
  
  def main():
      parser = argparse.ArgumentParser()
      parser.add_argument('--date', default=str(date.today()))
      args = parser.parse_args()
      target_date = args.date
  
      print(f"[collect] {target_date} 이슈 추출 시작")
      wiki_text = gather_recent_wiki(target_date)
      if not wiki_text:
          print("[collect] 오늘 데이터 없음 — ingest 먼저 실행 필요")
          sys.exit(1)
  
      issues = extract_issues(wiki_text, target_date)
      print(f"[collect] 추출된 이슈 {len(issues)}개: {[i['sector'] for i in issues]}")
  
      state = load_state()
      state['date'] = target_date
      state['issues'] = issues
      state['stage'] = 'collected'
      save_state(state)
      print(f"[collect] 상태 저장 완료 → {STATE_PATH}")
  
  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: 실행 테스트**

  ```bash
  python scripts/briefing/collect.py --date 2026-06-06
  ```
  예상 출력:
  ```
  [collect] 2026-06-06 이슈 추출 시작
  [collect] 추출된 이슈 3개: ['반도체', '조선', '로봇']
  [collect] 상태 저장 완료 → pipeline/briefing_state.json
  ```
  `pipeline/briefing_state.json` 열어서 `issues` 배열 3~5개 확인

- [ ] **Step 5: 커밋**

  ```bash
  git add scripts/briefing/__init__.py scripts/briefing/collect.py pipeline/briefing_state.json
  git commit -m "feat: briefing/collect.py — 오늘 핵심 이슈 추출"
  ```

---

## Task 2: bot.py (텔레그램 양방향 봇)

**Files:**
- Create: `scripts/briefing/bot.py`

> `.env`에 `BRIEFING_BOT_TOKEN`, `BRIEFING_OPERATOR_CHAT_ID` 설정 필요 (사전 준비 참고)

- [ ] **Step 1: `bot.py` 작성**

  ```python
  """
  bot.py — 텔레그램 양방향 브리핑 봇
  
  흐름:
    1. state.json의 issues 읽기
    2. 운영자에게 1단계 질문 (섹터 선택)
    3. 답변 수신 → 2단계 질문 (A/B 판단)
    4. 답변 수신 → card_gen 트리거
    5. 08:00 타임아웃 → 자동 초안 트리거
  
  사용:
    python scripts/briefing/bot.py
  """
  import sys, io, json, asyncio, os
  from datetime import datetime, time as dtime
  from pathlib import Path
  from telegram import Update, Bot
  from telegram.ext import Application, MessageHandler, filters, ContextTypes
  
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  
  ROOT       = Path(__file__).parent.parent.parent
  STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
  
  BOT_TOKEN   = os.environ['BRIEFING_BOT_TOKEN']
  OPERATOR_ID = int(os.environ['BRIEFING_OPERATOR_CHAT_ID'])
  TIMEOUT_TIME = dtime(8, 0)  # 08:00
  
  def load_state() -> dict:
      return json.loads(STATE_PATH.read_text(encoding='utf-8'))
  
  def save_state(s: dict):
      STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
  
  def build_q1_text(issues: list[dict]) -> str:
      lines = ['📊 *STOCK BRAIN 오늘의 브리핑 질문 (1/2)*\n',
               '오늘 핵심 이슈 정리됐어요\\.\n어느 섹터에 집중할까요?\n']
      for i, issue in enumerate(issues, 1):
          lines.append(f'{i}\\. {issue["sector"]} — {issue["headline"]}')
      lines.append('\n번호로 답해주세요 \\(예: 1\\)')
      lines.append('⏰ 08:00까지 미답변 시 자동 초안 발행')
      return '\n'.join(lines)
  
  def build_q2_text(issue: dict) -> str:
      return (
          f'📊 *STOCK BRAIN 오늘의 브리핑 질문 \\(2/2\\)*\n\n'
          f'{issue["sector"]} 선택하셨군요\\.\n판단을 알려주세요:\n\n'
          f'A\\. {issue["pivot_a"]}\n'
          f'B\\. {issue["pivot_b"]}\n\n'
          f'판단 \\+ 이유 한 줄만요\\.\n'
          f'예: "A\\. 이유 한 줄"'
      )
  
  async def send_q1(bot: Bot, state: dict):
      issues = state['issues']
      text = build_q1_text(issues)
      await bot.send_message(chat_id=OPERATOR_ID, text=text, parse_mode='MarkdownV2')
      state['stage'] = 'q1_sent'
      save_state(state)
      print('[bot] 1단계 질문 전송 완료')
  
  async def trigger_card_gen(auto: bool = False):
      """card_gen.py 호출 (subprocess)"""
      import subprocess
      flag = '--auto' if auto else ''
      result = subprocess.run(
          [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'card_gen.py'), flag],
          capture_output=True, text=True, encoding='utf-8'
      )
      print(result.stdout)
      if result.returncode != 0:
          print(f'[bot] card_gen 오류: {result.stderr}', file=sys.stderr)
  
  async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
      if update.effective_chat.id != OPERATOR_ID:
          return
      text = update.message.text.strip()
      state = load_state()
      stage = state['stage']
  
      if stage == 'q1_sent':
          # 번호 파싱
          try:
              idx = int(text) - 1
              assert 0 <= idx < len(state['issues'])
          except (ValueError, AssertionError):
              await update.message.reply_text('번호로만 답해주세요 (예: 1)')
              return
          state['selected_index'] = idx
          state['stage'] = 'q2_sent'
          save_state(state)
          issue = state['issues'][idx]
          await update.message.reply_text(
              build_q2_text(issue), parse_mode='MarkdownV2'
          )
          print(f'[bot] 2단계 질문 전송: {issue["sector"]}')
  
      elif stage == 'q2_sent':
          # 판단 + 근거 저장
          verdict = 'A' if text.upper().startswith('A') else 'B'
          reason = text[2:].strip() if len(text) > 2 else text
          state['verdict'] = verdict
          state['reason'] = reason
          state['stage'] = 'answered'
          save_state(state)
          await update.message.reply_text('✅ 받았어요! 카드 생성 시작할게요.')
          print(f'[bot] 답변 수신: {verdict} / {reason}')
          await trigger_card_gen(auto=False)
          context.application.stop_running()
  
  async def timeout_check(bot: Bot, state: dict, app):
      """08:00까지 대기 후 자동 초안 생성"""
      while True:
          await asyncio.sleep(30)
          now = datetime.now().time()
          state = load_state()
          if state['stage'] in ('card_done', 'published', 'answered'):
              break
          if now >= TIMEOUT_TIME:
              print('[bot] 타임아웃 — 자동 초안 생성')
              await bot.send_message(
                  chat_id=OPERATOR_ID,
                  text='⏰ 미답변으로 자동 초안 카드 발행해요.'
              )
              await trigger_card_gen(auto=True)
              app.stop_running()
              break
  
  async def main():
      state = load_state()
      if state['stage'] not in ('collected',):
          print(f'[bot] 현재 stage={state["stage"]}, collected 아님 — 중단')
          return
  
      app = Application.builder().token(BOT_TOKEN).build()
      app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
  
      async with app:
          await app.start()
          await send_q1(app.bot, state)
          # 타임아웃 체크 병행
          asyncio.create_task(timeout_check(app.bot, state, app))
          await app.updater.start_polling()
          await app.updater.idle()
          await app.stop()
  
  if __name__ == '__main__':
      asyncio.run(main())
  ```

- [ ] **Step 2: 봇 동작 수동 테스트**

  터미널에서 실행:
  ```bash
  python scripts/briefing/bot.py
  ```
  - 텔레그램에서 봇에게 `1` 전송 → 2단계 질문 오는지 확인
  - `A. 테스트 이유입니다` 전송 → "✅ 받았어요!" 응답 확인
  - `pipeline/briefing_state.json`에서 `stage: answered`, `verdict: A` 확인

- [ ] **Step 3: 커밋**

  ```bash
  git add scripts/briefing/bot.py
  git commit -m "feat: briefing/bot.py — 텔레그램 양방향 봇 (2단계 질문+타임아웃)"
  ```

---

## Task 3: card_gen.py (운영자 판단 담긴 카드 생성)

**Files:**
- Create: `scripts/briefing/card_gen.py`
- Reference: `channel/strategy/briefing_카드_디자인스펙.md` (기존 CSS/HTML 패턴 참고)

- [ ] **Step 1: `card_gen.py` 작성**

  ```python
  """
  card_gen.py — 운영자 판단이 담긴 아침 브리핑 HTML 카드 생성
  
  사용:
    python scripts/briefing/card_gen.py          # 운영자 답변 기반
    python scripts/briefing/card_gen.py --auto   # 자동 초안 (워터마크 포함)
  """
  import sys, io, json, argparse
  from datetime import date, datetime
  from pathlib import Path
  import anthropic
  
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  
  ROOT       = Path(__file__).parent.parent.parent
  STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
  OUT_DIR    = ROOT / 'out'
  
  def load_state() -> dict:
      return json.loads(STATE_PATH.read_text(encoding='utf-8'))
  
  def save_state(s: dict):
      STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
  
  VERDICT_BADGE = {
      'A': ('mint',  '#00e5c6', 'rgba(0,229,198,0.15)', '✓'),
      'B': ('red',   '#ff2244', 'rgba(255,34,68,0.15)',  '✗'),
      'AUTO': ('yellow', '#ffe500', 'rgba(255,229,0,0.15)', '⚠'),
  }
  
  def build_insight_text(state: dict, auto: bool) -> tuple[str, str, str, str]:
      """TODAY'S 인사이트 텍스트 + 배지 정보 반환"""
      if auto:
          issue = state['issues'][0] if state['issues'] else {}
          sector = issue.get('sector', '시장')
          headline = issue.get('headline', '오늘의 핵심 이슈')
          insight = f"{sector} 섹터 — {headline}에 주목해요. (자동 생성 초안)"
          verdict = 'AUTO'
          badge_label = '자동초안'
      else:
          idx = state['selected_index']
          issue = state['issues'][idx]
          sector = issue['sector']
          verdict = state['verdict']
          reason = state['reason']
          pivot = issue['pivot_a'] if verdict == 'A' else issue['pivot_b']
          insight = f"{sector} — {reason}." if reason else f"{sector} {pivot}으로 봐요."
          badge_label = pivot[:10]
  
      color_key, color_hex, bg, symbol = VERDICT_BADGE[verdict]
      return insight, badge_label, color_hex, bg, symbol
  
  def generate_sector_data(state: dict, auto: bool) -> str:
      """Haiku로 선택 섹터 핵심 데이터 3개 추출"""
      client = anthropic.Anthropic()
      idx = 0 if auto else (state['selected_index'] or 0)
      issue = state['issues'][idx] if state['issues'] else {}
      sector = issue.get('sector', '반도체')
  
      wiki_path = ROOT / 'wiki' / 'L5_섹터'
      sector_files = list(wiki_path.glob(f'*{sector}*/sector_*.md'))
      if not sector_files:
          sector_files = list(wiki_path.glob('*/sector_*.md'))
      if not sector_files:
          return ''
  
      content = sector_files[0].read_text(encoding='utf-8')[-3000:]
      resp = client.messages.create(
          model='claude-haiku-4-5-20251001',
          max_tokens=400,
          messages=[{'role': 'user', 'content': f"""아래 {sector} 섹터 위키에서
  오늘 가장 중요한 수치/팩트 3개를 JSON 배열로 추출하라.
  [{{"label":"브로드컴", "value":"-11.8%", "note":"AI 가이던스는 상향"}}]
  JSON만, 3개 정확히.
  
  {content}"""}]
      )
      text = resp.content[0].text.strip()
      if '```' in text:
          text = text.split('```')[1].lstrip('json').strip()
      try:
          return json.loads(text)
      except Exception:
          return []
  
  def render_html(state: dict, auto: bool) -> str:
      today = state['date'] or str(date.today())
      dt = datetime.strptime(today, '%Y-%m-%d')
      date_label = f"{dt.month}월 {dt.day}일 {'월화수목금토일'[dt.weekday()]}요일"
  
      insight, badge_label, color_hex, bg_color, symbol = build_insight_text(state, auto)
      sector_data = generate_sector_data(state, auto)
  
      idx = 0 if auto else (state['selected_index'] or 0)
      sector = state['issues'][idx]['sector'] if state['issues'] else '시장'
  
      data_items_html = ''
      for d in sector_data[:3]:
          data_items_html += f"""
          <div class="data-item">
            <span class="data-label">{d.get('label','')}</span>
            <span class="data-value" style="color:{color_hex}">{d.get('value','')}</span>
            <span class="data-note">{d.get('note','')}</span>
          </div>"""
  
      watermark = '<div class="watermark">⚠️ 자동생성 초안</div>' if auto else ''
  
      return f"""<!DOCTYPE html>
  <html lang="ko">
  <head>
  <meta charset="UTF-8">
  <style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#03030c; font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
         display:flex; justify-content:center; padding:24px; }}
  .card {{ width:800px; background:linear-gradient(160deg,#0d0d1c,#0a0a16,#080810);
           border-radius:16px; border:1px solid rgba(0,229,198,0.15);
           box-shadow:0 0 60px rgba(0,229,198,0.10),0 60px 120px rgba(0,0,0,0.8);
           overflow:hidden; position:relative; }}
  .card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px;
                   background:linear-gradient(90deg,transparent 5%,rgba(0,229,198,0.5) 35%,
                   #00e5c6 50%,rgba(0,229,198,0.5) 65%,transparent 95%); }}
  .hdr {{ display:flex; justify-content:space-between; align-items:center;
          padding:18px 24px; border-bottom:1px solid rgba(255,255,255,0.06); }}
  .brand {{ font-size:11px; font-weight:900; letter-spacing:5px; color:#00e5c6; }}
  .hdr-right {{ display:flex; align-items:center; gap:10px; }}
  .channel {{ font-size:11px; color:#8896aa; }}
  .date-badge {{ background:#00e5c6; color:#000; font-size:11px; font-weight:700;
                 padding:4px 10px; border-radius:20px; }}
  .body {{ padding:20px 24px; display:flex; flex-direction:column; gap:16px; }}
  .insight-block {{ background:rgba(0,229,198,0.05); border-left:3px solid #00e5c6;
                    border-radius:0 8px 8px 0; padding:14px 16px; }}
  .insight-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
  .insight-label {{ font-size:10px; font-weight:700; letter-spacing:3px; color:#00e5c6; }}
  .verdict-badge {{ font-size:11px; font-weight:700; padding:3px 10px; border-radius:12px;
                    color:{color_hex}; background:{bg_color}; border:1px solid {color_hex}40; }}
  .insight-text {{ font-size:13px; color:#ddeeff; line-height:1.75; }}
  .section-title {{ font-size:10px; font-weight:700; letter-spacing:3px; color:#8896aa; margin-bottom:10px; }}
  .data-grid {{ display:flex; flex-direction:column; gap:8px; }}
  .data-item {{ display:flex; align-items:center; gap:12px; padding:10px 14px;
                background:rgba(255,255,255,0.03); border-radius:8px; }}
  .data-label {{ font-size:12px; color:#c8d8ec; font-weight:600; min-width:80px; }}
  .data-value {{ font-size:15px; font-weight:900; }}
  .data-note {{ font-size:11px; color:#8896aa; flex:1; }}
  .watermark {{ position:absolute; top:12px; right:24px; font-size:11px; color:#ffe500;
                background:rgba(255,229,0,0.1); padding:3px 8px; border-radius:8px;
                border:1px solid rgba(255,229,0,0.3); }}
  .footer {{ padding:12px 24px; border-top:1px solid rgba(255,255,255,0.06);
             display:flex; justify-content:space-between; }}
  .ft {{ font-size:10px; color:#64748b; }}
  </style>
  </head>
  <body>
  <div class="card">
    {watermark}
    <div class="hdr">
      <div class="brand">STOCK BRAIN</div>
      <div class="hdr-right">
        <span class="channel">로또의 주식인사이트</span>
        <span class="date-badge">{date_label}</span>
      </div>
    </div>
    <div class="body">
      <div class="insight-block">
        <div class="insight-header">
          <span class="insight-label">⚡ TODAY'S 인사이트</span>
          <span class="verdict-badge">{symbol} {badge_label}</span>
        </div>
        <div class="insight-text">{insight}</div>
      </div>
      <div>
        <div class="section-title">📊 {sector} 핵심 데이터</div>
        <div class="data-grid">{data_items_html}</div>
      </div>
    </div>
    <div class="footer">
      <span class="ft">STOCK BRAIN · 로또의 주식인사이트</span>
      <span class="ft">아침 브리핑 · {today}</span>
    </div>
  </div>
  </body>
  </html>"""
  
  def main():
      parser = argparse.ArgumentParser()
      parser.add_argument('--auto', action='store_true')
      args = parser.parse_args()
  
      state = load_state()
      html = render_html(state, args.auto)
  
      fname = f"briefing_아침_{state['date'].replace('-','')}.html"
      out_path = OUT_DIR / fname
      out_path.write_text(html, encoding='utf-8')
      print(f'[card_gen] 카드 저장: {out_path}')
  
      state['card_html'] = str(out_path)
      state['stage'] = 'card_done'
      save_state(state)
  
      # 브라우저 자동 오픈
      import subprocess
      subprocess.Popen(['powershell', '-Command', f'Start-Process "{out_path}"'])
  
  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 2: 수동 테스트 (bot.py 없이)**

  `pipeline/briefing_state.json`을 아래처럼 수정 후 실행:
  ```json
  {
    "date": "2026-06-06",
    "issues": [{"sector":"반도체","headline":"브로드컴 쇼크 여파","pivot_a":"일시 조정","pivot_b":"추세 전환"}],
    "selected_index": 0,
    "verdict": "A",
    "reason": "AI 가이던스는 상향인데 네트워킹만 부진 부각된 것",
    "card_html": "", "card_png": "", "stage": "answered"
  }
  ```
  ```bash
  python scripts/briefing/card_gen.py
  ```
  - 브라우저에서 `out/briefing_아침_20260606.html` 자동 오픈 확인
  - TODAY'S 인사이트 블록에 운영자 판단 배지 + 말투 확인
  - `--auto` 플래그로도 실행해서 워터마크 확인:
    ```bash
    python scripts/briefing/card_gen.py --auto
    ```

- [ ] **Step 3: 커밋**

  ```bash
  git add scripts/briefing/card_gen.py
  git commit -m "feat: briefing/card_gen.py — 운영자 판단 담긴 HTML 카드 생성"
  ```

---

## Task 4: publish.py (PNG 캡처 + 텔레그램 채널 전송)

**Files:**
- Create: `scripts/briefing/publish.py`

> `.env`에 `BRIEFING_CHANNEL_ID` 설정 필요

- [ ] **Step 1: `publish.py` 작성**

  ```python
  """
  publish.py — HTML → PNG 캡처 + 텔레그램 채널 전송
  
  사용:
    python scripts/briefing/publish.py
  """
  import sys, io, json, asyncio, os
  from pathlib import Path
  from playwright.async_api import async_playwright
  from telegram import Bot
  
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
  
  ROOT        = Path(__file__).parent.parent.parent
  STATE_PATH  = ROOT / 'pipeline' / 'briefing_state.json'
  BOT_TOKEN   = os.environ['BRIEFING_BOT_TOKEN']
  OPERATOR_ID = int(os.environ['BRIEFING_OPERATOR_CHAT_ID'])
  CHANNEL_ID  = os.environ['BRIEFING_CHANNEL_ID']
  
  def load_state() -> dict:
      return json.loads(STATE_PATH.read_text(encoding='utf-8'))
  
  def save_state(s: dict):
      STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
  
  async def capture_png(html_path: str) -> str:
      """Playwright로 HTML → PNG 캡처, 카드 너비 800px 기준"""
      png_path = html_path.replace('.html', '.png')
      async with async_playwright() as p:
          browser = await p.chromium.launch()
          page = await browser.new_page(viewport={'width': 900, 'height': 1200})
          await page.goto(f'file:///{html_path}')
          await page.wait_for_timeout(500)
          card = page.locator('.card')
          await card.screenshot(path=png_path)
          await browser.close()
      print(f'[publish] PNG 캡처: {png_path}')
      return png_path
  
  async def send_to_channel(png_path: str, caption: str):
      bot = Bot(token=BOT_TOKEN)
      with open(png_path, 'rb') as f:
          await bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=caption)
      print(f'[publish] 채널 전송 완료: {CHANNEL_ID}')
  
  async def notify_operator(bot_token: str, operator_id: int, msg: str):
      bot = Bot(token=bot_token)
      await bot.send_message(chat_id=operator_id, text=msg)
  
  async def main():
      state = load_state()
      if state['stage'] != 'card_done':
          print(f'[publish] stage={state["stage"]}, card_done 아님 — 중단')
          return
  
      html_path = state['card_html']
      png_path = await capture_png(html_path)
  
      auto_flag = '⚠️ 자동생성 초안 ' if state['verdict'] == '' else ''
      caption = f"{auto_flag}📊 STOCK BRAIN 아침 브리핑 — {state['date']}\n@lotto_stockbrain"
  
      await send_to_channel(png_path, caption)
  
      state['card_png'] = png_path
      state['stage'] = 'published'
      save_state(state)
  
      await notify_operator(
          BOT_TOKEN, OPERATOR_ID,
          f'✅ 브리핑 카드 발행 완료!\n채널: {CHANNEL_ID}\n파일: {Path(png_path).name}'
      )
  
  if __name__ == '__main__':
      asyncio.run(main())
  ```

- [ ] **Step 2: PNG 캡처 단독 테스트**

  `state.json`의 `stage`가 `card_done`인 상태에서:
  ```bash
  python scripts/briefing/publish.py
  ```
  - `out/briefing_아침_20260606.png` 생성 확인
  - 파일 열어서 카드 레이아웃 800px 기준 깔끔한지 확인
  - 텔레그램 채널 전송 확인 (채널 ID 설정 후)

- [ ] **Step 3: 커밋**

  ```bash
  git add scripts/briefing/publish.py
  git commit -m "feat: briefing/publish.py — Playwright PNG 캡처 + 텔레그램 채널 전송"
  ```

---

## Task 5: Task Scheduler 등록 + 전체 연동 테스트

**Files:**
- Create: `scripts/briefing/run_briefing.bat` (Windows 스케줄러용)

- [ ] **Step 1: `run_briefing.bat` 작성**

  ```bat
  @echo off
  cd /d C:\Users\CH\Desktop\로또의 주식
  call C:\Users\CH\AppData\Local\Programs\Python\Python311\python.exe scripts/briefing/collect.py >> logs\briefing.log 2>&1
  timeout /t 30
  call C:\Users\CH\AppData\Local\Programs\Python\Python311\python.exe scripts/briefing/bot.py >> logs\briefing.log 2>&1
  call C:\Users\CH\AppData\Local\Programs\Python\Python311\python.exe scripts/briefing/publish.py >> logs\briefing.log 2>&1
  ```
  > Python 경로는 `where python` 결과로 교체

- [ ] **Step 2: logs 폴더 생성**

  ```bash
  mkdir logs
  echo. > logs/.gitkeep
  ```

- [ ] **Step 3: Task Scheduler 등록**

  PowerShell (관리자):
  ```powershell
  $action = New-ScheduledTaskAction -Execute "C:\Users\CH\Desktop\로또의 주식\scripts\briefing\run_briefing.bat"
  $trigger = New-ScheduledTaskTrigger -Daily -At "07:00AM"
  $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2)
  Register-ScheduledTask -TaskName "StockBrainBriefing" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest
  ```

- [ ] **Step 4: 전체 흐름 수동 연동 테스트**

  ```bash
  # 1. 이슈 추출
  python scripts/briefing/collect.py

  # 2. 봇 실행 (텔레그램에서 실제로 답변)
  python scripts/briefing/bot.py

  # 3. 카드 확인 후 발행
  python scripts/briefing/publish.py
  ```
  - `pipeline/briefing_state.json` stage가 `collected → q1_sent → q2_sent → answered → card_done → published` 순서로 변경되는지 확인
  - 텔레그램 채널에 PNG 카드 전송됐는지 확인
  - 운영자에게 완료 알림 오는지 확인

- [ ] **Step 5: 최종 커밋**

  ```bash
  git add scripts/briefing/run_briefing.bat logs/.gitkeep
  git commit -m "feat: briefing 전체 파이프라인 완성 — Task Scheduler 등록"
  ```

---

## Self-Review

**스펙 커버리지:**
- [x] 07:30 텔레그램 질문 → bot.py Task 2
- [x] 2단계 질문 흐름 → bot.py handle_message
- [x] 운영자 판단 + 근거 카드 반영 → card_gen.py render_html
- [x] PNG 자동 캡처 + 채널 전송 → publish.py Task 4
- [x] 08:00 타임아웃 자동 초안 → bot.py timeout_check + card_gen.py --auto
- [x] 자동초안 워터마크 → card_gen.py watermark
- [x] 운영자 완료 알림 → publish.py notify_operator
- [x] Task Scheduler 07:00 등록 → Task 5

**타입 일관성:**
- `state['issues']` 구조: collect.py에서 정의, bot.py/card_gen.py/publish.py 동일하게 참조 ✓
- `stage` 값: 모든 파일에서 동일 문자열 사용 ✓
- `BRIEFING_BOT_TOKEN` / `BRIEFING_OPERATOR_CHAT_ID` / `BRIEFING_CHANNEL_ID` — 3개 파일에서 동일 env 키 참조 ✓
