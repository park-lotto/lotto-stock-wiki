"""
publish.py — HTML → PNG 캡처 + 텔레그램 채널 전송

사용:
  python scripts/briefing/publish.py
"""
import sys, io, json, asyncio, os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from telegram import Bot

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT        = Path(__file__).parent.parent.parent
STATE_PATH  = ROOT / 'pipeline' / 'briefing_state.json'
load_dotenv(ROOT / '.env', encoding='utf-8')

BOT_TOKEN   = os.environ['BRIEFING_BOT_TOKEN']
OPERATOR_ID = int(os.environ['BRIEFING_OPERATOR_CHAT_ID'])
CHANNEL_ID  = os.environ['BRIEFING_CHANNEL_ID']

def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))

def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

async def capture_png(html_path: str) -> str:
    """Playwright로 .card 요소만 PNG 캡처"""
    png_path = html_path.replace('.html', '.png')
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 900, 'height': 1200})
        await page.goto(f'file:///{html_path}')
        await page.wait_for_timeout(800)
        card = page.locator('.card')
        await card.screenshot(path=png_path)
        await browser.close()
    print(f'[publish] PNG 캡처: {png_path}')
    return png_path

async def send_to_channel(png_path: str, date_str: str, auto: bool):
    bot = Bot(token=BOT_TOKEN)
    auto_flag = '⚠️ 자동생성 초안 ' if auto else ''
    caption = f"{auto_flag}📊 STOCK BRAIN 아침 브리핑 — {date_str}"
    with open(png_path, 'rb') as f:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=caption)
    print(f'[publish] 채널 전송 완료: {CHANNEL_ID}')

async def notify_operator(msg: str):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=OPERATOR_ID, text=msg)

async def main():
    state = load_state()
    if state['stage'] != 'card_done':
        print(f'[publish] stage={state["stage"]}, card_done 아님 — 중단')
        return

    html_path = state['card_html']
    if not html_path or not Path(html_path).exists():
        print(f'[publish] card_html 경로 없음: {html_path}')
        return

    png_path = await capture_png(html_path)
    auto = (state.get('verdict') == '')

    channel_ok = False
    try:
        await send_to_channel(png_path, state['date'], auto)
        channel_ok = True
    except Exception as e:
        err_msg = f'❌ 채널 전송 실패: {e}\n\n봇({BOT_TOKEN[:20]}...)이 @스탁브레인클로드 채널의 관리자인지 확인 필요.'
        print(f'[publish] 채널 전송 오류: {e}')
        await notify_operator(err_msg)

    state['card_png'] = png_path
    if channel_ok:
        state['stage'] = 'published'
    save_state(state)

    if channel_ok:
        await notify_operator(
            f'✅ 브리핑 카드 발행 완료!\n채널: {CHANNEL_ID}\n파일: {Path(png_path).name}'
        )

if __name__ == '__main__':
    asyncio.run(main())
