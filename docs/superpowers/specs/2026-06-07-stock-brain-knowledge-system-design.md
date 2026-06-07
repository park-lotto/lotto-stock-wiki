# STOCK BRAIN — 1타 주식 지식창고 시스템 설계

작성일: 2026-06-07  
상태: 설계 확정 (구현 대기)

---

## 핵심 목표

> 엄청난 정보의 파편화를 위키로 모아서 모든 질문이 가능하게 한다.
> 매일 아침 시장 전체 큰 그림이 스토리로 나온다.
> 나부터 쓰고, 구독자에게 서비스로 확장한다.

---

## 근본 원칙

| 원칙 | 내용 |
|------|------|
| 버리지 않는다 | 원본 정보 100% 보존. 요약이 원본을 대체하지 않음 |
| 모든 질문이 가능하다 | 예상 밖 질문도 벡터 검색으로 답변 가능 |
| 스토리로 나온다 | 원자 조합 → Claude 합성 → 항상 서술형 답변 |
| 모든 소스가 통합된다 | 텍스트·수치·리포트가 같은 검색 공간 안에 |

---

## 전체 아키텍처: 4레이어

```
┌─────────────────────────────────────────────────────┐
│  LAYER 0: ATOM DB  (진짜 두뇌)                      │
│  SQLite (구조화) + Vector DB (의미 검색)             │
│  모든 정보의 최소 단위. 원본 보존. 만료 관리.        │
└──────────────────────┬──────────────────────────────┘
                       │ 자동 집계 (materialized view)
┌──────────────────────▼──────────────────────────────┐
│  LAYER 1: WIKI  (인간 가독층)                       │
│  L1~L6 기존 구조 유지 (아카이브)                    │
│  + state/ + threads/ (Living State — 자동 생성)      │
└──────────────────────┬──────────────────────────────┘
                       │ 매일 아침 자동 합성
┌──────────────────────▼──────────────────────────────┐
│  LAYER 2: NARRATIVE  (스토리 생성층)                 │
│  MARKET_BRAIN.md — DB 쿼리 결과로 자동 생성          │
│  수동 관리 없음. 항상 최신.                          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  LAYER 3: QUERY  (질문 응답층)                      │
│  카카오봇 → 텔레봇 → 웹앱 (단계별 확장)             │
│  1차 벡터 검색 → 2차 Claude 검수 → 3차 합성         │
└─────────────────────────────────────────────────────┘
```

---

## LAYER 0: Atom DB 상세 설계

### 원자(Atom)란

> 정보를 버리지 않고 쪼개서 담는 최소 의미 단위.
> 요약이 아님. 원문 그대로 + 메타데이터를 씌운 것.

```
100줄 텔레그램
    ↓ Haiku 원자화
20~30개 원자 (각 3~7문장, 원문 보존)
    ↓ Google Embedding-004
각 원자에 벡터 부여
    ↓ SQLite + ChromaDB/Qdrant
저장 완료
```

### 원자 스키마

```json
{
  "id": "atom_20260607_신한리서치_001",
  "date": "2026-06-07",

  // 소스
  "source_type": "telegram",
  "source_name": "신한리서치",
  "source_trust": "B",
  "raw_file": "raw/telegram/2026-06-07_신한리서치.md",

  // 분류
  "layer": "L5",
  "sector": "반도체",
  "asset": "브로드컴",
  "asset_level": "stock",

  // 신호
  "signal": "bearish",
  "event_type": "earnings",
  "magnitude": "major",
  "content_type": "fact",
  "strength_score": 4,

  // 유효기간
  "validity_type": "permanent",
  "validity_until": null,

  // 내용 (원문 그대로)
  "content": "브로드컴 AI 가이던스 시장 예상 대비 -11.8% 미달. AI 네트워크 장비 수요 둔화 우려 확산. 다음 분기 가이던스도 컨센서스 하회.",

  // 벡터
  "embedding": [...],

  "created_at": "2026-06-07T06:30:00"
}
```

---

## 표준 택소노미

### signal (신호 방향)
```
bullish    — 상승 재료
bearish    — 하락 재료
neutral    — 현황/팩트 (방향 없음)
risk       — 리스크 (방향 미결, 주시 필요)
catalyst   — 트리거 (곧 터질 이벤트)
conflict   — 충돌 (같은 자산에 상반된 신호, 둘 다 보존)
data       — 순수 수치 (오실레이터, 수급값)
```

### event_type (이벤트 성격)
```
earnings    — 실적/어닝/가이던스
policy      — 정책/규제/금리
supply      — 수급 (외국인·기관 매매)
demand      — 제품·서비스 수요
consensus   — 컨센서스·TP 변화
momentum    — 가속화·모멘텀 데이터
macro       — 매크로 지표 (환율·금리·DXY)
news        — 뉴스·이슈·공시
report      — 리포트·분석 의견
event       — IR·컨퍼런스·발표 일정
```

