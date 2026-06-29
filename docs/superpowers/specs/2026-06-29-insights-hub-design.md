# 크롤링 인사이트 허브 — 설계 스펙

작성: 2026-06-29 (Opus 설계) · 구현: Sonnet 에이전트
대상 서버: 딸깍 대시보드 `dashboard/server.py` (FastAPI, :8090)

---

## 0. 목적 (한 문장)

크롤링되는 모든 소스(유튜브/텔레/블로그·리포트)를 **카테고리→채널→문서→상세**로 드릴다운하며,
각 문서마다 "이것만 보면 되는" AI 요약을 보여주고, 거기서 **① 유튜브 소재화 ② 위키 저장**까지 잇는 허브.

세 페이지 체계:
- **딸깍**(`/`) = 장전·장중·장후 시간 흐름
- **섹터맵**(`/market`) = 장중 흐름 관찰
- **인사이트**(`/insights`) = 크롤링 정보 요약 ← **이번 구현 대상**

핵심 원칙: **"보여주는 게 큰 거다"** — 메인 화면의 시각적 완성도와 드릴다운 연결감이 최우선.

---

## 1. 정보 구조 (4단계 드릴다운)

```
L0 메인        L1 소스          L2 문서             L3 상세
─────────────────────────────────────────────────────────────
📺 유튜브   →  채널 5개      →  영상별            →  AI요약 + 발언 타임라인
💬 텔레그램 →  채널 17개+    →  날짜 묶음         →  AI요약 + 메시지 원자
📰 블로그·리포트 → 증권사/블로거 → 글별            →  AI요약 + 핵심 원자
```

**문서(L2) 단위 정의** — `atoms.db`의 컬럼으로 그룹핑:
- 유튜브: `raw_file` 1개 = 영상 1개. (경로 불일치 주의 → **basename으로 정규화**해서 그룹)
- 텔레그램: `source_name`(채널) × `date` = 하루치 묶음 1개
- 블로그/리포트: `raw_file` 1개 = 글 1개

**source_type 매핑**:
- 카테고리 `youtube` ← `source_type IN ('youtube','yt')`
- 카테고리 `telegram` ← `source_type='telegram'`
- 카테고리 `report` ← `source_type IN ('report','blog','news')` (라벨 "블로그·리포트")

---

## 2. DB 스키마 추가 — AI 요약 캐시

`pipeline/atoms/` 에 신규 테이블. `db.py` 패턴(멱등 마이그레이션)을 따른다.

```sql
CREATE TABLE IF NOT EXISTS doc_summaries (
    doc_key       TEXT PRIMARY KEY,   -- 문서 식별자 (아래 규칙)
    category      TEXT,               -- youtube | telegram | report
    source_name   TEXT,               -- 채널/증권사/블로거
    doc_title     TEXT,               -- 표시용 제목
    doc_date      TEXT,               -- YYYY-MM-DD
    tldr          TEXT,               -- 🎯 한 줄 핵심
    summary3      TEXT,               -- 💬 주린이 3줄 (줄바꿈 구분)
    market_view   TEXT,               -- 📊 시장관: bullish|bearish|neutral
    market_reason TEXT,               -- 시장관 근거 1~2문장
    stocks_json   TEXT,               -- [{"name","stance","reason"}] JSON
    seeds_json    TEXT,               -- 유튜브 소재 후보 [{"angle","hook"}] JSON
    atom_count    INTEGER,
    generated_at  TEXT,
    model         TEXT DEFAULT 'claude-cli'
);
```

**doc_key 규칙** (재현 가능해야 캐시 hit):
- 유튜브/리포트: `f"{category}:{basename(raw_file)}"`
- 텔레그램: `f"telegram:{source_name}:{date}"`

---

## 3. AI 요약 생성기 — `pipeline/atoms/doc_summary.py` (신규)

`claude -p` 헤드리스 호출 (server.py의 `run_chat`와 동일한 CLAUDE_BIN/bypassPermissions 패턴).

### 함수 시그니처
```python
def get_or_build_summary(doc_key: str, *, force: bool=False) -> dict
    # 캐시 있으면 즉시 반환. 없거나 force면 생성→캐시→반환.

def _collect_atoms(doc_key: str) -> tuple[dict, list[dict]]
    # doc_key 파싱 → 해당 문서의 원자들 + 메타(category/source/title/date) 반환

def _build_prompt(meta: dict, atoms: list[dict]) -> str
def _call_claude(prompt: str) -> dict   # JSON 강제, 파싱 실패 시 재시도 1회
```

