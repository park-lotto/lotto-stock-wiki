# 영상 제작소 6단계 SEO — 설계

- 날짜: 2026-07-17
- 트랙: `SEO` (`.tracks/SEO`, 브랜치 `track/SEO`)
- 대상: `shopping_shorts/static/produce.html` 6단계(`data-step="5"`) — 현재 `Phase 4 예정` 스텁
- 선행 설계: `docs/superpowers/specs/2026-07-13-영상제작-8단계-위저드-design.md`
  (§36에서 SEO를 "제목/설명/태그/해시태그, AI 전체생성, Gemini"로 예고. 원래 8단계였으나
  7단계로 축소되며 SEO가 7→6번으로 당겨짐)

---

## 1. 무엇을 만드나

제작소 위저드 6단계에서 **확정 대본으로 업로드용 메타데이터 일습**을 만든다.
산출물: 제목(+추천 5) · 설명 · 태그 20 · 해시태그 · 후킹 멘트 · 댓글 유도 ·
플랫폼별 CTA(유튜브 쇼츠 / 틱톡 / 쓰레드).

### 왜 지금 하나

7단계 중 5·6단계만 스텁이다. 대본→영상→음성→꾸미기까지 다 만들어놓고
업로드 문구는 사람이 매번 손으로 쓰고 있다.

### 경쟁사 대비 무엇이 다른가 (= 이 설계의 존재 이유)

벤치마킹한 경쟁사 화면은 **대본 → LLM → 문구**, 그게 전부다. 추천 제목 5개가 나오지만
왜 그 제목인지, 저 태그 20개가 실제로 검색에 걸리는지는 **아무도 모른다**. 검증 없는 생성기다.

우리는 유튜브 Data API 키 10개와 `youtube_client.py`를 이미 갖고 있다.
그래서 **생성한 키워드를 실제로 검색해서 재고, 그 측정치를 화면에 근거로 띄우고,
사장님이 그걸 보고 누르면 측정치가 프롬프트로 되돌아간다.**

| | 경쟁사 | 이 설계 |
|---|---|---|
| 근거 | 없음 (5개 나열) | 제목마다 "왜 이 제목인지" 한 줄 + 키워드 배지 |
| 검증 | 없음 | 유튜브 실측 — 조회수 중앙값 + **소형채널 침투율** |
| 플랫폼 | CTA 문구만 분리, 제목·해시태그는 하나를 돌려씀 | 제목·해시태그·CTA 전부 플랫폼별 |
| 수정 | 전체 재생성 | 카드별 🔒 잠금 + 부분 재생성(측정치 되먹임) |

---

## 2. 재료 — 있는 것과 없는 것

### 있는 것

`Store.get_mix_job(job_id)` 반환 dict (`store.py:1237-1253`) 하나로 다 꺼낸다:

| 필드 | 내용 | 쓰임 |
|---|---|---|
| `given_script` | 확정 대본 전문 | ★ 주재료 |
| `script_structure` | `structure_analyze.py:21-60` 스키마 — `product_category`(홈템/레시피/가전/뷰티/기타) · `hook_type` · `hook_line` · `appeal` · `one_line_why` · `tone` · `storyline` · `twist` | ★ 제목·태그 1급 재료 |
| `headcopy` | `{text,...}` 화면 헤드카피 | ★ 제목 후보와 직결 |
| `edit_plan.beats[]` | `{narration, role, beat_idx}` | 설명 본문 |
| `target_seconds` · `urls` | | 보조 |

프론트 전역: `HANDOFF[]` = `{url, shortcode, name, thumbnail, caption, ...}` (`produce.html:1282`)
→ **소스 릴스의 캡션 원문 + 해시태그**. 실제로 터진 영상의 문구다.
`PM_CATEGORY` (`produce.html:1362`) — fx가 이미 이 패턴을 쓴다(`produce.html:525`).

### 없는 것 (조사로 확인 — 넘겨짚지 말 것)

