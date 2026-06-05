"""
prepare_ingest.py — crawling_bot_data → raw/ 증분 준비

텔레그램: **HH:MM** 타임스탬프 기준 → 마지막 처리 시간 이후 메시지만 추출
          → raw/telegram/{date}/{channel}_{HHMM}.md 저장 + state 업데이트
블로그: crawling_bot_data/{date}/blog/*.md → raw/blog/{date}/ 이동 + 원본 삭제

사용:
  python scripts/prepare_ingest.py telegram [--date 2026-06-05]
  python scripts/prepare_ingest.py blog     [--date 2026-06-05]
  python scripts/prepare_ingest.py all      [--date 2026-06-05]
  python scripts/prepare_ingest.py telegram --dry-run
"""
import sys, io, re, json, shutil, argparse
from datetime import date, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent
STATE_PATH = ROOT / 'pipeline' / 'crawl_ingest_state.json'
CRAWL_BASE = Path(r'C:\Users\TheRose\crawling_bot_data')
RAW_BASE   = ROOT / 'raw'

# 텔레그램 메시지 타임스탬프: **HH:MM** 패턴 (단독 줄)
TIME_RE = re.compile(r'^\*\*(\d{2}:\d{2})\*\*\s*$')


# ── state 유틸 ────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8-sig'))
    return {}

def save_state(state: dict):
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ── 텔레그램 파싱 ─────────────────────────────────────────────────────────────

def parse_telegram_messages(text: str) -> list:
    """
    텔레그램 md 파일에서 (time_str, content) 튜플 리스트 반환.
    시간 없는 첫 블록은 건너뜀.
    """
    messages = []
    current_time = None
    current_lines = []

    for line in text.splitlines():
        m = TIME_RE.match(line)
        if m:
            if current_time and current_lines:
                messages.append((current_time, '\n'.join(current_lines).strip()))
            current_time = m.group(1)
            current_lines = []
        elif current_time is not None:
            current_lines.append(line)

    if current_time and current_lines:
        messages.append((current_time, '\n'.join(current_lines).strip()))

    return messages


# ── 텔레그램 증분 처리 ────────────────────────────────────────────────────────

def process_telegram(date_str: str, dry_run: bool = False) -> int:
    crawl_dir = CRAWL_BASE / date_str / 'telegram'
    out_dir   = RAW_BASE / 'telegram' / date_str
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    state      = load_state()
    last_times = state.setdefault('telegram_last_time', {}).setdefault(date_str, {})

    tg_files = sorted(crawl_dir.glob('*.md')) if crawl_dir.exists() else []
    if not tg_files:
        print(f'텔레그램 파일 없음: {crawl_dir}')
        return 0

    run_time   = datetime.now().strftime('%H%M')
    total_new  = 0

    for f in tg_files:
        # 채널명: 날짜 프리픽스 제거 (예: 2026-06-05_한화철강.md → 한화철강)
        channel = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', f.stem)
        last_t  = last_times.get(channel, '00:00')

        text     = f.read_text(encoding='utf-8')
        messages = parse_telegram_messages(text)

        new_msgs = [(t, c) for t, c in messages if t > last_t]
        if not new_msgs:
            print(f'  [{channel}] 신규 없음 (마지막: {last_t})')
            continue

        max_time = max(t for t, _ in new_msgs)
        content  = f'# 텔레그램 - {channel} - {date_str} ({last_t}~{max_time})\n\n'
        for t, c in new_msgs:
            content += f'\n\n**{t}**\n\n{c}\n\n---'

        out_path = out_dir / f'{channel}_{run_time}.md'
        print(f'  [{channel}] {len(new_msgs)}개 신규 ({last_t} → {max_time})'
              + (' [DRY-RUN]' if dry_run else f' → {out_path.name}'))

        if not dry_run:
            out_path.write_text(content, encoding='utf-8')
            last_times[channel] = max_time
            total_new += len(new_msgs)

    if not dry_run:
        save_state(state)

    label = f'총 {total_new}개 신규 메시지 추출' if not dry_run else '(dry-run, 파일 수정 없음)'
    print(f'\n텔레그램 완료: {label}')
    return total_new


# ── 블로그 이동 ───────────────────────────────────────────────────────────────

def process_blog(date_str: str, dry_run: bool = False) -> int:
    crawl_dir = CRAWL_BASE / date_str / 'blog'
    out_dir   = RAW_BASE / 'blog' / date_str
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    blog_files = sorted(crawl_dir.glob('*.md')) if crawl_dir.exists() else []
    if not blog_files:
        print(f'블로그 파일 없음: {crawl_dir}')
        return 0

    moved = 0
    for f in blog_files:
        dest = out_dir / f.name
        print(f'  {f.name}' + (' [DRY-RUN]' if dry_run else f' → raw/blog/{date_str}/'))
        if not dry_run:
            shutil.move(str(f), str(dest))
            moved += 1

    label = f'{moved}개 이동 (원본 삭제됨)' if not dry_run else f'{len(blog_files)}개 대상 (dry-run, 이동 없음)'
    print(f'\n블로그 완료: {label}')
    return moved


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='crawling_bot_data → raw/ 증분 준비')
    p.add_argument('mode', choices=['telegram', 'blog', 'all'],
                   help='처리할 소스 타입')
    p.add_argument('--date',    default=date.today().strftime('%Y-%m-%d'),
                   help='처리 날짜 (기본: 오늘)')
    p.add_argument('--dry-run', action='store_true',
                   help='파일 수정 없이 미리보기')
    a = p.parse_args()

    print(f'=== prepare_ingest [{a.mode}] {a.date}'
          + (' DRY-RUN' if a.dry_run else '') + ' ===\n')

    if a.mode in ('telegram', 'all'):
        process_telegram(a.date, a.dry_run)
    if a.mode in ('blog', 'all'):
        if a.mode == 'all':
            print()
        process_blog(a.date, a.dry_run)


if __name__ == '__main__':
    main()
