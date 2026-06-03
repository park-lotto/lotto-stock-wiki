---
name: yt-content-research
description: Use when starting any YouTube video — finds hot trending topics via real YouTube view counts, analyzes winning patterns, and selects the best angle. Must run BEFORE yt-planner or yt-script-writer.
metadata:
  tags: youtube, 소재, 리서치, 기획, 조회수, 트렌드
---

# yt-content-research — 소재 탐색 & 주제 선정

## 핵심 원칙

**3가지 오염 금지.**

1. **위키 오염 금지** — 소재 탐색 중 wiki 보면 채널 기존 관점에 갇힌다. wiki는 마지막에만.
2. **대화 오염 금지** — 사용자가 대화에서 언급한 키워드(종목명·이슈·인물)를 소재 탐색의 시작점으로 쓰지 않는다. "젠슨황 어때요?" 라고 물어봤다고 젠슨황을 소재로 넣으면 안 된다.
3. **선입견 오염 금지** — Claude가 이미 알고 있는 "요즘 핫한 것 같은" 지식으로 시작하지 않는다.

**올바른 시작**: 키워드 없이 YouTube 조회수 데이터를 먼저 본다. 데이터가 소재를 결정한다.

순서: **YouTube 조회수 실사** → 패턴 추출 → 주제 선정 → (마지막에만) wiki 데이터 보강.

---

## 자가 점검 — 소재 제안 전 4가지 체크 (전부 통과해야 진행)

> **1. 대화 오염**
> 이 소재가 대화에서 나왔는가? → YES = 제안 금지

> **2. 서비스 연결 ← 핵심**
> 이 주제를 고른 이유가 내 서비스·시스템을 보여주기 위해서인가?
> → YES = 탈락. 서비스 없이도 완전히 성립하는 각도로 재정의해야 통과.
>
> 실패 예시: "금양 상폐" → 투경 시스템 연결 (투경 시스템 없으면 영상 성립 안 됨 → 탈락)
> 통과 예시: "금양 상폐" → "2차전지 버블은 왜 터졌나" (시스템 없이 성립 → 통과)

> **3. 레퍼런스 터진 이유 일치**
> 레퍼런스 영상이 터진 이유가 내 버전과 같은가?
> KBS 금양 241만 → 터진 이유: 공감+공포 (서비스 무관)
> 내 버전도 같은 이유로 터져야 한다. 서비스가 들어오면 이유가 달라진다.

> **4. 최종: "서비스 없이 이 영상이 성립하는가?"**
> → NO면 각도를 바꿔라. 서비스 없는 버전으로 재설계하라.

## 명령어

- `/소재찾자` / `/소재찾기` / "소재 찾자"

---

## STEP 0 — 이슈 타이밍 사전 체크 ⚡ (가장 먼저)

**소재를 찾기 전에, 지금 날짜 기준으로 이슈가 살아있는지 확인한다.**

```
WebSearch: "{관심 이슈} 오늘 주식" → 오늘 자 뉴스 있으면 살아있음
WebSearch: "{관심 이슈} 유튜브 최신" → 최근 24~48시간 내 영상 조회수 확인
```

| 상태 | 기준 | 처리 |
|------|------|------|
| 🔴 살아있음 | 오늘/어제 뉴스 + 조회수 상승 중 | 지금 당장 시작 |
| 🟠 식어가는 중 | 3~5일 지남, 후속 재료 있음 | 각도 변경 후 진행 |
| ⚫ 이미 식었음 | 1주일+ 지남, 뉴스 없음 | 해당 이슈 폐기 → 새 소재 탐색 |

> 예시: "젠슨황 방한"은 6/3~5 이슈 → 6/7 이후면 ⚫ 식었음.  
> 이 경우 "젠슨황 방한 결과 이후 순환매" 등 **후속 재료 각도**로 변형하거나 다른 소재로 변경.

---

## STEP 1 — YouTube 조회수 실사 (gstack:browse 먼저)

**키워드 없이** "주식", "주식 투자" 광범위 검색으로 조회수 높은 것부터 본다.
WebSearch로 키워드 뽑는 것보다 YouTube 실제 조회수 데이터가 더 정확하다.

수집 후 **3단계 필터**:
1. **조회수 확인** — 최근 1~3개월 내 5만 이상
2. **이벤트 생존 여부** — 그 영상이 터진 이유(이벤트/재료)가 지금도 살아있는가?
3. **우리 소재 적용 가능성** — 이 채널 각도로 가져올 수 있는가?

이 3가지를 통과한 것만 소재 후보로 올린다.

---

## STEP 2 — 핫 키워드 서칭 (WebSearch)