### claude 프롬프트 설계 (핵심 — 퀄리티 좌우)
출력은 **반드시 JSON 한 덩어리**. 프롬프트에 원자 발언 목록(시각·화자·내용·stance)을 넣고:

```
너는 주식 유튜브 채널 "로또의 주식"의 인사이트 분석가다.
아래는 [{source_name}] 의 [{doc_title}] ({doc_date}) 에서 추출한 발언들이다.
시청자가 영상을 안 보고도 핵심을 가져가게, 그리고 내가 이걸로 유튜브 콘텐츠를
만들 수 있게 요약하라.

[발언 목록]
- [16:40] (강세) 진행자: 주도주를 끝까지 끌고 가야 됩니다 ...
...

아래 JSON 스키마로만 답하라 (설명·마크다운 금지):
{
  "tldr": "한 줄로 이 문서의 핵심 (20자 내외)",
  "summary3": ["주린이도 이해할 쉬운 문장1", "문장2", "문장3"],
  "market_view": "bullish|bearish|neutral 중 하나",
  "market_reason": "왜 그렇게 보는지 1~2문장",
  "stocks": [{"name":"종목명","stance":"매수|매도|중립","reason":"한줄"}],
  "seeds": [{"angle":"영상 소재 앵글","hook":"썸네일/후킹 문구"}]
}
규칙: 발언에 없는 사실 지어내지 마라. 종목은 실제 언급된 것만.
```

`market_view`/stance 값은 한글 라벨로 프론트에서 변환. JSON 파싱 실패 시 1회 재시도, 그래도 실패하면 규칙기반 폴백(stance 집계)으로 최소 채워서 저장.

---

## 4. API 계약 (server.py 에 추가) — **프론트는 이 계약만 의존**

모든 응답 `application/json`. 에러는 `{"error": "..."}`.

### 4.1 `GET /insights` → HTML
`dashboard/insights.html` 파일 서빙 (index/market과 동일 패턴).

### 4.2 `GET /api/insights/overview`
메인 화면용. 카테고리 3개 카드 + 통합 최신 피드 + 오늘의 한 줄.
```json
{
  "today": "2026-06-29",
  "categories": [
    {"id":"youtube","label":"유튜브","icon":"📺",
     "channels":5,"docs":22,"atoms":148,"today_new":2,
     "hot":[{"doc_key":"...","title":"AI 버블이 온다...","source":"GODofIT","date":"2026-06-29","atoms":18}]},
    {"id":"telegram", ...},
    {"id":"report", ...}
  ],
  "feed":[  // 카테고리 섞어 최신 문서 시간 역순 20개
    {"category":"youtube","doc_key":"...","title":"...","source":"GODofIT",
     "date":"2026-06-29","atoms":18,"has_summary":true}
  ]
}
```

### 4.3 `GET /api/insights/sources?category=youtube`
L1 — 채널 목록.
```json
{"category":"youtube","label":"유튜브",
 "sources":[{"name":"GODofIT","docs":8,"atoms":48,"last_date":"2026-06-29"}, ...]}
```

### 4.4 `GET /api/insights/docs?category=youtube&source=GODofIT`
L2 — 문서 목록.
```json
{"category":"youtube","source":"GODofIT",
 "docs":[{"doc_key":"youtube:2026-06-29_1100_GODofIT.md","title":"AI 버블이 온다...",
          "date":"2026-06-29","atoms":18,"has_summary":true}, ...]}
```

### 4.5 `GET /api/insights/doc?doc_key=...`
L3 — 상세. 캐시된 요약 + 원자 타임라인.
```json
{
  "doc_key":"...","category":"youtube","source":"GODofIT",
  "title":"AI 버블이 온다...","date":"2026-06-29","video_url":"https://...",
  "summary":{  // doc_summaries 한 행 (없으면 null)
    "tldr":"...","summary3":["..."],"market_view":"bullish",
    "market_reason":"...","stocks":[{"name","stance","reason"}],
    "seeds":[{"angle","hook"}],"generated_at":"..."
  },
  "atoms":[  // 타임라인. yt_timestamp 오름차순
    {"timestamp":"16:40","seconds":1000,"speaker":"진행자","signal":"bullish",
     "stance":"중립","content":"...","deeplink":"https://...&t=1000",
     "asset":"주도주","sector":"AI소프트웨어"}
  ]
}
```