### asset_level (자산 범위)
```
stock       — 개별 종목 (삼성전자, SK하이닉스)
sector      — 섹터 (반도체, 조선, 로봇)
market      — 시장 (코스피, 코스닥, 나스닥)
macro       — 매크로 지표 (금리, 달러)
theme       — 사이클·서사 (AI투자사이클, 순환매)
```

### content_type (내용 성격)
```
fact        — 공시·실적·가격 등 검증된 사실 → 그대로 반영
data        — 수치 데이터 (수급·오실레이터) → 그대로 반영
analysis    — 증권사 공식 분석 → 출처 명시 후 반영
opinion     — 개인 의견·추천·예측 → 교차검증 후 반영
```

### source_trust (소스 신뢰도)
```
A — 증권사 공식 리포트
B — 텔레그램 유료 채널 (태린이아빠 등)
C — 텔레그램 일반 채널
D — 뉴스·블로그
E — 소셜·미확인
```

### validity_type (유효기간 유형)
```
event       — 특정 이벤트 기반 만료 (ETF 리밸런싱, FOMC 등)
date        — 날짜 기반 만료
permanent   — 계속 유효 (구조적 분석, 사이클 이해)
```

### magnitude (임팩트 크기)
```
major       — 시장·섹터 전체 영향
minor       — 종목 단위 영향
```

### strength_score (신호 강도: 1~5)
```
자동 계산 기준:
  소스 신뢰도 A → +2점
  소스 신뢰도 B → +1점
  확인 소스 2개 이상 → +1점
  magnitude=major → +1점
  키워드 "역대/쇼크/상한가" → +1점 (최대 5점 캡)
  사용자 수동 조정 가능
```

---

## 원자 간 관계 그래프

```
관계 타입:
  causes        브로드컴 실적 미달 →causes→ HBM 수요 의구심
  confirms      신한 리포트 →confirms→ 키움 리포트 (같은 방향)
  contradicts   매수 의견 →contradicts→ 매도 의견
  precedes      TEL 수주 증가 →precedes→ 국내 소부장 수혜
  belongs_to    HBM 협상 지연 →belongs_to→ AI투자사이클 thread

엣지 생성 방법:
  자동: 같은 asset + 같은 signal → confirms 자동 연결
  자동: 인제스트 시 원인-결과 키워드 감지 → causes 제안
  수동: 사용자/Claude가 중요 관계 직접 연결
```

그래프를 타고 "왜?"를 설명할 수 있음:
```
"SK하이닉스 왜 올라?"
→ 해당 원자
→ precedes 역방향: 어떤 선행 신호?
→ confirms: 확인 소스 수?
→ belongs_to: 어떤 큰 서사의 일부?
→ 스토리 자동 조립
```

---

## 서사 자동 감지

```
조건: 같은 asset + 같은 signal 방향 + 7일 이내 + 3개 이상 원자
결과: "반도체 bearish 신호 5개 누적 — 서사 생성할까요?" 알림
승인 시: thread 파일 자동 생성 + 원자들 belongs_to 연결
```

---

## LAYER 1: Wiki 구조 (2트랙)

### Track A — Archive (기존 유지)
```
wiki/L1~L6/     날짜별 사실 보관. 덮어쓰지 않음.
```

### Track B — Living State (신규, 자동 생성)
```
wiki/
├── MARKET_BRAIN.md          ← 시장 전체 스토리 (매일 자동 생성)
├── state/                   ← 섹터·매크로 현재 상태
│   ├── 반도체_state.md
│   ├── 로봇_state.md
│   ├── 조선_state.md
│   ├── 방산_state.md
│   ├── 금리_state.md
│   └── 외국인수급_state.md
└── threads/                 ← 진행중인 서사
    ├── AI_투자사이클.md
    ├── 순환매_전환국면.md
    └── 금리인하_타이밍.md
```

### MARKET_BRAIN.md 구조
```markdown
# MARKET BRAIN
업데이트: YYYY-MM-DD HH:MM

## 한 줄 요약

## 지금 어디에 있나 (사이클 국면)

## 살아있는 서사
| 서사 | 상태 | 강도 | 업데이트 |

## 전체 리스크 지도

## 전체 호재 지도

## 오늘 주목할 것 (catalyst 원자)

## 섹터별 상태 요약
```

### state 파일 구조
```markdown
# {섹터} STATE
업데이트: YYYY-MM-DD

## 현재 국면

## 내러티브 (3~5줄)

## 진행중인 리스크
## 진행중인 호재
## 신호 강도: 🟡
## 다음 트리거
```

### thread 파일 구조
```markdown
# Thread: {서사 이름}
상태: 🔴 진행중

## 서사 (현재형)
## 누적 증거 (날짜 + 원자 ID)
## 반증 증거
## 현재 판단
## 소멸 조건
```

---

## LAYER 2: MARKET_BRAIN 자동 생성

