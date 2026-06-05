# ingest-pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3시간 주기 크롤링 → 텔레그램 타임스탬프 증분 인제스트 + 블로그 처리 후 삭제 자동화

**Architecture:** `prepare_ingest.py`가 crawling_bot_data에서 신규 데이터만 추출해 `raw/`로 준비. 텔레그램은 `**HH:MM**` 타임스탬프 기준 증분, 블로그는 `raw/blog/`로 이동 후 원본 삭제. `ingest_crawl.py`는 channel명 파싱 regex 수정 + blog 소스 모드 추가.

**Tech Stack:** Python 3.x, pathlib, re, json / 기존 `crawl_ingest_state.json` 활용

---

## 파일 구조

| 파일 | 작업 |
|------|------|
| `scripts/prepare_ingest.py` | 신규 생성 |
| `scripts/ingest_crawl.py` | 수정 (load_telegram channel 파싱 + blog 소스 추가) |
| `pipeline/crawl_ingest_state.json` | 수정 (`telegram_last_time` 키 추가) |
| `.agents/skills/ingest-pipeline/SKILL.md` | 신규 생성 |

---

## 핵심 데이터 구조

### State JSON 추가 구조
```json
{
  "telegram_last_time": {
    "2026-06-05": {
      "한화철강": "16:45",
      "하나차이나": "09:12"
    }
  }
}
```

### prepare_ingest.py 출력 파일명 규칙
- 텔레그램: `raw/telegram/{date}/{channel}_{HHMM}.md` (예: `한화철강_1645.md`)
- 블로그: `raw/blog/{date}/{원본파일명}.md` (그대로 이동)

---

## Task 1: State JSON — telegram_last_time 키 추가

**Files:**
- Modify: `pipeline/crawl_ingest_state.json`

- [ ] **Step 1: crawl_ingest_state.json에 telegram_last_time 키 추가**

현재 상태 파일에 `telegram_last_time` 최상위 키 추가:
```json
{
  "telegram_last_time": {},
  "pdf_summarized": [...],
  "ingested": [...],
  "ingested_tg": [...],
  "last_run": "2026-06-05"
}
```

---

## Task 2: `scripts/prepare_ingest.py` 생성

**Files:**
- Create: `scripts/prepare_ingest.py`

- [ ] **Step 1: 파일 생성 — 헤더, import, 상수**

```python
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

# 텔레그램 메시지 구분자: **HH:MM** 패턴
TIME_RE = re.compile(r'^\*\*(\d{2}:\d{2})\*\*\s*$')
```

- [ ] **Step 2: State 유틸리티 함수**

```python
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8-sig'))
    return {}

def save_state(state: dict):
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8'
    )
```

- [ ] **Step 3: 텔레그램 메시지 파싱 함수**

```python
def parse_telegram_messages(text: str) -> list[tuple[str, str]]:
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
```

- [ ] **Step 4: 텔레그램 증분 처리 함수**

```python
def process_telegram(date_str: str, dry_run: bool = False) -> int:
    crawl_dir = CRAWL_BASE / date_str / 'telegram'
    out_dir   = RAW_BASE / 'telegram' / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    state = load_state()
    last_times = state.setdefault('telegram_last_time', {}).setdefault(date_str, {})

    tg_files = sorted(crawl_dir.glob('*.md')) if crawl_dir.exists() else []
    if not tg_files:
        print(f'텔레그램 파일 없음: {crawl_dir}')
        return 0

    run_time = datetime.now().strftime('%H%M')
    total_new = 0

    for f in tg_files:
        # 채널명: 파일명에서 날짜 프리픽스 제거 (예: 2026-06-05_한화철강.md → 한화철강)
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

    print(f'\n텔레그램 완료: 총 {total_new}개 신규 메시지 추출')
    return total_new
```

- [ ] **Step 5: 블로그 이동 함수**

```python
def process_blog(date_str: str, dry_run: bool = False) -> int:
    crawl_dir = CRAWL_BASE / date_str / 'blog'
    out_dir   = RAW_BASE / 'blog' / date_str
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

    print(f'\n블로그 완료: {moved}개 이동 (원본 삭제됨)')
    return moved
```

