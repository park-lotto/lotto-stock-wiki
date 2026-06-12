"""
섹터 딥리서치 스크립트
- Gemini 2.5 Flash + Google Search 멀티스텝
- 타임라인·현재진단·앞으로 90일 일정 생성
- wiki/L5_섹터/{섹터}/sector_{섹터}.md 자동 업데이트
사용: python scripts/sector_research.py 2차전지ESS
"""
import sys, os, re, textwrap
from datetime import date
from pathlib import Path
from google import genai
from google.genai import types

ROOT = Path(__file__).parent.parent
ENV  = ROOT / '.env'

# .env 로드
env = {}
for line in ENV.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

API_KEY = env.get('GEMINI_API_KEY', '')
if not API_KEY:
    print('❌ GEMINI_API_KEY 없음'); sys.exit(1)

SECTOR = sys.argv[1] if len(sys.argv) > 1 else '2차전지ESS'
TODAY  = date.today().strftime('%Y-%m-%d')

client = genai.Client(api_key=API_KEY)

# ── 프롬프트 ────────────────────────────────────────────────────────────────
PROMPT = f"""
당신은 한국 주식시장 섹터 전문 리서처입니다.
오늘 날짜: {TODAY}
조사 섹터: {SECTOR}

Google 검색을 활용해서 아래 3개 파트를 완성하세요.
검색은 필요한 만큼 여러 번 하세요. 각 파트마다 최소 2~3회 검색 권장.

---

## [파트1] 최근 12개월 이벤트 타임라인
이 섹터 주가를 실제로 움직인 사건들을 시간순으로 찾아주세요.

조사할 카테고리:
- 미국: 연준 금리·IRA 정책·EV/ESS 수요 발표·빅테크 전력 투자
- 한국: 주요 종목 실적 서프라이즈·쇼크·대형 수주 계약·증권사 리포트 전환
- 글로벌: 리튬·니켈·코발트 가격 급변·중국 경쟁 이슈·공급망 충격

각 이벤트마다: 날짜 / 분류(미국·한국·글로벌) / 이벤트 내용 / 주가영향(🔴상승·⚫하락·🟡중립) / 지금도 영향 지속?(Y/N)

## [파트2] 현재 섹터 진단 (한 문장)
"지금 이 섹터는 [상황]이며, [핵심이유] 때문에 [방향성]을 보이고 있다."

## [파트3] 앞으로 90일 주요 일정
예정된 이벤트: 실적발표·FOMC·정책결정·전시회·수주기대
각 이벤트: 예상날짜 / 내용 / 기대방향(📈·📉·❓) / 수혜 연결 종목

---

## 출력 형식 (이것만 출력, 다른 설명 없이)

### 오늘의 한줄 ({TODAY} 업데이트)
> [파트2 한 문장]

### 🌏 지속 영향 이벤트
| 이벤트 | 시작 | 섹터 영향 | 방향 |
|--------|------|---------|------|
[지금도 유효한 이벤트만 — Y인 것들]

### 📅 이벤트 타임라인 (최근 12개월)
| 날짜 | 분류 | 이벤트 | 주가영향 | 지속? |
|------|------|--------|--------|-------|
[날짜 오래된 순서로]

### 📆 앞으로 90일 일정
| 예상날짜 | 이벤트 | 기대 | 연결 종목 |
|---------|--------|------|---------|

### 💡 콘텐츠 기회
- [유튜브 영상 주제 3개]
"""

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print(f'[{SECTOR}] 섹터 리서치 시작...')
print(f'   Gemini 2.5 Flash + Google Search')
print(f'   조사 기준: {TODAY}\n')

# ── Gemini 호출 (Google Search 그라운딩) ────────────────────────────────────
response = client.models.generate_content(
    model='gemini-3-flash-preview',
    contents=PROMPT,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )
)

result_text = response.text
print('✅ 리서치 완료\n')
print('─' * 60)
print(result_text[:500], '...')
print('─' * 60)

# ── wiki 파일 업데이트 ────────────────────────────────────────────────────
sector_dir  = ROOT / 'wiki' / 'L5_섹터' / SECTOR
sector_file = sector_dir / f'sector_{SECTOR}.md'

# 기존 파일 읽기 (없으면 신규)
if sector_file.exists():
    original = sector_file.read_text(encoding='utf-8')
else:
    original = f'# {SECTOR} 섹터 — 현재 상태\n\n'

# Gemini 결과에서 각 섹션 추출해서 기존 파일 해당 섹션 교체
def extract_section(text, header):
    """마크다운 텍스트에서 특정 헤더 섹션 추출"""
    pattern = rf'(###\s*{re.escape(header)}.*?)(?=\n###\s|\Z)'
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else None

def replace_section(original, header, new_content):
    """기존 파일에서 해당 섹션을 새 내용으로 교체 (없으면 추가)"""
    pattern = rf'(##\s*{re.escape(header)}[^\n]*\n)(.*?)(?=\n##\s|\Z)'
    replacement = f'## {header} ({TODAY} 업데이트)\n{new_content}\n\n'
    if re.search(pattern, original, re.DOTALL):
        return re.sub(pattern, replacement, original, flags=re.DOTALL)
    else:
        return original + '\n' + replacement

# 결과를 새 파일로 저장 (기존 구조 보존 + Gemini 결과 섹션 업데이트)
updated = original

# 오늘의 한줄 교체
headline_m = re.search(r'### 오늘의 한줄.*?\n(>.*?)(?=\n###|\Z)', result_text, re.DOTALL)
if headline_m:
    new_headline = headline_m.group(1).strip()
    updated = re.sub(
        r'## 오늘의 한줄.*?\n>.*?\n',
        f'## 오늘의 한줄 ({TODAY} 업데이트)\n{new_headline}\n',
        updated
    )

# 리서치 결과 전체를 별도 섹션으로 추가
research_block = f"""
---

## 🔬 섹터 딥리서치 ({TODAY})
> Gemini 2.5 Flash + Google Search 자동 생성

{result_text}

---
"""

# 기존 딥리서치 섹션 교체 or 추가
if '## 🔬 섹터 딥리서치' in updated:
    updated = re.sub(
        r'## 🔬 섹터 딥리서치.*?(?=\n## |\Z)',
        research_block.strip(),
        updated,
        flags=re.DOTALL
    )
else:
    # 이벤트 히스토리 앞에 삽입
    if '## 📰 이벤트 히스토리' in updated:
        updated = updated.replace(
            '## 📰 이벤트 히스토리',
            research_block + '\n## 📰 이벤트 히스토리'
        )
    else:
        updated += research_block

sector_file.write_text(updated, encoding='utf-8')
print(f'\n✅ 저장 완료: wiki/L5_섹터/{SECTOR}/sector_{SECTOR}.md')

# log.md 기록
log_file = ROOT / 'wiki' / 'log.md'
if log_file.exists():
    log = log_file.read_text(encoding='utf-8')
    log_entry = f'\n- {TODAY}: [{SECTOR}] 섹터 딥리서치 완료 (Gemini 2.5 Flash + Google Search)'
    log_file.write_text(log + log_entry, encoding='utf-8')

print(f'📝 log.md 기록 완료')
print(f'\n전체 결과: wiki/L5_섹터/{SECTOR}/sector_{SECTOR}.md 에서 확인')
