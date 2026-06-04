---
name: yt-trend
description: YouTube 급상승 키워드 기반 영상 소재 발굴 → 대본 초안 자동 생성 파이프라인. 5단계: YouTube Top20 수집 → Gemini 딥리서치 → 자막 분석 → 소재 추출 → 대본 초안 S1~S8
metadata:
  tags: youtube, trend, 소재발굴, 파이프라인, gemini
---

# yt-trend

## 언제 실행하나

"오늘 유튜브 트렌드로 영상 소재 뽑아줘" / "YT 트렌드 파이프라인" / "급상승 키워드로 영상 기획해줘"

## 환경 변수 확인

실행 전 아래 두 변수가 설정되어 있는지 확인한다. 없으면 즉시 중단하고 설정 방법 안내.

- `YOUTUBE_API_KEY` — YouTube Data API v3
- `GEMINI_API_KEY` — Gemini MCP + Python 스크립트 공용

---

## Step 1 — YouTube API Top 20 수집

```bash
python scripts/yt_trend/step1_fetch.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step1_videos.json` 존재, 1개 이상
이미 파일 존재: 자동 skip

---

## Step 2 — Gemini MCP 딥리서치

step1_videos.json 을 읽어 제목 상위 10개 추출 후 Gemini MCP 호출.

**입력 준비:**

`raw/yt_trend/{날짜}/step1_videos.json` 에서 title 필드 상위 10개를 추출해 아래 프롬프트에 삽입.

**Gemini MCP 프롬프트:**

```
다음은 오늘 한국 주식 YouTube에서 급상승 중인 영상 제목들이다.

{제목 목록 — 각 줄에 번호. 제목}

분석 요청:
1. 공통적으로 부각되는 주제/테마는 무엇인가?
2. 왜 오늘 이 키워드들이 동시에 급상승하는가? (시장 배경, 이슈, 섹터 흐름)
3. 이 트렌드는 며칠이나 지속될 것으로 보이나? 근거는?
4. 투자자들이 가장 궁금해하는 핵심 질문은 무엇인가?

한국어로 1~2페이지 분량으로 작성.
```

**Gemini MCP 도구:** `mcp__gemini__*` 중 딥리서치/생성 도구 사용

**저장:** Gemini 응답 전체를 `raw/yt_trend/{날짜}/step2_research.md` 에 저장 (Write 도구)

이미 파일 존재: skip

---

## Step 3 — 자막 추출 + Gemini 영상 분석

```bash
python scripts/yt_trend/step3_analyze.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step3_analysis.json` 존재, 2개 이상 분석 결과
이미 파일 존재: 자동 skip

---

## Step 4 — 소재 추출

```bash
python scripts/yt_trend/step4_extract.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step4_ideas.json` 존재, 3개 소재
이미 파일 존재: 자동 skip

---

## Step 5 — 대본 초안 (Claude 직접 작성)

`raw/yt_trend/{날짜}/step4_ideas.json` 에서 rank 1 소재를 읽어 아래 형식으로 대본 초안 작성.

**70/20/10 원칙 엄수:**
- S1~S6: 순수 정보 (서비스명 일절 금지)
- S7: 간접 노출 ("나는 이렇게 한다" 방법론)
- S8: CTA 단 한 번 (서비스 언급 유일 허용 씬)

**출력 형식:**

```markdown
# {소재 제목}
> 생성일: {날짜} | 출처: yt-trend 파이프라인

## 제목 후보 5개
1. 
2. 
3. 
4. 
5. 

## 썸네일 컨셉
- 메인 텍스트: 
- 배경/이미지: 
- 서브 텍스트: 

## 대본

### S1 — 훅 (0~30초)
[30초 안에 "왜 봐야 하나"를 증명하는 충격/질문/역설 오프닝]

### S2 — 문제 제기 (30초~1:30)
[시청자가 공감하는 문제 상황 + 오늘 영상의 핵심 약속]

### S3 — 핵심 인사이트 1 (1:30~3:00)
[첫 번째 핵심 포인트. 데이터·사례 포함]

### S4 — 핵심 인사이트 2 (3:00~5:00)
[두 번째 핵심 포인트. 더 깊게]

### S5 — 핵심 인사이트 3 (5:00~7:00)
[세 번째 핵심 포인트. 실전 적용 방법]

### S6 — 반론/검증 (7:00~8:30)
[예상 반론 해소 + 리스크 언급으로 신뢰 구축]

### S7 — 결론 (8:30~9:30)
["나는 이렇게 한다" 방법론으로 간접 노출]

### S8 — CTA (9:30~10:00)
[서비스 언급 유일 허용. 구독+알림 요청]
```

완성된 대본을 `raw/yt_trend/{날짜}/step5_draft.md` 에 저장 (Write 도구).

---

## 오류 처리

| 상황 | 대응 |
|------|------|
| API 키 없음 | 즉시 중단. 설정 방법 안내 |
| Step1 결과 0개 | 중단. 키워드 또는 API 할당량 확인 요청 |
| Step3 자막 2개 미만 | 경고 후 중단 |
| Step2 MCP 오류 | 오류 메시지 출력. 수동 리서치 후 step2_research.md 직접 작성 요청 |
| Step4 JSON 파싱 실패 | raw 응답 출력 후 중단 |

---

## 재실행 안내

각 step 출력 파일이 이미 존재하면 해당 단계를 자동 skip한다.

특정 단계부터 재실행하려면:
```powershell
# step3부터 재실행: step3/4/5 파일 삭제 후 재실행
Remove-Item raw\yt_trend\{날짜}\step3_analysis.json -ErrorAction SilentlyContinue
Remove-Item raw\yt_trend\{날짜}\step4_ideas.json -ErrorAction SilentlyContinue
Remove-Item raw\yt_trend\{날짜}\step5_draft.md -ErrorAction SilentlyContinue
```
