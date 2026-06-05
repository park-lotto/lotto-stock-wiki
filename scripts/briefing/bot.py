"""
bot.py — 텔레그램 양방향 브리핑 봇

흐름:
  1. 스토리+수치 브리핑 전송 (A/B는 참고용)
  2. 운영자 자유 텍스트로 판단 작성
  3. Gemini가 인사이트로 변환 → 카드 생성
  4. 08:00 타임아웃 → 자동 초안

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

def build_briefing_text(issues: list[dict]) -> str:
    """스토리 + 수치 브리핑 메시지. A/B는 참고용으로만."""
    lines = ['📋 STOCK BRAIN 오늘 브리핑\n']
    for i, issue in enumerate(issues, 1):
        lines.append(f'【{issue["sector"]}】')
        lines.append(f'{issue["story"]}')
        if issue.get('numbers'):
            lines.append(f'📊 {issue["numbers"]}')
        lines.append(f'')
        lines.append(f'참고) A. {issue["pivot_a"]}')
        lines.append(f'      B. {issue["pivot_b"]}')
        lines.append('')
    lines.append('─────────────────')
    lines.append('💬 오늘 판단을 자유롭게 써주세요.')
    lines.append('어느 섹터든, 몇 줄이든 OK.')
    lines.append('⏰ 08:00까지 미답변 시 자동 초안 발행')
    return '\n'.join(lines)

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

    if state['stage'] != 'waiting_insight':
        return

    # 자유 텍스트 판단 수신
    state['reason'] = text
    state['verdict'] = 'FREE'  # 자유형 판단 표시
    state['stage'] = 'answered'
    save_state(state)
    await update.message.reply_text('✅ 받았어요! 카드 생성 시작할게요.')
    print(f'[bot] 판단 수신: {text[:50]}...')
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
                text='⏰ 08:00 지났어요. 자동 초안으로 발행할게요.'
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
        state = load_state()
        state['stage'] = 'waiting_insight'
        save_state(state)
        await app.bot.send_message(
            chat_id=OPERATOR_ID,
            text=build_briefing_text(state['issues'])
        )
        print('[bot] 브리핑 메시지 전송 완료')
        asyncio.create_task(timeout_check(app.bot, app))
        await app.updater.start_polling()
        await app.updater.idle()
        await app.stop()

if __name__ == '__main__':
    asyncio.run(main())
