---
name: yt-content-research
description: YouTube 영상 소재 탐색 & 주제 선정. 핫 이슈 정량 스캔 → YouTube 조회수 실사 → 패턴 분석 → 주제·각도 확정 → Gemini 브리프 생성. yt-gemini-pipeline 직전에 실행.
metadata:
  tags: youtube, 소재, 리서치, 기획, 조회수, 트렌드
---

# yt-content-research — 소재 탐색 & 주제 선정

## 핵심 원칙

**3가지 오염 금지**

1. **위키 오염 금지** — wiki는 마지막 STEP 6에서만. 기존 관점에 갇히지 않는다.
2. **대화 오염 금지** — 사용자가 언급한 키워드를 시작점으로 쓰지 않는다.
3. **선입견 오염 금지** — Claude 기억 기반 "요즘 핫한 것 같다" 금지. 수치가 결정한다.

---

## 명령어

`/소재찾자` / `/소재찾기` / "소재 찾자"

---

## 전체 흐름

```
STEP 0  브레인스토밍 여부 확인
    ↓
STEP 1  핫 이슈 스캔 (정량 데이터 기반)
    ↓
STEP 2  YouTube 조회수 실사 (gstack:browse)
    ↓
STEP 3  터지는 패턴 분석
    ↓
STEP 4  오염 체크 (전부 통과해야 진행)
    ↓
STEP 5  주제 + 각도 확정 → Gemini 브리프 생성
    ↓
STEP 6  wiki 데이터 연결 (마지막)
    ↓
→ yt-gemini-pipeline
```

---

## STEP 0 — 브레인스토밍 여부 확인

시작 전 반드시 묻는다:

> "방향이 아직 없으면 브레인스토밍 먼저 할게요.
> 방향이 있으면 바로 소재 탐색 들어갑니다."

| 응답 | 처리 |
|------|------|
| 방향 없음 | `superpowers:brainstorming` 실행 → 완료 후 STEP 1 |
| 방향 있음 | STEP 1로 바로 이동 |

---

## STEP 1 — 핫 이슈 스캔

**목표**: 지금 + D+1~7 안에 주식시장을 움직일 이슈를 수치로 확인.
Claude 기억 금지. 검색 결과 수치로만 판단.

### 1-A. 임박 이벤트 스캔 (D+1 ~ D+7)

```
WebSearch: "주식 주요 일정 이번주 {날짜}"
WebSearch: "FOMC 빅테크 실적 한국 수출 발표 {월} 일정"
WebSearch: "코스피 주요 이슈 {날짜} 예정"
```

→ 출력: 날짜 | 이벤트 | 관련 섹터 | 예상 영향 표

### 1-B. 현재 관심도 정량 측정

후보 이슈마다 3가지 수치 확인:

**① 뉴스 노출량**
```
WebSearch: "{키워드} 주식 뉴스" — 결과 수 + 최신 날짜
WebSearch: "{키워드} site:naver.com" — 네이버 뉴스 밀도
```

**② 검색량 트렌드 (Fetch MCP)**
```
Fetch: https://datalab.naver.com/keyword.naver?query={키워드}
→ 최근 7일 검색 트렌드 수치
```

**③ 커뮤니티 반응**
```
WebSearch: "{키워드} 주식 갤러리 OR 종토방 OR 카페" — 언급 밀도
gstack:browse → 실시간 커뮤니티 확인
```

### 1-C. 이슈 온도 판정

| 온도 | 기준 | 처리 |
|------|------|------|
| 🔴 급등 | 오늘/어제 뉴스 다수 + 검색량 급증 + 커뮤니티 활발 | 지금 바로 진행 |
| 🟠 상승 | 2~4일 내 이슈 + 검색량 유지 | D+1~2 업로드 목표로 진행 |
| 🟡 예열 | D+3~7 임박 이벤트 | 미리 준비, 이벤트 당일 업로드 |
| ⚫ 식음 | 1주일+ 뉴스 없음 + 검색량 하락 | 폐기 → 새 이슈 탐색 |

