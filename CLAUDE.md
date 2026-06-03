# 로또의 주식 — 나만의 지식 위키

---

## 🚀 세션 시작 시 필수 읽기 (AI가 매번 자동 실행)

새 세션이 시작되면 아래 파일을 **순서대로** 반드시 읽어라.

```
1. wiki/BRAIN_INDEX.md                        → 6레이어 분석 프레임워크
2. channel/yt/yt_전략_채널방향.md              → 채널/서비스 전략 (STOCK BRAIN)
3. channel/strategy/strategy_remotion_가이드.md → 영상 작성 핵심 가이드
4. wiki/log.md                                → 최근 작업 이력
5. wiki/rules/analysis_rules.md               → 분석 행동 규칙 (TYPE/Gemini/매크로/위키먼저)
```

### ⚡ Superpowers 자동 트리거 (사용자 요청 없이도 즉시 실행)

아래 조건 감지 시 **즉시** 해당 스킬을 호출한다. 설명 없이 바로 실행.

| 트리거 조건 | 실행 스킬 |
|------------|---------|
| "만들자" / "설계하자" / "기획하자" / 새 시스템·기능 논의 시작 | `superpowers:brainstorming` |
| brainstorming 완료 후 구현 단계 진입 | `superpowers:writing-plans` |
| writing-plans 완료 후 코드 작성 시작 | `superpowers:executing-plans` |
| 에러·버그·오작동 발생 | `superpowers:systematic-debugging` |
| "다 됐어" / "완료" / 커밋 전 마지막 확인 | `superpowers:verification-before-completion` |
| 씬 여러 개 동시 제작 / 파이프라인 병렬 처리 | `superpowers:dispatching-parallel-agents` |
| 커스텀 슬래시 명령어 새로 만들 때 | `superpowers:writing-skills` |
| 영상 제작 파이프라인 디버깅 | `superpowers:systematic-debugging` |

> **원칙**: 트리거 조건과 1%라도 겹치면 무조건 실행. "이건 간단해서 괜찮겠지" 금지.

---

## 🎯 스킬 활용 원칙 (모든 업무에 적용)

**모든 업무 시작 전, 사용 가능한 스킬 목록을 확인하고 가장 적합한 스킬을 선택해 실행한다.**

### 핵심 규칙

1. **스킬 먼저 확인** — 작업 시작 전 Skill 목록 스캔. 맞는 게 있으면 즉시 호출.
2. **2개 이상 조합 적극 권장** — 최고의 결과물을 위해 스킬을 체이닝한다.
3. **스킬 없이 혼자 하는 건 차선** — 스킬이 있는데 쓰지 않는 것은 품질 저하.

### 📺 유튜브 영상 콘텐츠 70/20/10 원칙 (모든 영상 씬 작성 시 필수)

> 상세 기준: `channel/yt/yt_전략_채널방향.md` § 콘텐츠 비율 원칙

| 비율 | 유형 | 핵심 |
|------|------|------|
| **70%** | 순수 정보 | 내 시스템·서비스·프로그램 **일절 언급 금지** |
| **20%** | 간접 노출 | "나는 이렇게 한다" 방법론만 — 광고 느낌 금지 |
| **10%** | 직접 CTA | S8(마지막 씬)에서만 **딱 한 번** |

**영상 대본 쓸 때 자가 점검**: "이 씬에서 내 프로그램이 언급되는가?" → YES & 70% 구간 → 즉시 삭제.

### Superpowers × Gstack 역할 분담

| 단계 | Superpowers (사고/프로세스) | Gstack (도구/실행) |
|------|--------------------------|-----------------|
| 설계 | `brainstorming` | `office-hours` (아이디어 검증) |
| 계획 | `writing-plans` | — |
| 구현 | `executing-plans` | — |
| 확인 | `verification-before-completion` | `qa` (브라우저 실제 확인) |
| 검수 | — | `design-review` · `review` |
| 배포 | `finishing-a-development-branch` | `ship` |
| 디버그 | `systematic-debugging` | `investigate` |
| 병렬 | `dispatching-parallel-agents` | — |

### 업무별 추천 스킬 조합

| 업무 | 조합 |
|------|------|
| 새 기능 설계+구현 | `brainstorming` → `writing-plans` → `executing-plans` → `qa` |
| 영상 제작 | `brainstorming` → `executing-plans` → `videoagent-*` → `qa` |
| 오류 수정 | `systematic-debugging` → `investigate` → `verification-before-completion` |
| HTML 결과물 | `executing-plans` → `qa` → `design-review` |
| 커밋/배포 | `verification-before-completion` → `review` → `ship` |

> **목표**: 스킬 조합으로 혼자 작업할 때보다 항상 더 높은 품질의 결과물을 낸다.

