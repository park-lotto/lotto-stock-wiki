# 블로그 인제스트 시스템 — 설계

- **날짜**: 2026-06-21
- **배경**: 소스 확장(C안)의 첫 단계. 텔레그램 인제스트([[project_telegram_ingest]]) 패턴을
  블로그로 확장. 블로그는 정보성·종목·인사이트가 모두 있는 고유 컨텐츠(pokara61 등 개인 분석).
- **범위**: 블로그 인제스트만. 유튜브·뉴스는 후속.
- **핵심 원칙**: **최대 재사용** — 새 코드 최소. 블로그는 "리포트의 내용기반 라우팅 +
  텔레그램의 2층 fan-out + sector_classify(섹터 자동분류)"의 합성이다.

---

## 1. 블로그 데이터의 성격 (실데이터 확인)

`raw/blog/{date}_{seq}_{제목}.md` — 포스트 1개 = 파일 1개. 예:
```
# 바이오 주식과 코스닥 승강제에 대해서
- **출처**: pokara61 블로그
- **날짜**: 2026-06-21
- **링크**: https://blog.naver.com/pokara61/...
## 본문
[핵심 주장] ... [근거 및 데이터] ... [투자 시사점] ...
```

| 특성 | 텔레그램과 차이 |
|---|---|
| 단위 | 포스트 1개 (채널 스트림 아님) |
| 사전요약 | 크롤러가 [핵심주장/근거/시사점]으로 이미 정리(~900자). **원문 아님** |
| 타입 | 포스트마다 제각각(종목분석/섹터/시황/에세이) → **채널타입 고정 불가, 내용기반 라우팅** |
| 출처 | 블로거명(pokara61 등) — 신뢰등급 부여 가능 |

---

## 2. 결정 사항 (brainstorming 확정)

| 항목 | 결정 |
|---|---|
| 추출 | **Gemini 재추출**(내용기반 라우팅 + 우리 슬롯). blog ~900자라 비용 극소 |
| 라우팅 | **내용기반**(리포트 target_kind 방식): stock / sector / market / insight |
| 의견 처리 | **2층 모델**(텔레그램 재사용): 사실 append / 스탠스 갱신 / 방법론. stance_key=블로거\|대상 |
| 신뢰등급 | 블로거별 레지스트리 + 기본 C |
| quote | 약함(이미 요약본이라 원문대조 검증 불가) — 검증은 생략/완화 |

---

## 3. 아키텍처 (재사용 중심)

```
raw/blog/*.md (포스트)
   │
blog_ingest.py (오케스트레이터, 신규 — 얇음)
   ├ 미처리 탐색 (telegram_ingest dedup 패턴 재사용)
   ├ 헤더 파싱: 출처(블로거)·날짜·링크·제목
   ├ blog_registry에서 신뢰등급 조회 (기본 C)
   ├ extract_blog(.md)  ← Gemini: STEP0 라우팅(kind) + 타입별 슬롯 채우기
   ├ questionnaire_to_atoms_tg(q, meta)  ← 텔레그램 fan-out 재사용
   │     meta = {date, channel=블로거, type=kind, source_type="blog", trust, raw_file, link}
   └ insert_atom + embed_and_store (+ 스탠스 만료)
```

### 재사용 vs 신규
| 자산 | 역할 | 신규/재사용 |
|---|---|---|
| `questionnaire_to_atoms_tg` (telegram) | 2층 fan-out·외국주·sector_hint | **재사용** (작은 확장: source_type 파라미터화) |
| `sector_classify.resolve_sector` | 섹터 자동분류 | 재사용 |
| `stock_resolve` | 종목 정규화·외국주 | 재사용 |
| `telegram_stance.deactivate_prior_stance` | 스탠스 만료 | 재사용 |
| `db`·`vector_db` | 저장 | 재사용 |
| `blog_questionnaire.py` | 내용라우팅 + 타입별 질문지 | **신규** |
| `blog_registry.json` | 블로거→신뢰등급 | **신규** |
| `blog_ingest.py` | 오케스트레이터 | **신규**(얇음) |

---

## 4. 내용기반 라우팅 + 질문지 (blog_questionnaire.py)

리포트 `target_kind` 방식 차용. Gemini가 STEP0에서 포스트 종류를 판별하고, 해당 타입의
슬롯을 채운다. **라우터는 텔레그램 fan-out과 호환되는 타입명을 직접 출력**한다(재사용 위해 — §5):

