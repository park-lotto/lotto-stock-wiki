# 다채널 인사이트 집계 파이프라인 — 설계 스펙

**날짜**: 2026-06-04  
**버전**: v2.0 (완전 재설계)  
**상태**: 승인됨

---

## 1. 목적

텔레그램·블로그·리포트·유튜브 4개 채널의 원문을 매일 자동으로 처리해 두 가지 결과물을 생성한다.

- **wiki 자동 업데이트**: 종목·섹터 마스터 페이지에 최신 이벤트 1~2줄 추가
- **HTML 브리핑**: `out/briefing_YYYYMMDD.html` — 07:40 아침 브리핑 자료

두 결과물은 동등하게 중요하다.

---

## 2. 전제 조건

- `raw/inbox/{telegram,blog,report,youtube}/` 에 크롤러가 `.md` 파일을 자동 저장 (완성됨)
- `GEMINI_API_KEY` 환경변수 설정됨
- `ANTHROPIC_API_KEY` 환경변수 설정됨

---

## 3. 아키텍처

### 전체 흐름

```
raw/inbox/ (4채널)
    ↓
[Agent A] Gemini Flash × 4채널 병렬
  · 클레임 추출 (원문 보존)
  · 팩트 / 의견 분리
  · 종목·섹터 태깅
  · 채널 간 충돌 후보 감지
    ↓ pipeline/YYYYMMDD/claims.json
[Agent B] Claude Sonnet × 1회 통합 호출
  · 충돌 감지 클레임 교차 검증
  · wiki 업데이트 위치 결정 (파일 경로 + 섹션)
  · 삽입할 마크다운 줄 직접 생성 (ready-to-use)
    ↓ pipeline/YYYYMMDD/decisions.json
[Script C] 순수 Python (LLM 없음) ──┐ 병렬
  · decisions.json 읽어 wiki 파일에  │
    append / ⚠️ flag 처리            │
[Agent D] Claude Haiku × 1회       ──┘
  · claims + decisions → HTML 브리핑
    ↓
git commit "auto: channel-ingest YYYY-MM-DD"
```

### LLM 호출 수
| 에이전트 | 모델 | 호출 수 |
|---------|------|--------|
| Agent A | Gemini 2.5 Flash | 채널당 1~2회 (최대 8회) |
| Agent B | Claude Sonnet | 1회 |
| Agent D | Claude Haiku | 1회 |
| **합계** | | **≤ 10회/일** |

예상 비용: $0.04~0.06/일

---

## 4. 데이터 모델

```python
class Claim:
    id: str                    # tg_001, bl_002, rp_003, yt_004
    channel: str               # telegram | blog | report | yt
    source: str                # 태린이아빠, KB증권, ...
    content: str               # 원문 핵심 (400자 max, 의역 금지)
    claim_type: str            # fact | opinion | prediction
    sector: str | None         # 반도체, 조선, ...
    tickers: list[str]         # [SK하이닉스, 000660]
    direction: str             # bullish | bearish | neutral
    conflict_candidate: bool   # 다른 채널과 상충 가능성

class WikiDecision:
    claim_id: str
    action: str                # append | flag | skip
    wiki_file: str             # wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md
    section: str               # ## 최신 이벤트
    line: str                  # - [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)
    conflict_note: str | None  # ⚠️ KB증권과 방향 상충 — 양쪽 게재

class PipelineState:
    run_date: str
    step: str                  # pending | A_done | B_done | done | failed
    claims_file: str | None
    decisions_file: str | None
    error: str | None
```

---

## 5. 파일 구조

```
scripts/channel_pipeline/
  __init__.py
  models.py        — 위 3개 Pydantic 모델
  manifest.py      — raw/inbox/ 파일 수집 + 날짜 필터
  cost_guard.py    — 토큰 추정 + $0.06 cap
  agent_a.py       — Gemini Flash 분류 (4채널 asyncio 병렬)
  agent_b.py       — Sonnet 검증 + 마크다운 생성
  wiki_writer.py   — 순수 Python wiki append/flag 처리
  agent_d.py       — Haiku HTML 브리핑
  pipeline.py      — 오케스트레이터 (state 관리, resume)

pipeline/
  YYYYMMDD/
    state.json
    claims.json
    decisions.json

docs/superpowers/specs/
  2026-06-04-channel-pipeline-design.md  ← 이 파일
```

---

## 6. 에러 처리

| 상황 | 처리 방식 |
|------|---------|
| Gemini API 실패 | 3회 retry (지수 백오프), 채널 스킵 후 계속 |
| Sonnet 타임아웃 | state에 `B_failed` 기록, `--resume`으로 재실행 |
| wiki 파일 없음 | `wiki_writer.py`가 신규 파일 생성 (page_templates 기준) |
| 충돌 감지 | ⚠️ 줄 추가 후 계속 진행 (중단 안 함) |
| 비용 초과 ($0.06+) | 파일 수 축소 후 재추정, 그래도 초과 시 중단 |
| 모든 채널 파일 없음 | 로그만 남기고 조용히 종료 |

---

## 7. 실행 방법

```bash
# 자동 (cron 07:00 KST)
python -m scripts.channel_pipeline.pipeline

# 수동
python -m scripts.channel_pipeline.pipeline --date 2026-06-04
python -m scripts.channel_pipeline.pipeline --dry-run   # wiki 쓰기 없이 확인만
python -m scripts.channel_pipeline.pipeline --resume    # 실패 단계부터 재시작
python -m scripts.channel_pipeline.pipeline --step A    # A 단계만 실행
```

---

## 8. wiki 업데이트 규칙

- `append`: `## 최신 이벤트` 섹션 최상단에 1줄 추가
  - 형식: `- [YYYY-MM-DD] {내용} ({출처}/{채널})`
  - 섹션이 없으면 파일 하단에 `## 최신 이벤트` 헤더와 함께 생성
  - 8일 이상 경과 행은 섹터 index.md로 이관 후 삭제 (기존 규칙 준수)
- `flag`: append와 동일하되 줄 끝에 `⚠️ {conflict_note}` 추가
- `skip`: wiki 파일 무수정, 로그에만 기록

---

## 9. HTML 브리핑 형식

`out/briefing_YYYYMMDD.html`

```
📊 [날짜] 채널 인사이트 브리핑

🔴 주목 클레임 (bullish/bearish 충돌)
  - 종목 | 채널 | 내용 | ⚠️ 표시

📋 채널별 주요 클레임
  텔레그램 | 블로그 | 리포트 | 유튜브 섹션

📈 오늘 언급 종목 요약
  종목명 | 섹터 | 방향 | 출처 수
```

---

## 10. 범위 외 (이번 버전 미포함)

- 채널 신뢰도 점수 추적 (ChannelStats) — 이후 버전에서 추가
- 토론 파일 생성 (wiki/채널토론/) — 이후 버전에서 추가
- 유튜브 영상 분석 (Whisper) — 별도 파이프라인
