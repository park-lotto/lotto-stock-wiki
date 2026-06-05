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
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent.parent
STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
load_dotenv(ROOT / '.env')

BOT_TOKEN    = os.environ['BRIEFING_BOT_TOKEN']
OPERATOR_ID  = int(os.environ['BRIEFING_OPERATOR_CHAT_ID'])
TIMEOUT_TIME = dtime(8, 0)  # 08:00

def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))

def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

def build_q1_text(issues: list[dict]) -> str:
    lines = ['📊 STOCK BRAIN 오늘의 브리핑 질문 (1/2)\n',
             '오늘 핵심 이슈 정리됐어요.\n어느 섹터에 집중할까요?\n']
    for i, issue in enumerate(issues, 1):
        lines.append(f'{i}. {issue["sector"]} — {issue["headline"]}')
    lines.append('\n번호로 답해주세요 (예: 1)')
    lines.append('⏰ 08:00까지 미답변 시 자동 초안 발행')
    return '\n'.join(lines)

def build_q2_text(issue: dict) -> str:
    return (
        f'📊 STOCK BRAIN 오늘의 브리핑 질문 (2/2)\n\n'
        f'{issue["sector"]} 선택하셨군요.\n판단을 알려주세요:\n\n'
        f'A. {issue["pivot_a"]}\n'
        f'B. {issue["pivot_b"]}\n\n'
        f'판단 + 이유 한 줄만요.\n'
        f'예: "A. 이유 한 줄"'
    )

async def send_q1(bot: Bot, state: dict):
    issues = state['issues']
    text = build_q1_text(issues)
    await bot.send_message(chat_id=OPERATOR_ID, text=text)
    state['stage'] = 'q1_sent'
    save_state(state)
    print('[bot] 1단계 질문 전송 완료')

async def trigger_card_gen(auto: bool = False):
    import subprocess
    args = [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'card_gen.py')]
    if auto:
        args.append('--auto')
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
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
        await update.message.reply_text(build_q2_text(issue))
        print(f'[bot] 2단계 질문 전송: {issue["sector"]}')

    elif stage == 'q2_sent':
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

async def timeout_check(bot: Bot, app):
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
    if state['stage'] != 'collected':
        print(f'[bot] 현재 stage={state["stage"]}, collected 아님 — 중단')
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async with app:
        await app.start()
        await send_q1(app.bot, state)
        asyncio.create_task(timeout_check(app.bot, app))
        await app.updater.start_polling()
        await app.updater.idle()
        await app.stop()

if __name__ == '__main__':
    asyncio.run(main())
