"""
assistant_bot.py — 텔레그램 Gemini 어시스턴트 봇

명령어:
  /s [검색어]     — 실시간 웹서치 후 결과 요약
  /ask [질문]     — Gemini 분석/질문 답변
  /brief          — 오늘 브리핑 카드 재생성 (보강 포함)
  /보강 [내용]    — 브리핑에 특정 데이터 추가 서치 후 재생성
  /wiki [질문]    — 로컬 wiki에서 검색 후 답변
  /help           — 명령어 목록

사용:
  python scripts/briefing/assistant_bot.py
"""
import sys, io, json, asyncio, os, re
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types as gtypes

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent.parent
STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
WIKI_L5    = ROOT / 'wiki' / 'L5_섹터'
load_dotenv(ROOT / '.env', encoding='utf-8')

BOT_TOKEN   = os.environ['BRIEFING_BOT_TOKEN']
OPERATOR_ID = int(os.environ['BRIEFING_OPERATOR_CHAT_ID'])
GEMINI_KEY  = os.environ['GEMINI_API_KEY']

client = genai.Client(api_key=GEMINI_KEY)

# ── 유틸 ──────────────────────────────────────────────────────────────────────

def only_operator(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != OPERATOR_ID:
            return
        await func(update, context)
    return wrapper

def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {}

def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

def chunk_text(text: str, size: int = 4000) -> list[str]:
    """텔레그램 메시지 4096자 제한 분할"""
    return [text[i:i+size] for i in range(0, len(text), size)]

async def send_long(update: Update, text: str):
    for chunk in chunk_text(text):
        await update.message.reply_text(chunk)

# ── Gemini 호출 ───────────────────────────────────────────────────────────────

def gemini_search(query: str) -> str:
    """웹서치 포함 Gemini 응답"""
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"""다음을 웹에서 검색하고 핵심만 한국어로 요약해줘. 수치·날짜 포함.
출처도 1~2개 간단히 표시해줘.

검색어: {query}""",
        config=gtypes.GenerateContentConfig(
            tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
            temperature=0.3
        )
    )
    return resp.text.strip()

def gemini_ask(question: str, context_text: str = '') -> str:
    """분석/질문 답변"""
    contents = question
    if context_text:
        contents = f"참고 데이터:\n{context_text}\n\n질문: {question}"
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=gtypes.GenerateContentConfig(temperature=0.5)
    )
    return resp.text.strip()

def gemini_search_and_enhance(briefing_text: str, request: str) -> str:
    """브리핑 보강 — 부족한 내용 서치 후 보완"""
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"""아래는 현재 아침 브리핑 내용이다.

{briefing_text}

운영자 요청: {request}

1. 위 요청에 맞게 웹서치로 최신 데이터를 찾아라.
2. 브리핑 내용을 보강해서 다시 작성해줘.
3. 구어체(~해요 말투), 핵심 수치 포함, 3~5줄 이내.
4. 마지막에 출처 1개만 표시.""",
        config=gtypes.GenerateContentConfig(
            tools=[gtypes.Tool(google_search=gtypes.GoogleSearch())],
            temperature=0.3
        )
    )
    return resp.text.strip()

def search_wiki(query: str) -> str:
    """로컬 wiki에서 키워드 검색"""
    results = []
    keywords = query.lower().split()
    for md_file in WIKI_L5.rglob('*.md'):
        try:
            content = md_file.read_text(encoding='utf-8')
            if all(kw in content.lower() for kw in keywords):
                # 매칭된 줄 주변 5줄 추출
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if any(kw in line.lower() for kw in keywords):
                        start = max(0, i - 2)
                        end = min(len(lines), i + 5)
                        snippet = '\n'.join(lines[start:end])
                        results.append(f"📄 {md_file.stem}\n{snippet}")
                        break
        except Exception:
            continue
    if not results:
        return '위키에서 관련 내용을 찾지 못했어요.'
    return '\n\n'.join(results[:5])

# ── 명령어 핸들러 ─────────────────────────────────────────────────────────────

@only_operator
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📋 STOCK BRAIN 어시스턴트 명령어

/s [검색어]
  실시간 웹서치 후 핵심 요약
  예) /s 브로드컴 오늘 주가

/ask [질문]
  Gemini 분석·질문 답변
  예) /ask 반도체 섹터 6월 전망은?

/brief
  오늘 브리핑 카드 다시 생성

/보강 [요청내용]
  브리핑에 추가 데이터 서치 후 보강
  예) /보강 미국장 마감 데이터 추가해줘

