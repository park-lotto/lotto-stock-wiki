# 시장 인사이트 헤드라인 — 브리핑 피드 최상단 고정 (설계)

## 배경

`2026-07-03-market-briefing-feed-design.md`로 구현한 5번째 칸(실시간 브리핑 피드)이
동작 중이다. 사용자 피드백: 지금의 시간순 스크롤 피드는 좋지만, **맨 위에 "오늘
시장이 왜 이렇게 움직이는지"를 강하게 설명하는 코멘트가 눈에 띄게 고정**돼 있어야
한다. "오늘은 전체적으로 다 빠졌다가 삼전·닉스가 다시 살아나는 흐름인데 왜? 이슈가
있으면 붙이고 없으면 수급이 어떻게 바뀌면서 반전됐는지" — 이런 인과관계 서술이
핵심이다. 주도섹터 나열은 다른 곳에도 이미 있어 불필요, 대신 특징종목(이유 포함)은
필요.

## 목표

1. 최상단에 지수의 오늘 흐름(빠졌다/반등했다 등 실제 패턴)을 근거로 한 2~4문장
   내러티브 코멘트를 표시한다.
2. 그 아래 오늘 특징적으로 움직인 종목 2~4개를, 왜 그런지 이유와 함께 붙인다.
3. 이유는 뉴스 또는 스탁브레인 고유 데이터(텔레그램·리포트·유튜브에서 뽑은 오늘자
   원자)에서 찾아 근거를 댄다 — 근거 없이 지어내지 않는다(기존 브리핑 피드와 같은
   원칙).
4. 시각적으로 눈에 띄게(강조 박스/굵은 글�씨) — 아래의 스크롤 피드와 구분되는
   고정 영역.

## 아키텍처

기존 3층 구조(감지→수집→종합)에 이 기능을 얹는다. 완전히 새 파이프라인을 만들지
않고, 이미 만든 `briefing_collect.py`/`briefing_synth.py`/`_briefing_keys()`를
재사용한다.

### 1. 지수 흐름 계산 — `briefing_detect.py`에 추가

`compute_index_shape(bars: list[dict]) -> dict | None` — 순수 함수. `bars`는 기존
market_flow의 `[{"t":"HHMMSS","price":...}]` 형식. 시가(첫 봉)·저점(최소가+시각)·
고점(최대가+시각)·현재가(마지막 봉)를 계산해 반환:
```python
{"open": 7650.0, "low": 7550.0, "low_t": "10:30",
 "high": 7890.0, "high_t": "11:50", "current": 7877.0}
```
Gemini에게 "이 숫자로 오늘 흐름을 설명해라"고 넘길 재료 — AI가 차트를 직접 해석하는
대신, 계산된 사실만 근거로 쓰게 해서 환각을 막는다. `bars`가 비어있거나 2개 미만이면
`None`.

### 2. 특징종목 선정 — `briefing_collect.py`에 추가

`pick_notable_movers(rank_pop: list, rank_amt: list, news_feed_data: dict | None, n: int = 4) -> list[dict]`
— market_flow의 `rank_popular`/`rank_amt`(이미 있음, 가격·등락률 포함)를 합쳐
등락률 절대값 기준 상위 N개를 뽑는다. 각 종목에 대해 `news_feed_data`의
`sectors[].stocks[]`에서 같은 이름을 찾아 매칭되는 뉴스 제목이 있으면 붙인다
(기존 `news_feed`가 이미 섹터별 종목뉴스를 매칭해두고 있어 재사용만 하면 됨).
반환:
```python
[{"name": "삼성전자", "change_rate": 6.8, "news_reason": "메모리 가격 반등 소식" },
 {"name": "SK하이닉스", "change_rate": 4.7, "news_reason": None}]
```
`news_reason`이 없으면 3번(atoms 매칭)에서 마저 채우거나, 그래도 없으면 `None`
유지(종합층 프롬프트가 "이유 없으면 수급으로 설명"하게 됨 — 지어내지 않되, 데이터
없다고 항목 자체를 버리진 않음).

### 3. 종목별 원자 매칭 — `briefing_collect.py`에 추가

`recent_atoms_for_stock(db_path: str, stock_name: str, limit: int = 1) -> list[str]`
— 기존 `recent_market_atoms`과 같은 파일, 같은 연결관리 패턴(try/finally close)
이되, `WHERE date=? AND asset=?`로 특정 종목명 매칭. 텔레그램·리포트·유튜브에서
오늘 그 종목을 언급한 원자 중 최신 것.

### 4. 종합 프롬프트 — `briefing_synth.py`에 추가