- **유튜브 조회수·원본 제목·태그가 위키에 없다.** `youtube_client.py:65`가 `part:"snippet"`만
  요청해 **tags 필드는 받아오지도 않는다**. 제목·설명은 수집하나(`:77-83`) `script_wiki`로 안 넘어간다.
- 랭킹(`ranking.py`)·발굴(`discovery.py`, `lens_discover.py`)에 제목·태그 분석 코드 **0건**.
- **썸네일 없음** — 5단계도 같은 스텁. 있는 건 미리보기 포스터뿐(`app.py:2001` `/api/produce/mix/poster/{job_id}`).
- 위키 항목(`store.py:992-999`)의 지표는 `followers`/`comments`/`density`뿐 (인스타 기준).

→ **SEO는 그린필드다.** "레퍼런스 실데이터를 근거로"는 저장된 데이터로는 불가능하고,
**생성 시점에 유튜브를 직접 조회**해서 확보한다(§4).

---

## 3. 아키텍처 — 생성 → 측정 → 되먹임

```
[Pass 1] 생성 (Gemini)          seo_generate.generate()
   in : given_script + script_structure + headcopy.text + HANDOFF[].caption
   out: 제목5(각각 why + seed_keywords) · 설명 · 태그20 · 해시태그
        · 후킹 · 댓글유도 · CTA 3종
   비용: Gemini 1회 (key_vault 공유풀)

[Pass 2] 측정 (YouTube Data API)   seo_probe.probe_keywords()
   in : Pass 1의 seed_keywords 중 상위 6개
   out: 키워드마다 {views_median, small_ratio, top_titles[3], verdict}
   비용: 키워드당 102유닛 → 6개 = 612유닛 (캐시 적중 시 0)

[Pass 3] 되먹임 — 버튼 눌렀을 때만
   측정치를 프롬프트에 도로 넣고 only='title' | 'tags' | … 로 부분 재생성
   🔒 잠긴 카드는 프롬프트에 "이건 확정, 건드리지 마라"로 들어감
```

Pass 3을 자동 강제하지 않는 것이 핵심이다. 측정치를 배지로 붙이는 건 코드가 하고,
**재생성은 사장님이 데이터를 보고 판단해 누를 때만** 돈다. 그래서 "근거 표시"와
"부분 재생성"이 별개 기능이 아니라 하나의 루프가 된다.

---

## 4. 측정 설계 — `seo_probe.py` (신설)

### 왜 `search_shorts()`를 그대로 못 쓰나

`youtube_client.search_shorts()` (`:87`)는 **발굴 전용으로 굳어 있다**:

- `_search_page`가 `pageInfo.totalResults`를 **버린다**(`:71-84`) → "검색결과 수"를 못 받음.
  (유튜브의 totalResults는 원래 부정확한 추정치라 근거로도 약하다 — 안 쓴다)
- `order:"viewCount"` + `publishedAfter` + `videoDuration:"short"` 고정 — 발굴엔 맞고 측정엔 과함
- 반환이 키워드별로 안 갈린다(`raw`에 전부 flat하게 extend, `:113-115`)
  → 키워드별 지표를 못 낸다

그래서 **읽기 전용 신규 모듈** `shopping_shorts/seo_probe.py`를 만든다.
`youtube_client.py`는 발굴이 쓰는 코드라 **건드리지 않는다**(회귀 위험).
`_LANG_REGION`·`_title_lang_ok`·`_stats` 같은 순수 헬퍼만 import해 재사용한다.

### 지표 — 조회수만으로는 부족하다

조회수 중앙값만 보면 **"수요는 있는데 대형 채널이 다 먹은 키워드"와 "작은 채널도 뚫리는
키워드"가 구분이 안 된다.** 우리한테 필요한 건 후자다.

응답에 `channel_id`가 이미 있고(`youtube_client.py:78`) `channels.list(part=statistics)`는
**1유닛**이다. 그래서 잰다:

```
probe_keyword(kw) →
  1. search.list   (100u)  q=kw, type=video, videoDuration=short,
                           order=viewCount, publishedAfter=최근 90일,
                           regionCode=KR, relevanceLanguage=ko, maxResults=20
                           → _title_lang_ok로 외국영상 제거
  2. videos.list   (  1u)  part=statistics  → views
  3. channels.list (  1u)  part=statistics  → subscriberCount
  = 102유닛/키워드

  반환 {
    keyword, sample_n,
    views_median,          # 수요: 이 키워드 상위 쇼츠가 실제로 얼마나 보이나
    small_ratio,           # 침투: 상위 중 구독자 1만 미만 채널 비율
    top_titles[3],         # 사장님이 눈으로 확인할 실물
    verdict,               # 아래 판정표
    checked_at
  }
```

### 판정표

| verdict | 조건 | 화면 | 뜻 |
|---|---|---|---|
| `blue` | `views_median ≥ 10만` **AND** `small_ratio ≥ 0.3` | 🟦 뚫린다 | 수요 있고 작은 채널도 상위권 |
| `red` | `views_median ≥ 10만` **AND** `small_ratio < 0.3` | 🟥 레드오션 | 수요는 있으나 대형 채널이 독식 |
| `dead` | `views_median < 10만` | ⬜ 수요 낮음 | 검색해도 사람이 안 봄 |
| `unknown` | 샘플 3건 미만 / API 실패 / 키 소진 | – 미측정 | **거짓 근거를 만들지 않는다** |

문턱값(10만·0.3·90일·20건)은 `seo_probe.py` 모듈 상수. 실측 후 튜닝 대상이며,
**첫 구현에서 이 숫자가 맞다고 주장하지 않는다** — 라이브에서 사장님이 보고 조정한다.

### 쿼터 방어 (필수)

`search.list`는 **호출당 100유닛**이고 키 10개 = 하루 10만 유닛인데,
**발굴 파이프라인(`service.py:14`)이 같은 `YOUTUBE_API_KEYS` 풀을 이미 쓰고 있다.**
태그 20개를 전부 재면 생성 1회에 2,000유닛이 날아간다.

1. **키워드 6개 상한** — `_MAX_PROBE = 6` 모듈 상수. Pass 1이 준 seed_keywords 앞 6개만.
2. **캐시 테이블 `seo_keyword_stats`** — TTL 7일. 같은 키워드는 재측정 없이 공짜.
   홈템/뷰티처럼 카테고리가 겹치면 적중률이 높다.
3. **키 소진 시 우아하게 꺼짐** — 403이면 `verdict='unknown'`으로 반환하고
   **생성 자체는 성공시킨다**. SEO 문구가 측정보다 우선이다.
4. **토큰 로테이션** — `search_shorts`의 403 로테이션 로직(`:106-112`)과 같은 방식.

---

## 5. 저장

### `mix_jobs.seo_json` (신설 컬럼)

```json
{
  "title": "...",
  "title_candidates": [{"text": "...", "why": "...", "keywords": ["..."]}],
  "description": "...",
  "tags": ["...x20"],
  "hashtags": {"youtube": ["..."], "tiktok": ["..."], "threads": ["..."]},
  "hook_line": "...",
  "comment_bait": "...",
  "cta": {"youtube": "...", "tiktok": "...", "threads": "..."},
  "keyword_stats": [{"keyword": "...", "views_median": 0, "small_ratio": 0.0,
                     "top_titles": ["..."], "verdict": "blue|red|dead|unknown"}],
  "locked": {"title": false, "description": false, "tags": false,
             "hashtags": false, "hook": false, "cta": false},
  "generated_at": "ISO8601"
}
```

### ⚠️ `store.py` 3곳을 전부 건드려야 한다