```
매일 아침 6:00 (미국장 마감 후)

1. Atom DB 쿼리:
   - 최근 24시간 hot 원자
   - 최근 7일 major 원자
   - 현재 유효한 risk/catalyst 원자
   - 활성 thread 현황

2. Google Embedding → 벡터 검색
   - "시장 전체 현황 리스크 호재 오늘 주목" 쿼리
   - 후보 50개

3. Claude Haiku 검수
   - opinion 원자 교차검증
   - conflict 원자 판단
   - 중복 제거
   - 15개 선별

4. Claude Sonnet/Haiku 합성
   - 15개 원자 → MARKET_BRAIN.md 생성
   - state/ 파일 업데이트
   - thread/ 서사 갱신
```

---

## LAYER 3: 검색 레이어

```
질문 수신
    ↓
1차: 질문 임베딩 → 벡터 검색 → 후보 50개
    ↓
2차: 메타데이터 필터 (날짜, 섹터, asset_level)
    ↓
3차: Claude 검수
     - opinion → source_trust 기반 가중치 적용
     - conflict → 양쪽 제시
     - 중복 제거
     → 15개 선별
    ↓
4차: 관계 그래프 추적
     - belongs_to thread 추가
     - precedes 선행 신호 추가
    ↓
5차: Claude 스토리 합성
     → 서술형 답변
```

---

## 인제스트 파이프라인

```
원천 소스:
  텔레그램 채널 (15개/일)
  리포트 PDF (10개/일)
  뉴스 (5개/일)
  Excel 데이터 (10개/일)
  블로그 (5개/일)

처리 흐름:
  1. raw/ 저장 (원본 보존)
  2. 소스 유형 판별
     - 단순 텔레/뉴스 → Gemini Flash 원자화
     - 긴 리포트(20p+) → Gemini Pro 원자화
     - Excel 숫자 → 의미 텍스트 변환 후 원자화
  3. 메타데이터 자동 추출 (택소노미 기준)
  4. 유효기간 자동 설정
  5. Google Embedding-004 → 벡터 생성
  6. SQLite + Vector DB 저장
  7. 관계 그래프 자동 연결 (confirms)
  8. 서사 감지 체크 (3개 이상 누적 시 알림)
  9. 주 1회 클린업 (validity_until 경과 → archive)
```

### Excel → 원자 변환 예시
```
입력: SK하이닉스 | 수급오실레이터 | +73 | 2026-06-07

출력 원자:
  content: "SK하이닉스 외국인+기관 수급 오실레이터 +73.
            상위 15% 진입, 수급 빈집 신호 발동.
            전주 대비 +12p 상승, 3주 연속 우상향."
  signal: bullish
  event_type: supply
  raw_value: 73
```

---

## 기술 스택

| 컴포넌트 | 도구 | 비용 |
|---------|------|------|
| 원자 저장 | SQLite | 무료 |
| 벡터 DB | ChromaDB (로컬) → Qdrant Cloud (서비스) | 무료 시작 |
| 임베딩 | Google Embedding-004 | 무료 |
| 원자화 | Gemini Flash | 무료 티어 |
| MARKET_BRAIN 생성 | Claude Haiku | $0.02/일 |
| 챗봇 답변 | Gemini 2.0 Flash | 무료 (초기 50명) |
| 카카오봇 플랫폼 | 카카오i 오픈빌더 | 무료 |
| 웹훅 서버 | Render/Railway | 무료 티어 |

**초기 MVP 비용: 월 $5 이하**

---

## 서비스 확장 단계

```
Phase 1 (MVP):
  - 나 혼자 사용
  - 카카오봇 연결
  - Gemini 무료 티어

Phase 2 (베타):
  - 소수 구독자 (10~50명)
  - 텔레봇 추가
  - 무료 티어 내 운영

Phase 3 (서비스):
  - 100명+ 구독자
  - 웹앱 추가
  - 유료 API 전환 (Gemini paid or Claude Haiku)
  - 월 구독 수익으로 API 비용 커버
```

---

## 비용 구조

```
인제스트 (일):
  원자화: Gemini Flash 무료 티어 내 처리
  임베딩: 무료
  총 인제스트: ~$0.00 (초기)

쿼리 (서비스):
  50명 × 5질문 = 250회/일 × 3,500토큰 = 875K 토큰
  Gemini 무료 티어: 1M 토큰/일 → 커버됨
  100명 이상부터 유료 전환: ~$0.03/일

MARKET_BRAIN 생성:
  Claude Haiku 1회: ~$0.02/일
```

---

## 변경 예상 포인트

> 이 설계는 구현하면서 변경될 수 있음. 핵심 원칙은 유지.

- 원자 granularity (3~7문장) — 실제 품질 보고 조정
- 메타데이터 추출 모델 (Haiku vs Gemini Flash) — 품질 비교 후 결정
- 벡터 DB 선택 (ChromaDB vs Qdrant) — 서비스 규모 보고 결정
- strength_score 캘리브레이션 — 데이터 쌓이면 조정