---

읽기 완료 후 요약:
```
📋 세션 시작 요약
- 6레이어 구조 파악
- 채널 전략 파악
- 최근 작업: {log.md 최근 내용}
- 미결 작업: {있으면 표시, 없으면 "없음"}
```

### ⚡ 대기 중인 검증/보고가 있으면 첫 메시지에서 즉시 보고

log.md에 아래 항목이 있으면 **요약 전에 먼저 보고**:

| 키워드 | 보고 내용 |
|--------|---------|
| `투경 해제 예측 검증` | 정확도 X/7, 일치 종목, 틀린 종목, 다음 단계 |
| `종가배팅 시스템` | 구현 진행 상태 |

> **보고 형식**: 한 눈에 파악할 수 있게 표로. 길게 설명하지 말고 숫자와 결론만.

> **규칙 파일 위치** (필요 시 읽기):
> - `wiki/rules/analysis_rules.md` → 분석 행동 규칙 (TYPE/Gemini Q10/매크로/위키먼저/검증)
> - `wiki/rules/ingest_rules.md` → ingest 상세 규칙 (수급/유동성/수출/일정/외부인사이트)
> - `wiki/rules/page_templates.md` → 페이지 템플릿 (stock/sector/스토리보드 구조)

---

## 운영자 프로필
- **역할**: 휴대폰 수출 사업자 + 주식 트레이더, 주식 유튜브 채널 운영자
- **채널명**: 로또의 주식인사이트
- **미션**: 정보의 홍수에서 인사이트만 복리로 쌓는다. AI를 제2의 두뇌(Stock Brain)로 삼아 데이터가 판단하게 만든다.
- **핵심 콘텐츠 방향**: 수급빈집추적, 대장주 포착, 단기 스윙 매매법

---

## 위키 구조

```
로또의 주식/
├── CLAUDE.md              ← 이 파일 (핵심 운영 규칙)
├── wiki/rules/            ← 상세 규칙 파일
│   ├── analysis_rules.md  ← 분석 행동 규칙
│   ├── ingest_rules.md    ← ingest 상세 규칙
│   └── page_templates.md  ← 페이지 템플릿
├── raw/                   ← 크롤링 원본 (Claude는 읽기만)
│   ├── L1_글로벌유동성/ / L2_미국시장/ / L3_한국시장/ / L4_국제정세/
│   ├── L5_섹터/ / L6_수급/
│   └── market/ news/ telegram/ report/ supply/ consensus/ export/ blog/ yt/
├── wiki/                  ← 주식 분석 지식 (Claude가 작성/관리)
│   ├── BRAIN_INDEX.md / index.md / log.md
│   ├── L1~L6 레이어 폴더
│   ├── L5_섹터/           ← sector/, stock/ 참조
│   └── 외부인사이트/
├── channel/               ← 채널/서비스 전략
└── out/                   ← 생성된 결과물 (HTML·MP4·스크립트)
```

**구조 원칙**:
- `raw/` : 크롤러가 저장. Claude는 읽기만.
- `wiki/` : MD 파일만. index.md·log.md는 루트에 유지.
- `out/` : 생성 결과물 전용.

---

## 스토리보드 시스템

> **스토리보드는 바뀌지 않는다. 데이터 레이어만 매일 바뀐다.**

- 파일: `wiki/L5_섹터/{섹터}/스토리보드_{섹터명}.md`
- 구조: Act1(배경) / Act2(현재 챕터) / Act3(미래 씬) / 챕터 온도계
- 수정 트리거: 새 챕터 열림 / 챕터 소멸 / D-Day 발생 / 컨센 ±30%↑

**3종 일일 결과물**:
| 결과물 | 파일명 | 배포 |
|-------|--------|------|
| 브리핑 | `out/sector_briefing_{섹터}.html` | 텔레그램·카카오·인스타 |
| 리포트 | `out/report_{섹터}_YYYYMMDD.html` | 유튜브 커뮤니티·블로그 |
| 대시보드 | `out/sector_dashboard_{섹터}.html` | 내부 참조 |

**섹터별 스토리보드 현황**:
| 섹터 | 상태 |
|------|------|
| 반도체 | ✅ V1 완성 (2026-05-28) |
| 조선·전력기기·방산·2차전지 | 🔲 미착수 |

> 상세 템플릿: `wiki/rules/page_templates.md`

---

## raw → wiki 매핑 규칙