`update_mix_job`은 **화이트리스트 방식**이라 한 곳이라도 빠뜨리면
**에러도 없이 조용히 무시된다.** 코드가 직접 경고해둔 함정이다
(`store.py:1260-1262`: *"여기 없으면 update_mix_job(preview_status=...)이 에러도 없이
조용히 무시된다 — 이 화이트리스트가 이 배선의 함정"*). 썸네일 트랙이 이미 여기 데였다.

1. **마이그레이션** `store.py:388-403` 리스트에 `("seo_json", "TEXT")` 추가
   (`ALTER TABLE ... ADD COLUMN`, 중복은 `OperationalError` pass — `:405-408`)
2. **읽기** `get_mix_job` — `:1227-1232` SELECT 컬럼 문자열 + `:1237-1253` 반환 dict 매핑.
   **인덱스 기반이라 반드시 끝에 추가**한다.
   ⚠️ 모션효과가 fx를 row19-21에 끼워 preview가 22-24로 밀린 전례가 있다
   → **착수 전 `git fetch origin && git merge origin/main`으로 최신 row 인덱스를 확인**한다.
3. **쓰기** `update_mix_job` — `:1270-1281` 패턴:
   ```python
   if "seo" in fields:
       cols.append("seo_json=?")
       vals.append(json.dumps(fields["seo"], ensure_ascii=False) if fields["seo"] else None)
   ```

### `seo_keyword_stats` (신설 테이블)

```sql
CREATE TABLE IF NOT EXISTS seo_keyword_stats (
  keyword TEXT NOT NULL, region TEXT NOT NULL DEFAULT 'KR',
  views_median INTEGER, small_ratio REAL, sample_n INTEGER,
  top_titles_json TEXT, verdict TEXT, checked_at TEXT NOT NULL,
  PRIMARY KEY (keyword, region)
)
```
job에 매이지 않는 **전역 캐시**다 — 다른 영상이 같은 키워드를 재면 공짜.

### ⚠️ STATE에 두면 안 된다

`const STATE` (`produce.html:1118`)는 **휘발성 미러**이고
`saveWork()` (`:1285-1286`)가 `sessionStorage`에 싣는 건
`{handoff, script, script_src_idx, script_from_wiki}`뿐이다.
**`STATE.seo`는 거기 없다 → 새로고침하면 날아간다.** 서버 저장이 유일한 진실이다.

---

## 6. 플랫폼 분리

| | 유튜브 쇼츠 | 틱톡 | 쓰레드 |
|---|---|---|---|
| 제목/캡션 | 100자, **검색 키워드를 앞쪽에** | 짧게 | 대화체 |
| 태그 | 500자 20개 (검색에 반영) | 없음 | 없음 |
| 해시태그 | 3~5개 | 3~5개 | 최소 |
| CTA | 설명란 링크 유도 | 댓글 유도형 | 되묻는 문장 |

인스타는 **범위 밖**(사장님이 플랫폼에서 제외).

경쟁사는 CTA만 나누고 제목·해시태그는 하나를 돌려쓴다. 유튜브 태그 20개를 틱톡에
그대로 붙이는 건 무의미하다. 여기를 실제로 가른다.

---

## 7. 배선

### 신설 모듈

**`shopping_shorts/seo_generate.py`** — `script_generate.py:20-47` 패턴을 그대로 복제:

```python
from pipeline.atoms import key_vault
_MODEL = comment_gen._MODEL          # gemini-3.1-flash-lite (comment_gen.py:18)
_GEN_GROUP = "general"
# _PROMPT / _SCHEMA 모듈 상수 (프롬프트 파일 없는 게 이 저장소 관례)
```

**키풀을 `comment_gen` 전용키로 쓰면 안 된다.** `script_generate.py:20-25` 주석이 명시:
> "produce 대본생성(우리믹스)은 comment_gen 전용키(1개, 쉽게 소진) 대신 key_vault
> 공유풀을 캐스케이드로 쓴다 — 배치된 예비키(general→ingest→embed→briefing)를 전부
> 활용해 소진 사고를 피한다(2026-07-13)."

SEO도 사장님이 버튼 누르고 기다리는 대화형이라 소진에 똑같이 취약하다.
`response_schema`로 JSON 강제(`script_generate.py:37`, `structure_analyze.py:116` 관례).
실패 분기도 동일: `is_daily_exhausted_error`/`is_account_disabled_error` → `mark_exhausted` 후 다음 키 /
`is_quota_error` → continue / 그 외 → 빈값.

**`shopping_shorts/seo_probe.py`** — §4. 읽기 전용, `youtube_client.py` 무수정.

### 엔드포인트 (`app.py` 단일 파일 — 라우터 분리 없음)

```python
POST /api/produce/seo/generate
  body: {job_id, only?: 'title'|'description'|'tags'|'hashtags'|'hook'|'cta', locked?: {}}
  → {seo: {...}}    # app.py:2427 /api/produce/fx/suggest 동형
```
- 카테고리 폴백 체인은 fx와 동일: `body → script_structure.product_category → ""`
- `only` 없으면 전체 생성(측정 포함). `only` 있으면 그 카드만, 🔒 잠긴 건 보존.
- **무과금** — fx/suggest처럼 포인트 차감 없음(DB 기록도 생성 시점엔 안 함)

저장은 **새 엔드포인트를 만들지 않는다.** `POST /api/produce/mix/settings`
(`app.py:1948-1966`)에 `seo` 필드를 한 줄 추가:
```python
if "seo" in body: fields["seo"] = body.get("seo")
```

### 프론트 (`produce.html`)

- `showPanel()` (`:460-469`)에 `if(cur===5) initSeo();` — 단계 진입 훅의 규약
  (기존: `cur===1 refreshSub` / `cur===2 loadTtsBeats` / `cur===3 initHeadcopy` / `cur===6 refreshFinal`)
- 게이트는 **cur===0 전용**이라 SEO는 대상 아님(`jump`/`go` 가드 `:1101-1115`)
- fetch는 `fxSuggest()` (`:520-535`) 패턴

### 화면

세로 카드 스택. 각 카드에 🔒(잠금) · ↻(이 카드만 재생성) · 복사:

1. **제목** — 확정 input(100자 카운터) / 추천 5개 = `제목 · 왜 이 제목인지 한 줄 · 키워드 배지`
2. **설명** — textarea + 글자수
3. **태그(20)** — 칩마다 배지, 입력+추가/삭제
4. **해시태그** — 플랫폼 탭(유튜브/틱톡/쓰레드)
5. **후킹 멘트 · 댓글 유도**
6. **플랫폼 CTA** — 유튜브 / 틱톡 / 쓰레드
7. 상단 — `AI로 전체 생성` · `유튜브 전체 복사`

**키워드 배지**는 `keyword_stats`를 그대로 보여준다:
`🟦 뚫린다 · 상위 조회수 32만 · 소형채널 40%` / `🟥 레드오션 · 상위 조회수 180만 · 소형채널 5%` /
`⬜ 수요 낮음` / `– 미측정`. 호버 시 `top_titles[3]` — **사장님이 실물로 검증할 수 있게.**

---

## 8. 테스트

### ⚠️ produce.html을 건드릴 때의 함정

`tests/test_produce_preview_gate.py`가 produce.html **실소스를 앵커 문자열로 잘라 Node로 실행**한다(`:26-34`).
앵커가 소스에 그대로 없으면 `assert s != -1, "START 못 찾음"`으로 죽는다:
- `"function jump(i){"` → `"// ── 1단계 대본: 3모드"`
- `"async function startProduceMix(){"` → `"async function pollMix(){"`
- `"async function loadMixReview(){"` → `"// ── 3단계 자막제거"`

또 하네스가 `var STEPS = [...]`를 복제한다(`:63`).
→ **앵커 구간과 STEPS 배열은 건드리지 않는다.** SEO 코드는 새 구간에 넣는다.

### 새 테스트

| 대상 | 검증 |
|---|---|
| `store.py` | `seo_json` 왕복(저장→읽기). **뮤테이션**: 화이트리스트에서 `seo` 분기 제거 → 반드시 죽어야 함(이게 진짜 자물쇠) |
| `seo_probe` | 판정표 4분기(blue/red/dead/unknown) / 샘플 3건 미만 → `unknown` / 403 → `unknown`이되 예외 안 던짐 / 캐시 TTL 7일 경계 / `_MAX_PROBE=6` 상한 |
| `seo_generate` | 키 소진 → 다음 키 캐스케이드 / 스키마 위반 응답 → 빈값 / 🔒 잠긴 필드가 프롬프트에 들어가나 |
| `app.py` | `/api/produce/seo/generate` 404(없는 job) / `only` 분기 / `mix/settings`에 `seo` 저장 |

### 🚨 진짜 합격 기준 — 테스트로는 못 잡는다

- **유튜브 실호출 1회 관측**: 실제 키워드로 `probe_keyword`를 태워
  `views_median`·`small_ratio`가 **말이 되는 값인지 눈으로 본다.**
  (모킹된 테스트는 판정 로직만 보지, 유튜브가 실제로 뭘 주는지는 아무도 안 봤다)
- **Gemini 실호출 1회 관측**: 뽑힌 제목·태그가 **한국어로 쓸 만한지.**
  스키마 통과 ≠ 쓸 만함.
- **라이브 화면**: 제작소 1→6단계를 실제로 타고 들어가 `initSeo()`가 도는지,
  새로고침 후 SEO가 살아있는지(= 서버 저장이 진짜 됐는지).

이 저장소가 반복해 데인 패턴이다 — 보이스 트랙의 "카드에서 듣는 소리 ≠ 실제 합성될 소리".
**화면·실호출로 확인 안 하면 "값은 맞는데 사용자가 보는 건 딴 것"이 남는다.**

---

## 9. 범위 밖 (하지 않는다)

- **`youtube_client.py` 수정** — 발굴이 쓰는 코드. `seo_probe.py`로 분리해 회귀 위험을 없앤다.
- **유튜브 원본 메타 수집 파이프라인** — tags·statistics를 위키에 쌓는 건 별건.
  (이번엔 생성 시점 실시간 조회로 해결)
- **썸네일 연동** — 5단계가 아직 스텁. 그 트랙이 끝난 뒤 별건.
- **인스타 CTA** — 플랫폼에서 제외됨.
- **성과 피드백 루프** — 업로드 후 실제 조회수를 되먹여 학습. 업로드 자동화가 없어 불가.
- **포인트 과금** — 무과금으로 시작.
- **`totalResults` 기반 경쟁도** — 유튜브 추정치가 부정확해 근거로 못 씀.

---

## 10. 열린 질문 / 리스크

| | 리스크 | 대응 |
|---|---|---|
| 1 | **문턱값(10만·0.3)이 근거 없다** | 첫 구현은 모듈 상수로 두고, 실측 후 사장님이 보고 조정. 맞다고 주장하지 않는다 |
| 2 | **쿼터를 발굴과 나눠 쓴다** — 하루 10만 유닛 | 6개 상한 + 7일 캐시. 영상 20편/일 = 12,240유닛(12%). 소진 시 `unknown`으로 우아하게 꺼짐 |
| 3 | `store.py`·`produce.html`을 **3개 트랙이 동시 편집** 중(썸네일·대본믹스통합·장면라이브러리) | 태스크마다 `git fetch origin && git merge origin/main`으로 짧게 따라붙는다. 쌓으면 병합 지옥 |
| 4 | 소스 릴스 캡션이 **인스타 문법** — 유튜브 검색과 다름 | 프롬프트에 "인스타 캡션은 톤 참고용, 유튜브 키워드는 실측으로 검증" 명시 |
| 5 | `small_ratio`의 1만 구독 문턱이 카테고리마다 다를 수 있음 | 상수. 실측 후 조정 |
