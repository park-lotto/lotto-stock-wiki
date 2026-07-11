"""
텔레그램 채널 크롤러 - config.yaml에 등록된 채널의 메시지를 수집한다.

Telethon 라이브러리로 실제 유저 계정을 통해 채널에 접근한다.
공개/비공개 채널 모두 수집 가능하다.
텍스트, 이미지, 링크 모두 수집한다.
이미지는 서버에 저장하고 MD 파일에 경로를 삽입한다.
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    ChannelPrivateError,
    ChannelInvalidError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
    ChatAdminRequiredError,
    UserNotParticipantError,
)

from config_loader import get_config, get_env
from logger import get_logger
from processors.md_writer import save_telegram, is_duplicate, mark_as_seen
from notifiers.telegram_sender import send_telegram_channel

logger = get_logger(__name__)


class ChannelAccessError(Exception):
    """봇 계정이 채널에 접근할 수 없을 때(강퇴·비공개 전환·초대링크 만료 등) 발생 — '새 메시지 없음'과 구분해야 함."""


async def _alert_admin(message: str) -> None:
    """크롤러 실패 시 관리자에게 즉시 알림 (Bot API — 죽은 유저봇 세션과 무관하게 항상 동작)."""
    try:
        from telegram import Bot
        token = get_env('TELEGRAM_BOT_TOKEN')
        admin_chat_id = get_env('ADMIN_CHAT_ID')
        if not token or not admin_chat_id:
            logger.warning('관리자 알림 스킵: TELEGRAM_BOT_TOKEN/ADMIN_CHAT_ID 없음')
            return
        bot = Bot(token=token)
        await bot.send_message(chat_id=admin_chat_id, text=message)
    except Exception as alert_err:
        logger.warning(f'관리자 알림 발송 실패: {alert_err}')


SESSION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.telegram_session')

# hang 방지 타임아웃(초)
PER_CHANNEL_TIMEOUT = 90   # 채널당 최대 수집 — 초과 시 건너뜀 (메시지 많은 뉴스릴레이 채널 대응 90s로 상향, 2026-07-03)
CONNECT_TIMEOUT = 30       # client.start() 연결
JOB_TIMEOUT = 900          # 전체 수집 하드캡(안전장치)


def _get_client() -> TelegramClient:
    api_id = get_env('TELEGRAM_API_ID')
    api_hash = get_env('TELEGRAM_API_HASH')

    if not api_id or not api_hash:
        raise ValueError('.env 파일에 TELEGRAM_API_ID와 TELEGRAM_API_HASH가 없습니다.')

    return TelegramClient(SESSION_PATH, int(api_id), api_hash)


async def _collect_channel(client: TelegramClient, channel_cfg: dict) -> list[dict]:
    """
    채널에서 최근 24시간 메시지를 수집한다.
    텍스트, 이미지 모두 수집한다.
    이미지는 output/md/telegram/images/ 폴더에 저장한다.
    """
    channel_url = channel_cfg.get('url', '')
    collect_all = channel_cfg.get('collect_all', True)
    keywords = channel_cfg.get('keywords', [])

    # 이미지 저장 폴더
    cfg = get_config()
    from config_loader import get_dated_dir
    img_dir = os.path.join(get_dated_dir('telegram'), 'images')
    os.makedirs(img_dir, exist_ok=True)

    messages = []
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    try:
        entity = await client.get_entity(channel_url)
    except (ChannelPrivateError, ChannelInvalidError, UsernameInvalidError,
            UsernameNotOccupiedError, ChatAdminRequiredError, UserNotParticipantError) as e:
        raise ChannelAccessError(f"{channel_url}: {e}") from e

    try:
        async for msg in client.iter_messages(entity, limit=200):
            if msg.date < since:
                break

            # 중복 체크 - 이미 수집한 메시지는 건너뜀
            msg_key = f"tg_{msg.chat_id}_{msg.id}"
            if is_duplicate(msg_key):
                continue

            text = msg.text or ''
            image_path = None

            # 이미지 다운로드
            if msg.photo:
                kst_time = msg.date.astimezone()
                img_filename = f"{kst_time.strftime('%Y%m%d_%H%M%S')}_{msg.id}.jpg"
                img_full_path = os.path.join(img_dir, img_filename)
                try:
                    await client.download_media(msg, file=img_full_path)
                    image_path = f"images/{img_filename}"
                    logger.debug(f"이미지 저장: {img_filename}")
                except Exception as e:
                    logger.warning(f"이미지 다운로드 실패: {e}")

            # 텍스트도 없고 이미지도 없으면 건너뜀
            if not text.strip() and not image_path:
                continue

            # 키워드 필터링 (텍스트가 있을 때만)
            if not collect_all and keywords and text:
                matched = any(kw.lower() in text.lower() for kw in keywords)
                if not matched and not image_path:
                    continue

            messages.append({
                'time': msg.date.astimezone().strftime('%H:%M'),
                'text': text.strip(),
                'image': image_path
            })
            mark_as_seen(msg_key)

        messages.reverse()
        return messages

    except Exception as e:
        logger.error(f"채널 수집 실패 ({channel_url}): {e}")
        return []


async def _run_async() -> int:
    cfg = get_config()
    tg_cfg = cfg.get('telegram', {})

    if not tg_cfg.get('enabled', False):
        logger.info("텔레그램 수집 비활성화 상태")
        return 0

    channels = [c for c in tg_cfg.get('channels', []) if c.get('enabled', True)]

    if not channels:
        logger.warning("수집할 텔레그램 채널이 없습니다.")
        return 0

    total_saved = 0
    client = _get_client()

    try:
        await asyncio.wait_for(client.start(), timeout=CONNECT_TIMEOUT)

        for ch in channels:
            ch_name = ch.get('name', '알 수 없음')
            logger.info(f"텔레그램 수집 중: {ch_name}")

            try:
                messages = await asyncio.wait_for(
                    _collect_channel(client, ch), timeout=PER_CHANNEL_TIMEOUT)
            except asyncio.TimeoutError:
                logger.error(f"  {ch_name}: 타임아웃 {PER_CHANNEL_TIMEOUT}s 초과 — 건너뜀")
                continue
            except ChannelAccessError as e:
                logger.error(f"  {ch_name}: 채널 접근 불가 (강퇴/비공개 전환/초대링크 만료 가능성) — {e}")
                await _alert_admin(
                    f"⚠️ 텔레그램 크롤러: [{ch_name}] 채널 접근 불가 — 강퇴/비공개 전환/초대링크 만료 가능성.\n오류: {e}\n조치: 채널 상태 확인 후 config.yaml의 채널 정보 갱신 필요."
                )
                continue

            if not messages:
                logger.info(f"  {ch_name}: 새 메시지 없음 (최근 24시간)")
                continue

            saved = save_telegram(
                channel_name=ch_name,
                messages=messages
            )

            if saved:
                total_saved += 1
                img_count = sum(1 for m in messages if m.get('image'))
                logger.info(f"  {ch_name}: {len(messages)}개 메시지 저장 (이미지 {img_count}개)")
                try:
                    body = f"{ch_name} 채널에 새 글 {len(messages)}건이 수집되었습니다. (옵시디언에서 확인)"
                    send_telegram_channel(title=f"[{ch_name}]", body=body)
                except Exception as e:
                    logger.warning(f"텔레그램 채널 발송 실패: {e}")

    except SessionPasswordNeededError:
        logger.error("2단계 인증 계정입니다.")
        await _alert_admin(
            "⚠️ 텔레그램 크롤러: 2단계 인증(비밀번호) 필요 — 자동 로그인 불가.\n서버 SSH 접속 후 python3 tg_login.py 재실행 필요."
        )
    except Exception as e:
        logger.error(f"텔레그램 수집 오류: {e}")
        await _alert_admin(
            f"⚠️ 텔레그램 크롤러 수집 실패 (세션 만료 가능성)\n오류: {e}\n조치: 서버 SSH 접속 후 python3 tg_login.py 재실행 필요."
        )
    finally:
        await client.disconnect()

    return total_saved


def run() -> int:
    async def _guarded():
        try:
            return await asyncio.wait_for(_run_async(), timeout=JOB_TIMEOUT)
        except asyncio.TimeoutError:
            logger.error(f"텔레그램 수집 전체 타임아웃 {JOB_TIMEOUT}s — 강제종료")
            return 0
    return asyncio.run(_guarded())


def auth() -> None:
    async def _auth():
        client = _get_client()
        await client.start()
        me = await client.get_me()
        logger.info(f"인증 완료: {me.first_name} (@{me.username})")
        await client.disconnect()

    asyncio.run(_auth())