### 4.6 `POST /api/insights/summarize` body `{doc_key, force?}`
요약 생성/재생성 트리거. `doc_summary.get_or_build_summary` 호출(threadpool). 생성된 summary 반환. 시간 걸림(수십 초) → 프론트는 로딩 표시.

### 4.7 `GET /api/insights/search?q=삼성전자`
종목 횡단 검색. content/asset LIKE + 가능하면 vector. 카테고리·채널 가로질러.
```json
{"q":"삼성전자","total":12,
 "hits":[{"category":"youtube","source":"UP_CYCLE_STOCK","doc_key":"...",
          "title":"...","date":"...","timestamp":"00:09","stance":"매도",
          "content":"...","deeplink":"..."}]}
```

### 4.8 `POST /api/insights/to_youtube` body `{doc_key}`
유튜브 소재화. 해당 문서 주제로 `pipeline.atoms.yt_plan` 호출 → 발언카드+70/20/10 골격 마크다운 반환. (yt_plan에 함수 진입점 있으면 import, 없으면 subprocess `python -m pipeline.atoms.yt_plan "주제"`)
```json
{"ok":true,"markdown":"## 발언카드\n...","topic":"AI 버블 주도주"}
```

### 4.9 `POST /api/insights/to_wiki` body `{doc_key}`
위키 저장. **이번 범위에서는 stub**: 요약을 `out/insights_wiki/{doc_key}.md` 로 저장하고 경로 반환. (실제 L5/L6 ingest 연결은 후속.)
```json
{"ok":true,"path":"out/insights_wiki/....md","note":"위키 정식 ingest는 후속 연결"}
```

---

## 5. 화면 설계 (시각 — 최우선)