| raw/ 입력 | stock/ 섹션 | sector/ 섹션 | 처리 방식 |
|-----------|-----------|------------|---------|
| `report/` | 증권사 컨센서스 덮어쓰기 | 대장주 현황 TP 갱신 | 증권사당 1행. 3개월 초과 삭제. |
| `news/` `telegram/` `blog/` | 최신 이벤트 추가 (7일 롤링) | 이벤트 히스토리 1줄 | 8일 이상 경과 행 삭제. |
| `export/` | 수출 데이터 행 추가 | 수출 신호 표 갱신 | YoY/판가/절대값 + 신호 |
| `supply/` | 수급 흐름 업데이트 | 섹터 온도 갱신 | 외국인·기관 순매수 방향 |
| `market/` | 수급 흐름 | 섹터 온도 | 지수·ETF 흐름 |
| `yt/` | (없음) | 콘텐츠 기회 | yt/ 페이지 별도 생성 |

### report/ 5종 세부 라우팅
| 리포트 유형 | 반영 위치 |
|-----------|---------|
| 종목보고서/ | stock/ 증권사 컨센서스 + 최신 이벤트 (증권사당 1행 덮어쓰기) |
| 산업보고서/ | 섹터 index.md 이벤트 히스토리 + 관련 stock/ |
| 경제분석보고서/ | 환율·금리→L1 / 지정학→L4 |
| 시황보고서/ | L3_한국시장/index.md 주간 이벤트 로그 |
| 투자정보보고서/ | 섹터 콘텐츠 기회 + stock/ 최신 이벤트 |

**공통 원칙**: 날짜 반드시 명시 / 기존 행 덮어쓰기 금지 / 소스 파일명 출처 기재 / 충돌 → ⚠️ 섹션 추가

---

## 파일 네이밍 규칙

### raw/ 파일명
```
{날짜}_{유형코드}_{간단설명}.{확장자}
예) 20260521_market_daily.md / 20260521_supply_수급오실레이터.xlsm
```

### 종목 마스터 페이지 경로
```
wiki/L5_섹터/{섹터명}/stock/stock_{종목명}.md
예) wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md
```
- 종목당 1개 마스터 페이지. 새 데이터 ingest 시 기존 파일에 누적.

### 섹터 파일명
```
sector_{섹터명}.md  (예: sector_조선.md)
```

> **페이지 구조 상세**: `wiki/rules/page_templates.md`

---

## 아침 전략노트 생성 규칙

**명령어**: `소재 찾자` / `/소재찾기`

### 5단계 소재 탐색 루틴
```
□ 1. 핫 키워드 서칭    → WebSearch "주식시장 핫이슈 오늘" 로 지금 뭐가 뜨는지
□ 2. 유튜브 조회수 분석 → Playwright로 관련 키워드 유튜브 검색, 최신순 조회수 확인
                          (절대 조회수 + 올라온 시점 함께 체크)
□ 3. 키워드 추출        → 핵심/롱테일/훅 키워드 3종 정리
□ 4. 리서치 + 주제 선정 → wiki + WebSearch로 깊게 파고
                          "터지는 조회수" × "내가 실제로 아는 것" 교집합 선정
□ 5. 대본 초안          → 선정된 각도로 씬 구성 시작
```

**타이밍 원칙**: 이벤트 터진 날 = 업로드 해야 하는 날. 소재는 D-3 이상 미리 파악.

---

## 영상 제작 프로세스 (이미지 포함)

**명령어**: `영상 만들자` / `/make-video`

### 단계
```
□ 1. 대본 작성
      → 씬별 대사 + 시간(초) 명시

□ 2. 씬별 이미지 프롬프트 작성 (한글)
      규칙:
      - 반드시 넣어야 할 장면 요소만 (뼈대만, 과도한 지시 금지)
      - 한글 텍스트는 이미지에서 지양 → 흐릿하게 처리하거나 생략
      - 인물이 필요한 씬 → Playwright로 Google 이미지 검색해서
        실제 인물 레퍼런스 사진 먼저 확보 후 프롬프트에 명시

□ 3. 인물 레퍼런스 수집 (Playwright)
      → Google Images에서 인물 검색 → 대표 사진 1장 확보
      → 프롬프트에 "이 인물과 유사한" 방식으로 활용

□ 4. Gemini API로 이미지 생성
      → 모델: gemini-2.5-flash (무료 500장/일)
      → public/images/{영상ID}/ 에 저장

□ 5. Remotion TSX 작성
      → 생성된 이미지 + 자막 조합
```

---

**명령어**: `아침 노트 만들어줘` / `/morning-note`

**출력**: `out/morning_note_cute.html` + `out/morning_note_dark.html`

### 생성 체크리스트
```
□ 1. wiki/L5_섹터/index.md → 오늘 🔴🟠🟡 섹터 온도 확인
□ 2. wiki/log.md → 최근 ingest 내용 확인
□ 3. wiki/L1_글로벌유동성/ → 매크로 한 줄 (VIX·달러·금리)
□ 4. 섹션 9개 선정 (🔴 2~3개 / 🟠 3~4개 / 🟡 1~2개)
□ 5. 각 섹션: 제목 + 불릿 3개 + 시그널 태그 + "왜 지금인지" 이유
□ 6. 날짜 업데이트 (cute·dark 두 파일 모두)
□ 7. log.md 기록
```