| blog kind (출력값) | 판별 | fan-out 슬롯 |
|---|---|---|
| `stock_tips` | 특정 종목 집중 분석 | `stocks:[{name, signal, reason, ts, quote, sector}]` |
| `sector` | 단일 섹터/테마 | `sector_name, sector_view, points, stocks_mentioned, events` |
| `market` | 시황/매크로 | `market_direction, macro_events, sectors_mentioned` |
| `insight` | 에세이·전략·잡생각 | `stance, methods, stocks_mentioned, leading_sectors` |

> 라우터 출력이 텔레 타입명(`stock_tips`)과 동일하므로 fan-out 분기 무변경.

- 종목 슬롯에 **sector_hint** 포함(sector_classify 재사용).
- `ts`(블로그는 메시지시각 없음 → null 허용), `quote`(요약본 핵심문장).
- 프롬프트 철칙: 없으면 null, 종목·수치 그대로, sector는 sectors.json 목록에서.

---

## 5. fan-out 재사용 (작은 확장)

`questionnaire_to_atoms_tg(q, meta)`를 그대로 쓰되 두 가지 최소 확장:
1. **`_base`의 source_type 파라미터화**: `meta.get("source_type", "telegram")`. blog는 "blog".
2. **kind "stock" 처리**: 현재 fan-out은 `stock_tips`를 stocks 슬롯으로 처리. blog의 `stock`
   kind를 `stock_tips`와 동일 분기로 매핑(별칭) 또는 라우터가 `stock_tips`로 출력.
   → 라우터가 텔레 호환 타입명(`stock_tips/sector/market/insight`)을 직접 출력하면 fan-out 무변경.

> 결정: **라우터가 텔레 호환 타입명을 출력** → fan-out은 source_type 파라미터화만 추가.
> stance_key=`{블로거}|{대상}`은 기존 `meta['channel']` 경로 그대로 동작(channel=블로거).

---

## 6. 오케스트레이터 (blog_ingest.py)

`telegram_ingest.py` 패턴 차용:
```
blog_ingest --all [--date] [--limit] [--dry-run]
  └ raw/blog/*.md 미처리 탐색 (DB done-체크 basename, telegram 패턴)
  └ 헤더 파싱: 출처/날짜/링크/제목 (정규식)
  └ blog_registry 신뢰등급 (없으면 C)
  └ extract_blog(.md) — Gemini 라우팅+추출
  └ meta 구성 → questionnaire_to_atoms_tg
  └ 스탠스원자 deactivate_prior_stance → insert_atom + embed_and_store
  └ 아티팩트: raw/blog_q/{date}/{제목}.json
```
`atom_pipeline.py`에 STEP3.6(텔레 STEP3.5 다음)으로 추가.

---

## 7. quote/검증 (약함)

블로그 .md는 크롤러 요약본이라 **원문 대조 불가**(원문은 링크 너머). 따라서:
- quote = 요약본의 핵심 문장(있는 그대로). 할루시네이션 1차 검증(verify_telegram quote 대조)은
  요약본 자체 대조로 완화 적용 — quote가 .md(요약본)에 있는지만 확인.
- comment/reason은 약신뢰(기존 원칙). strength는 블로거 신뢰등급(기본 C=2) 기반.
- 원문 검증이 필요하면 `link`로 추적(후속).

---

## 8. 검증/테스트
- 라우터 프롬프트 구조(타입·sector·quote 키 포함) 단위테스트(Gemini 호출 안 함).
- fan-out source_type="blog" 반영 테스트(원자 source_type 확인).
- blog_registry 조회(등록/미등록→기본C) 테스트.
- 헤더 파싱(출처·날짜·링크) 테스트.
- 라이브 1포스트 인제스트 → DB·아티팩트·source_type=blog 확인.
- 로그/DB 격리(운영 안 건드림) — 기존 패턴.

---

## 9. 범위 밖 (후속)
- 유튜브·뉴스 인제스트 (같은 패턴 확장)
- 블로그 원문 크롤링·원문 quote 검증 (현재 요약본 기준)
- daily_health 검증시스템 (설계 완료, 구현 보류)

---

## 10. 미해결/결정
- blog_registry 초기 시드: pokara61(B, 검증된 분석가) + 기본 C → 운영하며 보강
- 라우팅 4타입이면 충분 — theme는 sector로 흡수
- 사전요약본의 [핵심주장/근거/시사점] 구조를 프롬프트 입력에 그대로 활용(Gemini가 슬롯으로 재배치)
