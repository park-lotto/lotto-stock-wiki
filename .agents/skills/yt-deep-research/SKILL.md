---
name: yt-deep-research
description: Use after a video topic is confirmed and before scene structure is written — researches the topic deeply by collecting YouTube videos, articles, studies, comparisons, and real examples to fill scripts with substance rather than generic content.
metadata:
  tags: youtube, 리서치, 대본, 퀄리티, 소재, 기사, 데이터
---

# yt-deep-research — 영상 주제 심층 리서치

## 핵심 원칙

**대본 퀄리티는 리서치 깊이에서 결정된다.**

"다들 아는 얘기"로 가득 찬 대본은 조회수가 안 나온다.
이 스킬의 목표: 주제에 대해 아무도 몰랐던 데이터·사례·각도를 찾아내는 것.

**이 스킬이 없으면 대본이 이렇게 된다:**
- "장기투자 좋다" (다 아는 얘기)
- "심리 관리 중요하다" (다 아는 얘기)
- "수급을 봐라" (결론만 있고 왜인지 없음)

## 명령어

- `/리서치 [주제]` / "리서치해줘" / `/yt-deep-research`
- yt-content-research + yt-planner 완료 후 → yt-script-writer 전에 반드시 실행

---

## STEP 1 — YouTube 유사 영상 수집 (gstack:browse)

같은 주제로 조회수 높은 영상 10~15개를 수집한다.

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"

# 주제 키워드로 조회수순 검색
$B goto "https://www.youtube.com/results?search_query={주제키워드}&sp=CAMSAhAB"
sleep 3

# 제목 + 조회수 + 날짜 수집
$B js "
const r=[];
document.querySelectorAll('ytd-video-renderer').forEach(el=>{
  const t=el.querySelector('#video-title')?.textContent?.trim();
  const meta=el.querySelectorAll('.inline-metadata-item');
  const v=[...meta].find(m=>m.textContent.includes('회'))?.textContent?.trim();
  const d=[...meta].find(m=>m.textContent.match(/\d+.*(전|시간|일|주|개월)/))?.textContent?.trim();
  const ch=el.querySelector('.ytd-channel-name a')?.textContent?.trim();
  if(t&&v)r.push({t:t.slice(0,60),v,d,ch});
});
JSON.stringify(r.slice(0,15),null,1)
"
```

**수집 후 판단:**
- 조회수 TOP 5 → 다들 어떤 각도로 다루는가
- 조회수 낮은 영상 → 왜 안 터졌는가 (피해야 할 각도)

---

## STEP 2 — 고조회수 영상 내용 분석

TOP 3~5 영상의 설명·댓글·자막을 읽어서 **주요 논점과 약점**을 파악한다.

```bash
# 영상 설명 읽기
$B goto "{영상 URL}"
sleep 2
$B text  # 설명란 + 자막 읽기