- [ ] **Step 6: main() 함수**

```python
def main():
    p = argparse.ArgumentParser(description='crawling_bot_data → raw/ 증분 준비')
    p.add_argument('mode', choices=['telegram', 'blog', 'all'])
    p.add_argument('--date',    default=date.today().strftime('%Y-%m-%d'))
    p.add_argument('--dry-run', action='store_true', help='파일 수정 없이 미리보기')
    a = p.parse_args()

    print(f'=== prepare_ingest [{a.mode}] {a.date} ===')
    if a.mode in ('telegram', 'all'):
        process_telegram(a.date, a.dry_run)
    if a.mode in ('blog', 'all'):
        process_blog(a.date, a.dry_run)

if __name__ == '__main__':
    main()
```

- [ ] **Step 7: dry-run 테스트**

```powershell
cd "C:\Users\TheRose\Desktop\로또의 주식"
python scripts/prepare_ingest.py telegram --date 2026-06-05 --dry-run
python scripts/prepare_ingest.py blog --date 2026-06-05 --dry-run
```

예상 출력:
```
=== prepare_ingest [telegram] 2026-06-05 ===
  [한화철강] 5개 신규 (00:00 → 16:45) [DRY-RUN]
  [하나차이나] 3개 신규 (00:00 → 09:12) [DRY-RUN]
텔레그램 완료: 총 0개 신규 메시지 추출 (dry-run)
```

---

## Task 3: `ingest_crawl.py` — channel명 파싱 수정 + blog 소스 추가

**Files:**
- Modify: `scripts/ingest_crawl.py` (load_telegram 함수 ~line 276, process 함수 ~line 282)

- [ ] **Step 1: load_telegram channel 파싱 수정**

현재:
```python
channel = md_path.stem.replace('_요약', '')
```

변경 후 (날짜 프리픽스 + HHMM 서픽스 + _요약 제거):
```python
channel = md_path.stem
channel = re.sub(r'^\d{4}-\d{2}-\d{2}_', '', channel)  # 날짜 프리픽스 제거
channel = re.sub(r'_\d{4}$', '', channel)               # HHMM 서픽스 제거
channel = channel.replace('_요약', '')                   # _요약 제거
```

- [ ] **Step 2: load_blog 함수 추가 (load_telegram 아래)**

```python
def load_blog(md_path: Path) -> dict:
    text  = md_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    title  = next((l.lstrip('# ').strip() for l in lines if l.startswith('#')), md_path.stem)
    # 출처: **출처**: pokara61 블로그 패턴
    broker = next((l.split('**출처**:')[-1].strip() for l in lines if '**출처**:' in l), '블로그')
    # 전체 본문을 summary로 (이미 분석된 형태)
    return {'file': md_path.name, 'title': title, 'broker': broker, 'summary': text[:3000]}
```

- [ ] **Step 3: process() 함수 blog 소스 추가**

현재 `source` choices: `'report'`, `'telegram'`
아래 elif 블록 추가:

```python
elif source == 'blog':
    raw_dir   = ROOT / 'raw' / 'blog' / date_str
    state_key = 'ingested_blog'
    label     = f'raw/blog/{date_str}/'
    loader    = load_blog
```

그리고 `classify_telegram(reports)` 호출 부분을:
```python
# 기존
classified = classify_telegram(reports) if source == 'telegram' else classify_and_extract(reports)

# 변경: telegram만 telegram 프롬프트, 나머지는 report 프롬프트
classified = classify_telegram(reports) if source == 'telegram' else classify_and_extract(reports)
```
(blog는 report 프롬프트 재사용으로 변경 없음 — classify_and_extract가 자동으로 처리)

- [ ] **Step 4: argparse choices 업데이트**

```python
p.add_argument('--source', default='report', choices=['report', 'telegram', 'blog'])
```

- [ ] **Step 5: 테스트 (dry-run)**

```powershell
python scripts/ingest_crawl.py --source telegram --date 2026-06-05 --dry-run
```

---

## Task 4: SKILL.md 생성

**Files:**
- Create: `.agents/skills/ingest-pipeline/SKILL.md`

- [ ] **Step 1: SKILL.md 작성**