**주의**: Ingest 파일 생성 금지 (위키 읽기 전용). 실제 데이터만.

---

**명령어**: `시장분위기 어때` / `/morning-brief`

> 매일 **07:40** 자동 실행 (장 시작 전 핵심 브리핑). 5가지 질문을 순서대로 답한다.

### 5가지 질문 체계 (장전 브리핑)

**Q1. 오늘 시장분위기 어때? — 글로벌 분위기**

| 항목 | 데이터소스 | 체크 포인트 |
|------|---------|-----------|
| 달러/원 환율 | WebSearch | 1,500원 상하 위치 |
| WTI 유가 | WebSearch | 중동 긴장 → 유가 반응 |
| 달러인덱스(DXY) | WebSearch | 강달러 = 신흥국 자금이탈 |
| VIX | WebSearch | 20 이하=안정, 25 이상=주의 |
| S&P500 / NASDAQ / DOW | WebSearch | 전일 마감 방향 |
| 미-이란 전쟁 / 호르무즈 | WebSearch | 봉쇄 여부 → 유가·해운 |
| 한국 야간선물 | WebSearch | +/- 방향 |
| 미국 10Y 국채금리 | WebSearch | 4.5% 상단 돌파 여부 |

**Q2. 오늘 미국시장 어떤 섹터가 강했어? → 한국 연결**

```
□ WebSearch: "US sector performance today [날짜]"
□ 반도체(SOX) 강세 → SK하이닉스·삼성전자
□ AI/데이터센터 강세 → 반도체 소부장·PCB
□ 에너지 강세 → 중동 악재 확인
□ 자동차·로봇 강세 → 현대차·기아·레인보우로보틱스
□ 전력·유틸리티 강세 → 전력기기·변압기
```

**Q3. 지난밤 국내외 이슈가 뭐가 있어? → 한국 연결**

```
□ WebSearch: "한국 주식 오늘 시황 [날짜]"
□ WebSearch: "global market news overnight [날짜]"
□ 실적 발표·TP 상향 → wiki ingest 리포트 최신 확인
□ 정책 이슈 (금리·관세·밸류업) → 해당 섹터 영향 판단
□ 투경 신규 지정/해제 → 투경관리.md 확인
```

**Q4. 오늘 주도업종 섹터가 어디일까? → 태린이 파일**

```
□ raw/ingest_report_{어제날짜}.md 읽기
□ 수출 신호 🔴 섹터 확인 (디램·낸드·HBM·조선·변압기)
□ 컨센 신고가 TOP10 섹터 집계
□ 가속화모멘텀 TOP30 섹터 집계
□ 업종 쏠림지수 방향 (쏠림 장세 vs 순환매 장세)
□ 소르티노 TOP20 → 우상향 주도섹터
□ 종합: 3개 이상 교차 섹터 = 오늘 주도섹터
```

**Q5. 오늘 섹터 안에서 어떤 종목이 괜찮을까? → 태린이 + 투경**

```
□ 주도섹터 내 수급빈집A + 턴중(↑재진입) 종목
□ 투경관리.md — 오늘/이번주 해제 예정 종목 우선 확인
□ 컨센 탑픽 스코어 5점 이상 + 수급빈집 종목
□ 액티브ETF 비중 증가 종목 교차
□ 최종 출력: 탑픽 3~5개 (종목명 / 빈집등급 / 투경여부 / 이유 한줄)
```

### 브리핑 출력 형식

```
📊 [날짜] 장전 브리핑

① 글로벌: {환율} / WTI {유가} / S&P {%} — {한줄요약}
② 미국 강세섹터: {섹터1·섹터2} → 한국: {종목}
③ 밤사이 이슈: {핵심 1~2개}
④ 오늘 주도: 🔴{섹터1} > {섹터2} > {섹터3}
⑤ 탑픽 후보:
   - {종목} ({섹터}) | 빈집{등급} {방향} | {이유}
   - ...
```

---

## 4가지 운영 방법

### 1. 자료 넣기 (Ingest)

```
/ingest today              ← 매일 아침. 오늘 raw/ 전체
/ingest raw/{폴더}/{파일}  ← 단건 즉시 처리
```

**라우팅**: 섹터(L5) = 1줄 요약 / 종목(L6) = 상세 누적