```
WebSearch: "주식시장 핫이슈 오늘 {오늘날짜}"
WebSearch: "주식 유튜브 핫영상 {오늘날짜}"
WebSearch: "{관심 테마} 주식 수혜주 2026"
```

**목표**: 지금 시장에서 뭐가 뜨는지 3~5개 후보 키워드 추출.

---

## STEP 2 — YouTube 조회수 실사 (gstack:browse)

**규칙**: WebSearch 요약 말고 실제 조회수 숫자를 직접 확인.

```bash
B="$HOME/.claude/skills/gstack/browse/dist/browse"

# 키워드별 최신순 + 관련순 각각 검색
$B goto "https://www.youtube.com/results?search_query={키워드}&sp=CAMSAhAB"
sleep 3
$B js "
const results = [];
document.querySelectorAll('ytd-video-renderer').forEach(el => {
  const title = el.querySelector('#video-title')?.textContent?.trim();
  const meta = el.querySelectorAll('.inline-metadata-item');
  const views = [...meta].find(m => m.textContent.includes('회'))?.textContent?.trim();
  const ago = [...meta].find(m => m.textContent.includes('전') || m.textContent.includes('시간'))?.textContent?.trim();
  const channel = el.querySelector('.ytd-channel-name a')?.textContent?.trim();
  if(title) results.push({title: title.slice(0,60), views: views||'?', ago: ago||'?', channel: (channel||'').slice(0,20)});
});
JSON.stringify(results.slice(0,15), null, 1)
"
```

**수집 기준**:
- 최근 7일 이내 업로드
- 조회수 5만 이상 OR 업로드 24시간 내 1만 이상
- 주식·경제·재테크 카테고리

---

## STEP 3 — 4가지 터지는 패턴 분석

수집된 영상 제목에서 패턴 분류:

| 패턴 | 감정 | 공식 | 조회수 사례 |
|------|------|------|-----------|
| **경고+기대** | "사고 싶은데 물리면?" | 기대 → 바로 경고 → "그럼 어떻게?" | 38만 (2일) |
| **FOMO 후회** | "나만 손해볼 것 같다" | 숫자 + 비교대상 + "안 사면 후회" | 39만 (5개월) |
| **비밀 공개** | "남들 모르는 거 알고 싶다" | "숨겨진" / "히든카드" / "아무도 모르는" | 13만 (1일) |
| **속보 즉각성** | "실시간으로 따라가고 싶다" | "방금" / "지금 막" + 직접 행동 | 12만 (2일) |

---

## STEP 4 — 레퍼런스 시각화 (gstack:visual-companion)

수집된 영상 레퍼런스를 브라우저에 표시해 선택하게 한다.

```bash
# visual companion 서버 시작
bash ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/skills/brainstorming/scripts/start-server.sh \
  --project-dir "$(pwd)"
```

HTML에 레퍼런스 카드 표시:
- 영상 제목 + 조회수 + 업로드일
- 패턴 유형 (경고+기대 / FOMO / 비밀 / 속보)
- 이 채널에 적용할 훅 변형 제안

**복수 선택 허용** — 패턴 조합 가능.

---

## STEP 5 — 주제 + 각도 확정

사용자가 레퍼런스 선택 후:

```
선택된 패턴: {패턴명}
주제: {키워드}
각도: {레퍼런스에서 뽑은 각도}
훅 초안: "{제목 후보}"
업로드 데드라인: {이슈 만료 전 날짜}
```

---

## STEP 6 — wiki 데이터 연결 (마지막에만)

주제와 각도가 확정된 후에만 위키 참조:

```
wiki/L5_섹터/{관련섹터}/sector_{섹터}.md  → 섹터 온도, 대장주, 이벤트
wiki/L5_섹터/{관련섹터}/stock/stock_{종목}.md → 수급, 컨센, 수출
wiki/log.md → 최근 관련 ingest 내용
```

없는 데이터는 "(데이터 없음)" 표시 — calc_oscillator.py 실행 권고.

---

## 출력 — `channel/yt/yt_{주제}_소재탐색.md`

```markdown
# 소재 탐색 — {주제} ({날짜})

## 선택 주제
{주제} | {각도}

## 레퍼런스 영상
| 제목 | 조회수 | 날짜 | 패턴 | 배울 것 |
|------|--------|------|------|---------|

## 훅 초안 (3개)
1. {훅1}
2. {훅2}
3. {훅3}

## 업로드 데드라인
{날짜} — {이유}

## wiki 데이터 연결
{있는 것 / 없는 것}
```

---

## 다음 단계

→ `yt-planner` 호출 (씬 구성, 기획서 작성)