/wiki [검색어]
  로컬 wiki에서 검색
  예) /wiki 삼성중공업 CPSP

/help
  이 메시지"""
    await update.message.reply_text(text)

@only_operator
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text('검색어를 입력해주세요.\n예) /s 브로드컴 오늘 주가')
        return
    await update.message.reply_text(f'🔍 "{query}" 검색 중...')
    try:
        result = gemini_search(query)
        await send_long(update, f'🔍 {query}\n\n{result}')
    except Exception as e:
        await update.message.reply_text(f'검색 오류: {e}')

@only_operator
async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = ' '.join(context.args)
    if not question:
        await update.message.reply_text('질문을 입력해주세요.\n예) /ask 반도체 6월 전망은?')
        return
    await update.message.reply_text(f'💭 분석 중...')
    try:
        result = gemini_ask(question)
        await send_long(update, f'💭 {question}\n\n{result}')
    except Exception as e:
        await update.message.reply_text(f'오류: {e}')

@only_operator
async def cmd_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('📊 브리핑 카드 재생성 중...')
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'card_gen.py')],
            capture_output=True, text=True, encoding='utf-8'
        )
        if result.returncode == 0:
            # publish도 실행
            subprocess.run(
                [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'publish.py')],
                capture_output=True, text=True, encoding='utf-8'
            )
            await update.message.reply_text('✅ 브리핑 카드 재생성 + 채널 전송 완료!')
        else:
            await update.message.reply_text(f'오류: {result.stderr[:500]}')
    except Exception as e:
        await update.message.reply_text(f'오류: {e}')

@only_operator
async def cmd_enhance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = ' '.join(context.args)
    if not request:
        await update.message.reply_text('보강 내용을 입력해주세요.\n예) /보강 미국장 마감 데이터 추가해줘')
        return
    await update.message.reply_text(f'🔍 보강 데이터 서치 중...')
    try:
        state = load_state()
        issues = state.get('issues', [])
        briefing_text = '\n'.join([
            f'{i["sector"]}: {i.get("story", i.get("headline", ""))}'
            for i in issues
        ])
        enhanced = gemini_search_and_enhance(briefing_text, request)

        # state에 보강 내용 반영
        state['enhanced_insight'] = enhanced
        state['stage'] = 'answered'
        state['verdict'] = 'FREE'
        state['reason'] = enhanced
        save_state(state)

        await send_long(update, f'✏️ 보강된 내용:\n\n{enhanced}')
        await update.message.reply_text('카드 재생성할게요...')

        import subprocess
        subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'card_gen.py')],
            capture_output=True, text=True, encoding='utf-8'
        )
        subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'briefing' / 'publish.py')],
            capture_output=True, text=True, encoding='utf-8'
        )
        await update.message.reply_text('✅ 보강된 브리핑 카드 채널 전송 완료!')
    except Exception as e:
        await update.message.reply_text(f'오류: {e}')

@only_operator
async def cmd_wiki(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text('검색어를 입력해주세요.\n예) /wiki 삼성중공업')
        return
    await update.message.reply_text(f'📚 wiki 검색 중: {query}')
    try:
        result = search_wiki(query)
        # Gemini로 요약
        summary = gemini_ask(f'다음 wiki 내용을 3줄로 요약해줘:\n{result}')
        await send_long(update, f'📚 wiki: {query}\n\n{summary}')
    except Exception as e:
        await update.message.reply_text(f'오류: {e}')

@only_operator
async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """명령어 없이 일반 텍스트 → Gemini에게 그대로 전달"""
    text = update.message.text.strip()
    await update.message.reply_text('💭 Gemini에게 물어볼게요...')
    try:
        result = gemini_ask(text)
        await send_long(update, result)
    except Exception as e:
        await update.message.reply_text(f'오류: {e}')

# ── 메인 ──────────────────────────────────────────────────────────────────────

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CommandHandler('s', cmd_search))
    app.add_handler(CommandHandler('ask', cmd_ask))
    app.add_handler(CommandHandler('brief', cmd_brief))
    app.add_handler(CommandHandler('보강', cmd_enhance))
    app.add_handler(CommandHandler('wiki', cmd_wiki))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))

    print('[assistant_bot] 시작. 텔레그램 대기 중...')
    async with app:
        await app.start()
        await app.updater.start_polling()
        await app.updater.idle()
        await app.stop()

if __name__ == '__main__':
    asyncio.run(main())