| 폴더 | L5 섹터 반영 | L6 종목 반영 |
|------|------------|------------|
| `news/` `telegram/` | 이벤트 히스토리 1줄 | stock/ 최신 이벤트 상세 |
| `report/` | 대장주 TP 갱신 | stock/ 컨센서스 덮어쓰기 |
| `supply/` | 섹터 온도 갱신 | stock/ 수급흐름 + 탑픽점수 |
| `export/` | 수출 신호 갱신 | stock/ 수출 데이터 행 추가 |

**Claude 실행 체크리스트**:
```
□ 1. 폴더명으로 유형 판별
□ 2. 종목명·코드 추출 → 섹터 매핑
□ 3. L5/L6 동시 업데이트 (stock 없으면 신규 생성)
□ 4. 신호 강도 재평가 (같은 방향 3개↑ → 탑픽 콜아웃 / 충돌 → ⚠️)
□ 5. 종합 스토리 1~2줄 업데이트
□ 6. log.md 기록
```

**⚠️ Ingest 시 절대 금지**: 브리핑·HTML·스크립트 생성 — 사용자 명시 요청 시에만.

> **ingest 상세 규칙**: `wiki/rules/ingest_rules.md`

### 2. 결과물 만들기 (Output)

사용자가 명시적으로 요청할 때만: `오늘 리포트 만들어줘` / `브리핑 만들어줘`

1. wiki/ 관련 페이지 참조
2. 요청 형식으로 결과물 생성
3. `out/` 폴더에 저장
4. `wiki/log.md` 기록

### 3. 질문하기 (Query)

wiki 기반으로 자유롭게 질문. 위키에 없는 정보는 "위키에 없음 — 자료 추가 필요" 명시.

### 4. 건강검진 (Health Check)

`위키 건강검진 해줘`
1. 최근 7일 ingest 커버리지
2. 공백·오래된 페이지 탐지
3. 고아 페이지 탐지
4. 이번 주 유망 영상 주제 3가지
5. log.md 기록

---

## 탑픽 선정 기준

### 핵심 전략
```
1. 주도섹터 안에서
2. 주도주를 찾고
3. 수급 빈집을 찾는다

수급빈집 = 외인·기관이 빠져있는 상태 → 재진입 시 전량 신규매수 → 탄력 극대화
```

### 주도업종 판단 시스템 (태린이아빠 방식)

**3종 데이터 교차:**

| 데이터 | 파일 | 스크립트 |
|--------|------|---------|
| 소르티노 Top 20 | `소라티노ETF상대강도MMDD.xlsx` | `scan_sortino.py --tg` |
| 유동성 컨셉 | `유동성체크...xlsm` → '유동성 컨셉' 시트 | — |
| 업종 쏠림지수 | `특정업종쏠림지수국내MMDD.xlsx` | — |

**소르티노 원리**: 연수익 ÷ 하방편차 (하락할 때만 페널티). 3-6-12M 평균. 50일선 필터.
→ 점수 높음 = 꾸준히 우상향 = 주도업종 후보

**수출데이터 활용 원칙 (태린이아빠):**
- 주력 지표 ❌ — RS + 변동성모멘텀 + 기관유동성 + 거래대금이 주력
- 강한 섹터(RS↑)에서 수출까지 좋으면 확률 보완재로 활용
- 약한 섹터에서는 수출 무시 (시장 관심 없음)
- 발표일: 매월 1·11·21일 / 확정치: 15일

**2026년 6월 주도업종 결론:**
- 🔴 반도체 / 🟢 자동차·로봇 / 🩷 네트워크 / 🟡 전력에너지

### 빈집 등급
```
A 완전빈집: 하위 10% 이하
B 반빈집:   하위 10~25%
C 정상:     25~75%
D 과매수:   상위 25% 이상
```

### 8개 교집합 기준 (총 9점)

| # | 기준 | 배점 | 데이터 소스 |
|---|------|------|-----------|
| **0** | **수급 빈집** | **2점** | supply/ xlsm |
| 1 | 수출데이터 섹터 🔴 | 1점 | export_monitor.md |
| 2 | 판가이슈 | 1점 | export_monitor.md |
| 3 | 실적 어닝서프 | 1점 | stock/ 컨센서스 |
| 4 | 리포트 컨센 신고가 | 1점 | stock/ 컨센서스 |
| 5 | 미국 유사기업 커플링 | 1점 | sector/ 일일 로그 |
| 6 | 정책이슈 (국민성장펀드·밸류업·코스닥부양) | 1점 | stock/ 최신 이벤트 |
| 7 | 일정 재료 D-30 이내 | 1점 | stock/ 일정 섹션 |