🔴🟠만 STEP 2 진행. 🟡는 예약 등록. ⚫는 폐기.

---

## STEP 2 — YouTube 조회수 실사

WebSearch 요약 말고 **실제 숫자** 직접 확인.

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"
$B goto "https://www.youtube.com/results?search_query={키워드}&sp=CAMSAhAB"
sleep 3
$B js "
const results = [];
document.querySelectorAll('ytd-video-renderer').forEach(el => {
  const title = el.querySelector('#video-title')?.textContent?.trim();
  const meta = el.querySelectorAll('.inline-metadata-item');
  const views = [...meta].find(m => m.textContent.includes('회'))?.textContent?.trim();
  const ago = [...meta].find(m => m.textContent.match(/\d+.*(전|시간)/))?.textContent?.trim();
  const channel = el.querySelector('.ytd-channel-name a')?.textContent?.trim();
  if(title) results.push({title: title.slice(0,60), views: views||'?', ago: ago||'?', channel: (channel||'').slice(0,20)});
});
JSON.stringify(results.slice(0,15), null, 1)
"
```

수집 기준: 최근 7일 이내 + 조회수 5만 이상 (또는 24시간 내 1만 이상)

---

## STEP 3 — 터지는 패턴 분석

수집된 영상 제목 → 4가지 패턴 분류:

| 패턴 | 감정 | 공식 |
|------|------|------|
| **경고+기대** | "사고 싶은데 물리면?" | 기대 → 경고 → "그럼 어떻게?" |
| **FOMO 후회** | "나만 손해볼 것 같다" | 숫자 + 비교 + "안 사면 후회" |
| **비밀 공개** | "남들 모르는 거 알고 싶다" | "숨겨진" / "아무도 모르는" |
| **속보 즉각성** | "지금 바로 따라가고 싶다" | "방금" / "지금 막" |

---

## STEP 4 — 오염 체크 (4가지 전부 통과해야 진행)

> **① 대화 오염**: 이 소재가 대화에서 나왔는가? → YES = 탈락

> **② 서비스 연결**: 내 서비스·시스템을 보여주기 위한 주제인가?
> → YES = 탈락. 서비스 없이 성립하는 각도로 재정의.
> 실패: "금양 상폐" → 투경 시스템 연결 (시스템 없으면 성립 안 됨)
> 통과: "금양 상폐" → "2차전지 버블은 왜 터졌나" (시스템 없이 성립)

> **③ 레퍼런스 이유 일치**: 레퍼런스 영상이 터진 이유가 내 버전과 같은가?
> → 서비스가 들어오면 이유가 달라진다 = 탈락

> **④ 최종**: "서비스 없이 이 영상이 성립하는가?"
> → NO면 각도 변경

---

## STEP 5 — 주제 + 각도 확정 → Gemini 브리프 생성

오염 체크 통과 후 확정:

```
선택 패턴: {패턴명}
주제: {키워드}
각도: {레퍼런스에서 뽑은 차별화 각도}
훅 초안 3개:
  1. {훅1}
  2. {훅2}
  3. {훅3}
업로드 데드라인: {날짜} — {이유}
```

→ GEMINI INPUT BRIEF 포맷으로 변환 (yt-gemini-pipeline STEP 1 포맷)

---

## STEP 6 — wiki 데이터 연결 (마지막)

주제·각도 확정 후에만 참조:

```
wiki/L5_섹터/{섹터}/sector_{섹터}.md  → 섹터 온도, 대장주
wiki/L5_섹터/{섹터}/stock/stock_{종목}.md → 수급, 컨센
wiki/log.md → 최근 ingest 내용
```

없는 데이터는 "(데이터 없음)" 표시.

---

## 출력 파일

`channel/yt/brief_{주제}_{날짜}.md` — Gemini에 넘길 브리프 포함

---

## 다음 단계

→ `yt-gemini-pipeline` (Claude 브리프 → Gemini 딥리서치 + 스토리 + 대본)