```markdown
---
name: ingest-pipeline
description: "크롤링 데이터 증분 인제스트 파이프라인. 트리거: '인제스트 해줘' / '텔레 인제스트' / '블로그 인제스트' / '오늘 크롤링 처리'"
metadata:
  tags: ingest, telegram, blog, pipeline, 증분
---

# ingest-pipeline

## 언제 실행하나

"텔레 인제스트해줘" / "블로그 처리해줘" / "크롤링 데이터 인제스트" / "오늘 데이터 처리"

---

## 텔레그램 파이프라인

```powershell
# Step 1: 신규 메시지 추출 (crawling_bot_data → raw/telegram/)
python scripts/prepare_ingest.py telegram --date 2026-06-05

# Step 2: wiki에 코멘트 누적
python scripts/ingest_crawl.py --source telegram --date 2026-06-05
```

**동작 원리:**
- `prepare_ingest.py`: 채널별 `**HH:MM**` 파싱 → 마지막 처리 시간 이후 메시지만 추출 → `raw/telegram/{date}/{channel}_{HHMM}.md`
- `ingest_crawl.py`: Gemini 분류 → sector/stock 코멘트를 wiki에 누적

**상태 추적:** `pipeline/crawl_ingest_state.json` → `telegram_last_time[date][channel]`

---

## 블로그 파이프라인

```powershell
# Step 1: 블로그 파일 이동 (crawling_bot_data → raw/blog/) + 원본 삭제
python scripts/prepare_ingest.py blog --date 2026-06-05

# Step 2: 블로그 파일 wiki에 인제스트
python scripts/ingest_crawl.py --source blog --date 2026-06-05
```

**동작 원리:**
- `prepare_ingest.py blog`: `crawling_bot_data/{date}/blog/` 파일 → `raw/blog/{date}/`로 이동 후 원본 삭제
- `ingest_crawl.py --source blog`: Gemini 분류 → 섹터/종목 코멘트 wiki 누적

---

## 전체 파이프라인 (한 번에)

```powershell
# 데이터 준비
python scripts/prepare_ingest.py all --date 2026-06-05

# wiki 인제스트
python scripts/ingest_crawl.py --source telegram --date 2026-06-05
python scripts/ingest_crawl.py --source blog --date 2026-06-05
```

---

## 일일 권장 실행 시점

| 시점 | 명령 |
|------|------|
| 장 시작 전 (08:30) | `prepare_ingest.py all` + `ingest_crawl.py telegram/blog` |
| 장 마감 후 (15:30) | `prepare_ingest.py all` + `ingest_crawl.py telegram/blog` |
| 리포트 처리 | `pdf_summarize.py` + `ingest_crawl.py` (기존 report-pipeline 스킬) |

---

## 미리보기 (dry-run)

```powershell
python scripts/prepare_ingest.py telegram --dry-run
python scripts/ingest_crawl.py --source telegram --dry-run
```
```

---

## Task 5: 실제 실행 테스트

- [ ] **Step 1: prepare_ingest.py 실행 (실제)**

```powershell
python scripts/prepare_ingest.py telegram --date 2026-06-05
```

성공 조건: `raw/telegram/2026-06-05/` 에 `{channel}_{HHMM}.md` 파일 생성됨

- [ ] **Step 2: ingest_crawl.py 실행**

```powershell
python scripts/ingest_crawl.py --source telegram --date 2026-06-05 --dry-run
```

성공 조건: channel명이 `한화철강`, `하나차이나` 등으로 올바르게 추출됨

- [ ] **Step 3: state.json 확인**

```powershell
python -c "import json; s=json.load(open('pipeline/crawl_ingest_state.json', encoding='utf-8')); print(json.dumps(s.get('telegram_last_time', {}), ensure_ascii=False, indent=2))"
```

성공 조건: 각 채널의 마지막 처리 시간이 기록됨

- [ ] **Step 4: git commit**

```bash
git add scripts/prepare_ingest.py scripts/ingest_crawl.py pipeline/crawl_ingest_state.json .agents/skills/ingest-pipeline/
git commit -m "feat: ingest-pipeline — 텔레그램 타임스탬프 증분 + 블로그 처리 후 삭제"
```