# 댓글 상위 10개 (시청자가 원하는 게 뭔지 파악)
$B js "Array.from(document.querySelectorAll('ytd-comment-thread-renderer')).slice(0,10).map(el=>({
  text: el.querySelector('#content-text')?.textContent?.trim()?.slice(0,100),
  likes: el.querySelector('#vote-count-middle')?.textContent?.trim()
})).filter(c=>c.text)"
```

**분석 목표:**
- 다들 하는 얘기가 뭔가 → 이건 피하거나 더 깊이 들어간다
- 댓글에서 시청자가 원하는 것 → 아직 아무도 안 다룬 부분

---

## STEP 3 — WebSearch 심층 리서치 (6가지 방향)

### 3-1. 데이터·연구·통계 수집
```
WebSearch: "{주제} 연구 데이터 통계 2024 2025 2026"
WebSearch: "{주제} 논문 연구결과"
WebSearch: "{주제} survey data statistics"
```
→ 대본에 쓸 수 있는 숫자와 출처 확보

### 3-2. 반대 사례·예외 케이스 수집
```
WebSearch: "{주제} 실패 사례"
WebSearch: "{주제} 반대 의견 왜 틀렸나"
WebSearch: "{주제} 예외 사례 언제 안 통하나"
```
→ "다들 말하는 것의 허점" → 차별화 각도

### 3-3. 비교 사례 수집
```
WebSearch: "{주제} 미국 일본 비교"
WebSearch: "{주제} 다른 나라는 어떻게 하나"
WebSearch: "{주제} A vs B 비교"
```
→ 국내에서 안 나오는 비교 관점

### 3-4. 응용·실전 사례 수집
```
WebSearch: "{주제} 실전 적용 사례"
WebSearch: "{주제} 실제로 해보니"
WebSearch: "{주제} 성공한 사람들의 공통점"
```
→ 시청자가 당장 써먹을 수 있는 것

### 3-5. 역사·타임라인 수집
```
WebSearch: "{주제} 역사 변천 언제부터"
WebSearch: "{주제} 과거 데이터 연도별"
```
→ 시간 흐름으로 설명하면 이해가 쉬워짐

### 3-6. 전문가 의견·인용 수집
```
WebSearch: "{주제} 전문가 의견"
WebSearch: "{주제} 교수 연구원 인터뷰"
```
→ 권위 있는 인용 → 신뢰도 ↑

---

## STEP 4 — 기사·뉴스 스크래핑 (gstack:scrape)

```bash
# 관련 기사 본문 수집
$B goto "{기사 URL}"
$B text  # 본문 전체 읽기

# 또는 스크래핑
$B scrape images --selector article  # 기사 이미지
```

**주요 출처:**
- 한국: 조선·동아·매경·한경·서울경제
- 증권사 리포트: 키움·삼성·NH·미래에셋
- 해외: Bloomberg, Reuters, FT

---

## STEP 5 — 리서치 브리프 작성

수집한 내용을 **5개 버킷**으로 정리:

```markdown
## 리서치 브리프 — {주제} ({날짜})

### 🔴 다들 하는 얘기 (이건 쓰지 말거나 반박용으로만)
- ...
- ...

### 🟢 아무도 안 한 얘기 (차별화 각도)
- ...
- ...

### 📊 쓸 수 있는 데이터/연구
| 출처 | 데이터 | 인용 |
|------|--------|------|

### 🔄 비교·응용 사례
- 미국 사례: ...
- 일본 사례: ...
- 실전 적용: ...

### 💡 예상치 못한 인사이트
(리서치 중 발견한 놀라운 것)
- ...
```

---

## STEP 6 — 퀄리티 체크

리서치 브리프 완성 후 확인:

```
□ "다들 아는 얘기"만 있는가? → 있으면 더 파야 함
□ 구체적 숫자/연도가 최소 5개 이상인가?
□ 다른 채널이 못 쓸 각도가 1개 이상인가?
□ 시청자가 모르는 반전 포인트가 있는가?
□ 비교 사례가 1개 이상인가?
```

5개 중 3개 미만이면 → STEP 3 재실행.

---

## 출력

`channel/yt/research_{주제}_{날짜}.md` 저장

---

## 다음 단계

→ `yt-planner` 호출 (리서치 브리프를 씬 구조로 변환)

---

## 이 스킬이 없으면 생기는 문제

| 증상 | 원인 |
|------|------|
| "다 아는 얘기" 대본 | 리서치 없이 Claude가 아는 것만 씀 |
| "수급을 봐라" 결론 | 구체적 데이터·사례 수집 없이 마무리 |
| 경쟁 영상과 차별화 없음 | 다른 영상 분석 없이 진행 |
| 권위 없는 주장 | 연구·통계 인용 없음 |

## 파이프라인 위치

```
yt-content-research
    ↓ (주제 확정)
yt-deep-research  ← 여기 (대본 전 필수)
    ↓ (리서치 브리프)
yt-planner
    ↓ (씬 구조)
yt-script-writer
    ↓ (대본)
yt-editor
```