`build_insight_prompt(index_shape: dict, movers: list[dict], market_atoms: list[str]) -> str | None`
— `index_shape`가 `None`이면 `None`(재료 없으면 생성 안 함). 프롬프트 원칙(기존과
동일: 쉬운 말투, 사실만, 추측은 "~로 보임"):
```
너는 오늘 시장 상황을 한눈에 설명하는 헤드라인 작성자다.

## 오늘 지수 흐름 (실측)
시가 {open}, 저점 {low}({low_t}), 고점 {high}({high_t}), 현재 {current}

## 오늘 특징종목
- {name} {change_rate}%: {news_reason 또는 "이유 데이터 없음"}
...

## 오늘 시장 관련 코멘트(텔레그램/리포트)
{market_atoms}

## 출력 형식
코멘트: <오늘 지수가 왜 이렇게 움직였는지 2~4문장. 특징종목 이유 데이터 있으면
인용, 없으면 "~로 보임" 표시하며 수급 관점으로 설명>
특징종목: <종목명(이유)를 쉼표로 나열, 이유 없으면 종목명만>
```
`parse_insight_response(text: str) -> dict | None` — `"코멘트:"`/`"특징종목:"` 두
마커 파싱, 둘 다 없으면 `None`.

### 5. 저장 — `briefing_store.py` 확장

`market_briefing.json`에 최상위 `insight` 키 추가(기존 `items` 배열과 별도):
```json
{"date": "...", "insight": {"ts": "11:50", "comment": "...", "movers": "삼성전자, SK하이닉스"},
 "items": [...]}
```
`load_briefing`은 `insight` 없으면 `null` 기본값 포함해서 반환(하위호환 — 기존
`items`만 있는 파일을 읽어도 안 깨지게). 새 함수 `set_insight(path, insight_obj)`
— `items`는 안 건드리고 `insight` 필드만 갱신·저장(원자적 쓰기, 기존 append와
같은 tmp→replace 패턴).

### 6. 백그라운드 갱신 — `server.py`에 추가

`_insight_run_synthesis()` — 독립 타이머 15분(900초)마다 1회. `_prewarm_cache`의
`market_flow`에서 `bars`/`rank_popular`/`rank_amt` 읽어 위 파이프라인 실행,
`_briefing_keys()`로 Gemini 호출(기존 브리핑 피드와 같은 전용 키풀 — 쿼터 공유는
허용, 둘 다 15~20분급 저빈도라 문제 안 됨), 결과를 `set_insight()`로 저장.
`_poll_briefing`의 30초 루프 안에 시간 체크 추가(기존 12분 고정 타이머와 같은
패턴, 독립 변수로 관리).

### 7. API — 기존 `/api/market_briefing` 응답에 `insight` 필드가 자연히 포함됨
(저장 구조에 추가했으므로 별도 엔드포인트 불필요)

### 8. 프론트 — `market.html`

기존 `if(code==="briefing")` 분기 안, `.briefing-feed` 렌더 코드 앞에 삽입:
```html
<div class="mkt-insight">
  <div class="mi-comment">${esc(insight.comment)}</div>
  <div class="mi-movers">📌 ${esc(insight.movers)}</div>
</div>
```
CSS: 강조 배경(예: 골드 계열 테두리+짙은 배경), 코멘트는 굵은 글씨 13~14px 정도로
피드 항목(11~12px)보다 크게. `insight`가 `null`이면 이 블록 자체를 안 그림(플레이스홀더
없이 생략 — 로딩중엔 그냥 피드만 보임).

## 범위 제외 (이번엔 안 함)
- 주도섹터 나열 (사용자가 명시적으로 불필요하다고 함 — 다른 카드에 이미 있음)
- 특징종목의 클릭 시 상세 이동 등 인터랙션 (텍스트 표시만)

## 에러 처리
- `bars`가 아직 충분히 안 쌓였으면(장 초반) `compute_index_shape`가 `None` →
  이번 갱신 주기는 건너뜀(다음 15분 때 재시도)
- Gemini 실패 → 기존 `insight` 값 유지(있으면), 없으면 계속 null(블록 안 보임)
- atoms/news 매칭 실패해도 종목명만이라도 표시(부분 실패가 전체를 막지 않음)

## 테스트
- `compute_index_shape`: bars fixture로 시가/저점/고점/현재가 계산 정확성
- `pick_notable_movers`: rank 데이터 + news_feed 매칭 순수함수 테스트
- `recent_atoms_for_stock`: 실제 sqlite fixture, 종목명 필터+커넥션정리(기존
  `recent_market_atoms`과 같은 패턴)
- `build_insight_prompt`/`parse_insight_response`: 순수함수 유닛테스트
- `set_insight`/`load_briefing` 확장: 기존 파일(items만 있는) 호환성 테스트
