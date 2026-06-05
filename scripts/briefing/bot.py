"""
bot.py — 텔레그램 양방향 브리핑 봇

흐름:
  0. 이슈 확인 단계: 추출된 이슈 목록 전송 → 운영자 확인/수정 → ok
  1. 1단계 질문: 섹터 선택 (번호)
  2. 2단계 질문: A/B 판단 + 이유
  3. 카드 생성 트리거
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

def build_confirm_text(issues: list[dict]) -> str:
    """이슈 확인 메시지 — 설명 + A/B 판단 포인트 제시"""
    lines = ['📋 STOCK BRAIN 오늘 브리핑 준비됐어요!\n']

    lines.append('━━━ 오늘의 핵심 이슈 ━━━\n')
    for i, issue in enumerate(issues, 1):
        lines.append(f'【{i}】 {issue["sector"]}')
        lines.append(f'{issue["headline"]}')
        lines.append('')

    lines.append('━━━ 오늘 판단이 필요한 포인트 ━━━\n')
    for i, issue in enumerate(issues, 1):
        lines.append(f'Q{i}. {issue["sector"]} — 어떻게 보세요?')
        lines.append(f'  A. {issue["pivot_a"]}')
        lines.append(f'  B. {issue["pivot_b"]}')
        lines.append('')

    lines.append('─────────────────')
    lines.append('✅ 이대로 진행 → "ok"')
    lines.append('✏️ 이슈 추가/수정 → 텍스트로 말씀해주세요')
    return '\n'.join(lines)

def build_q1_text(issues: list[dict]) -> str:
    lines = ['📊 STOCK BRAIN 브리핑 질문 (1/2)\n',
             '오늘 어느 섹터에 집중할까요?\n']
    for i, issue in enumerate(issues, 1):
        lines.append(f'{i}. {issue["sector"]} — {issue["headline"]}')
    lines.append('\n번호로 답해주세요 (예: 1)')
    lines.append('⏰ 08:00까지 미답변 시 자동 초안 발행')
    return '\n'.join(lines)

def build_q2_text(issue: dict) -> str:
    return (
        f'📊 STOCK BRAIN 브리핑 질문 (2/2)\n\n'
        f'{issue["sector"]} 선택하셨군요.\n판단을 알려주세요:\n\n'
        f'A. {issue["pivot_a"]}\n'
        f'B. {issue["pivot_b"]}\n\n'
        f'판단 + 이유 한 줄만요.\n'
        f'예: "A. AI 가이던스 상향인데 네트워킹만 부진"'
    )

async def trigger_card_gen(auto: bool = False):
    import subprocess
    args = [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'card_gen.py')]
    if auto:
        args.append('--auto')
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
    print(result.stdout)
    if result.returncode != 0:
        print(f'[bot] card_gen 오류: {result.stderr}', file=sys.stderr)

async def apply_issue_edit(issues: list[dict], edit_text: str) -> list[dict]:
    """Gemini로 운영자 수정 요청 반영"""
    from google import genai
    from google.genai import types as gtypes
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    current = json.dumps(issues, ensure_ascii=False, indent=2)
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"""현재 이슈 목록:
{current}

운영자 수정 요청:
{edit_text}

위 수정 요청을 반영해서 이슈 목록을 업데이트하라.
동일한 JSON 배열 형식으로 반환하라. JSON만, 다른 텍스트 없이.""",
        config=gtypes.GenerateContentConfig(temperature=0)
    )
    text = resp.text.strip()
    if '```' in text:
        text = text.split('```')[1].lstrip('json').strip()
    return json.loads(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != OPERATOR_ID:
        return
    text = update.message.text.strip()
    state = load_state()
    stage = state['stage']

    # 0단계: 이슈 확인
    if stage == 'confirming':
        if text.lower() in ('ok', 'ㅇㅋ', '확인', '좋아', 'ㄱㄱ', 'go'):
            state['stage'] = 'q1_sent'
            save_state(state)
            await update.message.reply_text(build_q1_text(state['issues']))
            print('[bot] 이슈 확인 완료 → 1단계 질문 전송')
        else:
            # 수정 요청 처리
            await update.message.reply_text('✏️ 수정 중...')
            updated = await apply_issue_edit(state['issues'], text)
            state['issues'] = updated
            save_state(state)
            await update.message.reply_text(
                '수정됐어요! 다시 확인해주세요.\n\n' + build_confirm_text(updated)
            )

    # 1단계: 섹터 선택
    elif stage == 'q1_sent':
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

    # 2단계: 판단 + 이유
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
        # 이슈 확인 단계 먼저
        state = load_state()
        state['stage'] = 'confirming'
        save_state(state)
        await app.bot.send_message(chat_id=OPERATOR_ID, text=build_confirm_text(state['issues']))
        print('[bot] 이슈 확인 메시지 전송')
        asyncio.create_task(timeout_check(app.bot, app))
        await app.updater.start_polling()
        await app.updater.idle()
        await app.stop()

if __name__ == '__main__':
    asyncio.run(main())