공통: 검정(#0a0a0a)·골드(#d4af37) 테마, 딸깍과 동일 토큰. 폰트 Segoe UI/Malgun Gothic.
**상단 공통 네비** 3개 페이지 전환(딸깍/섹터맵/인사이트) — 현재 페이지 골드 underline. (딸깍 index.html/market.html에도 같은 네비 추가하면 좋지만, 최소 insights.html엔 필수.)

### L0 메인 — "인사이트 1면"
```
┌───────────────────────────────────────────────────────────────┐
│  로또의 주식  [딸깍] [섹터맵] [● 인사이트]                       │  ← 공통 네비
├───────────────────────────────────────────────────────────────┤
│  📚 인사이트 라이브러리        2026-06-29                        │
│  크롤링된 모든 소스를, 이것만 보면 되게                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 🔍  종목으로 가로질러 찾기  (예: 삼성전자, HBM, 조선)      │  │  ← 히어로 검색
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌── 📺 유튜브 ──┐ ┌── 💬 텔레그램 ─┐ ┌── 📰 블로그·리포트 ─┐  │  ← 카테고리 3카드
│  │ 채널5·영상22  │ │ 채널17·519     │ │ 소스多·896          │  │
│  │ 오늘 +2 🆕    │ │ 오늘 +N        │ │ 오늘 +N             │  │
│  │ ───────────   │ │ ───────────    │ │ ───────────         │  │
│  │ ▸ AI버블 온다 │ │ ▸ 하나차이나   │ │ ▸ 하나증권 리포트   │  │  ← 핫 미리보기 3
│  │ ▸ 반도체 사이클│ │ ▸ 리포트요약   │ │ ▸ pokara61 글       │  │
│  │ ▸ 주도주 교체 │ │ ▸ 대신시황     │ │ ▸ ...               │  │
│  └───────────────┘ └────────────────┘ └─────────────────────┘  │
│                                                                 │
│  최근 추가된 인사이트                              (통합 피드)   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 📺 GODofIT  · AI 버블이 온다  · 발언18 · 6/29  [요약✓]    │  │  ← 카테고리색 띠
│  │ 💬 하나차이나 · 6/29 묶음 · 메시지12       · 6/29  [요약 ]  │  │
│  │ 📰 하나증권 · 반도체 재평가 · 핵심5       · 6/28  [요약✓]  │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```
- 카테고리 카드: hover 시 떠오름(translateY -2px), 클릭 → L1. 카드 좌측 색 띠(유튜브 보라/텔레 청록/리포트 골드).
- 통합 피드: 카테고리 아이콘+색 칩, [요약✓] = 캐시 있음(초록), [요약 ] = 없음(회색). 클릭 → 바로 L3.

### L1 소스 목록
```
홈 > 📺 유튜브                                    [🔍 검색]
─────────────────────────────────────────────────
채널            영상   발언   최근        
GODofIT          8     48    6/29   [열기→]
한균수의주식...   7     36    6/27   [열기→]
UP_CYCLE_STOCK   6     28    6/29   [열기→]
...
```
브레드크럼 항상 표시(클릭 가능). 행 hover 강조.

### L2 문서 목록
```
홈 > 📺 유튜브 > GODofIT
─────────────────────────────────────────────────
6/29  AI 버블이 온다, 우리의 대응 전략은?   발언18  [요약✓] [보기→]
6/22  반도체 사이클 어디까지 왔나            발언14  [요약 ] [보기→]
...
```

### L3 상세 — "이것만 보면 됨" (★ 핵심 화면)
```
홈 > 📺 유튜브 > GODofIT > AI 버블이 온다...        [▶영상] [🎬소재화] [📚위키]
┌─────────────────────────────────────────────────────────────┐
│ 🎯  주도주는 끝까지, 그러나 재고·EPS 꺾이면 탈출              │  ← TLDR 큰글씨
├─────────────────────────────────────────────────────────────┤
│ 💬 주린이 3줄                          📊 시장관: 강세 🟢      │
│  1. AI 주식 많이 올랐지만 실적 탄탄한...   "실적 기반이라 아직"│
│  2. 반도체 재고 쌓이면 그게 신호...                            │
│  3. 그전까진 주도주 끝까지...                                  │
├─────────────────────────────────────────────────────────────┤
│ 🏷 언급 종목                                                  │
│  [아마존 매수] [빅테크 매수] [HBM 중립] [삼성전자 ...]         │
├─────────────────────────────────────────────────────────────┤
│ 📺 발언 타임라인 (18)                                         │
│  ▶00:25 [강세] 금리 유동성 풀리고 AI 혁신...     [AI소프트웨어]│  ← 타임스탬프 클릭→유튜브
│  ▶00:43 [리스크] 닷컴 버블급 쏠림...             [주도주]      │
│  ...                                                          │
└─────────────────────────────────────────────────────────────┘
```
- 요약 없으면(`summary:null`): 상단에 "AI 요약 생성하기" 버튼 → `/api/insights/summarize` 호출, 로딩 스피너(시황부장 패턴), 완료 시 채워짐.
- [🎬소재화] → 모달/하단에 yt_plan 마크다운 렌더. [📚위키] → 저장 후 토스트.

### 검색 결과 (L0 히어로 검색 실행 시)
```
🔍 "삼성전자" — 12건
📺 UP_CYCLE_STOCK · ▶00:09 [매도] 삼성·하이닉스 변동성...  6/29
📰 하나증권 · 삼성전자 목표가 상향...                       6/28
...
```
각 행 클릭 → 해당 문서 L3 (가능하면 타임스탬프로).

---

## 6. 구현 분할 (Sonnet 에이전트)

의존: 프론트는 §4 API 계약에만 의존 → 백/프론트 **병렬 가능**(다른 파일).

- **에이전트 A (백엔드)**: `pipeline/atoms/doc_summary.py` 신규 + `db.py`에 `doc_summaries` 마이그레이션 + `server.py`에 §4.2~4.9 라우트 8개 + `/insights` HTML 라우트. atoms.db 쿼리는 본 스펙 §1 그룹핑 규칙 준수. claude 호출은 server.py `run_chat` 패턴 재사용.
- **에이전트 B (프론트)**: `dashboard/insights.html` 단일 파일 — §5 화면 전부. 검정·골드 토큰은 `dashboard/index.html` `:root` 그대로. fetch로 §4 API 호출. 4단계 SPA 전환 + 브레드크럼 + 검색 + L3 액션.

각 에이전트는 끝나고 **자기 산출물 self-check** (서버 import 에러 없는지 / HTML 단독 렌더되는지).

통합: 둘 끝나면 Opus가 서버 재기동 → 스모크 테스트(메인 로드, 드릴다운, 요약 1건 생성, 검색 1건).

---

## 7. 범위 밖 (후속)

- 공개 모드 HTML export (지금은 내부 뷰만, 데이터 노출 토글은 자리만)
- 위키 정식 L5/L6 ingest 연결 (지금은 md 저장 stub)
- 텔레그램 vector 검색 고도화
- 딸깍/섹터맵 페이지에 공통 네비 역삽입(선택)