> **수급빈집(#0) 우선** — 없으면 나머지 7개 충족해도 후순위

### 탑픽 등급

| 점수 | 수급빈집 | 등급 |
|------|---------|------|
| 7~9점 | ✅ | 🔴 오늘의 탑픽 |
| 5~6점 | ✅ | 🔴 탑픽 후보 |
| 3~4점 | ✅ | 🟠 관심주 |
| 1~2점 | ✅ | 🟡 빈집 대기 |
| 5~7점 | ❌ | 🟠 좋은 종목 |
| ~4점 | ❌ | 🟡 모니터링 |

### TYPE별 탑픽 체크 우선순위
- **TYPE A (실적형)**: #0수급 + #1수출 + #3어닝서프 우선
- **TYPE B (성장형)**: #0수급 + #6정책 + #7일정 우선

---

## 카테고리 정의

| 코드 | 한글명 | 설명 |
|------|--------|------|
| `stock` | 종목분석 | 개별 종목 마스터 페이지 |
| `sector` | 섹터종합 | 섹터별 일일 상태 |
| `market` | 시장분석 | 매크로·지수·환율 |
| `supply` | 수급분석 | 수급빈집추적 |
| `strategy` | 매매전략 | 실전 매매법 |

---

## 데이터 관리 원칙 (페이지 비대화 방지)

> 종목 페이지는 "지금 이 종목 어때?"에 5초 안에 답해야 한다.

| 섹션 | 규칙 |
|------|------|
| 증권사 컨센서스 | 증권사당 1행 덮어쓰기. 3개월 초과 삭제. |
| 최신 이벤트 | 7일 롤링 — 8일 이상 경과 행 → 섹터 index.md에 1줄 이관 후 삭제 |
| 수출 데이터 | 월별 1행. 확정치 나오면 잠정치 대체. |
| 수급 흐름 | 최신 10행 유지 |
| 일정 | D-0 이후 → 최신 이벤트로 이관 후 삭제 |

---

## Claude 행동 원칙

0. **질문 답변 순서 (최우선)**: 위키 먼저 → WebSearch 현재 교차검증 → 합쳐서 답
   > 상세: `wiki/rules/analysis_rules.md` §0

1. **종목 페이지 즉시 생성**: 종목 탐지 시 stock/ 페이지 없으면 즉시 생성
2. **히스토리 누적**: stock/ 페이지는 새로 만들지 않고 기존에 계속 쌓는다
3. **충돌 감지**: 상충 정보 발견 시 즉시 ⚠️ 플래그, 덮어쓰지 않는다
4. **비즈니스 관점 우선**: "유튜브 콘텐츠로 활용 가능한가?" 렌즈로 정리
5. **실전 중심**: "오늘 바로 쓸 수 있는 것" 강조
6. **교차참조**: 새 페이지 작성 시 관련 sector/ stock/ 페이지와 반드시 연결
7. **출처 명시**: 모든 wiki 내용에 원본 raw 파일명 기재
8. **인덱스 최신화**: 파일 생성·수정 시 index.md 즉시 업데이트
9. **로그 기록**: 모든 ingest·건강검진 작업을 log.md에 기록
10. **수출 모니터링 우선**: export ingest 시 export_monitor.md 먼저 업데이트 후 신호 감지
11. **결과물 자동 열기**: 사용자 명시 요청 결과물은 응답 끝에 자동 실행
12. **Gemini 사후 검증 필수**: 파트너십·납품·행사 주장은 WebSearch로 검증
    > 상세: `wiki/rules/analysis_rules.md` §4
13. **대내외 매크로 변수 포함 필수**: 섹터·종목 분석 시 Layer A/B/C 체크
    > 상세: `wiki/rules/analysis_rules.md` §2
14. **TYPE 분류 적용**: 섹터 분석 전 TYPE A/B/C 판단
    > 상세: `wiki/rules/analysis_rules.md` §1
15. **모델 분기 — 필수 규칙** (선택 아님):
    - **Haiku 필수 위임** (Agent tool, model: "haiku"): log.md 기록 / index.md 업데이트 / 파일 탐색 / 단순 라우팅 / 템플릿에 데이터 채우기
    - **Sonnet 전용** (Gemini·Haiku 절대 불가): Q10 리서치 / 섹터·종목 분석 / 대본·HTML 생성 / WebSearch / 신호 해석 / 판단·창작
    - Gemini는 이 환경에서 직접 호출 불가 → Haiku로 대체. 퀄리티 필요 작업에 Gemini 권고 금지.
16. **MCP 최우선 사용**: 어떤 작업이든 MCP로 가능하면 MCP 먼저. Python 스크립트·Bash는 MCP로 못 하는 경우에만.
    - 웹 크롤링·URL 읽기 → Fetch MCP (requests 스크립트 X)
    - 브라우저 자동화 → Playwright MCP (별도 스크립트 X)
    - 데이터 저장·조회 → SQLite MCP (CSV/MD 파일 X)
    - Python 스크립트 → 복잡한 연산·파일처리 등 MCP 불가 작업만

17. **저장 트리거**: 사용자가 "저장해", "저장", "마무리", "세션 끝" 입력 시 순서대로 자동 실행

    **분류 기준 (대화 내용 보고 Claude가 판단)**:
    | 내용 유형 | 저장 위치 |
    |-----------|---------|
    | 분석 프레임워크·전략·원칙 | `wiki/rules/` |
    | 종목·섹터 분석 결과 | `wiki/L5_섹터/` 또는 `wiki/L6_수급/` |
    | 오늘 작업 기록 | `wiki/log.md` |
    | 시스템 운영 규칙 변경 | `CLAUDE.md` |
    | AI가 다음 세션에 기억할 것 | `memory/*.md` |

    **실행 순서**:
    1. 대화 내용 분석 → 저장할 항목 분류
    2. 각 항목을 위 기준에 따라 해당 파일에 저장
    3. `wiki/log.md` — 이번 세션 작업 기록
    4. `memory/*.md` — 변경된 프로젝트 상태 업데이트
    5. `git add -A` → `git commit -m "auto: {한줄요약}"` → `git push`

    > git push 한 번으로 wiki·rules·log 등 모든 변경 파일이 올라감.
    > memory는 git 밖이라 push로 동기화 안 됨. 중요 상태는 log.md에도 남길 것.

---

## 결과물 자동 열기

사용자 명시 요청 결과물 → 응답 끝에 PowerShell로 자동 실행.

| 확장자 | 실행 명령 |
|------|---------|
| `.html` | `Start-Process "<절대경로>"` |
| `.md` | `code "<절대경로>"` |

**자동 열기 대상**: `out/` 폴더 신규 생성·주요 수정 파일
**자동 열기 제외**: ingest 자동 갱신 파일 / log.md / index.md / 임시 파일

---

## Skill routing — 전체 스킬 활용 맵

> **규칙**: 요청이 아래 조건과 일치하면 즉시 해당 스킬 호출. 의심스러우면 호출. 스킬이 있는데 직접 답하는 건 품질 저하.

### 🧠 Superpowers — 사고·프로세스 규율

| 트리거 | 스킬 |
|--------|------|
| 새 시스템·기능·영상 기획 시작 | `superpowers:brainstorming` |
| 설계 끝나고 구현 계획 작성 | `superpowers:writing-plans` |
| 계획대로 코드 실행 | `superpowers:executing-plans` |
| 에러·버그·오작동 | `superpowers:systematic-debugging` |
| 작업 완료 전 최종 체크 | `superpowers:verification-before-completion` |
| 씬 여러 개 동시·파이프라인 병렬 | `superpowers:dispatching-parallel-agents` |
| 대형 작업 서브에이전트 분산 | `superpowers:subagent-driven-development` |
| 새 슬래시 명령어 만들기 | `superpowers:writing-skills` |
| 브랜치 마무리·PR 준비 | `superpowers:finishing-a-development-branch` |
| 코드 리뷰 요청 | `superpowers:requesting-code-review` |
| 코드 리뷰 받기 | `superpowers:receiving-code-review` |
| 테스트 기반 개발 | `superpowers:test-driven-development` |
| 병렬 브랜치 작업 | `superpowers:using-git-worktrees` |

### 🛠 Gstack — 브라우저·QA·배포·검수

| 트리거 | 스킬 |
|--------|------|
| HTML 결과물·사이트 실제 확인 | `qa` |
| 버그만 찾고 수정 안 할 때 | `qa-only` |
| 디자인·UI 시각적 검수 | `design-review` |
| 디자인 시스템 전체 설계 | `design-consultation` |
| 디자인 여러 시안 비교 | `design-shotgun` |
| 프로덕션용 HTML/CSS 생성 | `design-html` |
| 코드 diff 리뷰 | `review` |
| 보안 취약점 점검 | `cso` or `security-review` |
| 커밋+PR+배포 한번에 | `ship` |
| 머지+배포+검증 통합 | `land-and-deploy` |
| 배포 후 모니터링 | `canary` |
| 배포 설정 초기화 | `setup-deploy` |
| 버그·오류 심층 조사 | `investigate` |
| 아이디어 빠른 CEO 검증 | `office-hours` |
| 전략·규모·방향 검토 | `plan-ceo-review` |
| 아키텍처 설계 검토 | `plan-eng-review` |
| 디자인 계획 검토 | `plan-design-review` |
| DX·API 설계 검토 | `plan-devex-review` |
| 전체 리뷰 자동 파이프라인 | `autoplan` |
| 스펙·이슈·백로그 작성 | `spec` |
| 문서 신규 생성 | `document-generate` |
| 배포 후 문서 업데이트 | `document-release` |
| 주간 회고 | `retro` |
| 코드 품질 대시보드 | `health` |
| 성능 회귀 측정 | `benchmark` |
| 웹 스크래핑 | `scrape` |
| PDF 생성 | `make-pdf` |
| 세션 저장 | `context-save` |
| 세션 복원 | `context-restore` |
| 특정 디렉토리 수정 잠금 | `freeze` / `unfreeze` |
| 안전 모드 (위험 작업 전) | `careful` / `guard` |
| gstack 업그레이드 | `gstack-upgrade` |
| 반복 실행 태스크 설정 | `loop` |
| 예약 실행 설정 | `schedule` |
| 앱 실행 및 동작 확인 | `run` |
| 권한 프롬프트 최소화 | `fewer-permission-prompts` |

### 🎬 영상 제작 파이프라인 (커스텀 스킬 + Gstack)

> **진입점**: 항상 `yt-make-video`부터. 절대 중간 단계부터 시작하지 말 것.

| 트리거 | 스킬 |
|--------|------|
| "영상 만들자" / `/make-video` | `yt-make-video` (전체 파이프라인 오케스트레이터) |
| "소재 찾자" / `/소재찾기` | `yt-content-research` (YouTube 리서치 → 주제 선정) |
| "기획서 써줘" / "씬 짜줘" | `yt-planner` (씬 구성 + 이슈 타이밍 체크) |
| "리서치해줘" / `/리서치` | `yt-deep-research` (YouTube 유사영상 + 기사 + 데이터 + 비교사례 수집 → 리서치 브리프) |
| "대본 써줘" / `/script` | `yt-script-writer` (리서치 브리프 기반 대본) |
| 대본 완성 후 Remotion 제작 | `remotion-best-practices` → `videoagent-director` |
| 씬 이미지 생성 | `videoagent-image-studio` |
| 음성·음악 처리 | `videoagent-audio-studio` |
| 최종 영상 합성 | `videoagent-video-studio` |
| "편집해줘" / 녹음 끝난 후 | `yt-editor` (Whisper 싱크 + 렌더) |
| "업로드해줘" | `yt-publisher` (YouTube + 텔레그램) |

**이슈 타이밍 원칙**:
- 이슈 터진 날 = 업로드 해야 하는 날
- 이슈 후 3일 지나면 → 각도 변경 or 새 소재
- `yt-content-research` STEP 0에서 항상 타이밍 체크 먼저

### 🧬 Agentmemory — 세션 간 기억

| 트리거 | 스킬 |
|--------|------|
| 과거 세션 내용 검색 | `agentmemory:recall` |
| 중요 내용 저장 | `agentmemory:remember` |
| 잘못된 메모리 삭제 | `agentmemory:forget` |
| 세션 컨텍스트 커밋 | `agentmemory:commit-context` |
| 세션 이력 확인 | `agentmemory:session-history` |
| 현재 세션 요약 | `agentmemory:recap` |
| 다른 에이전트에 인계 | `agentmemory:handoff` |

### 🔍 Understand-anything — 코드베이스 이해

| 트리거 | 스킬 |
|--------|------|
| 새 프로젝트 구조 파악 | `understand-anything:understand-onboard` |
| 코드에 대해 질문 | `understand-anything:understand-chat` |
| 특정 파일·함수 설명 | `understand-anything:understand-explain` |
| 비즈니스 도메인 분석 | `understand-anything:understand-domain` |
| 지식 그래프 조회 | `understand-anything:understand-knowledge` |
| 코드 변경 분석 | `understand-anything:understand-diff` |

### ⚙️ Context-engineering — 컨텍스트 최적화

| 트리거 | 스킬 |
|--------|------|
| 대화가 너무 길어질 때 | `context-engineering:context-compression` |
| 멀티 에이전트 설계 | `context-engineering:multi-agent-patterns` |
| 메모리 시스템 설계 | `context-engineering:memory-systems` |

### 🎨 기타 전문 스킬

| 트리거 | 스킬 |
|--------|------|
| 프롬프트 설계·최적화 | `prompt-architect:prompt-architect` |
| 프론트엔드 UI 설계 | `frontend-design:frontend-design` |
| 영상 자막 처리 (Whisper) | `watch:watch` |
| raw/ 파일 → wiki 처리 | `ingest` |
| 시황브리핑 스크립트 작성 | `yt-briefing` |
| Claude API 개발·최적화 | `claude-api` |
| 코드 리뷰 (ultra 딥리뷰) | `code-review` |
| 코드 단순화·리팩터 | `simplify` |
| 설정 파일 변경 | `update-config` |
| 키바인딩 설정 | `keybindings-help` |
| 변경사항 실제 동작 검증 | `verify` |
